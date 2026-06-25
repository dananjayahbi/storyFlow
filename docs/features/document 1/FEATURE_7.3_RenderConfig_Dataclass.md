# Feature 7.3 — RenderConfig Dataclass

> **Status:** Planned
> **Category:** Core Engine / Architecture Cleanup
> **Primary Target File:** `backend/core_engine/render_config.py` (new file)
> **Secondary Target File:** `backend/core_engine/video_renderer.py`
> **Estimated Complexity:** Low
> **Expected Impact:** Catches attribute typos at initialization, cleaner code, easier testing
> **Date Created:** March 10, 2026

---

## Table of Contents

1. [Document Overview](#1-document-overview)
2. [Flow Diagram](#2-flow-diagram)
3. [Step-by-Step Instructions](#3-step-by-step-instructions)
4. [Expected Outcome](#4-expected-outcome)
5. [Verification Checklist](#5-verification-checklist)
6. [Notes for AI Agent](#6-notes-for-ai-agent)

---

## 1. Document Overview

### 1.1 Problem Statement

The render pipeline in `backend/core_engine/video_renderer.py` (1218 lines)
reads project settings through approximately 15 scattered `getattr()` calls
with manual fallback values inside the `render_project()` function, which
starts at line 568. These calls are spread across roughly 120 lines of
boilerplate code between lines 625 and 740, with each call individually
handling validation, type coercion, logging, and default assignment.

The specific `getattr()` calls currently in the function are:

| Line | Setting Read | Default Fallback |
|------|-------------|-----------------|
| L633 | `zoom_intensity` | `None` (then falls back to `_DEFAULT_ZOOM` of 1.3) |
| L663 | `subtitle_font` | Empty string |
| L666 | `subtitle_color` | Empty string |
| L670 | `subtitle_font_size` | `None` (auto-compute from resolution) |
| L674 | `subtitle_position` | Empty string |
| L678 | `subtitle_y_position` | `None` (use preset position) |
| L682 | `subtitles_enabled` | `True` |
| L684 | `inter_segment_silence` | `None` (then falls back to module constant) |
| L708 | `logo_enabled` | `False` |
| L709 | `active_logo` | `None` |
| L730 | `upscale_enabled` | `False` |
| L731 | `upscale_model` | `"RealESRGAN_x4plus"` |
| L732 | `upscale_denoise_strength` | `0.5` |
| L1026 | `active_logo` (repeated) | `None` |
| L1065 | `outro_enabled` | `False` |
| L1070 | `active_outro` | `None` |

This creates several problems:

1. **Typo risk.** Every `getattr()` call uses a raw string attribute name.
   A misspelling like `"subtitles_enaled"` instead of `"subtitles_enabled"`
   silently returns the default value instead of raising an error. The bug
   would go unnoticed until a user reports that a setting is being ignored.

2. **Duplicated reads.** The `active_logo` attribute is read twice — once in
   section C4 around line 709 and again in section H around line 1026 when
   building the `logo_settings_dict`. If the logo data were already captured
   in a structured object at the top, the second read would be unnecessary.

3. **No type safety.** Each value is read as a generic `Any` type and then
   manually coerced (for example, `int(raw_fs)` at line 671, `float(val)` at
   line 636, `raw_pos.strip()` at line 675). There is no single place that
   defines the expected types for all render settings.

4. **Difficult to test.** Unit tests that want to exercise `render_project()`
   with specific settings must either create a full Django `Project` model
   instance in the database or mock `getattr()` calls on a fake object. A
   typed dataclass would allow tests to construct a `RenderConfig(...)` with
   explicit values and inject it directly.

5. **Scattered defaults.** Default values for settings are defined in multiple
   places — the `Project` model field definitions in
   `backend/api/models.py`, the `getattr()` fallback arguments in
   `video_renderer.py`, and sometimes as module-level constants (for example,
   `INTER_SEGMENT_SILENCE` at the top of `video_renderer.py` and
   `TRANSITION_DURATION`). If a developer changes a default in one place
   but forgets the other, behavior becomes inconsistent.

6. **Long function body.** The boilerplate reading between lines 625 and 740
   accounts for over 100 lines of the roughly 650-line `render_project()`
   function. Extracting it into a classmethod on a dedicated dataclass would
   dramatically shorten `render_project()` and make its high-level flow
   easier to read.

### 1.2 Proposed Solution

Create a new Python module `backend/core_engine/render_config.py` containing
a `RenderConfig` dataclass (using the standard library `dataclasses` module
or Python 3.10+ `@dataclass` with `slots=True`) that holds every render
setting as a typed, named field with a clear default.

The dataclass will expose a `from_project(project)` classmethod that
encapsulates all `getattr()` extraction, type validation, default
assignment, and logging into a single factory. The `render_project()`
function will call `RenderConfig.from_project(project)` once near the top
and then use the resulting object throughout the rest of the pipeline.

The `fast_render_segments()` function in
`backend/core_engine/fast_compositor.py` (line 488) currently receives
individual settings as separate keyword arguments (resolution, fps,
zoom_intensity, subtitle_settings dict, logo_settings dict, and so on).
The initial implementation will NOT change the `fast_render_segments()`
signature — `render_project()` will unpack the `RenderConfig` fields
into the existing keyword arguments. A future iteration may update
`fast_render_segments()` to accept a `RenderConfig` directly, but that
is out of scope for this feature to minimize the change surface.

### 1.3 Scope

| In Scope | Out of Scope |
|----------|-------------|
| New `render_config.py` module with `RenderConfig` dataclass | Changing the `fast_render_segments()` function signature |
| `from_project()` classmethod that replaces all getattr() calls | Changing the `Project` Django model fields |
| Updating `render_project()` to use `RenderConfig` | Migrating any database schema |
| Logging all resolved settings from the config object | Adding new settings fields that do not already exist |
| Unit tests for `RenderConfig.from_project()` | Refactoring `fast_compositor.py` internals |
| Preserving identical runtime behavior (no functional change) | Changing the API serializer or frontend |

### 1.4 Key Files

| File | Lines | Role in Feature |
|------|-------|----------------|
| `backend/core_engine/render_config.py` | New file (~150 lines) | Houses the `RenderConfig` dataclass and `from_project()` factory |
| `backend/core_engine/video_renderer.py` | 1218 lines | `render_project()` at L568 is the consumer — replace boilerplate with one `RenderConfig.from_project()` call |
| `backend/api/models.py` | 279 lines | `Project` model at L35 defines the fields being read — used as reference for field names and types |
| `backend/core_engine/fast_compositor.py` | 839 lines | `fast_render_segments()` at L488 — no changes, but must receive the same values it does today |
| `backend/tests/` | Varies | New unit test file for `RenderConfig` |

### 1.5 Metadata

| Property | Value |
|----------|-------|
| Idea Reference | IDEAS_01, Section 7.3 |
| Dependencies | None (purely internal refactor) |
| Risk Level | Low — no behavioral change, no schema migration, no API change |
| Rollback Strategy | Delete `render_config.py`, revert changes to `video_renderer.py` |
| Estimated Lines Changed | ~150 new in `render_config.py`, ~120 removed / ~30 added in `video_renderer.py` |

---

## 2. Flow Diagram

### 2.1 Current Data Flow (Before This Feature)

The diagram below shows how render settings currently travel from the
database through the Django ORM, through scattered getattr() calls in
render_project(), through manual assembly of intermediate dicts, and
finally to fast_render_segments().

```
    ┌──────────────────────────────────────────────────────────────────┐
    │                     DATABASE (db.sqlite3)                        │
    │  Project table row: zoom_intensity, subtitle_font,               │
    │  subtitle_color, subtitle_font_size, subtitle_position,          │
    │  subtitle_y_position, subtitles_enabled, inter_segment_silence,  │
    │  logo_enabled, active_logo_id, logo_scale, logo_position,        │
    │  logo_opacity, logo_margin, upscale_enabled, upscale_model,      │
    │  upscale_denoise_strength, outro_enabled, active_outro_id,       │
    │  resolution_width, resolution_height, framerate                  │
    └──────────────────────────┬───────────────────────────────────────┘
                               │
                               │ Django ORM: Project.objects.get(id=...)
                               ▼
    ┌──────────────────────────────────────────────────────────────────┐
    │                 project (Django Model Instance)                   │
    │  All fields available as Python attributes on the ORM object     │
    └──────────────────────────┬───────────────────────────────────────┘
                               │
          ┌────────────────────┼────────────────────────────┐
          │                    │                             │
          ▼                    ▼                             ▼
    ┌────────────┐     ┌──────────────┐             ┌──────────────┐
    │ Section C2 │     │ Section C3   │             │ Section C4   │
    │ L633       │     │ L663–L684    │             │ L708–L709    │
    │ getattr()  │     │ 7 getattr()  │             │ 2 getattr()  │
    │ zoom_int.  │     │ calls for    │             │ calls for    │
    │            │     │ subtitle     │             │ logo         │
    │ Manual     │     │ settings     │             │ settings     │
    │ validation │     │              │             │              │
    │ + default  │     │ Each with    │             │ Plus file    │
    │ + logging  │     │ validation   │             │ existence    │
    │            │     │ + coercion   │             │ check        │
    └─────┬──────┘     └──────┬───────┘             └──────┬───────┘
          │                   │                            │
          │          ┌────────┘          ┌─────────────────┘
          │          │                   │
          ▼          ▼                   ▼
    ┌──────────────────────────────────────────────────────────────────┐
    │              Section C5: L730–L732                                │
    │              3 more getattr() calls for upscale settings         │
    └──────────────────────────┬───────────────────────────────────────┘
                               │
                               ▼
    ┌──────────────────────────────────────────────────────────────────┐
    │         Individual local variables scattered through             │
    │         render_project() body:                                    │
    │                                                                  │
    │  zoom_intensity (float)      subtitle_font (str or None)         │
    │  subtitle_color (str)        subtitle_font_size (int or None)    │
    │  subtitle_position (str)     subtitle_y_position (int or None)   │
    │  subtitles_enabled (bool)    inter_segment_silence (float)       │
    │  logo_enabled (bool)         logo_file_path (str)                │
    │  upscale_enabled (bool)      upscale_model (str)                 │
    │  upscale_denoise (float)     res_width (int)                     │
    │  res_height (int)            fps (int)                           │
    └──────────────────────────┬───────────────────────────────────────┘
                               │
                               │ Manual assembly into 2 dicts
                               │ (sub_settings at ~L1012, logo_settings_dict at ~L1026)
                               ▼
    ┌──────────────────────────────────────────────────────────────────┐
    │              fast_render_segments()  (fast_compositor.py L488)    │
    │                                                                  │
    │  Receives:  resolution=(w, h),  fps,  zoom_intensity,            │
    │             subtitle_settings={...},  logo_settings={...},       │
    │             audio_path,  use_nvenc,  crossfade_duration,         │
    │             inter_segment_silence                                 │
    └──────────────────────────────────────────────────────────────────┘
```

### 2.2 Proposed Data Flow (After This Feature)

```
    ┌──────────────────────────────────────────────────────────────────┐
    │                     DATABASE (db.sqlite3)                        │
    │  Project table row (unchanged)                                   │
    └──────────────────────────┬───────────────────────────────────────┘
                               │
                               │ Django ORM: Project.objects.get(id=...)
                               ▼
    ┌──────────────────────────────────────────────────────────────────┐
    │                 project (Django Model Instance)                   │
    └──────────────────────────┬───────────────────────────────────────┘
                               │
                               │  ONE call: RenderConfig.from_project(project)
                               │
                               ▼
    ┌──────────────────────────────────────────────────────────────────┐
    │                                                                  │
    │              RenderConfig  (frozen dataclass)                     │
    │              ─────────────────────────────                        │
    │                                                                  │
    │  render_config.py  (new module)                                  │
    │                                                                  │
    │  Fields:                                                         │
    │  ├── resolution_width: int          = 1920                       │
    │  ├── resolution_height: int         = 1080                       │
    │  ├── fps: int                       = 30                         │
    │  ├── zoom_intensity: float          = 1.3                        │
    │  ├── subtitle_font: str or None     = None                       │
    │  ├── subtitle_color: str            = "#FFFFFF"                  │
    │  ├── subtitle_font_size: int | None = None                       │
    │  ├── subtitle_position: str         = "bottom"                   │
    │  ├── subtitle_y_position: int|None  = None                       │
    │  ├── subtitles_enabled: bool        = True                       │
    │  ├── inter_segment_silence: float   = 0.3                        │
    │  ├── crossfade_duration: float      = 0.5                        │
    │  ├── logo_enabled: bool             = False                      │
    │  ├── logo_file_path: str or None    = None                       │
    │  ├── logo_scale: float              = 0.15                       │
    │  ├── logo_position: str             = "bottom-right"             │
    │  ├── logo_opacity: float            = 1.0                        │
    │  ├── logo_margin: int               = 20                         │
    │  ├── upscale_enabled: bool          = False                      │
    │  ├── upscale_model: str             = "RealESRGAN_x4plus"        │
    │  ├── upscale_denoise_strength: float= 0.5                        │
    │  ├── outro_enabled: bool            = False                      │
    │  ├── outro_file_path: str or None   = None                       │
    │  └── use_nvenc: bool                = False                      │
    │                                                                  │
    │  Methods:                                                        │
    │  ├── from_project(project) -> RenderConfig  [classmethod]        │
    │  ├── to_subtitle_settings() -> dict                              │
    │  ├── to_logo_settings() -> dict or None                          │
    │  └── log_summary(logger) -> None                                 │
    │                                                                  │
    └──────────────────────────┬───────────────────────────────────────┘
                               │
                               │  Unpack into keyword arguments
                               │  (preserving fast_render_segments signature)
                               ▼
    ┌──────────────────────────────────────────────────────────────────┐
    │              fast_render_segments()  (fast_compositor.py L488)    │
    │                                                                  │
    │  Receives the same keyword arguments as before — zero changes    │
    │  to this function's signature or behavior.                       │
    └──────────────────────────────────────────────────────────────────┘
```

### 2.3 Internal Structure of from_project() Classmethod

```
    ┌──────────────────────────────────────────────────────────────────┐
    │         RenderConfig.from_project(project)                       │
    ├──────────────────────────────────────────────────────────────────┤
    │                                                                  │
    │  Step 1: Read direct attributes (no getattr needed)              │
    │  ├── project.resolution_width                                    │
    │  ├── project.resolution_height                                   │
    │  └── project.framerate                                           │
    │                                                                  │
    │  Step 2: Read with safe fallbacks (via getattr)                  │
    │  ├── zoom_intensity  (validate range 1.0–2.0, default 1.3)      │
    │  ├── subtitle_font   (strip whitespace, None if empty)           │
    │  ├── subtitle_color  (strip, default "#FFFFFF")                  │
    │  ├── subtitle_font_size (int coerce, None if zero/negative)      │
    │  ├── subtitle_position  (validate in top/center/bottom)          │
    │  ├── subtitle_y_position (int coerce, None if missing)           │
    │  ├── subtitles_enabled  (bool, default True)                     │
    │  └── inter_segment_silence (float, validate >= 0)                │
    │                                                                  │
    │  Step 3: Read logo settings with file validation                 │
    │  ├── logo_enabled  (bool, default False)                         │
    │  ├── active_logo → check .file attribute → check os.path.isfile  │
    │  ├── logo_scale, logo_position, logo_opacity, logo_margin        │
    │  └── If file missing → set logo_enabled = False, log warning     │
    │                                                                  │
    │  Step 4: Read upscale settings                                   │
    │  ├── upscale_enabled  (bool)                                     │
    │  ├── upscale_model    (str, validate against MODEL_REGISTRY)     │
    │  └── upscale_denoise_strength  (float, clamp 0.0–1.0)           │
    │                                                                  │
    │  Step 5: Read outro settings with file validation                │
    │  ├── outro_enabled  (bool)                                       │
    │  ├── active_outro → check .file attribute → check os.path.isfile │
    │  └── If file missing → set outro_enabled = False, log warning    │
    │                                                                  │
    │  Step 6: Construct and return RenderConfig instance               │
    │  └── All fields explicitly assigned — frozen dataclass           │
    │                                                                  │
    └──────────────────────────────────────────────────────────────────┘
```

### 2.4 Relationship Between render_project() Sections and RenderConfig

```
    render_project() BEFORE                render_project() AFTER
    ──────────────────────                 ──────────────────────

    Section A: FFmpeg check        ──►     Section A: FFmpeg check  (unchanged)
    Section B: Load project        ──►     Section B: Load project  (unchanged)
    Section C:  Resolution         ──┐
    Section C2: Zoom intensity     ──┤
    Section C3: Subtitle settings  ──┤     Section C: config = RenderConfig
    Section C4: Logo settings      ──┤                .from_project(project)
    Section C5: Upscale settings   ──┘                config.log_summary(logger)
    Section D:  Query segments     ──►     Section D: Query segments (unchanged)
    Section E:  Validate segments  ──►     Section E: Validate segments (unchanged)
    Section F:  Output path        ──►     Section F: Output path (unchanged)
    Section G:  Collect data       ──►     Section G: Use config.upscale_*
    Section G1.5: Upscale images   ──►     Section G1.5: Use config.upscale_*
    Section G2: Export audio       ──►     Section G2: Use config.inter_segment_silence
    Section H:  Fast render call   ──►     Section H: Unpack config into kwargs
    Section I:  Append outro       ──►     Section I: Use config.outro_*
    Section K:  Verify output      ──►     Section K: (unchanged)
```

---

## 3. Step-by-Step Instructions

### Step 1: Create the New Module File

Create a new file at `backend/core_engine/render_config.py`.

At the top of the file, add the standard module docstring describing its
purpose — to centralize all render settings extraction from a Django Project
model instance into a single typed dataclass.

Add the following imports: `dataclasses` from the standard library (specifically
the `dataclass` decorator and the `field` function), `logging`, `os`, and
`typing.Optional`. The `logging` import is needed because the `from_project()`
classmethod and the `log_summary()` method will both emit log messages.

Create a module-level logger using `logging.getLogger(__name__)`.

### Step 2: Define Default Constants

Below the imports, define module-level constants for defaults that should match
the values currently scattered across `video_renderer.py`:

- A default zoom intensity constant with value 1.3, matching the
  `_DEFAULT_ZOOM` variable currently at line 632 of `video_renderer.py`.
- A default subtitle color constant with value `"#FFFFFF"`, matching the
  hardcoded default at line 661 of `video_renderer.py`.
- A default subtitle position constant with value `"bottom"`, matching line 662.
- A default inter-segment silence constant with value 0.3, matching the
  module-level `INTER_SEGMENT_SILENCE` constant in `video_renderer.py`.
- A default crossfade duration constant with value 0.5, matching the
  module-level `TRANSITION_DURATION` constant in `video_renderer.py`.
- A default upscale model constant with value `"RealESRGAN_x4plus"`, matching
  the getattr fallback at line 731.
- A default upscale denoise strength constant with value 0.5, matching line 732.
- A default logo scale with value 0.15, matching the getattr fallback in the
  logo settings assembly around line 1029.
- A default logo position with value `"bottom-right"`, matching line 1030.
- A default logo opacity with value 1.0, matching line 1031.
- A default logo margin with value 20, matching line 1032.

### Step 3: Define the RenderConfig Dataclass

Define a class named `RenderConfig` decorated with `@dataclass(frozen=True)`.
Using `frozen=True` ensures that once created, the config object cannot be
accidentally mutated during the render pipeline, which is important for
thread safety in the future multi-threaded rendering feature (Feature 1.1).

Add the following fields in this exact order, each with a type annotation
and default value:

**Resolution and framerate group:**
- `resolution_width` typed as `int` with default 1920
- `resolution_height` typed as `int` with default 1080
- `fps` typed as `int` with default 30

**Ken Burns group:**
- `zoom_intensity` typed as `float` with default matching the zoom constant

**Subtitle group:**
- `subtitle_font` typed as `Optional[str]` with default `None`
- `subtitle_color` typed as `str` with default matching the color constant
- `subtitle_font_size` typed as `Optional[int]` with default `None`
  (None means auto-compute from resolution, which is the current behavior)
- `subtitle_position` typed as `str` with default matching the position constant
- `subtitle_y_position` typed as `Optional[int]` with default `None`
- `subtitles_enabled` typed as `bool` with default `True`

**Audio and timing group:**
- `inter_segment_silence` typed as `float` with default matching the silence constant
- `crossfade_duration` typed as `float` with default matching the crossfade constant

**Logo group:**
- `logo_enabled` typed as `bool` with default `False`
- `logo_file_path` typed as `Optional[str]` with default `None`
- `logo_scale` typed as `float` with default matching the logo scale constant
- `logo_position` typed as `str` with default matching the logo position constant
- `logo_opacity` typed as `float` with default matching the logo opacity constant
- `logo_margin` typed as `int` with default matching the logo margin constant

**Upscale group:**
- `upscale_enabled` typed as `bool` with default `False`
- `upscale_model` typed as `str` with default matching the upscale model constant
- `upscale_denoise_strength` typed as `float` with default matching the denoise constant

**Outro group:**
- `outro_enabled` typed as `bool` with default `False`
- `outro_file_path` typed as `Optional[str]` with default `None`

**Encoding group:**
- `use_nvenc` typed as `bool` with default `False`

### Step 4: Implement the from_project() Classmethod

Add a classmethod named `from_project` that takes a single parameter `project`
(typed as `Any` since the Django model type should not be imported at class
definition time to avoid circular imports).

Inside the method, implement the following extraction logic. This logic directly
mirrors what currently exists in `render_project()` between lines 625 and 740,
but consolidated into one place.

**Resolution and FPS extraction:**
Read `project.resolution_width`, `project.resolution_height`, and
`project.framerate` as direct attribute accesses. These are concrete Django
model fields on the Project model (defined at lines 43–45 of
`backend/api/models.py`) and will never be missing on a saved instance.

**Zoom intensity extraction:**
Use getattr to read `zoom_intensity` from the project. If the value is not
None and is greater than zero, convert to float. If it falls outside the
1.0 to 2.0 range, log a debug-level message noting it is outside the typical
range but accept it as-is (matching the current behavior at lines 636–642 of
`video_renderer.py`). If the value is None or zero, use the default constant
and log a warning (matching lines 644–648).

**Subtitle font extraction:**
Use getattr to read `subtitle_font` from the project with a fallback of
empty string. Strip whitespace. If the result is non-empty, store it. If
empty, store None (meaning no custom font, the renderer will use the
system default). This matches the behavior at lines 663–665.

**Subtitle color extraction:**
Use getattr to read `subtitle_color` with empty string fallback. Strip
whitespace. If non-empty, use it. Otherwise use the default color constant.
This matches lines 666–668.

**Subtitle font size extraction:**
Use getattr to read `subtitle_font_size` with None fallback. If not None
and greater than zero after int conversion, store the int value. Otherwise
store None (auto-compute mode). This matches lines 670–672.

**Subtitle position extraction:**
Use getattr to read `subtitle_position` with empty string fallback. Strip
whitespace. Validate that the value is one of `"top"`, `"center"`, or
`"bottom"`. If valid, use it. If not, use the default position constant.
This matches lines 674–676.

**Subtitle Y position extraction:**
Use getattr to read `subtitle_y_position` with None fallback. If not None,
convert to int and store. Otherwise store None. This matches lines 678–679.

**Subtitles enabled extraction:**
Use getattr to read `subtitles_enabled` with True fallback. This is a
simple boolean pass-through matching line 682.

**Inter-segment silence extraction:**
Use getattr to read `inter_segment_silence` with None fallback. If not
None and the value is >= 0, convert to float. Otherwise use the default
silence constant. This matches lines 684–686.

**Crossfade duration extraction:**
Use getattr to read `transition_duration` from the project (note: the
Project model field is `transition_duration` at line 78 of models.py, but
the variable used in render_project is `TRANSITION_DURATION` module
constant). Read from the project and fall back to the default constant.

**Logo settings extraction:**
Wrap the entire logo extraction in a try/except block, matching the
pattern at lines 706–726 of `video_renderer.py`.

First, use getattr to read `logo_enabled` with False fallback. If True,
use getattr to read `active_logo` with None fallback. If active_logo is
not None and has a `.file` attribute, get the file path via
`active_logo.file.path`. Check that the path exists on disk using
`os.path.isfile()`. If the file exists, set `logo_enabled` to True and
store the path as `logo_file_path`. Also read the four logo styling
fields — `logo_scale` via getattr with 0.15 default, `logo_position`
via getattr with `"bottom-right"` default, `logo_opacity` via getattr
with 1.0 default, and `logo_margin` via getattr with 20 default, each
converted to the appropriate type (float, str, float, int).

If the file does not exist, log a warning and set `logo_enabled` to False.
If any exception occurs in the logo block, log a warning and set
`logo_enabled` to False with `logo_file_path` as None.

**Upscale settings extraction:**
Use getattr to read `upscale_enabled` with False fallback. Use getattr
to read `upscale_model` with the default model constant. Use getattr to
read `upscale_denoise_strength` with the default denoise constant.
Clamp the denoise strength to the 0.0 to 1.0 range. This matches lines
730–732.

**Outro settings extraction:**
Wrap in a try/except. Use getattr to read `outro_enabled` with False
fallback. If True, use getattr to read `active_outro` with None fallback.
If active_outro is not None and has a `.file` attribute, get the path
and check that it exists on disk. If valid, store the path. If not,
set `outro_enabled` to False and log a warning.

Finally, construct and return a RenderConfig instance with all extracted
values passed as keyword arguments to the constructor.

### Step 5: Implement the to_subtitle_settings() Method

Add a method named `to_subtitle_settings` that takes no parameters besides
self and returns a dict matching the structure of `sub_settings` currently
built at approximately line 1012 of `video_renderer.py`.

The returned dict should have these exact keys (to match what
`fast_render_segments()` expects in its `subtitle_settings` parameter):
- `"enabled"` mapped to `self.subtitles_enabled`
- `"font"` mapped to the result of resolving `self.subtitle_font` through
  the font path resolver. Import `render_utils` lazily inside this method
  and call `render_utils.get_font_path(self.subtitle_font)` to resolve
  the font name to a filesystem path, matching the call at approximately
  line 692 of `video_renderer.py`.
- `"color"` mapped to `self.subtitle_color`
- `"font_size"` mapped to `self.subtitle_font_size`
- `"position"` mapped to `self.subtitle_position`
- `"y_position"` mapped to `self.subtitle_y_position`

### Step 6: Implement the to_logo_settings() Method

Add a method named `to_logo_settings` that returns either a dict or None.

If `self.logo_enabled` is False or `self.logo_file_path` is None, return
None.

Otherwise return a dict with these exact keys (matching the
`logo_settings_dict` structure built at lines 1026–1033 of
`video_renderer.py`):
- `"file_path"` mapped to `self.logo_file_path`
- `"scale"` mapped to `self.logo_scale`
- `"position"` mapped to `self.logo_position`
- `"opacity"` mapped to `self.logo_opacity`
- `"margin"` mapped to `self.logo_margin`

### Step 7: Implement the log_summary() Method

Add a method named `log_summary` that takes a `logger` parameter and emits
a series of info-level log messages summarizing all resolved settings.

The method should log:
- Resolution and framerate on one line (matching the log at line 651 of
  `video_renderer.py`)
- Zoom intensity on one line (matching line 650)
- All subtitle settings on one line (matching lines 694–699)
- Inter-segment silence on one line (matching lines 700–702)
- Logo enabled status and file path if applicable (matching lines 714–717)
- Upscale settings (enabled, model, denoise) on one line (matching lines 733–736)
- Outro enabled status if applicable

This consolidates the 7 separate log statements currently scattered through
sections C, C2, C3, C4, and C5 into a single organized method.

### Step 8: Update video_renderer.py — Add Import

Open `backend/core_engine/video_renderer.py`.

At the top of the file, in the import section around line 28, add an import
for the new RenderConfig class. Import it from `core_engine.render_config`.
Place it after the existing `from core_engine` imports or alongside them.

Alternatively, import it lazily inside `render_project()` at the point of
use, similar to how the Django models are lazily imported at line 608. This
avoids import-time issues if the module is loaded outside Django context.

### Step 9: Update render_project() — Replace Section C through C5

In `render_project()`, locate section C (starting with the comment
"C. Read resolution and framerate settings" at approximately line 625)
through to the end of section C5 (ending at approximately line 736 after
the upscale logging statement).

Replace this entire block — roughly lines 625 through 740 — with a single
call to `RenderConfig.from_project(project)`, storing the result in a
local variable named `config`.

Immediately after, call `config.log_summary(logger)` to emit the same
log messages that the replaced code was producing.

Then add a line extracting the NVENC availability (since `_detect_nvenc()`
is called later in the pipeline at approximately line 1007 and is not a
project setting, it should either be set on the config after creation or
handled separately — the simplest approach is to keep the `_detect_nvenc()`
call where it is and not move it into the config, since it is a runtime
capability check, not a project setting).

After this change, the local variables that were previously set individually
(like `zoom_intensity`, `subtitle_font`, `subtitle_color`, `subtitle_font_size`,
`subtitle_position`, `subtitle_y_position`, `subtitles_enabled`,
`inter_segment_silence`, `logo_enabled`, `upscale_enabled`, `upscale_model`,
`upscale_denoise`, `res_width`, `res_height`, `fps`) no longer exist as
separate variables. All subsequent code in `render_project()` must now
reference `config.fieldname` instead.

### Step 10: Update References to Resolution, FPS, and Zoom

Search through the rest of `render_project()` for references to `res_width`,
`res_height`, and `fps` and replace them with `config.resolution_width`,
`config.resolution_height`, and `config.fps` respectively.

These variables are used when preparing the resolution tuple passed to
`fast_render_segments()` (around line 1047 where `resolution=(res_width,
res_height)` is currently passed).

### Step 11: Update References to Upscale Settings

In the upscale section (section G1.5, approximately lines 898–943 of
the original file), replace references to `upscale_enabled` with
`config.upscale_enabled`, `upscale_model` with `config.upscale_model`,
and `upscale_denoise` with `config.upscale_denoise_strength`.

The condition `if upscale_enabled:` at line 898 becomes
`if config.upscale_enabled:`.

The call to `upscale_images_batch()` at approximately line 916 which
passes `model_name=upscale_model` and `denoise_strength=upscale_denoise`
should be changed to `model_name=config.upscale_model` and
`denoise_strength=config.upscale_denoise_strength`.

### Step 12: Update the Sub-Settings Dict Assembly

In section H (approximately line 1010 onwards), remove the manual assembly
of `sub_settings` dict and replace it with a call to
`config.to_subtitle_settings()`.

The current code builds `sub_settings` with 6 keys from the local variables.
Replace it with `sub_settings = config.to_subtitle_settings()`.

### Step 13: Update the Logo Settings Dict Assembly

Remove the manual assembly of `logo_settings_dict` at approximately lines
1020–1033 (which includes a try/except, a getattr for active_logo, and
individual reads of logo_scale, logo_position, logo_opacity, logo_margin).

Replace it with `logo_settings_dict = config.to_logo_settings()`.

This is where the most significant deduplication occurs — the current code
reads `active_logo` via getattr a second time here, duplicating the read
that already happened in section C4. With `RenderConfig`, the logo file
path was already validated and extracted once in `from_project()`.

### Step 14: Update the fast_render_segments() Call

Locate the call to `fast_render_segments()` at approximately line 1047.
Update the keyword arguments to unpack from the config object:

- `resolution` should be `(config.resolution_width, config.resolution_height)`
- `fps` should be `config.fps`
- `zoom_intensity` should be `config.zoom_intensity`
- `subtitle_settings` should be `sub_settings` (from Step 12)
- `logo_settings` should be `logo_settings_dict` (from Step 13)
- `crossfade_duration` should be `config.crossfade_duration`
- `inter_segment_silence` should be `config.inter_segment_silence`
- `audio_path` and `use_nvenc` remain as they were (they come from
  local variables set elsewhere in the function)

### Step 15: Update the Outro Section

In section I (approximately lines 1065–1130), replace the getattr calls
for `outro_enabled` and `active_outro` with references to
`config.outro_enabled` and `config.outro_file_path`.

The current code at lines 1065–1070 reads `outro_enabled` via getattr
and then reads `active_outro` via getattr inside a try/except. Since
`RenderConfig.from_project()` already validated the outro path, the code
can be simplified to just check `config.outro_enabled` and use
`config.outro_file_path` directly, with a simple file existence guard.

### Step 16: Update the Audio Inter-Segment Silence References

In section G2 (audio mixing, approximately lines 950–1000), replace
references to the local variable `inter_segment_silence` with
`config.inter_segment_silence`.

This variable is used in the padded audio clips loop and in the staggered
timeline calculation.

### Step 17: Update Duration Estimation References

In section K (approximately lines 1140–1155), where total_duration is
estimated as a fallback, the calculation uses `inter_segment_silence`
and references `TRANSITION_DURATION`. Replace with
`config.inter_segment_silence` and `config.crossfade_duration`.

### Step 18: Remove Unused Local Variable Declarations

After all references have been updated, remove any local variable
declarations that are now dead code. This includes the block of
subtitle-related local variables initialized at lines 656–662 of the
original file (the block starting with `subtitle_font = None` and ending
with `inter_segment_silence = INTER_SEGMENT_SILENCE`).

Also remove the `_DEFAULT_ZOOM` constant at line 632 of `video_renderer.py`
since it now lives in `render_config.py`.

### Step 19: Remove the resolved_font Variable

The `resolved_font` variable (set at approximately line 692 of the original
file via `render_utils.get_font_path(subtitle_font)`) is now handled inside
`RenderConfig.to_subtitle_settings()`. Remove the standalone call and its
associated log statement in `render_project()`.

### Step 20: Write Unit Tests for RenderConfig

Create a new test file at `backend/tests/test_render_config.py`.

In this file, write the following test cases:

**Test 1: Default construction.**
Create a `RenderConfig()` with no arguments and verify that all fields
have their expected default values. Check resolution is 1920x1080, fps
is 30, zoom_intensity matches the default constant, subtitle_color is
"#FFFFFF", subtitles_enabled is True, logo_enabled is False, upscale_enabled
is False, outro_enabled is False, and use_nvenc is False.

**Test 2: from_project() with a mock project object.**
Create a mock object (using `unittest.mock.Mock` or a simple class with
attributes set) that mimics a Django Project instance. Set specific values
on the mock (for example, `zoom_intensity=1.5`, `subtitle_font="Roboto"`,
`subtitles_enabled=False`). Call `RenderConfig.from_project(mock_project)`
and verify the resulting config has the expected values.

**Test 3: from_project() with missing optional attributes.**
Create a mock project without the optional attributes (for example, no
`subtitle_font` attribute at all). Verify that getattr in `from_project()`
falls back to the default values without raising an exception.

**Test 4: from_project() logo validation.**
Create a mock project with `logo_enabled=True` but a non-existent file
path. Verify that the resulting config has `logo_enabled=False` and
`logo_file_path=None` because the file validation failed.

**Test 5: to_subtitle_settings() returns correct dict.**
Create a RenderConfig with specific subtitle settings and call
`to_subtitle_settings()`. Verify the returned dict has keys "enabled",
"font", "color", "font_size", "position", and "y_position" with the
correct values.

**Test 6: to_logo_settings() returns None when disabled.**
Create a RenderConfig with `logo_enabled=False` and verify
`to_logo_settings()` returns None.

**Test 7: to_logo_settings() returns dict when enabled.**
Create a RenderConfig with `logo_enabled=True` and a valid
`logo_file_path` and verify `to_logo_settings()` returns a dict with
the expected keys and values.

**Test 8: Frozen immutability.**
Create a RenderConfig and attempt to assign a new value to one of its
fields. Verify that a `FrozenInstanceError` (or `dataclasses.FrozenInstanceError`)
is raised.

**Test 9: Zoom intensity range warning.**
Create a mock project with `zoom_intensity=3.0` (outside 1.0–2.0 range).
Call `from_project()` and verify the value is accepted as-is (3.0) and
that a debug-level log message was emitted.

**Test 10: Denoise strength clamping.**
Create a mock project with `upscale_denoise_strength=1.5` (above 1.0).
Call `from_project()` and verify the value is clamped to 1.0.

### Step 21: Run Tests and Validate

Run the existing test suite to ensure no regressions. The key test to
run is `backend/tests/test_e2e.py` which exercises the full render
pipeline. Also run the new `test_render_config.py` tests.

Verify that a render with all default settings produces the same output
as before the change. Verify that a render with custom settings (logo
enabled, subtitles disabled, upscale enabled) also produces identical
output.

### Step 22: Clean Up Imports

Review `video_renderer.py` for any imports that are now unused after the
refactor. For example, if `render_utils.get_font_path` was only used in
the removed boilerplate section and is now called inside
`RenderConfig.to_subtitle_settings()`, the import in `video_renderer.py`
may still be needed for other uses — verify before removing.

---

## 4. Expected Outcome

### 4.1 Behavioral Changes

There are zero user-facing behavioral changes. This is a pure internal
refactor. The rendered video output is byte-for-byte identical before
and after this change for any given set of project settings.

### 4.2 Code Quality Improvements

**Before:**
- The `render_project()` function is approximately 650 lines long, with
  roughly 120 lines (18%) dedicated to reading settings via getattr calls
  and manual validation.
- Settings are scattered in 5 separate sections (C, C2, C3, C4, C5),
  each with its own logging and validation patterns.
- The same attribute (`active_logo`) is read via getattr in two separate
  locations (L709 and L1026).
- Default values for settings exist in three places: the model field
  definitions, the getattr fallbacks, and module-level constants.

**After:**
- The `render_project()` function loses approximately 120 lines and gains
  approximately 5 lines (one import, one `from_project()` call, one
  `log_summary()` call, and two `to_*_settings()` calls), for a net
  reduction of approximately 110 lines.
- All settings extraction, validation, and defaults are centralized in
  one class in one file (`render_config.py`).
- `active_logo` is read exactly once.
- Default values exist in exactly one place: the RenderConfig dataclass
  field definitions and the constants in `render_config.py`.

### 4.3 Testing Improvements

**Before:**
- Testing `render_project()` with specific settings requires either a
  full database-backed Project model or extensive mocking of the Django
  ORM.
- There is no way to test the settings extraction logic in isolation.

**After:**
- `RenderConfig.from_project()` can be tested with a simple mock object
  that has the right attributes — no database needed.
- `RenderConfig` can be constructed directly with explicit values for
  any test scenario, bypassing the extraction logic entirely.
- The `to_subtitle_settings()` and `to_logo_settings()` methods can be
  tested independently.

### 4.4 Developer Experience Improvements

- Adding a new render setting in the future follows a clear pattern:
  add the field to the Project model, add the field to RenderConfig,
  add the extraction logic in `from_project()`, and update the relevant
  `to_*_settings()` method or `fast_render_segments()` signature.
- IDE autocompletion works on `config.subtitle_font` (typed str or None)
  but not on `getattr(project, "subtitle_font", "")` which returns Any.
- Misspelling a field name at construction time raises a TypeError
  immediately, rather than silently falling back to a default value.

### 4.5 Performance Impact

None. The creation of one small dataclass instance at the start of
rendering adds negligible overhead (microseconds). The reduction in
duplicate getattr calls and file existence checks (logo is checked once
instead of twice) provides a trivial but measurable improvement.

### 4.6 File Size Changes

| File | Before | After | Net Change |
|------|--------|-------|------------|
| `backend/core_engine/render_config.py` | Does not exist | ~150 lines | +150 |
| `backend/core_engine/video_renderer.py` | 1218 lines | ~1110 lines | -108 |
| `backend/tests/test_render_config.py` | Does not exist | ~180 lines | +180 |
| **Total** | | | +222 lines |

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] All RenderConfig default values match the defaults currently
      hardcoded in video_renderer.py and the Project model fields
- [ ] RenderConfig.from_project() correctly extracts zoom_intensity from
      a mock project with a valid value
- [ ] RenderConfig.from_project() falls back to the default zoom when
      the project has zoom_intensity=None
- [ ] RenderConfig.from_project() falls back to the default zoom when
      the project has zoom_intensity=0
- [ ] Subtitle font is None when project.subtitle_font is empty string
- [ ] Subtitle font is correctly stripped of whitespace
- [ ] Subtitle color falls back to default when project value is empty
- [ ] Subtitle font_size is None when project value is None
- [ ] Subtitle font_size is None when project value is 0
- [ ] Subtitle font_size is correctly coerced to int when valid
- [ ] Subtitle position rejects invalid values and falls back to default
- [ ] Subtitle y_position is None when project value is None
- [ ] Subtitles_enabled correctly reads boolean from project
- [ ] Inter-segment silence rejects negative values and uses default
- [ ] Inter-segment silence accepts 0 (explicit zero is valid)
- [ ] Logo is disabled when logo_enabled=False on project
- [ ] Logo is disabled when logo_enabled=True but active_logo is None
- [ ] Logo is disabled when active_logo exists but file is missing on disk
- [ ] Logo is enabled when file exists, and file_path is correctly stored
- [ ] Logo scale, position, opacity, and margin are correctly extracted
- [ ] Upscale settings are correctly read from project
- [ ] Upscale denoise_strength is clamped to 0.0-1.0 range
- [ ] Outro is disabled when outro_enabled=False
- [ ] Outro is disabled when file does not exist on disk
- [ ] Outro file_path is correctly stored when valid
- [ ] Frozen dataclass raises error on mutation attempt
- [ ] to_subtitle_settings() returns dict with all 6 expected keys
- [ ] to_logo_settings() returns None when logo_enabled is False
- [ ] to_logo_settings() returns dict with all 5 expected keys when enabled
- [ ] log_summary() emits at least one log message for each settings group

### 5.2 Integration Tests

- [ ] Run `backend/tests/test_e2e.py` full render pipeline test
      and verify it passes with no changes to test code
- [ ] Render a project with default settings and compare output
      duration and file size to a baseline render from before the change
- [ ] Render a project with all optional features enabled (logo,
      upscale, subtitles, outro) and verify all features still function
- [ ] Render a project with all optional features disabled and verify
      clean output with no errors or warnings

### 5.3 Manual Verification

- [ ] Open the frontend UI, create a new project, and trigger a render
      with default settings — verify success
- [ ] Change subtitle font, color, and position in the UI, render
      again, and verify the changes are reflected in the video
- [ ] Enable logo watermark in the UI with a valid logo file, render,
      and verify the logo appears in the correct position
- [ ] Enable upscaling in the UI, render, and verify upscaled images
      are used (check log output for upscale messages)
- [ ] Check the render log output and verify the consolidated log
      messages from log_summary() appear correctly

### 5.4 Code Quality Checks

- [ ] Run linter or type checker to verify no type errors in new code
- [ ] Verify no circular import issues — render_config.py should not
      import from api.models at module level
- [ ] Verify render_config.py is importable outside Django context
      (for testing purposes)
- [ ] Verify all removed code in video_renderer.py is truly dead and
      not referenced elsewhere in the codebase

---

## 6. Notes for AI Agent

### 6.1 Implementation Order

Follow this exact sequence to minimize risk of intermediate breakage:

1. Create `backend/core_engine/render_config.py` first (Steps 1–7).
   This file is completely standalone and does not affect any existing code.
2. Write and run the unit tests in `backend/tests/test_render_config.py`
   (Step 20) to verify the dataclass works correctly in isolation.
3. Only after the dataclass is tested, begin modifying `video_renderer.py`
   (Steps 8–19).
4. Run the full test suite after the integration (Step 21).
5. Clean up unused imports last (Step 22).

### 6.2 Critical File Locations and Line Numbers

**`backend/core_engine/video_renderer.py`** (1218 lines total):

- Function `render_project()` starts at line 568 with the function signature
  and docstring. The function body begins executing at approximately line 607.
- Section B loads the project at approximately line 620.
- Section C reads resolution at lines 627–629:
  `res_width = project.resolution_width`,
  `res_height = project.resolution_height`, `fps = project.framerate`
- Section C2 begins at line 631 with `_DEFAULT_ZOOM = 1.3`
- Section C3 begins at line 656 with subtitle variable initializations
- Section C4 begins at line 706 with the logo try/except
- Section C5 begins at line 730 with upscale reads
- All sections C through C5 end at approximately line 740 (after the
  upscale logging at lines 733–736)
- Section G1.5 (upscale images) begins at line 898 with `if upscale_enabled:`
- Section H (fast render setup) begins at approximately line 1005
- The `sub_settings` dict is assembled at approximately lines 1012–1019
- The `logo_settings_dict` is assembled at approximately lines 1021–1033
- The `fast_render_segments()` call is at approximately lines 1047–1058
- Section I (outro) begins at approximately line 1065
- Duration fallback calculation is at approximately lines 1145–1152

**`backend/core_engine/fast_compositor.py`** (839 lines total):

- `fast_render_segments()` starts at line 488
- Its signature spans lines 488–500 with parameters: segment_data,
  output_path, resolution, fps, zoom_intensity, subtitle_settings,
  logo_settings, audio_path, use_nvenc, on_progress, crossfade_duration,
  inter_segment_silence
- DO NOT modify this function signature in this feature

**`backend/api/models.py`** (279 lines total):

- Project model starts at line 35
- Resolution fields at lines 43–45
- TTS settings at lines 49–50
- Subtitle fields at lines 52–70
- Zoom/Ken Burns fields at lines 73–75
- Audio timing at line 78
- Logo fields at lines 80–91
- Outro fields at lines 93–97
- Upscale fields at lines 100–111
- DO NOT modify this file

### 6.3 Patterns to Follow

**Existing getattr pattern to replicate (example from zoom intensity at L633):**
The current code reads `val = getattr(project, "zoom_intensity", None)`
then checks `if val is not None and val > 0:` then converts `float(val)`.
The `from_project()` classmethod should replicate this exact validation
logic for each field — do not simplify or change the behavior, only
consolidate the location.

**Existing font resolution pattern (at L692):**
The current code calls `resolved_font = render_utils.get_font_path(subtitle_font)`
and this must be replicated inside `to_subtitle_settings()`. Import
`render_utils` lazily from `core_engine` inside the method body.

**Existing logo file validation pattern (at L708–726):**
The current code wraps the entire logo block in `try: ... except Exception
as logo_err:`. The `from_project()` classmethod must replicate this
safety pattern. If any exception occurs while reading logo attributes
or checking the file, log a warning and disable the logo.

### 6.4 Do NOT Change

- Do NOT change the `fast_render_segments()` function signature in
  `fast_compositor.py`. This is a separate refactor (planned for a
  future iteration).
- Do NOT change the Project model in `models.py`. No schema changes.
- Do NOT change the API serializers or views.
- Do NOT change the frontend code.
- Do NOT add any new dependencies. Only standard library `dataclasses`.
- Do NOT change the module-level constants `TRANSITION_DURATION` and
  `INTER_SEGMENT_SILENCE` in `video_renderer.py` — they may be used
  elsewhere. The RenderConfig defaults should reference them or duplicate
  their values.

### 6.5 Frozen Dataclass Considerations

Using `@dataclass(frozen=True)` means the `from_project()` classmethod
cannot use `self.field = value` syntax. It must construct the instance
in one pass using the constructor. If the extraction logic is complex
(for example, logo validation requires multiple intermediate steps to
determine the final values), collect all values in local variables
within `from_project()` first, then call `cls(...)` with all values
at the end.

If the frozen constraint makes `from_project()` awkward, an alternative
is to use `@dataclass(frozen=False)` initially but document that the
object should not be mutated after construction. The frozen constraint
can be added in a later cleanup pass.

### 6.6 Import Concerns

The `render_config.py` module must NOT import Django models at the
module level. Since `from_project()` receives a generic project object
(with duck typing), no Django import is needed for the type annotation —
use `typing.Any` or a string literal.

The `render_utils` import inside `to_subtitle_settings()` must be done
lazily (inside the method body) because `render_utils` may depend on
Django settings or paths that are not available if the module is imported
outside Django context.

### 6.7 Constants Deduplication Strategy

The preferred approach for default values is:

1. Define each default as a module-level constant in `render_config.py`
   with a clear name (for example, `DEFAULT_ZOOM_INTENSITY = 1.3`).
2. Use these constants as field defaults in the dataclass definition.
3. Use these constants in `from_project()` for the getattr fallbacks.
4. The module-level constants `TRANSITION_DURATION` and
   `INTER_SEGMENT_SILENCE` in `video_renderer.py` should remain as-is
   for backward compatibility. The `render_config.py` constants should
   have the same numeric values.

### 6.8 Logging Expectations

The `from_project()` classmethod should emit the same log messages that
the current scattered code emits, including:

- A debug message when zoom_intensity is outside 1.0–2.0 range
- A warning when zoom_intensity falls back to default
- An info message for "Logo watermark enabled: filename"
- A warning for "Logo file not found: path"
- A warning for "Could not read logo settings: error"
- Info-level messages in `log_summary()` for resolution, zoom, subtitles,
  inter-segment silence, upscale settings

### 6.9 Edge Cases to Handle

- Project with no subtitle_font attribute at all (old DB migrations)
- Project with subtitle_font_size = 0 (should be treated as None/auto)
- Project with logo_enabled = True but active_logo = None
- Project with logo_enabled = True, active_logo exists, but
  active_logo.file is None or empty
- Project with upscale_denoise_strength = -0.1 (should be clamped to 0.0)
- Project with upscale_denoise_strength = 1.5 (should be clamped to 1.0)
- Project with inter_segment_silence = -1 (should use default, matching
  current behavior where `if iss_val is not None and iss_val >= 0:` gates it)

### 6.10 Test File Location

Place the test file at `backend/tests/test_render_config.py`. The
`backend/tests/` directory already exists and contains `__init__.py`,
`test_e2e.py`, and `test_settings.py`. Follow the existing test patterns
from those files.

### 6.11 Verification Command

After implementation, run these commands from the `backend/` directory:

1. Verify the new module imports cleanly without Django:
   Run `python -c "from core_engine.render_config import RenderConfig"`
   (this may fail if render_utils is imported at module level — check
   that all Django-dependent imports are lazy)

2. Run the test suite:
   `python manage.py test tests.test_render_config -v 2`
   `python manage.py test tests -v 2`

3. If there is an existing render test or E2E test, run it to confirm
   no regression.

---

*End of Feature 7.3 — RenderConfig Dataclass*
