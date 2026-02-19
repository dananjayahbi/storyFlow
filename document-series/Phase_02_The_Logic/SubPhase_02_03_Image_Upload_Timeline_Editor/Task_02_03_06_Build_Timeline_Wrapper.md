# Task 02.03.06 — Build Timeline Wrapper

> **Sub-Phase:** 02.03 — Image Upload & Timeline Editor UI
> **Phase:** Phase 02 — The Logic
> **Complexity:** Medium
> **Dependencies:** Task 02.03.05 (SegmentCard)
> **Parent Document:** [SubPhase_02_03_Overview.md](./SubPhase_02_03_Overview.md)

---

## Objective

Create the `Timeline` component that renders an ordered list of `SegmentCard` components inside a Shadcn `ScrollArea` with an empty-state fallback.

---

## Instructions

### Step 1 — Create the component file

Create `frontend/components/Timeline.tsx`.

### Step 2 — Define props interface

```typescript
import type { Segment, UpdateSegmentPayload } from '@/lib/types';

interface TimelineProps {
  segments: Segment[];
  onUpdateSegment: (id: number, data: UpdateSegmentPayload) => Promise<void>;
  onDeleteSegment: (id: number) => Promise<void>;
  onUploadImage: (id: number, file: File) => Promise<void>;
  onRemoveImage: (id: number) => Promise<void>;
}
```

### Step 3 — Implement the component

```typescript
'use client';

import { ScrollArea } from '@/components/ui/scroll-area';
import { SegmentCard } from './SegmentCard';

export function Timeline({
  segments, onUpdateSegment, onDeleteSegment, onUploadImage, onRemoveImage,
}: TimelineProps) {
  if (segments.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <p className="text-lg text-muted-foreground">No segments yet.</p>
        <p className="text-sm text-muted-foreground">
          Import a story to get started.
        </p>
      </div>
    );
  }

  return (
    <ScrollArea className="h-[calc(100vh-200px)]">
      <div className="space-y-4 p-4">
        {segments.map((segment) => (
          <SegmentCard
            key={segment.id}
            segment={segment}
            onUpdate={onUpdateSegment}
            onDelete={onDeleteSegment}
            onUploadImage={onUploadImage}
            onRemoveImage={onRemoveImage}
          />
        ))}
      </div>
    </ScrollArea>
  );
}
```

---

## Expected Output

```
frontend/
└── components/
    └── Timeline.tsx            ← NEW
```

---

## Validation

- [ ] Renders correct number of `SegmentCard` components.
- [ ] Cards keyed by `segment.id` (not array index).
- [ ] Vertical scroll via Shadcn `ScrollArea` with appropriate max height.
- [ ] Empty state shows "No segments yet. Import a story to get started." when no segments.
- [ ] Segments displayed in order (already sorted by `sequence_index` from the store).
- [ ] Spacing between cards (`space-y-4`).

---

## Notes

- The `key` prop must be `segment.id` for correct React reconciliation when segments are deleted or reordered.
- Segments are received already sorted from the Zustand store — no client-side sorting needed.
- The `ScrollArea` height uses `calc(100vh - 200px)` to account for header and action bar. Adjust if layout dimensions change.

---

> **Parent:** [SubPhase_02_03_Overview.md](./SubPhase_02_03_Overview.md) (Layer 2)
> **Phase:** [Phase_02_Overview.md](../Phase_02_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_02_03_05_Build_SegmentCard_Component.md](./Task_02_03_05_Build_SegmentCard_Component.md)
> **Next Task:** [Task_02_03_07_Build_Timeline_Editor_Page.md](./Task_02_03_07_Build_Timeline_Editor_Page.md)
