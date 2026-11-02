"""Unified TTS dispatcher.

StoryFlow supports two speech engines:

``kokoro`` (default)
    Kokoro-82M ONNX.  Lightweight and fast, runs on CPU.  Ideal for building a
    full draft video quickly.

``qwen``
    Qwen3-TTS 0.6B on the GPU through an isolated Python 3.11 worker.  Slower,
    heavier, and supports zero-shot voice cloning from uploaded references.
    Used to regenerate ("finalize") audio once the visuals are confirmed.

Both engines return the same result dict::

    {"success": True, "audio_path": str, "duration": float, "sample_rate": int}

This module is the only place the rest of the app needs to know about engines.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

ENGINE_KOKORO = "kokoro"
ENGINE_QWEN = "qwen"

ENGINE_CHOICES = [
    (ENGINE_KOKORO, "Kokoro (fast, default)"),
    (ENGINE_QWEN, "Qwen3-TTS (GPU)"),
]
VALID_ENGINES = {choice[0] for choice in ENGINE_CHOICES}

QWEN_MODE_CUSTOM = "custom_voice"
QWEN_MODE_CLONE = "clone"
QWEN_MODE_CHOICES = [
    (QWEN_MODE_CUSTOM, "Preset voice"),
    (QWEN_MODE_CLONE, "Voice cloning"),
]

# Mirrors backend/core_engine/qwen_engine.py:SPEAKERS so serializers/views can
# expose the same list.  Display labels come from the engine status endpoint.
QWEN_SPEAKERS = [
    "Aiden",
    "Ryan",
    "Vivian",
    "Serena",
    "Uncle_Fu",
    "Dylan",
    "Eric",
    "Ono_Anna",
    "Sohee",
]

QWEN_LANGUAGES = [
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

QWEN_DEFAULT_SPEAKER = "Aiden"
QWEN_DEFAULT_LANGUAGE = "English"
QWEN_MAX_TOKENS_MIN = 256
QWEN_MAX_TOKENS_MAX = 2048
QWEN_MAX_TOKENS_DEFAULT = 1024


def normalize_engine(value, default: str = ENGINE_KOKORO) -> str:
    """Return a valid engine id, falling back to *default*."""
    if value in VALID_ENGINES:
        return value
    return default


def kokoro_available() -> bool:
    """Whether the Kokoro ONNX model files are present.

    Accessing ``KokoroModelLoader`` through its module (not a direct import)
    keeps existing ``patch('core_engine.model_loader.KokoroModelLoader...')``
    test seams working.
    """
    try:
        from core_engine import model_loader

        return bool(model_loader.KokoroModelLoader.is_model_available())
    except Exception:
        return False


def qwen_available() -> bool:
    """Cheap check: dedicated Python 3.11 env + ``qwen_tts`` are installed.

    Deliberately does **not** start the GPU worker; full device/CUDA state is
    reported by ``GET /api/settings/tts-engines/``.
    """
    try:
        from core_engine import qwen_client

        return qwen_client.qwen_is_installed()
    except Exception:
        return False


def engine_available(engine: str) -> bool:
    if engine == ENGINE_QWEN:
        return qwen_available()
    return kokoro_available()


def unavailable_message(engine: str) -> str:
    if engine == ENGINE_QWEN:
        return (
            "Qwen TTS is not available. Run scripts/setup_qwen_tts.ps1 to "
            "copy the GPU virtualenv into backend/qwen_tts/.venv, then "
            "restart the backend. Qwen requires a CUDA GPU."
        )
    return (
        "Kokoro TTS model not available. Please install the Kokoro ONNX "
        "model and voices.bin in the 'models/' directory."
    )


def synthesize(
    text: str,
    output_path: str,
    *,
    engine: str = ENGINE_KOKORO,
    voice_id: str = "af_bella",
    speed: float = 1.0,
    qwen_mode: str = QWEN_MODE_CUSTOM,
    qwen_speaker: str = QWEN_DEFAULT_SPEAKER,
    qwen_language: str = QWEN_DEFAULT_LANGUAGE,
    qwen_instruct: str = "",
    qwen_max_new_tokens: int = QWEN_MAX_TOKENS_DEFAULT,
    qwen_x_vector_only: bool = True,
    reference_audio_path: str | None = None,
    reference_text: str = "",
) -> dict:
    """Generate speech with the selected engine.

    Never raises: always returns a dict containing ``success``.
    """
    engine = normalize_engine(engine)

    if engine == ENGINE_QWEN:
        from core_engine import qwen_client

        result = qwen_client.generate_audio(
            text=text,
            output_path=output_path,
            mode=qwen_mode,
            speaker=qwen_speaker,
            language=qwen_language,
            instruct=qwen_instruct,
            max_new_tokens=qwen_max_new_tokens,
            x_vector_only=qwen_x_vector_only,
            reference_audio_path=reference_audio_path,
            reference_text=reference_text,
            speed=speed,
        )
        result.setdefault("engine", ENGINE_QWEN)
        return result

    # Kokoro — imported through the module so tests can patch it.
    from core_engine import tts_wrapper

    result = tts_wrapper.generate_audio(
        text=text,
        voice_id=voice_id,
        speed=speed,
        output_path=output_path,
    )
    result.setdefault("engine", ENGINE_KOKORO)
    return result
