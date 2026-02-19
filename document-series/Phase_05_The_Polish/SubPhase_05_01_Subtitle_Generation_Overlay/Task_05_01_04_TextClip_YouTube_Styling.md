# Task 05.01.04 — TextClip YouTube Styling

## Metadata

| Field         | Value                                                                |
| ------------- | -------------------------------------------------------------------- |
| **Task ID**   | 05.01.04                                                             |
| **Task Name** | TextClip YouTube Styling                                             |
| **Sub-Phase** | 05.01 — Subtitle Generation & Overlay                                |
| **Phase**     | Phase 05 — The Polish                                                |
| **Complexity**| Medium                                                               |
| **Dependencies** | Task 05.01.01 (module skeleton), Task 05.01.08 (font validation) |
| **Parent**    | [SubPhase_05_01_Overview.md](./SubPhase_05_01_Overview.md)           |

---

## Objective

Implement the generate_subtitle_clips function that creates MoviePy TextClip objects styled to match the "YouTube-style" subtitle specification: white text with black stroke, bold font, positioned at bottom-center, with proportional font sizing based on video resolution. Each TextClip is assigned its start time and duration from the timing calculator.

---

## Instructions

### Step 1 — Replace the Stub

In backend/core_engine/subtitle_engine.py, replace the generate_subtitle_clips function stub with the full implementation.

### Step 2 — Handle Empty Input

If the chunks list is empty or the timings list is empty, return an empty list immediately.

### Step 3 — Compute Styling Parameters

Derive the following from the resolution tuple and module constants:

- Font size: resolution height divided by FONT_SIZE_DIVISOR (approximately 60px at 1080p, approximately 40px at 720p).
- Text width: resolution width multiplied by TEXT_WIDTH_RATIO (90% of frame width, preventing text from touching edges).
- Y position: resolution height multiplied by SUBTITLE_Y_RATIO (85% from top, placing subtitles near the bottom of the frame).

### Step 4 — Create TextClip for Each Chunk

Iterate over the paired chunks and timings. For each pair, create a MoviePy TextClip with the following parameters:

- txt: the chunk text string.
- fontsize: the computed font size.
- font: the validated font path (a .ttf file path).
- color: the subtitle color from GlobalSettings (e.g., "#FFFFFF").
- stroke_color: DEFAULT_STROKE_COLOR (black, "#000000") for readability over any background.
- stroke_width: DEFAULT_STROKE_WIDTH (2 pixels).
- method: "caption" — this is critical, as it tells MoviePy/ImageMagick to word-wrap text within the specified width. Using "label" instead would render text on a single line without wrapping.
- size: a tuple of (text_width, None) — fixed width with auto height so wrapped text adjusts automatically.
- align: "center" for horizontal centering.

### Step 5 — Set Position and Timing

For each created TextClip, set its position to ("center", y_position) for bottom-center placement. Set its start time and duration from the corresponding timing tuple.

### Step 6 — Add Logging

Log each TextClip creation at DEBUG level, including a truncated version of the chunk text, the start time, and the duration. Log any errors or exceptions at WARNING level.

### Step 7 — Handle TextClip Errors Gracefully

Wrap the TextClip creation in a try/except block. If TextClip raises an exception (most commonly OSError when ImageMagick is unavailable), log a warning and skip that chunk rather than failing the entire function. Return whatever clips were successfully created.

---

## Expected Output

The generate_subtitle_clips function is fully implemented. Given chunks, timings, resolution, font path, and color, it returns a list of styled TextClip objects ready for compositing onto a video clip.

---

## Validation

- [ ] Empty chunks or timings returns empty list.
- [ ] Font size is resolution_height / 18 (approximately 60px at 1080p).
- [ ] Text color matches the provided color parameter.
- [ ] Stroke color is black ("#000000").
- [ ] Stroke width is 2 pixels.
- [ ] Method is "caption" (not "label").
- [ ] Text width is 90% of frame width.
- [ ] Position is ("center", 85% of frame height).
- [ ] Each TextClip has the correct start time and duration from timings.
- [ ] Errors during TextClip creation are caught and logged, not propagated.

---

## Notes

- The "caption" method is mandatory — "label" would render single-line text that overflows the frame for longer chunks.
- The size parameter (text_width, None) uses None for height, allowing the TextClip to auto-size vertically based on how many lines the text wraps to. At 90% width and approximately 60px font at 1080p, a 6-word chunk typically fits on one line.
- The font parameter must be an absolute or relative path to a .ttf file. MoviePy passes this directly to ImageMagick — font names (like "Arial") are not supported.
- TextClip requires ImageMagick to be installed. If ImageMagick is missing, the caller (video_renderer.py via Task 05.01.05) should skip subtitle generation entirely. The error handling in this function is a secondary safety net.
- Each TextClip is a lightweight overlay that exists only during its assigned time window. Multiple TextClips from the same segment are sequentially timed — they never overlap.

---

> **Parent:** [SubPhase_05_01_Overview.md](./SubPhase_05_01_Overview.md) (Layer 2)
> **Phase:** [Phase_05_Overview.md](../Phase_05_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
