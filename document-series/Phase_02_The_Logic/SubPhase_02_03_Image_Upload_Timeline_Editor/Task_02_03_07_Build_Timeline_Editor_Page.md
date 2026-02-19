# Task 02.03.07 — Build Timeline Editor Page

> **Sub-Phase:** 02.03 — Image Upload & Timeline Editor UI
> **Phase:** Phase 02 — The Logic
> **Complexity:** High
> **Dependencies:** Task 02.03.01 (Zustand Store), Task 02.03.06 (Timeline)
> **Parent Document:** [SubPhase_02_03_Overview.md](./SubPhase_02_03_Overview.md)

---

## Objective

Create the full Timeline Editor page that **replaces** the Phase 01 placeholder at `frontend/app/projects/[id]/page.tsx`, featuring a header bar, left sidebar, center timeline panel, and bottom action bar.

---

## Instructions

### Step 1 — Replace the placeholder page

Overwrite `frontend/app/projects/[id]/page.tsx` entirely. Add the `"use client"` directive — this page uses hooks and interactive state.

### Step 2 — Extract route param and fetch data

```typescript
'use client';

import { useEffect } from 'react';
import { useParams } from 'next/navigation';
import { useProjectStore } from '@/lib/stores';

export default function TimelineEditorPage() {
  const params = useParams();
  const id = Number(params.id);
  const {
    project, segments, isLoading, error,
    fetchProject, updateSegment, deleteSegment,
    uploadImage, removeImage, reset,
  } = useProjectStore();

  useEffect(() => {
    fetchProject(id);
    return () => reset(); // Clear state on unmount
  }, [id, fetchProject, reset]);

  // ... render
}
```

### Step 3 — Implement loading and error states

- **Loading:** Show skeleton loaders (pulsing placeholder blocks) while `isLoading` is `true`.
- **Error:** Show error message with a "Retry" button that re-calls `fetchProject(id)`.

### Step 4 — Render the full layout

Use CSS Grid or Flexbox for the three-section layout:

**4a. Header Bar (full width):**
- Left: "StoryFlow — {project.title}".
- Right: "Back to Dashboard" link (`<Link href="/">`), "Export" button (`disabled`).

**4b. Left Sidebar (≈250px fixed width):**
- Project title.
- Status badge (`DRAFT`) — use a `Badge` or styled `span`.
- Segment count: `{segments.length} segments`.
- Created date (formatted with `toLocaleDateString()`).
- `<Separator />` between items.

**4c. Center Panel (fluid remaining width):**
```tsx
<Timeline
  segments={segments}
  onUpdateSegment={updateSegment}
  onDeleteSegment={deleteSegment}
  onUploadImage={uploadImage}
  onRemoveImage={removeImage}
/>
```

**4d. Bottom Action Bar (full width, fixed at bottom):**
- "Generate All Audio" button — `disabled`, with `<Tooltip>` showing "Coming in Phase 03".
- "Export Video" button — `disabled`, with `<Tooltip>` showing "Coming in Phase 04".

### Step 5 — Layout CSS structure

```tsx
<div className="flex flex-col h-screen">
  {/* Header */}
  <header className="border-b p-4 flex items-center justify-between">
    ...
  </header>

  {/* Main content */}
  <div className="flex flex-1 overflow-hidden">
    {/* Sidebar */}
    <aside className="w-64 border-r p-4 flex-shrink-0">
      ...
    </aside>

    {/* Center panel */}
    <main className="flex-1 overflow-auto">
      <Timeline ... />
    </main>
  </div>

  {/* Action bar */}
  <footer className="border-t p-4 flex items-center gap-4">
    ...
  </footer>
</div>
```

---

## Expected Output

```
frontend/
└── app/
    └── projects/
        └── [id]/
            └── page.tsx        ← REPLACED (Phase 01 placeholder → full Timeline Editor)
```

---

## Validation

- [ ] `/projects/{id}` loads the full Timeline Editor (NOT the Phase 01 placeholder).
- [ ] Loading skeleton shown while fetching project data.
- [ ] Error state with retry button shown on fetch failure.
- [ ] Header shows "StoryFlow — {title}" and "Back to Dashboard" link.
- [ ] Left sidebar shows project title, status badge, segment count, created date.
- [ ] Center panel renders the `Timeline` component with all segments.
- [ ] Bottom action bar has disabled "Generate All Audio" button with Phase 03 tooltip.
- [ ] Bottom action bar has disabled "Export Video" button with Phase 04 tooltip.
- [ ] `reset()` called on unmount to clear Zustand state.
- [ ] Page is a client component (`"use client"` directive).

---

## Notes

- This **replaces** the Phase 01 placeholder entirely — the simple "Project: {id}" text is deleted.
- The page must be a client component because it uses Zustand hooks, `useEffect`, and `useParams`.
- The sidebar width is fixed (≈250px / `w-64`), the center panel fills remaining space with `flex-1`.
- Export button is a disabled placeholder for Phase 05.

---

> **Parent:** [SubPhase_02_03_Overview.md](./SubPhase_02_03_Overview.md) (Layer 2)
> **Phase:** [Phase_02_Overview.md](../Phase_02_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_02_03_06_Build_Timeline_Wrapper.md](./Task_02_03_06_Build_Timeline_Wrapper.md)
> **Next Task:** [Task_02_03_08_Add_Lock_Toggle_Feature.md](./Task_02_03_08_Add_Lock_Toggle_Feature.md)
