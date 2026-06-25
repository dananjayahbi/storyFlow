# Feature 4.6 — Output Audio Resampling Fix

| Field | Value |
|---|---|
| **Feature ID** | 4.6 |
| **Title** | Output Audio Resampling Fix |
| **Status** | 🟡 Planned |
| **Priority** | High |
| **Complexity** | Low |
| **Estimated Effort** | 1 day |
| **Dependencies** | `librosa` (to be added to requirements.txt) |
| **Output Files (NEW)** | None — all changes are within existing files |
| **Files Modified** | `backend/core_engine/audio_utils.py`, `backend/core_engine/tts_wrapper.py`, `backend/requirements.txt` |

---

## 1. Document Overview

### 1.1 Problem Statement

The Kokoro ONNX TTS engine outputs audio at a fixed sample rate of 24,000 Hz (24 kHz). The final video export pipeline targets 44,100 Hz (44.1 kHz) AAC audio, which is the standard for MP4 video containers and consumer media players. The current pipeline does not perform an explicit resampling step between these two rates — instead, the conversion happens implicitly as MoviePy passes raw audio data to FFmpeg, which then resamples silently using its default algorithm. This uncontrolled implicit resampling can introduce aliasing artifacts (frequency content that folds back into the audible range) and interpolation distortion, particularly noticeable in fricative and sibilant sounds in narration (the "s", "sh", and "t" consonants). The magnitude of the artifact depends on the content and the FFmpeg version, making it difficult to detect consistently during QA. Replacing the implicit conversion with an explicit, high-quality resampling step using a known algorithm eliminates this variable entirely and guarantees deterministic output quality across all environments.

### 1.2 Proposed Solution

Add an explicit `resample_audio` function to `audio_utils.py` that resamples any audio array from a source sample rate to a target sample rate using `librosa`'s high-quality Kaiser-window algorithm. Call this function inside `tts_wrapper.py` immediately after Kokoro generates raw audio output and before `normalize_audio` is called, ensuring that all downstream processing always operates on 44.1 kHz data. Update `save_audio_wav` to write output at the resampled rate.

Key changes:

- Add `resample_audio(audio_array, orig_sr, target_sr=44100)` to `audio_utils.py`, implemented via `librosa.resample` with `res_type='kaiser_best'` for maximum quality.
- Call `resample_audio` in `tts_wrapper.py` in the `generate_audio` function immediately after the raw NumPy array is returned from the Kokoro ONNX inference call, before the normalization step.
- The function is always-on — there is no feature flag or project-level toggle. Correct resampling is a pipeline quality baseline, not an optional enhancement.
- Add `librosa` to `backend/requirements.txt`. Note the lighter alternative `soundfile` with a Sox backend if `librosa` is considered too heavy.
- No `Project` model changes and no serializer changes are needed — this is entirely internal to the audio processing pipeline.
- At no point does any segment WAV file exist on disk at 24 kHz after this change; all persisted intermediate WAV files will be 44.1 kHz.

### 1.3 Scope

| In Scope | Out of Scope |
|---|---|
| Explicit resampling from 24 kHz Kokoro output to 44.1 kHz pipeline target | Resampling background music or sound effects (handled separately) |
| Choosing and documenting the resampling algorithm (`kaiser_best`) | Implementing alternative resamplers (Sinc, linear, etc.) |
| Adding `librosa` to `requirements.txt` | Upgrading or pinning specific versions of FFmpeg |
| Updating `tts_wrapper.py` to call resampling before normalization | Frontend changes of any kind |
| Ensuring all intermediate WAV files are written at 44.1 kHz | GPU-accelerated resampling |
| Documenting the `soundfile`/Sox alternative approach | Changing the final video export sample rate or codec |
| Logging the resampling step for pipeline observability | Real-time resampling during live preview |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| `backend/core_engine/audio_utils.py` | Core DSP utility module; contains `normalize_audio`, `get_audio_duration`, `validate_audio_file`, `save_audio_wav` | Present; no resampling function exists; sample rate is accepted as a parameter in `save_audio_wav` but callers pass whatever rate Kokoro outputs |
| `backend/core_engine/tts_wrapper.py` | Wraps Kokoro ONNX inference; `generate_audio(text, voice_id, speed, output_path)` returns per-segment WAV; calls `normalize_audio` before `save_audio_wav` | Present; 24 kHz sample rate is passed directly to `save_audio_wav` without any conversion |
| `backend/requirements.txt` | Python package dependencies for the backend | Present; lists `soundfile`; does not yet include `librosa` |

---

## 2. Flow Diagram

```
[ Kokoro ONNX Inference (fixed 24 kHz output) ]
         |
         | (raw NumPy float32 array at 24,000 Hz sample rate)
         v
[ tts_wrapper.py: generate_audio() — STEP 1 ]
         |
         v
[ audio_utils.py: resample_audio(array, orig_sr=24000, target_sr=44100) ]  ← NEW
         |
         |  1. Validate that orig_sr != target_sr (no-op guard)
         |  2. Call librosa.resample with res_type='kaiser_best'
         |     - Kaiser window: near-ideal sinc interpolation
         |     - No aliasing artifacts
         |     - Best quality at cost of slight CPU overhead
         |  3. Ensure output dtype remains float32
         |  4. Return resampled array at 44,100 Hz
         |
         v
[ tts_wrapper.py: generate_audio() — STEP 2 ]
         |
         | (array is now 44,100 Hz — all downstream code operates at correct rate)
         v
[ audio_utils.py: normalize_audio(array, target_db=-1.0) ]
         |
         | (peak normalization — sample rate irrelevant to this step)
         v
[ audio_utils.py: save_audio_wav(array, sample_rate=44100, output_path) ]
         |
         | (WAV file written at 44,100 Hz — matches final export target)
         v
[ video_renderer.py: per-segment WAV files at 44,100 Hz ]
         |
         v
[ FFmpeg: concatenate segments + encode to AAC at 44,100 Hz ]
         |
         | (NO implicit resampling — source and target rates match exactly)
         v
[ Output MP4: clean, artifact-free 44.1 kHz AAC audio ]
```

---

## 3. Step-by-Step Instructions

### Step 3.1 — Add `librosa` to `requirements.txt`

Target file: `backend/requirements.txt`

Open the file and locate the section containing audio-related dependencies (look for `soundfile` or similar entries). Add a new line for `librosa`. It is acceptable to leave the version unpinned initially to allow a broad compatibility range, but consider pinning to at least a major version (e.g., `librosa>=0.10`) to avoid breaking changes from major version bumps. Add an inline comment on the same line noting that `librosa` is required for the high-quality audio resampling step introduced in Feature 4.6.

As a reference note for the installing engineer: `librosa` depends on `scikit-learn`, `scipy`, and `numba`, so the install is moderately heavy (~150MB with all transitive dependencies). If environment size is a concern, note in a comment that `soxr` (the standalone resampler library) can serve as a lighter alternative through the `soxr` Python bindings — however, the implementation in `audio_utils.py` should remain the same interface regardless of the backend.

### Step 3.2 — Add the `resample_audio` Function to `audio_utils.py`

Target file: `backend/core_engine/audio_utils.py`

Locate the imports at the top of the file. Add an import for `librosa` at the top, placed after existing third-party imports and before local imports. Handle the import inside a try/except block that raises an `ImportError` with a clear message directing the user to install `librosa` — this gives a clean failure message instead of an obscure AttributeError deeper in the call stack if the package is missing.

After adding the import, locate the bottom of the file near the end of the existing utility functions. Add a new public function named `resample_audio` with three parameters: `audio_array` (a NumPy float32 array), `orig_sr` (integer, the original sample rate), and `target_sr` (integer, defaulting to 44100).

Inside the function body, perform the following:

First, add an early-return guard: if `orig_sr` equals `target_sr`, return the input array immediately without calling `librosa` — this prevents unnecessary processing in edge cases where the source already matches the target rate.

Second, confirm that `audio_array` is a float32 NumPy array. If it is float64, cast it to float32 before passing to `librosa.resample`, since Kokoro outputs float32 and we want to maintain that precision level throughout the pipeline.

Third, call `librosa.resample` passing the audio array, `orig_sr=orig_sr`, `target_sr=target_sr`, and `res_type='kaiser_best'`. The `'kaiser_best'` resampler uses a Kaiser-windowed sinc filter that is the highest-quality option available in `librosa`, trading some CPU time for near-alias-free output. This is the correct choice for production audio — the CPU cost for a typical 5–30 second narration segment is negligible (well under 100ms on modern hardware).

Fourth, ensure the returned array dtype is float32 by casting explicitly if needed, since `librosa.resample` may return float64 depending on the version.

Fifth, return the resampled array.

Add a comprehensive docstring that explains: the parameter types, the purpose of the Kaiser window algorithm, the expected input sample rate (24000 from Kokoro), the expected output sample rate (44100 for final export), why `'kaiser_best'` was chosen over `'kaiser_fast'` or `'linear'`, and the performance implications.

### Step 3.3 — Call `resample_audio` in `tts_wrapper.py` Immediately After Inference

Target file: `backend/core_engine/tts_wrapper.py`

Locate the `generate_audio` function. Within the function body, find the line where the Kokoro ONNX model inference returns the raw audio array. This is the earliest possible point to apply resampling — doing it here ensures all downstream code operates on 44.1 kHz data and never has to track the original sample rate.

Add an import for `resample_audio` from `audio_utils` at the top of the file, alongside the existing imports from the same module.

Immediately after inference returns the raw audio array and before any other processing (before `normalize_audio` is called), call `resample_audio(raw_audio_array, orig_sr=24000, target_sr=44100)`. Assign the result back to the audio array variable.

Add a logger.debug call after the resampling step that logs the original and target sample rates, and the length change (since resampling from 24kHz to 44.1kHz will increase the array length by a factor of 44100/24000 ≈ 1.8375). This is useful for confirming the step ran and for diagnosing any timing discrepancies downstream.

Update the inline comment on the `save_audio_wav` call further down in the function to reflect that the saved rate is now always 44100, not 24000. If the sample rate was previously hardcoded as a literal 24000 in that call, change it to 44100. If it was passed as a variable, trace the variable back and update its assignment.

### Step 3.4 — Audit `save_audio_wav` in `audio_utils.py` for Sample Rate Assumptions

Target file: `backend/core_engine/audio_utils.py`

Locate the `save_audio_wav` function. Review its implementation to confirm that it writes the `sample_rate` parameter it receives to the WAV file header without any hardcoded overrides. If there is any hardcoded value of `24000` or `24_000` inside this function, replace it with the passed `sample_rate` parameter. The function should be rate-agnostic — it should write whatever rate it receives. Document this in the function's docstring if not already stated.

This step is a safety check rather than a required code change, but it must be explicitly verified to ensure the pipeline change is complete.

### Step 3.5 — Audit `video_renderer.py` for Any Hardcoded 24kHz References

Target file: `backend/core_engine/video_renderer.py`

Search the file for any hardcoded references to the number `24000`, `24_000`, or the string `"24kHz"` or `"24000"`. If any exist (for example in FFmpeg filter strings, in audio timing calculations, or in comments describing the pipeline), update or annotate them to reflect that all audio in the pipeline is now at 44,100 Hz from the point of TTS generation onward.

Pay particular attention to any FFmpeg command construction that specifies `-ar 24000` or similar. If such a flag exists, update it to `-ar 44100`. If the audio sample rate is derived dynamically from a file, no change is needed for that path.

### Step 3.6 — Update Inline Documentation and Pipeline Comments

In `tts_wrapper.py` and `audio_utils.py`, update or add a top-of-file or top-of-function comment documenting that the audio pipeline contract is: Kokoro outputs 24 kHz → resampled to 44.1 kHz at TTS generation time → all subsequent processing at 44.1 kHz → final export at 44.1 kHz. Having this documented in the code prevents future contributors from introducing a second implicit resampling step.

---

## 4. Expected Outcome

1. After implementation, every intermediate segment WAV file written to disk by `tts_wrapper.py` will be valid 44.1 kHz WAV files, verifiable by opening them in any audio tool and inspecting the file header.
2. FFmpeg's final audio encode step operates at the native target rate — no sample rate conversion occurs inside FFmpeg during the final render, eliminating the source of implicit resampling artifacts.
3. The function `resample_audio` can be tested in isolation by passing a synthetic tone at 24 kHz, resampling to 44.1 kHz, and confirming the tone frequency is preserved and no spurious frequency components appear (aliasing test).
4. The pipeline produces audio that passes an aliasing artifact check: a 10 kHz test tone generated at 24 kHz and resampled to 44.1 kHz should appear as a clean 10 kHz sine wave in spectral analysis with no folded-back energy at 24000–10000 = 14 kHz.
5. No changes to API behavior, project configuration, or frontend code are required — this improvement is completely transparent to all users.
6. A fresh installation of the requirements produces a working environment with `librosa` installed and importable, verified by running the resampling unit tests.
7. Any render started after deployment automatically benefits from the fix — no re-rendering of old projects is required (future renders of any project will use the new pipeline).

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] Test that `resample_audio(array, orig_sr=24000, target_sr=44100)` returns an array whose length is approximately `len(array) * (44100 / 24000)` within a rounding tolerance of ±2 samples.
- [ ] Test that `resample_audio` with `orig_sr == target_sr` returns the original array without calling `librosa.resample` (early-return guard).
- [ ] Test that the output dtype of `resample_audio` is always float32, regardless of whether the input is float32 or float64.
- [ ] Test that a pure 440 Hz sine wave generated at 24 kHz survives resampling to 44.1 kHz and, when analyzed spectrally, shows energy only at 440 Hz and not at any aliasing frequencies.
- [ ] Test that `resample_audio` raises a descriptive `ImportError` or `RuntimeError` when `librosa` is unavailable (mock the import in the test).
- [ ] Test that a 10 kHz sine wave resampled from 24 kHz to 44.1 kHz does not exhibit energy above 12 kHz (aliasing check: 12 kHz is the Nyquist limit of the 24 kHz source).

### 5.2 Integration / Manual Tests

- [ ] Run a full project render end-to-end and inspect an intermediate segment WAV using `ffprobe` — confirm the reported sample rate is 44100.
- [ ] Open a rendered segment WAV in Audacity and zoom into the waveform at a silence-to-speech transition; confirm that there are no audible pops, clicks, or aliasing artifacts compared to the pre-fix baseline.
- [ ] Compare the spectrogram of a rendered narration segment before and after this fix; confirm that the high-frequency content (above 10 kHz) is cleaner and without frequency mirroring.
- [ ] Run `pip install -r requirements.txt` in a clean virtual environment and confirm that `librosa` installs successfully and can be imported.
- [ ] Time the resampling call for a representative 30-second audio segment; confirm it completes in under 500ms on the development machine.
- [ ] Render a test project using one of the `docs/test_story_*.json` fixtures and confirm the output MP4 plays back without audio artifacts.

### 5.3 Regression Tests

- [ ] Run the full existing test suite in `backend/tests/` and `backend/api/tests.py` and confirm all previously passing tests still pass.
- [ ] Confirm that `normalize_audio` still produces the correct peak amplitude when called on an array that was first processed by `resample_audio`.
- [ ] Confirm that `validate_audio_file` still correctly validates WAV files written at 44100 Hz after the pipeline change.
- [ ] Confirm that `get_audio_duration` returns the correct duration (in seconds) for a resampled segment — the playback duration should be unchanged even though the array length increased.
- [ ] Render a project that previously produced a known-good output and compare the new output's audio duration in seconds to the original to confirm no timing drift from the resampling step.

---

## 6. Notes for AI Agent

**Implementation order:** The safest order is: (1) add `librosa` to `requirements.txt` and install it, (2) add and test `resample_audio` in `audio_utils.py` in complete isolation, (3) integrate the call into `tts_wrapper.py`, (4) perform the audit of `video_renderer.py`. Never wire up the call in `tts_wrapper.py` before the unit tests for `resample_audio` pass — otherwise a silent bug in the resampling function will corrupt all rendered audio for all projects.

**Why `kaiser_best` over `kaiser_fast`:** `kaiser_best` uses a longer sinc filter kernel (larger `num_zeros` parameter) which provides better stopband rejection and lower aliasing energy. The performance difference for a 30-second audio segment in float32 is on the order of 50–200ms on modern hardware — negligible for a batch render pipeline. `kaiser_fast` is appropriate for real-time or interactive use cases only. Document this choice explicitly so a future contributor does not "optimize" it away.

**Numba JIT compilation delay:** `librosa` uses `numba` for JIT compilation of certain inner loops. The first call to `librosa.resample` in a process may be slower (1–5 seconds) due to JIT warmup. Subsequent calls in the same process are fast. This means the first segment in a render may take unexpectedly long. Consider adding a warm-up call at server startup (process a tiny 1-sample dummy array) to pre-compile the JIT cache, so this delay does not affect the user-visible render time for real projects.

**Stereo vs. mono:** Kokoro produces mono audio. `librosa.resample` in recent versions expects shape `(num_samples,)` for mono (1D array) and `(num_channels, num_samples)` for multi-channel. Confirm the shape of the Kokoro output array before calling `resample_audio` and document the expected shape in the function docstring. If the shape is ever 2D mono (e.g., shape `(1, N)`), squeeze it to 1D first.

**Array length and timing:** The resampled array will be longer than the original by a factor of 44100/24000 ≈ 1.8375. Any downstream code that uses the array length to calculate timing (e.g., for computing segment start/end timestamps) must use the sample rate, not the array length, as the authoritative source of time. Audit `video_renderer.py` for any places where `len(audio_array) / 24000` appears as a duration calculation and replace with the correct rate.

**Alternative: soundfile + Sox backend:** If `librosa` is deemed too heavy for the deployment environment, the `soxr` Python package provides high-quality resampling with minimal dependencies. The interface is similar: call `soxr.resample(audio_array, orig_sr, target_sr, quality='HQ')`. The `HQ` quality level corresponds approximately to `kaiser_best` in terms of stopband performance. If this alternative is chosen, update `requirements.txt` to use `soxr` instead of `librosa`, and update the import in `audio_utils.py` accordingly. The function signature of `resample_audio` does not need to change.

**No model or serializer changes:** Because this is a pipeline-internal fix with no user-facing configuration, confirm that no migration is needed before deploying. The absence of model changes means this feature can be deployed to a running production environment without any database operations — a significant operational advantage.

**Interaction with Feature 4.5 (Noise Floor):** When both Feature 4.5 and Feature 4.6 are implemented, the noise floor function receives a 44.1 kHz array (since resampling happens first in `tts_wrapper.py`). The `add_noise_floor` function must therefore generate its pink noise at 44.1 kHz length. Because the noise generation is based purely on array length (not sample rate), this works correctly by default — but add a note in `add_noise_floor`'s docstring clarifying that it is rate-agnostic and always generates noise matching `len(audio_array)` samples.
