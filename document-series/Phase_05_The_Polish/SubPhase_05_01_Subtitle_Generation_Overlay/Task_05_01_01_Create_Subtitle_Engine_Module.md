# Task 05.01.01 — Create Subtitle Engine Module

## Metadata

| Field         | Value                                                                |
| ------------- | -------------------------------------------------------------------- |
| **Task ID**   | 05.01.01                                                             |
| **Task Name** | Create Subtitle Engine Module                                        |
| **Sub-Phase** | 05.01 — Subtitle Generation & Overlay                                |
| **Phase**     | Phase 05 — The Polish                                                |
| **Complexity**| Medium                                                               |
| **Dependencies** | None (first task — creates the file skeleton)                     |
| **Parent**    | [SubPhase_05_01_Overview.md](./SubPhase_05_01_Overview.md)           |

---

## Objective

Create the new subtitle_engine.py module inside backend/core_engine/ with the module-level structure, imports, constants, logging setup, function stubs, and a convenience entry-point function. This task establishes the file skeleton that subsequent tasks (05.01.02–04) will populate with their algorithm implementations.

---

## Instructions

### Step 1 — Create the File with Module Docstring

Create backend/core_engine/subtitle_engine.py with a module-level docstring explaining its purpose: generating timed, styled subtitle overlays for video segments from narration text.

### Step 2 — Add Imports

Import logging, re (for boundary detection in chunking), Optional from typing, and TextClip from moviepy.editor. The re and Optional imports support the subsequent algorithm tasks.

### Step 3 — Set Up Logger

Initialize a module-level logger using logging.getLogger(__name__) for consistent logging across all functions in this module.

### Step 4 — Define Module-Level Constants

Define the following constants that will be referenced by the algorithm functions:

- DEFAULT_MAX_WORDS = 6 — maximum words per subtitle chunk.
- MIN_CHUNK_WORDS = 4 — minimum words before considering a boundary break.
- MIN_DISPLAY_DURATION = 0.5 — minimum seconds a subtitle is displayed.
- FONT_SIZE_DIVISOR = 18 — resolution_height divided by this yields font size (approximately 60px at 1080p).
- TEXT_WIDTH_RATIO = 0.9 — subtitle width as a fraction of frame width (90%).
- SUBTITLE_Y_RATIO = 0.85 — vertical position of subtitles (85% from top, placing them near the bottom).
- DEFAULT_STROKE_COLOR = "#000000" — black stroke for readability.
- DEFAULT_STROKE_WIDTH = 2 — stroke width in pixels.

### Step 5 — Add Function Stubs

Add three function stubs with complete signatures, type hints, and docstrings, each raising NotImplementedError:

1. chunk_text — accepts text (str) and max_words (int, defaulting to DEFAULT_MAX_WORDS), returns list of strings. Splits text into word-chunks. Implementation deferred to Task 05.01.02.

2. calculate_subtitle_timing — accepts chunks (list of str), total_duration (float), and min_duration (float, defaulting to MIN_DISPLAY_DURATION), returns list of (start_time, duration) tuples. Calculates proportional timing. Implementation deferred to Task 05.01.03.

3. generate_subtitle_clips — accepts chunks (list of str), timings (list of tuples), resolution (tuple of two ints), font (str), and color (str), returns list of TextClip objects. Creates styled TextClips. Implementation deferred to Task 05.01.04.

### Step 6 — Add the Convenience Entry-Point Function

Add create_subtitles_for_segment as the main entry point called by video_renderer.py. This function accepts text_content (str), audio_duration (float), resolution (tuple of two ints), font (str), and color (str), and returns a list of TextClip objects. It chains the three steps: chunk_text → calculate_subtitle_timing → generate_subtitle_clips. If text_content is empty or whitespace-only, it returns an empty list immediately.

---

## Expected Output

A new file backend/core_engine/subtitle_engine.py containing imports, constants, a logger, three function stubs (raising NotImplementedError), and the create_subtitles_for_segment convenience function that orchestrates all three.

---

## Validation

- [ ] File backend/core_engine/subtitle_engine.py exists.
- [ ] Module docstring describes the subtitle engine's purpose.
- [ ] All required imports are present (logging, re, Optional, TextClip).
- [ ] Logger is initialized with __name__.
- [ ] All 8 module-level constants are defined with correct values.
- [ ] chunk_text stub has correct signature and raises NotImplementedError.
- [ ] calculate_subtitle_timing stub has correct signature and raises NotImplementedError.
- [ ] generate_subtitle_clips stub has correct signature and raises NotImplementedError.
- [ ] create_subtitles_for_segment returns empty list for empty/whitespace text.
- [ ] create_subtitles_for_segment calls the three functions in sequence for non-empty text.

---

## Notes

- The stubs are temporary placeholders — Tasks 05.01.02, 05.01.03, and 05.01.04 replace them with full implementations.
- The constants are module-level (not inside functions) so they can be easily tuned without searching through algorithm code.
- The re import is needed by Task 05.01.02 for sentence/clause boundary detection in the chunking algorithm.
- The create_subtitles_for_segment function will work as the single entry point from video_renderer.py, simplifying the renderer's integration (it only needs to call one function per segment).

---

> **Parent:** [SubPhase_05_01_Overview.md](./SubPhase_05_01_Overview.md) (Layer 2)
> **Phase:** [Phase_05_Overview.md](../Phase_05_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
