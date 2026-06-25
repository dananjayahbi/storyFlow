# Feature 2.4 — Music Fade-In / Fade-Out

| Field | Value |
|---|---|
| **Feature ID** | 2.4 |
| **Title** | Music Fade-In / Fade-Out |
| **Status** | 🟡 Planned |
| **Priority** | Medium |
| **Complexity** | Low |
| **Estimated Effort** | 1–2 days |
| **Dependencies** | Feature 2.1 (Background Music Mixing) — must be implemented first; Feature 2.3 (Music Library) is optional but complementary |
| **Output Files (NEW)** | Django migration file for the two new Project fields |
| **Files Modified** | `backend/api/models.py`, `backend/api/serializers.py`, `backend/core_engine/video_renderer.py` |

---

## 1. Document Overview

### 1.1 Problem Statement

Once Feature 2.1 (Background Music Mixing) is implemented, background music will start and end abruptly at the boundaries of the rendered video. A hard cut from silence to full-volume music at frame 1, and an equally hard cut back to silence at the final frame, sounds unprofessional and jarring. This problem applies regardless of whether the user has selected a built-in library track (Feature 2.3) or uploaded their own file. Every broadcast, podcast, and cinema production applies a short fade-in at the start and a longer fade-out at the end to smooth these transitions. Without it, the output feels unpolished even if every other element is high quality.

### 1.2 Proposed Solution

Apply FFmpeg's `afade` audio filter to the background music track during the audio mixing phase of the render pipeline. Two configurable durations are added to the `Project` model: `music_fade_in` (default 2.0 seconds) and `music_fade_out` (default 3.0 seconds). At render time, `video_renderer.py` reads these values, calculates the fade-out start position from the total video duration, and inserts `afade` filter expressions into the FFmpeg command that processes the music track before it is mixed with narration audio. If either value is zero, the corresponding fade is skipped. No additional dependencies are required — the `afade` filter is part of FFmpeg's standard build.

### 1.3 Scope

| In Scope | Out of Scope |
|---|---|
| `music_fade_in` float field on Project (seconds) | Per-segment music ducking |
| `music_fade_out` float field on Project (seconds) | Fade curve shape selection (linear vs. exponential) |
| Django migration for both new fields | Cross-fade between two different music tracks |
| FFmpeg `afade` filter applied to music track in `video_renderer.py` | Volume envelope animation beyond fade in/out |
| Serializer and frontend exposure of both fields | Music loop fade (looping track before it ends) |
| Skipping fade if value is 0.0 | Narration audio fades |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| `backend/api/models.py` | Django ORM models including `Project` | Has `Project` model; fields `music_fade_in` and `music_fade_out` do not exist yet |
| `backend/api/serializers.py` | DRF serializers for API I/O | `ProjectSerializer` exists; does not include fade fields |
| `backend/core_engine/video_renderer.py` | Orchestrates full render pipeline | Has `render_project(project_id)`; music mixing logic added by Feature 2.1 |
| `backend/core_engine/audio_utils.py` | Audio helper functions | Has `normalize_audio()`, `get_audio_duration()`, `save_audio_wav()` |
| `backend/storyflow_backend/settings.py` | Django config | `MEDIA_ROOT` defined here; relevant for resolving file paths |

---

## 2. Flow Diagram

```
render_project(project_id) is called
         |
         v
Load Project from database
Read: music_enabled, music_file (or music_library_track), music_volume,
      music_fade_in, music_fade_out
         |
         v
Determine total video duration
(sum of all segment durations, as calculated by render pipeline)
         |
         v
Is music_enabled true AND a music source is set?
    No  ──────────────────────────────────────────> Skip music entirely
    Yes
         |
         v
Resolve music file path from either music_file or music_library_track
         |
         v
Build FFmpeg filter chain for the music track:
  [Step A] Trim / loop music to match total video duration
  [Step B] Apply afade=t=in  if music_fade_in  > 0
           Insert filter: afade=t=in:st=0:d={music_fade_in}
  [Step C] Apply afade=t=out if music_fade_out > 0
           Calculate fade_out_start = total_duration - music_fade_out
           Insert filter: afade=t=out:st={fade_out_start}:d={music_fade_out}
  [Step D] Apply volume={music_volume} scaling
         |
         v
Faded, volume-adjusted music stream is now ready
         |
         v
Mix faded music stream with narration audio stream using amix filter
         |
         v
Muxed audio is combined with video frames by FFmpeg into final output file
```

---

## 3. Step-by-Step Instructions

### Step 3.1 — Add fade fields to the Project model

Open `backend/api/models.py`. Locate the `Project` model class. Find the block where music-related fields are defined (added by Feature 2.1: `music_enabled`, `music_file`, `music_volume`). Immediately after those fields, add two new fields:

- `music_fade_in` — a FloatField with a default value of 2.0. Add a help text string that says "Duration in seconds for music fade-in at start of video. Set to 0 to disable." Allow null and blank so that existing project records created before this migration do not fail validation.
- `music_fade_out` — a FloatField with a default value of 3.0. Add a help text string that says "Duration in seconds for music fade-out at end of video. Set to 0 to disable." Allow null and blank for the same reason.

Both fields represent durations in seconds and may be fractional (e.g. 1.5 seconds).

### Step 3.2 — Generate and apply the migration

Run `python manage.py makemigrations api` from the `backend/` directory. A new migration file will be created in `backend/api/migrations/`. Verify the migration file shows two `AddField` operations — one for `music_fade_in` and one for `music_fade_out`, both on the `Project` model, both with `FloatField` and the correct default values. Then run `python manage.py migrate` to apply it.

### Step 3.3 — Update the Project serializer

Open `backend/api/serializers.py`. Find the `ProjectSerializer` class. In the `Meta.fields` list (or the fields included), add `music_fade_in` and `music_fade_out`. These should be standard float fields — no special read-only or write-only constraints. Clients should be able to both read and write them.

If the serializer uses `fields = '__all__'`, the new model fields will be included automatically after the migration, but it is still good practice to verify this explicitly and ensure the API schema reflects the new fields.

### Step 3.4 — Locate the music mixing step in video_renderer.py

Open `backend/core_engine/video_renderer.py`. Find the `render_project` function. Within it, locate the section added by Feature 2.1 that handles background music mixing. This section will:

1. Check `project.music_enabled`.
2. Resolves the music file path.
3. Constructs an FFmpeg command or filter graph that takes the music audio and mixes it with the narration audio.

This is the section you will modify in the next step.

### Step 3.5 — Read fade parameters from the project

Still in `render_project`, after the section that resolves the music file path, add logic to read the two fade values from the project object. Load `music_fade_in` from `project.music_fade_in` with a fallback to 2.0 if the value is None (for safety against legacy records). Load `music_fade_out` from `project.music_fade_out` with a fallback to 3.0.

Also ensure you have access to the total video duration at this point in the function. The total duration should already be calculated earlier in `render_project` as the sum of all segment durations. Capture it into a local variable (e.g. `total_duration_seconds`) so you can use it in the fade-out start time calculation below.

### Step 3.6 — Build the afade filter expressions

In the music mixing FFmpeg command, the music audio track goes through a filter chain before being mixed with narration. Modify this filter chain to conditionally include fade filters.

The logic to follow, expressed in plain English:

- Start with an empty list of filter components for the music track.
- If `music_fade_in` is greater than 0.0, append a fade-in filter expression to the list. This filter type is "in", starts at time 0, and runs for the duration specified by `music_fade_in` seconds.
- If `music_fade_out` is greater than 0.0, calculate the start time for the fade-out. The start time equals `total_duration_seconds` minus `music_fade_out`. If this calculated start time is negative (which would happen if the fade duration is longer than the video), clamp it to 0.0. Append a fade-out filter expression to the list. This filter type is "out", starts at the calculated start time, and runs for the duration specified by `music_fade_out` seconds.
- If neither fade is requested (both are 0.0), the filter list remains empty and no fade processing is applied to the music track.

Combine these filter components into the `afade` filter chain syntax that FFmpeg's `-filter_complex` or `-af` argument expects. The `afade` filter is chained using commas in FFmpeg's filter syntax. The volume scaling filter (from Feature 2.1) should be applied after the fade filters in the chain, so the volume adjustment acts on the already-faded audio rather than the other way around.

### Step 3.7 — Validate edge cases in the filter construction

Before passing the filter chain to FFmpeg, add guards in `render_project` for the following edge cases:

- If `music_fade_in + music_fade_out` is greater than or equal to `total_duration_seconds`, log a warning and reduce the fade durations proportionally so they sum to at most 80% of the total duration. This prevents the two fades from overlapping, which would cause the music to never reach full volume.
- If `total_duration_seconds` is 0 or None (which should not happen in normal flow but could occur due to an empty project), skip music mixing entirely by treating `music_enabled` as false for this render.
- If the music file does not exist on disk at the resolved path, log an error and skip music mixing rather than crashing the render.

### Step 3.8 — Frontend: expose fade controls (reference only)

This step is a note for the frontend implementation rather than a backend code change. The frontend music settings panel (added in Feature 2.1) should be extended with two numeric input fields:

- "Fade In (seconds)" — a number input bound to `project.music_fade_in`, minimum 0, step 0.5, suggested default 2.0.
- "Fade Out (seconds)" — a number input bound to `project.music_fade_out`, minimum 0, step 0.5, suggested default 3.0.

Both inputs should be visible only when `music_enabled` is true and a music source is selected. Include short help text explaining that setting either value to 0 disables that fade. These fields are submitted as part of the existing project update API call alongside the other music settings.

---

## 4. Expected Outcome

1. The `Project` table in the database has two new float columns: `music_fade_in` and `music_fade_out`, both defaulting to 2.0 and 3.0 respectively.
2. The `GET /api/projects/{id}/` response JSON includes `music_fade_in` and `music_fade_out` fields.
3. The `PATCH /api/projects/{id}/` endpoint accepts updates to both fields and persists them.
4. When a project is rendered with `music_enabled=true` and non-zero fade values, the output video's background music audibly fades in over the configured duration at the start and fades out over the configured duration before the end.
5. When `music_fade_in=0` and `music_fade_out=0`, the rendered music starts and ends at full volume without any fade — identical to pre-feature behavior.
6. When `music_fade_in=2.0` and `music_fade_out=3.0` on a 10-second video, the music fades in over the first 2 seconds, plays at full volume from seconds 2 through 7, and fades out from second 7 to second 10.
7. When the combined fade duration would exceed the video length (e.g. fade_in=5 + fade_out=5 on a 6-second video), the render does not crash — it logs a warning and adjusts durations accordingly.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] `Project` model instantiates with `music_fade_in` and `music_fade_out` default values of 2.0 and 3.0
- [ ] Setting `music_fade_in=0.0` and `music_fade_out=0.0` on a Project saves without error
- [ ] `ProjectSerializer` serializes and deserializes `music_fade_in` and `music_fade_out` correctly
- [ ] Fade overlap guard: when fade_in + fade_out >= total_duration, a warning is logged and durations are adjusted
- [ ] Fade start time calculation: fade_out_start = total_duration - fade_out is correct for representative values
- [ ] Negative fade_out_start is clamped to 0.0

### 5.2 Integration / Manual Tests

- [ ] Render a project with default fade values (2.0 in, 3.0 out) and confirm the audio file has audible fades when played in any media player
- [ ] Render a project with `music_fade_in=0` and confirm the music begins at full volume immediately
- [ ] Render a project with `music_fade_out=0` and confirm the music ends without a fade
- [ ] Render a 5-second project with `music_fade_in=3` and `music_fade_out=3` — confirm the render completes without crashing and produces sensible output (fades overlap but do not error out)
- [ ] Update fade values via the API and immediately re-render; confirm the new render uses the updated fade durations
- [ ] Render a project with `music_enabled=false` — confirm the render ignores fade fields entirely and no music is present in the output

### 5.3 Regression Tests

- [ ] Projects with no music (`music_enabled=false`) still render successfully with no changes to audio behavior
- [ ] Projects created before this migration (with null fade values) render successfully due to the null fallback logic in `video_renderer.py`
- [ ] Narration audio (TTS) is unaffected — only background music is faded
- [ ] Existing API tests for project create, update, and list still pass
- [ ] Running `python manage.py migrate` on a fresh database applies the new migration cleanly

---

## 6. Notes for AI Agent

**Implementation order:** Complete Feature 2.1 before implementing this feature, since `video_renderer.py` must already have the music mixing section that this feature modifies. If Feature 2.1 is not yet done, this feature cannot be integrated into the render pipeline — only the model and serializer steps (3.1, 3.2, 3.3) can be done ahead of time.

**afade filter syntax reference:** FFmpeg's `afade` filter takes four key parameters: `t` (type: "in" or "out"), `st` (start time in seconds), `d` (duration in seconds), and optionally `curve` (default is "tri" for triangular/linear, which is appropriate here). When chaining multiple filters on a single stream, they are separated by commas in the filter string. The volume filter that Feature 2.1 adds should come after the afade filters in this chain.

**Where total_duration_seconds comes from:** In `render_project`, the total duration is the sum of all segment clip durations. This value should already be computed as part of the audio mixing preparation in Feature 2.1. If it is not yet a named variable, calculate it by summing `segment.duration` for all segments in the project queryset immediately before the music mixing block.

**Fade overlap scenario:** If `music_fade_in` is 4 seconds and `music_fade_out` is 4 seconds but the video is only 6 seconds, the two fades would overlap between seconds 2 and 4. FFmpeg does not error in this case but the audio will never reach full volume, which may be the desired behavior for very short ambient pieces. The proportional reduction guard (Step 3.7) limits each fade to at most 40% of total duration in these cases — so on a 6-second video with equal fade requests, each would be clamped to 2.4 seconds.

**Null safety for legacy projects:** The two new fields allow null so that `migrate` can add them to existing rows without supplying a default for existing data at the database level. However, the Python default in Django's model field definition means new projects created after the migration will always have the default float values. The fallback in `video_renderer.py` (reading the value with `or 2.0`) is a belt-and-suspenders safety measure for truly null database values left over from before the migration was applied to production.

**Testing audio fades manually:** The quickest manual test is to render a 15-second project, open the output video in VLC or an audio editor like Audacity, and visually inspect the waveform of the music track. The fade-in should show the waveform growing from zero amplitude, and the fade-out should show it tapering back to zero. There should be no sudden jumps in the waveform at the start or end.

**Frontend field labels:** "Fade In Duration" and "Fade Out Duration" with "(seconds)" as a suffix are clearer to non-technical users than raw field names. The step size of 0.5 seconds in the number input allows finer control without being overwhelming. A range of 0 to 10 seconds is a reasonable min/max for the UI control.

**Do not apply afade to narration:** The `afade` filters described here are applied exclusively to the background music audio stream within the FFmpeg filter graph. The narration (TTS) audio stream is a separate input in the filter graph and must not have these filters applied to it. Be careful when constructing the filter_complex string to keep the music stream label and the narration stream label distinct.
