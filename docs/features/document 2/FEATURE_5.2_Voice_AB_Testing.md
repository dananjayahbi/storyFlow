# Feature 5.2 — Voice A/B Testing

| Field | Value |
|---|---|
| **Feature ID** | 5.2 |
| **Title** | Voice A/B Testing |
| **Status** | 🟡 Planned |
| **Priority** | Medium |
| **Complexity** | Low |
| **Estimated Effort** | 2 day(s) |
| **Dependencies** | Feature 1.3 (per-segment voice ID) optional; TTS pipeline must be functional |
| **Output Files (NEW)** | None (temp WAV files are ephemeral under `media/projects/{id}/audio/`) |
| **Files Modified** | `backend/core_engine/tts_wrapper.py`, `backend/api/views.py`, `backend/api/urls.py`, `backend/api/tasks.py` |

---

## 1. Document Overview

### 1.1 Problem Statement

When a creator builds a project in StoryFlow, choosing the right TTS voice for a segment is currently a slow, trial-and-error process. To hear how a different voice sounds, the user must change the project's voice setting, trigger a full TTS regeneration for the segment, and wait for the audio to be created — only to find out they preferred the original voice. Each regeneration overwrites the previously saved audio file, so there is no way to compare voices without losing the prior result. This forces creators to mentally remember how earlier voices sounded and repeatedly redo work. For projects with many segments, the cumulative time wasted on voice selection is significant, and the experience discourages experimentation. The goal of this feature is to make voice comparison instant, non-destructive, and side-by-side so creators can make confident voice choices before committing.

### 1.2 Proposed Solution

Introduce a dedicated "compare voices" flow that generates temporary audio previews for a list of voices without overwriting the segment's saved audio. The user selects which voices they want to compare, the backend generates all previews in parallel or sequence, and the frontend presents them side-by-side for playback. When the user makes a final selection, a separate "apply" call promotes the chosen preview to the active audio file.

Key solution components:

- A new helper function in `tts_wrapper.py` that accepts a list of voice IDs and generates a temporary WAV file for each, returning the file paths and durations.
- A new REST endpoint `POST /api/projects/{id}/segments/{seg_id}/compare-voices/` that accepts the voice list, drives the helper, and returns audio URLs with metadata for each voice.
- A new REST endpoint `POST /api/projects/{id}/segments/{seg_id}/apply-voice/` that takes a single chosen voice ID, copies the corresponding temp file to the canonical audio path, and updates the segment record.
- A Celery periodic cleanup task that deletes any compare temp files older than 24 hours, preventing stale media accumulation.
- No permanent data model changes are required on the generation side — only the apply step updates existing model fields.

### 1.3 Scope

| In Scope | Out of Scope |
|---|---|
| Generating 2–5 voice preview files per segment on demand | Generating previews for an entire project at once |
| Returning audio URLs and duration for each voice | Waveform visualisation in the frontend |
| Applying a chosen voice to the segment and updating the model | Batch-applying a chosen voice to all segments |
| Cleaning up temp comparison files after 24 hours | Storing comparison history or analytics |
| Validating that requested voice IDs are in `VALID_VOICE_IDS` | Adding new voice models or voice cloning |
| Handling the case where the segment has no `text_content` | Real-time streaming TTS preview |
| Updating `Segment.audio_file` and optionally `Project.voice_id` on apply | Per-segment voice ID (Feature 1.3) — apply step is compatible but does not require it |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| `backend/core_engine/tts_wrapper.py` | Houses `generate_audio()`, voice ID constants, and speed validation | Functional; needs new `generate_tts_for_voices()` helper |
| `backend/api/views.py` | REST API view handlers | Functional; needs two new view functions/classes |
| `backend/api/urls.py` | URL routing configuration | Functional; needs two new URL patterns |
| `backend/api/tasks.py` | Celery async tasks for TTS generation | Functional; needs a new cleanup task |
| `backend/api/models.py` | Django ORM models for Project and Segment | Functional; no changes required for generation; apply step uses existing fields |
| `backend/core_engine/audio_utils.py` | Audio utility functions including `get_audio_duration()` | Functional; used to compute duration for compare results |
| `backend/media/projects/{id}/audio/` | Storage location for all audio files | Existing directory structure |

---

## 2. Flow Diagram

```
User selects voices to compare in frontend UI
              │
              ▼
POST /api/projects/{id}/segments/{seg_id}/compare-voices/
  body: { voice_ids: ["af_bella", "am_adam", "bf_emma"] }
              │
              ▼
   views.py: CompareVoicesView
              │
              ├─ Validate segment exists and belongs to project
              ├─ Validate all voice IDs are in VALID_VOICE_IDS
              └─ Call generate_tts_for_voices(text, voice_ids, project_id, seg_id)
                          │
                          ▼
              tts_wrapper.py: generate_tts_for_voices()
                          │
                   For each voice_id:
                   ├─ Build temp path: media/projects/{id}/audio/{seg_id}_compare_{voice_id}.wav
                   ├─ Call generate_audio(text, voice_id, speed, temp_path)
                   └─ Get duration via get_audio_duration(temp_path)
                          │
                          ▼
              Return list of { voice_id, audio_url, duration }
              │
              ▼
   Frontend plays each audio inline for comparison
              │
   User selects preferred voice
              │
              ▼
POST /api/projects/{id}/segments/{seg_id}/apply-voice/
  body: { voice_id: "am_adam" }
              │
              ▼
   views.py: ApplyVoiceView
              │
              ├─ Locate temp file: {seg_id}_compare_{voice_id}.wav
              ├─ Copy/move to canonical path: {seg_id}.wav
              ├─ Update Segment.audio_file field
              ├─ Optionally update Project.voice_id
              └─ Delete all other temp compare files for this segment
              │
              ▼
   Frontend confirms active voice, removes compare UI

              ┄┄┄ Background (Celery periodic task) ┄┄┄

   cleanup_compare_files_task (runs every 1 hour)
              │
   Scan media/projects/*/audio/ for files matching *_compare_*.wav
   Delete any where file modification time is older than 24 hours
```

---

## 3. Step-by-Step Instructions

### Step 3.1 — Add the `generate_tts_for_voices` helper to `tts_wrapper.py`

Open `backend/core_engine/tts_wrapper.py`. At the bottom of the file, after the existing `generate_audio` function and `get_available_voices` function, add a new function named `generate_tts_for_voices`. This function should accept four arguments: the text content to synthesize, a list of voice IDs to compare, the project ID, and the segment ID.

Inside the function, first validate that the voice IDs list contains between 2 and 5 entries — raise a `ValueError` with a readable message if the count is outside that range. Then, for each voice ID in the list, check that it appears in `VALID_VOICE_IDS` and skip it with a logged warning if it does not. Construct the temp output path for each voice using the pattern `media/projects/{project_id}/audio/{segment_id}_compare_{voice_id}.wav`. Ensure that the containing directory exists before writing. Call the existing `generate_audio(text, voice_id, speed, output_path)` function with the default speed and the constructed path. After generation, call `get_audio_duration(output_path)` from `audio_utils.py` to measure the duration. Collect the results as a list of dictionaries, each containing `voice_id`, the full file path, and the duration in seconds. Return this list to the caller. If generation fails for a particular voice, catch the exception, log it, and continue processing the remaining voices so a partial result is returned rather than a total failure.

### Step 3.2 — Create the `CompareVoicesView` in `views.py`

Open `backend/api/views.py`. Add a new view class or function named `CompareVoicesView` (or `compare_voices` if using function-based views). This view should handle `POST` requests only.

In the handler, extract `project_id` and `segment_id` from the URL kwargs. Query the database to confirm the `Project` exists and return a 404 if not. Then confirm the `Segment` exists and belongs to that project. Extract the `voice_ids` field from the request body — return a 400 error if it is missing, not a list, or contains fewer than 2 or more than 5 entries. Verify that every voice ID in the list is recognised by checking against `VALID_VOICE_IDS` from `tts_wrapper.py` — return a 400 with a descriptive message listing any unrecognised IDs.

Retrieve the segment's `text_content`. If the field is empty or None, return a 400 error explaining that the segment has no text to synthesise. Call `generate_tts_for_voices` with the text, the voice ID list, the project ID, and the segment ID. For each result in the returned list, convert the internal file path to a public media URL using Django's `request.build_absolute_uri` and the `settings.MEDIA_URL` prefix. Build a response list of objects containing `voice_id`, `audio_url`, and `duration`. Return this list with a 200 status code.

### Step 3.3 — Create the `ApplyVoiceView` in `views.py`

In the same `views.py` file, add a second new view named `ApplyVoiceView` (or `apply_voice`). This view also handles `POST` requests only.

Extract `project_id`, `segment_id`, and `voice_id` (from the request body). Validate that the project and segment exist. Validate that `voice_id` is in `VALID_VOICE_IDS`. Construct the expected temp file path for the chosen voice: `media/projects/{project_id}/audio/{segment_id}_compare_{voice_id}.wav`. If that file does not exist on disk, return a 404 explaining that the comparison audio for the selected voice was not found — the user may need to re-run the compare endpoint.

Define the canonical audio path for this segment: `media/projects/{project_id}/audio/{segment_id}.wav`. Copy the temp file to the canonical path, overwriting any existing file. Update `Segment.audio_file` to reference the canonical path and save the segment. Optionally, if Feature 1.3 per-segment voice IDs are implemented, also update `Segment.voice_id`. If the project-level `voice_id` should reflect the user's choice, update and save `Project.voice_id` as well—leave this as a conditional update based on a request body flag `update_project_voice` (defaulting to false) so it is not forced.

After saving, delete all temp compare files for this segment — iterate over the audio directory, find all files matching the `{segment_id}_compare_*.wav` pattern, and remove them. Return a 200 response confirming the applied voice ID and the updated audio URL.

### Step 3.4 — Register the two new URL patterns in `urls.py`

Open `backend/api/urls.py`. Add two new URL patterns to the existing `urlpatterns` list.

The first pattern should route `projects/<int:project_id>/segments/<int:segment_id>/compare-voices/` to `CompareVoicesView` with a name of `segment-compare-voices`.

The second pattern should route `projects/<int:project_id>/segments/<int:segment_id>/apply-voice/` to `ApplyVoiceView` with a name of `segment-apply-voice`.

Ensure that both patterns are placed logically near any other segment-specific URL patterns to keep the URL file readable.

### Step 3.5 — Add the `cleanup_compare_files_task` to `tasks.py`

Open `backend/api/tasks.py`. Add a new Celery task named `cleanup_compare_files_task`. Decorate it with the Celery `@shared_task` decorator.

Inside the task function, determine the root media directory from Django settings using `settings.MEDIA_ROOT`. Walk through all subdirectories matching the pattern `projects/*/audio/`. For each directory, list all files whose names match the pattern `*_compare_*.wav` using standard Python filename matching. For each matching file, check the file's last-modified timestamp using `os.path.getmtime`. If the file is more than 86400 seconds old (24 hours), delete it using `os.remove` and log the deletion at the INFO level. Catch any `OSError` during deletion and log it at the WARNING level without stopping the task. After scanning all directories, log a summary of how many files were deleted. Return the total deletion count from the task so Celery result backends can record it.

Register this task in the Celery beat schedule. Add an entry in the `CELERY_BEAT_SCHEDULE` dictionary in `storyflow_backend/settings.py` so that `cleanup_compare_files_task` runs every hour using a `crontab` or `timedelta(hours=1)` schedule.

### Step 3.6 — Verify serializer response shape (no changes expected)

Open `backend/api/serializers.py` and confirm that there is no need to update any existing serializer for this feature, since the compare and apply endpoints return ad-hoc JSON responses built directly in the view rather than using DRF serializers. If the project follows a strict serializer-per-response policy, consider adding lightweight data classes or simple serializer classes for `VoiceCompareResult` and `ApplyVoiceResult` — but this is optional and not required for the feature to function.

### Step 3.7 — Document the API contract for both new endpoints

Add inline docstrings to both view classes describing the expected request and response shapes. This serves as living documentation for frontend developers and for automated API schema tools (such as `drf-spectacular` or `drf-yasg`) that may be added in the future.

For `CompareVoicesView`, the request body shape is a JSON object with a single key `voice_ids` whose value is an array of between 2 and 5 strings from `VALID_VOICE_IDS`. The success response (HTTP 200) is a JSON array where each element contains three fields: `voice_id` (string), `audio_url` (absolute URL string), and `duration` (float, seconds).

For `ApplyVoiceView`, the request body shape is a JSON object with a required `voice_id` string field and an optional boolean `update_project_voice` field (default false). The success response (HTTP 200) is a JSON object containing `segment_id`, `voice_id`, `audio_url`, and `duration`.

Document all possible error responses for each endpoint in the docstring: 400 for validation failures, 404 for missing project, segment, or temp file, and 500 (logged internally) for unexpected TTS generation errors. This error contract lets the frontend implement consistent error handling across both endpoints.

### Step 3.8 — Add permission checks to both new endpoints

Before adding the new endpoints to production routing, verify that the existing authentication and permission classes applied globally in `storyflow_backend/settings.py` (such as `IsAuthenticated`) are enforced on the new views. If the views use class-based views inheriting from `APIView`, they will inherit global permission classes automatically. If function-based views are used, confirm that the `@permission_classes` decorator is applied.

Also confirm that neither endpoint allows a user to access segments belonging to another user's project. The segment lookup in both views already filters by project ID (Step 3.2 and 3.3), but additionally verify that the project itself is owned by the requesting user. Add a check comparing `project.owner` (or equivalent ownership field) to `request.user` and return a 403 Forbidden response if they do not match. Do not return a 404 in this case, as revealing that a project does or does not exist to an unauthorised user is an information leakage concern — a consistent 403 is safer.

---

## API Contract Reference

| Endpoint | Method | Request Body Fields | Success Response Shape | Key Error Codes |
|---|---|---|---|---|
| `/api/projects/{id}/segments/{seg_id}/compare-voices/` | POST | `voice_ids: string[]` (2–5 items) | Array of `{ voice_id, audio_url, duration }` | 400 invalid voices; 400 no text; 404 segment not found |
| `/api/projects/{id}/segments/{seg_id}/apply-voice/` | POST | `voice_id: string`, `update_project_voice?: bool` | `{ segment_id, voice_id, audio_url, duration }` | 400 invalid voice; 404 segment not found; 404 temp file missing |

---

## 8. Troubleshooting Guide

The following table covers the most likely failure modes during implementation and testing of this feature.

| Symptom | Likely Cause | Resolution |
|---|---|---|
| Compare endpoint returns 400 on all requests | `VALID_VOICE_IDS` import path is wrong in `views.py` | Confirm the import path for `tts_wrapper.VALID_VOICE_IDS` matches the module layout |
| Temp WAV files are not created | Audio directory for the project does not exist | Verify `os.makedirs(exist_ok=True)` is called before `generate_audio` in the helper |
| `audio_url` in response points to a 404 | `MEDIA_URL` is not set correctly in `settings.py` or has a trailing slash conflict | Check `settings.MEDIA_URL` and the URL construction logic in the view |
| Apply endpoint raises `FileNotFoundError` | Temp file was cleaned up before apply was called | Return a 404 and instruct the client to re-run the compare endpoint |
| Cleanup task deletes canonical audio files | Filename pattern matching is too broad | Ensure the glob pattern includes `_compare_` as a required infix |
| Celery Beat task never runs | Beat schedule not registered in `settings.py` | Add the `CELERY_BEAT_SCHEDULE` entry and restart the Beat process |
| Duration returned is 0.0 for all voices | `get_audio_duration` is failing silently | Add explicit error logging inside `generate_tts_for_voices` and check the WAV header |
| Apply endpoint does not update `Segment.audio_file` | ORM save is not being called after field assignment | Confirm `segment.save()` or `segment.save(update_fields=[...])` is present in the view |
| Compare generates only 1 of 3 requested voices | One or more voice IDs failed inference silently | Check the INFO-level logs for the `Skipping invalid voice` warning emitted by the helper |
| `shutil.copy2` raises `PermissionError` on Windows | Temp file still held open by the TTS inference library | Ensure `generate_audio` closes all file handles before returning; consider a small retry loop |
| Response takes over 30 seconds for 5 voices | TTS inference is running sequentially on slow hardware | Accept as a known limitation for the initial version; document the async upgrade path in Section 7 |

---

## 9. Recommended Implementation Order

Complete the backend steps before touching the URL routing, and test each component in isolation before wiring them together. The suggested order is: Step 3.1 (helper function) → run unit tests against the helper → Step 3.2 (compare view) → Step 3.3 (apply view) → Step 3.4 (URL registration) → Step 3.5 (cleanup task) → Step 3.6 (serializer review) → Step 3.7 (docstrings) → Step 3.8 (permissions). Following this order ensures that each dependency is verified before it is relied upon by the next component, making it easier to isolate failures during development. Do not register the URL patterns until both view classes pass their unit tests independently, because a misconfigured URL routing table with a broken view can mask the root cause of errors.

This order also mirrors the natural dependency chain: the helper in `tts_wrapper.py` has no Django dependencies, so it can be developed and tested first in full isolation before any web-layer code is written.

---

## 4. Expected Outcome

1. A `POST` request to `/api/projects/1/segments/3/compare-voices/` with a body of two or more valid voice IDs returns a JSON array containing one entry per voice, each with a `voice_id`, a playable `audio_url`, and a `duration` value in seconds.
2. The temporary WAV files appear on disk under `media/projects/1/audio/` with filenames following the `3_compare_{voice_id}.wav` pattern.
3. The segment's existing canonical audio file (`3.wav`) is not modified or deleted by the compare endpoint.
4. A `POST` request to `/api/projects/1/segments/3/apply-voice/` with the chosen `voice_id` replaces the canonical audio file, updates `Segment.audio_file` in the database, and removes all temp compare files for that segment from disk.
5. Requesting a compare with a voice ID not in `VALID_VOICE_IDS` returns a 400 error listing the unrecognised voices.
6. Requesting a compare for a segment with no `text_content` returns a clear 400 error.
7. The Celery cleanup task runs every hour and deletes any `*_compare_*.wav` files that are older than 24 hours, with deletions logged at INFO level.
8. Requesting an apply for a voice whose temp file no longer exists (e.g., cleaned up) returns a 404 with a message instructing the user to re-run the compare.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- Test that `generate_tts_for_voices` raises `ValueError` when passed fewer than 2 or more than 5 voice IDs.
- Test that `generate_tts_for_voices` silently skips an invalid voice ID and returns results only for valid ones, including a log warning.
- Test that `generate_tts_for_voices` returns the correct number of result dictionaries when all voice IDs are valid.
- Test that each result dictionary contains the keys `voice_id`, `file_path`, and `duration`.
- Test the `CompareVoicesView` with a mock of `generate_tts_for_voices` to confirm correct HTTP status codes for valid and invalid inputs.
- Test the `ApplyVoiceView` to confirm it returns 404 when the temp file does not exist.
- Test the `ApplyVoiceView` to confirm it updates `Segment.audio_file` and removes temp files after a successful apply.
- Test the `cleanup_compare_files_task` by creating mock files with fabricated modification times and confirming only files older than 24 hours are removed.

### 5.2 Integration / Manual Tests

- Start the Django development server with Celery worker and Beat running.
- Create a project with at least one segment that has `text_content`.
- Call the compare endpoint with three valid voice IDs and confirm all three audio URLs are accessible in the browser.
- Play each audio URL and verify they are distinct voices narrating the same text.
- Call the apply endpoint with one of the voice IDs and verify the canonical audio file is updated on disk.
- Confirm the other two temp compare files are deleted after apply.
- Manually set one temp compare file's modification time to 25 hours in the past and wait for the Celery beat task to run, then confirm the file is deleted.
- Test the compare endpoint with a mix of valid and invalid voice IDs and confirm the 400 response lists the invalid ones.

### 5.3 Regression Tests

- Confirm that the existing `generate_audio` function in `tts_wrapper.py` still works correctly for standard single-voice TTS generation after adding the new helper.
- Confirm that the existing TTS generation endpoint (if present) still returns the correct response shape.
- Confirm that running the cleanup task does not delete any canonical audio files (those without `_compare_` in their names).
- Confirm that calling the apply endpoint twice in a row with the same voice ID does not cause an error even if the temp file was already deleted after the first call.

---

## 6. Notes for AI Agent

- The `generate_tts_for_voices` function must not call `generate_audio` in a way that could corrupt the canonical audio path — always use the `_compare_` infix in temp filenames to ensure the canonical filename pattern is never accidentally matched.
- The directory creation (`os.makedirs(exist_ok=True)`) must happen before calling `generate_audio` for each voice because the audio directory might not exist for new projects.
- When implementing the apply endpoint, prefer `shutil.copy2` over a file rename/move so that the temp file stays available as a fallback if the copy step fails midway.
- The apply endpoint should always clean up all temp compare files for the given segment, not just the unselected ones, to avoid accumulation over multiple compare sessions.
- The cleanup Celery task should be tolerant of directory structures that do not match the expected pattern — wrap the `os.walk` in a broad try/except to prevent one malformed directory from stopping the entire cleanup run.
- When building the `audio_url` in `CompareVoicesView`, be careful about double-slashing between `MEDIA_URL` and the relative path — strip trailing slashes from `MEDIA_URL` before concatenation and use `request.build_absolute_uri` to produce a fully qualified URL.
- The Celery Beat schedule entry should be added in `settings.py` rather than being hardcoded inside the task file to keep configuration centralised and to allow it to be overridden in test settings.
- Consider adding a maximum of 5 voice IDs per compare request as a safeguard against deliberate or accidental abuse that could saturate the TTS inference queue.
- If Celery Beat is not available in the deployment environment, document in a comment that the cleanup task can also be triggered manually via the Django management command interface as a future enhancement.
- The compare endpoint is intentionally synchronous and blocking on the first implementation — generating audio for up to 5 voices sequentially should complete within a few seconds since each voice's TTS inference on the existing Kokoro model is fast. If generation time becomes a concern, a follow-up improvement could move the compare operation into a Celery task and return a task ID to the frontend for polling, but do not implement that complexity upfront in this feature.
- Implement the compare endpoint with a `Content-Type: application/json` enforcement check. If the client sends a non-JSON body, return a 415 Unsupported Media Type rather than allowing Django REST Framework to produce an unclear parse error.
- The `generate_tts_for_voices` helper should accept an optional `speed` parameter that defaults to the project's stored `tts_speed`. This allows future callers to also test voices at different speeds in tandem, even if the frontend form for this feature version only exposes voice selection and not speed.
- In the apply endpoint, update the segment's `duration` field to match the duration of the newly applied audio file so that the project's total duration calculation remains consistent. Fetch the duration using `get_audio_duration` after the copy step.
- When registering the Celery Beat cleanup task schedule, use `timedelta(hours=1)` rather than a crontab expression unless there is a specific requirement for time-of-day execution. This makes the schedule portable across time zones and easier to read.
- The compare endpoint should return results in the same order as the `voice_ids` list provided in the request body — do not sort or reorder them. The user submitted them in a preferred order, and preserving that order makes the frontend A/B comparison layout predictable.
- The apply endpoint response should include the updated `Segment` serialised representation (or at minimum `segment_id`, `audio_file`, `voice_id`, and `duration`) so the frontend can update its local state from a single response without needing to re-fetch the segment.
- Guard against a race condition in the apply endpoint: if two apply requests for the same segment arrive concurrently (which could happen if the user double-clicks), use a database-level select-for-update or an application-level lock keyed on segment ID to ensure only one apply mutates the canonical file at a time.
- When logging deletions in `cleanup_compare_files_task`, log the relative path rather than the full absolute path to keep logs portable and environment-independent. The project-relative path is sufficient to identify which file was removed.
- Do not raise a 400 error if the `voice_ids` list includes duplicates — deduplicate them silently before processing. Generating two identical voice outputs would waste inference time and confuse the frontend comparison UI.

---

## 7. Future Enhancements

The following ideas are explicitly out of scope for this feature version but should be recorded here so future planning documents can reference them.

- **Async compare endpoint:** Move generation into a Celery task group and return a task ID immediately. The frontend polls for completion. Beneficial if the inference queue is shared and synchronous requests create timeout risk.
- **Per-segment voice persistence:** Once Feature 1.3 (per-segment voice ID) is implemented, the apply endpoint should write to `Segment.voice_id` in addition to `Segment.audio_file`. This feature is already written to be compatible — the conditional update block in Step 3.3 anticipates this.
- **Compare history:** Store the compare results (voice IDs tested and the one selected) in a lightweight audit log. Useful for analytics to understand which voices creators prefer across a large corpus of projects.
- **Speed pairing:** Allow the compare request to accept `{ voice_id, speed }` tuples instead of just voice IDs, so a single comparison session can evaluate voice-and-speed combinations simultaneously.
- **Frontend diff view:** Display a waveform visualisation alongside the audio player for each voice preview so creators can visually compare pace and intensity without listening to the full clip.
- **Default voice suggestion:** After the user applies a choice, prompt whether they want to propagate the selected voice to all segments in the project that still use the old default voice.
