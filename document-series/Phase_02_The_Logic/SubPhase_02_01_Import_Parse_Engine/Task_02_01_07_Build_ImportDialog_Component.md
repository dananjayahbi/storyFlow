# Task 02.01.07 — Build ImportDialog Component

> **Sub-Phase:** 02.01 — Import & Parse Engine
> **Phase:** Phase 02 — The Logic
> **Complexity:** High
> **Dependencies:** None (frontend-only; can be built in parallel with backend)
> **Parent Document:** [SubPhase_02_01_Overview.md](./SubPhase_02_01_Overview.md)

---

## Objective

Create the `ImportDialog.tsx` component — a modal dialog that lets users import stories in JSON or Text format. This is the primary frontend piece of the import pipeline.

---

## Instructions

### Step 1 — Create the component file

Create `frontend/components/ImportDialog.tsx`.

### Step 2 — Define the component interface

```typescript
import { Project } from '@/lib/types';

interface ImportDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: (project: Project) => void;
}
```

- `open` / `onOpenChange` — controlled dialog pattern (parent manages visibility).
- `onSuccess` — callback invoked with the created project on successful import.

### Step 3 — Implement component state

```typescript
const [format, setFormat] = useState<'json' | 'text'>('json');
const [title, setTitle] = useState('');
const [content, setContent] = useState('');
const [isSubmitting, setIsSubmitting] = useState(false);
const [errors, setErrors] = useState<Record<string, string[]> | null>(null);
```

### Step 4 — Build the dialog structure

Use Shadcn `Dialog`, `DialogContent`, `DialogHeader`, `DialogTitle`, `DialogFooter`, `Button`, `Input`:

1. **Dialog Header** — Title: "Import Story".
2. **Format Toggle** — Two `Button` components side-by-side:
   - "JSON" — `variant={format === 'json' ? 'default' : 'outline'}`.
   - "Text" — `variant={format === 'text' ? 'default' : 'outline'}`.
3. **Title Input** — Optional `Input` field for custom project title. Label: "Project Title".
4. **Content Textarea** — `<textarea>` styled with Tailwind, minimum 10 rows.
   - Placeholder changes based on selected format (see Step 5).
5. **Error Display** — Conditionally rendered below the textarea when `errors` is non-null. Show each error message in a red text block.
6. **Dialog Footer** — "Cancel" and "Import" buttons.
   - "Import" is disabled when `isSubmitting || content.trim() === ''`.

### Step 5 — Dynamic placeholder text

**JSON placeholder:**
```
{
  "title": "My Story",
  "segments": [
    {
      "text_content": "Your narration text...",
      "image_prompt": "Description of the image..."
    }
  ]
}
```

**Text placeholder:**
```
Text: Your narration text for segment 1...
Prompt: Description of the image for segment 1...
---
Text: Your narration text for segment 2...
Prompt: Description of the image for segment 2...
```

### Step 6 — Implement submission handler

```typescript
const handleSubmit = async () => {
  setIsSubmitting(true);
  setErrors(null);

  try {
    const payload: ImportProjectRequest = {
      format,
      title: title.trim() || 'Untitled Project',
      ...(format === 'json'
        ? { segments: JSON.parse(content).segments }
        : { raw_text: content }),
    };

    // If JSON format and content has a title, use it
    if (format === 'json') {
      try {
        const parsed = JSON.parse(content);
        if (parsed.title && !title.trim()) {
          payload.title = parsed.title;
        }
        payload.segments = parsed.segments;
      } catch {
        setErrors({ content: ['Invalid JSON format'] });
        setIsSubmitting(false);
        return;
      }
    }

    const project = await importProject(payload);
    onSuccess(project);
    onOpenChange(false);
  } catch (err: any) {
    if (err.response?.data) {
      setErrors(err.response.data);
    } else {
      setErrors({ general: ['Import failed. Please try again.'] });
    }
  } finally {
    setIsSubmitting(false);
  }
};
```

### Step 7 — Reset state on dialog close

```typescript
useEffect(() => {
  if (!open) {
    setFormat('json');
    setTitle('');
    setContent('');
    setErrors(null);
    setIsSubmitting(false);
  }
}, [open]);
```

When the dialog closes (via Cancel or successful import), ALL internal state resets to defaults.

### Step 8 — Key UX rules

| Rule | Detail |
|---|---|
| Format toggle does NOT clear content | User may switch to check formatting without losing input |
| Title field is optional | If left blank, use the JSON `title` field or default to "Untitled Project" |
| Import button disabled states | Empty content OR active submission |
| Error display | Backend errors shown below textarea in red |
| Controlled dialog | Parent manages `open` state via props |

---

## Expected Output

```
frontend/
└── components/
    └── ImportDialog.tsx     ← NEW
```

---

## Validation

- [ ] `ImportDialog.tsx` exists and exports a React component.
- [ ] Dialog opens and closes via `open` / `onOpenChange` props.
- [ ] Format toggle switches between JSON and Text modes.
- [ ] Placeholder text updates when format is toggled.
- [ ] "Import" button is disabled when textarea is empty.
- [ ] "Import" button is disabled while `isSubmitting` is true.
- [ ] Successful import calls `onSuccess` with the created project and closes the dialog.
- [ ] Backend errors are displayed below the textarea.
- [ ] "Cancel" closes the dialog without side effects.
- [ ] All state resets when dialog closes.

---

## Notes

- This component needs `importProject` from `lib/api.ts` and `ImportProjectRequest`/`Project` from `lib/types.ts`. Those are added in Task 02.01.09 — if building in parallel, use placeholder imports.
- For JSON format: the frontend pre-parses the JSON content to extract `segments` before sending. If JSON parsing fails client-side, show an error immediately without hitting the API.
- The `'use client'` directive is required at the top of the file (Next.js App Router).

---

> **Parent:** [SubPhase_02_01_Overview.md](./SubPhase_02_01_Overview.md) (Layer 2)
> **Phase:** [Phase_02_Overview.md](../Phase_02_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_02_01_06_Write_Import_Tests.md](./Task_02_01_06_Write_Import_Tests.md)
> **Next Task:** [Task_02_01_08_Add_TextArea_Toggle_UI.md](./Task_02_01_08_Add_TextArea_Toggle_UI.md)
