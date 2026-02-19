# Task 01.03.10 — End-to-End Integration Test

## Metadata

| Field                    | Value                                                                   |
| ------------------------ | ----------------------------------------------------------------------- |
| **Sub-Phase**            | SubPhase 01.03 — Dashboard UI & Basic API                               |
| **Phase**                | Phase 01 — The Skeleton                                                 |
| **Document Type**        | Layer 3 — Task Document                                                 |
| **Estimated Complexity** | Medium                                                                  |
| **Dependencies**         | All Tasks 01.03.01–01.03.09 must be complete                            |
| **Parent Document**      | [SubPhase_01_03_Overview.md](SubPhase_01_03_Overview.md) (Layer 2, §5.10)|

---

## Objective

Perform a structured manual verification of the complete end-to-end flow — frontend to backend and back — confirming all Phase 01 functionality works together correctly.

> **Note:** This is a verification-only task. No files are created or modified.

---

## Instructions

### Step 1: Start Both Servers

1. Start the Django backend:

   ```bash
   cd backend
   venv\Scripts\activate        # Windows
   python manage.py runserver
   ```

2. In a separate terminal, start the Next.js frontend:

   ```bash
   cd frontend
   npm run dev
   ```

3. Confirm: backend on `http://localhost:8000`, frontend on `http://localhost:3000`.

---

### Step 2: Test Empty State

1. Open `http://localhost:3000` in a browser.
2. Verify the dashboard loads without errors.
3. Verify the "StoryFlow" header appears.
4. Verify the empty state message appears: "No projects yet. Create your first project!"
5. Verify a "Create Project" button/CTA is visible.
6. Open browser DevTools (F12) → Console. Verify **no CORS errors**.

---

### Step 3: Test Project Creation

1. Click "Create Project" button.
2. Verify the dialog opens with a title input.
3. Verify the "Create" button is disabled when the input is empty.
4. Enter a title: "My First Video".
5. Click "Create" (or press Enter).
6. Verify:
   - No CORS errors in the console.
   - The dialog closes.
   - The new project appears in the project grid without page refresh.
   - The project card shows: title ("My First Video"), "DRAFT" badge, today's date, "0 segments".

---

### Step 4: Test Multiple Projects

1. Create 2–3 more projects with different titles.
2. Verify all projects appear in the grid.
3. Verify projects are ordered newest-first (most recently created at the top/left).

---

### Step 5: Test Project Navigation

1. Click on a `ProjectCard`.
2. Verify navigation to `/projects/{uuid}`.
3. Verify the placeholder page shows:
   - The project title as a heading.
   - "Timeline Editor — Coming in Phase 02" message.
   - "Back to Dashboard" button.

---

### Step 6: Test Back Navigation

1. Click "Back to Dashboard" on the timeline page.
2. Verify return to the dashboard with all projects still listed.

---

### Step 7: Test Backend API Directly

1. Navigate to `http://localhost:8000/api/` — verify DRF browsable API root renders.
2. Navigate to `http://localhost:8000/api/projects/` — verify paginated JSON with projects.
3. Test `POST` via browsable API: submit `{"title": "API Test"}` → verify 201 response.
4. Copy a project UUID from the list response.
5. Navigate to `http://localhost:8000/api/projects/{uuid}/` — verify detail response with `segments: []` and `output_path: null`.
6. Test `DELETE` via curl or browser — verify `405 Method Not Allowed`.

---

### Step 8: Test TypeScript Compilation

```bash
cd frontend
npx tsc --noEmit
```

Verify zero TypeScript errors.

---

### Step 9: Test Django System Check

```bash
cd backend
python manage.py check
```

Verify "System check identified no issues."

---

## Expected Output

No files created or modified. This task produces a **verified checklist**.

---

## Validation

### Backend API ✓
- [ ] `GET /api/projects/` returns 200 with paginated JSON.
- [ ] `POST /api/projects/` with `{"title": "..."}` returns 201.
- [ ] `GET /api/projects/{id}/` returns 200 with detail + empty `segments`.
- [ ] `DELETE /api/projects/{id}/` returns 405 Method Not Allowed.
- [ ] DRF browsable API renders correctly.
- [ ] CORS headers present in responses.

### Frontend UI ✓
- [ ] Dashboard loads without errors.
- [ ] Empty state shows message and CTA.
- [ ] "Create Project" dialog opens, validates, and submits.
- [ ] New project appears in list without page refresh.
- [ ] ProjectCard shows title, status badge, date, segment count.
- [ ] Clicking card navigates to `/projects/{id}`.
- [ ] Timeline placeholder shows project title and Phase 02 message.
- [ ] "Back to Dashboard" navigation works.

### Technical ✓
- [ ] No CORS errors in browser console.
- [ ] `npx tsc --noEmit` passes with zero errors.
- [ ] `python manage.py check` reports no issues.
- [ ] Both servers run simultaneously without port conflicts.

---

## Notes

- This is the **last task** in SubPhase 01.03 and the **last task in Phase 01**. Successful completion of this checklist means Phase 01 — The Skeleton is **COMPLETE**.
- Any failures should be traced back to the specific task (01.03.01–01.03.09) and fixed before marking Phase 01 as complete.
- After Phase 01 is complete, the project has a functioning full-stack skeleton: Django backend with models + API, Next.js frontend with dashboard + navigation, and working cross-origin communication.
- Phase 02 — The Logic — extends this skeleton with segment editing, import pipeline, and the timeline editor.

---

> **Parent:** [SubPhase_01_03_Overview.md](SubPhase_01_03_Overview.md) (Layer 2)
> **Phase:** [Phase_01_Overview.md](../../Phase_01_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../../00_Project_Overview.md) (Layer 0)
> **Previous Task:** [Task_01_03_09_Create_Placeholder_Timeline_Page.md](Task_01_03_09_Create_Placeholder_Timeline_Page.md)
> **Next Task:** None — SubPhase 01.03 Complete ✓ / Phase 01 Complete ✓
