# Task 02.02.01 — Create Segment ViewSet

> **Sub-Phase:** 02.02 — Segment Management API
> **Phase:** Phase 02 — The Logic
> **Complexity:** Medium
> **Dependencies:** None
> **Parent Document:** [SubPhase_02_02_Overview.md](./SubPhase_02_02_Overview.md)

---

## Objective

Create the `SegmentViewSet` class in `backend/api/views.py` as a DRF `ModelViewSet` with restricted HTTP methods and project-based filtering. This is the foundation for all segment CRUD operations.

---

## Instructions

### Step 1 — Add imports to `backend/api/views.py`

```python
from .models import Segment
from .serializers import SegmentSerializer
```

### Step 2 — Define `SegmentViewSet`

```python
class SegmentViewSet(viewsets.ModelViewSet):
    """ViewSet for segment CRUD operations.

    Segments are created exclusively via the import endpoint.
    This ViewSet provides list, retrieve, partial_update, and destroy.
    """
    queryset = Segment.objects.all()
    serializer_class = SegmentSerializer

    # No create (POST) — segments are created via import only
    http_method_names = ['get', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        queryset = Segment.objects.all()
        project_id = self.request.query_params.get('project')
        if project_id is not None:
            queryset = queryset.filter(project_id=project_id)
        elif self.action == 'list':
            return Segment.objects.none()  # Require project filter for list
        return queryset
```

### Step 3 — Key design rules

| Rule | Detail |
|---|---|
| No `create` action | Segments are only created via `POST /api/projects/import/` (SubPhase 02.01) |
| Restricted HTTP methods | `GET`, `PATCH`, `DELETE` only — no `POST` or `PUT` |
| Project filtering on `list` | `?project={id}` query param filters segments; without it, list returns empty |
| `retrieve` without filter | Individual segment lookup by ID works without the `project` query param |
| Ordering | `sequence_index` ascending (via model `Meta.ordering = ['sequence_index']`) |

---

## Expected Output

```
backend/
└── api/
    └── views.py            ← MODIFIED (SegmentViewSet added)
```

---

## Validation

- [ ] `SegmentViewSet` exists in `backend/api/views.py`.
- [ ] `http_method_names` restricts to `GET`, `PATCH`, `DELETE`, `HEAD`, `OPTIONS`.
- [ ] `GET /api/segments/?project={id}` returns segments filtered by project, ordered by `sequence_index`.
- [ ] `GET /api/segments/` (no filter) returns empty list.
- [ ] `GET /api/segments/{id}/` retrieves a single segment by ID.
- [ ] `POST /api/segments/` returns 405 Method Not Allowed.

---

## Notes

- This task creates the base ViewSet shell. The `perform_update` (lock logic), `perform_destroy` (cleanup), and custom actions (upload/remove image) are added in subsequent tasks.
- The ViewSet will be registered on the DRF router in Task 02.02.08.

---

> **Parent:** [SubPhase_02_02_Overview.md](./SubPhase_02_02_Overview.md) (Layer 2)
> **Phase:** [Phase_02_Overview.md](../Phase_02_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** — (first task in SubPhase 02.02)
> **Next Task:** [Task_02_02_02_Implement_Segment_PATCH.md](./Task_02_02_02_Implement_Segment_PATCH.md)
