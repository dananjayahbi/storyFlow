# Task 03.01.11 — Write Audio Utils Tests

> **Sub-Phase:** 03.01 — TTS Engine Integration
> **Phase:** Phase 03 — The Voice
> **Complexity:** Medium
> **Dependencies:** Task 03.01.02 (Audio Utils Module), Task 03.01.06 (Normalization Pipeline)
> **Parent Document:** [SubPhase_03_01_Overview.md](./SubPhase_03_01_Overview.md)

---

## Objective

Write comprehensive unit tests for all functions in `audio_utils.py` — covering normalization edge cases, duration calculation, file validation, and WAV saving — using synthetic NumPy arrays and temporary files.

---

## Instructions

### Step 1 — Create the test file

Create `backend/core_engine/tests/test_audio_utils.py`. Import Django's `TestCase`, `tempfile`, `shutil`, `os`, `numpy`, and `soundfile`. All tests in this file are pure unit tests that do not require the Kokoro model.

### Step 2 — Write normalization tests

Create a test class for `normalize_audio()`:

- **Known input:** Create a `float32` array with a known peak (e.g., `[0.0, 0.25, 0.5, -0.5]` — peak is 0.5). Normalize it and verify the new peak is approximately 0.8913 (within a tolerance of 1e-4).
- **Silence handling:** Pass an all-zeros array. Verify the output is also all zeros — no `inf`, `nan`, or exceptions.
- **Already normalized:** Pass an array whose peak is already 0.8913. Verify the output is effectively unchanged (element-wise difference less than 1e-6).
- **Very quiet audio:** Pass an array with a peak of 0.001. Verify the output peak is approximately 0.8913 — the function must scale up correctly.
- **Clipping input:** Pass an array with values exceeding 1.0 (e.g., peak 2.0). Verify the output peak is approximately 0.8913 — the function must scale down.
- **Dtype preservation:** Pass a `float32` array and verify the output dtype is `float32`. Repeat with `float64` if the function claims to support it.
- **No in-place modification:** Create an array, make a copy, normalize the original, and verify the copy is unchanged. Use `numpy.array_equal()` to compare the original (before normalization) copy against the original array post-call.

### Step 3 — Write duration calculation tests

Create a test class for `get_audio_duration()`:

- **Synthetic WAV:** Create a known-length NumPy array (e.g., 24000 samples at 24000 Hz = exactly 1.0 second). Write it to a temporary `.wav` file using `soundfile.write()`. Call `get_audio_duration()` on that file and verify the returned duration is 1.0 (within tolerance of 0.01).
- **Multi-second file:** Repeat with 48000 samples (2.0 seconds) to confirm scaling.
- **Non-existent file:** Call with a path that does not exist and verify it raises an appropriate exception or returns a sentinel value, depending on the function's contract.

### Step 4 — Write validation tests

Create a test class for `validate_audio_file()`:

- **Valid file:** Write a legitimate WAV file to a temp directory. Call `validate_audio_file()` and verify it returns `True`.
- **Missing file:** Call with a non-existent path and verify it returns `False`.
- **Corrupt file:** Write random bytes (not valid WAV data) to a `.wav` file. Call `validate_audio_file()` and verify it returns `False` — the function must not crash on corrupt files.

### Step 5 — Write save tests

Create a test class for `save_audio_wav()`:

- **File creation:** Save a synthetic array to a temp path and verify the file exists on disk. Read it back with `soundfile.read()` and verify the data and sample rate match.
- **Directory auto-creation:** Provide a path whose parent directory does not yet exist. Verify the function creates the directory and saves the file successfully.
- **Overwrite:** Save to the same path twice with different data. Read back and verify the content matches the second write, not the first.

### Step 6 — Clean up temporary files

Use `tempfile.mkdtemp()` in `setUp()` and `shutil.rmtree()` in `tearDown()` for every test class that writes files. Never write to the real media directory.

---

## Expected Output

```
backend/
└── core_engine/
    └── tests/
        ├── __init__.py             ← EXISTS (created in Task 03.01.10)
        └── test_audio_utils.py     ← CREATED (~150–180 lines)
```

---

## Validation

- [ ] All tests pass with `python manage.py test core_engine.tests.test_audio_utils`.
- [ ] Normalization tests cover: known input, silence, already-normalized, quiet, clipping, dtype, no-mutation.
- [ ] Duration test uses a synthetic WAV with a deterministic length.
- [ ] Validation test handles valid, missing, and corrupt files.
- [ ] Save tests verify file creation, directory creation, and overwrite.
- [ ] All file operations use temporary directories, cleaned up after each test.

---

## Notes

- These tests require `numpy` and `soundfile` to be installed (from Task 03.01.09's `requirements.txt` update), but they do NOT require the Kokoro model.
- Synthetic arrays should be small (e.g., 24000 samples = 1 second) to keep tests fast.
- The normalization tolerance of 1e-4 accounts for `float32` precision limits.
- The "no in-place modification" test is important because NumPy's `*=` operator modifies arrays in place — the implementation must avoid this.
- The corrupt file test for `validate_audio_file()` ensures robustness: a partially downloaded or truncated WAV file should not crash the application.

---

> **Parent:** [SubPhase_03_01_Overview.md](./SubPhase_03_01_Overview.md) (Layer 2)
> **Phase:** [Phase_03_Overview.md](../Phase_03_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_03_01_10_Write_TTS_Unit_Tests.md](./Task_03_01_10_Write_TTS_Unit_Tests.md)
> **Next Task:** N/A (final task of SubPhase 03.01)
