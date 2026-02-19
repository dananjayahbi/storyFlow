# Task 01.03.08 — Build Create Project Dialog

## Metadata

| Field                    | Value                                                                                               |
| ------------------------ | --------------------------------------------------------------------------------------------------- |
| **Sub-Phase**            | SubPhase 01.03 — Dashboard UI & Basic API                                                           |
| **Phase**                | Phase 01 — The Skeleton                                                                             |
| **Document Type**        | Layer 3 — Task Document                                                                             |
| **Estimated Complexity** | Medium                                                                                              |
| **Dependencies**         | [Task_01_03_03](Task_01_03_03_Setup_Frontend_API_Client.md), [Task_01_03_04](Task_01_03_04_Define_TypeScript_Interfaces.md) |
| **Parent Document**      | [SubPhase_01_03_Overview.md](SubPhase_01_03_Overview.md) (Layer 2, §5.8)                            |

---

## Objective

Create the `CreateProjectDialog` component with a form containing a title input, submission via the API client, loading/error states, and a callback to notify the parent when a project is created.

---

## Instructions

### Step 1: Create `CreateProjectDialog.tsx`

Create `frontend/components/CreateProjectDialog.tsx`:

```tsx
'use client';

import { useState } from 'react';
import { createProject } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';

interface CreateProjectDialogProps {
  onProjectCreated: () => void;
}

export function CreateProjectDialog({ onProjectCreated }: CreateProjectDialogProps) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!title.trim()) return;

    try {
      setLoading(true);
      setError(null);
      await createProject({ title: title.trim() });
      setTitle('');
      setOpen(false);
      onProjectCreated();
    } catch (err) {
      setError('Failed to create project. Please try again.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>Create Project</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create New Project</DialogTitle>
          <DialogDescription>
            Enter a title for your new video project.
          </DialogDescription>
        </DialogHeader>
        <div className="py-4">
          <Input
            placeholder="Project title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && title.trim()) {
                handleSubmit();
              }
            }}
            disabled={loading}
          />
          {error && (
            <p className="text-sm text-destructive mt-2">{error}</p>
          )}
        </div>
        <DialogFooter>
          <Button
            onClick={handleSubmit}
            disabled={!title.trim() || loading}
          >
            {loading ? 'Creating...' : 'Create'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

---

## Expected Output

```
frontend/components/
├── ProjectCard.tsx            ← Task 01.03.07
├── CreateProjectDialog.tsx    ← NEW
└── ui/                        ← Existing (Shadcn/UI components)
```

---

## Validation

- [ ] `frontend/components/CreateProjectDialog.tsx` exists.
- [ ] `'use client'` directive is at the top.
- [ ] Component accepts `onProjectCreated: () => void` prop.
- [ ] Dialog is controlled via `open` / `setOpen` state.
- [ ] Title input is a controlled component via `useState`.
- [ ] "Create" button is disabled when title is empty or whitespace-only.
- [ ] "Create" button is disabled during loading.
- [ ] Button text changes to "Creating..." during submission.
- [ ] Enter key submits the form when title is valid.
- [ ] On success: dialog closes, title resets, `onProjectCreated()` is called.
- [ ] On error: inline error message is shown below the input.
- [ ] `DialogTrigger` wraps a `Button` with text "Create Project".

---

## Notes

- The dialog uses **controlled state** (`open`/`setOpen`) rather than uncontrolled behavior. This allows programmatic closing after successful submission.
- The `onKeyDown` handler enables Enter-key submission for better UX.
- Error state is reset on each new submission attempt (`setError(null)` at start of `handleSubmit`).
- The title is trimmed before submission to prevent whitespace-only titles.
- The component is self-contained — it includes its own trigger button. The parent page simply renders `<CreateProjectDialog onProjectCreated={handleProjectCreated} />` wherever a trigger is needed.

---

> **Parent:** [SubPhase_01_03_Overview.md](SubPhase_01_03_Overview.md) (Layer 2)
> **Previous Task:** [Task_01_03_07_Build_ProjectCard_Component.md](Task_01_03_07_Build_ProjectCard_Component.md)
> **Next Task:** [Task_01_03_09_Create_Placeholder_Timeline_Page.md](Task_01_03_09_Create_Placeholder_Timeline_Page.md)
