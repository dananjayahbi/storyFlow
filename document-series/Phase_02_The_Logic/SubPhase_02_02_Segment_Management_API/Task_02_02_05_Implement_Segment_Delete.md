# Task 02.02.05 — Implement Segment Delete

> **Sub-Phase:** 02.02 — Segment Management API
> **Phase:** Phase 02 — The Logic
> **Complexity:** Medium
> **Dependencies:** Task 02.02.01 (Segment ViewSet)
> **Parent Document:** [SubPhase_02_02_Overview.md](./SubPhase_02_02_Overview.md)

---

## Objective

Override `perform_destroy` on `SegmentViewSet` to clean up associated media files (images and audio) from disk before deleting the database record.

---

## Instructions

### Step 1 — Override `perform_destroy` on `SegmentViewSet`

```python
import os


def perform_destroy(self, instance):
    """Delete segment with media file cleanup."""
    # Delete image file from disk
    if instance.image_file:
        if os.path.isfile(instance.image_file.path):
            os.remove(instance.image_file.path)

    # Delete audio file from disk (future-proofing)
    if instance.audio_file:
        if os.path.isfile(instance.audio_file.path):
            os.remove(instance.audio_file.path)

    # Delete database record
    instance.delete()
```

### Step 2 — Key design decisions

| Decision | Rationale |
|---|---|
| No lock check on delete | Locked segments CAN be deleted — lock prevents content editing, not removal |
| Audio file cleanup included | Future-proofing for Phase 03, even though `audio_file` is always `None` in Phase 02 |
| `os.path.isfile()` guard | Prevents `FileNotFoundError` if file was manually deleted from disk |
| HTTP 204 response | DRF handles this automatically for `destroy` — no custom response needed |
| No `sequence_index` re-normalization | Remaining segments keep their indices; client calls reorder endpoint if needed |

---

## Expected Output

```
backend/
└── api/
    └── views.py            ← MODIFIED (perform_destroy added to SegmentViewSet)
```

---

## Validation

- [ ] `DELETE /api/segments/{id}/` removes the segment from the database (HTTP 204).
- [ ] Image file is deleted from disk when segment has an image.
- [ ] Audio file would be deleted from disk if present (future-proofing).
- [ ] Deleting a non-existent segment returns HTTP 404.
- [ ] Locked segments CAN be deleted (no lock check on destroy).
- [ ] `os.path.isfile()` is checked before `os.remove()`.

---

## Notes

- Always override `perform_destroy()`, not `destroy()` — this keeps DRF's response handling intact (HTTP 204 No Content).
- The `sequence_index` gap left by a deleted segment is intentional. The client should call `POST /api/segments/reorder/` if contiguous indices are required.

---

> **Parent:** [SubPhase_02_02_Overview.md](./SubPhase_02_02_Overview.md) (Layer 2)
> **Phase:** [Phase_02_Overview.md](../Phase_02_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_02_02_04_Implement_Image_Remove_Action.md](./Task_02_02_04_Implement_Image_Remove_Action.md)
> **Next Task:** [Task_02_02_06_Implement_Reorder_Endpoint.md](./Task_02_02_06_Implement_Reorder_Endpoint.md)
