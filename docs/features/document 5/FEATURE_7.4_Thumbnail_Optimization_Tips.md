# Feature 7.4 — Thumbnail Optimization Tips

| Field | Value |
|---|---|
| Feature ID | 7.4 |
| Title | Thumbnail Optimization Tips |
| Status | 🟡 Planned |
| Priority | Medium |
| Complexity | Medium |
| Estimated Effort | 3–5 days |
| Dependencies | Rendered MP4 output exists, FFmpeg installed in PATH, Pillow (PIL) available in backend virtualenv |
| Output Files (NEW) | frontend/components/ThumbnailWorkshop.tsx, backend/api/thumbnail_utils.py |
| Files Modified | backend/api/views.py, backend/api/urls.py, backend/api/models.py, frontend/app/projects/[id]/page.tsx, frontend/store/thumbnailStore.ts |

---

## 1. Document Overview

### 1.1 Problem Statement

Thumbnails are the single highest-impact visual asset controlling whether a potential viewer clicks a video on YouTube, TikTok, Instagram Reels, or any major distribution platform — research consistently shows that thumbnail quality can double or triple click-through rate for identically titled content.
StoryFlow currently produces a finished MP4 video file but provides absolutely no thumbnail tooling: there is no frame extraction, no overlay composition, no CTR-focused guidance, and no thumbnail management interface anywhere in the application.
Creators who want a thumbnail must leave StoryFlow entirely, manually scrub through the rendered video in an external player, take a screenshot, open a separate photo editor such as Canva or Photoshop, add text and graphic elements, export the result, and upload it to the platform — a multi-application workflow that is tedious, error-prone, and completely disconnected from the production pipeline.
The absence of thumbnail tooling means StoryFlow-generated content is systematically disadvantaged at the distribution layer because creators either skip custom thumbnails (using inferior auto-generated frames) or spend disproportionate time on manual post-processing outside the tool.

### 1.2 Proposed Solution

Add a self-contained Thumbnail Workshop module to StoryFlow that enables creators to extract candidate frames from the rendered video, receive data-backed CTR tips derived from the project's actual script content, apply basic text overlays directly in the browser, and save a final thumbnail — all without leaving the application. The module is intentionally lightweight: it does not attempt to replicate a full image editor, but instead focuses on the 80% use case of picking a strong frame, overlaying a short bold text phrase, and following evidence-based tips that most creators would not know to apply on their own.

- Add a backend endpoint at POST /api/projects/{id}/extract-thumbnail/ that accepts a timestamp in seconds and uses FFmpeg to extract a single JPEG frame from the rendered output video, saving it to the project's media folder as a thumbnail candidate with an auto-incremented filename.
- Add a companion GET /api/projects/{id}/thumbnail-candidates/ endpoint that returns a list of all previously extracted candidate images for the project, including their URLs, timestamps of extraction, and creation timestamps.
- Build a GET /api/projects/{id}/thumbnail-tips/ endpoint that reads the project's segment data, applies a set of heuristic rules to the script text, and returns 4–6 tip objects, each containing the tip text, a severity label (High Impact or Suggested), and a one-sentence rationale explaining the psychological or algorithmic reason behind the tip.
- Create the ThumbnailWorkshop.tsx component as a side panel or modal drawer on the project page, housing an HTML5 video element for the rendered output, a Capture Frame button, a candidate grid, and a Tips tab — all in a single coherent UI surface.
- Add a text overlay tool inside ThumbnailWorkshop.tsx: a form with a text input, a font size selector (Small / Medium / Large), and a vertical position selector (Top / Center / Bottom) that submits overlay parameters to the POST /api/projects/{id}/apply-thumbnail-overlay/ backend endpoint.
- Implement the overlay endpoint using Pillow (PIL) in a new thumbnail_utils.py helper module: it loads the candidate JPEG, draws the text at the specified position using a bundled bold font, and returns the resulting overlaid image as a new candidate.
- Save the final selected thumbnail via a POST /api/projects/{id}/set-thumbnail/ endpoint that copies the chosen candidate to a stable path and stores its URL in the Project model, then display it prominently in the project list card view.

### 1.3 Scope

**In Scope**

| Item | Description |
|---|---|
| Frame extraction | FFmpeg-based JPEG extraction at a creator-specified timestamp from the rendered MP4 |
| Heuristic CTR tips | Rule-based analysis of segment text to generate 4–6 actionable thumbnail tips with rationale |
| Text overlay | Simple form-based text overlay applied server-side using Pillow; no drag-and-drop canvas |
| Thumbnail persistence | Saving and displaying the final thumbnail URL in the Project model and project card UI |

**Out of Scope**

| Item | Description |
|---|---|
| WYSIWYG image editor | No live drag-and-drop canvas, no shape drawing, no layer management |
| AI-generated thumbnails | No generative image model or image-to-image enhancement at this phase |
| Platform API upload | No direct upload to YouTube, TikTok, or any social platform via OAuth |
| A/B testing analytics | No split-testing or CTR tracking; tips are static heuristics, not adaptive recommendations |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| backend/api/views.py | Houses all DRF API view classes and function-based views | Exists; thumbnail endpoints must be added as new view functions |
| backend/api/urls.py | URL routing for all backend API endpoints | Exists; four new URL patterns must be registered |
| backend/api/models.py | Defines Project, Segment, GlobalSettings Django models | Exists; thumbnail_url and thumbnail_candidate_count fields must be added to Project |
| backend/core_engine/video_renderer.py | FFmpeg-based MP4 render pipeline | Exists; output file path is needed to know which file to extract frames from |
| frontend/components/ThumbnailWorkshop.tsx | New React component for the thumbnail panel | Does not exist; must be created from scratch |
| frontend/app/projects/[id]/page.tsx | Project detail page in the Next.js app | Exists; must be updated to mount ThumbnailWorkshop conditionally when a render exists |

---

## 2. Flow Diagram

    Creator opens Project Page (render exists)
              |
              v
    [ ThumbnailWorkshop Panel opens ]
              |
        +-----+------+
        |             |
        v             v
    Scrub Video    View Tips Tab
    + Capture      (GET /thumbnail-tips/)
    Frame          Returns 4–6 tip cards
        |             |
        v             v
    POST /extract-thumbnail/    Render tip cards
    FFmpeg extracts JPEG        with severity badges
    Saved as candidate_N.jpg
        |
        v
    Candidate grid displayed
    (GET /thumbnail-candidates/)
        |
        v
    Creator selects candidate
    + enters overlay text
        |
        v
    POST /apply-thumbnail-overlay/
    Pillow draws text → new candidate
        |
        v
    POST /set-thumbnail/
    Candidate copied to stable path
    URL stored in Project.thumbnail_url
        |
        v
    Thumbnail shown in project card

---

## 3. Step-by-Step Instructions

### Step 1 — Add the Thumbnail URL field to the Project model and create the thumbnail_utils helper

Open backend/api/models.py and add a thumbnail_url field as a CharField with max_length=500 that allows blank and null values, and a thumbnail_candidate_count IntegerField with a default of zero — these two fields let the backend track the final chosen thumbnail and the auto-increment index for naming candidate files.
Run Django migrations after saving the model change so the new columns are created in the SQLite database without affecting any existing project data.
Create a new file at backend/api/thumbnail_utils.py and write a function called extract_frame_at_timestamp that accepts an input video path, a timestamp in seconds, and an output JPEG file path, then uses Python's subprocess module to call FFmpeg with the appropriate seek (-ss), input (-i), frame count (-frames:v 1), and output quality (-q:v 2) flags to extract a single high-quality JPEG frame.
In the same thumbnail_utils.py file, write a draw_text_overlay function that accepts an image file path, an overlay text string, a size token (small/medium/large mapped to specific pixel sizes), a position token (top/center/bottom mapped to Y-coordinate fractions), and an output path, then uses Pillow's ImageDraw.Draw to render the text with a dark semi-transparent drop shadow followed by white bold text on top.
Verify both functions work correctly in isolation by importing them in a Django shell session (python manage.py shell), calling each function with test inputs against a real image or video file on disk, and confirming that the output files are written with the expected content before wiring them to the API endpoints.

### Step 2 — Implement the four backend API endpoints in views.py and register them in urls.py

Open backend/api/views.py and add a function-based view called extract_thumbnail_view decorated with the DRF api_view POST decorator, which retrieves the project by primary key from the URL parameter, reads the timestamp_seconds float from the request body, resolves the rendered output video path from the project's media folder, calls extract_frame_at_timestamp from thumbnail_utils.py with an output path of thumbnail_candidate_{n}.jpg (where n is the current candidate count incremented by one), updates Project.thumbnail_candidate_count in the database, and returns the candidate URL in the JSON response.
Add a second view called list_thumbnail_candidates_view (GET) that scans the project's media folder for all files matching the thumbnail_candidate_*.jpg pattern, sorts them by creation timestamp, and returns a JSON array of objects each containing the candidate index, file URL, and creation datetime so the frontend can populate the candidate grid.
Add a third view called get_thumbnail_tips_view (GET) that fetches all segments for the project, concatenates their text_content fields, applies heuristic checks (number detection, question mark detection, segment count thresholds), builds a list of tip dictionaries with keys tip_text, severity, and rationale, and always appends the three universal tips about high contrast, face close-ups, and bold readable text before returning the list.
Add a fourth view called apply_thumbnail_overlay_view (POST) that reads candidate_filename, overlay_text, font_size, and position from the request body, resolves the candidate image path in the project media folder, calls draw_text_overlay from thumbnail_utils.py to produce a new candidate file named with an incremented index, stores the new candidate, and returns its URL in the response.
Open backend/api/urls.py and register all four new URL patterns under the projects/{id}/ namespace using the DRF path() function, making sure the URL names are unique and consistent with the naming convention used by existing project-scoped endpoints.

### Step 3 — Build the ThumbnailWorkshop.tsx React component with the video scrubber and candidate grid

Create the file frontend/components/ThumbnailWorkshop.tsx as a React functional component that accepts a projectId prop and a videoUrl prop representing the URL of the rendered MP4 output, then renders a container with two tabs: a "Workshop" tab for frame capture and overlay, and a "Tips" tab for the CTR recommendations.
In the Workshop tab, place an HTML5 video element pointing to the videoUrl prop with controls enabled so the creator can play, pause, and scrub to any desired frame; add a "Capture Frame" button that reads the video element's currentTime property in seconds using a React ref, calls the POST /api/projects/{id}/extract-thumbnail/ backend endpoint with that timestamp value, and appends the returned candidate URL to the local candidates state array.
Render the candidates state array as a responsive CSS grid of thumbnail cards below the video player, each card showing the candidate image, an extraction timestamp label formatted as "Captured at 1:23", a "Select" radio or highlight button to mark the candidate as the active selection for overlay, and a subtle delete button to remove unwanted candidates.
Add the text overlay form below the candidate grid: a controlled textarea for the overlay text (max 60 characters to prevent text from overflowing the thumbnail), a select element for font size with options Small, Medium, and Large, a select element for position, and a "Apply Overlay" button that posts the form data to the apply-thumbnail-overlay endpoint and replaces the selected candidate with the newly returned overlaid image URL.
Add a "Set as Final Thumbnail" primary button that is enabled only when a candidate is actively selected and sends a POST to /api/projects/{id}/set-thumbnail/ with the chosen candidate filename; on success, call any parent page callback or invalidate the SWR/React Query cache for the project so the updated thumbnail_url appears in the project card without requiring a page reload.

### Step 4 — Implement the Tips tab and severity badge rendering

In the Tips tab of ThumbnailWorkshop.tsx, use a useEffect hook (or React Query / SWR) to fetch from GET /api/projects/{id}/thumbnail-tips/ when the tab becomes active, storing the result in a tips state array and handling the loading and error states with appropriate skeleton placeholders or error messages.
Render each tip as a card element containing the tip text as the main body in a medium-weight font, the rationale sentence in a smaller muted italic font below the tip text, and a colored pill badge aligned to the right edge of the card — green with the label "High Impact" for high-priority tips, and blue with the label "Suggested" for lower-priority tips.
Ensure the tips are rendered in priority order so that the most impactful tips (High Impact severity) appear at the top of the list, giving creators an immediately actionable reading experience without needing to scroll past lower-priority suggestions.
Add a brief introductory sentence above the tips list explaining that the tips are derived from analyzing the project's script content and are based on documented CTR research, so creators understand the origin of the recommendations and do not perceive them as generic filler advice.
Test the tips endpoint manually with several different project scripts to confirm that the heuristic rules fire correctly: a script with a number in the opening line should return the numbers tip, a script without a question mark should return the curiosity-gap tip, and a project with more than fifteen segments should return the progress-bar tip.

### Step 5 — Integrate ThumbnailWorkshop into the project page and update the project list card UI

Open frontend/app/projects/[id]/page.tsx and conditionally mount the ThumbnailWorkshop component inside a collapsible section or accordion below the render controls section, only rendering it when the project's render_status field equals "completed" and a rendered output file URL is available in the project data.
Pass the correct projectId and videoUrl props to ThumbnailWorkshop by reading them from the project data fetched at the page level, ensuring the videoUrl points to the Django-served media file URL rather than a local filesystem path.
Open the project card component used in the project list view (likely frontend/components/ProjectCard.tsx or similar) and add an img element that renders when project.thumbnail_url is non-empty, positioned to fill the upper portion of the card with object-fit cover styling so the thumbnail looks like a polished video card similar to YouTube's grid layout.
Add a small "No Thumbnail" placeholder graphic or muted label in the card for projects that have a completed render but no thumbnail set yet, accompanied by a "Add Thumbnail" link that deep-links directly to the project page scrolled to the ThumbnailWorkshop section.
Run the full frontend development server alongside the Django backend, navigate to a project with a completed render, open the ThumbnailWorkshop panel, capture several frames, apply a text overlay to one, set it as the final thumbnail, return to the project list, and confirm the thumbnail image displays correctly in the project card.

---

## 4. Expected Outcome

1. Creators can extract a JPEG thumbnail candidate from any timestamp in the rendered video by scrubbing the in-browser video player and clicking a single button — the extracted frame appears in the candidate grid within two seconds of clicking.
2. The backend heuristic tips engine returns between four and six personalized CTR tips for every project by analyzing actual script content, and each tip is accompanied by a one-sentence rationale so creators understand the evidence behind the recommendation.
3. Creators can add short bold text overlays (up to 60 characters) to any thumbnail candidate using the overlay form, choosing from three font sizes and three vertical positions, and the server applies the overlay using Pillow and returns the updated image without requiring any external image editor.
4. The final chosen thumbnail is persisted to the Project model's thumbnail_url field and displayed prominently in the project card in the project list view, giving the project dashboard a polished, thumbnail-forward layout similar to professional video platforms.
5. All thumbnail candidate files are saved in the project's media folder with predictable numbered filenames, so they survive page reloads and server restarts and are visible in the candidate grid whenever the creator returns to the Workshop panel.
6. The Tips tab contains zero hard-coded generic tips: every tip in the returned list is either triggered by a condition in the specific project's script or is one of the three universal best-practice tips that apply to all video thumbnails regardless of content.
7. The entire thumbnail workflow — from frame extraction to overlay to final save — is completed without leaving the StoryFlow application, eliminating the multi-tool friction that previously required external software.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] thumbnail_utils.extract_frame_at_timestamp produces a valid non-empty JPEG file at the specified output path when given a valid video file and a timestamp within the video's duration
- [ ] thumbnail_utils.draw_text_overlay produces an output image with the correct dimensions and a non-identical pixel content compared to the input image, confirming text was drawn
- [ ] get_thumbnail_tips_view returns the numbers tip when the first segment text content contains a digit, and does not return it when no digit is present
- [ ] get_thumbnail_tips_view always includes exactly the three universal tips (high contrast, face close-up, bold text) regardless of script content
- [ ] extract_thumbnail_view increments Project.thumbnail_candidate_count by exactly one on each successful call and returns a 400 error if the project has no rendered output video

### 5.2 Integration / Manual Tests

- [ ] Navigate to a completed project, open ThumbnailWorkshop, scrub to a frame, click Capture Frame, and verify the extracted JPEG appears in the candidate grid with the correct timestamp label
- [ ] Apply a Medium-size centered text overlay to a candidate, verify the returned image shows visible white text drawn over the frame content, and confirm a new candidate file was created rather than overwriting the original
- [ ] Click Set as Final Thumbnail, navigate to the project list, and verify the selected thumbnail image appears in the project card with correct aspect ratio and no distortion
- [ ] Open the Tips tab on a project with a numbered opening line and confirm the numbers-in-titles tip is present with the "High Impact" green badge
- [ ] Attempt to extract a thumbnail from a project whose render_status is not "completed" and confirm the endpoint returns a descriptive error response rather than an unhandled exception
- [ ] Verify that refreshing the project page and reopening ThumbnailWorkshop shows all previously captured candidates still present in the grid by reading from the list-candidates endpoint

### 5.3 Regression Tests

- [ ] Confirm that the project detail page loads without errors for projects that have no thumbnail data (thumbnail_url is blank) and that the ThumbnailWorkshop section is simply hidden rather than throwing a React error
- [ ] Confirm that the existing render start, render status polling, and segment management endpoints continue to function correctly after the model migration that adds thumbnail_url and thumbnail_candidate_count fields
- [ ] Confirm that the project list API response still deserializes correctly in the frontend after the Project model gains the two new thumbnail fields, with no TypeScript type errors in the project list component

---

## 6. Notes for AI Agent

- When implementing extract_frame_at_timestamp, use the -ss flag before the -i flag (input-side seeking) rather than after, because input-side seeking is significantly faster for long videos since FFmpeg does not decode every preceding frame to reach the target timestamp.
- The tips heuristic logic should live entirely in the backend view or a dedicated tips_engine.py helper and must not contain any hardcoded project-specific assumptions; every rule should be a clearly named constant or function so future contributors can add new heuristic rules without modifying existing logic.
- The apply-thumbnail-overlay endpoint must create a new candidate file rather than modifying the original candidate in-place; this ensures the creator can compare the overlaid and original versions and revert to the clean candidate if the overlay text does not look good.
- When testing the Tips tab in the frontend, use React Query or SWR with a staleTime of at least 60 seconds to avoid re-fetching the tips on every render — the tips are derived from static script content and do not change unless segments are edited, so aggressive refetching wastes bandwidth.
- All thumbnail candidate files should be served through Django's standard MEDIA_URL mechanism rather than a custom static file route so that existing media file permissions, storage backend configuration, and CORS headers apply automatically without additional configuration.
