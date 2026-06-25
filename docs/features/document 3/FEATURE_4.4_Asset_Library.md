# Feature 4.4 — Global Asset Library

| Field | Value |
|---|---|
| Feature ID | 4.4 |
| Title | Global Asset Library (Images, Music, SFX) |
| Status | 🟡 Planned |
| Priority | High |
| Complexity | Medium |
| Estimated Effort | 4 days |
| Dependencies | Feature 2.1 (Segment model), Feature 2.2 (Project media upload) |
| Output Files (NEW) | `backend/api/asset_utils.py`, `frontend/app/library/page.tsx`, `frontend/components/library/AssetCard.tsx`, `frontend/components/library/AssetGrid.tsx`, `frontend/components/library/AssetUploadDialog.tsx` |
| Files Modified | `backend/api/models.py`, `backend/api/views.py`, `backend/api/serializers.py`, `backend/api/urls.py`, `frontend/components/segments/SegmentCard.tsx`, `frontend/components/segments/ImageUploader.tsx` |

---

## 1. Document Overview

### 1.1 Problem Statement

Every new StoryFlow project begins with a completely blank slate — no images, no music, no sound effects. Creators producing a series of episodes must re-upload the same stock images, the same intro music, and the same ambient audio for every single episode. This is an unnecessary and time-consuming repetition that scales catastrophically: a creator building a 20-episode series might upload the same five background images and three music tracks over 20 times. There is no concept of a shared media pool in the current system, and no mechanism to reference an asset that has already been uploaded in a previous project.

### 1.2 Proposed Solution

Introduce a project-independent global asset library that stores reusable media files across three categories — images, music, and sound effects — and allows those assets to be dragged into any segment of any project without re-uploading.

- Create a new Django model `AssetLibraryItem` with fields for asset type, title, file path, tags, creation timestamp, and file size in bytes, with no foreign key link to any specific project.
- Add three API endpoints: list and upload assets at `/api/assets/`, delete a specific asset at `/api/assets/{id}/`, and filtered lookup via query parameters such as `?type=image&tag=horror`.
- Build a dedicated frontend page at `app/library/page.tsx` displaying three tabs — Images, Music, SFX — each showing a responsive card grid with upload capabilities per category.
- Enable drag-and-drop from the library onto any segment's image area in `SegmentCard.tsx` and `ImageUploader.tsx`; dropping an image asset triggers a PATCH request to the segment that causes the backend to copy the asset file into the project's media directory.
- Allow a background music library asset to be assigned to a project through the existing `Project.background_music_file` field by adding a "Pick from Library" option alongside the current upload button.
- Allow SFX library assets to be assigned at the segment level through a new optional `segment_sfx_file` field or through the segment's existing audio configuration.
- Implement tag-based filtering in the library UI so creators can search by mood, genre, or custom labels they assign at upload time.

### 1.3 Scope

| Category | In Scope |
|---|---|
| Asset types | Image (jpg, png, webp), Music (mp3, wav), SFX (mp3, wav) |
| Library page | Three-tab grid with upload, delete, preview, and tag filter |
| Segment integration | Drag image from library onto segment image area |
| Project music | "Pick from Library" button on project background music field |

| Category | Out of Scope |
|---|---|
| Video assets | No video clip library in this phase |
| Cloud storage | All files remain on local `MEDIA_ROOT`; no S3 or CDN |
| Asset editing | No cropping, trimming, or conversion inside the library |
| Per-user access | No user accounts or per-user asset isolation in this phase |

### 1.4 Key Files Reference

| File | Role |
|---|---|
| `backend/api/models.py` | Add `AssetLibraryItem` model definition |
| `backend/api/views.py` | Add `AssetLibraryViewSet` with list, create, destroy, and filtered list actions |
| `backend/api/serializers.py` | Add `AssetLibraryItemSerializer` for request/response shaping |
| `frontend/app/library/page.tsx` | New page: three-tab asset browser with upload dialog |
| `frontend/components/segments/ImageUploader.tsx` | Add drop-zone event handlers to accept dragged library assets |

---

## 2. Flow Diagram

```
Creator opens Library page
         |
         v
  [Library Page — Three Tabs]
  +--Images--+--Music--+--SFX--+
         |
 Selects tab, sees AssetGrid
         |
         +---> [Upload Button]
         |           |
         |     POST /api/assets/
         |     (type, title, file, tags)
         |           |
         |     Backend saves to MEDIA_ROOT/library/
         |     Creates AssetLibraryItem record
         |           |
         v           v
  AssetCard renders with preview
         |
  Creator drags AssetCard to SegmentCard
         |
         v
  ImageUploader drop-zone receives asset_id
         |
         v
  PATCH /api/segments/{id}/
  { asset_image_id: 42 }
         |
         v
  Backend copies file to project media dir
  Updates Segment.image_file field
         |
         v
  Segment image area refreshes with new image
```

---

## 3. Step-by-Step Instructions

### Step 1 — Add the `AssetLibraryItem` model (`backend/api/models.py`)

Add a new model class `AssetLibraryItem` below the existing `GlobalSettings` model. The model needs a `type` field using `CharField` with `choices` covering image, music, and sfx values. Add a `title` field (CharField, max 255), a `file` field (FileField uploading to a `library/` subfolder of MEDIA_ROOT), a `tags` field (JSONField with blank default list), a `created_at` field (auto DateTimeField), and a `size_bytes` field (IntegerField, default 0). No `project` foreign key — this model is intentionally global. Register the model in `admin.py` for easy inspection in the Django admin panel.

### Step 2 — Create API endpoints (`backend/api/views.py` and `backend/api/urls.py`)

In `views.py`, add a new `AssetLibraryViewSet` class inheriting from `ModelViewSet`. Override `get_queryset` to support optional `type` and `tag` query parameters for filtered listing. Override `perform_create` to calculate and store the uploaded file's byte size into the `size_bytes` field before saving. Add a custom `destroy` action that also deletes the physical file from disk using `os.remove()` after the database record is deleted. In `urls.py`, register the new viewset under the router with the prefix `assets`, producing `/api/assets/` and `/api/assets/{id}/` routes automatically.

### Step 3 — Build the Library frontend page (`frontend/app/library/page.tsx`)

Create the library page file with three tab sections managed by a local `useState` hook tracking the active tab (image, music, sfx). Each tab renders an `AssetGrid` component that fetches from `/api/assets/?type={activeTab}` on tab switch using a `useEffect`. Add a tag filter input at the top of each grid that appends `&tag={value}` to the fetch URL. Add an "Upload" button that opens an `AssetUploadDialog` component; the dialog accepts title, optional tags (comma-separated input), and a file picker, then sends a `multipart/form-data` POST to `/api/assets/`. On successful upload, refresh the grid. Image cards show a thumbnail using an `<img>` tag; music and SFX cards show a generic waveform icon and the file title.

### Step 4 — Enable drag-and-drop in `SegmentCard.tsx` and `ImageUploader.tsx`

In `ImageUploader.tsx`, add an `onDragOver` handler that calls `event.preventDefault()` and visually highlights the drop zone (add a CSS border ring class). Add an `onDrop` handler that reads `event.dataTransfer.getData("asset_id")` and `event.dataTransfer.getData("asset_type")`. If `asset_type` is "image" and an `asset_id` is present, dispatch a PATCH call to `/api/segments/{segmentId}/` with the payload `{ asset_image_id: <id> }`. In `AssetCard.tsx` for image assets, add a `draggable` attribute and `onDragStart` handler that sets the dataTransfer data keys `asset_id` and `asset_type`.

### Step 5 — Wire "Pick from Library" to Project music field (`frontend/components/projects/ProjectSettingsForm.tsx` or equivalent)

Locate the component that renders the project's background music upload field. Add a secondary "Pick from Library" button beside the existing file input. Clicking it opens a modal that renders the `AssetGrid` component filtered to `type=music`. When the creator clicks a music asset card in this modal, close the modal and dispatch a PATCH to `/api/projects/{projectId}/` with `{ library_music_asset_id: <id> }`. The backend view for project update should handle the `library_music_asset_id` field by copying the library file to the project media directory and assigning the resulting path to `Project.background_music_file`.

---

## 4. Expected Outcome

- A new `/library` page exists in the frontend and is reachable from the top navigation bar.
- The library page displays three tabs, each fetching and rendering asset cards from the backend.
- Uploading an image, music file, or SFX clip through the library adds it to the database and renders it in the corresponding tab grid.
- Dragging an image asset card from the library and dropping it on a segment's image area successfully updates that segment's image without any file re-upload by the user.
- The "Pick from Library" option appears on the project background music input and allows selecting a previously uploaded music track.
- Tags entered at upload time are stored correctly and the tag filter on the library page narrows the displayed assets to matching items.
- Deleting an asset from the library removes both the database row and the physical file from disk.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] `AssetLibraryItem` model saves correctly with all three type choices (image, music, sfx) and persists to the database.
- [ ] `AssetLibraryViewSet` returns only assets matching the `type` query parameter when `?type=music` is passed.
- [ ] `AssetLibraryViewSet` returns only assets whose `tags` list contains the requested tag when `?tag=horror` is passed.
- [ ] Deleting an asset via `DELETE /api/assets/{id}/` removes the file from the filesystem (mock `os.remove` in the test).
- [ ] `perform_create` correctly computes and stores `size_bytes` from the uploaded file object.

### 5.2 Integration / Manual Tests

- [ ] Upload a JPEG image via the library UI — confirm it appears in the Images tab grid with a visible thumbnail.
- [ ] Upload an MP3 file via the library UI — confirm it appears in the Music tab grid with a title label.
- [ ] Drag an image asset card from the library onto a segment's image drop zone — confirm the segment's image area updates immediately in the UI.
- [ ] Open a project's settings, click "Pick from Library" for background music, select a track, save — confirm the project plays the selected music track on render.
- [ ] Enter a tag "summer" at upload time, use the tag filter to search "summer" — confirm only tagged assets appear.
- [ ] Delete an asset from the library — confirm it disappears from the grid and the file no longer exists under `backend/media/library/`.

### 5.3 Regression Tests

- [ ] Existing segment image upload (direct file upload, not library drag) continues to work without errors.
- [ ] Project background music file upload (direct, not library) continues to work as before.
- [ ] Existing project list, segment list, and render endpoints return unmodified responses after the new model and viewset are added.

---

## 6. Notes for AI Agent

- The `AssetLibraryItem.file` field must use `upload_to="library/"` so all library assets land in a dedicated subfolder under `MEDIA_ROOT`, keeping them separate from per-project media.
- When the backend copies a library asset into a project's media directory (for segment image or project music assignment), it must use `shutil.copy2()` rather than moving the file — the original library asset must remain intact for reuse.
- The `tags` JSONField stores a plain Python list of lowercase strings; the filter logic on the backend should check `tags__contains=[tag_value]` using Django's JSONField lookup syntax.
- Adding the library page to the frontend navigation requires updating whatever nav component currently exists (likely in `frontend/components/layout/` or `frontend/app/layout.tsx`) — check before creating a new nav item to avoid duplication.
- The drag-and-drop implementation must remain accessible: provide a fallback "Assign from Library" button click path for users who cannot use drag-and-drop (e.g., tablet or keyboard-only users).
