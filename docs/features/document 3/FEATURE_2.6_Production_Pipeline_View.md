# Feature 2.6 — Production Pipeline View (Kanban Board)

| Field | Value |
|---|---|
| **Feature ID** | 2.6 |
| **Title** | Production Pipeline View (Kanban Board) |
| **Status** | 🟡 Planned |
| **Priority** | High |
| **Complexity** | Medium |
| **Estimated Effort** | 4–6 days |
| **Dependencies** | Feature 2.1 (Project CRUD), Feature 2.3 (Segment Management), existing `ProjectCard` component |
| **Output Files (NEW)** | `frontend/app/pipeline/page.tsx`, `frontend/components/PipelineColumn.tsx`, `frontend/components/PipelineMiniCard.tsx` |
| **Files Modified** | `backend/api/serializers.py`, `backend/api/views.py`, `frontend/components/AppShell.tsx`, `frontend/store/settingsStore.ts` |

---

## 1. Document Overview

### 1.1 Problem Statement

A creator managing 50 or more projects currently has no way to see the overall health of their content production pipeline at a single glance. Every project must be opened individually to determine which stage it has reached. This makes prioritisation nearly impossible for high-volume producers who publish multiple videos per week. There is no concept of a "pipeline" — projects appear as a flat, date-sorted list with no visual grouping by production readiness. Without this view, bottlenecks in the workflow (e.g., 30 projects stuck at "Audio Generated" waiting for rendering) are invisible until they become emergencies.

### 1.2 Proposed Solution

Introduce a dedicated Kanban board page at `/pipeline` that groups all projects by their computed production stage. The board presents five columns representing sequential stages in the StoryFlow content pipeline. Each column displays a count badge, a scrollable list of mini project cards, and enough detail to act immediately without opening each project.

Key implementation points:

- Add a read-only computed `pipeline_status` field to the `ProjectSerializer` that derives the current stage from existing model data without requiring a new database column.
- The five stages are computed deterministically: "Draft" (no segments), "Segments Added" (segments exist but no images or audio yet), "Images Ready" (all segments have an `image_file`), "Audio Generated" (all segments have both `audio_file` and `duration`), and "Rendered" (the project-level output video file exists).
- Add a `?view=kanban` query parameter to `GET /api/projects/` that returns projects pre-grouped by `pipeline_status` as a dictionary keyed by status name instead of a flat array.
- Create `frontend/app/pipeline/page.tsx` as a full-width horizontal board using CSS grid or flexbox, one column per pipeline stage.
- Each column contains a scrollable list of `PipelineMiniCard` components showing project name, segment count, last updated timestamp, and a direct "Open" button.
- Add a "Pipeline" navigation link in `AppShell.tsx` alongside the existing "Projects" link.

### 1.3 Scope

| Category | Item |
|---|---|
| **In Scope** | Computed `pipeline_status` field in serializer |
| **In Scope** | Kanban board page with 5 columns |
| **In Scope** | `?view=kanban` grouped API response |
| **In Scope** | Mini project card component for the board |
| **In Scope** | Navigation link in app shell |
| **Out of Scope** | Drag-and-drop to manually reassign pipeline status (future enhancement) |
| **Out of Scope** | "Published" status (depends on Feature 2.9 Social Publishing) |
| **Out of Scope** | Filtering/searching within the pipeline board |
| **Out of Scope** | Real-time WebSocket updates to pipeline columns |
| **Out of Scope** | Per-column bulk actions (e.g., "Render all in this column") |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| `backend/api/serializers.py` | Converts Django model instances to JSON; `ProjectSerializer` used for all project API responses | Exists; does not yet include `pipeline_status` |
| `backend/api/views.py` | Django REST Framework views; `ProjectListView` handles `GET /api/projects/` | Exists; returns flat project list only |
| `frontend/app/pipeline/page.tsx` | New Kanban board page; top-level route at `/pipeline` | Does not exist yet |
| `frontend/components/AppShell.tsx` | Persistent app navigation wrapper; renders sidebar or top nav links | Exists; contains "Projects" and "Settings" links |
| `frontend/components/ProjectCard.tsx` | Full-size project card used on the projects list page | Exists; too large for Kanban mini-card use |
| `frontend/store/settingsStore.ts` | Global Zustand store; tracks UI preferences and feature flags | Exists; may be used to persist selected pipeline column filters |

---

## 2. Flow Diagram

```
User navigates to /pipeline
        |
        v
pipeline/page.tsx — mounts, calls GET /api/projects/?view=kanban
        |
        v
Django ProjectListView — detects view=kanban param
        |
        v
ProjectSerializer — computes pipeline_status per project
  [checks: segments count → image_file → audio_file+duration → output_file]
        |
        v
Groups projects into dict: { Draft:[...], Segments Added:[...], ... }
        |
        v
Returns grouped JSON to frontend
        |
        v
pipeline/page.tsx — maps each key to a PipelineColumn
        |
   _____|______________________________________________________
   |              |              |              |             |
Draft    Segments Added    Images Ready   Audio Generated  Rendered
   |              |              |              |             |
 [scroll]      [scroll]       [scroll]       [scroll]     [scroll]
   |
PipelineMiniCard x N
  (name, segment count, updated_at, Open button)
```

---

## 3. Step-by-Step Instructions

### Step 3.1 — Add `pipeline_status` Computed Field to `ProjectSerializer`

File: `backend/api/serializers.py`
Function/class: `ProjectSerializer`

Add a `SerializerMethodField` named `pipeline_status` to the serializer's field list. Implement a `get_pipeline_status` method that accepts the project instance. Inside the method, check the related segments queryset in order: if no segments exist return "Draft"; if segments exist but none have an `image_file` return "Segments Added"; if all segments have `image_file` but any segment is missing `audio_file` or `duration` return "Images Ready"; if all segments have `audio_file` and `duration` but the project has no output video file return "Audio Generated"; otherwise return "Rendered". This logic runs entirely in Python at serialization time and requires no schema changes. The method should use `prefetch_related` data if available to avoid N+1 queries — ensure the view prefetches `segments` when calling this serializer.

### Step 3.2 — Update `ProjectListView` to Support `?view=kanban`

File: `backend/api/views.py`
Function/class: `ProjectListView.get` (or `list` method if using `ListAPIView`)

After the standard queryset is serialized to a list, check if `request.query_params.get('view') == 'kanban'`. If true, iterate through the serialized data and group projects by their `pipeline_status` value into a Python dictionary. The dictionary keys should be the five stage names in pipeline order. Return this dictionary wrapped in a `Response` object. If the `view` param is absent or has any other value, return the normal flat list as before. This keeps the existing projects page unaffected. Add `prefetch_related('segments')` to the queryset inside this view to support efficient `pipeline_status` computation.

### Step 3.3 — Create `PipelineMiniCard` Component

File: `frontend/components/PipelineMiniCard.tsx`
Props: project object (name, id, segment count, updated_at)

Create a compact card component that shows the project name in bold, a small grey segment count label (e.g., "14 segments"), the last-updated date formatted as a relative time string (e.g., "3 days ago"), and a small "Open" button that navigates to the project edit page. The card should have a subtle bordered box style, a hover highlight, and a fixed height to keep columns visually uniform. Do not reuse `ProjectCard.tsx` — that component is too large and renders extra controls that are not needed in the pipeline view.

### Step 3.4 — Create `PipelineColumn` Component

File: `frontend/components/PipelineColumn.tsx`
Props: column title string, array of project objects, accent color string

Render a vertical column with a sticky header showing the column title and a count badge (e.g., "Images Ready · 7"). Below the header, render a scrollable container with `overflow-y: auto` and a max height calculated to fill the viewport. Map over the projects array and render one `PipelineMiniCard` per project. If the array is empty, show a centred grey "No projects here" placeholder message. Accept an optional `accentColor` prop to tint the column header for visual distinction between stages.

### Step 3.5 — Create `pipeline/page.tsx` Page

File: `frontend/app/pipeline/page.tsx`

This is a Next.js App Router page component. On mount it fetches `GET /api/projects/?view=kanban` using the existing API utility (same base URL as the projects page). While loading, show a full-width skeleton placeholder for each column. On error, show an inline error banner. On success, define the ordered list of column names and map each to a `PipelineColumn` component, passing the corresponding projects array from the API response. Arrange all five columns in a horizontal flex row with a small gap and horizontal overflow scroll so the board remains usable on smaller screens. The page title should read "Production Pipeline".

### Step 3.6 — Add "Pipeline" Link to `AppShell.tsx`

File: `frontend/components/AppShell.tsx`

Locate the existing navigation link list (which currently includes "Projects" and "Settings"). Insert a new navigation item labelled "Pipeline" pointing to `/pipeline`. Use the same link component and styling as the existing items. Place it between "Projects" and "Settings" in the nav order. Optionally add a Kanban-icon from the lucide-react library to match the icon style of other nav items.

---

## 4. Expected Outcome

1. Navigating to `/pipeline` shows a five-column Kanban board with all projects distributed across the appropriate columns.
2. Each column header displays the stage name and a live count of projects in that stage.
3. Mini project cards are compact and readable; name, segment count, and last-updated date are all visible without scrolling the card itself.
4. The "Open" button on each mini card navigates directly to the project editor for that project.
5. The `GET /api/projects/?view=kanban` endpoint returns a valid grouped JSON object; the existing `GET /api/projects/` endpoint (no query param) is unaffected and continues to return a flat list.
6. The "Pipeline" link appears in the app navigation alongside "Projects" and "Settings".
7. Columns with many projects scroll independently without affecting the horizontal layout of the board.
8. On a typical laptop screen (1366 px wide) all five columns are visible simultaneously or can be reached with horizontal scroll.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] `get_pipeline_status` returns "Draft" for a project with zero segments.
- [ ] `get_pipeline_status` returns "Images Ready" when all segments have `image_file` but at least one is missing `audio_file`.
- [ ] `get_pipeline_status` returns "Rendered" when all segments have both `audio_file` and `duration` and the project output file exists.
- [ ] `ProjectListView` with `?view=kanban` returns a dictionary with all five stage keys even if some are empty arrays.
- [ ] `PipelineMiniCard` renders the project name, segment count, and an "Open" link pointing to the correct project URL.
- [ ] `PipelineColumn` renders a "No projects here" placeholder when passed an empty array.

### 5.2 Integration / Manual Tests

- [ ] Open the pipeline page with a mix of projects in different stages; verify each project appears in the correct column.
- [ ] Create a new project with no segments; verify it appears in the "Draft" column immediately after page refresh.
- [ ] Add segments to a Draft project; verify it moves to "Segments Added" on next pipeline page load.
- [ ] Confirm that the flat projects list page (`/projects`) is completely unaffected by the kanban view changes.
- [ ] Click "Open" on a mini card; verify navigation to the correct project page.
- [ ] Load the pipeline page with 20+ projects in one column; verify the column scrolls correctly while the other columns remain stationary.
- [ ] Verify the "Pipeline" nav link is active/highlighted when on the `/pipeline` route.

### 5.3 Regression Tests

- [ ] Existing `GET /api/projects/` (no query param) still returns a flat array, not a grouped dictionary.
- [ ] The projects list page (`/projects`) continues to load and display `ProjectCard` components without errors.
- [ ] No new database migrations are required; confirm `pipeline_status` is a runtime-computed field only.

---

## 6. Notes for AI Agent

- The `pipeline_status` field must be a `SerializerMethodField` — never a model field or migration. Adding it to the database would create synchronisation bugs when segment data changes.
- Implement Step 3.1 and Step 3.2 first and verify the API response in a browser or Postman before touching the frontend; the frontend completely depends on the correct grouped JSON shape.
- The order of stage evaluation in `get_pipeline_status` matters — always check from most complete (Rendered) downward, or from least complete (Draft) upward, consistently. Mixing the order creates logical conflicts.
- Avoid reusing `ProjectCard.tsx` for the Kanban mini-card. The full card has action buttons and a layout that is too wide for a Kanban column. A dedicated `PipelineMiniCard` component is required.
- The "Published" status is intentionally excluded from this feature. Do not add a sixth column or reference the publishing feature; that is tracked separately under Feature 2.9.
- When implementing Step 3.2, be careful not to break the existing projects page. Test the flat list endpoint (`GET /api/projects/` with no query params) explicitly after making any changes to the view.
