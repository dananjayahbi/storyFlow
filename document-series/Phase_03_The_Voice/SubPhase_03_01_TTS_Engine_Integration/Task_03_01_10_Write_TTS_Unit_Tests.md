# Task 03.01.10 — Write TTS Unit Tests

> **Sub-Phase:** 03.01 — TTS Engine Integration
> **Phase:** Phase 03 — The Voice
> **Complexity:** High
> **Dependencies:** Task 03.01.01 (Model Loader), Task 03.01.03 (TTS Wrapper), Task 03.01.04 (Tokenization), Task 03.01.05 (Voice ID Validation), Task 03.01.07 (WAV Storage), Task 03.01.08 (Graceful Degradation)
> **Parent Document:** [SubPhase_03_01_Overview.md](./SubPhase_03_01_Overview.md)

---

## Objective

Write comprehensive unit tests for the Model Loader, TTS Wrapper, and Voice ID Validation modules, covering success paths, error paths, edge cases, and thread safety — all without requiring the actual Kokoro model file to be present.

---

## Instructions

### Step 1 — Create the test file

Create `backend/core_engine/tests/test_tts.py`. Ensure the `tests/` directory has an `__init__.py` file. Import Django's `TestCase`, `@override_settings`, `tempfile`, `unittest.mock.patch`, `unittest.mock.MagicMock`, and `numpy`.

### Step 2 — Write Model Loader tests

Create a test class for the `KokoroModelLoader` singleton:

- **Session acquisition:** Mock `onnxruntime.InferenceSession` and verify that `get_session()` returns a session object. Assert that `InferenceSession` is called with the correct model path.
- **Singleton behavior:** Call `get_session()` twice and verify that `InferenceSession` is instantiated only once (the second call reuses the cached session).
- **`is_model_available` — file present:** Mock `os.path.exists` to return `True` and verify `is_model_available()` returns `True`.
- **`is_model_available` — file absent:** Mock `os.path.exists` to return `False` and verify `is_model_available()` returns `False`.
- **Missing model error:** Do NOT mock `InferenceSession`; instead, ensure the model file path does not exist and verify that `get_session()` raises `FileNotFoundError` with a descriptive message.
- **Thread safety:** Use `threading.Thread` to call `get_session()` concurrently from multiple threads (e.g., 10 threads). After all threads complete, verify `InferenceSession` was called exactly once.
- **Singleton reset between tests:** The singleton's cached session must be cleared in `setUp()` or `tearDown()` to prevent cross-test contamination. Access the internal `_session` attribute and set it to `None`.

### Step 3 — Write TTS Wrapper tests

Create a test class for `generate_audio()`:

- **Successful generation:** Mock the model session's `run()` method to return a synthetic NumPy array. Call `generate_audio()` with valid parameters and verify the returned dict has `"success": True`, `"duration"` as a float, and `"audio_path"` pointing to a file that exists on disk. Use `tempfile.mkdtemp()` with `@override_settings(MEDIA_ROOT=...)` to isolate file writes.
- **Valid WAV output:** After a successful `generate_audio()` call, open the output file with `soundfile.read()` and verify it contains audio data with the expected sample rate (24000 Hz).
- **Empty text error:** Call `generate_audio(text="", ...)` and verify the return dict has `"success": False` and an `"error"` string mentioning empty text.
- **Missing model error:** Do NOT mock the model loader; let it fail naturally (no model file) and verify `generate_audio()` returns `{"success": False, "error": "..."}` — not an exception.
- **Overwrite behavior:** Call `generate_audio()` twice for the same project/segment IDs. Verify the file exists and was overwritten (check file modification time or content difference).
- **Speed clamping:** Call `generate_audio()` with `speed=0.1` and `speed=10.0` (out of valid range). Verify the speed is clamped to the valid range (e.g., 0.5–2.0) without errors. The exact clamping bounds depend on the implementation.

### Step 4 — Write Voice ID Validation tests

Create a test class for `validate_voice_id()`:

- **Valid ID pass-through:** Call with each valid voice ID and verify it returns the same ID unchanged.
- **Invalid ID fallback:** Call with `"invalid_voice"` and verify it returns `"af_bella"`.
- **Empty string fallback:** Call with `""` and verify it returns `"af_bella"`.
- **None handling:** Call with `None` and verify it returns `"af_bella"`.
- **Warning logged:** Use `self.assertLogs()` to verify that a warning is logged when an invalid ID triggers fallback.

### Step 5 — Write an integration test with model skip

Create a test decorated with `@unittest.skipUnless(is_model_available(), "Kokoro model not available")` that performs a real end-to-end TTS generation. This test only runs on machines where the model has been downloaded. It should call `generate_audio()` with real text and verify the output WAV file has non-zero audio data and a reasonable duration.

### Step 6 — Clean up temporary files

Use `tempfile.mkdtemp()` for all tests that write files. Clean up in `tearDown()` using `shutil.rmtree()`. Use `@override_settings(MEDIA_ROOT=temp_dir)` to redirect file writes away from the real media directory.

---

## Expected Output

```
backend/
└── core_engine/
    └── tests/
        ├── __init__.py             ← CREATED (if not existing)
        └── test_tts.py             ← CREATED (~200–250 lines)
```

---

## Validation

- [ ] All tests pass with `python manage.py test core_engine.tests.test_tts`.
- [ ] Tests pass WITHOUT the Kokoro model file present (except the skip-guarded integration test).
- [ ] Model loader singleton is properly reset between tests (no cross-test leakage).
- [ ] File-writing tests use temporary directories, not the real media folder.
- [ ] Thread safety test demonstrates only one `InferenceSession` creation across concurrent calls.
- [ ] Voice ID validation covers valid, invalid, empty, and None inputs.

---

## Notes

- Mocking `onnxruntime.InferenceSession` is the key strategy for testing without the model. The mock's `run()` method should return a list containing a NumPy `float32` array of appropriate shape (e.g., `np.random.randn(24000).astype(np.float32)` for 1 second of audio).
- The singleton pattern complicates testing. Always reset the singleton state between tests to ensure isolation.
- The `@override_settings(MEDIA_ROOT=...)` decorator is essential — without it, tests would write WAV files into the real media directory.
- The integration test (Step 5) is valuable for CI environments where the model is available, but it must never block developers who don't have the model downloaded.

---

> **Parent:** [SubPhase_03_01_Overview.md](./SubPhase_03_01_Overview.md) (Layer 2)
> **Phase:** [Phase_03_Overview.md](../Phase_03_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_03_01_09_Update_Requirements_Txt.md](./Task_03_01_09_Update_Requirements_Txt.md)
> **Next Task:** [Task_03_01_11_Write_Audio_Utils_Tests.md](./Task_03_01_11_Write_Audio_Utils_Tests.md)
