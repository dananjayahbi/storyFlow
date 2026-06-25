# Feature 2.2 — Project Duplication

| Field | Value |
|---|---|
| **Feature ID** | 2.2 |
| **Title** | Project Duplication (Clone / Fork) |
| **Status** | 🟡 Planned |
| **Priority** | High |
| **Complexity** | Low |
| **Estimated Effort** | 2–3 days |
| **Dependencies** | `Project` model stable, `Segment` model stable, media file storage paths consistent under `media/projects/` |
| **Output Files (NEW)** | None — all logic lives inside existing files |
| **Files Modified** | `backend/api/views.py`, `backend/api/urls.py`, `frontend/components/ProjectCard.tsx`, `frontend/app/projects/page.tsx` |

---

## 1. Document Overview

### 1.1 Problem Statement

StoryFlow currently offers no mechanism to clone an existing project. When a creator wants to produce a variation of a finished or in-progress project — for example, a Spanish-language version of an English narration, an A/B test with different background music, or the next episode of a series that shares the same structure — they must create a new blank project and manually reconstruct every setting and re-enter every segment from scratch. This process is error-prone and time-consuming, particularly for projects with ten or more segments, and it effectively discourages episode-based content workflows. The absence of a "fork" or "duplicate" action is one of the most commonly needed affordances in any project-management tool, and its absence in StoryFlow creates unnecessary friction that compounds as a creator's library grows.

### 1.2 Proposed Solution

Add a single backend endpoint and a minimal frontend interaction to support deep cloning of a project. A deep clone copies the project's settings fields, all of its segment records, and the physical media files (audio and images) on disk to new paths associated with the new project. The result is a fully independent copy that shares no file references with the original — edits to the duplicate cannot corrupt the source project.

Key components of the solution:

- Add a `POST /api/projects/{id}/duplicate/` endpoint in `views.py` implemented as a Django REST Framework function-based view or a simple `APIView` subclass.
- The view loads the source project, instantiates a new `Project` with all the same field values, renames it to `{original_name} (copy)`, saves it, then iterates through all associated `Segment` records.
- For each segment, a new `Segment` record is created with identical `text_content`, `sequence_index`, `duration`, and `is_locked` values.
- If a segment has an `audio_file` or `image_file`, use Python's `shutil.copy2()` to copy the physical file from its current path to a new path under the new project's media directory, then assign the new path to the cloned segment.
- The endpoint returns the full serialized representation of the new project (including its ID) in a single response, allowing the frontend to navigate immediately.
- On the frontend, add a three-dot dropdown menu to each `ProjectCard.tsx` using ShadCN's `DropdownMenu` component. The menu contains at minimum an "Open" item and a new "Duplicate" item.
- Clicking "Duplicate" calls the API, displays a loading state on the card, then shows a success toast with a "Go to Project" link that navigates to the new project's editor.
- The project list page (`app/projects/page.tsx`) refreshes its project list after a successful duplication by re-fetching or by appending the new project object to local state.

### 1.3 Scope

| Dimension | In Scope |
|---|---|
| Deep copy of all `Project` scalar and JSON fields | ✅ All configurable fields duplicated |
| Deep copy of all associated `Segment` records | ✅ New segment rows with same content |
| Physical copy of audio and image files on disk | ✅ `shutil.copy2()` to new project directory |
| Frontend three-dot menu on `ProjectCard` with "Duplicate" item | ✅ ShadCN DropdownMenu |
| Toast notification with link to new project | ✅ Success and error states handled |

| Dimension | Out of Scope |
|---|---|
| Copying logo files or music files referenced in project settings | ❌ Shared media assets are referenced by path only |
| Undo / rollback of a duplication action | ❌ Not planned; user can delete the copy manually |
| Bulk duplication of multiple selected projects at once | ❌ One-at-a-time only in this phase |
| Async / background processing of the duplication | ❌ Synchronous endpoint is sufficient for typical project sizes |
| Rename prompt before duplication completes | ❌ The "(copy)" suffix is applied automatically; user can rename afterward |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| `backend/api/views.py` | All API view logic | Contains `ProjectListCreateView`, `ProjectDetailView`; no duplicate view yet |
| `backend/api/urls.py` | URL routing | Routes for `projects/` and `projects/<int:pk>/`; no duplicate route |
| `frontend/components/ProjectCard.tsx` | Renders a single project card in the list | Shows name, status, last-updated, render button; no action menu |
| `frontend/app/projects/page.tsx` | Projects list page; fetches all projects | Fetches project list and renders `ProjectCard` components in a grid |
| `backend/api/models.py` | Project and Segment ORM models | `Project` (settings fields), `Segment` (content + media file paths); read-only in this feature |
| `backend/api/serializers.py` | DRF serializers | `ProjectSerializer` with full field set; `SegmentSerializer`; no changes needed |

---

## 2. Flow Diagram

```
User clicks ⋯ on ProjectCard
        │
        ▼
DropdownMenu opens
  ┌─────┴──────────────┐
  │   Open Project     │
  │   Duplicate        │  ◄── user clicks this
  │   Delete           │
  └────────────────────┘
        │
        ▼
Frontend calls POST /api/projects/{id}/duplicate/
        │
        ▼
DuplicateProjectView (backend)
 ┌─────────────────────────────────────────────┐
 │  1. Load source Project by id               │
 │  2. Clone Project fields → new Project row  │
 │     name = "{original} (copy)"              │
 │  3. For each Segment on source project:     │
 │     a. Clone segment row                    │
 │     b. If audio_file exists → shutil.copy2  │
 │     c. If image_file exists → shutil.copy2  │
 │     d. Save new segment with new file paths │
 │  4. Serialize new Project + segments        │
 │  5. Return HTTP 201 + serialized data       │
 └─────────────────────────────────────────────┘
        │
        ▼
Frontend receives new project object
        │
  ┌─────┴──────────────────────────────┐
  │  Append new project to list state  │
  │  Show success toast with link      │
  └────────────────────────────────────┘
        │
        ▼
User clicks "Go to Project" in toast
        │
        ▼
Navigate to /projects/{new_id}/editor
```

---

## 3. Step-by-Step Instructions

### Step 3.1 — Implement the DuplicateProjectView in views.py

File: `backend/api/views.py`

Locate the section where `ProjectDetailView` is defined. Directly below it, add a new view class or function called `DuplicateProjectView`. This view handles only the POST HTTP method. It begins by fetching the source project using `get_object_or_404(Project, pk=pk)` where `pk` is extracted from the URL kwargs. It then sets `source_project.pk = None` to prepare a clone — Django will insert a new row when the instance with `pk=None` is saved. Before saving, set the `name` field to `f"{source_project.name} (copy)"` and reset `created_at` by relying on `auto_now_add` (the field must be omitted from the clone or set to None). Save the cloned project to obtain a new `pk`. Then query all segments associated with the original project ID (use the source's original PK, stored in a local variable before it was set to None). For each segment, set `segment.pk = None`, assign the new project FK, copy any media files using `shutil.copy2()` to a subfolder named after the new project's ID, update the `audio_file` and `image_file` fields to the new paths, and save each segment. Return the serialized new project wrapped in a `Response` with `status=201`.

### Step 3.2 — Register the New Duplicate Route in urls.py

File: `backend/api/urls.py`

Open the existing `urlpatterns` list and locate the entry for `projects/<int:pk>/`. Immediately after it, append a new path entry for `projects/<int:pk>/duplicate/` pointing to `DuplicateProjectView.as_view()`. Assign the route a name such as `project-duplicate` following the naming conventions already used in the file (for example, `project-list`, `project-detail`). No other changes to the URL configuration are needed for this feature.

### Step 3.3 — Add Media File Copy Logic with Correct Path Handling

File: `backend/api/views.py` (continuation of Step 3.1)

Within the segment-cloning loop, before calling `shutil.copy2()`, verify that the source file actually exists on disk using `os.path.exists()` — if the file is missing (e.g., it was deleted manually), skip the copy gracefully and set the segment's file field to an empty string rather than letting the view crash. Build the destination path by joining `settings.MEDIA_ROOT`, `"projects"`, `str(new_project.pk)`, and the original filename extracted with `os.path.basename()`. Create the destination directory using `os.makedirs(dest_dir, exist_ok=True)` before attempting the copy. Store the destination path as a path relative to `MEDIA_ROOT` (i.e., strip the `MEDIA_ROOT` prefix) when assigning it back to the segment's `audio_file` or `image_file` field, so that Django's `FileField` URL generation continues to work correctly.

### Step 3.4 — Add the Three-Dot Action Menu to ProjectCard

File: `frontend/components/ProjectCard.tsx`

Locate the JSX returned by the component. In the top-right area of the card (currently where the render button or status badge sits), add a ShadCN `DropdownMenu` component. The trigger should be a `DropdownMenuTrigger` rendered as a small icon button using the `MoreHorizontal` icon from `lucide-react`. Inside `DropdownMenuContent`, add two `DropdownMenuItem` entries: "Open Project" (which navigates to the project editor, replacing or supplementing the existing click behavior on the card) and "Duplicate" (which triggers the duplication flow). Add a local `isDuplicating` boolean state using `useState` that sets the "Duplicate" menu item to a loading/disabled state while the API call is in flight. On successful response from the duplicate endpoint, call an `onDuplicated(newProject)` callback prop (add this prop to the component's interface) so the parent page can update its list. On error, show a destructive toast using the ShadCN `useToast` hook already expected to be in the project.

### Step 3.5 — Handle the Duplication Response in the Projects List Page

File: `frontend/app/projects/page.tsx`

Find the place where the array of project objects is held in state (likely a `useState` holding the fetched list, or derived from a Zustand slice). Add an `onDuplicated` handler function that accepts the new project object returned by the API and appends it to the existing list — either via `setProjects(prev => [...prev, newProject])` if using local state, or via the appropriate Zustand action if the list lives in the store. Pass this handler down to each `ProjectCard` component as the `onDuplicated` prop. Also add a toast call inside this handler: `toast({ title: "Project duplicated", description: newProject.name, action: <a href="/projects/{newProject.id}/editor">Go to Project</a> })`. Wrap the toast action link using the Next.js `Link` component to keep navigation within the SPA router. No additional changes to the data-fetching logic are required because the new project is appended client-side.

---

## 4. Expected Outcome

1. A POST request to `/api/projects/{id}/duplicate/` returns HTTP 201 with a complete serialized representation of the new project, including its auto-generated `id` and all copied settings fields.
2. The new project's name is `{source_name} (copy)` and it appears in subsequent calls to `GET /api/projects/` as a fully independent project record.
3. All segments from the source project are present in the duplicate with identical `text_content`, `sequence_index`, `duration`, and `is_locked` values.
4. Physical audio and image files that existed on disk for the source project are copied to the new project's media subdirectory; the source project's files are untouched.
5. Segments whose `audio_file` or `image_file` was empty or pointed to a missing path have those fields set to empty strings in the duplicate without causing a server error.
6. The `ProjectCard` component displays a three-dot menu that opens correctly, containing at minimum "Open Project" and "Duplicate" items.
7. Clicking "Duplicate" shows a loading indicator on the item while the request is in flight, preventing duplicate submissions.
8. After a successful duplication, a toast notification appears in the frontend with the new project's name and a navigable "Go to Project" link.
9. The project list page updates immediately to include the new duplicate card without requiring a full page reload or re-fetch.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] `DuplicateProjectView` called with a valid project ID returns HTTP 201 and a response body whose `name` equals `{source_name} (copy)`.
- [ ] The number of `Segment` records in the database increases by exactly the source project's segment count after a successful duplication call.
- [ ] When a segment has a valid `audio_file` path pointing to an existing file, the view creates a physical copy at the expected destination path.
- [ ] When a segment's `audio_file` points to a file that does not exist on disk, the view does not raise an exception and the cloned segment has an empty `audio_file` field.
- [ ] `DuplicateProjectView` called with a non-existent project ID returns HTTP 404.
- [ ] The source project and its segments remain completely unmodified after the duplication call (verified by re-fetching source project and comparing all fields to pre-call values).

### 5.2 Integration / Manual Tests

- [ ] Open the projects list in the browser, click the three-dot menu on any card, and verify the menu renders with "Open Project" and "Duplicate" items without visual overflow or misalignment.
- [ ] Click "Duplicate", wait for the call to complete, and verify the new card appears in the list with the "(copy)" suffix in its name.
- [ ] Open the duplicate project and verify all settings (voice, resolution, subtitle config, etc.) are identical to the source project.
- [ ] Open the duplicate project's editor and verify all segments are present with the correct text content and sequence order.
- [ ] Navigate to the source project and confirm its segments and settings have not been altered in any way.
- [ ] If the source project had rendered audio files, verify those files play correctly when loaded in the duplicate project editor.
- [ ] Simulate a slow network by throttling in browser devtools; confirm the "Duplicate" menu item shows a disabled/loading state during the request and re-enables after completion.

### 5.3 Regression Tests

- [ ] The standard project CRUD operations — create, read, update, delete — continue to work correctly with no regressions after the new route is added to `urls.py`.
- [ ] Deleting the source project after duplication does not delete or affect the duplicate's files (no shared file references or cascade delete side effects).
- [ ] The `ProjectCard` render button and click-to-open behavior that existed before this feature are fully preserved after the three-dot menu and new props are added.
- [ ] The projects list page still loads and displays all projects correctly when `onDuplicated` is wired as a prop to every card.

---

## 6. Notes for AI Agent

- The most critical implementation detail is preserving the source project's original `pk` in a local variable before setting `pk = None` for cloning; losing the original ID before querying the segments will result in silently duplicating zero segments.
- All file copy operations must happen inside a `try/except` block per file; a single missing file must never abort the entire duplication — fail gracefully per file, log a warning, and continue.
- When building the new media file path, always use `os.path.basename()` to extract just the filename from the stored path, because the stored value in `audio_file` / `image_file` may be a relative path like `projects/42/segment_3.mp3` — using the full stored string as a filename would create incorrect nested directories.
- On the frontend, add `onDuplicated` to the `ProjectCard` TypeScript interface definition before implementing the handler; TypeScript errors will surface immediately if the prop is missing and will prevent subtle runtime bugs.
- The implementation order should be: backend view → URL registration → backend tests → frontend card menu → frontend list handler → frontend toast; this order ensures every layer can be tested independently before the next is built.
- Consider adding a `django.db.transaction.atomic()` decorator or context manager around the entire duplication view so that if any segment copy or file operation fails after the project row has been inserted, the entire operation rolls back cleanly and the user does not end up with a partial project clone.
