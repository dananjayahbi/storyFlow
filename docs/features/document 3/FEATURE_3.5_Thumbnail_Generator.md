# Feature 3.5 — Thumbnail Generator

| Field | Value |
|---|---|
| Feature ID | 3.5 |
| Title | Auto-Generate Video Thumbnail (Image Overlay / Frame Extract / Template) |
| Status | 🟡 Planned |
| Priority | High |
| Complexity | Medium |
| Estimated Effort | 5–7 days |
| Dependencies | Project must have at least one segment with an image uploaded (Mode A); rendered `output.mp4` must exist for Mode B; Pillow must be installed in backend (all modes) |
| Output Files (NEW) | `backend/core_engine/thumbnail_generator.py`, `frontend/components/ThumbnailModal.tsx` |
| Files Modified | `backend/api/models.py`, `backend/api/views.py`, `backend/api/urls.py`, `backend/api/serializers.py`, `frontend/app/projects/[id]/page.tsx`, `frontend/components/ProjectCard.tsx` |

---

## 1. Document Overview

### 1.1 Problem Statement

Every video published to YouTube, TikTok, or any other short-form platform requires a custom thumbnail to drive click-through rates. StoryFlow currently has no thumbnail generation feature, forcing creators to leave the application and open external tools such as Canva or Adobe Photoshop after each render. For a creator producing fifty videos per month, this represents fifty separate sessions in an external application — adding ten to twenty minutes of overhead per video. The project page in StoryFlow offers no visual representation of what the video looks like once rendered, leaving the project list a wall of identical gradient placeholders. This disconnect between StoryFlow's streamlined render pipeline and the manual thumbnail step creates a friction point that works against the application's core promise of end-to-end video production.

### 1.2 Proposed Solution

Add a "Generate Thumbnail" button to the project detail page that opens a three-tab modal offering three distinct thumbnail creation modes. Each mode is handled by a dedicated backend endpoint, and all generated thumbnails are stored in the project media directory and associated with the `Project` model via a new `thumbnail_file` field.

Key implementation points:

- Add a `thumbnail_file` FileField (nullable, blank=true) to the `Project` model in `backend/api/models.py` and create the corresponding database migration.
- Create `backend/core_engine/thumbnail_generator.py` with two standalone functions: `generate_thumbnail_image_title` for Mode A and `generate_thumbnail_frame` for Mode B; Mode C templates are also handled in this file as a dictionary of named Pillow drawing procedures.
- Expose a single endpoint `POST /api/projects/{id}/thumbnail/` that accepts a `mode` query parameter (`image_title`, `frame`, or `template`) and an optional `at` parameter for timestamp in Mode B and an optional `template_id` parameter for Mode C.
- Add a secondary endpoint `GET /api/projects/{id}/thumbnail.jpg` that serves the stored thumbnail file or returns a 404 if none has been generated yet.
- Build `frontend/components/ThumbnailModal.tsx` as a ShadCN Dialog with three tabs, a live preview pane, a "Generate" button, and a "Download" link.
- Update `frontend/components/ProjectCard.tsx` to show the thumbnail image (if the `thumbnail_url` field is present in the project API response) in place of the current CSS gradient placeholder.
- Update the project serializer to include `thumbnail_url` as a read-only absolute URL field.

### 1.3 Scope

| Category | Item |
|---|---|
| In Scope | Mode A: first segment image composited with title text via Pillow, saved as 1280×720 JPEG |
| In Scope | Mode B: single frame extraction from rendered output.mp4 using FFmpeg at a user-specified timestamp |
| In Scope | Mode C: five Pillow-drawn template designs rendered with the project title |
| In Scope | Frontend modal with tab selection, live preview after generation, and one-click download |
| Out of Scope | Custom font upload — only bundled fonts in `backend/fonts/` are used |
| Out of Scope | Animated GIF or video preview thumbnails |
| Out of Scope | Social media direct upload from the thumbnail modal |
| Out of Scope | AI-generated thumbnail imagery (image generation model integration) |

### 1.4 Key Files Reference

| File | Role |
|---|---|
| `backend/core_engine/thumbnail_generator.py` | New file — contains all Pillow and FFmpeg thumbnail generation logic |
| `backend/api/models.py` | `Project` model — receives new `thumbnail_file` FileField |
| `backend/api/views.py` | Receives new `ThumbnailGenerateView` and `ThumbnailServeView` class-based views |
| `backend/api/urls.py` | Registers the two new thumbnail URL patterns |
| `backend/api/serializers.py` | `ProjectSerializer` gains read-only `thumbnail_url` serializer field |
| `frontend/components/ThumbnailModal.tsx` | New component — three-tab modal for trigger and preview |
| `frontend/components/ProjectCard.tsx` | Updated to display thumbnail image instead of gradient placeholder |
| `frontend/app/projects/[id]/page.tsx` | Project page — hosts the "Generate Thumbnail" button that opens the modal |

---

## 2. Flow Diagram

```
User clicks "Generate Thumbnail" on the project detail page
        |
        v
ThumbnailModal opens (ShadCN Dialog)
        |
        +-----> Tab A: Image + Title (default selected)
        |       Shows Mode A description and a "Generate" button
        |
        +-----> Tab B: Video Frame
        |       Shows timestamp input (seconds), only enabled if output.mp4 exists
        |
        +-----> Tab C: Template Gallery
                Shows 5 thumbnail template thumbnails for selection
        |
User selects a tab and clicks "Generate"
        |
        v
Frontend sends POST /api/projects/{id}/thumbnail/?mode=...
        |
        v
Django view routes to thumbnail_generator.py
        |
        +-- Mode A ----> load first segment image (Pillow)
        |                resize + crop to 1280x720
        |                draw semi-transparent bottom bar
        |                render project name in bold font from /fonts/
        |                save as media/projects/{id}/thumbnail.jpg
        |
        +-- Mode B ----> verify output.mp4 exists
        |                run ffmpeg -i output.mp4 -ss {at} -frames:v 1 thumbnail.jpg
        |                save to media/projects/{id}/thumbnail.jpg
        |
        +-- Mode C ----> lookup template by template_id
                         apply Pillow draw operations (gradient, shapes, text)
                         save as media/projects/{id}/thumbnail.jpg
        |
        v
View updates Project.thumbnail_file, returns JSON { thumbnail_url }
        |
        v
Frontend displays thumbnail in modal preview pane
        |
        v
User clicks "Download" → browser downloads thumbnail.jpg
        |
        v
ProjectCard in project list now shows the thumbnail image
```

---

## 3. Step-by-Step Instructions

### Step 1 — Extend the Project model and create migration

File: `backend/api/models.py`
Function/Component: `Project` model class
What to change: Add a `thumbnail_file` field of type `FileField` with `upload_to='projects/{id}/thumbnails/'`, `null=True`, and `blank=True`. After saving the file, run `python manage.py makemigrations` to generate the migration and then `python manage.py migrate` to apply it. Also add a helper property `thumbnail_url` on the model that returns an absolute URL to the file if it exists or `None` otherwise — this will be used by the serializer.

### Step 2 — Create thumbnail_generator.py

File: `backend/core_engine/thumbnail_generator.py`
Function/Component: New module — `generate_thumbnail_image_title`, `generate_thumbnail_frame`, `generate_thumbnail_template`
What to change: Create the file from scratch. `generate_thumbnail_image_title(project)` should open the image file from the first segment (sorted by order), use Pillow's `Image.open` and `ImageDraw.Draw` to resize to 1280×720 with cover cropping, draw a 90-pixel-tall semi-transparent dark rectangle across the bottom, then render the project's `name` field in white using a TrueType font from the `backend/fonts/` directory at approximately 52 pt. `generate_thumbnail_frame(project, timestamp)` should build an FFmpeg subprocess command that extracts one frame at the given timestamp from the project's rendered output path, saving it directly as the thumbnail file. `generate_thumbnail_template(project, template_id)` should select from a dictionary of five template drawing procedures and apply the chosen one.

### Step 3 — Add Django views for thumbnail generation and serving

File: `backend/api/views.py`
Function/Component: New `ThumbnailGenerateView` (APIView, POST) and `ThumbnailServeView` (APIView, GET)
What to change: `ThumbnailGenerateView` reads the `mode` query parameter and delegates to the appropriate function in `thumbnail_generator.py`. On success, it saves the returned file path to `project.thumbnail_file`, calls `project.save()`, and returns a JSON response containing `thumbnail_url`. On failure (for example no segment image exists or output video not found), it returns a 400 response with a descriptive error message. `ThumbnailServeView` checks whether `project.thumbnail_file` is set — if yes, it redirects or serves the file; if no, it returns a 404.

### Step 4 — Register URL patterns

File: `backend/api/urls.py`
Function/Component: `urlpatterns` list
What to change: Add two new URL patterns — one for `POST /api/projects/<int:pk>/thumbnail/` mapped to `ThumbnailGenerateView` and one for `GET /api/projects/<int:pk>/thumbnail.jpg` mapped to `ThumbnailServeView`. Place these patterns before any catch-all patterns in the list to avoid routing conflicts.

### Step 5 — Update serializers and ProjectCard

File: `backend/api/serializers.py` (primary) and `frontend/components/ProjectCard.tsx` (secondary)
Function/Component: `ProjectSerializer`, `ProjectCard` component
What to change: In `ProjectSerializer`, add a `thumbnail_url` field using `SerializerMethodField` that calls the model's helper property and wraps it with `request.build_absolute_uri()` to produce a full URL. In `ProjectCard.tsx`, check whether the `thumbnail_url` prop is a non-null string — if it is, render an `<img>` element with `object-fit: cover` inside the card's image area; if it is null, continue rendering the existing CSS gradient placeholder unchanged.

### Step 6 — Build the ThumbnailModal frontend component

File: `frontend/components/ThumbnailModal.tsx`
Function/Component: New `ThumbnailModal` functional component; also update `frontend/app/projects/[id]/page.tsx` to add the trigger button
What to change: Create `ThumbnailModal.tsx` using ShadCN Dialog, Tabs, TabsContent, Button, and Input components. Tab A shows Mode A description and a Generate button. Tab B shows a numeric input for timestamp (in seconds), a note that this mode requires a completed render, and a Generate button. Tab C shows five clickable template thumbnails generated from static preview images and a Generate button. After calling the generate endpoint, show a loading spinner on the Generate button, then display the returned thumbnail in an `<img>` preview inside the modal and enable a "Download as JPG" anchor link. In the project detail page, add a "Generate Thumbnail" button near the project title area that sets a boolean state variable `thumbnailModalOpen` to open the modal.

---

## 4. Expected Outcome

1. A "Generate Thumbnail" button appears on the project detail page, visible at all times regardless of project render status.
2. Clicking the button opens a modal with three clearly labeled tabs: "Image + Title", "Video Frame", and "Template".
3. In Mode A, clicking Generate produces a 1280×720 JPEG showing the first segment's image with a dark bottom bar and the project's name rendered in white text, delivered within three seconds for standard images.
4. In Mode B, the timestamp input defaults to 5.0 seconds; clicking Generate extracts that frame from the rendered video and displays it in the preview pane; the button is disabled and shows a tooltip if no render output exists.
5. In Mode C, the user can click one of five template previews to select it, then click Generate to produce the styled thumbnail with the project title applied.
6. After any successful generation, the thumbnail image appears in the preview pane and a "Download as JPG" button becomes active.
7. After the modal is closed, the project card in the project list view shows the newly generated thumbnail image instead of the default gradient placeholder.
8. The generated thumbnail file is persisted on the server and returned on subsequent page loads — regenerating is optional, not required on every visit.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] `generate_thumbnail_image_title` unit test: given a project with one segment containing a valid image file, the function returns a Pillow `Image` object of exactly 1280×720 pixels.
- [ ] `generate_thumbnail_image_title` unit test: the bottom bar is present — a pixel sample at (640, 700) should have an alpha-composited dark value, not the raw image color.
- [ ] `generate_thumbnail_frame` unit test: given a mock FFmpeg call, the function constructs the correct subprocess command string containing the timestamp and output path.
- [ ] `ThumbnailGenerateView` unit test: a POST request with `mode=image_title` to a project with no segments returns a 400 response with a message containing the word "segment".
- [ ] `ProjectSerializer` unit test: `thumbnail_url` is present in the serialized output and equals `None` when `thumbnail_file` is not set on the project.

### 5.2 Integration / Manual Tests

- [ ] End-to-end Mode A: upload an image to the first segment of a project, click Generate Thumbnail in Mode A, verify the returned image file appears in `media/projects/{id}/` and is visible in the modal preview.
- [ ] End-to-end Mode B: render a project to completion, open the Thumbnail modal, enter timestamp 3.0, click Generate, verify the returned frame matches the video content at approximately three seconds.
- [ ] End-to-end Mode C: select the second template, click Generate, verify the project title appears on the template background in the preview.
- [ ] Download button: after generation, click "Download as JPG" and confirm the browser receives a file named `thumbnail.jpg` with the correct MIME type `image/jpeg`.
- [ ] ProjectCard update: after generating a thumbnail and navigating to the project list, confirm the card shows the thumbnail image instead of the gradient.
- [ ] Error state: send a POST with `mode=frame` on a project with no render output — confirm the modal shows the error message returned by the API without crashing.

### 5.3 Regression Tests

- [ ] All existing project API endpoints (`GET /api/projects/`, `POST /api/projects/`, `PATCH /api/projects/{id}/`) return correct responses after the model migration is applied — none of the existing fields are altered.
- [ ] `ProjectCard.tsx` renders the gradient placeholder without error for all projects that do not yet have a `thumbnail_url` field — this is the common case until thumbnails are generated.
- [ ] The project detail page loads and all existing actions (segment editing, render trigger, audio controls) function normally after `ThumbnailModal` is added to the page.

---

## 6. Notes for AI Agent

- Before implementing `generate_thumbnail_image_title`, inspect `backend/fonts/` to determine which TrueType font files are available. Use the font file that is already present rather than downloading a new font — this keeps the dependency footprint minimal and avoids licensing concerns.
- The FFmpeg command in `generate_thumbnail_frame` must use the `-ss` flag before `-i` (input seek) for fast seeking on large video files, not after `-i` (output seek). This is a common FFmpeg mistake that results in slow extraction on files longer than thirty seconds.
- Pillow must be listed in `backend/requirements.txt`. Verify it is present before starting — if it is missing, add `Pillow>=10.0.0` to the requirements file and note this in the implementation PR.
- The `ThumbnailModal` component should use the ShadCN `Dialog` and `Tabs` primitives already configured in the project's `components.json` rather than building a custom modal from scratch. Check `frontend/components.json` for the exact component names available.
- When saving the thumbnail file to `project.thumbnail_file` in the Django view, use Django's `ContentFile` and `File` abstractions rather than writing directly to disk with `open()` — this ensures compatibility with any future storage backend configuration (such as S3) without requiring code changes.

---

*Document created: 2026-03-10 | Feature area: Backend / Frontend Integration | Phase 03 — The Polish*
