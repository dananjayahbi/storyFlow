# Feature 4.5 — Noise Floor Addition

| Field | Value |
|---|---|
| **Feature ID** | 4.5 |
| **Title** | Noise Floor Addition |
| **Status** | 🟡 Planned |
| **Priority** | Medium |
| **Complexity** | Low |
| **Estimated Effort** | 1–2 days |
| **Dependencies** | NumPy (already available via existing stack) |
| **Output Files (NEW)** | None — all changes are within existing files |
| **Files Modified** | `backend/core_engine/audio_utils.py`, `backend/core_engine/tts_wrapper.py`, `backend/core_engine/video_renderer.py`, `backend/api/models.py`, `backend/api/serializers.py` |

---

## 1. Document Overview

### 1.1 Problem Statement

Kokoro TTS produces audio that is technically pristine — silence between words is absolute zero amplitude, commonly referred to as "digital silence." While this is acoustically correct, it is perceptually unnatural to human listeners. Human auditory systems are calibrated for environments with ambient noise, and the sudden complete absence of sound causes a subtle but noticeable perceptual discontinuity sometimes called the "dead room" effect. This is especially apparent in narration-style video content where multiple short TTS segments are played in sequence, each surrounded by sharp-edged silence. Compared to recordings made in real rooms — where background hiss, room tone, or electrical hum provide a continuous low-level noise floor — digital silence sounds sterile and "wrong." Adding a very subtle noise floor at approximately -60 dB resolves this perception issue without being audible in any meaningful sense, as -60 dB is far below the threshold of conscious hearing in normal playback conditions.

### 1.2 Proposed Solution

Introduce a `add_noise_floor` function in `audio_utils.py` that takes an audio array and a target noise level in dBFS, generates a pink-approximation noise signal of matching length and amplitude, and adds it element-wise to the input audio. Call this function inside `video_renderer.py` on each segment's audio array after TTS generation and after any other DSP steps but before file concatenation. Expose the feature as a per-project toggle via two new fields on the `Project` model.

Key changes:

- Add `add_noise_floor(audio_array, noise_level_db=-60.0)` to `audio_utils.py` using NumPy for noise generation and dB-to-linear conversion.
- Generate a pink-approximation noise signal by filtering white noise through a simple first-order filter (multiply by 1/f weighting via running mean), matching the length of the input audio exactly.
- Clamp the output array to the valid float32 range (-1.0 to 1.0) after mixing to prevent downstream clipping issues.
- Add `noise_floor_enabled` (BooleanField, default=False) and `noise_floor_db` (FloatField, default=-60.0) to the `Project` model.
- Update `ProjectSerializer` in `serializers.py` to expose both new fields.
- Call `add_noise_floor()` in `video_renderer.py` only when `project.noise_floor_enabled` is True, passing in `project.noise_floor_db`.
- Document the alternative FFmpeg approach in code comments but do not use it as the default path.
- Ensure noise floor is applied last in the DSP chain (after de-essing, compression, and reverb) so it is not inadvertently processed by upstream compressors.

### 1.3 Scope

| In Scope | Out of Scope |
|---|---|
| Per-project toggle for enabling noise floor | Global/system-wide default toggle |
| Configurable noise floor level in dBFS via project field | Real-time preview of noise floor in frontend |
| NumPy-based pink-approximation noise generation | True perceptually-equalised pink noise using IIR filter banks |
| Applying noise floor per segment in video_renderer.py | Applying noise floor to background music tracks |
| Serializer exposure of the two new project fields | Frontend UI controls for noise_floor_db slider |
| DSP ordering documentation | Psychoacoustic analysis or listening tests |
| Clamping output to valid float32 range | Multi-channel (stereo) noise generation |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| `backend/core_engine/audio_utils.py` | Core DSP utility module; home of `normalize_audio`, `get_audio_duration`, `validate_audio_file`, `save_audio_wav` | Present; does not contain any noise generation logic |
| `backend/core_engine/tts_wrapper.py` | Generates per-segment WAV via Kokoro ONNX; calls `normalize_audio` before saving | Present; no DSP chain beyond normalization |
| `backend/core_engine/video_renderer.py` | Orchestrates the full render pipeline: calls TTS per segment, concatenates audio, passes to FFmpeg | Present; no post-TTS DSP calls other than normalization via tts_wrapper |
| `backend/api/models.py` | Django ORM models including `Project` and `GlobalSettings` | Present; `Project` has many fields but no audio DSP flags |
| `backend/api/serializers.py` | DRF serializers exposing `Project` fields to the API | Present; serializes existing project fields |

---

## 2. Flow Diagram

```
[ Kokoro ONNX TTS Engine ]
         |
         | (raw 24kHz float32 audio array — digital silence between words)
         v
[ tts_wrapper.py: generate_audio() ]
         |
         | (normalize_audio called → peak-normalized array)
         v
[ video_renderer.py: per-segment loop ]
         |
         |--- [de-essing step, if enabled — future feature]
         |--- [compression step, if enabled — future feature]
         |--- [reverb step, if enabled — future feature]
         |
         | (all upstream DSP complete)
         v
[ audio_utils.py: add_noise_floor(audio_array, noise_level_db) ]
         |
         | IF project.noise_floor_enabled == True:
         |   1. Convert noise_level_db to linear amplitude scalar
         |   2. Generate white noise array (np.random.randn) matching audio length
         |   3. Apply 1/f weighting: compute running cumulative sum to approximate pink noise
         |   4. Normalize pink noise to unit range, scale by linear amplitude scalar
         |   5. Add noise array to audio array element-wise
         |   6. Clamp result to [-1.0, 1.0]
         |   7. Return modified audio array
         |
         v
[ Segment WAV files concatenated ]
         |
         v
[ FFmpeg: final video render with combined audio ]
         |
         v
[ Output MP4 with natural-sounding noise floor ]
```

---

## 3. Step-by-Step Instructions

### Step 3.1 — Add the `add_noise_floor` Function to `audio_utils.py`

Target file: `backend/core_engine/audio_utils.py`

Locate the bottom of the file, after the existing `save_audio_wav` function. Add a new public function named `add_noise_floor` that accepts two parameters: `audio_array` (a NumPy float32 array representing the audio signal) and `noise_level_db` (a float, defaulting to -60.0).

Inside the function, perform the following:

First, convert `noise_level_db` from decibels to a linear amplitude scalar. The conversion formula is the standard power/amplitude relationship: ten raised to the power of (noise_level_db divided by 20.0). At -60 dB, this produces a scalar of approximately 0.001, which is well below audible threshold.

Second, generate a white noise array of the same length as `audio_array` using NumPy's random normal generator. White noise has equal energy at all frequencies.

Third, approximate pink noise (which sounds more natural than white noise) by performing a cumulative sum over the white noise array — this introduces a 1/f spectral tilt. Then subtract the mean of the result to center the signal around zero. Finally, normalize by dividing by the maximum absolute value to bring it back to unit amplitude range.

Fourth, scale the normalized pink noise array by multiplying it with the linear amplitude scalar computed in the first step.

Fifth, add the scaled noise array to the input `audio_array` element-wise.

Sixth, clamp the output to the valid float32 range of -1.0 to 1.0 using NumPy's clip function to prevent any sample from exceeding the representable range.

Return the clamped array. Add a docstring explaining the parameters, the pink-approximation technique, and the recommended working range for `noise_level_db` (suggested: -70.0 to -50.0).

### Step 3.2 — Add a Note About the Alternative FFmpeg Approach in `audio_utils.py`

Immediately after the `add_noise_floor` function, add a comment block (not a code block) in plain Python comments that describes the alternative FFmpeg filter chain approach using `anoisesrc=c=pink` with the `amix` filter. Note that this approach requires spawning a subprocess, makes it harder to compose with other NumPy-based DSP, and is recommended only if the project switches entirely to an FFmpeg-based audio pipeline in the future. This comment exists solely as a record for future maintainers — it is not executed.

### Step 3.3 — Add `noise_floor_enabled` and `noise_floor_db` Fields to the `Project` Model

Target file: `backend/api/models.py`

Locate the `Project` model class. Find the section where audio-related fields are grouped (look for fields related to audio settings or background music, or failing that, add to the end of the field list before the `Meta` class). Add two new fields:

- `noise_floor_enabled`: a `BooleanField` with `default=False` and a `help_text` value such as "Add a subtle background noise floor to prevent digital silence." Set `blank=True` so it can be omitted from optional form submissions.
- `noise_floor_db`: a `FloatField` with `default=-60.0` and a `help_text` value such as "Noise floor level in dBFS. Recommended range: -70.0 to -50.0." Set `blank=True` and `null=True`.

Choosing `default=False` for `noise_floor_enabled` means existing projects are unaffected and the feature must be explicitly opted into — this is the desired safe default.

### Step 3.4 — Create and Apply the Database Migration

After saving the model changes, a migration must be generated. Run Django's `makemigrations` command targeting the `api` app, then run `migrate` to apply it to the SQLite database. The migration file will be placed automatically in `backend/api/migrations/`. This is a non-destructive additive migration — no existing data is modified.

### Step 3.5 — Expose Both New Fields via `ProjectSerializer`

Target file: `backend/api/serializers.py`

Locate the `ProjectSerializer` class. Find its `fields` list or `Meta.fields` declaration. Add `noise_floor_enabled` and `noise_floor_db` to the list of included fields. If individual `serializers.Field` declarations are used instead of `Meta.fields = '__all__'`, add explicit `serializers.BooleanField` and `serializers.FloatField` entries matching the model defaults, so that partial updates and creation requests handle missing values gracefully.

If a `validate_noise_floor_db` method needs to be added for input safety, add it to the serializer and have it reject values outside the range -80.0 to -40.0 with a descriptive validation error message.

### Step 3.6 — Integrate `add_noise_floor` into the Per-Segment DSP Chain in `video_renderer.py`

Target file: `backend/core_engine/video_renderer.py`

Locate the `render_project` function. Within the per-segment processing loop, find the point at which TTS generation has completed and the normalized audio array for the segment is held in memory (after the call to `generate_audio()` and after any future upstream DSP steps). This must be after compression and reverb steps if/when those are added.

Add an import for `add_noise_floor` from `audio_utils` at the top of the file, alongside existing imports from the same module.

In the per-segment loop, after all other DSP, add a conditional block: if `project.noise_floor_enabled` evaluates to True, call `add_noise_floor` with the current segment's audio array and `project.noise_floor_db`. Reassign the result back to the audio array variable. Log a debug message indicating that the noise floor step was applied, including the dB level used.

Ensure that if `noise_floor_enabled` is False, the audio array passes through unmodified — no unnecessary copies or overhead.

### Step 3.7 — Validate DSP Ordering in `video_renderer.py`

While editing `video_renderer.py`, add a comment block above the DSP chain section documenting the intended order of audio processing operations so future contributors do not accidentally insert new DSP steps in the wrong position. The canonical order is:

1. TTS generation and file loading
2. Normalization (handled inside tts_wrapper)
3. De-essing (future feature 4.x)
4. Dynamic range compression (future feature 4.x)
5. Reverb or room simulation (future feature 4.x)
6. Noise floor addition (this feature — must be last)

This comment acts as a living contract for the audio DSP pipeline order.

---

## 4. Expected Outcome

1. After implementation, any project with `noise_floor_enabled=True` will produce audio segments that contain a barely perceptible but continuous low-level background hiss at the specified dB level, eliminating the digital silence feel.
2. Projects with `noise_floor_enabled=False` (the default) will produce audio identical to the current behavior — no regression for existing users.
3. The `add_noise_floor` function can be tested independently by passing a zero-amplitude audio array and verifying that the output is non-zero and its peak level approximately matches the specified `noise_level_db`.
4. The new model fields appear in Django admin and in all Project API responses, allowing the frontend to toggle this feature per project without backend changes.
5. The final exported MP4 for a noise-floor-enabled project will pass through a simple spectral analysis showing a very slight noise floor across the entire frequency spectrum, confirming the mix was applied correctly.
6. No audible impact on the narration signal itself — the noise floor is inaudible at -60 dB on standard playback hardware but detectable by waveform inspection.
7. The DSP ordering comment in `video_renderer.py` creates a documented, maintainable audio pipeline contract visible to all future contributors.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] Test that `add_noise_floor` with a zero-amplitude input array returns a non-zero array whose peak level is within 3 dB of the specified `noise_level_db`.
- [ ] Test that `add_noise_floor` does not modify the RMS level of the input signal by more than 0.5 dB (noise floor should be nearly inaudible at -60 dB).
- [ ] Test that the output array from `add_noise_floor` never contains values outside [-1.0, 1.0], regardless of input values near the clipping boundary.
- [ ] Test that passing `noise_level_db=-60.0` and `noise_level_db=-70.0` produces outputs with different peak noise floors (order matters: -70 dB should be quieter than -60 dB in the result).
- [ ] Test that `ProjectSerializer` accepts `noise_floor_enabled=True` and `noise_floor_db=-65.0` and correctly persists both values via the ORM.
- [ ] Test that `ProjectSerializer` rejects `noise_floor_db` values outside the valid range with the expected validation error.
- [ ] Test that the `Project` model creates a default instance with `noise_floor_enabled=False` and `noise_floor_db=-60.0` when no explicit values are provided.

### 5.2 Integration / Manual Tests

- [ ] Render a short test project (1–3 segments) with `noise_floor_enabled=False` and confirm audio is identical to the current baseline.
- [ ] Render the same test project with `noise_floor_enabled=True, noise_floor_db=-60.0` and open the output WAV in Audacity or similar; confirm a visible but extremely low noise floor between words.
- [ ] Render with `noise_floor_db=-50.0` and confirm the noise floor is clearly louder than at -60.0 but still below voiced narration.
- [ ] Confirm via Django admin that both fields are visible and editable for any project object.
- [ ] Issue a PATCH request to the Project API endpoint setting `noise_floor_enabled=true` and verify the updated values are returned in the response body.
- [ ] Confirm that the migration applies cleanly on a fresh copy of the development database without errors.

### 5.3 Regression Tests

- [ ] Run the full existing test suite in `backend/tests/` and `backend/api/tests.py` and confirm all previously passing tests still pass.
- [ ] Render an existing test project (any of the test_story JSON fixtures in `docs/`) with default settings and compare the output audio hash to the pre-feature baseline to confirm no unintended changes.
- [ ] Confirm that the `normalize_audio` function still produces correct output when called on an array that was previously processed by `add_noise_floor`.
- [ ] Confirm `save_audio_wav` still writes valid WAV files after noise floor has been applied to the input array.

---

## 6. Notes for AI Agent

**Implementation order:** Complete Step 3.1 (the new function) first and run its unit tests in isolation before touching the model or renderer. This way you know the DSP logic is correct before wiring it up.

**Pink noise approximation:** The cumulative sum method is not true pink noise (which requires a Voss-McCartney IIR filter bank or similar), but it is a convincing approximation that avoids the need for additional dependencies. For this feature's stated purpose (adding naturalness, not audiophile accuracy) it is entirely sufficient and should be documented as such.

**Float vs. int16 arrays:** NumPy operations throughout `audio_utils.py` expect float32 arrays normalized to [-1.0, 1.0]. Confirm that the input to `add_noise_floor` is always float32 before the function multiplies arrays together. If there is any chance an int16 array enters the function, add a dtype check and convert at the top of the function.

**Thread safety:** The random number generator call inside `add_noise_floor` uses NumPy's global random state by default, which is not thread-safe if multiple renders run concurrently. If parallel rendering is introduced in a future phase, replace the call with a locally-scoped `np.random.default_rng()` instance.

**Avoid applying noise floor to silence padding:** If the render pipeline ever adds explicit silent padding frames at the start or end of segments (e.g., for timing purposes), consider whether those padding frames should also receive the noise floor treatment. For consistency the answer is yes — silence padding should be indistinguishable from between-word silence.

**dB range guidance:** The recommended range for `noise_floor_db` is -70.0 (nearly inaudible on any hardware) to -50.0 (just barely audible in a quiet room on headphones). Values above -50.0 risk being audible as hiss to sensitive listeners. Consider adding a warning log if a project is configured with `noise_floor_db > -50.0`.

**Migration safety:** The two new model fields both have defaults, so the migration will be non-destructive. No `RunPython` data migration is required. However, always test the migration against a copy of the production database schema before merging.

**Future integration with compressor feature:** When dynamic range compression is added (future feature 4.x), ensure that the noise floor step remains after the compressor in the DSP chain. A compressor applied to a signal that already contains a -60 dB noise floor would amplify that noise floor during gain reduction, potentially making the silence sections louder than the spoken sections.
