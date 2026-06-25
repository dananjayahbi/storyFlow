# Feature 4.1 — LUFS Loudness Normalization

| Field | Value |
|---|---|
| **Feature ID** | 4.1 |
| **Title** | LUFS Loudness Normalization |
| **Status** | 🟡 Planned |
| **Priority** | High |
| **Complexity** | Medium |
| **Estimated Effort** | 2 days |
| **Dependencies** | FFmpeg (primary), pyloudnorm (optional fallback), Feature 4.2 / 4.3 recommended before but not required |
| **Output Files (NEW)** | None (processes audio file in-place via temp path) |
| **Files Modified** | `backend/core_engine/audio_utils.py`, `backend/core_engine/video_renderer.py`, `backend/api/models.py`, `backend/api/serializers.py` |

---

## 1. Document Overview

### 1.1 Problem Statement

StoryFlow currently applies only peak normalization to its TTS audio output via the `normalize_audio()` function in `audio_utils.py`, which brings the audio peak to -1.0 dBFS. Peak normalization ensures no clipping but does not control how loud the audio sounds perceptually. Different audio streaming and social media platforms use integrated loudness targets measured in LUFS (Loudness Units Full Scale) rather than peak levels.

This means a StoryFlow video exported for YouTube (-14 LUFS target) sounds dramatically louder or quieter than other content on that platform. A video exported without LUFS normalization will either be automatically attenuated by the platform (making it quieter than surrounding content) or will sound inconsistent when users switch between videos.

### 1.2 Proposed Solution

Add a two-pass LUFS integrated loudness normalization step to the audio post-processing pipeline. The normalization will be applied to the final concatenated audio file — after all per-segment TTS clips have been joined — before the audio is mixed into the final video render.

The primary implementation uses FFmpeg's built-in `loudnorm` filter, which performs a two-pass linear loudness normalization compliant with the EBU R128 broadcast standard. An optional `pyloudnorm` library integration may be added as a pure-Python fallback for environments where FFmpeg's loudnorm capabilities are restricted.

Platform presets are provided: YouTube and TikTok target -14 LUFS, Facebook targets -16 LUFS, podcasts and broadcast target -16 LUFS or -23 LUFS respectively.

### 1.3 Scope

| In Scope | Out of Scope |
|---|---|
| Two-pass FFmpeg `loudnorm` filter on final concatenated audio | Per-segment LUFS normalization |
| `loudness_target_lufs` field on the Project model | Background music loudness balancing |
| `loudness_normalization_enabled` toggle on Project model | Real-time loudness metering in frontend |
| Four standard presets: -14, -16, -18, -23 LUFS | Dynamic platform auto-detection |
| Adding `pyloudnorm` to requirements.txt as optional fallback | True loudness metering UI display |
| Serializer support for two new fields | Loudness history / analytics |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| `backend/core_engine/audio_utils.py` | Houses all audio utility functions including `normalize_audio()` | Has peak normalize only; no LUFS support |
| `backend/core_engine/video_renderer.py` | Orchestrates the full render pipeline; calls TTS, concatenation, FFmpeg export | Concatenates segment audio then passes to final FFmpeg render; no loudness step |
| `backend/api/models.py` | Django ORM models for `Project` and `GlobalSettings` | No loudness fields present |
| `backend/api/serializers.py` | DRF serializers exposing model fields to frontend/API | Must expose two new Project fields |

---

## 2. Flow Diagram

```
TTS Generation (per segment)
        │
        ▼
Segment WAV files (e.g. seg_001.wav, seg_002.wav, ...)
        │
        ▼
Concatenation via MoviePy / FFmpeg
        │
        ▼
  final_audio.wav  (peak-normalized only, raw concat)
        │
        ▼
┌───────────────────────────────────────────┐
│  loudness_normalization_enabled == True?  │
│                                           │
│  YES → normalize_lufs(                    │
│            final_audio.wav,               │
│            final_audio_lufs.wav,          │
│            target_lufs                    │
│        )                                  │
│                                           │
│  NO  → pass through unchanged             │
└───────────────────────────────────────────┘
        │
        ▼
 Audio passed into final FFmpeg video render
        │
        ▼
     output.mp4
```

---

## 3. Step-by-Step Instructions

### Step 3.1 — Add Fields to the Project Model

Open `backend/api/models.py` and locate the `Project` model class. Add two new fields after the existing audio-related fields (or at the bottom of the field list, before `Meta` or `__str__`):

- Add a `BooleanField` named `loudness_normalization_enabled` with a default of `False`. Give it a help text string such as "Apply LUFS integrated loudness normalization to final audio mix".
- Add a `FloatField` named `loudness_target_lufs` with a default of `-14.0`. This field should have `blank=True` and `null=False`. Add a help text string describing the target loudness in LUFS. Acceptable values are -14.0 (YouTube/TikTok), -16.0 (Facebook/Podcast), -18.0 (conservative), -23.0 (broadcast/EBU R128).

Do not add database-level choices constraints here; validation will be handled in the serializer.

### Step 3.2 — Create and Run a Migration

After modifying the model, create a new Django migration for the `api` app. Run `python manage.py makemigrations api` and then `python manage.py migrate`. The migration will add the two new columns to the `api_project` table in `db.sqlite3`.

### Step 3.3 — Update the Project Serializer

Open `backend/api/serializers.py` and locate the `ProjectSerializer` (or equivalent serializer for the `Project` model). Add `loudness_normalization_enabled` and `loudness_target_lufs` to the `fields` list in the serializer's `Meta` class.

Optionally, add a `validate_loudness_target_lufs` method on the serializer that raises a `serializers.ValidationError` if the provided value is not in the allowed set {-14.0, -16.0, -18.0, -23.0}. This protects against arbitrary LUFS values being submitted through the API.

### Step 3.4 — Implement `normalize_lufs()` in `audio_utils.py`

Open `backend/core_engine/audio_utils.py`. Below the existing `normalize_audio()` function, add a new function called `normalize_lufs`. The function signature should accept three parameters: `input_wav_path` (string path to the source WAV file), `output_wav_path` (string path for the output WAV file), and `target_lufs` (float, e.g. -14.0).

The function body should work as follows:

**Pass 1 — Measure integrated loudness.** Build an FFmpeg subprocess command that reads `input_wav_path` and applies the `loudnorm` filter in measurement mode. The `loudnorm` filter parameters to set are: `I` (integrated loudness target, set to `target_lufs`), `TP` (true peak maximum, set to -1.5), and `LRA` (loudness range, set to 11.0). Direct the audio output to a null sink (`-f null -`) so no file is written. Capture the standard error output from this command — FFmpeg writes the measured loudness statistics to stderr in JSON format at the end of the pass. Parse this JSON to extract the keys: `input_i` (measured integrated loudness), `input_tp` (true peak), `input_lra` (loudness range), and `input_thresh` (threshold).

**Pass 2 — Apply correction.** Build a second FFmpeg subprocess command that reads `input_wav_path`, applies the `loudnorm` filter a second time using the measured values from Pass 1 as linear correction parameters (`measured_I`, `measured_TP`, `measured_LRA`, `measured_thresh`), and writes the result to `output_wav_path`. Set `linear=true` so the correction is a simple gain adjustment rather than dynamic compression. Set `print_format=summary` to suppress per-frame output.

The function should return the output path string on success. Raise a descriptive `RuntimeError` if either FFmpeg pass fails (non-zero return code).

Include a brief docstring explaining the two-pass approach and the meaning of the `target_lufs` parameter.

### Step 3.5 — Add `pyloudnorm` as Optional Dependency

Open `backend/requirements.txt`. Add `pyloudnorm` on a new line with no version pin initially (or pin to `>=0.1.0`). Add an inline comment `# optional: pure-Python LUFS fallback if FFmpeg loudnorm unavailable`. Do not add any import of `pyloudnorm` in `audio_utils.py` at this stage — it is reserved for a future fallback implementation.

### Step 3.6 — Call `normalize_lufs()` from `video_renderer.py`

Open `backend/core_engine/video_renderer.py`. Locate the `render_project()` method (or the section responsible for handling audio after segment concatenation and before the final FFmpeg video render command).

Find the point where the concatenated audio file path is determined — this is the audio file created by joining all per-segment WAV clips. After that concatenated file exists on disk (i.e., after the concatenation subprocess or MoviePy call completes), insert a conditional block:

- Check if the project's `loudness_normalization_enabled` field is `True`.
- If yes, determine a temporary output path for the LUFS-normalized file (e.g., append `_lufs` to the filename, or place it in the same temp directory with a different name).
- Call `normalize_lufs(concatenated_audio_path, lufs_output_path, project.loudness_target_lufs)`.
- Update the audio path variable used in the subsequent FFmpeg render command to point to `lufs_output_path` instead of the original concatenated file.
- If `loudness_normalization_enabled` is `False`, leave the audio path variable unchanged.

Import `normalize_lufs` at the top of `video_renderer.py` alongside the existing imports from `audio_utils`.

---

## 4. Expected Outcome

1. When `loudness_normalization_enabled` is `False` on a Project, the render pipeline behaves identically to before — only peak normalization from `normalize_audio()` is applied.
2. When `loudness_normalization_enabled` is `True` and `loudness_target_lufs` is set to `-14.0`, the final exported video's audio measures approximately -14 LUFS integrated loudness when analyzed with an external tool (e.g., FFmpeg `astats` filter or Audacity's LUFS measurement).
3. The two-pass FFmpeg loudnorm process completes without errors for standard WAV inputs between 5 seconds and 30 minutes in length.
4. The API returns `loudness_normalization_enabled` and `loudness_target_lufs` in the Project JSON response after the migration.
5. Setting `loudness_target_lufs` to a value outside {-14.0, -16.0, -18.0, -23.0} via the API returns a 400 validation error.
6. The temporary LUFS-normalized WAV file is created in the project's temp directory and cleaned up as part of the normal render cleanup process.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] `normalize_lufs()` accepts valid paths and a target of -14.0 without raising exceptions (mock FFmpeg subprocess)
- [ ] `normalize_lufs()` raises `RuntimeError` when the first FFmpeg pass returns a non-zero exit code
- [ ] `normalize_lufs()` raises `RuntimeError` when the second FFmpeg pass returns a non-zero exit code
- [ ] `normalize_lufs()` correctly parses the JSON loudness stats from FFmpeg stderr
- [ ] `ProjectSerializer` rejects `loudness_target_lufs` values not in the allowed set
- [ ] `ProjectSerializer` accepts all four valid LUFS values (-14.0, -16.0, -18.0, -23.0)

### 5.2 Integration / Manual Tests

- [ ] Create a Project via the API with `loudness_normalization_enabled: true` and `loudness_target_lufs: -14.0`; verify the fields are persisted in the database
- [ ] Run a full render with loudness normalization enabled; verify the output MP4's audio measures within ±1 LUFS of the target using FFmpeg's `ebur128` filter
- [ ] Run a full render with loudness normalization disabled; verify output is identical to before this feature was added
- [ ] Test with a very short audio clip (under 3 seconds) — FFmpeg `loudnorm` may refuse to process; verify a graceful error or skip behavior
- [ ] Test with -23.0 LUFS target to ensure the broad range correction does not distort the audio

### 5.3 Regression Tests

- [ ] Existing renders with `loudness_normalization_enabled: false` (default) produce the same output as before
- [ ] Peak normalization (`normalize_audio()`) still functions independently and is still called during TTS generation in `tts_wrapper.py`
- [ ] All existing API tests for the `Project` model pass without modification (new fields have defaults, so old test fixtures remain valid)
- [ ] Migration is reversible — `python manage.py migrate api <previous_migration>` succeeds without data loss

---

## 6. Notes for AI Agent

- The FFmpeg `loudnorm` filter writes its measurement JSON to **stderr**, not stdout. Make sure to capture `stderr=subprocess.PIPE` in the Pass 1 subprocess call and parse only the JSON block at the end of the output (it starts with `{` and ends with `}`).
- FFmpeg's `loudnorm` requires audio to be at least a few seconds long to compute a meaningful integrated loudness measurement. If the audio is shorter than ~3 seconds, the filter may output a warning and produce unreliable results. Consider adding a minimum-duration guard in `normalize_lufs()` that skips LUFS normalization for very short clips and logs a warning.
- The two-pass approach is more accurate than single-pass. Do not attempt to simplify this to one pass — single-pass `loudnorm` uses dynamic compression rather than linear gain, which changes the character of the audio.
- Implementation order: models → migration → serializer → audio_utils → video_renderer. Test `normalize_lufs()` in isolation with a real WAV file before wiring it into the render pipeline.
- `pyloudnorm` is listed in requirements.txt as optional infrastructure but should not be imported or used until a fallback implementation is explicitly requested. Keep the `normalize_lufs()` function FFmpeg-only for now.
- When determining the temp output path for the LUFS file in `video_renderer.py`, follow the same naming convention used by other intermediate audio files in the same function to keep cleanup logic consistent.
