# Task 04.01.04 — Implement Video Renderer

> **Sub-Phase:** 04.01 — Basic Video Assembly
> **Phase:** Phase 04 — The Vision
> **Complexity:** High
> **Dependencies:** Task 04.01.02 (FFmpeg Check), Task 04.01.03 (Cover Resize), Task 04.01.10 (Output Path)
> **Parent Document:** [SubPhase_04_01_Overview.md](./SubPhase_04_01_Overview.md)

---

## Objective

Replace the Phase 01 stub `core_engine/video_renderer.py` with a fully functional MoviePy-based rendering pipeline that loads each segment's image and audio, creates synchronized static-image clips, concatenates them, and exports to MP4.

---

## Instructions

### Step 1 — Replace the stub file

Open `backend/core_engine/video_renderer.py` and replace the entire stub contents with the full implementation. Add a module-level docstring and logger.

### Step 2 — Handle MoviePy version imports

Use a try/except pattern to support both MoviePy 1.0.3 and 2.0 import paths. Attempt `from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips` first, and fall back to `from moviepy import ...` if the `.editor` submodule is not available.

### Step 3 — Define the render_project function signature

Implement `render_project(project_id: str, on_progress: callable = None) -> dict`. The function receives a project UUID string (not a model instance) for Django ORM thread safety. The optional `on_progress` callback accepts `(current_segment, total_segments, phase_description)`. The function returns a dict with keys `output_path` (str), `duration` (float), and `file_size` (int).

### Step 4 — Implement the rendering pipeline

Within `render_project`, execute the following steps in order:
- A. Check FFmpeg availability via `render_utils.check_ffmpeg()`. Raise `RuntimeError` with the FFmpeg error message if missing.
- B. Load the Project instance from the database using the project_id.
- C. Read resolution settings (`resolution_width`, `resolution_height`) and `framerate` from the project.
- D. Query all segments ordered by `sequence_index`.
- E. Validate that every segment has both `image_file` and `audio_file`. Raise `ValueError` listing incomplete segment IDs if any are missing.
- F. Get the output path via `render_utils.get_output_path(project_id)`.
- G. For each segment in order: load audio as `AudioFileClip`, get duration from the audio clip, resize image via `render_utils.resize_image_to_resolution`, create `ImageClip` with the audio's duration, set audio on the image clip, append to clips list, and call the progress callback.
- H. Concatenate all clips with `concatenate_videoclips(clips, method="compose")`.
- I. Call progress callback with "Exporting final MP4..." message.
- J. Export with `write_videofile` using `libx264` video, `aac` audio, `8000k` bitrate, and `logger=None`.
- K. Capture the total duration before closing the composite clip.
- L. Close all clips (composite, individual image clips, and audio clips) to free memory and file handles.
- M. Get the output file size.
- N. Return the result dict.

### Step 5 — Implement comprehensive error handling

Wrap the entire pipeline in try/except/finally. On any error: log the exception, close any open clips, attempt to delete partial output files, and re-raise so the caller (SubPhase 04.03's task layer) can handle status updates.

### Step 6 — Add logging throughout

Log key milestones: render start, segment count, each segment being processed, concatenation start, export start, export completion with file size and duration, and any errors.

---

## Expected Output

```
backend/
└── core_engine/
    └── video_renderer.py ← REPLACED (stub → full implementation)
```

---

## Validation

- [ ] `render_project()` accepts `project_id` (str) and optional `on_progress` callback.
- [ ] Returns dict with `output_path`, `duration`, `file_size`.
- [ ] Loads segments in `sequence_index` order.
- [ ] Each segment clip's duration matches its audio clip's duration.
- [ ] Concatenation uses `method="compose"`.
- [ ] Export uses `libx264` video, `aac` audio, `8000k` bitrate.
- [ ] `logger=None` suppresses MoviePy console output.
- [ ] `on_progress` is called for each segment and the export phase.
- [ ] Missing image/audio raises `FileNotFoundError` or `ValueError`.
- [ ] All clips and file handles are closed after rendering (in finally block).
- [ ] Partial output files are cleaned up on error.
- [ ] MoviePy 1.0.3 and 2.0 imports both supported.

---

## Notes

- This is the central task of SubPhase 04.01. Tasks 04.01.05 through 04.01.08 provide additional detail on specific aspects of the pipeline (pairing, duration sync, concatenation, export), but the main structure is defined here.
- **No Ken Burns effects** — image clips are static. Each frame displays the same resized image for the entire audio duration. Ken Burns is added in SubPhase 04.02 by modifying the clip creation step.
- **No Project.status updates** — the renderer is a pure function. Status management (DRAFT → PROCESSING → COMPLETED) is handled by SubPhase 04.03's API layer.
- **No Project.output_path updates** — the caller persists the output path.
- Memory management is critical. MoviePy clips hold references to image arrays and file handles. Failing to close them causes memory leaks and file locking issues, especially on Windows.

---

> **Parent:** [SubPhase_04_01_Overview.md](./SubPhase_04_01_Overview.md) (Layer 2)
> **Phase:** [Phase_04_Overview.md](../Phase_04_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_04_01_03_Image_Cover_Resize_Logic.md](./Task_04_01_03_Image_Cover_Resize_Logic.md)
> **Next Task:** [Task_04_01_05_AudioClip_ImageClip_Pairing.md](./Task_04_01_05_AudioClip_ImageClip_Pairing.md)
