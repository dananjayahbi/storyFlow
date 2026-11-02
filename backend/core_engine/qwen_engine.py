"""Qwen3-TTS inference engine (runs in the dedicated Python 3.11 GPU venv).

This file is **never imported by Django**.  It is executed as a child process
by :mod:`core_engine.qwen_client` because:

* ``qwen-tts`` pins ``transformers==4.57.3`` and only supports Python 3.10-3.12,
  while the Django service runs on Python 3.14.
* Torch/CUDA work must stay out of the web process.  Sampling holds the GIL
  for long stretches and inflates the CUDA context, which would freeze the
  Django dev server (and the Windows compositor) during synthesis.

Protocol
--------
Newline-delimited JSON over stdin/stdout::

    parent -> engine : {"id": "...", "cmd": "custom_voice", "payload": {...}}
    engine -> parent : {"id": "...", "ok": true, "result": {...}}
                       {"id": "...", "ok": false, "error": "..."}

All logging goes to stderr so stdout stays a clean protocol channel.

Hardware policy
---------------
**GPU only.**  ``torch.cuda.is_available()`` is a hard requirement; this module
refuses to run on CPU rather than silently producing very slow output.  The
VRAM cap (``QWEN_TTS_VRAM_FRACTION``, default ``0.72``) makes PyTorch raise a
clean OOM instead of spilling into Windows shared GPU memory.

Tuned for a GTX 1660 Ti (6 GB, Turing):

* ``bfloat16`` -- float16 trips a device-side assert in the code predictor.
* ``sdpa`` -- FlashAttention-2 has no prebuilt Windows wheels.
* No ``PYTORCH_CUDA_ALLOC_CONF`` -- a small ``max_split_size_mb`` increases
  reserved-but-unused VRAM on this card.
"""

from __future__ import annotations

import gc
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any

os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

BASE_MODEL_ID = os.environ.get(
    "QWEN_TTS_BASE_MODEL", "Qwen/Qwen3-TTS-12Hz-0.6B-Base"
)
CUSTOM_VOICE_MODEL_ID = os.environ.get(
    "QWEN_TTS_CUSTOM_VOICE_MODEL", "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"
)

# Kept as a module global so ``torch`` is only imported when a command that
# needs it arrives (so ``status`` is cheap for the parent's availability probe).
torch = None
DTYPE_NAME = "bfloat16"
ATTN_IMPLEMENTATION = "sdpa"
VRAM_FRACTION = float(os.environ.get("QWEN_TTS_VRAM_FRACTION", "0.72"))

# ~40 s of speech at 1024 codec tokens. The old 2048 default could not fit in a
# 6 GB card and only made OOM more likely.
DEFAULT_MAX_TOKENS = 1024
MAX_TOKENS_LIMIT = 2048

# Sentence-level chunking keeps each synthesis call inside the token budget.
MAX_CHUNK_CHARS = 360

SPEAKERS = {
    "Aiden": ("Aiden - Sunny American male (documentary / narrative)", "English"),
    "Ryan": ("Ryan - Dynamic male, rhythmic pacing", "English"),
    "Vivian": ("Vivian - Bright young female", "Chinese"),
    "Serena": ("Serena - Warm, gentle young female", "Chinese"),
    "Uncle_Fu": ("Uncle_Fu - Seasoned, mellow male", "Chinese"),
    "Dylan": ("Dylan - Youthful Beijing male", "Chinese"),
    "Eric": ("Eric - Lively Sichuan male", "Chinese"),
    "Ono_Anna": ("Ono_Anna - Playful Japanese female", "Japanese"),
    "Sohee": ("Sohee - Warm Korean female", "Korean"),
}

LANGUAGES = [
    "Auto",
    "Chinese",
    "English",
    "Japanese",
    "Korean",
    "German",
    "French",
    "Russian",
    "Portuguese",
    "Spanish",
    "Italian",
]


def log(message: str) -> None:
    print(f"[qwen3-tts] {message}", file=sys.stderr, flush=True)


def _require_torch():
    global torch
    if torch is None:
        import torch as _torch  # noqa: PLC0415 -- deliberate lazy import

        torch = _torch
    return torch


def require_cuda() -> None:
    """Raise unless a CUDA device is present.  Never falls back to CPU."""
    t = _require_torch()
    if not t.cuda.is_available():
        raise RuntimeError(
            "Qwen3-TTS requires a CUDA GPU and none was found. "
            "The Qwen engine never falls back to CPU - use Kokoro instead, "
            "or install a CUDA build of PyTorch."
        )


def configure_cuda() -> None:
    require_cuda()
    t = _require_torch()
    total = t.cuda.get_device_properties(0).total_memory
    limit = int(total * VRAM_FRACTION)
    # Raises a clean OOM instead of spilling into shared GPU memory.
    t.cuda.set_per_process_memory_fraction(VRAM_FRACTION, 0)
    log(
        f"VRAM cap {limit / 1024**3:.2f} GB of {total / 1024**3:.2f} GB "
        f"(fraction {VRAM_FRACTION})"
    )


def describe_device() -> str:
    t = _require_torch()
    if not t.cuda.is_available():
        return "CPU (no CUDA device found)"
    name = t.cuda.get_device_name(0)
    total = t.cuda.get_device_properties(0).total_memory / (1024**3)
    return f"{name} - {total:.1f} GB VRAM"


def vram_usage() -> str:
    t = _require_torch()
    if not t.cuda.is_available():
        return "n/a"
    allocated = t.cuda.memory_allocated(0) / (1024**3)
    reserved = t.cuda.memory_reserved(0) / (1024**3)
    return f"{allocated:.2f} GB allocated / {reserved:.2f} GB reserved"


def _find_ffmpeg() -> str | None:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    for candidate in (
        r"C:\ffmpeg-master-latest-win64-gpl\bin\ffmpeg.exe",
        r"C:\ffmpeg\bin\ffmpeg.exe",
    ):
        if os.path.isfile(candidate):
            return candidate
    return None


def load_reference_audio(path: str, target_sr: int = 24000):
    """Decode any ffmpeg-readable clip to mono float32 at *target_sr*."""
    import numpy as np

    if not path or not os.path.isfile(path):
        raise ValueError("Please upload a reference audio file first.")

    ffmpeg = _find_ffmpeg()
    if ffmpeg:
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "ref.wav")
            proc = subprocess.run(
                [
                    ffmpeg, "-nostdin", "-y", "-i", path,
                    "-vn", "-ac", "1", "-ar", str(target_sr),
                    "-f", "wav", out,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            if proc.returncode == 0 and os.path.isfile(out):
                import soundfile as sf

                data, sr = sf.read(out, dtype="float32", always_2d=False)
                return np.asarray(data, dtype=np.float32), int(sr)
            log(f"ffmpeg failed ({proc.returncode}); falling back to soundfile")

    import soundfile as sf

    data, sr = sf.read(path, dtype="float32", always_2d=False)
    data = np.asarray(data, dtype=np.float32)
    if data.ndim > 1:
        data = data.mean(axis=1)
    if sr != target_sr:
        import librosa

        data = librosa.resample(data, orig_sr=sr, target_sr=target_sr)
        sr = target_sr
    return data, int(sr)


def split_text(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    """Split long narration at sentence boundaries for the token budget."""
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if current and len(current) + 1 + len(sentence) > max_chars:
            chunks.append(current)
            current = sentence
        elif not current:
            current = sentence
        else:
            current += " " + sentence
    if current:
        chunks.append(current)
    return chunks or [text]


def apply_speed(path: str, speed: float) -> None:
    """Apply a Kokoro-compatible speed factor with ffmpeg ``atempo``."""
    try:
        speed = float(speed)
    except (TypeError, ValueError):
        return
    if abs(speed - 1.0) < 0.01:
        return

    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        log("ffmpeg not found - speed factor skipped")
        return

    speed = max(0.5, min(2.0, speed))
    tmp = f"{path}.speed.wav"
    proc = subprocess.run(
        [
            ffmpeg, "-nostdin", "-y", "-i", path,
            "-filter:a", f"atempo={speed:.4f}",
            "-ac", "1", tmp,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    if proc.returncode == 0 and os.path.isfile(tmp):
        os.replace(tmp, path)
    else:
        log(f"atempo failed ({proc.returncode}); keeping original speed")
        if os.path.isfile(tmp):
            os.remove(tmp)


def _normalise(audio):
    import numpy as np

    wav = np.asarray(audio, dtype=np.float32).squeeze()
    if wav.ndim > 1:
        wav = wav.mean(axis=0)
    peak = float(np.max(np.abs(wav))) if wav.size else 0.0
    if peak > 1.0:
        wav = wav / peak
    return np.clip(wav, -1.0, 1.0)


class Engine:
    """Keeps at most one checkpoint resident and releases VRAM after jobs."""

    def __init__(self) -> None:
        self._model: Any | None = None
        self._model_id: str | None = None
        self._configured = False

    @property
    def loaded_model_id(self) -> str | None:
        return self._model_id

    def status(self) -> dict[str, Any]:
        t = _require_torch()
        return {
            "device": describe_device(),
            "vram": vram_usage(),
            "loaded": self._model_id,
            "dtype": DTYPE_NAME,
            "cap": (
                f"{t.cuda.get_device_properties(0).total_memory * VRAM_FRACTION / 1024**3:.2f} GB"
                if t.cuda.is_available()
                else "n/a"
            ),
            "cuda": bool(t.cuda.is_available()),
            "python": sys.version.split()[0],
            "speakers": {name: label for name, (label, _lang) in SPEAKERS.items()},
            "languages": LANGUAGES,
        }

    def _load(self, model_id: str) -> Any:
        require_cuda()
        t = _require_torch()
        if not self._configured:
            configure_cuda()
            self._configured = True

        from qwen_tts import Qwen3TTSModel  # noqa: PLC0415

        dtype = t.bfloat16
        log(f"loading {model_id} on cuda:0 ({DTYPE_NAME}, {ATTN_IMPLEMENTATION})")
        model = Qwen3TTSModel.from_pretrained(
            model_id,
            device_map="cuda:0",
            dtype=dtype,
            attn_implementation=ATTN_IMPLEMENTATION,
        )
        model.model.eval()
        t.cuda.synchronize()
        log(f"{model_id} ready - {vram_usage()}")
        return model

    def _unload(self) -> None:
        if self._model is None:
            return
        log(f"unloading {self._model_id} to free VRAM")
        self._model = None
        self._model_id = None
        gc.collect()
        t = _require_torch()
        if t.cuda.is_available():
            t.cuda.empty_cache()
            t.cuda.ipc_collect()
            log(f"VRAM after unload - {vram_usage()}")

    def _release(self) -> None:
        gc.collect()
        t = _require_torch()
        if t.cuda.is_available():
            t.cuda.empty_cache()

    def acquire(self, model_id: str) -> Any:
        if self._model_id == model_id and self._model is not None:
            return self._model
        self._unload()
        self._model = self._load(model_id)
        self._model_id = model_id
        return self._model

    def unload_all(self) -> str:
        require_cuda()
        self._unload()
        self._release()
        return f"Unloaded. {vram_usage()}"

    # -- inference ---------------------------------------------------------
    def _write(self, audio, sr: int, output_path: str, speed: float) -> dict[str, Any]:
        import soundfile as sf

        wav = _normalise(audio)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        sf.write(output_path, wav, int(sr), subtype="PCM_16")
        if speed and abs(float(speed) - 1.0) >= 0.01:
            apply_speed(output_path, float(speed))

        # Read back from disk: speed post-processing changes the real duration.
        info = sf.info(output_path)
        rate = int(info.samplerate or sr)
        duration = float(info.frames) / float(rate) if rate else 0.0
        return {
            "output_path": output_path,
            "duration": duration,
            "sample_rate": rate,
        }

    def clone(
        self,
        text: str,
        language: str | None,
        ref_audio_path: str,
        ref_text: str,
        x_vector_only: bool,
        max_new_tokens: int = DEFAULT_MAX_TOKENS,
        output_path: str = "",
        speed: float = 1.0,
    ) -> dict[str, Any]:
        if not text or not text.strip():
            raise ValueError("Enter some text to synthesize.")
        if not output_path:
            raise ValueError("output_path is required.")

        require_cuda()
        t = _require_torch()
        t.cuda.reset_peak_memory_stats(0)
        model = self.acquire(BASE_MODEL_ID)
        ref_audio, ref_sr = load_reference_audio(ref_audio_path)

        import numpy as np

        pieces = []
        tokens = max(64, min(int(max_new_tokens), MAX_TOKENS_LIMIT))
        for chunk in split_text(text):
            kwargs: dict[str, Any] = {
                "text": chunk,
                "language": None if not language or language == "Auto" else language,
                "ref_audio": (ref_audio, ref_sr),
                "max_new_tokens": tokens,
            }
            if x_vector_only or not (ref_text and ref_text.strip()):
                kwargs["x_vector_only_mode"] = True
            else:
                kwargs["ref_text"] = ref_text.strip()

            with t.inference_mode():
                wavs, out_sr = model.generate_voice_clone(**kwargs)
            wav = wavs[0] if isinstance(wavs, (list, tuple)) else wavs
            pieces.append(np.asarray(wav, dtype=np.float32).squeeze())

        audio = np.concatenate(pieces) if len(pieces) > 1 else pieces[0]
        result = self._write(audio, out_sr, output_path, speed)
        result["model_id"] = BASE_MODEL_ID
        if t.cuda.is_available():
            result["peak_vram_gb"] = round(
                t.cuda.max_memory_reserved(0) / 1024**3, 2
            )
            log(
                f"clone done: {result['duration']:.2f}s audio, "
                f"peak reserved {result['peak_vram_gb']:.2f} GB"
            )
        self._release()
        return result

    def custom_voice(
        self,
        text: str,
        language: str | None,
        speaker: str,
        instruct: str = "",
        max_new_tokens: int = DEFAULT_MAX_TOKENS,
        output_path: str = "",
        speed: float = 1.0,
    ) -> dict[str, Any]:
        if not text or not text.strip():
            raise ValueError("Enter some text to synthesize.")
        if not output_path:
            raise ValueError("output_path is required.")
        if speaker not in SPEAKERS:
            raise ValueError(f"Unknown speaker: {speaker}")

        require_cuda()
        t = _require_torch()
        t.cuda.reset_peak_memory_stats(0)
        model = self.acquire(CUSTOM_VOICE_MODEL_ID)

        import numpy as np

        if not language or language == "Auto":
            language = SPEAKERS[speaker][1]

        pieces = []
        tokens = max(64, min(int(max_new_tokens), MAX_TOKENS_LIMIT))
        for chunk in split_text(text):
            kwargs: dict[str, Any] = {
                "text": chunk,
                "language": language,
                "speaker": speaker,
                "max_new_tokens": tokens,
            }
            # The 0.6B CustomVoice checkpoint ignores `instruct` upstream; it is
            # forwarded anyway so a future 1.7B swap keeps working.
            if instruct and instruct.strip():
                kwargs["instruct"] = instruct.strip()

            with t.inference_mode():
                wavs, out_sr = model.generate_custom_voice(**kwargs)
            wav = wavs[0] if isinstance(wavs, (list, tuple)) else wavs
            pieces.append(np.asarray(wav, dtype=np.float32).squeeze())

        audio = np.concatenate(pieces) if len(pieces) > 1 else pieces[0]
        result = self._write(audio, out_sr, output_path, speed)
        result["model_id"] = CUSTOM_VOICE_MODEL_ID
        if t.cuda.is_available():
            result["peak_vram_gb"] = round(
                t.cuda.max_memory_reserved(0) / 1024**3, 2
            )
            log(
                f"custom_voice done: {result['duration']:.2f}s audio, "
                f"peak reserved {result['peak_vram_gb']:.2f} GB"
            )
        self._release()
        return result


def _handle(engine: Engine, cmd: str, payload: dict[str, Any]) -> Any:
    if cmd == "status":
        return engine.status()
    if cmd == "unload":
        return {"message": engine.unload_all()}
    if cmd == "custom_voice":
        return engine.custom_voice(**payload)
    if cmd == "clone":
        return engine.clone(**payload)
    raise ValueError(f"Unknown command: {cmd}")


def serve() -> None:
    # Keep a private handle for the JSON protocol.  torch/transformers print
    # banners to stdout; redirect stdout to stderr so those lines only land in
    # the engine log and can never interleave with a protocol response.
    protocol_out = sys.stdout
    sys.stdout = sys.stderr

    engine = Engine()
    # Fail fast and clearly if there is no GPU; the parent surfaces this.
    require_cuda()
    configure_cuda()
    engine._configured = True
    log(f"ready on {describe_device()} (python {sys.version.split()[0]})")

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            protocol_out.write(
                json.dumps({"ok": False, "error": "invalid JSON"}) + "\n"
            )
            protocol_out.flush()
            continue

        request_id = request.get("id")
        cmd = request.get("cmd", "")
        payload = request.get("payload") or {}
        try:
            result = _handle(engine, cmd, payload)
            response = {"id": request_id, "ok": True, "result": result}
        except Exception as exc:  # keep the worker alive across a bad request
            traceback.print_exc()
            response = {
                "id": request_id,
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
        # One compact JSON object per line; audio never crosses this pipe.
        protocol_out.write(json.dumps(response, ensure_ascii=False) + "\n")
        protocol_out.flush()


def main(argv: list[str]) -> int:
    if len(argv) > 1 and argv[1] == "--probe":
        # Cheap parent-side availability check: reports Python/torch/CUDA/qwen.
        try:
            t = _require_torch()
            import qwen_tts  # noqa: F401

            print(
                json.dumps(
                    {
                        "ok": True,
                        "python": sys.version.split()[0],
                        "torch": t.__version__,
                        "cuda": bool(t.cuda.is_available()),
                        "device": describe_device(),
                        "base_model": BASE_MODEL_ID,
                        "custom_voice_model": CUSTOM_VOICE_MODEL_ID,
                    }
                )
            )
            return 0
        except Exception as exc:
            print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}))
            return 1

    serve()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
