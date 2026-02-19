# Task 01.02.10 — Create ProjectDetailSerializer

## Metadata

| Field                    | Value                                                                                                     |
| ------------------------ | --------------------------------------------------------------------------------------------------------- |
| **Sub-Phase**            | SubPhase 01.02 — Database Models & Migrations                                                             |
| **Phase**                | Phase 01 — The Skeleton                                                                                   |
| **Document Type**        | Layer 3 — Task Document                                                                                   |
| **Estimated Complexity** | Low                                                                                                       |
| **Dependencies**         | [Task_01_02_07](Task_01_02_07_Create_Project_Serializer.md), [Task_01_02_08](Task_01_02_08_Create_Segment_Serializer.md) |
| **Parent Document**      | [SubPhase_01_02_Overview.md](SubPhase_01_02_Overview.md) (Layer 2, §5.10)                                 |

---

## Objective

Add the nested `ProjectDetailSerializer` to `backend/api/serializers.py` that includes full project data plus an embedded array of its segments.

---

## Instructions

### Step 1: Add ProjectDetailSerializer

Open `backend/api/serializers.py` and add the following class **after** `SegmentSerializer` (it references `SegmentSerializer` directly):

```python
class ProjectDetailSerializer(serializers.ModelSerializer):
    segments = SegmentSerializer(many=True, read_only=True)

    class Meta:
        model = Project
        fields = [
            'id', 'title', 'created_at', 'updated_at',
            'status', 'resolution_width', 'resolution_height',
            'framerate', 'output_path', 'segments',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
```

---

## Expected Output

```
backend/api/serializers.py
├── from rest_framework import serializers
├── from .models import Project, Segment, GlobalSettings
├── class ProjectSerializer(...)              ← Task 01.02.07
├── class SegmentSerializer(...)              ← Task 01.02.08
├── class GlobalSettingsSerializer(...)       ← Task 01.02.09
└── class ProjectDetailSerializer(...)        ← NEW
```

The complete `serializers.py` file now contains **4 serializer classes**.

---

## Validation

- [ ] `ProjectDetailSerializer` extends `serializers.ModelSerializer`.
- [ ] `segments` field is `SegmentSerializer(many=True, read_only=True)`.
- [ ] `fields` includes 10 items: `id`, `title`, `created_at`, `updated_at`, `status`, `resolution_width`, `resolution_height`, `framerate`, `output_path`, `segments`.
- [ ] `output_path` is included (not present in `ProjectSerializer` list view).
- [ ] `segment_count` is NOT included (the nested `segments` array makes it redundant).
- [ ] `read_only_fields` includes `id`, `created_at`, `updated_at`.
- [ ] `ProjectDetailSerializer` is defined AFTER `SegmentSerializer` in the file.

---

## Notes

- **Differences from `ProjectSerializer`:** This serializer includes `output_path` and the nested `segments` array, but omits `segment_count` (redundant when segments are inline). It is used for the **detail view** (`GET /api/projects/{id}/`).
- **Nested segments are read-only.** Segments are created/updated/deleted through their own endpoint, not through the project detail endpoint.
- **Ordering:** Segments in the response are ordered by `sequence_index` (ascending), enforced by the Segment model's `Meta.ordering`.
- **`status` is NOT in `read_only_fields` here** (unlike `ProjectSerializer`). This is intentional — the detail view may need to update status in certain business logic flows in later phases.

---

> **Parent:** [SubPhase_01_02_Overview.md](SubPhase_01_02_Overview.md) (Layer 2)
> **Previous Task:** [Task_01_02_09_Create_GlobalSettings_Serializer.md](Task_01_02_09_Create_GlobalSettings_Serializer.md)
> **Next Task:** [Task_01_02_11_Create_Superuser.md](Task_01_02_11_Create_Superuser.md)
