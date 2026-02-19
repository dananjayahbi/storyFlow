# Task 01.02.08 — Create SegmentSerializer

## Metadata

| Field                    | Value                                                                                               |
| ------------------------ | --------------------------------------------------------------------------------------------------- |
| **Sub-Phase**            | SubPhase 01.02 — Database Models & Migrations                                                       |
| **Phase**                | Phase 01 — The Skeleton                                                                             |
| **Document Type**        | Layer 3 — Task Document                                                                             |
| **Estimated Complexity** | Low                                                                                                 |
| **Dependencies**         | [Task_01_02_02](Task_01_02_02_Create_Segment_Model.md), [Task_01_02_06](Task_01_02_06_Configure_DRF_Settings.md) |
| **Parent Document**      | [SubPhase_01_02_Overview.md](SubPhase_01_02_Overview.md) (Layer 2, §5.8)                            |

---

## Objective

Add the `SegmentSerializer` to `backend/api/serializers.py` for serializing all Segment model fields.

---

## Instructions

### Step 1: Add SegmentSerializer

Open `backend/api/serializers.py` and add the `Segment` import and serializer class:

```python
from .models import Project, Segment


class SegmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Segment
        fields = [
            'id', 'project', 'sequence_index', 'text_content',
            'image_prompt', 'image_file', 'audio_file',
            'audio_duration', 'is_locked',
        ]
        read_only_fields = ['id']
```

> Update the existing import line to include `Segment`. Place the `SegmentSerializer` class after `ProjectSerializer`.

---

## Expected Output

```
backend/api/serializers.py
├── from rest_framework import serializers
├── from .models import Project, Segment
├── class ProjectSerializer(...)        ← Task 01.02.07
└── class SegmentSerializer(...)        ← NEW
```

---

## Validation

- [ ] `Segment` is imported from `.models`.
- [ ] `SegmentSerializer` extends `serializers.ModelSerializer`.
- [ ] `fields` includes all 9 items: `id`, `project`, `sequence_index`, `text_content`, `image_prompt`, `image_file`, `audio_file`, `audio_duration`, `is_locked`.
- [ ] `read_only_fields` includes `id`.

---

## Notes

- This is a straightforward `ModelSerializer` with no computed fields. All fields map directly to database columns.
- The `project` field serializes as the Project's UUID. When creating a Segment via API, the client sends the project UUID to link the segment to its parent project.
- `SegmentSerializer` is also referenced by `ProjectDetailSerializer` (Task 01.02.10) for nested serialization.
- Must be defined BEFORE `ProjectDetailSerializer` since it references this class directly.

---

> **Parent:** [SubPhase_01_02_Overview.md](SubPhase_01_02_Overview.md) (Layer 2)
> **Previous Task:** [Task_01_02_07_Create_Project_Serializer.md](Task_01_02_07_Create_Project_Serializer.md)
> **Next Task:** [Task_01_02_09_Create_GlobalSettings_Serializer.md](Task_01_02_09_Create_GlobalSettings_Serializer.md)
