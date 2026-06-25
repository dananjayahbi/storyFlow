# Feature 5.4 — Two-Pass Encoding Mode

> **Status:** Planned  
> **Category:** Core Engine / Video Export Quality  
> **Primary Files:** `backend/core_engine/video_renderer.py`, `backend/api/models.py`, `backend/api/serializers.py`, `frontend/types/settings.ts`, `frontend/components/RenderSettingsForm.tsx`  
> **Estimated Complexity:** Medium  
> **Impact:** Enables consistent quality distribution across the entire video, especially valuable for mixed-motion content (transitions + static Ken Burns)  
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

StoryFlow currently renders video using **single-pass CRF encoding**
via libx264 or single-pass VBR via NVENC.  The encoding pipeline lives
in `FFmpegFrameWriter` inside `backend/core_engine/fast_compositor.py`
(839 lines total, class at lines 365–480).

The current encoding path works as follows:

1. **FFmpegFrameWriter.__init__()** (lines 381–398):
   Accepts `output_path`, `width`, `height`, `fps`, optional
   `audio_path`, `use_nvenc` flag, and `bitrate` (default `"8M"`).

2. **FFmpegFrameWriter._build_command()** (lines 400–455):
   Builds the FFmpeg command.  Two branches exist:

   - **NVENC** (GPU): Uses `h264_nvenc` with `preset p4`, `tune hq`,
     VBR rate control (`-rc vbr`), constant quality `-cq 23`, target
     bitrate `-b:v 8M`, maxrate `12M`, bufsize `16M`, profile `high`.

   - **CPU (libx264)**: Uses `libx264` with `preset fast`, `tune film`,
     **CRF 23**, profile `high`.  No target bitrate is specified — the
     encoder uses CRF as the sole quality metric.

   Both branches append `-pix_fmt yuv420p`, `-movflags +faststart`, and
   the output path.

3. **Frame piping** (lines 459–480):
   Frames are written one at a time via `write_frame()` which pipes raw
   RGB bytes to FFmpeg's stdin.  `finish()` closes stdin and waits for
   FFmpeg to complete.  Because frames are streamed once via a pipe,
   they **cannot be replayed** — this is the fundamental obstacle to
   traditional in-line two-pass encoding.

4. **fast_render_segments()** (line 487+):
   Orchestrates the full render: builds a timeline of segments, applies
   Ken Burns zoom + subtitles + logo + crossfade, and streams each
   composited frame to `FFmpegFrameWriter`.

5. **render_project()** in `video_renderer.py` (line 582+, 1218 lines total):
   - Loads project settings from the database (lines 618–710).
   - Calls `fast_render_segments()` at lines 1008–1063.
   - Optionally appends an outro video at lines 1068–1118.
   - Verifies output and returns result dict at lines 1130–1200.

6. **Data models** (`backend/api/models.py`, 279 lines):
   - `Project` model (line 35): Has `resolution_width`,
     `resolution_height`, `framerate`, and various render settings.
     **No `two_pass_encoding` field exists.**
   - `GlobalSettings` model (line 200): Singleton defaults for new
     projects.  Has render dimensions, fps, and other settings.
     **No `two_pass_encoding` field exists.**

**Why single-pass CRF is suboptimal for StoryFlow content:**

- **Mixed-motion content:** StoryFlow videos combine high-motion
  crossfade transitions (many pixels changing per frame) with slow Ken
  Burns panning (minimal inter-frame change).  CRF allocates bits
  reactively — it over-allocates to static segments and can under-
  allocate during transitions when the encoder encounters a sudden
  spike in motion.

- **Inconsistent file sizes:** CRF produces unpredictable file sizes
  because the encoder has no global view of the video's complexity
  distribution. A 60-second video might be 30 MB or 90 MB depending
  on content.

- **Professional distribution:** YouTube, Vimeo, and social platforms
  recommend VBR encoding with a target bitrate for consistent upload
  quality.  Two-pass VBR is the industry standard for final delivery.

- **Quality valleys:** The single-pass encoder can't anticipate an
  upcoming complex scene.  In a StoryFlow video, the crossfade
  transition frames may use a disproportionate share of the CRF
  budget, leaving subsequent Ken Burns frames at lower quality.

### 1.2 Proposed Solution

Add an **optional two-pass VBR encoding mode** that re-encodes the
rendered output for optimal bitrate distribution.  The approach is a
**post-render re-encode** strategy:

1. **Pass 1 (analysis):** Run FFmpeg on the CRF-encoded file with
   `-pass 1 -f null NUL` to generate a statistics log file.

2. **Pass 2 (final encode):** Run FFmpeg again on the same CRF file
   with `-pass 2` and a target bitrate to produce the final output
   with optimal bitrate allocation.

3. **Replace:** Swap the CRF file with the two-pass output.

This is the **recommended approach** because:

- The existing render pipeline (`fast_render_segments()` and
  `FFmpegFrameWriter`) requires **zero changes**.  Frames are still
  piped to FFmpeg in a single pass as before.

- Two-pass re-encode from an intermediate file is straightforward
  FFmpeg usage — the input is a regular MP4, not a pipe.

- The CRF intermediate file provides high-quality source material
  for the re-encode.  The quality loss from double-encoding at
  high bitrates is negligible (< 0.5 dB PSNR).

- **NVENC does not support true two-pass encoding** at the FFmpeg
  level, so this feature only applies to CPU (libx264) renders.
  When NVENC is in use, the two-pass flag is silently ignored.

### 1.3 Scope

| In Scope | Out of Scope |
|----------|-------------|
| `two_pass_encoding` BooleanField on `Project` and `GlobalSettings` | Multi-codec support (H.265, AV1, VP9) |
| Serializer fields and validation | Hardware-accelerated two-pass (NVENC) |
| `_two_pass_reencode()` function in `video_renderer.py` | Configurable target bitrate per project |
| Call after `fast_render_segments()` in `render_project()` | Real-time encoding preview |
| Progress reporting during re-encode phases | CRF quality slider (separate feature) |
| Frontend toggle in render settings | Encoding presets (fast/medium/slow) |
| Copy field in `ProjectImportSerializer` | Two-pass for outro append |
| Migration file for new model field | |

### 1.4 File Inventory

| # | File | Action | Lines Today | Est. Changes |
|---|------|--------|-------------|-------------|
| 1 | `backend/api/models.py` | MODIFY | 279 | +4 lines (2 fields) |
| 2 | `backend/api/serializers.py` | MODIFY | 488 | +6 lines (3 locations) |
| 3 | `backend/core_engine/video_renderer.py` | MODIFY | 1218 | +95 lines |
| 4 | `backend/api/migrations/NNNN_add_two_pass_encoding.py` | CREATE | — | ~25 lines |
| 5 | `frontend/types/settings.ts` | MODIFY | 68 | +3 lines |
| 6 | `frontend/components/RenderSettingsForm.tsx` | MODIFY | ~180 | +30 lines |
| 7 | `frontend/components/GlobalSettingsPanel.tsx` | VERIFY | ~350 | 0 (auto-propagates) |

---

## 2. Flow Diagram

### 2.1 Current Render Flow (Single-Pass CRF)

```
┌──────────────────────────────────────────────────────────────────────┐
│                       render_project()                                │
│                     video_renderer.py L582                            │
│                                                                      │
│  ┌─────────────┐    ┌────────────────────┐    ┌──────────────────┐   │
│  │ Load Project │───►│ Build Segment Data │───►│ Mix Audio (WAV)  │   │
│  │  from DB     │    │ + Validate         │    │ with Crossfade   │   │
│  └─────────────┘    └────────────────────┘    └────────┬─────────┘   │
│                                                         │             │
│                                            ┌────────────▼──────────┐ │
│                                            │ fast_render_segments() │ │
│                                            │ fast_compositor.py     │ │
│                                            │                        │ │
│                                            │ ┌────────────────────┐ │ │
│                                            │ │ FFmpegFrameWriter  │ │ │
│                                            │ │ • Single-pass CRF  │ │ │
│                                            │ │ • Pipe raw frames  │ │ │
│                                            │ │ • Output: final.mp4│ │ │
│                                            │ └────────────────────┘ │ │
│                                            └────────────┬──────────┘ │
│                                                         │             │
│                                            ┌────────────▼──────────┐ │
│                                            │ Append Outro (opt.)   │ │
│                                            └────────────┬──────────┘ │
│                                                         │             │
│                                            ┌────────────▼──────────┐ │
│                                            │ Verify + Return       │ │
│                                            └───────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

### 2.2 New Render Flow (With Two-Pass Re-Encode)

```
┌──────────────────────────────────────────────────────────────────────┐
│                       render_project()                                │
│                     video_renderer.py L582                            │
│                                                                      │
│  ┌─────────────┐    ┌────────────────────┐    ┌──────────────────┐   │
│  │ Load Project │───►│ Build Segment Data │───►│ Mix Audio (WAV)  │   │
│  │  from DB     │    │ + Validate         │    │ with Crossfade   │   │
│  │              │    │                    │    │                  │   │
│  │ NEW: Read    │    │                    │    │                  │   │
│  │ two_pass_    │    │                    │    │                  │   │
│  │ encoding     │    │                    │    │                  │   │
│  └─────────────┘    └────────────────────┘    └────────┬─────────┘   │
│                                                         │             │
│                                            ┌────────────▼──────────┐ │
│                                            │ fast_render_segments() │ │
│                                            │ (UNCHANGED)            │ │
│                                            │ Output: output.mp4     │ │
│                                            └────────────┬──────────┘ │
│                                                         │             │
│                                            ┌────────────▼──────────┐ │
│                                            │ Append Outro (opt.)   │ │
│                                            │ (UNCHANGED)            │ │
│                                            └────────────┬──────────┘ │
│                                                         │             │
│                        ┌────────────────────────────────▼───────┐    │
│                        │ NEW: if two_pass_encoding AND NOT nvenc │    │
│                        │                                         │    │
│                        │  ┌──────────────────────────────────┐   │    │
│                        │  │ _two_pass_reencode()             │   │    │
│                        │  │                                  │   │    │
│                        │  │  Pass 1: ffmpeg -i output.mp4    │   │    │
│                        │  │          -c:v libx264             │   │    │
│                        │  │          -b:v 10M -pass 1         │   │    │
│                        │  │          -f null NUL              │   │    │
│                        │  │                                  │   │    │
│                        │  │  Pass 2: ffmpeg -i output.mp4    │   │    │
│                        │  │          -c:v libx264             │   │    │
│                        │  │          -b:v 10M -pass 2         │   │    │
│                        │  │          output_2pass.mp4         │   │    │
│                        │  │                                  │   │    │
│                        │  │  Replace: mv output_2pass.mp4    │   │    │
│                        │  │           → output.mp4            │   │    │
│                        │  │                                  │   │    │
│                        │  │  Cleanup: rm ffmpeg2pass-*.log   │   │    │
│                        │  └──────────────────────────────────┘   │    │
│                        └────────────────────────────────────────┘    │
│                                                         │             │
│                                            ┌────────────▼──────────┐ │
│                                            │ Verify + Return       │ │
│                                            └───────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

### 2.3 Two-Pass Re-Encode Internals

```
                 _two_pass_reencode(input_path, on_progress)
                 ─────────────────────────────────────────────
                                    │
                                    ▼
                 ┌──────────────────────────────────┐
                 │  1. Probe input duration          │
                 │     ffprobe -v error ...          │
                 │     → total_duration (float)      │
                 └──────────────┬───────────────────┘
                                │
                                ▼
                 ┌──────────────────────────────────┐
                 │  2. Calculate target bitrate      │
                 │     Based on resolution:          │
                 │     • 720p  →  5M                 │
                 │     • 1080p → 10M                 │
                 │     • 4K    → 35M                 │
                 │     maxrate = bitrate × 1.5       │
                 │     bufsize = bitrate × 2.0       │
                 └──────────────┬───────────────────┘
                                │
                                ▼
                 ┌──────────────────────────────────┐
                 │  3. Create temp directory         │
                 │     (for pass log files)          │
                 │     passlogfile = tmpdir/ffmpeg2p  │
                 └──────────────┬───────────────────┘
                                │
                                ▼
                 ┌──────────────────────────────────┐
                 │  4. PASS 1 — Analysis             │
                 │                                   │
                 │  ffmpeg -y                         │
                 │    -i {input_path}                 │
                 │    -c:v libx264                    │
                 │    -preset medium                  │
                 │    -b:v {bitrate}                  │
                 │    -maxrate {maxrate}              │
                 │    -bufsize {bufsize}              │
                 │    -pass 1                         │
                 │    -passlogfile {passlogfile}       │
                 │    -an                             │
                 │    -f null NUL                     │
                 │                                   │
                 │  on_progress(88, 100,              │
                 │    "Two-pass encode: pass 1…")     │
                 │                                   │
                 │  Wait for completion               │
                 │  Check return code                 │
                 └──────────────┬───────────────────┘
                                │
                       Pass 1 succeeded?
                         │           │
                        YES          NO → log warning,
                         │                 return False
                         ▼                 (keep CRF file)
                 ┌──────────────────────────────────┐
                 │  5. PASS 2 — Final Encode         │
                 │                                   │
                 │  ffmpeg -y                         │
                 │    -i {input_path}                 │
                 │    -c:v libx264                    │
                 │    -preset medium                  │
                 │    -tune film                      │
                 │    -b:v {bitrate}                  │
                 │    -maxrate {maxrate}              │
                 │    -bufsize {bufsize}              │
                 │    -pass 2                         │
                 │    -passlogfile {passlogfile}       │
                 │    -c:a copy                       │
                 │    -movflags +faststart            │
                 │    {output_2pass_path}              │
                 │                                   │
                 │  on_progress(94, 100,              │
                 │    "Two-pass encode: pass 2…")     │
                 │                                   │
                 │  Wait for completion               │
                 │  Check return code                 │
                 └──────────────┬───────────────────┘
                                │
                       Pass 2 succeeded?
                         │           │
                        YES          NO → log warning,
                         │                 cleanup temp,
                         ▼                 return False
                 ┌──────────────────────────────────┐
                 │  6. Replace original               │
                 │     os.replace(output_2pass, input) │
                 └──────────────┬───────────────────┘
                                │
                                ▼
                 ┌──────────────────────────────────┐
                 │  7. Cleanup temp directory        │
                 │     shutil.rmtree(tmpdir)         │
                 └──────────────┬───────────────────┘
                                │
                                ▼
                 ┌──────────────────────────────────┐
                 │  8. Return True                   │
                 │     on_progress(96, 100,           │
                 │       "Two-pass encode complete")  │
                 └──────────────────────────────────┘
```

---

## 3. Step-by-Step Instructions

### Step 3.1 — Add `two_pass_encoding` Field to `Project` Model

**File:** `backend/api/models.py`  
**Location:** After the `upscale_denoise_strength` field (around line 116)

Add a new BooleanField to the `Project` model:

```python
    # ── Two-pass encoding ──
    two_pass_encoding = models.BooleanField(default=False)
```

**Placement rationale:** Group it with other render-quality settings
(upscale fields are directly above).  The field defaults to `False` so
existing projects are unaffected.

**After this change**, the `Project` model will have these render-related
fields (in order):

```
zoom_intensity          FloatField    1.3
ken_burns_zoom          FloatField    1.2
transition_duration     FloatField    0.5
upscale_enabled         BooleanField  False
upscale_model           CharField     'RealESRGAN_x4plus'
upscale_denoise_strength FloatField   0.5
two_pass_encoding       BooleanField  False   ← NEW
```

### Step 3.2 — Add `two_pass_encoding` Field to `GlobalSettings` Model

**File:** `backend/api/models.py`  
**Location:** After the `upscale_denoise_strength` field in
`GlobalSettings` (around line 265)

Add the same field to the singleton settings model:

```python
    # ── Two-pass encoding ──
    two_pass_encoding = models.BooleanField(default=False)
```

This ensures new projects copy the global default.

### Step 3.3 — Create Database Migration

**Run:**

```bash
cd backend
python manage.py makemigrations api -n "add_two_pass_encoding"
```

This will generate a migration file at
`backend/api/migrations/NNNN_add_two_pass_encoding.py` with two
`AddField` operations (one for `Project`, one for `GlobalSettings`).

**Verify** the auto-generated migration, then apply:

```bash
python manage.py migrate
```

### Step 3.4 — Add Serializer Fields

**File:** `backend/api/serializers.py`

Three locations need updating:

#### 3.4.1 — GlobalSettingsSerializer (around line 87)

Add `'two_pass_encoding'` to the `fields` list in the `Meta` class:

```python
class GlobalSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = GlobalSettings
        fields = [
            'default_voice_id', 'tts_speed',
            'subtitle_font_family', 'subtitle_font_size',
            'subtitle_font_color', 'subtitle_position',
            'subtitle_y_position',
            'subtitle_font', 'subtitle_color',
            'render_width', 'render_height', 'render_fps',
            'ken_burns_zoom', 'transition_duration', 'zoom_intensity',
            'inter_segment_silence', 'subtitles_enabled',
            'custom_font_file',
            'logo_enabled', 'active_logo', 'logo_scale',
            'logo_position', 'logo_opacity', 'logo_margin',
            'outro_enabled', 'active_outro',
            'upscale_enabled', 'upscale_model', 'upscale_denoise_strength',
            'two_pass_encoding',                                    # ← ADD
            'created_at', 'updated_at',
        ]
```

#### 3.4.2 — ProjectDetailSerializer (around line 252)

Add `'two_pass_encoding'` to the `fields` list:

```python
class ProjectDetailSerializer(serializers.ModelSerializer):
    segments = SegmentSerializer(many=True, read_only=True)

    class Meta:
        model = Project
        fields = [
            'id', 'title', 'created_at', 'updated_at',
            'status', 'resolution_width', 'resolution_height',
            'framerate', 'output_path', 'segments',
            # ── Per-project settings ──
            'default_voice_id', 'tts_speed',
            'subtitle_font_family', 'subtitle_font_size',
            'subtitle_font_color', 'subtitle_position',
            'subtitle_y_position',
            'subtitle_font', 'subtitle_color',
            'subtitles_enabled', 'custom_font_file',
            'zoom_intensity', 'ken_burns_zoom', 'transition_duration',
            'inter_segment_silence',
            'logo_enabled', 'active_logo', 'logo_scale',
            'logo_position', 'logo_opacity', 'logo_margin',
            'outro_enabled', 'active_outro',
            'upscale_enabled', 'upscale_model', 'upscale_denoise_strength',
            'two_pass_encoding',                                    # ← ADD
        ]
```

#### 3.4.3 — ProjectImportSerializer.create() (around line 440)

In the `create()` method that copies GlobalSettings to a new Project,
add the field copy:

```python
        project = Project.objects.create(
            title=parsed['title'],
            status='DRAFT',
            # ... existing field copies ...
            upscale_enabled=gs.upscale_enabled,
            upscale_model=gs.upscale_model,
            upscale_denoise_strength=gs.upscale_denoise_strength,
            two_pass_encoding=gs.two_pass_encoding,                 # ← ADD
        )
```

### Step 3.5 — Implement `_two_pass_reencode()` in `video_renderer.py`

**File:** `backend/core_engine/video_renderer.py`  
**Location:** Add as a new module-level function, after the existing
`_append_outro()` function (or similar helper) and before
`render_project()`.

```python
# ---------------------------------------------------------------------------
# Two-pass VBR re-encode (Feature 5.4)
# ---------------------------------------------------------------------------

def _get_target_bitrate(width: int, height: int) -> str:
    """Return a target bitrate string for two-pass encoding based on resolution."""
    pixels = width * height
    if pixels >= 3840 * 2160:       # 4K
        return "35M"
    elif pixels >= 1920 * 1080:     # 1080p
        return "10M"
    elif pixels >= 1280 * 720:      # 720p
        return "5M"
    else:
        return "3M"


def _two_pass_reencode(
    input_path: str,
    width: int,
    height: int,
    on_progress: Optional[Callable[[int, int, str], None]] = None,
) -> bool:
    """Re-encode a video file using two-pass VBR for optimal quality.

    This function:
    1. Probes the input duration.
    2. Runs FFmpeg pass 1 (analysis → stats log file).
    3. Runs FFmpeg pass 2 (final encode using stats).
    4. Replaces the original file with the two-pass output.
    5. Cleans up temporary files.

    Args:
        input_path: Absolute path to the single-pass rendered MP4.
        width:      Video width in pixels (for bitrate calculation).
        height:     Video height in pixels (for bitrate calculation).
        on_progress: Optional progress callback ``(current, total, msg)``.

    Returns:
        ``True`` if re-encode succeeded and original was replaced.
        ``False`` if any step failed (original file is preserved).
    """
    import shutil
    import tempfile

    logger.info("Two-pass re-encode starting: %s", input_path)

    # ── 1. Probe input duration ──
    duration = _probe_duration(input_path)
    if duration is None or duration <= 0:
        logger.warning("Could not probe duration for two-pass re-encode")
        return False

    # ── 2. Calculate target bitrate ──
    bitrate = _get_target_bitrate(width, height)
    # maxrate and bufsize as multiples of target
    bitrate_num = int(bitrate.rstrip("M"))
    maxrate = f"{int(bitrate_num * 1.5)}M"
    bufsize = f"{int(bitrate_num * 2)}M"

    logger.info(
        "Two-pass params: bitrate=%s, maxrate=%s, bufsize=%s, duration=%.2fs",
        bitrate, maxrate, bufsize, duration,
    )

    # ── 3. Create temp directory for pass log files ──
    tmpdir = tempfile.mkdtemp(prefix="storyflow_2pass_")
    passlogfile = os.path.join(tmpdir, "ffmpeg2pass")
    output_2pass = os.path.join(tmpdir, "output_2pass.mp4")

    try:
        # ── 4. PASS 1 — Analysis ──
        if on_progress:
            on_progress(88, 100, "Two-pass encode: analyzing (pass 1)…")

        null_output = "NUL" if os.name == "nt" else "/dev/null"

        pass1_cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-c:v", "libx264",
            "-preset", "medium",
            "-tune", "film",
            "-b:v", bitrate,
            "-maxrate", maxrate,
            "-bufsize", bufsize,
            "-pass", "1",
            "-passlogfile", passlogfile,
            "-an",
            "-f", "null",
            null_output,
        ]

        logger.info("Pass 1 cmd: %s", " ".join(pass1_cmd))
        result1 = subprocess.run(
            pass1_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        if result1.returncode != 0:
            stderr = result1.stderr.decode("utf-8", errors="replace")
            logger.warning(
                "Two-pass pass 1 failed (rc=%d): %s",
                result1.returncode, stderr[-500:],
            )
            return False

        logger.info("Pass 1 completed successfully")

        # ── 5. PASS 2 — Final Encode ──
        if on_progress:
            on_progress(92, 100, "Two-pass encode: encoding (pass 2)…")

        pass2_cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-c:v", "libx264",
            "-preset", "medium",
            "-tune", "film",
            "-b:v", bitrate,
            "-maxrate", maxrate,
            "-bufsize", bufsize,
            "-pass", "2",
            "-passlogfile", passlogfile,
            "-profile:v", "high",
            "-c:a", "copy",
            "-movflags", "+faststart",
            output_2pass,
        ]

        logger.info("Pass 2 cmd: %s", " ".join(pass2_cmd))
        result2 = subprocess.run(
            pass2_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        if result2.returncode != 0:
            stderr = result2.stderr.decode("utf-8", errors="replace")
            logger.warning(
                "Two-pass pass 2 failed (rc=%d): %s",
                result2.returncode, stderr[-500:],
            )
            return False

        logger.info("Pass 2 completed successfully")

        # ── 6. Verify output exists and has size ──
        if not os.path.exists(output_2pass):
            logger.warning("Two-pass output file not found: %s", output_2pass)
            return False

        two_pass_size = os.path.getsize(output_2pass)
        if two_pass_size < 1024:
            logger.warning(
                "Two-pass output suspiciously small: %d bytes", two_pass_size,
            )
            return False

        # ── 7. Replace original with two-pass output ──
        original_size = os.path.getsize(input_path)
        os.replace(output_2pass, input_path)

        logger.info(
            "Two-pass re-encode complete: %s → %s (%.1f MB → %.1f MB)",
            os.path.basename(input_path),
            os.path.basename(input_path),
            original_size / (1024 * 1024),
            two_pass_size / (1024 * 1024),
        )

        if on_progress:
            on_progress(96, 100, "Two-pass encode complete")

        return True

    except Exception as exc:
        logger.warning("Two-pass re-encode failed with exception: %s", exc)
        return False

    finally:
        # ── 8. Cleanup temp directory ──
        try:
            if os.path.isdir(tmpdir):
                shutil.rmtree(tmpdir)
                logger.debug("Cleaned up two-pass temp dir: %s", tmpdir)
        except OSError as err:
            logger.debug("Could not remove two-pass temp dir: %s", err)
```

### Step 3.6 — Call `_two_pass_reencode()` in `render_project()`

**File:** `backend/core_engine/video_renderer.py`  
**Location:** Inside `render_project()`, after `fast_render_segments()`
and `_append_outro()`, but **before** the "Verify output" section.

#### 3.6.1 — Read the `two_pass_encoding` setting

After loading zoom intensity and other settings (around line 660), add:

```python
    # ------------------------------------------------------------------
    # C4. Read two-pass encoding setting from Project
    # ------------------------------------------------------------------
    two_pass_encoding = getattr(project, "two_pass_encoding", False)
    logger.info("Two-pass encoding: %s", two_pass_encoding)
```

#### 3.6.2 — Insert re-encode step after outro append

After the outro append block (section I, around line 1118) and before
the "Verify output" block (section K, around line 1130), add:

```python
        # --------------------------------------------------------------
        # J. Two-pass VBR re-encode (Feature 5.4)
        # --------------------------------------------------------------
        two_pass_applied = False
        if two_pass_encoding and not use_nvenc:
            if on_progress:
                on_progress(87, 100, "Starting two-pass re-encode…")

            two_pass_applied = _two_pass_reencode(
                input_path=output_path,
                width=res_width,
                height=res_height,
                on_progress=on_progress,
            )

            if two_pass_applied:
                logger.info("Two-pass VBR re-encode applied successfully")
            else:
                warnings.append(
                    "Two-pass re-encode was requested but failed. "
                    "The single-pass CRF output was kept."
                )
                logger.warning(
                    "Two-pass re-encode failed; keeping CRF output"
                )
        elif two_pass_encoding and use_nvenc:
            logger.info(
                "Two-pass encoding requested but NVENC is active; "
                "skipping (NVENC does not support FFmpeg two-pass)."
            )
            warnings.append(
                "Two-pass encoding is not available with GPU (NVENC) "
                "rendering and was skipped."
            )
```

#### 3.6.3 — Include in result dict

In the result dict construction (section N, around line 1190), add
`two_pass_applied`:

```python
        result = {
            "output_path": output_path,
            "duration": total_duration,
            "expected_duration": total_duration,
            "num_transitions": max(len(segment_data_list) - 1, 0),
            "file_size": file_size,
            "warnings": warnings,
            "render_stats": render_stats,
            "two_pass_applied": two_pass_applied,                   # ← ADD
        }
```

### Step 3.7 — Update Frontend Types

**File:** `frontend/types/settings.ts`

Add the new field to the `GlobalSettings` interface:

```typescript
export interface GlobalSettings {
  // ... existing fields ...

  /** Whether to use two-pass VBR encoding for higher quality (CPU only). */
  two_pass_encoding: boolean;
}
```

### Step 3.8 — Add Toggle to RenderSettingsForm

**File:** `frontend/components/RenderSettingsForm.tsx`

Add a toggle switch for two-pass encoding below the framerate selector.

```tsx
{/* Two-Pass Encoding Toggle */}
<div className="space-y-1.5">
  <div className="flex items-center justify-between">
    <div className="space-y-0.5">
      <label className="text-xs text-muted-foreground font-medium">
        Two-Pass Encoding
      </label>
      <p className="text-[10px] text-muted-foreground">
        Higher quality VBR encoding (CPU only, slower render)
      </p>
    </div>
    <label className="flex items-center gap-2 cursor-pointer">
      <span className="text-xs text-muted-foreground">
        {twoPassEncoding ? 'On' : 'Off'}
      </span>
      <input
        type="checkbox"
        checked={twoPassEncoding}
        onChange={(e) => onChange({ two_pass_encoding: e.target.checked })}
        className="h-4 w-4 rounded border-muted-foreground accent-primary cursor-pointer"
      />
    </label>
  </div>
</div>
```

The `RenderSettingsForm` component receives its values from the parent
via props.  Add `twoPassEncoding` to the props interface:

```typescript
interface RenderSettingsFormProps {
  zoomIntensity: number;
  renderWidth: number;
  renderHeight: number;
  renderFps: number;
  twoPassEncoding?: boolean;                    // ← ADD
  onChange: (update: Record<string, unknown>) => void;
}
```

### Step 3.9 — Propagate in GlobalSettingsPanel

**File:** `frontend/components/GlobalSettingsPanel.tsx`

The `GlobalSettingsPanel` already passes all settings from the store to
`RenderSettingsForm`.  Ensure the new prop is passed:

```tsx
<RenderSettingsForm
  zoomIntensity={settings.zoom_intensity}
  renderWidth={settings.render_width ?? 1920}
  renderHeight={settings.render_height ?? 1080}
  renderFps={settings.render_fps ?? 30}
  twoPassEncoding={settings.two_pass_encoding ?? false}   // ← ADD
  onChange={handleSettingsChange}
/>
```

### Step 3.10 — Propagate in Project Editor Sidebar

The project editor sidebar (`frontend/app/projects/[id]/page.tsx`) also
renders `RenderSettingsForm` via the settings panel.  The same prop
propagation from Step 3.9 applies — the `GlobalSettingsPanel` component
handles both locations.  No additional changes are needed if the panel
component is reused.

---

## 4. Expected Outcome

### 4.1 Backend Behavior

| Scenario | Behavior |
|----------|----------|
| `two_pass_encoding = False` (default) | No change. Single-pass CRF as before. |
| `two_pass_encoding = True`, CPU render | After `fast_render_segments()` and optional outro, `_two_pass_reencode()` runs. Video is re-encoded with optimal bitrate distribution. |
| `two_pass_encoding = True`, NVENC active | Two-pass is **skipped** with a warning. NVENC VBR output is kept. |
| Two-pass pass 1 fails | Warning logged. Original CRF file is preserved. Render succeeds with degraded quality. |
| Two-pass pass 2 fails | Warning logged. Temp files cleaned up. Original CRF file is preserved. |

### 4.2 Quality Improvement

For a typical 10-segment StoryFlow video at 1080p with crossfade
transitions:

| Metric | Single-Pass CRF | Two-Pass VBR |
|--------|-----------------|-------------|
| File size predictability | Variable (CRF-dependent) | Consistent (~10 Mbps target) |
| Transition quality | May have banding | Smooth, consistent |
| Static segment quality | Over-allocated bits | Optimal allocation |
| Total file size (60s) | ~30–90 MB | ~75 MB (±10%) |
| Encode time | 1× | ~2.5× (analysis + re-encode) |

### 4.3 Frontend Behavior

- **Settings panel:** New toggle under "Render Settings" section,
  below the framerate selector.
- **Label:** "Two-Pass Encoding"
- **Description:** "Higher quality VBR encoding (CPU only, slower render)"
- **Default state:** Off (unchecked)
- **Persistence:** Saved to `GlobalSettings` via existing PATCH endpoint.
- **Per-project:** Copied to `Project` on creation from global defaults.

### 4.4 Render Progress Updates

When two-pass is active, progress messages will appear:

| Progress % | Message |
|------------|---------|
| 87% | "Starting two-pass re-encode…" |
| 88% | "Two-pass encode: analyzing (pass 1)…" |
| 92% | "Two-pass encode: encoding (pass 2)…" |
| 96% | "Two-pass encode complete" |
| 98% | "Verifying output file…" |
| 100% | "Render complete!" |

### 4.5 API Response

The render result dict gains a new key:

```json
{
  "output_path": "projects/<uuid>/final.mp4",
  "duration": 62.5,
  "file_size": 78643200,
  "render_stats": { ... },
  "two_pass_applied": true,
  "warnings": []
}
```

If two-pass was requested but failed:

```json
{
  "two_pass_applied": false,
  "warnings": [
    "Two-pass re-encode was requested but failed. The single-pass CRF output was kept."
  ]
}
```

---

## 5. Verification Checklist

### 5.1 Model & Migration

- [ ] `Project` model has `two_pass_encoding = models.BooleanField(default=False)`
- [ ] `GlobalSettings` model has `two_pass_encoding = models.BooleanField(default=False)`
- [ ] Migration file created and applies without errors
- [ ] `python manage.py migrate` runs successfully
- [ ] Existing projects have `two_pass_encoding = False` after migration

### 5.2 Serializers

- [ ] `GlobalSettingsSerializer.Meta.fields` includes `'two_pass_encoding'`
- [ ] `ProjectDetailSerializer.Meta.fields` includes `'two_pass_encoding'`
- [ ] `GET /api/settings/` returns `two_pass_encoding` field
- [ ] `PATCH /api/settings/` accepts `{"two_pass_encoding": true}`
- [ ] `GET /api/projects/<id>/` returns `two_pass_encoding` field
- [ ] `PATCH /api/projects/<id>/` accepts `{"two_pass_encoding": true}`
- [ ] `ProjectImportSerializer.create()` copies `two_pass_encoding` from GlobalSettings

### 5.3 Two-Pass Re-Encode Function

- [ ] `_get_target_bitrate()` returns correct bitrate for 720p, 1080p, 4K
- [ ] `_two_pass_reencode()` exists in `video_renderer.py`
- [ ] Pass 1 uses `-pass 1 -f null NUL` (Windows) or `-f null /dev/null` (Linux)
- [ ] Pass 2 uses `-pass 2 -c:a copy -movflags +faststart`
- [ ] Both passes use `-preset medium -tune film`
- [ ] Temp directory is created and cleaned up (even on failure)
- [ ] Pass log files use a temp directory (not cwd)
- [ ] `os.replace()` atomically replaces the original file
- [ ] Returns `True` on success, `False` on any failure
- [ ] Original CRF file is **preserved** when two-pass fails

### 5.4 Integration in render_project()

- [ ] `two_pass_encoding` is read from the project instance
- [ ] Two-pass block runs **after** `fast_render_segments()` and `_append_outro()`
- [ ] Two-pass block runs **before** "Verify output" section
- [ ] Two-pass is **skipped** when `use_nvenc = True`
- [ ] NVENC skip produces an appropriate warning message
- [ ] `two_pass_applied` is included in the result dict
- [ ] Progress callbacks fire at 87%, 88%, 92%, 96%

### 5.5 End-to-End Render Tests

- [ ] Render with `two_pass_encoding = False` → same behavior as before
- [ ] Render with `two_pass_encoding = True`, CPU → output is two-pass encoded
- [ ] Two-pass output has consistent bitrate (verify with `ffprobe -show_format`)
- [ ] Two-pass output plays correctly in VLC, Chrome, and QuickTime
- [ ] Two-pass output has `+faststart` flag (`moov` atom at beginning)
- [ ] Audio is preserved correctly (`-c:a copy`)
- [ ] File size is within expected range for target bitrate
- [ ] Render with `two_pass_encoding = True`, NVENC → warning, VBR output

### 5.6 Frontend

- [ ] `GlobalSettings` type includes `two_pass_encoding: boolean`
- [ ] Toggle appears in Render Settings section of settings panel
- [ ] Toggle correctly reads from and writes to settings store
- [ ] Toggle is labeled "Two-Pass Encoding" with descriptive text
- [ ] Changing toggle calls `PATCH /api/settings/` with correct payload
- [ ] New projects created after enabling toggle have `two_pass_encoding = True`

### 5.7 Edge Cases

- [ ] Very short video (< 2 seconds) — two-pass still works
- [ ] Very long video (> 10 minutes) — two-pass completes without timeout
- [ ] Disk full during pass 2 — fails gracefully, original preserved
- [ ] FFmpeg not found — handled upstream (render_project already checks)
- [ ] Concurrent renders — temp directories are unique (tempfile.mkdtemp)
- [ ] Interrupted render (SIGTERM) — temp files may remain (acceptable)

---

## 6. Notes for AI Agent

### 6.1 Critical Implementation Details

1. **Do NOT modify `FFmpegFrameWriter` or `fast_render_segments()`.**
   The two-pass feature is a *post-processing* step that runs on the
   already-completed output file.  The existing piped-frame pipeline
   must remain untouched.

2. **Windows vs. Linux null device:** The pass 1 output must go to
   `NUL` on Windows and `/dev/null` on Linux/Mac.  Use
   `os.name == "nt"` to detect Windows.  This is critical — using the
   wrong null device will cause FFmpeg to fail silently or create a
   file named "NUL".

3. **Pass log file location:** FFmpeg creates `ffmpeg2pass-0.log` and
   `ffmpeg2pass-0.log.mbtree` files.  These **must not** be created
   in the project output directory.  Use `tempfile.mkdtemp()` and pass
   the `-passlogfile` option pointing into the temp directory.

4. **Atomic replacement:** Use `os.replace()` (not `os.rename()` or
   `shutil.move()`) to replace the original file.  `os.replace()` is
   atomic on both Windows and POSIX and will overwrite the destination.

5. **Audio handling:** Pass 1 uses `-an` (no audio) because audio is
   irrelevant for video bitrate analysis.  Pass 2 uses `-c:a copy` to
   stream-copy the audio without re-encoding — this is lossless and
   fast.

6. **Preset choice:** Use `-preset medium` (not `fast`) for the two-
   pass encode.  Users opting into two-pass are explicitly trading speed
   for quality — `medium` provides significantly better compression
   efficiency than `fast` with only ~40% slower encoding.

7. **Graceful degradation:** If two-pass fails at any point, the
   function must return `False` and the original CRF file must be
   intact.  The render should complete successfully — two-pass failure
   is a warning, not an error.

### 6.2 Section Labels in `render_project()`

The existing `render_project()` uses letter-labeled sections:

```
A. FFmpeg availability check
B. Load project from database
C. Read resolution and framerate settings
   C2. Read zoom intensity
   C3. Read subtitle settings
D. (segment loading, etc.)
...
H. Fast render: NumPy compositing + direct FFmpeg pipe
I. Append outro video
K. Verify output and capture duration
M. Get output file size
N. Return result dict
```

Insert the two-pass block as section **J** between I and K.  Note that
`J` is currently unused (the section letters skip from I to K in the
existing code).  Add the setting read as section **C4**.

### 6.3 Import Statement Requirements

The `_two_pass_reencode()` function needs these imports (already
available in `video_renderer.py`):

- `import os` — already imported at module top
- `import subprocess` — already imported at module top
- `import logging` — already imported (`logger = logging.getLogger(...)`)

The function uses lazy imports for:
- `import shutil` — import inside the function to avoid top-level overhead
- `import tempfile` — import inside the function

### 6.4 Testing Strategy

1. **Unit test `_get_target_bitrate()`:** Verify correct bitrate strings
   for various resolution inputs.

2. **Unit test `_two_pass_reencode()`:** Mock `subprocess.run` to verify
   correct FFmpeg commands are constructed.  Test both success and
   failure paths.

3. **Integration test:** Render a 3-segment project with
   `two_pass_encoding = True` and verify:
   - Output file exists
   - `ffprobe` shows H.264 codec
   - Bitrate is within 20% of target
   - Audio stream is present and playable

4. **Regression test:** Render the same project with
   `two_pass_encoding = False` and verify output matches previous
   behavior.

### 6.5 Performance Expectations

| Resolution | Single-Pass | Two-Pass Total | Overhead |
|-----------|-------------|----------------|----------|
| 720p, 30s | ~15s | ~35s | +133% |
| 1080p, 60s | ~45s | ~110s | +144% |
| 4K, 60s | ~180s | ~450s | +150% |

The two-pass overhead is approximately 2–2.5× because:
- Pass 1 is slightly faster (no muxing, no audio)
- Pass 2 is slower than CRF (VBR rate control is more complex)

This is acceptable because users explicitly opt in to the feature and
the progress bar provides feedback during the re-encode phase.

### 6.6 Bitrate Targets Rationale

| Resolution | Target Bitrate | YouTube Recommendation | Our Target |
|-----------|---------------|----------------------|-----------|
| 720p | 5 Mbps | 5 Mbps (SDR) | Match |
| 1080p | 10 Mbps | 8 Mbps (SDR) | Slightly above |
| 4K | 35 Mbps | 35-45 Mbps (SDR) | Match low end |

Targets are set slightly above YouTube recommendations to account for
re-encoding quality loss and to ensure the upload looks pristine after
YouTube's own re-encoding.

### 6.7 Future Enhancements (Out of Scope)

These are explicitly **not** part of this feature but could build on it:

1. **Configurable target bitrate:** Let users set the target bitrate
   via a slider (e.g., 5M–50M).

2. **Preset selector:** Offer encoding presets (fast/medium/slow/veryslow)
   for the two-pass encode.

3. **H.265 two-pass:** When H.265 support is added, extend two-pass to
   `libx265` with appropriate parameters.

4. **Progress granularity:** Parse FFmpeg stderr during pass 1/2 to
   provide frame-level progress instead of coarse percentage steps.

5. **Two-pass for outro:** Currently the outro is appended via concat
   protocol before two-pass runs — so the outro IS included in the
   two-pass re-encode.  If outro append moves after two-pass, this
   would need revisiting.

### 6.8 Compatibility Notes

- **Python 3.8+:** `os.replace()` is available since Python 3.3.
- **FFmpeg 4.0+:** Two-pass encoding with `-passlogfile` is supported.
- **Windows:** `NUL` as null device.  `os.replace()` works on Windows
  since Python 3.3 (uses `MoveFileEx` with `MOVEFILE_REPLACE_EXISTING`).
- **Concurrent renders:** Each render creates its own `tempdir` via
  `tempfile.mkdtemp()`, so concurrent renders cannot interfere with
  each other's pass log files.
- **SQLite:** The new BooleanField has no special SQLite considerations.
  Default `False` is applied at the Django ORM level.

---

*End of Feature 5.4 — Two-Pass Encoding Mode*
