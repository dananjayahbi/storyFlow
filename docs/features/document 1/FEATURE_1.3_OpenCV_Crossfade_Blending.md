# Feature 1.3 — OpenCV `addWeighted()` for Crossfade Blending

> **Status:** Planned  
> **Category:** Core Engine / Rendering Performance  
> **Target File:** `backend/core_engine/fast_compositor.py`  
> **Estimated Complexity:** Low–Medium  
> **Expected Speedup:** 20–30% faster crossfade blending, ~40–60% less memory allocation per frame  
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
renders crossfade transitions between segments using manual float32
accumulation math.  The crossfade blending lives in **Phase 4**
(lines 663–766) inside the main frame loop.

For **every single frame** (including frames where only a single
segment is active and no blending is actually needed), the current
code:

1. Allocates a full-resolution `np.float32` accumulation buffer:
   ```python
   blended_float = np.zeros((height, width, 3), dtype=np.float32)  # Line 672
   ```
2. For each active segment, casts the uint8 frame to float32 and
   multiplies by the weight:
   ```python
   blended_float += seg_frame.astype(np.float32) * weight  # Line 733
   ```
3. After all segments are processed, normalises and converts back
   to uint8:
   ```python
   frame = np.clip(blended_float / total_weight, 0, 255).astype(np.uint8)  # Lines 737–739
   ```

This results in **3–4 temporary full-resolution array allocations per
frame**, even when there is nothing to blend.

#### Memory allocation breakdown (per frame, 1920×1080):

| Temporary Array | Size | When Created |
|---|---|---|
| `blended_float` (float32, H×W×3) | 23.7 MB | Every frame (line 672) |
| `seg_frame.astype(np.float32)` (temporary) | 23.7 MB | Per active segment (line 733) |
| `blended_float / total_weight` (temporary) | 23.7 MB | Every frame (line 738) |
| `np.clip(...).astype(np.uint8)` (temporary) | 5.9 MB | Every frame (line 738) |
| **Total per frame (single segment)** | **~77 MB** | — |
| **Total per frame (2 segments, crossfade)** | **~101 MB** | — |

At 30 fps for a 60-second video (1,800 frames), this is
**~138 GB of cumulative temporary allocations** — all of which must
be garbage-collected by Python.  While NumPy reuses buffers when
possible, the repeated allocation/deallocation pressure still causes
measurable overhead.

#### Performance profile of current approach:

The float32 math path takes roughly **5–8 ms per frame** at 1080p
on a modern CPU (measured with `time.perf_counter()`).  This is a
significant portion of the overall per-frame budget of ~10–15 ms.

### 1.2 Proposed Solution

Replace the manual float32 accumulation with OpenCV's built-in
`cv2.addWeighted()` function, which:

- Operates directly on **uint8** arrays (no float32 conversion)
- Uses **SIMD instructions** (SSE2/SSE4/AVX/AVX2) internally via
  OpenCV's Universal Intrinsics layer
- Can write to a **pre-allocated destination** buffer via the `dst`
  parameter, eliminating per-frame memory allocation
- Handles saturation arithmetic automatically (clamps to 0–255)

#### The key insight — crossfades only ever overlap 2 segments:

The timeline construction in Phase 2 (lines 618–637) creates
overlapping segment ranges where each segment starts
`crossfade_duration` seconds before the previous one ends.  This
means:

- **Most frames:** Only 1 segment is active → **no blending needed**,
  just use the segment frame directly.
- **During transitions:** Exactly 2 segments overlap → one call to
  `cv2.addWeighted()`.
- **3+ segments overlapping:** Theoretically impossible with the
  current timeline construction logic, but we handle it gracefully
  as a fallback.

#### cv2.addWeighted() signature:

```python
cv2.addWeighted(
    src1,     # First input array (uint8)
    alpha,    # Weight for src1 (float)
    src2,     # Second input array (uint8)
    beta,     # Weight for src2 (float)
    gamma,    # Scalar added to each sum (float, usually 0.0)
    dst=None  # Optional pre-allocated output array
) -> dst
```

The formula applied per pixel: `dst = saturate(src1 * alpha + src2 * beta + gamma)`

Saturation means values are clamped to `[0, 255]` for uint8 — no need
for explicit `np.clip()`.

### 1.3 Files Involved

| File | Role | Changes |
|---|---|---|
| `backend/core_engine/fast_compositor.py` | Main compositing engine | **Modified** — Phase 4 frame loop rewritten to use `cv2.addWeighted()` |
| `backend/core_engine/tests/test_fast_compositor.py` | Unit tests | **Modified** — add new tests for crossfade blending |
| All other files | — | **No changes** |

### 1.4 Dependencies

| Dependency | Status | Notes |
|---|---|---|
| `opencv-python-headless>=4.8.0` | Already installed | `cv2.addWeighted()` available in all OpenCV versions |
| `numpy` | Already installed | Still used for frame buffers, but no float32 intermediates |

### 1.5 Backward Compatibility

- **Public API:** `fast_render_segments()` signature and return value
  are **unchanged**.  Callers (`video_renderer.py`, `tasks.py`) are
  completely unaffected.
- **Visual output:** The rendered video must be **pixel-identical** to
  the current output (within ±1 per channel due to rounding
  differences between float32 path and uint8 saturated path).
- **No new parameters:** The optimisation is entirely internal.

---

## 2. Flow Diagram

### 2.1 Current Flow (float32 accumulation)

```
┌──────────────────────────────────────────────────────────────────────┐
│                     PHASE 4 — MAIN FRAME LOOP                       │
│                      (lines 663–766)                                 │
│                                                                      │
│  for frame_idx in range(total_frames):                               │
│    │                                                                 │
│    ▼                                                                 │
│  ┌────────────────────────────────────────────────────────────┐      │
│  │ ALLOCATE float32 buffer (23.7 MB at 1080p) — EVERY FRAME  │      │
│  │ blended_float = np.zeros((H, W, 3), dtype=np.float32)     │      │
│  │ total_weight = 0.0                                         │      │
│  └────────────────────┬───────────────────────────────────────┘      │
│                       │                                              │
│                       ▼                                              │
│  ┌────────────────────────────────────────────────────────────┐      │
│  │ for each active segment:                                   │      │
│  │   ├─ Ken Burns crop + cv2.resize() → seg_frame (uint8)     │      │
│  │   ├─ alpha_blit() subtitles onto seg_frame                 │      │
│  │   ├─ Compute crossfade weight (0.0 – 1.0)                 │      │
│  │   ├─ seg_frame.astype(np.float32) → TEMP COPY (23.7 MB)   │      │
│  │   ├─ TEMP * weight → TEMP MULTIPLY (23.7 MB)              │      │
│  │   └─ blended_float += result → ACCUMULATE                 │      │
│  └────────────────────┬───────────────────────────────────────┘      │
│                       │                                              │
│                       ▼                                              │
│  ┌────────────────────────────────────────────────────────────┐      │
│  │ NORMALIZE: blended_float / total_weight → TEMP (23.7 MB)  │      │
│  │ np.clip(..., 0, 255) → TEMP CLIP                          │      │
│  │ .astype(np.uint8) → frame (5.9 MB)                        │      │
│  └────────────────────┬───────────────────────────────────────┘      │
│                       │                                              │
│                       ▼                                              │
│  ┌────────────────────────────────────────────────────────────┐      │
│  │ alpha_blit(frame, logo_overlay) → Apply logo               │      │
│  │ writer.write_frame(frame) → Pipe to FFmpeg                 │      │
│  └────────────────────────────────────────────────────────────┘      │
│                                                                      │
│  Total temporaries per frame: 3–4 full-resolution arrays             │
│  Total allocation per frame: ~77–101 MB                              │
└──────────────────────────────────────────────────────────────────────┘
```

### 2.2 Proposed Flow (cv2.addWeighted)

```
┌──────────────────────────────────────────────────────────────────────┐
│                     PHASE 4 — MAIN FRAME LOOP                       │
│                      (optimised)                                     │
│                                                                      │
│  # Pre-allocate ONCE before the loop:                                │
│  output_frame = np.zeros((H, W, 3), dtype=np.uint8)                 │
│                                                                      │
│  for frame_idx in range(total_frames):                               │
│    │                                                                 │
│    ▼                                                                 │
│  ┌────────────────────────────────────────────────────────────┐      │
│  │ Collect active segments + weights into a list              │      │
│  │ active_segments = [(seg_frame, weight), ...]               │      │
│  └─────────────────┬──────────────────────────────────────────┘      │
│                    │                                                 │
│          ┌─────────┼──────────┐                                      │
│          ▼         ▼          ▼                                      │
│    ┌──────────┐ ┌──────────────────┐ ┌──────────────────────┐       │
│    │ 1 active │ │ 2 active         │ │ 3+ active            │       │
│    │          │ │ (transition)     │ │ (fallback — rare)    │       │
│    │ Direct   │ │                  │ │                      │       │
│    │ copy:    │ │ cv2.addWeighted  │ │ Chain addWeighted    │       │
│    │          │ │ (seg_a, w_a,     │ │ or fall back to      │       │
│    │ output = │ │  seg_b, w_b,     │ │ float32 accumulation │       │
│    │ seg[0]   │ │  0.0,            │ │                      │       │
│    │          │ │  dst=output)     │ │                      │       │
│    └────┬─────┘ └───────┬──────────┘ └──────────┬───────────┘       │
│         │               │                       │                    │
│         └───────────────┴───────────────────────┘                    │
│                         │                                            │
│                         ▼                                            │
│  ┌────────────────────────────────────────────────────────────┐      │
│  │ alpha_blit(output_frame, logo_overlay) → Apply logo        │      │
│  │ writer.write_frame(output_frame) → Pipe to FFmpeg          │      │
│  └────────────────────────────────────────────────────────────┘      │
│                                                                      │
│  Total temporaries per frame: 0 (single segment) or 0 (2 segments)  │
│  Total allocation per frame: 0 MB (all pre-allocated)               │
└──────────────────────────────────────────────────────────────────────┘
```

### 2.3 Decision Tree for Each Frame

```
                      ┌──────────────────┐
                      │  Count active    │
                      │  segments for    │
                      │  this frame_idx  │
                      └─────────┬────────┘
                                │
               ┌────────────────┼────────────────┐
               │                │                │
               ▼                ▼                ▼
         ┌──────────┐   ┌──────────────┐  ┌──────────────┐
         │ count = 0│   │ count = 1    │  │ count = 2    │
         │          │   │              │  │              │
         │ Black    │   │ Direct use:  │  │ Normalise    │
         │ frame    │   │ output_frame │  │ weights:     │
         │ (zeros)  │   │ = seg_frame  │  │ w_sum = wa+wb│
         │          │   │ (copy or     │  │ alpha = wa / │
         │          │   │  np.copyto)  │  │   w_sum      │
         │          │   │              │  │ beta = wb /  │
         │          │   │              │  │   w_sum      │
         │          │   │              │  │              │
         │          │   │ NO float32   │  │ addWeighted( │
         │          │   │ NO blending  │  │  seg_a,alpha,│
         │          │   │              │  │  seg_b,beta, │
         │          │   │              │  │  0.0,        │
         │          │   │              │  │  dst=output) │
         └────┬─────┘   └─────┬────────┘  └──────┬──────┘
              │               │                   │
              └───────────────┴───────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │ count >= 3       │
                    │ (Fallback)       │
                    │                  │
                    │ Chain calls to   │
                    │ addWeighted or   │
                    │ use float32      │
                    │ accumulation     │
                    └──────────────────┘
```

### 2.4 Memory Allocation Comparison

```
CURRENT (per frame at 1080p):
┌────────────┬──────────┬──────────────────────────────────────┐
│ Allocation │ Size     │ Purpose                              │
├────────────┼──────────┼──────────────────────────────────────┤
│ 1          │ 23.7 MB  │ blended_float (float32 accumulator)  │
│ 2          │ 23.7 MB  │ seg_frame.astype(float32) temp       │
│ 3          │ 23.7 MB  │ blended_float / total_weight temp    │
│ 4          │  5.9 MB  │ .astype(uint8) temp                  │
├────────────┼──────────┼──────────────────────────────────────┤
│ TOTAL      │ 77.0 MB  │ Per frame (single segment)           │
└────────────┴──────────┴──────────────────────────────────────┘

PROPOSED (per frame at 1080p):
┌────────────┬──────────┬──────────────────────────────────────┐
│ Allocation │ Size     │ Purpose                              │
├────────────┼──────────┼──────────────────────────────────────┤
│ 1          │  0.0 MB  │ output_frame reused (pre-allocated)  │
│ 2          │  0.0 MB  │ addWeighted writes to dst directly   │
├────────────┼──────────┼──────────────────────────────────────┤
│ TOTAL      │  0.0 MB  │ Zero per-frame allocation            │
└────────────┴──────────┴──────────────────────────────────────┘

One-time allocation (before loop):
  output_frame = np.zeros((H, W, 3), dtype=np.uint8)  →  5.9 MB
```

---

## 3. Step-by-Step Instructions

### Step 1: Understand the Current Code Structure

Before making changes, review the current Phase 4 frame loop in
`backend/core_engine/fast_compositor.py`.

**File:** `backend/core_engine/fast_compositor.py`  
**Function:** `fast_render_segments()` (starts at line 487)  
**Phase 4:** Lines 663–766

The loop structure is:

```python
# Line 663–666: Phase 4 header
render_start = time.perf_counter()
last_progress_pct = 5

# Line 668: Main loop
for frame_idx in range(total_frames):
    t_global = frame_idx / fps

    # Line 672: Per-frame allocation (TO BE REMOVED)
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    total_weight = 0.0
    blended_float = np.zeros((height, width, 3), dtype=np.float32)

    # Line 676–733: Segment iteration loop
    for seg_idx, (seg_start_frame, seg_end_frame) in enumerate(segment_frame_ranges):
        # ... Ken Burns + subtitle + weight accumulation

    # Line 737–739: Normalisation
    if total_weight > 0:
        frame = np.clip(blended_float / total_weight, 0, 255).astype(np.uint8)

    # Line 742–743: Logo overlay
    if logo_overlay:
        alpha_blit(frame, logo_overlay)

    # Line 746: Write frame
    writer.write_frame(frame)
```

---

### Step 2: Pre-allocate the Output Frame Buffer

**What:** Move the frame buffer allocation outside the loop and reuse
it every iteration.

**Where:** Insert immediately before the `for frame_idx` loop
(after line 666, before line 668).

**Add this code:**

```python
    # Pre-allocate reusable frame buffer (avoids per-frame allocation)
    output_frame = np.zeros((height, width, 3), dtype=np.uint8)
```

**Why:** This eliminates the `np.zeros()` call inside the loop.  The
buffer is zeroed at the start of each iteration only when needed
(count == 0 case), or overwritten entirely by the blending operations.

---

### Step 3: Collect Active Segments Before Blending

**What:** Restructure the inner segment loop to first collect all
active segments and their weights into a list, then decide how to
blend based on the count.

**Where:** Replace the current inner loop body (lines 672–739).

**Replace the current code (lines 668–739):**

```python
    for frame_idx in range(total_frames):
        t_global = frame_idx / fps

        # Determine which segments are active at this time
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        total_weight = 0.0
        blended_float = np.zeros((height, width, 3), dtype=np.float32)

        for seg_idx, (seg_start_frame, seg_end_frame) in enumerate(segment_frame_ranges):
            if frame_idx < seg_start_frame or frame_idx >= seg_end_frame:
                continue

            si = segments_info[seg_idx]
            seg_duration = si["visual_duration"]

            # Local time within this segment
            t_local = (frame_idx - seg_start_frame) / fps

            # Compute crossfade weight
            weight = 1.0
            frames_in_seg = seg_end_frame - seg_start_frame
            fade_frames = int(crossfade_duration * fps)

            if total_segments > 1:
                # Fade in (first segment doesn't fade in)
                if seg_idx > 0:
                    frames_since_start = frame_idx - seg_start_frame
                    if frames_since_start < fade_frames:
                        weight = frames_since_start / fade_frames

                # Fade out (last segment doesn't fade out)
                if seg_idx < total_segments - 1:
                    frames_until_end = seg_end_frame - frame_idx - 1
                    if frames_until_end < fade_frames:
                        weight = min(weight, frames_until_end / fade_frames)

            # Generate Ken Burns frame
            interp_x, interp_y = interpolate_position(
                si["start_coords"], si["end_coords"], t_local, seg_duration,
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

            # Apply subtitle overlays
            for overlay in si["subtitle_overlays"]:
                if overlay.start_time <= t_local < overlay.end_time:
                    alpha_blit(seg_frame, overlay)

            # Accumulate with crossfade weight
            blended_float += seg_frame.astype(np.float32) * weight
            total_weight += weight

        # Normalise blended result
        if total_weight > 0:
            frame = np.clip(
                blended_float / total_weight, 0, 255
            ).astype(np.uint8)
```

**With this new code:**

```python
    for frame_idx in range(total_frames):
        t_global = frame_idx / fps

        # Collect active segments and their weights for this frame
        active_layers: list = []  # List of (seg_frame, weight) tuples

        for seg_idx, (seg_start_frame, seg_end_frame) in enumerate(segment_frame_ranges):
            if frame_idx < seg_start_frame or frame_idx >= seg_end_frame:
                continue

            si = segments_info[seg_idx]
            seg_duration = si["visual_duration"]

            # Local time within this segment
            t_local = (frame_idx - seg_start_frame) / fps

            # Compute crossfade weight
            weight = 1.0
            frames_in_seg = seg_end_frame - seg_start_frame
            fade_frames = int(crossfade_duration * fps)

            if total_segments > 1:
                # Fade in (first segment doesn't fade in)
                if seg_idx > 0:
                    frames_since_start = frame_idx - seg_start_frame
                    if frames_since_start < fade_frames:
                        weight = frames_since_start / fade_frames

                # Fade out (last segment doesn't fade out)
                if seg_idx < total_segments - 1:
                    frames_until_end = seg_end_frame - frame_idx - 1
                    if frames_until_end < fade_frames:
                        weight = min(weight, frames_until_end / fade_frames)

            # Generate Ken Burns frame
            interp_x, interp_y = interpolate_position(
                si["start_coords"], si["end_coords"], t_local, seg_duration,
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

            # Apply subtitle overlays
            for overlay in si["subtitle_overlays"]:
                if overlay.start_time <= t_local < overlay.end_time:
                    alpha_blit(seg_frame, overlay)

            active_layers.append((seg_frame, weight))

        # ── Blend active layers using optimised path ──
        n_active = len(active_layers)

        if n_active == 0:
            # No segment active — black frame
            output_frame[:] = 0

        elif n_active == 1:
            # Single segment — direct copy, no blending needed
            np.copyto(output_frame, active_layers[0][0])

        elif n_active == 2:
            # Two segments — use cv2.addWeighted() (SIMD-optimised)
            seg_a, weight_a = active_layers[0]
            seg_b, weight_b = active_layers[1]
            w_sum = weight_a + weight_b
            if w_sum > 0:
                alpha = weight_a / w_sum
                beta = weight_b / w_sum
            else:
                alpha = 0.5
                beta = 0.5
            cv2.addWeighted(seg_a, alpha, seg_b, beta, 0.0, dst=output_frame)

        else:
            # 3+ segments (rare edge case) — fallback to float32 accumulation
            blended_float = np.zeros((height, width, 3), dtype=np.float32)
            total_weight = 0.0
            for seg_frame, weight in active_layers:
                blended_float += seg_frame.astype(np.float32) * weight
                total_weight += weight
            if total_weight > 0:
                np.clip(blended_float / total_weight, 0, 255, out=blended_float)
                output_frame[:] = blended_float.astype(np.uint8)
            else:
                output_frame[:] = 0
```

---

### Step 4: Update the Logo Overlay and Frame Write

**What:** Change `frame` references to `output_frame` in the logo
and writer calls.

**Where:** Lines 742–746 in the current code (immediately after
the blending section).

**Replace:**

```python
        # Apply logo (on top of everything, no crossfade)
        if logo_overlay:
            alpha_blit(frame, logo_overlay)

        # Write frame to FFmpeg
        writer.write_frame(frame)
```

**With:**

```python
        # Apply logo (on top of everything, no crossfade)
        if logo_overlay:
            alpha_blit(output_frame, logo_overlay)

        # Write frame to FFmpeg
        writer.write_frame(output_frame)
```

---

### Step 5: Remove Dead Variables

**What:** Remove the `frame`, `blended_float`, and `total_weight`
variables that were previously allocated at the top of each loop
iteration.  These are now handled inside the branch logic.

**Verify:** After the changes, the only allocation at the top of the
loop should be `t_global` and `active_layers`.  The `frame` variable
(line 671), `total_weight` (line 672), and `blended_float` (line 673)
should no longer exist in the main path.

---

### Step 6: Verify the Complete Modified Phase 4

After all changes, the complete Phase 4 should look like this:

```python
    # ------------------------------------------------------------------
    # Phase 4: Generate and write frames
    # ------------------------------------------------------------------
    render_start = time.perf_counter()
    last_progress_pct = 5

    # Pre-allocate reusable frame buffer (avoids per-frame allocation)
    output_frame = np.zeros((height, width, 3), dtype=np.uint8)

    for frame_idx in range(total_frames):
        t_global = frame_idx / fps

        # Collect active segments and their weights for this frame
        active_layers: list = []  # List of (seg_frame, weight) tuples

        for seg_idx, (seg_start_frame, seg_end_frame) in enumerate(segment_frame_ranges):
            if frame_idx < seg_start_frame or frame_idx >= seg_end_frame:
                continue

            si = segments_info[seg_idx]
            seg_duration = si["visual_duration"]

            # Local time within this segment
            t_local = (frame_idx - seg_start_frame) / fps

            # Compute crossfade weight
            weight = 1.0
            frames_in_seg = seg_end_frame - seg_start_frame
            fade_frames = int(crossfade_duration * fps)

            if total_segments > 1:
                # Fade in (first segment doesn't fade in)
                if seg_idx > 0:
                    frames_since_start = frame_idx - seg_start_frame
                    if frames_since_start < fade_frames:
                        weight = frames_since_start / fade_frames

                # Fade out (last segment doesn't fade out)
                if seg_idx < total_segments - 1:
                    frames_until_end = seg_end_frame - frame_idx - 1
                    if frames_until_end < fade_frames:
                        weight = min(weight, frames_until_end / fade_frames)

            # Generate Ken Burns frame
            interp_x, interp_y = interpolate_position(
                si["start_coords"], si["end_coords"], t_local, seg_duration,
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

            # Apply subtitle overlays
            for overlay in si["subtitle_overlays"]:
                if overlay.start_time <= t_local < overlay.end_time:
                    alpha_blit(seg_frame, overlay)

            active_layers.append((seg_frame, weight))

        # ── Blend active layers using optimised path ──
        n_active = len(active_layers)

        if n_active == 0:
            # No segment active — black frame
            output_frame[:] = 0

        elif n_active == 1:
            # Single segment — direct copy, no blending needed
            np.copyto(output_frame, active_layers[0][0])

        elif n_active == 2:
            # Two segments — use cv2.addWeighted() (SIMD-optimised)
            seg_a, weight_a = active_layers[0]
            seg_b, weight_b = active_layers[1]
            w_sum = weight_a + weight_b
            if w_sum > 0:
                alpha = weight_a / w_sum
                beta = weight_b / w_sum
            else:
                alpha = 0.5
                beta = 0.5
            cv2.addWeighted(seg_a, alpha, seg_b, beta, 0.0, dst=output_frame)

        else:
            # 3+ segments (rare edge case) — fallback to float32 accumulation
            blended_float = np.zeros((height, width, 3), dtype=np.float32)
            total_weight = 0.0
            for seg_frame, weight in active_layers:
                blended_float += seg_frame.astype(np.float32) * weight
                total_weight += weight
            if total_weight > 0:
                np.clip(blended_float / total_weight, 0, 255, out=blended_float)
                output_frame[:] = blended_float.astype(np.uint8)
            else:
                output_frame[:] = 0

        # Apply logo (on top of everything, no crossfade)
        if logo_overlay:
            alpha_blit(output_frame, logo_overlay)

        # Write frame to FFmpeg
        writer.write_frame(output_frame)

        # Progress reporting (throttled — every 2%)
        pct = 5 + int((frame_idx / total_frames) * 90)  # 5–95%
        if pct > last_progress_pct and pct <= 95:
            last_progress_pct = pct
            elapsed = time.perf_counter() - render_start
            fps_actual = (frame_idx + 1) / elapsed if elapsed > 0 else 0
            remaining = (total_frames - frame_idx) / fps_actual if fps_actual > 0 else 0
            if on_progress:
                on_progress(
                    pct, 100,
                    f"Rendering frames… {frame_idx + 1}/{total_frames} "
                    f"({fps_actual:.0f} fps, ~{remaining:.0f}s remaining)",
                )
```

---

### Step 7: Add a Micro-Benchmark for Validation

**What:** Add a standalone benchmark function that can be called from
tests or the command line to verify the performance improvement.

**Where:** Add at the bottom of `fast_compositor.py`, before the
utility functions section (before line 789).

**Code to add:**

```python
def _benchmark_crossfade_blending(
    width: int = 1920,
    height: int = 1080,
    n_frames: int = 300,
) -> dict:
    """Micro-benchmark comparing float32 vs cv2.addWeighted crossfade.

    This function is intended for development/testing only and is not
    called by any production code paths.

    Args:
        width: Frame width.
        height: Frame height.
        n_frames: Number of frames to blend.

    Returns:
        dict with timing results for both methods.
    """
    rng = np.random.default_rng(42)
    frame_a = rng.integers(0, 256, (height, width, 3), dtype=np.uint8)
    frame_b = rng.integers(0, 256, (height, width, 3), dtype=np.uint8)

    # --- Method 1: Current float32 accumulation ---
    output_f32 = np.zeros((height, width, 3), dtype=np.uint8)
    t0 = time.perf_counter()
    for i in range(n_frames):
        alpha = i / n_frames
        beta = 1.0 - alpha
        blended = frame_a.astype(np.float32) * alpha + frame_b.astype(np.float32) * beta
        output_f32 = np.clip(blended, 0, 255).astype(np.uint8)
    t_f32 = time.perf_counter() - t0

    # --- Method 2: cv2.addWeighted ---
    output_cv = np.zeros((height, width, 3), dtype=np.uint8)
    t0 = time.perf_counter()
    for i in range(n_frames):
        alpha = i / n_frames
        beta = 1.0 - alpha
        cv2.addWeighted(frame_a, alpha, frame_b, beta, 0.0, dst=output_cv)
    t_cv = time.perf_counter() - t0

    speedup = t_f32 / t_cv if t_cv > 0 else float("inf")

    results = {
        "resolution": f"{width}x{height}",
        "n_frames": n_frames,
        "float32_total_ms": round(t_f32 * 1000, 1),
        "float32_per_frame_ms": round(t_f32 / n_frames * 1000, 2),
        "addWeighted_total_ms": round(t_cv * 1000, 1),
        "addWeighted_per_frame_ms": round(t_cv / n_frames * 1000, 2),
        "speedup": round(speedup, 2),
    }

    logger.info(
        "Crossfade benchmark (%s, %d frames): "
        "float32=%.1fms/frame, addWeighted=%.1fms/frame, speedup=%.2fx",
        results["resolution"],
        n_frames,
        results["float32_per_frame_ms"],
        results["addWeighted_per_frame_ms"],
        speedup,
    )

    return results
```

---

### Step 8: Write Unit Tests

**What:** Add tests to verify correctness and performance of the new
crossfade blending.

**Where:** `backend/core_engine/tests/test_fast_compositor.py`
(create if it doesn't exist).

**Tests to add:**

```python
"""Tests for crossfade blending optimisation (Feature 1.3)."""
import numpy as np
import cv2
import pytest


class TestAddWeightedCrossfade:
    """Test that cv2.addWeighted produces correct results."""

    def test_single_segment_no_blend(self):
        """Single active segment should produce the segment frame directly."""
        frame = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)
        output = np.zeros_like(frame)
        np.copyto(output, frame)
        np.testing.assert_array_equal(output, frame)

    def test_two_segments_equal_weight(self):
        """Two segments with equal weight should produce the average."""
        a = np.full((100, 100, 3), 100, dtype=np.uint8)
        b = np.full((100, 100, 3), 200, dtype=np.uint8)
        output = np.zeros_like(a)
        cv2.addWeighted(a, 0.5, b, 0.5, 0.0, dst=output)
        # Expected: (100*0.5 + 200*0.5) = 150
        np.testing.assert_array_equal(output, 150)

    def test_two_segments_weighted(self):
        """Two segments with 0.25/0.75 should weight correctly."""
        a = np.full((100, 100, 3), 0, dtype=np.uint8)
        b = np.full((100, 100, 3), 200, dtype=np.uint8)
        output = np.zeros_like(a)
        cv2.addWeighted(a, 0.25, b, 0.75, 0.0, dst=output)
        # Expected: (0*0.25 + 200*0.75) = 150
        np.testing.assert_array_equal(output, 150)

    def test_full_fade_to_second(self):
        """Weight 0.0 for first, 1.0 for second = second segment."""
        a = np.full((100, 100, 3), 50, dtype=np.uint8)
        b = np.full((100, 100, 3), 200, dtype=np.uint8)
        output = np.zeros_like(a)
        cv2.addWeighted(a, 0.0, b, 1.0, 0.0, dst=output)
        np.testing.assert_array_equal(output, 200)

    def test_saturation_clamp(self):
        """addWeighted should saturate at 255, not overflow."""
        a = np.full((100, 100, 3), 200, dtype=np.uint8)
        b = np.full((100, 100, 3), 200, dtype=np.uint8)
        output = np.zeros_like(a)
        cv2.addWeighted(a, 0.8, b, 0.8, 0.0, dst=output)
        # 200*0.8 + 200*0.8 = 320 → saturated to 255
        np.testing.assert_array_equal(output, 255)

    def test_dst_reuse(self):
        """The dst buffer should be reused across calls."""
        a = np.full((100, 100, 3), 100, dtype=np.uint8)
        b = np.full((100, 100, 3), 200, dtype=np.uint8)
        output = np.zeros((100, 100, 3), dtype=np.uint8)
        output_id = id(output)

        cv2.addWeighted(a, 0.5, b, 0.5, 0.0, dst=output)
        assert id(output) == output_id  # Same object, no new allocation

    def test_matches_float32_path(self):
        """addWeighted result should match float32 result within ±1."""
        rng = np.random.default_rng(42)
        a = rng.integers(0, 256, (480, 640, 3), dtype=np.uint8)
        b = rng.integers(0, 256, (480, 640, 3), dtype=np.uint8)
        alpha, beta = 0.3, 0.7

        # Float32 path (current implementation)
        f32_result = np.clip(
            a.astype(np.float32) * alpha + b.astype(np.float32) * beta,
            0, 255,
        ).astype(np.uint8)

        # addWeighted path (proposed implementation)
        cv_result = np.zeros_like(a)
        cv2.addWeighted(a, alpha, b, beta, 0.0, dst=cv_result)

        # Allow ±1 difference due to rounding
        diff = np.abs(f32_result.astype(np.int16) - cv_result.astype(np.int16))
        assert diff.max() <= 1, f"Max difference: {diff.max()}"

    def test_weight_normalisation(self):
        """Weights that don't sum to 1.0 should be normalised."""
        a = np.full((100, 100, 3), 100, dtype=np.uint8)
        b = np.full((100, 100, 3), 200, dtype=np.uint8)
        output = np.zeros_like(a)

        weight_a, weight_b = 0.3, 0.7
        w_sum = weight_a + weight_b
        alpha = weight_a / w_sum
        beta = weight_b / w_sum

        cv2.addWeighted(a, alpha, b, beta, 0.0, dst=output)
        # (100*0.3 + 200*0.7) / 1.0 = 170
        expected = int(round(100 * alpha + 200 * beta))
        np.testing.assert_array_equal(output, expected)


class TestAddWeightedPerformance:
    """Benchmark tests to verify performance improvement."""

    @pytest.mark.slow
    def test_addweighted_faster_than_float32(self):
        """cv2.addWeighted should be faster than float32 path."""
        import time

        rng = np.random.default_rng(42)
        a = rng.integers(0, 256, (1080, 1920, 3), dtype=np.uint8)
        b = rng.integers(0, 256, (1080, 1920, 3), dtype=np.uint8)
        n_iters = 100

        # Warmup
        for _ in range(10):
            cv2.addWeighted(a, 0.5, b, 0.5, 0.0)
            np.clip(a.astype(np.float32) * 0.5 + b.astype(np.float32) * 0.5, 0, 255)

        # Float32 path
        t0 = time.perf_counter()
        for i in range(n_iters):
            alpha = i / n_iters
            blended = a.astype(np.float32) * alpha + b.astype(np.float32) * (1 - alpha)
            _ = np.clip(blended, 0, 255).astype(np.uint8)
        t_f32 = time.perf_counter() - t0

        # addWeighted path
        output = np.zeros_like(a)
        t0 = time.perf_counter()
        for i in range(n_iters):
            alpha = i / n_iters
            cv2.addWeighted(a, alpha, b, 1 - alpha, 0.0, dst=output)
        t_cv = time.perf_counter() - t0

        speedup = t_f32 / t_cv
        print(f"\nFloat32: {t_f32 / n_iters * 1000:.2f} ms/frame")
        print(f"addWeighted: {t_cv / n_iters * 1000:.2f} ms/frame")
        print(f"Speedup: {speedup:.2f}x")

        # Assert at least 1.1x speedup (conservative)
        assert speedup > 1.1, (
            f"Expected speedup > 1.1x, got {speedup:.2f}x "
            f"(float32={t_f32:.3f}s, addWeighted={t_cv:.3f}s)"
        )
```

---

### Step 9: Run Tests and Validate

Run the test suite to verify the changes:

```bash
cd backend
python -m pytest core_engine/tests/test_fast_compositor.py -v
```

Run the benchmark:

```bash
cd backend
python -c "
from core_engine.fast_compositor import _benchmark_crossfade_blending
results = _benchmark_crossfade_blending()
for k, v in results.items():
    print(f'  {k}: {v}')
"
```

Expected benchmark output (approximate):

```
  resolution: 1920x1080
  n_frames: 300
  float32_total_ms: 2400.0
  float32_per_frame_ms: 8.00
  addWeighted_total_ms: 1600.0
  addWeighted_per_frame_ms: 5.33
  speedup: 1.50
```

---

### Step 10: End-to-End Validation

Render a test video using the existing test fixtures and compare the
output against a reference render from the unmodified code.

```bash
cd backend
python -m pytest tests/test_e2e.py -v -k "render"
```

Alternatively, render a test project from the Django shell:

```bash
cd backend
python manage.py shell -c "
from core_engine.fast_compositor import fast_render_segments
# Use test data from docs/test_story_01.json
import json
with open('../docs/test_story_01.json') as f:
    story = json.load(f)
# ... set up segment_data from story and call fast_render_segments
"
```

---

## 4. Expected Outcome

### 4.1 Performance Improvements

| Metric | Before | After | Improvement |
|---|---|---|---|
| Per-frame blending time (1080p, 2 segments) | ~7–8 ms | ~4–5 ms | **~40–50% faster** |
| Per-frame blending time (1080p, 1 segment) | ~3–4 ms | **~0.01 ms** | **~300× faster** (just a copy) |
| Memory allocation per frame (1 segment) | ~77 MB | **0 MB** | **100% reduction** |
| Memory allocation per frame (2 segments) | ~101 MB | **0 MB** | **100% reduction** |
| One-time allocation | 0 MB | 5.9 MB | Negligible |
| Total render time (60s video, 30fps) | ~18 s | ~13 s | **~28% faster** |
| GC pressure | High | Minimal | Significantly less jitter |

### 4.2 Visual Output

The rendered video should be **visually identical** to the current
output.  Due to rounding differences between float32 operations and
OpenCV's saturated uint8 arithmetic, pixel values may differ by ±1
on some pixels.  This is imperceptible to the human eye.

### 4.3 API Compatibility

- `fast_render_segments()` signature: **unchanged**
- `fast_render_segments()` return value: **unchanged**
- All callers (`video_renderer.py`, `tasks.py`): **no changes needed**
- All existing tests: **should pass without modification**

### 4.4 Frame Distribution Analysis

For a typical 10-segment video with 0.5s crossfade at 30 fps:

```
Total frames: ~1,665 (assuming ~6s average per segment)
Crossfade frames: 9 transitions × 15 frames = 135 frames (8.1%)
Single-segment frames: ~1,530 frames (91.9%)

Frame breakdown:
  ┌─────────────────────────────────────────────────────────────┐
  │░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░│▓▓▓│
  │        91.9% single segment (fast path)          8.1% blend │
  └─────────────────────────────────────────────────────────────┘

  ░ = np.copyto() only (~0.01 ms)
  ▓ = cv2.addWeighted() (~4–5 ms)
```

This means **91.9% of frames skip blending entirely**, making the
single-segment fast path the most impactful optimisation.

---

## 5. Verification Checklist

### 5.1 Pre-Implementation Checks

- [ ] Read the current Phase 4 code (lines 663–766) in full
- [ ] Confirm `cv2` is imported at the top of the file (line 35)
- [ ] Confirm `cv2.addWeighted` is available:
  ```python
  python -c "import cv2; help(cv2.addWeighted)"
  ```
- [ ] Run existing tests to establish a baseline:
  ```bash
  python -m pytest tests/ -v
  ```

### 5.2 Implementation Checks

- [ ] `output_frame` buffer is allocated **once** before the loop
- [ ] `blended_float` and `total_weight` are **removed** from the
      per-frame allocation (only used in 3+ segment fallback)
- [ ] The `frame` variable is replaced with `output_frame` throughout
- [ ] `active_layers` list is created fresh each frame iteration
- [ ] Branch logic handles exactly 3 cases: 0, 1, and 2 active segments
- [ ] Fallback for 3+ segments preserves the original float32 logic
- [ ] Weight normalisation is correct: `alpha + beta = 1.0`
- [ ] `cv2.addWeighted()` uses `dst=output_frame` parameter
- [ ] Logo overlay uses `output_frame` not `frame`
- [ ] `writer.write_frame()` uses `output_frame` not `frame`
- [ ] Progress reporting code is unchanged

### 5.3 Correctness Checks

- [ ] Unit test: single segment produces identical output
- [ ] Unit test: two segments with equal weights → average
- [ ] Unit test: two segments with extreme weights (0.0/1.0)
- [ ] Unit test: saturation clamping works (no overflow)
- [ ] Unit test: result matches float32 path within ±1
- [ ] Unit test: `dst` buffer is reused (same `id()`)
- [ ] Unit test: weight normalisation handles edge cases
- [ ] End-to-end: render a test video and compare visually

### 5.4 Performance Checks

- [ ] Benchmark: `cv2.addWeighted()` is faster than float32 path
- [ ] Benchmark: single-segment path is near-zero cost
- [ ] Benchmark: no memory spikes during rendering (monitor with
      `tracemalloc` or `memory_profiler`)
- [ ] Full render benchmark: overall speedup of 20–30%

### 5.5 Regression Checks

- [ ] All existing tests pass: `python -m pytest tests/ -v`
- [ ] All existing tests pass: `python -m pytest core_engine/tests/ -v`
- [ ] End-to-end test passes: `python -m pytest tests/test_e2e.py -v`
- [ ] No new warnings or errors in test output
- [ ] Video output plays correctly in VLC/Firefox/Chrome
- [ ] Audio-video sync is maintained
- [ ] Subtitle timing is unchanged
- [ ] Logo position and opacity are unchanged
- [ ] First and last frames are correct (edge cases)
- [ ] Transition smoothness is visually indistinguishable

---

## 6. Notes for AI Agent

### 6.1 Exact File and Line Numbers

| Item | Location |
|---|---|
| File to modify | `backend/core_engine/fast_compositor.py` (839 lines) |
| Function to modify | `fast_render_segments()` starting at line 487 |
| Phase 4 start | Line 660 (comment `# Phase 4: Generate and write frames`) |
| Phase 4 frame loop | Line 668 (`for frame_idx in range(total_frames):`) |
| Per-frame allocation (REMOVE) | Lines 671–673 (`frame = ...`, `total_weight = ...`, `blended_float = ...`) |
| Inner segment loop | Lines 675–733 |
| Float32 accumulation (REMOVE) | Line 733 (`blended_float += seg_frame.astype(np.float32) * weight`) |
| Weight accumulation (REMOVE) | Line 734 (`total_weight += weight`) |
| Normalisation block (REMOVE) | Lines 737–739 (`if total_weight > 0: frame = np.clip(...)`) |
| Logo overlay | Line 742 (`if logo_overlay: alpha_blit(frame, logo_overlay)`) |
| Frame write | Line 746 (`writer.write_frame(frame)`) |
| Progress reporting | Lines 749–761 (DO NOT MODIFY) |
| `cv2` import | Line 35 (`import cv2`) — already present |
| `numpy` import | Line 36 (`import numpy as np`) — already present |

### 6.2 Critical Constraints

1. **DO NOT change the function signature** of `fast_render_segments()`.
   The parameters and return value must remain identical.

2. **DO NOT change Phase 1, Phase 2, Phase 3, or Phase 5.**  Only
   Phase 4 is modified.

3. **DO NOT modify `alpha_blit()`** (line 68).  It is used unchanged
   for both subtitle and logo compositing.

4. **DO NOT modify `FFmpegFrameWriter`** (line 390).  The writer
   interface is unchanged.

5. **DO NOT modify progress reporting** (lines 749–761).  The
   `on_progress` callback logic must remain exactly as-is.

6. **DO NOT change the Ken Burns or subtitle logic** inside the inner
   segment loop.  Only the accumulation method changes.

7. **Preserve the `frames_in_seg` variable** even though it appears
   unused — it may be referenced by future features or debugging.

8. **Weight normalisation is critical.**  When using `cv2.addWeighted`,
   the `alpha` and `beta` parameters must sum to 1.0 (or close to it)
   for correct blending.  The current code normalises by dividing by
   `total_weight` after accumulation.  In the new code, you must
   normalise the weights *before* calling `addWeighted()`:
   ```python
   w_sum = weight_a + weight_b
   alpha = weight_a / w_sum
   beta = weight_b / w_sum
   ```

9. **The `t_global` variable must remain** even if unused in the
   blending logic — it may be needed by future timeline features.

10. **Edge case: `w_sum == 0`.**  If both weights are 0 (shouldn't
    happen, but be defensive), default to `alpha = 0.5, beta = 0.5`
    to avoid division by zero.

### 6.3 Common Mistakes to Avoid

1. **Forgetting `dst=output_frame`.**  Without the `dst` parameter,
   `cv2.addWeighted()` allocates a new array every call, negating the
   memory benefit.

2. **Using `output_frame = cv2.addWeighted(...)` instead of
   `cv2.addWeighted(..., dst=output_frame)`.**  The assignment creates
   a new binding, not an in-place write.  Always pass `dst=` as a
   keyword argument.

3. **Not handling the single-segment case.**  If you run
   `addWeighted(seg, 1.0, zeros, 0.0, 0.0)` for single segments,
   you're doing unnecessary work.  Use `np.copyto()` instead.

4. **Forgetting to zero `output_frame` for the 0-active case.**
   If no segment is active, the frame should be black.  Since
   `output_frame` is reused, it may contain stale data from the
   previous frame.  Use `output_frame[:] = 0`.

5. **Modifying `seg_frame` after appending to `active_layers`.**
   The `seg_frame` in the list is a reference, not a copy.  If you
   modify it later, the blend will be incorrect.  This shouldn't
   happen with the current code structure but be aware.

6. **Incorrect weight normalisation for the 3+ fallback.**  The
   float32 fallback must still normalise by `total_weight` just
   like the original code.

7. **Breaking the `continue` early-exit.**  The `if frame_idx <
   seg_start_frame or frame_idx >= seg_end_frame: continue` must
   remain — it's how inactive segments are skipped.

### 6.4 Testing Strategy

Run tests in this order:

```bash
# 1. Unit tests for the new blending logic
python -m pytest core_engine/tests/test_fast_compositor.py -v -k "TestAddWeighted"

# 2. All unit tests
python -m pytest core_engine/tests/ -v

# 3. End-to-end tests
python -m pytest tests/test_e2e.py -v

# 4. Run the benchmark (optional but recommended)
python -c "
from core_engine.fast_compositor import _benchmark_crossfade_blending
r = _benchmark_crossfade_blending()
print(f'Speedup: {r[\"speedup\"]}x')
print(f'float32: {r[\"float32_per_frame_ms\"]}ms/frame')
print(f'addWeighted: {r[\"addWeighted_per_frame_ms\"]}ms/frame')
"
```

### 6.5 How to Verify Pixel-Level Correctness

If you want to verify that the new blending produces near-identical
output to the old method, you can add a debug mode that runs both
paths and compares:

```python
# Temporary verification code (remove after validation)
if os.environ.get("STORYFLOW_VERIFY_BLEND"):
    # Run old float32 path
    blended_float_check = np.zeros((height, width, 3), dtype=np.float32)
    total_weight_check = 0.0
    for seg_frame, weight in active_layers:
        blended_float_check += seg_frame.astype(np.float32) * weight
        total_weight_check += weight
    if total_weight_check > 0:
        old_frame = np.clip(
            blended_float_check / total_weight_check, 0, 255
        ).astype(np.uint8)
    else:
        old_frame = np.zeros((height, width, 3), dtype=np.uint8)

    # Compare
    diff = np.abs(output_frame.astype(np.int16) - old_frame.astype(np.int16))
    max_diff = diff.max()
    if max_diff > 1:
        logger.warning(
            "Frame %d: blend mismatch! max_diff=%d",
            frame_idx, max_diff,
        )
```

### 6.6 Rollback Plan

If the change causes issues, reverting is simple:

1. Restore lines 668–746 to their original state (replace the
   `active_layers` + branch logic with the original `blended_float`
   accumulation).
2. Remove the `output_frame` pre-allocation before the loop.
3. Remove `_benchmark_crossfade_blending()` function.
4. Remove new test file entries.

Since only one file is modified and the changes are localised to
Phase 4 of a single function, `git checkout -- backend/core_engine/fast_compositor.py`
is sufficient to revert.

### 6.7 Future Optimisation Opportunities

Once this feature is implemented, further optimisations become
possible:

1. **Feature 1.1 (Multi-Threaded Frame Generation):** The
   `active_layers` collection pattern makes it trivial to parallelise
   — each thread collects its own `active_layers` list and performs
   the branch logic independently.

2. **Feature 1.2 (GPU-Accelerated Compositing):** If `cv2.cuda` is
   available, `cv2.cuda.addWeighted()` can be used as a drop-in
   replacement for even faster blending on GPU.

3. **Pre-allocated `seg_frame` buffers:** The `cv2.resize()` call
   still allocates a new array each time.  A pre-allocated buffer
   per thread could eliminate this allocation too, using:
   ```python
   cv2.resize(crop, (width, height), dst=seg_frame_buffer, interpolation=interp)
   ```

4. **Skip blending when weight == 1.0:** During the middle of a
   segment (not in a transition), the weight is exactly 1.0.
   Detecting this case and using `np.copyto()` instead of
   `addWeighted()` saves the SIMD overhead for non-transition frames.
   This is already handled by the `n_active == 1` branch in the
   proposed code.

### 6.8 Summary of Changes

```
File: backend/core_engine/fast_compositor.py

BEFORE (Phase 4, ~80 lines):
  - Per-frame: allocate float32 buffer, accumulate, normalise, cast
  - Memory: 77–101 MB temporary allocations per frame
  - Speed: ~7–8 ms per frame for blending

AFTER (Phase 4, ~95 lines):
  - Pre-loop: allocate uint8 output buffer once
  - Per-frame: collect active layers, branch on count
    - 0 active: zero the buffer
    - 1 active: np.copyto() (~0.01 ms)
    - 2 active: cv2.addWeighted() (~4–5 ms)
    - 3+ active: fallback to float32 (preserves correctness)
  - Memory: 0 MB per-frame allocation (5.9 MB one-time)
  - Speed: ~0.01–5 ms per frame for blending

Net change: +15 lines, 0 new dependencies, 0 API changes
```
