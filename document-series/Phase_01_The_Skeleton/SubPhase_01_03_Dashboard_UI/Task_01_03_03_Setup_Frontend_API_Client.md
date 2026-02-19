# Task 01.03.03 — Setup Frontend API Client

## Metadata

| Field                    | Value                                                                   |
| ------------------------ | ----------------------------------------------------------------------- |
| **Sub-Phase**            | SubPhase 01.03 — Dashboard UI & Basic API                               |
| **Phase**                | Phase 01 — The Skeleton                                                 |
| **Document Type**        | Layer 3 — Task Document                                                 |
| **Estimated Complexity** | Medium                                                                  |
| **Dependencies**         | None (can be created before backend is ready)                           |
| **Parent Document**      | [SubPhase_01_03_Overview.md](SubPhase_01_03_Overview.md) (Layer 2, §5.3)|

---

## Objective

Create the Axios-based API client module with typed helper functions for all Phase 01 endpoints (list projects, get project detail, create project).

---

## Instructions

### Step 1: Create `lib/api.ts`

Create `frontend/lib/api.ts`:

```typescript
import axios from 'axios';
import { Project, ProjectDetail, CreateProjectPayload, PaginatedResponse } from './types';

const api = axios.create({
  baseURL: 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
});

export async function getProjects(): Promise<PaginatedResponse<Project>> {
  const response = await api.get<PaginatedResponse<Project>>('/api/projects/');
  return response.data;
}

export async function getProject(id: string): Promise<ProjectDetail> {
  const response = await api.get<ProjectDetail>(`/api/projects/${id}/`);
  return response.data;
}

export async function createProject(payload: CreateProjectPayload): Promise<Project> {
  const response = await api.post<Project>('/api/projects/', payload);
  return response.data;
}

export default api;
```

---

## Expected Output

```
frontend/lib/
├── api.ts       ← NEW
├── types.ts     ← Created in Task 01.03.04
└── utils.ts     ← Existing (from Shadcn/UI init)
```

---

## Validation

- [ ] `frontend/lib/api.ts` exists.
- [ ] Axios instance uses `baseURL: 'http://localhost:8000'` (no trailing slash).
- [ ] `Content-Type` header is set to `'application/json'`.
- [ ] `getProjects()` calls `GET /api/projects/` and returns `PaginatedResponse<Project>`.
- [ ] `getProject(id)` calls `GET /api/projects/${id}/` and returns `ProjectDetail`.
- [ ] `createProject(payload)` calls `POST /api/projects/` and returns `Project`.
- [ ] All API paths include trailing slashes.
- [ ] All functions return `response.data` (not the raw Axios response).
- [ ] The base Axios instance is exported as default.

---

## Notes

- **`baseURL` must NOT have a trailing slash.** Individual paths start with `/api/...`. A trailing slash on baseURL would create double-slash issues (`http://localhost:8000//api/projects/`).
- **Trailing slashes on paths are mandatory.** Django's `APPEND_SLASH` redirects non-trailing-slash URLs with a 301. This redirect can cause CORS issues because the redirect response may not include CORS headers.
- Functions return the parsed data (`response.data`), not the Axios response object. This simplifies consumption in components.
- The `types.ts` file (Task 01.03.04) must exist for the imports to work. These two tasks can be done in any order — just ensure both are complete before proceeding to components.
- This module will be extended in Phase 02 with additional functions (segment updates, image upload, etc.).

---

> **Parent:** [SubPhase_01_03_Overview.md](SubPhase_01_03_Overview.md) (Layer 2)
> **Previous Task:** [Task_01_03_02_Configure_URL_Routing.md](Task_01_03_02_Configure_URL_Routing.md)
> **Next Task:** [Task_01_03_04_Define_TypeScript_Interfaces.md](Task_01_03_04_Define_TypeScript_Interfaces.md)
