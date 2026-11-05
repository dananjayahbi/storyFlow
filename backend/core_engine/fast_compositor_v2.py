"""Fast Compositor v2 — parallel, selectable alternative to v1.

This module is a *drop-in* companion to :mod:`core_engine.fast_compositor`.
The v1 pipeline remains the default and is intentionally left untouched.  v2
keeps the exact same visual contract (Ken Burns motion plan, subtitle overlays,
crossfades and logo) but:

1. Splits the timeline into contiguous frame ranges and renders them in
   separate processes, so all CPU cores participate in frame generation.
2. Skips the full-frame ``float32`` blend on frames where only one segment is
   visible (the common case).  v1 performs that conversion for every frame.
3. Encodes each chunk with the existing ``FFmpegFrameWriter`` (NVENC when
   available) and concatenates the chunks losslessly with FFmpeg's concat
   demuxer.

Because each chunk uses the global frame index, the result is identical to v1
for the same input.  ``fast_render_segments_v2`` mirrors the v1 signature so
the renderer can choose between the two engines with a single switch.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Callable, List, Optional, Tuple

import cv2
import numpy as np

from core_engine.fast_compositor import (
    FFmpegFrameWriter,
    OverlaySlice,
    alpha_blit,
    pre_render_logo,
    pre_render_subtitles,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Timeline helper (kept in sync with v1)
# ---------------------------------------------------------------------------

def _build_timeline(
    segment_data: List[dict],
    fps: int,
    crossfade_duration: float,
    inter_segment_silence: float,
) -> Tuple[List[Tuple[int, int]], List[float], int, float]:
    """Return frame ranges, visual durations, total frames and duration."""
    ranges: List[Tuple[int, int]] = []
    visual_durations: List[float] = []
    offset = 0.0
    total_segments = len(segment_data)
    for index, seg in enumerate(segment_data):
        duration = seg["audio_duration"] + inter_segment_silence
        visual_durations.append(duration)
        start = int(round(offset * fps))
        end = int(round((offset + duration) * fps))
        ranges.append((start, end))
        if index < total_segments - 1:
            offset += duration - crossfade_duration
        else:
            offset += duration
    return ranges, visual_durations, int(round(offset * fps)), offset


def _worker_count(total_frames: int, fps: int, use_nvenc: bool) -> int:
    """Choose a safe number of parallel workers for this machine/encoder."""
    requested = os.environ.get("STORYFLOW_V2_WORKERS")
    if requested:
        try:
            workers = int(requested)
        except ValueError:
            workers = os.cpu_count() or 4
    else:
        workers = os.cpu_count() or 4
    # Each worker runs its own OpenCV/FFmpeg threads, so using every logical
    # core oversubscribes the machine.  Four chunks were the best balance in
    # local 1080p benchmarks; STORYFLOW_V2_WORKERS can override it.
    workers = min(workers, 4)
    # Keep chunks at least one second long so process startup and encoding
    # overhead never dominate.
    max_useful = max(1, total_frames // max(1, fps))
    return max(1, min(workers, max_useful))


# ---------------------------------------------------------------------------
# Per-process chunk renderer
# ---------------------------------------------------------------------------

def _render_chunk(job: dict) -> dict:
    """Render one contiguous frame range to an encoded MP4 chunk.

    The job dictionary only contains picklable primitives and file paths, so
    it can cross the process boundary on Windows/macOS (spawn start method).
    """
    from core_engine.ken_burns import (
        load_and_prepare_image,
        normalise_focus_areas,
        plan_ken_burns_motion,
        sample_ken_burns_motion,
    )
    from core_engine.subtitle_engine import chunk_and_time

    width, height = job["resolution"]
    fps = job["fps"]
    start_frame = job["start_frame"]
    end_frame = job["end_frame"]
    segment_data = job["segment_data"]
    frame_ranges = job["segment_frame_ranges"]
    total_segments = len(segment_data)
    crossfade_duration = job["crossfade_duration"]
    zoom_intensity = job["zoom_intensity"]
    subtitle_settings = job["subtitle_settings"]

    # Prepare only the segments that overlap this frame range.  Crossfade
    # frames fall inside both neighbouring ranges, so both are included.
    needed = [
        index
        for index, (seg_start, seg_end) in enumerate(frame_ranges)
        if seg_end > start_frame and seg_start < end_frame
    ]

    segments_info: dict[int, dict] = {}
    for index in needed:
        seg = segment_data[index]
        audio_duration = seg["audio_duration"]
        visual_duration = audio_duration + job["inter_segment_silence"]
        text_content = seg.get("text_content", "")

        sub_overlays: List[OverlaySlice] = []
        if subtitle_settings.get("enabled") and text_content.strip():
            chunks, timings = chunk_and_time(
                text_content,
                audio_duration,
                seg.get("audio_timings"),
            )
            sub_overlays = pre_render_subtitles(
                chunks=chunks,
                timings=timings,
                resolution=(width, height),
                font_path=subtitle_settings.get("font", ""),
                color=subtitle_settings.get("color", "#FFFFFF"),
                font_size=subtitle_settings.get("font_size"),
                position=subtitle_settings.get("position", "bottom"),
                y_position=subtitle_settings.get("y_position"),
            )

        source_image = load_and_prepare_image(
            seg["image_path"], (width, height), zoom_intensity,
            seg.get("focus_x", 0.5), seg.get("focus_y", 0.5),
        )
        src_h, src_w = source_image.shape[:2]
        focus_areas = normalise_focus_areas(
            seg.get("focus_areas")
        ) or normalise_focus_areas(seg.get("focus_area"))
        motion_plan = plan_ken_burns_motion(
            segment_index=seg["sequence_index"],
            duration=visual_duration,
            source_width=src_w,
            source_height=src_h,
            output_width=width,
            output_height=height,
            zoom_intensity=zoom_intensity,
            focus_area=focus_areas[0] if focus_areas else None,
        )
        segments_info[index] = {
            "source_image": source_image,
            "motion_plan": motion_plan,
            "visual_duration": visual_duration,
            "subtitle_overlays": sub_overlays,
        }

    logo_overlay: Optional[OverlaySlice] = None
    logo_settings = job.get("logo_settings")
    if logo_settings:
        logo_overlay = pre_render_logo(
            logo_file_path=logo_settings["file_path"],
            resolution=(width, height),
            scale=logo_settings.get("scale", 0.15),
            position_str=logo_settings.get("position", "bottom-right"),
            opacity=logo_settings.get("opacity", 1.0),
            margin_px=logo_settings.get("margin", 20),
        )

    writer = FFmpegFrameWriter(
        output_path=job["output_path"],
        width=width,
        height=height,
        fps=fps,
        audio_path=None,
        use_nvenc=job["use_nvenc"],
        bitrate=job.get("bitrate", "10M"),
    )
    writer.start()

    fade_frames = int(crossfade_duration * fps)
    try:
        for frame_idx in range(start_frame, end_frame):
            active: list[tuple[int, np.ndarray, float]] = []

            for index in needed:
                seg_start, seg_end = frame_ranges[index]
                if frame_idx < seg_start or frame_idx >= seg_end:
                    continue

                info = segments_info[index]
                seg_duration = info["visual_duration"]
                t_local = (frame_idx - seg_start) / fps

                weight = 1.0
                if total_segments > 1:
                    if index > 0:
                        frames_since_start = frame_idx - seg_start
                        if frames_since_start < fade_frames:
                            weight = frames_since_start / fade_frames
                    if index < total_segments - 1:
                        frames_until_end = seg_end - frame_idx - 1
                        if frames_until_end < fade_frames:
                            weight = min(weight, frames_until_end / fade_frames)

                x, y, crop_w, crop_h = sample_ken_burns_motion(
                    info["motion_plan"], t_local, seg_duration,
                )
                crop = info["source_image"][
                    y: y + crop_h,
                    x: x + crop_w,
                ]
                if crop_w == width and crop_h == height:
                    seg_frame = np.ascontiguousarray(crop)
                else:
                    is_downscale = crop_w > width or crop_h > height
                    interp = (
                        cv2.INTER_AREA if is_downscale else cv2.INTER_LINEAR
                    )
                    seg_frame = cv2.resize(
                        crop, (width, height), interpolation=interp,
                    )

                for overlay in info["subtitle_overlays"]:
                    if overlay.start_time <= t_local < overlay.end_time:
                        alpha_blit(seg_frame, overlay)

                active.append((index, seg_frame, weight))

            if not active:
                frame = np.zeros((height, width, 3), dtype=np.uint8)
            elif len(active) == 1 and active[0][2] >= 0.999:
                # Fast path: no crossfade, so skip the full-frame float blend.
                frame = active[0][1]
            else:
                blended = np.zeros((height, width, 3), dtype=np.float32)
                total_weight = 0.0
                for _index, seg_frame, weight in active:
                    blended += seg_frame.astype(np.float32) * weight
                    total_weight += weight
                if total_weight > 0:
                    frame = np.clip(
                        blended / total_weight, 0, 255,
                    ).astype(np.uint8)
                else:
                    # Both neighbours can have zero weight on the exact
                    # crossfade boundary; show the outgoing frame instead of
                    # dividing by zero.
                    frame = active[0][1]

            if logo_overlay:
                alpha_blit(frame, logo_overlay)

            writer.write_frame(frame)
    finally:
        returncode, stderr = writer.finish()

    if returncode != 0:
        logger.error(
            "v2 chunk %s failed (exit %d): %s",
            job["output_path"], returncode, stderr[-1000:],
        )
        raise RuntimeError(
            f"v2 chunk encoding failed (exit code {returncode}). "
            f"Last 500 chars of stderr: {stderr[-500:]}"
        )

    return {
        "path": job["output_path"],
        "frames": end_frame - start_frame,
    }


# ---------------------------------------------------------------------------
# Public entry point (mirrors fast_render_segments)
# ---------------------------------------------------------------------------

def fast_render_segments_v2(
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
    """Render the timeline with the parallel v2 engine.

    Args:
        segment_data: Same shape as :func:`fast_compositor.fast_render_segments`.
        output_path: Final MP4 path (with the mixed audio track).
        resolution: ``(width, height)`` output size.
        fps: Frames per second.
        zoom_intensity: Ken Burns zoom factor.
        subtitle_settings: Subtitle dict from the renderer.
        logo_settings: Optional logo dict.
        audio_path: Pre-exported audio track.
        use_nvenc: Use NVIDIA NVENC for chunk encoding.
        on_progress: ``(current, total, message)`` callback.
        crossfade_duration: Crossfade seconds between segments.
        inter_segment_silence: Silence appended to each segment.

    Returns:
        Stats dict with ``frames_rendered``, ``render_time``,
        ``avg_ms_per_frame``, ``workers`` and ``pipeline``.
    """
    if not segment_data:
        raise ValueError("fast_render_segments_v2 requires at least one segment")

    frame_ranges, _visual_durations, total_frames, total_duration = (
        _build_timeline(
            segment_data, fps, crossfade_duration, inter_segment_silence,
        )
    )
    if total_frames <= 0:
        raise ValueError("Timeline produced zero frames")

    workers = _worker_count(total_frames, fps, use_nvenc)
    boundaries = [
        int(round(index * total_frames / workers))
        for index in range(workers + 1)
    ]
    # Remove duplicate boundaries from very short timelines.
    boundaries = sorted(set(boundaries))
    workers = len(boundaries) - 1

    logger.info(
        "v2 render: %d frames, %.2fs, %d worker(s), NVENC=%s",
        total_frames, total_duration, workers, use_nvenc,
    )
    if on_progress:
        on_progress(
            5, 100,
            f"Pipeline v2: rendering {total_frames} frames "
            f"with {workers} worker(s)…",
        )

    temp_dir = tempfile.mkdtemp(prefix="storyflow-v2-")
    jobs: List[dict] = []
    for index, (start, end) in enumerate(
        zip(boundaries[:-1], boundaries[1:])
    ):
        jobs.append({
            "segment_data": segment_data,
            "segment_frame_ranges": frame_ranges,
            "total_segments": len(segment_data),
            "resolution": resolution,
            "fps": fps,
            "zoom_intensity": zoom_intensity,
            "subtitle_settings": subtitle_settings,
            "logo_settings": logo_settings,
            "inter_segment_silence": inter_segment_silence,
            "crossfade_duration": crossfade_duration,
            "start_frame": start,
            "end_frame": end,
            "output_path": os.path.join(temp_dir, f"chunk_{index:03d}.mp4"),
            "use_nvenc": use_nvenc,
            "bitrate": "10M",
        })

    render_start = time.perf_counter()
    chunk_paths: List[Optional[str]] = [None] * len(jobs)
    completed = 0

    try:
        if len(jobs) == 1:
            result = _render_chunk(jobs[0])
            chunk_paths[0] = result["path"]
        else:
            with ProcessPoolExecutor(max_workers=len(jobs)) as pool:
                futures = {
                    pool.submit(_render_chunk, job): index
                    for index, job in enumerate(jobs)
                }
                try:
                    for future in as_completed(futures):
                        index = futures[future]
                        try:
                            result = future.result()
                        except Exception:
                            if not use_nvenc:
                                raise
                            # Some consumer drivers allow fewer concurrent
                            # NVENC sessions than advertised. Retry this chunk
                            # sequentially with the CPU encoder instead of
                            # failing the whole render.
                            logger.warning(
                                "v2 NVENC chunk %d failed; retrying with "
                                "libx264", index, exc_info=True,
                            )
                            fallback_job = dict(jobs[index])
                            fallback_job["use_nvenc"] = False
                            result = _render_chunk(fallback_job)
                        chunk_paths[index] = result["path"]
                        completed += 1
                        if on_progress:
                            pct = 5 + int((completed / len(jobs)) * 85)
                            on_progress(
                                pct, 100,
                                f"Pipeline v2: rendered chunk "
                                f"{completed}/{len(jobs)}…",
                            )
                except BaseException:
                    for pending in futures:
                        pending.cancel()
                    pool.shutdown(wait=False, cancel_futures=True)
                    raise

        missing = [path for path in chunk_paths if not path]
        if missing:
            raise RuntimeError("Pipeline v2 did not produce all chunks")

        if on_progress:
            on_progress(92, 100, "Pipeline v2: combining chunks…")

        if len(chunk_paths) == 1:
            concat_input = ["-i", str(chunk_paths[0])]
        else:
            list_path = os.path.join(temp_dir, "concat.txt")
            with open(list_path, "w", encoding="utf-8") as handle:
                for path in chunk_paths:
                    safe = str(path).replace("'", "'\\''")
                    handle.write(f"file '{safe}'\n")
            concat_input = [
                "-f", "concat", "-safe", "0", "-i", list_path,
            ]

        cmd = ["ffmpeg", "-y", *concat_input]
        audio_available = bool(audio_path and os.path.isfile(audio_path))
        if audio_available:
            cmd.extend(["-i", audio_path])
        cmd.extend(["-map", "0:v:0"])
        if audio_available:
            cmd.extend(["-map", "1:a:0", "-c:a", "aac", "-b:a", "192k"])
        cmd.extend([
            "-c:v", "copy",
            "-shortest",
            "-movflags", "+faststart",
            output_path,
        ])
        logger.info("v2 concat command: %s", " ".join(cmd))
        completed_proc = subprocess.run(
            cmd, capture_output=True, text=True, check=False,
        )
        if completed_proc.returncode != 0:
            logger.error(
                "v2 concat failed (exit %d): %s",
                completed_proc.returncode, completed_proc.stderr[-2000:],
            )
            raise RuntimeError(
                "Pipeline v2 concat failed: "
                + completed_proc.stderr[-500:]
            )
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    render_time = time.perf_counter() - render_start
    avg_ms = (render_time / total_frames * 1000) if total_frames else 0
    logger.info(
        "v2 complete: %d frames in %.1fs (%.1f ms/frame, %d workers)",
        total_frames, render_time, avg_ms, workers,
    )

    if on_progress:
        on_progress(96, 100, "Finalizing video encoding…")

    return {
        "frames_rendered": total_frames,
        "render_time": render_time,
        "avg_ms_per_frame": avg_ms,
        "pipeline": "v2",
        "workers": workers,
    }
