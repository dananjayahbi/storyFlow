# Task 02.02.09 — Update Frontend API Client

> **Sub-Phase:** 02.02 — Segment Management API
> **Phase:** Phase 02 — The Logic
> **Complexity:** Medium
> **Dependencies:** Task 02.02.08 (URL Routing)
> **Parent Document:** [SubPhase_02_02_Overview.md](./SubPhase_02_02_Overview.md)

---

## Objective

Add 6 new API functions to `frontend/lib/api.ts` for segment CRUD, image management, reorder, and project deletion.

---

## Instructions

### Step 1 — Add imports to `frontend/lib/api.ts`

```typescript
import { Segment, UpdateSegmentPayload } from './types';
```

### Step 2 — Add segment CRUD functions

```typescript
export async function getSegments(projectId: number): Promise<Segment[]> {
  const response = await api.get(`/segments/?project=${projectId}`);
  return response.data;
}

export async function updateSegment(
  id: number,
  data: UpdateSegmentPayload
): Promise<Segment> {
  const response = await api.patch(`/segments/${id}/`, data);
  return response.data;
}

export async function deleteSegment(id: number): Promise<void> {
  await api.delete(`/segments/${id}/`);
}
```

### Step 3 — Add image management functions

```typescript
export async function uploadSegmentImage(
  id: number,
  file: File
): Promise<{ id: number; image_file: string; message: string }> {
  const formData = new FormData();
  formData.append('image', file);
  const response = await api.post(`/segments/${id}/upload-image/`, formData);
  return response.data;
}

export async function removeSegmentImage(
  id: number
): Promise<{ id: number; image_file: null; message: string }> {
  const response = await api.delete(`/segments/${id}/remove-image/`);
  return response.data;
}
```

### Step 4 — Add reorder and project delete functions

```typescript
export async function reorderSegments(
  projectId: number,
  segmentOrder: number[]
): Promise<void> {
  await api.post('/segments/reorder/', {
    project_id: projectId,
    segment_order: segmentOrder,
  });
}

export async function deleteProject(id: number): Promise<void> {
  await api.delete(`/projects/${id}/`);
}
```

### Step 5 — Important: Do NOT set Content-Type for FormData

For `uploadSegmentImage`, do **NOT** manually set `Content-Type: multipart/form-data`. Axios automatically sets it with the correct boundary when the body is a `FormData` object. Setting it manually removes the boundary parameter and breaks Django's multipart parsing.

```typescript
// ✅ CORRECT — let Axios handle Content-Type
await api.post(`/segments/${id}/upload-image/`, formData);

// ❌ WRONG — breaks boundary parameter
await api.post(`/segments/${id}/upload-image/`, formData, {
  headers: { 'Content-Type': 'multipart/form-data' },
});
```

---

## Expected Output

```
frontend/
└── lib/
    └── api.ts              ← MODIFIED (6 new functions added)
```

---

## Validation

- [ ] `updateSegment()` sends PATCH to `/segments/{id}/`.
- [ ] `deleteSegment()` sends DELETE to `/segments/{id}/`.
- [ ] `uploadSegmentImage()` sends POST with FormData to `/segments/{id}/upload-image/`.
- [ ] `removeSegmentImage()` sends DELETE to `/segments/{id}/remove-image/`.
- [ ] `reorderSegments()` sends POST to `/segments/reorder/`.
- [ ] `deleteProject()` sends DELETE to `/projects/{id}/`.
- [ ] All URLs include trailing slashes.
- [ ] No manual `Content-Type` header on FormData requests.
- [ ] TypeScript compiles: `npx tsc --noEmit` passes.

---

## Notes

- These functions are consumed by SubPhase 02.03's Timeline Editor UI components. In this sub-phase, they are implemented but not yet used in any frontend component.
- The `getSegments()` function is also added here as a convenience — it fetches segments filtered by project for the upcoming Timeline Editor.

---

> **Parent:** [SubPhase_02_02_Overview.md](./SubPhase_02_02_Overview.md) (Layer 2)
> **Phase:** [Phase_02_Overview.md](../Phase_02_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_02_02_08_Update_URL_Routing.md](./Task_02_02_08_Update_URL_Routing.md)
> **Next Task:** [Task_02_02_10_Update_TypeScript_Types.md](./Task_02_02_10_Update_TypeScript_Types.md)
