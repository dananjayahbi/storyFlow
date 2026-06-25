# Feature 4.5 — Media Usage Tracking & Storage Dashboard

| Field | Value |
|---|---|
| Feature ID | 4.5 |
| Title | Media Usage Tracking & Storage Dashboard |
| Status | 🟡 Planned |
| Priority | Medium |
| Complexity | Low |
| Estimated Effort | 2 days |
| Dependencies | Feature 2.1 (Project model with output_file field), Feature 3.1 (Video render pipeline) |
| Output Files (NEW) | `backend/api/utils.py`, `frontend/components/dashboard/MediaUsageDashboard.tsx`, `frontend/components/dashboard/StorageBar.tsx`, `frontend/components/dashboard/ProjectStorageTable.tsx` |
| Files Modified | `backend/api/views.py`, `backend/api/urls.py`, `frontend/app/settings/page.tsx`, `frontend/app/dashboard/page.tsx`, `frontend/components/layout/AppHeader.tsx` |

---

## 1. Document Overview

### 1.1 Problem Statement

A creator who has been running StoryFlow for three months and has produced over 500 projects has absolutely no visibility into how much disk space the system is consuming. A single 4K render file can easily reach 500 MB, and old renders from iterative re-renders of the same project accumulate silently in the `backend/media/` directory. Without any storage tracking, the application will eventually fail silently or crash due to a full disk — and the creator will have no warning and no actionable tools to reclaim space. There is currently no endpoint, widget, or background task that measures or reports on disk usage at any level of granularity.

### 1.2 Proposed Solution

Implement a lightweight server-side storage scanner that aggregates media file sizes by category and exposes that data through a REST endpoint, then surface the results in a frontend dashboard widget with a visual breakdown chart and per-project storage table.

- Add a utility function `get_media_usage_stats()` in a new `backend/api/utils.py` file that walks `MEDIA_ROOT` using `os.walk()` and classifies files by extension into four buckets: Renders (mp4, webm), Audio (wav, mp3), Images (jpg, png, webp), and Other.
- Create a new API endpoint `GET /api/media/usage/` that calls `get_media_usage_stats()` and returns a structured JSON response containing total storage in gigabytes, per-category breakdowns, and a ranked list of projects by their individual storage consumption.
- Build a `MediaUsageDashboard` React component that renders a horizontal stacked bar chart visualizing the four storage categories with color-coded segments, using either the `recharts` library or a pure CSS flexbox bar approach.
- Add a sortable "Projects by Storage" table below the chart that shows each project's name, total size in megabytes, and a "Clean Up Renders" action button for that specific project.
- Implement a cleanup endpoint `DELETE /api/projects/{id}/renders/` with an optional `?keep_latest=1` query parameter that removes all generated render files for that project except the most recently created one, then updates the `Project.output_file` field accordingly.
- Display a persistent warning badge in the application's top navigation bar whenever total storage exceeds a configurable threshold (default 10 GB): showing a human-readable label such as "Storage: 12.3 GB — Clean up suggested."

### 1.3 Scope

| Category | In Scope |
|---|---|
| Storage scanning | Scan all files under `MEDIA_ROOT` using `os.walk()` on-demand per API request |
| Category breakdown | Four categories: Renders, Audio, Images, Other by file extension |
| Per-project breakdown | Scan `MEDIA_ROOT/projects/{id}/` subdirectory for each known project |
| Cleanup action | Delete all but latest render file for a single project via API |

| Category | Out of Scope |
|---|---|
| Scheduled scanning | No Celery or cron job for background scanning in this phase |
| Auto-cleanup | No automated deletion without explicit user confirmation |
| Cross-device storage | No support for network drives or cloud storage paths |
| Archived projects | No distinction between active and archived project storage |

### 1.4 Key Files Reference

| File | Role |
|---|---|
| `backend/api/utils.py` | New file containing `get_media_usage_stats()` scanner function |
| `backend/api/views.py` | Add `MediaUsageView` and `ProjectRenderCleanupView` endpoint classes |
| `backend/storyflow_backend/settings.py` | References `MEDIA_ROOT` — used by the scanner to locate files |
| `frontend/app/settings/page.tsx` | Embed `MediaUsageDashboard` component in the Settings page |
| `frontend/components/layout/AppHeader.tsx` | Add storage warning badge logic using the usage API data |

---

## 2. Flow Diagram

```
User opens Settings page
         |
         v
  MediaUsageDashboard mounts
         |
         v
  GET /api/media/usage/
         |
         v
  Backend: get_media_usage_stats()
  os.walk(MEDIA_ROOT)
         |
     +---+---+---+---+
     |   |   |   |   |
  .mp4 .wav .jpg .other
  Renders Audio Imgs Other
     |   |   |   |   |
     +---+---+---+---+
         |
         v
  Aggregate totals + per-project sizes
  Return JSON: {total_gb, renders_gb,
   audio_gb, images_gb, other_gb,
   per_project: [{id, name, size_mb}]}
         |
         v
  StorageBar renders color-coded bar
  ProjectStorageTable renders sorted rows
         |
  User clicks "Clean Up Renders" on row
         |
         v
  DELETE /api/projects/{id}/renders/?keep_latest=1
         |
         v
  Backend deletes old render files
  Updates Project.output_file
         |
         v
  Dashboard refreshes — sizes decrease
```

---

## 3. Step-by-Step Instructions

### Step 1 — Create `get_media_usage_stats()` in `backend/api/utils.py`

Create the new file `backend/api/utils.py`. Implement the function `get_media_usage_stats()` that takes no arguments. Import `os` and `settings` from `django.conf`. Initialize five integer counters to zero: `renders_bytes`, `audio_bytes`, `images_bytes`, `other_bytes`, and `total_bytes`. Use `os.walk(settings.MEDIA_ROOT)` to iterate over all directories and files recursively. For each file, call `os.path.getsize()` and classify it by lowercase extension: `.mp4` and `.webm` go to `renders_bytes`, `.wav` and `.mp3` go to `audio_bytes`, `.jpg`, `.jpeg`, `.png`, and `.webp` go to `images_bytes`, and all other extensions go to `other_bytes`. Add every file's size to `total_bytes`. To compute per-project breakdown, iterate over the numeric subdirectory names under `MEDIA_ROOT/projects/` and sum each subdirectory's total file sizes independently. Return a dictionary with all totals converted to gigabytes (divide by 1024³) and the per-project list sorted by descending size.

### Step 2 — Add API endpoints in `backend/api/views.py` and `backend/api/urls.py`

In `views.py`, add two new view classes. The first, `MediaUsageView`, should inherit from `APIView`; its `get` method simply calls `get_media_usage_stats()` from `utils.py` and returns it wrapped in a `Response`. Add basic rate awareness: if the `MEDIA_ROOT` scan takes longer than expected, the view can cache the result for 60 seconds using Django's cache framework (`cache.get` / `cache.set`). The second view, `ProjectRenderCleanupView`, should inherit from `APIView`; its `delete` method reads the `project_id` from the URL, reads the optional `keep_latest` query parameter (default 1), lists all render files in that project's media directory sorted by modification time, and unlinks all but the most recent `keep_latest` files using `os.remove()`. After deletion, clear the usage cache. In `urls.py`, add `path("media/usage/", MediaUsageView.as_view())` and `path("projects/<int:pk>/renders/", ProjectRenderCleanupView.as_view())`.

### Step 3 — Build `StorageBar` and `MediaUsageDashboard` components

Create `frontend/components/dashboard/StorageBar.tsx`. This component accepts a props object with four numeric values: `rendersPct`, `audioPct`, `imagesPct`, `otherPct` (percentages that sum to 100). It renders a `div` with `flex` layout where each child `div` has a width set to the corresponding percentage and a distinct background color class. Add a legend row below the bar showing each category name, its color swatch, and its size in GB. Create `frontend/components/dashboard/MediaUsageDashboard.tsx` that calls `GET /api/media/usage/` on mount, passes the result to `StorageBar`, and renders the `ProjectStorageTable` below it. Show a loading skeleton while the request is in flight and an error message if it fails.

### Step 4 — Build `ProjectStorageTable` (`frontend/components/dashboard/ProjectStorageTable.tsx`)

The table receives the `per_project` array from the API response. Render it as a standard HTML table with columns: Project Name, Storage (MB), and Actions. The Actions column contains a "Clean Up Renders" button. Clicking the button sends `DELETE /api/projects/{id}/renders/?keep_latest=1`, then triggers a refresh of the parent `MediaUsageDashboard` component by calling a passed-in `onRefresh` callback prop. By default, sort rows by size descending. Add a sort toggle on the "Storage (MB)" column header to allow ascending sort as well. Truncate long project names with an ellipsis at 30 characters using a CSS utility class.

### Step 5 — Add the header warning badge to `AppHeader.tsx` and embed dashboard in settings

In `frontend/components/layout/AppHeader.tsx`, add a `useEffect` that fetches `/api/media/usage/` once on mount and stores the `total_gb` value in a local state variable. If `total_gb` exceeds 10, render a small badge element next to the app title containing the text "Storage: {total_gb} GB — Clean up" in an amber or red color scheme using Tailwind classes. In `frontend/app/settings/page.tsx`, import `MediaUsageDashboard` and add it as a new card section at the bottom of the settings page, placed after the existing global settings fields. Give the section a heading "Storage & Media Usage" to distinguish it from the settings form above.

---

## 4. Expected Outcome

- `GET /api/media/usage/` responds with a valid JSON payload containing `total_gb`, the four category size fields, and a non-empty `per_project` list when media files exist.
- The `MediaUsageDashboard` component renders on the settings page and displays a horizontally filled colored bar charting the storage breakdown.
- The "Projects by Storage" table shows rows sorted by size descending, with human-readable MB values.
- Clicking "Clean Up Renders" for a project triggers the backend deletion and the table refreshes with the reduced storage figure.
- The header badge appears automatically when total storage exceeds 10 GB and disappears (or turns green) when it drops below the threshold after cleanup.
- The scanner covers all file types present under `MEDIA_ROOT` — no files are silently missed because of an unrecognized extension (they fall into "Other").
- The per-project breakdown correctly isolates each project's media folder and does not cross-count shared files from the library or outros directories.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] `get_media_usage_stats()` correctly classifies a test set of mock files by extension into the four expected categories.
- [ ] `get_media_usage_stats()` returns `total_gb` equal to the sum of all category values.
- [ ] `ProjectRenderCleanupView.delete()` removes the correct number of files when `keep_latest=1` is passed, leaving exactly one file.
- [ ] `ProjectRenderCleanupView.delete()` does not error when the project has zero render files.
- [ ] `MediaUsageView.get()` returns HTTP 200 and a JSON body with all required keys.

### 5.2 Integration / Manual Tests

- [ ] Add several video files and image files to `backend/media/` manually, then call `GET /api/media/usage/` — verify the returned sizes match the actual disk usage reported by `du -sh`.
- [ ] Open the Settings page in the browser — verify the stacked bar chart renders and the four color segments sum to the full bar width.
- [ ] Click "Clean Up Renders" for a project that has multiple render files — verify the table row size drops and only one render file remains on disk.
- [ ] Verify the header badge appears when total usage is mocked above 10 GB and disappears when usage is below the threshold.
- [ ] Verify the `ProjectStorageTable` sorts correctly when the column header is clicked.
- [ ] Call `GET /api/media/usage/` twice within the 60-second cache window — verify the second response is returned faster and the filesystem is not re-walked.

### 5.3 Regression Tests

- [ ] All existing project CRUD endpoints continue to return correct responses after adding the two new URL routes.
- [ ] The existing settings page form fields (voice, subtitle, render settings) still save correctly after embedding `MediaUsageDashboard` as an additional section.
- [ ] The `Project.output_file` field is correctly updated (or cleared if the only file is deleted) after a cleanup action.

---

## 6. Notes for AI Agent

- `os.walk()` is synchronous and will block the Django request thread for large media directories; the 60-second cache on `MediaUsageView` is non-negotiable — implement it from the start, not as a follow-up optimization.
- The per-project scan must be scoped strictly to `MEDIA_ROOT/projects/{project_id}/` subdirectories; scanning the full `MEDIA_ROOT` and then attributing files is error-prone and may misattribute library or outro assets to projects.
- When implementing the `ProjectRenderCleanupView`, ensure the file list is sorted by `os.path.getmtime()` in ascending order before slicing — the files to delete are the oldest ones, and the file to keep is the one with the highest modification time.
- The `total_gb` threshold of 10 GB for the header warning badge should be a named constant defined in `frontend/constants/storage.ts` rather than a magic number embedded in the component, so it can be easily adjusted.
- If `recharts` is not already installed in the frontend package, use a pure CSS flex bar implementation for `StorageBar` to avoid adding a dependency for a single simple chart.
