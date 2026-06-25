# Feature 2.7 — Project Tags / Categories

| Field | Value |
|---|---|
| **Feature ID** | 2.7 |
| **Title** | Project Tags / Categories |
| **Status** | 🟡 Planned |
| **Priority** | Medium |
| **Complexity** | Low |
| **Estimated Effort** | 2–3 days |
| **Dependencies** | Feature 2.1 (Project CRUD), existing `ProjectCard` component, existing `CreateProjectDialog` component |
| **Output Files (NEW)** | `frontend/components/TagFilterSidebar.tsx`, `frontend/components/TagChip.tsx`, one new Django migration file |
| **Files Modified** | `backend/api/models.py`, `backend/api/serializers.py`, `frontend/components/ProjectCard.tsx`, `frontend/components/CreateProjectDialog.tsx`, `frontend/app/projects/page.tsx` |

---

## 1. Document Overview

### 1.1 Problem Statement

As the number of StoryFlow projects grows beyond a few dozen, the current flat date-sorted list becomes unmanageable. A creator who produces videos across multiple content categories — History, Science, Horror, Motivational, Funny — has no way to filter or group projects by theme. Finding all "Horror" episodes requires manually reading every project name. There is no label, badge, or filter mechanism of any kind on the projects page today. At 100 or more projects this problem becomes a daily friction point, and at 1000 projects the list is practically unusable without search and filtering tools. Tags are the lightest-weight solution that requires no structural redesign of the existing page or data model.

### 1.2 Proposed Solution

Add a flexible string-array `tags` field to the `Project` model using Django's `JSONField`, which is compatible with the SQLite database currently in use. Expose tags as a readable and writable field through the existing `ProjectSerializer`. On the frontend, render tag chips on each `ProjectCard`, add a filter bar to the projects list page, and add a tag input control to the project creation dialog and settings panel.

Key implementation points:

- Use `JSONField(default=list, blank=True)` for the `tags` field on the `Project` model. This stores tags as a JSON array of plain strings — no separate `Tag` model or many-to-many relationship is needed. This is the correct choice for SQLite compatibility; Django's `ArrayField` requires PostgreSQL.
- Add `tags` to `ProjectSerializer` so it is included in all `GET /api/projects/` responses and can be updated via `PATCH /api/projects/{id}/`.
- In `frontend/app/projects/page.tsx`, extract all unique tags from the loaded projects array on the client side and render a `TagFilterSidebar` component with clickable tag buttons. No dedicated backend tag listing endpoint is needed.
- In `frontend/components/ProjectCard.tsx`, display up to four tag chips below the project name. If a project has more than four tags, show a "+N more" label.
- In `frontend/components/CreateProjectDialog.tsx`, add a multi-select freeform tag input. The user types a tag name and presses Enter or comma to add it. Previously used tags (collected from the loaded projects) are offered as autocomplete suggestions via a dropdown.
- Tag colour assignment should be deterministic and consistent: derive a colour from the tag string using a simple hash-to-palette function so the same tag always renders the same colour across all cards.

### 1.3 Scope

| Category | Item |
|---|---|
| **In Scope** | `tags` JSONField on `Project` model with migration |
| **In Scope** | Tag read/write in `ProjectSerializer` |
| **In Scope** | Tag filter sidebar on projects page |
| **In Scope** | Tag chips on `ProjectCard` |
| **In Scope** | Tag input in `CreateProjectDialog` |
| **Out of Scope** | Dedicated backend `/api/tags/` endpoint (client-side extraction is sufficient) |
| **Out of Scope** | Tag rename or merge operations (bulk tag management is a future admin tool) |
| **Out of Scope** | Tag-based search in the Pipeline view (Feature 2.6 is independent) |
| **Out of Scope** | Tag ordering or priority/weight fields |
| **Out of Scope** | Per-tag project count analytics or dashboards |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| `backend/api/models.py` | Defines the `Project` Django model with all persistent fields | Exists; no `tags` field present |
| `backend/api/serializers.py` | `ProjectSerializer` controls which fields are exposed via the REST API | Exists; `tags` not yet included |
| `frontend/app/projects/page.tsx` | Projects list page; fetches all projects and renders `ProjectCard` grid | Exists; no filter UI present |
| `frontend/components/ProjectCard.tsx` | Renders a single project in the grid; shows name, status, segment count, action buttons | Exists; no tag chips rendered |
| `frontend/components/CreateProjectDialog.tsx` | Modal dialog for creating a new project; contains name and initial settings inputs | Exists; no tag input field |
| `frontend/store/settingsStore.ts` | Global Zustand store; used for persisting UI preferences | Exists; may be used to persist last active tag filter selection |

---

## 2. Flow Diagram

```
User opens /projects
        |
        v
projects/page.tsx — fetches GET /api/projects/
        |
        v
Django API — returns projects array, each with tags: ["Horror", "Short"]
        |
        v
projects/page.tsx — extracts unique tags from all projects client-side
  ["History", "Horror", "Science", "Motivational", "Funny", ...]
        |
        v
TagFilterSidebar — renders one clickable chip per unique tag
        |
   User clicks "Horror"
        |
        v
projects/page.tsx — filters displayed projects to those whose
  tags array includes "Horror"
        |
        v
ProjectCard grid re-renders with filtered subset
        |
ProjectCard.tsx — renders TagChip x N below project name
        |
   User opens CreateProjectDialog
        |
        v
CreateProjectDialog — tag input field with freeform entry
  (autocomplete suggestions from unique tags already loaded)
        |
   User types "Horror", presses Enter
        |
        v
PATCH /api/projects/{id}/ — body includes updated tags array
        |
        v
ProjectSerializer validates and saves tags JSONField
```

---

## 3. Step-by-Step Instructions

### Step 3.1 — Add `tags` JSONField to the `Project` Model

File: `backend/api/models.py`
Class: `Project`

Add a new field `tags` using `models.JSONField` with `default=list` and `blank=True`. Place it after the existing metadata fields such as `voice_id` or `resolution_width` to keep the model organised logically. After saving the model file, run `python manage.py makemigrations api` to generate a new migration, then `python manage.py migrate` to apply it. The migration should be a straightforward `AddField` operation with no data transformation needed. Verify the migration file name follows the existing sequential naming convention in `backend/api/migrations/`.

### Step 3.2 — Expose `tags` in `ProjectSerializer`

File: `backend/api/serializers.py`
Class: `ProjectSerializer`

Add the string `"tags"` to the `fields` list (or `Meta.fields` tuple) inside `ProjectSerializer`. Because `JSONField` stores a native Python list, no custom serializer field is needed — DRF will serialise it directly as a JSON array of strings. Confirm that the field is also writable by ensuring `tags` is not listed in `read_only_fields`. After this change, test that `GET /api/projects/` returns a `tags` key (array) for each project, and that `PATCH /api/projects/{id}/` with a body containing a `tags` array correctly persists the new value.

### Step 3.3 — Create `TagChip` and `TagFilterSidebar` Components

File: `frontend/components/TagChip.tsx`
File: `frontend/components/TagFilterSidebar.tsx`

`TagChip` is a small inline badge component. It accepts a `tag` string and an optional `onClick` callback. Its background colour is derived by hashing the tag string to one of eight preset Tailwind background colour classes (e.g., blue, green, red, amber, purple, pink, teal, orange) so the same tag always renders the same colour. The label is the tag string in lowercase, truncated to 20 characters with an ellipsis if longer.

`TagFilterSidebar` accepts the full array of unique tag strings and the currently active tag filter (a string or null). It renders a vertical list of `TagChip` components. Clicking an unselected chip sets it as the active filter; clicking the already-active chip deselects it (clearing the filter). A "Clear filter" button appears at the top when any filter is active. On mobile layouts the sidebar collapses into a horizontally scrollable chip row above the project grid.

### Step 3.4 — Update `ProjectCard.tsx` to Display Tag Chips

File: `frontend/components/ProjectCard.tsx`
Component: `ProjectCard`

Add a new section below the project name that renders up to four `TagChip` components from the project's `tags` array. If the array is empty, render nothing (no empty space). If the array has more than four items, render four chips and then a small grey "+N more" text label where N is the count of hidden tags. Tags should wrap naturally within the card width. Import the `TagChip` component. Ensure the additional tag row does not break the existing card height in the grid — the card should grow to fit content rather than overflow.

### Step 3.5 — Add Tag Filter UI to `projects/page.tsx`

File: `frontend/app/projects/page.tsx`

After the projects data is loaded, compute the unique tags array by flattening all `project.tags` arrays and deduplicating using a `Set`. Store the active tag filter in a local `useState` variable initialised to `null`. Pass the unique tags and the active filter state to a `TagFilterSidebar` rendered to the left of (or above) the project grid. Apply the filter by replacing the displayed projects array with a derived array: if a filter is active, include only projects whose `tags` array contains the active tag string; if no filter is active, show all projects. The filtering is entirely client-side — no new API call is triggered when a tag filter is selected.

### Step 3.6 — Add Tag Input to `CreateProjectDialog.tsx`

File: `frontend/components/CreateProjectDialog.tsx`

Add a tag input field to the project creation form, positioned below the project name input. The input should allow the user to type a tag name. When the user presses Enter or comma, the typed text is trimmed, lowercased, and added to a local tags array stored in component state. Each added tag is shown as a dismissible chip inside the input area (an "input tag bag" pattern). Clicking the × on a chip removes that tag. The field should offer autocomplete suggestions: as the user types, show a small dropdown of matching tags drawn from the `uniqueTags` array passed as a prop from the parent page. On form submission, include the `tags` array in the project creation payload. If the project creation API does not yet accept `tags` on `POST /api/projects/`, update the Django view to accept it — the serializer already handles it after Step 3.2.

---

## 4. Expected Outcome

1. Every project in the database has a `tags` field that defaults to an empty array; no existing projects are broken or require data migration.
2. `GET /api/projects/` returns a `tags` array for every project; `PATCH /api/projects/{id}/` with a `tags` body correctly updates the tags and returns the updated project.
3. The projects list page shows a tag filter sidebar (or chip row on mobile). Clicking a tag filters the visible project grid instantly without a page reload or API call.
4. Each `ProjectCard` displays up to four coloured tag chips below the project name. Projects with no tags show no chip row.
5. The same tag always renders the same background colour across all cards and across page reloads.
6. The `CreateProjectDialog` contains a tag input with freeform entry, Enter-to-add behaviour, dismissible chips, and autocomplete suggestions from existing tags.
7. A newly created project with tags set in the dialog appears in the projects grid immediately with the correct chips.
8. Filtering by a tag that no project currently has results in an empty grid with a friendly "No projects match this tag" message rather than an error.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] `Project` model accepts `tags` as a list of strings and rejects non-list values at the serializer validation level.
- [ ] `ProjectSerializer` with `tags=["History", "Science"]` serialises to `{"tags": ["History", "Science"]}` in the API response.
- [ ] `TagChip` renders the correct Tailwind colour class for at least three different known tag strings (verify hash determinism).
- [ ] `TagFilterSidebar` calls `onTagSelect` with the correct tag string when a chip is clicked.
- [ ] `ProjectCard` renders exactly four chips and a "+2 more" label when given six tags.
- [ ] `CreateProjectDialog` tag input correctly adds a tag on Enter key and removes it on chip × click.

### 5.2 Integration / Manual Tests

- [ ] Create a new project with tags ["Horror", "Short"] via the dialog; verify both chips appear on the project card immediately.
- [ ] Open the projects page with mixed projects; click a tag in the filter sidebar; verify only projects with that tag are shown.
- [ ] Deselect the active filter by clicking the active chip; verify all projects reappear.
- [ ] Patch a project via `PATCH /api/projects/{id}/` with a new tags array using a REST client; verify the UI reflects the change on page refresh.
- [ ] Verify that a project created before the migration (with no explicit `tags` value) shows no chips and does not throw a JavaScript error.
- [ ] Add more than four tags to a project; verify the "+N more" label appears correctly and the layout does not break.
- [ ] Type a partial tag name in the create dialog input and verify matching suggestions appear in the dropdown.

### 5.3 Regression Tests

- [ ] Existing `ProjectCard` rendering is unchanged for projects with no tags — no layout shift, no empty whitespace block.
- [ ] The `GET /api/projects/` endpoint continues to return all existing fields (`name`, `updated_at`, `voice_id`, etc.) alongside the new `tags` field.
- [ ] The projects page search/sort functionality (if any exists) continues to work correctly alongside the new tag filter.

---

## 6. Notes for AI Agent

- Use `models.JSONField(default=list, blank=True)` — not `default=[]`. Using a mutable default like `[]` directly causes a Django system check error ("mutable default"). Always use `default=list` (a callable) for list-type JSONFields.
- Complete Step 3.1 and Step 3.2 (backend) first and verify the API reflects the `tags` field before starting any frontend work. If the API does not return `tags`, the frontend components will silently render nothing rather than erroring visibly.
- The tag colour hash function must be purely deterministic based on the tag string alone — never use random colour assignment. Inconsistent colours across cards break the visual language and confuse users.
- Do not add a backend `/api/tags/` endpoint. All unique-tag extraction happens client-side by reducing the `projects` array already loaded by the page. This avoids an extra API call and dependency.
- When updating `CreateProjectDialog.tsx`, pass the `uniqueTags` array from the parent `projects/page.tsx` as a prop rather than making the dialog fetch its own data. This keeps the dialog stateless with respect to data loading.
- The tag input in the dialog should normalise tags to lowercase and trim whitespace before adding them, so "Horror", " horror ", and "HORROR" all resolve to "horror" and avoid duplicates with different casing.
