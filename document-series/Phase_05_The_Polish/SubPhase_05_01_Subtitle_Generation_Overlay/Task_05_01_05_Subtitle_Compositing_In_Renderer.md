# Task 05.01.05 — Subtitle Compositing In Renderer

## Metadata

| Field         | Value                                                                |
| ------------- | -------------------------------------------------------------------- |
| **Task ID**   | 05.01.05                                                             |
| **Task Name** | Subtitle Compositing In Renderer                                     |
| **Sub-Phase** | 05.01 — Subtitle Generation & Overlay                                |
| **Phase**     | Phase 05 — The Polish                                                |
| **Complexity**| High                                                                 |
| **Dependencies** | Task 05.01.04 (TextClip generation), Task 05.01.06 (ImageMagick check) |
| **Parent**    | [SubPhase_05_01_Overview.md](./SubPhase_05_01_Overview.md)           |

---

## Objective

Modify the existing video_renderer.py to composite subtitle TextClip overlays onto each segment's Ken Burns clip before concatenation. This is the integration point where the subtitle engine connects to the render pipeline. The modification adds subtitle generation as a new step in the per-segment processing loop, using CompositeVideoClip to layer subtitles on top of the Ken Burns animation, with graceful degradation if ImageMagick is unavailable or subtitle generation fails.

---

## Instructions

### Step 1 — Add New Imports

At the top of backend/core_engine/video_renderer.py, add imports for CompositeVideoClip from moviepy.editor, create_subtitles_for_segment from core_engine.subtitle_engine, and check_imagemagick and get_font_path from core_engine.render_utils.

### Step 2 — Check ImageMagick Availability Once

In the render_project function, before the segment processing loop begins, call check_imagemagick() once and store the result in a boolean variable. If ImageMagick is not available, log a warning and add "Subtitles disabled: ImageMagick not found" to a warnings list. This single check prevents repeated subprocess calls during segment iteration.

### Step 3 — Read Subtitle Settings from GlobalSettings

Before the loop, query GlobalSettings for the subtitle_font and subtitle_color values. Pass the subtitle_font through get_font_path (Task 05.01.08) to resolve it to a validated font path (falling back to the bundled default if needed). Default subtitle_color to "#FFFFFF" (white) if the value is empty or unset.

### Step 4 — Add Subtitle Generation to the Per-Segment Loop

After the existing Ken Burns clip creation step and before audio assignment, add subtitle compositing. The logic should be: if ImageMagick is available AND the segment has non-empty text_content, call create_subtitles_for_segment with the segment's text, audio_duration, resolution, font, and color. If the function returns a non-empty list of TextClip objects, create a CompositeVideoClip with the Ken Burns clip as the base layer and the subtitle clips as overlay layers. If subtitles are not applicable (no ImageMagick, empty text, or empty clip list), use the Ken Burns clip directly.

### Step 5 — Set Duration on Composited Clip

Explicitly set the composited clip's duration to segment.audio_duration. This is necessary because CompositeVideoClip infers duration from the longest clip in the composition, which may differ slightly from the intended duration due to floating-point precision in subtitle timing.

### Step 6 — Handle Subtitle Errors Gracefully

Wrap the create_subtitles_for_segment call in a try/except block catching Exception. If subtitle generation fails for a segment, log a warning including the segment index and the error message, add a descriptive warning to the warnings list, and proceed with the Ken Burns clip alone (no subtitles for that segment). The render must never fail entirely due to a subtitle error.

### Step 7 — Update Progress Reporting

Add a subtitle-phase progress update to the on_progress callback between Ken Burns creation and final clip assembly, reporting "Compositing subtitles for segment N."

### Step 8 — Include Warnings in Render Result

Add the warnings list to the render result dictionary returned by render_project. This allows the task function (api/tasks.py) and status endpoint to relay warning information. The warnings list may contain ImageMagick-missing notices or per-segment subtitle failure notices.

---

## Expected Output

The video_renderer.py render_project function now composites subtitle TextClips onto each segment's Ken Burns clip. When ImageMagick is available and segments have text content, the rendered MP4 contains burned-in subtitles at the bottom of each segment. When ImageMagick is missing or subtitles fail, the video renders normally without subtitles and includes warnings in the result.

---

## Validation

- [ ] CompositeVideoClip import is added to video_renderer.py.
- [ ] ImageMagick availability is checked once before the segment loop.
- [ ] Subtitle settings (font, color) are read from GlobalSettings.
- [ ] Subtitles are composited onto Ken Burns clips when available.
- [ ] Segments with empty text_content render without subtitles (no error).
- [ ] Ken Burns effects continue to work correctly alongside subtitles.
- [ ] Composited clip duration is explicitly set to segment.audio_duration.
- [ ] Audio is set on the composited clip, not on individual subtitle clips.
- [ ] Subtitle generation errors are caught and do not crash the render.
- [ ] Warnings list is included in the render result dictionary.
- [ ] Progress reporting includes subtitle compositing phase.

---

## Notes

- CompositeVideoClip([ken_burns_clip, *subtitle_clips]) layers the TextClips on top of the Ken Burns animation. The order matters — the Ken Burns clip is the background (first), subtitle clips are the foreground (after).
- Subtitle compositing is the most computationally expensive part of Phase 05. Each TextClip is rasterized by ImageMagick, and the compositing happens per-frame during encoding. Expected render time increase is 1.5x–3x compared to rendering without subtitles.
- The warnings list is a new field in the render result. Existing code in api/tasks.py should forward these warnings through the TaskManager to the status endpoint. For Phase 05, warnings are informational only — the frontend does not display them yet (toast notifications come in SubPhase 05.03).
- The single ImageMagick check avoids running subprocess.run for every segment. Since ImageMagick availability does not change during a render, one check is sufficient.

---

> **Parent:** [SubPhase_05_01_Overview.md](./SubPhase_05_01_Overview.md) (Layer 2)
> **Phase:** [Phase_05_Overview.md](../Phase_05_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
