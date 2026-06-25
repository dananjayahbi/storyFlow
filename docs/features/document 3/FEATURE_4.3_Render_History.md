# Feature 4.3 — Render History

| Field | Value |
|---|---|
| Feature ID | 4.3 |
| Title | Render History |
| Status | 🟡 Planned |
| Priority | High |
| Complexity | Medium |
| Estimated Effort | 2–3 days |
| Dependencies | None — foundational feature; required by Feature 4.2 (Video Comparison View) |
| Output Files (NEW) | `backend/api/migrations/000X_add_renderhistory_model.py`, `backend/media/projects/{id}/history/render_{N}.mp4` |
| Files Modified | `backend/api/models.py`, `backend/api/views.py`, `backend/api/urls.py`, `backend/api/serializers.py`, `backend/core_engine/video_renderer.py`, `frontend/app/projects/[id]/page.tsx`, `frontend/store/projectStore.ts`, `frontend/types/project.ts` |

---

## 1. Document Overview

### 1.1 Problem Statement

Every time a creator triggers a new render in StoryFlow, the resulting `output.mp4` is written directly to `backend/media/projects/{id}/output.mp4`, overwriting the previous file. The project's `render_settings` JSON field is also updated in place, meaning the exact configuration that produced any prior render is permanently lost. If a creator renders a project on Monday with a calm voice and on Tuesday with a faster voice, and then decides on Wednesday that Monday's version was better, there is no mechanism to recover it — the file is gone and the settings that generated it are gone with it. This turns every render into a one-way, irreversible operation, which is incompatible with iterative creative workflows.

### 1.2 Proposed Solution

Introduce a `RenderHistory` model that captures each render as a versioned, immutable record, and update the render pipeline to write versioned output files instead of overwriting. Enforce a maximum of five stored versions per project to contain disk usage.

- Add a new `RenderHistory` Django model with fields for the parent project, a per-project auto-incrementing render number, the output video file path, a full snapshot of the render settings at the time of the render, the creation timestamp, the video duration in seconds, and the output file size in bytes.
- Modify `video_renderer.py` so that instead of writing to `output.mp4`, it writes to `media/projects/{id}/history/render_{N}.mp4` where N is the next render number derived from the existing history count.
- Immediately after the file is written, create a `RenderHistory` record with the file path, the full `render_settings_snapshot` (combining `Project.render_settings` and any active global settings at render time), the duration from the ffprobe call already available in the pipeline, and the file size from `os.path.getsize`.
- After each new record is saved, check the total count of `RenderHistory` records for the project; if it exceeds five, delete the oldest record (by `created_at`) and remove its associated file from disk using `os.remove`.
- Also update `Project.output_file` to point to the latest render's file path for backward compatibility with any code that reads `project.output_file` directly.
- Add a `GET /api/projects/{id}/render-history/` API endpoint that returns all history records for the project sorted newest-first.
- On the project detail page, add a collapsible "Render History" panel listing each version with its render number, formatted timestamp, file size, duration, a Play button (opens the video in a lightweight modal), a "Restore Settings" button (writes the snapshot back to `Project.render_settings` via a PATCH request), and a Delete button (removes the record and file via a `DELETE /api/projects/{id}/render-history/{historyId}/` endpoint).

### 1.3 Scope

| Category | Item |
|---|---|
| In Scope | `RenderHistory` model with per-project versioned file storage |
| In Scope | Automatic cap at 5 versions — oldest deleted on overflow |
| In Scope | Settings snapshot captured at render time and stored in JSON |
| In Scope | "Restore Settings" action that writes the snapshot back to `Project.render_settings` |
| Out of Scope | Unlimited version storage or configurable retention limit per project |
| Out of Scope | Diffing render settings between arbitrary history versions (covered by Feature 4.2) |
| Out of Scope | Cloud or off-device backup of render history files |
| Out of Scope | Branching or tagging render versions with user-defined names |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| `backend/api/models.py` | Defines all persistent Django models | Has `Project` model; no `RenderHistory` model exists |
| `backend/core_engine/video_renderer.py` | Full render pipeline — writes output file, sets `project.output_file` | Writes to fixed `output.mp4` path; no history versioning |
| `backend/api/views.py` | Django REST views for project CRUD and render trigger | Has project views; no render history list or delete views |
| `backend/api/serializers.py` | Serializes model data to JSON for API responses | Has `ProjectSerializer`; no `RenderHistorySerializer` |
| `frontend/app/projects/[id]/page.tsx` | Project detail page — segments, settings, render button | Has render controls; no Render History panel |

---

## 2. Flow Diagram

```
Render triggered (video_renderer.py)
         |
         v
  [Get existing RenderHistory count for project]
         |
         v
  [next_render_N = count + 1]
         |
         v
  [Write output to:
   media/projects/{id}/history/render_{N}.mp4]
         |
         v
  [ffprobe: get duration_seconds]
         |
         v
  [os.path.getsize -> file_size_bytes]
         |
         v
  [Capture render_settings_snapshot
   from Project.render_settings +
   GlobalSettings at this moment]
         |
         v
  [Create RenderHistory record]
         |
         v
  [Update Project.output_file -> render_{N}.mp4]
         |
         v
  [Count RenderHistory records for project]
         |
    -----+------
    |           |
  [<= 5]     [> 5]
    |           |
    v           v
  [Done]   [Query oldest record]
                |
                v
           [os.remove file]
                |
                v
           [Delete record]
                |
                v
             [Done]
```

---

## 3. Step-by-Step Instructions

### Step 1 — Create the `RenderHistory` model and migration
- File: `backend/api/models.py`
- Add a `RenderHistory` class with `project` as a `ForeignKey` to `Project` with `on_delete=CASCADE` and `related_name='render_history'`; `render_number` as a `PositiveIntegerField`; `output_file` as a `FileField` with `upload_to='projects/history/'`; `render_settings_snapshot` as a `JSONField`; `created_at` as a `DateTimeField` with `auto_now_add=True`; `duration_seconds` as a `FloatField` defaulting to 0.0; and `file_size_bytes` as a `BigIntegerField` defaulting to 0.
- Add a `Meta` class with `ordering = ['-created_at']` so the default queryset is newest-first.
- Run `makemigrations api` and `migrate` to apply.

### Step 2 — Update the render pipeline to write versioned output files
- File: `backend/core_engine/video_renderer.py`
- Before writing the output file, query `RenderHistory.objects.filter(project=project).count()` to determine the next render number.
- Construct the versioned output path as `media/projects/{id}/history/render_{N}.mp4` and create the `history/` subdirectory with `os.makedirs(..., exist_ok=True)` if it does not exist.
- After writing and confirming the output file, build the `render_settings_snapshot` dict by merging `project.render_settings` with any global settings values active at that moment.
- Create the `RenderHistory` record, then update `project.output_file` to the new versioned path and save.
- After saving, check count; if greater than five, retrieve the oldest `RenderHistory` by `created_at`, call `os.remove` on its file if it exists on disk, and then call `.delete()` on the model record.

### Step 3 — Add the render history API endpoints
- File: `backend/api/views.py`
- Add `RenderHistoryListView` as a `ListAPIView` that filters `RenderHistory` by `project_id` from the URL kwargs and serializes using `RenderHistorySerializer`.
- Add `RenderHistoryDeleteView` as a `DestroyAPIView` that retrieves the `RenderHistory` record by `pk`, calls `os.remove` on the file path if the file exists, and then deletes the record.
- Add `RestoreSettingsView` as an action (or `UpdateAPIView`) that takes a `POST /api/projects/{id}/render-history/{historyId}/restore/` request, reads `render_settings_snapshot` from the history record, writes it back to `project.render_settings`, saves the project, and returns the updated project.
- File: `backend/api/urls.py` — register all three new URL patterns.

### Step 4 — Create `RenderHistorySerializer`
- File: `backend/api/serializers.py`
- Add `RenderHistorySerializer` with fields: `id`, `renderNumber` (mapped from `render_number`), `createdAt` (mapped from `created_at`), `fileSizeBytes`, `durationSeconds`, `outputFileUrl` (a `SerializerMethodField` returning the absolute URL), and `renderSettingsSnapshot`.
- Use `camelCase` field names via `source` arguments so the frontend receives consistent naming without a mapping layer.

### Step 5 — Add the Render History panel to the project detail page
- File: `frontend/app/projects/[id]/page.tsx`
- Add a collapsible section below the render controls using a ShadCN `Collapsible` component labeled "Render History (N)".
- Inside, render a list of `RenderHistoryItem` entries; for each entry show the render number, formatted `createdAt`, formatted file size (in MB), duration in seconds, a "Play" icon button that opens the video URL in a lightweight `<dialog>` or ShadCN `Dialog`, a "Restore Settings" text button that calls `POST .../restore/` and then refreshes the project data in the Zustand store, and a "Delete" icon button with a confirmation tooltip that calls the delete endpoint.
- Fetch render history in the existing page-level `useEffect` by calling `GET /api/projects/{id}/render-history/` and dispatching to `setRenderHistory` in the Zustand store.

---

## 4. Expected Outcome

1. Every completed render produces a new versioned file at `media/projects/{id}/history/render_{N}.mp4` rather than overwriting any existing file.
2. A `RenderHistory` record is created for every render, capturing the exact settings and timestamps needed to reproduce or reference that render in the future.
3. The project never accumulates more than five history entries — the oldest file and record are removed automatically when the sixth render completes.
4. The `GET /api/projects/{id}/render-history/` endpoint returns a properly ordered list of history items with all fields needed by the frontend and by Feature 4.2.
5. Clicking "Restore Settings" on any history entry writes that entry's settings snapshot back to the project and immediately reflects the change in the render settings panel without requiring a page reload.
6. The "Delete" action on a history entry removes both the database record and the physical MP4 file from disk, freeing storage cleanly.
7. Feature 4.2 (Video Comparison View) can be implemented directly on top of this feature's data model and API endpoint with no further backend changes required.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] Test that `video_renderer.py` writes the output file to the versioned `history/render_{N}.mp4` path and not to the old `output.mp4` path
- [ ] Test that a `RenderHistory` record is created with the correct `render_number`, `file_size_bytes`, and `render_settings_snapshot` after a render
- [ ] Test that when a sixth render completes, the `RenderHistory` record count for the project remains at 5 and the oldest record is deleted
- [ ] Test that `RenderHistorySerializer` returns `outputFileUrl` as a fully qualified absolute URL
- [ ] Test that the restore endpoint writes the correct keys from `renderSettingsSnapshot` into `Project.render_settings` and returns a 200 response

### 5.2 Integration / Manual Tests

- [ ] Trigger six consecutive renders on the same project and confirm only five entries appear in the render history panel and only five MP4 files exist in `media/projects/{id}/history/`
- [ ] Open the render history panel and click "Play" on an older entry — confirm the correct versioned video plays in the modal
- [ ] Click "Restore Settings" on the second-oldest entry and confirm the render settings panel reflects the restored values without a page reload
- [ ] Click "Delete" on an entry and confirm the entry disappears from the list and the corresponding MP4 file is gone from disk
- [ ] Verify that `Project.output_file` always points to the most recently rendered versioned file after each render
- [ ] Confirm the render history API endpoint returns items sorted newest-first

### 5.3 Regression Tests

- [ ] The render trigger endpoint still returns a success response and the project model is still updated after the render pipeline changes
- [ ] Existing projects in the database with `output_file` set but no `RenderHistory` records continue to work normally — their detail pages load without errors and render can be triggered
- [ ] The project detail page renders without errors when the render history list is empty (zero entries)

---

## 6. Notes for AI Agent

- The `render_number` field cannot use Django's `auto_increment` for the per-project sequence — query `RenderHistory.objects.filter(project=project).count() + 1` inside the render function to calculate the next number; wrap it in a `select_for_update()` transaction if concurrent renders per project are possible.
- When deleting the oldest history entry, always check `os.path.exists(record.output_file.path)` before calling `os.remove` to avoid a `FileNotFoundError` if the file was already removed manually from disk.
- The `render_settings_snapshot` should be a deep copy of the settings dict at the time of capture — use `copy.deepcopy` rather than a reference to avoid the snapshot mutating if `project.render_settings` is updated later in the same request cycle.
- The `history/` subdirectory under each project's media folder is created lazily inside the render function — it is not pre-created by any migration or fixture; use `os.makedirs(..., exist_ok=True)`.
- This feature is a prerequisite for Feature 4.2: do not attempt to integrate the comparison view until the `GET /api/projects/{id}/render-history/` endpoint is returning real data with valid `outputFileUrl` values.
