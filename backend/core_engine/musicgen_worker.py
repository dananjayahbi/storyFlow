"""One-shot MusicGen worker for the CUDA Python 3.11 environment.

Django (Python 3.14) launches this file with the same interpreter used by Qwen
TTS (Python 3.11 + CUDA PyTorch).  It loads ``facebook/musicgen-small`` through
Transformers, generates every segment on the GPU, crossfades them, writes a WAV
file and exits — which guarantees all VRAM is released.

Usage::

    python musicgen_worker.py --probe --model models/musicgen-small
    python musicgen_worker.py --job job.json --model models/musicgen-small

The worker never imports Django and intentionally limits CPU threads because
all heavy work must happen on the GPU.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import traceback
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# facebook/musicgen-small model.safetensors, as published on Hugging Face.
MODEL_WEIGHTS_FILE = "model.safetensors"
MODEL_WEIGHTS_SIZE = 2364427288
MODEL_WEIGHTS_SHA256 = (
    "1bdc99d43eb6c775967df24b65b0a9f847c0907e95664698d93b5a1c35f5090d"
)
_CHECKSUM_MARKER = ".model.safetensors.verified"


def _sha256_file(path: str, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(chunk_size), b""):
            digest.update(block)
    return digest.hexdigest()


def _weights_integrity(model_dir: str) -> dict:
    """Verify the checkpoint before inference.

    A truncated or partially-resumed ``model.safetensors`` still loads without
    an error, but MusicGen then produces pure noise.  The SHA-256 is computed
    once and cached in a marker file keyed by size + mtime, so later probes and
    generations only pay for a stat() call.

    Returns ``{"ok": bool, "checked": bool, "reason": str | None}``.
    """
    if os.environ.get("MUSICGEN_SKIP_CHECKSUM", "").strip().lower() in (
        "1", "true", "yes", "on",
    ):
        return {"ok": True, "checked": False, "reason": None}

    path = os.path.join(model_dir, MODEL_WEIGHTS_FILE)
    if not os.path.isfile(path):
        return {
            "ok": False,
            "checked": True,
            "reason": f"{MODEL_WEIGHTS_FILE} is missing from {model_dir}.",
        }

    size = os.path.getsize(path)
    if size != MODEL_WEIGHTS_SIZE:
        return {
            "ok": False,
            "checked": True,
            "reason": (
                f"{MODEL_WEIGHTS_FILE} is {size} bytes, expected "
                f"{MODEL_WEIGHTS_SIZE}: the download is truncated."
            ),
        }

    try:
        modified = int(os.path.getmtime(path))
    except OSError:
        modified = 0
    stamp = f"{size}:{modified}:{MODEL_WEIGHTS_SHA256}"
    marker = os.path.join(model_dir, _CHECKSUM_MARKER)
    try:
        with open(marker, "r", encoding="utf-8") as handle:
            if handle.read().strip() == stamp:
                return {
                    "ok": True,
                    "checked": True,
                    "reason": None,
                    "sha256": MODEL_WEIGHTS_SHA256,
                    "cached": True,
                }
    except OSError:
        pass

    actual = _sha256_file(path)
    if actual.lower() != MODEL_WEIGHTS_SHA256.lower():
        return {
            "ok": False,
            "checked": True,
            "reason": (
                f"{MODEL_WEIGHTS_FILE} is corrupt (SHA-256 {actual}, expected "
                f"{MODEL_WEIGHTS_SHA256}); this generates pure noise. Run "
                "scripts/download_musicgen.py again."
            ),
        }

    try:
        with open(marker, "w", encoding="utf-8") as handle:
            handle.write(stamp)
    except OSError:
        pass
    return {
        "ok": True,
        "checked": True,
        "reason": None,
        "sha256": MODEL_WEIGHTS_SHA256,
        "cached": False,
    }


def _nvidia_smi_info() -> dict:
    """Read GPU name/VRAM without creating a CUDA context in this process."""
    try:
        completed = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.free",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        line = (completed.stdout or "").strip().splitlines()[0]
        name, total_mb, free_mb = [part.strip() for part in line.split(",")]
        return {
            "gpu": name,
            "vram_total_gb": round(float(total_mb) / 1024, 2),
            "vram_free_gb": round(float(free_mb) / 1024, 2),
        }
    except Exception:
        return {"gpu": None, "vram_total_gb": None, "vram_free_gb": None}


def _probe(model_dir: str) -> dict:
    result = {
        "available": False,
        "model_dir": model_dir,
        "python_version": sys.version.split()[0],
        "cuda_available": False,
        "transformers_version": None,
        "torch_version": None,
        "gpu": None,
        "vram_total_gb": None,
        "vram_free_gb": None,
    }
    try:
        import torch
        import transformers
    except Exception as exc:
        result["reason"] = f"torch/transformers import failed: {exc}"
        return result

    result["torch_version"] = getattr(torch, "__version__", "unknown")
    result["transformers_version"] = getattr(transformers, "__version__", "unknown")
    result["cuda_available"] = bool(torch.cuda.is_available())
    # nvidia-smi is safe while a TTS model still owns VRAM: it does not create
    # a competing CUDA context in this short-lived probe process.
    result.update(_nvidia_smi_info())

    required = [
        "config.json",
        "generation_config.json",
        "preprocessor_config.json",
        "tokenizer.json",
    ]
    missing = [
        relative for relative in required
        if not os.path.isfile(os.path.join(model_dir, relative))
    ]
    if not any(
        os.path.isfile(os.path.join(model_dir, weights))
        for weights in ("model.safetensors", "pytorch_model.bin")
    ):
        missing.append("model.safetensors")
    result["model_present"] = not missing
    result["missing_files"] = missing

    integrity = {"ok": True, "checked": False, "reason": None}
    if not missing:
        integrity = _weights_integrity(model_dir)
    result["weights_verified"] = bool(
        integrity.get("ok") and integrity.get("checked")
    )
    result["weights_sha256"] = integrity.get("sha256")

    if not result["cuda_available"]:
        result["reason"] = (
            "CUDA is not available in the MusicGen worker environment."
        )
    elif missing:
        result["reason"] = (
            "Model files are incomplete at "
            f"{model_dir}: {', '.join(missing)}. Download "
            "facebook/musicgen-small from Hugging Face."
        )
    elif not integrity["ok"]:
        result["reason"] = integrity["reason"]
    else:
        result["available"] = True
        result["reason"] = None
    return result


def _print(event: str, payload: dict) -> None:
    print(f"{event} {json.dumps(payload)}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="StoryFlow MusicGen GPU worker")
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--job", help="Path to the JSON generation job")
    parser.add_argument("--model", required=True, help="Local musicgen-small dir")
    args = parser.parse_args()

    if args.probe:
        _print("PROBE", _probe(args.model))
        return 0

    if not args.job:
        parser.error("--job is required unless --probe is used")

    try:
        import torch

        # Refuse to generate from a truncated/corrupt checkpoint: it loads
        # silently but produces pure noise.
        integrity = _weights_integrity(args.model)
        if not integrity["ok"]:
            raise RuntimeError(integrity["reason"])

        # Keep the CPU nearly idle; inference must happen on the GPU.
        torch.set_num_threads(1)
        try:
            torch.set_num_interop_threads(1)
        except RuntimeError:
            pass
        if not torch.cuda.is_available():
            raise RuntimeError(
                "CUDA is not available; refusing to run MusicGen on CPU."
            )
        device = "cuda"
        torch.cuda.init()

        with open(args.job, "r", encoding="utf-8") as handle:
            job = json.load(handle)

        from core_engine import music_generator as mg

        plan_data = dict(job.get("plan") or {})
        plan = mg.MusicPlan(
            bpm=int(plan_data.get("bpm", 70)),
            root_key=str(plan_data.get("root_key", "D")),
            mode=str(plan_data.get("mode", "minor")),
            prompts=list(plan_data.get("prompts") or []),
            anchor=str(plan_data.get("anchor", "")),
            style=str(
                plan_data.get("style")
                or "instrumental cinematic documentary score"
            ),
            metadata={
                key: value
                for key, value in plan_data.items()
                if key not in {
                    "bpm", "root_key", "mode", "prompts", "anchor", "style",
                }
            },
        )
        segments = job.get("segments") or []
        total = len(segments)

        _print("PROGRESS", {
            "current": 0,
            "total": total,
            "description": "Loading MusicGen on CUDA…",
        })

        def on_progress(current, total_segments, description):
            _print("PROGRESS", {
                "current": current,
                "total": total_segments,
                "description": description,
            })

        result = mg.synthesize_soundtrack_transformers(
            segments,
            job["output_path"],
            model_dir=args.model,
            plan=plan,
            crossfade_seconds=float(job.get("crossfade_seconds", 3.0)),
            progress=on_progress,
            device=device,
        )

        try:
            torch.cuda.synchronize()
            result["vram_after_generation_gb"] = round(
                torch.cuda.memory_allocated(0) / 1e9, 2
            )
            result["gpu"] = torch.cuda.get_device_name(0)
        except Exception:
            pass

        _print("RESULT", result)
        return 0
    except Exception as exc:
        traceback.print_exc()
        _print("ERROR", {"error": str(exc)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
