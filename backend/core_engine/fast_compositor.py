"""
Fast Compositor — Direct-to-FFmpeg frame renderer.

Bypasses MoviePy's per-frame Pillow compositing pipeline with pure
NumPy alpha blending and direct FFmpeg subprocess piping.

MoviePy 2.x's ``CompositeVideoClip`` uses ``Image.alpha_composite``
for every overlay on every frame, creating full-frame RGBA canvases
and performing 4–8 NumPy↔Pillow conversions per frame.  At 1080p this
costs ~120 ms/frame for compositing alone plus ~80 ms/frame in
conversion overhead — totalling ~200+ ms/frame of pure waste.

This module replaces that pipeline with:

1. **Pre-rendered overlays** — subtitle text and logo are rasterised
   once into NumPy arrays with pre-multiplied alpha masks.
2. **Fast NumPy alpha blending** — each overlay is composited via
   vectorised NumPy operations on a small ROI (not the full frame),
   costing ~0.5–2 ms per overlay per frame.
3. **Direct FFmpeg pipe** — raw uint8 frames are written to FFmpeg's
   stdin via ``subprocess.Popen``, eliminating MoviePy's
   ``FFMPEG_VideoWriter`` overhead.

Expected per-frame cost: ~5–10 ms at 1080p (vs ~350 ms with MoviePy).
"""

import logging
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures for pre-rendered overlays
# ---------------------------------------------------------------------------

@dataclass
class OverlaySlice:
    """A pre-rendered overlay ready for fast NumPy alpha blending.

    All data is stored as uint8 NumPy arrays.  The alpha mask is stored
    as a float32 array normalised to [0, 1] for efficient blending.

    Attributes:
        rgb: ``(H, W, 3)`` uint8 array — the visible pixels.
        alpha: ``(H, W, 1)`` float32 array — normalised alpha mask.
        x: Horizontal position (left edge) in the output frame.
        y: Vertical position (top edge) in the output frame.
        start_time: When this overlay becomes visible (seconds).
        end_time: When this overlay disappears (seconds).
    """
    rgb: np.ndarray
    alpha: np.ndarray
    x: int
    y: int
    start_time: float
    end_time: float


def alpha_blit(frame: np.ndarray, overlay: OverlaySlice) -> None:
    """Composite *overlay* onto *frame* in-place using NumPy alpha blending.

    Only the ROI (region of interest) covered by the overlay is touched.
    The blending formula is the standard Porter-Duff "over" operation:

        out = fg * alpha + bg * (1 - alpha)

    This is ~50–100× faster than MoviePy's full-frame Pillow pipeline
    because:
      - No NumPy↔Pillow conversions
      - No full-frame RGBA canvas allocation
      - Only the overlay's bounding box is processed

    Args:
        frame: ``(H, W, 3)`` uint8 array — the target frame (modified
            in-place).
        overlay: Pre-rendered overlay with position and alpha.
    """
    oh, ow = overlay.rgb.shape[:2]
    fh, fw = frame.shape[:2]

    # Compute clipped ROI (overlay may extend beyond frame edges)
    x1 = max(overlay.x, 0)
    y1 = max(overlay.y, 0)
    x2 = min(overlay.x + ow, fw)
    y2 = min(overlay.y + oh, fh)

    if x2 <= x1 or y2 <= y1:
        return  # Overlay is entirely off-screen

    # Source region within the overlay
    sx1 = x1 - overlay.x
    sy1 = y1 - overlay.y
    sx2 = sx1 + (x2 - x1)
    sy2 = sy1 + (y2 - y1)

    # Extract the ROI from both frame and overlay
    roi = frame[y1:y2, x1:x2]
    fg = overlay.rgb[sy1:sy2, sx1:sx2]
    alpha = overlay.alpha[sy1:sy2, sx1:sx2]

    # Porter-Duff "over" in-place — vectorised NumPy
    # Using float32 for the blend, then clip back to uint8
    blended = (fg.astype(np.float32) * alpha
               + roi.astype(np.float32) * (1.0 - alpha))
    np.clip(blended, 0, 255, out=blended)
    frame[y1:y2, x1:x2] = blended.astype(np.uint8)


# ---------------------------------------------------------------------------
# Subtitle pre-renderer
# ---------------------------------------------------------------------------

def pre_render_subtitles(
    chunks: List[str],
    timings: List[Tuple[float, float]],
    resolution: Tuple[int, int],
    font_path: str,
    color: str,
    font_size: Optional[int] = None,
    position: str = "bottom",
    y_position: Optional[int] = None,
    stroke_color: str = "#000000",
    stroke_width: int = 2,
) -> List[OverlaySlice]:
    """Pre-render subtitle text into NumPy overlay slices.

    Uses OpenCV ``cv2.putText`` with anti-aliased rendering for fast
    text rasterisation.  Each chunk is rendered once and stored as an
    :class:`OverlaySlice` with exact timing and position data.

    For high-quality text with stroke (outline), we render the text
    twice: once with the stroke colour at a thicker line width, then
    again with the fill colour on top.

    Args:
        chunks: Ordered subtitle strings.
        timings: ``(start_time, duration)`` for each chunk.
        resolution: ``(width, height)`` of the output video.
        font_path: Path to a ``.ttf`` font file.
        color: Text fill colour as hex string (e.g. ``"#FFFFFF"``).
        font_size: Explicit font size in pixels.  ``None`` → auto.
        position: ``"bottom"``, ``"center"``, or ``"top"``.
        y_position: Manual vertical position override — top edge of the
            subtitle block in pixels from the top of the frame.
            When not ``None``, overrides the *position* keyword.
        stroke_color: Outline colour as hex string.
        stroke_width: Outline thickness in pixels.

    Returns:
        List of :class:`OverlaySlice` objects ready for alpha blending.
    """
    if not chunks or not timings:
        return []

    width, height = resolution

    # Compute effective font size
    eff_font_size = font_size if font_size and font_size > 0 else int(height / 18)

    # Parse colours
    fill_rgb = _hex_to_bgr(color)     # OpenCV uses BGR
    outline_bgr = _hex_to_bgr(stroke_color)

    # Use Pillow for high-quality text rendering with the actual TTF font
    # (OpenCV's putText only supports Hershey fonts which look terrible)
    from PIL import Image, ImageDraw, ImageFont

    try:
        pil_font = ImageFont.truetype(font_path, eff_font_size)
    except Exception:
        logger.warning("Cannot load font %s, falling back to default", font_path)
        pil_font = ImageFont.load_default()

    text_width = int(width * 0.9)  # 90% of frame width
    vert_margin = int(height * 0.08)
    pad_px = max(stroke_width * 4, eff_font_size // 4, 12)

    overlays: List[OverlaySlice] = []

    for chunk, (start_time, duration) in zip(chunks, timings):
        try:
            # Create transparent RGBA canvas for this subtitle
            # Use Pillow for text layout (wrapping) and rendering
            canvas = Image.new("RGBA", (text_width, height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(canvas)

            # Render stroke (outline) first
            fill_rgb_tuple = _hex_to_rgb_tuple(color)
            outline_rgb_tuple = _hex_to_rgb_tuple(stroke_color)

            # Draw text with anchor at top-center of canvas
            # Use multiline_text for word wrapping
            wrapped = _wrap_text(chunk, pil_font, text_width - 2 * pad_px)

            # Measure text bounds
            bbox = draw.multiline_textbbox(
                (0, 0), wrapped, font=pil_font,
                stroke_width=stroke_width,
            )
            text_h = bbox[3] - bbox[1] + 2 * pad_px
            text_w = min(bbox[2] - bbox[0] + 2 * pad_px, text_width)

            # Create tight canvas
            canvas = Image.new("RGBA", (text_w, text_h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(canvas)

            # Draw centred text
            tx = (text_w - (bbox[2] - bbox[0])) // 2
            ty = pad_px - bbox[1]

            # Draw stroke
            if stroke_width > 0:
                draw.multiline_text(
                    (tx, ty), wrapped, font=pil_font,
                    fill=outline_rgb_tuple + (255,),
                    stroke_width=stroke_width,
                    stroke_fill=outline_rgb_tuple + (255,),
                    align="center",
                )

            # Draw fill on top
            draw.multiline_text(
                (tx, ty), wrapped, font=pil_font,
                fill=fill_rgb_tuple + (255,),
                align="center",
            )

            # Convert to NumPy
            arr = np.array(canvas)  # (H, W, 4) RGBA
            rgb = arr[:, :, :3]        # (H, W, 3) RGB
            alpha = arr[:, :, 3:4].astype(np.float32) / 255.0  # (H, W, 1)

            # Apply max height constraint (40% of frame)
            clip_height = rgb.shape[0]
            max_clip_h = int(height * 0.40)
            if clip_height > max_clip_h and clip_height > 0:
                scale_factor = max_clip_h / clip_height
                new_h = int(clip_height * scale_factor)
                new_w = int(rgb.shape[1] * scale_factor)
                rgb = cv2.resize(rgb, (new_w, new_h), interpolation=cv2.INTER_AREA)
                alpha = cv2.resize(
                    alpha, (new_w, new_h), interpolation=cv2.INTER_AREA
                )
                if alpha.ndim == 2:
                    alpha = alpha[:, :, np.newaxis]
                clip_height = new_h

            # Compute position
            clip_w = rgb.shape[1]
            x_pos = (width - clip_w) // 2  # centred horizontally

            if y_position is not None:
                # Manual override — y_position is the TOP EDGE of the subtitle.
                # Used directly — no clip-height conversion needed.
                y_pos = y_position
            elif position == "top":
                y_pos = vert_margin
            elif position == "center":
                y_pos = (height - clip_height) // 2
            else:  # bottom
                y_pos = height - clip_height - vert_margin

            y_pos = max(0, min(y_pos, height - clip_height))

            overlays.append(OverlaySlice(
                rgb=rgb,
                alpha=alpha,
                x=x_pos,
                y=y_pos,
                start_time=start_time,
                end_time=start_time + duration,
            ))

        except Exception as exc:
            logger.warning(
                "Failed to pre-render subtitle '%.30s': %s", chunk, exc,
            )

    return overlays


def pre_render_logo(
    logo_file_path: str,
    resolution: Tuple[int, int],
    scale: float = 0.15,
    position_str: str = "bottom-right",
    opacity: float = 1.0,
    margin_px: int = 20,
) -> Optional[OverlaySlice]:
    """Pre-render logo watermark into a NumPy overlay slice.

    Args:
        logo_file_path: Path to the logo image file (supports RGBA).
        resolution: ``(width, height)`` of the output video.
        scale: Logo size as a fraction of frame width.
        position_str: Corner position string.
        opacity: Logo opacity (0.0–1.0).
        margin_px: Margin from frame edges in pixels.

    Returns:
        :class:`OverlaySlice` or ``None`` if loading fails.
    """
    from PIL import Image

    try:
        width, height = resolution
        pil_logo = Image.open(logo_file_path).convert("RGBA")

        # Compute target size
        target_w = int(width * scale)
        logo_aspect = pil_logo.width / pil_logo.height
        target_h = int(target_w / logo_aspect)

        pil_logo = pil_logo.resize((target_w, target_h), Image.LANCZOS)

        # Convert to NumPy
        arr = np.array(pil_logo)  # (H, W, 4) RGBA
        rgb = arr[:, :, :3]
        alpha = arr[:, :, 3:4].astype(np.float32) / 255.0

        if opacity < 1.0:
            alpha = alpha * opacity

        # Compute position
        if position_str == "top-left":
            x, y = margin_px, margin_px
        elif position_str == "top-right":
            x = width - target_w - margin_px
            y = margin_px
        elif position_str == "bottom-left":
            x = margin_px
            y = height - target_h - margin_px
        else:  # bottom-right
            x = width - target_w - margin_px
            y = height - target_h - margin_px

        # Logo is always visible (start=0, end=inf)
        return OverlaySlice(
            rgb=rgb,
            alpha=alpha,
            x=x,
            y=y,
            start_time=0.0,
            end_time=float("inf"),
        )

    except Exception as exc:
        logger.warning("Failed to pre-render logo: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Direct FFmpeg frame writer
# ---------------------------------------------------------------------------

class FFmpegFrameWriter:
    """Pipe raw frames directly to an FFmpeg subprocess.

    This bypasses MoviePy's ``FFMPEG_VideoWriter`` and its associated
    overhead (proglog callbacks, temp file management, etc.).

    Usage::

        writer = FFmpegFrameWriter(output_path, width, height, fps, ...)
        writer.start()
        for frame in frames:
            writer.write_frame(frame)
        writer.finish()
    """

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

    def _build_command(self) -> List[str]:
        """Build the FFmpeg command line."""
        cmd = [
            "ffmpeg", "-y",
            # Input: raw video frames from stdin
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-pix_fmt", "rgb24",
            "-s", f"{self.width}x{self.height}",
            "-r", str(self.fps),
            "-i", "pipe:0",
        ]

        # Audio input (if provided)
        if self.audio_path and os.path.isfile(self.audio_path):
            cmd.extend(["-i", self.audio_path])

        # Video encoding
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

        # Output
        cmd.extend([
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            self.output_path,
        ])

        return cmd

    def start(self) -> None:
        """Start the FFmpeg subprocess."""
        cmd = self._build_command()
        logger.info("FFmpeg command: %s", " ".join(cmd))
        self._proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def write_frame(self, frame: np.ndarray) -> None:
        """Write a single RGB frame to FFmpeg's stdin."""
        if self._proc is None or self._proc.stdin is None:
            raise RuntimeError("FFmpeg process not started")
        self._proc.stdin.write(frame.tobytes())

    def finish(self) -> Tuple[int, str]:
        """Close stdin and wait for FFmpeg to finish.

        Returns:
            ``(return_code, stderr_output)``
        """
        if self._proc is None:
            return (1, "Process not started")

        if self._proc.stdin:
            self._proc.stdin.close()

        stdout, stderr = self._proc.communicate()
        return (self._proc.returncode, stderr.decode("utf-8", errors="replace"))


# ---------------------------------------------------------------------------
# Main fast render function
# ---------------------------------------------------------------------------

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
    """Render video segments using fast NumPy compositing + direct FFmpeg pipe.

    This is the high-performance replacement for MoviePy's
    ``CompositeVideoClip.write_videofile()`` pipeline.

    Args:
        segment_data: List of dicts with keys: ``image_path``,
            ``audio_duration``, ``text_content``, ``sequence_index``.
        output_path: Path for the output MP4 file.
        resolution: ``(width, height)`` of the output video.
        fps: Frames per second.
        zoom_intensity: Ken Burns zoom factor.
        subtitle_settings: Dict with keys: ``enabled``, ``font``,
            ``color``, ``font_size``, ``position``.
        logo_settings: Optional dict with keys: ``file_path``,
            ``scale``, ``position``, ``opacity``, ``margin``.
            ``None`` if logo is disabled.
        audio_path: Path to the pre-exported audio file.
        use_nvenc: Whether to use NVIDIA NVENC GPU encoder.
        on_progress: Progress callback ``(current, total, message)``.
        crossfade_duration: Duration of crossfade transitions in seconds.
        inter_segment_silence: Silence gap appended after each segment.

    Returns:
        dict with ``frames_rendered``, ``render_time``, ``avg_ms_per_frame``.
    """
    from core_engine.ken_burns import (
        apply_ken_burns,
        load_and_prepare_image,
        calculate_crop_dimensions,
        get_pan_direction,
        get_start_end_coords,
        interpolate_position,
    )
    from core_engine.subtitle_engine import chunk_text, calculate_subtitle_timing

    width, height = resolution
    total_segments = len(segment_data)

    # ------------------------------------------------------------------
    # Phase 1: Pre-compute all segment frame generators + overlays
    # ------------------------------------------------------------------
    if on_progress:
        on_progress(0, 100, "Pre-rendering overlays…")

    # Pre-render logo (once)
    logo_overlay: Optional[OverlaySlice] = None
    if logo_settings:
        logo_overlay = pre_render_logo(
            logo_file_path=logo_settings["file_path"],
            resolution=resolution,
            scale=logo_settings.get("scale", 0.15),
            position_str=logo_settings.get("position", "bottom-right"),
            opacity=logo_settings.get("opacity", 1.0),
            margin_px=logo_settings.get("margin", 20),
        )
        if logo_overlay:
            logger.info("Logo pre-rendered: %dx%d", logo_overlay.rgb.shape[1], logo_overlay.rgb.shape[0])

    # Build segment descriptors
    segments_info: List[dict] = []

    for idx, seg in enumerate(segment_data):
        audio_duration = seg["audio_duration"]
        visual_duration = audio_duration + inter_segment_silence
        text_content = seg.get("text_content", "")

        # Pre-render subtitles for this segment
        sub_overlays: List[OverlaySlice] = []
        if subtitle_settings.get("enabled") and text_content.strip():
            chunks = chunk_text(text_content)
            timings = calculate_subtitle_timing(chunks, audio_duration)
            sub_overlays = pre_render_subtitles(
                chunks=chunks,
                timings=timings,
                resolution=resolution,
                font_path=subtitle_settings.get("font", ""),
                color=subtitle_settings.get("color", "#FFFFFF"),
                font_size=subtitle_settings.get("font_size"),
                position=subtitle_settings.get("position", "bottom"),
                y_position=subtitle_settings.get("y_position"),
            )

        # Prepare Ken Burns frame generator
        source_image = load_and_prepare_image(
            seg["image_path"], resolution, zoom_intensity,
        )
        src_h, src_w = source_image.shape[:2]
        crop_w, crop_h = calculate_crop_dimensions(width, height, zoom_intensity)
        start_name, end_name = get_pan_direction(seg["sequence_index"])
        (sx, sy), (ex, ey) = get_start_end_coords(
            start_name, end_name, src_w, src_h, crop_w, crop_h,
        )

        segments_info.append({
            "source_image": source_image,
            "crop_w": crop_w,
            "crop_h": crop_h,
            "start_coords": (sx, sy),
            "end_coords": (ex, ey),
            "visual_duration": visual_duration,
            "subtitle_overlays": sub_overlays,
        })

        logger.info(
            "Segment %d/%d pre-processed: %.2fs, %d subtitles",
            idx + 1, total_segments, visual_duration, len(sub_overlays),
        )

    # ------------------------------------------------------------------
    # Phase 2: Calculate total frames and timing
    # ------------------------------------------------------------------
    # Build a timeline of segments with crossfade overlaps
    segment_frame_ranges: List[Tuple[int, int]] = []  # (start_frame, end_frame)
    timeline_offset = 0.0

    for i, si in enumerate(segments_info):
        seg_start = timeline_offset
        seg_duration = si["visual_duration"]
        seg_frames_start = int(round(seg_start * fps))
        seg_frames_end = int(round((seg_start + seg_duration) * fps))

        segment_frame_ranges.append((seg_frames_start, seg_frames_end))

        # Next segment starts earlier by crossfade_duration (overlap)
        if i < total_segments - 1:
            timeline_offset += seg_duration - crossfade_duration
        else:
            timeline_offset += seg_duration

    total_frames = int(round(timeline_offset * fps))
    total_duration = timeline_offset

    logger.info(
        "Timeline: %d frames, %.2fs total (%d segments, %.1fs crossfade)",
        total_frames, total_duration, total_segments, crossfade_duration,
    )

    if on_progress:
        on_progress(5, 100, f"Rendering {total_frames} frames…")

    # ------------------------------------------------------------------
    # Phase 3: Start FFmpeg writer
    # ------------------------------------------------------------------
    writer = FFmpegFrameWriter(
        output_path=output_path,
        width=width,
        height=height,
        fps=fps,
        audio_path=audio_path,
        use_nvenc=use_nvenc,
        bitrate="8M",
    )
    writer.start()

    # ------------------------------------------------------------------
    # Phase 4: Generate and write frames
    # ------------------------------------------------------------------
    render_start = time.perf_counter()
    last_progress_pct = 5

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

        # Apply logo (on top of everything, no crossfade)
        if logo_overlay:
            alpha_blit(frame, logo_overlay)

        # Write frame to FFmpeg
        writer.write_frame(frame)

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

    # ------------------------------------------------------------------
    # Phase 5: Finish FFmpeg
    # ------------------------------------------------------------------
    if on_progress:
        on_progress(96, 100, "Finalizing video encoding…")

    returncode, stderr = writer.finish()

    render_time = time.perf_counter() - render_start
    avg_ms = (render_time / total_frames * 1000) if total_frames > 0 else 0

    if returncode != 0:
        logger.error("FFmpeg exited with code %d: %s", returncode, stderr[-2000:])
        raise RuntimeError(
            f"FFmpeg encoding failed (exit code {returncode}). "
            f"Last 500 chars of stderr: {stderr[-500:]}"
        )

    logger.info(
        "Fast render complete: %d frames in %.1fs (%.1f ms/frame, %.1f fps)",
        total_frames, render_time, avg_ms, total_frames / render_time if render_time > 0 else 0,
    )

    return {
        "frames_rendered": total_frames,
        "render_time": render_time,
        "avg_ms_per_frame": avg_ms,
    }


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def _hex_to_bgr(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex colour to BGR tuple (for OpenCV)."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return (b, g, r)


def _hex_to_rgb_tuple(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex colour to RGB tuple."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)
    return (int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16))


def _wrap_text(text: str, font, max_width: int) -> str:
    """Word-wrap text to fit within max_width pixels using the given font."""
    from PIL import ImageDraw, Image

    # Create a temporary draw context for measuring
    tmp = Image.new("RGBA", (1, 1))
    draw = ImageDraw.Draw(tmp)

    words = text.split()
    if not words:
        return text

    lines: List[str] = []
    current_line: List[str] = []

    for word in words:
        test_line = " ".join(current_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=font)
        line_width = bbox[2] - bbox[0]

        if line_width <= max_width or not current_line:
            current_line.append(word)
        else:
            lines.append(" ".join(current_line))
            current_line = [word]

    if current_line:
        lines.append(" ".join(current_line))

    return "\n".join(lines)
