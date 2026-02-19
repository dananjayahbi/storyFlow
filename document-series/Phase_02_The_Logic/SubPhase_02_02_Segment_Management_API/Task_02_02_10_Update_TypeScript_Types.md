# Task 02.02.10 — Update TypeScript Types

> **Sub-Phase:** 02.02 — Segment Management API
> **Phase:** Phase 02 — The Logic
> **Complexity:** Low
> **Dependencies:** None
> **Parent Document:** [SubPhase_02_02_Overview.md](./SubPhase_02_02_Overview.md)

---

## Objective

Add new TypeScript interfaces to `frontend/lib/types.ts` for segment mutation payloads used by the API client functions.

---

## Instructions

### Step 1 — Add `UpdateSegmentPayload` interface

```typescript
export interface UpdateSegmentPayload {
  text_content?: string;
  image_prompt?: string;
  is_locked?: boolean;
}
```

All fields are optional because PATCH only requires the fields being updated.

### Step 2 — Add `ReorderPayload` interface

```typescript
export interface ReorderPayload {
  project_id: number;
  segment_order: number[];
}
```

### Step 3 — Verify existing `Segment` interface

Confirm that the `Segment` interface (defined in SubPhase 01.03, Task 01.03.04) includes all fields returned by the API:

```typescript
export interface Segment {
  id: number;
  sequence_index: number;
  text_content: string;
  image_prompt: string;
  image_file: string | null;
  audio_file: string | null;
  audio_duration: number | null;
  is_locked: boolean;
  created_at: string;
  updated_at: string;
}
```

If any fields are missing (especially `is_locked`, `audio_file`, `audio_duration`), add them now.

---

## Expected Output

```
frontend/
└── lib/
    └── types.ts            ← MODIFIED (2 new interfaces added)
```

---

## Validation

- [ ] `UpdateSegmentPayload` interface exists with optional `text_content`, `image_prompt`, `is_locked` fields.
- [ ] `ReorderPayload` interface exists with `project_id` and `segment_order` fields.
- [ ] Existing `Segment` interface includes `is_locked`, `image_file`, `audio_file`, `audio_duration`.
- [ ] TypeScript compiles: `npx tsc --noEmit` passes.

---

## Notes

- The `ImportProjectRequest` type was already added in SubPhase 02.01 (Task 02.01.09) — no changes needed for import types.
- `ReorderPayload` will also be useful for the Zustand store in SubPhase 02.03.

---

> **Parent:** [SubPhase_02_02_Overview.md](./SubPhase_02_02_Overview.md) (Layer 2)
> **Phase:** [Phase_02_Overview.md](../Phase_02_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_02_02_09_Update_Frontend_API_Client.md](./Task_02_02_09_Update_Frontend_API_Client.md)
> **Next Task:** [Task_02_02_11_Write_Segment_API_Tests.md](./Task_02_02_11_Write_Segment_API_Tests.md)
