# Task 02.03.09 — Add Delete Segment with Confirm

> **Sub-Phase:** 02.03 — Image Upload & Timeline Editor UI
> **Phase:** Phase 02 — The Logic
> **Complexity:** Medium
> **Dependencies:** Task 02.03.05 (SegmentCard)
> **Parent Document:** [SubPhase_02_03_Overview.md](./SubPhase_02_03_Overview.md)

---

## Objective

Implement the delete segment button on `SegmentCard` with a Shadcn `AlertDialog` confirmation dialog that prevents accidental deletions.

---

## Instructions

### Step 1 — Add delete button in SegmentCard header

In `frontend/components/SegmentCard.tsx`, add a delete button in the header row (right side, after the lock toggle).

### Step 2 — Implement with AlertDialog

```typescript
import { Trash2 } from 'lucide-react';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel,
  AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
```

### Step 3 — Render the confirmation dialog

```tsx
<AlertDialog>
  <AlertDialogTrigger asChild>
    <Button variant="ghost" size="icon" className="text-destructive">
      <Trash2 className="h-4 w-4" />
    </Button>
  </AlertDialogTrigger>
  <AlertDialogContent>
    <AlertDialogHeader>
      <AlertDialogTitle>Delete Segment</AlertDialogTitle>
      <AlertDialogDescription>
        Are you sure you want to delete Segment #{segment.sequence_index + 1}?
        This action cannot be undone. Any uploaded images will also be removed.
      </AlertDialogDescription>
    </AlertDialogHeader>
    <AlertDialogFooter>
      <AlertDialogCancel>Cancel</AlertDialogCancel>
      <AlertDialogAction
        onClick={() => onDelete(segment.id)}
        className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
      >
        Delete
      </AlertDialogAction>
    </AlertDialogFooter>
  </AlertDialogContent>
</AlertDialog>
```

### Step 4 — Handle loading state

Optionally show a loading spinner on the "Delete" button during the API call using local `isDeleting` state.

---

## Expected Output

```
frontend/
└── components/
    └── SegmentCard.tsx         ← MODIFIED (delete button + dialog added)
```

---

## Validation

- [ ] Delete button (🗑️) visible in segment card header.
- [ ] Clicking opens `AlertDialog` with segment number in the message.
- [ ] "Cancel" closes dialog without deletion.
- [ ] "Delete" calls `onDelete(segment.id)` and segment disappears from timeline.
- [ ] Button styled with destructive variant (red tint).
- [ ] Shadcn AlertDialog handles keyboard focus trapping automatically.

---

## Notes

- Segment deletion is irreversible — it also deletes associated images from disk via the backend.
- The confirmation text includes the segment number for clarity.
- After deletion, remaining segments keep their `sequence_index` values (no auto-reindexing). Display order is maintained.

---

> **Parent:** [SubPhase_02_03_Overview.md](./SubPhase_02_03_Overview.md) (Layer 2)
> **Phase:** [Phase_02_Overview.md](../Phase_02_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_02_03_08_Add_Lock_Toggle_Feature.md](./Task_02_03_08_Add_Lock_Toggle_Feature.md)
> **Next Task:** [Task_02_03_10_Enhance_Dashboard_Features.md](./Task_02_03_10_Enhance_Dashboard_Features.md)
