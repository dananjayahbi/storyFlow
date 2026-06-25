# Feature 4.4 — Disk Space Management

| Field | Value |
|---|---|
| Feature ID | 4.4 |
| Title | Disk Space Management |
| Status | 🟡 Planned |
| Priority | High |
| Complexity | Medium |
| Estimated Effort | 3–5 days |
| Dependencies | Feature 1.1 (Project Model), Feature 1.2 (Segment Model), Celery task runner |
| Output Files (NEW) | backend/api/storage_utils.py, frontend/app/settings/storage/page.tsx |
| Files Modified | backend/api/views.py, backend/api/urls.py, backend/api/models.py, frontend/app/projects/[id]/page.tsx, frontend/app/projects/page.tsx, frontend/components/StorageBar.tsx |

---

## 1. Document Overview

### 1.1 Problem Statement

Every StoryFlow project accumulates a significant volume of media files on disk over its lifecycle:
per-segment PNG source images, per-segment WAV or MP3 audio files produced by the TTS engine,
any intermediate processing artifacts generated during rendering, and the final output MP4 file
itself — all stored under the project's subdirectory inside the configured media root. A single
rendered project can consume between 50 MB and 200 MB depending on segment count, image
resolution, and audio duration, meaning a creator who regularly produces content can silently
accumulate 50 to 100 gigabytes of storage without ever receiving a warning or a summary. There
is currently no mechanism within the StoryFlow user interface to visualize, measure, or reclaim
disk space from projects that have already been completed and whose intermediate files are no
longer needed. Without storage management tooling, the application will eventually exhaust the
host machine's disk capacity and begin failing at file write operations during render tasks,
causing opaque errors that are difficult to diagnose and frustrating for the end user.

### 1.2 Proposed Solution

Introduce a dedicated disk space monitoring and cleanup system consisting of a backend utility
layer that computes per-project and global storage usage, a set of cleanup API endpoints that
selectively remove intermediate or redundant files, and a frontend storage management interface
that gives creators clear visibility into their media footprint and actionable controls to
reclaim space. The solution is designed to be non-destructive by default: cleanup operations
are gated behind the project's completion status and require explicit user confirmation before
any files are deleted.

- Add a utility function in a new module `backend/api/storage_utils.py` that walks the project
  media directory and returns a structured breakdown of storage consumption by file category.
- Expose a `GET /api/projects/{id}/storage/` endpoint that returns per-project storage metrics
  including total bytes, image bytes, audio bytes, output file bytes, and segment file count.
- Expose a `POST /api/projects/{id}/clean-intermediate/` endpoint that removes audio and
  temporary processing files while preserving source images and the final MP4 output.
- Expose a `POST /api/projects/{id}/compact/` endpoint that goes further and also removes
  source images, leaving only the final rendered MP4, and only when project status is complete.
- Expose a `GET /api/storage/summary/` endpoint that aggregates storage usage across all
  projects and returns a sorted list for a global dashboard view.
- Build a `StorageBar` React component in `frontend/components/StorageBar.tsx` that renders
  a segmented horizontal bar chart showing images, audio, and output proportions in distinct
  colors with labeled MB values for each category.
- Create a new `frontend/app/settings/storage/page.tsx` global storage management page with
  a budget progress bar and per-project cleanup controls in a sortable table.

### 1.3 Scope

#### In Scope

| Item | Description |
|---|---|
| Per-project storage metrics | Walking the media directory and returning byte counts per file category for any given project |
| Selective file cleanup | Removing intermediate audio files or full source media while preserving the rendered output |
| Global storage dashboard | A settings page showing total disk usage, budget threshold, and per-project space consumption |
| Storage budget warning | A configurable storage budget setting with a warning banner when usage exceeds 80 percent |

#### Out of Scope

| Item | Description |
|---|---|
| Cloud storage integration | Offloading media files to S3 or similar remote storage is not part of this feature |
| Automatic scheduled cleanup | Automated nightly or cron-based cleanup jobs are excluded from this initial implementation |
| Compression of existing files | Re-encoding or compressing already-stored images or audio is out of scope here |
| Cross-project deduplication | Detecting and de-duplicating identical image assets shared between projects is not included |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| backend/api/views.py | DRF API views; will receive storage and cleanup endpoints | Existing; contains project CRUD and render trigger views |
| backend/api/models.py | Project and Segment ORM models | Existing; no storage-related fields currently present |
| backend/api/storage_utils.py | New utility module for directory walking and byte accounting | Does not exist; must be created |
| frontend/app/projects/[id]/page.tsx | Project detail editor page | Existing; will receive a new Storage section panel |
| frontend/app/settings/storage/page.tsx | New global storage management page | Does not exist; must be created |

---

## 2. Flow Diagram

    Creator opens project detail page
            |
            v
    Frontend calls GET /api/projects/{id}/storage/
            |
            v
    storage_utils.compute_project_storage(project_id)
       walks media directory, sums bytes by category
            |
            v
    Returns { total_bytes, image_bytes, audio_bytes,
              output_bytes, segment_count }
            |
            v
    StorageBar renders color-coded breakdown bar
            |
         [User action?]
            |
      ------+------
      |            |
      v            v
  Clean         Compact
  Intermediate  Project
  Files         (images + audio)
      |            |
      v            v
  POST /clean-  POST /compact/
  intermediate/ (status==complete
  (audio only)   required)
      |            |
      v            v
    Files deleted, response returns
    updated storage metrics to frontend

---

## 3. Step-by-Step Instructions

### Step 1 — Create the Storage Utility Module

Create a new file at `backend/api/storage_utils.py` to house all disk-space accounting logic,
keeping the view layer clean and the logic independently testable. The primary function
`compute_project_storage(project_id)` should accept a Django project ID, resolve the project's
media root subdirectory from the `Project` model record, and then use `os.walk` to enumerate
every file under that directory recursively. As it walks the directory, it should categorize
each file by extension: PNG and JPG files count toward `image_bytes`, WAV and MP3 files count
toward `audio_bytes`, MP4 files count toward `output_bytes`, and all remaining files accumulate
into an `other_bytes` bucket for unexpected artifacts. The function should return a Python
dictionary containing all five byte counters, the total segment count derived from the
`Segment` queryset, and the absolute path of the project media directory for reference by the
calling view.

### Step 2 — Add Backend Storage and Cleanup API Endpoints

Open `backend/api/views.py` and add three new class-based or function-based DRF views for
storage operations, then register their URL patterns in `backend/api/urls.py`. The first view
handles `GET /api/projects/{id}/storage/` and calls `compute_project_storage` from the utility
module, returning the structured byte breakdown as a JSON response. The second view handles
`POST /api/projects/{id}/clean-intermediate/` and must first verify that the project status is
"complete" before it iterates over all `Segment` records and calls `os.remove` on each
`audio_file` path, then removes any temporary files in the project media directory that are not
PNG, JPG, or MP4 — it returns a summary of how many files were deleted and how many bytes were
freed. The third view handles `POST /api/projects/{id}/compact/` and performs a deeper cleanup
that also removes segment image files from disk and clears the `image_file` fields on the
`Segment` records in the database, preserving only the final MP4, and it must also be gated
behind the "complete" status check to prevent destroying an in-progress project.

### Step 3 — Add the Global Storage Summary Endpoint

Add a fourth endpoint `GET /api/storage/summary/` in `backend/api/views.py` that queries all
`Project` records, calls `compute_project_storage` for each one, assembles a list of per-project
storage dictionaries, and returns the aggregate sorted by `total_bytes` in descending order so
that the largest projects appear first in the frontend dashboard. This endpoint does not require
a project ID parameter — it operates globally across all projects in the database. The response
envelope should include a `total_bytes` field that sums all project totals, a `total_projects`
count, and a `projects` array where each item contains the project's `id`, `name`, `status`,
`total_bytes`, `image_bytes`, `audio_bytes`, and `output_bytes` fields for frontend rendering.
Register this endpoint at the router level in `backend/api/urls.py` under the `/api/storage/`
prefix separate from the project-scoped routes.

### Step 4 — Build the Storage Section in the Project Detail Page

Open `frontend/app/projects/[id]/page.tsx` and add a new collapsible "Storage" section below
the existing render settings panel in the project editor layout. This section should fetch
storage data on mount by calling `GET /api/projects/{id}/storage/` and storing the result in
a local React state variable, then render a `StorageBar` component imported from
`frontend/components/StorageBar.tsx` that displays three colored segments for images, audio,
and output with labeled megabyte values below each segment. Below the bar, add two action
buttons: "Clean Intermediate Files" and "Compact Project (keep MP4 only)" — both should
open a confirmation dialog using the existing Shadcn/UI dialog component before dispatching
the respective POST request. After a successful cleanup action, re-fetch the storage data so
the bar updates to reflect the new totals without requiring a page reload.

### Step 5 — Create the Global Storage Management Settings Page

Create `frontend/app/settings/storage/page.tsx` as a new Next.js page route under the settings
section of the application. At the top of the page, fetch from `GET /api/storage/summary/` on
mount and render the total disk usage as a large horizontal progress bar that fills proportionally
toward a configurable storage budget; the budget value should be read from a Zustand global
settings store (or localStorage as a fallback) and default to 100 GB expressed in bytes. Add a
numeric input field labeled "Storage Budget (GB)" that writes changes back to the settings store
so the threshold persists across sessions. Below the summary bar, render a full-width data table
of all projects sorted by size descending, with columns for project name, status, total size in
MB, and a per-row "Clean" button that calls `POST /api/projects/{id}/clean-intermediate/` inline.
Wire up a global warning banner that appears at the top of the application layout component when
total usage exceeds 80 percent of the configured budget, using a Zustand selector to keep the
banner reactive.

---

## 4. Expected Outcome

1. Calling `GET /api/projects/{id}/storage/` for any existing project returns a valid JSON
   response with `total_bytes`, `image_bytes`, `audio_bytes`, `output_bytes`, and
   `segment_count` fields accurately reflecting the files on disk.
2. The `StorageBar` component renders correctly in the project detail page with three distinct
   color-coded segments whose widths and labels match the storage breakdown returned by the API.
3. Clicking "Clean Intermediate Files" in the project detail page, confirming the dialog, and
   receiving a 200 response causes the audio files to be removed from disk and the storage bar
   to update its audio segment to zero without a page reload.
4. Clicking "Compact Project" on a completed project removes both audio and image files from
   disk and clears the corresponding `image_file` foreign key fields on all `Segment` records.
5. Attempting to call either cleanup endpoint on a project whose status is not "complete" returns
   a 400 or 403 error response with a descriptive message and does not delete any files.
6. The global storage settings page renders a correct total usage bar and a sortable project
   table populated from the `/api/storage/summary/` endpoint within two seconds of page load.
7. When total storage usage exceeds 80 percent of the configured budget, a persistent warning
   banner appears at the top of the application layout and disappears when usage drops below
   the threshold or the budget is adjusted upward.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] `compute_project_storage` returns correct byte totals when given a project ID whose
      media directory contains a known set of test files with known sizes.
- [ ] `compute_project_storage` returns all-zero values without raising an exception when the
      project media directory does not exist or is empty.
- [ ] The `clean-intermediate` endpoint returns 400 when called on a project with status other
      than "complete" and does not modify any files on disk.
- [ ] The `compact` endpoint correctly removes image files from the Segment records in the
      database after a successful cleanup operation on a completed project.
- [ ] The `storage/summary/` endpoint returns a list sorted by `total_bytes` descending and
      includes all projects in the database regardless of their status.

### 5.2 Integration / Manual Tests

- [ ] Create a project, render it, then call the storage endpoint and verify the returned byte
      counts match the actual sizes of files in the project media directory on disk.
- [ ] Open the project detail page, navigate to the Storage section, and confirm the bar renders
      with correct proportions for a project that has image, audio, and output files present.
- [ ] Click "Clean Intermediate Files", confirm the dialog, and then manually verify on disk that
      the audio files are gone but the source images and final MP4 still exist.
- [ ] Navigate to Settings → Storage and verify the global total and per-project rows load
      correctly and reflect the current state of the filesystem.
- [ ] Set the storage budget to a value smaller than the current total usage and confirm the
      warning banner appears at the top of the application layout immediately.
- [ ] Set the storage budget back above the current usage and confirm the warning banner
      disappears without requiring a page reload.

### 5.3 Regression Tests

- [ ] Verify that all existing project creation, editing, and rendering workflows remain
      unaffected after the new storage utility module and cleanup endpoints are added.
- [ ] Confirm that the project detail page still loads and renders all existing sections
      correctly after the new Storage section is inserted into the layout.
- [ ] Ensure that calling the compact endpoint on a project does not corrupt the project
      database record or cause a 500 error on subsequent GET requests for that project.

---

## 6. Notes for AI Agent

- The `compute_project_storage` utility must handle the case where the project media directory
  path does not exist yet (e.g., a newly created project that has no files), returning zeros
  gracefully rather than raising a `FileNotFoundError`.
- When implementing the cleanup endpoints, always resolve file paths using Django's
  `default_storage` or the `MEDIA_ROOT` setting rather than constructing raw OS paths from
  the request, to ensure compatibility with any configured storage backend.
- The `StorageBar` component should express all values in human-readable megabytes rounded to
  one decimal place in its labels, even though the API returns raw byte counts, to keep the
  display clean for non-technical users.
- Both cleanup endpoints should return a response body that includes the number of files
  deleted, the bytes freed, and the updated storage metrics so the frontend can update its
  state in a single round trip without making a second GET request.
- The global storage warning banner should be implemented at the root layout level using a
  Zustand selector so it is reactive and automatically appears or disappears as storage
  changes without requiring a full navigation event or page refresh.

---

## 7. Implementation Risks and Mitigations

- **Risk: Race condition between cleanup and active render tasks.** If a creator triggers the
  clean-intermediate endpoint while a Celery render task is still writing audio files for that
  same project, the cleanup code could delete files that are actively being written, causing
  the render task to fail with a file-not-found error mid-execution. Mitigation: the cleanup
  endpoints must check not only the project's stored status field but also inspect the Celery
  task ID stored on the project (if any) using Celery's AsyncResult to confirm no task is
  currently active before deleting any files. If an active task is detected, the endpoint
  should return 409 Conflict with a message instructing the creator to wait for the render
  to complete before attempting any cleanup operation.

- **Risk: Inaccurate storage metrics due to external file placement.** The compute_project_storage
  function walks a specific media subdirectory, but if any project files were placed outside
  that directory due to a configuration change or manual intervention, they will not appear
  in the count and the storage display will underreport actual disk usage. Mitigation: document
  clearly in the utility module's docstring that the function only accounts for files under the
  project's expected media subdirectory, and add a warning log entry if the subdirectory does
  not exist at the expected path so operators can detect misconfiguration early without needing
  to trace the source of inaccurate storage metrics.

- **Risk: Compact endpoint leaving orphaned database references.** After the compact operation
  removes image files from disk, the corresponding image_file fields on Segment records must
  also be cleared in the database; if only one of these two operations succeeds (e.g., the
  file is deleted but the database update fails due to a constraint), the UI may display broken
  image references pointing to files that no longer exist. Mitigation: wrap the file deletion
  and database field clearing in a single database transaction using transaction.atomic(), and
  use a try/except block that rolls back the database changes if any file deletion fails so
  the system remains in a fully consistent state with no partial cleanup artifacts.

- **Risk: Storage summary endpoint performance degradation at scale.** The global summary
  endpoint calls compute_project_storage for every project in the database, and with hundreds
  of projects each requiring an os.walk call, the response time could exceed ten seconds and
  time out in the frontend fetch. Mitigation: implement a lightweight caching layer using
  Django's cache framework that stores the most recently computed storage total per project
  and is invalidated whenever a cleanup operation runs or a new render completes, so the
  summary endpoint can return cached values without re-walking the entire filesystem on every
  single request to the dashboard page.

- **Risk: Storage budget setting lost between browser sessions.** If the storage budget is
  stored only in localStorage, it will be absent in a different browser profile, in private
  browsing mode, or after the user clears browser storage, causing the progress bar to display
  against an undefined budget and potentially hiding the warning banner even when usage is
  critical. Mitigation: store the budget value in a backend global settings record and sync it
  to the frontend on page load via an API call so the setting persists across devices, browsers,
  and sessions without depending solely on client-side storage that can be lost unexpectedly.

---

## 8. Rollout and Phasing

### 8.1 Phase One — Backend Metrics Only

In the first phase of rollout, implement only the storage_utils.py module and the
GET /api/projects/{id}/storage/ endpoint to establish the data foundation. This phase can be
deployed independently and tested by calling the endpoint directly via the browser or a REST
client without any frontend changes required. Validating the accuracy of the byte counting
logic against known project directories is the primary goal of this phase, and it should be
completed and reviewed before any cleanup logic is written. The summary endpoint
GET /api/storage/summary/ should also be included in this phase so that the global aggregate
metrics are available as a foundation for the frontend work in the next phase.

### 8.2 Phase Two — Cleanup Endpoints and Project Detail UI

In the second phase, implement both cleanup endpoints clean-intermediate and compact with their
status guards, then add the StorageBar component and the Storage section to the project detail
page. This phase introduces the first user-facing interaction with the storage system and
requires thorough manual testing of the confirmation dialog flow and the post-cleanup re-fetch
of storage metrics. The per-project storage footprint display on the project list page (the
small disk icon with MB value next to each project name) should also be shipped in this phase
since it depends only on the metrics endpoint already deployed in phase one and requires only
a small addition to the existing project card component.

### 8.3 Phase Three — Global Settings Page and Budget Warning

In the third and final phase, build the frontend/app/settings/storage/page.tsx global storage
management page, implement the storage budget preference in the Zustand settings store, and
wire up the top-level warning banner at the root application layout level. This phase is the
most frontend-heavy and depends on all backend work from phases one and two being stable and
tested. The warning banner in particular should be tested by manually adjusting the budget to
a value below the current storage total to verify it appears immediately, and then setting it
back above the total to verify it disappears without requiring any navigation event or page
reload to take effect.

