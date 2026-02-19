# Task 01.02.03 — Define GlobalSettings Model

## Metadata

| Field                    | Value                                                                   |
| ------------------------ | ----------------------------------------------------------------------- |
| **Sub-Phase**            | SubPhase 01.02 — Database Models & Migrations                           |
| **Phase**                | Phase 01 — The Skeleton                                                 |
| **Document Type**        | Layer 3 — Task Document                                                 |
| **Estimated Complexity** | Medium                                                                  |
| **Dependencies**         | None (independent of Project and Segment models)                        |
| **Parent Document**      | [SubPhase_01_02_Overview.md](SubPhase_01_02_Overview.md) (Layer 2, §5.3)|

---

## Objective

Define the `GlobalSettings` singleton model with the `load()` class method, all settings fields, and appropriate metadata enforcing singular naming.

---

## Instructions

### Step 1: Define the GlobalSettings Model

Add the following class to `backend/api/models.py` (after the `Segment` class):

```python
class GlobalSettings(models.Model):
    default_voice_id = models.CharField(max_length=100, default='af_bella')
    tts_speed = models.FloatField(default=1.0)
    zoom_intensity = models.FloatField(default=1.3)
    subtitle_font = models.CharField(max_length=255, blank=True, default='')
    subtitle_color = models.CharField(max_length=7, default='#FFFFFF')

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return "Global Settings"

    class Meta:
        verbose_name = 'Global Settings'
        verbose_name_plural = 'Global Settings'
```

---

## Expected Output

After this task, `backend/api/models.py` contains all three models:

```
backend/api/models.py
├── import uuid
├── from django.db import models
├── STATUS_CHOICES
├── class Project(models.Model)          ← Task 01.02.01
├── def segment_image_path(...)          ← Task 01.02.02
├── def segment_audio_path(...)          ← Task 01.02.02
├── class Segment(models.Model)          ← Task 01.02.02
└── class GlobalSettings(models.Model)   ← NEW
    ├── 5 fields (default_voice_id, tts_speed, zoom_intensity, subtitle_font, subtitle_color)
    ├── load() classmethod → singleton access
    ├── __str__ → "Global Settings"
    └── Meta (verbose_name / verbose_name_plural)
```

---

## Validation

- [ ] `GlobalSettings` has exactly 5 fields: `default_voice_id`, `tts_speed`, `zoom_intensity`, `subtitle_font`, `subtitle_color`.
- [ ] `default_voice_id` defaults to `'af_bella'`.
- [ ] `tts_speed` defaults to `1.0`.
- [ ] `zoom_intensity` defaults to `1.3`.
- [ ] `subtitle_color` defaults to `'#FFFFFF'` with `max_length=7`.
- [ ] `load()` is a `@classmethod` using `get_or_create(pk=1)`.
- [ ] `__str__` returns `"Global Settings"`.
- [ ] `Meta.verbose_name` and `Meta.verbose_name_plural` are both `'Global Settings'`.

---

## Notes

- **No UUID primary key:** Unlike `Project` and `Segment`, `GlobalSettings` uses Django's default `BigAutoField` (configured in `settings.py` as `DEFAULT_AUTO_FIELD`). The `pk=1` in `get_or_create` refers to this auto-generated ID.
- **Singleton pattern:** `get_or_create(pk=1)` creates a row with all default values on first access. Subsequent calls return the existing row. There is always exactly one `GlobalSettings` row in the database.
- **Why not `first()`?** `GlobalSettings.objects.first()` returns `None` if no row exists, requiring explicit null-check and creation logic. `get_or_create(pk=1)` is atomic and cleaner.
- Do NOT run `makemigrations` yet — proceed to Task 01.02.04.

---

> **Parent:** [SubPhase_01_02_Overview.md](SubPhase_01_02_Overview.md) (Layer 2)
> **Previous Task:** [Task_01_02_02_Create_Segment_Model.md](Task_01_02_02_Create_Segment_Model.md)
> **Next Task:** [Task_01_02_04_Run_Migrations.md](Task_01_02_04_Run_Migrations.md)
