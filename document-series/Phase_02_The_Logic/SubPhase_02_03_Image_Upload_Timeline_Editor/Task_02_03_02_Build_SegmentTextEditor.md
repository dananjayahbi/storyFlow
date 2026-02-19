# Task 02.03.02 — Build SegmentTextEditor

> **Sub-Phase:** 02.03 — Image Upload & Timeline Editor UI
> **Phase:** Phase 02 — The Logic
> **Complexity:** Medium
> **Dependencies:** None
> **Parent Document:** [SubPhase_02_03_Overview.md](./SubPhase_02_03_Overview.md)

---

## Objective

Create a controlled textarea component with 500ms debounced auto-save, "Saving..." indicator, and lock-awareness.

---

## Instructions

### Step 1 — Create the component file

Create `frontend/components/SegmentTextEditor.tsx`.

### Step 2 — Define props interface

```typescript
interface SegmentTextEditorProps {
  segmentId: number;
  initialContent: string;
  isLocked: boolean;
  onSave: (id: number, data: { text_content: string }) => Promise<void>;
}
```

### Step 3 — Implement the component

```typescript
'use client';

import { useState, useEffect, useRef } from 'react';
import { Textarea } from '@/components/ui/textarea';

export function SegmentTextEditor({
  segmentId, initialContent, isLocked, onSave,
}: SegmentTextEditorProps) {
  const [text, setText] = useState(initialContent);
  const [isSaving, setIsSaving] = useState(false);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const lastSavedRef = useRef(initialContent);

  // Sync if initialContent changes externally (e.g., optimistic rollback)
  useEffect(() => {
    setText(initialContent);
    lastSavedRef.current = initialContent;
  }, [initialContent]);

  // Debounced auto-save
  useEffect(() => {
    if (text === lastSavedRef.current) return; // No change

    timerRef.current = setTimeout(async () => {
      setIsSaving(true);
      try {
        await onSave(segmentId, { text_content: text });
        lastSavedRef.current = text;
      } finally {
        setIsSaving(false);
      }
    }, 500);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [text, segmentId, onSave]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  return (
    <div className="space-y-1">
      <Textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        disabled={isLocked}
        rows={4}
        className="resize-y"
        placeholder="Segment text content..."
      />
      {isSaving && (
        <p className="text-xs text-muted-foreground">Saving...</p>
      )}
    </div>
  );
}
```

### Step 4 — Verify

```bash
cd frontend
npx tsc --noEmit
```

---

## Expected Output

```
frontend/
└── components/
    └── SegmentTextEditor.tsx   ← NEW
```

---

## Validation

- [ ] Textarea renders with `initialContent`.
- [ ] Local state updates on typing without immediate API calls.
- [ ] Auto-save fires after 500ms of inactivity.
- [ ] No save if text hasn't changed from last saved value.
- [ ] "Saving..." text appears during the API call.
- [ ] Textarea is disabled when `isLocked` is `true`.
- [ ] Timer is cleared on unmount (no memory leaks).
- [ ] Syncs with external `initialContent` changes.

---

## Notes

- Use `useRef` for the timeout to persist across renders.
- Track the last saved value to skip redundant saves.
- Clear the timer in `useEffect` cleanup to prevent "state update on unmounted component" warnings.

---

> **Parent:** [SubPhase_02_03_Overview.md](./SubPhase_02_03_Overview.md) (Layer 2)
> **Phase:** [Phase_02_Overview.md](../Phase_02_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_02_03_01_Create_Zustand_Project_Store.md](./Task_02_03_01_Create_Zustand_Project_Store.md)
> **Next Task:** [Task_02_03_03_Build_ImageUploader_DragDrop.md](./Task_02_03_03_Build_ImageUploader_DragDrop.md)
