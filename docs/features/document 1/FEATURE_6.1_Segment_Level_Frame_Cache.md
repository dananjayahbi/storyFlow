# Feature 6.1 — Segment-Level Frame Cache

> **Status:** Planned  
> **Category:** Core Engine / Caching & Incremental Rendering  
> **Primary Files:** `backend/core_engine/frame_cache.py` (NEW), `backend/core_engine/fast_compositor.py`, `backend/api/models.py`, `backend/api/serializers.py`  
> **Estimated Complexity:** High  
> **Impact:** Re-renders after subtitle/audio-only changes drop from minutes to seconds  
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

The current rendering pipeline in StoryFlow produces every video frame
from scratch on every render, regardless of whether the underlying
segment data has actually changed.  This behaviour is rooted in
`fast_render_segments()` in `backend/core_engine/fast_compositor.py`
(line 488, 839 lines total).

The function executes five sequential phases:

1. **Phase 1 — Pre-compute segment info** (lines 547–612):  For each
   segment, the function loads the source image from disk via
   `load_and_prepare_image()`, calculates the Ken Burns crop
   dimensions via `calculate_crop_dimensions()`, determines the pan
   direction via `get_pan_direction()`, computes start and end
   coordinates via `get_start_end_coords()`, and pre-renders subtitle
   overlays.  All of this is stored in a `segments_info` list of
   dicts.

2. **Phase 2 — Timeline calculation** (lines 617–646):  Segment frame
   ranges are computed with crossfade overlap.  This determines which
   frames belong to which segments and how many total frames will be
   generated.

3. **Phase 3 — FFmpeg writer** (lines 651–662):  An `FFmpegFrameWriter`
   is instantiated and started.

4. **Phase 4 — Main frame loop** (lines 666–770):  For every single
   frame in the video, the compositor iterates over active segments,
   generates Ken Burns crops via `interpolate_position()`, resizes
   with `cv2.resize()`, applies subtitle overlays via `alpha_blit()`,
   performs crossfade blending, applies the logo overlay, and writes
   the result to FFmpeg.

5. **Phase 5 — Finalize** (lines 775–789):  FFmpeg encoding is
   completed and statistics are returned.

The critical observation is that **Phase 1 is the most expensive
non-rendering step**.  Loading images from disk, preparing them at the
correct resolution for Ken Burns (which involves upscaling or
resizing the source image to accommodate the zoom factor), and pre-
rendering subtitle overlays all consume significant time and memory.
More importantly, the **source image preparation and Ken Burns
parameters rarely change between renders**.

Consider this common workflow:

- A user creates a 20-segment project and renders it (takes 3 minutes).
- The user notices a typo in segment 7's subtitle text.
- The user fixes the typo and re-renders.
- The system **re-loads and re-prepares all 20 images from scratch**,
  even though only segment 7's subtitle overlay changed.
- The image loading, resizing, and Ken Burns parameter computation for
  the other 19 segments is pure waste.

Similarly, if the user changes only the background music, adjusts
inter-segment silence, or modifies subtitle styling, the entire image
preparation pipeline runs from scratch.

The root cause is simple: **there is no caching layer whatsoever**.
Every call to `fast_render_segments()` is stateless and ephemeral.

### 1.2 Proposed Solution

Implement a **content-addressed frame cache** that stores pre-computed
Ken Burns source images and their associated metadata on disk.  The
cache is keyed by a SHA-256 hash of all parameters that affect the
visual output of a segment's Ken Burns frames:

- The image file content hash (SHA-256 of the file bytes)
- The zoom intensity value
- The output resolution (width and height)
- The frames-per-second value
- The Ken Burns pan direction (start name, end name)

When these parameters have not changed for a segment, the cached
source image and crop metadata can be loaded directly from the cache
directory, bypassing the expensive `load_and_prepare_image()`,
`calculate_crop_dimensions()`, `get_pan_direction()`, and
`get_start_end_coords()` calls.

The cache is structured per-project under the existing media
directory:

    media/projects/{project_id}/frame_cache/{segment_hash}/
        source_image.npy      (the prepared NumPy array)
        metadata.json          (crop dimensions, coordinates, etc.)

A new module `backend/core_engine/frame_cache.py` will house all
cache logic, including:

- Cache key computation (content-addressed hashing)
- Cache read (load source image and metadata from disk)
- Cache write (save source image and metadata to disk)
- Cache invalidation (automatic via content addressing — changed
  inputs produce a new hash, old entries become stale)
- Disk space management (per-project size limit with LRU eviction)

The integration point is **Phase 1** of `fast_render_segments()`.
Before loading and preparing each segment's image, the compositor
will compute the cache key and check whether a valid cache entry
exists.  If it does, the source image and Ken Burns parameters are
loaded from cache instead of being recomputed.

A new model field `Project.frame_cache_enabled` (BooleanField,
default True) allows users to disable caching per-project if needed,
and exposes the toggle through the API and frontend.

### 1.3 Scope

| In Scope | Out of Scope |
|---|---|
| Content-addressed caching of Ken Burns source images and parameters | Caching of rendered video frames (the final composited frames written to FFmpeg) |
| Per-project cache directory under `media/projects/{id}/frame_cache/` | Cross-project cache sharing (two projects using the same image would have separate cache entries) |
| SHA-256 hashing of image file content + Ken Burns parameters | Caching of subtitle overlays (these are fast to render and depend on many volatile parameters) |
| Automatic invalidation via content addressing | Manual cache invalidation UI (not needed — content addressing handles it) |
| LRU disk space eviction per project | Global disk quota across all projects |
| New `frame_cache.py` module in `core_engine/` | Changes to the FFmpeg writer or encoding parameters |
| New `frame_cache_enabled` field on Project model | Changes to the frontend rendering UI beyond the toggle |
| Cache hit/miss logging for diagnostics | Cache analytics dashboard or statistics API |
| NumPy `.npy` format for source image storage | Compressed image formats (PNG, JPEG) for cache storage |
| JSON metadata files for crop dimensions and coordinates | Database-backed cache metadata |

### 1.4 Key Files

| # | File | Role | Changes |
|---|------|------|---------|
| 1 | `backend/core_engine/frame_cache.py` | **NEW** — cache manager class and helper functions | Create entire module |
| 2 | `backend/core_engine/fast_compositor.py` | Main render function | Modify Phase 1 to check cache before loading images |
| 3 | `backend/api/models.py` | Data models | Add `frame_cache_enabled` to Project and GlobalSettings |
| 4 | `backend/api/serializers.py` | API serialization | Expose `frame_cache_enabled` in serializers |
| 5 | `backend/api/migrations/` | Django migrations | Auto-generated migration for new field |
| 6 | `backend/core_engine/video_renderer.py` | Calls `fast_render_segments()` | Pass `project_id` and `frame_cache_enabled` to compositor |
| 7 | `backend/core_engine/ken_burns.py` | Ken Burns functions | **No changes** (read-only dependency) |
| 8 | `frontend/types/` | TypeScript interfaces | Add `frame_cache_enabled` to project type |
| 9 | `frontend/components/` | UI components | Add cache toggle in project settings |

### 1.5 Key Existing Functions Reference

| Function | Location | Purpose |
|---|---|---|
| `fast_render_segments()` | `fast_compositor.py` L488 | Main render entry point — Phase 1 is the integration point |
| `load_and_prepare_image()` | `ken_burns.py` L74 | Loads image from disk, resizes for Ken Burns — expensive, cacheable |
| `calculate_crop_dimensions()` | `ken_burns.py` L195 | Computes crop width/height from resolution and zoom — pure math, cacheable |
| `get_pan_direction()` | `ken_burns.py` L267 | Determines start/end direction names from segment index — pure lookup, cacheable |
| `get_start_end_coords()` | `ken_burns.py` L391 | Computes pixel coordinates for pan start/end — pure math, cacheable |
| `interpolate_position()` | `ken_burns.py` L430 | Per-frame interpolation — NOT cached (called per frame, depends on time) |
| `pre_render_subtitles()` | `fast_compositor.py` L113 | Renders subtitle overlays — NOT cached (depends on volatile text/styling) |
| `pre_render_logo()` | `fast_compositor.py` L299 | Renders logo overlay — NOT cached (rendered once per render, not per segment) |

### 1.6 Dependencies

- **hashlib** (Python stdlib) — for SHA-256 hashing of image files and
  parameter strings.
- **NumPy** (`numpy.save`, `numpy.load`) — for efficient serialization
  and deserialization of source image arrays in `.npy` format.  Already
  installed.
- **json** (Python stdlib) — for metadata storage in human-readable
  JSON format.
- **os** / **shutil** / **pathlib** (Python stdlib) — for filesystem
  operations (directory creation, file existence checks, deletion).
- **time** (Python stdlib) — for tracking last-access timestamps in
  LRU eviction.
- **logging** (Python stdlib) — for cache hit/miss diagnostics.
- No new pip packages required.

### 1.7 Risk Assessment

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Stale cache served after image file replaced with same filename | Medium | Hash the image file CONTENT (bytes), not just the filename. If the content changes, the hash changes. |
| Disk space exhaustion from accumulated cache entries | Medium | Implement per-project cache size limit with LRU eviction. Default limit of 2 GB per project. |
| Cache corruption (partial write due to crash) | Low | Write to a temporary file first, then atomically rename to the final path. Check file integrity on read. |
| Performance regression from hashing overhead | Low | SHA-256 of a 5 MB image takes approximately 10 ms — negligible compared to the 200–500 ms saved by skipping image preparation. |
| Race condition if two renders run simultaneously for the same project | Very Low | The project status check already prevents concurrent renders. Cache writes are per-segment, so no two threads would write the same entry. |
| Migration breaks existing data | Very Low | New `frame_cache_enabled` field has `default=True`. Existing projects work identically — cache simply starts cold. |
| NumPy version mismatch corrupts `.npy` files | Very Low | NumPy `.npy` format is stable across versions. Include a version marker in metadata for future-proofing. |

### 1.8 Backward Compatibility

- The `frame_cache_enabled` field defaults to True, so existing
  projects automatically benefit from caching on their next render
  without any user action.
- The first render of any project will be a "cold cache" run — exactly
  the same speed as today.  Subsequent renders will be faster.
- If `frame_cache_enabled` is set to False, the render pipeline
  behaves identically to the current implementation with zero overhead
  (the cache check is skipped entirely).
- The `fast_render_segments()` function gains two new optional keyword
  arguments (`project_id` and `frame_cache_enabled`).  Existing callers
  that do not pass these arguments will see no caching (graceful
  degradation).

---

## 2. Flow Diagram

### 2.1 Current Architecture (No Caching)

```
┌──────────────────────────────────────────────────────────────────┐
│                    CURRENT FLOW (No Cache)                        │
│                                                                  │
│  fast_render_segments() called                                   │
│       │                                                          │
│       ▼                                                          │
│  Phase 1: For EACH segment (0 .. N-1):                           │
│       │                                                          │
│       ├──► load_and_prepare_image(image_path, resolution, zoom)  │
│       │       │                                                  │
│       │       ├── Read image from disk (cv2.imread)              │
│       │       ├── Calculate target size for Ken Burns zoom       │
│       │       └── Resize image to target size (cv2.resize)       │
│       │       ╰── Returns: source_image (NumPy array)            │
│       │                                                          │
│       ├──► calculate_crop_dimensions(width, height, zoom)        │
│       │       ╰── Returns: (crop_w, crop_h)                     │
│       │                                                          │
│       ├──► get_pan_direction(sequence_index)                     │
│       │       ╰── Returns: (start_name, end_name)               │
│       │                                                          │
│       ├──► get_start_end_coords(start, end, src_w, src_h, ...)  │
│       │       ╰── Returns: ((sx, sy), (ex, ey))                 │
│       │                                                          │
│       └──► pre_render_subtitles(text, timing, ...)               │
│               ╰── Returns: list of OverlaySlice                  │
│                                                                  │
│  Result: segments_info = [                                       │
│    { source_image, crop_w, crop_h, start_coords, end_coords,    │
│      visual_duration, subtitle_overlays }                        │
│    ...for each segment                                           │
│  ]                                                               │
│                                                                  │
│  Phase 2–5: Timeline, FFmpeg, frame loop, finalize               │
│                                                                  │
│  PROBLEM: Every field above is recomputed from scratch on        │
│  every render, even if nothing changed.                          │
└──────────────────────────────────────────────────────────────────┘
```

### 2.2 Proposed Architecture (With Frame Cache)

```
┌──────────────────────────────────────────────────────────────────┐
│                  PROPOSED FLOW (With Frame Cache)                 │
│                                                                  │
│  fast_render_segments() called                                   │
│       │                                                          │
│       ├── frame_cache_enabled?                                   │
│       │       │                                                  │
│       │   NO──┤                                                  │
│       │       ▼                                                  │
│       │   (skip all cache logic, proceed as before)              │
│       │                                                          │
│       │  YES──┤                                                  │
│       │       ▼                                                  │
│       │   Instantiate FrameCache(project_id, cache_root)         │
│       │                                                          │
│       ▼                                                          │
│  Phase 1: For EACH segment (0 .. N-1):                           │
│       │                                                          │
│       ├──► Compute cache key:                                    │
│       │       │                                                  │
│       │       ├── hash_file(image_path) → image_hash             │
│       │       ├── Build params string:                           │
│       │       │     zoom_intensity + resolution_w + resolution_h │
│       │       │     + fps + sequence_index                       │
│       │       ├── SHA-256(image_hash + params_string)            │
│       │       └── segment_hash = hex digest (first 16 chars)     │
│       │                                                          │
│       ├──► cache.get(segment_hash)                               │
│       │       │                                                  │
│       │   ┌───┴───────────────────────────────┐                  │
│       │   │                                   │                  │
│       │  HIT                                MISS                 │
│       │   │                                   │                  │
│       │   ▼                                   ▼                  │
│       │  Load from disk:              Compute fresh:             │
│       │   source_image.npy             load_and_prepare_image()  │
│       │   metadata.json                calculate_crop_dims()     │
│       │   (30–50 ms)                   get_pan_direction()       │
│       │                                get_start_end_coords()    │
│       │   Update last_access            (300–800 ms)             │
│       │   timestamp                                              │
│       │                                cache.put(segment_hash,   │
│       │                                  source_image, metadata) │
│       │   │                                   │                  │
│       │   └───────────┬───────────────────────┘                  │
│       │               │                                          │
│       │               ▼                                          │
│       │   segments_info[i] = {                                   │
│       │     source_image, crop_w, crop_h,                        │
│       │     start_coords, end_coords, ...                        │
│       │   }                                                      │
│       │                                                          │
│       ├──► pre_render_subtitles(...)  (ALWAYS recomputed)        │
│       │                                                          │
│       └── (continue to next segment)                             │
│                                                                  │
│  Phase 2–5: (unchanged — timeline, FFmpeg, frame loop, finalize) │
│                                                                  │
│  After Phase 5:                                                  │
│       └──► cache.evict_if_over_limit()                           │
│            (remove oldest entries if total > 2 GB)               │
└──────────────────────────────────────────────────────────────────┘
```

### 2.3 Cache Directory Structure

```
media/
└── projects/
    └── {project_id}/
        ├── images/           (existing — uploaded segment images)
        ├── audio/            (existing — generated TTS audio)
        ├── upscaled_images/  (existing — upscaled images)
        │
        └── frame_cache/      (NEW — segment frame cache)
            │
            ├── a3f2b8c1e9d04721/          (segment_hash directory)
            │   ├── source_image.npy        (prepared Ken Burns source)
            │   ├── metadata.json           (crop dims, coords, etc.)
            │   └── .last_access            (timestamp file for LRU)
            │
            ├── 7b1e93f4d2a856c0/          (another segment_hash)
            │   ├── source_image.npy
            │   ├── metadata.json
            │   └── .last_access
            │
            ├── e5c0a912b83f4167/          (stale entry — old hash)
            │   ├── source_image.npy        (will be evicted by LRU)
            │   ├── metadata.json
            │   └── .last_access
            │
            └── ... (one directory per unique segment configuration)
```

### 2.4 Cache Key Computation Detail

```
INPUTS:
  ┌────────────────────────────────────────────────────────┐
  │  image_path = "media/projects/abc/images/photo.jpg"    │
  │  zoom_intensity = 1.3                                  │
  │  resolution = (1920, 1080)                             │
  │  fps = 30                                              │
  │  sequence_index = 4                                    │
  └────────────────────┬───────────────────────────────────┘
                       │
                       ▼
  STEP 1: Hash the image file content
  ┌────────────────────────────────────────────────────────┐
  │  Read file bytes in 64 KB chunks                       │
  │  Feed each chunk to SHA-256 hasher                     │
  │  image_hash = sha256.hexdigest()                       │
  │  Example: "a1b2c3d4e5f6..."  (64 hex chars)           │
  └────────────────────┬───────────────────────────────────┘
                       │
                       ▼
  STEP 2: Build composite parameter string
  ┌────────────────────────────────────────────────────────┐
  │  params = f"{image_hash}|{zoom_intensity}|"            │
  │           f"{resolution_w}x{resolution_h}|"            │
  │           f"{fps}|{sequence_index}"                    │
  │                                                        │
  │  Example: "a1b2c3d4...|1.3|1920x1080|30|4"            │
  └────────────────────┬───────────────────────────────────┘
                       │
                       ▼
  STEP 3: Hash the composite string
  ┌────────────────────────────────────────────────────────┐
  │  segment_hash = SHA-256(params.encode()).hexdigest()    │
  │  Truncate to first 16 characters for directory name    │
  │                                                        │
  │  Example: "a3f2b8c1e9d04721"                           │
  └────────────────────┬───────────────────────────────────┘
                       │
                       ▼
  RESULT: Cache directory path
  ┌────────────────────────────────────────────────────────┐
  │  media/projects/{project_id}/frame_cache/a3f2b8c1e9d04721/ │
  └────────────────────────────────────────────────────────┘
```

### 2.5 Cache Hit vs Cache Miss — Timing Comparison

```
CACHE MISS (first render or after image change):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  hash_file(image_path)           ~10 ms   (read + SHA-256)
  cache.get(hash) → MISS           ~1 ms   (check directory exists)
  load_and_prepare_image()       ~300 ms   (imread + resize)
  calculate_crop_dimensions()      ~0 ms   (pure math)
  get_pan_direction()              ~0 ms   (lookup)
  get_start_end_coords()           ~0 ms   (pure math)
  cache.put(hash, image, meta)    ~50 ms   (numpy.save + json.dump)
                                 ─────────
  TOTAL per segment:             ~361 ms

  20 segments × 361 ms = ~7.2 seconds


CACHE HIT (subsequent render, image unchanged):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  hash_file(image_path)           ~10 ms   (read + SHA-256)
  cache.get(hash) → HIT                    
    numpy.load(source_image.npy)  ~30 ms   (mmap load)
    json.load(metadata.json)       ~1 ms   (parse JSON)
    update .last_access            ~1 ms   (touch file)
                                 ─────────
  TOTAL per segment:              ~42 ms

  20 segments × 42 ms = ~0.84 seconds

  SAVINGS: ~6.4 seconds on Phase 1 alone for a 20-segment project.
```

### 2.6 LRU Eviction Flow

```
After render completes:
       │
       ▼
  cache.evict_if_over_limit(max_size_bytes)
       │
       ├── Scan all subdirectories in frame_cache/
       │   For each entry:
       │     ├── Read .last_access timestamp
       │     └── Calculate directory size (source_image.npy + metadata.json)
       │
       ├── Sum total cache size
       │
       ├── total_size > max_size_bytes?
       │       │
       │   NO──┤  → done, return
       │       │
       │  YES──┤
       │       ▼
       │   Sort entries by .last_access (oldest first)
       │       │
       │       ▼
       │   While total_size > max_size_bytes:
       │     ├── oldest_entry = entries.pop(0)
       │     ├── shutil.rmtree(oldest_entry.path)
       │     ├── total_size -= oldest_entry.size
       │     └── Log: "Evicted cache entry {hash} (last access: {date})"
       │
       └── Log: "Cache eviction complete. Size: {remaining} / {limit}"
```

### 2.7 Integration Point in fast_render_segments()

```
CURRENT Phase 1 (lines 563–612):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  for idx, seg in enumerate(segment_data):
      # Subtitles (always)
      sub_overlays = pre_render_subtitles(...)

      # Image loading (always from scratch)
      source_image = load_and_prepare_image(image_path, resolution, zoom)
      crop_w, crop_h = calculate_crop_dimensions(width, height, zoom)
      start_name, end_name = get_pan_direction(sequence_index)
      (sx, sy), (ex, ey) = get_start_end_coords(...)

      segments_info.append({...})


PROPOSED Phase 1 (with cache integration):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  cache = None
  if frame_cache_enabled and project_id:
      cache = FrameCache(project_id, cache_root=MEDIA_ROOT)

  for idx, seg in enumerate(segment_data):
      # Subtitles (always)
      sub_overlays = pre_render_subtitles(...)

      # Attempt cache lookup
      cache_hit = False
      if cache is not None:
          segment_hash = cache.compute_key(
              image_path, zoom_intensity, width, height, fps, sequence_index
          )
          cached = cache.get(segment_hash)
          if cached is not None:
              source_image = cached["source_image"]
              crop_w = cached["crop_w"]
              crop_h = cached["crop_h"]
              start_coords = cached["start_coords"]
              end_coords = cached["end_coords"]
              cache_hit = True

      if not cache_hit:
          # Compute fresh (current path)
          source_image = load_and_prepare_image(image_path, resolution, zoom)
          crop_w, crop_h = calculate_crop_dimensions(width, height, zoom)
          start_name, end_name = get_pan_direction(sequence_index)
          (sx, sy), (ex, ey) = get_start_end_coords(...)
          start_coords = (sx, sy)
          end_coords = (ex, ey)

          # Store in cache
          if cache is not None:
              cache.put(segment_hash, source_image,
                  crop_w, crop_h, start_coords, end_coords)

      segments_info.append({
          "source_image": source_image,
          "crop_w": crop_w,
          "crop_h": crop_h,
          "start_coords": start_coords,
          "end_coords": end_coords,
          "visual_duration": visual_duration,
          "subtitle_overlays": sub_overlays,
      })

  # After render completes (after Phase 5):
  if cache is not None:
      cache.evict_if_over_limit()
```

---

## 3. Step-by-Step Instructions

### Step 1: Create the Frame Cache Module

Create a new file at `backend/core_engine/frame_cache.py`.  This module
will contain the `FrameCache` class and all supporting functions.

The module should begin with the standard logging setup, importing
`logging`, `hashlib`, `json`, `os`, `shutil`, `time`, `pathlib`, and
`numpy`.  Define a module-level logger using `logging.getLogger(__name__)`.

Define a module-level constant `DEFAULT_MAX_CACHE_SIZE_BYTES` set to
2 times 1024 cubed (2 GB).  This is the default per-project cache size
limit.

Define another constant `HASH_TRUNCATE_LENGTH` set to 16.  This
controls how many hex characters of the SHA-256 digest are used as the
cache directory name.  Sixteen characters provide 64 bits of entropy,
which is more than sufficient to avoid collisions within a single
project's cache.

---

### Step 2: Implement the File Hashing Helper

Within `frame_cache.py`, create a standalone function called
`hash_file_content` that accepts a file path as a string and returns
the SHA-256 hex digest of the file's content.

The function should open the file in binary read mode and read it in
chunks of 65536 bytes (64 KB) to handle large image files without
loading the entire file into memory.  Each chunk is fed into a
`hashlib.sha256()` object.  After all chunks are read, return the hex
digest string.

If the file does not exist or cannot be read, the function should log
a warning and return an empty string.  This ensures that a missing file
does not crash the render — it simply forces a cache miss.

---

### Step 3: Implement the Cache Key Computation

Add a method called `compute_key` to the `FrameCache` class.  This
method accepts the following parameters: `image_path` (string),
`zoom_intensity` (float), `width` (int), `height` (int), `fps` (int),
and `sequence_index` (int).

The method should:

1. Call `hash_file_content(image_path)` to get the image content hash.
2. Build a composite parameter string by joining the image hash, zoom
   intensity (formatted to 4 decimal places), resolution width,
   resolution height, fps, and sequence index with pipe characters as
   delimiters.
3. Compute a SHA-256 hash of that composite string (encoded as UTF-8).
4. Return the first `HASH_TRUNCATE_LENGTH` characters of the hex
   digest.

The pipe-delimited format ensures that different parameter
combinations always produce different hashes.  Including the sequence
index in the hash is essential because `get_pan_direction()` uses
the sequence index modulo 7 to determine the Ken Burns direction,
so the same image at different sequence positions would have different
pan paths.

---

### Step 4: Implement the FrameCache Class Constructor

The `FrameCache` class constructor should accept `project_id` (string)
and an optional `cache_root` (string, defaulting to None).  If
`cache_root` is None, the constructor should determine the media root
by looking for a `media` directory relative to the backend directory.

The constructor should build the cache directory path as:
`{cache_root}/projects/{project_id}/frame_cache/`

It should call `os.makedirs()` with `exist_ok=True` to ensure the
directory exists.

Store the `project_id`, `cache_dir` path, and `max_size_bytes`
(defaulting to `DEFAULT_MAX_CACHE_SIZE_BYTES`) as instance attributes.

Log the cache directory path at debug level.

---

### Step 5: Implement the Cache Get Method

Add a `get` method to `FrameCache` that accepts a `segment_hash`
string and returns either a dictionary containing the cached data or
None if the cache entry does not exist or is corrupted.

The method should:

1. Construct the entry directory path as
   `{cache_dir}/{segment_hash}/`.
2. Check if the directory exists.  If not, log a debug message
   ("Cache miss: {segment_hash}") and return None.
3. Construct paths for `source_image.npy` and `metadata.json` within
   the entry directory.
4. Check that both files exist.  If either is missing, log a warning
   about a corrupted cache entry, delete the directory using
   `shutil.rmtree()`, and return None.
5. Load the source image using `numpy.load()` with
   `allow_pickle=False` for security.
6. Load the metadata by opening and parsing the JSON file.
7. Verify that the metadata contains all required keys: `crop_w`,
   `crop_h`, `start_coords`, and `end_coords`.  If any key is missing,
   log a warning, delete the entry, and return None.
8. Update the `.last_access` file in the entry directory by writing
   the current Unix timestamp to it.  This is used by the LRU eviction
   logic.
9. Convert `start_coords` and `end_coords` from JSON lists back to
   tuples (JSON does not distinguish between lists and tuples).
10. Log a debug message ("Cache hit: {segment_hash}") and return a
    dictionary with keys `source_image`, `crop_w`, `crop_h`,
    `start_coords`, and `end_coords`.

Wrap the entire method body in a try/except block.  If any exception
occurs during loading (e.g., corrupted `.npy` file, malformed JSON),
log a warning with the exception details, attempt to delete the
corrupted entry directory, and return None.  The render should never
fail because of a cache error — it should always fall back gracefully
to recomputation.

---

### Step 6: Implement the Cache Put Method

Add a `put` method to `FrameCache` that accepts `segment_hash`
(string), `source_image` (NumPy ndarray), `crop_w` (int), `crop_h`
(int), `start_coords` (tuple of two ints), and `end_coords`
(tuple of two ints).  The method returns None.

The method should:

1. Construct the entry directory path.
2. Create a temporary directory alongside it (same parent, with a
   `.tmp` suffix) to enable atomic writes.
3. Create the temporary directory using `os.makedirs()`.
4. Save the source image to `{tmp_dir}/source_image.npy` using
   `numpy.save()`.
5. Build a metadata dictionary containing `crop_w`, `crop_h`,
   `start_coords` (converted to a list for JSON serialization), and
   `end_coords` (also converted to a list).  Also include a
   `cache_version` key set to 1 (for future-proofing) and a
   `created_at` key with the current ISO-format timestamp.
6. Write the metadata dictionary to `{tmp_dir}/metadata.json`
   using `json.dump()` with an indent of 2 for readability.
7. Write the current Unix timestamp to `{tmp_dir}/.last_access`.
8. If the final entry directory already exists (from a previous
   cache write), remove it with `shutil.rmtree()`.
9. Rename the temporary directory to the final entry directory
   using `os.rename()`.  On the same filesystem, this is an atomic
   operation.
10. Log a debug message ("Cache stored: {segment_hash},
    image shape: {source_image.shape}").

Wrap the entire method in a try/except block.  If any exception occurs,
log a warning, clean up the temporary directory if it exists, and
return without raising.  Cache write failures must never abort the
render.

---

### Step 7: Implement LRU Eviction

Add an `evict_if_over_limit` method to `FrameCache` that accepts an
optional `max_size_bytes` parameter (defaulting to the instance's
`max_size_bytes` attribute).

The method should:

1. If the cache directory does not exist, return immediately.
2. Walk the cache directory and collect a list of cache entries.  For
   each subdirectory that contains a `source_image.npy` file:
   a. Calculate the total size of all files in the subdirectory.
   b. Read the `.last_access` file to get the last-access timestamp.
      If the file does not exist, use the directory's modification
      time as a fallback.
   c. Store the entry as a tuple of (last_access_timestamp,
      total_size, directory_path).
3. Sum all entry sizes to get the total cache size.
4. If total cache size is within the limit, log a debug message with
   the current size and limit, then return.
5. Sort entries by last_access_timestamp in ascending order (oldest
   first).
6. While total cache size exceeds the limit and there are entries
   remaining:
   a. Pop the oldest entry from the list.
   b. Delete the entry directory using `shutil.rmtree()`.
   c. Subtract the entry size from the total cache size.
   d. Log an info message: "Evicted cache entry {hash}
      (size: {size}, last access: {timestamp})".
7. Log a summary: "Cache eviction complete.  Remaining:
   {remaining_size} / {max_size_bytes}".

---

### Step 8: Implement Cache Clear Method

Add a `clear` method to `FrameCache` that removes the entire cache
directory for the project and recreates it empty.  This provides a
way to manually reset the cache.

The method should:

1. If the cache directory exists, delete it with `shutil.rmtree()`.
2. Recreate the empty directory with `os.makedirs()`.
3. Log an info message: "Cache cleared for project {project_id}".

---

### Step 9: Implement Cache Statistics Method

Add a `stats` method to `FrameCache` that returns a dictionary with
cache statistics.  This is useful for diagnostics and potential future
API exposure.

The method should return a dictionary containing:

- `cache_dir`: the absolute path to the cache directory.
- `entry_count`: the number of cache entry subdirectories.
- `total_size_bytes`: the total size of all cache entries in bytes.
- `total_size_mb`: the total size in megabytes (rounded to 2 decimal
  places).
- `max_size_bytes`: the configured maximum cache size.
- `max_size_mb`: the maximum size in megabytes.
- `utilization_pct`: the percentage of the cache limit that is
  currently used.

If the cache directory does not exist, return zero values for all
size-related fields.

---

### Step 10: Add the frame_cache_enabled Field to the Project Model

Open `backend/api/models.py` and locate the Project model class
(line 33).  Find the group of render-related fields near line 78
(after `transition_duration`).

Add a new BooleanField called `frame_cache_enabled` with
`default=True`.  Place it immediately after the `transition_duration`
field.  Add a brief comment explaining the field's purpose:
"Enable segment-level Ken Burns frame cache for faster re-renders."

---

### Step 11: Add the frame_cache_enabled Field to GlobalSettings

In the same file, locate the GlobalSettings model (line 182).  Find
the Ken Burns and transitions section (near line 239, after
`zoom_intensity`).

Add the same `frame_cache_enabled` BooleanField with `default=True`
to GlobalSettings.  This allows the application-wide default to be
configured.

---

### Step 12: Generate and Apply the Django Migration

After saving the model changes, run the Django migration generator
from the backend directory.  Use the `makemigrations` management
command targeting the `api` app.  Then run the `migrate` command
to apply the new migration.

Verify the migration was applied correctly by running the
`showmigrations` command and confirming the new migration has a
checkmark.

---

### Step 13: Update the Serializers

Open `backend/api/serializers.py`.

In the `ProjectSerializer` class (line 34), locate the `fields` list
in the Meta class (line 39).  Add `'frame_cache_enabled'` to the list
of fields.

In the `GlobalSettingsSerializer` class (line 78), locate the `fields`
list in the Meta class (line 81).  Add `'frame_cache_enabled'` to the
list of fields.

In the `ProjectDetailSerializer` class (line 239), locate the `fields`
list in the Meta class (line 244).  Add `'frame_cache_enabled'` to the
list of fields.

---

### Step 14: Update the Video Renderer to Pass Cache Parameters

Open `backend/core_engine/video_renderer.py`.  Locate the
`render_project()` function (line 579).

Near the section where project settings are read (around line 625–640),
add a new variable to read the `frame_cache_enabled` setting from the
project.  Use `getattr(project, "frame_cache_enabled", True)` to
safely read it with a fallback default of True.

Log the value at info level alongside the other render settings.

Then locate the call to `fast_render_segments()` (around line 1008–
1063).  Add two new keyword arguments to the call:

- `project_id=str(project.id)` — passes the project UUID as a string
  for cache directory naming.
- `frame_cache_enabled=frame_cache_enabled` — passes the toggle value.

---

### Step 15: Update fast_render_segments() Signature

Open `backend/core_engine/fast_compositor.py`.  Locate the
`fast_render_segments()` function definition (line 488).

Add two new optional keyword arguments to the function signature:

- `project_id` with a default of None (type Optional[str]).
- `frame_cache_enabled` with a default of False (type bool).

Update the docstring to document these new parameters.  The
`project_id` parameter is described as the UUID string of the project,
used for cache directory naming.  The `frame_cache_enabled` parameter
controls whether segment-level frame caching is active.

---

### Step 16: Integrate Cache Lookup in Phase 1

This is the core integration step.  In `fast_render_segments()`,
locate Phase 1 where `segments_info` is built (lines 563–612).

At the beginning of Phase 1 (after the logo pre-rendering block,
around line 560), add cache initialization logic:

1. Import the `FrameCache` class using a lazy import (inside the
   function body, not at module top level) from
   `core_engine.frame_cache`.  Use a conditional import that only
   runs if `frame_cache_enabled` is True and `project_id` is not None.

2. Instantiate a `FrameCache` object, passing `project_id` and the
   cache root path.  The cache root should be determined from the
   Django settings `MEDIA_ROOT` or derived from the `output_path`
   parameter.

3. Initialize counters for cache hits and cache misses (both starting
   at zero).  These will be logged after Phase 1 completes for
   diagnostics.

Then, within the per-segment loop (starting around line 565), add
cache lookup logic AFTER the subtitle pre-rendering but BEFORE the
Ken Burns image loading.

The flow for each segment becomes:

1. Pre-render subtitles (unchanged — always recomputed).
2. If cache is active, compute the segment hash by calling
   `cache.compute_key()` with the image path, zoom intensity, width,
   height, fps, and the segment's sequence index.
3. Attempt a cache get with the computed hash.
4. If the cache returns a result (cache hit), extract `source_image`,
   `crop_w`, `crop_h`, `start_coords`, and `end_coords` from the
   cached dictionary.  Increment the hit counter.
5. If the cache returns None (cache miss), proceed with the existing
   code path: call `load_and_prepare_image()`,
   `calculate_crop_dimensions()`, `get_pan_direction()`, and
   `get_start_end_coords()`.  Then store the results in the cache by
   calling `cache.put()`.  Increment the miss counter.
6. Append to `segments_info` as before.

After the per-segment loop completes, log the cache hit/miss summary
at info level.  For example: "Frame cache: 18 hits, 2 misses out of
20 segments".

---

### Step 17: Add Cache Eviction After Render

Still in `fast_render_segments()`, locate Phase 5 (lines 775–789)
where the render finalizes.  After the render statistics are computed
but before the function returns, add a cache eviction call.

If the cache object exists (is not None), call
`cache.evict_if_over_limit()`.  Wrap this in a try/except block so
that any eviction error is logged but does not prevent the render
result from being returned.

---

### Step 18: Add Cache Clearing on Project Deletion

Open `backend/api/views.py`.  Locate the ProjectViewSet class and
find the destroy method or the appropriate signal/hook for project
deletion.

When a project is deleted, the cache directory should also be cleaned
up.  Since the cache lives under `media/projects/{project_id}/`, and
the entire project media directory is typically cleaned up on deletion,
verify that the existing cleanup logic handles subdirectories
recursively.  If it does, no additional code is needed.  If it does
not, add a step to remove the `frame_cache/` subdirectory.

Alternatively, if the project uses Django signals for cleanup, ensure
the `post_delete` signal handler for the Project model includes cache
directory removal.

---

### Step 19: Update the Frontend TypeScript Types

Open the frontend types directory and locate the interface or type
definition for the Project object.  Add a new optional boolean field
called `frame_cache_enabled` with a default value annotation of true.

This ensures the frontend can read and write the new field through
the API.

---

### Step 20: Add Cache Toggle to Frontend Settings

In the frontend components that render the project settings panel,
add a toggle switch or checkbox for "Enable Frame Cache".  This should
be placed near the other render-related settings (resolution, framerate,
zoom intensity).

The toggle should bind to the `frame_cache_enabled` field on the
project object and use the same optimistic update pattern as other
project settings (PATCH request to the project endpoint).

Include a brief tooltip or help text explaining the feature: "When
enabled, Ken Burns frames are cached per segment. Re-renders after
subtitle or audio changes will be significantly faster."

---

### Step 21: Write Unit Tests for the Cache Module

Create a new test file at `backend/core_engine/tests/test_frame_cache.py`.

Write the following test cases:

1. **Test hash_file_content**: Create a temporary file with known
   content, call `hash_file_content()`, and verify the returned hash
   matches the expected SHA-256 digest.

2. **Test hash_file_content with missing file**: Call the function
   with a nonexistent path and verify it returns an empty string
   without raising an exception.

3. **Test compute_key determinism**: Call `compute_key()` twice with
   the same parameters and verify both calls return the same hash.

4. **Test compute_key sensitivity**: Call `compute_key()` with
   slightly different parameters (e.g., different zoom intensity) and
   verify the hashes differ.

5. **Test cache put and get round-trip**: Create a FrameCache instance
   with a temporary directory, put a source image and metadata, then
   get with the same hash and verify all data is correctly restored
   (source image array equality, metadata values).

6. **Test cache miss**: Call `get()` with a hash that has not been
   stored and verify it returns None.

7. **Test cache corruption recovery**: Create a cache entry, then
   delete the `source_image.npy` file manually.  Call `get()` and
   verify it returns None and cleans up the corrupted entry directory.

8. **Test LRU eviction**: Create multiple cache entries, set a low
   `max_size_bytes` limit, call `evict_if_over_limit()`, and verify
   that the oldest entries are removed while newer ones are preserved.

9. **Test cache clear**: Create entries, call `clear()`, and verify
   the cache directory is empty.

10. **Test cache stats**: Create entries and call `stats()`, verifying
    the returned dictionary has correct `entry_count` and approximate
    `total_size_bytes`.

---

### Step 22: Write Integration Tests

Add integration tests to `backend/tests/test_e2e.py` or create a new
file `backend/core_engine/tests/test_cache_integration.py`.

1. **Test cached render produces identical output**: Render a short
   test project (2–3 segments) twice.  The first render should have
   all cache misses.  The second render should have all cache hits.
   Verify that both renders produce visually identical output
   (compare file sizes, or use frame-by-frame SSIM comparison).

2. **Test cache invalidation on image change**: Render a project,
   then replace one segment's image file with a different image (same
   filename, different content).  Re-render and verify the changed
   segment is a cache miss while unchanged segments are cache hits.

3. **Test cache disabled**: Render with `frame_cache_enabled=False`
   and verify no cache directory is created.

4. **Test cache toggle via API**: Use the Django test client to
   PATCH a project's `frame_cache_enabled` field to False, then
   verify the response contains the updated value.

---

### Step 23: Add Cache Information to Render Stats

In `fast_render_segments()`, update the return dictionary to include
cache statistics alongside the existing `frames_rendered`,
`render_time`, and `avg_ms_per_frame` keys.

Add three new keys:

- `cache_hits`: the number of segments that were served from cache.
- `cache_misses`: the number of segments that required fresh
  computation.
- `cache_enabled`: whether frame caching was active for this render.

These values will propagate through `video_renderer.py` and can be
logged or returned in the render status API for user visibility.

---

### Step 24: Update Logging Throughout

Ensure all cache operations produce clear log messages at appropriate
levels:

- **DEBUG**: Individual cache hit/miss per segment, cache directory
  paths, hash values.
- **INFO**: Cache summary after Phase 1 (total hits/misses), eviction
  summary, cache statistics.
- **WARNING**: Corrupted cache entries, file system errors during
  cache operations.

All log messages should include the project ID for easy filtering in
multi-project environments.

---

## 4. Expected Outcome

### 4.1 Performance

| Metric | Before (No Cache) | After (Warm Cache) | Notes |
|---|---|---|---|
| Phase 1 time (20 segments, 1080p) | ~6–8 seconds | ~0.8–1.2 seconds | 5–8× faster for Phase 1 |
| Phase 1 time (20 segments, 4K) | ~15–25 seconds | ~1.5–3 seconds | Larger images benefit more |
| Total re-render time (subtitle change only) | ~3–5 minutes | ~2.5–4.5 minutes | Phase 1 savings; Phase 4 still dominates |
| Total re-render time (audio change only) | ~3–5 minutes | ~2.5–4.5 minutes | Same improvement — Phase 1 is cached |
| First render time (cold cache) | ~3–5 minutes | ~3–5.2 minutes | Slight overhead from cache writes (~50 ms/segment) |
| Cache write overhead per segment | N/A | ~50 ms | numpy.save + json.dump |
| Cache read overhead per segment | N/A | ~40 ms | numpy.load + json.load |
| Disk usage per cached segment (1080p) | N/A | ~15–30 MB | Depends on image size after Ken Burns preparation |
| Disk usage per cached segment (4K) | N/A | ~60–120 MB | 4K source images are significantly larger |
| Disk usage per project (20 segments, 1080p) | N/A | ~300–600 MB | Well within the 2 GB default limit |

### 4.2 User Experience Improvements

**Before this feature:**
- User renders a 20-segment project (3 minutes).
- User spots a typo in one subtitle.
- User fixes the typo and re-renders.
- The system re-loads all 20 images, re-prepares them for Ken Burns,
  re-computes all crop dimensions and pan directions.
- User waits another 3 minutes for an identical pipeline to run from
  scratch.

**After this feature:**
- User renders a 20-segment project (3 minutes + ~1 second cache
  write overhead).
- User spots a typo in one subtitle.
- User fixes the typo and re-renders.
- The system checks the frame cache: all 20 segments have unchanged
  images, zoom, resolution, and fps.  All 20 segments are cache hits.
- Phase 1 completes in under 1 second instead of 6–8 seconds.
- User notices the "Pre-rendering overlays" phase completes almost
  instantly.
- The remaining render time is dominated by frame generation
  (Phase 4), which is unchanged.

### 4.3 Scenarios Where Cache Helps Most

| Scenario | Cache Impact |
|---|---|
| Subtitle text changes (typo fix, rephrasing) | All segments hit cache — subtitles are NOT cached, but images ARE |
| Audio re-generation (different TTS voice) | All segments hit cache — audio does not affect image cache keys |
| Background music changes | All segments hit cache — music is mixed separately |
| Inter-segment silence adjustment | All segments hit cache — silence does not affect image cache keys |
| Subtitle styling changes (font, color, size) | All segments hit cache — subtitle styling is not part of the cache key |
| Logo changes (position, opacity, image) | All segments hit cache — logo is rendered separately, not per-segment |
| One segment's image replaced | 19 cache hits, 1 miss — only the changed segment recomputes |
| Zoom intensity changed | All segments miss cache — zoom affects the prepared image |
| Resolution changed | All segments miss cache — resolution affects image preparation |
| FPS changed | All segments miss cache — fps is part of the cache key |

### 4.4 Correctness

- **Cache-hit output must be identical to cache-miss output.**  The
  cached `source_image` array is the exact same NumPy array that
  `load_and_prepare_image()` would produce.  It is saved with
  `numpy.save()` which preserves dtype, shape, and all values exactly.
  There is no lossy compression.

- **The metadata (crop_w, crop_h, start_coords, end_coords) must be
  numerically identical.**  These are small integers stored in JSON,
  which preserves exact integer values.

- **The rendered video must be byte-identical** between a cold-cache
  render and a warm-cache render when all inputs are the same.

### 4.5 API Compatibility

- `fast_render_segments()` gains two optional keyword arguments:
  `project_id` and `frame_cache_enabled`.  Both have safe defaults
  (None and False respectively).  Existing callers that do not pass
  these arguments see no change in behaviour.

- The return dictionary gains three new optional keys: `cache_hits`,
  `cache_misses`, `cache_enabled`.  Callers that do not read these
  keys are unaffected.

- The `Project` and `GlobalSettings` models gain one new field each
  (`frame_cache_enabled`).  The migration sets a default value, so
  existing database records are automatically updated.

### 4.6 Error Handling

- **Cache read failure** (corrupted file, permission error): the
  segment falls back to fresh computation.  A warning is logged.  The
  render succeeds.

- **Cache write failure** (disk full, permission error): the segment
  is not cached.  A warning is logged.  The render succeeds.  The
  next render will attempt to cache again.

- **Hash computation failure** (file not found during hashing): the
  `hash_file_content` function returns an empty string, which produces
  a valid but unique hash.  The segment proceeds as a cache miss.

- **Eviction failure** (permission error on delete): a warning is
  logged.  The cache may exceed the size limit, but the render
  succeeds.

---

## 5. Verification Checklist

### 5.1 Pre-Implementation

- [ ] Read and understand Phase 1 of `fast_render_segments()` in
      `backend/core_engine/fast_compositor.py` (lines 547–612).
- [ ] Confirm that `load_and_prepare_image()` in `ken_burns.py` (L74)
      is a pure function — given the same inputs, it always produces
      the same output array.
- [ ] Confirm that `calculate_crop_dimensions()` in `ken_burns.py`
      (L195) is deterministic.
- [ ] Confirm that `get_pan_direction()` in `ken_burns.py` (L267)
      uses only `sequence_index` to determine direction.
- [ ] Confirm that `get_start_end_coords()` in `ken_burns.py` (L391)
      is a pure function of its inputs.
- [ ] Check the current `media/projects/` directory structure to
      verify there are no naming conflicts with `frame_cache/`.
- [ ] Verify that the Django `MEDIA_ROOT` setting points to the
      expected location.

### 5.2 Implementation — Cache Module

- [ ] `backend/core_engine/frame_cache.py` file created.
- [ ] `hash_file_content()` function implemented and tested.
- [ ] `FrameCache` class constructor implemented.
- [ ] `FrameCache.compute_key()` method implemented and tested.
- [ ] `FrameCache.get()` method implemented with corruption handling.
- [ ] `FrameCache.put()` method implemented with atomic writes.
- [ ] `FrameCache.evict_if_over_limit()` method implemented.
- [ ] `FrameCache.clear()` method implemented.
- [ ] `FrameCache.stats()` method implemented.
- [ ] All methods are wrapped in try/except to prevent cache errors
      from aborting renders.

### 5.3 Implementation — Model and Serializer

- [ ] `frame_cache_enabled` BooleanField added to Project model
      (after `transition_duration`, around line 78).
- [ ] `frame_cache_enabled` BooleanField added to GlobalSettings model
      (near line 239).
- [ ] Django migration generated successfully.
- [ ] Django migration applied without errors.
- [ ] `frame_cache_enabled` added to `ProjectSerializer` fields list.
- [ ] `frame_cache_enabled` added to `GlobalSettingsSerializer`
      fields list.
- [ ] `frame_cache_enabled` added to `ProjectDetailSerializer` fields
      list.

### 5.4 Implementation — Compositor Integration

- [ ] Two new keyword arguments (`project_id`, `frame_cache_enabled`)
      added to `fast_render_segments()` signature.
- [ ] Lazy import of `FrameCache` class inside `fast_render_segments()`.
- [ ] Cache initialization at the start of Phase 1 (conditional on
      `frame_cache_enabled` and `project_id` being set).
- [ ] Per-segment cache key computation added to the Phase 1 loop.
- [ ] Cache get attempted before `load_and_prepare_image()`.
- [ ] Cache put called after fresh computation (on cache miss).
- [ ] Cache hit/miss counters tracked and logged.
- [ ] Cache eviction called after Phase 5.
- [ ] Return dictionary updated with cache statistics.

### 5.5 Implementation — Video Renderer

- [ ] `frame_cache_enabled` read from project in `render_project()`
      (around line 625–640).
- [ ] `project_id` and `frame_cache_enabled` passed to
      `fast_render_segments()` call (around line 1008–1063).
- [ ] Cache statistics logged after render completes.

### 5.6 Testing — Unit Tests

- [ ] `test_hash_file_content` — known content produces expected hash.
- [ ] `test_hash_file_missing` — missing file returns empty string.
- [ ] `test_compute_key_determinism` — same inputs produce same hash.
- [ ] `test_compute_key_sensitivity` — different inputs produce
      different hashes.
- [ ] `test_cache_put_get_roundtrip` — stored data is correctly
      retrieved.
- [ ] `test_cache_miss` — unset hash returns None.
- [ ] `test_cache_corruption_recovery` — corrupted entry returns None
      and is cleaned up.
- [ ] `test_lru_eviction` — oldest entries are removed when over limit.
- [ ] `test_cache_clear` — directory is emptied.
- [ ] `test_cache_stats` — correct counts and sizes returned.

### 5.7 Testing — Integration Tests

- [ ] Cold render followed by warm render produces identical output.
- [ ] Image replacement invalidates only the changed segment's cache.
- [ ] `frame_cache_enabled=False` skips all cache operations.
- [ ] API PATCH of `frame_cache_enabled` round-trips correctly.
- [ ] Full test suite passes: `python manage.py test`.
- [ ] End-to-end test in `test_e2e.py` passes.

### 5.8 Testing — Manual Verification

- [ ] Render `test_story_01.json` with cache enabled.  Check that
      `media/projects/{id}/frame_cache/` directory is created with
      subdirectories.
- [ ] Re-render the same project without changes.  Check logs for
      "Cache hit" messages for all segments.
- [ ] Change one segment's subtitle text and re-render.  Verify all
      segments are cache hits (subtitle changes do not invalidate the
      image cache).
- [ ] Change one segment's image and re-render.  Verify that segment
      is a cache miss while all others are cache hits.
- [ ] Change the project's zoom intensity and re-render.  Verify all
      segments are cache misses.
- [ ] Disable frame caching via the API, re-render, and verify no
      cache operations appear in the logs.

### 5.9 Regression

- [ ] Existing test suite passes without modifications.
- [ ] Projects created before the migration render correctly.
- [ ] The `frame_cache_enabled` field defaults to True for all
      existing projects after migration.
- [ ] Frontend project settings page loads without errors.
- [ ] Progress bar and render status updates are unaffected.

---

## 6. Notes for AI Agent

### 6.1 Critical Constraints

1. **Do NOT modify the return type of `fast_render_segments()`.**  It
   must still return a dictionary.  Adding new keys to the dictionary
   is allowed but removing or renaming existing keys (`frames_rendered`,
   `render_time`, `avg_ms_per_frame`) is not.

2. **Do NOT cache subtitle overlays.**  Subtitles depend on text
   content, font, color, size, and position — all of which are volatile
   and frequently changed by users.  Caching subtitles would add
   significant complexity to cache invalidation with little benefit
   (subtitle pre-rendering is already fast).

3. **Do NOT cache the final composited frames** (the output of
   Phase 4).  Composited frames depend on crossfade blending with
   adjacent segments, logo overlay, and frame timing — too many
   dependencies for effective content addressing.  This feature caches
   only the Phase 1 outputs (source images and Ken Burns parameters).

4. **Cache errors must NEVER abort a render.**  Every cache operation
   (get, put, evict, hash) must be wrapped in try/except blocks that
   log warnings and fall back to the non-cached code path.  The user
   must never see a render failure caused by cache corruption or disk
   space issues.

5. **Use lazy imports for the FrameCache class** inside
   `fast_render_segments()`.  The fast compositor module is imported
   in contexts where Django may not be fully initialized, and the
   cache module references file paths that depend on Django settings.
   Use the same import pattern as the existing Ken Burns imports on
   line 538 of `fast_compositor.py`.

6. **Use atomic writes for cache entries.**  Write to a temporary
   directory first, then rename to the final path.  This prevents
   corrupted cache entries if the process crashes during a write.  On
   POSIX systems, `os.rename()` is atomic when source and destination
   are on the same filesystem.  On Windows, use `os.replace()` which
   provides atomic semantics.

7. **The `.npy` format must use `allow_pickle=False`** on load.  This
   prevents arbitrary code execution from a maliciously crafted cache
   file.  The `numpy.save()` function stores arrays in a simple binary
   format that does not require pickling.

8. **The sequence_index MUST be part of the cache key.**  The
   `get_pan_direction()` function at line 267 of `ken_burns.py` uses
   `sequence_index % 7` to determine the Ken Burns direction.  If two
   segments use the same image but are at different sequence positions,
   they will have different pan directions and therefore different
   start/end coordinates.

### 6.2 Implementation Order

Follow this exact sequence to minimize risk and enable incremental
testing:

    1.  Create backend/core_engine/frame_cache.py with FrameCache
        class, hash_file_content(), compute_key(), get(), put(),
        evict_if_over_limit(), clear(), stats().
        Estimated: ~200 lines.

    2.  Write unit tests in
        backend/core_engine/tests/test_frame_cache.py.
        Estimated: ~150 lines. Run tests — all should pass.

    3.  Add frame_cache_enabled to Project model in
        backend/api/models.py (after line 78).
        Estimated: 2 lines.

    4.  Add frame_cache_enabled to GlobalSettings model in
        backend/api/models.py (after line 239).
        Estimated: 2 lines.

    5.  Generate and apply Django migration.
        Estimated: one management command.

    6.  Add frame_cache_enabled to serializer field lists in
        backend/api/serializers.py (3 locations).
        Estimated: 3 lines.

    7.  Update fast_render_segments() signature in
        backend/core_engine/fast_compositor.py (line 488) to
        accept project_id and frame_cache_enabled.
        Estimated: 2 lines + 6 lines docstring.

    8.  Add cache initialization and per-segment cache logic
        to Phase 1 of fast_render_segments() (lines 563–612).
        Estimated: ~40 lines.

    9.  Add cache eviction call after Phase 5 (after line 789).
        Estimated: 5 lines.

    10. Update return dictionary to include cache stats (line 796).
        Estimated: 3 lines.

    11. Update render_project() in video_renderer.py to read
        frame_cache_enabled and pass it to fast_render_segments()
        (around lines 625–640 and 1008–1063).
        Estimated: 8 lines.

    12. Write integration tests.
        Estimated: ~80 lines.

    13. Update frontend types and settings UI.
        Estimated: ~20 lines.

### 6.3 Exact Line References for Edits

| Edit | Location | Action |
|---|---|---|
| Create `frame_cache.py` | `backend/core_engine/` | New file |
| Add `frame_cache_enabled` to Project | `models.py` after L78 (`transition_duration`) | Insert field |
| Add `frame_cache_enabled` to GlobalSettings | `models.py` after L239 (`zoom_intensity`) | Insert field |
| Add to `ProjectSerializer` fields | `serializers.py` L39–43 (fields list) | Add string |
| Add to `GlobalSettingsSerializer` fields | `serializers.py` L81–96 (fields list) | Add string |
| Add to `ProjectDetailSerializer` fields | `serializers.py` L244–261 (fields list) | Add string |
| Add `project_id` param | `fast_compositor.py` L488 (function signature) | Add kwarg |
| Add `frame_cache_enabled` param | `fast_compositor.py` L488 (function signature) | Add kwarg |
| Add cache initialization | `fast_compositor.py` after L560 (after logo pre-render) | Insert block |
| Add cache lookup in Phase 1 loop | `fast_compositor.py` L587–611 (per-segment block) | Wrap existing code |
| Add cache eviction | `fast_compositor.py` after L789 (after Phase 5) | Insert block |
| Update return dict | `fast_compositor.py` L796 (return statement) | Add keys |
| Read `frame_cache_enabled` | `video_renderer.py` after L633 (settings reading) | Insert line |
| Pass to `fast_render_segments()` | `video_renderer.py` L1008–1063 (function call) | Add kwargs |
| Create test file | `backend/core_engine/tests/test_frame_cache.py` | New file |

### 6.4 Cache Key Design Rationale

**Why include image file CONTENT hash instead of just the path?**
Users sometimes replace an image file at the same path (e.g., upload a
new version of "hero_image.jpg" overwriting the old one).  If the cache
key used only the file path, the old cached source image would be
served even though the file content changed.  Hashing the content
guarantees that any change to the file — even if the filename stays
the same — produces a new cache key.

**Why include fps in the cache key?**
The `load_and_prepare_image()` function itself does not use fps, but
fps affects how many frames are generated per segment, which affects
whether the source image is "sufficient" at a given zoom level.  More
critically, if a future optimization caches per-frame data (not just
per-segment), fps would be essential.  Including it now is defensive
and costs nothing.

**Why NOT include subtitle-related parameters?**
Subtitles are rendered as overlays AFTER the Ken Burns source image is
prepared.  They are applied per-frame in Phase 4, not during Phase 1.
The cached data (source_image + Ken Burns metadata) is independent of
subtitle content, font, color, size, or position.  This is what makes
the cache so effective for subtitle-only changes.

**Why truncate the hash to 16 hex characters?**
16 hex characters represent 64 bits of entropy.  The birthday paradox
probability of a collision in a set of N items with 64-bit hashes is
approximately N squared divided by (2 times 2 to the 64th power).
For a project with 100 segments and 10 renders each (1000 unique
cache keys), the collision probability is approximately 0.000000003
percent.  This is negligible, and shorter directory names improve
readability in logs and file explorers.

### 6.5 Metadata JSON Schema

The `metadata.json` file stored in each cache entry should follow this
structure:

    cache_version:  integer (currently 1)
    created_at:     ISO 8601 timestamp string
    crop_w:         integer (crop width in pixels)
    crop_h:         integer (crop height in pixels)
    start_coords:   array of two integers [sx, sy]
    end_coords:     array of two integers [ex, ey]
    image_shape:    array of two or three integers [height, width]
                    or [height, width, channels]
    params:         object containing the original cache key inputs:
        image_hash:       string (SHA-256 hex of image content)
        zoom_intensity:   number (float)
        resolution_w:     integer
        resolution_h:     integer
        fps:              integer
        sequence_index:   integer

The `params` sub-object is stored for debugging purposes only — it is
NOT used for cache lookup (the hash is used instead).  It allows a
developer to inspect a cache entry and understand which parameters
produced it.

### 6.6 Potential Pitfalls

| Pitfall | Symptom | Fix |
|---|---|---|
| Forgetting to include sequence_index in cache key | Two segments with the same image but different positions render with the same pan direction | Always include sequence_index in the composite parameter string |
| Using `os.rename()` on Windows across drives | `OSError` because rename cannot cross filesystem boundaries | Use `shutil.move()` as fallback, or ensure temp directory is on the same drive as the cache directory |
| Loading `.npy` file with `allow_pickle=True` | Security vulnerability — arbitrary code execution | Always use `allow_pickle=False` in `numpy.load()` |
| Not handling `numpy.load()` returning a 0-d array | Crash when trying to access `.shape` | Verify array dimensions after loading; delete entry and return None if invalid |
| Cache directory not created before first put | `FileNotFoundError` when writing cache entry | Constructor calls `os.makedirs(exist_ok=True)` |
| Extremely large source images filling disk | Cache exceeds size limit rapidly | LRU eviction handles this; warn in logs if a single entry exceeds 500 MB |
| Race condition between hash computation and file modification | Hash computed, then file is modified, then load_and_prepare_image reads the new file | Extremely unlikely in practice (user would need to upload a new image while a render is in progress, which is blocked by the PROCESSING status) |
| Float formatting producing different strings on different platforms | Different cache keys for the same logical parameters | Use explicit format string with fixed decimal places (4 decimal places for zoom_intensity) |

### 6.7 Performance Optimization Notes

- **Memory-mapped loading:** `numpy.load()` supports memory-mapped
  mode via the `mmap_mode` parameter.  Using `mmap_mode='r'` loads
  the array as a read-only memory-mapped file, which can be faster
  for very large arrays because the OS handles paging.  However, this
  only works on systems that support memory mapping (all modern
  systems).  Consider using `mmap_mode='r'` for arrays larger than
  100 MB.

- **Parallel cache loading:** If the Multi-Threaded Frame Generation
  feature (Feature 1.1) is implemented, the cache loading in Phase 1
  could also be parallelized — each segment's cache lookup is
  independent.  However, this is out of scope for Feature 6.1.

- **Incremental hashing:** For very large image files (20+ MB), the
  hashing operation could be optimized by caching the file hash
  alongside the file and only recomputing it when the file's
  modification time changes.  This is a micro-optimization that is
  not needed for v1 but could be added later.

### 6.8 Interaction with Other Features

| Feature | Interaction |
|---|---|
| Feature 1.1 (Multi-Threaded Frame Generation) | No conflict. The cache is populated during Phase 1, which runs before the threading pipeline in Phase 4. Cache operations are single-threaded. |
| Feature 1.2 (GPU Compositing) | No conflict. GPU compositing affects Phase 4 (frame generation), not Phase 1 (image preparation). |
| Feature 2.4 (Zoom Level Per Segment) | If per-segment zoom is implemented, the zoom_intensity in the cache key would need to come from the segment rather than the project. The cache key computation already receives zoom_intensity as a parameter, so passing a per-segment value instead of a project-level one would work transparently. |
| Feature 3.1 (Transition Variety) | No conflict. Transitions affect Phase 4 (frame compositing during overlap), not Phase 1 (image preparation). |
| Feature 6.2 (Preview Render Mode) | Preview mode uses a different resolution and fps. This means preview renders will have different cache keys from final renders. The same project will have separate cache entries for preview and final, which is correct behaviour. |

### 6.9 Disk Space Estimation Guide

For planning cache disk space requirements:

| Resolution | Approx. Source Image Size | 20 Segments | 50 Segments |
|---|---|---|---|
| 854x480 (480p) | ~2 MB | ~40 MB | ~100 MB |
| 1280x720 (720p) | ~5 MB | ~100 MB | ~250 MB |
| 1920x1080 (1080p) | ~15 MB | ~300 MB | ~750 MB |
| 2560x1440 (1440p) | ~25 MB | ~500 MB | ~1.25 GB |
| 3840x2160 (4K) | ~60 MB | ~1.2 GB | ~3.0 GB |

The source image size depends on the Ken Burns zoom factor — higher
zoom means the source image is prepared at a larger resolution to
accommodate the pan movement.  The values above assume the default
zoom intensity of 1.3.

At 4K resolution with 50 segments, the cache would exceed the default
2 GB limit.  The LRU eviction would keep only the most recently used
entries.  Users working at 4K with many segments may want to increase
the cache limit or accept more frequent evictions.

### 6.10 Testing Commands

    Run unit tests for cache module only:
    cd backend
    python manage.py test core_engine.tests.test_frame_cache -v 2

    Run full test suite:
    python manage.py test -v 2

    Check migration status:
    python manage.py showmigrations api

    Generate migration:
    python manage.py makemigrations api

    Apply migration:
    python manage.py migrate api

    Manual smoke test — render with cache:
    python manage.py shell -c "
    from core_engine.video_renderer import render_project
    result = render_project('PROJECT_UUID_HERE')
    print(result)
    "

    Inspect cache directory:
    ls -la media/projects/PROJECT_UUID/frame_cache/

    Check cache entry contents:
    python -c "
    import numpy as np, json
    img = np.load('media/projects/XXX/frame_cache/HASH/source_image.npy')
    print(f'Shape: {img.shape}, dtype: {img.dtype}')
    meta = json.load(open('media/projects/XXX/frame_cache/HASH/metadata.json'))
    print(json.dumps(meta, indent=2))
    "

### 6.11 Future Enhancements (Out of Scope)

These are explicitly NOT part of Feature 6.1 but are noted for future
reference:

- **Cross-project cache sharing:** If multiple projects use the same
  image at the same resolution and zoom, they could share a single
  cache entry.  This would require a global content-addressed store
  (keyed by image_hash + params, without project_id in the path).
  Significantly more complex due to reference counting and cleanup.

- **Compressed cache storage:** Instead of storing raw `.npy` arrays,
  compress with LZ4 or Zstandard for 3–5x disk space reduction.  The
  trade-off is CPU time for decompression on cache read.

- **Database-backed cache metadata:** Instead of filesystem-based
  `.last_access` files, store cache metadata in a Django model.  This
  would enable richer queries (e.g., "show all cached segments for
  project X") but adds database load.

- **Cache warming:** Pre-compute cache entries for a project without
  actually rendering the video.  Useful if a user uploads all images
  first and wants to ensure fast subsequent renders.

- **Remote cache storage:** Store cache entries in S3 or similar
  object storage for persistence across server restarts or deployments.
  Only relevant for cloud-hosted installations.

---

*End of Feature 6.1 — Segment-Level Frame Cache implementation document.*
