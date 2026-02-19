# Task 01.02.02 — Define Segment Model

## Metadata

| Field                    | Value                                                                          |
| ------------------------ | ------------------------------------------------------------------------------ |
| **Sub-Phase**            | SubPhase 01.02 — Database Models & Migrations                                  |
| **Phase**                | Phase 01 — The Skeleton                                                        |
| **Document Type**        | Layer 3 — Task Document                                                        |
| **Estimated Complexity** | Medium                                                                         |
| **Dependencies**         | [Task_01_02_01](Task_01_02_01_Create_Project_Model.md) — Project model must be defined |
| **Parent Document**      | [SubPhase_01_02_Overview.md](SubPhase_01_02_Overview.md) (Layer 2, §5.2)       |

---

## Objective

Define the `Segment` model in `api/models.py` with the ForeignKey relationship to Project, upload path callable functions, all media-related fields, and appropriate metadata.

---

## Instructions

### Step 1: Define Upload Path Callables

Add these two functions at the **module level** (before the `Segment` class, after the `Project` class):

```python
def segment_image_path(instance, filename):
    return f'projects/{instance.project.id}/images/{filename}'


def segment_audio_path(instance, filename):
    return f'projects/{instance.project.id}/audio/{filename}'
```

> **Why module-level?** Django serializes migration files and needs to reference `upload_to` callables by their import path. Lambdas or nested functions cause migration serialization errors.

---

### Step 2: Define the Segment Model

```python
class Segment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='segments')
    sequence_index = models.IntegerField(default=0)
    text_content = models.TextField(blank=True, default='')
    image_prompt = models.TextField(blank=True, default='')
    image_file = models.ImageField(upload_to=segment_image_path, blank=True, null=True)
    audio_file = models.FileField(upload_to=segment_audio_path, blank=True, null=True)
    audio_duration = models.FloatField(null=True, blank=True)
    is_locked = models.BooleanField(default=False)

    def __str__(self):
        return f"Segment {self.sequence_index} of {self.project.title}"

    class Meta:
        ordering = ['sequence_index']
```

---

## Expected Output

After this task, `backend/api/models.py` contains:

```
backend/api/models.py
├── import uuid
├── from django.db import models
├── STATUS_CHOICES
├── class Project(models.Model)          ← from Task 01.02.01
├── def segment_image_path(instance, filename)   ← NEW
├── def segment_audio_path(instance, filename)   ← NEW
└── class Segment(models.Model)                  ← NEW
    ├── 9 fields (id, project, sequence_index, text_content, image_prompt, image_file, audio_file, audio_duration, is_locked)
    ├── __str__ → "Segment {index} of {project.title}"
    └── Meta.ordering = ['sequence_index']
```

---

## Validation

- [ ] `segment_image_path` is a module-level function returning `'projects/{project_id}/images/{filename}'`.
- [ ] `segment_audio_path` is a module-level function returning `'projects/{project_id}/audio/{filename}'`.
- [ ] `project` field uses `ForeignKey(Project)` with `on_delete=models.CASCADE` and `related_name='segments'`.
- [ ] `image_file` uses `ImageField` with `upload_to=segment_image_path`.
- [ ] `audio_file` uses `FileField` with `upload_to=segment_audio_path`.
- [ ] `text_content` and `image_prompt` are `TextField` with `blank=True, default=''`.
- [ ] `audio_duration` is `FloatField` with `null=True, blank=True`.
- [ ] `is_locked` is `BooleanField` with `default=False`.
- [ ] `Meta.ordering` is `['sequence_index']` (ascending).

---

## Notes

- **`related_name='segments'`** is critical. Without it, the reverse relation defaults to `segment_set`, which would break the `ProjectDetailSerializer` and `get_segment_count()` method in later tasks.
- **`ImageField` requires Pillow** to be installed. This was handled in SubPhase 01.01 (Task 01.01.04).
- **Cascade delete:** When a `Project` is deleted, all its `Segment` instances are automatically deleted. This is intentional — segments have no meaning without their parent project.
- Do NOT run `makemigrations` yet — wait for Task 01.02.04 after all models are defined.

---

> **Parent:** [SubPhase_01_02_Overview.md](SubPhase_01_02_Overview.md) (Layer 2)
> **Previous Task:** [Task_01_02_01_Create_Project_Model.md](Task_01_02_01_Create_Project_Model.md)
> **Next Task:** [Task_01_02_03_Create_GlobalSettings_Model.md](Task_01_02_03_Create_GlobalSettings_Model.md)
