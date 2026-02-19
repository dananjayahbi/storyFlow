# Task 02.02.06 — Implement Reorder Endpoint

> **Sub-Phase:** 02.02 — Segment Management API
> **Phase:** Phase 02 — The Logic
> **Complexity:** Medium
> **Dependencies:** None (standalone endpoint)
> **Parent Document:** [SubPhase_02_02_Overview.md](./SubPhase_02_02_Overview.md)

---

## Objective

Create the `POST /api/segments/reorder/` standalone function-based view that atomically batch-updates `sequence_index` values for all segments in a project.

---

## Instructions

### Step 1 — Implement `reorder_segments` view in `backend/api/views.py`

```python
from django.db import transaction
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .models import Project, Segment


@api_view(['POST'])
def reorder_segments(request):
    """Atomically reorder all segments within a project.

    Request body:
        {
            "project_id": 1,
            "segment_order": [3, 1, 2]  // segment IDs in desired order
        }
    """
    project_id = request.data.get('project_id')
    segment_order = request.data.get('segment_order')

    # 1. Validate project_id
    if project_id is None:
        return Response(
            {'error': 'project_id is required'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        project = Project.objects.get(pk=project_id)
    except Project.DoesNotExist:
        return Response(
            {'error': 'Project not found'},
            status=status.HTTP_404_NOT_FOUND,
        )

    # 2. Validate segment_order
    if not isinstance(segment_order, list) or len(segment_order) == 0:
        return Response(
            {'error': 'segment_order must be a non-empty list of segment IDs'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # 3. Verify all IDs belong to the project
    actual_segments = Segment.objects.filter(project=project)
    actual_ids = set(actual_segments.values_list('id', flat=True))
    requested_ids = set(segment_order)

    if requested_ids != actual_ids:
        missing = actual_ids - requested_ids
        extra = requested_ids - actual_ids
        details = []
        if missing:
            details.append(f"Missing IDs: {sorted(missing)}")
        if extra:
            details.append(f"Invalid IDs: {sorted(extra)}")
        return Response(
            {'error': 'Invalid segment IDs', 'details': '; '.join(details)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # 4. Atomic batch update
    with transaction.atomic():
        segments_to_update = []
        for new_index, seg_id in enumerate(segment_order):
            seg = actual_segments.get(id=seg_id)
            seg.sequence_index = new_index
            segments_to_update.append(seg)
        Segment.objects.bulk_update(segments_to_update, ['sequence_index'])

    # 5. Return updated order
    return Response({
        'message': 'Segments reordered successfully',
        'segments': [
            {'id': seg.id, 'sequence_index': seg.sequence_index}
            for seg in segments_to_update
        ],
    }, status=status.HTTP_200_OK)
```

### Step 2 — Key design details

| Detail | Explanation |
|---|---|
| **Standalone view** | `@api_view(['POST'])`, NOT a ViewSet action — operates on multiple segments at once |
| **`@transaction.atomic`** | All-or-nothing update — partial failure rolls back all changes |
| **`bulk_update`** | Single DB query instead of N individual updates — O(1) vs O(n) |
| **ID completeness check** | `segment_order` must contain exactly the same IDs as the project's segments — no missing, no extras |
| **0-based indexing** | Position in `segment_order` array = new `sequence_index` value |

---

## Expected Output

```
backend/
└── api/
    └── views.py            ← MODIFIED (reorder_segments view added)
```

---

## Validation

- [ ] `POST /api/segments/reorder/` with valid data → 200, `sequence_index` values updated correctly.
- [ ] Response includes `{"message": "...", "segments": [{id, sequence_index}, ...]}`.
- [ ] Missing `project_id` → 400.
- [ ] Non-existent project → 404.
- [ ] Missing segment IDs in `segment_order` → 400 with details.
- [ ] Extra segment IDs (wrong project) → 400 with details.
- [ ] Reorder is atomic — partial failure leaves indices unchanged.
- [ ] `bulk_update` is used for efficiency.

---

## Notes

- This endpoint will be registered in `urls.py` in Task 02.02.08, placed BEFORE `include(router.urls)` to prevent the router from intercepting the path.
- The `segment_order` array contains integer segment IDs (Django's default auto-incrementing PK).

---

> **Parent:** [SubPhase_02_02_Overview.md](./SubPhase_02_02_Overview.md) (Layer 2)
> **Phase:** [Phase_02_Overview.md](../Phase_02_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_02_02_05_Implement_Segment_Delete.md](./Task_02_02_05_Implement_Segment_Delete.md)
> **Next Task:** [Task_02_02_07_Implement_Project_Delete.md](./Task_02_02_07_Implement_Project_Delete.md)
