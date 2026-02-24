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
import subprocess
from pathlib import Path
from typing import Callable, Optional

import proglog

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
        ImageClip,
        concatenate_videoclips,
        vfx,
    )
    from moviepy.audio.AudioClip import AudioClip as _AudioClipBase  # type: ignore[import-untyped]
except ImportError:
    # MoviePy 2.x — direct imports from moviepy
    from moviepy import (  # type: ignore[import-untyped]
        AudioFileClip,
        CompositeVideoClip,
        ImageClip,
        concatenate_videoclips,
        vfx,
    )
    from moviepy.audio.AudioClip import AudioClip as _AudioClipBase  # type: ignore[import-untyped]

import numpy as np

# ---------------------------------------------------------------------------
# GPU encoder detection (NVENC)
# ---------------------------------------------------------------------------
# Cached result so the detection probe runs at most once per process.
_nvenc_available: Optional[bool] = None


def _detect_nvenc() -> bool:
    """Probe FFmpeg for h264_nvenc hardware encoder support.

    Runs ``ffmpeg -encoders`` once and checks if ``h264_nvenc`` is listed.
    The result is cached in :data:`_nvenc_available` for subsequent calls.

    Returns:
        True if h264_nvenc is available, False otherwise.
    """
    global _nvenc_available
    if _nvenc_available is not None:
        return _nvenc_available

    try:
        result = subprocess.run(
            ["ffmpeg", "-encoders"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        _nvenc_available = "h264_nvenc" in result.stdout
    except Exception as exc:
        logger.debug("NVENC detection failed: %s", exc)
        _nvenc_available = False

    logger.info("NVENC h264_nvenc available: %s", _nvenc_available)
    return _nvenc_available


# ---------------------------------------------------------------------------
# Transition constants
# ---------------------------------------------------------------------------
# Fixed crossfade duration for v1.0.  This value is intentionally NOT
# user-configurable and must NOT be exposed in GlobalSettings or the
# settings UI.  0.5 s is the standard perceptible-but-not-sluggish value
# recommended by mainstream video-editing guides.
TRANSITION_DURATION: float = 0.5

# Brief silence gap appended to the end of each segment's audio before
# concatenation.  This ensures narration from consecutive segments does
# not run together without a natural pause.  The gap is in addition to
# the crossfade overlap, giving the listener a moment of breathing room
# between narration segments.
INTER_SEGMENT_SILENCE: float = 0.3


# Type alias for the progress callback
ProgressCallback = Optional[Callable[[int, int, str], None]]


# ---------------------------------------------------------------------------
# Silent audio utility
# ---------------------------------------------------------------------------

def _make_silent_audio(duration: float, fps: int = 44100) -> _AudioClipBase:
    """Create a silent AudioClip of the given duration.

    Used to pad silence to the end of each segment's audio so that
    consecutive segments don't run together without a natural pause.
    """
    return _AudioClipBase(
        frame_function=lambda t: np.zeros((1 if np.isscalar(t) else len(t), 2)),
        duration=duration,
        fps=fps,
    )


# ---------------------------------------------------------------------------
# Export progress logger — reports frame-level progress during write_videofile
# ---------------------------------------------------------------------------

class _ExportProgressLogger(proglog.ProgressBarLogger):
    """Custom proglog logger that funnels MoviePy export progress into the
    render pipeline's progress callback.

    ``write_videofile`` iterates every frame through a ``proglog`` bar named
    ``"t"`` (time-based).  This logger intercepts bar updates and maps them
    to percentage values, invoking *on_progress* at a throttled rate (at most
    once per percentage-point change) so the TaskManager registry gets smooth,
    fine-grained progress during the slowest phase of the render.
    """

    def __init__(
        self,
        on_progress: ProgressCallback,
        total_segments: int,
        base_percentage: int = 80,
    ):
        super().__init__()
        self._on_progress = on_progress
        self._total_segments = total_segments
        self._base_pct = base_percentage  # percentage at start of export
        self._last_reported_pct = base_percentage
        # Track bars in order of appearance to detect phase transitions
        self._seen_bars: list[str] = []

    def bars_callback(self, bar, attr, value, old_value=None):
        """Called by proglog whenever a progress bar attribute changes.

        Splits the export range into two sub-phases:
          • First progress bar  (video frames) → base_pct … 93 %
          • Second progress bar (audio chunks)  → 93 … 98 %
        The remaining 98 → 100 % is reported after ``write_videofile``
        returns (file verification step in ``render_project``).
        """
        if self._on_progress is None:
            return
        if attr != "index":
            return

        # Determine total frames from the bar's total attribute
        bar_data = self.bars.get(bar)
        if bar_data is None:
            return
        total = bar_data.get("total", 0)
        if total <= 0:
            return

        # Record the bar name the first time we see it
        if bar not in self._seen_bars:
            self._seen_bars.append(bar)

        bar_index = self._seen_bars.index(bar)
        fraction = min(value / total, 1.0)

        # Map fraction to percentage depending on phase
        if bar_index == 0:
            # First bar — video frame encoding: base_pct → 93 %
            pct = int(self._base_pct + fraction * (93 - self._base_pct))
            pct = min(pct, 93)
            phase_msg = f"Encoding video frames… {pct}%"
        elif bar_index == 1:
            # Second bar — audio encoding: 93 → 98 %
            pct = int(93 + fraction * 5)
            pct = min(pct, 98)
            phase_msg = f"Encoding audio track… {pct}%"
        else:
            # Any additional bars: 98 → 99 %
            pct = int(98 + fraction * 1)
            pct = min(pct, 99)
            phase_msg = f"Finalizing… {pct}%"

        # Throttle: only report when percentage actually advances
        if pct <= self._last_reported_pct:
            return
        self._last_reported_pct = pct

        # Report with current=pct, total=100 so the TaskManager computes
        # the correct percentage directly.
        self._on_progress(
            pct,
            100,
            phase_msg,
        )


# ---------------------------------------------------------------------------
# Crossfade utility
# ---------------------------------------------------------------------------

def apply_crossfade_transitions(
    clips: list,
    transition_duration: float = TRANSITION_DURATION,
) -> list:
    """Apply crossfade effects to a list of video clips based on position.

    * **First clip** — ``CrossFadeOut`` only (video starts at full opacity).
    * **Middle clips** — both ``CrossFadeIn`` and ``CrossFadeOut``.
    * **Last clip** — ``CrossFadeIn`` only (video ends at full opacity).

    This function only *prepares* the clips with crossfade effects — it does
    **not** concatenate them.  Concatenation with negative padding is handled
    separately in Task 05.02.02.

    Args:
        clips: Ordered list of MoviePy video clips.
        transition_duration: Duration (seconds) of each crossfade effect.
            Defaults to :data:`TRANSITION_DURATION`.

    Returns:
        A **new** list of clips with the appropriate crossfade effects
        applied.  The original *clips* list is not mutated.
    """
    # Guard clause — crossfade is meaningless for 0 or 1 clips.
    if len(clips) <= 1:
        return list(clips)

    logger.info(
        "Applying crossfade transitions to %d clips (duration=%.2fs)",
        len(clips),
        transition_duration,
    )

    # Debug: report each clip's duration before crossfade application.
    for idx, clip in enumerate(clips):
        clip_dur = getattr(clip, "duration", None)
        logger.debug("  Clip %d duration before crossfade: %s s", idx, clip_dur)

        # Defensive warning — clip shorter than the transition duration.
        if clip_dur is not None and clip_dur < transition_duration:
            logger.warning(
                "Clip %d duration (%.2fs) is shorter than the transition "
                "duration (%.2fs). The crossfade will consume the entire "
                "clip, which may produce unexpected visuals.",
                idx,
                clip_dur,
                transition_duration,
            )

    result: list = []
    last_idx = len(clips) - 1

    for idx, clip in enumerate(clips):
        has_predecessor = idx > 0
        has_successor = idx < last_idx

        effects: list = []
        if has_predecessor:
            effects.append(vfx.CrossFadeIn(transition_duration))
        if has_successor:
            effects.append(vfx.CrossFadeOut(transition_duration))

        if effects:
            clip = clip.with_effects(effects)

        result.append(clip)

    return result


# ---------------------------------------------------------------------------
# Duration calculation utility
# ---------------------------------------------------------------------------

def calculate_total_duration_with_transitions(
    clip_durations: list[float],
    transition_duration: float = TRANSITION_DURATION,
) -> float:
    """Calculate the expected total video duration accounting for crossfade overlaps.

    Formula::

        total = sum(clip_durations) − (N − 1) × transition_duration

    where *N* is the number of clips.  Each pair of adjacent clips shares
    one overlap of *transition_duration* seconds, shortening the total
    output by that amount.

    This is a **pure function** — no side effects, no I/O, no external
    dependencies.

    Worked examples (transition_duration = 0.5):

    * 1 clip  of 5.0 s → 5.0 s  (zero overlaps)
    * 2 clips of 5.0 s → 9.5 s  (one overlap)
    * 3 clips of 5.0 s → 14.0 s (two overlaps)
    * 5 clips of 3.0 s → 13.0 s (four overlaps)

    Args:
        clip_durations: Ordered list of individual clip durations (seconds).
        transition_duration: Duration of each crossfade transition.
            Defaults to :data:`TRANSITION_DURATION`.

    Returns:
        Expected total duration in seconds.  May be negative in extreme
        edge cases (many very short clips) — no clamping is applied.
    """
    if not clip_durations:
        return 0.0

    if len(clip_durations) == 1:
        return clip_durations[0]

    # Warn about clips shorter than the transition duration.
    short_clips = [
        (i, d) for i, d in enumerate(clip_durations)
        if d < transition_duration
    ]
    if short_clips:
        logger.warning(
            "%d clip(s) have duration shorter than transition duration "
            "(%.2fs): %s",
            len(short_clips),
            transition_duration,
            ", ".join(
                f"clip {i} ({d:.2f}s)" for i, d in short_clips
            ),
        )

    num_transitions = len(clip_durations) - 1
    total = sum(clip_durations) - num_transitions * transition_duration
    return total


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

    # ------------------------------------------------------------------
    # C2. Read zoom intensity and overrides from GlobalSettings
    # ------------------------------------------------------------------
    _DEFAULT_ZOOM = 1.3
    zoom_intensity = _DEFAULT_ZOOM

    if GlobalSettings is not None:
        try:
            gs = GlobalSettings.objects.first()

            if gs is not None:
                # ── Override resolution from GlobalSettings if set ──
                gs_width = getattr(gs, "render_width", None)
                gs_height = getattr(gs, "render_height", None)
                if gs_width and gs_height and gs_width > 0 and gs_height > 0:
                    res_width = int(gs_width)
                    res_height = int(gs_height)
                    logger.info(
                        "Resolution overridden by GlobalSettings: %dx%d",
                        res_width, res_height,
                    )

                # ── Override FPS from GlobalSettings if set ──
                gs_fps = getattr(gs, "render_fps", None)
                if gs_fps and gs_fps > 0:
                    fps = int(gs_fps)
                    logger.info(
                        "FPS overridden by GlobalSettings: %d", fps,
                    )

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
    logger.info("Resolution: %dx%d @ %d fps", res_width, res_height, fps)

    # ------------------------------------------------------------------
    # C3. Read subtitle settings from GlobalSettings
    # ------------------------------------------------------------------
    subtitle_font = None
    subtitle_color = "#FFFFFF"
    subtitle_font_size = None  # None → auto-compute from resolution
    subtitle_position = "bottom"
    subtitles_enabled = True
    inter_segment_silence = INTER_SEGMENT_SILENCE

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
                # Font size (None → auto)
                raw_fs = getattr(gs_sub, "subtitle_font_size", None)
                if raw_fs is not None and int(raw_fs) > 0:
                    subtitle_font_size = int(raw_fs)
                # Subtitle position
                raw_pos = getattr(gs_sub, "subtitle_position", "") or ""
                if raw_pos.strip() in ("top", "center", "bottom"):
                    subtitle_position = raw_pos.strip()
                # Subtitles toggle
                subtitles_enabled = getattr(gs_sub, "subtitles_enabled", True)
                # Inter-segment silence
                iss_val = getattr(gs_sub, "inter_segment_silence", None)
                if iss_val is not None and iss_val >= 0:
                    inter_segment_silence = float(iss_val)
        except Exception as sub_err:
            logger.warning(
                "Could not read subtitle settings from GlobalSettings: %s. "
                "Using defaults.",
                sub_err,
            )

    # Resolve font name to a filesystem path
    resolved_font = render_utils.get_font_path(subtitle_font)
    logger.info(
        "Subtitle settings — font: %s (resolved: %s), color: %s, "
        "size: %s, position: %s, enabled: %s",
        subtitle_font, resolved_font, subtitle_color,
        subtitle_font_size or "auto", subtitle_position, subtitles_enabled,
    )
    logger.info(
        "Inter-segment silence: %.2fs", inter_segment_silence,
    )

    # ------------------------------------------------------------------
    # C4. Read logo watermark settings from GlobalSettings
    # ------------------------------------------------------------------
    logo_enabled = False
    logo_clip = None  # Will be set if logo is enabled and valid

    if GlobalSettings is not None:
        try:
            gs_logo = GlobalSettings.objects.first()
            if gs_logo is not None and getattr(gs_logo, "logo_enabled", False):
                active_logo = getattr(gs_logo, "active_logo", None)
                if active_logo is not None and active_logo.file:
                    logo_file_path = active_logo.file.path
                    if os.path.isfile(logo_file_path):
                        logo_enabled = True
                        logo_scale = float(getattr(gs_logo, "logo_scale", 0.15))
                        logo_position_str = getattr(gs_logo, "logo_position", "bottom-right")
                        logo_opacity = float(getattr(gs_logo, "logo_opacity", 1.0))
                        logo_margin_px = int(getattr(gs_logo, "logo_margin", 20))

                        # Compute logo size based on resolution and scale
                        logo_target_w = int(res_width * logo_scale)

                        from PIL import Image as PILImage
                        pil_logo = PILImage.open(logo_file_path).convert("RGBA")
                        logo_aspect = pil_logo.width / pil_logo.height
                        logo_target_h = int(logo_target_w / logo_aspect)
                        pil_logo = pil_logo.resize(
                            (logo_target_w, logo_target_h),
                            PILImage.LANCZOS,
                        )

                        # Compute position
                        if logo_position_str == "top-left":
                            logo_pos = (logo_margin_px, logo_margin_px)
                        elif logo_position_str == "top-right":
                            logo_pos = (res_width - logo_target_w - logo_margin_px, logo_margin_px)
                        elif logo_position_str == "bottom-left":
                            logo_pos = (logo_margin_px, res_height - logo_target_h - logo_margin_px)
                        else:  # bottom-right
                            logo_pos = (res_width - logo_target_w - logo_margin_px, res_height - logo_target_h - logo_margin_px)

                        import numpy as np  # noqa: F811 — already imported at module level
                        logo_arr = np.array(pil_logo)
                        # Separate RGB and alpha
                        logo_rgb = logo_arr[:, :, :3]
                        logo_alpha = logo_arr[:, :, 3].astype(float) / 255.0
                        if logo_opacity < 1.0:
                            logo_alpha = logo_alpha * logo_opacity

                        logo_clip = (
                            ImageClip(logo_rgb)
                            .with_mask(ImageClip(logo_alpha, is_mask=True))
                            .with_position(logo_pos)
                        )

                        logger.info(
                            "Logo watermark enabled: %s, size: %dx%d, "
                            "position: %s (%s), opacity: %.2f",
                            os.path.basename(logo_file_path),
                            logo_target_w, logo_target_h,
                            logo_position_str, logo_pos, logo_opacity,
                        )
                    else:
                        logger.warning(
                            "Logo file not found: %s", logo_file_path,
                        )
        except Exception as logo_err:
            logger.warning(
                "Could not read logo settings: %s. Logo disabled.", logo_err,
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

            # Step 3: Compute visual duration (image stays on screen
            #         during the inter-segment silence gap too)
            visual_duration = audio_duration
            if inter_segment_silence > 0:
                visual_duration = audio_duration + inter_segment_silence

            # Step 3a: Create Ken Burns animated clip with error handling
            try:
                ken_burns_clip = apply_ken_burns(
                    image_path=image_path,
                    duration=visual_duration,
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
                "  Ken Burns clip created: %s (direction index %d, "
                "visual_duration=%.2fs)",
                image_path, segment.sequence_index, visual_duration,
            )

            # Step 3b: Collect subtitle and logo overlays for FLAT compositing
            # Instead of nesting multiple CompositeVideoClip layers (each
            # adding per-frame Python overhead), we collect all overlay
            # clips and composite them in a single pass.
            overlay_layers: list = []
            text_content = getattr(segment, "text_content", None) or ""

            # Subtitles
            if subtitles_enabled and text_content.strip():
                try:
                    subtitle_clips = create_subtitles_for_segment(
                        text_content=text_content,
                        audio_duration=audio_duration,
                        resolution=(res_width, res_height),
                        font=resolved_font,
                        color=subtitle_color,
                        font_size=subtitle_font_size,
                        position=subtitle_position,
                    )
                    if subtitle_clips:
                        overlay_layers.extend(subtitle_clips)
                        logger.debug(
                            "  Subtitles queued: %d clip(s) for %s",
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
            elif not subtitles_enabled:
                logger.debug(
                    "  Subtitles disabled — skipping for %s.",
                    seg_label,
                )
            elif not text_content.strip():
                logger.debug(
                    "  No text_content for %s — skipping subtitles.",
                    seg_label,
                )

            # Logo watermark
            if logo_enabled and logo_clip is not None:
                try:
                    seg_logo = logo_clip.with_duration(visual_duration)
                    overlay_layers.append(seg_logo)
                    logger.debug(
                        "  Logo watermark queued for %s", seg_label,
                    )
                except Exception as logo_exc:
                    logger.warning(
                        "  Logo compositing failed for %s: %s",
                        seg_label, logo_exc,
                    )

            # Step 3c: Single flat CompositeVideoClip (if overlays exist)
            if overlay_layers:
                ken_burns_clip = CompositeVideoClip(
                    [ken_burns_clip] + overlay_layers,
                    size=(res_width, res_height),
                ).with_duration(visual_duration)
                logger.debug(
                    "  Flat composite: %d overlay(s) for %s "
                    "(visual_duration=%.2fs)",
                    len(overlay_layers), seg_label, visual_duration,
                )

            # Step 4: Pair Ken Burns clip with audio
            # The Ken Burns clip was already created with visual_duration
            # (audio + silence), so the image stays on screen during the
            # silence gap — no black frame.
            if inter_segment_silence > 0:
                try:
                    from moviepy import concatenate_audioclips  # type: ignore[import-untyped]
                except ImportError:
                    from moviepy.editor import concatenate_audioclips  # type: ignore[import-untyped]

                silence = _make_silent_audio(
                    inter_segment_silence,
                    fps=getattr(audio_clip, "fps", 44100) or 44100,
                )
                padded_audio = concatenate_audioclips([audio_clip, silence])
                ken_burns_clip = ken_burns_clip.with_audio(padded_audio)

                logger.debug(
                    "  Audio padded: %.2fs + %.2fs silence = %.2fs",
                    audio_duration, inter_segment_silence, visual_duration,
                )
            else:
                ken_burns_clip = ken_burns_clip.with_audio(audio_clip)
                logger.debug(
                    "  Audio set: %.2fs (no silence gap)", audio_duration,
                )

            # Step 5: Append and continue
            clips.append(ken_burns_clip)

            # Progress callback
            if on_progress:
                subtitle_note = ""
                if subtitles_enabled and text_content.strip():
                    subtitle_note = " + subtitles composited"
                on_progress(
                    idx,
                    total_segments,
                    f"Ken Burns applied to {seg_label}{subtitle_note}",
                )

        # --------------------------------------------------------------
        # H. Concatenate all clips (transition-aware)
        # --------------------------------------------------------------
        # Validate clips list is not empty (all segments may have been
        # skipped due to zero-duration audio)
        if not clips:
            raise ValueError(
                "No clips available for rendering. All segments may have "
                "been skipped due to zero-duration audio or missing files. "
                "This should have been caught by pre-render validation."
            )

        # Preserve original durations for logging before crossfade.
        original_durations = [c.duration for c in clips]

        if len(clips) > 1:
            # --- Multi-clip: apply crossfade transitions, then
            # concatenate with negative padding for overlap. ---
            #
            # AUDIO CROSSFADE BEHAVIOUR (Task 05.02.04)
            # ------------------------------------------
            # MoviePy's CrossFadeIn / CrossFadeOut effects modify BOTH
            # the video opacity AND the audio volume simultaneously:
            #
            #   • CrossFadeOut(d) ramps audio volume 1.0 → 0.0 over the
            #     last *d* seconds of the outgoing clip.
            #   • CrossFadeIn(d) ramps audio volume 0.0 → 1.0 over the
            #     first *d* seconds of the incoming clip.
            #
            # During the 0.5 s overlap created by negative padding, both
            # audio streams play at the same time.  The outgoing audio
            # fades out while the incoming audio fades in, producing a
            # smooth cross-mix whose total level stays approximately
            # constant (the two linear ramps sum to ~1.0 at every point).
            #
            # No manual AudioClip manipulation is required — this
            # automatic behaviour produces a natural-sounding transition
            # for TTS narration, where segment boundaries usually fall in
            # natural speech pauses.
            #
            # ALTERNATIVES NOT IMPLEMENTED (v1.0 design decision):
            #
            #   A) Independent audio fading (audio_fadein / audio_fadeout
            #      with different curves or durations).  Adds complexity
            #      without clear benefit for narration content.
            #
            #   B) Full-volume audio during visual crossfade (strip audio
            #      before crossfade, reattach after).  Would produce a
            #      harsh, abrupt audio cut rather than a smooth cross-mix.
            #
            # SUBTITLE–TRANSITION INTERACTION (Task 05.02.06)
            # -----------------------------------------------
            # Subtitles are composited INTO each clip (via
            # CompositeVideoClip) in SubPhase 05.01 *before* crossfade
            # effects are applied here.  The crossfade opacity therefore
            # affects the ENTIRE composite — Ken Burns visuals and
            # subtitle text fade together as a single unit.
            #
            # During the 0.5 s overlap, both the outgoing clip's subtitle
            # and the incoming clip's subtitle are partially visible at
            # reduced opacity.  This brief blended state is standard
            # video-editing behaviour and is visually acceptable for v1.0
            # because:
            #   • The overlap is only 0.5 s — too short for viewers to
            #     focus on the blended text.
            #   • Both subtitles occupy the same screen position, so the
            #     blend appears as one subtitle morphing into another.
            #   • Content boundaries (end-of-sentence → start-of-sentence)
            #     make the transition feel coherent.
            #
            # Subtitle timing (start / duration of each TextClip) is
            # unaffected by crossfade — only opacity is modified.
            #
            # POTENTIAL FUTURE IMPROVEMENTS (not implemented in v1.0):
            #   A) Truncate outgoing subtitles 0.5 s before clip end.
            #   B) Delay incoming subtitles 0.5 s after clip start.
            #   C) Add semi-transparent background behind subtitle text
            #      for readability during partial-opacity blending.
            # All deferred due to added complexity with minimal benefit.

            # Progress: transition phase
            if on_progress:
                on_progress(
                    total_segments,
                    total_segments,
                    "Applying crossfade transitions…",
                )

            clips = apply_crossfade_transitions(clips, TRANSITION_DURATION)

            logger.info(
                "Concatenating %d clip(s) with crossfade "
                "(padding=%.2fs)...",
                len(clips),
                -TRANSITION_DURATION,
            )
            composite_clip = concatenate_videoclips(
                clips,
                method="compose",
                padding=-TRANSITION_DURATION,
            )
        else:
            # --- Single-clip: no transitions, no concatenation. ---
            # A single segment renders as-is — no crossfadein/crossfadeout,
            # no fadein/fadeout, no concatenation overhead.  All previously
            # applied effects (Ken Burns, subtitle overlay, audio) are
            # preserved exactly as they were baked into the clip.
            logger.info(
                "Project has a single segment — skipping crossfade "
                "transitions and concatenation.  The clip will be "
                "exported directly with all existing effects intact."
            )
            composite_clip = clips[0]

        # Validate concatenation / single-clip result
        if composite_clip.duration is None or composite_clip.duration <= 0:
            raise ValueError(
                "Concatenation produced a clip with zero or negative duration."
            )

        # Log expected duration accounting for overlaps.
        num_overlaps = max(len(original_durations) - 1, 0)
        naive_sum = sum(original_durations)
        expected_duration = calculate_total_duration_with_transitions(
            original_durations, TRANSITION_DURATION,
        )
        logger.info(
            "Concatenation complete: %d clip(s), %d crossfade "
            "transition(s) (%.2fs each).  Naive sum %.2fs, "
            "adjusted expected duration %.2fs, actual duration %.2fs",
            len(original_durations),
            num_overlaps,
            TRANSITION_DURATION if num_overlaps else 0.0,
            naive_sum,
            expected_duration,
            composite_clip.duration,
        )

        # --------------------------------------------------------------
        # I. Progress: exporting
        # --------------------------------------------------------------
        # Calculate what percentage we're at before export begins.
        # Segment processing occupies roughly 0–80%, export occupies 80–100%.
        if on_progress:
            export_base_pct = 80  # segments done, entering export
            on_progress(
                export_base_pct,
                100,
                f"Exporting MP4… {export_base_pct}%",
            )

        # --------------------------------------------------------------
        # J. Export to MP4 — with GPU (NVENC) acceleration when available
        # --------------------------------------------------------------
        logger.info("Exporting to %s ...", output_path)

        # Build a fine-grained export progress logger so the frontend
        # sees smooth advancement during the most time-consuming phase.
        export_logger: object = None
        if on_progress:
            export_logger = _ExportProgressLogger(
                on_progress=on_progress,
                total_segments=total_segments,
                base_percentage=80,
            )

        # ── Determine best codec and encoding parameters ──
        use_nvenc = _detect_nvenc()

        if use_nvenc:
            # NVIDIA NVENC hardware encoder — offloads encoding to the
            # GPU's fixed-function hardware.  5–10× faster than libx264
            # at equivalent quality.
            video_codec = "h264_nvenc"
            ffmpeg_params = [
                "-preset", "p4",          # Balanced speed/quality preset
                "-tune", "hq",            # Optimise for visual quality
                "-rc", "vbr",             # Variable bitrate mode
                "-cq", "23",              # Constant quality level (lower = better)
                "-b:v", "8M",             # Target bitrate
                "-maxrate", "12M",        # Cap peak bitrate
                "-bufsize", "16M",        # VBV buffer size
                "-profile:v", "high",     # H.264 High profile
                "-movflags", "+faststart",  # Move moov atom for web streaming
            ]
            logger.info(
                "Using NVIDIA NVENC GPU encoder (h264_nvenc) for export."
            )
        else:
            # CPU fallback — libx264 with optimised preset.
            # "fast" preset is ~3× faster than default "medium" with
            # negligible quality difference at 8 Mbps bitrate.
            video_codec = "libx264"
            ffmpeg_params = [
                "-preset", "fast",
                "-tune", "film",           # Optimise for high-detail content
                "-crf", "23",              # Constant rate factor (good quality)
                "-profile:v", "high",
                "-movflags", "+faststart",
            ]
            logger.info(
                "Using libx264 CPU encoder (preset=fast) for export."
            )

        try:
            composite_clip.write_videofile(
                output_path,
                codec=video_codec,
                audio_codec="aac",
                bitrate="8000k",
                fps=fps,
                threads=0,                # Auto-detect available CPU threads
                ffmpeg_params=ffmpeg_params,
                logger=export_logger,     # Fine-grained frame-by-frame progress
            )
        except PermissionError as perm_err:
            # On Windows MoviePy sometimes fails to delete the temp
            # audio file (``finalTEMP_MPY_wvf_snd.mp4``) because another
            # process still holds a lock.  The actual video export has
            # already completed successfully if we reach this point, so
            # we log a warning and continue.
            logger.warning(
                "Temp-file cleanup failed (non-fatal, Windows lock): %s",
                perm_err,
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
        if on_progress:
            on_progress(99, 100, "Verifying output file…")

        if not os.path.exists(output_path):
            raise RuntimeError(
                f"Export completed but output file not found: {output_path}"
            )

        total_duration = composite_clip.duration

        # Duration validation: compare actual vs expected.
        duration_diff = abs(total_duration - expected_duration)
        if duration_diff > 0.2:
            logger.warning(
                "Duration mismatch: expected %.2fs, actual %.2fs "
                "(diff %.2fs exceeds 0.2s tolerance).",
                expected_duration,
                total_duration,
                duration_diff,
            )

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
            "expected_duration": expected_duration,
            "num_transitions": num_overlaps,
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
