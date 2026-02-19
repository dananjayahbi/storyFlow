# Task 03.02.10 — Update TypeScript Types

> **Sub-Phase:** 03.02 — Audio Generation API
> **Phase:** Phase 03 — The Voice
> **Complexity:** Low
> **Dependencies:** Task 03.02.09 (Frontend API Client)
> **Parent Document:** [SubPhase_03_02_Overview.md](./SubPhase_03_02_Overview.md)

---

## Objective

Add all audio-related TypeScript types to `lib/types.ts` that match the exact JSON response shapes from the backend API endpoints, providing type safety for the frontend API client and SubPhase 03.03's UI components.

---

## Instructions

### Step 1 — Add `TaskStatus` type

Define a union type of the four status string literals: `"PENDING"`, `"PROCESSING"`, `"COMPLETED"`, `"FAILED"`. Use a union type (not an enum) for simplicity and direct compatibility with JSON deserialization.

### Step 2 — Add `TaskResponse` interface

Define the response shape for single-segment audio generation (POST generate-audio). Fields: `task_id` (string), `segment_id` (string), `status` (TaskStatus), `message` (string).

### Step 3 — Add `BulkTaskResponse` interface

Define the response shape for bulk audio generation (POST generate-all-audio). Fields: `task_id` (string), `project_id` (string), `status` (TaskStatus), `total_segments` (number), `segments_to_process` (number), `message` (string).

### Step 4 — Add `TaskProgress` interface

Define the progress sub-object shape. Fields: `current` (number), `total` (number), `percentage` (number), `current_segment_id` (optional string).

### Step 5 — Add `CompletedSegmentAudio` interface

Define the completed segment audio entry shape. Fields: `segment_id` (string), `audio_url` (string), `duration` (number).

### Step 6 — Add `TaskError` interface

Define the error entry shape. Fields: `segment_id` (string), `error` (string).

### Step 7 — Add `TaskStatusResponse` interface

Define the response shape for the task status polling endpoint (GET task status). Fields: `task_id` (string), `status` (TaskStatus), `progress` (TaskProgress), `completed_segments` (array of CompletedSegmentAudio), `errors` (array of TaskError).

---

## Expected Output

```
frontend/
└── lib/
    └── types.ts                ← MODIFIED (7 new types/interfaces added)
```

---

## Validation

- [ ] `TaskStatus` type matches backend status string values exactly.
- [ ] `TaskResponse` matches the single generation POST response shape.
- [ ] `BulkTaskResponse` matches the bulk generation POST response shape.
- [ ] `TaskStatusResponse` matches the GET task status response shape.
- [ ] `TaskProgress` matches the progress sub-object shape.
- [ ] `CompletedSegmentAudio` matches the completed segment entry shape.
- [ ] `TaskError` matches the error entry shape.
- [ ] TypeScript compiles: `npx tsc --noEmit` passes with zero errors.

---

## Notes

- All types mirror the exact JSON shapes returned by the Django REST Framework endpoints. Any mismatch will cause runtime type errors.
- `TaskStatus` is a union type, not a TypeScript `enum`, because JSON responses are plain strings — a union type matches them directly without conversion.
- These types are consumed by Task 03.02.09's API functions and by SubPhase 03.03's Zustand store extensions and UI components.
- The `current_segment_id` field in `TaskProgress` is optional because single-segment tasks may not set it.

---

> **Parent:** [SubPhase_03_02_Overview.md](./SubPhase_03_02_Overview.md) (Layer 2)
> **Phase:** [Phase_03_Overview.md](../Phase_03_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_03_02_09_Update_Frontend_API_Client.md](./Task_03_02_09_Update_Frontend_API_Client.md)
> **Next Task:** [Task_03_02_11_Write_API_Integration_Tests.md](./Task_03_02_11_Write_API_Integration_Tests.md)
