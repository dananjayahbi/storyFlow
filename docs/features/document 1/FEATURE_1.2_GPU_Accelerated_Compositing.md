# Feature 1.2 — GPU-Accelerated Compositing (CuPy)

> **Status:** Planned  
> **Category:** Core Engine / Rendering Performance  
> **Target File:** `backend/core_engine/fast_compositor.py`  
> **Estimated Complexity:** Medium-High  
> **Expected Speedup:** 5–10× at 4K resolution on CUDA-capable GPUs  
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

The current `fast_render_segments()` function in
`backend/core_engine/fast_compositor.py` (line 487, 839 lines total)
performs all frame compositing with pure NumPy on the CPU.  The main
frame loop lives in **Phase 4** (lines 663–766) and performs these
operations for every frame:

1. **Ken Burns crop** — slice the source image array with NumPy
   indexing: `source_image[y:y+crop_h, x:x+crop_w]` (L711–714).
2. **Resize** — `cv2.resize(crop, (width, height))` to fit the output
   resolution (L719–721).
3. **Subtitle overlay** — `alpha_blit(seg_frame, overlay)` for each
   active subtitle (L724–726).
4. **Crossfade accumulation** — `blended_float += seg_frame.astype(
   np.float32) * weight` plus weight tracking (L729–730).
5. **Normalisation** — `np.clip(blended_float / total_weight, 0, 255)
   .astype(np.uint8)` (L733–736).
6. **Logo overlay** — `alpha_blit(frame, logo_overlay)` (L739–740).
7. **Write frame** — `writer.write_frame(frame)` sends raw uint8 bytes
   to the FFmpeg stdin pipe (L743).

At **1080p** (1920×1080), per-frame cost is approx 5–10 ms — quite
acceptable.  However, at **4K** (3840×2160), the per-frame cost
balloons to 40–80 ms due to:

| Operation | 1080p Cost | 4K Cost | Ratio |
|---|---|---|---|
| NumPy crop + slice | ~0.5 ms | ~2 ms | 4× |
| `cv2.resize()` | ~2 ms | ~12 ms | 6× |
| Alpha blit (subtitles) | ~1 ms | ~4 ms | 4× |
| Crossfade blend (float32) | ~1 ms | ~8 ms | 8× |
| Normalise + cast | ~0.5 ms | ~4 ms | 8× |
| Logo blit | ~0.5 ms | ~2 ms | 4× |
| **Total compositing** | **~5.5 ms** | **~32 ms** | **~6×** |
| FFmpeg pipe write | ~2 ms | ~8 ms | 4× |

At 4K/30fps, the compositing budget is ~33 ms/frame and we're already
at the edge.  Adding more overlays or complex effects pushes well past
real-time.

### 1.2 Proposed Solution

Use **CuPy** as a drop-in NumPy replacement for CUDA GPUs to offload
the heavy array arithmetic — cropping, blending, normalisation, and
alpha compositing — to the GPU.  CuPy arrays live in GPU VRAM and all
element-wise operations run as CUDA kernels automatically.

**Key principles:**

1. **Upload once, render many** — source images, subtitle overlays,
   and the logo overlay are transferred to GPU memory at the start of
   the render.  They stay on the GPU for the entire render session.
2. **Compute on GPU** — crop (slicing), resize, alpha blend, crossfade
   accumulation, normalisation, and type casting all run as CuPy
   operations on the GPU.
3. **Download once per frame** — the finished uint8 frame is
   transferred back to CPU (`cp.asnumpy()`) only at write time, just
   before `FFmpegFrameWriter.write_frame()`.
4. **Graceful fallback** — if CuPy is not installed, or no CUDA GPU
   is available, the existing NumPy code path is used unchanged.

Expected speedup: **5–10×** at 4K resolution, reducing per-frame
compositing cost to approximately 3–6 ms.

### 1.3 CuPy Primer

CuPy is a drop-in NumPy replacement that runs on NVIDIA CUDA GPUs.

```python
import cupy as cp

# CPU → GPU
gpu_array = cp.asarray(numpy_array)

# GPU operations (identical syntax to NumPy)
result = gpu_array * 0.5 + other_gpu_array * 0.5
result = cp.clip(result, 0, 255).astype(cp.uint8)

# GPU → CPU
cpu_array = cp.asnumpy(result)

# GPU memory management
cp.get_default_memory_pool().free_all_blocks()
```

Key CuPy features used in this implementation:

- `cp.asarray()` — transfer NumPy array to GPU
- `cp.asnumpy()` — transfer CuPy array back to CPU
- `cp.zeros()` — allocate zeroed GPU array
- Array slicing — `gpu_img[y:y+h, x:x+w]` works identically to NumPy
- Arithmetic — `+`, `*`, `/` are elementwise CUDA kernels
- `cp.clip()` — clamp values (CUDA kernel)
- `.astype()` — type casting on GPU
- `cupyx.scipy.ndimage.zoom()` — GPU-accelerated resize

### 1.4 Files Involved

| File | Role | Changes |
|---|---|---|
| `backend/core_engine/fast_compositor.py` | Main implementation (839 lines) | Add GPU array helpers, modify `alpha_blit()`, modify Phase 4 loop, add GPU init/cleanup |
| `backend/requirements.txt` | Dependencies | Add optional CuPy dependency note |
| `backend/core_engine/ken_burns.py` | Provides `interpolate_position()`, `load_and_prepare_image()`, etc. | **No changes** — outputs NumPy arrays, converted to CuPy in compositor |
| `backend/core_engine/video_renderer.py` | Calls `fast_render_segments()` at L1039 | **No changes** (API unchanged) |
| `backend/api/tasks.py` | Progress callbacks | **No changes** |
| `backend/core_engine/image_upscaler.py` | Already uses PyTorch on GPU | **No changes** — CuPy and PyTorch coexist fine; both use CUDA but separate memory pools |
| `backend/core_engine/tests/` | Test suite | Add GPU compositing tests |

### 1.5 Key Existing Functions Reference

| Function | Location | GPU-Relevant? |
|---|---|---|
| `alpha_blit(frame, overlay)` | `fast_compositor.py` L68 | **Yes** — core target for GPU acceleration |
| `pre_render_subtitles()` | `fast_compositor.py` L113 | No — runs once at startup; output transferred to GPU |
| `pre_render_logo()` | `fast_compositor.py` L299 | No — runs once at startup; output transferred to GPU |
| `FFmpegFrameWriter.write_frame()` | `fast_compositor.py` L462 | No — expects CPU uint8 bytes; GPU→CPU transfer before call |
| `fast_render_segments()` | `fast_compositor.py` L487 | **Yes** — Phase 4 loop is the main target |
| `interpolate_position()` | `ken_burns.py` | No — returns floats, runs on CPU (negligible cost) |
| `load_and_prepare_image()` | `ken_burns.py` | No — returns NumPy array; transferred to GPU once |
| `OverlaySlice` dataclass | `fast_compositor.py` L46 | **Yes** — needs GPU-aware variant |

### 1.6 Dependencies

| Package | Version | Purpose |
|---|---|---|
| `cupy-cuda12x` | ≥ 13.0 | CuPy for CUDA 12.x (primary) |
| `cupy-cuda11x` | ≥ 13.0 | CuPy for CUDA 11.x (alternative) |

**Installation:**
```bash
# For CUDA 12.x
pip install cupy-cuda12x

# For CUDA 11.x
pip install cupy-cuda11x

# Auto-detect (slower install, builds from source)
pip install cupy
```

**IMPORTANT:** CuPy must be **optional**.  The system must function
identically without it — all GPU code paths must have CPU fallbacks.

---

## 2. Flow Diagram

### 2.1 Current Architecture (CPU-Only)

```
┌─────────────────────────────────────────────────────────────────┐
│                         CPU (NumPy)                             │
│                                                                 │
│  Phase 1: Pre-render overlays (subtitles, logo) as NumPy arrays │
│  Phase 2: Calculate timeline & frame ranges                     │
│  Phase 3: Start FFmpeg writer                                   │
│                                                                 │
│  Phase 4: ┌───────────────────────────────────────────────────┐ │
│           │  for frame_idx in range(total_frames):            │ │
│           │                                                   │ │
│           │    ┌─ Ken Burns ─────────────────────────────────┐│ │
│           │    │  interp_x, interp_y = interpolate_position()││ │
│           │    │  crop = source_image[y:y+h, x:x+w]  (NumPy)││ │
│           │    │  seg_frame = cv2.resize(crop)        (CPU)  ││ │
│           │    └─────────────────────────────────────────────┘│ │
│           │                                                   │ │
│           │    ┌─ Subtitles ────────────────────────────────┐ │ │
│           │    │  alpha_blit(seg_frame, overlay)     (NumPy) │ │ │
│           │    └─────────────────────────────────────────────┘ │ │
│           │                                                   │ │
│           │    ┌─ Crossfade ────────────────────────────────┐ │ │
│           │    │  blended += seg_frame.float32 * weight (NP) │ │ │
│           │    └─────────────────────────────────────────────┘ │ │
│           │                                                   │ │
│           │    ┌─ Normalise ────────────────────────────────┐ │ │
│           │    │  frame = clip(blended/weight).uint8  (NumPy)│ │ │
│           │    └─────────────────────────────────────────────┘ │ │
│           │                                                   │ │
│           │    ┌─ Logo ─────────────────────────────────────┐ │ │
│           │    │  alpha_blit(frame, logo_overlay)    (NumPy) │ │ │
│           │    └─────────────────────────────────────────────┘ │ │
│           │                                                   │ │
│           │    writer.write_frame(frame)  ──────────► FFmpeg  │ │
│           │                                                   │ │
│           └───────────────────────────────────────────────────┘ │
│                                                                 │
│  Phase 5: writer.finish()                                       │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Proposed Architecture (GPU-Accelerated)

```
┌──────────────────────┐       ┌──────────────────────────────────┐
│      CPU (NumPy)     │       │        GPU (CuPy / CUDA)         │
│                      │       │                                  │
│  Phase 1: Pre-render │       │                                  │
│   subtitles & logo   │       │                                  │
│   as NumPy arrays    │       │                                  │
│         │            │       │                                  │
│         ▼            │       │                                  │
│  Phase 1b: Upload    │──────►│  gpu_sources[i] = cp.asarray()   │
│   source images,     │       │  gpu_sub_overlays = [GpuOverlay] │
│   subtitle overlays, │       │  gpu_logo = GpuOverlay(...)      │
│   logo overlay       │       │                                  │
│   to GPU VRAM        │       │  All data resident in VRAM       │
│                      │       │                                  │
│  Phase 2: Timeline   │       │                                  │
│   (pure Python, CPU) │       │                                  │
│                      │       │                                  │
│  Phase 3: Start      │       │                                  │
│   FFmpeg writer      │       │                                  │
│                      │       │                                  │
│  Phase 4: Frame loop │       │                                  │
│           │          │       │                                  │
│    for each frame:   │       │                                  │
│                      │       │                                  │
│    interp_position() │       │                                  │
│    (CPU — fast math) │       │                                  │
│           │          │       │                                  │
│           ├─────────────────►│  ┌─ GPU Ken Burns ─────────────┐ │
│           │          │       │  │ crop = gpu_src[y:y+h, x:x+w]│ │
│           │          │       │  │ seg = gpu_resize(crop, w, h) │ │
│           │          │       │  └──────────────────────────────┘ │
│           │          │       │                                  │
│           │          │       │  ┌─ GPU Alpha Blit ────────────┐ │
│           │          │       │  │ gpu_alpha_blit(seg, sub_ovl) │ │
│           │          │       │  └──────────────────────────────┘ │
│           │          │       │                                  │
│           │          │       │  ┌─ GPU Crossfade ─────────────┐ │
│           │          │       │  │ blend += seg.float32 * wt    │ │
│           │          │       │  └──────────────────────────────┘ │
│           │          │       │                                  │
│           │          │       │  ┌─ GPU Normalise ─────────────┐ │
│           │          │       │  │ frame = clip(blend/wt).uint8 │ │
│           │          │       │  └──────────────────────────────┘ │
│           │          │       │                                  │
│           │          │       │  ┌─ GPU Logo Blit ─────────────┐ │
│           │          │       │  │ gpu_alpha_blit(frame, logo)  │ │
│           │          │       │  └──────────────────────────────┘ │
│           │          │       │            │                      │
│           │◄─────────────────┤  cpu = cp.asnumpy(frame)         │
│           │          │       │                                  │
│    writer.write_frame│       │                                  │
│    (cpu_frame)       │       │                                  │
│      │               │       │                                  │
│      ▼               │       │                                  │
│    FFmpeg stdin pipe  │       │                                  │
│                      │       │                                  │
│  Phase 5: Finish     │       │                                  │
│   FFmpeg + free VRAM │──────►│  cp.get_default_memory_pool()    │
│                      │       │    .free_all_blocks()            │
└──────────────────────┘       └──────────────────────────────────┘
```

### 2.3 Data Transfer Timeline (Per Frame)

```
Time ──────────────────────────────────────────────────────►

CPU:  [interp_pos]                                 [write_frame]
       0.01ms                                        ~2-8ms
          │                                             ▲
          ▼                                             │
GPU:      [crop──►resize──►sub_blit──►blend──►norm──►logo_blit]
           └─────────────── ~3-6ms @ 4K ──────────────┘
                                                        │
                                                        ▼
Transfer:                                          [asnumpy ~1-2ms]

Total per-frame: ~4-10ms @ 4K  (vs ~40-80ms CPU-only)
```

### 2.4 GPU Memory Layout

```
┌─────────────────────────────────── GPU VRAM ──────────────────────────────┐
│                                                                          │
│  ┌─ Source Images ───────────────────────────────────────────────────┐    │
│  │  gpu_sources[0]: (H, W, 3) uint8   ~24 MB @ 4K (3840×2160×3)    │    │
│  │  gpu_sources[1]: (H, W, 3) uint8   ~24 MB @ 4K                  │    │
│  │  ...                                                             │    │
│  │  gpu_sources[N]: (H, W, 3) uint8   ~24 MB @ 4K                  │    │
│  │  Total: N × ~24 MB (e.g. 10 segments = ~240 MB)                 │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌─ Subtitle Overlays ──────────────────────────────────────────────┐    │
│  │  gpu_sub[0].rgb:   (h, w, 3) uint8     ~1-3 MB each             │    │
│  │  gpu_sub[0].alpha: (h, w, 1) float32   ~0.5-1 MB each           │    │
│  │  ... (typically 5-20 per segment)                                │    │
│  │  Total: ~20-100 MB for all segments                              │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌─ Logo Overlay ───────────────────────────────────────────────────┐    │
│  │  gpu_logo.rgb:   (h, w, 3) uint8       ~0.5 MB                  │    │
│  │  gpu_logo.alpha: (h, w, 1) float32     ~0.2 MB                  │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌─ Working Buffers (re-used each frame) ───────────────────────────┐    │
│  │  blend_buf:  (3840, 2160, 3) float32    ~95 MB                  │    │
│  │  frame_buf:  (3840, 2160, 3) uint8      ~24 MB                  │    │
│  │  crop_buf:   variable (temp)            ~0-24 MB                 │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  Estimated total: ~400-600 MB for a 10-segment 4K render                │
│  (fits comfortably in 4 GB+ VRAM)                                        │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Step-by-Step Instructions

### Step 1: Add CuPy Availability Detection

**File:** `backend/core_engine/fast_compositor.py`  
**Location:** After existing imports (after L36: `import numpy as np`)  
**Action:** Add a CuPy availability flag, similar to how `image_upscaler.py`
handles PyTorch availability (L95–102).

**Add the following code block:**

```python
# ---------------------------------------------------------------------------
# Optional CuPy (GPU acceleration) — graceful fallback to NumPy
# ---------------------------------------------------------------------------
_CUPY_AVAILABLE = False
_cp = None  # Module-level alias; will be cupy if available, else None

try:
    import cupy as cp
    import cupyx.scipy.ndimage  # For GPU-accelerated resize

    # Verify that a CUDA device is actually available
    cp.cuda.Device(0).compute_capability
    _CUPY_AVAILABLE = True
    _cp = cp
    logger.info(
        "CuPy %s detected — GPU-accelerated compositing enabled (device: %s)",
        cp.__version__,
        cp.cuda.runtime.getDeviceProperties(0)["name"].decode(),
    )
except ImportError:
    logger.info("CuPy not installed — using CPU compositing (NumPy)")
except Exception as exc:
    logger.warning(
        "CuPy installed but CUDA unavailable (%s) — falling back to CPU",
        exc,
    )
```

**Why `_cp` module alias?**
Throughout the code, we'll reference `_cp` instead of `cp` directly.
This avoids `NameError` if CuPy isn't installed, and makes the
GPU/CPU branch selection cleaner.

---

### Step 2: Create GPU-Aware Overlay Data Class

**File:** `backend/core_engine/fast_compositor.py`  
**Location:** After the `OverlaySlice` dataclass (after L66)  
**Action:** Add a `GpuOverlaySlice` dataclass that mirrors `OverlaySlice`
but holds CuPy arrays instead of NumPy arrays.

```python
@dataclass
class GpuOverlaySlice:
    """GPU-resident version of OverlaySlice.

    Holds CuPy arrays in GPU VRAM for fast alpha blending without
    CPU↔GPU transfers per frame.

    Only instantiated when CuPy is available (_CUPY_AVAILABLE is True).
    """
    rgb: "cp.ndarray"      # (H, W, 3) uint8 on GPU
    alpha: "cp.ndarray"    # (H, W, 1) float32 on GPU
    x: int
    y: int
    start_time: float
    end_time: float

    @staticmethod
    def from_cpu(overlay: OverlaySlice) -> "GpuOverlaySlice":
        """Transfer a CPU OverlaySlice to GPU memory."""
        return GpuOverlaySlice(
            rgb=_cp.asarray(overlay.rgb),
            alpha=_cp.asarray(overlay.alpha),
            x=overlay.x,
            y=overlay.y,
            start_time=overlay.start_time,
            end_time=overlay.end_time,
        )
```

---

### Step 3: Create GPU Alpha Blit Function

**File:** `backend/core_engine/fast_compositor.py`  
**Location:** After the existing `alpha_blit()` function (after L117)  
**Action:** Add a `gpu_alpha_blit()` function that performs the same
Porter-Duff "over" operation using CuPy arrays on the GPU.

```python
def gpu_alpha_blit(
    frame: "cp.ndarray",
    overlay: "GpuOverlaySlice",
) -> None:
    """Composite *overlay* onto *frame* in-place using CuPy (GPU).

    GPU equivalent of :func:`alpha_blit`.  All arrays must be CuPy
    arrays resident on the same CUDA device.

    The blending formula is identical to the CPU version:
        out = fg * alpha + bg * (1 - alpha)

    Args:
        frame: ``(H, W, 3)`` uint8 CuPy array — the target frame
            (modified in-place).
        overlay: GPU-resident overlay with position and alpha.
    """
    oh, ow = overlay.rgb.shape[:2]
    fh, fw = frame.shape[:2]

    # Compute clipped ROI
    x1 = max(overlay.x, 0)
    y1 = max(overlay.y, 0)
    x2 = min(overlay.x + ow, fw)
    y2 = min(overlay.y + oh, fh)

    if x2 <= x1 or y2 <= y1:
        return  # Off-screen

    # Source region within the overlay
    sx1 = x1 - overlay.x
    sy1 = y1 - overlay.y
    sx2 = sx1 + (x2 - x1)
    sy2 = sy1 + (y2 - y1)

    # Extract ROI (GPU slicing — no data transfer)
    roi = frame[y1:y2, x1:x2]
    fg = overlay.rgb[sy1:sy2, sx1:sx2]
    alpha = overlay.alpha[sy1:sy2, sx1:sx2]

    # Porter-Duff "over" — CuPy arithmetic (CUDA kernels)
    blended = (fg.astype(_cp.float32) * alpha
               + roi.astype(_cp.float32) * (1.0 - alpha))
    _cp.clip(blended, 0, 255, out=blended)
    frame[y1:y2, x1:x2] = blended.astype(_cp.uint8)
```

---

### Step 4: Create GPU Resize Helper

**File:** `backend/core_engine/fast_compositor.py`  
**Location:** After `gpu_alpha_blit()` (from Step 3)  
**Action:** Add a `gpu_resize()` function that replicates the
`cv2.resize()` behaviour on the GPU.

There are two strategies for GPU resize:

1. **`cupyx.scipy.ndimage.zoom()`** — built-in CuPy function, good
   quality, simple API.
2. **Hybrid approach** — crop on GPU, transfer small crop to CPU,
   `cv2.resize()` on CPU, transfer result back.  Fallback if
   `cupyx.scipy.ndimage.zoom` quality is insufficient.

We implement strategy 1 (pure GPU) as the default with strategy 2 as
a fallback controlled by a flag.

```python
def gpu_resize(
    crop: "cp.ndarray",
    target_width: int,
    target_height: int,
    is_downscale: bool = False,
) -> "cp.ndarray":
    """Resize a CuPy array on GPU using cupyx.scipy.ndimage.zoom.

    Args:
        crop: ``(H, W, 3)`` uint8 CuPy array — the cropped region.
        target_width: Desired output width.
        target_height: Desired output height.
        is_downscale: Whether the operation is a downscale (affects
            interpolation order).

    Returns:
        ``(target_height, target_width, 3)`` uint8 CuPy array.
    """
    src_h, src_w = crop.shape[:2]

    if src_h == target_height and src_w == target_width:
        return crop  # No resize needed

    # Compute zoom factors per axis
    zoom_h = target_height / src_h
    zoom_w = target_width / src_w

    # order=1 (bilinear) for all cases — good balance of speed/quality
    # order=0 (nearest) would be fastest but too blocky
    # order=3 (cubic) is slow on GPU for minimal quality gain
    order = 1

    # Zoom each channel — cupyx.scipy.ndimage.zoom on uint8 is fine
    # but we convert to float32 for smoother interpolation
    crop_f = crop.astype(_cp.float32)
    resized = cupyx.scipy.ndimage.zoom(
        crop_f,
        (zoom_h, zoom_w, 1.0),  # (H, W, C) zoom factors
        order=order,
        mode="nearest",         # Edge handling
    )
    return _cp.clip(resized, 0, 255).astype(_cp.uint8)
```

**Alternative: Hybrid CPU resize fallback** (add below `gpu_resize`):

```python
def _hybrid_resize_via_cpu(
    gpu_crop: "cp.ndarray",
    target_width: int,
    target_height: int,
    is_downscale: bool = False,
) -> "cp.ndarray":
    """Fallback: transfer crop to CPU, cv2.resize, transfer back.

    Use this if cupyx.scipy.ndimage.zoom quality is unacceptable.
    Still faster than full-CPU path because the crop is much smaller
    than the full source image.
    """
    cpu_crop = _cp.asnumpy(gpu_crop)
    interp = cv2.INTER_AREA if is_downscale else cv2.INTER_LINEAR
    cpu_resized = cv2.resize(
        cpu_crop, (target_width, target_height), interpolation=interp,
    )
    return _cp.asarray(cpu_resized)
```

---

### Step 5: Create GPU Memory Upload/Cleanup Helpers

**File:** `backend/core_engine/fast_compositor.py`  
**Location:** After GPU resize helpers  
**Action:** Add utility functions for bulk GPU upload and cleanup.

```python
def _upload_sources_to_gpu(
    segments_info: List[dict],
) -> List["cp.ndarray"]:
    """Transfer all source images to GPU VRAM.

    Args:
        segments_info: List of segment descriptor dicts, each
            containing a ``"source_image"`` key with a NumPy array.

    Returns:
        List of CuPy arrays (one per segment) in GPU VRAM.
    """
    gpu_sources = []
    total_bytes = 0
    for si in segments_info:
        gpu_img = _cp.asarray(si["source_image"])
        gpu_sources.append(gpu_img)
        total_bytes += gpu_img.nbytes
    logger.info(
        "Uploaded %d source images to GPU (%.1f MB)",
        len(gpu_sources), total_bytes / (1024 * 1024),
    )
    return gpu_sources


def _upload_overlays_to_gpu(
    segments_info: List[dict],
    logo_overlay: Optional[OverlaySlice],
) -> Tuple[List[List["GpuOverlaySlice"]], Optional["GpuOverlaySlice"]]:
    """Transfer all overlays (subtitles + logo) to GPU VRAM.

    Args:
        segments_info: Segment descriptors with ``"subtitle_overlays"``.
        logo_overlay: Optional CPU logo overlay.

    Returns:
        Tuple of (gpu_subtitle_overlays_per_segment, gpu_logo_overlay).
    """
    gpu_subs: List[List[GpuOverlaySlice]] = []
    for si in segments_info:
        seg_gpu_subs = [
            GpuOverlaySlice.from_cpu(ov)
            for ov in si["subtitle_overlays"]
        ]
        gpu_subs.append(seg_gpu_subs)

    gpu_logo = None
    if logo_overlay:
        gpu_logo = GpuOverlaySlice.from_cpu(logo_overlay)

    logger.info(
        "Uploaded overlays to GPU: %d segments of subtitles + logo=%s",
        len(gpu_subs), gpu_logo is not None,
    )
    return gpu_subs, gpu_logo


def _check_gpu_memory(segments_info: List[dict], width: int, height: int) -> bool:
    """Estimate GPU memory needed and check against available VRAM.

    Returns True if estimated usage fits within 80% of available VRAM.
    """
    if not _CUPY_AVAILABLE:
        return False

    # Estimate memory: source images + working buffers
    source_bytes = sum(
        si["source_image"].nbytes for si in segments_info
    )
    # Overlay bytes (rough estimate)
    overlay_bytes = sum(
        sum(ov.rgb.nbytes + ov.alpha.nbytes for ov in si["subtitle_overlays"])
        for si in segments_info
    )
    # Working buffers: 2 full frames (uint8 + float32)
    buffer_bytes = width * height * 3 * (1 + 4)  # uint8 + float32
    total_est = source_bytes + overlay_bytes + buffer_bytes

    # Query VRAM
    free_mem, total_mem = _cp.cuda.Device(0).mem_info
    threshold = int(total_mem * 0.80)

    logger.info(
        "GPU memory check: need ~%.0f MB, free %.0f MB / %.0f MB total "
        "(threshold 80%%: %.0f MB)",
        total_est / 1e6, free_mem / 1e6, total_mem / 1e6, threshold / 1e6,
    )

    if total_est > threshold:
        logger.warning(
            "Not enough GPU memory for compositing — falling back to CPU. "
            "Need %.0f MB but only %.0f MB available (80%% threshold).",
            total_est / 1e6, threshold / 1e6,
        )
        return False

    return True


def _cleanup_gpu_memory() -> None:
    """Free all CuPy memory pools to release VRAM."""
    if _CUPY_AVAILABLE:
        _cp.get_default_memory_pool().free_all_blocks()
        _cp.get_default_pinned_memory_pool().free_all_blocks()
        logger.info("GPU memory pools freed")
```

---

### Step 6: Modify `fast_render_segments()` — GPU Initialisation

**File:** `backend/core_engine/fast_compositor.py`  
**Location:** Inside `fast_render_segments()`, after Phase 1 (overlay
pre-rendering, around L610) and before Phase 2 (timeline calculation).  
**Action:** Add a new **Phase 1b** that uploads data to GPU if CuPy is
available and sufficient VRAM exists.

**Insert after the `segments_info` list is fully built (after L614):**

```python
    # ------------------------------------------------------------------
    # Phase 1b: Upload to GPU (if CuPy available)
    # ------------------------------------------------------------------
    use_gpu = False
    gpu_sources: List = []
    gpu_sub_overlays: List[List] = []
    gpu_logo: Optional[GpuOverlaySlice] = None

    if _CUPY_AVAILABLE:
        if _check_gpu_memory(segments_info, width, height):
            try:
                gpu_sources = _upload_sources_to_gpu(segments_info)
                gpu_sub_overlays, gpu_logo = _upload_overlays_to_gpu(
                    segments_info, logo_overlay,
                )
                use_gpu = True
                logger.info("GPU compositing enabled for this render")
            except Exception as gpu_exc:
                logger.warning(
                    "GPU upload failed (%s) — falling back to CPU",
                    gpu_exc,
                )
                gpu_sources = []
                gpu_sub_overlays = []
                gpu_logo = None
                use_gpu = False
                _cleanup_gpu_memory()
    else:
        logger.info("GPU compositing not available — using CPU path")
```

---

### Step 7: Modify Phase 4 Frame Loop — GPU Compositing Path

**File:** `backend/core_engine/fast_compositor.py`  
**Location:** Phase 4 frame loop (L663–766)  
**Action:** Add a GPU branch that runs when `use_gpu` is True.  The
existing CPU code remains as the `else` branch, completely unchanged.

This is the most critical change.  The GPU path mirrors the CPU path
exactly but uses CuPy arrays and GPU functions.

**Replace the Phase 4 loop body with a branched structure:**

```python
    # ------------------------------------------------------------------
    # Phase 4: Generate and write frames
    # ------------------------------------------------------------------
    render_start = time.perf_counter()
    last_progress_pct = 5

    for frame_idx in range(total_frames):
        t_global = frame_idx / fps

        if use_gpu:
            # ============================================================
            # GPU PATH (CuPy)
            # ============================================================
            total_weight = 0.0
            blended_float = _cp.zeros((height, width, 3), dtype=_cp.float32)

            for seg_idx, (seg_start_frame, seg_end_frame) in enumerate(
                segment_frame_ranges
            ):
                if frame_idx < seg_start_frame or frame_idx >= seg_end_frame:
                    continue

                si = segments_info[seg_idx]
                seg_duration = si["visual_duration"]
                t_local = (frame_idx - seg_start_frame) / fps

                # Crossfade weight (pure Python math — CPU)
                weight = 1.0
                fade_frames = int(crossfade_duration * fps)

                if total_segments > 1:
                    if seg_idx > 0:
                        frames_since_start = frame_idx - seg_start_frame
                        if frames_since_start < fade_frames:
                            weight = frames_since_start / fade_frames
                    if seg_idx < total_segments - 1:
                        frames_until_end = seg_end_frame - frame_idx - 1
                        if frames_until_end < fade_frames:
                            weight = min(weight, frames_until_end / fade_frames)

                # Ken Burns position (pure Python math — CPU)
                interp_x, interp_y = interpolate_position(
                    si["start_coords"], si["end_coords"],
                    t_local, seg_duration,
                )
                x = int(round(interp_x))
                y = int(round(interp_y))
                gpu_src = gpu_sources[seg_idx]
                src_h, src_w = gpu_src.shape[:2]
                x = max(0, min(x, src_w - si["crop_w"]))
                y = max(0, min(y, src_h - si["crop_h"]))

                # GPU crop (array slicing — no data transfer)
                gpu_crop = gpu_src[
                    y: y + si["crop_h"],
                    x: x + si["crop_w"],
                ]

                # GPU resize
                is_downscale = (
                    si["crop_w"] > width or si["crop_h"] > height
                )
                seg_frame = gpu_resize(
                    gpu_crop, width, height, is_downscale,
                )

                # GPU subtitle overlays
                for sub_ov in gpu_sub_overlays[seg_idx]:
                    if sub_ov.start_time <= t_local < sub_ov.end_time:
                        gpu_alpha_blit(seg_frame, sub_ov)

                # GPU crossfade accumulation
                blended_float += seg_frame.astype(_cp.float32) * weight
                total_weight += weight

            # GPU normalisation
            if total_weight > 0:
                frame_gpu = _cp.clip(
                    blended_float / total_weight, 0, 255
                ).astype(_cp.uint8)
            else:
                frame_gpu = _cp.zeros(
                    (height, width, 3), dtype=_cp.uint8
                )

            # GPU logo overlay
            if gpu_logo:
                gpu_alpha_blit(frame_gpu, gpu_logo)

            # Transfer to CPU for FFmpeg write
            frame = _cp.asnumpy(frame_gpu)

        else:
            # ============================================================
            # CPU PATH (NumPy) — original code, unchanged
            # ============================================================
            total_weight = 0.0
            blended_float = np.zeros((height, width, 3), dtype=np.float32)

            for seg_idx, (seg_start_frame, seg_end_frame) in enumerate(
                segment_frame_ranges
            ):
                if frame_idx < seg_start_frame or frame_idx >= seg_end_frame:
                    continue

                si = segments_info[seg_idx]
                seg_duration = si["visual_duration"]
                t_local = (frame_idx - seg_start_frame) / fps

                weight = 1.0
                fade_frames = int(crossfade_duration * fps)

                if total_segments > 1:
                    if seg_idx > 0:
                        frames_since_start = frame_idx - seg_start_frame
                        if frames_since_start < fade_frames:
                            weight = frames_since_start / fade_frames
                    if seg_idx < total_segments - 1:
                        frames_until_end = seg_end_frame - frame_idx - 1
                        if frames_until_end < fade_frames:
                            weight = min(weight, frames_until_end / fade_frames)

                interp_x, interp_y = interpolate_position(
                    si["start_coords"], si["end_coords"],
                    t_local, seg_duration,
                )
                x = int(round(interp_x))
                y = int(round(interp_y))
                src_h, src_w = si["source_image"].shape[:2]
                x = max(0, min(x, src_w - si["crop_w"]))
                y = max(0, min(y, src_h - si["crop_h"]))

                crop = si["source_image"][
                    y: y + si["crop_h"],
                    x: x + si["crop_w"],
                ]

                is_downscale = (
                    si["crop_w"] > width or si["crop_h"] > height
                )
                interp = cv2.INTER_AREA if is_downscale else cv2.INTER_LINEAR
                seg_frame = cv2.resize(
                    crop, (width, height), interpolation=interp,
                )

                for overlay in si["subtitle_overlays"]:
                    if overlay.start_time <= t_local < overlay.end_time:
                        alpha_blit(seg_frame, overlay)

                blended_float += seg_frame.astype(np.float32) * weight
                total_weight += weight

            if total_weight > 0:
                frame = np.clip(
                    blended_float / total_weight, 0, 255
                ).astype(np.uint8)
            else:
                frame = np.zeros((height, width, 3), dtype=np.uint8)

            if logo_overlay:
                alpha_blit(frame, logo_overlay)

        # Write frame to FFmpeg (both paths produce CPU uint8 array)
        writer.write_frame(frame)

        # Progress reporting (unchanged)
        pct = 5 + int((frame_idx / total_frames) * 90)
        if pct > last_progress_pct and pct <= 95:
            last_progress_pct = pct
            elapsed = time.perf_counter() - render_start
            fps_actual = (frame_idx + 1) / elapsed if elapsed > 0 else 0
            remaining = (
                (total_frames - frame_idx) / fps_actual
                if fps_actual > 0 else 0
            )
            if on_progress:
                on_progress(
                    pct, 100,
                    f"Rendering frames… {frame_idx + 1}/{total_frames} "
                    f"({fps_actual:.0f} fps, ~{remaining:.0f}s remaining)"
                    + (" [GPU]" if use_gpu else ""),
                )
```

---

### Step 8: Add GPU Cleanup to Phase 5

**File:** `backend/core_engine/fast_compositor.py`  
**Location:** Phase 5 (after L768, writer.finish())  
**Action:** Free GPU memory after rendering is complete.

**Add after `writer.finish()`:**

```python
    # Free GPU memory
    if use_gpu:
        del gpu_sources, gpu_sub_overlays, gpu_logo
        _cleanup_gpu_memory()
```

---

### Step 9: Add GPU Info to Return Dict

**File:** `backend/core_engine/fast_compositor.py`  
**Location:** Return statement at the end of `fast_render_segments()`
(around L785)  
**Action:** Include GPU usage information in the return dict.

**Modify the return dict:**

```python
    return {
        "frames_rendered": total_frames,
        "render_time": render_time,
        "avg_ms_per_frame": avg_ms,
        "gpu_accelerated": use_gpu,
    }
```

---

### Step 10: Update `requirements.txt`

**File:** `backend/requirements.txt`  
**Location:** After the existing PyTorch comment block (end of file)  
**Action:** Add an optional CuPy dependency note.

**Add:**

```
# GPU-accelerated compositing (CuPy — optional)
# CuPy provides 5-10x speedup for 4K frame compositing on CUDA GPUs.
# Install the package matching your CUDA version:
#   CUDA 12.x: pip install cupy-cuda12x
#   CUDA 11.x: pip install cupy-cuda11x
#   Auto-detect: pip install cupy  (slower — builds from source)
# CuPy is OPTIONAL — the system falls back to NumPy if not installed.
```

---

### Step 11: Add Logging for GPU vs CPU Path Selection

**File:** `backend/core_engine/fast_compositor.py`  
**Location:** At the start of Phase 4; also in the final log message  
**Action:** Ensure the render log clearly indicates which path was used.

**Modify the final log line (around L780):**

```python
    logger.info(
        "Fast render complete: %d frames in %.1fs (%.1f ms/frame, %.1f fps) [%s]",
        total_frames, render_time, avg_ms,
        total_frames / render_time if render_time > 0 else 0,
        "GPU/CuPy" if use_gpu else "CPU/NumPy",
    )
```

---

### Step 12: Write Unit Tests for GPU Compositing

**File:** `backend/core_engine/tests/test_gpu_compositing.py` (new file)  
**Action:** Create tests that validate GPU compositing produces
pixel-identical (or near-identical) output to the CPU path.

```python
"""
Tests for GPU-accelerated compositing (CuPy).

These tests verify:
1. CuPy availability detection works correctly.
2. GPU alpha_blit produces same results as CPU alpha_blit.
3. GPU resize produces similar results to cv2.resize.
4. Full GPU frame loop matches CPU frame loop output.
5. Graceful fallback when CuPy is unavailable.
"""

import unittest
import numpy as np

# Import from fast_compositor
from core_engine.fast_compositor import (
    OverlaySlice,
    alpha_blit,
    _CUPY_AVAILABLE,
)


class TestCuPyDetection(unittest.TestCase):
    """Test that CuPy availability detection works."""

    def test_cupy_flag_is_bool(self):
        self.assertIsInstance(_CUPY_AVAILABLE, bool)

    @unittest.skipUnless(_CUPY_AVAILABLE, "CuPy not available")
    def test_cupy_device_accessible(self):
        import cupy as cp
        # Should not raise
        cp.cuda.Device(0).compute_capability


@unittest.skipUnless(_CUPY_AVAILABLE, "CuPy not available")
class TestGpuAlphaBlit(unittest.TestCase):
    """Compare GPU alpha_blit output against CPU alpha_blit."""

    def test_solid_overlay(self):
        from core_engine.fast_compositor import (
            gpu_alpha_blit,
            GpuOverlaySlice,
        )
        import cupy as cp

        # Create a 100x100 black frame
        cpu_frame = np.zeros((100, 100, 3), dtype=np.uint8)
        gpu_frame = cp.asarray(cpu_frame.copy())

        # White overlay with 50% alpha at position (10, 10)
        overlay_rgb = np.full((20, 20, 3), 255, dtype=np.uint8)
        overlay_alpha = np.full((20, 20, 1), 0.5, dtype=np.float32)

        cpu_overlay = OverlaySlice(
            rgb=overlay_rgb, alpha=overlay_alpha,
            x=10, y=10, start_time=0.0, end_time=1.0,
        )
        gpu_overlay = GpuOverlaySlice.from_cpu(cpu_overlay)

        # Apply both
        alpha_blit(cpu_frame, cpu_overlay)
        gpu_alpha_blit(gpu_frame, gpu_overlay)

        # Compare
        gpu_result = cp.asnumpy(gpu_frame)
        np.testing.assert_array_almost_equal(
            cpu_frame.astype(float),
            gpu_result.astype(float),
            decimal=0,  # Allow ±1 rounding difference
        )


@unittest.skipUnless(_CUPY_AVAILABLE, "CuPy not available")
class TestGpuResize(unittest.TestCase):
    """Test GPU resize produces reasonable output."""

    def test_downscale(self):
        from core_engine.fast_compositor import gpu_resize
        import cupy as cp

        # 200x200 gradient image
        img = np.arange(200 * 200 * 3, dtype=np.uint8).reshape(200, 200, 3)
        gpu_img = cp.asarray(img)

        result = gpu_resize(gpu_img, 100, 100, is_downscale=True)
        self.assertEqual(result.shape, (100, 100, 3))
        self.assertEqual(result.dtype, cp.uint8)

    def test_upscale(self):
        from core_engine.fast_compositor import gpu_resize
        import cupy as cp

        img = np.arange(50 * 50 * 3, dtype=np.uint8).reshape(50, 50, 3)
        gpu_img = cp.asarray(img)

        result = gpu_resize(gpu_img, 200, 200, is_downscale=False)
        self.assertEqual(result.shape, (200, 200, 3))


if __name__ == "__main__":
    unittest.main()
```

---

### Step 13: Performance Benchmark Script

**File:** `backend/core_engine/tests/bench_gpu_compositing.py` (new file)  
**Action:** Create a benchmark script that compares CPU vs GPU
compositing performance at various resolutions.

```python
"""
Benchmark: CPU vs GPU compositing performance.

Usage:
    cd backend
    python -m core_engine.tests.bench_gpu_compositing

Measures per-frame compositing cost (excluding FFmpeg write) at
1080p, 2K, and 4K resolutions for:
  - NumPy (CPU)
  - CuPy  (GPU)
"""

import time
import numpy as np
import cv2

RESOLUTIONS = {
    "1080p": (1920, 1080),
    "2K":    (2560, 1440),
    "4K":    (3840, 2160),
}

N_FRAMES = 100


def bench_cpu(width, height, n_frames):
    """Benchmark CPU compositing."""
    source = np.random.randint(0, 255, (height * 2, width * 2, 3), dtype=np.uint8)
    overlay_rgb = np.random.randint(0, 255, (100, 300, 3), dtype=np.uint8)
    overlay_alpha = np.random.rand(100, 300, 1).astype(np.float32)

    start = time.perf_counter()
    for _ in range(n_frames):
        crop = source[100:100 + height + 200, 100:100 + width + 200]
        frame = cv2.resize(crop, (width, height))
        # Alpha blit
        roi = frame[height - 110:height - 10, 50:350]
        fg = overlay_rgb
        alpha = overlay_alpha
        blended = fg.astype(np.float32) * alpha + roi.astype(np.float32) * (1 - alpha)
        frame[height - 110:height - 10, 50:350] = np.clip(blended, 0, 255).astype(np.uint8)
    elapsed = time.perf_counter() - start
    return elapsed / n_frames * 1000  # ms per frame


def bench_gpu(width, height, n_frames):
    """Benchmark GPU compositing."""
    try:
        import cupy as cp
        import cupyx.scipy.ndimage
    except ImportError:
        return None

    source = cp.random.randint(0, 255, (height * 2, width * 2, 3), dtype=cp.uint8)
    overlay_rgb = cp.random.randint(0, 255, (100, 300, 3), dtype=cp.uint8)
    overlay_alpha = cp.random.random((100, 300, 1), dtype=cp.float32)

    # Warm up
    for _ in range(5):
        _ = cp.asnumpy(source[:10, :10])

    cp.cuda.Stream.null.synchronize()
    start = time.perf_counter()
    for _ in range(n_frames):
        crop = source[100:100 + height + 200, 100:100 + width + 200]
        crop_f = crop.astype(cp.float32)
        zoom_h = height / crop.shape[0]
        zoom_w = width / crop.shape[1]
        frame_f = cupyx.scipy.ndimage.zoom(crop_f, (zoom_h, zoom_w, 1.0), order=1)
        frame = cp.clip(frame_f, 0, 255).astype(cp.uint8)
        # Alpha blit
        roi = frame[height - 110:height - 10, 50:350]
        fg = overlay_rgb
        alpha = overlay_alpha
        blended = fg.astype(cp.float32) * alpha + roi.astype(cp.float32) * (1 - alpha)
        frame[height - 110:height - 10, 50:350] = cp.clip(blended, 0, 255).astype(cp.uint8)
        # Transfer to CPU
        _ = cp.asnumpy(frame)
    cp.cuda.Stream.null.synchronize()
    elapsed = time.perf_counter() - start
    return elapsed / n_frames * 1000  # ms per frame


if __name__ == "__main__":
    print(f"{'Resolution':<12} {'CPU (ms/fr)':<14} {'GPU (ms/fr)':<14} {'Speedup':<10}")
    print("-" * 50)
    for name, (w, h) in RESOLUTIONS.items():
        cpu_ms = bench_cpu(w, h, N_FRAMES)
        gpu_ms = bench_gpu(w, h, N_FRAMES)
        if gpu_ms:
            speedup = f"{cpu_ms / gpu_ms:.1f}x"
        else:
            gpu_ms_str = "N/A"
            speedup = "N/A"
        gpu_ms_str = f"{gpu_ms:.2f}" if gpu_ms else "N/A"
        print(f"{name:<12} {cpu_ms:<14.2f} {gpu_ms_str:<14} {speedup:<10}")
```

---

## 4. Expected Outcome

### 4.1 Performance Targets

| Resolution | CPU (NumPy) | GPU (CuPy) | Target Speedup |
|---|---|---|---|
| 1080p (1920×1080) | ~5–10 ms/frame | ~1–3 ms/frame | 3–5× |
| 2K (2560×1440) | ~15–25 ms/frame | ~2–4 ms/frame | 5–8× |
| 4K (3840×2160) | ~40–80 ms/frame | ~4–8 ms/frame | 5–10× |

### 4.2 Functional Requirements

1. **Pixel-accurate output** — GPU-rendered video must be visually
   identical to CPU-rendered video.  Minor rounding differences (±1
   per channel) are acceptable due to float32 arithmetic differences
   between CPU and GPU.

2. **Zero API changes** — `fast_render_segments()` keeps the same
   function signature, same parameters, same return dict structure
   (with an added `"gpu_accelerated"` key).  Callers in
   `video_renderer.py` (L1039) and `tasks.py` are unaffected.

3. **Graceful fallback** — the system must work identically when:
   - CuPy is not installed
   - No CUDA GPU is present
   - GPU memory is insufficient
   - CuPy import fails for any reason
   In all fallback cases, the existing NumPy code path runs.

4. **Correct frame ordering** — frames are written to FFmpeg in
   sequential order, identical to the current implementation.

5. **Progress reporting** — the `on_progress` callback continues to
   work, with an added `[GPU]` indicator in the message string when
   GPU compositing is active.

6. **CuPy/PyTorch coexistence** — CuPy and PyTorch (used by
   `image_upscaler.py`) can coexist.  Both use CUDA but maintain
   separate memory pools.  The image upscaler runs before the
   compositor, so there's no concurrent VRAM contention.

### 4.3 Memory Constraints

- **VRAM budget:** ≤80% of total GPU VRAM
- **Typical 4K render (10 segments):** ~400–600 MB VRAM
- **4 GB GPU:** handles up to ~15 segments at 4K
- **8 GB GPU:** handles up to ~30+ segments at 4K
- If VRAM is insufficient, automatic fallback to CPU

### 4.4 Logging Output

**When GPU is available and used:**
```
INFO  CuPy 13.1.0 detected — GPU-accelerated compositing enabled (device: NVIDIA RTX 4070)
INFO  GPU memory check: need ~450 MB, free 7200 MB / 8192 MB total (threshold 80%: 6554 MB)
INFO  Uploaded 10 source images to GPU (240.0 MB)
INFO  Uploaded overlays to GPU: 10 segments of subtitles + logo=True
INFO  GPU compositing enabled for this render
INFO  Fast render complete: 9000 frames in 45.2s (5.0 ms/frame, 199.1 fps) [GPU/CuPy]
```

**When GPU is not available (fallback):**
```
INFO  CuPy not installed — using CPU compositing (NumPy)
INFO  GPU compositing not available — using CPU path
INFO  Fast render complete: 9000 frames in 320.5s (35.6 ms/frame, 28.1 fps) [CPU/NumPy]
```

---

## 5. Verification Checklist

### 5.1 Pre-Implementation Checks

- [ ] **CuPy installation verified** — `python -c "import cupy; print(cupy.__version__)"` succeeds
- [ ] **CUDA device accessible** — `python -c "import cupy; print(cupy.cuda.Device(0).compute_capability)"` returns valid compute capability
- [ ] **Existing tests pass** — `cd backend && python -m pytest core_engine/tests/ -v` passes before any changes
- [ ] **Baseline performance measured** — run existing render at 1080p and 4K, record ms/frame

### 5.2 Implementation Checks

- [ ] **Step 1:** CuPy detection block added after imports (after L36)
- [ ] **Step 1:** `_CUPY_AVAILABLE` is `False` when CuPy is not installed
- [ ] **Step 1:** `_CUPY_AVAILABLE` is `False` when CUDA device is unavailable
- [ ] **Step 1:** No `ImportError` or `NameError` when CuPy is absent
- [ ] **Step 2:** `GpuOverlaySlice` dataclass created with `from_cpu()` static method
- [ ] **Step 2:** `GpuOverlaySlice.from_cpu()` correctly transfers rgb and alpha to GPU
- [ ] **Step 3:** `gpu_alpha_blit()` function created
- [ ] **Step 3:** `gpu_alpha_blit()` handles off-screen overlays (returns early)
- [ ] **Step 3:** `gpu_alpha_blit()` handles edge-clipped overlays correctly
- [ ] **Step 3:** `gpu_alpha_blit()` output matches `alpha_blit()` within ±1 per channel
- [ ] **Step 4:** `gpu_resize()` function created using `cupyx.scipy.ndimage.zoom`
- [ ] **Step 4:** `_hybrid_resize_via_cpu()` fallback function created
- [ ] **Step 4:** Resize output dimensions are correct: `(target_height, target_width, 3)`
- [ ] **Step 5:** `_upload_sources_to_gpu()` transfers all source images
- [ ] **Step 5:** `_upload_overlays_to_gpu()` transfers subtitles and logo
- [ ] **Step 5:** `_check_gpu_memory()` returns `False` when VRAM insufficient
- [ ] **Step 5:** `_cleanup_gpu_memory()` frees all CuPy memory pools
- [ ] **Step 6:** Phase 1b GPU init block added inside `fast_render_segments()`
- [ ] **Step 6:** `use_gpu` flag correctly set based on CuPy availability + VRAM check
- [ ] **Step 6:** GPU upload failure falls back to CPU gracefully (try/except)
- [ ] **Step 7:** GPU frame loop mirrors CPU frame loop logic exactly
- [ ] **Step 7:** CPU frame loop code is unchanged (preserved as `else` branch)
- [ ] **Step 7:** GPU crops use `gpu_sources[seg_idx]` not `si["source_image"]`
- [ ] **Step 7:** GPU subtitles use `gpu_sub_overlays[seg_idx]` not `si["subtitle_overlays"]`
- [ ] **Step 7:** GPU logo uses `gpu_logo` not `logo_overlay`
- [ ] **Step 7:** `_cp.asnumpy(frame_gpu)` transfers frame to CPU before `write_frame()`
- [ ] **Step 7:** Progress message includes `[GPU]` indicator when using GPU path
- [ ] **Step 8:** GPU cleanup runs after `writer.finish()` in Phase 5
- [ ] **Step 9:** Return dict includes `"gpu_accelerated": use_gpu`
- [ ] **Step 10:** `requirements.txt` updated with CuPy installation instructions
- [ ] **Step 11:** Final log message includes `[GPU/CuPy]` or `[CPU/NumPy]` tag

### 5.3 Post-Implementation Tests

- [ ] **CPU-only test:** Uninstall CuPy → render completes with CPU path → verify output
- [ ] **GPU test:** Install CuPy → render completes with GPU path → verify output
- [ ] **Visual comparison:** Render same project at 1080p with CPU and GPU → compare frames
- [ ] **4K render:** Render a 10-segment project at 4K with GPU → verify performance improvement
- [ ] **Memory test:** Monitor GPU VRAM during render → stays within 80% threshold
- [ ] **Cleanup test:** After render, GPU memory is freed → `nvidia-smi` shows reduced usage
- [ ] **Fallback test:** Set `_CUPY_AVAILABLE = False` manually → CPU path runs correctly
- [ ] **Edge case:** Single segment (no crossfade) renders correctly on GPU
- [ ] **Edge case:** Many overlapping segments (3+ active at once) blend correctly on GPU
- [ ] **Edge case:** No subtitles → GPU path still works
- [ ] **Edge case:** No logo → GPU path still works
- [ ] **Benchmark:** Run `bench_gpu_compositing.py` → confirm speedup ratios

### 5.4 Integration Tests

- [ ] **Video renderer:** `video_renderer.py` calls `fast_render_segments()` successfully with GPU → output valid
- [ ] **API test:** Trigger render via API → check logs show `[GPU/CuPy]` path → video plays correctly
- [ ] **Coexistence:** Run image upscaling (PyTorch GPU) then video render (CuPy GPU) in same session → both succeed

---

## 6. Notes for AI Agent

### 6.1 Critical Implementation Notes

1. **DO NOT modify the CPU code path.** The existing NumPy compositing
   code (Phase 4, lines 663–766) must remain **exactly as-is** inside
   the `else` branch.  The GPU path is an **additive** parallel branch
   controlled by the `use_gpu` flag.  If in doubt, compare the CPU
   branch against the original line-by-line.

2. **The `_cp` module alias pattern** is essential.  Never reference
   `cp` directly in function bodies — always use `_cp`.  This prevents
   `NameError` when CuPy is not installed because the `import cupy as cp`
   line is inside a try/except that may not execute.

3. **CuPy import block** must catch both `ImportError` (not installed)
   and generic `Exception` (CUDA runtime errors).  Follow the pattern
   used in `image_upscaler.py` (L95–102) for `_TORCH_AVAILABLE`.

4. **GPU→CPU transfer** (`_cp.asnumpy()`) happens **once per frame**,
   immediately before `writer.write_frame()`.  Do NOT transfer
   intermediate results (crops, blended buffers) to CPU — that defeats
   the purpose.

5. **`FFmpegFrameWriter.write_frame()`** at L462 expects a NumPy uint8
   array (it calls `.tobytes()`). CuPy arrays do NOT have a `.tobytes()`
   compatible with FFmpeg pipe. Always convert with `_cp.asnumpy()`.

6. **`cupyx.scipy.ndimage.zoom`** must be imported inside the try/except
   along with `cupy`.  If cupy is not installed, `cupyx` is also
   unavailable.  The `gpu_resize()` function should only be called
   when `use_gpu is True`.

7. **`interpolate_position()`** from `ken_burns.py` returns Python
   floats.  This runs on the CPU and is negligible cost (~0.001 ms).
   Do NOT try to GPU-accelerate this.

8. **Crossfade weight computation** is pure Python float math (no
   arrays).  Keep it on the CPU.  Only the array operations (crop,
   resize, blend, normalise) go to the GPU.

9. **Source images** in `segments_info[i]["source_image"]` are NumPy
   arrays from `load_and_prepare_image()` in `ken_burns.py`.  These
   are potentially large (4K+ with zoom headroom).  Upload them once
   to GPU in Phase 1b.  The `gpu_sources` list must be indexed by
   `seg_idx` in the same order as `segments_info`.

10. **Subtitle overlays** are stored per-segment in
    `segments_info[i]["subtitle_overlays"]` as a list of `OverlaySlice`
    objects.  Each must be converted to `GpuOverlaySlice` using
    `from_cpu()`.  The `gpu_sub_overlays` list must maintain the same
    nesting structure: `gpu_sub_overlays[seg_idx][sub_idx]`.

### 6.2 File Locations Quick Reference

| What | Where |
|---|---|
| CuPy detection block | `fast_compositor.py` — after L36 (imports) |
| `GpuOverlaySlice` class | `fast_compositor.py` — after L66 (`OverlaySlice`) |
| `gpu_alpha_blit()` | `fast_compositor.py` — after L117 (`alpha_blit`) |
| `gpu_resize()` | `fast_compositor.py` — after `gpu_alpha_blit()` |
| Upload helpers | `fast_compositor.py` — after `gpu_resize()` |
| Phase 1b (GPU init) | `fast_compositor.py` — inside `fast_render_segments()`, after L614 |
| Phase 4 (GPU loop) | `fast_compositor.py` — L663–766, branched by `use_gpu` |
| Phase 5 (GPU cleanup) | `fast_compositor.py` — after L768 |
| Return dict update | `fast_compositor.py` — around L785 |
| Requirements update | `requirements.txt` — end of file |
| Unit tests | `core_engine/tests/test_gpu_compositing.py` (new) |
| Benchmark | `core_engine/tests/bench_gpu_compositing.py` (new) |

### 6.3 Common Pitfalls

1. **Mixing CuPy and NumPy arrays** — Many NumPy functions silently
   accept CuPy arrays but produce wrong results or crash.  Always
   verify which array type you're operating on.  Use `isinstance(arr,
   cp.ndarray)` or check `type(arr)` during debugging.

2. **`cv2.resize()` on CuPy array** — OpenCV does NOT accept CuPy
   arrays.  This will crash.  Always use `gpu_resize()` on GPU or
   transfer to CPU first.

3. **CuPy memory fragmentation** — After many small allocations, GPU
   memory can fragment.  Call `_cleanup_gpu_memory()` after each render.

4. **CUDA stream synchronisation** — CuPy operations are asynchronous
   by default.  `_cp.asnumpy()` implicitly synchronises (waits for
   GPU to finish).  This is fine for our use case since we need the
   CPU result before writing to FFmpeg.

5. **`cupyx.scipy.ndimage.zoom` axis order** — the zoom factors tuple
   must match the array shape `(H, W, C)` → `(zoom_h, zoom_w, 1.0)`.
   Do NOT pass `(zoom_w, zoom_h, 1.0)` — this swaps width and height.

6. **Float32 precision differences** — CPU and GPU float32 arithmetic
   may produce slightly different results due to different rounding
   modes and fused multiply-add.  Expect ±1 difference per uint8
   channel.  This is normal and visually imperceptible.

7. **Multiple CUDA contexts** — If PyTorch (image_upscaler) and CuPy
   are both active, they may compete for the default CUDA device.
   CuPy and PyTorch can share the same device but maintain separate
   memory allocators.  Avoid running both simultaneously.  In
   StoryFlow, upscaling completes before rendering starts, so this
   is not an issue in the normal workflow.

8. **Large segment counts** — If a project has 50+ segments with 4K
   source images, the total GPU upload could exceed VRAM.  The
   `_check_gpu_memory()` function guards against this.  If it returns
   False, the entire render falls back to CPU.  A more sophisticated
   approach (uploading only active segments) could be added later.

### 6.4 Testing Strategy

1. **Unit tests** — test individual GPU functions (`gpu_alpha_blit`,
   `gpu_resize`, `GpuOverlaySlice.from_cpu`) in isolation.
2. **Comparison tests** — render the same frame with CPU and GPU paths,
   compare pixel values (allow ±1 tolerance).
3. **Integration test** — render a full 5-segment video with GPU and
   verify the output file is valid (playable, correct duration).
4. **Fallback test** — mock `_CUPY_AVAILABLE = False` and verify the
   CPU path runs without errors.
5. **Benchmark** — time 100 frames at 1080p, 2K, and 4K on both paths.

### 6.5 Future Enhancements (Out of Scope for This Feature)

- **CUDA RawKernel** for fused crop+resize+blend in a single kernel invocation
- **Pinned memory** (`cp.cuda.alloc_pinned_memory`) for faster GPU↔CPU transfers
- **Multi-GPU** support for extremely large renders
- **Partial GPU upload** — upload only the 2–3 segments active at any given time
- **CuPy + Feature 1.1 integration** — GPU compositing with multi-threaded frame generation (each thread gets its own CUDA stream)
- **NVJPEG** for GPU-accelerated source image decoding
- **Tensor Core** utilisation for float16 blending on RTX GPUs

### 6.6 Relationship to Other Features

| Feature | Relationship |
|---|---|
| **Feature 1.1** (Multi-Threaded Frame Generation) | Independent but complementary. Feature 1.1 parallelises across CPU cores; Feature 1.2 offloads to GPU. They can be combined later (each thread uses a CUDA stream). Implement 1.2 against the **current single-threaded** code. |
| **NVENC encoding** (`use_nvenc` flag in FFmpegFrameWriter) | Already supported. NVENC encodes with GPU hardware. CuPy compositing + NVENC encoding means frames stay "close to GPU" — only a CPU round-trip for the pipe write. |
| **Image Upscaler** (PyTorch GPU) | Runs before compositing. No VRAM contention. CuPy and PyTorch coexist on the same CUDA device. |

---

*End of Feature 1.2 implementation document.*
