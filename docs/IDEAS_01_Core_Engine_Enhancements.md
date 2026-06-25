# StoryFlow Ideas — Document 1: Core Engine Enhancements

> **Category:** Rendering, Compositing, Ken Burns, Performance, Video Pipeline  
> **Last Updated:** March 1, 2026  
> **Purpose:** Ideas to make the video rendering engine faster, higher quality, and more capable

---

## Table of Contents

- [1. Rendering Performance](#1-rendering-performance)
- [2. Ken Burns & Motion Improvements](#2-ken-burns--motion-improvements)
- [3. Transition System Overhaul](#3-transition-system-overhaul)
- [4. Video Composition Enhancements](#4-video-composition-enhancements)
- [5. Encoding & Output Quality](#5-encoding--output-quality)
- [6. Caching & Incremental Rendering](#6-caching--incremental-rendering)
- [7. Architecture Cleanup](#7-architecture-cleanup)

---

## 1. Rendering Performance

### 1.1 Multi-Threaded Frame Generation
- **Current:** Single-threaded frame loop — each frame rendered sequentially.
- **Idea:** Implement a producer/consumer pipeline: N frame-generation threads feed a single FFmpeg writer thread via a bounded queue.
- **Impact:** 2–4× rendering speedup on multi-core CPUs.
- **Complexity:** Medium — need thread-safe frame ordering and queue backpressure.

### 1.2 GPU-Accelerated Compositing (CuPy)
- **Current:** Pure NumPy CPU compositing. At 4K, per-frame cost balloons significantly.
- **Idea:** Use CuPy (drop-in NumPy replacement for CUDA) for Ken Burns cropping, alpha blending, and crossfade math.
- **Impact:** 5–10× speedup at 4K resolution on CUDA-capable GPUs.
- **Complexity:** Medium — CuPy is mostly API-compatible with NumPy.

### 1.3 OpenCV `addWeighted()` for Crossfade Blending
- **Current:** Manual float32 math for crossfade blending (allocate full float32 buffer per frame).
- **Idea:** Replace with OpenCV's optimized `cv2.addWeighted()` which uses SSE/AVX instructions.
- **Impact:** 20–30% faster crossfade blending with less memory allocation.
- **Complexity:** Low — drop-in replacement.

### 1.4 Parallel Image Upscaling
- **Current:** Images upscaled one-at-a-time sequentially.
- **Idea:** Upscale images in parallel (2–4 threads on CPU, or batch on GPU).
- **Impact:** A 20-segment project upscaling could drop from 10+ minutes to 3–4 minutes.
- **Complexity:** Medium — need to manage GPU memory carefully for batched inference.

### 1.5 ONNX Runtime for Upscaling
- **Current:** PyTorch only for Real-ESRGAN inference.
- **Idea:** Export Real-ESRGAN to ONNX and run via ONNX Runtime (same as Kokoro TTS).
- **Impact:** 2–3× faster CPU inference, eliminates PyTorch dependency for upscaling.
- **Complexity:** Medium — needs model export and validation.

### 1.6 Smart Upscaling Skip Logic
- **Current:** All images are upscaled regardless of size.
- **Idea:** If an image already exceeds the target render resolution, skip upscaling entirely.
- **Impact:** Saves 30–60+ seconds per high-res image that doesn't need upscaling.
- **Complexity:** Low — simple resolution check before upscaling.

---

## 2. Ken Burns & Motion Improvements

### 2.1 Easing Curves (Ease-In/Ease-Out)
- **Current:** Linear interpolation only — motion looks mechanical and robotic.
- **Idea:** Add configurable easing functions: ease-in, ease-out, ease-in-out (cubic bezier or sine).
- **Impact:** Dramatically more natural, professional-feeling camera motion.
- **Complexity:** Low — swap `lerp(t)` with `ease(t)` where `ease` applies a curve.

### 2.2 Multi-Keyframe Pan Paths
- **Current:** Only start → end positions (2-point interpolation).
- **Idea:** Define N keyframe positions per segment with timing percentages: `[{pos: 'top-left', t: 0}, {pos: 'center', t: 0.5}, {pos: 'bottom-right', t: 1}]`.
- **Impact:** Complex camera moves like "start wide, zoom to detail, pan across" — much more cinematic.
- **Complexity:** Medium — need keyframe interpolation with intermediate bezier segments.

### 2.3 Custom Pan Directions
- **Current:** 7 hardcoded direction presets selected by `segment_index % 7`.
- **Idea:** Allow per-segment custom pan direction, or a "random from pool" option, or user-defined sequences.
- **Impact:** More variety, less repetitive patterns in long videos.
- **Complexity:** Low — add a `ken_burns_direction` field to Segment model.

### 2.4 Zoom Level Control Per Segment
- **Current:** Single global `zoom_intensity` applied uniformly.
- **Idea:** Allow per-segment zoom intensity (e.g., dramatic scenes get 1.5× zoom, calm scenes get 1.1×).
- **Impact:** More expressive visual storytelling.
- **Complexity:** Low — add field to Segment, pass to Ken Burns function.

### 2.5 Focus-Point Selection
- **Current:** Ken Burns pans between predefined positions (center, corners).
- **Idea:** Allow user to click on the image to set a "focus point" that the camera gravitates toward.
- **Impact:** Camera always highlights the subject (face, key object) in the image.
- **Complexity:** Medium — need UI for focus point selection and interpolation math.

### 2.6 Parallax / Multi-Layer Ken Burns
- **Current:** Single image plane.
- **Idea:** Split image into foreground/background layers (either manually or via AI depth estimation) and animate each at different speeds for parallax effect.
- **Impact:** 2.5D effect that adds significant depth and production value.
- **Complexity:** High — requires depth estimation model or manual layer separation.

---

## 3. Transition System Overhaul

### 3.1 Transition Variety
- **Current:** Crossfade is the only transition.
- **Idea:** Implement a transition library:
  - **Slide** (left, right, up, down)
  - **Wipe** (horizontal, vertical, diagonal, radial)
  - **Zoom** (zoom in to next, zoom out from previous)
  - **Dissolve** (pixelated dissolve)
  - **Glitch** (digital glitch transition)
  - **Push** (push the current frame off-screen)
  - **Iris** (circular reveal)
- **Impact:** Much more professional production value, variety prevents monotony.
- **Complexity:** Medium per transition — each is a different blending algorithm.

### 3.2 Per-Segment Transition Selection
- **Current:** All transitions are identical (crossfade).
- **Idea:** Allow choosing transition type per segment, or a "random from set" mode.
- **Impact:** Creator control over pacing and visual rhythm.
- **Complexity:** Low (once transition library exists) — add field to Segment model.

### 3.3 Configurable Transition Duration Per Segment
- **Current:** Single global `transition_duration`.
- **Idea:** Per-segment override for transition duration (some cuts should be sharp, some slow).
- **Impact:** Better pacing control.
- **Complexity:** Low — add field, pass-through to compositor.

---

## 4. Video Composition Enhancements

### 4.1 Video Clip Segment Support (B-Roll)
- **Current:** Segments only support still images.
- **Idea:** Allow uploading short video clips per segment (MP4, WebM). The compositor plays the video clip instead of applying Ken Burns to a still image.
- **Impact:** Essential for professional content — explainer videos need screen recordings, demos, B-roll footage.
- **Complexity:** High — need FFmpeg decode pipeline, frame timing sync, audio handling.

### 4.2 Text Overlay Layer (Lower Thirds, Titles)
- **Current:** Only subtitles (narration text). No separate text overlay.
- **Idea:** Add a "text overlay" layer per segment for:
  - Titles / headlines
  - Lower thirds (name + title bars)
  - Call-to-action text ("Subscribe!", "Link in bio")
  - Key facts/stats
- **Impact:** Essential for educational/explainer/fact videos — not just stories.
- **Complexity:** Medium — needs new overlay rendering in compositor, UI for text placement.

### 4.3 Multiple Image Per Segment (Image Slideshow)
- **Current:** One image per segment.
- **Idea:** Allow 2–4 images per segment that cycle during the segment's audio duration.
- **Impact:** More visual variety per narration segment.
- **Complexity:** Medium — timing subdivision, Ken Burns per sub-image.

### 4.4 Picture-in-Picture Overlay
- **Current:** No PiP compositing during render (only in gallery playback).
- **Idea:** Allow overlaying a secondary image/video (e.g., a face cam, a product shot) in a corner during rendering.
- **Impact:** Useful for reaction-style or tutorial videos.
- **Complexity:** Medium — new overlay layer with configurable position, size, border.

### 4.5 Color Grading / LUT Support
- **Current:** No color post-processing.
- **Idea:** Apply a LUT (Look-Up Table) or color grading filter to all frames — warm, cold, vintage, cinematic.
- **Impact:** Gives videos a consistent professional "look". Huge for branding.
- **Complexity:** Medium — apply 3D LUT to each frame via OpenCV or NumPy.

### 4.6 Intro Sequence Support
- **Current:** Only outro video is supported.
- **Idea:** Add intro video support (branding intro that plays before the content).
- **Impact:** Every professional channel uses branded intros — essential for YouTube.
- **Complexity:** Low — mirror the existing outro implementation.

---

## 5. Encoding & Output Quality

### 5.1 Platform-Specific Encoding Presets
- **Current:** Single CRF 23, 8Mbps cap, generic H.264.
- **Idea:** Pre-configured presets:
  - **YouTube** → CRF 18, 20Mbps, H.264 High profile, -faststart
  - **TikTok** → CRF 20, 8Mbps, 9:16, max 10 min
  - **Instagram Reel** → CRF 20, 8Mbps, 9:16, max 90s
  - **Facebook** → CRF 21, 16Mbps, H.264, -faststart
  - **Twitter/X** → CRF 22, 6.4Mbps, max 2:20
- **Impact:** Optimized quality per platform without manual encoding knowledge.
- **Complexity:** Low — just FFmpeg argument presets.

### 5.2 Resolution-Aware Bitrate
- **Current:** Fixed 8Mbps cap regardless of resolution.
- **Idea:** Auto-scale bitrate based on resolution: 720p=5Mbps, 1080p=10Mbps, 4K=35Mbps.
- **Impact:** 4K videos won't be under-compressed, 720p won't waste bandwidth.
- **Complexity:** Low — simple lookup table.

### 5.3 H.265/HEVC and AV1 Support
- **Current:** H.264 (CPU or NVENC) only.
- **Idea:** Add H.265 (hevc_nvenc) and AV1 (libaom-av1 or SVT-AV1) encoding options.
- **Impact:** 40–50% smaller files at same quality. YouTube and TikTok accept both.
- **Complexity:** Low — FFmpeg codec arguments; AV1 is slower but much smaller.

### 5.4 Two-Pass Encoding Mode
- **Current:** Single-pass CRF.
- **Idea:** Optional two-pass VBR encoding for more consistent quality distribution.
- **Impact:** Better quality for videos with high-motion transitions mixed with static segments.
- **Complexity:** Low — two-pass FFmpeg flow.

### 5.5 Audio Bitrate Selection
- **Current:** 192kbps AAC fixed.
- **Idea:** Options: 128kbps (small), 192kbps (balanced), 320kbps (premium).
- **Impact:** Smaller files for TikTok/short content, higher quality for YouTube.
- **Complexity:** Low.

---

## 6. Caching & Incremental Rendering

### 6.1 Segment-Level Frame Cache
- **Current:** Re-rendering always starts from scratch.
- **Idea:** Cache Ken Burns frames per segment (content-addressed by image hash + Ken Burns params + resolution). On re-render, only regenerate changed segments.
- **Impact:** Re-renders after subtitle/audio-only changes drop from minutes to seconds.
- **Complexity:** High — cache invalidation, disk space management.

### 6.2 Preview Render Mode
- **Current:** Full render or nothing.
- **Idea:** "Quick Preview" mode: render at 480p, 15fps, no upscaling — generates in seconds.
- **Impact:** Fast iteration cycle for checking flow, timing, and subtitle quality.
- **Complexity:** Medium — parameterize render quality.

### 6.3 Single-Segment Preview
- **Current:** Must render entire video to see any output.
- **Idea:** Render a 3–5 second preview of a single segment (with Ken Burns, subtitle, audio).
- **Impact:** Near-instant feedback loop for tweaking individual segments.
- **Complexity:** Medium — need to isolate segment rendering from full pipeline.

### 6.4 Render Settings Diff
- **Current:** No way to know what changed since last render.
- **Idea:** Hash all render-affecting settings + segment data. Show "changed since last render" indicator.
- **Impact:** Users know whether a re-render is needed.
- **Complexity:** Low — hash comparison on settings and segment fields.

---

## 7. Architecture Cleanup

### 7.1 Remove Dead MoviePy Code
- **Current:** `apply_crossfade_transitions()` in video_renderer.py, `generate_subtitle_clips()` in subtitle_engine.py, and `apply_ken_burns()` MoviePy wrapper are all unused in the fast compositor path.
- **Idea:** Remove or deprecate these dead code paths.
- **Impact:** Cleaner codebase, reduced confusion for future development.
- **Complexity:** Low.

### 7.2 Replace MoviePy Audio with Pure FFmpeg
- **Current:** Audio mixing uses MoviePy's `CompositeAudioClip` and `concatenate_audioclips`.
- **Idea:** Replace with direct FFmpeg `amix`/`concat` filter graph for audio mixing.
- **Impact:** Eliminate MoviePy as a dependency entirely (major dependency reduction).
- **Complexity:** Medium — need to build correct FFmpeg audio filter graphs.

### 7.3 RenderConfig Dataclass
- **Current:** Settings read via scattered `getattr()` calls with fallbacks.
- **Idea:** Extract all render settings into a typed `RenderConfig` dataclass at the start of rendering.
- **Impact:** Catches attribute name typos at initialization, cleaner code, easier testing.
- **Complexity:** Low.

### 7.4 FFmpeg Filter Graph Builder
- **Current:** Manual string concatenation for FFmpeg filter graphs (fragile, hard to test).
- **Idea:** Use `ffmpeg-python` library or build a simple filter graph builder class.
- **Impact:** Safer filter graph construction, easier to add new transitions.
- **Complexity:** Medium.

### 7.5 Denoise Strength Implementation
- **Current:** `denoise_strength` parameter is accepted but not used in the upscaler architecture.
- **Idea:** Implement via the DNoise variant of Real-ESRGAN (mix between noisy and clean models).
- **Impact:** Proper denoise control as advertised in the UI.
- **Complexity:** Medium — need DNoise model weights and mixing logic.

---

## Priority Matrix

| Idea | Impact | Effort | Recommended Priority |
|------|--------|--------|---------------------|
| 2.1 Easing Curves | HIGH | LOW | 🔴 Do First |
| 3.1 Transition Variety | HIGH | MEDIUM | 🔴 Do First |
| 5.1 Platform Encoding Presets | HIGH | LOW | 🔴 Do First |
| 1.3 OpenCV Crossfade | MEDIUM | LOW | 🟡 Do Soon |
| 1.6 Smart Upscale Skip | MEDIUM | LOW | 🟡 Do Soon |
| 4.6 Intro Sequence | MEDIUM | LOW | 🟡 Do Soon |
| 5.2 Resolution-Aware Bitrate | MEDIUM | LOW | 🟡 Do Soon |
| 7.1 Remove Dead Code | LOW | LOW | 🟡 Do Soon |
| 7.3 RenderConfig Dataclass | LOW | LOW | 🟡 Do Soon |
| 6.2 Preview Render Mode | HIGH | MEDIUM | 🟡 Do Soon |
| 6.3 Single-Segment Preview | HIGH | MEDIUM | 🟡 Do Soon |
| 1.1 Multi-Threaded Frames | HIGH | MEDIUM | 🟠 Plan Ahead |
| 4.1 Video Clip Segments | HIGH | HIGH | 🟠 Plan Ahead |
| 4.2 Text Overlay Layer | HIGH | MEDIUM | 🟠 Plan Ahead |
| 2.2 Multi-Keyframe Paths | MEDIUM | MEDIUM | 🟠 Plan Ahead |
| 7.2 Replace MoviePy Audio | MEDIUM | MEDIUM | 🟠 Plan Ahead |
| 1.2 GPU Compositing (CuPy) | HIGH | MEDIUM | 🔵 Future |
| 2.6 Parallax Ken Burns | HIGH | HIGH | 🔵 Future |
| 4.5 Color Grading/LUT | MEDIUM | MEDIUM | 🔵 Future |
