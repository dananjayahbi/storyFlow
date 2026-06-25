# Feature 5.4 — Bulk Settings Apply

| Field | Value |
|---|---|
| Feature ID | 5.4 |
| Title | Bulk Settings Apply Across Projects |
| Status | 🟡 Planned |
| Priority | High |
| Complexity | Low |
| Estimated Effort | 2 days |
| Dependencies | Feature 2.1 (Project model with settings fields), Feature 2.2 (Project update endpoint) |
| Output Files (NEW) | `frontend/components/projects/BulkActionBar.tsx`, `frontend/components/projects/BulkSettingsPreviewPanel.tsx` |
| Files Modified | `backend/api/views.py`, `backend/api/urls.py`, `backend/api/serializers.py`, `frontend/app/projects/page.tsx`, `frontend/components/projects/ProjectCard.tsx` |

---

## 1. Document Overview

### 1.1 Problem Statement

When a creator decides to adopt a new branding standard — a different subtitle font, a new voice actor, an updated Ken Burns intensity, a refined transition style — they must apply that change to every project in their library individually. Each project requires navigating to its settings page, changing the same ten fields, and saving. For a creator with 100 projects, this means performing the exact same 10-click sequence 100 separate times, which is both error-prone and deeply tedious. There is currently no mechanism to propagate settings from one project to a group of target projects in a single operation, and no way to define a settings template that can be re-applied as standards evolve.

### 1.2 Proposed Solution

Add a multi-select mode to the projects grid and an action bar that allows the creator to pick a source project, preview which settings will be overwritten, and apply those settings to all selected projects with a single confirmed action.

- Add a "Select" toggle button to the toolbar of `frontend/app/projects/page.tsx` that activates multi-select mode; when active, each `ProjectCard` in the grid displays a visible checkbox overlay.
- Track selected project IDs in a local `useState` array within the projects page; ticking a `ProjectCard` checkbox adds or removes that project's ID from the selection array.
- When one or more projects are selected, render a `BulkActionBar` component anchored at the bottom of the viewport with three elements: an "Apply Settings From..." dropdown selector, an "Apply" button, and a "Cancel" button.
- The dropdown in the `BulkActionBar` is populated by fetching all project names from the existing `/api/projects/` endpoint; the creator selects one source project whose settings will be copied.
- After the creator picks a source project, render a `BulkSettingsPreviewPanel` above the bar showing a table of the settings fields that will be overwritten: subtitle font, voice ID, Ken Burns intensity, transition type, and resolution — with the current value and the incoming value side by side, and a checkbox per field allowing the creator to exclude specific fields.
- On confirm, send a `POST /api/projects/bulk-apply-settings/` request with the source project ID, the list of target project IDs, and the list of selected settings field names to overwrite.
- The backend view performs a single `Project.objects.filter(id__in=target_ids).update(...)` call per settings field, copies values from the source project's fields, and returns a success summary.

### 1.3 Scope

| Category | In Scope |
|---|---|
| Settings fields | `subtitle_settings`, `voice_id`, `zoom_intensity`, `transition_type`, `render_settings` (resolution/fps) |
| Selection UI | Checkbox overlay on ProjectCard in multi-select mode |
| Source options | Any existing project as source |
| Partial apply | Per-field checkboxes allow excluding specific fields from the bulk apply |

| Category | Out of Scope |
|---|---|
| Named profiles | Saving a named "settings profile" not tied to a project is a future feature |
| Asset copying | Bulk apply does not copy images, audio, or segments — settings fields only |
| Undo | No undo/rollback mechanism for bulk apply in this phase |
| Scheduled apply | No deferred or scheduled bulk apply |

### 1.4 Key Files Reference

| File | Role |
|---|---|
| `frontend/app/projects/page.tsx` | Add Select toggle, selection state, and `BulkActionBar` rendering |
| `frontend/components/projects/ProjectCard.tsx` | Add checkbox overlay when `selectionMode` prop is true |
| `frontend/components/projects/BulkActionBar.tsx` | New component: action bar with source dropdown and Apply button |
| `backend/api/views.py` | Add `BulkApplySettingsView` handling `POST /api/projects/bulk-apply-settings/` |
| `backend/api/serializers.py` | Add `BulkApplySettingsSerializer` for validating the request payload |

---

## 2. Flow Diagram

```
Projects Page — normal mode
         |
  User clicks "Select" button in toolbar
         |
         v
  Multi-select mode activates
  All ProjectCards show checkbox overlay
         |
  User ticks checkboxes on 5 projects
         |
         v
  BulkActionBar appears (bottom of screen)
  [Apply Settings From... ▼] [Apply] [Cancel]
         |
  User opens dropdown → picks "Episode 1"
         |
         v
  BulkSettingsPreviewPanel shows table:
  | Field           | Current       | Incoming      | Include |
  | subtitle_font   | Arial         | Cinzel        | [x]     |
  | voice_id        | af_bella      | am_adam       | [x]     |
  | zoom_intensity  | 0.05          | 0.08          | [x]     |
         |
  User unchecks zoom_intensity, clicks Apply
         |
         v
  POST /api/projects/bulk-apply-settings/
  { source_project_id: 1,
    target_project_ids: [2,3,4,5,6],
    settings_fields: ["subtitle_settings","voice_id"] }
         |
         v
  Backend fetches source Project fields
  Project.objects.filter(id__in=[2..6])
  .update(subtitle_settings=..., voice_id=...)
         |
         v
  Response: { updated_count: 5 }
  Toast: "Settings applied to 5 projects"
  Selection clears, normal mode resumes
```

---

## 3. Step-by-Step Instructions

### Step 1 — Add selection mode to `frontend/app/projects/page.tsx`

At the top of the projects page component, add two new pieces of state: a boolean `selectionMode` (default false) and an array of numbers `selectedIds` (default empty array). Add a "Select" button to the existing toolbar area at the top of the page; clicking it toggles `selectionMode`. When `selectionMode` becomes false, also clear `selectedIds` to reset any prior selection. Pass `selectionMode` and a callback `onToggleSelect(id: number)` as props to each `ProjectCard` rendered in the grid. The `onToggleSelect` callback adds the given ID to `selectedIds` if it is not present, or removes it if it is already present. When `selectedIds.length > 0` and `selectionMode` is true, render the `BulkActionBar` component positioned as a fixed bar at the bottom of the viewport, passing `selectedIds` as a prop.

### Step 2 — Add checkbox overlay to `ProjectCard.tsx`

In `frontend/components/projects/ProjectCard.tsx`, accept two new optional props: `selectionMode` (boolean) and `onToggleSelect` (function receiving the project ID). When `selectionMode` is true, render an absolutely positioned `div` in the top-left corner of the card containing a ShadCN `Checkbox` component. Set the checkbox's `checked` value by comparing the card's project ID against a passed-in `selectedIds` array prop. Call `onToggleSelect(project.id)` in the checkbox's `onCheckedChange` handler. Ensure the checkbox click does not bubble up to any card-level click handler that would navigate to the project detail page — call `event.stopPropagation()` in the checkbox wrapper's `onClick` handler.

### Step 3 — Build `BulkActionBar.tsx` and `BulkSettingsPreviewPanel.tsx`

Create `frontend/components/projects/BulkActionBar.tsx`. The component accepts `selectedIds: number[]` and an `onComplete` callback as props. It fetches all projects from `/api/projects/` to populate the source dropdown. Maintain local state for `sourceProjectId` (the selected source) and `previewVisible` (boolean). When a source project is selected from the dropdown, set `previewVisible` to true and render the `BulkSettingsPreviewPanel` component inline above the bar. The "Apply" button is disabled until a source project is selected. Create `frontend/components/projects/BulkSettingsPreviewPanel.tsx` as a table component. It accepts `sourceProject` (the full project object) and `includedFields: string[]` with a setter. It renders one row per settings field using a static list of field definitions (field key, display label). Each row shows the field's current value from the source project parsed into a human-readable string, and a checkbox for inclusion. Changing a checkbox calls the setter to update `includedFields`.

### Step 4 — Add the backend endpoint in `backend/api/views.py`

Add a new class `BulkApplySettingsView` inheriting from `APIView`. Its `post` method receives a JSON body with three keys: `source_project_id`, `target_project_ids`, and `settings_fields`. Validate the payload using a new `BulkApplySettingsSerializer` in `serializers.py` — the serializer should enforce that `source_project_id` is an integer, `target_project_ids` is a non-empty list of integers with a maximum of 500 entries, and `settings_fields` is a list of strings constrained to a hardcoded allowlist of permitted field names. Fetch the source `Project` instance using `get_object_or_404`. Build an `update_kwargs` dictionary by iterating over the validated `settings_fields` and reading the corresponding attribute from the source project object. Call `Project.objects.filter(id__in=target_ids).update(**update_kwargs)`. Return a response with `{ "updated_count": <integer> }` and HTTP 200. Register the view in `urls.py` at `path("projects/bulk-apply-settings/", BulkApplySettingsView.as_view())` — place this path before any `<int:pk>` pattern to avoid URL routing conflicts.

### Step 5 — Wire the "Apply" button confirmation and toast feedback

In `BulkActionBar.tsx`, the "Apply" button's click handler should first show a `window.confirm()` dialog (or a ShadCN `AlertDialog` modal) summarizing the action: "Apply settings from Project X to Y selected projects? This cannot be undone." On confirmation, send the `POST /api/projects/bulk-apply-settings/` request. While the request is in flight, disable the Apply button and show a spinner. On success, display a toast notification using whatever toast system exists in the frontend (check `frontend/components/ui/` for an existing `Toast` or `Sonner` component). The toast message should read "Settings applied to N projects." Call the `onComplete` prop to signal the parent page to clear `selectedIds` and exit selection mode. On error, display an error toast with the message returned by the backend.

---

## 4. Expected Outcome

- A "Select" button appears in the project list toolbar and toggles multi-select mode on and off.
- Each `ProjectCard` displays a visible checkbox in the top-left corner when multi-select mode is active.
- Checking two or more project cards causes the `BulkActionBar` to appear at the bottom of the screen.
- Selecting a source project in the dropdown causes the `BulkSettingsPreviewPanel` to appear with the correct field values from that source project.
- Unchecking a field in the preview panel removes it from the `settings_fields` payload sent to the backend.
- Confirming the apply operation successfully updates all target projects' settings fields in the database.
- The backend returns the correct `updated_count` equal to the number of target project IDs.
- A success toast appears after the operation and the selection mode automatically resets.
- Fields not included in `settings_fields` (because the user unchecked them) are not modified on any target project.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] `BulkApplySettingsSerializer` rejects a payload where `target_project_ids` exceeds the maximum of 500 entries.
- [ ] `BulkApplySettingsSerializer` rejects a payload where `settings_fields` contains a field name not in the allowlist.
- [ ] `BulkApplySettingsView.post()` correctly copies only the specified fields from source to all target projects and does not modify unspecified fields.
- [ ] `BulkApplySettingsView.post()` returns 404 if `source_project_id` does not exist.
- [ ] `BulkApplySettingsView.post()` returns the correct `updated_count` in the response body.

### 5.2 Integration / Manual Tests

- [ ] Click "Select" on the project list page — verify all project cards immediately display checkbox overlays.
- [ ] Select three project cards, open the source dropdown, pick a source — verify the preview panel table shows the correct field values from the source project.
- [ ] Uncheck the `voice_id` field in the preview panel, click Apply — verify that target projects' `voice_id` is unchanged after the operation while other fields are updated.
- [ ] After a successful bulk apply, open one of the target projects' settings pages and confirm the applied fields match the source project's values.
- [ ] Clicking "Cancel" in the `BulkActionBar` clears the selection and exits multi-select mode without sending any API request.
- [ ] Submit a bulk apply with 200 target projects — verify the backend handles the request without timeout and returns the correct count.

### 5.3 Regression Tests

- [ ] The standard project detail navigation (clicking a card) still works correctly when multi-select mode is off.
- [ ] The existing `PATCH /api/projects/{id}/` endpoint for single-project settings updates continues to work unchanged.
- [ ] The project list page still loads and paginates correctly after the new selection state and `BulkActionBar` rendering logic is added.

---

## 6. Notes for AI Agent

- The field allowlist in `BulkApplySettingsSerializer` must be strictly defined as a Python list constant at the top of `serializers.py` — never allow arbitrary field names from the request payload to reach the `update()` call, as this would create a mass-assignment vulnerability allowing callers to overwrite any model field including `id` or `output_file`.
- The URL route for `projects/bulk-apply-settings/` must be registered before the `projects/<int:pk>/` pattern in `urls.py`, because Django matches URL patterns in order and `bulk-apply-settings` would otherwise be interpreted as a project ID.
- The `BulkSettingsPreviewPanel` should display `zoom_intensity` as a percentage (e.g., "8%" rather than "0.08") and `subtitle_settings` as a JSON summary string (e.g., "Font: Cinzel, Color: #FFFFFF") — parse these into human-readable form using a small helper function in the component rather than displaying raw JSON objects.
- If the frontend does not already have a `Toast` or notification system installed, use the ShadCN `Sonner` component, which is already part of the ShadCN/UI library that the project uses, rather than installing a separate toast library.
- The `BulkActionBar` should be implemented as a `position: fixed; bottom: 0` element with a high `z-index` to ensure it overlays the project grid — use the Tailwind classes `fixed bottom-0 left-0 right-0 z-50` and add a visible shadow above it to separate it from the page content.
