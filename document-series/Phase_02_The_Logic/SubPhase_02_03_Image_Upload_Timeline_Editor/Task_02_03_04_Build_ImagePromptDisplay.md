# Task 02.03.04 — Build ImagePromptDisplay

> **Sub-Phase:** 02.03 — Image Upload & Timeline Editor UI
> **Phase:** Phase 02 — The Logic
> **Complexity:** Low
> **Dependencies:** None
> **Parent Document:** [SubPhase_02_03_Overview.md](./SubPhase_02_03_Overview.md)

---

## Objective

Create a read-only display for the segment's image prompt with a "Copy to Clipboard" button and "Copied!" feedback.

---

## Instructions

### Step 1 — Create the component file

Create `frontend/components/ImagePromptDisplay.tsx`.

### Step 2 — Define props interface

```typescript
interface ImagePromptDisplayProps {
  prompt: string;
}
```

### Step 3 — Implement the component

```typescript
'use client';

import { useState } from 'react';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { Button } from '@/components/ui/button';
import { ClipboardCopy, Check } from 'lucide-react';

export function ImagePromptDisplay({ prompt }: ImagePromptDisplayProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(prompt);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!prompt) {
    return (
      <div className="rounded-md bg-muted p-3">
        <p className="text-sm font-medium text-muted-foreground">Image Prompt</p>
        <p className="text-sm italic text-muted-foreground">No image prompt</p>
      </div>
    );
  }

  return (
    <div className="rounded-md bg-muted p-3 space-y-2">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium">Image Prompt</p>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="ghost" size="icon" onClick={handleCopy}>
              {copied ? <Check className="h-4 w-4" /> : <ClipboardCopy className="h-4 w-4" />}
            </Button>
          </TooltipTrigger>
          <TooltipContent>
            {copied ? 'Copied!' : 'Copy prompt to clipboard'}
          </TooltipContent>
        </Tooltip>
      </div>
      <p className="text-sm font-mono">{prompt}</p>
    </div>
  );
}
```

---

## Expected Output

```
frontend/
└── components/
    └── ImagePromptDisplay.tsx  ← NEW
```

---

## Validation

- [ ] Prompt text renders in a styled read-only block.
- [ ] "Copy" button calls `navigator.clipboard.writeText(prompt)`.
- [ ] "Copied!" feedback shown for 2 seconds after copy.
- [ ] Empty prompt shows "No image prompt" placeholder in muted color.
- [ ] Tooltip shows "Copy prompt to clipboard" on hover.

---

## Notes

- `navigator.clipboard.writeText()` requires HTTPS or localhost — works in development.
- This component is purely presentational — no API calls.

---

> **Parent:** [SubPhase_02_03_Overview.md](./SubPhase_02_03_Overview.md) (Layer 2)
> **Phase:** [Phase_02_Overview.md](../Phase_02_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_02_03_03_Build_ImageUploader_DragDrop.md](./Task_02_03_03_Build_ImageUploader_DragDrop.md)
> **Next Task:** [Task_02_03_05_Build_SegmentCard_Component.md](./Task_02_03_05_Build_SegmentCard_Component.md)
