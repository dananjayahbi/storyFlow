# Task 01.02.05 — Register Models in Django Admin

## Metadata

| Field                    | Value                                                                   |
| ------------------------ | ----------------------------------------------------------------------- |
| **Sub-Phase**            | SubPhase 01.02 — Database Models & Migrations                           |
| **Phase**                | Phase 01 — The Skeleton                                                 |
| **Document Type**        | Layer 3 — Task Document                                                 |
| **Estimated Complexity** | Low                                                                     |
| **Dependencies**         | [Task_01_02_04](Task_01_02_04_Run_Migrations.md) — Migrations must be applied |
| **Parent Document**      | [SubPhase_01_02_Overview.md](SubPhase_01_02_Overview.md) (Layer 2, §5.5)|

---

## Objective

Register all three models (Project, Segment, GlobalSettings) in Django Admin with appropriate display configurations and singleton enforcement for GlobalSettings.

---

## Instructions

### Step 1: Replace `admin.py` Contents

Open `backend/api/admin.py` and replace the default content with:

```python
from django.contrib import admin
from .models import Project, Segment, GlobalSettings


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['title', 'status', 'created_at', 'updated_at']
    list_filter = ['status', 'created_at']
    search_fields = ['title']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(Segment)
class SegmentAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'project', 'sequence_index', 'is_locked']
    list_filter = ['is_locked', 'project']
    search_fields = ['text_content', 'image_prompt']
    readonly_fields = ['id']


@admin.register(GlobalSettings)
class GlobalSettingsAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'default_voice_id', 'tts_speed', 'zoom_intensity']

    def has_add_permission(self, request):
        # Prevent creating multiple GlobalSettings instances
        if GlobalSettings.objects.exists():
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        # Prevent deleting the singleton
        return False
```

---

### Step 2: Verify in Browser

1. Start the dev server: `python manage.py runserver`
2. Navigate to `http://localhost:8000/admin/`
3. Log in with the superuser credentials (created in Task 01.02.11 — or create one now for testing).
4. Confirm all three models appear in the admin: **Projects**, **Segments**, **Global Settings**.

---

## Expected Output

```
backend/api/admin.py   ← MODIFIED (replaced default content)
```

---

## Validation

- [ ] `ProjectAdmin` uses `list_display = ['title', 'status', 'created_at', 'updated_at']`.
- [ ] `ProjectAdmin` has `list_filter`, `search_fields`, and `readonly_fields`.
- [ ] `SegmentAdmin` uses `list_display = ['__str__', 'project', 'sequence_index', 'is_locked']`.
- [ ] `SegmentAdmin` has `search_fields = ['text_content', 'image_prompt']`.
- [ ] `GlobalSettingsAdmin` overrides `has_add_permission` — returns `False` if instance exists.
- [ ] `GlobalSettingsAdmin` overrides `has_delete_permission` — always returns `False`.
- [ ] All three models appear in the Django Admin interface.

---

## Notes

- The `@admin.register(Model)` decorator is used instead of `admin.site.register(Model, ModelAdmin)`. Both are equivalent — the decorator is the modern, cleaner pattern.
- `GlobalSettingsAdmin` enforces singleton behavior at the admin level. The `load()` class method enforces it at the code level. Together, they prevent accidental creation or deletion of extra instances.
- Full admin verification requires a superuser (Task 01.02.11). If testing now, create a temporary superuser with `python manage.py createsuperuser`.

---

> **Parent:** [SubPhase_01_02_Overview.md](SubPhase_01_02_Overview.md) (Layer 2)
> **Previous Task:** [Task_01_02_04_Run_Migrations.md](Task_01_02_04_Run_Migrations.md)
> **Next Task:** [Task_01_02_06_Configure_DRF_Settings.md](Task_01_02_06_Configure_DRF_Settings.md)
