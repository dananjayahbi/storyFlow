# Feature 4.1 — Project Archiving

| Field | Value |
|---|---|
| Feature ID | 4.1 |
| Title | Project Archiving |
| Status | 🟡 Planned |
| Priority | High |
| Complexity | Low |
| Estimated Effort | 2–3 days |
| Dependencies | Existing Project model, DRF ProjectListView, frontend project list page |
| Output Files (NEW) | frontend/app/projects/archive/page.tsx |
| Files Modified | backend/api/models.py, backend/api/serializers.py, backend/api/views.py, backend/api/urls.py, frontend/app/projects/page.tsx, frontend/components/Sidebar.tsx |

---

## 1. Document Overview

### 1.1 Problem Statement

As a creator produces more and more videos using StoryFlow over weeks and months of active
use, the flat project list grows to hundreds or thousands of entries with no mechanism
for decluttering, filtering, or organizing the workspace by the actual status of each project.

All projects — active drafts, completed renders, canceled experiments, and published
months-old content — appear together in the exact same list, sorted uniformly by date
with no visual separation whatsoever between projects that are active and those that are not.

Scrolling through a list of five hundred or more projects just to locate an actively-in-progress
draft wastes meaningful amounts of time at the beginning of every session and creates cognitive
overload that reduces the creator's ability to focus on the work that actually matters today.

There is currently no way in StoryFlow to distinguish between projects that are actively
being worked on and those that are fully finished and should be set aside so that completed
content stops competing for visual attention alongside current production work.

### 1.2 Proposed Solution

Implement a project archiving system that allows creators to move completed or no-longer-active
projects into an archived state with a single click from the project list.

Archived projects are hidden from the default project list view so that the primary workspace
shows only active, in-progress content, but all archived projects remain fully accessible
through a dedicated archive view that can be reached from the sidebar at any time.

The system records a timestamp when a project is archived, enabling creators to see how long
ago a project was put away, and provides a one-click unarchive action to bring any archived
project back into the active workspace instantly and without any data loss.

- Add an `is_archived` BooleanField and an `archived_at` DateTimeField to the Project model
  and run a new database migration to apply the schema change without touching existing data.
- Modify the default ProjectListView queryset to exclude archived projects by default so
  that the primary GET /api/projects/ endpoint only returns active projects unless overridden.
- Add a new `?archived=true` query parameter to the list endpoint that switches the queryset
  to return only archived projects, powering the archive page without a separate endpoint.
- Expose two new PATCH action endpoints — /api/projects/{id}/archive/ and
  /api/projects/{id}/unarchive/ — that toggle the archived state and update the timestamp.
- Add an "Archive" option to each project card's context menu that calls the archive endpoint,
  removes the card with a CSS fade-out, and offers a five-second Undo toast notification.
- Create a new archive page at frontend/app/projects/archive/page.tsx that fetches and
  displays archived projects in a visually muted, reduced-opacity style for clear distinction.
- Add an "Archive" navigation link in the sidebar directly below the main "Projects" link,
  using a smaller size or indentation level to mark it as a sub-section of the projects area.

### 1.3 Scope

#### In Scope

| Item | Description |
|---|---|
| is_archived field | Add BooleanField with default False to Project model and migrate |
| archived_at field | Add DateTimeField nullable to record when archiving occurred |
| Archive / Unarchive endpoints | Two PATCH endpoints to toggle archived state on any single project |
| Archive list page | New frontend page that shows only archived projects with unarchive action |

#### Out of Scope

| Item | Description |
|---|---|
| Bulk archive | Selecting and archiving multiple projects at once in a single action |
| Auto-archive rules | Automatically archiving projects after X days of inactivity |
| Permanent deletion | Deleting a project and its files from the server entirely |
| Export before archive | Bundling all project files into a zip before archiving |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| backend/api/models.py | Defines the Project model with all database fields | Has name, status, render_settings, created_at, updated_at — no archive fields |
| backend/api/serializers.py | Converts Project model instances to/from JSON for the API | Serializes existing fields; does not include is_archived or archived_at |
| backend/api/views.py | Contains DRF views for all project and segment operations | ProjectListView returns all projects without archive filtering |
| backend/api/urls.py | Maps URL patterns to view functions | No archive-related URL patterns exist yet |
| frontend/app/projects/page.tsx | The main project list page rendered in Next.js | Displays all projects; has no archive action in the UI |
| frontend/components/Sidebar.tsx | The persistent left-side navigation component | Has a Projects link but no sub-links for Archive |

---

## 2. Flow Diagram

    Creator clicks "Archive" on a project card
                    |
                    v
    Frontend sends PATCH /api/projects/{id}/archive/
                    |
                    v
    Backend view sets is_archived=True, archived_at=now()
                    |
                    v
    Returns updated project object with 200 OK
                    |
                    v
    Frontend removes card from list with fade-out animation
                    |
                    v
    Toast notification appears: "Project archived. Undo?"
                    |
           ---------+---------
           |                 |
    User clicks Undo   Timer expires (5s)
           |                 |
    PATCH /unarchive/   Toast dismissed
           |                 |
    Card fades back in  Archive complete
           |
    Project restored to active list

---

## 3. Step-by-Step Instructions

Each step below describes the exact files to open, the specific classes or functions to locate,
and the precise changes to make in plain English without any code.
Follow each step in order, as later steps depend on the database fields and endpoint logic
introduced by the earlier ones.

### Step 1 — Extend the Project Model and Run Migration

Open `backend/api/models.py` and locate the Project class definition where the existing
fields such as name, status, render_settings, created_at, and updated_at are declared.

Add a new `is_archived` field as a BooleanField with default=False placed directly after
the updated_at field, so that all existing projects are automatically treated as non-archived
and visible in the standard project list as soon as the migration is applied.

Add a second new field called `archived_at` as a DateTimeField with null=True and blank=True
so that this timestamp column is entirely optional and will be populated only when a project
is actually sent to the archive via the API endpoint created in Step 3.

After saving the model file, run the Django makemigrations command to generate a new migration
file inside the backend/api/migrations/ directory, giving the migration a descriptive name
such as add_project_archiving_fields so the intention is clear in version control history.

Run the Django migrate command to apply the new migration to the local SQLite development
database, then inspect the database to confirm that both the is_archived and archived_at
columns have been added to the api_project table without any data loss or type errors.

Open `backend/api/serializers.py`, locate the ProjectSerializer's fields declaration, and
add both `is_archived` and `archived_at` to the list so that every project API response
includes the current archive state and timestamp for the frontend to consume.

### Step 2 — Update ProjectListView to Filter by Archive Status

Open `backend/api/views.py` and locate the class or function that handles GET requests
to the /api/projects/ endpoint — this is the view responsible for returning the list of
projects that the frontend renders on the main projects page.

Change the default queryset expression from returning all Project objects to filtering
by `is_archived=False` so that unarchived, active projects are always returned by default
without requiring any explicit query parameter from the frontend client.

Add logic near the top of the list handler to inspect an incoming query parameter named
`archived`, and when that parameter's value equals the string "true", switch the queryset
to filter by `is_archived=True` instead of False, returning only the archived project set.

Apply the same `order_by('-updated_at')` ordering clause to both conditional branches of
the queryset so that the most recently updated projects always appear first regardless of
whether the caller is viewing the active list or the archived list.

Ensure that any pagination envelope or `count` field returned in the response reflects
only the currently filtered subset rather than the total count of all projects, so the
frontend pagination component shows the correct number of pages for each view.

### Step 3 — Add Archive and Unarchive Action Endpoints

In `backend/api/views.py`, create a new view class called `ArchiveProjectView` that
handles PATCH requests to the URL pattern /api/projects/{id}/archive/ and contains
all the logic needed to set a project's archived state on the server side.

Inside ArchiveProjectView, retrieve the specific Project instance by its primary key
extracted from the URL kwargs, then set `is_archived` to True and set `archived_at`
to the current UTC datetime by calling Django's `timezone.now()` utility function.

Save the updated model instance using the save() method and return the full serialized
project object using the ProjectSerializer inside an HTTP 200 Response, so the frontend
receives the updated field values including the new archived_at timestamp.

Create a parallel view class called `UnarchiveProjectView` for PATCH requests to the URL
/api/projects/{id}/unarchive/ that sets `is_archived` back to False and explicitly
sets `archived_at` back to None, then saves the instance and returns the updated object.

Open `backend/api/urls.py` and add two new path() entries, registering the archive URL
pattern to ArchiveProjectView.as_view() and the unarchive URL pattern to
UnarchiveProjectView.as_view() in the API URL configuration.

Return an HTTP 404 response if the project ID provided in the URL does not match any
existing project, and return an HTTP 400 response if the project is already in the exact
archived state being requested, with a descriptive error message in both cases.

### Step 4 — Add Archive Action to the Project List Frontend

Open `frontend/app/projects/page.tsx` and locate the JSX section that maps over the
projects array and renders an individual card component for each project, which is where
the Archive button needs to be added as a new action alongside existing card options.

Add a new "Archive" menu item or button to each project card's existing actions dropdown
or context menu, positioned near other project-management actions such as "Edit" or "Delete"
so that the archive action is logically co-located with similar project management operations.

Wire the Archive button's onClick handler to an async function that calls the PATCH
/api/projects/{id}/archive/ endpoint, and on successful response updates the local Zustand
store or React component state to remove that project from the currently rendered list.

Apply a CSS opacity and transform transition class to the project card element before removing
it from state so the card fades out and slightly shrinks over approximately 300 milliseconds,
giving the interface a polished and professional feel rather than an abrupt disappearance.

Immediately after the archive API call succeeds and the animation begins, trigger a toast
notification displaying "Project archived. Undo?" with a clearly visible Undo button that
remains active for exactly five seconds before the toast auto-dismisses.

If the user clicks the Undo button within the five-second window, call PATCH
/api/projects/{id}/unarchive/ and re-insert the project card back into the list at its
original index position, which must be captured in a ref or closure before removing it.

### Step 5 — Create the Archive View Page and Sidebar Link

Create the new file `frontend/app/projects/archive/page.tsx` as a standard Next.js page
component that on mount calls GET /api/projects/?archived=true and stores the resulting
array of archived projects in local component state or a dedicated Zustand store slice.

Render the archived projects using the exact same project card component already used on
the main list page, but pass a prop or apply a CSS modifier class that reduces each card's
opacity to approximately 60 percent and adds a CSS grayscale filter to communicate inactivity.

Include an "Unarchive" button on each archived project card wired to the PATCH
/api/projects/{id}/unarchive/ endpoint, and on a successful response remove that card
from the local archive list with the same fade-out animation used in the main list.

Add a descriptive banner or subtitle element at the top of the archive page — for example,
"Archived projects are hidden from the main project list. Click Unarchive to restore any
project to your active workspace." — to orient the creator when they first visit this page.

Open `frontend/components/Sidebar.tsx` and insert a new navigation link element labeled
"Archive" positioned directly below the main "Projects" link, styled with a slightly smaller
font size and a left padding indent of 12 to 16 pixels to mark it as a child navigation item.

Wire the Archive sidebar link to the Next.js Link component pointing to the /projects/archive
route, and use the usePathname hook to compare the current path and apply a highlighted active
style class when the user is already on the archive page.

---

## 4. Expected Outcome

After completing all five implementation steps, the following observable behaviors and
technical conditions should all be true in a correctly functioning environment.

1. The Project model in the database gains two new columns — `is_archived` (boolean, default
   false) and `archived_at` (nullable datetime) — applied cleanly via a versioned migration
   file with no data loss or type mismatches on any previously existing project rows.

2. The default GET /api/projects/ endpoint returns only projects where `is_archived` is false,
   making the main project listing page show only active, in-progress work for all sessions
   without requiring any additional parameters from the frontend client.

3. Calling GET /api/projects/?archived=true returns only the archived subset of projects,
   enabling the dedicated archive page to display its own list correctly without any
   additional backend view or URL pattern beyond what is defined on the list endpoint.

4. The PATCH /api/projects/{id}/archive/ endpoint sets `is_archived=True` and populates
   `archived_at` with the current UTC time, and the unarchive endpoint reverses both fields,
   with both endpoints returning the full updated project object and HTTP 200.

5. The main project list page in the frontend removes the archived project card with a
   smooth CSS fade-out animation when Archive is triggered, and the five-second undo toast
   allows the action to be fully reversed in-place without requiring a page reload.

6. The new archive page at /projects/archive displays archived projects in a visually muted
   style using reduced opacity and a grayscale CSS filter, with per-card Unarchive buttons
   that restore any project back to the active list on click.

7. The sidebar renders an "Archive" sub-link indented below the main Projects link, using
   the usePathname hook to apply an active highlight when on the archive page, giving
   creators persistent one-click access to their archived project collection.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] Test that the Project model's `is_archived` field defaults to False when a new project
  instance is created without explicitly setting the field, verifying the migration default applies.

- [ ] Test that `archived_at` is None on a newly created project and is populated with
  a non-null UTC datetime value immediately after the archive endpoint is called via the test client.

- [ ] Test that ProjectListView returns zero archived projects when the `?archived` parameter
  is absent, and returns only archived projects when `?archived=true` is passed in the test request.

- [ ] Test that ArchiveProjectView correctly sets `is_archived=True` and populates `archived_at`
  with a recent datetime when called with a valid project ID, and that the response status is HTTP 200.

- [ ] Test that UnarchiveProjectView correctly sets `is_archived=False` and resets `archived_at`
  to None when called on a currently archived project, and that the response status is HTTP 200.

### 5.2 Integration / Manual Tests

- [ ] Manually create three projects in the UI, archive two of them using the card context
  menu, and confirm that only one project appears in the main list immediately after the fade-out.

- [ ] Navigate to /projects/archive in the browser and confirm both archived projects appear
  in the archive view with visually muted styling and working Unarchive buttons.

- [ ] Click "Unarchive" on one of the archived project cards and verify the card disappears
  from the archive view and that navigating back to the main list shows the restored project.

- [ ] Archive a project and immediately click the "Undo" button in the toast notification within
  the five-second window, confirming the project card smoothly reappears in the main list.

- [ ] Click the "Archive" sub-link in the sidebar and confirm the route changes to /projects/archive
  and that the sidebar Archive link receives its active highlight styling.

- [ ] Send a direct API PATCH request to the archive endpoint using a non-existent project ID
  and confirm the HTTP response status is 404 with an appropriate JSON error message.

### 5.3 Regression Tests

- [ ] Confirm that the main project list still loads correctly for all existing projects after
  the migration has been applied, with no previously created project inadvertently set to archived.

- [ ] Confirm that all existing project CRUD endpoints — create, retrieve, update, and delete —
  continue to function exactly as before after the archive fields are added to the serializer.

- [ ] Confirm that the project detail page at /projects/[id]/page.tsx loads correctly for
  both archived and unarchived projects, displaying project data without any thrown exceptions.

---

## 6. Notes for AI Agent

- When adding the `is_archived` filter to ProjectListView, apply the filter only inside the view's
  get_queryset method rather than on the model's default manager, because the task queue, segment
  views, and any internal lookup by primary key must still be able to access archived projects.

- The `archived_at` timestamp must always be stored in UTC using Django's `timezone.now()` rather
  than Python's `datetime.now()`, as the latter ignores the time zone setting in Django's settings.py
  and will produce incorrect timestamps if the server is ever deployed in a non-UTC environment.

- On the frontend, the fade-out animation for the project card must be implemented by adding a CSS
  transition class to trigger the opacity change, then scheduling a setTimeout for the same duration
  as the CSS transition before calling the state update that removes the element from the React tree.

- The Undo toast implementation must capture a copy of the full project data object before removing
  it from Zustand state, because once the state is updated the data is gone and cannot be re-inserted
  at the correct list position if the user clicks Undo after the state removal has occurred.

- If a project's `is_archived` value is changed through a separate browser tab or a direct API call
  during an active session, the frontend will not detect the change because there is no WebSocket or
  polling mechanism; this is acceptable for v1 but should be flagged as a future real-time sync task.
