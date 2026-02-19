# Task 02.02.07 — Implement Project Delete

> **Sub-Phase:** 02.02 — Segment Management API
> **Phase:** Phase 02 — The Logic
> **Complexity:** Medium
> **Dependencies:** None (extends existing ProjectViewSet)
> **Parent Document:** [SubPhase_02_02_Overview.md](./SubPhase_02_02_Overview.md)

---

## Objective

Add the `destroy` action to `ProjectViewSet` with a `perform_destroy()` override that deletes the project's entire media directory from disk before the database cascade delete removes all segment records.

---

## Instructions

### Step 1 — Override `perform_destroy` on `ProjectViewSet`

```python
import os
import shutil
from django.conf import settings


def perform_destroy(self, instance):
    """Delete project with full media directory cleanup.

    Order matters:
      1. Delete media directory (while segment records still exist for reference)
      2. Delete DB record (CASCADE removes all segments)
    """
    # 1. Build and remove media directory
    media_path = os.path.join(
        settings.MEDIA_ROOT, 'projects', str(instance.id)
    )
    if os.path.isdir(media_path):
        shutil.rmtree(media_path, ignore_errors=True)

    # 2. Delete database record (CASCADE handles segments)
    instance.delete()
```

### Step 2 — Enable `destroy` on `ProjectViewSet`

The Phase 01 `ProjectViewSet` restricted methods to `list`, `create`, `retrieve`. Add `delete` to the allowed methods:

```python
http_method_names = ['get', 'post', 'delete', 'head', 'options']
```

### Step 3 — Key execution order

```
DELETE /api/projects/{id}/
    │
    ├── 1. shutil.rmtree(media/projects/{id}/)
    │      └── Removes ALL images, audio files, subdirectories
    │
    └── 2. instance.delete()
           └── CASCADE removes all Segment DB records
```

**Why this order?** Once `instance.delete()` runs, the segment records (with their `image_file` paths) are gone from the database, making file cleanup impossible if done second.

### Step 4 — Key details

| Detail | Explanation |
|---|---|
| **`shutil.rmtree(path, ignore_errors=True)`** | Prevents failures if directory is partially deleted or has permission issues |
| **`os.path.isdir()` check** | Media directory may not exist if project has no uploaded files |
| **CASCADE delete** | Django's `on_delete=models.CASCADE` on Segment.project FK handles segment DB cleanup automatically |
| **HTTP 204 response** | DRF's `destroy` action returns 204 No Content automatically |

---

## Expected Output

```
backend/
└── api/
    └── views.py            ← MODIFIED (perform_destroy + http_method_names updated on ProjectViewSet)
```

---

## Validation

- [ ] `DELETE /api/projects/{id}/` removes the project from the database (HTTP 204).
- [ ] All associated segments are cascade-deleted from the database.
- [ ] The entire project media directory (`media/projects/{id}/`) is deleted from disk.
- [ ] Deleting a project with no media directory succeeds without errors.
- [ ] Deleting a non-existent project returns HTTP 404.
- [ ] Media directory is deleted BEFORE `instance.delete()` is called.

---

## Notes

- The `ProjectViewSet` from Phase 01 only had `list`, `create`, and `retrieve`. This task extends it with `destroy` without breaking existing functionality.
- `shutil.rmtree` with `ignore_errors=True` is a safety net — in production, a missing directory or permission issue should not crash the delete operation.

---

> **Parent:** [SubPhase_02_02_Overview.md](./SubPhase_02_02_Overview.md) (Layer 2)
> **Phase:** [Phase_02_Overview.md](../Phase_02_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_02_02_06_Implement_Reorder_Endpoint.md](./Task_02_02_06_Implement_Reorder_Endpoint.md)
> **Next Task:** [Task_02_02_08_Update_URL_Routing.md](./Task_02_02_08_Update_URL_Routing.md)
