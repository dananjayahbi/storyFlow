# Task 03.02.07 — Update URL Routing

> **Sub-Phase:** 03.02 — Audio Generation API
> **Phase:** Phase 03 — The Voice
> **Complexity:** Low
> **Dependencies:** Task 03.02.03 (Generate Audio), Task 03.02.04 (Generate All), Task 03.02.05 (Task Status)
> **Parent Document:** [SubPhase_03_02_Overview.md](./SubPhase_03_02_Overview.md)

---

## Objective

Register the new task status endpoint URL pattern and verify that the DRF router automatically exposes the `generate-audio` and `generate-all-audio` ViewSet actions.

---

## Instructions

### Step 1 — Add the task status URL pattern

Import the `TaskStatusView` (or `task_status_view`) from `api.views` and add a manual `path()` entry in `backend/api/urls.py`. The pattern should be `api/tasks/<str:task_id>/status/` with a name of `task-status`. The `<str:task_id>` captures the task ID as a string.

### Step 2 — Verify ViewSet action routes

The `@action(detail=True, url_path='generate-audio')` on `SegmentViewSet` is automatically registered by the DRF router. When the router calls `router.register('segments', SegmentViewSet)`, it creates `POST /api/segments/{pk}/generate-audio/`. Similarly, `@action(detail=True, url_path='generate-all-audio')` on `ProjectViewSet` creates `POST /api/projects/{pk}/generate-all-audio/`. No manual URL entries are needed for these — just verify they work.

### Step 3 — Verify existing routes are unaffected

All Phase 01 and Phase 02 endpoints must continue to work: project CRUD, segment CRUD, image upload/remove, segment reorder. Run Django's URL pattern inspection or test with curl to confirm.

---

## Expected Output

```
backend/
└── api/
    └── urls.py                 ← MODIFIED (task status URL added)
```

---

## Validation

- [ ] `POST /api/segments/{id}/generate-audio/` is routable.
- [ ] `POST /api/projects/{id}/generate-all-audio/` is routable.
- [ ] `GET /api/tasks/{task_id}/status/` is routable.
- [ ] All existing endpoints from Phase 01–02 still function correctly.

---

## Notes

- Only the task status URL needs a manual `path()` entry — it's a standalone view, not a ViewSet action.
- The `@action` decorator's `url_path` parameter controls the URL suffix. Without it, DRF would use the method name (underscored), which is less readable.
- Task IDs are strings (not UUIDs), so use `<str:task_id>` in the URL pattern, not `<uuid:task_id>`.

---

> **Parent:** [SubPhase_03_02_Overview.md](./SubPhase_03_02_Overview.md) (Layer 2)
> **Phase:** [Phase_03_Overview.md](../Phase_03_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_03_02_06_Task_Progress_Tracking.md](./Task_03_02_06_Task_Progress_Tracking.md)
> **Next Task:** [Task_03_02_08_Update_Segment_Delete_Audio.md](./Task_03_02_08_Update_Segment_Delete_Audio.md)
