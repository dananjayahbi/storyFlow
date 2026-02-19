# Task 03.02.12 — Task Cleanup & Memory Management

> **Sub-Phase:** 03.02 — Audio Generation API
> **Phase:** Phase 03 — The Voice
> **Complexity:** Medium
> **Dependencies:** Task 03.02.01 (TaskManager), Task 03.02.06 (Progress Tracking)
> **Parent Document:** [SubPhase_03_02_Overview.md](./SubPhase_03_02_Overview.md)

---

## Objective

Implement automatic cleanup of completed task records from the in-memory task registry to prevent memory growth during long sessions, while preserving active tasks and recently completed ones.

---

## Instructions

### Step 1 — Implement `_cleanup_old_tasks()`

Add a private method that iterates the `_tasks` dictionary and identifies completed or failed tasks whose `completed_at` timestamp is older than `_cleanup_threshold` (1 hour). Remove all matching entries from the dict. Log the count of cleaned-up tasks at the `info` level if any were removed. Acquire `_tasks_lock` for the entire operation.

### Step 2 — Trigger cleanup on task submission

Call `_cleanup_old_tasks()` from within `submit_task()`, piggyback-style. This means cleanup runs every time a new task is submitted, which is sufficient for a single-user app where tasks are submitted one at a time.

### Step 3 — Protect active tasks

Never clean up tasks in `PENDING` or `PROCESSING` states, regardless of age. Only tasks with a non-`None` `completed_at` timestamp AND an age exceeding the threshold are eligible for removal.

### Step 4 — Make the threshold configurable

Read the cleanup threshold from Django settings with a fallback: `getattr(settings, 'TASK_CLEANUP_THRESHOLD', 3600)`. This allows tests to use a short threshold for verifying cleanup behavior.

### Step 5 — Consider optional periodic cleanup (optional)

Piggybacking on `submit_task()` means cleanup only runs when new tasks are submitted. If the app is idle for hours after a batch generation, old records persist until the next submission. For StoryFlow's single-user context this is acceptable. Optionally, a daemon thread that runs `_cleanup_old_tasks()` every 10 minutes could be added, but this adds complexity for minimal benefit.

---

## Expected Output

```
backend/
└── api/
    └── tasks.py                ← MODIFIED (cleanup logic added)
```

---

## Validation

- [ ] Completed tasks older than 1 hour are removed from `_tasks`.
- [ ] Failed tasks older than 1 hour are removed from `_tasks`.
- [ ] `PENDING` and `PROCESSING` tasks are never removed regardless of age.
- [ ] Cleanup is triggered on each `submit_task()` call.
- [ ] Cleanup logs the count of removed tasks.
- [ ] The threshold is configurable via Django settings.
- [ ] No memory growth during extended sessions with many task submissions.

---

## Notes

- Without cleanup, each completed task record holds `completed_segments` data (arrays of segment IDs, URLs, and durations). A batch of 50 segments generates a task record of a few KB. Over hundreds of generations in a long session, this could grow to several MB — not critical, but worth managing.
- The 1-hour threshold is generous. In practice, the frontend stops polling within seconds of task completion. No one will request status for a task completed an hour ago.
- The `_tasks_lock` is held during the entire cleanup scan. For StoryFlow's small task registries (rarely more than 10–20 entries), this is instantaneous.
- Tests can override `TASK_CLEANUP_THRESHOLD` to a small value (e.g., 1 second) and use `time.sleep(2)` to verify cleanup behavior.

---

> **Parent:** [SubPhase_03_02_Overview.md](./SubPhase_03_02_Overview.md) (Layer 2)
> **Phase:** [Phase_03_Overview.md](../Phase_03_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_03_02_11_Write_API_Integration_Tests.md](./Task_03_02_11_Write_API_Integration_Tests.md)
> **Next Task:** N/A (final task of SubPhase 03.02)
