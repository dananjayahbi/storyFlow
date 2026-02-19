# Task 02.02.02 — Implement Segment PATCH

> **Sub-Phase:** 02.02 — Segment Management API
> **Phase:** Phase 02 — The Logic
> **Complexity:** Medium
> **Dependencies:** Task 02.02.01 (Segment ViewSet)
> **Parent Document:** [SubPhase_02_02_Overview.md](./SubPhase_02_02_Overview.md)

---

## Objective

Implement the `partial_update` (PATCH) logic in `SegmentViewSet` with lock-awareness — allowing edits to `text_content`, `image_prompt`, and `is_locked`, while preventing content edits on locked segments.

---

## Instructions

### Step 1 — Override `perform_update` on `SegmentViewSet`

```python
from rest_framework.exceptions import ValidationError


def perform_update(self, serializer):
    instance = self.get_object()

    if instance.is_locked:
        # Allow ONLY the is_locked field to be updated (unlock operation)
        requested_fields = set(serializer.validated_data.keys())
        if requested_fields - {'is_locked'}:
            raise ValidationError({
                "error": "Cannot edit a locked segment. Unlock it first."
            })

    serializer.save()
```

### Step 2 — Restrict writable fields in `SegmentSerializer`

Ensure the existing `SegmentSerializer` (from Phase 01) marks non-editable fields as read-only:

```python
class SegmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Segment
        fields = '__all__'
        read_only_fields = [
            'id', 'project', 'sequence_index',
            'image_file', 'audio_file', 'audio_duration',
            'created_at', 'updated_at',
        ]
```

This ensures PATCH can only modify `text_content`, `image_prompt`, and `is_locked`.

### Step 3 — Lock behavior matrix

| Current `is_locked` | PATCH Fields | Result |
|---|---|---|
| `false` | `{"text_content": "new"}` | ✅ 200 — updated |
| `false` | `{"image_prompt": "new"}` | ✅ 200 — updated |
| `false` | `{"is_locked": true}` | ✅ 200 — locked |
| `true` | `{"is_locked": false}` | ✅ 200 — unlocked |
| `true` | `{"text_content": "new"}` | ❌ 400 — lock error |
| `true` | `{"text_content": "new", "is_locked": false}` | ❌ 400 — lock error (other fields present) |

---

## Expected Output

```
backend/
└── api/
    ├── views.py            ← MODIFIED (perform_update added to SegmentViewSet)
    └── serializers.py      ← MODIFIED (read_only_fields updated on SegmentSerializer)
```

---

## Validation

- [ ] `PATCH /api/segments/{id}/` updates `text_content` on an unlocked segment (200).
- [ ] `PATCH /api/segments/{id}/` updates `image_prompt` on an unlocked segment (200).
- [ ] `PATCH /api/segments/{id}/` sets `is_locked` to `true` (200).
- [ ] `PATCH /api/segments/{id}/` on a locked segment with `text_content` returns 400.
- [ ] `PATCH /api/segments/{id}/` with `{"is_locked": false}` on a locked segment succeeds (200).
- [ ] `sequence_index`, `image_file`, `audio_file`, `audio_duration` are not writable via PATCH.
- [ ] Response includes the full updated segment object.

---

## Notes

- DRF automatically uses `partial=True` for PATCH requests via `ModelViewSet`, so all fields are optional.
- The lock check must allow the unlock operation (`{"is_locked": false}`) even when the segment is locked — this is the ONLY way to unlock a segment.

---

> **Parent:** [SubPhase_02_02_Overview.md](./SubPhase_02_02_Overview.md) (Layer 2)
> **Phase:** [Phase_02_Overview.md](../Phase_02_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_02_02_01_Create_Segment_ViewSet.md](./Task_02_02_01_Create_Segment_ViewSet.md)
> **Next Task:** [Task_02_02_03_Implement_Image_Upload_Action.md](./Task_02_02_03_Implement_Image_Upload_Action.md)
