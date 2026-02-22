"""
StoryFlow Video Renderer Module.

Orchestrates MoviePy-based video assembly from image and audio segments.
Loads each segment's image and audio, applies Ken Burns (zoom-and-pan)
animation to each cover image, concatenates them in order, and exports
the final MP4 file.

This module is a pure rendering function — it does NOT update project
status in the database.  Status management is handled by the API layer
in SubPhase 04.03.
"""

import logging
import os
from pathlib import Path
from typing import Callable, Optional

from core_engine import render_utils
from core_engine.ken_burns import apply_ken_burns
from core_engine.subtitle_engine import create_subtitles_for_segment

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MoviePy version-safe imports
# ---------------------------------------------------------------------------

try:
    # MoviePy 1.x — everything lives under moviepy.editor
    from moviepy.editor import (  # type: ignore[import-untyped]
        AudioFileClip,
        CompositeVideoClip,
        concatenate_videoclips,
    )
except ImportError:
    # MoviePy 2.x — direct imports from moviepy
    from moviepy import (  # type: ignore[import-untyped]
        AudioFileClip,
        CompositeVideoClip,
        concatenate_videoclips,
    )


# Type alias for the progress callback
ProgressCallback = Optional[Callable[[int, int, str], None]]


def render_project(
    project_id: str,
    on_progress: ProgressCallback = None,
) -> dict:
    """
    Render a project's segments into a single MP4 video file.

    Each segment must have both an ``image_file`` and an ``audio_file``.
    The image is resized to the project's resolution using cover mode,
    displayed for the duration of its audio clip, and then all segment
    clips are concatenated in ``sequence_index`` order.

    Args:
        project_id: UUID string of the project to render.
        on_progress: Optional callback ``(current, total, description)``
            invoked after each segment and before export.

    Returns:
        dict: ``{"output_path": str, "duration": float, "file_size": int}``

    Raises:
        RuntimeError: If FFmpeg is not installed.
        ValueError: If any segment is missing an image or audio file.
        Exception: Re-raises any MoviePy or I/O error after cleanup.
    """
    # Import Django models lazily to keep this module importable
    # outside a Django context during early development.
    from api.models import Project, Segment  # noqa: E402

    # GlobalSettings may not exist yet; import separately to handle
    # gracefully if the model or table is missing.
    try:
        from api.models import GlobalSettings  # noqa: E402
    except ImportError:
        GlobalSettings = None  # type: ignore[assignment,misc]

    logger.info("=== Render started for project %s ===", project_id)

    # ------------------------------------------------------------------
    # A. FFmpeg availability check
    # ------------------------------------------------------------------
    if not render_utils.check_ffmpeg():
        raise RuntimeError(render_utils.get_ffmpeg_error_message())

    # ------------------------------------------------------------------
    # B. Load project from database
    # ------------------------------------------------------------------
    project = Project.objects.get(id=project_id)
    logger.info("Project loaded: '%s'", project.title)

    # ------------------------------------------------------------------
    # C. Read resolution and framerate settings
    # ------------------------------------------------------------------
    res_width = project.resolution_width
    res_height = project.resolution_height
    fps = project.framerate
    logger.info("Resolution: %dx%d @ %d fps", res_width, res_height, fps)

    # ------------------------------------------------------------------
    # C2. Read zoom intensity from GlobalSettings
    # ------------------------------------------------------------------
    _DEFAULT_ZOOM = 1.3
    zoom_intensity = _DEFAULT_ZOOM

    if GlobalSettings is not None:
        try:
            gs = GlobalSettings.objects.first()

            if gs is not None:
                val = getattr(gs, "zoom_intensity", None)

                if val is None:
                    # zoom_intensity attribute missing or None — use default.
                    logger.warning(
                        "GlobalSettings zoom_intensity is None. "
                        "Falling back to default %.1f.",
                        _DEFAULT_ZOOM,
                    )
                elif val <= 0:
                    # Invalid: zoom_intensity must be positive.
                    logger.warning(
                        "Invalid zoom_intensity value in GlobalSettings: %s "
                        "(must be > 0). Falling back to default %.1f.",
                        val,
                        _DEFAULT_ZOOM,
                    )
                else:
                    # Valid positive value — accept it.
                    zoom_intensity = float(val)

                    # Log atypical but technically valid ranges.
                    if zoom_intensity < 1.0 or zoom_intensity > 2.0:
                        logger.debug(
                            "zoom_intensity %.2f is outside the typical "
                            "range (1.0–2.0). Accepting as-is.",
                            zoom_intensity,
                        )
            else:
                # GlobalSettings table exists but has no rows.
                logger.warning(
                    "No GlobalSettings row found in the database. "
                    "Using default zoom_intensity=%.1f.",
                    _DEFAULT_ZOOM,
                )
        except Exception as gs_err:
            logger.warning(
                "Could not read GlobalSettings: %s. "
                "Using default zoom_intensity=%.1f.",
                gs_err,
                _DEFAULT_ZOOM,
            )

    logger.info("Zoom intensity for render: %.2f", zoom_intensity)

    # ------------------------------------------------------------------
    # C3. Read subtitle settings from GlobalSettings
    # ------------------------------------------------------------------
    subtitle_font = None
    subtitle_color = "#FFFFFF"

    if GlobalSettings is not None:
        try:
            gs_sub = GlobalSettings.objects.first()
            if gs_sub is not None:
                raw_font = getattr(gs_sub, "subtitle_font", "") or ""
                if raw_font.strip():
                    subtitle_font = raw_font.strip()
                raw_color = getattr(gs_sub, "subtitle_color", "") or ""
                if raw_color.strip():
                    subtitle_color = raw_color.strip()
        except Exception as sub_err:
            logger.warning(
                "Could not read subtitle settings from GlobalSettings: %s. "
                "Using defaults.",
                sub_err,
            )

    # Resolve font name to a filesystem path
    resolved_font = render_utils.get_font_path(subtitle_font)
    logger.info(
        "Subtitle settings — font: %s (resolved: %s), color: %s",
        subtitle_font, resolved_font, subtitle_color,
    )

    # ------------------------------------------------------------------
    # C4. Check ImageMagick availability (once, before loop)
    # ------------------------------------------------------------------
    imagemagick_available = render_utils.check_imagemagick()
    if not imagemagick_available:
        logger.warning(
            "ImageMagick not available — subtitle overlay will be skipped "
            "for all segments."
        )

    # Warnings accumulator for the result dict
    warnings: list[str] = []

    # ------------------------------------------------------------------
    # D. Query segments in order
    # ------------------------------------------------------------------
    segments = list(
        Segment.objects.filter(project=project).order_by("sequence_index")
    )
    total_segments = len(segments)

    if total_segments == 0:
        raise ValueError(
            f"Project '{project.title}' has no segments to render."
        )

    logger.info("Found %d segment(s) to render.", total_segments)

    # ------------------------------------------------------------------
    # E. Validate every segment has image + audio
    # ------------------------------------------------------------------
    incomplete = []
    for seg in segments:
        missing = []
        if not seg.image_file:
            missing.append("image")
        if not seg.audio_file:
            missing.append("audio")
        if missing:
            incomplete.append(
                f"Segment {seg.id} (index {seg.sequence_index}): "
                f"missing {', '.join(missing)}"
            )

    if incomplete:
        raise ValueError(
            "Cannot render — the following segments are incomplete:\n"
            + "\n".join(incomplete)
        )

    # ------------------------------------------------------------------
    # F. Determine output path
    # ------------------------------------------------------------------
    output_path = render_utils.get_output_path(str(project_id))
    logger.info("Output path: %s", output_path)

    # ------------------------------------------------------------------
    # Rendering pipeline (with proper cleanup)
    # ------------------------------------------------------------------
    clips: list = []
    audio_clips: list = []
    composite_clip = None

    try:
        # --------------------------------------------------------------
        # G. Build a clip for each segment
        # --------------------------------------------------------------
        for idx, segment in enumerate(segments, start=1):
            seg_label = (
                f"Segment {idx}/{total_segments} "
                f"(index {segment.sequence_index})"
            )
            logger.info("Processing %s", seg_label)

            # Step 1: Verify file existence before loading
            audio_path = segment.audio_file.path
            image_path = segment.image_file.path

            if not os.path.exists(audio_path):
                raise FileNotFoundError(
                    f"Audio file missing for {seg_label} "
                    f"(segment ID {segment.id}): {audio_path}"
                )
            if not os.path.exists(image_path):
                raise FileNotFoundError(
                    f"Image file missing for {seg_label} "
                    f"(segment ID {segment.id}): {image_path}"
                )

            # Step 2: Load audio clip with error handling
            try:
                audio_clip = AudioFileClip(audio_path)
            except Exception as exc:
                logger.error(
                    "Failed to load audio for %s (ID %s): %s",
                    seg_label, segment.id, exc,
                )
                raise RuntimeError(
                    f"Corrupt or unreadable audio file for {seg_label} "
                    f"(segment ID {segment.id}): {audio_path}"
                ) from exc

            audio_clips.append(audio_clip)
            audio_duration = audio_clip.duration
            logger.debug(
                "  Audio loaded: %s (%.2fs)", audio_path, audio_duration
            )

            # Duration synchronization checks
            # Use audio_clip.duration as the authoritative source (not DB)
            if audio_duration is None or audio_duration <= 0:
                logger.warning(
                    "Skipping %s (ID %s): audio duration is zero or negative "
                    "(%.4f). This would cause MoviePy errors.",
                    seg_label, segment.id, audio_duration or 0,
                )
                continue

            if audio_duration > 60:
                logger.warning(
                    "%s (ID %s) has unusually long audio duration: %.2fs. "
                    "This may indicate a content issue.",
                    seg_label, segment.id, audio_duration,
                )

            # Cross-validate against database duration
            if segment.audio_duration is not None:
                diff = abs(audio_duration - segment.audio_duration)
                if diff > 0.1:
                    logger.warning(
                        "%s (ID %s): audio file duration (%.3fs) differs "
                        "from database value (%.3fs) by %.3fs. "
                        "Using file duration as authoritative.",
                        seg_label, segment.id,
                        audio_duration, segment.audio_duration, diff,
                    )

            # Step 3: Create Ken Burns animated clip with error handling
            try:
                ken_burns_clip = apply_ken_burns(
                    image_path=image_path,
                    duration=audio_duration,
                    resolution=(res_width, res_height),
                    zoom_intensity=zoom_intensity,
                    fps=fps,
                    segment_index=segment.sequence_index,
                )
            except Exception as exc:
                logger.error(
                    "Failed to create Ken Burns clip for %s (ID %s): %s",
                    seg_label, segment.id, exc,
                )
                raise RuntimeError(
                    f"Ken Burns effect failed for {seg_label} "
                    f"(segment ID {segment.id}): {image_path}"
                ) from exc

            logger.debug(
                "  Ken Burns clip created: %s (direction index %d)",
                image_path, segment.sequence_index,
            )

            # Step 3b: Composite subtitles onto Ken Burns clip
            text_content = getattr(segment, "text_content", None) or ""
            if imagemagick_available and text_content.strip():
                try:
                    subtitle_clips = create_subtitles_for_segment(
                        text_content=text_content,
                        audio_duration=audio_duration,
                        resolution=(res_width, res_height),
                        font=resolved_font,
                        color=subtitle_color,
                    )
                    if subtitle_clips:
                        ken_burns_clip = CompositeVideoClip(
                            [ken_burns_clip] + subtitle_clips
                        ).with_duration(audio_duration)
                        logger.debug(
                            "  Subtitles composited: %d clip(s) for %s",
                            len(subtitle_clips), seg_label,
                        )
                    else:
                        logger.debug(
                            "  No subtitle clips generated for %s",
                            seg_label,
                        )
                except Exception as sub_exc:
                    warn_msg = (
                        f"Subtitle generation failed for {seg_label} "
                        f"(segment ID {segment.id}): {sub_exc}"
                    )
                    logger.warning(warn_msg)
                    warnings.append(warn_msg)
                    # Continue rendering without subtitles for this segment
            elif not text_content.strip():
                logger.debug(
                    "  No text_content for %s — skipping subtitles.",
                    seg_label,
                )

            # Step 4: Pair Ken Burns clip with audio
            ken_burns_clip = ken_burns_clip.with_audio(audio_clip)

            # Step 5: Append and continue
            clips.append(ken_burns_clip)

            # Progress callback
            if on_progress:
                subtitle_note = ""
                if imagemagick_available and text_content.strip():
                    subtitle_note = " + subtitles composited"
                on_progress(
                    idx,
                    total_segments,
                    f"Ken Burns applied to {seg_label}{subtitle_note}",
                )

        # --------------------------------------------------------------
        # H. Concatenate all clips
        # --------------------------------------------------------------
        # Validate clips list is not empty (all segments may have been
        # skipped due to zero-duration audio)
        if not clips:
            raise ValueError("No segments to render")

        logger.info("Concatenating %d clip(s)...", len(clips))
        composite_clip = concatenate_videoclips(clips, method="compose")

        # Validate concatenation result
        if composite_clip.duration is None or composite_clip.duration <= 0:
            raise ValueError(
                "Concatenation produced a clip with zero or negative duration."
            )

        logger.info(
            "Concatenation complete: %d clip(s), total duration %.2fs",
            len(clips), composite_clip.duration,
        )

        # --------------------------------------------------------------
        # I. Progress: exporting
        # --------------------------------------------------------------
        if on_progress:
            on_progress(
                total_segments,
                total_segments,
                "Exporting final MP4...",
            )

        # --------------------------------------------------------------
        # J. Export to MP4
        # --------------------------------------------------------------
        logger.info("Exporting to %s ...", output_path)
        try:
            composite_clip.write_videofile(
                output_path,
                codec="libx264",
                audio_codec="aac",
                bitrate="8000k",
                fps=fps,
                logger=None,  # Suppress MoviePy's console progress bar
            )
        except (IOError, RuntimeError) as export_err:
            logger.error("Export failed: %s", export_err)
            # Delete partial/unusable output file
            try:
                if os.path.exists(output_path):
                    os.remove(output_path)
                    logger.info("Removed partial output file: %s", output_path)
            except OSError:
                pass
            raise RuntimeError(
                f"Video export failed for project {project_id}: {export_err}"
            ) from export_err

        # --------------------------------------------------------------
        # K. Verify output and capture duration
        # --------------------------------------------------------------
        if not os.path.exists(output_path):
            raise RuntimeError(
                f"Export completed but output file not found: {output_path}"
            )

        total_duration = composite_clip.duration

        # --------------------------------------------------------------
        # M. Get output file size
        # --------------------------------------------------------------
        file_size = os.path.getsize(output_path)
        file_size_mb = file_size / (1024 * 1024)

        logger.info(
            "=== Render complete: %.2fs, %.1f MB (%s bytes), %s ===",
            total_duration,
            file_size_mb,
            f"{file_size:,}",
            output_path,
        )

        # --------------------------------------------------------------
        # N. Return result dict
        # --------------------------------------------------------------
        result = {
            "output_path": output_path,
            "duration": total_duration,
            "file_size": file_size,
            "warnings": warnings,
        }

        if warnings:
            logger.info(
                "Render completed with %d warning(s).", len(warnings)
            )

        return result

    except Exception:
        logger.exception("Render failed for project %s", project_id)

        # Attempt to delete partial output file
        try:
            if os.path.exists(output_path):
                os.remove(output_path)
                logger.info("Cleaned up partial output file: %s", output_path)
        except OSError as cleanup_err:
            logger.warning(
                "Failed to clean up partial output: %s", cleanup_err
            )

        raise

    finally:
        # --------------------------------------------------------------
        # L. Close all clips to free memory and file handles
        # --------------------------------------------------------------
        if composite_clip is not None:
            try:
                composite_clip.close()
            except Exception:
                pass

        for clip in clips:
            try:
                # Close audio sub-clip if attached
                if hasattr(clip, "audio") and clip.audio is not None:
                    clip.audio.close()
            except Exception:
                pass
            try:
                clip.close()
            except Exception:
                pass

        for ac in audio_clips:
            try:
                ac.close()
            except Exception:
                pass

        logger.debug("All clips closed.")
