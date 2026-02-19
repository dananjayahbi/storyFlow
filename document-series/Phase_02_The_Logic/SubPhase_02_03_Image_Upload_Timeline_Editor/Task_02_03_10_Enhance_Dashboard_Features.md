# Task 02.03.10 — Enhance Dashboard Features

> **Sub-Phase:** 02.03 — Image Upload & Timeline Editor UI
> **Phase:** Phase 02 — The Logic
> **Complexity:** Medium
> **Dependencies:** None (independent track)
> **Parent Document:** [SubPhase_02_03_Overview.md](./SubPhase_02_03_Overview.md)

---

## Objective

Improve the dashboard page with segment count display on project cards, better formatting, visual distinction between imported and empty projects, and post-import navigation to the timeline.

---

## Instructions

### Step 1 — Display segment count on ProjectCard

In `frontend/components/ProjectCard.tsx`, show the number of segments for each project. Derive the count from the project's data:

- If the API response includes segments or a count field, use it directly.
- Otherwise, display a derived count from the project detail response (e.g., `project.segments?.length`).

```tsx
<p className="text-sm text-muted-foreground">
  {segmentCount} segment{segmentCount !== 1 ? 's' : ''}
</p>
```

### Step 2 — Improve project card layout

- Add a status badge: `DRAFT` with an appropriate color (e.g., `bg-yellow-100 text-yellow-800`).
- Format the created date: `new Date(project.created_at).toLocaleDateString()`.
- Visual distinction: projects with segments show a filled indicator; empty projects show muted styling.

### Step 3 — Post-import navigation

In `frontend/app/page.tsx`, after successful import from `ImportDialog`:
- Navigate to the new project's timeline page using `router.push(`/projects/${newProject.id}`)`.
- Import `useRouter` from `next/navigation`.

### Step 4 — Post-delete toast

After project delete (implemented in Task 02.03.11), show a toast: "Project deleted successfully."

```typescript
import { useToast } from '@/components/ui/use-toast';

const { toast } = useToast();
toast({ title: 'Project deleted', description: 'Project and all media removed.' });
```

---

## Expected Output

```
frontend/
├── app/
│   └── page.tsx                ← MODIFIED (navigation, toast)
└── components/
    └── ProjectCard.tsx         ← MODIFIED (segment count, styling)
```

---

## Validation

- [ ] Each ProjectCard displays the segment count.
- [ ] Status badge shows "DRAFT" with styled color.
- [ ] Created date is formatted (not raw ISO string).
- [ ] After import, browser navigates to `/projects/{id}`.
- [ ] Visual distinction between projects with and without segments.

---

## Notes

- Keep changes minimal — the dashboard was already functional from SubPhase 01.03 and 02.01.
- Focus on polish and user experience improvements.
- The project list uses `getProjects()` from `api.ts` (already implemented).

---

> **Parent:** [SubPhase_02_03_Overview.md](./SubPhase_02_03_Overview.md) (Layer 2)
> **Phase:** [Phase_02_Overview.md](../Phase_02_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_02_03_09_Add_Delete_Segment_With_Confirm.md](./Task_02_03_09_Add_Delete_Segment_With_Confirm.md)
> **Next Task:** [Task_02_03_11_Add_Project_Delete_To_Dashboard.md](./Task_02_03_11_Add_Project_Delete_To_Dashboard.md)
