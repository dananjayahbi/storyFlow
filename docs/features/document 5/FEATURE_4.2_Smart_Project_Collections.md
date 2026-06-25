# Feature 4.2 — Smart Project Collections

| Field | Value |
|---|---|
| Feature ID | 4.2 |
| Title | Smart Project Collections |
| Status | 🟡 Planned |
| Priority | High |
| Complexity | Medium |
| Estimated Effort | 4–6 days |
| Dependencies | Existing Project model, DRF router, frontend project list page, Feature 4.1 (Project Archiving recommended but not required) |
| Output Files (NEW) | frontend/components/CollectionManager.tsx, backend/api/migrations/0X_add_collection_model.py |
| Files Modified | backend/api/models.py, backend/api/serializers.py, backend/api/views.py, backend/api/urls.py, frontend/app/projects/page.tsx, frontend/components/Sidebar.tsx |

---

## 1. Document Overview

### 1.1 Problem Statement

Creators who produce content in multiple series or categories — such as a Roman History Series, a weekly Science Facts channel, or a Horror Stories Season 2 production — have absolutely no way to group related projects together inside StoryFlow's current data model.
The flat project list treats every video as a fully independent, unrelated item, making it impossible to view all episodes of a particular series at once or to navigate quickly among the projects that share a common theme, style, or production schedule.
Applying a shared setting change — such as updating the default aspect ratio or output resolution — to all projects in a series requires opening each project individually, which becomes prohibitively time-consuming as series grow beyond five or six episodes.
As the total video library grows over months of production, the complete absence of any organization layer beyond a date-sorted flat list transforms the workspace from a productive tool into a disorganized archive of hundreds of identically styled cards with no way to mentally cluster them.

### 1.2 Proposed Solution

Introduce a "Collections" system that allows creators to create named, color-coded collections
— functioning similarly to folders or playlists — and assign each project to one collection,
with support for parent-child collection nesting to enable series and season hierarchies.

The implementation uses a new Collection database model linked to the existing Project model
via a ForeignKey, keeping the schema minimal and straightforward for v1 and avoiding the added
complexity of a many-to-many join table until multi-collection membership is actually needed.

The frontend exposes a dedicated CollectionManager component as a modal or drawer for creating,
editing, and deleting collections, and integrates a collection filter panel into the main project
list page so clicking any collection immediately narrows the visible project grid.

- Create a new `Collection` database model with name, description, color, parent ForeignKey,
  and created_at fields to support both flat collections and nested parent-child hierarchies.
- Add a nullable `collection` ForeignKey to the Project model so any project can be assigned
  to at most one collection, keeping the data relationship predictable and easy to query.
- Expose a CollectionViewSet in the Django backend with full CRUD coverage, annotating each
  collection with its project count so labels in the frontend require no additional requests.
- Add a collections filter panel into the main /projects page that shows all collections as
  colored chips or a list and filters the project grid when any collection entry is clicked.
- Create a new `CollectionManager.tsx` modal component for creating, renaming, recoloring,
  and deleting collections, triggered by a button above the project grid on the projects page.
- Add a "Collection" assignment dropdown to both the project creation modal and the project
  settings panel so creators can assign or change a project's collection within existing flows.
- Show nested sub-collections as indented child entries in the sidebar and CollectionManager,
  communicating the two-level hierarchy without needing a full recursive tree widget.

### 1.3 Scope

#### In Scope

| Item | Description |
|---|---|
| Collection model | New Django model with name, color, description, parent FK, and created_at |
| Project collection FK | Nullable ForeignKey from Project to Collection for single-collection assignment |
| Collection CRUD API | Full list, create, retrieve, update, delete via DRF ViewSet |
| Frontend filter panel | Collection chips/list in the projects page sidebar that filter the project grid |

#### Out of Scope

| Item | Description |
|---|---|
| Many-to-many collections | Assigning a single project to multiple collections simultaneously |
| Drag-and-drop reordering | Manually ordering projects within a collection by dragging cards |
| Collection-level settings | Applying a shared render setting or style override to all projects in a collection |
| Collection sharing | Sharing or publishing a collection view link with external collaborators |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| backend/api/models.py | Defines all database models including Project and Segment | No Collection model exists; Project has no collection FK |
| backend/api/serializers.py | Serializes model instances to JSON for API responses | ProjectSerializer does not include collection data |
| backend/api/views.py | Contains DRF views for all existing API endpoints | No CollectionViewSet exists; ProjectListView has no collection filtering |
| backend/api/urls.py | Registers URL patterns and the DRF router | No collection routes registered |
| frontend/app/projects/page.tsx | Main project list page in Next.js | No collection filter panel or collection assignment UI |
| frontend/components/Sidebar.tsx | Persistent left-side navigation component | Static list of links; no dynamic collection listing |

---

## 2. Flow Diagram

    Creator opens Projects page
                |
                v
    CollectionFilter panel renders on left
    Lists all collections with color badges
                |
        --------+--------
        |               |
    No collection   Collection selected
    selected        |
        |           v
    All projects    GET /api/projects/?collection={id}
    displayed       |
                    v
                Filtered project grid renders
                    |
                    v
    Creator clicks "Manage Collections" button
                    |
                    v
    CollectionManager modal opens
                    |
         -----------+-----------
         |          |           |
      Create     Rename      Delete
      new coll.  existing    collection
         |          |           |
      POST       PATCH       DELETE
      /collections/ /collections/{id}/ /collections/{id}/
         |          |           |
         v          v           v
    Sidebar and filter panel refresh with updated collection list

---

## 3. Step-by-Step Instructions

Each step below identifies exact files to open, specific models or components to create or modify,
and precisely what each change must accomplish, all described in plain English without code.
Complete the steps in the order listed, because later steps depend on the database model and API
endpoints introduced in the first two steps.

### Step 1 — Create the Collection Model and Run Migration

Open `backend/api/models.py` and add a brand new Django model class called `Collection`
positioned above the existing Project class definition so that Project's ForeignKey to
Collection can reference it directly without a quoted forward-reference string.

Define the following fields on Collection: `name` as a CharField with max_length=100;
`description` as a TextField with blank=True and an empty default; `parent` as a
ForeignKey to self with null=True, blank=True, on_delete=SET_NULL, related_name="subcollections";
`cover_color` as a CharField with max_length=7 and a default of "#6366f1"; and `created_at`
as a DateTimeField with auto_now_add=True.

Add a `collection` ForeignKey to the Project model pointing at the Collection model with
null=True, blank=True, and on_delete=SET_NULL so that deleting a collection never cascades
into deleting the projects that were grouped inside that collection.

Run Django makemigrations with the descriptive name "add_collection_model_and_project_fk"
to generate the migration file inside backend/api/migrations/, then run migrate to create the
new api_collection table and add the collection_id column to the api_project table.

Open `backend/api/serializers.py` and create a new `CollectionSerializer` class that exposes
all Collection fields including a read-only `project_count` integer field populated via
annotation in the view layer rather than computed inside the serializer itself.

Update the existing `ProjectSerializer` to add `collection_id` as a writable integer field
and `collection_name` as a read-only SerializerMethodField returning the collection's name
string or null when the project has no collection currently assigned.

### Step 2 — Build the CollectionViewSet in the Backend

Open `backend/api/views.py` and add a new `CollectionViewSet` class that inherits from
DRF's ModelViewSet to automatically provide the full set of HTTP methods — list, create,
retrieve, update, partial_update, and destroy — for the Collection model.

In the list action, annotate each queryset element with a `project_count` value using Django's
Count() aggregation with distinct=True on the linked projects, so each response object includes
an accurate count badge value without requiring a second API call from the client.

Order the CollectionViewSet list queryset by `created_at` descending by default, and override
the ordering to alphabetical by name when the frontend passes an `?ordering=name` query
parameter, allowing the filter panel to sort collections in the way most useful to the creator.

Add logic to the list action to handle a `?parent_id` filter: when `?parent_id=null` is passed
return only top-level collections with no parent assigned; when `?parent_id={id}` is passed
return only the direct children of that specified parent collection.

In the existing `ProjectListView`, add a new block of queryset filtering logic that checks
for a `?collection={id}` query parameter and, when a valid integer is present, narrows the
project queryset to only include projects where `collection_id` matches that value.

Open `backend/api/urls.py` and register the new CollectionViewSet with the existing DRF router
using `router.register("collections", CollectionViewSet, basename="collection")` so that all
standard REST URL patterns are auto-generated at the /api/collections/ path prefix.

### Step 3 — Add the Collection Filter Panel to the Projects Page

Open `frontend/app/projects/page.tsx` and restructure the top-level layout to accommodate
a left-side filter panel alongside the existing project card grid, using a flex or CSS grid
layout with a fixed-width column of approximately 220 pixels for the panel.

Fetch the full collection list from GET /api/collections/ when the projects page mounts and
store the resulting array in either the Zustand projects store or in component-level state,
alongside the existing projects data that the page already fetches.

Render each collection in the filter panel as a clickable chip or list row that displays the
collection's `cover_color` as a small filled dot or rounded pill, the collection name in
readable text, and the project count inside a small muted badge to the right of the name.

Track the currently selected collection ID in the Zustand store or as a URL search parameter
such as `?collection={id}`, and when any chip is clicked update the active filter and fetch
GET /api/projects/?collection={id} to refresh the project grid with only that collection.

Add an "All Projects" entry at the very top of the filter panel list that clears the active
collection filter, returns the project grid to the full unfiltered list, and is styled slightly
bolded compared to other entries to mark it as the default unfiltered state.

Ensure the filter panel renders in a scrollable container so that it remains usable when a
creator has many collections that exceed the available viewport height, keeping the project
grid fully visible alongside the panel throughout the scroll.

### Step 4 — Build the CollectionManager Modal Component

Create the file `frontend/components/CollectionManager.tsx` as a reusable React component
that renders as a slide-in drawer or a centered dialog modal, and is triggered by a
"Manage Collections" button placed clearly above the project grid on the projects page.

Inside the CollectionManager, render the current list of all collections in a compact row:
show the color dot, the collection name, the project count badge, and two icon action
buttons per row — one for renaming or recoloring, and one for deleting the collection.

At the top of the CollectionManager, implement a "Create New Collection" form as an inline
section containing a text input for the name, a set of preset color swatch buttons for the
cover_color field, an optional description textarea, and a parent collection dropdown.

Wire the creation form's submit action to POST /api/collections/ with the entered data;
on success, append the new collection to the local list and trigger a refresh of the sidebar
and filter panel; display an inline validation error without closing the modal on failure.

For the edit action on each row, replace the read-only list item with an inline edit form
pre-filled with the existing values, and on save call PATCH /api/collections/{id}/ using
a partial update so only the changed fields are sent to the server.

For the delete action, show a brief inline confirmation prompt explaining that deleting a
collection will not remove the projects within it — only the label will be cleared — and
on confirmation call DELETE /api/collections/{id}/ and remove the row from the local list.

### Step 5 — Integrate Collection Assignment into Project Create and Edit Flows

Locate the project creation modal or form component in the frontend codebase and add a new
"Collection" dropdown field positioned after the project name or status field, so the creator
can optionally assign a collection at the moment of creating a new project.

Render this dropdown populated with the collections array from the Zustand store, showing each
option's color dot and name together; include a "None" option at the top for projects that
should not belong to any collection when originally created.

Add an inline "+ New Collection" entry at the bottom of the dropdown options list that, when
clicked, opens a minimal inline creation popover allowing the creator to type a name and pick
a color without needing to open the full CollectionManager modal drawer.

When the project creation form is submitted, include the selected `collection_id` value in
the POST /api/projects/ request body; the backend ProjectSerializer will accept this field
and correctly persist the collection FK after the serializer changes from Step 1.

Open the project settings or edit panel — accessible from the project detail page or the
project card's three-dot menu — and add the same Collection dropdown field wired to call
PATCH /api/projects/{id}/ with the updated collection_id when the selection changes.

In `frontend/components/Sidebar.tsx`, replace any static placeholder with a dynamically
rendered list of collection links fetched from the Zustand store, each linking to
/projects?collection={id} and showing indented child collections under their parent.

---

## 4. Expected Outcome

After completing all five steps, the following observable behaviors and technical conditions
should all be true in a correctly functioning local development environment.

1. The database gains a new `api_collection` table with name, description, cover_color, parent_id,
   and created_at columns, and the `api_project` table gains a nullable `collection_id` FK column,
   both applied cleanly via migration with no data loss on existing project rows.

2. The GET /api/collections/ endpoint returns all collections, each annotated with a `project_count`
   integer, enabling the frontend to display count badges for every collection chip immediately
   without making any secondary API requests.

3. The GET /api/projects/?collection={id} endpoint returns only the projects belonging to the
   specified collection, and GET /api/projects/ with no collection parameter continues to return
   the full non-archived project list as it did before this feature was added.

4. The CollectionViewSet handles full CRUD — creating, reading, updating, partial-updating, and
   deleting collections — with the DRF router auto-generating all URL patterns at /api/collections/
   without requiring any manual path() entries in urls.py.

5. The projects page displays a working collection filter panel with color-dot chips that highlight
   the active selection and immediately refresh the project grid whenever a different collection
   chip is clicked or the "All Projects" reset option is selected.

6. The CollectionManager modal lets creators create, rename, recolor, and delete collections from
   a single focused interface, with all changes reflected instantly in the filter panel and the
   sidebar navigation without requiring a full page reload.

7. Sub-collections created with a parent reference appear as indented child items under their
   parent in both the sidebar and the CollectionManager list, producing a clear two-level hierarchy
   that supports organizing projects into series and seasons.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] Test that creating a Collection instance with a valid name and cover_color and no parent
  saves without errors and that the project_count annotation returns 0 for a brand new collection.

- [ ] Test that assigning a Project to a Collection by setting collection_id and saving correctly
  persists the FK relationship and is reflected in the collection's project_count annotation.

- [ ] Test that deleting a Collection with SET_NULL on_delete does not delete any linked Project
  instances, and that those projects have their collection_id set to null after the deletion.

- [ ] Test that the CollectionViewSet list action returns HTTP 200 with the correct project_count
  annotation value in the response payload for each collection in the queryset.

- [ ] Test that the ProjectListView filters by collection_id correctly when a valid integer is
  passed as the `?collection` query param and returns only projects matching that FK value.

### 5.2 Integration / Manual Tests

- [ ] Create three collections — "Sci-Fi", "History", and "History > Ancient" as a child of History
  — and confirm all three appear in the filter panel with correct color badges and zero project counts.

- [ ] Assign four projects to "Sci-Fi" and two projects to "History" using the project edit flow,
  then click the "Sci-Fi" chip and verify that exactly four project cards appear in the grid.

- [ ] Open the CollectionManager, rename "Sci-Fi" to "Science Fiction", and confirm the updated
  name is immediately reflected in the filter panel, sidebar, and project card labels.

- [ ] Delete the "History" collection and confirm the two previously assigned projects remain
  intact and visible under "All Projects" with their collection field cleared to None.

- [ ] Create a new project using the creation modal, assign it to "Science Fiction" via the
  inline dropdown, and verify after saving that the project appears only under that collection.

- [ ] Confirm the sidebar dynamically lists all collections as clickable links, and that clicking
  a sidebar collection link navigates to the projects page with that collection pre-selected.

### 5.3 Regression Tests

- [ ] Confirm that all previously existing projects remain accessible under "All Projects" after the
  collection FK migration is applied, with no project inadvertently assigned or hidden by the change.

- [ ] Confirm that all existing project CRUD endpoints continue to function normally for projects
  with no collection assignment, returning null for collection-related fields without serializer errors.

- [ ] Confirm that the archive feature from Feature 4.1 (if implemented) still correctly hides
  archived projects even when a collection filter is active, so both filters work together correctly.

---

## 6. Notes for AI Agent

- The `parent` ForeignKey on Collection creates a self-referential relationship; when serializing
  nested collections for the sidebar, explicitly limit depth to two levels (parent plus direct
  children) to avoid runaway recursive serialization if deeply nested structures are ever created.

- Always include `distinct=True` inside the Count() call when annotating the CollectionViewSet
  queryset with project_count, because without it any future many-to-many relationship on Project
  could inflate the annotation and display wrong badge numbers across the filter panel.

- The `cover_color` field stores a CSS hex color string; add a custom Django validator using a
  regex that requires a hash sign followed by exactly six hexadecimal characters, and reject any
  other format with a ValidationError before the Collection instance is saved to the database.

- Store the active collection filter in the URL as a query parameter such as /projects?collection=5
  rather than only in Zustand memory, so users can bookmark and share pre-filtered views and
  the browser back button restores the correct filtered state without extra implementation work.

- When a collection is deleted via the CollectionManager while the project grid is actively
  filtered to show that collection's projects, the frontend must detect the successful delete
  response and immediately clear the filter, reverting the grid to the All Projects view so the
  creator does not encounter a confusingly empty project list with no visible explanation.
