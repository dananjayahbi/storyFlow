"""
Audio utility functions for StoryFlow TTS pipeline.

Pure utility functions for peak normalization, WAV file saving,
duration calculation, and audio file validation. No Django imports,
no model access — testable in isolation with synthetic numpy arrays.
"""

import logging
import os

import numpy as np
import soundfile as sf

logger = logging.getLogger(__name__)


def normalize_audio(audio_array: np.ndarray, target_db: float = -1.0) -> np.ndarray:
    """
    Peak-normalize a 1D float32 numpy array to the target dB level.

    Scales the audio so the loudest sample reaches the target amplitude
    (−1.0 dB ≈ 0.8913). Handles edge cases: silence, already-normalized
    audio, very quiet audio, and clipping input.

    The function returns a NEW array — the input is never modified in place.
    The output dtype matches the input dtype.

    Args:
        audio_array: 1D numpy array of audio samples (typically float32).
        target_db: Target peak level in dB (default -1.0 dB, ≈ 0.8913).

    Returns:
        A new normalized numpy array with peak at the target level.
    """
    original_dtype = audio_array.dtype

    peak = np.max(np.abs(audio_array))

    # Silence — avoid division by zero (near-zero threshold)
    if peak < 1e-10:
        return audio_array.copy()

    target_amplitude = 10 ** (target_db / 20)

    # Already normalized — skip unnecessary floating-point manipulation
    if abs(peak - target_amplitude) < 1e-6:
        return audio_array.copy()

    # Compute normalization factor and scale
    # Works correctly for: quiet audio (scales up), loud/clipping (scales down)
    normalization_factor = target_amplitude / peak
    normalized = audio_array * normalization_factor

    # Preserve original dtype (e.g., float32)
    if normalized.dtype != original_dtype:
        normalized = normalized.astype(original_dtype)

    return normalized


def get_audio_duration(file_path: str) -> float:
    """
    Return the duration of a WAV file in seconds.

    Args:
        file_path: Path to the .wav file.

    Returns:
        Duration in seconds as a float.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Audio file not found: {file_path}")

    info = sf.info(file_path)
    return info.duration


def validate_audio_file(file_path: str) -> bool:
    """
    Check if a WAV file is valid and readable.

    Returns True if soundfile can read the file info and it reports
    a positive duration and sample rate. Returns False for any
    exception, missing file, or corrupt data.

    Args:
        file_path: Path to the .wav file.

    Returns:
        True if valid, False otherwise.
    """
    try:
        if not os.path.exists(file_path):
            return False

        info = sf.info(file_path)
        return info.duration > 0 and info.samplerate > 0
    except Exception:
        return False


def save_audio_wav(
    audio_array: np.ndarray,
    output_path: str,
    sample_rate: int,
) -> str:
    """
    Save a float32 audio array as a WAV file.

    Automatically creates parent directories if they don't exist.

    Args:
        audio_array: 1D float32 numpy array of audio samples.
        output_path: Destination file path.
        sample_rate: Sample rate in Hz (e.g. 24000).

    Returns:
        The output_path for chaining convenience.
    """
    parent_dir = os.path.dirname(output_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    sf.write(output_path, audio_array, sample_rate)
    logger.info("Saved audio file: %s", output_path)

    return output_path
