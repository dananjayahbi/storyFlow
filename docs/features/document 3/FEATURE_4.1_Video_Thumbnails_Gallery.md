# Feature 4.1 — Video Thumbnails Gallery

| Field | Value |
|---|---|
| Feature ID | 4.1 |
| Title | Video Thumbnails Gallery |
| Status | 🟡 Planned |
| Priority | High |
| Complexity | Low |
| Estimated Effort | 1–2 days |
| Dependencies | FFmpeg (already installed), rendered `output.mp4` must exist |
| Output Files (NEW) | `backend/api/migrations/000X_add_thumbnail_to_project.py`, `backend/media/projects/{id}/thumbnail.jpg` |
| Files Modified | `backend/api/models.py`, `backend/api/views.py`, `backend/api/urls.py`, `backend/api/serializers.py`, `backend/core_engine/video_renderer.py`, `frontend/components/ProjectCard.tsx`, `frontend/types/project.ts` |

---

## 1. Document Overview

### 1.1 Problem Statement

The StoryFlow project gallery currently displays all project cards as uniform text-based tiles showing only the project name, a status badge, and a render button. With any collection of more than a handful of projects, every card is visually identical in layout, differing only in the name string. A creator managing fifty or more projects cannot quickly distinguish between them at a glance — they must read each project name individually to navigate their library. This absence of visual context slows down the creative workflow and makes the gallery feel like a file manager rather than a video production tool.

### 1.2 Proposed Solution

When a render completes successfully, use FFmpeg to extract a single representative frame from the finished video and store it as a JPEG thumbnail alongside the video file. Surface that thumbnail in the project gallery card so creators can immediately see a visual preview of each project.

- Add a nullable `thumbnail` FileField to the `Project` model with a migration so the change is backward-compatible with all existing projects that have no thumbnail yet.
- After every successful render in `video_renderer.py`, probe the output MP4's total duration, calculate 10% of that duration as the seek timestamp, and invoke FFmpeg to extract one frame at that position as a JPEG into `media/projects/{id}/thumbnail.jpg`.
- Store the relative file path of the extracted thumbnail in `project.thumbnail` and save the model record, so the path is retrievable via the serializer.
- Expose the thumbnail URL through the existing project serializer so the frontend receives a `thumbnail_url` field alongside all other project fields — no extra endpoint is required.
- Update `ProjectCard.tsx` to conditionally render an `<img>` tag with aspect ratio 16:9 and `object-cover` when `thumbnail_url` is present, preserving the existing colored gradient placeholder for projects with no thumbnail.
- Wrap the entire thumbnail extraction block in a try/except so that any FFmpeg failure (missing file, permission error, corrupted video) is logged as a warning and silently skipped — the render result and project record are saved regardless.
- Provide a management command or admin action to backfill thumbnails for projects that already have an `output_file` but no thumbnail, so existing libraries are not left without previews.

### 1.3 Scope

| Category | Item |
|---|---|
| In Scope | FFmpeg frame extraction at 10% of video duration on render completion |
| In Scope | Nullable `thumbnail` FileField on Project model with migration |
| In Scope | `thumbnail_url` field in project serializer response |
| In Scope | Conditional thumbnail display in `ProjectCard.tsx` with gradient fallback |
| Out of Scope | Animated GIF or video preview on hover |
| Out of Scope | Manual thumbnail upload by the user |
| Out of Scope | Thumbnail regeneration endpoint triggered from the frontend |
| Out of Scope | Thumbnail caching layer or CDN delivery |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| `backend/api/models.py` | Defines the `Project` model with all persistent fields | Has `output_file` FileField; no `thumbnail` field exists |
| `backend/core_engine/video_renderer.py` | Orchestrates the full render pipeline, writes `output.mp4` | Saves output file path; no post-render thumbnail step |
| `backend/api/serializers.py` | Converts Django model instances to JSON for the API | Serializes `output_file`; no `thumbnail_url` field |
| `frontend/components/ProjectCard.tsx` | Renders one project tile in the gallery grid | Displays name, status badge, and render button; no image element |
| `frontend/types/project.ts` | TypeScript interface for the Project data shape | Has `outputFile`; no `thumbnailUrl` field |

---

## 2. Flow Diagram

```
Render Pipeline (video_renderer.py)
         |
         v
  [Write output.mp4]
         |
         v
  [Probe video duration via ffprobe]
         |
         v
  [Calculate seek_time = duration * 0.10]
         |
         v
  [FFmpeg: extract 1 frame at seek_time -> thumbnail.jpg]
         |
    -----+------
    |           |
[Success]    [Failure]
    |           |
    v           v
[Save path   [Log warning,
 to project   skip thumbnail]
  .thumbnail]     |
    |             |
    +-----------+-+
                |
                v
      [Project record saved]
                |
                v
  API serializer includes thumbnail_url
                |
                v
   ProjectCard.tsx receives thumbnail_url
                |
         -------+-------
         |               |
  [thumbnail_url       [No URL]
   present]               |
         |               v
         v         [Show gradient
  [Render <img>     placeholder]
   16:9 cover]
```

---

## 3. Step-by-Step Instructions

### Step 1 — Add `thumbnail` field to the Project model
- File: `backend/api/models.py`
- Add a `thumbnail` field of type `FileField` with `upload_to='projects/thumbnails/'`, set `null=True` and `blank=True` so it does not affect existing records.
- Run `python manage.py makemigrations api` to generate the migration file, then `python manage.py migrate` to apply it.
- No change to any view or serializer yet — just the model and migration.

### Step 2 — Add thumbnail extraction to the render pipeline
- File: `backend/core_engine/video_renderer.py`
- After the final MP4 has been written and its path confirmed, add a post-render block that probes the file duration using `ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1`.
- Calculate the seek time as 10% of the returned duration, then call FFmpeg with `-ss {seek_time} -i {output_path} -frames:v 1 -q:v 2 {thumb_path}` where `thumb_path` is `media/projects/{id}/thumbnail.jpg`.
- Wrap both the probe and the extraction calls in a broad try/except, log any exception at WARNING level, and continue execution so the render is never failed by a thumbnail error.

### Step 3 — Expose thumbnail URL in the serializer
- File: `backend/api/serializers.py`
- Add `thumbnail_url` as a `SerializerMethodField` on `ProjectSerializer`.
- In the method body, check if `instance.thumbnail` is truthy, and if so return `request.build_absolute_uri(instance.thumbnail.url)` — otherwise return `None`.
- Add `thumbnail_url` to the `fields` list in the serializer's Meta class.

### Step 4 — Update the TypeScript Project type and ProjectCard component
- File: `frontend/types/project.ts` — add `thumbnailUrl: string | null` to the `Project` interface.
- File: `frontend/components/ProjectCard.tsx` — in the card's visual area, conditionally render an `<img>` element with `src={project.thumbnailUrl}`, `className` set to `w-full aspect-video object-cover rounded-t-lg`, and an `alt` of `"Thumbnail for {project.name}"`.
- When `thumbnailUrl` is null or undefined, render the existing colored gradient `<div>` placeholder instead.
- No state management change required; the thumbnail URL arrives with the project list fetch already handled by the existing Zustand store and API hook.

### Step 5 — Validate end-to-end in the browser
- File: `backend/api/views.py` — no change required if the serializer already handles the field; confirm the project detail and list endpoints both return `thumbnail_url`.
- Trigger a test render on a project, then reload the gallery page and verify the card shows the thumbnail image instead of the gradient.
- Check the `backend/media/projects/{id}/` directory to confirm `thumbnail.jpg` exists and is a valid JPEG.

---

## 4. Expected Outcome

1. After any successful render, a `thumbnail.jpg` file appears in `backend/media/projects/{id}/` automatically with no manual step required.
2. The project list API response includes a `thumbnail_url` string for projects that have been rendered and `null` for projects that have never been rendered.
3. ProjectCard components in the gallery display a 16:9 preview image for rendered projects, making the library visually browsable.
4. Projects with no rendered output continue to display the colored gradient placeholder without any visual regression.
5. A failed thumbnail extraction (due to a short video, a missing binary, or any I/O error) produces only a WARNING log entry and does not interrupt, fail, or alter the render result in any way.
6. The gallery page loads without any additional API requests — thumbnail URLs are embedded in the same project list response that already powers the gallery.
7. The feature is fully backward-compatible; existing projects in the database are unaffected until they are rendered again, at which point they gain a thumbnail automatically.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] Test that `ProjectSerializer` returns `thumbnail_url` as a full absolute URL when `project.thumbnail` is set
- [ ] Test that `ProjectSerializer` returns `thumbnail_url` as `None` when `project.thumbnail` is empty
- [ ] Test that the thumbnail extraction block in `video_renderer.py` stores the correct relative path on `project.thumbnail` after a successful FFmpeg call
- [ ] Test that if the FFmpeg subprocess raises an exception, the renderer does not re-raise it and still returns the project record with a saved `output_file`
- [ ] Test that the `Project` model migration applies cleanly from the prior migration state with no data loss

### 5.2 Integration / Manual Tests

- [ ] Trigger a full render for a new project and confirm `thumbnail.jpg` is created at the expected path in the media directory
- [ ] Reload the gallery page and visually confirm the newly rendered project card shows the thumbnail image
- [ ] Open the network tab in browser DevTools and confirm the gallery API call returns `thumbnail_url` as a non-null string for rendered projects
- [ ] Simulate a bad video file by temporarily renaming the output MP4 before the thumbnail step; confirm only a WARNING is logged and the project record is still saved
- [ ] Confirm that projects with no render history display the gradient placeholder and not a broken image element

### 5.3 Regression Tests

- [ ] Existing render flow completes successfully and writes `output.mp4` without any behavioral change
- [ ] Project list and project detail API responses still include all previously existing fields with correct values
- [ ] `ProjectCard.tsx` renders without console errors for both thumbnail-present and thumbnail-absent project data shapes

---

## 6. Notes for AI Agent

- The `ffprobe` command must be run before `ffmpeg` to get the video duration — do not hardcode a fixed seek time, as very short videos (under 5 seconds) would produce an out-of-range seek and a blank frame.
- Use `subprocess.run` with `capture_output=True` and `check=False` for both the probe and the extraction calls so exit codes are handled explicitly rather than raising on non-zero.
- The `thumbnail` FileField's `upload_to` path does not need to match the `projects/{id}/` convention used by `output_file` — a flat `projects/thumbnails/` directory is simpler and avoids coupling the thumbnail path to the project PK before the record is saved.
- In `ProjectCard.tsx`, always set explicit `width` and `height` attributes on the `<img>` or use the `aspect-video` Tailwind class to prevent layout shift while the image loads.
- The `thumbnail_url` field should be read-only in the serializer — it must never be writable from the API to prevent arbitrary file path injection.
