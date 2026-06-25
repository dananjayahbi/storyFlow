# Feature 5.1 — Batch Pipeline: Bulk Import & Auto-Queue

| Field | Value |
|---|---|
| Feature ID | 5.1 |
| Title | Batch Pipeline: Bulk Import & Auto-Queue |
| Status | 🟡 Planned |
| Priority | High |
| Complexity | High |
| Estimated Effort | 8–12 days |
| Dependencies | Celery worker running and configured, existing `generate_audio_task` and `render_project_task` in `tasks.py`, `GlobalSettings` model already in `models.py`, Django REST Framework installed, `uuid` standard library available in Python |
| Output Files (NEW) | `frontend/app/batch/page.tsx`, `frontend/components/batch/BatchSetupWizard.tsx`, `frontend/components/batch/BatchProgressTable.tsx`, `frontend/store/batchStore.ts`, `backend/api/batch_views.py`, `backend/api/batch_urls.py` |
| Files Modified | `backend/api/models.py`, `backend/api/urls.py`, `backend/api/tasks.py`, `backend/api/admin.py`, `backend/storyflow_backend/settings.py`, `frontend/components/Sidebar.tsx` |

---

## 1. Document Overview

### 1.1 Problem Statement

StoryFlow currently requires a creator to perform a minimum of fifteen distinct manual actions per project in order to go from a raw script to a finished rendered video — including project creation, segment entry, individual image uploads one row at a time, a separate audio generation trigger, and a final render trigger — and this entire interaction sequence must be repeated independently for every project with no shared orchestration layer connecting the steps across multiple projects at once.

A YouTuber running a twelve-episode documentary series is therefore forced to repeat this full fifteen-step manual flow twelve times over, producing at minimum one hundred and eighty separate manual interactions before a single video has been rendered, a workload that realistically consumes the better part of a full working day even for an experienced user who knows the interface well.

Even the partial automations already present in the codebase — the fact that audio generation and rendering already run as Celery background tasks — provide no time benefit in the multi-project scenario, because the user must still manually navigate to each individual project page and click the relevant trigger button one project at a time, visiting every project page in sequence like turning pages in a book rather than submitting everything at once.

For creators working at the scale of fifty to one hundred short-form videos per week — the core targeted growth use case for StoryFlow as laid out in the product ideas documents — this manual bottleneck makes the application impractical as a production tool regardless of how fast or high-quality the underlying rendering pipeline performs.

The absence of a batch orchestration system is therefore not a convenience gap but a blocking architectural limitation that prevents StoryFlow from reaching its stated goal of producing fifty videos overnight from a single user action, and it must be resolved before any serious scale-production workflow can be demonstrated to stakeholders.

### 1.2 Proposed Solution

Introduce a dedicated "Batch Pipeline" mode as a first-class section of the application, built as a multi-step guided wizard that accepts raw input in the form of either a JSON file describing many projects or a selection of Draft projects already stored in the database, then walks the user through image folder assignment, audio queue submission, and render queue submission in a single sequential flow. The batch system tracks the lifecycle of the entire operation under a single database record and surfaces a live-polling progress dashboard so the user can monitor every project in the batch simultaneously while the system processes them asynchronously in the background.

Key implementation aspects:

- Introduce a new `BatchJob` database model in `backend/api/models.py` that acts as the authoritative record for a single batch pipeline execution. The model stores a UUID primary key generated automatically, a `JSONField` holding the flat list of integer project primary keys belonging to this batch, a `status` CharField with choices enumerated as `queued`, `running`, `completed`, and `failed`, ISO timestamp fields for `created_at` and `completed_at` (the latter nullable until the batch finishes), and a free-text `error_log` field that accumulates per-project failure messages as the batch progresses so developers can inspect what went wrong without accessing Celery task logs directly.

- A four-step guided wizard at `frontend/app/batch/page.tsx` ensures the user provides all required inputs before any backend processing begins. Step one is the input source selection, where the user uploads a JSON file containing an array of project objects each with a `name` key and a `segments` array of text strings, or switches to a "Select Existing" toggle that fetches all Draft-status projects and renders them as a labeled checkbox list. Step two covers image folder assignment. Step three presents queue configuration options. Step four shows a confirmation summary with project count, image assignment status, and estimated total processing time before the user clicks Launch.

- The image assignment step accepts two browser input methods depending on capability: a modern `showDirectoryPicker()` call via the File System Access API, which grants the frontend read access to a local folder and returns a sorted list of filenames without uploading any binary data, and a fallback `input[type="file"][multiple][webkitdirectory]` element for Firefox and Safari users. In both cases the frontend sends only the ordered list of filenames to `POST /api/batch/assign-images/` rather than the actual image binaries, and the backend matches filenames to segment `image_file` fields by positional index within each project subfolder.

- The audio queue step sends a single `POST /api/batch/generate-audio/` request containing the `batch_id` and the list of project IDs. The backend view iterates through the project IDs and calls `generate_audio_task.delay(project_id)` for each one using Celery's non-blocking `.delay()` dispatch, so all N tasks are enqueued and the API request returns HTTP 202 immediately without waiting for any single task to complete. The backend simultaneously sets `BatchJob.status` to `running` so the frontend polling dashboard transitions to the active monitoring state.

- The render queue step is structurally identical to the audio queue step but calls `render_project_task` and additionally enforces a maximum concurrency limit read live from `GlobalSettings.max_concurrent_renders`. This cap is implemented using Celery's `group` primitive to assemble a collection of render tasks, wrapped in a `chord` that executes a `batch_completion_callback` task once all chord members have resolved. The callback task sets `BatchJob.status` to `completed`, populates `BatchJob.completed_at`, and writes a final summary line to `BatchJob.error_log`. This pattern prevents the render workers from saturating system resources when large batches contain many projects.

- Per-project failure isolation is enforced at the individual Celery task level. Each `generate_audio_task` and `render_project_task` wraps its core processing logic in a try-except block that, on any unhandled exception, writes the project ID and the exception message into `BatchJob.error_log` and sets the individual project's `status` field to `Failed`. Critically, the exception is not re-raised; the Celery task returns normally so the batch-level chord callback proceeds and counts that project as resolved. This design ensures that one bad image file or one TTS API timeout does not halt the remaining nineteen projects waiting in the queue.

- Real-time progress visibility is provided by polling `GET /api/batch/{batch_id}/progress/` every three seconds from the frontend `BatchProgressTable` component. The endpoint queries the current `status` field of every project listed in `BatchJob.project_ids` and returns a structured JSON array where each element carries the project name, the current stage label, a numeric percentage estimate, and any accumulated error text. The table renders colored stage badges using ShadCN's `Badge` component, progress bars using ShadCN's `Progress` component, and an ETA column computed from the average elapsed time of projects that have already completed divided by the number still processing.

- A per-project retry mechanism is available directly from the progress table. Any project row showing the `Failed` badge exposes a "Retry" button that POSTs to `POST /api/batch/{batch_id}/retry/{project_id}/`. The backend view re-enqueues only the failed task for that project — audio generation if audio failed, rendering if rendering failed — without modifying the `BatchJob` record at the batch level or affecting any other project in the batch. This allows selective recovery from transient failures without restarting the entire overnight run.

### 1.3 Scope

| Category | Item |
|---|---|
| In Scope | Four-step wizard UI for batch creation via JSON file upload on the new `/batch` page accessible from the sidebar |
| In Scope | Four-step wizard UI path for selecting and queuing existing Draft-status projects via a checkbox list fetched from the standard projects API |
| In Scope | Image folder assignment by alphanumeric index order using File System Access API with traditional file-input fallback for unsupported browsers |
| In Scope | Bulk audio queue endpoint dispatching one `generate_audio_task` Celery call per project, returning immediately with HTTP 202 |
| In Scope | Bulk render queue endpoint with `GlobalSettings.max_concurrent_renders` cap, Celery chord-based completion callback, per-project failure isolation, 3-second polling dashboard, and individual project retry button |
| Out of Scope | AI-based semantic image-to-segment matching during the image assignment step — this is a separate feature (Feature 5.3) and should not be implemented here |
| Out of Scope | WebSocket-based real-time push updates to replace the polling dashboard; polling at 3-second intervals is sufficient for the initial release and a WebSocket upgrade path is deferred to Phase 6 |
| Out of Scope | Scheduled batch execution — automatically launching the batch pipeline at a specific future time via a cron trigger or Celery Beat schedule |
| Out of Scope | Multi-user batch access isolation; a single-user environment is assumed for this development phase and role-based access control is a later concern |
| Out of Scope | Automated social media publishing triggered after batch completion; this is the scope of Feature 5.5 and depends on platform API integrations not yet built |

### 1.4 Key Files Reference

| File | Role in This Feature |
|---|---|
| `backend/api/models.py` | Add `BatchJob` model with UUID primary key, `project_ids` JSONField, `status` CharField with choices, `created_at` and `completed_at` DateTimeFields, and `error_log` TextField; also add `max_concurrent_renders` IntegerField to existing `GlobalSettings` if not already present |
| `backend/api/batch_views.py` | New file housing all six batch DRF views: `BatchCreateView`, `BatchAssignImagesView`, `BatchAudioView`, `BatchRenderView`, `BatchProgressView`, `BatchRetryView` |
| `backend/api/tasks.py` | Add `batch_completion_callback` Celery task as a chord callback; update existing `generate_audio_task` and `render_project_task` to accept an optional `batch_id` keyword argument for error-log writing |
| `backend/api/urls.py` | Add `include('api.batch_urls')` to mount all batch routes under `/api/` prefix alongside existing API routes |
| `frontend/app/batch/page.tsx` | New Next.js App Router page: renders the four-step step indicator above `BatchSetupWizard`, then renders `BatchProgressTable` after a successful batch submission |
| `frontend/components/batch/BatchSetupWizard.tsx` | Four-step wizard container managing step transitions; contains or imports `StepSource`, `StepImages`, `StepQueueConfig`, and `StepConfirm` child components |
| `frontend/components/batch/BatchProgressTable.tsx` | Live polling dashboard: `useEffect` with `setInterval` at 3-second cadence, ShadCN Table displaying per-project Name, Stage badge, Progress bar, ETA, and Retry button |

---

## 2. Flow Diagram

    User clicks "Batch Pipeline" in sidebar → navigates to /batch
                        |
                        v
            [Step 1 — Source Selection]
            Option A: Upload JSON file (array of project objects)
            Option B: Toggle to "Select Existing"
                       → fetch GET /api/projects/?status=Draft
                       → render checkbox list of Draft projects
                        |
                        v
            Frontend: POST /api/batch/create/
            Body: { projects: [...] }  OR  { project_ids: [...] }
            Backend: create BatchJob + Project/Segment records if new
            Response: { batch_id: "uuid", project_ids: [1,2,3,...] }
                        |
                        v
            [Step 2 — Image Folder Assignment]
            User calls showDirectoryPicker() → selects local folder
              (or uses file input[multiple] fallback)
            Frontend collects sorted filename list per project
                        |
                        v
            Frontend: POST /api/batch/assign-images/
            Body: { batch_id, assignments: [{project_id, filenames[]}] }
            Backend: for each project, map filenames[i] → segments[i].image_file
            Response: { assigned_count, skipped_count }
                        |
                        v
            [Step 3 — Queue Configuration]
            User optionally overrides max_concurrent_renders (default: 2)
                        |
                        v
            [Step 4 — Confirm & Launch]
            Shows summary: N projects, M images assigned, concurrency cap
                        |
                        +──→ POST /api/batch/generate-audio/
                        |    Backend: enqueue generate_audio_task × N
                        |    BatchJob.status → "running"
                        |    Returns HTTP 202 immediately
                        |
                        +──→ POST /api/batch/render/
                             Backend: build Celery group of render tasks
                             wrapped in chord → batch_completion_callback
                             Returns HTTP 202 immediately
                        |
                        v
            [BatchProgressTable appears below wizard]
            Polls GET /api/batch/{batch_id}/progress/ every 3 seconds
            Per-project row: Name | Stage badge | % bar | ETA | Retry
                        |
                failure path: one project fails → row → Failed badge
                             other projects continue unaffected
                        |
                        v
            All resolved → BatchJob.status = "completed"
            Dashboard shows final banner: X succeeded, Y failed

---

## 3. Step-by-Step Instructions

### Step 1 — Add BatchJob Model and Extend GlobalSettings

File: `backend/api/models.py`

Add a new `BatchJob` model class below the existing `GlobalSettings` model. At the top of `models.py`, add `import uuid` if it is not already imported. The model fields are: `id` as `models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)`, `project_ids` as `models.JSONField(default=list)`, `status` as `models.CharField(max_length=20)` with a `TextChoices` inner class defining `QUEUED = 'queued'`, `RUNNING = 'running'`, `COMPLETED = 'completed'`, `FAILED = 'failed'` and a default of `QUEUED`, `created_at` as `models.DateTimeField(auto_now_add=True)`, `completed_at` as `models.DateTimeField(null=True, blank=True)`, and `error_log` as `models.TextField(blank=True, default='')`. Also add `max_concurrent_renders = models.IntegerField(default=2)` to `GlobalSettings` if absent. Run `python manage.py makemigrations && python manage.py migrate` and register `BatchJob` in `backend/api/admin.py`.

### Step 2 — Create the Batch API Views File

File: `backend/api/batch_views.py` (new file)

Create this file and define six DRF views. `BatchCreateView` (POST): parses the request body for either a `projects` array or a `project_ids` list; bulk-creates `Project` and `Segment` records from the JSON data when new content is provided; creates a `BatchJob` record with the collected project IDs; returns `{batch_id, project_ids}` with HTTP 201. `BatchAssignImagesView` (POST): receives `batch_id` and an `assignments` list where each entry has `project_id` and `filenames`; for each project iterates segments ordered by `sequence_index` and sets `segment.image_file` using the filename at the matching zero-based index; returns `{assigned_count, skipped_count}`. `BatchAudioView` (POST): calls `generate_audio_task.delay(pid)` for each project ID in the batch and sets `BatchJob.status` to `running`; returns HTTP 202. `BatchRenderView` (POST): builds a Celery `group` of `render_project_task` calls and wraps it in a `chord` with `batch_completion_callback`; returns HTTP 202. `BatchProgressView` (GET): queries per-project `status` and returns as JSON array. `BatchRetryView` (POST): re-enqueues the appropriate failed task for a single `project_id`.

### Step 3 — Register Batch Routes

Files: `backend/api/batch_urls.py` (new), `backend/api/urls.py`

Create `backend/api/batch_urls.py` and add `urlpatterns` with five path entries: `batch/create/` → `BatchCreateView.as_view()`, `batch/assign-images/` → `BatchAssignImagesView.as_view()`, `batch/generate-audio/` → `BatchAudioView.as_view()`, `batch/render/` → `BatchRenderView.as_view()`, `batch/<uuid:batch_id>/progress/` → `BatchProgressView.as_view()`, and `batch/<uuid:batch_id>/retry/<int:project_id>/` → `BatchRetryView.as_view()`. Open `backend/api/urls.py` and add `path('', include('api.batch_urls'))` to the existing `urlpatterns` list so all batch routes are mounted under the `/api/` prefix. After this change, verify the routes appear by running `python manage.py show_urls | grep batch` in the backend working directory and confirming six lines are printed.

### Step 4 — Build the Wizard Frontend and Zustand Store

Files: `frontend/store/batchStore.ts`, `frontend/app/batch/page.tsx`, `frontend/components/batch/BatchSetupWizard.tsx`

Create `frontend/store/batchStore.ts` as a Zustand store with state shape: `currentStep: number` (0–3), `batchId: string | null`, `projectIds: number[]`, `selectedDraftIds: number[]`, `imageAssignmentMap: Record<number, string[]>` (project ID to sorted filename list), `maxConcurrentRenders: number` (default 2), and action functions `setStep`, `setBatchId`, `setProjectIds`, `setImageAssignment`, and `reset`. Create `frontend/app/batch/page.tsx` rendering a horizontal step indicator with four labeled numbered steps above the wizard component. Create `frontend/components/batch/BatchSetupWizard.tsx` which reads `currentStep` from the store and conditionally mounts the correct step component: `StepSource` (JSON file upload dropzone and "Select Existing" toggle with Draft project checkbox list), `StepImages` (folder picker with fallback file input), `StepQueueConfig` (numeric input for concurrent renders override), and `StepConfirm` (summary table and the Launch button that fires both batch endpoints).

### Step 5 — Build the Live Polling Progress Dashboard

File: `frontend/components/batch/BatchProgressTable.tsx`

Create this component accepting `batchId: string` as its only required prop. In a `useEffect` that lists `batchId` as a dependency, immediately fetch `GET /api/batch/${batchId}/progress/` on mount and then schedule a `setInterval` calling the same fetch every 3000 milliseconds. Store the response array in local state typed as `ProjectStatus[]` where each object has `project_id`, `project_name`, `stage`, `percentage`, and `error`. Return a cleanup function from the `useEffect` that calls `clearInterval` on the stored interval handle so the polling stops when the component unmounts. Render the data using the ShadCN `Table`, `TableRow`, and `TableCell` components. Display stage as a `Badge` with variant `default` for queued, `secondary` for in-progress stages, `outline` for complete, and `destructive` for failed. Render `percentage` as a ShadCN `Progress` component. Show a "Retry" `Button` with `variant="outline"` and `size="sm"` only on rows whose `stage` equals `"failed"`; on click, POST to `batch/${batchId}/retry/${project_id}/` and reset that row's stage in local state to `"queued"`.

### Step 6 — Add Sidebar Navigation Link

Files: `frontend/components/Sidebar.tsx`, `frontend/app/layout.tsx` if sidebar is defined there

Open the Sidebar component and locate the array or JSX block defining navigation items — it should already contain an entry for "Projects" pointing to `/projects`. Add a new navigation item object with `label: "Batch Pipeline"`, `href: "/batch"`, and `icon: Layers` (imported from `lucide-react`). Position this item directly below the "Projects" entry since both relate to project management workflows. Ensure the item renders using the same `Link` component pattern as the existing navigation items so routing is handled client-side by Next.js without a full browser navigation. Confirm by starting the dev server, opening the browser, and verifying that the "Batch Pipeline" link appears in the sidebar, navigates to `/batch` when clicked, and does not produce any TypeScript compile errors.

---

## 4. Expected Outcome

1. Navigating to `/batch` from the sidebar renders the four-step wizard shell cleanly with a horizontal step indicator numbered 1 through 4, no console errors printed, and no broken layout at any standard viewport width from 1024px to 1920px.

2. Uploading a valid JSON file in Step 1 containing an array of five project objects — each with a `name` string and a `segments` array of three text strings — causes the frontend to POST to `/api/batch/create/` and receive a response containing a `batch_id` UUID and an array of five integer project IDs; confirming the creation in the Django admin shows five new `Project` records and one new `BatchJob` record whose `project_ids` JSONField contains those five IDs.

3. Using the Step 1 "Select Existing" toggle fetches all Draft-status projects and displays them as a labeled checkbox list; selecting three projects and clicking "Next" creates a `BatchJob` referencing those three existing project IDs without duplicating any project records or creating any new `Segment` rows.

4. Providing a test folder containing five sequentially named images in Step 2 triggers `POST /api/batch/assign-images/`; inspecting segment records in the Django admin afterwards shows that each project's first segment now has a non-null `image_file` value corresponding to the filename at index zero of the sorted filename list for that project.

5. Clicking the Launch button with both audio and render enabled fires two API requests — one to `/api/batch/generate-audio/` and one to `/api/batch/render/` — both returning HTTP 202 within one second; checking Celery worker logs shows N `generate_audio_task` and N `render_project_task` entries enqueued, where N is the number of projects in the batch.

6. Setting `GlobalSettings.max_concurrent_renders` to two in the Django admin and triggering "Render All" on a five-project batch results in at most two `render_project_task` workers executing simultaneously; confirmed by observing Celery worker log output showing a maximum of two tasks in the `STARTED` state at any point in time.

7. The polling dashboard updates the stage badge for at least one project within six seconds of that project's audio task completing in the Celery worker; no full-page reload is required and the badge color change is visible to the user in the browser without any manual action.

8. Simulating a failure by running a batch where one project has a segment with no text content results in only that row entering the `Failed` stage with a red badge and the error message displayed as a tooltip; all remaining projects continue to process and eventually reach `Complete`.

9. Clicking "Retry" on the single failed project row dispatches a new Celery task for only that project; the row's badge transitions back to an active-processing state within the next polling cycle and the project reaches `Complete` without affecting the other projects' state or the `BatchJob` record's completion timestamp.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] `BatchJob` model instantiates with correct defaults: `status` is `'queued'`, `project_ids` is an empty list `[]`, `error_log` is an empty string `''`, and `completed_at` is `None`
- [ ] `BatchCreateView` returns HTTP 201 and a UUID-formatted `batch_id` string when given a POST body containing a valid `projects` array with two project objects each having a `name` and a `segments` list
- [ ] `BatchAssignImagesView` sets the `image_file` field on the first segment of a test project to the expected filename string when given a `filenames` list containing one entry at index zero
- [ ] `BatchRenderView` calls `render_project_task.delay()` exactly three times when given a `BatchJob` whose `project_ids` list contains three IDs, as verified by mocking the task and asserting call count
- [ ] `BatchProgressView` returns a JSON array with exactly N objects, where N matches the length of `BatchJob.project_ids`, each object containing at minimum the keys `project_id`, `stage`, and `percentage`
- [ ] `batch_completion_callback` Celery task, when called with a valid `batch_id`, sets `BatchJob.status` to `'completed'` and sets `BatchJob.completed_at` to a non-null datetime value in the database

### 5.2 Integration / Manual Tests

- [ ] Upload a JSON file containing five project objects in the browser Step 1 interface; confirm five `Project` records and one `BatchJob` record appear in the Django admin with the five project IDs stored in `BatchJob.project_ids`
- [ ] Use the folder picker to select a test folder with five sequentially named images; confirm the assignment POST fires, the admin shows non-null `image_file` values on five segment rows, and the Step 3 UI advances without error
- [ ] Click "Launch" with audio enabled on a three-project batch; open the Celery worker terminal output and verify three separate `generate_audio_task` entries appear as accepted within five seconds of the button click
- [ ] Set `GlobalSettings.max_concurrent_renders` to one in Django admin; trigger "Render All" on a three-project batch; observe Celery worker logs and confirm tasks execute one at a time — the second task does not appear as STARTED until the first task log shows SUCCESS
- [ ] Open the progress dashboard and trigger a three-project batch; manually count two complete polling cycles (wait six seconds); confirm that any project whose Celery task completed during that window now shows an updated stage badge without any user interaction
- [ ] Provide one project with an empty `text_content` on all segments; trigger audio generation; confirm that project enters `Failed` stage in the dashboard while the other two projects continue to `Audio Generated` then `Rendering` then `Complete`
- [ ] Click "Retry" on the failed project after fixing its segment text in the admin; confirm a new `generate_audio_task` is dispatched per Celery worker logs and the row's badge transitions from `Failed` to an active-processing badge within the next polling cycle

### 5.3 Regression Tests

- [ ] Existing single-project creation flow via the main projects page still creates one `Project` and the expected number of `Segment` records without triggering any `BatchJob` creation side effects or producing HTTP errors
- [ ] Calling `generate_audio_task.delay(project_id)` directly from the existing per-project detail page — without supplying the optional `batch_id` parameter — still completes successfully and produces a valid audio file, confirming the new optional parameter is backward-compatible
- [ ] Saving a `GlobalSettings` record in the Django admin after the `max_concurrent_renders` field is added does not raise any migration-related `OperationalError` or `FieldError` exceptions, and the existing GlobalSettings serializer returns the new field in its JSON output alongside all previously existing fields

---

## 6. Notes for AI Agent

- The `BatchJob.project_ids` field must be stored as a plain Python list of integers in a `JSONField`, not as a `ManyToManyField` relation. Batch membership is determined at creation time and is immutable — no projects should be added to or removed from a `BatchJob` after it is created — so using a JSONField rather than a join table eliminates unnecessary ORM complexity and makes the batch record fully self-contained for archival, export, and debugging purposes without additional joins.

- The File System Access API (`showDirectoryPicker`) is only available in Chromium-based browsers (Chrome and Edge) as of early 2026; Firefox and Safari do not support it. Always render a standard `input[type="file"][multiple][webkitdirectory]` element as a visible fallback, even if it is visually secondary. Use a try-catch block around the `showDirectoryPicker()` call so that a `NotAllowedError` thrown when the user dismisses the picker dialog does not crash the component and surfaces as a friendly "Please select a folder using the file picker below" message instead.

- When implementing the concurrency-limited render queue in `BatchRenderView`, use Celery's `group()` and `chord()` primitives rather than any Python-level loop with delays, threading locks, or semaphores. A Python-level loop with `time.sleep()` would block the Django request-response cycle and cause a gateway timeout; Celery primitives handle scheduling natively at the queue level. Configure a dedicated `batch_render` Celery queue with its own worker process started with the `--concurrency=2` flag matching the `max_concurrent_renders` default, so the cap is enforced at the infrastructure level and not only in application code.

- All six new batch API endpoints must include `permission_classes = [IsAuthenticated]` in their view class definition. If the current development environment has authentication disabled globally via a `DEFAULT_PERMISSION_CLASSES` setting override in `settings.py`, add the guard code with a `# NOTE: Authentication enforced — ensure this is enabled in production` comment but do not remove it, so enabling authentication in a future release requires no code changes.

- The 3-second polling interval is appropriate for batches up to approximately twenty projects. For larger batches, the progress response payload grows and the `SELECT` query over all project status records becomes more expensive. Add a check inside the `useEffect` that reads the total `project_count` from the first successful progress response: if the count exceeds twenty, automatically double the interval to six seconds to reduce database load during large overnight runs without the user needing to configure anything.

- When adding the optional `batch_id` parameter to the existing `generate_audio_task` and `render_project_task` Celery tasks, default it to `None` and add an `if batch_id is not None:` guard around every code path that touches the `BatchJob` model inside the task's except block. This preserves complete backward compatibility with all existing callers of those tasks throughout the codebase that invoke them without the `batch_id` argument.
