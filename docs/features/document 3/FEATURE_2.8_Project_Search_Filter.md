# Feature 2.8 — Advanced Project Search & Filter

| Field | Value |
|---|---|
| Feature ID | 2.8 |
| Title | Advanced Project Search & Filter |
| Status | 🟡 Planned |
| Priority | High |
| Complexity | Low |
| Estimated Effort | 2 days |
| Dependencies | Feature 2.1 (Project List API), django-filter package |
| Output Files (NEW) | `frontend/components/ProjectFilterBar.tsx`, `backend/api/filters.py` |
| Files Modified | `frontend/app/projects/page.tsx`, `frontend/hooks/useProjectFilters.ts`, `backend/api/views.py`, `backend/api/urls.py`, `backend/requirements.txt` |

---

## 1. Document Overview

### 1.1 Problem Statement

StoryFlow currently provides only a basic name-search input on the projects list page, which becomes inadequate as a user's library grows beyond 50 or 100 projects. A producer working with hundreds of videos needs to instantly locate "all Rendered Horror projects from last month" without manually scrolling through an unsorted grid. There is no way to filter by status, tag, date range, or segment count, making project discovery slow and frustrating. This gap becomes a critical UX failure for any power user or small studio treating StoryFlow as their primary production tool.

### 1.2 Proposed Solution

Introduce a collapsible filter bar above the project grid that provides multi-dimensional filtering across all meaningful project attributes. Filters operate client-side first for instant feedback on already-loaded data, and fall back to server-side query parameters when a full-library search is needed. Persisting filter state to localStorage ensures the user's last session context is restored automatically.

- Add a new `ProjectFilterBar` component, rendered as a collapsible row at the top of the project grid in `projects/page.tsx`, containing a status dropdown, date range picker, tag multi-select input, segment count min/max sliders, and a has-rendered-output checkbox.
- Implement a `useProjectFilters` custom hook that owns the filter state object and exposes update functions to the filter bar and the project list.
- Apply filters client-side first by running a `filterProjects(projects, filters)` pure function over the in-memory Zustand project array before re-rendering the grid — no network round-trip for small libraries.
- For libraries exceeding a configurable threshold (default 200 projects), automatically pass active filter values as query parameters to `GET /api/projects/` so the server returns only matching rows.
- Create `backend/api/filters.py` containing a `ProjectFilter` class using `django-filter` that supports `status`, `tag`, `updated_at__gte`, `updated_at__lte`, and `segment_count__gte` lookups.
- Display an active-filter count badge on the filter toggle button ("3 filters active") so the user can see at a glance that results are constrained.
- Provide a "Clear all filters" button that resets every control to its default value and removes the localStorage entry.

### 1.3 Scope

| # | In Scope | Out of Scope |
|---|---|---|
| 1 | Status, date range, tag, segment count, and has-output filters | Saved/named filter presets |
| 2 | Client-side filtering of the in-memory project array | Elasticsearch or full-text search indexing |
| 3 | Server-side query parameter forwarding for large libraries | Real-time filter suggestions or autocomplete tags |
| 4 | Persisting active filters to localStorage across page reloads | Cross-device filter sync via user account |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| `frontend/app/projects/page.tsx` | Renders project grid; fetches project list on mount | Has name search input; no filter controls |
| `frontend/components/ProjectCard.tsx` | Displays a single project card with status badge and tags | Fully functional; no changes needed |
| `frontend/hooks/useKeyboardShortcuts.ts` | Global keyboard event handler | Existing; may need Escape key to close filter panel |
| `backend/api/views.py` | `ProjectListView` handles `GET /api/projects/` | Returns all projects; no query-param filtering |
| `backend/api/filters.py` | Django-filter filter class for Project model | Does not exist yet — new file required |

---

## 2. Flow Diagram

```
User opens /projects page
        |
        v
Fetch GET /api/projects/ (no params)  ──>  Store all projects in Zustand
        |
        v
Render ProjectFilterBar (collapsed by default)
        |
        v
User toggles filter bar open
        |
        v
User sets one or more filter values (status / date / tag / segments)
        |
        v
useProjectFilters hook updates filter state object
        |
        v
filterProjects() runs over in-memory array  ──>  Filtered results rendered instantly
        |
        v
[Library > 200 projects?]
   YES  |                  NO
        v                   \──>  Client-side result displayed (done)
Re-fetch GET /api/projects/?status=X&tag=Y&from=Z
        |
        v
Backend ProjectFilter applies Django ORM filters
        |
        v
Filtered JSON response replaces Zustand store slice
        |
        v
Filter bar shows active badge count  ──>  Grid re-renders with server results
```

---

## 3. Step-by-Step Instructions

### Step 3.1 — Create the Backend Filter Class

**File:** `backend/api/filters.py`
**Function / Class:** `ProjectFilter`

- Add `django-filter` to `backend/requirements.txt` then install it in the virtual environment.
- Create `backend/api/filters.py` and define a `ProjectFilter` class that inherits from `django_filters.FilterSet`, targeting the `Project` model.
- Declare the following filter fields: `status` (exact), `tags` (custom method filter that checks if the supplied tag string exists inside the JSONField array), `updated_at__gte` mapped to a `DateFilter` named `from_date`, `updated_at__lte` mapped to `to_date`, and `segment_count__gte` mapped to `min_segments`.
- Register `django_filters.DjangoFilterBackend` in `REST_FRAMEWORK` settings inside `storyflow_backend/settings.py`.

### Step 3.2 — Wire the Filter Class into the Project View

**File:** `backend/api/views.py`
**Function:** `ProjectListView.get_queryset`

- Import `ProjectFilter` from `api.filters` at the top of `views.py`.
- Set `filterset_class = ProjectFilter` on `ProjectListView` (or the relevant `ListAPIView` subclass).
- Confirm that `filter_backends` includes `DjangoFilterBackend` and `OrderingFilter`.
- Add a `segment_count` annotation to the default queryset using `Count('segments')` so the `min_segments` filter has a column to operate on.
- Run the existing test suite to ensure no regression on the unannotated path.

### Step 3.3 — Build the useProjectFilters Hook

**File:** `frontend/hooks/useProjectFilters.ts`
**Function:** `useProjectFilters` (new custom hook)

- Define a `ProjectFilters` TypeScript interface with fields: `status` (string or null), `fromDate` (string or null), `toDate` (string or null), `tags` (string array), `minSegments` (number or null), `maxSegments` (number or null), `hasOutput` (boolean).
- Initialise state from `localStorage` on first render using a lazy `useState` initialiser that reads and JSON-parses the `storyflow_project_filters` key; fall back to all-null defaults if the key is absent or invalid.
- Expose a `setFilter(field, value)` updater and a `clearFilters()` reset function; both must also write the new state back to `localStorage`.
- Export a `filterProjects(projects, filters)` pure function that can be imported into the page component and called synchronously — this function should apply each non-null filter field sequentially using array `.filter()` and `.includes()` logic.

### Step 3.4 — Build the ProjectFilterBar Component

**File:** `frontend/components/ProjectFilterBar.tsx`
**Function:** `ProjectFilterBar` (new React component)

- Accept props: `filters` (current filter state), `onFilterChange` (per-field updater), `onClear` (reset all), and `activeCount` (number of non-default filters currently set).
- Render a collapsible container; the trigger button displays "Filters" with a ShadCN `Badge` showing `activeCount` when greater than zero.
- Inside the expanded panel, lay out controls in a single responsive row using Tailwind's `flex flex-wrap gap-3`: a ShadCN `Select` for status, two `DatePicker` inputs for from/to, a tag `MultiSelect`, two `Slider` components for segment count range, and a `Checkbox` for has-output.
- The "Clear all filters" button calls `onClear`, sets button variant to `ghost`, and is only shown when `activeCount > 0`.

### Step 3.5 — Integrate the Filter Bar into the Projects Page

**File:** `frontend/app/projects/page.tsx`
**Function:** Page component (top-level)

- Import `useProjectFilters`, `filterProjects`, and `ProjectFilterBar` at the top of the file.
- Call the hook to get `filters`, `setFilter`, `clearFilters`, and `activeCount`; derive `displayedProjects` by calling `filterProjects(allProjects, filters)` inside a `useMemo` that re-runs when either `allProjects` or `filters` changes.
- Mount `ProjectFilterBar` above the existing project grid, passing the appropriate props; remove or demote the old simple name-search input by making it a filter field in the new panel.
- Add a `useEffect` that watches `filters`; when any server-side–eligible filter is set and the project count exceeds 200, call the API with the serialised query parameters and update the Zustand store slice.
- Pass `displayedProjects` (not `allProjects`) to the grid render loop.

---

## 4. Expected Outcome

1. A collapsible filter bar appears above the project grid with controls for status, date range, tags, segment count, and has-output.
2. Filtering responds instantly (< 16 ms) when the in-memory project list has fewer than 200 items by running the client-side pure filter function.
3. When the project library exceeds 200 items, a server request is automatically dispatched with the active filter values as URL query parameters.
4. The Django backend correctly filters the queryset by status, tag membership, date range, and minimum segment count, returning only matching rows.
5. An active-filter count badge appears on the filter toggle button whenever one or more filters are non-default, giving the user a clear signal that results are constrained.
6. The "Clear all filters" button resets all controls, removes the localStorage entry, and restores the full project grid in one action.
7. Closing and re-opening the browser tab restores the last active filter state from localStorage, preserving the user's working context.
8. The existing project name search is preserved as an additional field inside the filter bar, not replaced or broken.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] `filterProjects()` with `status = 'Rendered'` returns only projects whose status matches and excludes all others.
- [ ] `filterProjects()` with a tag value correctly excludes projects whose `tags` array does not contain that value.
- [ ] `filterProjects()` with `fromDate` and `toDate` correctly excludes projects whose `updated_at` falls outside the range.
- [ ] `clearFilters()` resets every field to null/default and removes the `storyflow_project_filters` localStorage key.
- [ ] `useProjectFilters` initialises from a valid localStorage entry rather than defaults when a persisted state exists.
- [ ] `ProjectFilter` Django class returns empty queryset for a status value that no project has.

### 5.2 Integration / Manual Tests

- [ ] Open the projects page with 5 seed projects; set status filter to "Draft"; confirm the grid shows only Draft projects without a network re-fetch.
- [ ] Set a date range that excludes all projects; confirm the grid shows an empty-state message rather than errors.
- [ ] Set a tag filter to a value that only two projects share; confirm both appear and the badge shows "1 filter active".
- [ ] With the filter active, refresh the page; confirm the filter bar restores the previous state from localStorage and the grid is pre-filtered.
- [ ] Click "Clear all filters"; confirm the badge disappears, all controls reset, and the full project list is shown.
- [ ] In a Django shell, call `GET /api/projects/?status=Rendered&tag=Horror`; confirm only matching projects are returned as JSON.

### 5.3 Regression Tests

- [ ] Existing name search on the projects page still narrows results correctly when used alongside the new filter bar.
- [ ] `ProjectCard` renders correctly in the filtered grid with no layout breakage or missing props.
- [ ] The `GET /api/projects/` endpoint with no query parameters still returns all projects with the correct serialised fields.

---

## 6. Notes for AI Agent

- The `tags` field on the `Project` model is a `JSONField` storing a plain Python list of strings; the custom Django filter method must use `__contains` or a raw annotation — do not use `__icontains` on a JSONField directly as it will not work reliably across SQLite and PostgreSQL.
- The `filterProjects` pure function must be kept outside the React component tree so that `useMemo` can hold a stable reference and Vitest can import and test it in isolation without rendering a component.
- The localStorage key should be namespaced as `storyflow_project_filters` to avoid collisions with any other future persisted state, and the value should always be JSON-stringified before writing and JSON-parsed with a try/catch on read.
- The ShadCN `Slider` component requires a controlled `value` prop as an array (e.g., `[0, 100]`); make sure the `minSegments` and `maxSegments` state fields are kept in sync with the slider's two-handle output array.
- Do not add the `ProjectFilterBar` to the shared layout — it belongs only inside `frontend/app/projects/page.tsx` since it is context-specific to the project list view.
