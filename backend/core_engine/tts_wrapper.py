"""
StoryFlow TTS Wrapper Module.

Provides text-to-speech functionality using Kokoro-82M ONNX model.
The main function `generate_audio()` accepts text, voice ID, speed,
and output path, runs the full pipeline, and returns a structured
result dict. Never raises exceptions — always returns a dict.
"""

import logging
import os
import re
import unicodedata
from pathlib import Path

import numpy as np

from core_engine.audio_utils import get_audio_duration, normalize_audio, save_audio_wav
from core_engine.model_loader import KokoroModelLoader

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

SAMPLE_RATE = 24000  # Kokoro-82M native sample rate

VALID_VOICE_IDS = {
    "af_bella",
    "af_sarah",
    "af_nicole",
    "am_adam",
    "am_michael",
    "bf_emma",
    "bm_george",
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


def get_voice_embedding(voice_id):
    """
    Get the voice embedding tensor for a given voice ID.

    Attempts to load a voice embedding from a .npy file in the
    models/voices/ directory. If the file doesn't exist, returns
    None and the caller should use a zero-filled fallback.

    The voice embedding mechanism depends on the Kokoro model version.
    Voice packs are stored as numpy arrays in:
        <project_root>/models/voices/<voice_id>.npy

    Args:
        voice_id: A validated voice ID string.

    Returns:
        numpy.ndarray or None: Voice embedding tensor with the correct
        shape for the model's style/voice input, or None if the voice
        pack file is not available.
    """
    voice_path = _resolve_voice_path(voice_id)

    if voice_path and os.path.exists(voice_path):
        try:
            embedding = np.load(voice_path)
            # Ensure correct shape: [1, embedding_dim]
            if embedding.ndim == 1:
                embedding = embedding.reshape(1, -1)
            logger.debug("Loaded voice embedding for '%s' from %s", voice_id, voice_path)
            return embedding.astype(np.float32)
        except Exception as e:
            logger.warning(
                "Failed to load voice embedding for '%s': %s — using fallback",
                voice_id,
                e,
            )
            return None

    logger.debug(
        "Voice embedding file not found for '%s' at %s — using fallback",
        voice_id,
        voice_path,
    )
    return None


def _resolve_voice_path(voice_id):
    """
    Resolve the path to a voice embedding .npy file.

    Args:
        voice_id: Voice ID string.

    Returns:
        str or None: Absolute path to the voice .npy file, or None
        if Django settings are not available.
    """
    try:
        from django.conf import settings
        voice_dir = settings.BASE_DIR.parent / "models" / "voices"
        return str(voice_dir / f"{voice_id}.npy")
    except Exception:
        return None


def get_available_voices():
    """
    Return a list of voice IDs that have embedding files available.

    Returns:
        list[str]: Voice IDs with available .npy files, sorted.
    """
    available = []
    for vid in sorted(VALID_VOICE_IDS):
        path = _resolve_voice_path(vid)
        if path and os.path.exists(path):
            available.append(vid)
    return available


# --------------------------------------------------------------------------
# Tokenization (Task 03.01.04)
# --------------------------------------------------------------------------

# Special token IDs — update after inspecting model metadata
PAD_TOKEN = 0
BOS_TOKEN = 1
EOS_TOKEN = 2
VOCAB_OFFSET = 3  # Real character tokens start after special tokens

# Maximum input length (characters). If the model has a fixed max,
# update this after inspecting model metadata.
MAX_TOKEN_LENGTH = 510  # Reserve 2 slots for BOS + EOS → 512 total

# Number-to-word mapping for digit conversion
_ONES = [
    "", "one", "two", "three", "four", "five", "six", "seven",
    "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen",
    "fifteen", "sixteen", "seventeen", "eighteen", "nineteen",
]
_TENS = [
    "", "", "twenty", "thirty", "forty", "fifty",
    "sixty", "seventy", "eighty", "ninety",
]


def _number_to_words(n):
    """Convert an integer (0–9999) to English words."""
    if n < 0:
        return "minus " + _number_to_words(-n)
    if n < 20:
        return _ONES[n] if n > 0 else "zero"
    if n < 100:
        return _TENS[n // 10] + (" " + _ONES[n % 10] if n % 10 else "")
    if n < 1000:
        remainder = n % 100
        return (
            _ONES[n // 100] + " hundred"
            + (" and " + _number_to_words(remainder) if remainder else "")
        )
    if n < 10000:
        remainder = n % 1000
        return (
            _number_to_words(n // 1000) + " thousand"
            + (" " + _number_to_words(remainder) if remainder else "")
        )
    return str(n)  # Fallback for large numbers


def _replace_numbers(text):
    """Replace digit sequences with their English word equivalents."""
    def _repl(match):
        num = int(match.group())
        if num > 9999:
            return match.group()  # Keep very large numbers as-is
        return _number_to_words(num)

    return re.sub(r"\b\d+\b", _repl, text)


def clean_text(text):
    """
    Clean and normalize input text for tokenization.

    Performs Unicode normalization, number-to-word conversion,
    special character handling, and whitespace normalization.

    Args:
        text: Raw input text string.

    Returns:
        str: Cleaned text ready for tokenization.
    """
    if not text:
        return ""

    # Unicode normalization (NFC — composed form)
    text = unicodedata.normalize("NFC", text)

    # Replace common typographic characters
    text = text.replace("\u2018", "'").replace("\u2019", "'")  # Smart quotes
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2014", " - ")   # Em dash → hyphen
    text = text.replace("\u2013", " - ")   # En dash → hyphen
    text = text.replace("\u2026", "...")   # Ellipsis

    # Convert numbers to words
    text = _replace_numbers(text)

    # Remove characters that the model likely can't handle
    # Keep: letters, digits (remaining), basic punctuation, whitespace
    text = re.sub(r"[^\w\s.,!?;:'\"\-()$%&@#/\\]", "", text)

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text


def tokenize_text(text):
    """
    Convert text to the model's expected token format.

    Cleans the input text, maps characters to token IDs with BOS/EOS
    framing, and returns a properly shaped numpy array.

    The tokenization uses character-level encoding with a vocabulary
    offset. Special tokens BOS and EOS frame the sequence. Sequences
    longer than MAX_TOKEN_LENGTH are truncated.

    Args:
        text: Input text string (will be cleaned internally).

    Returns:
        numpy.ndarray: Token array with shape [1, seq_len] and dtype int64.
    """
    # Clean and preprocess
    cleaned = clean_text(text)

    if not cleaned:
        # Return minimal valid token sequence
        return np.array([[BOS_TOKEN, EOS_TOKEN]], dtype=np.int64)

    # Character-level tokenization with vocabulary offset
    char_tokens = [ord(c) + VOCAB_OFFSET for c in cleaned]

    # Truncate if exceeding max length
    if len(char_tokens) > MAX_TOKEN_LENGTH:
        char_tokens = char_tokens[:MAX_TOKEN_LENGTH]
        logger.warning(
            "Text truncated from %d to %d tokens",
            len(cleaned),
            MAX_TOKEN_LENGTH,
        )

    # Frame with BOS and EOS
    tokens = [BOS_TOKEN] + char_tokens + [EOS_TOKEN]

    return np.array([tokens], dtype=np.int64)


def split_text_into_chunks(text, max_length=500):
    """
    Split text into chunks at sentence boundaries.

    Splits at sentence-ending punctuation (. ! ?) followed by whitespace.
    Accumulates sentences into chunks without exceeding max_length.
    Single sentences longer than max_length are kept as their own chunk.

    Args:
        text: Input text to split.
        max_length: Maximum character length per chunk.

    Returns:
        list[str]: List of text chunks.
    """
    if not text or len(text) <= max_length:
        return [text] if text else []

    # Split at sentence boundaries
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())

    chunks = []
    current_chunk = ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        # Check if adding this sentence would exceed the limit
        if current_chunk and len(current_chunk) + 1 + len(sentence) > max_length:
            chunks.append(current_chunk.strip())
            current_chunk = sentence
        elif not current_chunk:
            current_chunk = sentence
        else:
            current_chunk += " " + sentence

    # Don't forget the last chunk
    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks if chunks else [text]


# --------------------------------------------------------------------------
# Main TTS Pipeline
# --------------------------------------------------------------------------


def generate_audio(text, voice_id="af_bella", speed=1.0, output_path=None):
    """
    Generate speech audio from text using the Kokoro-82M ONNX model.

    Runs the full pipeline: validate → load model → tokenize → infer →
    normalize → save → measure duration. Returns a structured result dict.

    This function NEVER raises exceptions — it always returns a dict with
    a 'success' key.

    Args:
        text (str): Text to convert to speech.
        voice_id (str): Kokoro voice ID (default "af_bella").
        speed (float): Speech speed multiplier (clamped to 0.5–2.0).
        output_path (str): Absolute path where the .wav file will be saved.

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
    # Step 4: Get ONNX session
    # ------------------------------------------------------------------
    try:
        session = KokoroModelLoader.get_session()
    except FileNotFoundError as e:
        logger.error("Model not found: %s", e)
        return {
            "success": False,
            "error": (
                "TTS model not found. Please download the Kokoro-82M ONNX model "
                "and place it in the 'models/' directory."
            ),
        }

    # ------------------------------------------------------------------
    # Step 5–11: Inference pipeline (with chunking support)
    # ------------------------------------------------------------------
    try:
        # Step 5: Split into chunks if text is long
        chunks = split_text_into_chunks(text, max_length=MAX_TOKEN_LENGTH)
        audio_segments = []
        silence_gap = np.zeros(int(0.1 * SAMPLE_RATE), dtype=np.float32)  # 100ms

        for i, chunk in enumerate(chunks):
            # Tokenize chunk
            tokens = tokenize_text(chunk)

            # Step 6: Prepare input tensors
            input_dict = _build_input_dict(session, tokens, voice_id, speed)

            # Step 7: Run inference
            outputs = session.run(None, input_dict)
            chunk_audio = outputs[0]

            # Flatten if needed (model may return [1, T] or [T])
            if chunk_audio.ndim > 1:
                chunk_audio = chunk_audio.squeeze()

            chunk_audio = chunk_audio.astype(np.float32)
            audio_segments.append(chunk_audio)

            # Insert silence gap between chunks (not after the last one)
            if i < len(chunks) - 1:
                audio_segments.append(silence_gap)

            logger.debug("Processed chunk %d/%d (%d chars)", i + 1, len(chunks), len(chunk))

        # Concatenate all chunks
        audio_array = np.concatenate(audio_segments) if len(audio_segments) > 1 else audio_segments[0]

        # Step 8: Normalize the concatenated audio as a whole
        audio_array = normalize_audio(audio_array)

        # Step 9: Save WAV file
        save_audio_wav(audio_array, output_path, SAMPLE_RATE)

        # Step 10: Calculate duration
        duration = get_audio_duration(output_path)

        # Step 11: Return success dict
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
            "sample_rate": SAMPLE_RATE,
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


def _build_input_dict(session, tokens, voice_id, speed):
    """
    Build the input tensor dict for ONNX inference.

    Discovers input tensor names at runtime using session.get_inputs()
    and maps them to the prepared tensors.

    Args:
        session: ONNX InferenceSession.
        tokens: Tokenized text as numpy array.
        voice_id: Validated voice ID string.
        speed: Clamped speed multiplier.

    Returns:
        dict: Input tensor dict for session.run().
    """
    model_inputs = session.get_inputs()
    input_dict = {}

    for inp in model_inputs:
        name = inp.name.lower()

        if "token" in name or "input" in name or "text" in name:
            # Token / text input
            input_dict[inp.name] = tokens.astype(np.int64)

        elif "style" in name or "voice" in name or "embed" in name or "spk" in name:
            # Voice embedding
            voice_emb = get_voice_embedding(voice_id)
            if voice_emb is not None:
                input_dict[inp.name] = voice_emb
            else:
                # Fallback: zero embedding matching expected shape
                shape = [d if isinstance(d, int) and d > 0 else 1 for d in inp.shape]
                input_dict[inp.name] = np.zeros(shape, dtype=np.float32)

        elif "speed" in name or "rate" in name:
            # Speed tensor
            shape = [d if isinstance(d, int) and d > 0 else 1 for d in inp.shape]
            speed_tensor = np.full(shape, speed, dtype=np.float32)
            input_dict[inp.name] = speed_tensor

        else:
            # Unknown input — provide zeros with the expected shape
            shape = [d if isinstance(d, int) and d > 0 else 1 for d in inp.shape]
            dtype = np.float32 if "float" in str(inp.type).lower() else np.int64
            input_dict[inp.name] = np.zeros(shape, dtype=dtype)
            logger.warning(
                "Unknown model input '%s' (shape=%s, type=%s) — using zeros",
                inp.name,
                inp.shape,
                inp.type,
            )

    return input_dict
