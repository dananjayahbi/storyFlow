# Task 01.03.06 — Build Dashboard Page

## Metadata

| Field                    | Value                                                                                                                      |
| ------------------------ | -------------------------------------------------------------------------------------------------------------------------- |
| **Sub-Phase**            | SubPhase 01.03 — Dashboard UI & Basic API                                                                                  |
| **Phase**                | Phase 01 — The Skeleton                                                                                                    |
| **Document Type**        | Layer 3 — Task Document                                                                                                    |
| **Estimated Complexity** | High                                                                                                                       |
| **Dependencies**         | [Task_01_03_03](Task_01_03_03_Setup_Frontend_API_Client.md), [Task_01_03_04](Task_01_03_04_Define_TypeScript_Interfaces.md), [Task_01_03_05](Task_01_03_05_Build_Root_Layout.md), [Task_01_03_07](Task_01_03_07_Build_ProjectCard_Component.md), [Task_01_03_08](Task_01_03_08_Build_Create_Project_Dialog.md) |
| **Parent Document**      | [SubPhase_01_03_Overview.md](SubPhase_01_03_Overview.md) (Layer 2, §5.6)                                                  |

---

## Objective

Build the main dashboard page that fetches the project list from the backend, displays projects in a responsive grid via `ProjectCard` components, shows an empty state when no projects exist, and integrates the `CreateProjectDialog`.

---

## Instructions

### Step 1: Replace `app/page.tsx`

Open `frontend/app/page.tsx` and replace the default Next.js content:

```tsx
'use client';

import { useState, useEffect } from 'react';
import { getProjects } from '@/lib/api';
import { Project } from '@/lib/types';
import { ProjectCard } from '@/components/ProjectCard';
import { CreateProjectDialog } from '@/components/CreateProjectDialog';
import { Button } from '@/components/ui/button';

export default function DashboardPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchProjects = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getProjects();
      setProjects(data.results);
    } catch (err) {
      setError('Failed to load projects. Is the backend server running?');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProjects();
  }, []);

  const handleProjectCreated = () => {
    fetchProjects();
  };

  if (loading) {
    return <p className="text-muted-foreground">Loading projects...</p>;
  }

  if (error) {
    return <p className="text-destructive">{error}</p>;
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h2 className="text-3xl font-bold">Projects</h2>
        <CreateProjectDialog onProjectCreated={handleProjectCreated} />
      </div>

      {projects.length === 0 ? (
        <div className="text-center py-16">
          <p className="text-muted-foreground text-lg mb-4">
            No projects yet. Create your first project!
          </p>
          <CreateProjectDialog onProjectCreated={handleProjectCreated} />
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {projects.map((project) => (
            <ProjectCard key={project.id} project={project} />
          ))}
        </div>
      )}
    </div>
  );
}
```

---

### Step 2: Verify Rendering States

The page must handle three states:

| State        | Condition            | Display                                          |
| ------------ | -------------------- | ------------------------------------------------ |
| Loading      | `loading === true`   | "Loading projects..." text                       |
| Error        | `error !== null`     | Error message in red                             |
| Empty        | `projects.length === 0` | Empty state with CTA to create project       |
| Has projects | `projects.length > 0`| Responsive grid of `ProjectCard` components      |

---

## Expected Output

```
frontend/app/page.tsx   ← MODIFIED (replaced default content)
```

---

## Validation

- [ ] `'use client'` directive is at the top of the file.
- [ ] `useState` manages `projects`, `loading`, and `error` state.
- [ ] `useEffect` calls `fetchProjects()` on mount.
- [ ] `getProjects()` result is accessed via `data.results` (paginated format).
- [ ] Loading state shows "Loading projects..." text.
- [ ] Error state shows an error message.
- [ ] Empty state shows a message and a "Create Project" CTA.
- [ ] Project grid uses responsive columns: 1 col on mobile, 2 on medium, 3 on large.
- [ ] `handleProjectCreated` callback refetches the project list.
- [ ] `ProjectCard` receives `project` prop with `key={project.id}`.

---

## Notes

- This is a `'use client'` component because it uses React hooks (`useState`, `useEffect`). Next.js Server Components cannot use hooks or make browser API calls.
- The `CreateProjectDialog` component appears twice: once in the header area (always visible) and once in the empty state (as a CTA). Both call the same `handleProjectCreated` callback.
- The refetch strategy is simple: call `getProjects()` again after mutation. No optimistic updates, no cache invalidation — just a fresh API call.
- This page depends on `ProjectCard` (Task 01.03.07) and `CreateProjectDialog` (Task 01.03.08). Those components must exist before this page compiles.

---

> **Parent:** [SubPhase_01_03_Overview.md](SubPhase_01_03_Overview.md) (Layer 2)
> **Previous Task:** [Task_01_03_05_Build_Root_Layout.md](Task_01_03_05_Build_Root_Layout.md)
> **Next Task:** [Task_01_03_07_Build_ProjectCard_Component.md](Task_01_03_07_Build_ProjectCard_Component.md)
