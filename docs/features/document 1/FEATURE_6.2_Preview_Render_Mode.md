# Feature 6.2 — Preview Render Mode

> **Status:** Planned  
> **Category:** Core Engine / Render Performance  
> **Primary Files:** `backend/core_engine/fast_compositor.py`, `backend/core_engine/video_renderer.py`, `backend/api/views.py`, `backend/api/tasks.py`, `backend/api/serializers.py`  
> **Estimated Complexity:** Medium  
> **Impact:** Reduces iteration cycle from minutes to seconds — enables fast checking of flow, timing, and subtitle quality without a full quality render  
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

StoryFlow's current rendering pipeline always performs a full-quality render:
full project resolution (e.g. 1920×1080), project framerate (typically 24–30 fps),
with optional upscaling enabled. A typical 5-segment project at 1080p takes
2–5 minutes to render even with the fast compositor.

During content development — checking subtitles, verifying audio-visual timing,
reviewing Ken Burns motion direction — users do **not** need broadcast quality.
They need speed. There is currently **no lower-quality fast preview path** at all.

### 1.2 Proposed Solution

Add a `preview_mode` boolean flag that threads through the entire render pipeline.
When `True`, the renderer automatically applies a set of quality-reducing
but speed-maximising overrides:

| Setting | Full Render | Preview Mode |
|---|---|---|
| Resolution | Project setting (e.g. 1920×1080) | Capped at 854×480 (480p) |
| Framerate | Project setting (e.g. 30 fps) | Capped at 15 fps |
| Image upscaling | Per project setting | Always skipped |
| FFmpeg video codec | libx264 `crf 23` / NVENC | libx264 `crf 32 preset ultrafast` |
| FFmpeg audio bitrate | 192k (project setting) | 96k |
| Output file | `projects/<id>/output.mp4` | `projects/<id>/preview.mp4` |
| Logo watermark | Per project setting | Rendered (preserves preview accuracy) |
| Subtitles | Per project setting | Rendered (key check point) |

The flag is exposed as a boolean query parameter on the existing render API
endpoint so no new endpoint is required.

### 1.3 Scope of Changes

| File | Change |
|---|---|
| `fast_compositor.py` | Add `preview_mode` param to `FFmpegFrameWriter.__init__()` and `fast_render_segments()` |
| `video_renderer.py` | Add `preview_mode` param to `render_project()`, compute preview resolution/fps, skip upscaling |
| `api/tasks.py` | Pass `preview_mode` flag from task kwargs to `render_project()` |
| `api/views.py` | Read `preview_mode` from request data, pass to task |
| `api/serializers.py` | No model change needed — preview is purely a runtime flag |

### 1.4 Key Design Decisions

- **No new model field** — `preview_mode` is a transient render-time flag, not a
  persisted project property. This keeps migration overhead zero.
- **Separate output path** — preview renders to `preview.mp4` alongside the
  project's main `output.mp4`, so they do not overwrite each other.
- **Resolution scaling** — if the project resolution is already ≤ 480p, the
  preview renders at the project resolution rather than upscaling.
- **Framerate cap** — 15 fps is half of 30 fps, halving the total frame count
  and rendering time proportionally.
- **`ultrafast` preset** — libx264's `ultrafast` preset with `crf 32` produces
  files roughly 4–6× faster than the default `fast` + `crf 23` used in full renders.

---

## 2. Flow Diagram

```
API Request  ──►  views.py
   ?preview_mode=true       │
                            ▼
                    tasks.py (Celery task)
                    render_project(project_id,
                        preview_mode=True)
                            │
                            ▼
                  video_renderer.py
                  render_project()
                  ┌──────────────────────────────────┐
                  │ preview_mode=True?                │
                  │  ► cap resolution to 854×480      │
                  │  ► cap fps to 15                  │
                  │  ► skip upscaling                 │
                  │  ► output → preview.mp4           │
                  └──────────────────────────────────┘
                            │
                            ▼
                  fast_render_segments(
                      resolution=(854,480),
                      fps=15,
                      preview_mode=True
                  )
                            │
                  ┌─────────┴──────────┐
                  │  Phase 1           │  Phase 2
                  │  Pre-compute       │  Frame calc
                  │  overlays          │  at 15fps
                  └─────────┬──────────┘
                            │
                            ▼
                  FFmpegFrameWriter(
                      width=854, height=480,
                      fps=15,
                      preview_mode=True
                  )
                  _build_command():
                  ► -crf 32
                  ► -preset ultrafast
                  ► -b:a 96k
                  ► output → preview.mp4
                            │
                            ▼
                    preview.mp4  (seconds, not minutes)
```

---

## 3. Step-by-Step Instructions

### Step 3.1 — Update `FFmpegFrameWriter` in `fast_compositor.py`

**File:** `backend/core_engine/fast_compositor.py`

**Location:** `FFmpegFrameWriter.__init__()` (line ~382) and `_build_command()` (line ~400).

**Change 1 — Add `preview_mode` parameter to `__init__()`:**

```python
# BEFORE (line ~382):
def __init__(
    self,
    output_path: str,
    width: int,
    height: int,
    fps: int,
    audio_path: Optional[str] = None,
    use_nvenc: bool = False,
    bitrate: str = "8M",
):
    self.output_path = output_path
    self.width = width
    self.height = height
    self.fps = fps
    self.audio_path = audio_path
    self.use_nvenc = use_nvenc
    self.bitrate = bitrate
    self._proc: Optional[subprocess.Popen] = None
```

```python
# AFTER:
def __init__(
    self,
    output_path: str,
    width: int,
    height: int,
    fps: int,
    audio_path: Optional[str] = None,
    use_nvenc: bool = False,
    bitrate: str = "8M",
    preview_mode: bool = False,
):
    self.output_path = output_path
    self.width = width
    self.height = height
    self.fps = fps
    self.audio_path = audio_path
    self.use_nvenc = use_nvenc
    self.bitrate = bitrate
    self.preview_mode = preview_mode
    self._proc: Optional[subprocess.Popen] = None
```

**Change 2 — Use preview settings in `_build_command()`:**

Locate the `libx264` branch inside `_build_command()`. Currently it uses
`-preset fast -crf 23`. In preview mode, use `-preset ultrafast -crf 32`.
Also reduce audio bitrate to `96k` in preview mode.

```python
# BEFORE (inside _build_command, the libx264 branch ~line 425):
        else:
            cmd.extend([
                "-c:v", "libx264",
                "-preset", "fast",
                "-tune", "film",
                "-crf", "23",
                "-profile:v", "high",
            ])

        # Audio encoding
        if self.audio_path and os.path.isfile(self.audio_path):
            cmd.extend(["-c:a", "aac", "-b:a", "192k"])
```

```python
# AFTER:
        else:
            if self.preview_mode:
                cmd.extend([
                    "-c:v", "libx264",
                    "-preset", "ultrafast",
                    "-crf", "32",
                    "-profile:v", "baseline",
                ])
            else:
                cmd.extend([
                    "-c:v", "libx264",
                    "-preset", "fast",
                    "-tune", "film",
                    "-crf", "23",
                    "-profile:v", "high",
                ])

        # Audio encoding
        if self.audio_path and os.path.isfile(self.audio_path):
            audio_bitrate = "96k" if self.preview_mode else "192k"
            cmd.extend(["-c:a", "aac", "-b:a", audio_bitrate])
```

**Note:** NVENC path is NOT modified since preview mode always falls back to
`libx264` (NVENC overhead is not justified for throwaway previews). Add a guard
in Step 3.2 to set `use_nvenc=False` when `preview_mode=True`.

---

### Step 3.2 — Update `fast_render_segments()` in `fast_compositor.py`

**File:** `backend/core_engine/fast_compositor.py`

**Location:** `fast_render_segments()` function signature (line ~487).

**Change — Add `preview_mode` parameter and pass it to `FFmpegFrameWriter`:**

```python
# BEFORE (function signature ~line 487):
def fast_render_segments(
    segment_data: List[dict],
    output_path: str,
    resolution: Tuple[int, int],
    fps: int,
    zoom_intensity: float,
    subtitle_settings: dict,
    logo_settings: Optional[dict],
    audio_path: str,
    use_nvenc: bool = False,
    on_progress: Optional[Callable[[int, int, str], None]] = None,
    crossfade_duration: float = 0.5,
    inter_segment_silence: float = 0.3,
) -> dict:
```

```python
# AFTER:
def fast_render_segments(
    segment_data: List[dict],
    output_path: str,
    resolution: Tuple[int, int],
    fps: int,
    zoom_intensity: float,
    subtitle_settings: dict,
    logo_settings: Optional[dict],
    audio_path: str,
    use_nvenc: bool = False,
    on_progress: Optional[Callable[[int, int, str], None]] = None,
    crossfade_duration: float = 0.5,
    inter_segment_silence: float = 0.3,
    preview_mode: bool = False,
) -> dict:
```

Then locate where `FFmpegFrameWriter` is instantiated inside
`fast_render_segments()`. It will be near the bottom of the function where
the writer is created and started. Add `preview_mode=preview_mode` and force
`use_nvenc=False` when in preview mode:

```python
# BEFORE (FFmpegFrameWriter instantiation, locate by searching for "FFmpegFrameWriter("):
    writer = FFmpegFrameWriter(
        output_path=output_path,
        width=width,
        height=height,
        fps=fps,
        audio_path=combined_audio_path,
        use_nvenc=use_nvenc,
        bitrate=bitrate,
    )
```

```python
# AFTER:
    writer = FFmpegFrameWriter(
        output_path=output_path,
        width=width,
        height=height,
        fps=fps,
        audio_path=combined_audio_path,
        use_nvenc=False if preview_mode else use_nvenc,
        bitrate=bitrate,
        preview_mode=preview_mode,
    )
```

Also add a log line at the top of `fast_render_segments()` body (after the
docstring, before Phase 1):

```python
    if preview_mode:
        logger.info(
            "PREVIEW MODE: rendering at %dx%d @ %dfps (ultrafast, crf=32)",
            width, height, fps,
        )
```

---

### Step 3.3 — Update `render_project()` in `video_renderer.py`

**File:** `backend/core_engine/video_renderer.py`

**Location:** `render_project()` function signature (line ~581).

**Change 1 — Add `preview_mode` parameter:**

```python
# BEFORE:
def render_project(
    project_id: str,
    on_progress: ProgressCallback = None,
) -> dict:
```

```python
# AFTER:
def render_project(
    project_id: str,
    on_progress: ProgressCallback = None,
    preview_mode: bool = False,
) -> dict:
```

**Change 2 — Compute preview resolution and fps after reading project settings:**

Locate section `C. Read resolution and framerate settings` (line ~620):

```python
# AFTER the existing lines that set res_width, res_height, fps:
    # ------------------------------------------------------------------
    # C1b. Preview mode overrides
    # ------------------------------------------------------------------
    PREVIEW_MAX_WIDTH = 854
    PREVIEW_MAX_HEIGHT = 480
    PREVIEW_MAX_FPS = 15

    if preview_mode:
        # Scale resolution down to fit within 854×480, preserving aspect ratio
        scale = min(
            PREVIEW_MAX_WIDTH / res_width,
            PREVIEW_MAX_HEIGHT / res_height,
            1.0,  # Never upscale in preview
        )
        res_width = int(res_width * scale)
        res_height = int(res_height * scale)
        # FFmpeg requires dimensions divisible by 2 for yuv420p
        res_width = res_width if res_width % 2 == 0 else res_width - 1
        res_height = res_height if res_height % 2 == 0 else res_height - 1
        fps = min(fps, PREVIEW_MAX_FPS)
        logger.info(
            "Preview mode active: capped to %dx%d @ %dfps",
            res_width, res_height, fps,
        )
```

**Change 3 — Skip upscaling in preview mode:**

Locate the block that reads upscale settings (section `C5`, line ~730):

```python
# BEFORE:
    upscale_enabled = getattr(project, "upscale_enabled", False)
    upscale_model = getattr(project, "upscale_model", "RealESRGAN_x4plus")
    upscale_denoise = getattr(project, "upscale_denoise_strength", 0.5)
```

```python
# AFTER:
    upscale_enabled = getattr(project, "upscale_enabled", False)
    upscale_model = getattr(project, "upscale_model", "RealESRGAN_x4plus")
    upscale_denoise = getattr(project, "upscale_denoise_strength", 0.5)

    if preview_mode and upscale_enabled:
        upscale_enabled = False
        logger.info("Preview mode: image upscaling skipped.")
```

**Change 4 — Use a separate output path for previews:**

Locate section `F. Determine output path` (line ~790):

```python
# BEFORE:
    output_path = render_utils.get_output_path(str(project_id))
    logger.info("Output path: %s", output_path)
```

```python
# AFTER:
    if preview_mode:
        output_path = render_utils.get_output_path(str(project_id), filename="preview.mp4")
    else:
        output_path = render_utils.get_output_path(str(project_id))
    logger.info("Output path: %s", output_path)
```

**Change 5 — Pass `preview_mode` to `fast_render_segments()`:**

Locate the call to `fast_render_segments()` (around line 1008–1063). Add
`preview_mode=preview_mode` to the keyword arguments:

```python
# BEFORE:
        render_result = fast_render_segments(
            segment_data=segment_data_list,
            output_path=output_path,
            resolution=(res_width, res_height),
            fps=fps,
            zoom_intensity=zoom_intensity,
            subtitle_settings=subtitle_settings,
            logo_settings=logo_settings_dict if logo_enabled else None,
            audio_path=temp_audio_path,
            use_nvenc=use_nvenc,
            on_progress=on_progress,
            crossfade_duration=crossfade_duration,
            inter_segment_silence=inter_segment_silence,
        )
```

```python
# AFTER:
        render_result = fast_render_segments(
            segment_data=segment_data_list,
            output_path=output_path,
            resolution=(res_width, res_height),
            fps=fps,
            zoom_intensity=zoom_intensity,
            subtitle_settings=subtitle_settings,
            logo_settings=logo_settings_dict if logo_enabled else None,
            audio_path=temp_audio_path,
            use_nvenc=use_nvenc,
            on_progress=on_progress,
            crossfade_duration=crossfade_duration,
            inter_segment_silence=inter_segment_silence,
            preview_mode=preview_mode,
        )
```

---

### Step 3.4 — Update `render_utils.get_output_path()` to Accept a Filename

**File:** `backend/core_engine/render_utils.py`

Search for `get_output_path` in `render_utils.py` and add an optional
`filename` parameter:

```python
# BEFORE (example signature):
def get_output_path(project_id: str) -> str:
    ...
    return os.path.join(project_dir, "output.mp4")
```

```python
# AFTER:
def get_output_path(project_id: str, filename: str = "output.mp4") -> str:
    ...
    return os.path.join(project_dir, filename)
```

If `get_output_path` constructs the directory and the filename inline,
just ensure the returned path uses `filename` instead of the hardcoded
`"output.mp4"` string. Do **not** change any other call sites — they all
pass no `filename` and will default to `"output.mp4"`.

---

### Step 3.5 — Update `api/tasks.py`

**File:** `backend/api/tasks.py`

Locate the Celery task that calls `render_project()`. It will look
similar to:

```python
# BEFORE:
@shared_task(bind=True, ...)
def render_project_task(self, project_id, ...):
    ...
    result = render_project(
        project_id=project_id,
        on_progress=progress_callback,
    )
```

```python
# AFTER:
@shared_task(bind=True, ...)
def render_project_task(self, project_id, preview_mode=False, ...):
    ...
    result = render_project(
        project_id=project_id,
        on_progress=progress_callback,
        preview_mode=preview_mode,
    )
```

---

### Step 3.6 — Update `api/views.py`

**File:** `backend/api/views.py`

Locate the view that triggers the render task (typically a POST to
`/api/projects/{id}/render/` or similar). Add reading of `preview_mode`
from the request:

```python
# BEFORE:
    render_project_task.delay(
        project_id=str(project.id),
    )
```

```python
# AFTER:
    preview_mode = bool(request.data.get("preview_mode", False))
    render_project_task.delay(
        project_id=str(project.id),
        preview_mode=preview_mode,
    )
```

This makes the flag fully opt-in: existing clients that do not send
`preview_mode` continue to receive full-quality renders.

---

### Step 3.7 — Return Preview Flag in Render Result

**File:** `backend/core_engine/video_renderer.py`

At the end of `render_project()`, the function returns a dict with
`output_path`, `duration`, and `file_size`. Add `preview_mode` to the
returned dict so the API can communicate it to the frontend:

```python
# Locate the final return statement in render_project() and add:
    return {
        "output_path": output_path,
        "duration": ...,
        "file_size": ...,
        "preview_mode": preview_mode,   # ADD THIS LINE
    }
```

---

### Step 3.8 — (Optional) Frontend Quick Preview Button

If the frontend is being updated as part of this feature, add a
"Quick Preview" button alongside the existing "Render" button in the
project render controls component.

**File:** `frontend/components/` — locate the render button component.

The button should POST `{ preview_mode: true }` to the render endpoint
and open the result in the video player with a visible "PREVIEW" badge
to communicate the reduced quality to the user.

This step is optional if only backend changes are scoped for now.

---

## 4. Expected Outcome

After implementing this feature:

1. Sending `POST /api/projects/{id}/render/` with `{ "preview_mode": true }`
   triggers a fast render at 480p, 15fps, no upscaling.

2. For a typical 5-segment project (30 fps, 1080p), render time drops from
   ~2–5 minutes to **~15–30 seconds**.

3. The preview file is saved as `preview.mp4` in the project's media directory,
   leaving the full-quality `output.mp4` untouched.

4. The render task result includes `"preview_mode": true` so the frontend can
   display the result with a "PREVIEW" indicator.

5. All subtitle overlays and logo watermarks are still rendered in preview mode,
   preserving the accuracy of timing and positioning checks.

6. Existing renders (no `preview_mode` flag or `preview_mode: false`) are
   completely unaffected.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] `FFmpegFrameWriter._build_command()` with `preview_mode=True` produces
  `-preset ultrafast -crf 32` instead of `-preset fast -crf 23`.
- [ ] `FFmpegFrameWriter._build_command()` with `preview_mode=True` produces
  audio bitrate `96k` instead of `192k`.
- [ ] `FFmpegFrameWriter._build_command()` with `preview_mode=True` does NOT
  use NVENC (`h264_nvenc` not in command).
- [ ] `render_project()` with `preview_mode=True` computes resolution that is
  ≤ 854×480 and fps ≤ 15.
- [ ] `render_project()` with `preview_mode=True` sets `upscale_enabled=False`
  even when project has upscaling enabled.
- [ ] `render_project()` with `preview_mode=True` returns `output_path` ending
  in `preview.mp4`.
- [ ] `render_project()` with `preview_mode=False` (default) returns `output_path`
  ending in `output.mp4`.
- [ ] `render_utils.get_output_path(project_id, filename="preview.mp4")` returns
  the correct path with `preview.mp4` suffix.
- [ ] `render_utils.get_output_path(project_id)` (no filename arg) still returns
  path with `output.mp4` suffix.

### 5.2 Integration / Manual Tests

- [ ] Trigger a preview render via API. Verify the task completes in under 45
  seconds for a 5-segment 1080p project.
- [ ] Open `preview.mp4` and confirm it plays at reduced quality.
- [ ] Confirm `output.mp4` is NOT overwritten by a preview render.
- [ ] Run a full render immediately after a preview render. Confirm `output.mp4`
  is created/updated correctly.
- [ ] Test a project that is already 480p or smaller — confirm preview mode does
  NOT upscale but renders at the original resolution.
- [ ] Confirm subtitles are visible in the preview output.
- [ ] Confirm logo watermark is visible in the preview output (if enabled).

### 5.3 Regression Tests

- [ ] Existing tests that call `render_project()` without `preview_mode` still pass.
- [ ] `fast_render_segments()` without `preview_mode` still produces identical
  output to pre-change behavior.
- [ ] `FFmpegFrameWriter` without `preview_mode` still uses the same FFmpeg command
  as before (verify with `_build_command()` test).

---

## 6. Notes for AI Agent

### 6.1 Finding the FFmpegFrameWriter Instantiation in `fast_render_segments()`

The writer is created near the bottom of `fast_render_segments()`.  Search for
`FFmpegFrameWriter(` in `backend/core_engine/fast_compositor.py` — there should
be exactly one instantiation site in that function body.  Pass
`preview_mode=preview_mode` there.

### 6.2 `render_utils.get_output_path()` Exact Signature

Before modifying it, read `backend/core_engine/render_utils.py` to identify
the exact signature and implementation.  The function likely constructs a
`media/projects/<project_id>/output.mp4` path.  Only change the hardcoded
`"output.mp4"` to be the `filename` parameter — do not alter the directory
construction logic.

### 6.3 Aspect-Ratio-Preserving Downscale

The preview resolution calculation in Step 3.3 Change 2 uses:

```python
scale = min(PREVIEW_MAX_WIDTH / res_width, PREVIEW_MAX_HEIGHT / res_height, 1.0)
```

This ensures portrait (9:16), landscape (16:9), and square projects all stay
within the 854×480 box while preserving their aspect ratio.  The final
even-number enforcement (`res_width - 1` if odd) is required by libx264's
`yuv420p` pixel format which requires even dimensions.

### 6.4 Why NVENC Is Disabled in Preview Mode

NVENC initialization overhead (session startup, memory allocation) is
non-trivial and only pays off for large encodes.  For short 480p/15fps previews
the overhead is not justified.  libx264 `ultrafast` is faster in this case.
The guard `use_nvenc=False if preview_mode else use_nvenc` in the
`FFmpegFrameWriter` call handles this.

### 6.5 Task Kwargs Propagation

In Celery, task kwargs must be JSON-serializable.  `preview_mode` is a `bool`,
which is JSON-serializable.  No additional serialization configuration is needed.

### 6.6 Do Not Modify Any Existing Default Arguments

All new parameters (`preview_mode`) default to `False`.  This guarantees zero
behavioral change for all existing callers that do not explicitly pass the flag.
No existing call sites need to be updated unless they want preview behavior.

### 6.7 Step Order

Implement in this order to avoid import errors during testing:
1. `render_utils.py` (Step 3.4) — no dependencies
2. `fast_compositor.py` (Steps 3.1, 3.2) — no Django dependency
3. `video_renderer.py` (Step 3.3) — depends on fast_compositor and render_utils
4. `tasks.py` (Step 3.5) — depends on video_renderer
5. `views.py` (Step 3.6) — depends on tasks
