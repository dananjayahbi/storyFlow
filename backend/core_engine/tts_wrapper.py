"""
StoryFlow TTS Wrapper Module.

Provides text-to-speech functionality using Kokoro-82M ONNX model
via the kokoro-onnx package. The main function ``generate_audio()``
accepts text, voice ID, speed, and output path, runs the full
pipeline, and returns a structured result dict.

Never raises exceptions — always returns a dict with a ``success``
key.
"""

import logging
import os
import re
import threading
import wave
from pathlib import Path

import numpy as np

from core_engine.audio_utils import get_audio_duration

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

SAMPLE_RATE = 24000  # Kokoro-82M native sample rate

VALID_VOICE_IDS = {
    # Primary voices (subset shown in UI)
    "af_bella",
    "af_sarah",
    "af_nicole",
    "am_adam",
    "am_michael",
    "bf_emma",
    "bm_george",
    # Additional voices from voices.bin
    "af_sky",
    "af_alloy",
    "af_aoede",
    "af_jessica",
    "af_kore",
    "af_nova",
    "af_river",
    "am_echo",
    "am_eric",
    "am_fenrir",
    "am_liam",
    "am_onyx",
    "am_puck",
    "bf_alice",
    "bf_isabella",
    "bf_lily",
    "bm_daniel",
    "bm_fable",
    "bm_lewis",
}

DEFAULT_VOICE_ID = "af_bella"

SPEED_MIN = 0.5
SPEED_MAX = 2.0

# --------------------------------------------------------------------------
# Audio File Path Construction (Task 03.01.07)
# --------------------------------------------------------------------------


def construct_audio_path(project_id, segment_id):
    """
    Build an absolute filesystem path for a segment's WAV file.

    The path follows the pattern:
        {MEDIA_ROOT}/projects/{project_id}/audio/{segment_id}.wav

    Automatically creates the parent directory if it doesn't exist.

    Args:
        project_id: Project primary key (int or str).
        segment_id: Segment primary key (int, str, or UUID).

    Returns:
        pathlib.Path: Absolute path to the WAV file.
    """
    from django.conf import settings

    audio_dir = Path(settings.MEDIA_ROOT) / "projects" / str(project_id) / "audio"
    os.makedirs(audio_dir, exist_ok=True)

    return audio_dir / f"{segment_id}.wav"


def construct_audio_url(project_id, segment_id):
    """
    Build a URL-relative path for serving a segment's WAV file.

    The URL follows the pattern:
        /media/projects/{project_id}/audio/{segment_id}.wav

    This path is stored in the Segment model's audio_file field and
    served by Django's media file handling in development.

    Args:
        project_id: Project primary key (int or str).
        segment_id: Segment primary key (int, str, or UUID).

    Returns:
        str: URL-relative path to the WAV file.
    """
    return f"/media/projects/{project_id}/audio/{segment_id}.wav"


# --------------------------------------------------------------------------
# Voice Validation (Task 03.01.05)
# --------------------------------------------------------------------------


def validate_voice_id(voice_id):
    """
    Validate a voice ID and return a safe value.

    Returns the voice_id unchanged if valid, otherwise falls back to
    DEFAULT_VOICE_ID with a logged warning. Never raises.

    Args:
        voice_id: The voice ID to validate (may be None or invalid).

    Returns:
        str: A valid voice ID.
    """
    if voice_id and voice_id in VALID_VOICE_IDS:
        return voice_id

    logger.warning(
        "Invalid voice ID '%s' — falling back to default '%s'",
        voice_id,
        DEFAULT_VOICE_ID,
    )
    return DEFAULT_VOICE_ID


def get_available_voices():
    """
    Return a list of voice IDs available in the voices.bin file.

    Falls back to the static VALID_VOICE_IDS set if the Kokoro
    instance can't be loaded.

    Returns:
        list[str]: Available voice IDs, sorted.
    """
    try:
        kokoro = _get_kokoro_instance()
        if kokoro is not None:
            return sorted(kokoro.get_voices())
    except Exception:
        pass
    return sorted(VALID_VOICE_IDS)


# --------------------------------------------------------------------------
# Kokoro-ONNX Singleton
# --------------------------------------------------------------------------

_kokoro_instance = None
_kokoro_lock = threading.Lock()


def _resolve_model_path():
    """Resolve the absolute path to the Kokoro ONNX model file."""
    from django.conf import settings
    return str(settings.BASE_DIR.parent / "models" / "kokoro-v0_19.onnx")


def _resolve_voices_path():
    """Resolve the absolute path to the voices.bin file."""
    from django.conf import settings
    return str(settings.BASE_DIR.parent / "models" / "voices.bin")


def _get_kokoro_instance():
    """
    Return a lazily-initialized Kokoro instance (thread-safe singleton).

    Uses double-checked locking to avoid lock contention on the hot path.

    Returns:
        Kokoro instance, or None if initialization fails.
    """
    global _kokoro_instance

    if _kokoro_instance is not None:
        return _kokoro_instance

    with _kokoro_lock:
        if _kokoro_instance is None:
            try:
                from kokoro_onnx import Kokoro

                model_path = _resolve_model_path()
                voices_path = _resolve_voices_path()

                if not os.path.exists(model_path):
                    logger.error("Kokoro model not found at: %s", model_path)
                    return None

                if not os.path.exists(voices_path):
                    logger.error("Voices file not found at: %s", voices_path)
                    return None

                _kokoro_instance = Kokoro(model_path, voices_path)
                logger.info(
                    "Kokoro-ONNX initialized: model=%s, voices=%s",
                    model_path,
                    voices_path,
                )
            except Exception as e:
                logger.error(
                    "Failed to initialize Kokoro-ONNX: %s", e, exc_info=True
                )
                return None

    return _kokoro_instance


def _reset_kokoro_instance():
    """Reset the singleton (for testing only)."""
    global _kokoro_instance
    with _kokoro_lock:
        _kokoro_instance = None


# --------------------------------------------------------------------------
# Main TTS Pipeline
# --------------------------------------------------------------------------


def generate_audio(text, voice_id="af_bella", speed=1.0, output_path=None):
    """
    Generate speech audio from text using the Kokoro-82M ONNX model.

    Uses the ``kokoro-onnx`` package for proper phonemization,
    tokenization, and inference. Returns a structured result dict.

    This function NEVER raises exceptions — it always returns a dict
    with a ``success`` key.

    Args:
        text (str): Text to convert to speech.
        voice_id (str): Kokoro voice ID (default "af_bella").
        speed (float): Speech speed multiplier (clamped to 0.5–2.0).
        output_path (str): Absolute path where the .wav file will be
            saved.

    Returns:
        dict: On success: {
            "success": True,
            "audio_path": str,
            "duration": float (seconds),
            "sample_rate": int
        }
        On failure: {
            "success": False,
            "error": str (human-readable message)
        }
    """
    # ------------------------------------------------------------------
    # Step 1: Validate inputs
    # ------------------------------------------------------------------
    if not isinstance(text, str) or not text.strip():
        return {"success": False, "error": "Text is empty or whitespace-only."}

    if not output_path:
        return {"success": False, "error": "Output path is required."}

    text = text.strip()

    # ------------------------------------------------------------------
    # Step 2: Validate voice ID (soft — falls back to default)
    # ------------------------------------------------------------------
    voice_id = validate_voice_id(voice_id)

    # ------------------------------------------------------------------
    # Step 3: Clamp speed to valid range
    # ------------------------------------------------------------------
    speed = max(SPEED_MIN, min(SPEED_MAX, float(speed)))

    # ------------------------------------------------------------------
    # Step 4: Get Kokoro instance
    # ------------------------------------------------------------------
    try:
        kokoro = _get_kokoro_instance()
    except Exception as e:
        logger.error("Failed to get Kokoro instance: %s", e)
        return {
            "success": False,
            "error": (
                "TTS engine failed to initialize. Please ensure the Kokoro "
                "model and voices.bin are in the 'models/' directory."
            ),
        }

    if kokoro is None:
        return {
            "success": False,
            "error": (
                "TTS model not found. Please download the Kokoro-82M ONNX "
                "model and place it in the 'models/' directory."
            ),
        }

    # ------------------------------------------------------------------
    # Step 5: Check if voice exists in the loaded voices
    # ------------------------------------------------------------------
    try:
        available = kokoro.get_voices()
        if voice_id not in available:
            logger.warning(
                "Voice '%s' not in voices.bin (available: %s). Using '%s'.",
                voice_id,
                available[:5],
                DEFAULT_VOICE_ID,
            )
            voice_id = DEFAULT_VOICE_ID
    except Exception:
        pass  # Proceed anyway — kokoro.create will fail with a clear error

    # ------------------------------------------------------------------
    # Step 6: Generate audio via kokoro-onnx
    # ------------------------------------------------------------------
    try:
        audio_array, sample_rate = kokoro.create(
            text=text,
            voice=voice_id,
            speed=speed,
            lang="en-us",
        )

        # ------------------------------------------------------------------
        # Step 7: Save WAV file
        # ------------------------------------------------------------------
        _save_wav(audio_array, output_path, sample_rate)

        # ------------------------------------------------------------------
        # Step 8: Calculate duration
        # ------------------------------------------------------------------
        duration = get_audio_duration(output_path)

        # ------------------------------------------------------------------
        # Step 9: Return success dict
        # ------------------------------------------------------------------
        logger.info(
            "TTS generation successful: voice=%s, speed=%.1f, "
            "duration=%.2fs, path=%s",
            voice_id,
            speed,
            duration,
            output_path,
        )

        return {
            "success": True,
            "audio_path": output_path,
            "duration": duration,
            "sample_rate": sample_rate,
        }

    except FileNotFoundError as e:
        logger.error("File not found during TTS generation: %s", e, exc_info=True)
        return {"success": False, "error": str(e)}

    except Exception as e:
        logger.error("TTS generation failed: %s", e, exc_info=True)
        return {"success": False, "error": f"TTS generation failed: {e}"}


# --------------------------------------------------------------------------
# Internal Helpers
# --------------------------------------------------------------------------


def _save_wav(audio_array, output_path, sample_rate=SAMPLE_RATE):
    """
    Save a float32 numpy audio array as a 16-bit WAV file.

    Args:
        audio_array: 1-D float32 numpy array with values in [-1, 1].
        output_path: Destination file path.
        sample_rate: Audio sample rate (default 24000).
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Clip and convert float32 [-1,1] → int16
    clipped = np.clip(audio_array, -1.0, 1.0)
    audio_int16 = (clipped * 32767).astype(np.int16)

    with wave.open(str(output_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(audio_int16.tobytes())


def split_text_into_chunks(text, max_length=500):
    """
    Split text into chunks at sentence boundaries.

    Note: kokoro-onnx handles chunking internally, but this utility
    is kept for backward compatibility and potential use by callers.

    Args:
        text: Input text to split.
        max_length: Maximum character length per chunk.

    Returns:
        list[str]: List of text chunks.
    """
    if not text or len(text) <= max_length:
        return [text] if text else []

    sentences = re.split(r"(?<=[.!?])\s+", text.strip())

    chunks = []
    current_chunk = ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if current_chunk and len(current_chunk) + 1 + len(sentence) > max_length:
            chunks.append(current_chunk.strip())
            current_chunk = sentence
        elif not current_chunk:
            current_chunk = sentence
        else:
            current_chunk += " " + sentence

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks if chunks else [text]
