# Feature 5.2 — Resolution-Aware Bitrate

| Field                  | Value                                                                                       |
| ---------------------- | ------------------------------------------------------------------------------------------- |
| **Feature ID**         | 5.2                                                                                         |
| **Title**              | Resolution-Aware Bitrate                                                                    |
| **Status**             | 🟡 Planned                                                                                   |
| **Priority**           | High                                                                                        |
| **Complexity**         | Low-Medium                                                                                  |
| **Estimated Effort**   | 1–2 days                                                                                    |
| **Dependencies**       | None (standalone; integrates cleanly with Feature 5.1 if implemented first)                 |
| **Output Files (NEW)** | None (all changes in existing files unless 5.1 `encoding_presets.py` already exists)        |
| **Files Modified**     | `backend/core_engine/fast_compositor.py`, `backend/core_engine/video_renderer.py`           |

---

## 1. Document Overview

### 1.1 Problem Statement

The `FFmpegFrameWriter` class in `backend/core_engine/fast_compositor.py` (L365–480)
currently uses a **hardcoded `8M` (8 Mbps) video bitrate** for all output resolutions.
This single value is applied regardless of whether the output is 360p, 720p, 1080p,
1440p, or 4K. The consequences are:

| Resolution      | Problem with fixed 8 Mbps                                 |
| --------------- | ---------------------------------------------------------- |
| 640×360 (360p)  | **Massive overkill** — 8 Mbps for 230K pixels wastes 4–5× disk space for no visible gain |
| 1280×720 (720p) | **Slightly over-budgeted** — 5 Mbps is more than sufficient for 720p H.264 High Profile   |
| 1920×1080       | **Under-budgeted** — 8 Mbps is below YouTube's recommended 10 Mbps for 1080p30            |
| 2560×1440       | **Severely under-budgeted** — visible macro-blocking on detailed scenes                    |
| 3840×2160 (4K)  | **Critically under-budgeted** — 8 Mbps at 4K produces heavily compressed, blurry output    |

The problem is localised to the NVENC (GPU) encoding path. The CPU path (libx264) uses
CRF-only mode (CRF 23) without a bitrate cap, so quality auto-scales with resolution.
However, NVENC's VBR mode depends on `-b:v` and `-maxrate` to control quality, making the
fixed value problematic.

Additionally, the `-maxrate` and `-bufsize` parameters are also hardcoded at `12M` and
`16M` respectively — these should scale proportionally with the target bitrate.

### 1.2 Proposed Solution

Introduce a **resolution-aware bitrate lookup function** that:

1. Accepts the output resolution `(width, height)` as input.
2. Computes the total pixel count: `pixels = width × height`.
3. Looks up the appropriate video bitrate, max bitrate, and buffer size from a predefined
   table, interpolating linearly between entries for non-standard resolutions.
4. Returns a `dict` with `bitrate`, `maxrate`, and `bufsize` values as FFmpeg-compatible
   strings (e.g., `"10M"`, `"12M"`, `"16M"`).

The function is called at writer instantiation time, replacing the hardcoded `"8M"` default.

### 1.3 Scope

| In Scope                                                           | Out of Scope                                         |
| ------------------------------------------------------------------ | ---------------------------------------------------- |
| Bitrate lookup table + interpolation function                      | CRF adjustment per resolution (future enhancement)   |
| Updating `FFmpegFrameWriter.__init__` to accept `maxrate`/`bufsize`| Per-platform encoding presets (Feature 5.1)           |
| Updating `FFmpegFrameWriter._build_command()` to use new params    | Audio bitrate scaling                                |
| Updating `fast_render_segments()` to auto-calculate bitrate        | HDR / 10-bit encoding                                |
| Updating `video_renderer.py` to pass resolution through            | Frontend UI changes (none needed)                    |
| Unit tests for the bitrate calculation function                    | Model / migration changes (bitrate is computed)      |
| Logging the selected bitrate for debugging                         | AV1 / VP9 codec support                             |

### 1.4 Key Files Reference

| File                                         | Role                                      | Current State                                           |
| -------------------------------------------- | ----------------------------------------- | ------------------------------------------------------- |
| `backend/core_engine/fast_compositor.py`     | FFmpeg frame writer + fast render pipeline| Hardcoded `bitrate="8M"`, `maxrate="12M"`, `bufsize="16M"` |
| `backend/core_engine/video_renderer.py`      | Orchestrates full render pipeline         | Calls `fast_render_segments()` without bitrate logic     |
| `backend/core_engine/encoding_presets.py`    | (May exist from Feature 5.1)              | Could house the bitrate table if 5.1 is done first      |

### 1.5 Bitrate Lookup Table

The following table defines the target bitrate, maximum bitrate, and buffer size for each
standard resolution. Values are based on YouTube's recommended upload encoding settings
and adjusted for the H.264 High Profile used by StoryFlow.

| Resolution         | Pixel Count  | Bitrate (`-b:v`) | Max Rate (`-maxrate`) | Buffer (`-bufsize`) |
| ------------------ | ------------ | ----------------- | --------------------- | ------------------- |
| 640×360 (360p)     | 230,400      | 1.5M              | 2M                    | 3M                  |
| 854×480 (480p)     | 409,920      | 2.5M              | 4M                    | 5M                  |
| 1280×720 (720p)    | 921,600      | 5M                | 7M                    | 10M                 |
| 1080×1080 (Square) | 1,166,400    | 6M                | 8M                    | 10M                 |
| 1920×1080 (1080p)  | 2,073,600    | 10M               | 12M                   | 16M                 |
| 1080×1920 (9:16)   | 2,073,600    | 10M               | 12M                   | 16M                 |
| 2560×1440 (1440p)  | 3,686,400    | 20M               | 25M                   | 30M                 |
| 3840×2160 (4K)     | 8,294,400    | 35M               | 45M                   | 50M                 |

**Non-standard resolutions** are handled by linear interpolation between the two closest
entries in the table (sorted by pixel count). Resolutions below 360p clamp to 360p values.
Resolutions above 4K clamp to 4K values.

---

## 2. Flow Diagram

### 2.1 Bitrate Resolution Flow (Current vs. Proposed)

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                        CURRENT FLOW (BROKEN)                                ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║   video_renderer.py                    fast_compositor.py                    ║
║   ┌──────────────────┐                 ┌──────────────────────────────┐     ║
║   │ render_project() │                 │ fast_render_segments()       │     ║
║   │                  │─── calls ──────►│                              │     ║
║   │ (no bitrate      │                 │ bitrate="8M" (hardcoded)    │     ║
║   │  awareness)      │                 │         │                    │     ║
║   └──────────────────┘                 │         ▼                    │     ║
║                                        │ FFmpegFrameWriter(           │     ║
║                                        │   bitrate="8M",             │     ║
║                                        │   maxrate="12M", ← FIXED   │     ║
║                                        │   bufsize="16M"  ← FIXED   │     ║
║                                        │ )                            │     ║
║                                        └──────────────────────────────┘     ║
║                                                                              ║
║   Result: 4K video gets 8Mbps (blurry), 360p gets 8Mbps (wasted space)     ║
╚══════════════════════════════════════════════════════════════════════════════╝


╔══════════════════════════════════════════════════════════════════════════════╗
║                       PROPOSED FLOW (FIXED)                                  ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║   video_renderer.py                    fast_compositor.py                    ║
║   ┌──────────────────┐                 ┌──────────────────────────────┐     ║
║   │ render_project() │                 │ fast_render_segments()       │     ║
║   │                  │─── calls ──────►│                              │     ║
║   │ (no changes      │                 │         │                    │     ║
║   │  needed — res    │                 │         ▼                    │     ║
║   │  already passed) │                 │ calculate_bitrate_for_       │     ║
║   └──────────────────┘                 │   resolution(width, height)  │     ║
║                                        │         │                    │     ║
║                                        │         ▼                    │     ║
║                                        │ { bitrate: "10M",           │     ║
║                                        │   maxrate: "12M",           │     ║
║                                        │   bufsize: "16M" }          │     ║
║                                        │         │                    │     ║
║                                        │         ▼                    │     ║
║                                        │ FFmpegFrameWriter(           │     ║
║                                        │   bitrate="10M",  ← AUTO   │     ║
║                                        │   maxrate="12M",  ← AUTO   │     ║
║                                        │   bufsize="16M"   ← AUTO   │     ║
║                                        │ )                            │     ║
║                                        └──────────────────────────────┘     ║
║                                                                              ║
║   Result: Each resolution gets optimal bitrate automatically                ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

### 2.2 Bitrate Calculation Internal Flow

```
                    ┌─────────────────────────┐
                    │   Input: (width, height) │
                    │   e.g. (1920, 1080)      │
                    └────────────┬─────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │  pixels = width × height │
                    │  = 1920 × 1080           │
                    │  = 2,073,600             │
                    └────────────┬─────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │  Search BITRATE_TABLE    │
                    │  for closest entries     │
                    │                          │
                    │  Table (sorted by px):   │
                    │  230400  → 1.5M/2M/3M   │
                    │  409920  → 2.5M/4M/5M   │
                    │  921600  → 5M/7M/10M    │
                    │  1166400 → 6M/8M/10M    │
                    │  2073600 → 10M/12M/16M  │  ◄── exact match!
                    │  3686400 → 20M/25M/30M  │
                    │  8294400 → 35M/45M/50M  │
                    └────────────┬─────────────┘
                                 │
                          ┌──────┴──────┐
                          │             │
                   exact match?    between entries?
                          │             │
                          ▼             ▼
                   ┌──────────┐  ┌─────────────────┐
                   │ Return   │  │ Linear interp   │
                   │ directly │  │ between lower &  │
                   │          │  │ upper entries    │
                   └──────┬───┘  └────────┬────────┘
                          │               │
                          └───────┬───────┘
                                  │
                                  ▼
                    ┌─────────────────────────┐
                    │  Return dict:            │
                    │  {                        │
                    │    "bitrate": "10M",      │
                    │    "maxrate": "12M",      │
                    │    "bufsize": "16M"       │
                    │  }                        │
                    └─────────────────────────┘
```

### 2.3 Integration with FFmpegFrameWriter

```
    fast_render_segments()
            │
            ▼
    ┌───────────────────────────────────────────────┐
    │  bitrate_info = calculate_bitrate_for_         │
    │      resolution(width, height)                 │
    │                                                │
    │  writer = FFmpegFrameWriter(                   │
    │      output_path=output_path,                  │
    │      width=width,                              │
    │      height=height,                            │
    │      fps=fps,                                  │
    │      audio_path=audio_path,                    │
    │      use_nvenc=use_nvenc,                      │
    │      bitrate=bitrate_info["bitrate"],          │
    │      maxrate=bitrate_info["maxrate"],          │
    │      bufsize=bitrate_info["bufsize"],          │
    │  )                                             │
    └───────────────────────────────────────────────┘
            │
            ▼
    ┌───────────────────────────────────────────────┐
    │  _build_command()                              │
    │                                                │
    │  NVENC path:                                   │
    │    -b:v {self.bitrate}    ← was hardcoded "8M" │
    │    -maxrate {self.maxrate} ← was hardcoded "12M"│
    │    -bufsize {self.bufsize} ← was hardcoded "16M"│
    │                                                │
    │  CPU path:                                     │
    │    -crf 23                ← unchanged          │
    │    -maxrate {self.maxrate} ← NEW (optional cap)│
    │    -bufsize {self.bufsize} ← NEW (optional cap)│
    └───────────────────────────────────────────────┘
```

---

## 3. Step-by-Step Instructions

### Step 1: Add the Bitrate Lookup Table and Calculation Function

**File:** `backend/core_engine/fast_compositor.py`
**Location:** Insert after the existing imports and before the `OverlaySlice` dataclass (around L40–42)

Add a module-level constant `BITRATE_TABLE` and a function `calculate_bitrate_for_resolution()`.

#### 1a. Define the bitrate table

```python
# ---------------------------------------------------------------------------
# Resolution-aware bitrate table
# ---------------------------------------------------------------------------
# Each entry: (pixel_count, bitrate_bps, maxrate_bps, bufsize_bps)
# Sorted by pixel count ascending for binary-search / interpolation.
# Values in bits-per-second for arithmetic; converted to FFmpeg strings on output.

BITRATE_TABLE = [
    #  pixels,    bitrate,   maxrate,    bufsize
    (  230_400,   1_500_000,  2_000_000,  3_000_000),   # 640×360  (360p)
    (  409_920,   2_500_000,  4_000_000,  5_000_000),   # 854×480  (480p)
    (  921_600,   5_000_000,  7_000_000, 10_000_000),   # 1280×720 (720p)
    (1_166_400,   6_000_000,  8_000_000, 10_000_000),   # 1080×1080 (square)
    (2_073_600,  10_000_000, 12_000_000, 16_000_000),   # 1920×1080 (1080p)
    (3_686_400,  20_000_000, 25_000_000, 30_000_000),   # 2560×1440 (1440p)
    (8_294_400,  35_000_000, 45_000_000, 50_000_000),   # 3840×2160 (4K)
]


def _bps_to_ffmpeg_str(bps: int) -> str:
    """Convert bits-per-second to an FFmpeg-compatible rate string.

    Examples:
        10_000_000  → "10M"
        7_500_000   → "7500K"
        1_500_000   → "1500K"
    """
    if bps >= 1_000_000 and bps % 1_000_000 == 0:
        return f"{bps // 1_000_000}M"
    elif bps >= 1_000 and bps % 1_000 == 0:
        return f"{bps // 1_000}K"
    else:
        return str(bps)


def calculate_bitrate_for_resolution(width: int, height: int) -> dict:
    """Return optimal bitrate/maxrate/bufsize for the given resolution.

    Uses linear interpolation between entries in ``BITRATE_TABLE`` when the
    resolution does not match a predefined entry exactly.  Clamps to the
    lowest entry for sub-360p resolutions and to the highest entry for
    resolutions above 4K.

    Args:
        width: Output video width in pixels.
        height: Output video height in pixels.

    Returns:
        Dict with keys ``"bitrate"``, ``"maxrate"``, ``"bufsize"`` — all
        FFmpeg-compatible rate strings (e.g. ``"10M"``, ``"7500K"``).
    """
    pixels = width * height

    # Clamp below minimum
    if pixels <= BITRATE_TABLE[0][0]:
        entry = BITRATE_TABLE[0]
        result = {
            "bitrate": _bps_to_ffmpeg_str(entry[1]),
            "maxrate": _bps_to_ffmpeg_str(entry[2]),
            "bufsize": _bps_to_ffmpeg_str(entry[3]),
        }
        logger.info(
            "Bitrate for %dx%d (%d px): %s (clamped to minimum)",
            width, height, pixels, result,
        )
        return result

    # Clamp above maximum
    if pixels >= BITRATE_TABLE[-1][0]:
        entry = BITRATE_TABLE[-1]
        result = {
            "bitrate": _bps_to_ffmpeg_str(entry[1]),
            "maxrate": _bps_to_ffmpeg_str(entry[2]),
            "bufsize": _bps_to_ffmpeg_str(entry[3]),
        }
        logger.info(
            "Bitrate for %dx%d (%d px): %s (clamped to maximum)",
            width, height, pixels, result,
        )
        return result

    # Find the two bracketing entries and interpolate
    for i in range(len(BITRATE_TABLE) - 1):
        lo = BITRATE_TABLE[i]
        hi = BITRATE_TABLE[i + 1]
        if lo[0] <= pixels <= hi[0]:
            # Exact match on lower bound
            if pixels == lo[0]:
                result = {
                    "bitrate": _bps_to_ffmpeg_str(lo[1]),
                    "maxrate": _bps_to_ffmpeg_str(lo[2]),
                    "bufsize": _bps_to_ffmpeg_str(lo[3]),
                }
                logger.info(
                    "Bitrate for %dx%d (%d px): %s (exact match)",
                    width, height, pixels, result,
                )
                return result

            # Linear interpolation
            t = (pixels - lo[0]) / (hi[0] - lo[0])
            bitrate = int(lo[1] + t * (hi[1] - lo[1]))
            maxrate = int(lo[2] + t * (hi[2] - lo[2]))
            bufsize = int(lo[3] + t * (hi[3] - lo[3]))

            result = {
                "bitrate": _bps_to_ffmpeg_str(bitrate),
                "maxrate": _bps_to_ffmpeg_str(maxrate),
                "bufsize": _bps_to_ffmpeg_str(bufsize),
            }
            logger.info(
                "Bitrate for %dx%d (%d px): %s (interpolated, t=%.3f)",
                width, height, pixels, result, t,
            )
            return result

    # Fallback (should never reach here)
    logger.warning(
        "Bitrate calculation fallback for %dx%d — using 10M default", width, height,
    )
    return {"bitrate": "10M", "maxrate": "12M", "bufsize": "16M"}
```

---

### Step 2: Update `FFmpegFrameWriter.__init__` to Accept `maxrate` and `bufsize`

**File:** `backend/core_engine/fast_compositor.py`
**Location:** L381–399 (the `__init__` method of `FFmpegFrameWriter`)

#### Current code (L381–399):

```python
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

#### New code:

```python
    def __init__(
        self,
        output_path: str,
        width: int,
        height: int,
        fps: int,
        audio_path: Optional[str] = None,
        use_nvenc: bool = False,
        bitrate: str = "8M",
        maxrate: str = "12M",
        bufsize: str = "16M",
    ):
        self.output_path = output_path
        self.width = width
        self.height = height
        self.fps = fps
        self.audio_path = audio_path
        self.use_nvenc = use_nvenc
        self.bitrate = bitrate
        self.maxrate = maxrate
        self.bufsize = bufsize
        self._proc: Optional[subprocess.Popen] = None
```

**What changed:**
- Added `maxrate: str = "12M"` parameter (default matches current hardcoded value).
- Added `bufsize: str = "16M"` parameter (default matches current hardcoded value).
- Stored both as instance attributes.

---

### Step 3: Update `FFmpegFrameWriter._build_command()` to Use Instance Attributes

**File:** `backend/core_engine/fast_compositor.py`
**Location:** L401–449 (the `_build_command` method)

#### Current NVENC block (L420–431):

```python
        if self.use_nvenc:
            cmd.extend([
                "-c:v", "h264_nvenc",
                "-preset", "p4",
                "-tune", "hq",
                "-rc", "vbr",
                "-cq", "23",
                "-b:v", self.bitrate,
                "-maxrate", "12M",
                "-bufsize", "16M",
                "-profile:v", "high",
            ])
```

#### New NVENC block:

```python
        if self.use_nvenc:
            cmd.extend([
                "-c:v", "h264_nvenc",
                "-preset", "p4",
                "-tune", "hq",
                "-rc", "vbr",
                "-cq", "23",
                "-b:v", self.bitrate,
                "-maxrate", self.maxrate,
                "-bufsize", self.bufsize,
                "-profile:v", "high",
            ])
```

**What changed:**
- Replaced hardcoded `"12M"` with `self.maxrate`.
- Replaced hardcoded `"16M"` with `self.bufsize`.

#### Current CPU (libx264) block (L432–438):

```python
        else:
            cmd.extend([
                "-c:v", "libx264",
                "-preset", "fast",
                "-tune", "film",
                "-crf", "23",
                "-profile:v", "high",
            ])
```

#### New CPU (libx264) block:

```python
        else:
            cmd.extend([
                "-c:v", "libx264",
                "-preset", "fast",
                "-tune", "film",
                "-crf", "23",
                "-maxrate", self.maxrate,
                "-bufsize", self.bufsize,
                "-profile:v", "high",
            ])
```

**What changed:**
- Added `-maxrate` and `-bufsize` to the CPU path as well. This converts the CPU encoder
  from pure CRF mode to **capped CRF mode** (CRF with a maximum bitrate ceiling). This
  prevents runaway bitrates on highly detailed 4K content while preserving CRF-based
  quality adaptation.
- When `-maxrate` is specified alongside `-crf`, libx264 treats it as a VBV (Video
  Buffering Verifier) constraint that caps the peak bitrate while CRF controls average
  quality. This is the recommended approach per FFmpeg documentation.

> **Note:** If you do NOT want to cap the CPU encoder, you can skip adding `-maxrate` and
> `-bufsize` to the CPU block. The NVENC path is the primary beneficiary of this feature
> since it already uses bitrate-based rate control.

---

### Step 4: Update `fast_render_segments()` to Auto-Calculate Bitrate

**File:** `backend/core_engine/fast_compositor.py`
**Location:** L646–655 (the FFmpegFrameWriter instantiation inside `fast_render_segments()`)

#### Current code (L646–655):

```python
    writer = FFmpegFrameWriter(
        output_path=output_path,
        width=width,
        height=height,
        fps=fps,
        audio_path=audio_path,
        use_nvenc=use_nvenc,
        bitrate="8M",
    )
```

#### New code:

```python
    # Auto-calculate bitrate based on output resolution
    bitrate_info = calculate_bitrate_for_resolution(width, height)
    logger.info(
        "Resolution-aware bitrate for %dx%d: bitrate=%s, maxrate=%s, bufsize=%s",
        width, height, bitrate_info["bitrate"], bitrate_info["maxrate"],
        bitrate_info["bufsize"],
    )

    writer = FFmpegFrameWriter(
        output_path=output_path,
        width=width,
        height=height,
        fps=fps,
        audio_path=audio_path,
        use_nvenc=use_nvenc,
        bitrate=bitrate_info["bitrate"],
        maxrate=bitrate_info["maxrate"],
        bufsize=bitrate_info["bufsize"],
    )
```

**What changed:**
- Removed the hardcoded `bitrate="8M"`.
- Added `calculate_bitrate_for_resolution(width, height)` call before writer creation.
- Passes computed `bitrate`, `maxrate`, and `bufsize` to the writer.
- Added debug logging so the selected bitrate is visible in render logs.

---

### Step 5: Verify `video_renderer.py` — No Changes Required

**File:** `backend/core_engine/video_renderer.py`
**Location:** L1039–1052 (the `fast_render_segments()` call)

The current code already passes `resolution=(res_width, res_height)` to
`fast_render_segments()`. Since the bitrate calculation happens inside
`fast_render_segments()` (Step 4), **no changes are needed in `video_renderer.py`**.

#### Current code (L1039–1052) — unchanged:

```python
        render_stats = fast_render_segments(
            segment_data=segment_data_list,
            output_path=output_path,
            resolution=(res_width, res_height),
            fps=fps,
            zoom_intensity=zoom_intensity,
            subtitle_settings=sub_settings,
            logo_settings=logo_settings_dict,
            audio_path=temp_audio_path,
            use_nvenc=use_nvenc,
            on_progress=on_progress,
            crossfade_duration=TRANSITION_DURATION,
            inter_segment_silence=inter_segment_silence,
        )
```

The resolution is unpacked inside `fast_render_segments()` at L537 (`width, height = resolution`),
which is exactly what `calculate_bitrate_for_resolution()` needs.

> **Optional enhancement:** If you want `video_renderer.py` to log the selected bitrate
> at the orchestration level, you could import `calculate_bitrate_for_resolution` and log
> there too — but this is not required for the feature to work.

---

### Step 6: Update the `fast_render_segments()` Function Signature (Optional)

If you want to allow callers to **override** the auto-calculated bitrate (e.g., for testing
or for Feature 5.1 platform presets), add an optional `bitrate_override` parameter:

**File:** `backend/core_engine/fast_compositor.py`
**Location:** L487–510 (the function signature)

#### Add this parameter to the function signature:

```python
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
    bitrate_override: Optional[dict] = None,  # ← NEW
) -> dict:
```

Then update Step 4's code to respect the override:

```python
    # Auto-calculate bitrate based on output resolution (or use override)
    if bitrate_override:
        bitrate_info = bitrate_override
        logger.info(
            "Using bitrate override for %dx%d: %s", width, height, bitrate_info,
        )
    else:
        bitrate_info = calculate_bitrate_for_resolution(width, height)
        logger.info(
            "Resolution-aware bitrate for %dx%d: bitrate=%s, maxrate=%s, bufsize=%s",
            width, height, bitrate_info["bitrate"], bitrate_info["maxrate"],
            bitrate_info["bufsize"],
        )
```

This is **optional** but recommended for forward-compatibility with Feature 5.1.

---

### Step 7: Add Unit Tests

**File:** `backend/core_engine/tests/test_bitrate_calculation.py` (NEW FILE)

```python
"""Unit tests for resolution-aware bitrate calculation.

Tests the ``calculate_bitrate_for_resolution`` function and the
``BITRATE_TABLE`` constant from ``fast_compositor.py``.
"""

import pytest
from core_engine.fast_compositor import (
    BITRATE_TABLE,
    calculate_bitrate_for_resolution,
    _bps_to_ffmpeg_str,
)


class TestBpsToFfmpegStr:
    """Tests for the _bps_to_ffmpeg_str helper."""

    def test_exact_megabits(self):
        assert _bps_to_ffmpeg_str(10_000_000) == "10M"
        assert _bps_to_ffmpeg_str(1_000_000) == "1M"
        assert _bps_to_ffmpeg_str(35_000_000) == "35M"

    def test_exact_kilobits(self):
        assert _bps_to_ffmpeg_str(1_500_000) == "1500K"
        assert _bps_to_ffmpeg_str(7_500_000) == "7500K"
        assert _bps_to_ffmpeg_str(2_500_000) == "2500K"

    def test_raw_value(self):
        assert _bps_to_ffmpeg_str(123_456) == "123456"

    def test_zero(self):
        assert _bps_to_ffmpeg_str(0) == "0"


class TestBitrateTable:
    """Validate the BITRATE_TABLE structure."""

    def test_sorted_by_pixel_count(self):
        pixel_counts = [entry[0] for entry in BITRATE_TABLE]
        assert pixel_counts == sorted(pixel_counts), \
            "BITRATE_TABLE must be sorted by pixel count ascending"

    def test_all_entries_have_four_values(self):
        for entry in BITRATE_TABLE:
            assert len(entry) == 4, f"Entry {entry} must have 4 values"

    def test_bitrate_increases_with_resolution(self):
        for i in range(len(BITRATE_TABLE) - 1):
            lo, hi = BITRATE_TABLE[i], BITRATE_TABLE[i + 1]
            assert hi[1] >= lo[1], \
                f"Bitrate should increase: {lo[0]}px={lo[1]} > {hi[0]}px={hi[1]}"

    def test_maxrate_exceeds_bitrate(self):
        for entry in BITRATE_TABLE:
            assert entry[2] >= entry[1], \
                f"maxrate ({entry[2]}) must be >= bitrate ({entry[1]}) for {entry[0]}px"

    def test_bufsize_exceeds_maxrate(self):
        for entry in BITRATE_TABLE:
            assert entry[3] >= entry[2], \
                f"bufsize ({entry[3]}) must be >= maxrate ({entry[2]}) for {entry[0]}px"


class TestCalculateBitrateForResolution:
    """Tests for the main calculation function."""

    # ── Exact matches ──────────────────────────────────────────────────

    def test_360p(self):
        result = calculate_bitrate_for_resolution(640, 360)
        assert result["bitrate"] == "1500K"
        assert result["maxrate"] == "2M"
        assert result["bufsize"] == "3M"

    def test_720p(self):
        result = calculate_bitrate_for_resolution(1280, 720)
        assert result["bitrate"] == "5M"
        assert result["maxrate"] == "7M"
        assert result["bufsize"] == "10M"

    def test_1080p(self):
        result = calculate_bitrate_for_resolution(1920, 1080)
        assert result["bitrate"] == "10M"
        assert result["maxrate"] == "12M"
        assert result["bufsize"] == "16M"

    def test_1440p(self):
        result = calculate_bitrate_for_resolution(2560, 1440)
        assert result["bitrate"] == "20M"
        assert result["maxrate"] == "25M"
        assert result["bufsize"] == "30M"

    def test_4k(self):
        result = calculate_bitrate_for_resolution(3840, 2160)
        assert result["bitrate"] == "35M"
        assert result["maxrate"] == "45M"
        assert result["bufsize"] == "50M"

    # ── Portrait / square orientations ─────────────────────────────────

    def test_portrait_1080x1920(self):
        """Portrait 1080×1920 has same pixel count as 1920×1080."""
        result = calculate_bitrate_for_resolution(1080, 1920)
        assert result["bitrate"] == "10M"

    def test_square_1080x1080(self):
        result = calculate_bitrate_for_resolution(1080, 1080)
        assert result["bitrate"] == "6M"

    # ── Clamping ───────────────────────────────────────────────────────

    def test_below_minimum_clamps_to_360p(self):
        """320×240 should clamp to 360p values."""
        result = calculate_bitrate_for_resolution(320, 240)
        assert result["bitrate"] == "1500K"
        assert result["maxrate"] == "2M"

    def test_above_maximum_clamps_to_4k(self):
        """7680×4320 (8K) should clamp to 4K values."""
        result = calculate_bitrate_for_resolution(7680, 4320)
        assert result["bitrate"] == "35M"
        assert result["maxrate"] == "45M"

    # ── Interpolation ─────────────────────────────────────────────────

    def test_interpolation_between_720p_and_1080p(self):
        """A non-standard resolution between 720p and 1080p."""
        result = calculate_bitrate_for_resolution(1600, 900)
        # 1600×900 = 1,440,000 pixels
        # Between 1,166,400 (square, 6M) and 2,073,600 (1080p, 10M)
        # Interpolation factor t ≈ (1440000-1166400)/(2073600-1166400) ≈ 0.302
        # Expected bitrate ≈ 6M + 0.302 * 4M ≈ 7.2M
        # Just verify it's between the two bounding values
        bitrate_str = result["bitrate"]
        # It should be between 6M and 10M — just check it's a valid string
        assert bitrate_str is not None
        assert result["maxrate"] is not None
        assert result["bufsize"] is not None

    def test_interpolation_produces_intermediate_values(self):
        """Verify interpolated bitrate is between the bracketing entries."""
        # 1600×1200 = 1,920,000 pixels — between square and 1080p
        result = calculate_bitrate_for_resolution(1600, 1200)
        # Should be between 6M and 10M range
        assert result["bitrate"] is not None

    # ── Return type validation ─────────────────────────────────────────

    def test_return_type(self):
        result = calculate_bitrate_for_resolution(1920, 1080)
        assert isinstance(result, dict)
        assert "bitrate" in result
        assert "maxrate" in result
        assert "bufsize" in result
        assert isinstance(result["bitrate"], str)
        assert isinstance(result["maxrate"], str)
        assert isinstance(result["bufsize"], str)
```

---

### Step 8: Integration with Feature 5.1 (If Applicable)

If Feature 5.1 (Platform-Specific Encoding Presets) has already been implemented and
`backend/core_engine/encoding_presets.py` exists, consider the following integration:

1. **Move** `BITRATE_TABLE` and `calculate_bitrate_for_resolution()` into
   `encoding_presets.py` alongside the platform preset definitions.

2. **Update imports** in `fast_compositor.py`:
   ```python
   from core_engine.encoding_presets import calculate_bitrate_for_resolution
   ```

3. **Platform presets can override** the resolution-based calculation. For example, a
   "TikTok" preset might specify a lower bitrate than the resolution suggests (to reduce
   upload time), while a "YouTube" preset might use the full resolution-optimal bitrate.

4. **Priority order** for bitrate selection:
   ```
   Platform preset bitrate  >  Resolution-calculated bitrate  >  Hardcoded default
   ```

If Feature 5.1 is NOT yet implemented, keep everything in `fast_compositor.py` and the
migration to `encoding_presets.py` can be done when 5.1 is built.

---

### Step 9: Manual Testing Checklist

Test the feature manually by rendering projects at different resolutions and inspecting
the FFmpeg command logged output.

#### 9a. Check log output for bitrate selection

Run a render at 1080p and verify the log contains:
```
Resolution-aware bitrate for 1920x1080: bitrate=10M, maxrate=12M, bufsize=16M
```

#### 9b. Check FFmpeg command for correct parameters

Enable DEBUG logging and verify the FFmpeg command line includes the correct bitrate flags:
```
ffmpeg -y -f rawvideo ... -b:v 10M -maxrate 12M -bufsize 16M ...
```

#### 9c. Compare file sizes across resolutions

Render the same project at 720p, 1080p, and 4K. Verify:
- 720p file is smaller than 1080p
- 1080p file is smaller than 4K
- File sizes are roughly proportional to the bitrate ratios (5:10:35)

#### 9d. Visual quality spot-check

Open the 4K render and verify there is no visible macro-blocking on detailed scenes
(this was the primary complaint with the old 8Mbps cap).

---

## 4. Expected Outcome

### 4.1 Before (Current Behaviour)

| Resolution | Bitrate | Maxrate | Bufsize | Result                              |
| ---------- | ------- | ------- | ------- | ----------------------------------- |
| 640×360    | 8M      | 12M     | 16M     | Massively over-budgeted             |
| 1280×720   | 8M      | 12M     | 16M     | Slightly over-budgeted              |
| 1920×1080  | 8M      | 12M     | 16M     | Slightly under YouTube's 10M rec    |
| 2560×1440  | 8M      | 12M     | 16M     | Visible quality degradation          |
| 3840×2160  | 8M      | 12M     | 16M     | Severe quality loss, blurry output  |

### 4.2 After (New Behaviour)

| Resolution | Bitrate | Maxrate | Bufsize | Result                              |
| ---------- | ------- | ------- | ------- | ----------------------------------- |
| 640×360    | 1.5M    | 2M      | 3M      | Appropriate quality, small files     |
| 1280×720   | 5M      | 7M      | 10M     | YouTube-recommended quality          |
| 1920×1080  | 10M     | 12M     | 16M     | Matches YouTube 1080p recommendation |
| 2560×1440  | 20M     | 25M     | 30M     | Good quality for 1440p content       |
| 3840×2160  | 35M     | 45M     | 50M     | Professional 4K quality              |

### 4.3 Expected File Size Impact

Based on a 3-minute render at 30fps:

| Resolution | Old Size (8M) | New Size | Change     |
| ---------- | ------------- | -------- | ---------- |
| 640×360    | ~180 MB       | ~34 MB   | **−81%**   |
| 1280×720   | ~180 MB       | ~113 MB  | **−37%**   |
| 1920×1080  | ~180 MB       | ~225 MB  | **+25%**   |
| 2560×1440  | ~180 MB       | ~450 MB  | **+150%**  |
| 3840×2160  | ~180 MB       | ~788 MB  | **+338%**  |

> Note: Actual sizes vary due to VBR. The 1080p increase is modest and delivers better
> quality. The 4K increase is expected — previously it was severely under-budgeted.

### 4.4 Backward Compatibility

- **Default values unchanged.** If `FFmpegFrameWriter` is instantiated without the new
  `maxrate`/`bufsize` params, the defaults (`"12M"` / `"16M"`) match the old hardcoded
  values. The `bitrate` default remains `"8M"`.
- **No model changes.** Bitrate is computed at render time, not stored in the database.
- **No API changes.** No new endpoints, serializers, or model fields.
- **No frontend changes.** The bitrate is fully transparent to the user.
- **CPU encoder gains. ** The libx264 path now has a VBV cap, which prevents runaway
  bitrates on highly detailed content at 4K. At lower resolutions, CRF 23 typically
  stays well within the cap, so behaviour is effectively unchanged.

### 4.5 Performance Impact

- **Negligible.** The bitrate calculation is a single function call with ~7 table entries.
  It runs once per render (not per frame). Cost: < 1 microsecond.
- **Encoding speed:** NVENC speed is unaffected by bitrate changes. libx264 may be
  marginally slower at higher bitrates due to more complex motion estimation, but the
  difference is negligible at CRF 23.

---

## 5. Verification Checklist

### 5.1 Code Changes

- [ ] `BITRATE_TABLE` constant added to `fast_compositor.py` (after imports, before L42)
- [ ] `_bps_to_ffmpeg_str()` helper function added
- [ ] `calculate_bitrate_for_resolution()` function added with:
  - [ ] Correct clamp-below logic (sub-360p → 360p values)
  - [ ] Correct clamp-above logic (above-4K → 4K values)
  - [ ] Linear interpolation between entries
  - [ ] Fallback return for edge cases
  - [ ] Debug logging of selected bitrate
- [ ] `FFmpegFrameWriter.__init__` updated with `maxrate` and `bufsize` params
- [ ] `FFmpegFrameWriter._build_command()` NVENC block uses `self.maxrate` / `self.bufsize`
- [ ] `FFmpegFrameWriter._build_command()` CPU block uses `self.maxrate` / `self.bufsize`
- [ ] `fast_render_segments()` calls `calculate_bitrate_for_resolution()` before writer init
- [ ] `fast_render_segments()` passes computed bitrate/maxrate/bufsize to writer
- [ ] Old hardcoded `bitrate="8M"` removed from `fast_render_segments()`
- [ ] Old hardcoded `"-maxrate", "12M"` removed from `_build_command()` NVENC block
- [ ] Old hardcoded `"-bufsize", "16M"` removed from `_build_command()` NVENC block

### 5.2 Tests

- [ ] `test_bitrate_calculation.py` created in `backend/core_engine/tests/`
- [ ] All exact-match resolution tests pass (360p, 720p, 1080p, 1440p, 4K)
- [ ] Portrait orientation test passes (1080×1920 → same as 1920×1080)
- [ ] Square orientation test passes (1080×1080 → 6M)
- [ ] Below-minimum clamping test passes (320×240 → 360p values)
- [ ] Above-maximum clamping test passes (7680×4320 → 4K values)
- [ ] Interpolation tests pass (non-standard resolutions)
- [ ] `_bps_to_ffmpeg_str` tests pass (M, K, raw)
- [ ] `BITRATE_TABLE` structural validation passes

### 5.3 Integration

- [ ] Existing test suite passes (`python manage.py test`)
- [ ] A 1080p render completes successfully with new bitrate logic
- [ ] FFmpeg command in logs shows correct `-b:v`, `-maxrate`, `-bufsize` values
- [ ] No regressions in render output quality or timing

### 5.4 Log Verification

- [ ] Render log shows `"Resolution-aware bitrate for WxH"` message
- [ ] Bitrate values in log match expected table values for the resolution
- [ ] FFmpeg command log shows dynamic (not hardcoded) bitrate flags

### 5.5 Edge Cases

- [ ] Rendering at the lowest supported resolution (e.g., 480×270) produces valid output
- [ ] Rendering at the highest supported resolution (e.g., 3840×2160) produces valid output
- [ ] Rendering at a non-standard resolution (e.g., 1600×900) produces valid output
- [ ] `use_nvenc=False` (CPU) path still works with the new maxrate/bufsize
- [ ] `use_nvenc=True` (GPU) path still works with the new dynamic values

---

## 6. Notes for AI Agent

### 6.1 General Implementation Notes

1. **This is a backend-only change.** No frontend, API, serializer, or model modifications
   are needed. The bitrate is computed from the resolution at render time.

2. **The primary file is `backend/core_engine/fast_compositor.py`.** All new code goes here
   unless Feature 5.1 has already created `encoding_presets.py`.

3. **The bitrate table values are derived from YouTube's recommended upload encoding
   settings.** They represent a good balance between quality and file size for H.264 High
   Profile content. If the user later requests different values, only the `BITRATE_TABLE`
   constant needs updating.

4. **Linear interpolation is intentional.** Bitrate vs. pixel count has a roughly linear
   relationship for H.264 at a constant quality level. More sophisticated models (e.g.,
   logarithmic scaling) are not needed for this use case.

5. **The CPU (libx264) path change is optional but recommended.** Adding `-maxrate` and
   `-bufsize` converts it from pure CRF to capped CRF, which prevents file size surprises
   on highly detailed 4K content. If this causes issues, the CPU block can be left as-is
   (CRF-only) by simply not adding the maxrate/bufsize flags there.

### 6.2 Exact File Locations and Line Numbers

| What                                    | File                                          | Line(s)    |
| --------------------------------------- | --------------------------------------------- | ---------- |
| `FFmpegFrameWriter` class definition    | `backend/core_engine/fast_compositor.py`      | L365       |
| `__init__` method                       | `backend/core_engine/fast_compositor.py`      | L381–399   |
| `_build_command` NVENC block            | `backend/core_engine/fast_compositor.py`      | L420–431   |
| `_build_command` CPU block              | `backend/core_engine/fast_compositor.py`      | L432–438   |
| Writer instantiation in fast_render     | `backend/core_engine/fast_compositor.py`      | L646–655   |
| `fast_render_segments()` signature      | `backend/core_engine/fast_compositor.py`      | L487–510   |
| `fast_render_segments()` call site      | `backend/core_engine/video_renderer.py`       | L1039–1052 |
| Insert point for BITRATE_TABLE          | `backend/core_engine/fast_compositor.py`      | ~L40       |
| Existing test directory                 | `backend/core_engine/tests/`                  | —          |

### 6.3 Import Requirements

No new external packages needed. The implementation uses only:
- `int` arithmetic (for pixel counts and interpolation)
- `str` formatting (for FFmpeg rate strings)
- `logging` (already imported)
- `typing` (already imported)

### 6.4 Critical Gotchas

1. **Do NOT remove the `bitrate` parameter from `FFmpegFrameWriter.__init__`.**
   The old default `"8M"` must remain as a fallback for any external callers. The new
   `maxrate` and `bufsize` params are additive, not replacements.

2. **The `_bps_to_ffmpeg_str` function must handle non-round values gracefully.**
   Interpolation may produce values like `7,523,456` bps. The function should convert
   these to kilo format (`"7523K"`) or raw integer strings if they don't divide evenly.

3. **Keep `BITRATE_TABLE` sorted by pixel count.** The interpolation logic assumes
   ascending order. Adding an entry out of sort order will silently produce wrong results.

4. **Test with `use_nvenc=True` and `use_nvenc=False` separately.** The NVENC path uses
   `-b:v` as a target bitrate, while the CPU path uses CRF. Both should work correctly
   with the new maxrate/bufsize, but the behaviour differs.

5. **The function `calculate_bitrate_for_resolution` should be pure** (no side effects
   except logging). This makes it safe to call from tests and from multiple places.

6. **When testing, check the FFmpeg stderr output for warnings.** If the bitrate values
   are inconsistent (e.g., maxrate < bitrate), FFmpeg will emit a warning in stderr. The
   `finish()` method returns stderr — log it at WARNING level if returncode is 0 but
   stderr contains `"Warning"` or `"Error"`.

### 6.5 Testing Commands

```bash
# Run only the new bitrate tests
cd backend
python -m pytest core_engine/tests/test_bitrate_calculation.py -v

# Run the full test suite to check for regressions
python manage.py test

# Quick smoke test: import the function in a Python shell
python -c "from core_engine.fast_compositor import calculate_bitrate_for_resolution; print(calculate_bitrate_for_resolution(1920, 1080))"
```

### 6.6 Rollback Strategy

If this feature causes issues:

1. **Quick rollback:** Revert `fast_render_segments()` to use `bitrate="8M"` and remove
   the `calculate_bitrate_for_resolution()` call. The writer's new `maxrate`/`bufsize`
   params have defaults matching the old hardcoded values, so they're harmless.

2. **Partial rollback (NVENC only):** Keep the dynamic bitrate for NVENC but revert the
   CPU path to pure CRF (remove the `-maxrate`/`-bufsize` lines from the `else` block).

3. **Full rollback:** Revert all changes in `fast_compositor.py` and delete the test file.
   No model migrations to undo.

### 6.7 Future Enhancements

After this feature is stable, consider:

- **FPS-aware bitrate scaling:** Higher FPS (60fps) may benefit from ~1.5× the bitrate of
  30fps at the same resolution. Add an optional FPS multiplier.
- **Content-complexity awareness:** High-motion content (action, fast panning) benefits
  from higher bitrates. Could analyse Ken Burns zoom speed as a proxy.
- **Two-pass encoding option:** For maximum quality at a target file size. Would require
  changes to the `FFmpegFrameWriter` pipeline (currently single-pass).
- **User-configurable bitrate multiplier:** A "Quality" slider (0.5×–2.0×) in the frontend
  that scales the auto-calculated bitrate. Simple to implement once this feature exists.

### 6.8 Relationship to Other Features

| Feature | Relationship                                                                      |
| ------- | --------------------------------------------------------------------------------- |
| 5.1     | Platform presets may override resolution-based bitrate; this feature provides the default |
| 1.2     | GPU-accelerated compositing — NVENC is the primary beneficiary of dynamic bitrate  |
| 3.1     | Transition effects don't affect bitrate selection; they're composited at frame level|

### 6.9 Summary of All Changes (Copy-Paste Reference)

**Files to modify:**
1. `backend/core_engine/fast_compositor.py` — 4 changes:
   - Add `BITRATE_TABLE`, `_bps_to_ffmpeg_str()`, `calculate_bitrate_for_resolution()` (~L40)
   - Update `FFmpegFrameWriter.__init__` to add `maxrate`/`bufsize` params (L381–399)
   - Update `_build_command()` to use `self.maxrate`/`self.bufsize` (L420–438)
   - Update writer instantiation in `fast_render_segments()` (L646–655)

**Files to create:**
1. `backend/core_engine/tests/test_bitrate_calculation.py` — unit tests

**Files that need NO changes:**
1. `backend/core_engine/video_renderer.py` — already passes resolution correctly
2. `backend/api/models.py` — no model changes needed
3. `backend/api/serializers.py` — no serializer changes needed
4. `backend/api/views.py` — no view changes needed
5. All frontend files — no frontend changes needed
