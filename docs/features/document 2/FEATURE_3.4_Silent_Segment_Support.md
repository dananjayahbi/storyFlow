# Feature 3.4 — Silent Segment Support

| Field | Value |
|---|---|
| **Feature ID** | 3.4 |
| **Title** | Silent Segment Support |
| **Status** | 🟡 Planned |
| **Priority** | Medium |
| **Complexity** | Low |
| **Estimated Effort** | 2–3 days |
| **Dependencies** | Feature 2.1 (Background Music, optional), FFmpeg available in PATH |
| **Output Files (NEW)** | None |
| **Files Modified** | `backend/api/models.py`, `backend/api/serializers.py`, `backend/core_engine/audio_utils.py`, `backend/core_engine/video_renderer.py`, `backend/api/migrations/` (new migration file) |

---

## 1. Document Overview

### 1.1 Problem Statement

Currently, every segment in a StoryFlow project is expected to carry narration text in its `text_content` field. When `text_content` is empty or whitespace-only, the TTS system either throws an error, produces a zero-byte audio file, or generates audio of zero duration. Any of these outcomes causes the segment to be skipped entirely during rendering, or worse, causes `render_project()` to crash.

There is no intentional way for a creator to insert a deliberate "visual pause" — a moment where the image is displayed with only background music (or silence) and no voiceover. This is a common creative technique: let an establishing shot breathe before cutting to narrated content. Without this capability, every StoryFlow video must have continuous back-to-back narration with no rest.

### 1.2 Proposed Solution

Add two new fields to the `Segment` model — `is_silent` (a boolean flag) and `silent_duration` (a configurable hold duration in seconds). When a segment is marked silent, the rendering pipeline bypasses TTS entirely and instead generates a silent WAV file of the specified duration. The segment still renders its image with Ken Burns animation. If background music is active, it plays through uninterrupted. This creates a clean visual-only pause without any code changes to the compositor or FFmpeg layer.

### 1.3 Scope

| In Scope | Out of Scope |
|---|---|
| `is_silent` BooleanField on `Segment` model | Auto-detecting silent segments by scanning audio file amplitude |
| `silent_duration` FloatField on `Segment` model | Dedicated "ambient sound" segments with non-speech audio clips |
| `generate_silence_wav()` helper in `audio_utils.py` | Fading out narration of adjacent segments to blend with silence |
| Silent segment handling in `render_project()` | Video chapters or markers triggered by silent segments |
| Existing background music playing through silent segments | Changing the compositor or Ken Burns logic |
| Frontend toggle + duration input in segment editor | Per-segment volume override for background music |
| Database migration for new fields | Bulk "make segment silent" action |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| `backend/api/models.py` | `Segment` model definition | Has `text_content`, `audio_file`, `duration` — no silent fields |
| `backend/api/serializers.py` | DRF serializer for `Segment` | Does not expose `is_silent` or `silent_duration` |
| `backend/core_engine/audio_utils.py` | Audio helper functions | Has `get_audio_duration()`, `normalize_audio()`, `save_audio_wav()` — no silence generator |
| `backend/core_engine/video_renderer.py` | Main render orchestrator | `render_project()` unconditionally calls TTS for every segment |
| `backend/api/migrations/` | Django migration history | Will need a new auto-generated migration file |

---

## 2. Flow Diagram

```
render_project(project_id)
        │
        ▼
   For each Segment (ordered by sequence_index):
        │
        ├── is_silent == True OR text_content.strip() == "" ?
        │           │
        │     YES   ▼
        │    Skip TTS completely
        │    Call generate_silence_wav(
        │         duration=segment.silent_duration,
        │         output_path=tmp_audio_path)
        │    audio_duration = segment.silent_duration
        │           │
        │     NO    ▼
        │    Run TTS as normal
        │    audio_duration = get_audio_duration(tts_output)
        │
        ▼
   Build segment_data entry:
   {
     "audio_duration": audio_duration,
     "image_path": segment.image_file.path,
     "text_content": segment.text_content,
     "sequence_index": segment.sequence_index
   }
        │
        ▼
   fast_render_segments(segment_data, ...)
        │
        ▼
   FFmpeg mixes rendered frames + audio
   (Background music continues through silent segments
    because it is applied at the FFmpeg mix stage,
    not per-segment)
        │
        ▼
   Final video file written to disk
```

---

## 3. Step-by-Step Instructions

### Step 3.1 — Add new fields to the `Segment` model

Open `backend/api/models.py`. Locate the `Segment` model class. Add two new fields immediately after the existing `duration` field:

1. `is_silent` — a `BooleanField` with `default=False` and `help_text` set to a short description such as "If True, this segment produces no narration and uses silent_duration instead of TTS."
2. `silent_duration` — a `FloatField` with `default=3.0`, `null=True`, and `blank=True`. Add a `help_text` indicating the value is in seconds. A value of `3.0` represents a 3-second visual hold.

Do not remove or rename any existing fields. These two additions are purely additive.

### Step 3.2 — Generate and apply the migration

After saving `models.py`, run `python manage.py makemigrations api` from the `backend/` directory. Django will auto-generate a new migration file in `backend/api/migrations/` that adds the two fields with their defaults. Run `python manage.py migrate` to apply it. Verify that the migration succeeds with no errors before continuing.

### Step 3.3 — Update the `SegmentSerializer`

Open `backend/api/serializers.py`. Locate the `SegmentSerializer` class. Add `is_silent` and `silent_duration` to the `fields` list in its `Meta` inner class. Both fields should be writable (no `read_only` restriction). The default validation provided by DRF for `BooleanField` and `FloatField` is sufficient — no custom validator is needed for this step.

Optionally, add a validator that rejects a `silent_duration` value of zero or negative if `is_silent` is `True`. This prevents the user from accidentally creating a segment that holds for zero seconds. The error message should say something like "silent_duration must be greater than zero when is_silent is True."

### Step 3.4 — Add `generate_silence_wav()` to `audio_utils.py`

Open `backend/core_engine/audio_utils.py`. Add a new function named `generate_silence_wav` at the bottom of the file (after the existing helper functions).

This function takes two arguments:
- `duration`: a float representing the length in seconds
- `output_path`: a string representing the absolute file path where the WAV file should be written

The function's job is to produce a valid, silent WAV file of exactly the requested duration. There are two acceptable implementation approaches — choose the one that matches what is already used elsewhere in `audio_utils.py`:

**Approach A (numpy):** If `numpy` is already imported in `audio_utils.py`, create a zero-valued numpy array of the appropriate length by multiplying `duration` by a standard sample rate (44100 Hz). Write it as a 16-bit mono WAV file using `scipy.io.wavfile.write()` or Python's built-in `wave` module. No external process is spawned.

**Approach B (FFmpeg subprocess):** If the file already uses `subprocess` to call FFmpeg for other tasks, call FFmpeg with the `anullsrc` audio filter source, setting the duration via `-t`, the audio codec to `pcm_s16le`, and the output to the specified `output_path`. This approach requires no additional Python dependencies.

Either approach produces a bit-for-bit identical WAV that FFmpeg can read without issue at the mixing stage. Choose whichever is more consistent with the existing code style in the file.

The function should raise a `ValueError` if `duration` is zero or negative. It should raise a `RuntimeError` if the WAV file cannot be written (permissions error, disk full, etc.) with a clear message including the attempted output path.

### Step 3.5 — Handle silent segments in `render_project()`

Open `backend/core_engine/video_renderer.py`. Locate the `render_project(project_id)` function. Find the loop that iterates over a project's segments to process audio and build the `segment_data` list.

Currently, this loop unconditionally calls TTS generation for every segment. Modify this loop as follows:

For each segment, before calling TTS:

1. Evaluate whether the segment is silent by checking either `segment.is_silent == True` or `segment.text_content.strip() == ""` (empty text also triggers silent mode as a safety fallback).
2. If the segment is silent:
   - Construct a temporary file path for the silence WAV. Use the same temp directory convention already used by the renderer for TTS output files (likely something under `MEDIA_ROOT/projects/{project_id}/temp/` or a Python `tempfile` location). The filename can be `silence_{sequence_index}.wav`.
   - Call `generate_silence_wav(duration=segment.silent_duration or 3.0, output_path=tmp_silence_path)`.
   - Set `audio_duration = segment.silent_duration or 3.0`.
   - Set the audio file path for this segment to `tmp_silence_path`.
   - Do NOT call TTS. Do NOT call `get_audio_duration()` on a TTS output (since none exists). Read the duration from `segment.silent_duration` directly.
3. If the segment is not silent, proceed with TTS exactly as before — no changes to the normal code path.
4. In both cases, append the segment's entry to `segment_data` using the same dictionary structure as the existing code.

The `fast_render_segments()` function does not need to be changed. From its perspective, a silent segment is identical to a voiced segment — it receives an audio path and a duration. The fact that the audio happens to be silence is invisible to the compositor.

### Step 3.6 — Frontend: Silent Segment toggle in the segment editor

Locate the segment editor component in the frontend. It is likely at a path such as `frontend/components/SegmentEditor.tsx` or inside `frontend/app/` — search for the component that renders the `text_content` textarea and the segment's other editable fields.

Add the following UI controls to the segment form:

1. A toggle switch (or checkbox) labeled "Silent Segment" bound to the `is_silent` field of the segment.
2. When `is_silent` is toggled ON:
   - Disable (but do not hide) the `text_content` textarea so the user can see any existing text but cannot edit it.
   - Show a new numeric input labeled "Display Duration (seconds)" bound to `silent_duration`, with a minimum value of 0.5 and a default of 3.0.
3. When `is_silent` is toggled OFF:
   - Re-enable the `text_content` textarea.
   - Hide the duration input.
4. On form save/PATCH, include both `is_silent` and `silent_duration` in the request payload.

Ensure the segment card in the segment list view shows a visual indicator (e.g., a small "SILENT" badge or a muted icon) for segments where `is_silent` is `True` so the user can identify them at a glance without opening the editor.

---

## 4. Expected Outcome

1. A segment with `is_silent = True` renders successfully without any TTS call.
2. The rendered segment displays its image with full Ken Burns animation for exactly `silent_duration` seconds.
3. No narration audio is heard during the silent segment in the final video.
4. If background music is active, it plays continuously through the silent segment without a gap or duck.
5. A segment with `text_content = ""` (empty string) also triggers silent mode automatically as a safety fallback, using `silent_duration` or the default of 3.0 seconds.
6. The video renderer does not crash when encountering a silent segment — previous behavior was to error out or skip.
7. The total video duration increases correctly by the `silent_duration` value for each silent segment.
8. The `SegmentSerializer` returns `is_silent` and `silent_duration` in API responses so the frontend can accurately reflect segment state.
9. The Django admin panel shows both new fields on the `Segment` model.
10. Existing projects (with no silent segments) render identically to before — zero behavior change for the normal code path.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] `generate_silence_wav(duration=3.0, output_path=...)` creates a file at the specified path
- [ ] The created WAV file has the correct duration (within 10ms tolerance) when read back with `get_audio_duration()`
- [ ] `generate_silence_wav(duration=0, ...)` raises `ValueError`
- [ ] `generate_silence_wav(duration=-1.0, ...)` raises `ValueError`
- [ ] `Segment` model saves with `is_silent=True, silent_duration=5.0` without error
- [ ] `Segment` model saves with `is_silent=False` and `silent_duration` defaults to `3.0`
- [ ] `SegmentSerializer` validates that `silent_duration` must be > 0 when `is_silent=True`

### 5.2 Integration / Manual Tests

- [ ] Create a project with two narrated segments and one silent segment in the middle; render the project and verify the output video plays narration → silence → narration
- [ ] Create a project where the first segment is silent; render verifies the video starts with a visual hold before narration begins
- [ ] Create a segment with empty `text_content` and `is_silent=False`; render verifies the fallback silent handling activates and does not crash
- [ ] Verify that the silent segment's image renders with Ken Burns animation (not a freeze frame)
- [ ] Verify that background music (if enabled) does not have a gap or restart during a silent segment
- [ ] PATCH a segment to set `is_silent=True`; verify the API returns the updated `is_silent` and `silent_duration` values
- [ ] Frontend: toggle "Silent Segment" on — verify duration input appears and text area is disabled
- [ ] Frontend: toggle "Silent Segment" off — verify duration input disappears and text area re-enables
- [ ] Frontend: verify "SILENT" badge appears on segment card when `is_silent` is true

### 5.3 Regression Tests

- [ ] All existing narrated segments (with non-empty `text_content` and `is_silent=False`) render identically to before the feature was deployed
- [ ] `render_project()` for a project with zero silent segments completes without any change in output
- [ ] The new migration applies cleanly on a fresh SQLite database
- [ ] The new migration applies cleanly on a database with existing `Segment` rows (existing rows get `is_silent=False` and `silent_duration=3.0` as defaults)
- [ ] `SegmentSerializer` backward compatibility: an API client that does not send `is_silent` or `silent_duration` in a PATCH request receives the existing defaults without error
- [ ] No existing test in `backend/tests/` fails after the model change

---

## 6. Notes for AI Agent

**Implementation order:** Steps must be completed in order: 3.1 → 3.2 → 3.3 → 3.4 → 3.5 → 3.6. The migration (Step 3.2) is a hard prerequisite for any runtime testing of Steps 3.3 onward. Do not attempt to test the render pipeline until the migration has been applied.

**`silent_duration` default behavior:** The `or 3.0` guard in Step 3.5 (`segment.silent_duration or 3.0`) handles the case where `silent_duration` is `None` in the database (possible for segments created before this feature was deployed if the migration default was not applied retroactively). Always apply this guard in the renderer — never pass `None` as a duration to `generate_silence_wav()`.

**Empty `text_content` fallback:** The empty-text fallback in Step 3.5 is intentionally a secondary safety net, not the primary mechanism. Creators should use `is_silent=True` explicitly for intentional pauses. The fallback prevents regressions for projects that may have accidentally empty segments. Log a warning (using Python `logging`) when the fallback triggers so it is visible in backend logs.

**WAV format compatibility:** `generate_silence_wav()` must output a WAV file that FFmpeg will accept without conversion. The safest format is 16-bit PCM, mono, 44100 Hz. If the project uses 48000 Hz elsewhere (common for video), match that rate. Check the sample rate used by `save_audio_wav()` in the same file and use the same value.

**Ken Burns on silent segments:** No changes are needed in `fast_compositor.py` or `ken_burns.py`. Both functions receive only `audio_duration` and `image_path` — the fact that the audio is silence does not affect the animation calculation. The Ken Burns effect will animate normally for the full `silent_duration`.

**Frontend `is_silent` and empty text interaction:** The frontend should prevent a situation where `is_silent=False` AND `text_content=""` are saved together (since this triggers the fallback, which may be confusing). When the user clears `text_content`, the editor could offer a prompt: "Text is empty — would you like to mark this as a Silent Segment?" This is a UX improvement, not a hard requirement for the first version.

**Migration defaults:** Django will set the default for `is_silent` to `False` and `silent_duration` to `3.0` for all existing rows automatically via the migration. Verify this in the generated migration file before applying — look for `default=False` and `default=3.0` in the `AddField` operations.

**Do not modify `fast_compositor.py`:** The compositor is not aware of whether a segment is silent. This is by design. Keeping the compositor generic (it just takes an audio path and a duration) means silent segment support requires zero changes to the most complex part of the codebase.
