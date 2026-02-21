"""
Unit tests for audio_utils.py — normalization, duration, validation, and saving.

All tests are pure unit tests using synthetic NumPy arrays and temporary
directories. No Kokoro model or Django media directory required.
"""

import os
import shutil
import tempfile

import numpy as np
import soundfile as sf
from django.test import TestCase

from core_engine.audio_utils import (
    get_audio_duration,
    normalize_audio,
    save_audio_wav,
    validate_audio_file,
)

# Target amplitude for -1.0 dB
TARGET_AMP = 10 ** (-1.0 / 20)  # ≈ 0.8913


# ---------------------------------------------------------------------------
# normalize_audio() tests
# ---------------------------------------------------------------------------


class TestNormalizeAudio(TestCase):
    """Tests for normalize_audio()."""

    def test_known_input(self):
        """Array with known peak 0.5 is normalized to ≈0.8913."""
        audio = np.array([0.0, 0.25, 0.5, -0.5], dtype=np.float32)
        result = normalize_audio(audio)

        new_peak = np.max(np.abs(result))
        self.assertAlmostEqual(new_peak, TARGET_AMP, places=4)

    def test_silence_handling(self):
        """All-zeros input returns all-zeros — no inf, nan, or crash."""
        audio = np.zeros(1000, dtype=np.float32)
        result = normalize_audio(audio)

        self.assertTrue(np.all(result == 0))
        self.assertFalse(np.any(np.isinf(result)))
        self.assertFalse(np.any(np.isnan(result)))

    def test_already_normalized(self):
        """Array already at target peak is returned effectively unchanged."""
        audio = np.array([0.0, TARGET_AMP, -TARGET_AMP / 2], dtype=np.float32)
        result = normalize_audio(audio)

        diff = np.max(np.abs(result - audio))
        self.assertLess(diff, 1e-6)

    def test_very_quiet_audio(self):
        """Very quiet audio (peak 0.001) is scaled up to ≈0.8913."""
        audio = np.array([0.001, -0.0005, 0.0], dtype=np.float32)
        result = normalize_audio(audio)

        new_peak = np.max(np.abs(result))
        self.assertAlmostEqual(new_peak, TARGET_AMP, places=4)

    def test_clipping_input(self):
        """Audio exceeding 1.0 (peak 2.0) is scaled down to ≈0.8913."""
        audio = np.array([2.0, -1.5, 0.5], dtype=np.float32)
        result = normalize_audio(audio)

        new_peak = np.max(np.abs(result))
        self.assertAlmostEqual(new_peak, TARGET_AMP, places=4)

    def test_dtype_preservation_float32(self):
        """float32 input yields float32 output."""
        audio = np.array([0.5, -0.3], dtype=np.float32)
        result = normalize_audio(audio)

        self.assertEqual(result.dtype, np.float32)

    def test_dtype_preservation_float64(self):
        """float64 input yields float64 output."""
        audio = np.array([0.5, -0.3], dtype=np.float64)
        result = normalize_audio(audio)

        self.assertEqual(result.dtype, np.float64)

    def test_no_in_place_modification(self):
        """Input array is not modified — the function returns a new array."""
        audio = np.array([0.0, 0.25, 0.5, -0.5], dtype=np.float32)
        original_copy = audio.copy()

        _ = normalize_audio(audio)

        self.assertTrue(
            np.array_equal(audio, original_copy),
            "normalize_audio() must not modify the input array",
        )


# ---------------------------------------------------------------------------
# get_audio_duration() tests
# ---------------------------------------------------------------------------


class TestGetAudioDuration(TestCase):
    """Tests for get_audio_duration()."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_synthetic_one_second(self):
        """24000 samples at 24000 Hz = exactly 1.0 second."""
        audio = np.zeros(24000, dtype=np.float32)
        path = os.path.join(self.temp_dir, "one_sec.wav")
        sf.write(path, audio, 24000)

        duration = get_audio_duration(path)
        self.assertAlmostEqual(duration, 1.0, places=2)

    def test_synthetic_two_seconds(self):
        """48000 samples at 24000 Hz = exactly 2.0 seconds."""
        audio = np.zeros(48000, dtype=np.float32)
        path = os.path.join(self.temp_dir, "two_sec.wav")
        sf.write(path, audio, 24000)

        duration = get_audio_duration(path)
        self.assertAlmostEqual(duration, 2.0, places=2)

    def test_nonexistent_file_raises(self):
        """Non-existent file raises FileNotFoundError."""
        fake_path = os.path.join(self.temp_dir, "does_not_exist.wav")
        with self.assertRaises(FileNotFoundError):
            get_audio_duration(fake_path)


# ---------------------------------------------------------------------------
# validate_audio_file() tests
# ---------------------------------------------------------------------------


class TestValidateAudioFile(TestCase):
    """Tests for validate_audio_file()."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_valid_wav(self):
        """Legitimate WAV file returns True."""
        audio = np.random.randn(24000).astype(np.float32) * 0.5
        path = os.path.join(self.temp_dir, "valid.wav")
        sf.write(path, audio, 24000)

        self.assertTrue(validate_audio_file(path))

    def test_missing_file(self):
        """Non-existent path returns False."""
        fake_path = os.path.join(self.temp_dir, "missing.wav")
        self.assertFalse(validate_audio_file(fake_path))

    def test_corrupt_file(self):
        """Corrupt file (random bytes) returns False — no crash."""
        path = os.path.join(self.temp_dir, "corrupt.wav")
        with open(path, "wb") as f:
            f.write(os.urandom(512))

        self.assertFalse(validate_audio_file(path))


# ---------------------------------------------------------------------------
# save_audio_wav() tests
# ---------------------------------------------------------------------------


class TestSaveAudioWav(TestCase):
    """Tests for save_audio_wav()."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_file_creation_and_readback(self):
        """Save creates a valid WAV that reads back with correct data and SR."""
        audio = np.array([0.1, 0.2, 0.3, -0.3, -0.2, -0.1], dtype=np.float32)
        path = os.path.join(self.temp_dir, "created.wav")

        returned_path = save_audio_wav(audio, path, 24000)

        self.assertEqual(returned_path, path)
        self.assertTrue(os.path.exists(path))

        data, sr = sf.read(path, dtype="float32")
        self.assertEqual(sr, 24000)
        np.testing.assert_array_almost_equal(data, audio, decimal=3)

    def test_directory_auto_creation(self):
        """Save auto-creates parent directories that don't exist."""
        nested_path = os.path.join(
            self.temp_dir, "deep", "nested", "dir", "output.wav"
        )
        audio = np.zeros(100, dtype=np.float32)

        returned_path = save_audio_wav(audio, nested_path, 24000)

        self.assertEqual(returned_path, nested_path)
        self.assertTrue(os.path.exists(nested_path))

    def test_overwrite(self):
        """Second save to same path overwrites with new data."""
        path = os.path.join(self.temp_dir, "overwrite.wav")

        audio1 = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        save_audio_wav(audio1, path, 24000)

        audio2 = np.array([0.9, 0.8, 0.7, 0.6], dtype=np.float32)
        save_audio_wav(audio2, path, 24000)

        data, sr = sf.read(path, dtype="float32")
        self.assertEqual(sr, 24000)
        self.assertEqual(len(data), 4, "Content should match second write")
        np.testing.assert_array_almost_equal(data, audio2, decimal=3)
