# Task 02.02.04 — Implement Image Remove Action

> **Sub-Phase:** 02.02 — Segment Management API
> **Phase:** Phase 02 — The Logic
> **Complexity:** Low
> **Dependencies:** Task 02.02.01 (Segment ViewSet)
> **Parent Document:** [SubPhase_02_02_Overview.md](./SubPhase_02_02_Overview.md)

---

## Objective

Add the `remove-image` custom action to `SegmentViewSet` that deletes the image file from disk and clears the model field.

---

## Instructions

### Step 1 — Add `remove_image` action to `SegmentViewSet`

```python
@action(detail=True, methods=['delete'], url_path='remove-image')
def remove_image(self, request, pk=None):
    segment = self.get_object()

    # 1. Lock check
    if segment.is_locked:
        return Response(
            {'error': 'Cannot modify a locked segment.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # 2. Check image exists
    if not segment.image_file:
        return Response(
            {'error': 'No image to remove'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # 3. Delete file from disk (self-healing if already missing)
    try:
        if os.path.isfile(segment.image_file.path):
            os.remove(segment.image_file.path)
    except FileNotFoundError:
        pass  # File already gone — clear field anyway

    # 4. Clear model field
    segment.image_file = None
    segment.save()

    return Response({
        'id': segment.id,
        'image_file': None,
        'message': 'Image removed successfully',
    }, status=status.HTTP_200_OK)
```

### Step 2 — Key behavior

| Scenario | Result |
|---|---|
| Segment has an image, file exists on disk | File deleted, field cleared, 200 |
| Segment has an image, file missing from disk | Field cleared anyway (self-healing), 200 |
| Segment has no image (`image_file` is None) | 400: "No image to remove" |
| Segment is locked | 400: "Cannot modify a locked segment." |

---

## Expected Output

```
backend/
└── api/
    └── views.py            ← MODIFIED (remove_image action added to SegmentViewSet)
```

---

## Validation

- [ ] `DELETE /api/segments/{id}/remove-image/` on segment with image → 200, file deleted, field set to null.
- [ ] On segment without image → 400: "No image to remove".
- [ ] On locked segment → 400: "Cannot modify a locked segment."
- [ ] If file is already missing from disk but `image_file` field is set → field is cleared (self-healing).
- [ ] Response includes `{"id": ..., "image_file": null, "message": "Image removed successfully"}`.

---

## Notes

- The `try/except FileNotFoundError` provides self-healing — if a file was manually deleted from disk, the model field is still cleared to maintain consistency.
- The DRF router auto-generates the `DELETE /api/segments/{pk}/remove-image/` route from the `@action` decorator.

---

> **Parent:** [SubPhase_02_02_Overview.md](./SubPhase_02_02_Overview.md) (Layer 2)
> **Phase:** [Phase_02_Overview.md](../Phase_02_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_02_02_03_Implement_Image_Upload_Action.md](./Task_02_02_03_Implement_Image_Upload_Action.md)
> **Next Task:** [Task_02_02_05_Implement_Segment_Delete.md](./Task_02_02_05_Implement_Segment_Delete.md)
