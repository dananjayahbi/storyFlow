# Task 03.02.06 — Task Progress Tracking

> **Sub-Phase:** 03.02 — Audio Generation API
> **Phase:** Phase 03 — The Voice
> **Complexity:** Medium
> **Dependencies:** Task 03.02.01 (TaskManager), Task 03.02.02 (ThreadPool)
> **Parent Document:** [SubPhase_03_02_Overview.md](./SubPhase_03_02_Overview.md)

---

## Objective

Verify and harden the progress tracking mechanism in `TaskManager` so that both single-segment and batch tasks report accurate, thread-safe progress information to the polling frontend.

---

## Instructions

### Step 1 — Verify `update_task_progress()` behavior

Ensure the method correctly sets `progress.current`, `progress.total`, and computes `progress.percentage` as `int((current / total) * 100)` when `total > 0`. The method must accept arbitrary `**kwargs` (e.g., `current_segment_id`) and merge them into the progress dict.

### Step 2 — Handle the zero-total edge case

If `total` is 0, set `percentage` to 0 — not a division-by-zero error. This can occur if the batch endpoint filters out all segments but still creates a task (an unlikely but possible race condition).

### Step 3 — Verify `add_completed_segment()` accumulation

Each call should append a new entry to the `completed_segments` list with `segment_id` (as a string), `audio_url` (from the TTS result), and `duration` (float). The list grows as segments complete. Verify that entries are never overwritten or lost.

### Step 4 — Verify `add_error()` accumulation

Each call should append a new entry to the `errors` list with `segment_id` (as a string) and `error` (the error message string). Errors for individual segments are recorded without stopping the batch.

### Step 5 — Single-segment task progress

For a single-segment task, progress is straightforward: the task does not call `update_task_progress()` during execution (there is only one segment). The status transitions directly from `PENDING` to `PROCESSING` to `COMPLETED`. The `progress` remains at the initial values. One `completed_segments` entry or one `errors` entry is added at the end.

### Step 6 — Batch task progress interaction

For batch tasks, progress updates happen inside the loop (before processing each segment). The background thread calls `update_task_progress(task_id, current=i+1, total=N, current_segment_id=str(seg_id))`. Meanwhile, the API thread may call `get_task_status(task_id)` concurrently. The `_tasks_lock` ensures these don't race.

### Step 7 — Handle calls for non-existent tasks

If `update_task_progress()`, `add_completed_segment()`, or `add_error()` is called with a `task_id` that doesn't exist in `_tasks` (e.g., it was cleaned up), the method should silently ignore the call — no exception, no log warning.

---

## Expected Output

```
backend/
└── api/
    └── tasks.py                ← MODIFIED (progress tracking hardened)
```

---

## Validation

- [ ] `update_task_progress(task_id, current=5, total=10)` sets percentage to 50.
- [ ] `update_task_progress(task_id, current=0, total=0)` sets percentage to 0 (no crash).
- [ ] `add_completed_segment()` appends entries (does not overwrite).
- [ ] `add_error()` appends entries (does not overwrite).
- [ ] Calling any mutation method with an unknown task ID silently does nothing.
- [ ] All mutation methods acquire `_tasks_lock` before modifying `_tasks`.
- [ ] `get_task_status()` returns a snapshot that includes up-to-date progress.

---

## Notes

- Thread safety is the primary concern. The background thread writes progress while the API request thread reads it. The `_tasks_lock` is a simple mutex — it's sufficient for StoryFlow's low concurrency.
- The progress percentage is always an integer, not a float, for UI simplicity.
- The `current_segment_id` kwarg in the progress dict tells the frontend which segment is currently being processed, enabling a "currently generating: Segment 3" indicator.
- This task is largely about verification and edge-case handling rather than new feature development. The core methods were defined in Task 03.02.01; this task ensures they work correctly under all conditions.

---

> **Parent:** [SubPhase_03_02_Overview.md](./SubPhase_03_02_Overview.md) (Layer 2)
> **Phase:** [Phase_03_Overview.md](../Phase_03_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_03_02_05_Build_Task_Status_Endpoint.md](./Task_03_02_05_Build_Task_Status_Endpoint.md)
> **Next Task:** [Task_03_02_07_Update_URL_Routing.md](./Task_03_02_07_Update_URL_Routing.md)
