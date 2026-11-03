"""Run MusicGen on the CUDA Python 3.11 worker.

The Django process runs on Python 3.14 with CPU-only PyTorch.  AudioCraft (and
the Transformers MusicGen implementation) therefore cannot be imported there.
This module launches ``musicgen_worker.py`` inside the already-provisioned
Python 3.11 + CUDA environment used by Qwen TTS, sends it a JSON generation
job, and streams progress back.

Nothing here imports torch, so importing it from Django is cheap.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from core_engine.music_generator import MusicGenerationError

logger = logging.getLogger(__name__)

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _BACKEND_DIR.parent
_WORKER = Path(__file__).resolve().with_name("musicgen_worker.py")

_PROBE_TTL_SECONDS = 120.0
_PROBE_LOCK = threading.Lock()
_PROBE_CACHE: dict | None = None
_PROBE_AT = 0.0


def _configured_python() -> str | None:
    value = os.environ.get("MUSICGEN_PYTHON")
    if value:
        return value
    try:
        from django.conf import settings

        return getattr(settings, "MUSICGEN_PYTHON", None)
    except Exception:
        return None


def resolve_python() -> str | None:
    """Return a Python executable that has CUDA PyTorch + Transformers."""
    explicit = _configured_python()
    if explicit and os.path.isfile(explicit):
        return explicit

    candidates = [
        _BACKEND_DIR / "musicgen" / ".venv" / "Scripts" / "python.exe",
        _BACKEND_DIR / "qwen_tts" / ".venv" / "Scripts" / "python.exe",
        _BACKEND_DIR / "musicgen" / ".venv" / "bin" / "python",
        _BACKEND_DIR / "qwen_tts" / ".venv" / "bin" / "python",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return explicit


def _configured_model_dir() -> str | None:
    value = os.environ.get("MUSICGEN_MODEL_DIR")
    if value:
        return value
    try:
        from django.conf import settings

        return getattr(settings, "MUSICGEN_MODEL_DIR", None)
    except Exception:
        return None


def resolve_model_dir() -> str:
    explicit = _configured_model_dir()
    if explicit:
        return explicit
    return str(_PROJECT_ROOT / "models" / "musicgen-small")


def _worker_env() -> dict:
    env = os.environ.copy()
    env.update({
        "PYTHONUNBUFFERED": "1",
        "TOKENIZERS_PARALLELISM": "false",
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        # The checkpoint is local; never fall back to network downloads.
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        # Reduce fragmentation on the 6 GB card.
        "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True",
    })
    return env


def _run_probe(python: str, model_dir: str) -> dict:
    command = [python, str(_WORKER), "--probe", "--model", model_dir]
    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        completed = subprocess.run(
            command,
            cwd=str(_BACKEND_DIR),
            env=_worker_env(),
            capture_output=True,
            text=True,
            timeout=180,
            **kwargs,
        )
    except Exception as exc:
        return {
            "available": False,
            "reason": f"Could not start the MusicGen worker: {exc}",
        }

    output = (completed.stdout or "").strip().splitlines()
    for line in reversed(output):
        if line.startswith("PROBE "):
            try:
                return json.loads(line[len("PROBE "):])
            except json.JSONDecodeError:
                break
    detail = (completed.stderr or completed.stdout or "").strip().splitlines()
    return {
        "available": False,
        "reason": (
            "MusicGen worker probe failed. "
            + " ".join(detail[-4:])[:800]
        ).strip(),
    }


def probe(force: bool = False) -> dict:
    """Return cached GPU/runtime availability for the external worker."""
    global _PROBE_CACHE, _PROBE_AT

    if os.environ.get("MUSICGEN_DISABLE_EXTERNAL", "").strip().lower() in (
        "1", "true", "yes", "on",
    ):
        return {
            "available": False,
            "reason": "External MusicGen worker disabled by MUSICGEN_DISABLE_EXTERNAL.",
        }

    with _PROBE_LOCK:
        if (
            not force
            and _PROBE_CACHE is not None
            and (time.monotonic() - _PROBE_AT) < _PROBE_TTL_SECONDS
        ):
            return dict(_PROBE_CACHE)

        python = resolve_python()
        model_dir = resolve_model_dir()
        if not python:
            result = {
                "available": False,
                "reason": (
                    "No CUDA Python environment found. Set MUSICGEN_PYTHON to a "
                    "Python 3.9-3.12 interpreter with CUDA PyTorch and "
                    "Transformers."
                ),
                "model_dir": model_dir,
            }
        elif not os.path.isfile(python):
            result = {
                "available": False,
                "reason": f"MUSICGEN_PYTHON does not exist: {python}",
                "python": python,
                "model_dir": model_dir,
            }
        elif not os.path.isdir(model_dir):
            result = {
                "available": False,
                "reason": (
                    f"MusicGen model not found at {model_dir}. Download "
                    "facebook/musicgen-small from Hugging Face."
                ),
                "python": python,
                "model_dir": model_dir,
            }
        else:
            result = _run_probe(python, model_dir)
            # ``python`` is the executable Django must launch; the worker's
            # own ``python_version`` is kept separately for display.
            result["python"] = python
            result.setdefault("model_dir", model_dir)

        _PROBE_CACHE = dict(result)
        _PROBE_AT = time.monotonic()
        return result


def is_available() -> bool:
    return bool(probe().get("available"))


def run_soundtrack(
    *,
    segments,
    plan,
    output_path: str,
    sample_rate: int,
    crossfade_seconds: float,
    progress=None,
) -> dict:
    """Run one soundtrack job in the external CUDA worker."""
    status = probe()
    if not status.get("available"):
        raise MusicGenerationError(
            status.get("reason") or "MusicGen GPU worker is not available."
        )

    python = status.get("python") or resolve_python()
    model_dir = status.get("model_dir") or resolve_model_dir()
    if not python:
        raise MusicGenerationError("No MusicGen Python interpreter configured.")

    payload = {
        "segments": [
            {
                "index": segment.index,
                "text": segment.text,
                "image_prompt": segment.image_prompt,
                "duration": segment.duration,
            }
            for segment in segments
        ],
        "plan": plan.to_dict(),
        "output_path": output_path,
        "crossfade_seconds": crossfade_seconds,
        "sample_rate": sample_rate,
    }

    handle, job_path = tempfile.mkstemp(prefix="storyflow-musicgen-", suffix=".json")
    os.close(handle)
    try:
        with open(job_path, "w", encoding="utf-8") as job_file:
            json.dump(payload, job_file)

        command = [
            python,
            str(_WORKER),
            "--job", job_path,
            "--model", model_dir,
        ]
        kwargs = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        logger.info("Starting MusicGen GPU worker: %s", " ".join(command))
        process = subprocess.Popen(
            command,
            cwd=str(_BACKEND_DIR),
            env=_worker_env(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            **kwargs,
        )

        result = None
        output_lines: list[str] = []
        assert process.stdout is not None
        for raw_line in process.stdout:
            line = raw_line.strip()
            if not line:
                continue
            output_lines.append(line)
            if len(output_lines) > 120:
                output_lines.pop(0)

            if line.startswith("PROGRESS "):
                try:
                    event = json.loads(line[len("PROGRESS "):])
                except json.JSONDecodeError:
                    continue
                if progress:
                    progress(
                        int(event.get("current", 0)),
                        int(event.get("total", len(segments))),
                        str(event.get("description") or "Generating music…"),
                    )
            elif line.startswith("RESULT "):
                try:
                    result = json.loads(line[len("RESULT "):])
                except json.JSONDecodeError:
                    result = None

        return_code = process.wait(timeout=60)
        if return_code != 0 or result is None:
            tail = " | ".join(output_lines[-8:])
            raise MusicGenerationError(
                "MusicGen GPU worker failed"
                + (f": {tail}" if tail else ".")
            )
        return result
    finally:
        try:
            os.remove(job_path)
        except OSError:
            pass
