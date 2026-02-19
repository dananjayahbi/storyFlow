# Task 03.02.09 — Update Frontend API Client

> **Sub-Phase:** 03.02 — Audio Generation API
> **Phase:** Phase 03 — The Voice
> **Complexity:** Medium
> **Dependencies:** Task 03.02.03 (Generate Audio), Task 03.02.04 (Generate All), Task 03.02.05 (Task Status)
> **Parent Document:** [SubPhase_03_02_Overview.md](./SubPhase_03_02_Overview.md)

---

## Objective

Add audio generation and task polling functions to the frontend API client (`lib/api.ts`), providing the interface that SubPhase 03.03's UI components will consume.

---

## Instructions

### Step 1 — Add `generateSegmentAudio(segmentId: string) → Promise<TaskResponse>`

Send a `POST` request to `/segments/${segmentId}/generate-audio/` using the existing Axios instance. Return the response data typed as `TaskResponse`.

### Step 2 — Add `generateAllAudio(projectId: string, options?) → Promise<BulkTaskResponse>`

Send a `POST` request to `/projects/${projectId}/generate-all-audio/` with an optional request body containing `skip_locked` (boolean, default true) and `force_regenerate` (boolean, default false). Return the response data typed as `BulkTaskResponse`.

### Step 3 — Add `getTaskStatus(taskId: string) → Promise<TaskStatusResponse>`

Send a `GET` request to `/tasks/${taskId}/status/`. Return the response data typed as `TaskStatusResponse`.

### Step 4 — Add `pollTaskStatus(taskId, onProgress, intervalMs?) → Promise<TaskStatusResponse>`

Implement a polling utility that calls `getTaskStatus()` at a regular interval (default 2000ms). On each poll, invoke the `onProgress` callback with the latest `TaskStatusResponse`. When the status is `COMPLETED` or `FAILED`, clear the interval and resolve the promise. On any network error, clear the interval and reject. This function returns a promise that resolves with the final status.

### Step 5 — Import TypeScript types

Import `TaskResponse`, `BulkTaskResponse`, `TaskStatusResponse` from `./types` (created in Task 03.02.10). Ensure all function signatures and return types are fully typed.

---

## Expected Output

```
frontend/
└── lib/
    └── api.ts                  ← MODIFIED (4 new functions added)
```

---

## Validation

- [ ] `generateSegmentAudio(segmentId)` sends POST to the correct endpoint.
- [ ] `generateAllAudio(projectId, options)` sends POST with body.
- [ ] `getTaskStatus(taskId)` sends GET to the correct endpoint.
- [ ] `pollTaskStatus(taskId, callback)` polls every 2 seconds by default.
- [ ] `pollTaskStatus` resolves when status is COMPLETED or FAILED.
- [ ] `pollTaskStatus` rejects on network errors and clears the interval.
- [ ] All functions are properly typed with TypeScript.
- [ ] TypeScript compiles: `npx tsc --noEmit` passes.

---

## Notes

- `pollTaskStatus` is the key frontend utility — SubPhase 03.03's Zustand store will call it to drive the audio generation progress UI.
- The polling interval of 2 seconds is a balance between UI responsiveness and network overhead. For a local app, even 1 second would be fine, but 2 seconds is gentler.
- The `onProgress` callback enables incremental UI updates (e.g., a progress bar that fills segment by segment).
- All functions use the same Axios instance configured in Phase 01 with the `API_BASE_URL`.

---

> **Parent:** [SubPhase_03_02_Overview.md](./SubPhase_03_02_Overview.md) (Layer 2)
> **Phase:** [Phase_03_Overview.md](../Phase_03_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_03_02_08_Update_Segment_Delete_Audio.md](./Task_03_02_08_Update_Segment_Delete_Audio.md)
> **Next Task:** [Task_03_02_10_Update_TypeScript_Types.md](./Task_03_02_10_Update_TypeScript_Types.md)
