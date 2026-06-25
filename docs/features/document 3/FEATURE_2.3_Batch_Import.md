# Feature 2.3 — Batch Import (Multiple Stories)

| Field | Value |
|---|---|
| **Feature ID** | 2.3 |
| **Title** | Batch Import (Multiple Stories) |
| **Status** | 🟡 Planned |
| **Priority** | High |
| **Complexity** | Low |
| **Estimated Effort** | 1 day |
| **Dependencies** | Existing `POST /api/projects/import/` endpoint, `ImportDialog.tsx` |
| **Output Files (NEW)** | `frontend/components/BatchImportDialog.tsx` |
| **Files Modified** | `frontend/components/ImportDialog.tsx`, `frontend/app/projects/page.tsx` |

---

## 1. Document Overview

### 1.1 Problem Statement

The current import workflow in `ImportDialog.tsx` accepts exactly one JSON file per interaction. A content creator who has prepared 50 or 100 story scripts must repeat the full import flow — open dialog, browse file, confirm, close — for every single file. This creates a severe usability bottleneck that makes StoryFlow impractical for bulk content pipelines. There is no way at present to import an entire batch of scripts in one action.

### 1.2 Proposed Solution

Introduce a dedicated `BatchImportDialog.tsx` component that enables multi-file selection and automates sequential API calls to the existing import endpoint, showing live progress throughout.

- Support multiple file selection via the HTML file input's `multiple` attribute, allowing users to select dozens of JSON files in a single browser dialog.
- After file selection, render a preview table in the dialog listing each file with its detected project name (read from the JSON `name` or `title` field client-side before any upload occurs) and its segment count.
- Provide a "Remove" control next to each file entry so the user can deselect individual files from the batch before committing.
- On confirm, iterate over the selected files sequentially using an async loop — call `POST /api/projects/import/` once per file and track a running count displayed as "3 of 12 imported…".
- Show a final summary toast notification on completion: "12 projects imported successfully" accompanied by a "View Projects" link that navigates to the projects list page.
- Keep the existing single-file `ImportDialog.tsx` unchanged for users who prefer importing one file at a time; surface the batch option as an additional "Batch Import" button or tab on the projects page.

### 1.3 Scope

| Category | Item |
|---|---|
| **In Scope** | Multi-file selection via browser file input |
| **In Scope** | Client-side JSON preview before upload |
| **In Scope** | Sequential upload loop with live progress indicator |
| **In Scope** | Summary toast on batch completion |
| **Out of Scope** | Folder/directory drag-and-drop (browser limitation) |
| **Out of Scope** | Parallel concurrent uploads (sequential is sufficient and avoids race conditions) |
| **Out of Scope** | Any backend API changes — the existing endpoint is reused as-is |
| **Out of Scope** | File format validation beyond what the existing import endpoint already performs |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| `frontend/components/ImportDialog.tsx` | Original single-file import modal | Accepts one file; has basic JSON validation |
| `frontend/app/projects/page.tsx` | Projects list page | Has button to open existing ImportDialog |
| `frontend/components/BatchImportDialog.tsx` | New multi-file import modal | Does not exist yet |
| `frontend/store/projectStore.ts` | Zustand store holding project list state | Has `fetchProjects()` action to refresh list |
| `frontend/lib/api.ts` | API utility functions | Contains `importProject(file)` helper |

---

## 2. Flow Diagram

```
User on Projects Page
        |
        v
  [Batch Import] button clicked
        |
        v
  BatchImportDialog opens
        |
        v
  User selects multiple JSON files
  via <input type="file" multiple>
        |
        v
  Client reads each file → extracts
  project name + segment count
        |
        v
  Preview table rendered
  [File Name | Project Name | Segments | Remove]
        |
        v
  User clicks [Confirm Import]
        |
        +-----> for each file:
        |         POST /api/projects/import/
        |         progress: "N of M imported…"
        |
        v
  All calls complete
        |
        v
  Toast: "M projects imported successfully"
  [View Projects] link → /projects
        |
        v
  projectStore.fetchProjects() called
  → Projects list refreshed
```

---

## 3. Step-by-Step Instructions

### Step 3.1 — Add "Batch Import" Trigger to Projects Page

File: `frontend/app/projects/page.tsx`
Function/component: `ProjectsPage` (default export)

Add a secondary "Batch Import" button alongside the existing "Import Story" button in the page header toolbar. This button sets a local state variable `isBatchDialogOpen` to `true`. Wire the `BatchImportDialog` component's `open` and `onClose` props to this state. Import `BatchImportDialog` at the top of the file.

### Step 3.2 — Create BatchImportDialog Component (Shell)

File: `frontend/components/BatchImportDialog.tsx`
Component: `BatchImportDialog`

Create the component shell accepting props: `open: boolean` and `onClose: () => void`. Inside, render a ShadCN `Dialog` containing a title "Batch Import Stories", a file input configured with `multiple` and `accept=".json"`, and placeholder sections for the preview table and confirm button. Use a `files` state variable (array of `File`) updated by the file input's `onChange` handler.

### Step 3.3 — Implement Client-Side JSON Preview

File: `frontend/components/BatchImportDialog.tsx`
Function: `parseFilePreviews`

After file selection, read each `File` using `FileReader` or the `text()` method and parse the JSON. Extract the project name from the top-level `name` or `title` field (fall back to the filename without extension if neither field exists). Count the items in the `segments` array. Store the results as an array of `{fileName, projectName, segmentCount, file}` objects in a `previews` state variable. Render the previews in a table with a remove button per row that splices the entry out of the `previews` array.

### Step 3.4 — Implement Sequential Upload Loop with Progress

File: `frontend/components/BatchImportDialog.tsx`
Function: `handleConfirmImport`

On confirm button click, set `isImporting` to `true` and iterate over `previews` using a `for…of` loop. On each iteration, call the existing `importProject(file)` API helper from `lib/api.ts`, increment a `completed` counter, and update a `progress` state string formatted as "N of M imported…". Wrap each call in a try/catch and collect errors into a `failedFiles` array. After the loop finishes, call `projectStore.fetchProjects()`, show a toast with the total success count and any failures, then call `onClose()`.

### Step 3.5 — Wire Progress UI and Summary Toast

File: `frontend/components/BatchImportDialog.tsx`
Component: inline progress display

While `isImporting` is true, show the progress string and disable the confirm button. Use ShadCN's `toast` utility (or the existing toast wrapper in the project) to fire the summary notification after completion. The toast message should read "X projects imported successfully" for a full success, or "X imported, Y failed" when some files errored. Provide a `View Projects` action button in the toast that calls `router.push('/projects')`.

---

## 4. Expected Outcome

1. A "Batch Import" button appears on the Projects page alongside the existing single-file import button.
2. Clicking it opens the `BatchImportDialog` where the user can select multiple JSON files in one browser file-picker action.
3. A preview table immediately shows each file's detected project name and segment count before any upload begins.
4. Individual rows can be removed from the batch before confirming.
5. On confirm, a live progress indicator counts through each file as it is uploaded to the backend.
6. A summary toast appears on completion and the projects list is automatically refreshed.
7. The existing single-file `ImportDialog.tsx` remains fully functional and unchanged for users who do not need batch imports.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] `parseFilePreviews` correctly extracts `name`, `title`, or filename fallback from varied JSON structures.
- [ ] `parseFilePreviews` returns the correct segment count when `segments` array has N items.
- [ ] Removing a row from the preview table splices only that entry from the `previews` state.
- [ ] `handleConfirmImport` calls `importProject` exactly once per remaining preview entry.
- [ ] Failed individual imports are collected in `failedFiles` and do not abort the remaining loop.

### 5.2 Integration / Manual Tests

- [ ] Select 5 valid JSON story files → preview table shows all 5 with correct names and counts.
- [ ] Remove 2 files from the preview → confirm → only 3 projects are created in the backend.
- [ ] Simulate a network error on file 3 of 5 → remaining files still upload; toast reports "4 imported, 1 failed".
- [ ] After batch completes, the Projects page list is updated without a manual page refresh.
- [ ] Opening `BatchImportDialog` and immediately closing without selecting files causes no errors.

### 5.3 Regression Tests

- [ ] The existing `ImportDialog.tsx` single-file import still works correctly and is unaffected.
- [ ] The `POST /api/projects/import/` backend endpoint behavior is unchanged for single-file calls.
- [ ] Project list page renders correctly when there are zero projects (empty state not broken by new button).

---

## 6. Notes for AI Agent

- Do not modify the existing `ImportDialog.tsx` component; create `BatchImportDialog.tsx` as a sibling file and import it separately from the projects page.
- The backend requires no changes — the loop over files happens entirely client-side by calling the existing endpoint once per file.
- Read file contents using the browser `File.text()` async method (already available in all modern browsers) rather than the older callback-based `FileReader` API to keep the async preview logic cleaner.
- The `importProject` API helper in `lib/api.ts` should already accept a `File` object (matching what `ImportDialog.tsx` uses); reuse it directly without modification.
- Use ShadCN `Dialog`, `Table`, `Button`, and `Progress` (or a simple text counter) for the UI — avoid introducing new UI dependencies beyond what the project already uses.
