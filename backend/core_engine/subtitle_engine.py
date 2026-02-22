"""
Subtitle Engine — Timed, styled subtitle overlays for video segments.

This module generates subtitle overlays from narration text for each
video segment.  It splits text into readable chunks, calculates
proportional timing based on audio duration, and produces MoviePy
``TextClip`` objects positioned near the bottom of each frame.

The public entry-point is :func:`create_subtitles_for_segment`, which
orchestrates the full pipeline:

    chunk_text → calculate_subtitle_timing → generate_subtitle_clips

Subsequent tasks populate the algorithm implementations:

- **Task 05.01.02** — ``chunk_text``
- **Task 05.01.03** — ``calculate_subtitle_timing``
- **Task 05.01.04** — ``generate_subtitle_clips``
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from moviepy import TextClip

# ── Logger ──────────────────────────────────────────────────────────────────

logger = logging.getLogger(__name__)

# ── Module-Level Constants ──────────────────────────────────────────────────

DEFAULT_MAX_WORDS: int = 6
"""Maximum words per subtitle chunk."""

MIN_CHUNK_WORDS: int = 4
"""Minimum words before considering a boundary break."""

MIN_DISPLAY_DURATION: float = 0.5
"""Minimum seconds a subtitle is displayed."""

FONT_SIZE_DIVISOR: int = 18
"""``resolution_height / FONT_SIZE_DIVISOR`` ≈ font size (60 px at 1080p)."""

TEXT_WIDTH_RATIO: float = 0.9
"""Subtitle width as a fraction of frame width (90 %)."""

SUBTITLE_Y_RATIO: float = 0.85
"""Vertical position of subtitles (85 % from top)."""

DEFAULT_STROKE_COLOR: str = "#000000"
"""Black stroke for readability against any background."""

DEFAULT_STROKE_WIDTH: int = 2
"""Stroke width in pixels."""


# ── Function Stubs (populated by Tasks 05.01.02–04) ────────────────────────


def _is_boundary_word(word: str) -> bool:
    """Return ``True`` if *word* ends at a natural break-point.

    Strips trailing quotation marks and parentheses before checking so
    that words like ``"dog."`` and ``"world!)"`` are both recognised as
    boundary words.

    Sentence boundaries: ``.``, ``!``, ``?``
    Clause boundaries:   ``,``, ``;``, ``:``, ``—``, ``…``
    """
    stripped = word.rstrip("\"')]}»")
    if not stripped:
        return False
    return stripped[-1] in ".!?,;:—…"


def chunk_text(text: str, max_words: int = DEFAULT_MAX_WORDS) -> list[str]:
    """Split *text* into readable word-chunks of at most *max_words*.

    The algorithm prefers breaking at sentence boundaries (periods,
    exclamation marks, question marks) and clause boundaries (commas,
    semicolons, colons, em dashes) to produce subtitle chunks that
    read naturally, while enforcing a maximum word count per chunk.

    Parameters
    ----------
    text:
        The narration text to split.
    max_words:
        Maximum number of words per chunk (default
        :data:`DEFAULT_MAX_WORDS`).

    Returns
    -------
    list[str]
        Ordered list of subtitle strings.
    """
    # Edge cases — empty / whitespace-only text
    if not text or not text.strip():
        return []

    # Normalize whitespace (collapse tabs, newlines, multiple spaces)
    words = text.split()
    if not words:
        return []

    # Short text — fits in a single chunk
    if len(words) <= max_words:
        return [" ".join(words)]

    # ── Chunking loop ───────────────────────────────────────────────
    chunks: list[list[str]] = []
    current: list[str] = []

    for word in words:
        current.append(word)

        # Hard break — reached the maximum word count
        if len(current) >= max_words:
            chunks.append(current)
            current = []
            continue

        # Soft break — natural boundary AND enough words accumulated
        if _is_boundary_word(word) and len(current) >= MIN_CHUNK_WORDS:
            chunks.append(current)
            current = []

    # ── Orphan prevention ───────────────────────────────────────────
    if current:
        # Merge tiny remainders into the previous chunk when feasible
        if (
            len(current) <= 2
            and chunks
            and len(chunks[-1]) + len(current) <= max_words + 1
        ):
            chunks[-1].extend(current)
        else:
            chunks.append(current)

    # ── Finalise ────────────────────────────────────────────────────
    return [" ".join(chunk) for chunk in chunks if chunk]


def calculate_subtitle_timing(
    chunks: list[str],
    total_duration: float,
    min_duration: float = MIN_DISPLAY_DURATION,
) -> list[tuple[float, float]]:
    """Calculate proportional timing for each subtitle chunk.

    Distributes *total_duration* across *chunks* proportionally to the
    number of words in each chunk, enforces a minimum display time, and
    normalises so that all durations sum to exactly *total_duration*
    with no gaps between consecutive subtitles.

    Parameters
    ----------
    chunks:
        Ordered list of subtitle strings (from :func:`chunk_text`).
    total_duration:
        Total audio duration in seconds.
    min_duration:
        Minimum display time per subtitle (default
        :data:`MIN_DISPLAY_DURATION`).

    Returns
    -------
    list[tuple[float, float]]
        List of ``(start_time, duration)`` tuples, one per chunk.
    """
    # Edge case — no chunks
    if not chunks:
        return []

    # Single chunk — takes the full duration
    if len(chunks) == 1:
        return [(0.0, total_duration)]

    # ── Step 3: Count words per chunk ───────────────────────────────
    word_counts = [len(chunk.split()) for chunk in chunks]
    total_words = sum(word_counts)

    if total_words == 0:
        return []

    # ── Step 4: Proportional durations ──────────────────────────────
    durations = [
        (wc / total_words) * total_duration for wc in word_counts
    ]

    # ── Step 5: Enforce minimum duration ────────────────────────────
    durations = [max(d, min_duration) for d in durations]

    # ── Step 6: Normalise to fit total_duration exactly ─────────────
    duration_sum = sum(durations)
    if duration_sum > 0:
        factor = total_duration / duration_sum
        durations = [d * factor for d in durations]

    # ── Step 7: Build (start_time, duration) tuples ─────────────────
    timings: list[tuple[float, float]] = []
    current_start = 0.0

    for i, dur in enumerate(durations):
        # Step 8: Absorb float remainder on the last chunk
        if i == len(durations) - 1:
            dur = total_duration - current_start

        timings.append((current_start, dur))
        current_start += dur

    return timings


def generate_subtitle_clips(
    chunks: list[str],
    timings: list[tuple[float, float]],
    resolution: tuple[int, int],
    font: str,
    color: str,
) -> list[TextClip]:
    """Create styled ``TextClip`` objects for each subtitle chunk.

    Each clip is styled in the "YouTube-style" subtitle look: white
    text with black stroke, bold font, positioned at bottom-centre,
    with proportional font sizing based on video resolution.

    Parameters
    ----------
    chunks:
        Ordered list of subtitle strings.
    timings:
        Matching ``(start_time, duration)`` tuples.
    resolution:
        ``(width, height)`` of the video frame.
    font:
        Path to a ``.ttf`` font file.
    color:
        Text colour (e.g. ``"#FFFFFF"``).

    Returns
    -------
    list[TextClip]
        MoviePy ``TextClip`` objects ready for compositing.
    """
    if not chunks or not timings:
        return []

    width, height = resolution

    # ── Step 3: Compute styling parameters ──────────────────────────
    font_size = int(height / FONT_SIZE_DIVISOR)
    text_width = int(width * TEXT_WIDTH_RATIO)
    y_position = int(height * SUBTITLE_Y_RATIO)

    # ── Step 4–7: Create TextClips ──────────────────────────────────
    clips: list[TextClip] = []

    for chunk, (start_time, duration) in zip(chunks, timings):
        try:
            clip = TextClip(
                text=chunk,
                font_size=font_size,
                font=font,
                color=color,
                stroke_color=DEFAULT_STROKE_COLOR,
                stroke_width=DEFAULT_STROKE_WIDTH,
                method="caption",
                size=(text_width, None),
                text_align="center",
            )

            # Set position and timing (MoviePy 2.x immutable API)
            clip = (
                clip
                .with_position(("center", y_position))
                .with_start(start_time)
                .with_duration(duration)
            )

            clips.append(clip)

            logger.debug(
                "Subtitle clip: '%.30s%s' @ %.2fs for %.2fs",
                chunk,
                "…" if len(chunk) > 30 else "",
                start_time,
                duration,
            )

        except Exception as exc:
            logger.warning(
                "Failed to create TextClip for chunk '%.30s': %s",
                chunk,
                exc,
            )

    return clips


# ── Convenience Entry-Point ────────────────────────────────────────────────


def create_subtitles_for_segment(
    text_content: str,
    audio_duration: float,
    resolution: tuple[int, int],
    font: str,
    color: str,
) -> list[TextClip]:
    """Generate subtitle clips for a single video segment.

    This is the main entry-point called by ``video_renderer.py``.  It
    chains the three processing steps:

    1. :func:`chunk_text` — split narration into readable chunks.
    2. :func:`calculate_subtitle_timing` — assign proportional timing.
    3. :func:`generate_subtitle_clips` — create styled ``TextClip``
       objects.

    Parameters
    ----------
    text_content:
        The narration / transcript text for the segment.
    audio_duration:
        Duration of the segment's audio in seconds.
    resolution:
        ``(width, height)`` of the video frame.
    font:
        Font family name.
    color:
        Text colour.

    Returns
    -------
    list[TextClip]
        Subtitle clips ready for compositing, or an empty list if
        *text_content* is empty / whitespace-only.
    """
    if not text_content or not text_content.strip():
        logger.debug("Empty text — returning no subtitles.")
        return []

    # Step 1 — chunk
    chunks = chunk_text(text_content)

    # Step 2 — timing
    timings = calculate_subtitle_timing(chunks, audio_duration)

    # Step 3 — clips
    clips = generate_subtitle_clips(chunks, timings, resolution, font, color)

    logger.info(
        "Created %d subtitle clips (%.1f s total).",
        len(clips),
        audio_duration,
    )
    return clips
