# Feature 1.1 — Multi-Threaded Frame Generation

> **Status:** Planned  
> **Category:** Core Engine / Rendering Performance  
> **Target File:** `backend/core_engine/fast_compositor.py`  
> **Estimated Complexity:** Medium  
> **Expected Speedup:** 2–4× on multi-core CPUs  
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
renders every frame sequentially in a single thread.  The main frame
loop lives in **Phase 4** (lines 663–766) and performs these operations
for each frame:

1. Iterate over active segments and compute Ken Burns crop position
   via `interpolate_position()`.
2. Crop the source image with NumPy slicing and resize with
   `cv2.resize()`.
3. Apply subtitle overlays via `alpha_blit()`.
4. Accumulate crossfade weights into a float32 blending buffer.
5. Normalize the blended result and apply the logo overlay.
6. Write the finished uint8 frame to FFmpeg via
   `FFmpegFrameWriter.write_frame()` (line 475).

Steps 1–5 are **CPU-bound** and independent for each frame (they only
read from shared, immutable segment data).  Step 6 is **I/O-bound**
(pipe write to an FFmpeg subprocess).  Because everything runs on a
single thread, the CPU cannot generate frame N+1 while FFmpeg is
consuming frame N.  On a modern 4–8 core machine, this leaves the
majority of cores idle during the entire render.

### 1.2 Proposed Solution

Replace the single-threaded frame loop with a **producer/consumer
pipeline**:

| Component | Count | Role |
|---|---|---|
| **Frame producer threads** | N (configurable, default `os.cpu_count() - 1` clamped to 2–6) | Each thread picks frame indices from a shared counter, generates the composited frame, and puts `(frame_idx, frame_bytes)` into a bounded queue. |
| **Writer thread** | 1 | Pulls frames from the queue **in order** and writes them to the FFmpeg pipe. Handles progress reporting. |

Key design constraints:

- **Strict frame ordering** — FFmpeg expects frames in sequential
  order.  The writer thread must reorder frames that arrive
  out-of-sequence.
- **Bounded queue** — prevents runaway memory usage when producers
  are faster than the writer can flush to FFmpeg.
- **GIL considerations** — `cv2.resize()` and large NumPy operations
  release the GIL, so Python threads provide real parallelism for the
  heavy operations.  Lightweight Python bookkeeping (loop overhead,
  dict lookups) remains GIL-serialized but is negligible.
- **Thread-safe progress** — the `on_progress` callback and any
  cancellation checks must use atomic counters or locks.
- **Zero changes to the public API** — `fast_render_segments()`
  keeps the same signature and return value.  Callers
  (`video_renderer.py` line 1047, `tasks.py` line 415) are unaffected.

### 1.3 Files Involved

| File | Role | Changes |
|---|---|---|
| `backend/core_engine/fast_compositor.py` | Main implementation | Add threading pipeline, refactor Phase 4 |
| `backend/core_engine/video_renderer.py` | Calls `fast_render_segments()` at L1047–1063 | **No changes** (API unchanged) |
| `backend/api/tasks.py` | Provides `on_progress` callback at L371 | **No changes** |
| `backend/core_engine/ken_burns.py` | Provides `interpolate_position()`, etc. | **No changes** (all functions are stateless, thread-safe) |
| `backend/core_engine/tests/` | Unit/integration tests | Add new test file for threaded rendering |

### 1.4 Key Existing Functions Reference

| Function | Location | Thread-Safe? |
|---|---|---|
| `alpha_blit(frame, overlay)` | `fast_compositor.py` L68 | Yes — operates on local frame arrays |
| `pre_render_subtitles()` | `fast_compositor.py` L113 | Yes — called once before threading starts |
| `pre_render_logo()` | `fast_compositor.py` L299 | Yes — called once before threading starts |
| `FFmpegFrameWriter` class | `fast_compositor.py` L365 | **No** — `write_frame()` writes to a single pipe; must be called from one thread only |
| `fast_render_segments()` | `fast_compositor.py` L487 | Outer function — not called concurrently |
| `interpolate_position()` | `ken_burns.py` | Yes — pure math, no shared state |
| `load_and_prepare_image()` | `ken_burns.py` | Yes — returns new array |
| `calculate_crop_dimensions()` | `ken_burns.py` | Yes — pure math |
| `get_pan_direction()` | `ken_burns.py` | Yes — pure lookup |
| `get_start_end_coords()` | `ken_burns.py` | Yes — pure math |

---

## 2. Flow Diagram

### 2.1 Current Architecture (Single-Threaded)

```
┌─────────────────────────────────────────────────────────┐
│                  Main Thread                            │
│                                                         │
│  Phase 1: Pre-render overlays (subtitles, logo)         │
│  Phase 2: Calculate timeline & frame ranges             │
│  Phase 3: Start FFmpeg writer                           │
│  Phase 4: ┌──────────────────────────────────────┐      │
│           │  for frame_idx in range(total_frames):│      │
│           │    compute Ken Burns crop             │      │
│           │    cv2.resize()                       │      │
│           │    alpha_blit() subtitles             │      │
│           │    crossfade blend                    │      │
│           │    alpha_blit() logo                  │      │
│           │    writer.write_frame(frame)  ───────►│ FFmpeg│
│           └──────────────────────────────────────┘      │
│  Phase 5: writer.finish()                               │
└─────────────────────────────────────────────────────────┘
```

### 2.2 Proposed Architecture (Multi-Threaded)

```
                    ┌──────────────────────┐
                    │   AtomicFrameCounter  │
                    │  next_idx = 0         │
                    │  lock = Lock()        │
                    └──────────┬───────────┘
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                     │
          ▼                    ▼                     ▼
 ┌─────────────────┐ ┌─────────────────┐  ┌─────────────────┐
 │ Producer Thread 0│ │ Producer Thread 1│  │ Producer Thread N│
 │                  │ │                  │  │                  │
 │ loop:            │ │ loop:            │  │ loop:            │
 │  idx = counter() │ │  idx = counter() │  │  idx = counter() │
 │  if idx >= total │ │  if idx >= total │  │  if idx >= total │
 │    break         │ │    break         │  │    break         │
 │  frame = gen(idx)│ │  frame = gen(idx)│  │  frame = gen(idx)│
 │  queue.put(      │ │  queue.put(      │  │  queue.put(      │
 │   (idx, bytes))  │ │   (idx, bytes))  │  │   (idx, bytes))  │
 └────────┬─────────┘ └────────┬─────────┘  └────────┬─────────┘
          │                    │                      │
          ▼                    ▼                      ▼
 ┌────────────────────────────────────────────────────────────┐
 │              Bounded Queue (maxsize = N * 2)               │
 │                                                            │
 │   Holds (frame_idx, frame_bytes) tuples                    │
 │   Blocks producers when full (backpressure)                │
 └────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
                 ┌─────────────────────────┐
                 │     Writer Thread        │
                 │                          │
                 │  reorder_buffer = {}     │
                 │  next_write_idx = 0      │
                 │                          │
                 │  loop:                   │
                 │   (idx, data) = queue.get│
                 │   if idx == SENTINEL:    │
                 │     break                │
                 │   reorder_buffer[idx]    │
                 │     = data               │
                 │   while next_write_idx   │
                 │     in reorder_buffer:   │
                 │    writer.write_frame()  │──► FFmpeg stdin
                 │    next_write_idx += 1   │
                 │    update progress       │
                 └─────────────────────────┘
```

### 2.3 Detailed Queue Interaction

```
Timeline (frame indices):

Producer-0:  [0]────[3]────[6]────[9]───...
Producer-1:  [1]────[4]────[7]────[10]──...
Producer-2:  [2]────[5]────[8]────[11]──...
                │      │      │
                ▼      ▼      ▼
Queue:       (0,d) (1,d) (2,d) (3,d) (5,d) (4,d) ...
                │
                ▼
Writer:      write(0) → write(1) → write(2) → write(3) → buffer(5)
             → write(4) arrives → write(4) → write(5) → ...

Note: Frame 5 arrived before frame 4.  The writer buffers frame 5
and waits until frame 4 arrives before writing both in order.
```

### 2.4 Shutdown Sequence

```
  Producers finish all frames
            │
            ▼
  Each producer exits its loop
            │
            ▼
  Main thread joins all producers
            │
            ▼
  Main thread puts SENTINEL on queue
            │
            ▼
  Writer thread sees SENTINEL → exits loop
            │
            ▼
  Main thread joins writer thread
            │
            ▼
  writer.finish() → close FFmpeg pipe
```

---

## 3. Step-by-Step Instructions

### Step 1: Add Imports

At the top of `backend/core_engine/fast_compositor.py` (after line 33),
add the threading and queue imports:

```python
import threading
from queue import Queue
```

These are stdlib modules — no new dependencies required.

---

### Step 2: Create the `_generate_single_frame()` Helper

Extract the per-frame logic currently inside the Phase 4 `for` loop
(lines 663–753) into a standalone function.  Place it **above**
`fast_render_segments()`, around line 480.

```python
def _generate_single_frame(
    frame_idx: int,
    fps: int,
    width: int,
    height: int,
    segment_frame_ranges: List[Tuple[int, int]],
    segments_info: List[dict],
    total_segments: int,
    crossfade_duration: float,
    logo_overlay: Optional[OverlaySlice],
    interpolate_position_fn,
) -> bytes:
    """Generate a single composited frame and return it as raw bytes.

    This function is designed to be called from multiple threads
    concurrently.  It only reads from shared, immutable data structures
    (segment_frame_ranges, segments_info, logo_overlay) and allocates
    all mutable buffers locally on the stack.

    Args:
        frame_idx: Zero-based index of the frame to generate.
        fps: Frames per second.
        width: Output frame width.
        height: Output frame height.
        segment_frame_ranges: List of (start_frame, end_frame) tuples.
        segments_info: Pre-computed segment descriptors.
        total_segments: Number of segments.
        crossfade_duration: Crossfade duration in seconds.
        logo_overlay: Pre-rendered logo overlay (or None).
        interpolate_position_fn: Reference to ken_burns.interpolate_position.

    Returns:
        Raw RGB bytes (length = width * height * 3) for this frame.
    """
    t_global = frame_idx / fps

    frame = np.zeros((height, width, 3), dtype=np.uint8)
    total_weight = 0.0
    blended_float = np.zeros((height, width, 3), dtype=np.float32)

    for seg_idx, (seg_start_frame, seg_end_frame) in enumerate(segment_frame_ranges):
        if frame_idx < seg_start_frame or frame_idx >= seg_end_frame:
            continue

        si = segments_info[seg_idx]
        seg_duration = si["visual_duration"]
        t_local = (frame_idx - seg_start_frame) / fps

        # Compute crossfade weight
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

        # Ken Burns crop
        interp_x, interp_y = interpolate_position_fn(
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

        is_downscale = (si["crop_w"] > width or si["crop_h"] > height)
        interp = cv2.INTER_AREA if is_downscale else cv2.INTER_LINEAR
        seg_frame = cv2.resize(crop, (width, height), interpolation=interp)

        # Subtitle overlays
        for overlay in si["subtitle_overlays"]:
            if overlay.start_time <= t_local < overlay.end_time:
                alpha_blit(seg_frame, overlay)

        # Crossfade accumulation
        blended_float += seg_frame.astype(np.float32) * weight
        total_weight += weight

    # Normalize
    if total_weight > 0:
        frame = np.clip(blended_float / total_weight, 0, 255).astype(np.uint8)

    # Logo
    if logo_overlay:
        alpha_blit(frame, logo_overlay)

    return frame.tobytes()
```

**Why `.tobytes()`?**  Returning raw bytes instead of an ndarray avoids
accidental shared-memory bugs and makes the data trivially picklable.
It also matches what `FFmpegFrameWriter.write_frame()` does internally
(`frame.tobytes()`), so we can later write bytes directly to the pipe
without the extra conversion.

---

### Step 3: Add `.write_frame_bytes()` to `FFmpegFrameWriter`

Add a new method to the `FFmpegFrameWriter` class (after
`write_frame()`, around line 478) that accepts pre-serialized bytes
instead of an ndarray.  This avoids a redundant `.tobytes()` call in
the writer thread.

```python
def write_frame_bytes(self, data: bytes) -> None:
    """Write pre-serialized raw RGB frame bytes to FFmpeg's stdin."""
    if self._proc is None or self._proc.stdin is None:
        raise RuntimeError("FFmpeg process not started")
    self._proc.stdin.write(data)
```

---

### Step 4: Create the `_frame_producer_worker()` Function

This is the target function for each producer thread.  Place it right
after `_generate_single_frame()`.

```python
_SENTINEL = None  # Sentinel value signalling "no more frames"


def _frame_producer_worker(
    thread_id: int,
    frame_counter: "AtomicCounter",
    total_frames: int,
    output_queue: "Queue[Optional[Tuple[int, bytes]]]",
    generate_kwargs: dict,
) -> None:
    """Worker function for frame-producer threads.

    Continuously fetches the next unprocessed frame index from
    *frame_counter*, generates the frame, and puts it on the queue.
    Exits when all frames have been claimed.

    Args:
        thread_id: Numeric ID for logging.
        frame_counter: Shared atomic counter for frame indices.
        total_frames: Total number of frames to render.
        output_queue: Bounded queue for (frame_idx, frame_bytes) tuples.
        generate_kwargs: Keyword arguments forwarded to
            ``_generate_single_frame()``.
    """
    generated = 0
    try:
        while True:
            idx = frame_counter.get_next()
            if idx >= total_frames:
                break
            data = _generate_single_frame(frame_idx=idx, **generate_kwargs)
            output_queue.put((idx, data))
            generated += 1
    except Exception:
        logger.exception("Producer thread %d crashed", thread_id)
        raise
    finally:
        logger.debug(
            "Producer thread %d finished (%d frames generated)",
            thread_id, generated,
        )
```

---

### Step 5: Create the `_frame_writer_worker()` Function

This is the target function for the single writer thread.  Place it
directly after `_frame_producer_worker()`.

```python
def _frame_writer_worker(
    writer: FFmpegFrameWriter,
    output_queue: "Queue[Optional[Tuple[int, bytes]]]",
    total_frames: int,
    render_start: float,
    on_progress: Optional[Callable[[int, int, str], None]],
    num_producers: int,
) -> None:
    """Writer thread: dequeue frames in order and pipe to FFmpeg.

    Maintains a reorder buffer to handle out-of-order arrivals from
    the producer pool.  Writes frames to FFmpeg sequentially as soon
    as the next expected frame index is available.

    Args:
        writer: The started ``FFmpegFrameWriter`` instance.
        output_queue: Shared queue from which to read
            ``(frame_idx, frame_bytes)`` tuples.
        total_frames: Total number of frames expected.
        render_start: ``time.perf_counter()`` timestamp of render start.
        on_progress: Optional progress callback.
        num_producers: Number of producer threads (used to count
            sentinel values).
    """
    reorder_buffer: dict[int, bytes] = {}
    next_write_idx = 0
    last_progress_pct = 5
    sentinels_received = 0

    while next_write_idx < total_frames:
        item = output_queue.get()

        # Sentinel check — producers send None when done
        if item is _SENTINEL:
            sentinels_received += 1
            if sentinels_received >= num_producers:
                # All producers done but we haven't written all frames.
                # This means an error occurred — break and let finish()
                # handle it.
                break
            continue

        idx, data = item
        reorder_buffer[idx] = data

        # Flush as many consecutive frames as possible
        while next_write_idx in reorder_buffer:
            writer.write_frame_bytes(reorder_buffer.pop(next_write_idx))
            next_write_idx += 1

            # Progress reporting (same throttling as original)
            pct = 5 + int((next_write_idx / total_frames) * 90)
            if pct > last_progress_pct and pct <= 95:
                last_progress_pct = pct
                elapsed = time.perf_counter() - render_start
                fps_actual = next_write_idx / elapsed if elapsed > 0 else 0
                remaining = (
                    (total_frames - next_write_idx) / fps_actual
                    if fps_actual > 0 else 0
                )
                if on_progress:
                    on_progress(
                        pct, 100,
                        f"Rendering frames… {next_write_idx}/{total_frames} "
                        f"({fps_actual:.0f} fps, ~{remaining:.0f}s remaining)",
                    )

    logger.debug(
        "Writer thread finished: %d frames written, %d leftover in buffer",
        next_write_idx, len(reorder_buffer),
    )
```

---

### Step 6: Create the `AtomicCounter` Class

A minimal thread-safe counter for distributing frame indices to
producers.  Place it near the top of the file, after the
`OverlaySlice` dataclass (around line 66).

```python
class AtomicCounter:
    """Thread-safe incrementing counter.

    Used to distribute frame indices to producer threads without
    overlap or gaps.
    """

    def __init__(self, initial: int = 0) -> None:
        self._value = initial
        self._lock = threading.Lock()

    def get_next(self) -> int:
        """Atomically return the current value and increment by one."""
        with self._lock:
            val = self._value
            self._value += 1
            return val
```

---

### Step 7: Add `num_workers` Parameter to `fast_render_segments()`

Extend the function signature (line 487) with an optional parameter:

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
    num_workers: Optional[int] = None,  # ← NEW
) -> dict:
```

Add worker count resolution at the beginning of the function body
(just after the existing local variable setup, before Phase 1):

```python
    # Resolve worker count
    if num_workers is None:
        cpu_count = os.cpu_count() or 4
        num_workers = max(2, min(cpu_count - 1, 6))
    num_workers = max(1, num_workers)  # floor at 1

    logger.info("Multi-threaded render: %d producer threads", num_workers)
```

**Rationale for the default:**
- Reserve 1 core for the writer thread + FFmpeg.
- Cap at 6 producers to avoid memory explosion (each thread holds
  ≥1 full frame in flight — at 1080p that's ~6 MB per frame).
- Floor at 2 to guarantee some parallelism.

---

### Step 8: Replace Phase 4 With the Threading Pipeline

This is the main change.  Replace the **entire** Phase 4 block
(lines 663–766 — from the `render_start = time.perf_counter()` line
through the progress reporting block, but NOT Phase 5) with the
threaded pipeline.

**New Phase 4 code:**

```python
    # ------------------------------------------------------------------
    # Phase 4: Multi-threaded frame generation + ordered writing
    # ------------------------------------------------------------------
    render_start = time.perf_counter()

    # Import interpolate_position reference for thread workers
    # (already imported at top of this function in Phase 1)
    # We pass it explicitly to avoid thread-local import issues.

    generate_kwargs = {
        "fps": fps,
        "width": width,
        "height": height,
        "segment_frame_ranges": segment_frame_ranges,
        "segments_info": segments_info,
        "total_segments": total_segments,
        "crossfade_duration": crossfade_duration,
        "logo_overlay": logo_overlay,
        "interpolate_position_fn": interpolate_position,
    }

    # Bounded queue: N*2 slots provides enough buffer for producers
    # to stay ahead without consuming excessive memory.
    queue_size = num_workers * 2
    frame_queue: Queue[Optional[Tuple[int, bytes]]] = Queue(maxsize=queue_size)
    frame_counter = AtomicCounter(0)

    # --- Start writer thread ---
    writer_thread = threading.Thread(
        target=_frame_writer_worker,
        args=(
            writer,
            frame_queue,
            total_frames,
            render_start,
            on_progress,
            num_workers,
        ),
        name="frame-writer",
        daemon=True,
    )
    writer_thread.start()

    # --- Start producer threads ---
    producer_threads: List[threading.Thread] = []
    producer_error: Optional[Exception] = None
    producer_error_lock = threading.Lock()

    def _safe_producer(tid, counter, total, queue, kwargs):
        """Wrapper that captures exceptions for the main thread."""
        nonlocal producer_error
        try:
            _frame_producer_worker(tid, counter, total, queue, kwargs)
        except Exception as exc:
            with producer_error_lock:
                if producer_error is None:
                    producer_error = exc

    for tid in range(num_workers):
        t = threading.Thread(
            target=_safe_producer,
            args=(tid, frame_counter, total_frames, frame_queue, generate_kwargs),
            name=f"frame-producer-{tid}",
            daemon=True,
        )
        t.start()
        producer_threads.append(t)

    # --- Wait for producers to finish ---
    for t in producer_threads:
        t.join()

    # Signal writer to finish (one sentinel per producer for safety,
    # but we only strictly need one after all producers are joined).
    frame_queue.put(_SENTINEL)

    # --- Wait for writer to finish ---
    writer_thread.join()

    # --- Check for errors ---
    if producer_error is not None:
        logger.error("Producer thread error: %s", producer_error)
        raise RuntimeError(
            f"Frame generation failed: {producer_error}"
        ) from producer_error
```

**Key points:**

1. The main thread starts all threads, then joins producers first
   (ensuring all frames are generated), then sends the sentinel,
   then joins the writer (ensuring all frames are written).
2. If a producer crashes, the error is captured and re-raised on the
   main thread after cleanup.
3. Daemon threads ensure the process won't hang if the main thread
   is killed.

---

### Step 9: Handle Cancellation in Producers

The `on_progress` callback in `tasks.py` (line 371) raises a
`RenderCancelled` exception when the user cancels.  In the current
single-threaded design this propagates naturally.  With threading we
need a cooperative cancellation flag.

Add a `threading.Event` for cancellation:

```python
    # In Phase 4 setup, before starting threads:
    cancel_event = threading.Event()
```

Modify `_frame_producer_worker()` to accept and check it:

```python
def _frame_producer_worker(
    thread_id: int,
    frame_counter: "AtomicCounter",
    total_frames: int,
    output_queue: "Queue[Optional[Tuple[int, bytes]]]",
    generate_kwargs: dict,
    cancel_event: Optional[threading.Event] = None,
) -> None:
    generated = 0
    try:
        while True:
            if cancel_event and cancel_event.is_set():
                break
            idx = frame_counter.get_next()
            if idx >= total_frames:
                break
            data = _generate_single_frame(frame_idx=idx, **generate_kwargs)
            output_queue.put((idx, data))
            generated += 1
    except Exception:
        logger.exception("Producer thread %d crashed", thread_id)
        raise
    finally:
        logger.debug(
            "Producer thread %d finished (%d frames generated)",
            thread_id, generated,
        )
```

Wrap the `on_progress` call in the writer thread to catch cancellation
and set the event:

```python
    # Inside _frame_writer_worker, wrap the on_progress call:
    if on_progress:
        try:
            on_progress(
                pct, 100,
                f"Rendering frames… {next_write_idx}/{total_frames} "
                f"({fps_actual:.0f} fps, ~{remaining:.0f}s remaining)",
            )
        except Exception:
            # Cancellation or other error — signal producers to stop
            if cancel_event:
                cancel_event.set()
            raise
```

Pass `cancel_event` through from Phase 4 into both worker functions
(add it to `_safe_producer` args and `_frame_writer_worker` args).

---

### Step 10: Memory Safety — Ensure Shared Data Is Read-Only

Verify that the data shared across threads is never mutated:

| Shared Object | Thread Access | Mutable? | Safe? |
|---|---|---|---|
| `segments_info` (list of dicts) | Read by all producers | **No** — built in Phase 1, never modified after | ✅ |
| `segments_info[i]["source_image"]` (ndarray) | Read (NumPy slicing) | **No** — slicing creates a view, pixel data not modified | ✅ |
| `segments_info[i]["subtitle_overlays"]` | Read by producers | **No** — pre-rendered in Phase 1 | ✅ |
| `logo_overlay` | Read by all producers | **No** — pre-rendered, never modified | ✅ |
| `segment_frame_ranges` (list of tuples) | Read by all producers | **No** — built in Phase 2 | ✅ |
| `frame_counter` | Read + write (via lock) | **Yes** — protected by `AtomicCounter._lock` | ✅ |
| `frame_queue` | Put by producers, get by writer | **Yes** — `queue.Queue` is thread-safe | ✅ |
| `writer` | `write_frame_bytes()` by writer thread only | **Yes** — single writer thread | ✅ |

**IMPORTANT:** `alpha_blit()` modifies `frame` **in-place**.  Each
producer allocates its own `frame` and `seg_frame` arrays locally
inside `_generate_single_frame()`, so there is no cross-thread
mutation.  The shared `subtitle_overlays` and `logo_overlay` are only
**read** (their `.rgb` and `.alpha` arrays are source operands).
This is confirmed by inspecting `alpha_blit()` at line 68 — it reads
`overlay.rgb` and `overlay.alpha` but only writes to `frame`.

---

### Step 11: Fallback to Single-Threaded Mode

For debugging and backwards compatibility, add a single-threaded
fallback when `num_workers == 1`:

```python
    if num_workers == 1:
        # Single-threaded fallback — original behavior
        render_start = time.perf_counter()
        last_progress_pct = 5

        for frame_idx in range(total_frames):
            data = _generate_single_frame(frame_idx=frame_idx, **generate_kwargs)
            writer.write_frame_bytes(data)

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
                        f"({fps_actual:.0f} fps, ~{remaining:.0f}s remaining)",
                    )
    else:
        # Multi-threaded pipeline (Phase 4 code from Step 8)
        ...
```

---

### Step 12: Update Logging

Add structured logging around the thread pool lifecycle so render
times can be compared before/after:

```python
    logger.info(
        "Fast render complete: %d frames in %.1fs (%.1f ms/frame, %.1f fps) "
        "[%d producer threads]",
        total_frames, render_time, avg_ms,
        total_frames / render_time if render_time > 0 else 0,
        num_workers,
    )
```

---

### Step 13: Write Tests

Create `backend/core_engine/tests/test_threaded_render.py`:

```python
"""Tests for multi-threaded frame generation pipeline."""

import threading
import time
from queue import Queue
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from core_engine.fast_compositor import (
    AtomicCounter,
    _generate_single_frame,
    _frame_producer_worker,
    _frame_writer_worker,
    _SENTINEL,
)


class TestAtomicCounter:
    """Verify AtomicCounter is race-free."""

    def test_sequential_counting(self):
        c = AtomicCounter(0)
        assert c.get_next() == 0
        assert c.get_next() == 1
        assert c.get_next() == 2

    def test_concurrent_counting(self):
        """Spawn 8 threads each grabbing 1000 indices.
        All 8000 indices should appear exactly once."""
        c = AtomicCounter(0)
        results = [[] for _ in range(8)]

        def grab(tid):
            for _ in range(1000):
                results[tid].append(c.get_next())

        threads = [threading.Thread(target=grab, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        all_indices = sorted(v for r in results for v in r)
        assert all_indices == list(range(8000))


class TestFrameOrdering:
    """Verify writer reorders out-of-sequence frames."""

    def test_out_of_order_arrival(self):
        """Frames arrive as 2,0,1 but must be written as 0,1,2."""
        written = []

        mock_writer = MagicMock()
        mock_writer.write_frame_bytes.side_effect = (
            lambda data: written.append(data)
        )

        q: Queue = Queue()
        # Simulate out-of-order arrival
        q.put((2, b"frame2"))
        q.put((0, b"frame0"))
        q.put((1, b"frame1"))
        q.put(_SENTINEL)

        _frame_writer_worker(
            writer=mock_writer,
            output_queue=q,
            total_frames=3,
            render_start=time.perf_counter(),
            on_progress=None,
            num_producers=1,
        )

        assert written == [b"frame0", b"frame1", b"frame2"]
```

---

## 4. Expected Outcome

### 4.1 Performance

| Metric | Before (single-threaded) | After (4 workers) | Notes |
|---|---|---|---|
| CPU utilization | ~25% (1 of 4 cores) | ~80–95% (all cores busy) | Measured via `htop` or Task Manager |
| Frame rate (1080p, 5 segments) | ~80–120 fps | ~250–400 fps | Depends on image resolution and overlay count |
| Render time (60s video @ 30fps = 1800 frames) | ~15–22s | ~5–8s | 2–4× faster |
| Memory overhead | ~50 MB (one frame buffer) | ~150 MB (queue + reorder buffer + per-thread frames) | Bounded by queue maxsize |
| FFmpeg pipe utilization | Bursty (idle between frames) | Near-continuous (queue keeps it fed) | Writer thread drains smoothly |

### 4.2 Correctness

- **Bit-identical output:** When `num_workers=1` (single-threaded
  fallback), the output must be byte-for-byte identical to the
  current implementation.
- **Frame ordering:** The FFmpeg stdin stream must receive frames in
  strictly ascending index order regardless of how many threads are
  generating frames.
- **Deterministic output:** For a given `num_workers`, the output
  video must be identical across runs (no race-dependent visual
  artifacts).

### 4.3 API Compatibility

- `fast_render_segments()` signature gains one optional kwarg
  (`num_workers`).  The default (`None` → auto-detect) preserves
  backward compatibility.
- Return value (`dict` with `frames_rendered`, `render_time`,
  `avg_ms_per_frame`) is unchanged.
- Callers in `video_renderer.py` (L1047) and `tasks.py` (L415)
  require **zero changes**.
- Progress callback behavior is identical (same percentage ranges,
  same message format, same throttling).

### 4.4 Error Handling

- If any producer thread crashes, the error is captured and re-raised
  on the main thread with full traceback.
- If the FFmpeg process dies mid-render, `write_frame_bytes()` will
  raise `BrokenPipeError` in the writer thread, which propagates up.
- User cancellation (via `on_progress` raising `RenderCancelled`) is
  handled by the `cancel_event` — all threads exit cooperatively.

---

## 5. Verification Checklist

### 5.1 Pre-Implementation

- [ ] Read and understand the entire Phase 4 loop (L663–766) in
      `fast_compositor.py`.
- [ ] Confirm that `interpolate_position()` in `ken_burns.py` is
      pure/stateless (no module-level mutable state).
- [ ] Confirm that `alpha_blit()` only writes to its `frame` argument
      (not to `overlay.rgb` or `overlay.alpha`).
- [ ] Confirm that `segments_info` and `segment_frame_ranges` are
      fully built before Phase 4 starts and never mutated after.

### 5.2 Implementation

- [ ] `AtomicCounter` class added and unit-tested.
- [ ] `_generate_single_frame()` function extracted and produces
      identical output to the inline loop for every frame.
- [ ] `write_frame_bytes()` method added to `FFmpegFrameWriter`.
- [ ] `_frame_producer_worker()` function implemented.
- [ ] `_frame_writer_worker()` function implemented with reorder
      buffer.
- [ ] `num_workers` parameter added to `fast_render_segments()`.
- [ ] Phase 4 replaced with threading pipeline.
- [ ] Single-threaded fallback (`num_workers=1`) implemented.
- [ ] Cancellation event wired through all threads.
- [ ] Sentinel-based shutdown sequence implemented.

### 5.3 Testing

- [ ] **Unit test:** `AtomicCounter` concurrent correctness (8 threads,
      no duplicates or gaps).
- [ ] **Unit test:** Writer reorder buffer handles out-of-order
      arrivals.
- [ ] **Integration test:** Render a 3-segment test story with
      `num_workers=1` and compare output hash to current implementation.
- [ ] **Integration test:** Render the same story with `num_workers=4`
      and verify output is visually correct (frame-by-frame spot check
      or SSIM comparison).
- [ ] **Stress test:** Render with `num_workers=8` on a 4-core machine
      to verify no deadlocks or hangs.
- [ ] **Cancellation test:** Start a render, cancel mid-way, verify
      all threads exit within 2 seconds.
- [ ] **Memory test:** Monitor RSS during a 5000-frame render with
      `num_workers=4`; memory should stay under 500 MB.

### 5.4 Regression

- [ ] Existing test suite passes (`python manage.py test`).
- [ ] `test_e2e.py` end-to-end render test passes.
- [ ] Manual render of `test_story_01.json` through the full pipeline
      (API → tasks → video_renderer → fast_compositor) produces a
      valid MP4 with correct audio sync.
- [ ] Progress bar in the frontend updates smoothly (no jumps or
      freezes).

---

## 6. Notes for AI Agent

### 6.1 Critical Constraints

1. **Do NOT modify the function signature of `fast_render_segments()`
   beyond adding the optional `num_workers` keyword argument.**
   All existing callers must continue to work without changes.

2. **Do NOT modify `video_renderer.py` or `tasks.py`.**  The threading
   is entirely internal to `fast_compositor.py`.

3. **Frame ordering is non-negotiable.**  If frames reach FFmpeg out
   of order, the output video will have visible glitches (frames in
   wrong positions).  The reorder buffer in the writer thread is the
   mechanism that guarantees this.

4. **The `alpha_blit()` function modifies its `frame` argument
   in-place.**  Each producer MUST allocate its own `frame` and
   `seg_frame` arrays — never share them.  The extracted
   `_generate_single_frame()` function handles this by creating
   `np.zeros()` locally.

5. **Do NOT use `multiprocessing`.**  The shared `segments_info` data
   (which includes large NumPy arrays for source images) would need to
   be serialized/pickled across process boundaries, which is extremely
   expensive.  `threading` is the correct choice here because the
   heavy operations (`cv2.resize`, large NumPy slicing) release the
   GIL.

6. **Queue maxsize matters.**  Too large → excessive memory (each
   1080p frame is ~6 MB as bytes).  Too small → producers block and
   throughput drops.  `num_workers * 2` is a good default.  At
   `num_workers=4`, that's 8 slots × 6 MB ≈ 48 MB of queue memory.

7. **The `_SENTINEL` value must be a singleton that cannot be confused
   with a valid queue item.**  Using `None` is fine because valid
   items are always `(int, bytes)` tuples.

### 6.2 Implementation Order

Follow this exact sequence to minimize risk:

```
1. Add imports (threading, Queue)                  — 2 lines
2. Add AtomicCounter class                         — ~15 lines
3. Add _generate_single_frame()                    — ~75 lines
4. Add write_frame_bytes() to FFmpegFrameWriter    — ~5 lines
5. Add _SENTINEL constant                          — 1 line
6. Add _frame_producer_worker()                    — ~30 lines
7. Add _frame_writer_worker()                      — ~50 lines
8. Add num_workers param to fast_render_segments() — 1 line + 5 lines
9. Replace Phase 4 with threading pipeline         — ~60 lines
   (keep original code commented out for reference
    until tests pass, then delete it)
10. Add single-threaded fallback (num_workers=1)   — ~20 lines
11. Update logging in Phase 5                      — 1 line
12. Write tests                                    — ~80 lines
```

### 6.3 Exact Line References for Edits

| Edit | Location in `fast_compositor.py` | Action |
|---|---|---|
| Add `import threading` | After line 33 (`from typing import ...`) | Insert |
| Add `from queue import Queue` | After line 33 | Insert |
| Add `AtomicCounter` class | After line 66 (end of `OverlaySlice`) | Insert |
| Add `_SENTINEL` | Before `_generate_single_frame` | Insert |
| Add `_generate_single_frame()` | Before line 487 (`fast_render_segments`) | Insert |
| Add `_frame_producer_worker()` | After `_generate_single_frame` | Insert |
| Add `_frame_writer_worker()` | After `_frame_producer_worker` | Insert |
| Add `write_frame_bytes()` | After line 478 (`write_frame` method) | Insert |
| Add `num_workers` param | Line 500 (function signature) | Modify |
| Add worker count resolution | After line 536 (local var setup) | Insert |
| Replace Phase 4 | Lines 663–766 | Replace |
| Update Phase 5 logging | Line 785 | Modify |

### 6.4 Testing Commands

```bash
# Run unit tests only
cd backend
python manage.py test core_engine.tests.test_threaded_render -v 2

# Run full test suite to check for regressions
python manage.py test -v 2

# Quick manual smoke test (render test_story_01)
python manage.py shell -c "
from core_engine.video_renderer import render_project
render_project(1)
"

# Compare single-threaded vs multi-threaded output
python -c "
import hashlib
h1 = hashlib.md5(open('output_single.mp4','rb').read()).hexdigest()
h2 = hashlib.md5(open('output_multi.mp4','rb').read()).hexdigest()
print(f'Single: {h1}')
print(f'Multi:  {h2}')
print(f'Match:  {h1 == h2}')
"
```

### 6.5 Potential Pitfalls

| Pitfall | Symptom | Fix |
|---|---|---|
| Forgetting to send sentinel after producers finish | Writer thread hangs forever on `queue.get()` | Always `queue.put(_SENTINEL)` after joining all producers |
| Reorder buffer grows unbounded | Memory explosion if writer can't keep up | Bounded queue provides backpressure — producers block when queue is full |
| `on_progress` raising `RenderCancelled` in writer thread | Writer crashes, producers keep going | Wire `cancel_event` — writer sets it, producers check it |
| Passing mutable objects into `generate_kwargs` | Race conditions on shared state | All items in `generate_kwargs` must be immutable or read-only after Phase 2 |
| NumPy array sharing via views | One thread's crop modifies another's source | `_generate_single_frame` allocates new arrays; `source_image[y:y+h, x:x+w]` creates a view but only reads — safe |
| FFmpeg pipe broken mid-render | `BrokenPipeError` in writer thread | Catch in writer, set `cancel_event`, reraise on main thread |

### 6.6 Future Enhancements (Out of Scope)

These are explicitly **NOT** part of this feature but are noted for
future reference:

- **ProcessPoolExecutor with shared memory:** For true GIL-free
  parallelism on CPU-bound Python code.  Requires `multiprocessing.
  shared_memory` for source images.  Feature 1.2 territory.
- **GPU compositing (CuPy):** Feature 1.2 in IDEAS_01.  Would replace
  NumPy operations in `_generate_single_frame()` with CuPy equivalents.
- **Adaptive worker count:** Dynamically adjust `num_workers` based on
  available memory and current system load.
- **Per-segment parallelism:** Instead of per-frame parallelism,
  assign entire segments to threads.  Simpler but less balanced for
  segments with different durations.

---

*End of Feature 1.1 implementation document.*
