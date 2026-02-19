# Task 01.03.02 — Configure URL Routing

## Metadata

| Field                    | Value                                                                          |
| ------------------------ | ------------------------------------------------------------------------------ |
| **Sub-Phase**            | SubPhase 01.03 — Dashboard UI & Basic API                                      |
| **Phase**                | Phase 01 — The Skeleton                                                        |
| **Document Type**        | Layer 3 — Task Document                                                        |
| **Estimated Complexity** | Low                                                                            |
| **Dependencies**         | [Task_01_03_01](Task_01_03_01_Create_Project_ViewSet.md) — ViewSet must exist  |
| **Parent Document**      | [SubPhase_01_03_Overview.md](SubPhase_01_03_Overview.md) (Layer 2, §5.2)       |

---

## Objective

Create the API URL routing file with DRF's DefaultRouter and update the root URL configuration to include API endpoints and media file serving for development.

---

## Instructions

### Step 1: Create `api/urls.py`

Create `backend/api/urls.py`:

```python
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProjectViewSet

router = DefaultRouter()
router.register(r'projects', ProjectViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
```

---

### Step 2: Update Root URL Configuration

Open `backend/storyflow_backend/urls.py` and replace with:

```python
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

---

### Step 3: Verify Endpoints

1. Start the dev server: `python manage.py runserver`
2. Navigate to `http://localhost:8000/api/` — DRF browsable API root should display.
3. Navigate to `http://localhost:8000/api/projects/` — should return:

```json
{
    "count": 0,
    "next": null,
    "previous": null,
    "results": []
}
```

4. Test POST via the DRF browsable API: submit `{"title": "Test"}` and verify a project is created.

---

## Expected Output

**Resulting URL patterns:**

| URL Pattern               | View                          | Name             |
| ------------------------- | ----------------------------- | ---------------- |
| `/api/projects/`          | ProjectViewSet (list/create)  | `project-list`   |
| `/api/projects/{uuid}/`   | ProjectViewSet (retrieve)     | `project-detail` |
| `/admin/`                 | Django Admin                  | —                |
| `/media/<path>`           | Media file serving (dev only) | —                |

```
backend/
├── api/
│   └── urls.py                      ← NEW
├── storyflow_backend/
│   └── urls.py                      ← MODIFIED
└── ...
```

---

## Validation

- [ ] `backend/api/urls.py` exists with `DefaultRouter` and `ProjectViewSet` registered.
- [ ] `backend/storyflow_backend/urls.py` includes `api.urls` under the `api/` prefix.
- [ ] Media file serving is wrapped in `if settings.DEBUG:`.
- [ ] `http://localhost:8000/api/` shows the DRF browsable API root.
- [ ] `http://localhost:8000/api/projects/` returns paginated JSON.
- [ ] POST to `/api/projects/` creates a new project successfully.

---

## Notes

- The `DefaultRouter` auto-generates list (`/projects/`), detail (`/projects/{pk}/`), and the API root (`/api/`). No manual URL patterns needed.
- UUID-based lookup works automatically because `Project.id` is the primary key and DRF uses `pk` for lookup by default.
- The `static()` helper for media serving only works when `DEBUG=True`. It is wrapped in `if settings.DEBUG:` to prevent accidental production use.
- **Trailing slashes:** DRF's `DefaultRouter` includes trailing slashes by default. This is consistent with Django's `APPEND_SLASH` behavior.

---

> **Parent:** [SubPhase_01_03_Overview.md](SubPhase_01_03_Overview.md) (Layer 2)
> **Previous Task:** [Task_01_03_01_Create_Project_ViewSet.md](Task_01_03_01_Create_Project_ViewSet.md)
> **Next Task:** [Task_01_03_03_Setup_Frontend_API_Client.md](Task_01_03_03_Setup_Frontend_API_Client.md)
