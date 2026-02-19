# Task 01.02.07 — Create ProjectSerializer

## Metadata

| Field                    | Value                                                                                               |
| ------------------------ | --------------------------------------------------------------------------------------------------- |
| **Sub-Phase**            | SubPhase 01.02 — Database Models & Migrations                                                       |
| **Phase**                | Phase 01 — The Skeleton                                                                             |
| **Document Type**        | Layer 3 — Task Document                                                                             |
| **Estimated Complexity** | Low                                                                                                 |
| **Dependencies**         | [Task_01_02_01](Task_01_02_01_Create_Project_Model.md), [Task_01_02_06](Task_01_02_06_Configure_DRF_Settings.md) |
| **Parent Document**      | [SubPhase_01_02_Overview.md](SubPhase_01_02_Overview.md) (Layer 2, §5.7)                            |

---

## Objective

Create `backend/api/serializers.py` and implement the `ProjectSerializer` with a computed `segment_count` field for the project list view.

---

## Instructions

### Step 1: Create `serializers.py`

Create a new file at `backend/api/serializers.py`:

```python
from rest_framework import serializers
from .models import Project


class ProjectSerializer(serializers.ModelSerializer):
    segment_count = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            'id', 'title', 'created_at', 'updated_at',
            'status', 'resolution_width', 'resolution_height',
            'framerate', 'segment_count',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'status']

    def get_segment_count(self, obj):
        return obj.segments.count()
```

---

## Expected Output

```
backend/api/
├── serializers.py    ← NEW
├── models.py
├── admin.py
└── ...
```

---

## Validation

- [ ] `backend/api/serializers.py` exists.
- [ ] `ProjectSerializer` extends `serializers.ModelSerializer`.
- [ ] `segment_count` is declared as `SerializerMethodField()`.
- [ ] `fields` list includes all 9 items: `id`, `title`, `created_at`, `updated_at`, `status`, `resolution_width`, `resolution_height`, `framerate`, `segment_count`.
- [ ] `read_only_fields` includes `id`, `created_at`, `updated_at`, `status`.
- [ ] `get_segment_count` calls `obj.segments.count()`.

---

## Notes

- `segment_count` is a computed field — NOT a database column. It's calculated via `obj.segments.count()` which relies on `related_name='segments'` from the Segment model's ForeignKey.
- On `POST /api/projects/`, only `title` is required. All other fields use defaults. `status` is read-only in the serializer — status transitions happen through business logic in later phases, not direct API updates.
- This serializer is used for the **list view** (`GET /api/projects/`). The **detail view** uses `ProjectDetailSerializer` (Task 01.02.10) which includes nested segments.
- Additional serializers (Segment, GlobalSettings, ProjectDetail) will be added to this same file in subsequent tasks.

---

> **Parent:** [SubPhase_01_02_Overview.md](SubPhase_01_02_Overview.md) (Layer 2)
> **Previous Task:** [Task_01_02_06_Configure_DRF_Settings.md](Task_01_02_06_Configure_DRF_Settings.md)
> **Next Task:** [Task_01_02_08_Create_Segment_Serializer.md](Task_01_02_08_Create_Segment_Serializer.md)
