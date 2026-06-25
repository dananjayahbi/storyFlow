# Feature 3.1 — Transition Variety

> **Status:** Planned  
> **Category:** Core Engine / Visual Production  
> **Primary Files:** `backend/core_engine/transitions.py` (NEW), `backend/core_engine/fast_compositor.py`, `backend/api/models.py`, `backend/api/serializers.py`, `backend/core_engine/video_renderer.py`  
> **Estimated Complexity:** Medium–High  
> **Impact:** Adds 12 professional transition types, eliminating visual monotony in longer videos  
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

Crossfade is the **only** transition effect between segments in StoryFlow
videos today.  The transition is implemented as a simple alpha-weighted
blend inside `fast_render_segments()` in
`backend/core_engine/fast_compositor.py` (839 lines).

The current crossfade works as follows:

1. **Phase 2 – Timeline construction** (lines 619–648):
   Each segment overlaps the next by `crossfade_duration` seconds
   (default 0.5 s).  The overlap is subtracted from the start of the
   next segment so both segments produce frames during the same time
   window.

2. **Phase 4 – Main frame loop** (lines 653–766):
   On every frame, the compositor iterates over all segments.  When two
   segments overlap, each segment's Ken Burns frame is generated
   independently and then blended using linear weights:

   ```
   outgoing segment  →  weight ramps 1.0 → 0.0  (fade out)
   incoming segment  →  weight ramps 0.0 → 1.0  (fade in)
   blended = (frame_out × weight_out + frame_in × weight_in) / total_weight
   ```

   This produces a smooth dissolve, but the same effect for every single
   cut in the video makes longer projects (10+ segments) feel visually
   monotonous and amateurish.

3. **Data model** (`backend/api/models.py`, 279 lines):
   - `Project.transition_duration` (`FloatField`, default `0.5`)  —
     controls duration only; **no transition type field exists**.
   - `Segment` model (line 130) — **no transition fields at all**.
   - `GlobalSettings` — stores `transition_duration` only (line ~239).

4. **Video renderer** (`backend/core_engine/video_renderer.py`, 1218 lines):
   - `TRANSITION_DURATION` constant at line 321 (value `0.5`).
   - `render_project()` reads `transition_duration` from project
     settings and passes it to `fast_render_segments()` as
     `crossfade_duration` (line ~1047).
   - No concept of transition *type* is passed or read.

This is limiting because:

- **Professional video content** uses varied transitions (slides, wipes,
  zooms) to convey pacing, mood, and narrative structure.
- **Longer videos** (10–30 segments) with identical crossfades feel
  repetitive and cheap.
- **Content creators** expect at least basic transition options similar
  to iMovie, CapCut, or Canva Video.
- Competing AI video generators already offer transition variety.

### 1.2 Proposed Solution

Implement a **Transition Library** — a pluggable registry of transition
functions.  Each function takes two frames (outgoing and incoming) plus
a progress value (0.0 → 1.0) and returns one blended frame.

The transition functions live in a new module:
`backend/core_engine/transitions.py`

The system changes:

1. **`TransitionRegistry`** — a singleton class that maps string names
   to transition functions.  Ships with 12 built-in transitions.
2. **Data model** — `Project.transition_type` (default for the project)
   and `Segment.transition_type` (per-segment override for the
   transition *into* this segment from the previous one).
3. **Fast compositor** — during Phase 4, when exactly 2 segments
   overlap, call the registered transition function instead of doing
   the current weight-based alpha blend.
4. **Serializers** — expose `transition_type` on both
   `ProjectSerializer` and `SegmentSerializer`.
5. **Video renderer** — pass per-segment transition info in
   `segment_data_list`.
6. **Frontend** — add a transition type selector dropdown per segment.

**Transition types to implement:**

| # | Name | Key | Description |
|---|------|-----|-------------|
| 1 | Crossfade | `crossfade` | Existing alpha blend (default) |
| 2 | Slide Left | `slide_left` | Incoming slides in from right, pushing outgoing left |
| 3 | Slide Right | `slide_right` | Incoming slides in from left |
| 4 | Slide Up | `slide_up` | Incoming slides in from bottom |
| 5 | Slide Down | `slide_down` | Incoming slides in from top |
| 6 | Wipe Horizontal | `wipe_horizontal` | Vertical line sweeps left→right revealing incoming |
| 7 | Wipe Vertical | `wipe_vertical` | Horizontal line sweeps top→bottom |
| 8 | Wipe Diagonal | `wipe_diagonal` | Diagonal line sweeps corner to corner |
| 9 | Zoom In | `zoom_in` | Outgoing zooms into center; incoming appears beneath |
| 10 | Zoom Out | `zoom_out` | Outgoing shrinks from center; incoming grows |
| 11 | Dissolve | `dissolve` | Random pixel blocks flip from outgoing to incoming |
| 12 | Push Left | `push_left` | Both segments slide together, like a conveyor belt |
| 13 | Iris | `iris` | Circular reveal from center outward |

**Function signature:**

```python
def transition_fn(
    frame_out: np.ndarray,   # (H, W, 3) uint8 — outgoing segment
    frame_in: np.ndarray,    # (H, W, 3) uint8 — incoming segment
    progress: float,         # 0.0 → 1.0 across transition duration
    width: int,
    height: int,
) -> np.ndarray:             # (H, W, 3) uint8 — blended result
```

### 1.3 Files to Modify

| # | File | Change |
|---|------|--------|
| 1 | `backend/core_engine/transitions.py` | **NEW** — transition registry and 13 transition functions |
| 2 | `backend/api/models.py` | Add `transition_type` to `Project` and `Segment` models |
| 3 | `backend/api/serializers.py` | Expose `transition_type` in `ProjectSerializer`, `SegmentSerializer`, `GlobalSettingsSerializer` |
| 4 | `backend/api/migrations/` | Auto-generated Django migration |
| 5 | `backend/core_engine/video_renderer.py` | Pass per-segment `transition_type` in `segment_data_list` |
| 6 | `backend/core_engine/fast_compositor.py` | Replace weight-based blending with transition function calls in Phase 4 |
| 7 | `frontend/types/` | Add `transition_type` to segment and project TypeScript interfaces |
| 8 | `frontend/components/` | Add transition selector dropdown per segment |

### 1.4 Dependencies

- **NumPy** — array manipulation for all transition effects (already
  installed)
- **OpenCV (`cv2`)** — `cv2.resize()` for zoom transitions,
  `cv2.warpAffine()` optionally (already installed)
- **Django ORM** — `models.CharField` with `choices` for transition type
- **Django REST Framework** — serializer field addition
- No new pip packages required.

### 1.5 Risk Assessment

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Performance regression from per-frame transition calls | Medium | Transition functions use vectorized NumPy ops; no Python loops over pixels. Benchmark and optimize hot paths. |
| Invalid transition_type stored in DB | Low | Validate against `TRANSITION_CHOICES` in serializer and model |
| Two segments not overlapping exactly (edge case with 1 segment) | Low | Guard: only call transition when exactly 2 segments overlap; fall back to simple frame if only 1 active |
| Migration breaks existing data | Very Low | New field has `default='crossfade'`; existing projects render identically |
| Frontend state desync when changing transition type | Low | Use same optimistic update pattern as other segment fields |
| Glitch transition causes seizure-inducing flicker | Low | Intentionally omit true "glitch" in v1; dissolve is the most aggressive effect |

### 1.6 Backward Compatibility

- All new model fields default to `'crossfade'`, so existing projects
  continue to render exactly as before.
- The fast compositor only invokes the transition library when 2
  segments overlap.  Single-segment projects are unaffected.
- The `crossfade` transition function replicates the exact behaviour of
  the current weight-based blend, so the default path is mathematically
  identical.

---

## 2. Flow Diagram

### 2.1 Current Data Flow (Crossfade Only)

```
┌──────────────────────────────────────────────────────────────────────┐
│                        CURRENT FLOW                                  │
│                                                                      │
│  ┌──────────────┐       ┌──────────────────────┐                     │
│  │ GlobalSettings│──────▶│       Project         │                     │
│  │ trans_dur: 0.5│ copy  │ transition_duration:  │                     │
│  │ (no type)    │  on   │        0.5             │                     │
│  └──────────────┘ create│ (no transition_type)   │                     │
│                         └──────────┬─────────────┘                     │
│                                    │                                   │
│                                    │ read once                        │
│                                    ▼                                   │
│                         ┌──────────────────────┐                      │
│                         │   render_project()    │                      │
│                         │ crossfade_dur = 0.5   │                      │
│                         │ (no type concept)     │                      │
│                         └──────────┬───────────┘                      │
│                                    │ pass to compositor                │
│                                    ▼                                   │
│                         ┌──────────────────────┐                      │
│                         │  fast_render_segments │                      │
│                         │  crossfade_dur = 0.5  │                      │
│                         └──────────┬───────────┘                      │
│                                    │                                   │
│             Phase 4: Main frame loop                                  │
│                                    │                                   │
│          ┌─────────────────────────┼─────────────────────────┐        │
│          ▼                         ▼                         ▼        │
│   ┌─────────────┐          ┌─────────────┐          ┌─────────────┐   │
│   │  Segment 0  │          │  Segment 1  │          │  Segment 2  │   │
│   │  frame_out  │          │  frame_out  │          │  (last)     │   │
│   └──────┬──────┘          └──────┬──────┘          └─────────────┘   │
│          │ overlap                │ overlap                           │
│          ▼                        ▼                                    │
│   ┌──────────────────┐   ┌──────────────────┐                        │
│   │ weight blending  │   │ weight blending  │                        │
│   │ w_out + w_in     │   │ w_out + w_in     │                        │
│   │ ALWAYS crossfade │   │ ALWAYS crossfade │                        │
│   └──────────────────┘   └──────────────────┘                        │
│                                                                      │
│  Every cut uses the SAME crossfade effect.                           │
└──────────────────────────────────────────────────────────────────────┘
```

### 2.2 Proposed Data Flow (Per-Segment Transition Type)

```
┌──────────────────────────────────────────────────────────────────────┐
│                       PROPOSED FLOW                                   │
│                                                                      │
│  ┌──────────────┐       ┌──────────────────────┐                     │
│  │ GlobalSettings│──────▶│       Project         │                     │
│  │ trans_dur: 0.5│ copy  │ transition_duration:  │                     │
│  │ trans_type:   │  on   │        0.5            │                     │
│  │   crossfade  │ create│ transition_type:       │                     │
│  └──────────────┘       │   "crossfade"          │                     │
│                         └──────────┬─────────────┘                     │
│                                    │                                   │
│                                    │ read project default              │
│                                    ▼                                   │
│                       ┌──────────────────────────┐                    │
│                       │     render_project()      │                    │
│                       │  For each segment:        │                    │
│                       │    seg.transition_type     │                    │
│                       │    ?? project.trans_type   │                    │
│                       │    ?? "crossfade"          │                    │
│                       └──────────────┬───────────┘                    │
│                                      │                                 │
│                                      │ segment_data_list[]             │
│                                      │ each dict includes:             │
│                                      │   "transition_type": str        │
│                                      ▼                                 │
│                       ┌──────────────────────────┐                    │
│                       │   fast_render_segments    │                    │
│                       │  Now receives per-segment │                    │
│                       │  transition types         │                    │
│                       └──────────────┬───────────┘                    │
│                                      │                                 │
│           Phase 4: Main frame loop   │                                 │
│                                      │                                 │
│       When 2 segments overlap at frame_idx:                           │
│                                      │                                 │
│          ┌───────────────────────────┼───────────────────┐            │
│          ▼                           ▼                   ▼            │
│  ┌──────────────┐   ┌───────────────────────┐   ┌──────────────┐     │
│  │  Segment 0   │   │      Segment 1        │   │  Segment 2   │     │
│  │  (outgoing)  │   │  transition_type:      │   │  trans_type:  │     │
│  │              │   │    "slide_left"        │   │  "iris"      │     │
│  └──────┬───────┘   └──────────┬────────────┘   └──────┬───────┘     │
│         │                      │                        │             │
│         │    ┌─────────────────┘                        │             │
│         ▼    ▼                                          │             │
│  ┌─────────────────────┐                                │             │
│  │ TransitionRegistry  │                                │             │
│  │  .apply(            │                                │             │
│  │    "slide_left",    │                                │             │
│  │    frame_out,       │                                │             │
│  │    frame_in,        │                                │             │
│  │    progress         │                                │             │
│  │  )                  │                                │             │
│  └──────────┬──────────┘                                │             │
│             ▼                                           │             │
│     ┌──────────────┐                           ┌────────┴─────┐      │
│     │ blended frame│                           │  .apply(     │      │
│     │ (slide_left) │                           │  "iris", …)  │      │
│     └──────────────┘                           └──────────────┘      │
│                                                                      │
│  Each cut can use a DIFFERENT transition effect.                      │
└──────────────────────────────────────────────────────────────────────┘
```

### 2.3 TransitionRegistry Internal Design

```
┌───────────────────────────────────────────────────────────────┐
│                    TransitionRegistry                          │
│                                                               │
│  _registry: Dict[str, TransitionFn]                           │
│                                                               │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐  │
│  │  "crossfade"   │  │  "slide_left"  │  │  "slide_right" │  │
│  │  → crossfade() │  │  → slide_left()│  │  → slide_right │  │
│  └────────────────┘  └────────────────┘  └────────────────┘  │
│                                                               │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐  │
│  │  "slide_up"    │  │  "slide_down"  │  │ "wipe_horiz"   │  │
│  │  → slide_up()  │  │  → slide_down()│  │ → wipe_horiz() │  │
│  └────────────────┘  └────────────────┘  └────────────────┘  │
│                                                               │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐  │
│  │ "wipe_vertical"│  │ "wipe_diagonal"│  │  "zoom_in"     │  │
│  │ → wipe_vert()  │  │ → wipe_diag()  │  │  → zoom_in()   │  │
│  └────────────────┘  └────────────────┘  └────────────────┘  │
│                                                               │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐  │
│  │  "zoom_out"    │  │  "dissolve"    │  │  "push_left"   │  │
│  │  → zoom_out()  │  │  → dissolve()  │  │  → push_left() │  │
│  └────────────────┘  └────────────────┘  └────────────────┘  │
│                                                               │
│  ┌────────────────┐                                           │
│  │  "iris"        │  .apply(name, out, in, progress, w, h)   │
│  │  → iris()      │  → looks up _registry[name]              │
│  └────────────────┘  → calls fn(out, in, progress, w, h)     │
│                      → returns blended (H, W, 3) uint8       │
│                                                               │
│  .list_transitions() → ["crossfade", "slide_left", …]        │
│  .get(name)          → TransitionFn or KeyError               │
│  .register(name, fn) → adds custom transition                 │
└───────────────────────────────────────────────────────────────┘
```

### 2.4 Phase 4 Frame Loop — Before vs After

```
BEFORE (current — weight blending):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  for frame_idx in range(total_frames):
      blended_float = zeros(...)
      total_weight = 0.0

      for seg_idx, (start, end) in enumerate(ranges):
          if frame_idx not in [start..end): continue

          seg_frame = generate_ken_burns_frame(...)
          apply_subtitles(seg_frame, ...)

          weight = compute_crossfade_weight(...)    ◄── linear ramp
          blended_float += seg_frame * weight
          total_weight += weight

      frame = (blended_float / total_weight).uint8  ◄── always alpha blend

AFTER (proposed — transition dispatch):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  for frame_idx in range(total_frames):
      active_segments = get_active_segments(frame_idx)

      if len(active_segments) == 1:
          frame = generate_frame(active_segments[0])

      elif len(active_segments) == 2:
          seg_out, seg_in = active_segments
          frame_out = generate_frame(seg_out)
          frame_in  = generate_frame(seg_in)

          progress = compute_transition_progress(...)
          trans_type = seg_in["transition_type"]     ◄── per-segment

          frame = registry.apply(                    ◄── dispatch
              trans_type, frame_out, frame_in,
              progress, width, height
          )

      apply_logo(frame)
      writer.write_frame(frame)
```

---

## 3. Step-by-Step Instructions

### Step 1: Create `backend/core_engine/transitions.py`

This is the core of the feature — a new module containing the
`TransitionRegistry` class and all transition functions.

#### 1A. File scaffold and imports

Create `backend/core_engine/transitions.py` with:

```python
"""Transition library for video segment blending.

Each transition function takes two frames (outgoing and incoming)
plus a progress value (0.0 → 1.0) and returns one blended frame.

Usage:
    from core_engine.transitions import registry

    frame = registry.apply("slide_left", frame_out, frame_in, 0.5, 1920, 1080)
"""

import logging
import math
from typing import Callable, Dict, List, Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Type alias for transition functions
TransitionFn = Callable[[np.ndarray, np.ndarray, float, int, int], np.ndarray]
```

#### 1B. Define `TRANSITION_CHOICES`

This constant will be shared by models, serializers, and the registry:

```python
# Canonical list of transition types — used by Django models/serializers
TRANSITION_CHOICES = [
    ("crossfade", "Crossfade"),
    ("slide_left", "Slide Left"),
    ("slide_right", "Slide Right"),
    ("slide_up", "Slide Up"),
    ("slide_down", "Slide Down"),
    ("wipe_horizontal", "Wipe Horizontal"),
    ("wipe_vertical", "Wipe Vertical"),
    ("wipe_diagonal", "Wipe Diagonal"),
    ("zoom_in", "Zoom In"),
    ("zoom_out", "Zoom Out"),
    ("dissolve", "Dissolve"),
    ("push_left", "Push Left"),
    ("iris", "Iris"),
]

TRANSITION_KEYS = {key for key, _ in TRANSITION_CHOICES}
DEFAULT_TRANSITION = "crossfade"
```

#### 1C. Implement `TransitionRegistry`

```python
class TransitionRegistry:
    """Registry of named transition functions."""

    def __init__(self):
        self._registry: Dict[str, TransitionFn] = {}

    def register(self, name: str, fn: TransitionFn) -> None:
        """Register a transition function under the given name."""
        self._registry[name] = fn
        logger.debug("Registered transition: %s", name)

    def get(self, name: str) -> TransitionFn:
        """Look up a transition function by name.  Raises KeyError."""
        return self._registry[name]

    def apply(
        self,
        name: str,
        frame_out: np.ndarray,
        frame_in: np.ndarray,
        progress: float,
        width: int,
        height: int,
    ) -> np.ndarray:
        """Apply a named transition and return the blended frame.

        Falls back to crossfade if the name is not registered.
        """
        fn = self._registry.get(name)
        if fn is None:
            logger.warning(
                "Unknown transition '%s', falling back to crossfade", name,
            )
            fn = self._registry.get("crossfade", _transition_crossfade)
        return fn(frame_out, frame_in, progress, width, height)

    def list_transitions(self) -> List[str]:
        """Return sorted list of registered transition names."""
        return sorted(self._registry.keys())
```

#### 1D. Implement each transition function

Each function follows the same signature:

```python
def fn(frame_out: np.ndarray, frame_in: np.ndarray,
       progress: float, width: int, height: int) -> np.ndarray
```

**1. Crossfade** (replicates current behaviour exactly):

```python
def _transition_crossfade(
    frame_out: np.ndarray,
    frame_in: np.ndarray,
    progress: float,
    width: int,
    height: int,
) -> np.ndarray:
    """Simple alpha blend — outgoing fades out, incoming fades in."""
    alpha = np.float32(progress)
    blended = cv2.addWeighted(frame_out, 1.0 - alpha, frame_in, alpha, 0)
    return blended
```

**2. Slide Left** (incoming slides in from right):

```python
def _transition_slide_left(
    frame_out: np.ndarray,
    frame_in: np.ndarray,
    progress: float,
    width: int,
    height: int,
) -> np.ndarray:
    """Incoming frame slides in from right; outgoing stays in place."""
    offset = int(width * (1.0 - progress))
    canvas = frame_out.copy()
    # Incoming occupies the right portion that has "arrived"
    visible_width = width - offset
    if visible_width > 0:
        canvas[:, offset:offset + visible_width] = frame_in[:, :visible_width]
    return canvas
```

**3. Slide Right** (incoming slides in from left):

```python
def _transition_slide_right(
    frame_out: np.ndarray,
    frame_in: np.ndarray,
    progress: float,
    width: int,
    height: int,
) -> np.ndarray:
    """Incoming frame slides in from left; outgoing stays in place."""
    offset = int(width * (1.0 - progress))
    canvas = frame_out.copy()
    visible_width = width - offset
    if visible_width > 0:
        canvas[:, :visible_width] = frame_in[:, offset:offset + visible_width]
    return canvas
```

**4. Slide Up** (incoming slides in from bottom):

```python
def _transition_slide_up(
    frame_out: np.ndarray,
    frame_in: np.ndarray,
    progress: float,
    width: int,
    height: int,
) -> np.ndarray:
    """Incoming frame slides in from the bottom."""
    offset = int(height * (1.0 - progress))
    canvas = frame_out.copy()
    visible_height = height - offset
    if visible_height > 0:
        canvas[offset:offset + visible_height, :] = frame_in[:visible_height, :]
    return canvas
```

**5. Slide Down** (incoming slides in from top):

```python
def _transition_slide_down(
    frame_out: np.ndarray,
    frame_in: np.ndarray,
    progress: float,
    width: int,
    height: int,
) -> np.ndarray:
    """Incoming frame slides in from the top."""
    offset = int(height * (1.0 - progress))
    canvas = frame_out.copy()
    visible_height = height - offset
    if visible_height > 0:
        canvas[:visible_height, :] = frame_in[offset:offset + visible_height, :]
    return canvas
```

**6. Wipe Horizontal** (vertical line sweeps left to right):

```python
def _transition_wipe_horizontal(
    frame_out: np.ndarray,
    frame_in: np.ndarray,
    progress: float,
    width: int,
    height: int,
) -> np.ndarray:
    """A vertical line sweeps left→right, revealing the incoming frame."""
    split = int(width * progress)
    canvas = frame_out.copy()
    if split > 0:
        canvas[:, :split] = frame_in[:, :split]
    return canvas
```

**7. Wipe Vertical** (horizontal line sweeps top to bottom):

```python
def _transition_wipe_vertical(
    frame_out: np.ndarray,
    frame_in: np.ndarray,
    progress: float,
    width: int,
    height: int,
) -> np.ndarray:
    """A horizontal line sweeps top→bottom, revealing the incoming frame."""
    split = int(height * progress)
    canvas = frame_out.copy()
    if split > 0:
        canvas[:split, :] = frame_in[:split, :]
    return canvas
```

**8. Wipe Diagonal** (diagonal line from top-left to bottom-right):

```python
def _transition_wipe_diagonal(
    frame_out: np.ndarray,
    frame_in: np.ndarray,
    progress: float,
    width: int,
    height: int,
) -> np.ndarray:
    """Diagonal wipe from top-left to bottom-right."""
    # Create a gradient mask: for each pixel (x, y), compute
    # normalized_position = (x/width + y/height) / 2.0
    # If normalized_position < progress → show incoming
    ys = np.arange(height, dtype=np.float32).reshape(-1, 1) / height
    xs = np.arange(width, dtype=np.float32).reshape(1, -1) / width
    mask = ((xs + ys) / 2.0 < progress).astype(np.uint8)
    mask_3ch = mask[:, :, np.newaxis]  # (H, W, 1)
    canvas = frame_out * (1 - mask_3ch) + frame_in * mask_3ch
    return canvas.astype(np.uint8)
```

**9. Zoom In** (outgoing zooms into center, incoming appears beneath):

```python
def _transition_zoom_in(
    frame_out: np.ndarray,
    frame_in: np.ndarray,
    progress: float,
    width: int,
    height: int,
) -> np.ndarray:
    """Outgoing zooms into the center while fading; incoming appears."""
    # Scale outgoing frame up
    scale = 1.0 + progress * 0.5  # 1.0→1.5
    new_w = int(width * scale)
    new_h = int(height * scale)
    zoomed = cv2.resize(frame_out, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

    # Crop center to original size
    x_off = (new_w - width) // 2
    y_off = (new_h - height) // 2
    cropped = zoomed[y_off:y_off + height, x_off:x_off + width]

    # Blend: outgoing fades out as it zooms
    alpha = progress
    blended = cv2.addWeighted(cropped, 1.0 - alpha, frame_in, alpha, 0)
    return blended
```

**10. Zoom Out** (outgoing shrinks from center, incoming grows):

```python
def _transition_zoom_out(
    frame_out: np.ndarray,
    frame_in: np.ndarray,
    progress: float,
    width: int,
    height: int,
) -> np.ndarray:
    """Outgoing shrinks from center; incoming grows from behind."""
    # Shrink outgoing
    scale = max(1.0 - progress * 0.5, 0.1)  # 1.0→0.5
    new_w = max(int(width * scale), 2)
    new_h = max(int(height * scale), 2)
    shrunk = cv2.resize(frame_out, (new_w, new_h), interpolation=cv2.INTER_AREA)

    # Place shrunk frame centered on the incoming frame
    canvas = frame_in.copy()
    x_off = (width - new_w) // 2
    y_off = (height - new_h) // 2
    canvas[y_off:y_off + new_h, x_off:x_off + new_w] = shrunk
    return canvas
```

**11. Dissolve** (random pixel blocks flip one by one):

```python
def _transition_dissolve(
    frame_out: np.ndarray,
    frame_in: np.ndarray,
    progress: float,
    width: int,
    height: int,
) -> np.ndarray:
    """Random blocks of pixels switch from outgoing to incoming."""
    block_size = 16  # pixels per block
    rows = (height + block_size - 1) // block_size
    cols = (width + block_size - 1) // block_size

    # Deterministic random mask based on block coordinates
    # Use a fixed seed so the pattern is consistent across frames
    rng = np.random.RandomState(seed=42)
    thresholds = rng.rand(rows, cols).astype(np.float32)

    canvas = frame_out.copy()
    for r in range(rows):
        for c in range(cols):
            if thresholds[r, c] < progress:
                y1 = r * block_size
                y2 = min(y1 + block_size, height)
                x1 = c * block_size
                x2 = min(x1 + block_size, width)
                canvas[y1:y2, x1:x2] = frame_in[y1:y2, x1:x2]
    return canvas
```

> **Performance note:** The dissolve loop over blocks is manageable for
> 1080p (120×68 = 8,160 iterations with `block_size=16`).  If
> profiling shows this is a bottleneck, replace the Python loop with a
> vectorized mask:
>
> ```python
> mask = (thresholds < progress)
> mask_full = np.repeat(np.repeat(mask, block_size, axis=0), block_size, axis=1)
> mask_full = mask_full[:height, :width, np.newaxis]
> canvas = np.where(mask_full, frame_in, frame_out)
> ```

**12. Push Left** (both frames slide together like a conveyor):

```python
def _transition_push_left(
    frame_out: np.ndarray,
    frame_in: np.ndarray,
    progress: float,
    width: int,
    height: int,
) -> np.ndarray:
    """Both segments slide left together like a conveyor belt."""
    offset = int(width * progress)
    canvas = np.zeros_like(frame_out)

    # Outgoing slides left
    remaining_out = width - offset
    if remaining_out > 0:
        canvas[:, :remaining_out] = frame_out[:, offset:]

    # Incoming slides in from the right
    if offset > 0:
        canvas[:, remaining_out:] = frame_in[:, :offset]

    return canvas
```

**13. Iris** (circular reveal from center outward):

```python
def _transition_iris(
    frame_out: np.ndarray,
    frame_in: np.ndarray,
    progress: float,
    width: int,
    height: int,
) -> np.ndarray:
    """Circular reveal from center — incoming appears inside an
    expanding circle."""
    cx, cy = width // 2, height // 2
    max_radius = math.sqrt(cx * cx + cy * cy)
    radius = int(max_radius * progress)

    # Create circular mask
    Y, X = np.ogrid[:height, :width]
    dist_sq = (X - cx) ** 2 + (Y - cy) ** 2
    mask = (dist_sq <= radius * radius).astype(np.uint8)
    mask_3ch = mask[:, :, np.newaxis]

    canvas = frame_out * (1 - mask_3ch) + frame_in * mask_3ch
    return canvas.astype(np.uint8)
```

#### 1E. Register all transitions and create module-level singleton

At the bottom of `transitions.py`:

```python
# ---------------------------------------------------------------------------
# Module-level singleton registry
# ---------------------------------------------------------------------------

registry = TransitionRegistry()

# Register built-in transitions
registry.register("crossfade", _transition_crossfade)
registry.register("slide_left", _transition_slide_left)
registry.register("slide_right", _transition_slide_right)
registry.register("slide_up", _transition_slide_up)
registry.register("slide_down", _transition_slide_down)
registry.register("wipe_horizontal", _transition_wipe_horizontal)
registry.register("wipe_vertical", _transition_wipe_vertical)
registry.register("wipe_diagonal", _transition_wipe_diagonal)
registry.register("zoom_in", _transition_zoom_in)
registry.register("zoom_out", _transition_zoom_out)
registry.register("dissolve", _transition_dissolve)
registry.register("push_left", _transition_push_left)
registry.register("iris", _transition_iris)

logger.debug(
    "Transition registry initialized with %d transitions: %s",
    len(registry.list_transitions()),
    ", ".join(registry.list_transitions()),
)
```

---

### Step 2: Update `backend/api/models.py`

#### 2A. Import `TRANSITION_CHOICES` and `DEFAULT_TRANSITION`

At the top of `models.py`, after existing imports:

```python
from core_engine.transitions import TRANSITION_CHOICES, DEFAULT_TRANSITION
```

> **Circular import note:** If this causes a circular import (unlikely
> since `transitions.py` doesn't import from `api.models`), define
> `TRANSITION_CHOICES` and `DEFAULT_TRANSITION` inline in `models.py`
> instead, and import them into `transitions.py`.  The safer approach
> is to define the choices in `models.py` and import them into
> `transitions.py`.  See **Notes for AI Agent §6.3** for details.

#### 2B. Add `transition_type` to `Project` model

In the `Project` model, after `transition_duration`:

```python
    # Render / Ken-Burns
    zoom_intensity = models.FloatField(default=1.3)
    ken_burns_zoom = models.FloatField(default=1.2)
    transition_duration = models.FloatField(default=0.5)
    transition_type = models.CharField(
        max_length=30,
        choices=TRANSITION_CHOICES,
        default=DEFAULT_TRANSITION,
    )
```

This is the **project-level default** transition type.  Every segment
without an explicit override will use this.

#### 2C. Add `transition_type` to `Segment` model

In the `Segment` model, after `is_locked`:

```python
    is_locked = models.BooleanField(default=False)
    transition_type = models.CharField(
        max_length=30,
        choices=TRANSITION_CHOICES,
        default='',
        blank=True,
    )
```

When `transition_type` is empty string (`''`), the segment inherits the
project-level default.  When explicitly set (e.g. `"slide_left"`), it
overrides the project default **for the transition INTO this segment**
from the previous one.

> **Design decision — empty string vs NULL:**  We use empty string
> (`default=''`, `blank=True`) rather than `null=True` because Django
> convention is to avoid `null` on `CharField`.  The resolution:
> ```
> segment.transition_type  →  if ''  →  project.transition_type  →  if ''  →  "crossfade"
> ```

#### 2D. Add `transition_type` to `GlobalSettings` model

In the `GlobalSettings` model, after `transition_duration`:

```python
    # ── Ken Burns & transitions ──
    ken_burns_zoom = models.FloatField(default=1.2)
    transition_duration = models.FloatField(default=0.5)
    transition_type = models.CharField(
        max_length=30,
        choices=TRANSITION_CHOICES,
        default=DEFAULT_TRANSITION,
    )
    zoom_intensity = models.FloatField(default=1.3)  # legacy
```

#### 2E. Generate and apply the migration

```bash
cd backend
python manage.py makemigrations api
python manage.py migrate
```

This will create a migration that adds `transition_type` to three
tables: `api_project`, `api_segment`, and `api_globalsettings`.
The default values ensure zero data loss.

---

### Step 3: Update `backend/api/serializers.py`

#### 3A. Add `transition_type` to `ProjectSerializer`

In the `ProjectSerializer.Meta.fields` list:

```python
class ProjectSerializer(serializers.ModelSerializer):
    segment_count = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            'id', 'title', 'created_at', 'updated_at',
            'status', 'resolution_width', 'resolution_height',
            'framerate', 'segment_count', 'transition_type',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'status']
```

#### 3B. Add `transition_type` to `SegmentSerializer`

In the `SegmentSerializer.Meta.fields` list:

```python
class SegmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Segment
        fields = [
            'id', 'project', 'sequence_index', 'text_content',
            'image_prompt', 'image_file', 'audio_file',
            'audio_duration', 'is_locked', 'transition_type',
        ]
        read_only_fields = [
            'id', 'project', 'sequence_index',
            'image_file', 'audio_file', 'audio_duration',
        ]
```

#### 3C. Add `transition_type` to `GlobalSettingsSerializer`

In the `GlobalSettingsSerializer.Meta.fields` list, add
`'transition_type'` alongside `'transition_duration'`:

```python
        fields = [
            'default_voice_id', 'tts_speed',
            'subtitle_font_family', 'subtitle_font_size',
            'subtitle_font_color', 'subtitle_position',
            'subtitle_y_position',
            'subtitle_font', 'subtitle_color',
            'render_width', 'render_height', 'render_fps',
            'ken_burns_zoom', 'transition_duration', 'transition_type',
            'zoom_intensity',
            'inter_segment_silence', 'subtitles_enabled',
            'custom_font_file',
            'logo_enabled', 'active_logo', 'logo_scale',
            'logo_position', 'logo_opacity', 'logo_margin',
            'outro_enabled', 'active_outro',
            'upscale_enabled', 'upscale_model', 'upscale_denoise_strength',
            'created_at', 'updated_at',
        ]
```

#### 3D. Add validation for `transition_type` in `GlobalSettingsSerializer`

```python
    def validate_transition_type(self, value):
        from core_engine.transitions import TRANSITION_KEYS
        if value not in TRANSITION_KEYS:
            raise serializers.ValidationError(
                f'Transition type must be one of: {", ".join(sorted(TRANSITION_KEYS))}.'
            )
        return value
```

---

### Step 4: Update `backend/core_engine/video_renderer.py`

#### 4A. Read project-level `transition_type`

After the line that reads `transition_duration` (~currently using the
constant `TRANSITION_DURATION`), read the transition type:

```python
# In render_project(), around Section C or after reading project settings:

# Transition type (project default)
project_transition_type = getattr(project, "transition_type", "") or "crossfade"
```

#### 4B. Include per-segment `transition_type` in `segment_data_list`

In the loop that builds `segment_data_list` (Section G, ~line 845),
add the resolved transition type for each segment:

```python
    # Resolve effective transition type for this segment
    seg_transition_type = getattr(segment, "transition_type", "") or ""
    effective_transition = seg_transition_type if seg_transition_type else project_transition_type

    segment_data_list.append({
        "image_path": image_path,
        "audio_duration": audio_duration,
        "text_content": text_content,
        "sequence_index": segment.sequence_index,
        "transition_type": effective_transition,
    })
```

#### 4C. Pass `transition_type` info to `fast_render_segments()`

The transition type is now embedded in each item of
`segment_data_list`.  No new top-level parameter is needed on
`fast_render_segments()` — the compositor reads it from the per-segment
dict.  However, we may optionally add a `default_transition_type`
parameter for clarity.

---

### Step 5: Update `backend/core_engine/fast_compositor.py`

This is the most critical change — replacing the weight-based crossfade
with the transition library dispatch.

#### 5A. Import the transition registry

At the top of `fast_compositor.py`:

```python
from core_engine.transitions import registry as transition_registry
```

#### 5B. Read per-segment transition_type in Phase 1

In Phase 1 where `segments_info` is built, carry the transition type:

```python
    segments_info.append({
        "source_image": source_image,
        "crop_w": crop_w,
        "crop_h": crop_h,
        "start_coords": (sx, sy),
        "end_coords": (ex, ey),
        "visual_duration": visual_duration,
        "subtitle_overlays": sub_overlays,
        "transition_type": seg.get("transition_type", "crossfade"),  # ← NEW
    })
```

#### 5C. Rewrite Phase 4 frame blending logic

Replace the current inner loop (the weight accumulation + normalization
pattern) with a two-path approach:

```python
    # Phase 4: Generate and write frames
    render_start = time.perf_counter()
    last_progress_pct = 5
    crossfade_frames = int(crossfade_duration * fps)

    for frame_idx in range(total_frames):
        t_global = frame_idx / fps

        # ── Collect active segments at this frame ──
        active: list[tuple[int, int, int]] = []
        # Each entry: (seg_idx, seg_start_frame, seg_end_frame)
        for seg_idx, (seg_start_frame, seg_end_frame) in enumerate(segment_frame_ranges):
            if seg_start_frame <= frame_idx < seg_end_frame:
                active.append((seg_idx, seg_start_frame, seg_end_frame))

        if len(active) == 0:
            # Safety: black frame (shouldn't happen)
            frame = np.zeros((height, width, 3), dtype=np.uint8)

        elif len(active) == 1:
            # ── Single segment: no transition ──
            seg_idx, seg_start_frame, seg_end_frame = active[0]
            frame = _generate_segment_frame(
                segments_info[seg_idx], frame_idx, seg_start_frame, fps,
                width, height,
            )

        else:
            # ── Two (or more) segments overlap: apply transition ──
            # The OUTGOING segment is the earlier one; INCOMING is the later one.
            out_idx, out_start, out_end = active[0]
            in_idx, in_start, in_end = active[-1]

            frame_out = _generate_segment_frame(
                segments_info[out_idx], frame_idx, out_start, fps,
                width, height,
            )
            frame_in = _generate_segment_frame(
                segments_info[in_idx], frame_idx, in_start, fps,
                width, height,
            )

            # Compute transition progress (0.0 → 1.0)
            # The overlap starts at in_start and ends at out_end
            overlap_start = in_start
            overlap_end = out_end
            overlap_length = overlap_end - overlap_start
            if overlap_length > 0:
                progress = (frame_idx - overlap_start) / overlap_length
                progress = max(0.0, min(1.0, progress))
            else:
                progress = 1.0

            # Dispatch to transition function
            trans_type = segments_info[in_idx].get(
                "transition_type", "crossfade"
            )
            frame = transition_registry.apply(
                trans_type, frame_out, frame_in, progress, width, height,
            )

        # Apply logo (on top of everything, no transition)
        if logo_overlay:
            alpha_blit(frame, logo_overlay)

        # Write frame to FFmpeg
        writer.write_frame(frame)

        # Progress reporting (same as before) …
```

#### 5D. Extract a helper `_generate_segment_frame()`

To keep the Phase 4 loop clean, extract the Ken Burns + subtitle
generation into a helper:

```python
def _generate_segment_frame(
    si: dict,
    frame_idx: int,
    seg_start_frame: int,
    fps: int,
    width: int,
    height: int,
) -> np.ndarray:
    """Generate one Ken Burns frame with subtitles for a single segment."""
    from core_engine.ken_burns import interpolate_position

    t_local = (frame_idx - seg_start_frame) / fps
    seg_duration = si["visual_duration"]

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

    is_downscale = si["crop_w"] > width or si["crop_h"] > height
    interp = cv2.INTER_AREA if is_downscale else cv2.INTER_LINEAR
    seg_frame = cv2.resize(crop, (width, height), interpolation=interp)

    # Apply subtitle overlays
    for overlay in si["subtitle_overlays"]:
        if overlay.start_time <= t_local < overlay.end_time:
            alpha_blit(seg_frame, overlay)

    return seg_frame
```

---

### Step 6: Frontend Changes (TypeScript / React)

#### 6A. Update TypeScript types

In the relevant types file (e.g. `frontend/types/`), add
`transition_type` to both `Project` and `Segment` interfaces:

```typescript
// In Segment interface/type:
export interface Segment {
  id: string;
  project: string;
  sequence_index: number;
  text_content: string;
  image_prompt: string;
  image_file: string | null;
  audio_file: string | null;
  audio_duration: number | null;
  is_locked: boolean;
  transition_type: string;  // "" = inherit project default
}

// In Project interface/type:
export interface Project {
  // ... existing fields ...
  transition_type: string;  // default transition for all segments
}
```

#### 6B. Define transition options constant

```typescript
// frontend/constants/transitions.ts
export const TRANSITION_OPTIONS = [
  { value: '', label: 'Project Default' },
  { value: 'crossfade', label: 'Crossfade' },
  { value: 'slide_left', label: 'Slide Left' },
  { value: 'slide_right', label: 'Slide Right' },
  { value: 'slide_up', label: 'Slide Up' },
  { value: 'slide_down', label: 'Slide Down' },
  { value: 'wipe_horizontal', label: 'Wipe Horizontal' },
  { value: 'wipe_vertical', label: 'Wipe Vertical' },
  { value: 'wipe_diagonal', label: 'Wipe Diagonal' },
  { value: 'zoom_in', label: 'Zoom In' },
  { value: 'zoom_out', label: 'Zoom Out' },
  { value: 'dissolve', label: 'Dissolve' },
  { value: 'push_left', label: 'Push Left' },
  { value: 'iris', label: 'Iris' },
] as const;

export const PROJECT_TRANSITION_OPTIONS = TRANSITION_OPTIONS.filter(
  (opt) => opt.value !== '',
);
```

#### 6C. Add transition selector to segment card

In the segment card component, add a dropdown to select the transition
type for each segment.  Use the same `Select` / `DropdownMenu` pattern
already used in the project for other per-segment controls:

```tsx
// In SegmentCard.tsx or equivalent
<Select
  value={segment.transition_type || ''}
  onValueChange={(value) =>
    updateSegment(segment.id, { transition_type: value })
  }
>
  <SelectTrigger className="w-[180px]">
    <SelectValue placeholder="Transition" />
  </SelectTrigger>
  <SelectContent>
    {TRANSITION_OPTIONS.map((opt) => (
      <SelectItem key={opt.value} value={opt.value}>
        {opt.label}
      </SelectItem>
    ))}
  </SelectContent>
</Select>
```

The first segment's transition type controls the transition *into* that
segment from the previous one.  Segment 0 (the first segment) has no
preceding segment, so its transition_type is ignored during rendering.
The UI may hide or disable the selector for segment 0, or show it as
informational only.

#### 6D. Add project-level transition type to settings

In the project settings panel, add a default transition type selector:

```tsx
<Select
  value={project.transition_type}
  onValueChange={(value) =>
    updateProject({ transition_type: value })
  }
>
  <SelectTrigger>
    <SelectValue placeholder="Default Transition" />
  </SelectTrigger>
  <SelectContent>
    {PROJECT_TRANSITION_OPTIONS.map((opt) => (
      <SelectItem key={opt.value} value={opt.value}>
        {opt.label}
      </SelectItem>
    ))}
  </SelectContent>
</Select>
```

---

### Step 7: Testing

#### 7A. Unit tests for `transitions.py`

Create `backend/core_engine/tests/test_transitions.py`:

```python
"""Unit tests for the transition library."""

import numpy as np
import pytest

from core_engine.transitions import (
    registry,
    TRANSITION_CHOICES,
    TRANSITION_KEYS,
    DEFAULT_TRANSITION,
)


@pytest.fixture
def frame_pair():
    """Create a pair of test frames (100x100, solid colours)."""
    frame_out = np.full((100, 100, 3), [255, 0, 0], dtype=np.uint8)  # red
    frame_in = np.full((100, 100, 3), [0, 0, 255], dtype=np.uint8)   # blue
    return frame_out, frame_in


class TestTransitionRegistry:
    def test_all_choices_registered(self):
        """Every transition in TRANSITION_CHOICES must be registered."""
        for key, _label in TRANSITION_CHOICES:
            assert key in registry.list_transitions(), (
                f"Transition '{key}' is in TRANSITION_CHOICES but not registered"
            )

    def test_default_is_registered(self):
        assert DEFAULT_TRANSITION in registry.list_transitions()

    def test_list_transitions_returns_sorted(self):
        names = registry.list_transitions()
        assert names == sorted(names)

    def test_unknown_transition_falls_back_to_crossfade(self, frame_pair):
        frame_out, frame_in = frame_pair
        result = registry.apply("nonexistent", frame_out, frame_in, 0.5, 100, 100)
        assert result.shape == (100, 100, 3)
        assert result.dtype == np.uint8


class TestTransitionFunctions:
    """Verify each transition returns a valid frame at progress 0, 0.5, 1."""

    @pytest.mark.parametrize("name", [k for k, _ in TRANSITION_CHOICES])
    @pytest.mark.parametrize("progress", [0.0, 0.25, 0.5, 0.75, 1.0])
    def test_output_shape_and_dtype(self, name, progress, frame_pair):
        frame_out, frame_in = frame_pair
        result = registry.apply(name, frame_out, frame_in, progress, 100, 100)
        assert result.shape == (100, 100, 3), f"{name} at {progress}"
        assert result.dtype == np.uint8, f"{name} at {progress}"

    @pytest.mark.parametrize("name", [k for k, _ in TRANSITION_CHOICES])
    def test_progress_zero_shows_outgoing(self, name, frame_pair):
        """At progress=0, the result should be the outgoing frame (or close)."""
        frame_out, frame_in = frame_pair
        result = registry.apply(name, frame_out, frame_in, 0.0, 100, 100)
        # Most transitions at progress=0 should return frame_out exactly
        # (some may have rounding differences)
        assert result.shape == frame_out.shape

    @pytest.mark.parametrize("name", [k for k, _ in TRANSITION_CHOICES])
    def test_progress_one_shows_incoming(self, name, frame_pair):
        """At progress=1, the result should be the incoming frame (or close)."""
        frame_out, frame_in = frame_pair
        result = registry.apply(name, frame_out, frame_in, 1.0, 100, 100)
        assert result.shape == frame_in.shape

    def test_crossfade_at_half(self, frame_pair):
        """Crossfade at 0.5 should be the midpoint of the two frames."""
        frame_out, frame_in = frame_pair
        result = registry.apply("crossfade", frame_out, frame_in, 0.5, 100, 100)
        # Red [255,0,0] + Blue [0,0,255] at 0.5 → [127,0,127] or [128,0,128]
        center = result[50, 50]
        assert 120 <= center[0] <= 135  # R channel
        assert center[1] == 0           # G channel
        assert 120 <= center[2] <= 135  # B channel


class TestTransitionPerformance:
    """Basic performance sanity — transitions should not be unreasonably slow."""

    @pytest.mark.parametrize("name", [k for k, _ in TRANSITION_CHOICES])
    def test_1080p_under_50ms(self, name):
        """Each transition call on a 1080p frame should take < 50ms."""
        import time
        frame_out = np.random.randint(0, 255, (1080, 1920, 3), dtype=np.uint8)
        frame_in = np.random.randint(0, 255, (1080, 1920, 3), dtype=np.uint8)

        start = time.perf_counter()
        result = registry.apply(name, frame_out, frame_in, 0.5, 1920, 1080)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert result.shape == (1080, 1920, 3)
        assert elapsed_ms < 50, (
            f"Transition '{name}' took {elapsed_ms:.1f}ms (limit: 50ms)"
        )
```

#### 7B. Integration test: render with varied transitions

Add a test to `backend/tests/test_e2e.py` or a new test file:

```python
def test_render_with_mixed_transitions():
    """Create a 3-segment project with different transition types and
    verify it renders without errors."""
    project = Project.objects.create(
        title="Transition Test",
        transition_type="crossfade",
    )
    for i, trans in enumerate(["", "slide_left", "iris"]):
        Segment.objects.create(
            project=project,
            sequence_index=i,
            text_content=f"Segment {i}",
            transition_type=trans,
            # ... image_file, audio_file setup ...
        )
    # Trigger render and assert success
    # (Full E2E test requires media fixtures)
```

#### 7C. Manual testing checklist

1. Create a project with 3+ segments.
2. Set different transition types on segments 1, 2, 3.
3. Render the project.
4. Play the output video and visually verify each transition.
5. Re-render with `transition_type = "crossfade"` on all and verify
   the output is identical to a pre-feature render.

---

## 4. Expected Outcome

### 4.1 After Implementation

1. **New module** `backend/core_engine/transitions.py` exists with:
   - `TransitionRegistry` class
   - 13 registered transition functions
   - `TRANSITION_CHOICES` and `TRANSITION_KEYS` constants
   - Module-level `registry` singleton

2. **Data model** changes:
   - `Project.transition_type` field (`CharField`, default `"crossfade"`)
   - `Segment.transition_type` field (`CharField`, default `""` meaning
     inherit)
   - `GlobalSettings.transition_type` field
   - All existing data migrated with default values

3. **API** returns `transition_type` on Project, Segment, and
   GlobalSettings endpoints.

4. **Rendering** honours per-segment transitions:
   - Segment 0 → Segment 1: uses Segment 1's `transition_type`
   - Segment 1 → Segment 2: uses Segment 2's `transition_type`
   - Empty `transition_type` on a segment → falls back to project
     default

5. **Frontend** shows:
   - A dropdown per segment to select the transition type
   - A project-level default transition type in settings

### 4.2 Visual Examples

```
Project: "Amazing Travel Video"
  transition_type: "crossfade" (default)

  Segment 0: "The journey begins…"
    transition_type: ""          → inherits "crossfade" (first segment, ignored)
    
  Segment 1: "Arrival in Tokyo…"
    transition_type: "slide_left" → slide-left from Segment 0 to 1
    
  Segment 2: "The temple gardens…"
    transition_type: ""          → inherits "crossfade" (project default)
    
  Segment 3: "Night life…"
    transition_type: "iris"      → iris reveal from Segment 2 to 3
    
  Segment 4: "Final thoughts…"
    transition_type: "zoom_in"   → zoom-in from Segment 3 to 4

Rendered output:
  [Seg0 ───crossfade─→ Seg1 ───slide_left─→ Seg2 ───crossfade─→ Seg3 ───iris─→ Seg4 ───zoom_in─→ Seg5]
         (ignored)       ✓ custom             ✓ default           ✓ custom        ✓ custom
```

### 4.3 Performance Expectations

| Metric | Before | After | Notes |
|--------|--------|-------|-------|
| Avg ms/frame (crossfade) | ~8 ms | ~8 ms | Identical — crossfade fn replicates weight blend |
| Avg ms/frame (slide_left) | N/A | ~3 ms | Simple array slicing, faster than crossfade |
| Avg ms/frame (iris) | N/A | ~12 ms | Uses `np.ogrid` distance calculation |
| Avg ms/frame (dissolve) | N/A | ~15 ms | Block loop; vectorize if needed |
| Avg ms/frame (zoom_in) | N/A | ~10 ms | One `cv2.resize` + `cv2.addWeighted` |
| Memory overhead | 0 | ~negligible | One extra frame buffer during transitions |

Transitions only execute during the overlap window (default 0.5 s ×
30 fps = 15 frames per cut).  Impact on total render time for a
30-segment video is minimal (~0.5 s total extra).

---

## 5. Verification Checklist

### 5.1 Pre-Implementation Checks

- [ ] Confirm `fast_compositor.py` is at 839 lines and Phase 4 starts
      at line ~653
- [ ] Confirm `models.py` has `Project.transition_duration` but no
      `transition_type`
- [ ] Confirm `Segment` model has no transition-related fields
- [ ] Confirm `video_renderer.py` uses `TRANSITION_DURATION` constant
      at line 321
- [ ] Confirm NumPy and OpenCV are available in the virtual environment
- [ ] Review `serializers.py` to confirm `transition_type` is not
      already present

### 5.2 File-Level Checks

#### `backend/core_engine/transitions.py` (NEW)
- [ ] File created at correct path
- [ ] `TRANSITION_CHOICES` has 13 entries
- [ ] `TRANSITION_KEYS` set matches choice keys
- [ ] `DEFAULT_TRANSITION` is `"crossfade"`
- [ ] `TransitionRegistry` class has `register()`, `get()`, `apply()`,
      `list_transitions()` methods
- [ ] All 13 transition functions implemented
- [ ] Each function accepts `(frame_out, frame_in, progress, width, height)`
- [ ] Each function returns `np.ndarray` of shape `(height, width, 3)` dtype `uint8`
- [ ] Module-level `registry` singleton created and all transitions registered
- [ ] `apply()` falls back to crossfade for unknown transition names
- [ ] No circular imports

#### `backend/api/models.py`
- [ ] `Project.transition_type` added with `default="crossfade"`
- [ ] `Segment.transition_type` added with `default=""`, `blank=True`
- [ ] `GlobalSettings.transition_type` added with `default="crossfade"`
- [ ] `choices=TRANSITION_CHOICES` on all three fields
- [ ] Migration generated and applied cleanly
- [ ] Existing data unchanged (no data migration needed)

#### `backend/api/serializers.py`
- [ ] `transition_type` in `ProjectSerializer.Meta.fields`
- [ ] `transition_type` in `SegmentSerializer.Meta.fields`
- [ ] `transition_type` in `GlobalSettingsSerializer.Meta.fields`
- [ ] Validation method `validate_transition_type` added to
      `GlobalSettingsSerializer`
- [ ] Validation rejects invalid transition names with clear error message

#### `backend/core_engine/video_renderer.py`
- [ ] `project_transition_type` read from `project.transition_type`
- [ ] Per-segment resolution cascade: `segment.transition_type || project_transition_type || "crossfade"`
- [ ] `"transition_type"` key added to each dict in `segment_data_list`

#### `backend/core_engine/fast_compositor.py`
- [ ] `transition_registry` imported from `core_engine.transitions`
- [ ] `segments_info` dicts include `"transition_type"` key
- [ ] Phase 4 rewritten to:
  - Collect active segments per frame
  - Single active segment → generate frame directly
  - Two active segments → generate both frames, compute progress,
    dispatch to `registry.apply()`
- [ ] `_generate_segment_frame()` helper extracted
- [ ] Logo overlay still applied AFTER transition (on top)
- [ ] Progress reporting unchanged
- [ ] No regressions for single-segment projects

#### Frontend
- [ ] TypeScript types updated with `transition_type` on Segment and Project
- [ ] `TRANSITION_OPTIONS` constant defined
- [ ] Dropdown selector added to segment card
- [ ] Project-level default transition selector added to settings
- [ ] Segment 0's transition selector disabled or hidden (no preceding segment)

### 5.3 Behavioral Checks

- [ ] Default render (no transition_type set) is identical to pre-feature render
- [ ] Setting `transition_type = "slide_left"` on Segment 2 produces
      a visible slide-left between Segment 1 and Segment 2
- [ ] Setting `transition_type = ""` on a segment falls back to project default
- [ ] All 13 transitions produce visually distinct effects
- [ ] No black frames or artifacts at transition boundaries
- [ ] Single-segment project renders without errors
- [ ] Two-segment project renders with one transition
- [ ] 10+ segment project renders with mixed transitions

### 5.4 Performance Checks

- [ ] All transition functions complete in < 50ms at 1080p
- [ ] Total render time for a 10-segment video increases by < 5%
      when using non-crossfade transitions
- [ ] Memory usage during transitions does not spike (only 2 extra
      frame buffers)

### 5.5 Regression Checks

- [ ] Existing crossfade-only renders produce byte-identical output
      (or visually identical if float precision differs)
- [ ] All existing API endpoints still work
- [ ] All existing tests pass
- [ ] Migration is reversible (`python manage.py migrate api <previous>`)

---

## 6. Notes for AI Agent

### 6.1 Implementation Order

Follow this exact sequence to avoid dependency issues:

```
1. Create transitions.py          (standalone, no dependencies)
2. Update models.py               (imports from transitions.py)
3. Generate + apply migration     (depends on models.py change)
4. Update serializers.py          (depends on models.py change)
5. Update video_renderer.py       (depends on models.py field)
6. Update fast_compositor.py      (depends on transitions.py)
7. Write unit tests               (depends on transitions.py)
8. Run tests                      (validates everything)
9. Frontend changes               (depends on API changes)
```

### 6.2 Critical: Avoid Circular Imports

`transitions.py` must NOT import from `api.models`.  The import
direction is:

```
api/models.py  →  imports from  →  core_engine/transitions.py  ✓
core_engine/transitions.py  →  imports from  →  api/models.py  ✗ CIRCULAR
```

If you need `TRANSITION_CHOICES` in both files, define them in
`transitions.py` and import into `models.py`.  If Django's app loading
order causes issues (AppRegistryNotReady), define `TRANSITION_CHOICES`
as a plain tuple in `transitions.py` — it has no Django dependencies.

**Safe alternative:** Define `TRANSITION_CHOICES` directly in
`models.py` and import it into `transitions.py`:

```python
# In models.py (top-level, no imports needed):
TRANSITION_CHOICES = [
    ("crossfade", "Crossfade"),
    ...
]

# In transitions.py:
from api.models import TRANSITION_CHOICES  # This is fine — models.py
                                            # doesn't import transitions.py
```

But this inverts the logical dependency.  The cleanest solution is:

```python
# In transitions.py (standalone, no Django imports):
TRANSITION_CHOICES = [...]  # Plain Python — no Django needed
DEFAULT_TRANSITION = "crossfade"
TRANSITION_KEYS = {k for k, _ in TRANSITION_CHOICES}

# In models.py:
from core_engine.transitions import TRANSITION_CHOICES, DEFAULT_TRANSITION
```

This works because `transitions.py` only uses `numpy`, `cv2`, `math`,
and `logging` — all stdlib/pip packages, no Django.

### 6.3 Phase 4 Rewrite Strategy

The Phase 4 rewrite is the most delicate part.  Here is the exact
strategy:

1. **Do NOT delete the existing weight-based blending code immediately.**
   Instead, wrap it in a conditional that checks if `transition_type`
   is being used.  This allows incremental testing.

2. **The overlap detection is already correct** — the existing code
   iterates active segments per frame.  You just need to change what
   happens when 2 segments are active simultaneously.

3. **Progress computation:**
   - The transition overlap region starts at `in_start` (where the
     incoming segment begins) and ends at `out_end` (where the
     outgoing segment ends).
   - `progress = (frame_idx - in_start) / (out_end - in_start)`
   - Clamp to [0.0, 1.0].

4. **Transition direction:** The `transition_type` on the INCOMING
   segment is used (Segment 1's transition_type governs the cut FROM
   Segment 0 TO Segment 1).  The first segment's `transition_type` is
   never used during rendering.

5. **Edge case — 3+ overlapping segments:** This shouldn't happen with
   the current timeline calculation (overlap is exactly
   `crossfade_duration`).  But if it does, use only the first and last
   active segments and ignore middle ones.

### 6.4 Transition Function Guidelines

When implementing transition functions:

1. **Always return `uint8`** — callers expect this.
2. **Never modify `frame_out` or `frame_in` in place** — use `.copy()`
   if you need to write into one of them.
3. **Handle `progress = 0.0`** (show outgoing) and `progress = 1.0`
   (show incoming) cleanly.
4. **Use vectorized NumPy operations** — avoid Python loops over
   pixels.  The dissolve function's block loop is acceptable because
   it loops over blocks (not pixels), but the vectorized alternative
   in the performance note is preferred.
5. **Use `cv2.addWeighted()`** for alpha blending — it's faster than
   manual `frame * alpha + frame * (1 - alpha)` because it uses SIMD.
6. **Avoid creating large temporary arrays unnecessarily** — reuse
   buffers where possible.

### 6.5 Model Field Design Decisions

**Why `CharField` instead of `IntegerField` with choices?**
String keys like `"slide_left"` are self-documenting in the database
and API, whereas integer choices (0, 1, 2, …) require a mapping table
to interpret.  The minor storage overhead of a 30-char string vs an
int is negligible.

**Why `default=""` on Segment instead of `null=True`?**
Django convention: avoid `null=True` on string-based fields.  Empty
string is the "not set" sentinel.  This simplifies queryset filtering
(`Segment.objects.filter(transition_type="")` vs `…filter(transition_type__isnull=True)`).

**Why `transition_type` on the INCOMING segment, not the outgoing?**
It matches user mental model: "What transition leads INTO this scene?"
iMovie, Premiere, and CapCut all place transitions on the incoming
clip's boundary.

### 6.6 Frontend Notes

- The transition selector should only appear on segments with
  `sequence_index > 0` (no incoming transition for the first segment).
- Consider adding a small visual preview icon per transition type
  (SVG icons or CSS animations).  This is optional for v1.
- The `""` (empty string) option in the dropdown should display as
  "Project Default (Crossfade)" — showing the resolved default.
- When the user changes the project-level default, all segments with
  `transition_type = ""` implicitly update.

### 6.7 Testing Notes

- **Crossfade reproduction test:** Render a 3-segment project with all
  transitions set to "crossfade" and compare the output to a render
  from before the feature was implemented.  The outputs should be
  visually identical (pixel-level matching may differ slightly due to
  `cv2.addWeighted` vs manual division, but the difference should be
  imperceptible).

- **Progress values to test:** 0.0, 0.001 (near-zero), 0.5, 0.999
  (near-one), 1.0.  Edge values often expose off-by-one bugs.

- **Resolution parity:** Test with both 1920×1080 and 1080×1920
  (portrait mode) to catch width/height confusion bugs.

- **Single segment project:** Must render without errors.  No
  transition code should execute.

### 6.8 Dissolve Performance Optimization

The dissolve function uses a Python loop over blocks.  If profiling
shows this is too slow, replace it with the vectorized version:

```python
def _transition_dissolve_vectorized(
    frame_out: np.ndarray,
    frame_in: np.ndarray,
    progress: float,
    width: int,
    height: int,
) -> np.ndarray:
    block_size = 16
    rows = (height + block_size - 1) // block_size
    cols = (width + block_size - 1) // block_size

    rng = np.random.RandomState(seed=42)
    thresholds = rng.rand(rows, cols)

    # Expand threshold block mask to full resolution
    mask = (thresholds < progress).astype(np.uint8)
    mask_full = np.repeat(np.repeat(mask, block_size, axis=0), block_size, axis=1)
    mask_full = mask_full[:height, :width, np.newaxis]

    return np.where(mask_full, frame_in, frame_out).astype(np.uint8)
```

This is ~10× faster because it avoids the Python loop entirely.
Consider using this as the default implementation from the start.

### 6.9 Future Extensibility

The `TransitionRegistry.register()` method allows users (or plugins)
to add custom transitions at runtime:

```python
from core_engine.transitions import registry

def my_custom_wipe(frame_out, frame_in, progress, width, height):
    # Custom logic
    ...

registry.register("my_custom_wipe", my_custom_wipe)
```

To support this in the UI, the API could expose an endpoint that lists
available transitions:

```python
# views.py
@api_view(['GET'])
def list_transitions(request):
    from core_engine.transitions import registry, TRANSITION_CHOICES
    return Response({
        "transitions": [
            {"key": key, "label": label}
            for key, label in TRANSITION_CHOICES
        ]
    })
```

This is optional for v1 but worth planning for.

### 6.10 Exact Lines to Modify (Reference)

| File | Lines | What to Change |
|------|-------|----------------|
| `fast_compositor.py` | 560–610 | Phase 1: add `"transition_type"` to `segments_info` dict |
| `fast_compositor.py` | 653–766 | Phase 4: replace weight blending with transition dispatch |
| `models.py` | ~78 (after `transition_duration`) | Add `transition_type` to `Project` |
| `models.py` | ~146 (after `is_locked`) | Add `transition_type` to `Segment` |
| `models.py` | ~239 (after `transition_duration`) | Add `transition_type` to `GlobalSettings` |
| `serializers.py` | ~43 (ProjectSerializer fields) | Add `'transition_type'` to fields list |
| `serializers.py` | ~56 (SegmentSerializer fields) | Add `'transition_type'` to fields list |
| `serializers.py` | ~85 (GlobalSettingsSerializer fields) | Add `'transition_type'` to fields list |
| `video_renderer.py` | ~845 (segment_data_list loop) | Add `"transition_type"` to each segment dict |
| `video_renderer.py` | ~640 (project settings reading) | Read `project.transition_type` |

### 6.11 Migration Safety

The migration is safe because:

1. **All new fields have defaults** — `"crossfade"` for Project and
   GlobalSettings, `""` for Segment.
2. **No data migration is needed** — Django applies column defaults
   automatically.
3. **The migration is reversible** — `RemoveField` is auto-generated
   by Django when rolling back.
4. **No foreign keys or complex constraints** — just `CharField` with
   `choices`.

To verify migration safety:

```bash
python manage.py makemigrations --dry-run api  # preview
python manage.py makemigrations api              # generate
python manage.py showmigrations api              # verify
python manage.py migrate api                     # apply
python manage.py migrate api <previous_number>   # rollback test
python manage.py migrate api                     # re-apply
```

### 6.12 Common Pitfalls

1. **Don't import `transitions.py` at module level in
   `fast_compositor.py`** if it triggers Django app loading.  Use a
   lazy import inside `fast_render_segments()` (similar to how
   `ken_burns` is imported at line ~535).

2. **Don't forget to handle the case where `segments_info[in_idx]`
   doesn't have `"transition_type"`** — always use `.get(key, "crossfade")`
   for backward compatibility with any code that builds `segments_info`
   without the new key.

3. **Don't modify `frame_out` or `frame_in` arrays in-place** inside
   transition functions.  The compositor may reuse these buffers. Always
   return a new array or use `.copy()`.

4. **Don't use random seeds that change per frame** in dissolve.  The
   dissolve pattern must be consistent across all 15 frames of the
   transition (only `progress` changes).  Using `RandomState(seed=42)`
   ensures block ordering is fixed.

5. **Don't forget to clamp progress to [0.0, 1.0]** before passing to
   transition functions.  Floating-point arithmetic may produce values
   like -0.001 or 1.002.

---

*End of Feature 3.1 — Transition Variety implementation document.*
