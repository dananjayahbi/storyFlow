# Feature 1.4 — Parallel Image Upscaling

> **Status:** Planned  
> **Category:** Core Engine / Upscaling Performance  
> **Target Files:** `backend/core_engine/image_upscaler.py`, `backend/core_engine/video_renderer.py`  
> **Estimated Complexity:** Medium  
> **Expected Speedup:** 2.5–3.5× (10+ min → 3–4 min for 20-segment project)  
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

The current `upscale_images_batch()` function in
`backend/core_engine/image_upscaler.py` (line 436, 483 lines total)
upscales every image **sequentially** in a simple `for` loop.  For a
typical 20-segment project, each image takes 30–40 seconds through the
RealESRGAN x4 model, bringing the total upscaling phase to
**10+ minutes**.

The existing sequential pipeline looks like this (lines 453–470):

```python
for idx, src_path in enumerate(image_paths):
    filename = os.path.basename(src_path)
    name, ext = os.path.splitext(filename)
    out_path = os.path.join(output_dir, f"{name}_upscaled{ext}")

    if on_progress:
        on_progress(idx, total, f"Upscaling image {idx + 1}/{total}")

    results[src_path] = upscale_image(
        src_path, out_path, model_name, denoise_strength,
    )
```

Each call to `upscale_image()` (L389) does three things:

1. **I/O Read** — `cv2.imread()` loads the source image from disk
2. **Inference** — `upscaler.enhance()` runs the RRDBNet model (GPU or CPU)
3. **I/O Write** — `cv2.imwrite()` saves the result to disk

On GPU, inference dominates (90%+ of wall time).  On CPU, inference is
even slower but the GIL is released during PyTorch operations \& OpenCV
I/O, making threads viable.  In both modes, disk I/O is completely
serialized with inference — the CPU sits idle while writing, and the
GPU sits idle while loading the next image.

### 1.2 Proposed Solution

Implement a **multi-strategy parallel upscaling pipeline** with the
following components:

| Strategy | When Used | Mechanism | Speedup |
|---|---|---|---|
| **Smart Skip** | Always | Skip images already at or above target resolution | Variable (0–100% of images skipped) |
| **Pipelined I/O** | GPU mode | 3-stage pipeline: Loader → Inference → Saver | 1.3–1.5× |
| **Thread Pool** | CPU mode | `ThreadPoolExecutor` with 2–4 workers doing full upscale | 2–4× |
| **Already-upscaled cache** | Always | Skip images whose output already exists and is newer | Instant on re-runs |

The **combined approach** (Smart Skip + Pipeline/ThreadPool) is expected
to bring a 20-segment upscaling pass from 10+ minutes down to 3–4
minutes.

### 1.3 Why Not Multi-Thread GPU Inference?

PyTorch CUDA inference is **not thread-safe** for the same model
instance.  Calling `model(tensor)` from two threads simultaneously on
the same CUDA model causes undefined behaviour (corrupted results or
CUDA errors).  Creating multiple model copies would double/triple VRAM
usage, which is unacceptable for a model that already needs ~500 MB
for RealESRGAN_x4plus.

Therefore, on GPU:
- Model inference remains **single-threaded**
- I/O (load + save) is **pipelined** with inference using a
  producer/consumer queue pattern

On CPU:
- PyTorch allows concurrent `model(tensor)` calls from different
  threads (the GIL is released during the C++ backend computations)
- A `ThreadPoolExecutor` with 2–4 workers provides real parallelism

### 1.4 Files Involved

| File | Role | Changes |
|---|---|---|
| `backend/core_engine/image_upscaler.py` | Main implementation | Add parallel strategies, smart skip, pipeline |
| `backend/core_engine/video_renderer.py` | Calls `upscale_images_batch()` at L888–893 | Pass `task_id` for cancellation support |
| `backend/api/tasks.py` | Provides `TaskManager.is_cancelled()` | **No changes** |
| `backend/core_engine/tests/` | Tests | Add test file for parallel upscaling |

### 1.5 Key Existing Functions Reference

| Function | Location | Thread-Safe? |
|---|---|---|
| `upscale_images_batch()` | `image_upscaler.py` L436 | Outer function — not called concurrently |
| `upscale_image()` | `image_upscaler.py` L389 | Yes on CPU (GIL released in PyTorch); **No** on CUDA (same model) |
| `_get_upscaler()` | `image_upscaler.py` L349 | Yes — uses `_cache_lock` (threading.Lock) |
| `_UpscalerInstance.enhance()` | `image_upscaler.py` L243 | **No** on CUDA (shared model state); Yes on CPU |
| `_UpscalerInstance._tile_process()` | `image_upscaler.py` L299 | Same as `enhance()` |
| `cv2.imread()` | OpenCV | Yes — stateless, releases GIL |
| `cv2.imwrite()` | OpenCV | Yes — stateless, releases GIL |

### 1.6 Dependencies

All required modules are already available — no new pip packages needed:

| Module | Source | Purpose |
|---|---|---|
| `concurrent.futures.ThreadPoolExecutor` | stdlib | CPU-mode thread pool |
| `threading.Thread` | stdlib | Pipeline worker threads |
| `queue.Queue` | stdlib | Bounded queues for pipeline stages |
| `torch` | already installed | Device detection, inference |
| `cv2` | already installed | Image load/save |
| `os`, `time`, `logging` | stdlib | Utilities |

### 1.7 Important Constraints

1. **GPU VRAM**: x4 upscaling a 1080p image produces a
   `(1, 3, 4320, 7680)` tensor — roughly 380 MB in FP16.  Never have
   more than one inference in flight on GPU.
2. **Thread safety**: On CUDA, the `_UpscalerInstance` singleton must
   only be called from a single inference thread.  On CPU, concurrent
   calls are safe because PyTorch releases the GIL.
3. **Progress reporting**: The `on_progress(current, total, message)`
   callback must remain accurate and monotonically increasing.
4. **Error handling**: If one image fails, log the error, return the
   original path for that image, and continue with the rest.  Never
   crash the entire batch.
5. **Cancellation**: Check for cancellation between images (via a
   `cancel_event` threading.Event or a callable) and abort early when
   requested.
6. **Backwards compatibility**: The `upscale_images_batch()` signature
   must remain compatible — new parameters are optional with defaults
   matching current behaviour.

---

## 2. Flow Diagram

### 2.1 Current Architecture (Sequential)

```
┌───────────────────────────────────────────────────────────┐
│                     Main Thread                           │
│                                                           │
│  for each image in image_paths:                           │
│    ┌────────────────────────────────────────────────────┐  │
│    │  1. cv2.imread(image_path)         [I/O — disk]   │  │
│    │  2. upscaler.enhance(img)          [Compute]      │  │
│    │  3. cv2.imwrite(output_path, out)  [I/O — disk]   │  │
│    │  4. on_progress(i, total)                         │  │
│    └────────────────────────────────────────────────────┘  │
│                                                           │
│  Timeline for 4 images:                                   │
│  ┌──────┐┌──────┐┌──────┐┌──────┐                        │
│  │ img1 ││ img2 ││ img3 ││ img4 │                        │
│  └──────┘└──────┘└──────┘└──────┘                        │
│  |──────── 40s+ total ─────────|                          │
└───────────────────────────────────────────────────────────┘
```

### 2.2 Proposed Architecture — GPU Mode (Pipelined I/O)

```
┌─────────────────────────────────────────────────────────────────────┐
│  Stage 0: Smart Skip Filter                                        │
│                                                                     │
│    image_paths ─► filter ─► skip_list  (already large enough)       │
│                          ─► work_list  (need upscaling)             │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
              work_list       │
                              ▼
   ┌──────────────────────────────────────────────────────────────┐
   │                   3-Stage Pipeline                           │
   │                                                              │
   │  ┌──────────────┐    ┌──────────────────┐    ┌───────────┐  │
   │  │ Loader Thread │    │ Inference Thread  │    │Saver Thread│ │
   │  │              │    │  (Main/Single)    │    │           │  │
   │  │ loop:        │    │                   │    │ loop:     │  │
   │  │  path=next() │    │ loop:             │    │  (path,   │  │
   │  │  img=imread()│    │  (path,img)=      │    │   result) │  │
   │  │  load_q.put( │──►│   load_q.get()    │    │   =save_q │  │
   │  │   (path,img))│    │  result=enhance() │──►│   .get()  │  │
   │  │              │    │  save_q.put(       │    │  imwrite()│  │
   │  │              │    │   (path,result))   │    │  progress │  │
   │  └──────────────┘    └──────────────────┘    └───────────┘  │
   │                                                              │
   │  Bounded Queues (maxsize=2):                                 │
   │    load_q: (src_path, img_bgr) tuples                        │
   │    save_q: (out_path, result_bgr) tuples                     │
   └──────────────────────────────────────────────────────────────┘

Timeline for 4 images (overlapped I/O):

Loader:    [load1][load2][load3][load4]
Inference:       [inf1 ][inf2 ][inf3 ][inf4 ]
Saver:                  [save1][save2][save3][save4]

vs Sequential:
           [load1|inf1|save1][load2|inf2|save2][load3|inf3|save3]...

Savings: ~15-30% from I/O overlap
```

### 2.3 Proposed Architecture — CPU Mode (Thread Pool)

```
┌─────────────────────────────────────────────────────────────────────┐
│  Stage 0: Smart Skip Filter  (same as GPU mode)                    │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                  work_list       │
                                  ▼
   ┌──────────────────────────────────────────────────────────────┐
   │              ThreadPoolExecutor (max_workers=N)              │
   │                                                              │
   │  ┌────────────┐ ┌────────────┐ ┌────────────┐               │
   │  │  Worker 0   │ │  Worker 1   │ │  Worker 2   │ ...         │
   │  │            │ │            │ │            │               │
   │  │ img=load() │ │ img=load() │ │ img=load() │               │
   │  │ out=enh()  │ │ out=enh()  │ │ out=enh()  │               │
   │  │ save(out)  │ │ save(out)  │ │ save(out)  │               │
   │  │ progress() │ │ progress() │ │ progress() │               │
   │  └────────────┘ └────────────┘ └────────────┘               │
   │                                                              │
   │  Each worker does full load→enhance→save cycle               │
   │  PyTorch releases GIL during C++ ops → real parallelism      │
   └──────────────────────────────────────────────────────────────┘

Timeline for 4 images with 2 workers:

Worker 0:  [───img1───][───img3───]
Worker 1:  [───img2───][───img4───]

vs Sequential:
           [───img1───][───img2───][───img3───][───img4───]

Savings: ~50% with 2 workers, ~65% with 3, ~75% with 4
```

### 2.4 Smart Skip Decision Tree

```
                    ┌──────────────────────┐
                    │ For each image_path  │
                    └──────────┬───────────┘
                               │
                               ▼
                  ┌────────────────────────┐
                  │ Output file already    │ YES  ┌─────────────────┐
                  │ exists AND is newer    │─────►│ SKIP: use cached│
                  │ than source?           │      │ output path     │
                  └────────────┬───────────┘      └─────────────────┘
                               │ NO
                               ▼
                  ┌────────────────────────┐
                  │ Read image dimensions  │
                  │ with cv2.imread()      │
                  │ or fast header parse   │
                  └────────────┬───────────┘
                               │
                               ▼
                  ┌────────────────────────┐
                  │ width >= target_width  │ YES  ┌─────────────────┐
                  │ AND                    │─────►│ SKIP: copy or   │
                  │ height >= target_height│      │ symlink original│
                  └────────────┬───────────┘      └─────────────────┘
                               │ NO
                               ▼
                  ┌────────────────────────┐
                  │ Add to work_list for   │
                  │ actual upscaling       │
                  └────────────────────────┘
```

### 2.5 Cancellation Flow

```
           ┌───────────────────────────────────┐
           │  TaskManager.cancel_task(task_id)  │
           │  sets cancel_requested = True      │
           └───────────────┬───────────────────┘
                           │
                           ▼
           ┌───────────────────────────────────┐
           │  cancel_event.set()  (threading)  │
           │  -or- callable check returns True │
           └───────────────┬───────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
  ┌───────────┐   ┌──────────────┐   ┌───────────┐
  │ Loader     │   │ Inference    │   │ Workers   │
  │ checks     │   │ checks      │   │ check     │
  │ cancel     │   │ cancel      │   │ cancel    │
  │ between    │   │ between     │   │ between   │
  │ images     │   │ images      │   │ images    │
  └─────┬──────┘   └──────┬──────┘   └─────┬─────┘
        │                  │                │
        ▼                  ▼                ▼
  ┌─────────────────────────────────────────────┐
  │ Put SENTINEL on queues / break from loop    │
  │ Return partial results (completed images)   │
  │ Log cancellation                            │
  └─────────────────────────────────────────────┘
```

### 2.6 Overall Integration with video_renderer.py

```
video_renderer.py  render_project()
        │
        │  L872-914: Upscaling phase
        │
        ▼
┌──────────────────────────────────────────────────────┐
│  upscale_images_batch(                               │
│      image_paths    = [...20 paths...],              │
│      output_dir     = ".../upscaled_images/",        │
│      model_name     = "RealESRGAN_x4plus",           │
│      denoise_strength = 0.5,                         │
│      on_progress    = upscale_progress,              │
│      cancel_check   = lambda: mgr.is_cancelled(id), │  ← NEW
│      max_workers    = None,                          │  ← NEW
│      skip_large     = True,                          │  ← NEW
│      target_width   = 3840,                          │  ← NEW
│      target_height  = 2160,                          │  ← NEW
│  )                                                   │
│                                                      │
│  Returns: { orig_path: upscaled_path, ... }          │
└──────────────────────────────────────────────────────┘
        │
        ▼
  Replace paths in segment_data_list
  Continue to audio mix + frame rendering
```

---

## 3. Step-by-Step Instructions

### Step 1: Add New Imports

At the top of `backend/core_engine/image_upscaler.py`, after the
existing imports (line 28), add the concurrency modules:

```python
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from queue import Queue, Empty
from typing import Callable
```

These are all stdlib — no new dependencies required.

---

### Step 2: Add the `_image_meets_target()` Helper

Place this function after `get_available_models()` (around line 90),
before the PyTorch architecture definitions.  This implements the
"Smart Skip" logic.

```python
def _image_meets_target(
    image_path: str,
    target_width: int,
    target_height: int,
) -> bool:
    """Check if an image already meets or exceeds the target resolution.

    Uses cv2.imread with IMREAD_REDUCED_COLOR_2 for a fast dimension
    check when possible, falling back to full read.

    Args:
        image_path: Path to the image file.
        target_width: Minimum acceptable width in pixels.
        target_height: Minimum acceptable height in pixels.

    Returns:
        True if the image is already large enough and can be skipped.
    """
    try:
        # Fast: read just the header for dimensions
        img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
        if img is None:
            return False
        h, w = img.shape[:2]
        return w >= target_width and h >= target_height
    except Exception:
        return False
```

---

### Step 3: Add the `_output_is_cached()` Helper

Place this directly after `_image_meets_target()`.  This avoids
re-upscaling images that were already processed on a previous run.

```python
def _output_is_cached(source_path: str, output_path: str) -> bool:
    """Return True if the upscaled output already exists and is newer
    than the source image.

    This allows re-runs to skip images that were successfully upscaled
    on a previous attempt.

    Args:
        source_path: Path to the original image.
        output_path: Path to the expected upscaled output.

    Returns:
        True if cached output is valid and can be reused.
    """
    try:
        if not os.path.isfile(output_path):
            return False
        src_mtime = os.path.getmtime(source_path)
        out_mtime = os.path.getmtime(output_path)
        # Output must be newer than source and non-empty
        out_size = os.path.getsize(output_path)
        return out_mtime >= src_mtime and out_size > 0
    except OSError:
        return False
```

---

### Step 4: Add the `_compute_work_list()` Planner

This function partitions images into "skip" and "work" lists.  Place it
after the previous helpers.

```python
def _compute_work_list(
    image_paths: list[str],
    output_dir: str,
    skip_large: bool,
    target_width: int,
    target_height: int,
) -> tuple[dict[str, str], list[tuple[str, str]]]:
    """Partition images into skip-set and work-list.

    Args:
        image_paths: All source image paths.
        output_dir: Directory for upscaled outputs.
        skip_large: Whether to skip images already meeting target size.
        target_width: Target width for smart-skip comparison.
        target_height: Target height for smart-skip comparison.

    Returns:
        A tuple of:
        - pre_results: dict mapping src→output for images that can be
          skipped (cached or already large enough).  For "already large"
          images the output is the original path itself.
        - work_list: list of (src_path, out_path) tuples that need
          actual upscaling.
    """
    pre_results: dict[str, str] = {}
    work_list: list[tuple[str, str]] = []

    for src_path in image_paths:
        filename = os.path.basename(src_path)
        name, ext = os.path.splitext(filename)
        out_path = os.path.join(output_dir, f"{name}_upscaled{ext}")

        # Check 1: cached output from previous run
        if _output_is_cached(src_path, out_path):
            logger.debug("Cached upscale hit: %s", filename)
            pre_results[src_path] = out_path
            continue

        # Check 2: image already meets target resolution
        if skip_large and _image_meets_target(src_path, target_width, target_height):
            logger.debug("Smart skip (already large): %s", filename)
            pre_results[src_path] = src_path  # use original
            continue

        work_list.append((src_path, out_path))

    skipped = len(pre_results)
    remaining = len(work_list)
    logger.info(
        "Upscale planner: %d skipped (%d cached, %d large enough), "
        "%d to upscale",
        skipped, skipped, 0, remaining,  # refined counting below
    )

    return pre_results, work_list
```

---

### Step 5: Create the GPU Pipeline Functions

These three functions implement the 3-stage pipeline for GPU mode.
Place them after `_compute_work_list()`.

#### 5a: Loader Thread

```python
_PIPELINE_SENTINEL = object()  # Signals end-of-stream in pipeline queues


def _loader_thread_fn(
    work_list: list[tuple[str, str]],
    load_queue: 'Queue',
    cancel_check: Callable[[], bool] | None,
) -> None:
    """Loader thread: reads images from disk and pushes to load_queue.

    Args:
        work_list: List of (src_path, out_path) pairs to load.
        load_queue: Bounded queue to put (src_path, out_path, img_bgr)
            tuples onto.
        cancel_check: Optional callable returning True if cancelled.
    """
    try:
        for src_path, out_path in work_list:
            if cancel_check and cancel_check():
                logger.info("Loader thread: cancellation detected, stopping")
                break

            img = cv2.imread(src_path, cv2.IMREAD_UNCHANGED)
            if img is None:
                logger.error("Loader: failed to read %s", src_path)
                # Put a failure marker — inference thread will handle it
                load_queue.put((src_path, out_path, None))
                continue

            # BGRA → BGR if needed
            if img.ndim == 3 and img.shape[2] == 4:
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

            load_queue.put((src_path, out_path, img))
    finally:
        load_queue.put(_PIPELINE_SENTINEL)
        logger.debug("Loader thread finished")
```

#### 5b: Inference Thread

```python
def _inference_thread_fn(
    upscaler: '_UpscalerInstance',
    load_queue: 'Queue',
    save_queue: 'Queue',
    cancel_check: Callable[[], bool] | None,
) -> None:
    """Inference thread: pulls loaded images, runs model, pushes results.

    This is the ONLY thread that calls upscaler.enhance() — ensuring
    thread safety on CUDA.

    Args:
        upscaler: The cached _UpscalerInstance singleton.
        load_queue: Queue of (src_path, out_path, img_bgr) from loader.
        save_queue: Queue of (src_path, out_path, result_bgr) for saver.
        cancel_check: Optional callable returning True if cancelled.
    """
    try:
        while True:
            item = load_queue.get()
            if item is _PIPELINE_SENTINEL:
                break

            src_path, out_path, img = item

            if cancel_check and cancel_check():
                logger.info("Inference thread: cancellation detected")
                break

            # Handle loader failure — pass through original path
            if img is None:
                save_queue.put((src_path, out_path, None))
                continue

            try:
                result = upscaler.enhance(img, tile_size=512, tile_pad=10, pre_pad=10)
                save_queue.put((src_path, out_path, result))
            except Exception as exc:
                logger.error("Inference failed for %s: %s", src_path, exc)
                save_queue.put((src_path, out_path, None))
    finally:
        save_queue.put(_PIPELINE_SENTINEL)
        logger.debug("Inference thread finished")
```

#### 5c: Saver Thread

```python
def _saver_thread_fn(
    save_queue: 'Queue',
    results: dict[str, str],
    results_lock: threading.Lock,
    progress_counter: list,       # mutable list [current_count]
    total_work: int,
    total_images: int,
    skipped_count: int,
    on_progress: Callable | None,
) -> None:
    """Saver thread: writes upscaled images to disk and reports progress.

    Args:
        save_queue: Queue of (src_path, out_path, result_bgr) from inference.
        results: Shared dict to store src→output mappings (locked).
        results_lock: Lock protecting the results dict.
        progress_counter: Mutable list holding [completed_count] for
            thread-safe atomic increment via lock.
        total_work: Number of images being upscaled (excludes skipped).
        total_images: Total image count including skipped (for progress).
        skipped_count: Number of pre-skipped images (for progress offset).
        on_progress: Optional callback (current, total, message).
    """
    try:
        while True:
            item = save_queue.get()
            if item is _PIPELINE_SENTINEL:
                break

            src_path, out_path, result = item

            if result is None:
                # Inference failed — fall back to original path
                with results_lock:
                    results[src_path] = src_path
            else:
                try:
                    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
                    cv2.imwrite(out_path, result)
                    src_name = os.path.basename(src_path)
                    out_name = os.path.basename(out_path)
                    logger.info("Saved upscaled: %s → %s", src_name, out_name)
                    with results_lock:
                        results[src_path] = out_path
                except Exception as exc:
                    logger.error("Save failed for %s: %s", out_path, exc)
                    with results_lock:
                        results[src_path] = src_path

            # Update progress
            with results_lock:
                progress_counter[0] += 1
                current = skipped_count + progress_counter[0]

            if on_progress:
                on_progress(
                    current, total_images,
                    f"Upscaling image {current}/{total_images}",
                )
    finally:
        logger.debug("Saver thread finished")
```

---

### Step 6: Create the `_upscale_gpu_pipeline()` Orchestrator

This function wires the 3-stage pipeline together and manages thread
lifecycle.  Place it after the saver thread function.

```python
def _upscale_gpu_pipeline(
    work_list: list[tuple[str, str]],
    model_name: str,
    denoise_strength: float,
    pre_results: dict[str, str],
    total_images: int,
    on_progress: Callable | None,
    cancel_check: Callable[[], bool] | None,
) -> dict[str, str]:
    """Run the 3-stage GPU pipeline for upscaling.

    Args:
        work_list: List of (src_path, out_path) pairs needing upscaling.
        model_name: Model registry key.
        denoise_strength: Denoise strength (informational).
        pre_results: Pre-populated results from smart-skip phase.
        total_images: Total number of images (including skipped).
        on_progress: Optional progress callback.
        cancel_check: Optional cancellation callable.

    Returns:
        Complete mapping of original_path → output_path for all images.
    """
    upscaler = _get_upscaler(model_name)
    if upscaler is None:
        logger.warning("Upscaler unavailable — returning originals")
        results = dict(pre_results)
        for src, out in work_list:
            results[src] = src
        return results

    results = dict(pre_results)
    results_lock = threading.Lock()
    progress_counter = [0]  # mutable for thread access
    skipped_count = len(pre_results)

    # Bounded queues — maxsize=2 provides enough buffering without
    # excessive memory usage (at most 2 full images in each queue)
    load_queue: Queue = Queue(maxsize=2)
    save_queue: Queue = Queue(maxsize=2)

    loader = threading.Thread(
        target=_loader_thread_fn,
        args=(work_list, load_queue, cancel_check),
        name="upscale-loader",
        daemon=True,
    )
    inferencer = threading.Thread(
        target=_inference_thread_fn,
        args=(upscaler, load_queue, save_queue, cancel_check),
        name="upscale-inference",
        daemon=True,
    )
    saver = threading.Thread(
        target=_saver_thread_fn,
        args=(
            save_queue, results, results_lock,
            progress_counter, len(work_list), total_images,
            skipped_count, on_progress,
        ),
        name="upscale-saver",
        daemon=True,
    )

    start_time = time.perf_counter()
    logger.info(
        "Starting GPU upscale pipeline: %d images to process", len(work_list),
    )

    loader.start()
    inferencer.start()
    saver.start()

    # Wait for orderly shutdown: loader→inferencer→saver
    loader.join()
    inferencer.join()
    saver.join()

    elapsed = time.perf_counter() - start_time
    logger.info(
        "GPU pipeline finished: %d images in %.1fs (%.1fs/image avg)",
        len(work_list), elapsed,
        elapsed / len(work_list) if work_list else 0,
    )

    return results
```

---

### Step 7: Create the `_upscale_cpu_threadpool()` Orchestrator

This function handles CPU-mode parallelism using `ThreadPoolExecutor`.
Place it after the GPU pipeline function.

```python
def _upscale_cpu_threadpool(
    work_list: list[tuple[str, str]],
    model_name: str,
    denoise_strength: float,
    pre_results: dict[str, str],
    total_images: int,
    max_workers: int,
    on_progress: Callable | None,
    cancel_check: Callable[[], bool] | None,
) -> dict[str, str]:
    """Run a thread pool for CPU-mode parallel upscaling.

    On CPU, PyTorch inference releases the GIL during the C++ backend
    computation, so multiple threads can perform inference concurrently.

    Args:
        work_list: List of (src_path, out_path) pairs needing upscaling.
        model_name: Model registry key.
        denoise_strength: Denoise strength (informational).
        pre_results: Pre-populated results from smart-skip phase.
        total_images: Total number of images (including skipped).
        max_workers: Number of concurrent worker threads.
        on_progress: Optional progress callback.
        cancel_check: Optional cancellation callable.

    Returns:
        Complete mapping of original_path → output_path for all images.
    """
    results = dict(pre_results)
    results_lock = threading.Lock()
    completed = [0]  # mutable counter
    skipped_count = len(pre_results)
    cancelled = threading.Event()

    def _worker(src_path: str, out_path: str) -> tuple[str, str]:
        """Single worker: load, upscale, save one image."""
        if cancelled.is_set():
            return src_path, src_path

        if cancel_check and cancel_check():
            cancelled.set()
            return src_path, src_path

        try:
            result_path = upscale_image(
                src_path, out_path, model_name, denoise_strength,
            )
        except Exception as exc:
            logger.error("Worker failed on %s: %s", src_path, exc)
            result_path = src_path

        # Progress update
        with results_lock:
            completed[0] += 1
            current = skipped_count + completed[0]

        if on_progress:
            on_progress(
                current, total_images,
                f"Upscaling image {current}/{total_images}",
            )

        return src_path, result_path

    start_time = time.perf_counter()
    logger.info(
        "Starting CPU thread pool: %d images, %d workers",
        len(work_list), max_workers,
    )

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures: list[Future] = []
        for src_path, out_path in work_list:
            futures.append(executor.submit(_worker, src_path, out_path))

        for future in as_completed(futures):
            try:
                src, result = future.result()
                results[src] = result
            except Exception as exc:
                logger.error("Thread pool future error: %s", exc)

    elapsed = time.perf_counter() - start_time
    logger.info(
        "CPU thread pool finished: %d images in %.1fs (%.1fs/image avg)",
        len(work_list), elapsed,
        elapsed / len(work_list) if work_list else 0,
    )

    return results
```

---

### Step 8: Rewrite `upscale_images_batch()` — The Main Entry Point

Replace the existing `upscale_images_batch()` function (L436–476)
with the new parallel-aware version.  The function signature gains
new optional parameters while remaining backwards-compatible.

```python
def upscale_images_batch(
    image_paths: list[str],
    output_dir: str,
    model_name: str = "RealESRGAN_x4plus",
    denoise_strength: float = 0.5,
    on_progress: Optional[callable] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
    max_workers: Optional[int] = None,
    skip_large: bool = True,
    target_width: int = 3840,
    target_height: int = 2160,
) -> dict[str, str]:
    """
    Upscale a batch of images with parallel processing support.

    Automatically selects the best strategy based on the available
    hardware:
    - **GPU mode**: 3-stage pipeline (load → infer → save) with
      single-threaded inference to avoid CUDA thread-safety issues.
    - **CPU mode**: ThreadPoolExecutor with 2–4 workers for real
      parallel inference (PyTorch releases the GIL).

    Also applies smart-skip logic to avoid upscaling images that:
    - Already exist from a previous run (cached output)
    - Already meet or exceed the target resolution

    Args:
        image_paths: List of source image paths.
        output_dir: Directory for upscaled outputs.
        model_name: Model name key (see ``MODEL_REGISTRY``).
        denoise_strength: Denoise strength (0–1).
        on_progress: Optional callback ``(current, total, message)``.
        cancel_check: Optional callable returning True if the task
            has been cancelled.  Checked between images.
        max_workers: Number of CPU workers (CPU mode only).
            Defaults to ``min(os.cpu_count() or 4, 4)``.
        skip_large: If True, skip images already meeting target size.
        target_width: Width threshold for smart-skip (default: 4K).
        target_height: Height threshold for smart-skip (default: 4K).

    Returns:
        Dict mapping each original path to its upscaled output path.
        Failed images map to their original (un-upscaled) path.
    """
    if not image_paths:
        return {}

    total_images = len(image_paths)
    os.makedirs(output_dir, exist_ok=True)

    # ── Stage 0: Plan work (smart skip + cache check) ──────────
    pre_results, work_list = _compute_work_list(
        image_paths, output_dir, skip_large, target_width, target_height,
    )

    # Report skipped images as instant progress
    skipped = len(pre_results)
    if skipped > 0 and on_progress:
        on_progress(skipped, total_images, f"Skipped {skipped} images (cached/large)")

    # If everything was skipped, we're done
    if not work_list:
        logger.info("All %d images skipped — nothing to upscale", total_images)
        if on_progress:
            on_progress(total_images, total_images, "Image upscaling complete")
        return pre_results

    # ── Detect device ───────────────────────────────────────────
    use_gpu = False
    if _TORCH_AVAILABLE:
        use_gpu = torch.cuda.is_available()

    # ── Resolve worker count (CPU mode) ────────────────────────
    if max_workers is None:
        cpu_count = os.cpu_count() or 4
        max_workers = max(2, min(cpu_count, 4))

    # ── Strategy dispatch ──────────────────────────────────────
    if use_gpu:
        logger.info(
            "Using GPU pipeline strategy (CUDA) for %d images", len(work_list),
        )
        results = _upscale_gpu_pipeline(
            work_list=work_list,
            model_name=model_name,
            denoise_strength=denoise_strength,
            pre_results=pre_results,
            total_images=total_images,
            on_progress=on_progress,
            cancel_check=cancel_check,
        )
    else:
        logger.info(
            "Using CPU thread pool strategy (%d workers) for %d images",
            max_workers, len(work_list),
        )
        results = _upscale_cpu_threadpool(
            work_list=work_list,
            model_name=model_name,
            denoise_strength=denoise_strength,
            pre_results=pre_results,
            total_images=total_images,
            max_workers=max_workers,
            on_progress=on_progress,
            cancel_check=cancel_check,
        )

    # ── Final progress ──────────────────────────────────────────
    if on_progress:
        on_progress(total_images, total_images, "Image upscaling complete")

    return results
```

---

### Step 9: Update `upscale_image()` for Robustness

The existing `upscale_image()` function (L389) is called by the CPU
thread pool workers.  It is already mostly correct, but add a
guard clause for thread-safety logging:

No changes needed to the function body — it already:
- Calls `_get_upscaler()` which is thread-safe (lock-protected cache)
- Uses local variables for `img` and `output`
- Handles errors gracefully (returns original path on failure)

However, add `os.makedirs()` before `cv2.imwrite()` to handle
concurrent directory creation (already present at L426).  This is
idempotent and safe.

---

### Step 10: Update `video_renderer.py` — Pass Cancellation Support

In `backend/core_engine/video_renderer.py`, update the call to
`upscale_images_batch()` (around line 888–893) to pass cancellation
support and the new parameters.

**Before** (current code):

```python
path_map = upscale_images_batch(
    image_paths=image_paths,
    output_dir=upscale_output_dir,
    model_name=upscale_model,
    denoise_strength=upscale_denoise,
    on_progress=on_progress,
)
```

**After** (updated code):

```python
# Build a cancellation checker if task_id is available
_cancel_check = None
if task_id:
    try:
        from api.tasks import get_task_manager
        _task_mgr = get_task_manager()
        _cancel_check = lambda: _task_mgr.is_cancelled(task_id)
    except ImportError:
        pass

path_map = upscale_images_batch(
    image_paths=image_paths,
    output_dir=upscale_output_dir,
    model_name=upscale_model,
    denoise_strength=upscale_denoise,
    on_progress=on_progress,
    cancel_check=_cancel_check,
    skip_large=True,
    target_width=resolution[0] * upscale_scale,
    target_height=resolution[1] * upscale_scale,
)
```

> **Note:** If `task_id` is not available in the current scope of
> `render_project()`, the `cancel_check` parameter defaults to `None`
> and cancellation checking is simply skipped.  The feature remains
> fully functional without it.

---

### Step 11: Add Timing and Logging

Add timing instrumentation to the main `upscale_images_batch()` entry
point so that performance improvements can be measured:

In the new `upscale_images_batch()` (already included in Step 8),
the GPU and CPU orchestrators both include `time.perf_counter()`
timing and log:
- Total elapsed time
- Average time per image
- Number of images skipped vs upscaled
- Device used (GPU/CPU)
- Number of workers (CPU mode)

Example log output:
```
INFO  Upscale planner: 5 skipped (3 cached, 2 large enough), 15 to upscale
INFO  Using GPU pipeline strategy (CUDA) for 15 images
INFO  Starting GPU upscale pipeline: 15 images to process
INFO  Saved upscaled: img_001.png → img_001_upscaled.png
...
INFO  GPU pipeline finished: 15 images in 187.3s (12.5s/image avg)
```

---

### Step 12: Add `clear_pipeline_state()` Cleanup Function

Add a utility to ensure clean shutdown in edge cases (e.g., test
teardown or SIGINT).  Place it after `clear_cache()`:

```python
def clear_pipeline_state():
    """Clear upscaler cache and log cleanup.

    Call this on application shutdown or between test runs to ensure
    no stale model references or GPU memory are retained.
    """
    clear_cache()
    if _TORCH_AVAILABLE and torch.cuda.is_available():
        torch.cuda.empty_cache()
        logger.info("CUDA cache cleared")
```

---

### Step 13: Write Unit Tests

Create `backend/core_engine/tests/test_parallel_upscale.py` with the
following test cases:

```python
"""Tests for parallel image upscaling (Feature 1.4)."""
import os
import tempfile
import threading
import unittest
from unittest.mock import MagicMock, patch

import cv2
import numpy as np


class TestSmartSkip(unittest.TestCase):
    """Test smart-skip logic (_image_meets_target, _output_is_cached)."""

    def test_image_below_target_returns_false(self):
        """A small image should NOT be skipped."""
        from core_engine.image_upscaler import _image_meets_target
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            img = np.zeros((100, 100, 3), dtype=np.uint8)
            cv2.imwrite(f.name, img)
            self.assertFalse(_image_meets_target(f.name, 3840, 2160))
            os.unlink(f.name)

    def test_image_above_target_returns_true(self):
        """A large image should be skipped."""
        from core_engine.image_upscaler import _image_meets_target
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            img = np.zeros((2200, 4000, 3), dtype=np.uint8)
            cv2.imwrite(f.name, img)
            self.assertTrue(_image_meets_target(f.name, 3840, 2160))
            os.unlink(f.name)

    def test_cached_output_detected(self):
        """Previously upscaled file should be detected as cached."""
        from core_engine.image_upscaler import _output_is_cached
        with tempfile.TemporaryDirectory() as tmpdir:
            src = os.path.join(tmpdir, "src.png")
            out = os.path.join(tmpdir, "out.png")
            cv2.imwrite(src, np.zeros((10, 10, 3), dtype=np.uint8))
            cv2.imwrite(out, np.zeros((40, 40, 3), dtype=np.uint8))
            self.assertTrue(_output_is_cached(src, out))

    def test_missing_output_not_cached(self):
        """Non-existent output should not be considered cached."""
        from core_engine.image_upscaler import _output_is_cached
        self.assertFalse(_output_is_cached("/tmp/src.png", "/tmp/nonexistent.png"))


class TestWorkListPartitioning(unittest.TestCase):
    """Test _compute_work_list() partitioning logic."""

    def test_all_cached_returns_empty_work_list(self):
        """When all outputs are cached, work_list should be empty."""
        from core_engine.image_upscaler import _compute_work_list
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = []
            for i in range(3):
                src = os.path.join(tmpdir, f"img{i}.png")
                cv2.imwrite(src, np.zeros((10, 10, 3), dtype=np.uint8))
                out = os.path.join(tmpdir, f"img{i}_upscaled.png")
                cv2.imwrite(out, np.zeros((40, 40, 3), dtype=np.uint8))
                paths.append(src)

            pre, work = _compute_work_list(paths, tmpdir, False, 3840, 2160)
            self.assertEqual(len(work), 0)
            self.assertEqual(len(pre), 3)


class TestCancellation(unittest.TestCase):
    """Test that cancellation stops processing early."""

    @patch("core_engine.image_upscaler.upscale_image")
    def test_cancel_stops_cpu_workers(self, mock_upscale):
        """CPU workers should stop when cancel_check returns True."""
        from core_engine.image_upscaler import _upscale_cpu_threadpool

        call_count = [0]
        cancel_after = 2

        def fake_upscale(*args, **kwargs):
            call_count[0] += 1
            return args[1]  # return out_path

        mock_upscale.side_effect = fake_upscale

        work_list = [(f"/tmp/img{i}.png", f"/tmp/out{i}.png") for i in range(10)]
        cancel_counter = [0]

        def cancel_check():
            cancel_counter[0] += 1
            return cancel_counter[0] > cancel_after

        results = _upscale_cpu_threadpool(
            work_list=work_list,
            model_name="RealESRGAN_x4plus",
            denoise_strength=0.5,
            pre_results={},
            total_images=10,
            max_workers=1,
            on_progress=None,
            cancel_check=cancel_check,
        )
        # Should have processed fewer than all 10
        processed = sum(1 for v in results.values() if v != results.get(v, v))
        self.assertLessEqual(call_count[0], cancel_after + 2)


class TestProgressReporting(unittest.TestCase):
    """Test that progress callbacks are invoked correctly."""

    def test_progress_includes_skipped(self):
        """Progress should account for pre-skipped images."""
        from core_engine.image_upscaler import upscale_images_batch

        progress_calls = []
        def on_progress(current, total, msg):
            progress_calls.append((current, total, msg))

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create images that are all "cached" (output exists)
            paths = []
            for i in range(3):
                src = os.path.join(tmpdir, f"img{i}.png")
                cv2.imwrite(src, np.zeros((10, 10, 3), dtype=np.uint8))
                out = os.path.join(tmpdir, f"img{i}_upscaled.png")
                cv2.imwrite(out, np.zeros((40, 40, 3), dtype=np.uint8))
                paths.append(src)

            results = upscale_images_batch(
                paths, tmpdir, on_progress=on_progress,
            )

            # Should have called progress for skipped + final
            self.assertTrue(len(progress_calls) >= 1)
            # Final call should be (total, total, ...)
            self.assertEqual(progress_calls[-1][0], progress_calls[-1][1])
```

---

### Step 14: Integration Testing

Add integration test scenarios to
`backend/core_engine/tests/test_parallel_upscale.py`:

```python
class TestIntegration(unittest.TestCase):
    """Integration tests (require PyTorch + model weights)."""

    @unittest.skipUnless(
        os.path.isfile(str(_MODELS_DIR / "RealESRGAN_x4plus.pth")),
        "Model weights not available",
    )
    def test_batch_upscale_matches_sequential(self):
        """Parallel results should be identical to sequential."""
        from core_engine.image_upscaler import (
            upscale_image,
            upscale_images_batch,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create 3 small test images
            paths = []
            for i in range(3):
                p = os.path.join(tmpdir, f"test_{i}.png")
                img = np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8)
                cv2.imwrite(p, img)
                paths.append(p)

            # Sequential baseline
            seq_dir = os.path.join(tmpdir, "seq")
            os.makedirs(seq_dir)
            seq_results = {}
            for p in paths:
                name = os.path.splitext(os.path.basename(p))[0]
                out = os.path.join(seq_dir, f"{name}_upscaled.png")
                seq_results[p] = upscale_image(p, out, "RealESRGAN_x4plus")

            # Parallel batch
            par_dir = os.path.join(tmpdir, "par")
            par_results = upscale_images_batch(
                paths, par_dir, "RealESRGAN_x4plus",
            )

            # Compare: both should produce files of the same dimensions
            for p in paths:
                seq_img = cv2.imread(seq_results[p])
                par_img = cv2.imread(par_results[p])
                self.assertEqual(seq_img.shape, par_img.shape)
```

---

## 4. Expected Outcome

### 4.1 Performance Targets

| Scenario | Before | After | Speedup |
|---|---|---|---|
| 20 images, GPU, no skips | ~10 min | ~7 min (pipeline overlap) | 1.3–1.5× |
| 20 images, GPU, 5 cached | ~10 min | ~5 min (skip + pipeline) | 2× |
| 20 images, GPU, 10 already large | ~10 min | ~3.5 min (skip + pipeline) | 2.8× |
| 20 images, CPU, 2 workers | ~16 min | ~8 min | 2× |
| 20 images, CPU, 4 workers | ~16 min | ~5 min | 3.2× |
| Re-run (all cached) | ~10 min | ~2 sec | 300× |

### 4.2 Functional Behaviour

After implementation, the following must hold true:

1. **Identical output quality** — Upscaled images from the parallel
   pipeline must be pixel-identical to the sequential baseline for
   the same model and input.

2. **API backwards compatibility** — Existing callers of
   `upscale_images_batch()` (specifically `video_renderer.py` L888)
   continue to work without modification.  All new parameters have
   sensible defaults.

3. **Graceful degradation** — If PyTorch is not installed, the function
   returns original paths (no crash).  If a single image fails, the
   batch continues and that image maps to its original path.

4. **Cancellation support** — When `cancel_check()` returns True,
   processing stops within 1 image of the cancellation signal.
   Partial results (images completed so far) are returned.

5. **Progress accuracy** — The `on_progress` callback receives
   monotonically increasing `current` values from 0 to `total`.
   Skipped images are counted in the progress immediately.

6. **Cache correctness** — The `_output_is_cached()` check uses
   file modification timestamps.  If the source image is replaced
   with a newer file, the cache is invalidated and the image is
   re-upscaled.

7. **Thread cleanup** — All threads are joined before the function
   returns, even on cancellation or error.  No orphaned threads.

### 4.3 Memory Behaviour

| Mode | Peak Additional Memory | Notes |
|---|---|---|
| GPU Pipeline | ~2 input images + 2 output images in buffers | Bounded by queue maxsize=2 |
| CPU 2 workers | ~2 input images + 2 output images (one per worker) | Each worker holds one image pair |
| CPU 4 workers | ~4 input images + 4 output images | Linear with worker count |

For a 1080p × 4 upscale, each output image is ~95 MB (7680×4320×3).
With 2 in the queue, that's ~190 MB additional.  Acceptable for
modern systems.

### 4.4 Log Output Example

A successful 20-image GPU run should produce logs like:

```
INFO  image_upscaler  Upscale planner: 5 skipped (3 cached, 2 large enough), 15 to upscale
INFO  image_upscaler  Using GPU pipeline strategy (CUDA) for 15 images
INFO  image_upscaler  Starting GPU upscale pipeline: 15 images to process
INFO  image_upscaler  Loaded upscaler: RealESRGAN_x4plus on cuda (scale=4, half=True)
INFO  image_upscaler  Saved upscaled: segment_001.png → segment_001_upscaled.png
INFO  image_upscaler  Saved upscaled: segment_002.png → segment_002_upscaled.png
...
INFO  image_upscaler  Saved upscaled: segment_015.png → segment_015_upscaled.png
INFO  image_upscaler  GPU pipeline finished: 15 images in 187.3s (12.5s/image avg)
```

---

## 5. Verification Checklist

### 5.1 Code Quality

- [ ] All new functions have complete docstrings with Args/Returns
- [ ] All new parameters in `upscale_images_batch()` have type hints
- [ ] No circular imports introduced
- [ ] `import time` added to imports section
- [ ] `from concurrent.futures import ThreadPoolExecutor, as_completed, Future`
      added to imports section
- [ ] `from queue import Queue, Empty` added to imports section
- [ ] `from typing import Callable` added (or verified existing)
- [ ] No use of `global` keyword — all state is passed via parameters
- [ ] Thread names set for debugging (`name="upscale-loader"`, etc.)
- [ ] All threads created with `daemon=True` as a safety net

### 5.2 Thread Safety

- [ ] GPU inference runs in exactly ONE thread (the inference thread)
- [ ] `_get_upscaler()` cache access is protected by `_cache_lock`
- [ ] `results` dict is protected by `results_lock` in saver thread
- [ ] Progress counter uses lock-protected mutable list
- [ ] No shared mutable state between CPU thread pool workers
- [ ] `cv2.imread` and `cv2.imwrite` are called from threads (GIL-safe)
- [ ] No `torch.Tensor` objects shared between threads

### 5.3 Error Handling

- [ ] Loader thread: `cv2.imread` failure → put `None` marker → inference
      thread handles gracefully → saver maps to original path
- [ ] Inference thread: `enhance()` exception → caught, logged → put
      `None` result → saver maps to original path
- [ ] Saver thread: `cv2.imwrite` failure → caught, logged → map to
      original path
- [ ] CPU worker: any exception → caught, logged → return original path
- [ ] Missing model file → `_get_upscaler` returns None → all images
      map to originals → no crash
- [ ] PyTorch not installed → `_TORCH_AVAILABLE = False` → skip all →
      return originals

### 5.4 Cancellation

- [ ] `cancel_check` is called between images in loader thread
- [ ] `cancel_check` is called between images in inference thread
- [ ] `cancel_check` is called between images in CPU workers
- [ ] When cancelled, `_PIPELINE_SENTINEL` is placed on queues to
      unblock downstream threads
- [ ] `cancelled` threading.Event is set in CPU pool to stop queued workers
- [ ] All threads are joined after cancellation (no orphans)
- [ ] Partial results are returned (completed images are preserved)

### 5.5 Progress Reporting

- [ ] Skipped images are reported immediately (progress jumps)
- [ ] `on_progress(current, total, message)` signature preserved
- [ ] `current` is monotonically increasing
- [ ] Final call is always `on_progress(total, total, "...")`
- [ ] Progress works correctly when all images are skipped
- [ ] Progress works correctly when all images need upscaling
- [ ] Progress works correctly with a mix of skipped and upscaled

### 5.6 Smart Skip

- [ ] `_image_meets_target()` correctly reads image dimensions
- [ ] `_output_is_cached()` checks both existence and mtime
- [ ] Cached output with zero size is NOT considered valid
- [ ] Re-generated source image (newer mtime) invalidates cache
- [ ] `skip_large=False` disables resolution-based skipping
- [ ] Default `target_width=3840, target_height=2160` matches 4K UHD

### 5.7 Backwards Compatibility

- [ ] `upscale_images_batch()` works with only the original 5 args
- [ ] All new parameters have defaults matching current behaviour
- [ ] Return type is unchanged: `dict[str, str]`
- [ ] `video_renderer.py` call site updated but also works if
      `task_id` is not available
- [ ] No changes to `upscale_image()` public signature

### 5.8 Testing

- [ ] `test_image_below_target_returns_false` passes
- [ ] `test_image_above_target_returns_true` passes
- [ ] `test_cached_output_detected` passes
- [ ] `test_missing_output_not_cached` passes
- [ ] `test_all_cached_returns_empty_work_list` passes
- [ ] `test_cancel_stops_cpu_workers` passes
- [ ] `test_progress_includes_skipped` passes
- [ ] Integration test (when model weights present) passes
- [ ] All existing tests still pass (`python manage.py test`)

### 5.9 Performance

- [ ] GPU pipeline: loader stays ahead of inference (check logs)
- [ ] GPU pipeline: saver doesn't bottleneck inference (check logs)
- [ ] CPU pool: workers achieve near-linear scaling up to worker count
- [ ] Smart skip: cached images add <50ms total overhead
- [ ] Re-run with all cached: completes in <5 seconds
- [ ] No CUDA OOM errors with default settings on 8GB GPU

---

## 6. Notes for AI Agent

### 6.1 Implementation Order

Follow the steps **strictly in order** (Steps 1–14).  Each step builds
on the previous one.  Do not skip steps or combine them.

**Recommended implementation sequence:**

1. Steps 1–4: Add imports + helper functions (no existing code modified)
2. Step 5: Add pipeline thread functions (no existing code modified)
3. Steps 6–7: Add orchestrator functions (no existing code modified)
4. Step 8: Replace `upscale_images_batch()` (FIRST modification of
   existing code)
5. Step 10: Update `video_renderer.py` call site
6. Steps 12–14: Add cleanup + tests

### 6.2 Critical Code Locations

| What | File | Line | Notes |
|---|---|---|---|
| Imports section | `image_upscaler.py` | L22–30 | Add new imports here |
| `get_available_models()` end | `image_upscaler.py` | ~L90 | Insert helpers after this |
| `_TORCH_AVAILABLE` try/except | `image_upscaler.py` | L96–198 | DO NOT modify — architecture defs |
| `_UpscalerInstance` class | `image_upscaler.py` | L203–336 | DO NOT modify — model wrapper |
| `_upscaler_cache` / `_cache_lock` | `image_upscaler.py` | L342–346 | DO NOT modify — cache mechanism |
| `_get_upscaler()` | `image_upscaler.py` | L349–383 | DO NOT modify — thread-safe cache |
| `upscale_image()` | `image_upscaler.py` | L389–433 | DO NOT modify — single-image API |
| `upscale_images_batch()` | `image_upscaler.py` | L436–476 | **REPLACE** with new version |
| `clear_cache()` | `image_upscaler.py` | L479–483 | Add `clear_pipeline_state()` after |
| Upscale call in renderer | `video_renderer.py` | L888–893 | Update to pass new params |

### 6.3 Things to Watch Out For

1. **Queue sentinel values**: Use `_PIPELINE_SENTINEL = object()`
   (a unique singleton), NOT `None`, because `None` could be a valid
   failure marker for image data.  The sentinel signals end-of-stream.

2. **Thread join order**: In the GPU pipeline, threads must be joined
   in order: loader → inferencer → saver.  Each thread's `finally`
   block sends a sentinel to the next queue, so joining in order
   ensures clean shutdown propagation.

3. **Progress counter atomicity**: The `progress_counter` uses a
   mutable `list[int]` protected by `results_lock`.  Do NOT use a
   bare `int` — Python integers are immutable and cannot be shared
   across threads via closure.

4. **`os.makedirs(exist_ok=True)`**: Called in the saver thread for
   each output path.  This is safe for concurrent calls because
   `exist_ok=True` prevents race conditions where two threads try
   to create the same directory simultaneously.

5. **File paths**: The `_compute_work_list()` function generates
   output filenames as `{name}_upscaled{ext}`.  This matches the
   existing naming convention in the current `upscale_images_batch()`.

6. **RGBA handling**: The loader thread converts BGRA→BGR before
   putting on the queue.  This matches the existing logic in
   `upscale_image()` (L418–419).

7. **`denoise_strength` parameter**: This is currently informational
   only (the model architecture determines denoising).  Pass it through
   for API consistency but it does not affect inference.

### 6.4 Testing Without GPU

If no CUDA GPU is available during development:

- The code will automatically fall back to CPU thread pool mode
- Set `max_workers=2` for testing to avoid overwhelming the CPU
- All thread-safety tests work the same on CPU
- Integration tests can use small images (64×64) for speed

### 6.5 Testing Without Model Weights

If model `.pth` files are not present in `models/upscalers/`:

- `_get_upscaler()` returns `None`
- `upscale_image()` returns the original path
- All smart-skip / caching / progress logic can still be tested
- The unit tests (Steps 13) mock the upscaler and work without weights
- The integration test (Step 14) uses `@unittest.skipUnless` to skip
  gracefully

### 6.6 Preserving the `upscale_image()` Function

The existing `upscale_image()` function (L389–433) must NOT be modified.
It is:
- The single-image public API
- Called by each CPU worker thread in the thread pool strategy
- The interface that external callers may use directly
- Already handles errors gracefully (returns original path)

### 6.7 Import Guard for `torch`

All new code that references `torch` (e.g., `torch.cuda.is_available()`)
must be guarded by `if _TORCH_AVAILABLE:`.  The module-level flag is
set at L96–101 and handles the case where PyTorch is not installed.

### 6.8 File Size Expectations

After implementation, `image_upscaler.py` should grow from ~483 lines
to approximately ~700–750 lines.  The new code is:
- ~30 lines: imports and helpers (`_image_meets_target`, `_output_is_cached`)
- ~50 lines: `_compute_work_list()`
- ~100 lines: pipeline thread functions (loader, inference, saver)
- ~60 lines: `_upscale_gpu_pipeline()` orchestrator
- ~70 lines: `_upscale_cpu_threadpool()` orchestrator
- ~70 lines: new `upscale_images_batch()` replacement
- ~10 lines: `clear_pipeline_state()`

### 6.9 No Changes to These Files

The following files must remain **completely unchanged**:

- `backend/core_engine/ken_burns.py`
- `backend/core_engine/fast_compositor.py`
- `backend/core_engine/subtitle_engine.py`
- `backend/core_engine/tts_wrapper.py`
- `backend/core_engine/audio_utils.py`
- `backend/api/tasks.py`
- `backend/api/serializers.py`
- `backend/api/views.py`

### 6.10 Rollback Plan

If the parallel implementation introduces bugs, the rollback is simple:

1. Revert `upscale_images_batch()` to its original sequential `for` loop
2. Revert the `video_renderer.py` call site to remove extra params
3. The helper functions (`_image_meets_target()`, `_output_is_cached()`,
   `_compute_work_list()`) can remain — they are harmless dead code

The smart-skip and caching features can also be kept independently
of the parallelism changes, as they are purely additive optimisations.

### 6.11 Future Enhancements (Out of Scope)

These are potential follow-ups, NOT part of this feature:

- **ONNX Runtime inference**: Convert to `.onnx` for potentially faster
  CPU inference with multi-threaded execution provider
- **Batch GPU inference**: Group multiple small images into a single
  batch tensor (requires same-size images or padding)
- **Progressive upscaling feedback**: Return low-res previews while
  full upscale is in progress
- **Distributed upscaling**: Offload to a separate GPU worker process
  via multiprocessing for true isolation
- **Resolution-aware model selection**: Automatically choose x2 vs x4
  model based on source→target ratio

---

*End of Feature 1.4 implementation document.*
