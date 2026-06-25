# Feature 2.6 — Music Tempo Matching

| Field | Value |
|---|---|
| **Feature ID** | 2.6 |
| **Title** | Music Tempo Matching |
| **Status** | 🟡 Planned |
| **Priority** | Medium |
| **Complexity** | High |
| **Estimated Effort** | 5–8 days |
| **Dependencies** | Feature 2.1 (Background Music), `librosa` Python library |
| **Output Files (NEW)** | `backend/core_engine/beat_detector.py` |
| **Files Modified** | `backend/api/models.py`, `backend/api/serializers.py`, `backend/api/views.py`, `backend/api/urls.py`, `backend/requirements.txt` |

---

## 1. Document Overview

### 1.1 Problem Statement

When a user adds background music to a StoryFlow project, segment transitions happen at arbitrary time points dictated solely by the TTS audio duration of each segment. These cut points have no relationship to the musical rhythm underneath. The result is a video that feels "off" — transitions happen mid-phrase or mid-bar rather than on a beat, beat drop, or downbeat. This is immediately noticeable to viewers accustomed to TikTok and YouTube Shorts content where edits are timed to the music.

There is currently no mechanism in the pipeline to even measure the BPM of the project's music file, let alone suggest edit points based on its rhythmic structure.

### 1.2 Proposed Solution

Introduce a backend beat analysis service that operates as a fully advisory layer. When the user triggers analysis, the system detects the BPM and all beat timestamps from the project's music file using the `librosa` library. The results are cached on the `Project` model. A second endpoint then computes suggested durations for each segment such that each transition lands on the nearest beat. The frontend displays these suggestions alongside a waveform visualization so the user can accept or reject each one individually. No segment duration is ever changed automatically.

### 1.3 Scope

| In Scope | Out of Scope |
|---|---|
| BPM detection via `librosa.beat.beat_track()` | Automatic application of beat-aligned durations |
| Beat and downbeat timestamp extraction | Changing TTS speech rate to fit beat windows |
| `beat_data` caching on the `Project` model | Per-segment music volume ducking during narration |
| Suggested duration endpoint for all segments | Real-time beat waveform in the video renderer |
| Frontend advisory UI (accept / reject per segment) | Beat detection for segment audio files (only music track) |
| Adding `librosa` to `requirements.txt` | Support for multi-track stems or MIDI |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| `backend/core_engine/beat_detector.py` | New module — wraps librosa beat analysis | Does not exist |
| `backend/api/models.py` | `Project` and `Segment` models | `Project` has no `beat_data` field |
| `backend/api/views.py` | DRF viewsets and API endpoints | No beat-related endpoints |
| `backend/api/urls.py` | URL routing for API | No beat-related routes |
| `backend/api/serializers.py` | DRF serializers | `ProjectSerializer` needs `beat_data` inclusion |
| `backend/requirements.txt` | Python dependencies | `librosa` not listed |

---

## 2. Flow Diagram

```
User triggers "Analyze Music Beats"
            │
            ▼
POST /api/projects/{id}/analyze-music-beats/
            │
            ▼
  beat_detector.detect_beats(project.music_file)
            │
     ┌──────┴──────┐
     │             │
  librosa       librosa
beat_track()  onset_detect()
     │             │
     └──────┬──────┘
            │
    Returns { bpm, beats[], downbeats[] }
            │
            ▼
  Saved to Project.beat_data (JSONField)
            │
            ▼
GET /api/projects/{id}/beat-suggestions/
            │
            ▼
  For each Segment: find nearest beat to
  cumulative end-time of segment narration
            │
            ▼
  Returns { suggestions: [{ segment_index,
            suggested_duration, nearest_beat }] }
            │
            ▼
  Frontend displays waveform + beat markers
  User accepts / rejects per segment
            │
            ▼
  Accepted durations saved to Segment.duration
  (existing field — no new field needed)
```

---

## 3. Step-by-Step Instructions

### Step 3.1 — Add `librosa` to requirements

Open `backend/requirements.txt`. Add a new line for `librosa` and a new line for `soundfile`, which librosa uses as its audio I/O backend. Both should be unpinned for now to allow pip to resolve compatible versions; pin them after successful testing.

### Step 3.2 — Create `beat_detector.py`

Create a new file at `backend/core_engine/beat_detector.py`. This module must expose a single public function called `detect_beats` that accepts one argument: the absolute file path to an audio file.

Inside `detect_beats`, the function should:

1. Load the audio file using `librosa.load()` with `sr=None` to preserve the native sample rate.
2. Call `librosa.beat.beat_track()` on the loaded audio to obtain the estimated BPM and a frame-indexed beat array.
3. Convert the beat frame indices to timestamps in seconds using `librosa.frames_to_time()`.
4. Call `librosa.onset.onset_detect()` with `units="time"` to obtain onset timestamps that can approximate downbeats when combined with the beat grid.
5. Identify downbeats by selecting every Nth beat from the beat array where N is determined by the time signature assumption (default 4 for 4/4 time). This is a heuristic — not music-theory-accurate, but sufficient for visual editing purposes.
6. Return a plain Python dictionary with three keys: `bpm` (float, rounded to two decimal places), `beats` (list of floats representing seconds), and `downbeats` (list of floats representing seconds).

The function should wrap the librosa calls in a try/except block. If librosa raises any exception (corrupted file, unsupported format), the function should raise a descriptive `ValueError` with the file path and the original exception message included in the error text.

### Step 3.3 — Add `beat_data` JSONField to `Project` model

Open `backend/api/models.py`. Locate the `Project` model class. Add a new field named `beat_data` using Django's `JSONField`. Set `null=True`, `blank=True`, and `default=None`. This field stores the raw output of `detect_beats()` as a cached dictionary. It should be invalidated (set back to `None`) whenever the project's `music_file` is changed.

After adding the field, generate and apply a database migration by running `python manage.py makemigrations api` followed by `python manage.py migrate`.

### Step 3.4 — Update `ProjectSerializer`

Open `backend/api/serializers.py`. Find the `ProjectSerializer` class. Add `beat_data` to the `fields` list in its `Meta` inner class. Mark it as `read_only=True` using `extra_kwargs` — the field should only be written by the backend analysis endpoint, never by a direct client PATCH request.

### Step 3.5 — Add `analyze_music_beats` view action

Open `backend/api/views.py`. In the `ProjectViewSet` class (or whichever viewset handles the `Project` model), add a new action using the `@action` decorator from `rest_framework.decorators`.

Configure the action as:
- `methods=['post']`
- `detail=True` (operates on a single project by its primary key)
- `url_path='analyze-music-beats'`

Inside the action:
1. Retrieve the `Project` instance using `self.get_object()`.
2. Check that the project's `music_file` field is not empty. If it is, return a 400 response with a message explaining that no music file is attached to the project.
3. Resolve the absolute path of `music_file` on disk. Use Django's `MEDIA_ROOT` setting combined with the relative field value to construct the absolute path.
4. Call `beat_detector.detect_beats(absolute_path)`.
5. Save the returned dictionary to `project.beat_data` and call `project.save(update_fields=['beat_data'])`.
6. Return a 200 response containing the beat data dictionary.
7. Wrap the `detect_beats` call in a try/except for `ValueError` and return a 422 response with the error message if it fails.

### Step 3.6 — Add `beat_suggestions` view action

In the same `ProjectViewSet`, add a second action:

Configure the action as:
- `methods=['get']`
- `detail=True`
- `url_path='beat-suggestions'`

Inside the action:
1. Retrieve the `Project` instance.
2. Check that `project.beat_data` is not `None`. If it is, return a 400 response instructing the user to run the analyze endpoint first.
3. Retrieve all `Segment` objects belonging to this project, ordered by `sequence_index`.
4. For each segment, compute a cumulative end time by summing the `duration` field of all preceding segments plus the current segment's own `duration`. If `duration` is `None` for a segment, skip it and mark its suggestion as `null`.
5. Look up the beat timestamp in `project.beat_data['beats']` that is closest to the segment's cumulative end time using a simple minimum absolute-difference search.
6. The suggested duration for that segment is: `nearest_beat - cumulative_start_time` where `cumulative_start_time` is the sum of all preceding segments' durations.
7. Build a list of suggestion dictionaries, each with keys: `segment_index` (int), `segment_id` (int, the database PK), `suggested_duration` (float, rounded to 3 decimal places), `nearest_beat` (float), and `delta` (float — the difference between the suggested and current duration, for UX display).
8. Return a 200 response with `{ "bpm": project.beat_data["bpm"], "suggestions": [...] }`.

### Step 3.7 — Register the new URL routes

Open `backend/api/urls.py`. If using a DRF `DefaultRouter`, the `@action` routes on `ProjectViewSet` will be registered automatically as long as the viewset is registered with the router. Verify that `ProjectViewSet` is already registered. If the project uses explicit `path()` entries instead of a router, add two new entries:

- One for `projects/<pk>/analyze-music-beats/` mapped to the analyze action
- One for `projects/<pk>/beat-suggestions/` mapped to the suggestions action

### Step 3.8 — Invalidate `beat_data` on music file change

Open `backend/api/views.py` (or wherever PATCH/PUT for `Project` is handled). When a `music_file` field update is detected on a project save, set `project.beat_data = None` before saving. The cleanest way is to override `perform_update()` in the `ProjectViewSet` and check whether `music_file` is in the validated data — if so, also set `beat_data` to `None` in the instance before calling `serializer.save()`.

### Step 3.9 — Frontend beat visualization UI

In the project editor page (location: `frontend/app/` or `frontend/components/` — identify the segment editor component), add the following UI elements:

1. An "Analyze Music Beats" button, visible only when the project has a `music_file` attached. On click, it calls `POST /api/projects/{id}/analyze-music-beats/`.
2. After analysis, display a read-only BPM badge near the music track label.
3. A "Beat Suggestions" button that calls `GET /api/projects/{id}/beat-suggestions/` and populates a suggestion panel.
4. In the suggestion panel, list each segment by name/index. For each, show: current duration, suggested duration, and delta (e.g., "+0.34s" or "-0.12s"). Provide an "Accept" button per row.
5. An "Accept All" button that applies all suggestions at once.
6. Accepting a suggestion calls the existing segment update endpoint (PATCH `Segment.duration`) with the suggested value.

A waveform visualization (using a library such as `wavesurfer.js` or a static SVG heatmap) showing beat markers is a stretch goal for this feature's first version. The core advisory flow (analyze → suggest → accept/reject) is the required deliverable.

---

## 4. Expected Outcome

1. A new `POST /api/projects/{id}/analyze-music-beats/` endpoint returns BPM and beat timestamps within a few seconds for typical music files (under 5 minutes).
2. The `Project.beat_data` database field stores the analysis result persistently so re-analysis is not required on every page load.
3. A new `GET /api/projects/{id}/beat-suggestions/` endpoint returns per-segment duration suggestions based on the cached beat data.
4. The `beat_data` field is automatically cleared (set to `None`) when the project's music file is replaced.
5. Segments whose `duration` is `None` are listed in the suggestions response with a `null` suggestion value and a human-readable note.
6. The frontend displays an "Analyze" button, a BPM badge, and a suggestion panel with per-segment accept controls.
7. Accepting a suggestion updates the segment duration via the existing PATCH endpoint — no new write endpoint is needed.
8. The existing video rendering pipeline is completely unaffected — this feature is advisory only.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] `detect_beats()` returns a dict with keys `bpm`, `beats`, `downbeats` for a valid WAV file
- [ ] `detect_beats()` raises `ValueError` for a non-audio file (e.g., a text file)
- [ ] `detect_beats()` raises `ValueError` for a missing file path
- [ ] `beat_data` returned `bpm` value is a positive float
- [ ] `beats` list is non-empty and all values are non-negative floats
- [ ] `downbeats` list length is approximately one-quarter of the `beats` list length (within 2 elements)
- [ ] Beat suggestion computation correctly identifies the nearest beat for a known beat array and known segment duration

### 5.2 Integration / Manual Tests

- [ ] `POST /api/projects/{id}/analyze-music-beats/` returns 400 when project has no music file
- [ ] `POST /api/projects/{id}/analyze-music-beats/` returns 200 with beat data for a real MP3 music file
- [ ] After successful analysis, `Project.beat_data` is non-null in the database
- [ ] `GET /api/projects/{id}/beat-suggestions/` returns 400 when `beat_data` is null
- [ ] `GET /api/projects/{id}/beat-suggestions/` returns a suggestion for every segment with a non-null duration
- [ ] Uploading a new music file via PATCH clears `beat_data` to null
- [ ] Frontend "Analyze" button triggers analysis and displays BPM badge
- [ ] Accepting a single suggestion updates the segment duration in the database
- [ ] "Accept All" updates all suggested segment durations in the database

### 5.3 Regression Tests

- [ ] Existing video rendering `render_project()` completes successfully after this feature is deployed (no model import errors)
- [ ] `ProjectSerializer` serializes correctly for projects that have no `beat_data` (null field)
- [ ] Segment PATCH endpoint still works for duration updates unrelated to beat suggestions
- [ ] Adding `librosa` does not introduce dependency conflicts with existing packages in `requirements.txt`
- [ ] Django migrations apply cleanly on a fresh database with no prior data

---

## 6. Notes for AI Agent

**Implementation order:** Follow steps 3.1 → 3.2 → 3.3 → 3.4 → 3.5 → 3.6 → 3.7 → 3.8 → 3.9 strictly. The migration (Step 3.3) must be applied before any endpoint code that reads or writes `beat_data` is tested.

**librosa loading time:** The first import of `librosa` is slow (several seconds) due to its internal lazy loading of numba JIT caches. This is normal. Do not mistake the first-import delay for a bug.

**Beat detection accuracy:** `librosa.beat.beat_track()` uses a dynamic programming beat tracker that performs well on 4/4 rhythm. It degrades on complex polyrhythms, rubato sections, and very quiet passages. The beat suggestions will be imperfect for cinematic/ambient music — this is expected and is why the feature is advisory only.

**File format support:** `librosa` supports WAV, MP3, FLAC, OGG via `soundfile` and `audioread`. If a user's music file is in an unusual format (e.g., AAC, M4A), `librosa` may fail. The `ValueError` handling in Step 3.2 will surface this gracefully. Document this limitation in the frontend UI as a tooltip.

**JSONField availability:** Django's `JSONField` requires Django 3.1+ and works on SQLite (the current dev database) without issues. For production PostgreSQL, it maps to the native JSONB type.

**Beat suggestion edge case:** If a project has only one segment and its duration is longer than all beats in the track, the suggestion algorithm will return the last beat in the array as the nearest, resulting in a suggested duration shorter than the narration. The frontend should visually flag suggestions where `suggested_duration < segment.audio_duration` and warn the user that accepting it will truncate narration.

**Do not auto-apply suggestions in `render_project()`:** The render pipeline must remain unaware of beat data. Beat alignment is a pre-render editorial decision made by the user. Never read `Project.beat_data` inside `video_renderer.py` or `fast_compositor.py`.

**Frontend state isolation:** Beat suggestion state (loaded suggestions, accepted set) should be kept in local component state or a dedicated Zustand slice — not mixed into the main project save payload. Suggestions are transient UI state; only accepted duration values get persisted.
