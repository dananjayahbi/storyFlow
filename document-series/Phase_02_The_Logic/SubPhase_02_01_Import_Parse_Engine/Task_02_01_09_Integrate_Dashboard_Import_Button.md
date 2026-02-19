# Task 02.01.09 — Integrate Dashboard Import Button

> **Sub-Phase:** 02.01 — Import & Parse Engine
> **Phase:** Phase 02 — The Logic
> **Complexity:** Medium
> **Dependencies:** Task 02.01.07 (ImportDialog Component)
> **Parent Document:** [SubPhase_02_01_Overview.md](./SubPhase_02_01_Overview.md)

---

## Objective

Add the "Import Story" option to the dashboard page, wire up the `ImportDialog` component, and extend the API client and TypeScript types with import-related functions and interfaces.

---

## Instructions

### Step 1 — Add import-related types to `frontend/lib/types.ts`

Add the `ImportProjectRequest` interface:

```typescript
export interface ImportProjectRequest {
  format: 'json' | 'text';
  title: string;
  segments?: Array<{ text_content: string; image_prompt: string }>;
  raw_text?: string;
}
```

- `segments` is required when `format === 'json'`.
- `raw_text` is required when `format === 'text'`.
- Both are optional at the type level; runtime validation is handled by the backend.

### Step 2 — Add `importProject` function to `frontend/lib/api.ts`

```typescript
import { ImportProjectRequest, Project } from './types';

export async function importProject(data: ImportProjectRequest): Promise<Project> {
  const response = await api.post('/projects/import/', data);
  return response.data;
}
```

- Uses the existing Axios instance (`api`) from Phase 01.
- Trailing slash is required (`/projects/import/`).
- Returns the full `Project` object (with nested segments) from the 201 response.

### Step 3 — Modify the dashboard page (`frontend/app/page.tsx`)

Add the Import button and ImportDialog to the existing dashboard:

1. **Import the component:**
   ```typescript
   import ImportDialog from '@/components/ImportDialog';
   ```

2. **Add state for the import dialog:**
   ```typescript
   const [showImportDialog, setShowImportDialog] = useState(false);
   ```

3. **Add the "Import Story" button** alongside the existing "Create Project" button:
   ```tsx
   <div className="flex gap-2">
     {/* Existing Create Project button */}
     <Button onClick={() => setShowCreateDialog(true)}>
       Create Project
     </Button>

     {/* New Import Story button */}
     <Button variant="outline" onClick={() => setShowImportDialog(true)}>
       Import Story
     </Button>
   </div>
   ```

4. **Place the ImportDialog component** in the page JSX:
   ```tsx
   <ImportDialog
     open={showImportDialog}
     onOpenChange={setShowImportDialog}
     onSuccess={(project) => {
       // Refresh the project list
       fetchProjects();
       // Optionally: navigate to the new project
     }}
   />
   ```

5. **Refresh behavior:** After successful import, call the existing `fetchProjects()` function (or equivalent) to re-fetch and display the updated project list. The new project should appear immediately.

### Step 4 — Layout approach

Use two separate buttons side-by-side (recommended):
- "Create Project" — existing behavior (opens `CreateProjectDialog`).
- "Import Story" — new button (opens `ImportDialog`).

This is simpler than a dropdown menu and keeps both actions equally visible.

---

## Expected Output

```
frontend/
├── lib/
│   ├── types.ts            ← MODIFIED (ImportProjectRequest added)
│   └── api.ts              ← MODIFIED (importProject function added)
├── app/
│   └── page.tsx            ← MODIFIED (Import button + ImportDialog added)
└── components/
    └── ImportDialog.tsx     ← (Already created in Task 07)
```

---

## Validation

- [ ] `ImportProjectRequest` type is defined in `lib/types.ts`.
- [ ] `importProject()` function exists in `lib/api.ts` and calls `POST /api/projects/import/`.
- [ ] Dashboard page shows an "Import Story" button alongside "Create Project".
- [ ] Clicking "Import Story" opens the ImportDialog.
- [ ] After successful import, the project list is refreshed and the new project appears.
- [ ] The `importProject()` function uses a trailing slash in the URL.
- [ ] TypeScript compiles without errors: `npx tsc --noEmit`.

---

## Notes

- The "Import Story" button uses `variant="outline"` to visually distinguish it from the primary "Create Project" button, but both are equally accessible.
- Navigation to the new project's timeline page after import is optional in this sub-phase (Timeline Editor is built in SubPhase 02.03).
- The `fetchProjects()` call in `onSuccess` ensures the dashboard is always in sync with the backend after import.

---

> **Parent:** [SubPhase_02_01_Overview.md](./SubPhase_02_01_Overview.md) (Layer 2)
> **Phase:** [Phase_02_Overview.md](../Phase_02_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_02_01_08_Add_TextArea_Toggle_UI.md](./Task_02_01_08_Add_TextArea_Toggle_UI.md)
> **Next Task:** [Task_02_01_10_Write_Frontend_Import_Tests.md](./Task_02_01_10_Write_Frontend_Import_Tests.md)
