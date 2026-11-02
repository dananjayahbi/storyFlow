"""Qwen3-TTS client for the Django process.

Django runs on Python 3.14 while ``qwen-tts`` requires Python 3.10-3.12, so the
model lives in a **separate, dedicated virtualenv** and is driven as a
long-lived child process:

    Django (3.14)  --JSON lines-->  qwen_engine.py (3.11 + torch/CUDA)

Reasons for the process split:

* version incompatibility (qwen-tts does not support 3.14);
* the GIL stalls and CUDA-context growth caused by sampling would otherwise
  freeze the dev server and the Windows compositor;
* a CUDA OOM or crash restarts the worker instead of taking the API down.

This module deliberately **never imports torch or qwen_tts**.  It exposes the
same result contract as :func:`core_engine.tts_wrapper.generate_audio` so the
rest of StoryFlow can treat both engines identically.

GPU-only: the engine refuses to run without CUDA.  There is no CPU fallback.
"""

from __future__ import annotations

import atexit
import json
import logging
import os
import queue
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

ENGINE_SCRIPT = Path(__file__).resolve().parent / "qwen_engine.py"

#: Populated by ``probe()``; cheap path-based availability uses this instead.
_PROBE_CACHE: dict | None = None
_PROBE_AT: float = 0.0
_PROBE_TTL = 60.0

# Synthesis may need a cold model load (50-100 s) plus generation.  The bulk
# worker is already asynchronous, so a generous ceiling is safe.
DEFAULT_TIMEOUT = 900.0


# ---------------------------------------------------------------------------
# Interpreter discovery
# ---------------------------------------------------------------------------

def resolve_qwen_python() -> str | None:
    """Return the Python 3.11 interpreter that has ``qwen-tts`` installed.

    Order:

    1. ``QWEN_TTS_PYTHON`` setting / env var (explicit override)
    2. ``backend/qwen_tts/.venv`` (copied from the TTS-test venv)
    3. the original ``E:\\test_repos\\TTS-test\\.venv`` (for machines that
       have not run the setup script yet)
    """
    candidates: list[str] = []

    try:
        from django.conf import settings

        configured = getattr(settings, "QWEN_TTS_PYTHON", None)
        if configured:
            candidates.append(str(configured))
    except Exception:  # settings not configured (e.g. import-time in tests)
        pass

    env_override = os.environ.get("QWEN_TTS_PYTHON")
    if env_override:
        candidates.append(env_override)

    try:
        from django.conf import settings

        base_dir = Path(settings.BASE_DIR)
    except Exception:
        base_dir = Path(__file__).resolve().parent.parent

    candidates.append(
        str(base_dir / "qwen_tts" / ".venv" / "Scripts" / "python.exe")
    )
    candidates.append(r"E:\test_repos\TTS-test\.venv\Scripts\python.exe")

    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            return candidate
    return None


def _site_packages(python: str) -> Path:
    return Path(python).resolve().parent.parent / "Lib" / "site-packages"


def qwen_is_installed() -> bool:
    """True when the dedicated interpreter and ``qwen_tts`` package exist.

    This is a cheap filesystem check (no subprocess, no CUDA) used by request
    validation so a missing engine fails fast with a helpful message.
    """
    python = resolve_qwen_python()
    if not python:
        return False
    return (_site_packages(python) / "qwen_tts").is_dir()


def probe(force: bool = False) -> dict:
    """Run the child's ``--probe`` mode and cache the result briefly."""
    global _PROBE_CACHE, _PROBE_AT

    now = time.time()
    if not force and _PROBE_CACHE is not None and (now - _PROBE_AT) < _PROBE_TTL:
        return _PROBE_CACHE

    python = resolve_qwen_python()
    if not python:
        result = {
            "ok": False,
            "error": (
                "Qwen TTS interpreter not found. Run scripts/setup_qwen_tts.ps1 "
                "to copy the TTS-test virtualenv into backend/qwen_tts/.venv."
            ),
        }
        _PROBE_CACHE, _PROBE_AT = result, now
        return result

    try:
        proc = subprocess.run(
            [python, "-u", str(ENGINE_SCRIPT), "--probe"],
            capture_output=True,
            text=True,
            timeout=180,
        )
        payload = None
        for line in (proc.stdout or "").splitlines():
            line = line.strip()
            if line.startswith("{"):
                payload = json.loads(line)
                break
        if payload is None:
            payload = {
                "ok": False,
                "error": (proc.stderr or "probe produced no output").strip()[-800:],
            }
        if not payload.get("ok"):
            payload["python"] = python
    except Exception as exc:
        payload = {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "python": python,
        }

    _PROBE_CACHE, _PROBE_AT = payload, now
    return payload


def invalidate_probe() -> None:
    global _PROBE_CACHE, _PROBE_AT
    _PROBE_CACHE = None
    _PROBE_AT = 0.0


# ---------------------------------------------------------------------------
# Long-lived worker process
# ---------------------------------------------------------------------------

class _EngineProcess:
    """One supervised ``qwen_engine.py --serve`` child process."""

    def __init__(self) -> None:
        self._proc: subprocess.Popen | None = None
        self._responses: queue.Queue[str | None] = queue.Queue()
        self._reader: threading.Thread | None = None
        self._log_handle = None
        self._lock = threading.RLock()

    # -- process lifecycle -------------------------------------------------
    def _log_path(self) -> str:
        try:
            from django.conf import settings

            root = Path(settings.MEDIA_ROOT)
        except Exception:
            root = Path(__file__).resolve().parent.parent / "Storage"
        try:
            root.mkdir(parents=True, exist_ok=True)
            return str(root / "qwen_tts_engine.log")
        except Exception:
            return os.devnull

    def _read_stdout(self, proc: subprocess.Popen) -> None:
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                self._responses.put(line)
        except Exception:
            logger.debug("Qwen stdout reader stopped", exc_info=True)
        finally:
            self._responses.put(None)

    def start(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            return

        python = resolve_qwen_python()
        if not python:
            raise RuntimeError(
                "Qwen TTS is not installed. Run scripts/setup_qwen_tts.ps1 "
                "to copy the GPU virtualenv into backend/qwen_tts/.venv."
            )

        env = dict(os.environ)
        env.setdefault("HF_HUB_DISABLE_XET", "1")
        env.setdefault("PYTHONIOENCODING", "utf-8")

        self._log_handle = open(self._log_path(), "ab", buffering=0)
        creationflags = (
            subprocess.CREATE_NO_WINDOW
            if sys.platform == "win32"
            else 0
        )
        logger.info("Starting Qwen3-TTS worker: %s", python)
        self._proc = subprocess.Popen(
            [python, "-u", str(ENGINE_SCRIPT), "--serve"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self._log_handle,
            text=True,
            encoding="utf-8",
            bufsize=1,
            cwd=str(ENGINE_SCRIPT.parent),
            env=env,
            creationflags=creationflags,
        )
        self._reader = threading.Thread(
            target=self._read_stdout,
            args=(self._proc,),
            name="qwen-tts-stdout",
            daemon=True,
        )
        self._reader.start()

    def stop(self) -> None:
        proc, self._proc = self._proc, None
        if proc is not None:
            try:
                if proc.stdin:
                    proc.stdin.close()
            except Exception:
                pass
            try:
                proc.terminate()
                proc.wait(timeout=10)
            except Exception:
                try:
                    proc.kill()
                    proc.wait(timeout=5)
                except Exception:
                    pass
        if self._log_handle is not None:
            try:
                self._log_handle.close()
            except Exception:
                pass
            self._log_handle = None
        # Drain stale responses so the next call cannot read an old reply.
        while True:
            try:
                self._responses.get_nowait()
            except queue.Empty:
                break

    def _log_tail(self, lines: int = 12) -> str:
        try:
            path = self._log_path()
            if path == os.devnull or not os.path.isfile(path):
                return ""
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                tail = handle.readlines()[-lines:]
            return "".join(tail).strip()
        except Exception:
            return ""

    def _dead_error(self) -> RuntimeError:
        tail = self._log_tail()
        detail = f"\nLast engine output:\n{tail}" if tail else ""
        return RuntimeError(
            "The Qwen TTS engine process exited. It requires a CUDA GPU and "
            "never falls back to CPU; check backend/Storage/qwen_tts_engine.log "
            f"for details.{detail}"
        )

    # -- RPC ---------------------------------------------------------------
    def call(self, cmd: str, payload: dict | None = None,
             timeout: float = DEFAULT_TIMEOUT) -> dict:
        with self._lock:
            self.start()
            assert self._proc is not None and self._proc.stdin is not None

            request_id = uuid.uuid4().hex
            message = json.dumps(
                {"id": request_id, "cmd": cmd, "payload": payload or {}},
                ensure_ascii=False,
            )

            try:
                self._proc.stdin.write(message + "\n")
                self._proc.stdin.flush()
            except (BrokenPipeError, OSError) as exc:
                self.stop()
                raise self._dead_error() from exc

            deadline = time.time() + timeout
            while True:
                remaining = max(0.0, deadline - time.time())
                try:
                    line = self._responses.get(timeout=remaining)
                except queue.Empty:
                    self.stop()
                    raise TimeoutError(
                        "The Qwen TTS engine did not respond in time and was "
                        "restarted. The GPU may be out of memory - try shorter "
                        "text or a lower 'max new tokens'."
                    )

                if line is None:
                    self.stop()
                    raise self._dead_error()

                line = line.strip()
                if not line:
                    continue
                try:
                    response = json.loads(line)
                except json.JSONDecodeError:
                    logger.debug("Ignoring non-JSON Qwen output: %r", line[:200])
                    continue

                if response.get("id") not in (request_id, None):
                    continue  # stale reply from a previous, killed request

                if not response.get("ok"):
                    raise RuntimeError(response.get("error", "Qwen TTS failed"))
                return response.get("result") or {}


_ENGINE = _EngineProcess()


def shutdown() -> None:
    """Stop the worker (frees VRAM).  Safe to call multiple times."""
    _ENGINE.stop()


atexit.register(shutdown)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_status() -> dict:
    """Return engine status, including whether a GPU is usable."""
    if not qwen_is_installed():
        return {
            "available": False,
            "cuda": False,
            "error": "Qwen TTS is not installed.",
            "python": resolve_qwen_python(),
        }
    try:
        result = _ENGINE.call("status", timeout=300)
        return {"available": bool(result.get("cuda")), **result}
    except Exception as exc:
        return {
            "available": False,
            "cuda": False,
            "error": str(exc),
            "python": resolve_qwen_python(),
        }


def unload() -> dict:
    """Unload the resident checkpoint and free VRAM."""
    if not qwen_is_installed():
        return {"ok": False, "error": "Qwen TTS is not installed."}
    try:
        return {"ok": True, **_ENGINE.call("unload", timeout=300)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def generate_audio(
    text: str,
    output_path: str,
    *,
    mode: str = "custom_voice",
    speaker: str = "Aiden",
    language: str = "English",
    instruct: str = "",
    max_new_tokens: int = 1024,
    x_vector_only: bool = True,
    reference_audio_path: str | None = None,
    reference_text: str = "",
    speed: float = 1.0,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict:
    """Synthesize narration with Qwen3-TTS.

    Returns the same shape as ``tts_wrapper.generate_audio`` so callers do not
    need engine-specific branches::

        {"success": True, "audio_path": str, "duration": float,
         "sample_rate": int, "engine": "qwen"}
    """
    if not isinstance(text, str) or not text.strip():
        return {"success": False, "error": "Text is empty or whitespace-only."}
    if not output_path:
        return {"success": False, "error": "Output path is required."}

    if not qwen_is_installed():
        return {
            "success": False,
            "error": (
                "Qwen TTS is not installed. Run scripts/setup_qwen_tts.ps1 "
                "to copy the GPU virtualenv, then restart the backend."
            ),
        }

    try:
        if mode == "clone":
            if not reference_audio_path:
                return {
                    "success": False,
                    "error": (
                        "Voice cloning needs a reference voice. Upload one in "
                        "Settings -> Voice References and select it."
                    ),
                }
            payload = {
                "text": text,
                "language": language or "Auto",
                "ref_audio_path": reference_audio_path,
                "ref_text": reference_text or "",
                "x_vector_only": bool(x_vector_only),
                "max_new_tokens": int(max_new_tokens),
                "output_path": output_path,
                "speed": float(speed),
            }
            result = _ENGINE.call("clone", payload, timeout=timeout)
        else:
            payload = {
                "text": text,
                "language": language or "Auto",
                "speaker": speaker or "Aiden",
                "instruct": instruct or "",
                "max_new_tokens": int(max_new_tokens),
                "output_path": output_path,
                "speed": float(speed),
            }
            result = _ENGINE.call("custom_voice", payload, timeout=timeout)

        duration = result.get("duration")
        if not duration or duration <= 0:
            from core_engine.audio_utils import get_audio_duration

            duration = get_audio_duration(output_path)

        return {
            "success": True,
            "audio_path": output_path,
            "duration": float(duration),
            "sample_rate": int(result.get("sample_rate", 24000)),
            "engine": "qwen",
            "model_id": result.get("model_id", ""),
        }
    except TimeoutError as exc:
        logger.error("Qwen TTS timed out: %s", exc)
        return {"success": False, "error": str(exc)}
    except Exception as exc:
        logger.error("Qwen TTS failed: %s", exc, exc_info=True)
        return {
            "success": False,
            "error": f"Qwen TTS failed: {exc}",
        }
