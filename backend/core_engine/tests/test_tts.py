"""
Unit tests for the TTS engine: Model Loader, TTS Wrapper, and Voice ID Validation.

All tests run WITHOUT the Kokoro model file present (except the
skip-guarded integration test). Mocking onnxruntime.InferenceSession
is the key strategy for testing without the model.
"""

import os
import shutil
import tempfile
import threading
import unittest
from unittest.mock import MagicMock, patch

import numpy as np
import soundfile as sf
from django.test import TestCase, override_settings

from core_engine.model_loader import KokoroModelLoader
from core_engine.tts_wrapper import (
    DEFAULT_VOICE_ID,
    SPEED_MAX,
    SPEED_MIN,
    VALID_VOICE_IDS,
    generate_audio,
    validate_voice_id,
)


# ---------------------------------------------------------------------------
# Model Loader Tests
# ---------------------------------------------------------------------------


class TestKokoroModelLoader(TestCase):
    """Tests for the KokoroModelLoader singleton."""

    def setUp(self):
        """Reset singleton state before each test."""
        KokoroModelLoader._session = None

    def tearDown(self):
        """Reset singleton state after each test."""
        KokoroModelLoader._session = None

    @patch("core_engine.model_loader.os.path.exists", return_value=True)
    @patch("onnxruntime.InferenceSession")
    def test_get_session_returns_session(self, mock_session_cls, mock_exists):
        """get_session() returns an InferenceSession object."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        session = KokoroModelLoader.get_session()

        self.assertEqual(session, mock_session)
        mock_session_cls.assert_called_once()

    @patch("core_engine.model_loader.os.path.exists", return_value=True)
    @patch("onnxruntime.InferenceSession")
    def test_singleton_behavior(self, mock_session_cls, mock_exists):
        """get_session() called twice returns the same session, loads only once."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        session1 = KokoroModelLoader.get_session()
        session2 = KokoroModelLoader.get_session()

        self.assertIs(session1, session2)
        mock_session_cls.assert_called_once()

    @patch("core_engine.model_loader.os.path.exists", return_value=True)
    def test_is_model_available_true(self, mock_exists):
        """is_model_available() returns True when the file exists."""
        self.assertTrue(KokoroModelLoader.is_model_available())

    @patch("core_engine.model_loader.os.path.exists", return_value=False)
    def test_is_model_available_false(self, mock_exists):
        """is_model_available() returns False when the file is missing."""
        self.assertFalse(KokoroModelLoader.is_model_available())

    @patch("core_engine.model_loader.os.path.exists", return_value=False)
    def test_missing_model_raises_file_not_found(self, mock_exists):
        """get_session() raises FileNotFoundError with descriptive message."""
        with self.assertRaises(FileNotFoundError) as ctx:
            KokoroModelLoader.get_session()

        error_msg = str(ctx.exception)
        self.assertIn("kokoro-v0_19.onnx", error_msg)
        self.assertIn("models", error_msg.lower())

    @patch("core_engine.model_loader.os.path.exists", return_value=True)
    @patch("onnxruntime.InferenceSession")
    def test_thread_safety(self, mock_session_cls, mock_exists):
        """Concurrent get_session() calls only create one InferenceSession."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        results = []
        errors = []

        def get_session():
            try:
                session = KokoroModelLoader.get_session()
                results.append(session)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=get_session) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Thread errors: {errors}")
        self.assertEqual(len(results), 10)
        mock_session_cls.assert_called_once()
        # All threads got the same session
        for session in results:
            self.assertIs(session, mock_session)

    @patch("core_engine.model_loader.os.path.exists", return_value=True)
    @patch("onnxruntime.InferenceSession")
    def test_get_model_info(self, mock_session_cls, mock_exists):
        """get_model_info() returns input/output tensor metadata."""
        mock_input = MagicMock()
        mock_input.name = "tokens"
        mock_input.shape = [1, 512]
        mock_input.type = "tensor(int64)"

        mock_output = MagicMock()
        mock_output.name = "audio"
        mock_output.shape = [1, None]
        mock_output.type = "tensor(float)"

        mock_session = MagicMock()
        mock_session.get_inputs.return_value = [mock_input]
        mock_session.get_outputs.return_value = [mock_output]
        mock_session_cls.return_value = mock_session

        info = KokoroModelLoader.get_model_info()

        self.assertIn("inputs", info)
        self.assertIn("outputs", info)
        self.assertEqual(len(info["inputs"]), 1)
        self.assertEqual(info["inputs"][0]["name"], "tokens")
        self.assertEqual(info["outputs"][0]["name"], "audio")


# ---------------------------------------------------------------------------
# TTS Wrapper Tests
# ---------------------------------------------------------------------------


class TestGenerateAudio(TestCase):
    """Tests for the generate_audio() function."""

    def setUp(self):
        """Create temp directory and reset singleton."""
        self.temp_dir = tempfile.mkdtemp()
        KokoroModelLoader._session = None

    def tearDown(self):
        """Clean up temp directory and reset singleton."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        KokoroModelLoader._session = None

    def _mock_session(self):
        """Create a mock ONNX session that returns synthetic audio."""
        mock_session = MagicMock()

        # Mock get_inputs to return a simple structure
        mock_input = MagicMock()
        mock_input.name = "tokens"
        mock_input.shape = [1, None]
        mock_input.type = "tensor(int64)"
        mock_session.get_inputs.return_value = [mock_input]

        # Mock run to return 1 second of synthetic audio
        audio = np.random.randn(24000).astype(np.float32) * 0.5
        mock_session.run.return_value = [audio]

        return mock_session

    @override_settings(MEDIA_ROOT=None)
    def test_successful_generation(self):
        """generate_audio() returns success dict with valid output."""
        mock_session = self._mock_session()
        KokoroModelLoader._session = mock_session

        output_path = os.path.join(self.temp_dir, "test.wav")
        result = generate_audio(
            text="Hello world",
            voice_id="af_bella",
            speed=1.0,
            output_path=output_path,
        )

        self.assertTrue(result["success"])
        self.assertIn("audio_path", result)
        self.assertIn("duration", result)
        self.assertIn("sample_rate", result)
        self.assertIsInstance(result["duration"], float)
        self.assertTrue(os.path.exists(output_path))

    @override_settings(MEDIA_ROOT=None)
    def test_valid_wav_output(self):
        """Output file is a valid WAV with correct sample rate."""
        mock_session = self._mock_session()
        KokoroModelLoader._session = mock_session

        output_path = os.path.join(self.temp_dir, "test.wav")
        result = generate_audio(
            text="Hello world",
            output_path=output_path,
        )

        self.assertTrue(result["success"])

        # Read the WAV file and verify
        data, sr = sf.read(output_path)
        self.assertEqual(sr, 24000)
        self.assertGreater(len(data), 0)

    def test_empty_text_error(self):
        """Empty text returns error dict."""
        result = generate_audio(text="", output_path="/tmp/test.wav")
        self.assertFalse(result["success"])
        self.assertIn("empty", result["error"].lower())

    def test_whitespace_text_error(self):
        """Whitespace-only text returns error dict."""
        result = generate_audio(text="   \n  ", output_path="/tmp/test.wav")
        self.assertFalse(result["success"])

    def test_none_output_path_error(self):
        """None output_path returns error dict."""
        result = generate_audio(text="Hello", output_path=None)
        self.assertFalse(result["success"])
        self.assertIn("path", result["error"].lower())

    @patch("core_engine.model_loader.os.path.exists", return_value=False)
    def test_missing_model_returns_error_dict(self, mock_exists):
        """Missing model returns error dict, never raises."""
        result = generate_audio(
            text="Hello world",
            output_path=os.path.join(self.temp_dir, "test.wav"),
        )
        self.assertFalse(result["success"])
        self.assertIn("error", result)
        self.assertIsInstance(result["error"], str)

    @override_settings(MEDIA_ROOT=None)
    def test_overwrite_behavior(self):
        """Regenerating for same path overwrites the file."""
        mock_session = self._mock_session()
        KokoroModelLoader._session = mock_session

        output_path = os.path.join(self.temp_dir, "overwrite.wav")

        result1 = generate_audio(text="First", output_path=output_path)
        self.assertTrue(result1["success"])
        mtime1 = os.path.getmtime(output_path)

        # Small delay to ensure mtime differs
        import time
        time.sleep(0.05)

        result2 = generate_audio(text="Second", output_path=output_path)
        self.assertTrue(result2["success"])
        mtime2 = os.path.getmtime(output_path)

        self.assertGreaterEqual(mtime2, mtime1)

    def test_speed_clamping_low(self):
        """Speed below minimum is clamped (no error)."""
        # Speed clamping happens before model access, so the error
        # will be about the missing model, not about speed
        result = generate_audio(
            text="Hello",
            speed=0.1,
            output_path=os.path.join(self.temp_dir, "test.wav"),
        )
        # Should not crash — returns error dict (model missing)
        self.assertIn("success", result)

    def test_speed_clamping_high(self):
        """Speed above maximum is clamped (no error)."""
        result = generate_audio(
            text="Hello",
            speed=10.0,
            output_path=os.path.join(self.temp_dir, "test.wav"),
        )
        self.assertIn("success", result)

    def test_non_string_text_error(self):
        """Non-string text returns error dict."""
        for bad in [123, None, [], {}]:
            result = generate_audio(text=bad, output_path="/tmp/test.wav")
            self.assertFalse(result["success"])

    def test_never_raises(self):
        """generate_audio never raises exceptions for any input."""
        test_cases = [
            {"text": None, "output_path": None},
            {"text": "", "output_path": ""},
            {"text": 123, "output_path": 456},
            {"text": "valid", "output_path": None},
        ]
        for kwargs in test_cases:
            try:
                result = generate_audio(**kwargs)
                self.assertIn("success", result)
            except Exception as e:
                self.fail(f"generate_audio raised {type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# Voice ID Validation Tests
# ---------------------------------------------------------------------------


class TestVoiceIdValidation(TestCase):
    """Tests for the validate_voice_id() function."""

    def test_valid_ids_pass_through(self):
        """Each valid voice ID is returned unchanged."""
        for vid in VALID_VOICE_IDS:
            result = validate_voice_id(vid)
            self.assertEqual(result, vid, f"Valid ID '{vid}' was changed")

    def test_invalid_id_fallback(self):
        """Invalid voice ID falls back to default."""
        result = validate_voice_id("invalid_voice")
        self.assertEqual(result, DEFAULT_VOICE_ID)

    def test_empty_string_fallback(self):
        """Empty string falls back to default."""
        result = validate_voice_id("")
        self.assertEqual(result, DEFAULT_VOICE_ID)

    def test_none_fallback(self):
        """None value falls back to default."""
        result = validate_voice_id(None)
        self.assertEqual(result, DEFAULT_VOICE_ID)

    def test_warning_logged_on_invalid(self):
        """A warning is logged when an invalid ID triggers fallback."""
        with self.assertLogs("core_engine.tts_wrapper", level="WARNING") as logs:
            validate_voice_id("bad_voice")
        self.assertTrue(
            any("bad_voice" in log for log in logs.output),
            "Warning should mention the invalid voice ID",
        )

    def test_default_voice_in_valid_set(self):
        """DEFAULT_VOICE_ID is in VALID_VOICE_IDS."""
        self.assertIn(DEFAULT_VOICE_ID, VALID_VOICE_IDS)


# ---------------------------------------------------------------------------
# Integration Test (skip if model not available)
# ---------------------------------------------------------------------------


class TestTTSIntegration(TestCase):
    """End-to-end TTS test — only runs when the model is available."""

    @unittest.skipUnless(
        KokoroModelLoader.is_model_available(),
        "Kokoro model not available — skipping integration test",
    )
    def test_real_generation(self):
        """Generate real audio and verify output."""
        temp_dir = tempfile.mkdtemp()
        try:
            output_path = os.path.join(temp_dir, "integration_test.wav")
            result = generate_audio(
                text="This is a test of the Kokoro text to speech engine.",
                voice_id="af_bella",
                speed=1.0,
                output_path=output_path,
            )

            self.assertTrue(result["success"], f"Generation failed: {result.get('error')}")
            self.assertTrue(os.path.exists(output_path))

            # Verify the WAV has non-zero audio data
            data, sr = sf.read(output_path)
            self.assertEqual(sr, 24000)
            self.assertGreater(len(data), 0)
            self.assertGreater(np.max(np.abs(data)), 0, "Audio is all silence")

            # Reasonable duration (0.5s–120s for a short sentence)
            self.assertGreater(result["duration"], 0.5)
            self.assertLess(result["duration"], 120.0)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
