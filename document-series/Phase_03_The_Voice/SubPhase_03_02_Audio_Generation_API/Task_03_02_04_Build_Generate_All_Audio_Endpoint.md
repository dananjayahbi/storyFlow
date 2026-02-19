# Task 03.02.04 — Build Generate All Audio Endpoint

> **Sub-Phase:** 03.02 — Audio Generation API
> **Phase:** Phase 03 — The Voice
> **Complexity:** High
> **Dependencies:** Task 03.02.01 (TaskManager), Task 03.02.02 (ThreadPool), Task 03.02.03 (Single Generate)
> **Parent Document:** [SubPhase_03_02_Overview.md](./SubPhase_03_02_Overview.md)

---

## Objective

Implement the `POST /api/projects/{id}/generate-all-audio/` DRF action on `ProjectViewSet` that triggers sequential TTS generation for all eligible segments in a project, with filtering, progress tracking, and per-segment error handling.

---

## Instructions

### Step 1 — Add the `generate_all_audio` action

Add a `@action(detail=True, methods=['post'], url_path='generate-all-audio')` method to `ProjectViewSet`. Use `self.get_object()` to fetch the project.

### Step 2 — Parse request options

Read `skip_locked` (default `True`) and `force_regenerate` (default `False`) from `request.data`. These control which segments are included.

### Step 3 — Fetch and filter segments

Query all segments for the project ordered by `sequence_index`. Iterate and apply filters: skip locked segments if `skip_locked` is true, skip segments with existing `audio_file` if `force_regenerate` is false, and skip segments with empty `text_content`. Build a list of segments to process and track skip counts.

### Step 4 — Handle empty processing list

If no segments remain after filtering, return HTTP 200 (not 202) with a message "No segments to process", the total segment count, and `segments_to_process: 0`.

### Step 5 — Check TTS model availability

Call `KokoroModelLoader.is_model_available()`. Return 503 if unavailable — same as the single-segment endpoint.

### Step 6 — Read GlobalSettings and capture values

Fetch the `GlobalSettings` singleton. Capture `voice_id` and `speed` as local variables. Critically, capture segment IDs as a plain list (not ORM objects) for thread safety — Django ORM objects are bound to database connections that are NOT thread-safe across threads.

### Step 7 — Define the batch task function

Create a closure `batch_task_fn()` that re-imports `generate_audio`, `construct_audio_path`, `construct_audio_url` from `core_engine.tts_wrapper` and `Segment` from the models module (fresh imports inside the thread context). Loop through the captured segment IDs. On each iteration: check cancellation via `task_manager.is_cancelled(task_id)` and break if true, update progress via `task_manager.update_task_progress()`, re-fetch the segment by ID, call `generate_audio()`, update the segment's `audio_file` and `audio_duration` on success, or record the error via `task_manager.add_error()` on failure. Wrap each segment in its own try/except so individual failures don't stop the batch.

### Step 8 — Submit and return 202

Generate a task ID in the format `tts_batch_{project_id}_{uuid_hex_8chars}`. Submit the batch function. Return HTTP 202 with `task_id`, `project_id`, `status: "PENDING"`, `total_segments`, `segments_to_process`, and a descriptive message including skip counts.

---

## Expected Output

```
backend/
└── api/
    └── views.py                ← MODIFIED (generate_all_audio action added to ProjectViewSet)
```

---

## Validation

- [ ] `POST /api/projects/{id}/generate-all-audio/` returns 202 with counts.
- [ ] Locked segments are skipped when `skip_locked` is true.
- [ ] Segments with existing audio are skipped when `force_regenerate` is false.
- [ ] Empty-text segments are always skipped.
- [ ] No segments to process returns 200 (not 202).
- [ ] Missing model returns 503.
- [ ] Non-existent project returns 404.
- [ ] Progress updates after each segment.
- [ ] Individual segment errors don't stop the batch.
- [ ] Cancellation check runs between segments.

---

## Notes

- **Thread safety is the most important concern in this task.** Do NOT pass Django ORM querysets or model instances to the background thread. Pass IDs and re-fetch them inside the thread with fresh database queries.
- Segments are processed sequentially (one at a time) by design — TTS is CPU/GPU-intensive.
- The batch task status shows `COMPLETED` (not `FAILED`) even if some segments errored. The task is `FAILED` only if the entire batch function crashes with an unhandled exception outside the per-segment loop.
- Progress is updated BEFORE processing each segment, so the UI shows "processing 3/10" while segment 3 is being generated.
- The `skip_locked` behavior differs from the single-segment endpoint: single returns 409, bulk silently skips. This is by design — bulk is a convenience operation.

---

> **Parent:** [SubPhase_03_02_Overview.md](./SubPhase_03_02_Overview.md) (Layer 2)
> **Phase:** [Phase_03_Overview.md](../Phase_03_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_03_02_03_Build_Generate_Audio_Endpoint.md](./Task_03_02_03_Build_Generate_Audio_Endpoint.md)
> **Next Task:** [Task_03_02_05_Build_Task_Status_Endpoint.md](./Task_03_02_05_Build_Task_Status_Endpoint.md)
