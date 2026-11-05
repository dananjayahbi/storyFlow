"""
StoryFlow Ken Burns Effect Module.

Provides zoom-and-pan animation for still images used in narrative video
segments.  The module converts static cover images into MoviePy VideoClip
objects with per-frame camera motion.  A smart planner measures the free
space around an optional single highlighted subject and chooses a pan, a
slow zoom, or a combined move with a comfortable speed.

The primary public interface is :func:`apply_ken_burns`, which the video
renderer calls once per segment.  All other functions in this module are
internal helpers implementing specific parts of the algorithm.

Design principles
-----------------
* **Deterministic** — Motion presets and directions are selected from
  ``segment_index % 7``, so re-rendering the same project always produces
  identical output.
* **No Django dependency** — The module performs pure computation on images
  and NumPy arrays.  The only I/O is reading the source image file from
  disk (in ``load_and_prepare_image``).  All configuration values
  (zoom_intensity, fps, resolution, …) are passed in by the caller.
* **MoviePy version-safe** — Imports are wrapped in ``try``/``except`` to
  support both MoviePy 1.x (``moviepy.editor``) and 2.x (``moviepy``).
"""

import logging
from typing import Tuple

import cv2
import numpy as np
from PIL import Image

# ---------------------------------------------------------------------------
# MoviePy version-safe imports
# ---------------------------------------------------------------------------
# MoviePy 1.x exposes classes under moviepy.editor, while MoviePy 2.x
# uses direct imports from moviepy.  The try/except block ensures this
# module works with either version.
try:
    from moviepy.editor import VideoClip  # type: ignore[import-untyped]
except ImportError:
    from moviepy import VideoClip  # type: ignore[import-untyped]

# ---------------------------------------------------------------------------
# Module-level logger
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Direction presets
# ---------------------------------------------------------------------------
# Each tuple is (start_position_name, end_position_name) describing a
# camera pan trajectory.  ``segment_index % 7`` selects the direction,
# ensuring deterministic and visually varied motion across consecutive
# segments.  Every entry moves the camera: the first segment must animate
# too, so there is deliberately no static "center → center" preset.
# The mapping from position names to pixel coordinates is handled by
# ``position_to_coords`` (Task 04.02.05).
DIRECTIONS: Tuple[
    Tuple[str, str], ...
] = (
    ("top_left", "center"),            # pan from the top-left into frame
    ("bottom_right", "top_left"),      # reverse diagonal
    ("top_right", "bottom_left"),      # opposite diagonal
    ("bottom_left", "top_right"),      # reverse opposite diagonal
    ("center", "top_left"),            # drift upward-left
    ("center", "bottom_right"),        # drift downward-right
    ("top_left", "bottom_right"),      # diagonal pan
)

#: Only one subject rectangle may be marked per image.  Older projects may
#: still store a list of rectangles in ``image_focus_areas``; the renderer
#: uses the first one and ignores the rest so stored data stays untouched.
MAX_FOCUS_AREAS = 1

# ---------------------------------------------------------------------------
# Smart motion planning
# ---------------------------------------------------------------------------
# Ken Burns is more than a blind corner-to-corner pan.  The planner measures
# how much room is left around the marked subject and then picks a motion
# (pan, slow zoom in/out or a combined move) whose speed is comfortable for
# the clip length.  The preset order is deterministic, but every entry is
# validated against the available room and replaced when it would look static.
MOTION_PAN = "pan"
MOTION_ZOOM_IN = "zoom_in"
MOTION_ZOOM_OUT = "zoom_out"
MOTION_PAN_ZOOM = "pan_zoom"

MOTION_PRESETS: Tuple[str, ...] = (
    MOTION_PAN,
    MOTION_ZOOM_IN,
    MOTION_PAN,
    MOTION_ZOOM_OUT,
    MOTION_PAN_ZOOM,
    MOTION_PAN,
    MOTION_ZOOM_IN,
)

#: Comfortable camera speed, expressed as frame widths per second.  A 5 s
#: segment therefore travels about 17 % of the frame instead of whipping
#: across it.
PAN_SPEED_TARGET = 0.035

#: Comfortable zoom speed as a fraction of the base crop scale per second.
ZOOM_RATE_TARGET = 0.025

#: Below these thresholds a move is practically invisible; the planner picks
#: a different motion instead of producing a nearly static shot.
MIN_PAN_ROOM = 0.018
MIN_ZOOM_ROOM = 0.035

#: Extra zoom headroom used by the slow zoom presets.
ZOOM_IN_RANGE = 0.12
ZOOM_OUT_RANGE = 0.15

#: A combined pan+zoom move uses this fraction of the pan budget so the two
#: motions do not fight each other.
PAN_ZOOM_FACTOR = 0.6

#: Unit positions used to turn the deterministic direction names into a
#: movement vector.  ``center`` is handled as 0.5 on both axes.
_POSITION_UNIT = {
    "top_left": (0.0, 0.0),
    "top_right": (1.0, 0.0),
    "bottom_left": (0.0, 1.0),
    "bottom_right": (1.0, 1.0),
    "center": (0.5, 0.5),
}


# ===================================================================
# Helper function stubs (Tasks 04.02.02 — 04.02.07)
# ===================================================================
# These stubs will be replaced with full implementations in the
# subsequent tasks of SubPhase 04.02.

def load_and_prepare_image(
    image_path: str,
    resolution: Tuple[int, int],
    zoom_intensity: float,
    focus_x: float = 0.5,
    focus_y: float = 0.5,
) -> np.ndarray:
    """Load a source image and prepare it for Ken Burns animation.

    The source is first **cover-cropped to the render aspect ratio** with
    ``object-fit: cover`` semantics.  ``focus_x``/``focus_y`` select where
    the frame window sits inside the source image (``0.5`` = centred), so
    the frame shown in the editor is exactly the region the renderer uses.
    Everything outside that frame is discarded before Ken Burns runs.

    The cropped frame must be at least ``resolution × zoom_intensity``
    pixels in each dimension to provide sufficient "zoom headroom".  If it
    is smaller it is upscaled uniformly with LANCZOS resampling; if it is
    significantly larger (> 1.5× the minimum) it is downscaled to the
    minimum to limit memory usage during frame generation.

    Args:
        image_path: Absolute path to the source cover image.
        resolution: Target output ``(width, height)``.
        zoom_intensity: Zoom factor (≥ 1.0).
        focus_x: Horizontal frame position inside the source (0..1).
        focus_y: Vertical frame position inside the source (0..1).

    Returns:
        NumPy array of shape ``(H, W, 3)`` with dtype ``uint8``
        representing the prepared RGB image.

    Raises:
        ValueError: If the image file cannot be opened or is corrupted.
    """
    output_width, output_height = resolution

    # ------------------------------------------------------------------
    # Step 2: Load the image and convert to RGB
    # ------------------------------------------------------------------
    try:
        # OpenCV on Windows cannot open paths containing non-ASCII characters,
        # so use Pillow directly for those (and as a fallback for any other
        # file OpenCV fails to decode).
        img = None
        if str(image_path).isascii():
            img = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if img is None:
            with Image.open(image_path) as pil_img:
                img = np.array(pil_img.convert("RGB"), dtype=np.uint8)
        else:
            # OpenCV loads as BGR — convert to RGB for MoviePy
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    except Exception as exc:
        raise ValueError(
            f"Cannot open or read image file: {image_path}"
        ) from exc

    src_h, src_w = img.shape[:2]  # OpenCV returns (height, width)
    logger.debug(
        "load_and_prepare_image: loaded %s (%dx%d)",
        image_path, src_w, src_h,
    )

    # ------------------------------------------------------------------
    # Step 3: Cover-crop the source to the render aspect ratio
    # ------------------------------------------------------------------
    # This is the same geometry as CSS ``object-fit: cover``.  The focus
    # values are ``object-position`` percentages: 0.0 aligns the frame
    # with the left/top edge and 1.0 with the right/bottom edge.  Only
    # the region inside the frame is kept, so Ken Burns can never reveal
    # the parts of the image that are outside the editor's crop frame.
    target_aspect = output_width / output_height
    source_aspect = src_w / src_h
    focus_x = min(1.0, max(0.0, float(focus_x)))
    focus_y = min(1.0, max(0.0, float(focus_y)))

    if source_aspect > target_aspect:
        # Source is wider than the frame: trim left/right.
        frame_h = src_h
        frame_w = max(1, int(round(src_h * target_aspect)))
        max_offset_x = src_w - frame_w
        offset_x = int(round(focus_x * max_offset_x))
        img = img[:, offset_x : offset_x + frame_w]
        logger.debug(
            "  Cover-cropped horizontally: %dx%d → %dx%d (focus %.2f)",
            src_w, src_h, frame_w, frame_h, focus_x,
        )
    else:
        # Source is taller than (or equal to) the frame: trim top/bottom.
        frame_w = src_w
        frame_h = max(1, int(round(src_w / target_aspect)))
        max_offset_y = src_h - frame_h
        offset_y = int(round(focus_y * max_offset_y))
        img = img[offset_y : offset_y + frame_h, :]
        logger.debug(
            "  Cover-cropped vertically: %dx%d → %dx%d (focus %.2f)",
            src_w, src_h, frame_w, frame_h, focus_y,
        )

    img = np.ascontiguousarray(img)
    src_h, src_w = img.shape[:2]

    # ------------------------------------------------------------------
    # Step 4: Calculate minimum required dimensions
    # ------------------------------------------------------------------
    min_w = int(output_width * zoom_intensity)
    min_h = int(output_height * zoom_intensity)
    logger.debug(
        "  Minimum required: %dx%d (output %dx%d × zoom %.2f)",
        min_w, min_h, output_width, output_height, zoom_intensity,
    )

    # ------------------------------------------------------------------
    # Step 5: Upscale if necessary
    # ------------------------------------------------------------------
    if src_w < min_w or src_h < min_h:
        scale = max(min_w / src_w, min_h / src_h)
        new_w = max(min_w, int(round(src_w * scale)))
        new_h = max(min_h, int(round(src_h * scale)))

        logger.info(
            "  Upscaling frame from %dx%d to %dx%d "
            "(minimum required: %dx%d, scale factor: %.2f)",
            src_w, src_h, new_w, new_h, min_w, min_h, scale,
        )

        # cv2.INTER_LANCZOS4 for upscaling gives high quality
        img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
        src_h, src_w = img.shape[:2]

    # ------------------------------------------------------------------
    # Step 6: Downscale oversized frames to limit memory usage
    # ------------------------------------------------------------------
    # Moderately larger frames are kept at full size for slightly better
    # crop quality; anything above 1.5× the minimum is resized down.
    if src_w > min_w * 1.5 or src_h > min_h * 1.5:
        img = cv2.resize(
            img, (min_w, min_h), interpolation=cv2.INTER_AREA,
        )
        src_h, src_w = img.shape[:2]
        logger.debug(
            "  Downscaled oversized frame to %dx%d (memory optimisation)",
            src_w, src_h,
        )

    # ------------------------------------------------------------------
    # Step 7: Edge-case logging
    # ------------------------------------------------------------------
    final_h, final_w = img.shape[:2]
    if final_w == min_w and final_h == min_h:
        logger.debug(
            "  Frame exactly matches minimum size — "
            "zero pan range in both axes (zoom-only)."
        )

    # ------------------------------------------------------------------
    # Step 8: Return the NumPy array (already in correct format)
    # ------------------------------------------------------------------
    result = np.ascontiguousarray(img)
    logger.debug(
        "  Prepared image array: shape=%s, dtype=%s",
        result.shape, result.dtype,
    )
    return result


def calculate_crop_dimensions(
    output_width: int,
    output_height: int,
    zoom_intensity: float,
) -> Tuple[int, int]:
    """Calculate the crop-box dimensions for the Ken Burns effect.

    The crop box is the rectangular region extracted from the (upscaled)
    source image on every frame.  Its size is derived from the output
    resolution divided by the zoom intensity:

    .. math::

        \\text{crop\\_width}  = \\lfloor \\text{output\\_width}  / \\text{zoom\\_intensity} \\rfloor

        \\text{crop\\_height} = \\lfloor \\text{output\\_height} / \\text{zoom\\_intensity} \\rfloor

    Because the crop region is then resized **up** to fill the full
    output resolution, the viewer perceives a zoomed-in view of the
    source image.  A ``zoom_intensity`` of ``1.0`` produces crop
    dimensions equal to the output (no zoom).

    Args:
        output_width: Horizontal resolution of the output video (px).
        output_height: Vertical resolution of the output video (px).
        zoom_intensity: Zoom factor — must be > 0.  Typical default
            is ``1.3``.

    Returns:
        ``(crop_width, crop_height)`` as positive integers.

    Raises:
        ValueError: If *zoom_intensity* ≤ 0 or either output dimension
            is non-positive.

    Examples::

        >>> calculate_crop_dimensions(1920, 1080, 1.3)
        (1476, 830)
        >>> calculate_crop_dimensions(1920, 1080, 1.0)
        (1920, 1080)
        >>> calculate_crop_dimensions(1920, 1080, 2.0)
        (960, 540)
    """
    # --- Input validation ---
    if zoom_intensity <= 0:
        raise ValueError(
            f"zoom_intensity must be a positive number, got {zoom_intensity}"
        )
    if output_width <= 0 or output_height <= 0:
        raise ValueError(
            f"Output dimensions must be positive integers, "
            f"got {output_width}x{output_height}"
        )

    # --- Crop box formula (floor division) ---
    crop_width = int(output_width / zoom_intensity)
    crop_height = int(output_height / zoom_intensity)

    # --- Guard: ensure at least 1 px ---
    crop_width = max(1, crop_width)
    crop_height = max(1, crop_height)

    logger.debug(
        "calculate_crop_dimensions: %dx%d @ zoom %.2f → crop %dx%d",
        output_width, output_height, zoom_intensity,
        crop_width, crop_height,
    )

    return (crop_width, crop_height)


def get_pan_direction(
    segment_index: int,
) -> Tuple[str, str]:
    """Select a deterministic pan direction for a segment.

    Cycles through the :data:`DIRECTIONS` constant using
    ``segment_index % len(DIRECTIONS)`` (i.e. modulo 7).  This produces
    a repeating sequence of camera-motion directions across consecutive
    segments, ensuring visual variety while remaining fully
    deterministic — re-rendering the same project always yields
    identical results.

    The cycling sequence is:

    ====  ==========================
    idx   Direction
    ====  ==========================
    0     top_left → center
    1     bottom_right → top_left
    2     top_right → bottom_left
    3     bottom_left → top_right
    4     center → top_left
    5     center → bottom_right
    6     top_left → bottom_right
    7     (repeats from 0)
    ====  ==========================

    Args:
        segment_index: Zero-based sequence index of the current segment.

    Returns:
        ``(start_position_name, end_position_name)`` from
        :data:`DIRECTIONS`.
    """
    direction = DIRECTIONS[segment_index % len(DIRECTIONS)]
    logger.debug(
        "get_pan_direction: segment_index=%d → %s → %s",
        segment_index, direction[0], direction[1],
    )
    return direction


def position_to_coords(
    position: str,
    img_w: int,
    img_h: int,
    crop_w: int,
    crop_h: int,
) -> Tuple[int, int]:
    """Map a position name to the top-left crop-box pixel coordinate.

    The crop box is a rectangle of size ``(crop_w, crop_h)`` that must
    fit within the source image of size ``(img_w, img_h)``.  The maximum
    valid placement coordinates are:

    * ``max_x = img_w - crop_w``  (rightmost x)
    * ``max_y = img_h - crop_h``  (bottommost y)

    Position mapping:

    ================  ======================
    Position name     Coordinates
    ================  ======================
    ``top_left``      ``(0, 0)``
    ``top_right``     ``(max_x, 0)``
    ``bottom_left``   ``(0, max_y)``
    ``bottom_right``  ``(max_x, max_y)``
    ``center``        ``(max_x // 2, max_y // 2)``
    ================  ======================

    Args:
        position: One of ``"center"``, ``"top_left"``, ``"top_right"``,
            ``"bottom_left"``, ``"bottom_right"``.
        img_w: Width of the prepared source image in pixels.
        img_h: Height of the prepared source image in pixels.
        crop_w: Width of the crop box in pixels.
        crop_h: Height of the crop box in pixels.

    Returns:
        ``(x, y)`` — the top-left corner of the crop box as
        non-negative integers.

    Raises:
        ValueError: If *position* is not a recognised name.
    """
    max_x = img_w - crop_w
    max_y = img_h - crop_h

    # Warn if there is zero movement range in either axis
    if max_x == 0:
        logger.debug(
            "position_to_coords: max_x is 0 — no horizontal pan range "
            "(img_w=%d, crop_w=%d)", img_w, crop_w,
        )
    if max_y == 0:
        logger.debug(
            "position_to_coords: max_y is 0 — no vertical pan range "
            "(img_h=%d, crop_h=%d)", img_h, crop_h,
        )

    mapping = {
        "top_left": (0, 0),
        "top_right": (max_x, 0),
        "bottom_left": (0, max_y),
        "bottom_right": (max_x, max_y),
        "center": (max_x // 2, max_y // 2),
    }

    if position not in mapping:
        valid = ", ".join(sorted(mapping.keys()))
        raise ValueError(
            f"Unknown position name '{position}'. "
            f"Valid names are: {valid}"
        )

    x, y = mapping[position]

    # Clamp to non-negative (guard against unexpected edge cases)
    x = max(0, x)
    y = max(0, y)

    return (x, y)


def get_focus_area_bounds(
    focus_area: dict,
    source_width: int,
    source_height: int,
    crop_width: int,
    crop_height: int,
) -> Tuple[int, int, int, int]:
    """Translate a normalised focus rectangle into crop-position bounds.

    The returned ``(min_x, max_x, min_y, max_y)`` describe every top-left
    crop position that still keeps the marked subject inside the crop.
    When the rectangle is larger than the crop (for example a focus area
    that fills most of the frame), the bounds collapse to its centre.

    Args:
        focus_area: ``{"x", "y", "w", "h"}`` normalised to the frame.
        source_width: Width of the prepared frame in pixels.
        source_height: Height of the prepared frame in pixels.
        crop_width: Width of the Ken Burns crop box in pixels.
        crop_height: Height of the Ken Burns crop box in pixels.

    Returns:
        ``(min_x, max_x, min_y, max_y)`` as non-negative integers.
    """
    fx = int(round(float(focus_area['x']) * source_width))
    fy = int(round(float(focus_area['y']) * source_height))
    fw = max(1, int(round(float(focus_area['w']) * source_width)))
    fh = max(1, int(round(float(focus_area['h']) * source_height)))

    # Clamp a rectangle that slightly overflows after rounding.
    fx = max(0, min(fx, source_width - 1))
    fy = max(0, min(fy, source_height - 1))
    fw = max(1, min(fw, source_width - fx))
    fh = max(1, min(fh, source_height - fy))

    # To keep the focus rectangle inside the crop:
    #   crop_left <= fx                 → left <= fx
    #   crop_left >= fx + fw - crop_w   → left >= fx + fw - crop_w
    min_x = max(0, fx + fw - crop_width)
    max_x = min(source_width - crop_width, fx)
    min_y = max(0, fy + fh - crop_height)
    max_y = min(source_height - crop_height, fy)

    if min_x > max_x:
        centre = fx + fw // 2 - crop_width // 2
        min_x = max_x = max(0, min(centre, source_width - crop_width))
    if min_y > max_y:
        centre = fy + fh // 2 - crop_height // 2
        min_y = max_y = max(0, min(centre, source_height - crop_height))

    return (min_x, max_x, min_y, max_y)


def normalise_focus_areas(focus_areas) -> list[dict]:
    """Normalise one rectangle or a legacy list into a single clean list.

    Older segments store a single rectangle in ``image_focus_area``; newer
    ones store a list in ``image_focus_areas``.  Both shapes are accepted so
    the renderer has one code path.  Only **one** rectangle is supported per
    image (``MAX_FOCUS_AREAS``), so any extra legacy entries are ignored
    without mutating the stored project data.  Invalid entries are skipped
    rather than crashing a render, and rectangles are clipped to the frame.
    """
    if not focus_areas:
        return []
    items = [focus_areas] if isinstance(focus_areas, dict) else focus_areas
    areas: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            x = float(item['x'])
            y = float(item['y'])
            w = float(item['w'])
            h = float(item['h'])
        except (KeyError, TypeError, ValueError):
            continue
        if not all(0.0 <= number <= 1.0 for number in (x, y, w, h)):
            continue
        w = min(w, 1.0 - x)
        h = min(h, 1.0 - y)
        if w <= 0.0 or h <= 0.0:
            continue
        areas.append({'x': x, 'y': y, 'w': w, 'h': h})
    return areas[:MAX_FOCUS_AREAS]


def focus_area_inside_crop(
    focus_area: dict,
    x: int,
    y: int,
    crop_width: int,
    crop_height: int,
    source_width: int,
    source_height: int,
    tolerance: float = 1.0,
) -> bool:
    """Return ``True`` when the crop still fully contains the subject.

    Used by the planner and its tests as the single containment contract:
    the highlighted rectangle must never leave the visible frame, at any
    point in the animation.
    """
    fx = float(focus_area['x']) * source_width
    fy = float(focus_area['y']) * source_height
    fw = float(focus_area['w']) * source_width
    fh = float(focus_area['h']) * source_height
    return (
        x <= fx + tolerance
        and y <= fy + tolerance
        and x + crop_width >= fx + fw - tolerance
        and y + crop_height >= fy + fh - tolerance
    )


def _crop_for_scale(
    base_width: int,
    base_height: int,
    scale: float,
    source_width: int,
    source_height: int,
) -> Tuple[int, int]:
    """Return crop dimensions for *scale*, clamped to the prepared frame."""
    crop_w = max(1, min(source_width, int(round(base_width * scale))))
    crop_h = max(1, min(source_height, int(round(base_height * scale))))
    return crop_w, crop_h


def _focus_bounds_for_crop(
    focus_area: dict | None,
    source_width: int,
    source_height: int,
    crop_width: int,
    crop_height: int,
) -> Tuple[int, int, int, int]:
    """Allowed crop top-left range for the current crop size."""
    if focus_area:
        return get_focus_area_bounds(
            focus_area, source_width, source_height, crop_width, crop_height,
        )
    return (
        0,
        max(0, source_width - crop_width),
        0,
        max(0, source_height - crop_height),
    )


def _centre_range(
    bounds: Tuple[int, int, int, int],
    crop_width: int,
    crop_height: int,
) -> Tuple[float, float, float, float]:
    """Convert top-left bounds into the matching crop-centre range."""
    return (
        bounds[0] + crop_width / 2.0,
        bounds[1] + crop_width / 2.0,
        bounds[2] + crop_height / 2.0,
        bounds[3] + crop_height / 2.0,
    )


def _direction_vector(segment_index: int) -> Tuple[int, int, str, str]:
    """Turn the deterministic direction preset into a sign vector."""
    start_name, end_name = get_pan_direction(segment_index)
    sx, sy = _POSITION_UNIT[start_name]
    ex, ey = _POSITION_UNIT[end_name]

    def sign(value: float) -> int:
        if value > 0.001:
            return 1
        if value < -0.001:
            return -1
        return 0

    return sign(ex - sx), sign(ey - sy), start_name, end_name


def _select_motion(
    preferred: str,
    pan_room: float,
    zoom_in_room: float,
    zoom_out_room: float,
) -> str:
    """Adapt the preferred preset to the room actually available.

    A large subject leaves little panning space, so the planner substitutes a
    slow zoom (or the reverse for a small subject) instead of producing a
    barely visible pan.  When nothing has enough room the pan is kept, but the
    caller shortens it to the available travel instead of rushing.
    """
    if preferred == MOTION_PAN_ZOOM:
        if (
            pan_room >= MIN_PAN_ROOM
            or zoom_in_room >= MIN_ZOOM_ROOM
            or zoom_out_room >= MIN_ZOOM_ROOM
        ):
            return MOTION_PAN_ZOOM
        return MOTION_PAN

    if preferred == MOTION_ZOOM_IN:
        if zoom_in_room >= MIN_ZOOM_ROOM:
            return MOTION_ZOOM_IN
        if pan_room >= MIN_PAN_ROOM:
            return MOTION_PAN
        if zoom_out_room >= MIN_ZOOM_ROOM:
            return MOTION_ZOOM_OUT
        return MOTION_PAN

    if preferred == MOTION_ZOOM_OUT:
        if zoom_out_room >= MIN_ZOOM_ROOM:
            return MOTION_ZOOM_OUT
        if pan_room >= MIN_PAN_ROOM:
            return MOTION_PAN
        if zoom_in_room >= MIN_ZOOM_ROOM:
            return MOTION_ZOOM_IN
        return MOTION_PAN

    # Preferred pan: zoom only when the subject leaves too little travel.
    if pan_room >= MIN_PAN_ROOM:
        return MOTION_PAN
    if zoom_in_room >= MIN_ZOOM_ROOM:
        return MOTION_ZOOM_IN
    if zoom_out_room >= MIN_ZOOM_ROOM:
        return MOTION_ZOOM_OUT
    return MOTION_PAN


def plan_ken_burns_motion(
    segment_index: int,
    duration: float,
    source_width: int,
    source_height: int,
    output_width: int,
    output_height: int,
    zoom_intensity: float,
    focus_area: dict | None = None,
) -> dict:
    """Build a deterministic, subject-aware Ken Burns motion plan.

    The planner measures the free space around the highlighted rectangle and
    chooses one of four motions for the clip:

    * ``pan`` — a comfortable horizontal/diagonal sweep.
    * ``zoom_in`` / ``zoom_out`` — a slow, subtle zoom.
    * ``pan_zoom`` — both at reduced strength.

    The crop is never allowed to shrink below the rectangle, so the marked
    subject stays inside the frame for the whole animation.  Pan distance is
    derived from a target on-screen speed and then capped by the available
    room; a large subject therefore moves more slowly (or zooms instead)
    rather than being rushed across the frame.

    Returns:
        A dictionary consumed by :func:`sample_ken_burns_motion`.
    """
    base_width, base_height = calculate_crop_dimensions(
        output_width, output_height, zoom_intensity,
    )
    areas = normalise_focus_areas(focus_area)
    subject = areas[0] if areas else None

    focus_width, focus_height = calculate_focus_crop_dimensions(
        output_width, output_height, zoom_intensity, subject,
        source_width, source_height,
    )
    min_scale = max(
        focus_width / base_width if base_width else 1.0,
        focus_height / base_height if base_height else 1.0,
        1.0,
    )
    max_scale = min(
        source_width / base_width if base_width else 1.0,
        source_height / base_height if base_height else 1.0,
    )
    min_scale = min(min_scale, max_scale)
    min_scale = max(0.05, min_scale)

    # --- Measure available pan room at the subject-safe crop -------------
    pan_crop_w, pan_crop_h = _crop_for_scale(
        base_width, base_height, min_scale, source_width, source_height,
    )
    pan_bounds = _focus_bounds_for_crop(
        subject, source_width, source_height, pan_crop_w, pan_crop_h,
    )
    room_x_px = max(0, pan_bounds[1] - pan_bounds[0])
    room_y_px = max(0, pan_bounds[3] - pan_bounds[2])
    pan_room = max(
        room_x_px / pan_crop_w if pan_crop_w else 0.0,
        room_y_px / pan_crop_h if pan_crop_h else 0.0,
    )

    # --- Measure available zoom headroom ---------------------------------
    # The zoom span follows the same practical-speed idea as the pan: it is
    # proportional to the clip length, then capped by the fixed preset range
    # and by how much room the prepared source frame actually provides.
    effective_duration = max(0.0, float(duration))
    zoom_in_span = min(ZOOM_IN_RANGE, ZOOM_RATE_TARGET * effective_duration)
    zoom_out_span = min(ZOOM_OUT_RANGE, ZOOM_RATE_TARGET * effective_duration)
    zoom_in_start_scale = min(
        max_scale, min_scale * (1.0 + zoom_in_span),
    )
    zoom_out_end_scale = min(
        max_scale, min_scale * (1.0 + zoom_out_span),
    )
    zoom_in_room = max(0.0, zoom_in_start_scale - min_scale)
    zoom_out_room = max(0.0, zoom_out_end_scale - min_scale)

    preferred = MOTION_PRESETS[segment_index % len(MOTION_PRESETS)]
    motion = _select_motion(
        preferred, pan_room, zoom_in_room, zoom_out_room,
    )

    # --- Resolve the endpoint scales -------------------------------------
    start_scale = end_scale = min_scale
    pan_factor = 0.0
    if motion == MOTION_ZOOM_IN:
        start_scale, end_scale = zoom_in_start_scale, min_scale
    elif motion == MOTION_ZOOM_OUT:
        start_scale, end_scale = min_scale, zoom_out_end_scale
    elif motion == MOTION_PAN_ZOOM:
        pan_factor = PAN_ZOOM_FACTOR
        prefer_in = zoom_in_room >= MIN_ZOOM_ROOM and (
            zoom_out_room < MIN_ZOOM_ROOM or segment_index % 2 == 0
        )
        if prefer_in:
            start_scale, end_scale = zoom_in_start_scale, min_scale
        elif zoom_out_room >= MIN_ZOOM_ROOM:
            start_scale, end_scale = min_scale, zoom_out_end_scale
        else:
            motion = MOTION_PAN

    start_crop = _crop_for_scale(
        base_width, base_height, start_scale, source_width, source_height,
    )
    end_crop = _crop_for_scale(
        base_width, base_height, end_scale, source_width, source_height,
    )

    # --- Pan distance: target speed, capped by the free space ------------
    direction_x, direction_y, start_name, end_name = _direction_vector(
        segment_index,
    )
    if motion == MOTION_PAN:
        pan_factor = 1.0

    reference_crop_w = (start_crop[0] + end_crop[0]) / 2.0
    reference_crop_h = (start_crop[1] + end_crop[1]) / 2.0
    target_x = (
        abs(direction_x) * PAN_SPEED_TARGET * max(0.0, duration)
        * reference_crop_w * pan_factor
    )
    target_y = (
        abs(direction_y) * PAN_SPEED_TARGET * max(0.0, duration)
        * reference_crop_h * pan_factor
    )
    travel_x = min(room_x_px, target_x)
    travel_y = min(room_y_px, target_y)

    start_bounds = _focus_bounds_for_crop(
        subject, source_width, source_height, *start_crop,
    )
    end_bounds = _focus_bounds_for_crop(
        subject, source_width, source_height, *end_crop,
    )
    start_centre_range = _centre_range(start_bounds, *start_crop)
    end_centre_range = _centre_range(end_bounds, *end_crop)

    if direction_x > 0:
        start_cx = (
            (start_centre_range[0] + start_centre_range[1]) / 2.0
            - travel_x / 2.0
        )
        end_cx = (
            (end_centre_range[0] + end_centre_range[1]) / 2.0
            + travel_x / 2.0
        )
    elif direction_x < 0:
        start_cx = (
            (start_centre_range[0] + start_centre_range[1]) / 2.0
            + travel_x / 2.0
        )
        end_cx = (
            (end_centre_range[0] + end_centre_range[1]) / 2.0
            - travel_x / 2.0
        )
    else:
        start_cx = (start_centre_range[0] + start_centre_range[1]) / 2.0
        end_cx = (end_centre_range[0] + end_centre_range[1]) / 2.0

    if direction_y > 0:
        start_cy = (
            (start_centre_range[2] + start_centre_range[3]) / 2.0
            - travel_y / 2.0
        )
        end_cy = (
            (end_centre_range[2] + end_centre_range[3]) / 2.0
            + travel_y / 2.0
        )
    elif direction_y < 0:
        start_cy = (
            (start_centre_range[2] + start_centre_range[3]) / 2.0
            + travel_y / 2.0
        )
        end_cy = (
            (end_centre_range[2] + end_centre_range[3]) / 2.0
            - travel_y / 2.0
        )
    else:
        start_cy = (start_centre_range[2] + start_centre_range[3]) / 2.0
        end_cy = (end_centre_range[2] + end_centre_range[3]) / 2.0

    # Keep both keyframes inside the containment bounds, including when the
    # crop changes size for a zoom.
    start_cx = min(max(start_cx, start_centre_range[0]), start_centre_range[1])
    end_cx = min(max(end_cx, end_centre_range[0]), end_centre_range[1])
    start_cy = min(max(start_cy, start_centre_range[2]), start_centre_range[3])
    end_cy = min(max(end_cy, end_centre_range[2]), end_centre_range[3])

    pan_speed = 0.0
    if duration > 0:
        pan_speed = max(
            travel_x / (duration * max(1.0, reference_crop_w)),
            travel_y / (duration * max(1.0, reference_crop_h)),
        )
    zoom_speed = abs(end_scale - start_scale) / duration if duration > 0 else 0.0

    plan = {
        "motion": motion,
        "duration": float(duration),
        "source_width": int(source_width),
        "source_height": int(source_height),
        "focus_area": subject,
        "start_scale": float(start_scale),
        "end_scale": float(end_scale),
        "start_crop": start_crop,
        "end_crop": end_crop,
        "start_centre": (float(start_cx), float(start_cy)),
        "end_centre": (float(end_cx), float(end_cy)),
        "pan_speed": float(pan_speed),
        "zoom_speed": float(zoom_speed),
        "pan_room": float(pan_room),
        "zoom_room": float(max(zoom_in_room, zoom_out_room)),
        "direction": (direction_x, direction_y, start_name, end_name),
    }
    logger.debug(
        "plan_ken_burns_motion: segment=%d motion=%s pan_room=%.3f "
        "zoom_room=%.3f pan_speed=%.4f zoom_speed=%.4f",
        segment_index, motion, pan_room, plan["zoom_room"],
        pan_speed, zoom_speed,
    )
    return plan


def sample_ken_burns_motion(
    plan: dict,
    t: float,
    duration: float | None = None,
) -> Tuple[int, int, int, int]:
    """Sample a motion plan at time *t*.

    Returns ``(x, y, crop_width, crop_height)`` where ``x``/``y`` are the
    top-left corner of the crop.  The position is clamped to the subject
    bounds for the *current* crop size on every frame, so a highlighted
    rectangle can never leave the rendered frame, even mid-zoom.
    """
    span = plan.get("duration", 0.0) if duration is None else duration
    if span is None or span <= 0:
        progress = 0.0
    else:
        progress = max(0.0, min(1.0, float(t) / float(span)))
    eased = progress * progress * (3.0 - 2.0 * progress)

    start_crop = plan["start_crop"]
    end_crop = plan["end_crop"]
    crop_w = int(round(start_crop[0] + (end_crop[0] - start_crop[0]) * eased))
    crop_h = int(round(start_crop[1] + (end_crop[1] - start_crop[1]) * eased))

    source_w = int(plan["source_width"])
    source_h = int(plan["source_height"])
    crop_w = max(1, min(source_w, crop_w))
    crop_h = max(1, min(source_h, crop_h))

    start_cx, start_cy = plan["start_centre"]
    end_cx, end_cy = plan["end_centre"]
    cx = start_cx + (end_cx - start_cx) * eased
    cy = start_cy + (end_cy - start_cy) * eased

    x = int(round(cx - crop_w / 2.0))
    y = int(round(cy - crop_h / 2.0))
    x = max(0, min(x, source_w - crop_w))
    y = max(0, min(y, source_h - crop_h))

    subject = plan.get("focus_area")
    if subject:
        bounds = get_focus_area_bounds(
            subject, source_w, source_h, crop_w, crop_h,
        )
        x = max(bounds[0], min(x, bounds[1]))
        y = max(bounds[2], min(y, bounds[3]))

    return x, y, crop_w, crop_h


def get_focus_camera_path(
    focus_areas,
    source_width: int,
    source_height: int,
    crop_width: int,
    crop_height: int,
) -> list[Tuple[int, int]]:
    """Return the crop top-left positions that centre each focus area.

    Each entry is the crop position whose centre sits on the centre of the
    matching subject rectangle (clamped inside the prepared frame).  With two
    or more areas the Ken Burns camera travels through this ordered path, so
    every marked subject is centred in turn.
    """
    areas = normalise_focus_areas(focus_areas)
    if not areas:
        return []

    max_x = max(0, source_width - crop_width)
    max_y = max(0, source_height - crop_height)
    path: list[Tuple[int, int]] = []
    for area in areas:
        centre_x = (area['x'] + area['w'] / 2.0) * source_width
        centre_y = (area['y'] + area['h'] / 2.0) * source_height
        x = int(round(centre_x - crop_width / 2.0))
        y = int(round(centre_y - crop_height / 2.0))
        path.append((max(0, min(x, max_x)), max(0, min(y, max_y))))
    logger.debug(
        "get_focus_camera_path: %d area(s) → %s", len(areas), path
    )
    return path


def interpolate_focus_path(
    path: list[Tuple[int, int]],
    t: float,
    duration: float,
) -> Tuple[float, float]:
    """Interpolate the camera position along an ordered focus path.

    Keyframes are spread evenly over the clip: the first area is centred at
    ``t=0``, the last at ``t=duration``, and every intermediate area is
    centred at its proportional time.  Each leg uses smoothstep easing so the
    camera settles on a subject instead of whipping past it.
    """
    if not path:
        return (0.0, 0.0)
    if len(path) == 1 or duration <= 0:
        return (float(path[0][0]), float(path[0][1]))

    progress = max(0.0, min(1.0, t / duration))
    legs = len(path) - 1
    scaled = progress * legs
    index = min(int(scaled), legs - 1)
    local = scaled - index
    # Smoothstep: zero velocity at both keyframes.
    eased = local * local * (3.0 - 2.0 * local)

    start = path[index]
    end = path[index + 1]
    return (
        start[0] + (end[0] - start[0]) * eased,
        start[1] + (end[1] - start[1]) * eased,
    )


def get_position_in_bounds(
    position: str,
    bounds: Tuple[int, int, int, int],
) -> Tuple[int, int]:
    """Map a direction position name inside focus-area crop bounds."""
    min_x, max_x, min_y, max_y = bounds
    mapping = {
        'top_left': (min_x, min_y),
        'top_right': (max_x, min_y),
        'bottom_left': (min_x, max_y),
        'bottom_right': (max_x, max_y),
        'center': ((min_x + max_x) // 2, (min_y + max_y) // 2),
    }
    if position not in mapping:
        valid = ', '.join(sorted(mapping.keys()))
        raise ValueError(
            f"Unknown position name '{position}'. Valid names are: {valid}"
        )
    return mapping[position]


def get_focus_sweep_coords(
    start_name: str,
    end_name: str,
    focus_area: dict,
    source_width: int,
    source_height: int,
    crop_width: int,
    crop_height: int,
    spread: float = 0.5,
) -> Tuple[Tuple[int, int], Tuple[int, int]]:
    """Return a gentle pan path centred on a single marked subject.

    The full bounds allow the crop to travel from one side of the subject
    to the other.  Pulling those endpoints toward the bounds centre by
    ``spread`` keeps the subject near the middle of the frame while still
    giving the shot visible motion.
    """
    bounds = get_focus_area_bounds(
        focus_area, source_width, source_height, crop_width, crop_height,
    )
    start = get_position_in_bounds(start_name, bounds)
    end = get_position_in_bounds(end_name, bounds)
    centre_x = (bounds[0] + bounds[1]) / 2.0
    centre_y = (bounds[2] + bounds[3]) / 2.0
    spread = max(0.0, min(1.0, float(spread)))

    def settled(point: Tuple[int, int]) -> Tuple[int, int]:
        return (
            int(round(centre_x + (point[0] - centre_x) * spread)),
            int(round(centre_y + (point[1] - centre_y) * spread)),
        )

    return settled(start), settled(end)


def get_start_end_coords(
    start_name: str,
    end_name: str,
    source_width: int,
    source_height: int,
    crop_width: int,
    crop_height: int,
    focus_area: dict | None = None,
) -> Tuple[Tuple[int, int], Tuple[int, int]]:
    """Compute start and end crop-box positions for the Ken Burns pan.

    Convenience wrapper around :func:`position_to_coords` that resolves
    both the start and end position names in a single call.

    Args:
        start_name: Position name for the beginning of the pan
            (e.g. ``"top_left"``).
        end_name: Position name for the end of the pan
            (e.g. ``"bottom_right"``).
        source_width: Width of the prepared source image in pixels.
        source_height: Height of the prepared source image in pixels.
        crop_width: Width of the crop box in pixels.
        crop_height: Height of the crop box in pixels.
        focus_area: Optional normalised subject rectangle.  When supplied,
            the pan happens inside the region that keeps the subject
            visible instead of across the whole frame.

    Returns:
        ``((start_x, start_y), (end_x, end_y))`` — top-left corner of
        the crop box at the beginning and end of the clip.

    Raises:
        ValueError: If either position name is not recognised.
    """
    if focus_area:
        bounds = get_focus_area_bounds(
            focus_area, source_width, source_height,
            crop_width, crop_height,
        )
        return (
            get_position_in_bounds(start_name, bounds),
            get_position_in_bounds(end_name, bounds),
        )

    start = position_to_coords(
        start_name, source_width, source_height, crop_width, crop_height
    )
    end = position_to_coords(
        end_name, source_width, source_height, crop_width, crop_height
    )
    return (start, end)


def calculate_focus_crop_dimensions(
    output_width: int,
    output_height: int,
    zoom_intensity: float,
    focus_area,
    source_width: int,
    source_height: int,
) -> Tuple[int, int]:
    """Grow the crop box just enough to keep the marked subject in view.

    ``focus_area`` may be a single rectangle or the legacy list form (only
    the first entry is used).  The base crop is the normal zoom crop.  If
    the subject is larger than that crop, the box is scaled up (zooming out)
    with a small padding until it contains the subject, then capped at the
    prepared frame size.
    """
    base_crop_w, base_crop_h = calculate_crop_dimensions(
        output_width, output_height, zoom_intensity
    )
    areas = normalise_focus_areas(focus_area)
    if not areas:
        return base_crop_w, base_crop_h

    focus_w = max(area['w'] for area in areas)
    focus_h = max(area['h'] for area in areas)
    padding = 1.1
    # The rectangles are normalised to the *prepared source frame*, so their
    # pixel size is measured against source_width/source_height.  Using the
    # output resolution here (as an earlier version did) underestimates large
    # subjects whenever the prepared frame is bigger than the output, which
    # could let the subject leave the crop.
    needed_scale = max(
        (focus_w * source_width) / base_crop_w,
        (focus_h * source_height) / base_crop_h,
        1.0,
    ) * padding
    max_scale = min(
        source_width / base_crop_w,
        source_height / base_crop_h,
    )
    scale = min(needed_scale, max_scale)

    crop_w = max(1, min(source_width, int(round(base_crop_w * scale))))
    crop_h = max(1, min(source_height, int(round(base_crop_h * scale))))
    logger.debug(
        "calculate_focus_crop_dimensions: base %dx%d → focus %dx%d "
        "(scale %.2f, subject %.2f×%.2f, %d area(s))",
        base_crop_w, base_crop_h, crop_w, crop_h, scale,
        focus_w, focus_h, len(areas),
    )
    return crop_w, crop_h


def interpolate_position(
    start: Tuple[float, float],
    end: Tuple[float, float],
    t: float,
    duration: float,
) -> Tuple[float, float]:
    """Linearly interpolate the crop-box position between *start* and *end*.

    Computes the camera's top-left crop-box coordinate at time *t* using
    the standard linear interpolation formula applied independently to
    each axis:

    .. math::

        x(t) = x_{\\text{start}} + (x_{\\text{end}} - x_{\\text{start}})
               \\cdot \\text{progress}

        y(t) = y_{\\text{start}} + (y_{\\text{end}} - y_{\\text{start}})
               \\cdot \\text{progress}

    where ``progress = clamp(t / duration, 0, 1)``.

    The progress ratio is clamped to ``[0, 1]`` so that floating-point
    overshoot from MoviePy (e.g. ``t = -1e-15`` or ``t = duration + ε``)
    never causes the crop box to exceed its intended start/end bounds.

    Args:
        start: ``(x, y)`` pixel coordinates of the crop-box top-left
            corner at the beginning of the clip (``t = 0``).
        end: ``(x, y)`` pixel coordinates of the crop-box top-left
            corner at the end of the clip (``t = duration``).
        t: Current time in seconds (from MoviePy's ``make_frame``).
        duration: Total clip duration in seconds.

    Returns:
        ``(x, y)`` as floats — the interpolated position at time *t*.
        Conversion to integer pixel coordinates should be done by the
        caller (e.g. ``int(round(x))``).
    """
    # Edge case: zero or negative duration — no time span to interpolate
    if duration <= 0:
        return (float(start[0]), float(start[1]))

    # Compute progress ratio, clamped to [0.0, 1.0]
    progress = max(0.0, min(1.0, t / duration))

    # Linear interpolation on each axis independently
    x = start[0] + (end[0] - start[0]) * progress
    y = start[1] + (end[1] - start[1]) * progress

    return (x, y)


# ===================================================================
# Main public interface
# ===================================================================

def apply_ken_burns(
    image_path: str,
    duration: float,
    resolution: Tuple[int, int],
    zoom_intensity: float = 1.3,
    fps: int = 30,
    segment_index: int = 0,
    focus_x: float = 0.5,
    focus_y: float = 0.5,
    focus_area: dict | None = None,
    focus_areas: list | None = None,
) -> VideoClip:
    """Apply the Ken Burns (zoom-and-pan) effect to a still image.

    Converts a static cover image into a MoviePy :class:`VideoClip` with
    animated camera motion.  A smart planner measures the free space
    around the optional highlighted subject and chooses a pan, a slow
    zoom, or a combined move with a comfortable speed.  The crop centre
    and size are interpolated together, and the crop is clamped to the
    subject-safe bounds on every frame.

    Algorithm overview
    ------------------
    1. Load and prepare the source image (upscale for zoom headroom).
    2. Measure the subject rectangle and available pan/zoom room.
    3. Choose a deterministic motion preset and adapt its speed to the
       available room (large subjects pan less, or zoom instead).
    4. Build a ``make_frame(t)`` closure that samples the motion plan and
       extracts the region for each time instant.
    5. Construct and return a :class:`VideoClip`.

    Args:
        image_path: Absolute file-system path to the source cover image.
        duration: Length in seconds the clip should play (matches audio).
        resolution: Output video dimensions as ``(width, height)``,
            e.g. ``(1920, 1080)``.
        zoom_intensity: Zoom factor read from GlobalSettings.  ``1.0``
            means no zoom; values > 1.0 create a zoom-in effect.
            Defaults to ``1.3``.
        fps: Frames per second for the output VideoClip.  Should match
            the project framerate setting.  Defaults to ``30``.
        segment_index: Zero-based index of this segment within the
            project, used to deterministically select the pan direction.
            Defaults to ``0``.
        focus_x: Horizontal position of the render frame inside the
            source image (0..1).  Defaults to centred.
        focus_y: Vertical position of the render frame inside the source
            image (0..1).  Defaults to centred.
        focus_area: Optional ``{"x", "y", "w", "h"}`` subject rectangle
            normalised to the prepared frame.  The planner keeps this
            rectangle inside the rendered frame for the whole animation
            and adapts the motion speed to the free space around it.
        focus_areas: Legacy list form of ``focus_area``.  Only the first
            valid rectangle is used; the rest are ignored so old projects
            can still be rendered without rewriting their stored data.

    Returns:
        A MoviePy :class:`VideoClip` with the specified duration and FPS,
        whose ``make_frame`` callback generates each frame by
        interpolating the camera position and extracting the appropriate
        crop from the source image.
    """
    output_width, output_height = resolution

    logger.info(
        "apply_ken_burns called: image=%s, duration=%.2fs, "
        "resolution=%dx%d, zoom=%.2f, fps=%d, segment_index=%d",
        image_path,
        duration,
        output_width,
        output_height,
        zoom_intensity,
        fps,
        segment_index,
    )

    # ------------------------------------------------------------------
    # 1. Load and prepare the source image
    # ------------------------------------------------------------------
    source_image = load_and_prepare_image(
        image_path, resolution, zoom_intensity, focus_x, focus_y,
    )
    source_height, source_width = source_image.shape[:2]
    logger.debug(
        "  Source image prepared: %dx%d", source_width, source_height
    )

    # ------------------------------------------------------------------
    # 2. Build the smart motion plan
    # ------------------------------------------------------------------
    # ``image_focus_areas`` is the newer field; ``image_focus_area`` is the
    # legacy single-rectangle field.  Only one subject rectangle is
    # supported, so the first valid entry wins.  The planner measures the
    # free space around it and picks pan/zoom motion with a practical speed.
    areas = normalise_focus_areas(focus_areas) or normalise_focus_areas(
        focus_area
    )
    motion_plan = plan_ken_burns_motion(
        segment_index=segment_index,
        duration=duration,
        source_width=source_width,
        source_height=source_height,
        output_width=output_width,
        output_height=output_height,
        zoom_intensity=zoom_intensity,
        focus_area=areas[0] if areas else None,
    )
    logger.debug(
        "  Motion plan: %s (pan %.4f, zoom %.4f)",
        motion_plan["motion"], motion_plan["pan_speed"],
        motion_plan["zoom_speed"],
    )

    # ------------------------------------------------------------------
    # 3. Define the make_frame closure (Task 04.02.06)
    # ------------------------------------------------------------------

    def make_frame(t: float) -> np.ndarray:
        """Generate a single frame at time *t* by interpolating the crop.

        Called by MoviePy once per frame during rendering.  The closure
        captures the source image, camera keyframes, crop dimensions,
        output resolution, and duration from the enclosing
        :func:`apply_ken_burns` scope.

        Algorithm per frame:

        1. Sample the motion plan: interpolate both the crop centre and
           the crop size, then clamp to the subject-safe bounds.
        2. Round to integer pixel coordinates.
        3. Extract the crop via NumPy slicing ``[y:y+h, x:x+w]``
           (O(1) view, no data copy).
        4. Resize the crop to the output resolution via OpenCV
           (3–5× faster than Pillow LANCZOS, no conversion overhead).
        5. Return a contiguous ``uint8`` NumPy array.

        Performance notes:

        * **OpenCV ``cv2.resize``** eliminates the NumPy→PIL→resize→
          PIL→NumPy round-trip, giving 3–5× speedup per frame.
        * ``cv2.INTER_AREA`` for downsampling (best anti-aliasing)
          and ``cv2.INTER_LINEAR`` for upsampling (fast + good quality).
        * The resize operation is the only per-frame allocation; NumPy
          slicing is O(1).

        Args:
            t: Current time in seconds within the clip.

        Returns:
            NumPy array of shape ``(output_height, output_width, 3)``
            with dtype ``uint8``.
        """
        # Step 1: Sample the subject-aware motion plan.  The sampler
        # interpolates the crop centre and size together and clamps every
        # frame to the bounds that keep the highlighted area visible.
        x, y, crop_width, crop_height = sample_ken_burns_motion(
            motion_plan, t, duration,
        )

        # Step 2: Extract crop region via NumPy array slicing (rows=y, cols=x).
        # NumPy slicing returns a *view* into the existing array — an O(1)
        # operation regardless of crop size.
        crop = source_image[y : y + crop_height, x : x + crop_width]

        # Step 3: Resize crop to output resolution using OpenCV
        # cv2.INTER_AREA for downsampling (superior anti-aliasing),
        # cv2.INTER_LINEAR for upsampling (fast + good quality).
        is_downscale = (
            crop_width > output_width or crop_height > output_height
        )
        interp = cv2.INTER_AREA if is_downscale else cv2.INTER_LINEAR
        frame = cv2.resize(
            crop, (output_width, output_height), interpolation=interp
        )

        # Step 4: Ensure contiguous memory layout for MoviePy
        return np.ascontiguousarray(frame)

    # ------------------------------------------------------------------
    # 6. Construct and return the VideoClip
    # ------------------------------------------------------------------
    # Performance expectations:
    #
    # With OpenCV cv2.resize (INTER_LINEAR / INTER_AREA), per-frame
    # cost is ~2–4 ms at 1080p, compared to ~10–15 ms with PIL LANCZOS.
    # This yields frame generation rates of 250–500 FPS — limited only
    # by MoviePy's sequential make_frame contract.
    #
    # For a typical 12-segment project (5 s per segment, 30 FPS):
    #   total_frames  = 12 × 5 × 30 = 1800
    #   frame_gen     ≈ 1800 × 3 ms ≈ 5.4 seconds
    #
    # All per-segment computations (image loading, subject measurement,
    # motion selection, endpoint coordinates) are executed once and
    # captured by the make_frame closure.  Only cheap interpolation and
    # clamping happen per frame.
    total_frames = int(duration * fps)
    logger.debug(
        "  Expected frame count for this clip: %d "
        "(%.2f s × %d fps)",
        total_frames, duration, fps,
    )

    clip = VideoClip(make_frame, duration=duration)
    clip = clip.with_fps(fps)

    return clip
