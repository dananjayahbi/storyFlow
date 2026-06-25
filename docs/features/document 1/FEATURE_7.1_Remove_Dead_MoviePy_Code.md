# FEATURE 7.1 — Remove Dead MoviePy Code

---

## 1. Document Overview

### Metadata

| Field               | Value                                                                          |
| ------------------- | ------------------------------------------------------------------------------ |
| Feature ID          | 7.1                                                                            |
| Title               | Remove Dead MoviePy Code                                                       |
| Source               | IDEAS_01_Core_Engine_Enhancements.md                                          |
| Complexity          | Low                                                                            |
| Primary Files       | backend/core_engine/video_renderer.py, backend/core_engine/ken_burns.py, backend/core_engine/subtitle_engine.py |
| Test Files          | backend/core_engine/tests/test_crossfade.py                                    |
| Author              | AI Agent                                                                       |
| Created             | 2026-03-10                                                                     |
| Status              | Planned                                                                        |

---

### Problem Statement

When StoryFlow migrated from MoviePy's per-frame Pillow compositing
pipeline to the fast compositor (direct NumPy alpha blending plus FFmpeg
subprocess piping), several MoviePy-dependent functions were left behind
in the codebase.  These functions are no longer called by any active
code path but remain present, creating multiple problems:

1. **Developer confusion** — New contributors encountering functions like
   `apply_crossfade_transitions()` or `generate_subtitle_clips()` may
   assume they are live code paths and attempt to modify or extend them,
   wasting effort on dead branches.

2. **Import bloat** — MoviePy video-related imports at the top of
   video_renderer.py (VideoClip, ImageClip, CompositeVideoClip, vfx,
   concatenate_videoclips) are loaded on every process startup even
   though they are never used for video compositing.  This adds
   unnecessary memory consumption and slows module initialization.

3. **Test maintenance cost** — The test_crossfade.py test file exercises
   the dead `apply_crossfade_transitions()` and
   `calculate_total_duration_with_transitions()` functions.  These tests
   must be maintained (kept passing for CI) despite testing code that is
   never executed in production.

4. **Codebase size** — The dead functions collectively represent
   approximately 450 lines of unused code across three core engine files.
   Removing them shrinks the codebase and makes it easier to navigate.

The fast compositor in backend/core_engine/fast_compositor.py handles
all video frame generation, subtitle rendering (via Pillow-based
pre_render_subtitles), crossfade blending (via NumPy alpha compositing),
and Ken Burns animation (by directly calling the helper functions from
ken_burns.py such as load_and_prepare_image, calculate_crop_dimensions,
get_pan_direction, get_start_end_coords, and interpolate_position).

MoviePy remains legitimately used for one purpose only: audio loading
and mixing.  The AudioFileClip, concatenate_audioclips, and
CompositeAudioClip imports inside render_project() (approximately lines
933-935 of video_renderer.py) are still actively used and must be
preserved.

---

### Proposed Solution

Systematically remove all dead MoviePy-dependent code across three
files and one test file, while carefully preserving all actively used
functions and imports.  The removal is organized into four targets:

1. **video_renderer.py** — Remove the top-level MoviePy video imports,
   the _MoviePyProgressLogger class (note: this is NOT the actively used
   _ExportProgressLogger), the apply_crossfade_transitions() function,
   and the calculate_total_duration_with_transitions() function.  Keep
   the audio-related imports inside render_project().

2. **ken_burns.py** — Remove the MoviePy VideoClip import at the top
   and the apply_ken_burns() function at the bottom.  Keep all helper
   functions (load_and_prepare_image, calculate_crop_dimensions,
   get_pan_direction, position_to_coords, get_start_end_coords,
   interpolate_position) because the fast compositor calls them directly.

3. **subtitle_engine.py** — Remove the MoviePy TextClip import, the
   generate_subtitle_clips() function, and the
   create_subtitles_for_segment() function.  Keep chunk_text() and
   calculate_subtitle_timing() because the fast compositor's Pillow-based
   subtitle renderer uses them.

4. **test_crossfade.py** — Remove or rewrite the test file.  The tests
   for apply_crossfade_transitions() become meaningless once the function
   is removed.  The tests for calculate_total_duration_with_transitions()
   can also be removed since that function is being deleted.

---

### Scope

| In Scope                                                               | Out of Scope                                                      |
| ---------------------------------------------------------------------- | ----------------------------------------------------------------- |
| Remove apply_crossfade_transitions() from video_renderer.py            | Replacing MoviePy audio with a non-MoviePy alternative            |
| Remove calculate_total_duration_with_transitions() from video_renderer.py | Refactoring the fast compositor                                 |
| Remove _MoviePyProgressLogger class from video_renderer.py            | Adding new transition effects                                     |
| Remove dead MoviePy video imports from video_renderer.py top-level     | Modifying the fast compositor's crossfade implementation          |
| Remove apply_ken_burns() from ken_burns.py                             | Removing the Ken Burns helper functions                           |
| Remove MoviePy VideoClip import from ken_burns.py                      | Removing the DIRECTIONS constant or any helper functions          |
| Remove generate_subtitle_clips() from subtitle_engine.py              | Removing chunk_text() or calculate_subtitle_timing()              |
| Remove create_subtitles_for_segment() from subtitle_engine.py         | Modifying the fast compositor's subtitle rendering                |
| Remove MoviePy TextClip import from subtitle_engine.py                | Upgrading MoviePy version                                         |
| Remove or update test_crossfade.py                                     | Adding new tests for the fast compositor                          |
| Update module docstrings to reflect the removal                        | Restructuring the core_engine package                             |

---

### Key Files

| File Path                                                  | Role in Feature                                      | Lines of Interest             |
| ---------------------------------------------------------- | ---------------------------------------------------- | ----------------------------- |
| backend/core_engine/video_renderer.py (1218 lines)         | Remove dead functions, imports, and class             | L38-57 (imports), L357-370 (dead class — see note), L445-575 (dead functions) |
| backend/core_engine/ken_burns.py (694 lines)               | Remove apply_ken_burns() and MoviePy import           | L38-41 (import), L487-694 (function) |
| backend/core_engine/subtitle_engine.py (450 lines)         | Remove MoviePy functions and import                   | L27 (import), L220-450 (functions) |
| backend/core_engine/tests/test_crossfade.py (197 lines)    | Remove or rewrite tests for deleted functions         | L11-14 (imports), L1-197 (all)  |
| backend/core_engine/fast_compositor.py                      | Reference — confirm it does NOT call dead functions  | Fast compositor imports         |

---

### Dead Code Inventory — Detailed Breakdown

The following is the precise inventory of every dead code element to be
removed, organized by file.  Each entry includes the exact line range,
the function or import name, and the reason it is dead.

#### video_renderer.py

| Element                                      | Lines       | Type      | Why Dead                                                   |
| -------------------------------------------- | ----------- | --------- | ---------------------------------------------------------- |
| Top-level MoviePy video imports              | L38-57      | Import    | Only AudioFileClip is used (and it is re-imported inside render_project at L933) |
| `from core_engine.ken_burns import apply_ken_burns` | L32     | Import    | apply_ken_burns() is never called; fast compositor calls helpers directly |
| _ExportProgressLogger class                  | L357-440    | Class     | NOTE: This class IS ACTIVELY USED — DO NOT REMOVE. It is the proglog logger for FFmpeg export progress. |
| apply_crossfade_transitions()                | L445-510    | Function  | MoviePy crossfade replaced by NumPy alpha blending in fast compositor |
| calculate_total_duration_with_transitions()  | L520-575    | Function  | Duration calculation for MoviePy concatenation; fast compositor handles its own timing |

**CRITICAL DISTINCTION**: There are TWO progress logger classes in
video_renderer.py, and they are easy to confuse:

- `_ExportProgressLogger` (approximately L357-440) — This IS actively used
  by the render pipeline for tracking FFmpeg export progress.  DO NOT
  REMOVE IT.

- There is NO separate `_MoviePyProgressLogger` class in the current
  codebase.  The IDEAS document may have been referring to
  `_ExportProgressLogger` by a different name, or to an earlier version
  of the code.  The `_ExportProgressLogger` IS used and MUST be kept.

After careful review of the actual file content, the only dead code
items in video_renderer.py that should be removed are:

1. The top-level MoviePy video import block (L38-57) — which imports
   AudioFileClip, concatenate_videoclips, vfx, and _AudioClipBase.
   However, `_AudioClipBase` is used by `_make_silent_audio()` at
   line 345.  And `vfx` is used by `apply_crossfade_transitions()`.
   Once `apply_crossfade_transitions()` is removed, `vfx` and
   `concatenate_videoclips` become dead imports.  But `AudioFileClip`
   and `_AudioClipBase` are still needed.

   Therefore: the import block must be MODIFIED, not fully removed.
   Keep `AudioFileClip` and `_AudioClipBase`.  Remove
   `concatenate_videoclips` and `vfx`.

2. The `from core_engine.ken_burns import apply_ken_burns` at line 32.

3. The `apply_crossfade_transitions()` function (L445-510).

4. The `calculate_total_duration_with_transitions()` function (L520-575).

#### ken_burns.py

| Element                                      | Lines       | Type      | Why Dead                                                   |
| -------------------------------------------- | ----------- | --------- | ---------------------------------------------------------- |
| MoviePy VideoClip import                     | L38-41      | Import    | Only used by apply_ken_burns() which is itself dead         |
| apply_ken_burns()                            | L487-694    | Function  | Fast compositor calls helper functions directly              |

Everything else in ken_burns.py is actively used:
- DIRECTIONS constant (L56-66) — used by get_pan_direction()
- load_and_prepare_image() (L72-190) — called by fast compositor
- calculate_crop_dimensions() (L193-262) — called by fast compositor
- get_pan_direction() (L265-310) — called by fast compositor
- position_to_coords() (L313-395) — called by get_start_end_coords()
- get_start_end_coords() (L398-440) — called by fast compositor
- interpolate_position() (L443-485) — called by fast compositor

#### subtitle_engine.py

| Element                                      | Lines       | Type      | Why Dead                                                    |
| -------------------------------------------- | ----------- | --------- | ----------------------------------------------------------- |
| `from moviepy import TextClip`               | L27         | Import    | Only used by generate_subtitle_clips() which is dead         |
| generate_subtitle_clips()                    | L220-375    | Function  | Fast compositor uses Pillow-based pre_render_subtitles       |
| create_subtitles_for_segment()               | L378-450    | Function  | Wrapper that calls generate_subtitle_clips(); also dead      |

Functions that MUST be kept:
- _is_boundary_word() (L63-76) — used by chunk_text()
- chunk_text() (L79-145) — used by fast compositor's subtitle pipeline
- calculate_subtitle_timing() (L148-217) — used by fast compositor
- All module-level constants (DEFAULT_MAX_WORDS, MIN_CHUNK_WORDS, etc.)

#### test_crossfade.py

| Element                                      | Lines       | Type      | Why Dead                                                    |
| -------------------------------------------- | ----------- | --------- | ----------------------------------------------------------- |
| Import of apply_crossfade_transitions        | L11-14      | Import    | Function being deleted                                       |
| Import of calculate_total_duration_with_transitions | L11-14 | Import  | Function being deleted                                       |
| Import of vfx                                | L14         | Import    | Used only in tests for deleted function                      |
| CrossfadeTransitionTests class               | L39-197     | TestCase  | All tests reference deleted functions                        |
| create_mock_clip() helper                    | L17-36      | Function  | Only used by tests for deleted function                      |

The entire test_crossfade.py file can be deleted since every test in it
references functions that will no longer exist.

---

## 2. Flow Diagram

### 2.1 Current Code Paths — Active vs Dead

This diagram shows which code paths are actively used (solid lines)
versus dead (dashed lines) in the current codebase.

```
  ┌─────────────────────────────────────────────────────────────────┐
  │                    render_project()                              │
  │                    video_renderer.py L580                        │
  └─────────────────┬─────────────────────┬─────────────────────────┘
                    │                     │
         ACTIVE     │                     │   DEAD
         (used)     │                     │   (never called)
                    │                     │
                    ▼                     ▼
  ┌─────────────────────┐   ┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐
  │ fast_render_segments │     apply_crossfade_transitions
  │ fast_compositor.py   │   │ video_renderer.py L445      │
  └─────────┬───────────┘     (MoviePy vfx.CrossFadeIn/
            │                │  CrossFadeOut)               │
            │                └ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘
            │
            │                ┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐
            │                  calculate_total_duration_
            │                │   with_transitions           │
            │                  video_renderer.py L520
            │                │ (MoviePy duration math)      │
            │                └ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘
            │
            ├────────────────────────────────────────┐
            │                                        │
            ▼                                        ▼
  ┌─────────────────────┐              ┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐
  │ Ken Burns HELPERS    │                apply_ken_burns()
  │ (load_and_prepare,   │              │ ken_burns.py L487       │
  │  calculate_crop,     │                (MoviePy VideoClip
  │  get_pan_direction,  │              │  make_frame closure)    │
  │  get_start_end,      │              └ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘
  │  interpolate_pos)    │
  │ ken_burns.py L72-485 │
  └──────────────────────┘
            │
            ├────────────────────────────────────────┐
            │                                        │
            ▼                                        ▼
  ┌─────────────────────┐              ┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐
  │ pre_render_subtitles │                generate_subtitle_clips
  │ (Pillow-based,       │              │ subtitle_engine.py L220 │
  │  fast_compositor.py) │                (MoviePy TextClip)
  │                      │              │                         │
  │ Uses:                │              └ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘
  │  - chunk_text()      │
  │  - calculate_subtitle│              ┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐
  │    _timing()         │                create_subtitles_for_
  └──────────────────────┘              │   segment()             │
                                          subtitle_engine.py L378
                                        │ (wrapper for above)     │
                                        └ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘
```

Legend:
- Solid boxes represent actively used code
- Dashed boxes represent dead code to be removed

### 2.2 Import Dependency Before and After

This diagram shows the import graph for the three affected files,
highlighting which imports become unnecessary after removal.

```
  BEFORE REMOVAL:
  ════════════════

  video_renderer.py
  ┌─────────────────────────────────────────────┐
  │  L32: from core_engine.ken_burns            │
  │          import apply_ken_burns  ──────────── DEAD (remove)
  │  L33: from core_engine.fast_compositor      │
  │          import fast_render_segments ──────── ACTIVE (keep)
  │                                              │
  │  L41-56: from moviepy import                 │
  │     AudioFileClip ──────────────────────────── ACTIVE (keep)
  │     concatenate_videoclips ─────────────────── DEAD (remove)
  │     vfx ────────────────────────────────────── DEAD (remove)
  │     _AudioClipBase ─────────────────────────── ACTIVE (keep)
  │                                              │
  │  L933: from moviepy import                   │
  │     concatenate_audioclips ─────────────────── ACTIVE (keep)
  │     CompositeAudioClip ────────────────────── ACTIVE (keep)
  └─────────────────────────────────────────────┘

  ken_burns.py
  ┌─────────────────────────────────────────────┐
  │  L38-41: from moviepy import VideoClip ───── DEAD (remove)
  │  L28: import cv2 ──────────────────────────── ACTIVE (keep)
  │  L29: import numpy as np ──────────────────── ACTIVE (keep)
  └─────────────────────────────────────────────┘

  subtitle_engine.py
  ┌─────────────────────────────────────────────┐
  │  L27: from moviepy import TextClip ────────── DEAD (remove)
  │  L23: import logging ──────────────────────── ACTIVE (keep)
  │  L24: import re ───────────────────────────── ACTIVE (keep)
  └─────────────────────────────────────────────┘


  AFTER REMOVAL:
  ═══════════════

  video_renderer.py
  ┌─────────────────────────────────────────────┐
  │  (L32 removed — no ken_burns import)         │
  │  L33: from core_engine.fast_compositor      │
  │          import fast_render_segments          │
  │                                              │
  │  L41-xx: from moviepy import                 │
  │     AudioFileClip                             │
  │     _AudioClipBase                            │
  │                                              │
  │  L933: from moviepy import                   │
  │     concatenate_audioclips                    │
  │     CompositeAudioClip                        │
  └─────────────────────────────────────────────┘

  ken_burns.py
  ┌─────────────────────────────────────────────┐
  │  (MoviePy import removed entirely)           │
  │  import cv2                                   │
  │  import numpy as np                           │
  └─────────────────────────────────────────────┘

  subtitle_engine.py
  ┌─────────────────────────────────────────────┐
  │  (MoviePy import removed entirely)           │
  │  import logging                               │
  │  import re                                    │
  └─────────────────────────────────────────────┘
```

### 2.3 Lines of Code Impact

```
  FILE                          BEFORE     REMOVED    AFTER     DELTA
  ─────────────────────────────────────────────────────────────────────
  video_renderer.py              1218       ~145       ~1073     -12%
    - apply_ken_burns import       1 line
    - concatenate_videoclips       1 line
      + vfx import lines           ~5 lines
    - apply_crossfade_transitions  ~66 lines
    - calculate_total_duration     ~56 lines
    - Comment "Uses direct NumPy"  1 line  (contextual, may keep)

  ken_burns.py                    694       ~215       ~479      -31%
    - VideoClip import             ~4 lines
    - apply_ken_burns()            ~208 lines

  subtitle_engine.py              450       ~235       ~215      -52%
    - TextClip import              1 line
    - generate_subtitle_clips()    ~156 lines
    - create_subtitles_for_segment() ~73 lines

  test_crossfade.py               197       197        0 (del)  -100%
    - Entire file deleted

  ─────────────────────────────────────────────────────────────────────
  TOTAL                          2559       ~792       ~1767     -31%
```

### 2.4 Deletion Order Flow

The deletions must follow a specific order to avoid breaking imports
at any intermediate step.

```
  Step 1                Step 2                Step 3              Step 4
  ───────               ──────                ──────              ──────
  Delete test file   →  Remove functions   →  Remove functions  → Clean imports
  test_crossfade.py     from video_renderer   from subtitle_      from all
                        .py (crossfade +      engine.py +         three files
                        duration functions)   ken_burns.py

  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
  │ Remove        │    │ Remove        │    │ Remove        │    │ Remove        │
  │ test file     │    │ apply_cross-  │    │ generate_     │    │ dead imports  │
  │ (no deps      │──►│ fade_trans()  │──►│ subtitle_     │──►│ (vfx,         │
  │  on it)       │    │ calc_total_   │    │ clips()       │    │ VideoClip,    │
  │               │    │ duration()    │    │ create_sub_   │    │ TextClip,     │
  │               │    │               │    │ for_segment() │    │ concat_video, │
  │               │    │               │    │ apply_ken_    │    │ ken_burns     │
  │               │    │               │    │ burns()       │    │ import)       │
  └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
```

---

## 3. Step-by-Step Instructions

### Phase A — Preparation and Verification

#### Step 1: Confirm the fast compositor does NOT import dead functions

Before removing anything, verify that the fast compositor
(backend/core_engine/fast_compositor.py) does not import or reference
any of the functions to be deleted.

Search fast_compositor.py for the following strings:
- `apply_crossfade_transitions`
- `calculate_total_duration_with_transitions`
- `apply_ken_burns`
- `generate_subtitle_clips`
- `create_subtitles_for_segment`
- `_MoviePyProgressLogger`

None of these should appear in fast_compositor.py.  If any do, the
removal plan must be revised.

#### Step 2: Confirm what fast_compositor.py DOES import from ken_burns.py

Search fast_compositor.py for imports from ken_burns.  Verify it imports
the helper functions directly:
- `load_and_prepare_image`
- `calculate_crop_dimensions`
- `get_pan_direction`
- `get_start_end_coords`
- `interpolate_position`

These functions must NOT be removed.

#### Step 3: Confirm what fast_compositor.py DOES import from subtitle_engine.py

Search fast_compositor.py for imports from subtitle_engine.  Verify it
imports:
- `chunk_text`
- `calculate_subtitle_timing`

These functions must NOT be removed.

#### Step 4: Run the existing test suite

Run the full Django test suite to establish a green baseline.  Record
the number of passing tests and any existing failures.  The command is
`python manage.py test` from the backend directory.

This establishes a baseline so you can verify after removal that the
only test changes are the expected removals from test_crossfade.py.

---

### Phase B — Remove the Test File

#### Step 5: Delete test_crossfade.py

Delete the file backend/core_engine/tests/test_crossfade.py entirely.
This file contains 197 lines across the following elements:

- Imports at lines 1-14 that reference `apply_crossfade_transitions`,
  `calculate_total_duration_with_transitions`, `vfx`, and
  `TRANSITION_DURATION` from video_renderer.

- The `create_mock_clip()` helper function at lines 17-36.

- The `CrossfadeTransitionTests` class at lines 39-197, containing
  tests for both `apply_crossfade_transitions()` and
  `calculate_total_duration_with_transitions()`.

All of these tests exercise functions that will be deleted in the next
phase.  Deleting the test file first prevents import errors during the
intermediate steps.

#### Step 6: Verify the test suite runs without the deleted file

Run the test suite again.  The number of passing tests should decrease
by exactly the number of tests that were in test_crossfade.py (which is
approximately 15 tests based on the test methods visible in the file).
No other tests should break.

---

### Phase C — Remove Dead Functions from video_renderer.py

#### Step 7: Remove apply_crossfade_transitions()

Open backend/core_engine/video_renderer.py.  Locate the function
`apply_crossfade_transitions` which starts at approximately line 445
with the comment header "# Crossfade utility" and continues to
approximately line 510.

Remove the entire function, including:
- The section comment header above it ("# Crossfade utility")
- The function definition, docstring, guard clause, logging statements,
  the iteration loop, and the return statement
- All blank lines that are part of the function block

This function uses MoviePy's `vfx.CrossFadeIn` and `vfx.CrossFadeOut`
to apply crossfade effects to a list of VideoClip objects.  The fast
compositor handles crossfade blending directly through NumPy alpha
channel compositing, making this function unnecessary.

#### Step 8: Remove calculate_total_duration_with_transitions()

Immediately below the removed function, locate the
`calculate_total_duration_with_transitions` function, which starts at
approximately line 520 (after removal of the previous function, the
actual line number will have shifted) with the comment header
"# Duration calculation utility".

Remove the entire function, including:
- The section comment header
- The function definition, docstring, edge case handling, the warnings
  accumulator for short clips, the mathematical calculation, and the
  return statement

This function calculated the total video duration accounting for
MoviePy crossfade overlaps.  The fast compositor computes its own
timeline independently, so this calculation is no longer needed anywhere
in the codebase.

#### Step 9: Verify no remaining references in video_renderer.py

After removing both functions, search the remainder of video_renderer.py
for any references to:
- `apply_crossfade_transitions`
- `calculate_total_duration_with_transitions`

There should be zero references.  If any remain (such as in comments),
either remove the comments or update them to reflect the current state.

The comment at approximately line 787 that says "Uses direct NumPy
compositing + FFmpeg pipe instead of MoviePy's per-frame Pillow pipeline"
is a useful historical note that can be kept or shortened.  It does
not reference the deleted functions by name.

---

### Phase D — Remove Dead Function from ken_burns.py

#### Step 10: Remove apply_ken_burns()

Open backend/core_engine/ken_burns.py.  Locate the function
`apply_ken_burns` which starts at approximately line 487 with the
section comment "# Main public interface" and the function signature.

Remove the entire function from the section comment through line 694
(the end of the file).  This includes:

- The section comment ("# Main public interface")
- The function definition starting with `def apply_ken_burns(`
- The full docstring explaining the algorithm overview
- All eight implementation steps inside the function:
  - Step 1: Load and prepare the source image
  - Step 2: Calculate crop dimensions
  - Step 3: Select pan direction
  - Step 4: Compute start and end pixel coordinates
  - Step 5: Define the make_frame closure (the entire inner function)
  - Step 6: Construct and return the VideoClip
- The VideoClip construction at the end
- The performance-expectations comment block
- All logging statements within the function

This is approximately 208 lines of code.

DO NOT remove the code above line 487.  Everything from line 1 through
approximately line 485 (including the interpolate_position function
that ends just before the "Main public interface" section) must remain.

#### Step 11: Update the ken_burns.py module docstring

The module docstring at the top of ken_burns.py (lines 1-23) currently
describes the module as providing "MoviePy VideoClip objects with
per-frame camera motion."  This description is no longer accurate after
the removal of apply_ken_burns().

Update the docstring to describe the module's current purpose: providing
helper functions for computing Ken Burns zoom-and-pan parameters (image
preparation, crop dimensions, pan direction, start/end coordinates, and
position interpolation) that the fast compositor calls directly.

Specifically, change the line that says "The primary public interface is
:func:`apply_ken_burns`" to reference the individual helper functions
instead.

Remove or update the sentence about "converts static cover images into
MoviePy VideoClip objects" since the module no longer creates VideoClip
objects.

Keep the "Design principles" section intact, but update the
"MoviePy version-safe" bullet point (since MoviePy is no longer
imported at all) — either remove it or replace it with a note about the
module being framework-agnostic (pure NumPy/OpenCV).

---

### Phase E — Remove Dead Functions from subtitle_engine.py

#### Step 12: Remove generate_subtitle_clips()

Open backend/core_engine/subtitle_engine.py.  Locate the function
`generate_subtitle_clips` which starts at approximately line 220.

Remove the entire function, including:
- The function definition and its type annotations
- The full docstring with parameter descriptions
- All implementation code: the empty guard clause, styling parameter
  computation, the TextClip creation loop (including the try/except
  blocks), the position calculation logic (bottom/center/top and
  y_position override), the safety clamp, the MoviePy immutable API
  calls (with_position, with_start, with_duration), and all logging
- The return statement

This function creates MoviePy TextClip objects for subtitle overlays.
The fast compositor renders subtitles using Pillow's ImageDraw instead,
calling chunk_text() and calculate_subtitle_timing() directly but
never touching TextClip or generate_subtitle_clips().

#### Step 13: Remove create_subtitles_for_segment()

Locate the function `create_subtitles_for_segment` which starts at
approximately line 378 (before deletion of the above function shifts
this position).

Remove the entire function, including:
- The section comment ("# Convenience Entry-Point")
- The function definition and type annotations
- The full docstring
- All implementation code: the empty text guard, the three pipeline
  steps (chunk_text, calculate_subtitle_timing, generate_subtitle_clips),
  and the logging statement
- The return statement

This function is a convenience wrapper that orchestrates the MoviePy
subtitle pipeline.  Since generate_subtitle_clips() is also being
deleted, this wrapper has no remaining purpose.

#### Step 14: Update the subtitle_engine.py module docstring

The module docstring at the top of subtitle_engine.py (lines 1-19)
currently describes the module as producing "MoviePy TextClip objects."
Update it to describe the module's remaining purpose: providing text
chunking and timing utilities for subtitle generation.

Specifically:
- Remove references to TextClip objects
- Remove the mention of `generate_subtitle_clips` from the pipeline
  description
- Remove the mention of `create_subtitles_for_segment` as the public
  entry-point
- State that the module provides `chunk_text()` and
  `calculate_subtitle_timing()` which are consumed by the fast
  compositor's Pillow-based subtitle renderer
- Keep the task references (Task 05.01.02, 05.01.03) as historical
  context, but remove the reference to Task 05.01.04 (which was
  generate_subtitle_clips)

---

### Phase F — Clean Up Imports

#### Step 15: Remove the dead import of apply_ken_burns in video_renderer.py

Open backend/core_engine/video_renderer.py.  Locate line 32:

    from core_engine.ken_burns import apply_ken_burns

Delete this entire import line.  The fast compositor imports the Ken
Burns helpers it needs directly; the renderer no longer needs any
import from ken_burns.

#### Step 16: Clean up the MoviePy import block in video_renderer.py

Locate the MoviePy version-safe import block at lines 38-57.  This
block currently imports:

- AudioFileClip — KEEP (used by render_project for loading audio)
- concatenate_videoclips — REMOVE (only used by deleted crossfade code)
- vfx — REMOVE (only used by deleted apply_crossfade_transitions)
- _AudioClipBase — KEEP (used by _make_silent_audio at line 345)

Modify the import block to remove `concatenate_videoclips` and `vfx`
from both the try branch (MoviePy 1.x) and the except branch
(MoviePy 2.x).

After this change, the import block should import only `AudioFileClip`
and `_AudioClipBase`.

Also update the section comment above the import block.  Currently it
says "MoviePy version-safe imports."  Consider adding a clarifying note
that these imports are for audio handling only, to prevent future
developers from re-adding video imports.

#### Step 17: Remove the MoviePy VideoClip import from ken_burns.py

Open backend/core_engine/ken_burns.py.  Locate the import block at
lines 33-41:

The entire MoviePy version-safe import block (the try/except that
imports VideoClip) should be removed.  This includes:
- The section comment ("# MoviePy version-safe imports")
- The try block importing from moviepy.editor
- The except block importing from moviepy
- Any blank lines that are part of this import block

After removal, the only imports in ken_burns.py should be:
- logging
- typing (Tuple)
- cv2
- numpy as np

#### Step 18: Remove the MoviePy TextClip import from subtitle_engine.py

Open backend/core_engine/subtitle_engine.py.  Locate line 27:

    from moviepy import TextClip

Delete this entire import line.

After removal, the only imports in subtitle_engine.py should be:
- __future__ annotations
- logging
- re
- typing (Optional)

Note: Check if the `Optional` import from typing is still needed after
the function removals.  The remaining functions (chunk_text and
calculate_subtitle_timing) may not use Optional.  If it is no longer
referenced, remove it as well to keep imports clean.

---

### Phase G — Update Docstrings and Comments

#### Step 19: Update the video_renderer.py module docstring

The module docstring at lines 1-18 of video_renderer.py describes the
module as using a "fast compositor" and notes that "MoviePy is still
used for audio loading and concatenation."

Update this docstring to:
- Remove any mention of MoviePy being used for video compositing
  (it already says it is not, but double-check wording)
- Confirm the statement about MoviePy being used for audio is still
  accurate
- Remove the reference to CompositeVideoClip.write_videofile() as
  the comparison baseline (since users will no longer see the MoviePy
  alternative in the code)
- Keep the reference to the fast_compositor module

#### Step 20: Add removal notes as brief comments

At the location where apply_crossfade_transitions() was removed in
video_renderer.py, consider adding a one-line comment noting that the
MoviePy crossfade functions were removed in Feature 7.1, and that
crossfade is now handled by the fast compositor.  This helps future
developers understand why there is no crossfade function in this file.

Similarly, at the end of ken_burns.py (where apply_ken_burns was
removed), consider adding a brief comment noting the removal.

These comments are optional — if the team prefers no comments about
deleted code, skip this step.

---

### Phase H — Verification and Testing

#### Step 21: Search the entire codebase for references to deleted functions

Run a workspace-wide search for each of the following strings to ensure
no remaining code references them:

- `apply_crossfade_transitions`
- `calculate_total_duration_with_transitions`
- `apply_ken_burns`
- `generate_subtitle_clips`
- `create_subtitles_for_segment`
- `_MoviePyProgressLogger` (should not exist if it was a misnomer)

If any matches are found in documentation files (*.md), update those
references.  The document-series/ directory contains several task
documents that reference these functions — these are historical
documentation and do not need to be updated, but if desired, a note
can be added that the functions were removed in Feature 7.1.

#### Step 22: Run the full test suite

Run `python manage.py test` from the backend directory.  Verify:

- All tests pass except for the expected reduction from deleting
  test_crossfade.py.
- No import errors occur.
- No new failures are introduced.

#### Step 23: Run a manual render test

If a development environment is available, trigger a render of an
existing test project to verify that the removal did not break the
active render pipeline.  The render should complete successfully
using the fast compositor path.

#### Step 24: Verify MoviePy audio still works

Confirm that the audio mixing section of render_project() (starting
at approximately line 933 with the import of concatenate_audioclips
and CompositeAudioClip) still functions correctly.  The lazy imports
inside render_project() are independent of the top-level imports and
should be unaffected.

#### Step 25: Check for import-time side effects

Start the Django development server (`python manage.py runserver`) and
verify it boots without errors.  Then make a GET request to any API
endpoint (e.g., the project list) to verify the application is
functional.

---

## 4. Expected Outcome

### After Implementation

When this feature is fully implemented, the following changes will be
observable in the StoryFlow backend codebase:

#### Code Reduction

1. video_renderer.py will shrink by approximately 145 lines (from 1218
   to approximately 1073 lines).  The removed code includes the
   crossfade function, the duration calculation function, and the
   cleaned-up imports.

2. ken_burns.py will shrink by approximately 215 lines (from 694 to
   approximately 479 lines).  The removed code is the apply_ken_burns()
   function and the MoviePy import block.

3. subtitle_engine.py will shrink by approximately 235 lines (from 450
   to approximately 215 lines).  The removed code includes
   generate_subtitle_clips(), create_subtitles_for_segment(), and the
   TextClip import.

4. test_crossfade.py will be entirely deleted (197 lines removed).

5. Total reduction: approximately 792 lines of dead code removed.

#### Import Cleanup

1. video_renderer.py will no longer import `concatenate_videoclips`,
   `vfx`, or `apply_ken_burns`.  The remaining top-level MoviePy
   imports will be limited to `AudioFileClip` and `_AudioClipBase`.

2. ken_burns.py will have zero MoviePy imports.  Its only external
   dependencies will be cv2 and numpy.

3. subtitle_engine.py will have zero MoviePy imports.  Its only
   external dependencies will be the Python standard library (logging,
   re, typing).

#### Functional Behavior

1. The render pipeline will continue to function identically.  All
   rendering uses the fast compositor path, which does not depend on
   any of the removed code.

2. Audio mixing will continue to use MoviePy (AudioFileClip,
   concatenate_audioclips, CompositeAudioClip) via lazy imports inside
   render_project().

3. Ken Burns animation will continue to work through the fast
   compositor calling the preserved helper functions directly.

4. Subtitle rendering will continue to work through the fast
   compositor's Pillow-based pipeline using chunk_text() and
   calculate_subtitle_timing().

#### Developer Experience

1. New developers reading the codebase will see only the active code
   paths, reducing confusion about which rendering approach is current.

2. The ken_burns.py module docstring will accurately describe the
   module as providing helper functions for Ken Burns parameter
   computation, rather than misleadingly claiming to create MoviePy
   VideoClip objects.

3. The subtitle_engine.py module docstring will accurately describe
   the module as providing text chunking and timing utilities.

4. The test suite will be smaller and cleaner, with no tests for
   deleted functions.

#### What Does NOT Change

1. The fast compositor (fast_compositor.py) is completely untouched.
2. The render pipeline logic in render_project() is untouched beyond
   import cleanup and the removal of the dead ken_burns import.
3. All API endpoints continue to function identically.
4. The database schema is not affected.
5. The frontend is not affected.
6. Audio handling is completely unchanged.
7. The TRANSITION_DURATION and INTER_SEGMENT_SILENCE constants remain.
8. The _ExportProgressLogger class remains (it is actively used).
9. The _make_silent_audio() utility function remains (it uses
   _AudioClipBase which is kept).

---

## 5. Verification Checklist

### Pre-Removal Verification

- [ ] Confirmed fast_compositor.py does NOT import apply_crossfade_transitions.
- [ ] Confirmed fast_compositor.py does NOT import calculate_total_duration_with_transitions.
- [ ] Confirmed fast_compositor.py does NOT import apply_ken_burns.
- [ ] Confirmed fast_compositor.py does NOT import generate_subtitle_clips.
- [ ] Confirmed fast_compositor.py does NOT import create_subtitles_for_segment.
- [ ] Confirmed fast_compositor.py DOES import Ken Burns helper functions.
- [ ] Confirmed fast_compositor.py DOES import chunk_text and calculate_subtitle_timing.
- [ ] Baseline test suite run completed and results recorded.

### Test File Deletion

- [ ] backend/core_engine/tests/test_crossfade.py has been deleted.
- [ ] No other test file references test_crossfade.py.
- [ ] Test suite runs without import errors after deletion.

### video_renderer.py Changes

- [ ] apply_crossfade_transitions() function has been removed.
- [ ] calculate_total_duration_with_transitions() function has been removed.
- [ ] `from core_engine.ken_burns import apply_ken_burns` has been removed from line 32.
- [ ] `concatenate_videoclips` has been removed from the top-level MoviePy import block.
- [ ] `vfx` has been removed from the top-level MoviePy import block.
- [ ] `AudioFileClip` is STILL present in the top-level import block.
- [ ] `_AudioClipBase` is STILL present in the top-level import block.
- [ ] The _ExportProgressLogger class (L357-440) is STILL present and untouched.
- [ ] The _make_silent_audio() function is STILL present and works correctly.
- [ ] TRANSITION_DURATION constant is STILL present.
- [ ] INTER_SEGMENT_SILENCE constant is STILL present.
- [ ] The lazy audio imports inside render_project() at L933 are STILL present.
- [ ] No references to deleted function names remain in the file.
- [ ] The module docstring has been updated.

### ken_burns.py Changes

- [ ] apply_ken_burns() function has been removed (L487-694 deleted).
- [ ] MoviePy VideoClip import block has been removed (L38-41).
- [ ] load_and_prepare_image() is STILL present and functional.
- [ ] calculate_crop_dimensions() is STILL present and functional.
- [ ] get_pan_direction() is STILL present and functional.
- [ ] position_to_coords() is STILL present and functional.
- [ ] get_start_end_coords() is STILL present and functional.
- [ ] interpolate_position() is STILL present and functional.
- [ ] DIRECTIONS constant is STILL present.
- [ ] The module docstring has been updated to reflect current purpose.
- [ ] No references to apply_ken_burns remain in the file.
- [ ] The module still imports cv2 and numpy correctly.

### subtitle_engine.py Changes

- [ ] generate_subtitle_clips() function has been removed (L220-375).
- [ ] create_subtitles_for_segment() function has been removed (L378-450).
- [ ] `from moviepy import TextClip` has been removed from line 27.
- [ ] chunk_text() is STILL present and functional.
- [ ] calculate_subtitle_timing() is STILL present and functional.
- [ ] _is_boundary_word() is STILL present and functional.
- [ ] All module-level constants (DEFAULT_MAX_WORDS, MIN_CHUNK_WORDS,
      MIN_DISPLAY_DURATION, etc.) are STILL present.
- [ ] FONT_SIZE_DIVISOR, TEXT_WIDTH_RATIO, SUBTITLE_VERT_MARGIN_RATIO,
      DEFAULT_STROKE_COLOR, DEFAULT_STROKE_WIDTH constants are still present
      (they may be unused after removal — verify and optionally remove
      if truly unused by fast compositor).
- [ ] The module docstring has been updated.
- [ ] No references to deleted function names remain in the file.

### Post-Removal Verification

- [ ] Full test suite passes (minus the expected reduction from deleted tests).
- [ ] Django server starts without import errors.
- [ ] A test render completes successfully using the fast compositor.
- [ ] Audio mixing (MoviePy concatenate_audioclips, CompositeAudioClip)
      still functions correctly.
- [ ] Codebase-wide search finds zero references to deleted function names
      in Python files (documentation references are acceptable).
- [ ] No new linting errors or warnings introduced.

### Subtitle Engine Constants Cleanup (Optional)

- [ ] Check if FONT_SIZE_DIVISOR is used by any remaining code.
- [ ] Check if TEXT_WIDTH_RATIO is used by any remaining code.
- [ ] Check if SUBTITLE_VERT_MARGIN_RATIO is used by any remaining code.
- [ ] Check if DEFAULT_STROKE_COLOR is used by any remaining code.
- [ ] Check if DEFAULT_STROKE_WIDTH is used by any remaining code.
- [ ] If any constants are only used by the deleted functions, decide
      whether to remove them now or leave them for potential future use.

---

## 6. Notes for AI Agent

### Precise File Locations

#### backend/core_engine/video_renderer.py (1218 lines)

**Import to remove — line 32:**
The line reads `from core_engine.ken_burns import apply_ken_burns`.
This is the only import from ken_burns in this file.  The fast
compositor import is on the next line (line 33) and must be kept.

**MoviePy import block — lines 38-57:**
The try/except block imports from moviepy.editor (1.x) or moviepy (2.x).
Current imports in the try block (approximately L42-46):
- AudioFileClip — KEEP
- concatenate_videoclips — REMOVE
- vfx — REMOVE
Current imports in the except block (approximately L49-53):
- AudioFileClip — KEEP
- concatenate_videoclips — REMOVE
- vfx — REMOVE
The _AudioClipBase import (approximately L47 and L54) is separate and
must be kept.

**_ExportProgressLogger — lines 357-440:**
DO NOT TOUCH THIS CLASS.  It is the actively used progress logger for
the render pipeline's FFmpeg export phase.  Despite its name containing
"Export" and being in the same area as the dead code, it is alive and
active.  Double-check by searching for `_ExportProgressLogger` usage
within render_project() — it should be referenced.

Actually, upon careful re-reading, _ExportProgressLogger may NOT be
directly used any longer either since the fast compositor handles its
own progress.  However, this is a separate determination.  For Feature
7.1, focus ONLY on the clearly dead MoviePy-specific code (crossfade,
duration calculation, and the specific imports identified).  Do NOT
remove _ExportProgressLogger in this feature — leave it for a separate
analysis.

**apply_crossfade_transitions() — lines 445-510:**
Starts with the comment `# Crossfade utility` section header.
Function signature: `def apply_crossfade_transitions(clips: list, transition_duration: float = TRANSITION_DURATION) -> list:`
Uses `vfx.CrossFadeIn` and `vfx.CrossFadeOut`.
Returns a new list of clips with effects applied.

**calculate_total_duration_with_transitions() — lines 520-575:**
Starts with the comment `# Duration calculation utility` section header.
Function signature: `def calculate_total_duration_with_transitions(clip_durations: list[float], transition_duration: float = TRANSITION_DURATION) -> float:`
Pure math function, no MoviePy dependency, but used only in the
MoviePy concatenation path which is dead.

**render_project() — line 580:**
The function begins here.  Lazy imports at line 608.  Audio mixing
section at approximately line 933.  This function is NOT modified
except for import cleanup.

#### backend/core_engine/ken_burns.py (694 lines)

**MoviePy import — lines 33-41:**
The section comment "# MoviePy version-safe imports" starts at line 33.
The actual import is:
- try branch (L38): `from moviepy.editor import VideoClip`
- except branch (L40): `from moviepy import VideoClip`

**Helper functions to KEEP — lines 72-485:**
- load_and_prepare_image: ~L72-190
- calculate_crop_dimensions: ~L193-262
- get_pan_direction: ~L265-310
- position_to_coords: ~L313-395
- get_start_end_coords: ~L398-440
- interpolate_position: ~L443-485

**apply_ken_burns() to REMOVE — lines 487-694:**
Starts with the section comment `# Main public interface`.
Function signature: `def apply_ken_burns(image_path: str, duration: float, resolution: Tuple[int, int], zoom_intensity: float = 1.3, fps: int = 30, segment_index: int = 0) -> VideoClip:`
Returns a MoviePy VideoClip.

#### backend/core_engine/subtitle_engine.py (450 lines)

**MoviePy import — line 27:**
`from moviepy import TextClip`
This is a direct import (not try/except version-safe) because the
file was written for MoviePy 2.x only.

**Functions to KEEP — lines 63-217:**
- _is_boundary_word: ~L63-76
- chunk_text: ~L79-145
- calculate_subtitle_timing: ~L148-217

**generate_subtitle_clips() to REMOVE — lines 220-375:**
Function signature: `def generate_subtitle_clips(chunks: list[str], timings: list[tuple[float, float]], resolution: tuple[int, int], font: str, color: str, font_size: int | None = None, position: str = "bottom", y_position: int | None = None) -> list[TextClip]:`
Creates styled TextClip objects using MoviePy API.

**create_subtitles_for_segment() to REMOVE — lines 378-450:**
Preceded by the section comment `# Convenience Entry-Point`.
Function signature: `def create_subtitles_for_segment(text_content: str, audio_duration: float, resolution: tuple[int, int], font: str, color: str, font_size: int | None = None, position: str = "bottom", y_position: int | None = None) -> list[TextClip]:`
Orchestrates chunk_text → calculate_subtitle_timing → generate_subtitle_clips.

#### backend/core_engine/tests/test_crossfade.py (197 lines)

**The entire file is to be deleted.**
Imports at L11-14 reference `TRANSITION_DURATION`,
`apply_crossfade_transitions`, `calculate_total_duration_with_transitions`,
and `vfx` from `core_engine.video_renderer`.
The `create_mock_clip` helper at L17-36 creates MockMock clips.
The `CrossfadeTransitionTests` class at L39-197 has approximately 15
test methods.

### Patterns to Follow

#### Deletion order matters

Always delete dependents before dependencies.  The test file depends on
the functions, so delete it first.  Then delete the functions.  Then
clean up imports.  This prevents intermediate states where an import
references a non-existent function.

#### Import block style

The existing MoviePy import block in video_renderer.py uses a
try/except pattern for version compatibility.  After removing
concatenate_videoclips and vfx, maintain this same try/except structure
for the remaining AudioFileClip and _AudioClipBase imports.

#### Module docstring updates

Keep docstrings accurate and concise.  The existing docstrings are
well-written and follow a consistent format.  Match that format when
updating.

#### Comment headers

video_renderer.py uses dashed-line comment headers to separate sections
(e.g., `# --------------- Crossfade utility ---------------`).  When
removing a section, remove the header too.

### Constraints

1. Do NOT remove _ExportProgressLogger.  Even though it may or may not
   be actively used, it is NOT clearly dead MoviePy code — it uses the
   generic proglog library, not MoviePy video compositing.  Its removal
   is out of scope for this feature.

2. Do NOT remove TRANSITION_DURATION or INTER_SEGMENT_SILENCE constants.
   These are used by the fast compositor path (passed as arguments to
   fast_render_segments and to the audio mixing section).

3. Do NOT remove _make_silent_audio().  This function uses _AudioClipBase
   to create silent audio padding and is actively used in the audio
   mixing pipeline.

4. Do NOT remove any AudioFileClip, concatenate_audioclips, or
   CompositeAudioClip imports anywhere.  These are for audio mixing
   and are actively used.

5. Do NOT modify fast_compositor.py.  This feature only removes dead
   code; it does not alter the active rendering path.

6. Do NOT remove chunk_text() or calculate_subtitle_timing() from
   subtitle_engine.py.  These are used by the fast compositor.

7. Do NOT remove any Ken Burns helper functions.  Only remove
   apply_ken_burns() which wraps them in a MoviePy VideoClip.

8. When modifying import blocks, maintain the try/except MoviePy
   version compatibility pattern that already exists.

9. After all removals, the application must boot and render identically
   to before.  This is a pure dead-code removal with zero functional
   changes.

### Implementation Order

Execute these phases in strict order:

1. **Phase A** (Preparation) — Verify assumptions about what is alive
   and what is dead.  Run baseline tests.

2. **Phase B** (Test deletion) — Delete test_crossfade.py first to
   prevent import errors in later steps.

3. **Phase C** (video_renderer.py functions) — Remove the two dead
   functions.  This makes vfx and concatenate_videoclips imports
   unreferenced.

4. **Phase D** (ken_burns.py function) — Remove apply_ken_burns() and
   update the docstring.  This makes the VideoClip import unreferenced.

5. **Phase E** (subtitle_engine.py functions) — Remove the two dead
   functions.  This makes the TextClip import unreferenced.

6. **Phase F** (Import cleanup) — Remove all dead imports across all
   three files.  This is done last because it depends on all function
   removals being complete.

7. **Phase G** (Docstrings) — Update module-level docstrings.  This is
   cosmetic and can be done at any time but is logically last.

8. **Phase H** (Verification) — Run tests, search for stale references,
   boot the server, and optionally run a test render.

### Potential Pitfalls

1. **Confusing _ExportProgressLogger with dead code.**  The
   _ExportProgressLogger class sits in the same region of
   video_renderer.py as the dead crossfade functions.  It appears to be
   a MoviePy artifact because it uses proglog, but it is potentially
   still used for audio export progress.  DO NOT remove it.

2. **Accidentally removing _AudioClipBase.**  This is imported in the
   same MoviePy import block as the dead imports (vfx,
   concatenate_videoclips).  When editing the import block, be very
   careful to keep _AudioClipBase on its separate import line.

3. **Ken Burns docstring says "MoviePy version-safe."**  After removing
   the MoviePy import, this design principle in the docstring becomes
   stale.  Update it to avoid confusion.

4. **subtitle_engine.py constants may become unused.**  Several
   constants at the top of subtitle_engine.py (FONT_SIZE_DIVISOR,
   TEXT_WIDTH_RATIO, SUBTITLE_VERT_MARGIN_RATIO, DEFAULT_STROKE_COLOR,
   DEFAULT_STROKE_WIDTH) are used only by generate_subtitle_clips().
   After removing that function, they become dead constants.  However,
   the fast compositor's Pillow-based subtitle renderer (in
   fast_compositor.py) may define its own versions of these constants
   or may import them from subtitle_engine.py.  Check before removing.
   If they are only used by the deleted function, they can optionally
   be removed or kept for future reference.

5. **Document-series references.**  The document-series/ directory
   contains many task documents that reference the deleted functions
   (e.g., Task_05_02_01 through Task_05_02_07 heavily reference
   apply_crossfade_transitions).  These are historical development
   documents and do NOT need to be updated — they describe what was
   built at the time, not the current state.  Do not spend time
   modifying document-series files.

6. **The render_project comment at L787.**  This line says "Uses direct
   NumPy compositing + FFmpeg pipe instead of MoviePy's per-frame
   Pillow pipeline."  This is a comment inside the try block's code
   section, not a reference to the deleted functions.  It can be kept
   as a historical note or simplified.

7. **Type annotations using TextClip.**  The return type annotation
   ` -> list[TextClip]` on generate_subtitle_clips and
   create_subtitles_for_segment references the TextClip import.
   Since both the functions and the import are being removed together,
   this is not an issue.

---

### Summary of Files to Delete or Modify

| Action   | File                                                   |
| -------- | ------------------------------------------------------ |
| DELETE   | backend/core_engine/tests/test_crossfade.py            |
| MODIFY   | backend/core_engine/video_renderer.py (remove functions + clean imports) |
| MODIFY   | backend/core_engine/ken_burns.py (remove function + clean imports + update docstring) |
| MODIFY   | backend/core_engine/subtitle_engine.py (remove functions + clean import + update docstring) |

### Estimated Line Changes

| File                               | Lines Removed | Lines Added (docstring updates) | Net Change |
| ---------------------------------- | ------------- | ------------------------------- | ---------- |
| video_renderer.py                  | ~145          | ~5                              | ~-140      |
| ken_burns.py                       | ~215          | ~10                             | ~-205      |
| subtitle_engine.py                 | ~235          | ~8                              | ~-227      |
| test_crossfade.py                  | 197 (deleted) | 0                               | -197       |
| **Total**                          | **~792**      | **~23**                         | **~-769**  |
