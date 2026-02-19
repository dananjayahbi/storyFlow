# Task 02.03.11 — Add Project Delete to Dashboard

> **Sub-Phase:** 02.03 — Image Upload & Timeline Editor UI
> **Phase:** Phase 02 — The Logic
> **Complexity:** Medium
> **Dependencies:** Task 02.03.10 (Dashboard Enhancements)
> **Parent Document:** [SubPhase_02_03_Overview.md](./SubPhase_02_03_Overview.md)

---

## Objective

Add the ability to delete a project from the dashboard via a confirmation dialog on `ProjectCard`, with cascade awareness messaging and parent list refresh.

---

## Instructions

### Step 1 — Add delete trigger to ProjectCard

In `frontend/components/ProjectCard.tsx`, add a delete button — either a small icon (e.g., `Trash2`) in the top-right corner or a `DropdownMenu` (three-dot menu) with a "Delete" option.

### Step 2 — Implement AlertDialog confirmation

```tsx
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel,
  AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from '@/components/ui/alert-dialog';

<AlertDialog>
  <AlertDialogTrigger asChild>
    <Button variant="ghost" size="icon"><Trash2 className="h-4 w-4" /></Button>
  </AlertDialogTrigger>
  <AlertDialogContent>
    <AlertDialogHeader>
      <AlertDialogTitle>Delete Project</AlertDialogTitle>
      <AlertDialogDescription>
        Are you sure you want to delete &quot;{project.title}&quot;?
        All segments and associated media will be permanently removed.
      </AlertDialogDescription>
    </AlertDialogHeader>
    <AlertDialogFooter>
      <AlertDialogCancel>Cancel</AlertDialogCancel>
      <AlertDialogAction
        onClick={handleDelete}
        className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
      >
        Delete
      </AlertDialogAction>
    </AlertDialogFooter>
  </AlertDialogContent>
</AlertDialog>
```

### Step 3 — Implement delete handler

```typescript
const handleDelete = async () => {
  await deleteProject(project.id);  // from api.ts
  onDelete(project.id);             // callback to parent
};
```

### Step 4 — Wire up in dashboard page

In `frontend/app/page.tsx`, pass an `onDelete` callback to each `ProjectCard`:

```tsx
const handleProjectDelete = (id: number) => {
  setProjects((prev) => prev.filter((p) => p.id !== id));
  toast({ title: 'Project deleted', description: 'Project and all media removed.' });
};

<ProjectCard
  project={project}
  onDelete={handleProjectDelete}
/>
```

---

## Expected Output

```
frontend/
├── app/
│   └── page.tsx                ← MODIFIED (onDelete callback)
└── components/
    └── ProjectCard.tsx         ← MODIFIED (delete button + AlertDialog)
```

---

## Validation

- [ ] Delete button/icon visible on each ProjectCard.
- [ ] Clicking opens AlertDialog with project title in the message.
- [ ] "Cancel" closes dialog without deletion.
- [ ] "Delete" calls `deleteProject(id)` and removes project from the list.
- [ ] Success toast shown after deletion.
- [ ] Destructive styling on the confirm button (red).

---

## Notes

- The `AlertDialog` is critical — project deletion cascades to ALL segments and media files (irreversible).
- The delete button could be a small icon in the top-right corner or behind a `DropdownMenu` (three-dot menu) — either approach is acceptable.
- The backend `perform_destroy` on `ProjectViewSet` (SubPhase 02.02) handles the cascade: `shutil.rmtree` for media, then `instance.delete()`.

---

> **Parent:** [SubPhase_02_03_Overview.md](./SubPhase_02_03_Overview.md) (Layer 2)
> **Phase:** [Phase_02_Overview.md](../Phase_02_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_02_03_10_Enhance_Dashboard_Features.md](./Task_02_03_10_Enhance_Dashboard_Features.md)
> **Next Task:** [Task_02_03_12_Install_New_Shadcn_Components.md](./Task_02_03_12_Install_New_Shadcn_Components.md)
