# Task 02.03.08 — Add Lock Toggle Feature

> **Sub-Phase:** 02.03 — Image Upload & Timeline Editor UI
> **Phase:** Phase 02 — The Logic
> **Complexity:** Low
> **Dependencies:** Task 02.03.05 (SegmentCard)
> **Parent Document:** [SubPhase_02_03_Overview.md](./SubPhase_02_03_Overview.md)

---

## Objective

Implement the lock/unlock toggle button on `SegmentCard` that toggles `is_locked` via the Zustand store's optimistic update, disabling text editing and image operations when locked.

---

## Instructions

### Step 1 — Add lock toggle button in SegmentCard header

In `frontend/components/SegmentCard.tsx`, add a lock toggle button in the header row (right side, before the delete button).

### Step 2 — Implement toggle logic

```typescript
import { Lock, LockOpen } from 'lucide-react';

const handleLockToggle = () => {
  onUpdate(segment.id, { is_locked: !segment.is_locked });
};
```

### Step 3 — Render the button with visual states

```tsx
<Tooltip>
  <TooltipTrigger asChild>
    <Button variant="ghost" size="icon" onClick={handleLockToggle}>
      {segment.is_locked
        ? <Lock className="h-4 w-4" />
        : <LockOpen className="h-4 w-4 text-muted-foreground" />
      }
    </Button>
  </TooltipTrigger>
  <TooltipContent>
    {segment.is_locked ? 'Unlock segment' : 'Lock segment'}
  </TooltipContent>
</Tooltip>
```

### Step 4 — Ensure child components respect lock state

Verify that when `segment.is_locked` is `true`:
- `SegmentTextEditor` textarea is disabled.
- `ImageUploader` upload/remove is disabled.
- Only the lock toggle itself and the delete button remain functional.

---

## Expected Output

```
frontend/
└── components/
    └── SegmentCard.tsx         ← MODIFIED (lock toggle added)
```

---

## Validation

- [ ] Lock button toggles between 🔒 (locked) and 🔓 (unlocked) icons.
- [ ] Toggle calls `onUpdate` with `{ is_locked: !current }` — optimistic via store.
- [ ] Locked segments disable text editor and image upload.
- [ ] Lock toggle itself still works on locked segments (to unlock).
- [ ] Delete button still works on locked segments.
- [ ] Tooltip shows "Lock segment" / "Unlock segment" on hover.

---

## Notes

- The lock state flows: `segment.is_locked` (Zustand store) → SegmentCard → child components.
- The backend also enforces the lock in SubPhase 02.02's PATCH handler — the frontend respects it for UX (disabled states).
- Deletion is still allowed on locked segments (design decision from SubPhase 02.02).

---

> **Parent:** [SubPhase_02_03_Overview.md](./SubPhase_02_03_Overview.md) (Layer 2)
> **Phase:** [Phase_02_Overview.md](../Phase_02_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_02_03_07_Build_Timeline_Editor_Page.md](./Task_02_03_07_Build_Timeline_Editor_Page.md)
> **Next Task:** [Task_02_03_09_Add_Delete_Segment_With_Confirm.md](./Task_02_03_09_Add_Delete_Segment_With_Confirm.md)
