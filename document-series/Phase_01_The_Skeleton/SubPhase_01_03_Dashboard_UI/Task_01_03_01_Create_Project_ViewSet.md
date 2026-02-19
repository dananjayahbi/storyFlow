# Task 01.03.01 — Create ProjectViewSet

## Metadata

| Field                    | Value                                                                   |
| ------------------------ | ----------------------------------------------------------------------- |
| **Sub-Phase**            | SubPhase 01.03 — Dashboard UI & Basic API                               |
| **Phase**                | Phase 01 — The Skeleton                                                 |
| **Document Type**        | Layer 3 — Task Document                                                 |
| **Estimated Complexity** | Medium                                                                  |
| **Dependencies**         | SubPhase 01.02 complete (models, serializers, DRF config exist)         |
| **Parent Document**      | [SubPhase_01_03_Overview.md](SubPhase_01_03_Overview.md) (Layer 2, §5.1)|

---

## Objective

Implement the `ProjectViewSet` in `api/views.py` that exposes list, create, and retrieve actions for projects, with appropriate method restrictions and serializer switching between list and detail views.

---

## Instructions

### Step 1: Implement the ViewSet

Open `backend/api/views.py` and replace the default content with:

```python
from rest_framework import viewsets
from .models import Project
from .serializers import ProjectSerializer, ProjectDetailSerializer


class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    http_method_names = ['get', 'post', 'head', 'options']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ProjectDetailSerializer
        return ProjectSerializer
```

---

### Step 2: Verify Import Chain

Confirm the import chain works by checking in the Django shell:

```bash
python manage.py shell
```

```python
from api.views import ProjectViewSet
print(ProjectViewSet.queryset.model)  # <class 'api.models.Project'>
```

---

## Expected Output

```
backend/api/views.py   ← MODIFIED (replaced default content)
```

---

## Validation

- [ ] `ProjectViewSet` extends `viewsets.ModelViewSet`.
- [ ] `queryset` is `Project.objects.all()`.
- [ ] `serializer_class` defaults to `ProjectSerializer`.
- [ ] `http_method_names` restricts to `['get', 'post', 'head', 'options']` — no PUT, PATCH, DELETE.
- [ ] `get_serializer_class` returns `ProjectDetailSerializer` when `self.action == 'retrieve'`.
- [ ] `get_serializer_class` returns `ProjectSerializer` for all other actions (list, create).

---

## Notes

- **Why `ModelViewSet` with method restriction?** Using `ModelViewSet` provides all CRUD actions automatically, but `http_method_names` limits to only GET and POST. This is cleaner than using `mixins.ListModelMixin`, `mixins.CreateModelMixin`, etc. — and easier to extend in Phase 02 when more methods are needed.
- **Serializer switching:** The detail view (`GET /api/projects/{id}/`) returns nested segments via `ProjectDetailSerializer`, while the list view returns the lightweight `ProjectSerializer` with `segment_count`.
- The ViewSet will NOT be accessible until URL routing is configured in Task 01.03.02.

---

> **Parent:** [SubPhase_01_03_Overview.md](SubPhase_01_03_Overview.md) (Layer 2)
> **Phase:** [Phase_01_Overview.md](../../Phase_01_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../../00_Project_Overview.md) (Layer 0)
> **Next Task:** [Task_01_03_02_Configure_URL_Routing.md](Task_01_03_02_Configure_URL_Routing.md)
