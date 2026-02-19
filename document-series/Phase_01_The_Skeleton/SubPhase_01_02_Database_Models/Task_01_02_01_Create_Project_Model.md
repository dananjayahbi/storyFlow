# Task 01.02.01 — Define Project Model

## Metadata

| Field                    | Value                                                                   |
| ------------------------ | ----------------------------------------------------------------------- |
| **Sub-Phase**            | SubPhase 01.02 — Database Models & Migrations                           |
| **Phase**                | Phase 01 — The Skeleton                                                 |
| **Document Type**        | Layer 3 — Task Document                                                 |
| **Estimated Complexity** | Medium                                                                  |
| **Dependencies**         | SubPhase 01.01 complete (Django project and `api` app exist)            |
| **Parent Document**      | [SubPhase_01_02_Overview.md](SubPhase_01_02_Overview.md) (Layer 2, §5.1)|

---

## Objective

Define the `Project` model in `api/models.py` with all fields, status choices, metadata, and the `__str__` method as specified in the architecture documents.

---

## Instructions

### Step 1: Add UUID Import

Open `backend/api/models.py` and add the `uuid` import at the top:

```python
import uuid
from django.db import models
```

---

### Step 2: Define Status Choices

Add the `STATUS_CHOICES` constant at the module level (before the model class):

```python
STATUS_CHOICES = [
    ('DRAFT', 'Draft'),
    ('PROCESSING', 'Processing'),
    ('COMPLETED', 'Completed'),
    ('FAILED', 'Failed'),
]
```

---

### Step 3: Define the Project Model

```python
class Project(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    resolution_width = models.IntegerField(default=1920)
    resolution_height = models.IntegerField(default=1080)
    framerate = models.IntegerField(default=30)
    output_path = models.CharField(max_length=500, blank=True, null=True)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['-created_at']
```

---

## Expected Output

After this task, `backend/api/models.py` contains:

```
backend/api/models.py
├── import uuid
├── from django.db import models
├── STATUS_CHOICES (module-level constant)
└── class Project(models.Model)
    ├── 9 fields (id, title, created_at, updated_at, status, resolution_width, resolution_height, framerate, output_path)
    ├── __str__ → self.title
    └── Meta.ordering = ['-created_at']
```

---

## Validation

- [ ] `import uuid` is present at the top of the file.
- [ ] `STATUS_CHOICES` has exactly 4 entries: DRAFT, PROCESSING, COMPLETED, FAILED.
- [ ] `id` field uses `UUIDField` with `primary_key=True`, `default=uuid.uuid4` (no parentheses), `editable=False`.
- [ ] `created_at` uses `auto_now_add=True`; `updated_at` uses `auto_now=True`.
- [ ] `status` uses `choices=STATUS_CHOICES` and `default='DRAFT'`.
- [ ] `output_path` has `blank=True, null=True`.
- [ ] `__str__` returns `self.title`.
- [ ] `Meta.ordering` is `['-created_at']` (descending — newest first).

---

## Notes

- **Critical:** `default=uuid.uuid4` must NOT have parentheses. With parentheses (`uuid.uuid4()`), the UUID is evaluated once at class definition time and every instance would receive the same UUID.
- Do NOT run `makemigrations` yet — all three models should be defined before generating migrations (Task 01.02.04).
- `STATUS_CHOICES` is defined as a module-level constant rather than inside the class. This is a style preference that keeps it accessible for imports elsewhere if needed.

---

> **Parent:** [SubPhase_01_02_Overview.md](SubPhase_01_02_Overview.md) (Layer 2)
> **Phase:** [Phase_01_Overview.md](../../Phase_01_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../../00_Project_Overview.md) (Layer 0)
> **Next Task:** [Task_01_02_02_Create_Segment_Model.md](Task_01_02_02_Create_Segment_Model.md)
