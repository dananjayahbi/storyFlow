# Task 02.01.05 — Build Import Endpoint

> **Sub-Phase:** 02.01 — Import & Parse Engine
> **Phase:** Phase 02 — The Logic
> **Complexity:** Medium
> **Dependencies:** Task 02.01.04 (Import Serializer)
> **Parent Document:** [SubPhase_02_01_Overview.md](./SubPhase_02_01_Overview.md)

---

## Objective

Create the `POST /api/projects/import/` endpoint as a standalone function-based view and register it in the URL routing. This endpoint accepts JSON or text import requests and returns fully-created projects with all segments.

---

## Instructions

### Step 1 — Add `import_project` view to `backend/api/views.py`

Add imports and the view function to the existing `views.py`:

```python
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .serializers import ProjectImportSerializer, ProjectDetailSerializer
from .parsers import ParseError


@api_view(['POST'])
def import_project(request):
    """Import a story as a new project with segments.

    Accepts JSON or text format via the 'format' field.
    Returns the created project with nested segments.
    """
    serializer = ProjectImportSerializer(data=request.data)

    try:
        serializer.is_valid(raise_exception=True)
        project = serializer.save()
    except ParseError as e:
        return Response(
            {'error': e.message, 'details': e.details},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Serialize response with full project + nested segments
    response_serializer = ProjectDetailSerializer(project)
    return Response(response_serializer.data, status=status.HTTP_201_CREATED)
```

**Design decision:** This is a **standalone view** (`@api_view`), NOT a custom action on `ProjectViewSet`. The import endpoint is a separate route per [Phase_02_Overview.md](../Phase_02_Overview.md) §4.1.

### Step 2 — Register the route in `backend/api/urls.py`

Add the import route **BEFORE** the router-generated project routes to avoid URL conflicts:

```python
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'projects', views.ProjectViewSet)

urlpatterns = [
    path('projects/import/', views.import_project, name='project-import'),  # ← Before router
    path('', include(router.urls)),
]
```

**Why before the router?** The router generates a catch-all pattern for `projects/<pk>/`. If placed after, Django would try to match `import` as a project PK and return 404.

### Step 3 — Verify trailing slash

The endpoint MUST use a trailing slash:

```
/api/projects/import/     ← Correct
/api/projects/import      ← WRONG — will 301 redirect, breaking POST data
```

### Step 4 — Verify error response structure

| Condition | Status | Response Body |
|---|---|---|
| Valid JSON import | 201 | Full project with nested segments |
| Valid text import | 201 | Full project with nested segments |
| Invalid JSON format | 400 | `{"error": "...", "details": "..."}` |
| Missing `format` field | 400 | `{"format": ["This field is required."]}` |
| Missing `title` | 400 | `{"title": ["This field is required."]}` |
| Empty segments | 400 | `{"error": "Missing or empty segments array"}` |
| DRF parse error (malformed JSON body) | 400 | DRF's default parse error response |

---

## Expected Output

```
backend/
└── api/
    ├── views.py            ← MODIFIED (import_project view added)
    └── urls.py             ← MODIFIED (import route added)
```

---

## Validation

- [ ] `POST /api/projects/import/` with valid JSON format → HTTP 201, project with nested segments.
- [ ] `POST /api/projects/import/` with valid text format → HTTP 201, project with nested segments.
- [ ] `POST /api/projects/import/` with invalid data → HTTP 400 with structured error body.
- [ ] Import route is placed BEFORE router URLs in `urls.py`.
- [ ] Trailing slash is present in the route pattern.
- [ ] Response includes full project with nested segments (uses `ProjectDetailSerializer`).
- [ ] `ParseError` from parsers is caught and returned as a 400 response.
- [ ] DRF `ValidationError` from validators passes through with standard DRF error formatting.

---

## Notes

- The response serializer is `ProjectDetailSerializer` (from Phase 01, Task 01.03), which includes nested `SegmentSerializer`. This ensures the response contains the full project with all created segments.
- This endpoint is entirely **synchronous** — no background tasks, no Celery, no async.
- The view only accepts `POST`. All other methods return 405 Method Not Allowed (handled by DRF's `@api_view` decorator).

---

> **Parent:** [SubPhase_02_01_Overview.md](./SubPhase_02_01_Overview.md) (Layer 2)
> **Phase:** [Phase_02_Overview.md](../Phase_02_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_02_01_04_Create_Import_Serializer.md](./Task_02_01_04_Create_Import_Serializer.md)
> **Next Task:** [Task_02_01_06_Write_Import_Tests.md](./Task_02_01_06_Write_Import_Tests.md)
