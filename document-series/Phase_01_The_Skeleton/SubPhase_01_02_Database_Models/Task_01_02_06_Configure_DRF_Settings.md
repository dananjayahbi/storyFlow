# Task 01.02.06 — Configure DRF Settings

## Metadata

| Field                    | Value                                                                   |
| ------------------------ | ----------------------------------------------------------------------- |
| **Sub-Phase**            | SubPhase 01.02 — Database Models & Migrations                           |
| **Phase**                | Phase 01 — The Skeleton                                                 |
| **Document Type**        | Layer 3 — Task Document                                                 |
| **Estimated Complexity** | Low                                                                     |
| **Dependencies**         | None (independent of model tasks)                                       |
| **Parent Document**      | [SubPhase_01_02_Overview.md](SubPhase_01_02_Overview.md) (Layer 2, §5.6)|

---

## Objective

Add the `REST_FRAMEWORK` configuration dictionary to `settings.py` with appropriate default permissions, renderers, and pagination for a local-only, no-auth application.

---

## Instructions

### Step 1: Add REST_FRAMEWORK Settings

Open `backend/storyflow_backend/settings.py` and add the following block (at the end of the file, after the existing settings):

```python
# ---------------------
# Django REST Framework
# ---------------------
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
}
```

---

### Step 2: Verify Server Starts

```bash
python manage.py runserver
```

Confirm the server starts without errors.

---

## Expected Output

```
backend/storyflow_backend/settings.py   ← MODIFIED (REST_FRAMEWORK dict added)
```

---

## Validation

- [ ] `REST_FRAMEWORK` dict exists in `settings.py`.
- [ ] `DEFAULT_PERMISSION_CLASSES` is `['rest_framework.permissions.AllowAny']`.
- [ ] `DEFAULT_RENDERER_CLASSES` includes both `JSONRenderer` and `BrowsableAPIRenderer`.
- [ ] `DEFAULT_PAGINATION_CLASS` is set to `PageNumberPagination`.
- [ ] `PAGE_SIZE` is `50`.
- [ ] `python manage.py runserver` starts without errors.

---

## Notes

- **`AllowAny` is intentional.** This is a local-only, single-user application with no authentication. As defined in `00_Project_Overview.md` (Layer 0, §14.1): "Authentication: None."
- **`BrowsableAPIRenderer` is kept** for development convenience. It provides a built-in web interface for testing API endpoints at `http://localhost:8000/api/`.
- **`PAGE_SIZE: 50`** is a generous default. StoryFlow projects are unlikely to exceed dozens of items. Pagination is included for correctness but won't practically trigger in v1.0.

---

> **Parent:** [SubPhase_01_02_Overview.md](SubPhase_01_02_Overview.md) (Layer 2)
> **Previous Task:** [Task_01_02_05_Register_Admin.md](Task_01_02_05_Register_Admin.md)
> **Next Task:** [Task_01_02_07_Create_Project_Serializer.md](Task_01_02_07_Create_Project_Serializer.md)
