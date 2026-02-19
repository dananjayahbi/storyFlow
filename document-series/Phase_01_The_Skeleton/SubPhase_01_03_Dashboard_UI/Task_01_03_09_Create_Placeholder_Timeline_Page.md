# Task 01.03.09 — Create Placeholder Timeline Page

## Metadata

| Field                    | Value                                                                                               |
| ------------------------ | --------------------------------------------------------------------------------------------------- |
| **Sub-Phase**            | SubPhase 01.03 — Dashboard UI & Basic API                                                           |
| **Phase**                | Phase 01 — The Skeleton                                                                             |
| **Document Type**        | Layer 3 — Task Document                                                                             |
| **Estimated Complexity** | Low                                                                                                 |
| **Dependencies**         | [Task_01_03_03](Task_01_03_03_Setup_Frontend_API_Client.md), [Task_01_03_04](Task_01_03_04_Define_TypeScript_Interfaces.md) |
| **Parent Document**      | [SubPhase_01_03_Overview.md](SubPhase_01_03_Overview.md) (Layer 2, §5.9)                            |

---

## Objective

Create a stub page at `/projects/[id]` that fetches the project detail from the API and displays the project title with a "Coming in Phase 02" placeholder message and a back-navigation link.

---

## Instructions

### Step 1: Create the Dynamic Route Page

Create `frontend/app/projects/[id]/page.tsx`:

```tsx
'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { getProject } from '@/lib/api';
import { ProjectDetail } from '@/lib/types';
import { Button } from '@/components/ui/button';

export default function TimelinePage() {
  const params = useParams();
  const id = params.id as string;
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchProject = async () => {
      try {
        setLoading(true);
        const data = await getProject(id);
        setProject(data);
      } catch (err) {
        setError('Failed to load project.');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchProject();
  }, [id]);

  if (loading) {
    return <p className="text-muted-foreground">Loading project...</p>;
  }

  if (error || !project) {
    return (
      <div>
        <p className="text-destructive mb-4">{error || 'Project not found.'}</p>
        <Link href="/">
          <Button variant="outline">Back to Dashboard</Button>
        </Link>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-8">
        <Link href="/">
          <Button variant="outline" size="sm">← Back to Dashboard</Button>
        </Link>
      </div>
      <h2 className="text-3xl font-bold mb-4">{project.title}</h2>
      <div className="rounded-lg border p-8 text-center">
        <p className="text-xl text-muted-foreground">
          Timeline Editor — Coming in Phase 02
        </p>
        <p className="text-sm text-muted-foreground mt-2">
          This page will contain the segment-by-segment editing interface.
        </p>
      </div>
    </div>
  );
}
```

---

## Expected Output

```
frontend/app/
├── page.tsx                    ← Dashboard (Task 01.03.06)
├── layout.tsx                  ← Root layout (Task 01.03.05)
├── globals.css
└── projects/
    └── [id]/
        └── page.tsx            ← NEW (placeholder timeline)
```

---

## Validation

- [ ] `frontend/app/projects/[id]/page.tsx` exists.
- [ ] `'use client'` directive is at the top.
- [ ] `useParams()` is imported from `next/navigation` (NOT `next/router`).
- [ ] `id` is extracted from params and used to call `getProject(id)`.
- [ ] Loading state shows "Loading project..." text.
- [ ] Error state shows error message and a "Back to Dashboard" link.
- [ ] Success state shows the project title as a heading.
- [ ] "Timeline Editor — Coming in Phase 02" placeholder message is displayed.
- [ ] "Back to Dashboard" button links to `/`.

---

## Notes

- **`useParams` from `next/navigation`** — In Next.js App Router, `useParams` comes from `next/navigation`, NOT `next/router`. Using the wrong import will cause runtime errors.
- This page is replaced entirely in Phase 02 with the full Timeline Editor UI. It serves only as a navigation target for `ProjectCard` links during Phase 01.
- The `[id]` folder name creates a dynamic route. Next.js will match `/projects/any-uuid-here` and make `any-uuid-here` available via `params.id`.
- The `id` dependency in `useEffect` ensures the page refetches if the route changes without unmounting.

---

> **Parent:** [SubPhase_01_03_Overview.md](SubPhase_01_03_Overview.md) (Layer 2)
> **Previous Task:** [Task_01_03_08_Build_Create_Project_Dialog.md](Task_01_03_08_Build_Create_Project_Dialog.md)
> **Next Task:** [Task_01_03_10_End_To_End_Integration_Test.md](Task_01_03_10_End_To_End_Integration_Test.md)
