# Task 02.03.01 — Create Zustand Project Store

> **Sub-Phase:** 02.03 — Image Upload & Timeline Editor UI
> **Phase:** Phase 02 — The Logic
> **Complexity:** High
> **Dependencies:** None (foundational)
> **Parent Document:** [SubPhase_02_03_Overview.md](./SubPhase_02_03_Overview.md)

---

## Objective

Implement the `useProjectStore` Zustand store in `frontend/lib/stores.ts` to manage all project and segment state for the Timeline Editor, including fetch, optimistic text updates, pessimistic destructive actions, and image operations.

---

## Instructions

### Step 1 — Create the store file

Create `frontend/lib/stores.ts`.

### Step 2 — Define imports

```typescript
import { create } from 'zustand';
import {
  getProject,
  getSegments,
  updateSegment as apiUpdateSegment,
  deleteSegment as apiDeleteSegment,
  uploadSegmentImage,
  removeSegmentImage,
  reorderSegments as apiReorderSegments,
} from './api';
import type { Project, Segment, UpdateSegmentPayload } from './types';
```

### Step 3 — Define the store interface

```typescript
interface ProjectStore {
  // State
  project: Project | null;
  segments: Segment[];
  isLoading: boolean;
  error: string | null;

  // Actions
  fetchProject: (id: number) => Promise<void>;
  updateSegment: (id: number, data: UpdateSegmentPayload) => Promise<void>;
  deleteSegment: (id: number) => Promise<void>;
  reorderSegments: (newOrder: number[]) => Promise<void>;
  uploadImage: (segmentId: number, file: File) => Promise<void>;
  removeImage: (segmentId: number) => Promise<void>;
  reset: () => void;
}
```

### Step 4 — Implement the store

```typescript
export const useProjectStore = create<ProjectStore>()((set, get) => ({
  project: null,
  segments: [],
  isLoading: false,
  error: null,

  fetchProject: async (id) => {
    set({ isLoading: true, error: null });
    try {
      const project = await getProject(id);
      const segments = await getSegments(id);
      set({ project, segments, isLoading: false });
    } catch (err) {
      set({ error: 'Failed to load project', isLoading: false });
    }
  },

  updateSegment: async (id, data) => {
    // Optimistic update — save previous state for rollback
    const previousSegments = get().segments;
    set((state) => ({
      segments: state.segments.map((s) =>
        s.id === id ? { ...s, ...data } : s
      ),
    }));
    try {
      const updated = await apiUpdateSegment(id, data);
      set((state) => ({
        segments: state.segments.map((s) =>
          s.id === id ? updated : s
        ),
      }));
    } catch (err) {
      // Rollback on failure
      set({ segments: previousSegments, error: 'Failed to update segment' });
    }
  },

  deleteSegment: async (id) => {
    // Pessimistic — wait for API success
    try {
      await apiDeleteSegment(id);
      set((state) => ({
        segments: state.segments.filter((s) => s.id !== id),
      }));
    } catch (err) {
      set({ error: 'Failed to delete segment' });
    }
  },

  reorderSegments: async (newOrder) => {
    const { project } = get();
    if (!project) return;
    try {
      await apiReorderSegments(project.id, newOrder);
      set((state) => ({
        segments: newOrder.map((id, index) => {
          const seg = state.segments.find((s) => s.id === id);
          return seg ? { ...seg, sequence_index: index } : seg!;
        }),
      }));
    } catch (err) {
      set({ error: 'Failed to reorder segments' });
    }
  },

  uploadImage: async (segmentId, file) => {
    // Pessimistic — wait for response
    try {
      const updated = await uploadSegmentImage(segmentId, file);
      set((state) => ({
        segments: state.segments.map((s) =>
          s.id === segmentId ? updated : s
        ),
      }));
    } catch (err) {
      set({ error: 'Failed to upload image' });
    }
  },

  removeImage: async (segmentId) => {
    try {
      await removeSegmentImage(segmentId);
      set((state) => ({
        segments: state.segments.map((s) =>
          s.id === segmentId ? { ...s, image_file: null } : s
        ),
      }));
    } catch (err) {
      set({ error: 'Failed to remove image' });
    }
  },

  reset: () => set({ project: null, segments: [], isLoading: false, error: null }),
}));
```

### Step 5 — Verify TypeScript compilation

```bash
cd frontend
npx tsc --noEmit
```

---

## Expected Output

```
frontend/
└── lib/
    └── stores.ts           ← NEW (Zustand project store)
```

---

## Validation

- [ ] `useProjectStore` is exported and importable.
- [ ] `fetchProject` sets `isLoading`, populates `project` and `segments`, clears `isLoading`.
- [ ] `updateSegment` performs optimistic update and rolls back on error.
- [ ] `deleteSegment`, `uploadImage`, `removeImage` use pessimistic strategy.
- [ ] `reorderSegments` updates `sequence_index` values.
- [ ] `reset` clears all state to initial values.
- [ ] TypeScript compiles with zero errors.

---

## Notes

- Zustand stores are created with `create<T>()((set, get) => ({ ... }))`.
- Use `set((state) => ({ ... }))` for immutable updates based on current state.
- Optimistic updates give a snappy typing experience; pessimistic updates for destructive actions prevent inconsistencies on failure.
- The store is a single global instance — `reset()` must be called on page unmount to clear stale state.

---

> **Parent:** [SubPhase_02_03_Overview.md](./SubPhase_02_03_Overview.md) (Layer 2)
> **Phase:** [Phase_02_Overview.md](../Phase_02_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** None (first task of SubPhase 02.03)
> **Next Task:** [Task_02_03_02_Build_SegmentTextEditor.md](./Task_02_03_02_Build_SegmentTextEditor.md)
