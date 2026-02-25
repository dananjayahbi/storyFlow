"""
StoryFlow Video Renderer Module.

Orchestrates video assembly from image and audio segments.  Uses a
**fast compositor** that bypasses MoviePy's per-frame Pillow pipeline
with direct NumPy alpha blending and FFmpeg subprocess piping.

MoviePy is still used for:
  - Audio loading and concatenation (crossfade mixing)
  - Exporting the mixed audio to a temporary WAV file

Video frame generation and compositing is handled entirely by
:mod:`core_engine.fast_compositor`, which is ~10–15× faster than
MoviePy's ``CompositeVideoClip.write_videofile()``.

This module is a pure rendering function — it does NOT update project
status in the database.  Status management is handled by the API layer
in SubPhase 04.03.
"""

import logging
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Callable, Optional

import proglog

from core_engine import render_utils
from core_engine.ken_burns import apply_ken_burns
from core_engine.fast_compositor import fast_render_segments

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MoviePy version-safe imports
# ---------------------------------------------------------------------------

try:
    # MoviePy 1.x — everything lives under moviepy.editor
    from moviepy.editor import (  # type: ignore[import-untyped]
        AudioFileClip,
        concatenate_videoclips,
        vfx,
    )
    from moviepy.audio.AudioClip import AudioClip as _AudioClipBase  # type: ignore[import-untyped]
except ImportError:
    # MoviePy 2.x — direct imports from moviepy
    from moviepy import (  # type: ignore[import-untyped]
        AudioFileClip,
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


def _probe_duration(file_path: str) -> Optional[float]:
    """Probe the duration of a video file using FFprobe.

    Returns:
        Duration in seconds, or ``None`` if probing fails.
    """
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                file_path,
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except Exception as exc:
        logger.debug("FFprobe duration query failed: %s", exc)
    return None


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
    subtitle_y_position = None  # None → use preset position
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
                # Manual Y position override
                raw_y_pos = getattr(gs_sub, "subtitle_y_position", None)
                if raw_y_pos is not None:
                    subtitle_y_position = int(raw_y_pos)
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
    # Logo is pre-rendered in the fast compositor — we only need to
    # detect if it's enabled and pass the file path.
    logo_enabled = False

    if GlobalSettings is not None:
        try:
            gs_logo = GlobalSettings.objects.first()
            if gs_logo is not None and getattr(gs_logo, "logo_enabled", False):
                active_logo = getattr(gs_logo, "active_logo", None)
                if active_logo is not None and active_logo.file:
                    logo_file_path = active_logo.file.path
                    if os.path.isfile(logo_file_path):
                        logo_enabled = True
                        logger.info(
                            "Logo watermark enabled: %s",
                            os.path.basename(logo_file_path),
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
    # Rendering pipeline — Fast Compositor path
    # ------------------------------------------------------------------
    # Uses direct NumPy compositing + FFmpeg pipe instead of MoviePy's
    # per-frame Pillow pipeline.  ~10-15× faster.
    audio_clips: list = []
    temp_audio_path: Optional[str] = None

    try:
        # --------------------------------------------------------------
        # G. Collect segment data and export audio
        # --------------------------------------------------------------
        segment_data_list: list[dict] = []

        for idx, segment in enumerate(segments, start=1):
            seg_label = (
                f"Segment {idx}/{total_segments} "
                f"(index {segment.sequence_index})"
            )
            logger.info("Loading %s", seg_label)

            # Step 1: Verify file existence
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

            # Step 2: Load audio clip
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

            if audio_duration is None or audio_duration <= 0:
                logger.warning(
                    "Skipping %s (ID %s): audio duration is zero or negative.",
                    seg_label, segment.id,
                )
                continue

            # Duration cross-validation
            if segment.audio_duration is not None:
                diff = abs(audio_duration - segment.audio_duration)
                if diff > 0.1:
                    logger.warning(
                        "%s: audio file (%.3fs) differs from DB (%.3fs).",
                        seg_label, audio_duration, segment.audio_duration,
                    )

            text_content = getattr(segment, "text_content", None) or ""

            segment_data_list.append({
                "image_path": image_path,
                "audio_duration": audio_duration,
                "text_content": text_content,
                "sequence_index": segment.sequence_index,
            })

            if on_progress:
                on_progress(idx, total_segments, f"Loaded {seg_label}")

        if not segment_data_list:
            raise ValueError(
                "No valid segments available for rendering."
            )

        # --------------------------------------------------------------
        # G2. Export mixed audio to temp WAV file
        # --------------------------------------------------------------
        # Audio must use the SAME timeline as the video — i.e. segments
        # are staggered with crossfade overlap, not simply concatenated.
        # Without this, audio is longer than video by
        # (N-1) × crossfade_duration, causing progressive subtitle drift.
        if on_progress:
            on_progress(total_segments, total_segments, "Mixing audio…")

        logger.info("Exporting mixed audio track…")

        # Import audio compositing tools
        try:
            from moviepy import concatenate_audioclips, CompositeAudioClip
        except ImportError:
            from moviepy.editor import concatenate_audioclips, CompositeAudioClip

        # Build padded audio clips (audio + inter-segment silence)
        padded_audio_clips = []
        for i, ac in enumerate(audio_clips):
            if inter_segment_silence > 0:
                silence = _make_silent_audio(
                    inter_segment_silence,
                    fps=getattr(ac, "fps", 44100) or 44100,
                )
                padded = concatenate_audioclips([ac, silence])
                padded_audio_clips.append(padded)
            else:
                padded_audio_clips.append(ac)

        # Stagger audio clips using the same timeline as the video
        # fast compositor: each segment starts at
        #   offset += visual_duration - crossfade_duration
        if len(padded_audio_clips) > 1:
            timeline_offset = 0.0
            staggered_clips = []
            for i, pac in enumerate(padded_audio_clips):
                staggered_clips.append(
                    pac.with_start(timeline_offset)
                )
                visual_dur = segment_data_list[i]["audio_duration"] + inter_segment_silence
                if i < len(padded_audio_clips) - 1:
                    timeline_offset += visual_dur - TRANSITION_DURATION
                else:
                    timeline_offset += visual_dur

            # CompositeAudioClip mixes overlapping audio (crossfade)
            mixed_audio = CompositeAudioClip(staggered_clips)
            # Explicitly set duration to match the video timeline
            mixed_audio = mixed_audio.with_duration(timeline_offset)
            logger.info(
                "Audio staggered with crossfade: %d clips, "
                "total duration %.2fs (crossfade=%.2fs)",
                len(staggered_clips), timeline_offset, TRANSITION_DURATION,
            )
        else:
            mixed_audio = padded_audio_clips[0]

        # Write to a temp WAV file
        temp_audio_fd, temp_audio_path = tempfile.mkstemp(suffix=".wav")
        os.close(temp_audio_fd)

        mixed_audio.write_audiofile(
            temp_audio_path,
            fps=44100,
            nbytes=2,
            codec="pcm_s16le",
            logger=None,
        )
        logger.info(
            "Audio exported to temp file: %s (%.2fs)",
            temp_audio_path, mixed_audio.duration,
        )

        # Close audio clips to free handles
        mixed_audio.close()
        for ac in audio_clips:
            try:
                ac.close()
            except Exception:
                pass
        audio_clips.clear()

        # --------------------------------------------------------------
        # H. Fast render: NumPy compositing + direct FFmpeg pipe
        # --------------------------------------------------------------
        if on_progress:
            on_progress(5, 100, "Starting fast render pipeline…")

        # Determine NVENC availability
        use_nvenc = _detect_nvenc()

        # Prepare subtitle settings dict
        sub_settings = {
            "enabled": subtitles_enabled,
            "font": resolved_font,
            "color": subtitle_color,
            "font_size": subtitle_font_size,
            "position": subtitle_position,
            "y_position": subtitle_y_position,
        }

        # Prepare logo settings dict
        logo_settings_dict: Optional[dict] = None
        if logo_enabled:
            try:
                gs_logo = GlobalSettings.objects.first()
                active_logo = getattr(gs_logo, "active_logo", None)
                if active_logo and active_logo.file:
                    logo_settings_dict = {
                        "file_path": active_logo.file.path,
                        "scale": float(getattr(gs_logo, "logo_scale", 0.15)),
                        "position": getattr(gs_logo, "logo_position", "bottom-right"),
                        "opacity": float(getattr(gs_logo, "logo_opacity", 1.0)),
                        "margin": int(getattr(gs_logo, "logo_margin", 20)),
                    }
            except Exception as logo_err:
                logger.warning("Could not read logo settings: %s", logo_err)

        # Run the fast compositor
        render_stats = fast_render_segments(
            segment_data=segment_data_list,
            output_path=output_path,
            resolution=(res_width, res_height),
            fps=fps,
            zoom_intensity=zoom_intensity,
            subtitle_settings=sub_settings,
            logo_settings=logo_settings_dict,
            audio_path=temp_audio_path,
            use_nvenc=use_nvenc,
            on_progress=on_progress,
            crossfade_duration=TRANSITION_DURATION,
            inter_segment_silence=inter_segment_silence,
        )

        logger.info(
            "Fast render stats: %d frames, %.1fs, %.1f ms/frame",
            render_stats["frames_rendered"],
            render_stats["render_time"],
            render_stats["avg_ms_per_frame"],
        )

        # --------------------------------------------------------------
        # K. Verify output and capture duration
        # --------------------------------------------------------------
        if on_progress:
            on_progress(98, 100, "Verifying output file…")

        if not os.path.exists(output_path):
            raise RuntimeError(
                f"Export completed but output file not found: {output_path}"
            )

        # Get duration from FFmpeg probe
        total_duration = _probe_duration(output_path)
        if total_duration is None or total_duration <= 0:
            # Fallback: estimate from segment data
            total_duration = sum(
                sd["audio_duration"] + inter_segment_silence
                for sd in segment_data_list
            )
            if len(segment_data_list) > 1:
                total_duration -= (len(segment_data_list) - 1) * TRANSITION_DURATION

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
        logger.info(
            "Performance: %d frames in %.1fs (%.1f ms/frame avg)",
            render_stats["frames_rendered"],
            render_stats["render_time"],
            render_stats["avg_ms_per_frame"],
        )

        # --------------------------------------------------------------
        # N. Return result dict
        # --------------------------------------------------------------
        if on_progress:
            on_progress(100, 100, "Render complete!")

        result = {
            "output_path": output_path,
            "duration": total_duration,
            "expected_duration": total_duration,
            "num_transitions": max(len(segment_data_list) - 1, 0),
            "file_size": file_size,
            "warnings": warnings,
            "render_stats": render_stats,
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
        # L. Clean up temp audio file and close clips
        # --------------------------------------------------------------
        if temp_audio_path and os.path.exists(temp_audio_path):
            try:
                os.remove(temp_audio_path)
                logger.debug("Removed temp audio: %s", temp_audio_path)
            except OSError:
                pass

        for ac in audio_clips:
            try:
                ac.close()
            except Exception:
                pass

        logger.debug("Cleanup complete.")
