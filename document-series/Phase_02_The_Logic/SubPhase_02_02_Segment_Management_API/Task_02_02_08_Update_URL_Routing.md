# Task 02.02.08 — Update URL Routing

> **Sub-Phase:** 02.02 — Segment Management API
> **Phase:** Phase 02 — The Logic
> **Complexity:** Low
> **Dependencies:** Task 02.02.01 (Segment ViewSet), Task 02.02.06 (Reorder Endpoint)
> **Parent Document:** [SubPhase_02_02_Overview.md](./SubPhase_02_02_Overview.md)

---

## Objective

Register `SegmentViewSet` on the DRF router and add the `segments/reorder/` standalone route to `backend/api/urls.py`.

---

## Instructions

### Step 1 — Update `backend/api/urls.py`

```python
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'projects', views.ProjectViewSet)
router.register(r'segments', views.SegmentViewSet)

urlpatterns = [
    path('projects/import/', views.import_project, name='project-import'),
    path('segments/reorder/', views.reorder_segments, name='segment-reorder'),
    path('', include(router.urls)),
]
```

### Step 2 — Verify route ordering

Standalone routes (`projects/import/`, `segments/reorder/`) **MUST** come before `include(router.urls)` to prevent the router from intercepting them as resource IDs.

### Step 3 — Verify auto-generated routes

The DRF router automatically generates these routes for `SegmentViewSet`:

| Method | URL | Action |
|---|---|---|
| `GET` | `/api/segments/` | list |
| `GET` | `/api/segments/{id}/` | retrieve |
| `PATCH` | `/api/segments/{id}/` | partial_update |
| `DELETE` | `/api/segments/{id}/` | destroy |
| `POST` | `/api/segments/{id}/upload-image/` | upload_image (custom action) |
| `DELETE` | `/api/segments/{id}/remove-image/` | remove_image (custom action) |

All routes include trailing slashes. All custom `@action` routes are auto-discovered by the router.

---

## Expected Output

```
backend/
└── api/
    └── urls.py             ← MODIFIED
```

---

## Validation

- [ ] `SegmentViewSet` is accessible at `/api/segments/` and `/api/segments/{id}/`.
- [ ] Custom actions accessible at `/api/segments/{id}/upload-image/` and `/api/segments/{id}/remove-image/`.
- [ ] Reorder endpoint accessible at `/api/segments/reorder/`.
- [ ] Import endpoint still works at `/api/projects/import/`.
- [ ] Project CRUD still works at `/api/projects/` and `/api/projects/{id}/`.
- [ ] All routes include trailing slashes.
- [ ] Standalone routes are BEFORE `include(router.urls)`.

---

## Notes

- No new standalone routes are needed for `upload-image` or `remove-image` — the DRF router auto-generates them from `@action` decorators on `SegmentViewSet`.

---

> **Parent:** [SubPhase_02_02_Overview.md](./SubPhase_02_02_Overview.md) (Layer 2)
> **Phase:** [Phase_02_Overview.md](../Phase_02_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_02_02_07_Implement_Project_Delete.md](./Task_02_02_07_Implement_Project_Delete.md)
> **Next Task:** [Task_02_02_09_Update_Frontend_API_Client.md](./Task_02_02_09_Update_Frontend_API_Client.md)
