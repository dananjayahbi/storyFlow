# Task 02.03.05 — Build SegmentCard Component

> **Sub-Phase:** 02.03 — Image Upload & Timeline Editor UI
> **Phase:** Phase 02 — The Logic
> **Complexity:** High
> **Dependencies:** Task 02.03.02, Task 02.03.03, Task 02.03.04
> **Parent Document:** [SubPhase_02_03_Overview.md](./SubPhase_02_03_Overview.md)

---

## Objective

Assemble the core `SegmentCard` composite component that combines SegmentTextEditor, ImageUploader, ImagePromptDisplay, action buttons (lock toggle, delete), and an audio placeholder.

---

## Instructions

### Step 1 — Create the component file

Create `frontend/components/SegmentCard.tsx`.

### Step 2 — Define props interface

```typescript
import type { Segment, UpdateSegmentPayload } from '@/lib/types';

interface SegmentCardProps {
  segment: Segment;
  onUpdate: (id: number, data: UpdateSegmentPayload) => Promise<void>;
  onDelete: (id: number) => Promise<void>;
  onUploadImage: (id: number, file: File) => Promise<void>;
  onRemoveImage: (id: number) => Promise<void>;
}
```

### Step 3 — Implement the card layout

Render a Shadcn `Card` (or styled `div`) with these sections in order:

**3a. Header Row** — Flex container:
- **Left:** Sequence number badge displaying `#${segment.sequence_index + 1}` (1-based).
- **Right:** Lock toggle button (placeholder — fully implemented in Task 02.03.08) and Delete button (placeholder — fully implemented in Task 02.03.09).

**3b. Text Content Area:**
```tsx
<SegmentTextEditor
  segmentId={segment.id}
  initialContent={segment.text_content}
  isLocked={segment.is_locked}
  onSave={onUpdate}
/>
```

**3c. Image + Prompt Row** — Two-column layout (flex or grid):
- Left column (~40%): `<ImageUploader>` with `currentImage={segment.image_file}`, `isLocked={segment.is_locked}`, `onUpload={onUploadImage}`, `onRemove={onRemoveImage}`.
- Right column (~60%): `<ImagePromptDisplay>` with `prompt={segment.image_prompt}`.

**3d. Separator** — Shadcn `<Separator />` between text area and image row.

**3e. Audio Placeholder:**
```tsx
<div className="rounded-md bg-muted/50 p-3 opacity-60">
  <p className="text-sm text-muted-foreground">
    🔊 Audio — Coming in Phase 03
  </p>
</div>
```

### Step 4 — Apply visual styling

- Subtle border, rounded corners, shadow (`border rounded-lg shadow-sm`).
- Padding: `p-4`.
- When locked: subtle visual indicator (e.g., `border-amber-300` or a semi-transparent overlay tint).

### Step 5 — Memoize for performance

Wrap the component with `React.memo` to prevent re-renders when sibling segments change:

```typescript
export const SegmentCard = React.memo(SegmentCardComponent);
```

---

## Expected Output

```
frontend/
└── components/
    └── SegmentCard.tsx         ← NEW
```

---

## Validation

- [ ] Card renders with correct 1-based sequence number badge.
- [ ] `SegmentTextEditor` renders with segment's text content.
- [ ] `ImageUploader` renders with segment's image state.
- [ ] `ImagePromptDisplay` renders with segment's image prompt.
- [ ] Audio placeholder shows "Audio — Coming in Phase 03" (disabled).
- [ ] Lock toggle and delete button positions are present (full logic in Tasks 08/09).
- [ ] Locked segments show visual distinction (border color or overlay).
- [ ] Component is wrapped with `React.memo`.

---

## Notes

- This component does NOT directly call API functions — it receives all callbacks via props from the parent.
- Lock toggle and delete button are initially placeholder buttons. Full implementations come in Tasks 02.03.08 and 02.03.09.
- The 1-based display index is computed from `segment.sequence_index + 1` (the model uses 0-based indexing).
- Audio placeholder is static — no functionality, just visual presence for Phase 03 readiness.

---

> **Parent:** [SubPhase_02_03_Overview.md](./SubPhase_02_03_Overview.md) (Layer 2)
> **Phase:** [Phase_02_Overview.md](../Phase_02_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_02_03_04_Build_ImagePromptDisplay.md](./Task_02_03_04_Build_ImagePromptDisplay.md)
> **Next Task:** [Task_02_03_06_Build_Timeline_Wrapper.md](./Task_02_03_06_Build_Timeline_Wrapper.md)
