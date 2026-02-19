# Task 03.02.05 — Build Task Status Endpoint

> **Sub-Phase:** 03.02 — Audio Generation API
> **Phase:** Phase 03 — The Voice
> **Complexity:** Medium
> **Dependencies:** Task 03.02.01 (TaskManager)
> **Parent Document:** [SubPhase_03_02_Overview.md](./SubPhase_03_02_Overview.md)

---

## Objective

Implement the `GET /api/tasks/{task_id}/status/` standalone DRF view that returns real-time progress of background TTS tasks, enabling the frontend to poll for status updates.

---

## Instructions

### Step 1 — Choose view type

Implement as either a class-based `APIView` or a function-based view using `@api_view(['GET'])`. Both approaches are acceptable. A class-based view provides cleaner structure; a function-based view is simpler for a single-method endpoint.

### Step 2 — Implement the GET handler

Accept `task_id` as a URL parameter (string, not UUID). Call `get_task_manager().get_task_status(task_id)`. If the result is `None`, return HTTP 404 with `{"error": "Task not found"}`.

### Step 3 — Build the response

Return HTTP 200 with a JSON body containing: `task_id`, `status` (one of PENDING, PROCESSING, COMPLETED, FAILED), `progress` (the progress sub-dict with current, total, percentage, and optional current_segment_id), `completed_segments` (array of completed segment audio details), and `errors` (array of per-segment error entries).

### Step 4 — Ensure thread safety of response data

The `get_task_status()` method returns a copy of the task state dict. This prevents the response serialization from racing with background thread mutations. The returned data is a snapshot — it may be slightly stale, which is acceptable for a polling-based UI.

---

## Expected Output

```
backend/
└── api/
    └── views.py                ← MODIFIED (TaskStatusView or task_status_view added)
```

---

## Validation

- [ ] `GET /api/tasks/{task_id}/status/` returns 200 with all expected fields.
- [ ] Unknown `task_id` returns 404.
- [ ] Status field reflects the current task state accurately.
- [ ] Progress field includes `current`, `total`, `percentage`.
- [ ] `completed_segments` array grows as segments are processed.
- [ ] `errors` array captures per-segment failures.
- [ ] Response is always valid JSON via DRF's `Response`.

---

## Notes

- This is a standalone view, NOT part of any ViewSet. It needs a manual URL pattern entry (see Task 03.02.07).
- No authentication is required — StoryFlow has no auth.
- The `percentage` is an integer (0–100), not a float, for UI simplicity.
- The frontend polls this endpoint at 2-second intervals (see Task 03.02.09's `pollTaskStatus`). The endpoint should be lightweight — just a dict lookup, no database queries.

---

> **Parent:** [SubPhase_03_02_Overview.md](./SubPhase_03_02_Overview.md) (Layer 2)
> **Phase:** [Phase_03_Overview.md](../Phase_03_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_03_02_04_Build_Generate_All_Audio_Endpoint.md](./Task_03_02_04_Build_Generate_All_Audio_Endpoint.md)
> **Next Task:** [Task_03_02_06_Task_Progress_Tracking.md](./Task_03_02_06_Task_Progress_Tracking.md)
