"""
StoryFlow Ken Burns Effect Module.

Provides zoom-and-pan animation for still images used in narrative video
segments.  The module converts static cover images into MoviePy VideoClip
objects with per-frame camera motion computed through linear interpolation
of crop-box positions.

The primary public interface is :func:`apply_ken_burns`, which the video
renderer calls once per segment.  All other functions in this module are
internal helpers implementing specific parts of the algorithm.

Design principles
-----------------
* **Deterministic** — Direction selection is based on ``segment_index % 7``,
  so re-rendering the same project always produces identical output.
* **No Django dependency** — The module performs pure computation on images
  and NumPy arrays.  The only I/O is reading the source image file from
  disk (in ``load_and_prepare_image``).  All configuration values
  (zoom_intensity, fps, resolution, …) are passed in by the caller.
* **MoviePy version-safe** — Imports are wrapped in ``try``/``except`` to
  support both MoviePy 1.x (``moviepy.editor``) and 2.x (``moviepy``).
"""

import logging
from typing import Tuple

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
# segments.  The mapping from position names to pixel coordinates is
# handled by ``position_to_coords`` (Task 04.02.05).
DIRECTIONS: Tuple[
    Tuple[str, str], ...
] = (
    ("center", "center"),              # zoom-only, no pan
    ("top_left", "bottom_right"),      # diagonal pan
    ("bottom_right", "top_left"),      # reverse diagonal
    ("top_right", "bottom_left"),      # opposite diagonal
    ("bottom_left", "top_right"),      # reverse opposite diagonal
    ("center", "top_left"),            # drift upward-left
    ("center", "bottom_right"),        # drift downward-right
)


# ===================================================================
# Helper function stubs (Tasks 04.02.02 — 04.02.07)
# ===================================================================
# These stubs will be replaced with full implementations in the
# subsequent tasks of SubPhase 04.02.

def load_and_prepare_image(
    image_path: str,
    resolution: Tuple[int, int],
    zoom_intensity: float,
) -> np.ndarray:
    """Load a source image and prepare it for Ken Burns animation.

    The source image must be at least ``resolution × zoom_intensity``
    pixels in each dimension to provide sufficient "zoom headroom" —
    enough room for the crop box to pan across all five defined
    positions (corners and center) without leaving the image bounds.

    If the source image is smaller than the minimum, it is upscaled
    uniformly using LANCZOS resampling.  If it is significantly larger
    than the minimum (> 1.5× in both dimensions), it is center-cropped
    to limit memory usage during frame generation.

    Args:
        image_path: Absolute path to the source cover image.
        resolution: Target output ``(width, height)``.
        zoom_intensity: Zoom factor (≥ 1.0).

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
        img = Image.open(image_path)
        img = img.convert("RGB")
    except Exception as exc:
        raise ValueError(
            f"Cannot open or read image file: {image_path}"
        ) from exc

    src_w, src_h = img.size  # Pillow returns (width, height)
    logger.debug(
        "load_and_prepare_image: loaded %s (%dx%d)",
        image_path, src_w, src_h,
    )

    # ------------------------------------------------------------------
    # Step 3: Calculate minimum required dimensions
    # ------------------------------------------------------------------
    min_w = int(output_width * zoom_intensity)
    min_h = int(output_height * zoom_intensity)
    logger.debug(
        "  Minimum required: %dx%d (output %dx%d × zoom %.2f)",
        min_w, min_h, output_width, output_height, zoom_intensity,
    )

    # ------------------------------------------------------------------
    # Step 4 & 5: Upscale if necessary
    # ------------------------------------------------------------------
    if src_w < min_w or src_h < min_h:
        scale_x = min_w / src_w
        scale_y = min_h / src_h
        scale = max(scale_x, scale_y)

        new_w = int(src_w * scale)
        new_h = int(src_h * scale)

        logger.info(
            "  Upscaling image from %dx%d to %dx%d "
            "(minimum required: %dx%d, scale factor: %.2f)",
            src_w, src_h, new_w, new_h, min_w, min_h, scale,
        )

        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        src_w, src_h = img.size

    # ------------------------------------------------------------------
    # Step 6: Cover-crop to limit memory usage
    # ------------------------------------------------------------------
    # Only crop if the image is significantly larger than the minimum
    # (more than 1.5× in both axes).  Moderately larger images are
    # kept at full size for slightly better crop quality.
    if src_w > min_w * 1.5 and src_h > min_h * 1.5:
        offset_x = (src_w - min_w) // 2
        offset_y = (src_h - min_h) // 2
        img = img.crop((
            offset_x,
            offset_y,
            offset_x + min_w,
            offset_y + min_h,
        ))
        logger.debug(
            "  Center-cropped from %dx%d to %dx%d (memory optimisation)",
            src_w, src_h, min_w, min_h,
        )

    # ------------------------------------------------------------------
    # Step 7: Edge-case logging
    # ------------------------------------------------------------------
    final_w, final_h = img.size
    if final_w == min_w and final_h == min_h:
        logger.debug(
            "  Image exactly matches minimum size — "
            "zero pan range in both axes (zoom-only)."
        )

    # ------------------------------------------------------------------
    # Step 8: Convert to NumPy array and return
    # ------------------------------------------------------------------
    result = np.array(img)
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
    0     center → center (zoom only)
    1     top_left → bottom_right
    2     bottom_right → top_left
    3     top_right → bottom_left
    4     bottom_left → top_right
    5     center → top_left
    6     center → bottom_right
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


def get_start_end_coords(
    start_name: str,
    end_name: str,
    source_width: int,
    source_height: int,
    crop_width: int,
    crop_height: int,
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

    Returns:
        ``((start_x, start_y), (end_x, end_y))`` — top-left corner of
        the crop box at the beginning and end of the clip.

    Raises:
        ValueError: If either position name is not recognised.
    """
    start = position_to_coords(
        start_name, source_width, source_height, crop_width, crop_height
    )
    end = position_to_coords(
        end_name, source_width, source_height, crop_width, crop_height
    )
    return (start, end)


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
) -> VideoClip:
    """Apply the Ken Burns (zoom-and-pan) effect to a still image.

    Converts a static cover image into a MoviePy :class:`VideoClip` with
    animated camera motion.  The camera position is linearly interpolated
    between a start and end point, and a crop box of the appropriate size
    is extracted from the source image on every frame.

    Algorithm overview
    ------------------
    1. Load and prepare the source image (upscale for zoom headroom).
    2. Calculate crop-box dimensions from output resolution and zoom.
    3. Select a deterministic pan direction based on ``segment_index``.
    4. Map direction names to start/end pixel coordinates.
    5. Build a ``make_frame(t)`` closure that interpolates the crop
       position and extracts the region for each time instant.
    6. Construct and return a :class:`VideoClip`.

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
    source_image = load_and_prepare_image(image_path, resolution, zoom_intensity)
    source_height, source_width = source_image.shape[:2]
    logger.debug(
        "  Source image prepared: %dx%d", source_width, source_height
    )

    # ------------------------------------------------------------------
    # 2. Calculate crop dimensions
    # ------------------------------------------------------------------
    crop_width, crop_height = calculate_crop_dimensions(
        output_width, output_height, zoom_intensity
    )
    logger.debug(
        "  Crop dimensions: %dx%d", crop_width, crop_height
    )

    # ------------------------------------------------------------------
    # 3. Select pan direction
    # ------------------------------------------------------------------
    start_name, end_name = get_pan_direction(segment_index)
    logger.debug(
        "  Pan direction: %s → %s", start_name, end_name
    )

    # ------------------------------------------------------------------
    # 4. Compute start and end pixel coordinates
    # ------------------------------------------------------------------
    (start_x, start_y), (end_x, end_y) = get_start_end_coords(
        start_name,
        end_name,
        source_width,
        source_height,
        crop_width,
        crop_height,
    )
    logger.debug(
        "  Start coords: (%d, %d), End coords: (%d, %d)",
        start_x, start_y, end_x, end_y,
    )

    # ------------------------------------------------------------------
    # 5. Define the make_frame closure (Task 04.02.06)
    # ------------------------------------------------------------------
    # Capture coordinates as tuples for interpolate_position
    start_coords = (start_x, start_y)
    end_coords = (end_x, end_y)

    def make_frame(t: float) -> np.ndarray:
        """Generate a single frame at time *t* by interpolating the crop.

        Called by MoviePy once per frame during rendering.  The closure
        captures the source image, start/end coordinates, crop
        dimensions, output resolution, and duration from the enclosing
        :func:`apply_ken_burns` scope.

        Algorithm per frame:

        1. Call :func:`interpolate_position` to get the float crop-box
           position at time *t* (with clamped progress).
        2. Round to integer pixel coordinates.
        3. Clamp to valid image bounds.
        4. Extract the crop via NumPy slicing ``[y:y+h, x:x+w]``
           (O(1) view, no data copy).
        5. Resize the crop to the output resolution via Pillow LANCZOS.
        6. Return a contiguous ``uint8`` NumPy array.

        Performance notes (Task 04.02.10):

        * **No multithreading** — MoviePy calls ``make_frame``
          sequentially; parallel frame generation is not supported.
        * **No frame caching** — At 1080p/30fps for a 5-second clip
          (150 frames), caching all frames would require ~935 MB of
          RAM (150 × 1920 × 1080 × 3 bytes).  Not feasible for a
          local desktop application.
        * **Per-frame object creation** is limited to the unavoidable
          minimum given the Pillow+NumPy constraint:
          1. ``Image.fromarray(crop)`` — convert NumPy slice to PIL
          2. ``pil_crop.resize(…)`` — the core resize operation
          3. ``np.array(pil_crop)`` — convert back to NumPy for MoviePy
          Alternative libraries (OpenCV ``cv2.resize``,
          ``scipy.ndimage.zoom``) could eliminate the NumPy ↔ Pillow
          conversion overhead, but are intentionally excluded from the
          dependency list to keep the application footprint small.
        * **Resampling filter tradeoffs**:
          - ``Image.Resampling.LANCZOS`` — highest quality, ~10 ms/frame
            at 1080p.  Used for all renders (current default).
          - ``Image.Resampling.BILINEAR`` — good quality, ~2× faster.
            Suitable for previews or draft renders.
          - ``Image.Resampling.NEAREST`` — lowest quality (pixelated),
            ~5× faster.  Only for debugging or performance testing.
          A future "render quality" setting could select the filter,
          but this is out of scope for Phase 04.

        Args:
            t: Current time in seconds within the clip.

        Returns:
            NumPy array of shape ``(output_height, output_width, 3)``
            with dtype ``uint8``.
        """
        # Step 1: Interpolate the crop-box position (progress clamped
        # to [0, 1] inside interpolate_position)
        interp_x, interp_y = interpolate_position(
            start_coords, end_coords, t, duration
        )

        # Step 2: Convert float coordinates to integer pixels
        x = int(round(interp_x))
        y = int(round(interp_y))

        # Step 3: Clamp to valid image boundaries
        x = max(0, min(x, source_width - crop_width))
        y = max(0, min(y, source_height - crop_height))

        # Step 4: Extract crop region via NumPy array slicing (rows=y, cols=x).
        # NumPy slicing returns a *view* into the existing array — an O(1)
        # operation regardless of crop size.  Actual data transfer happens
        # during the subsequent Pillow resize step.
        crop = source_image[y : y + crop_height, x : x + crop_width]

        # Step 5: Resize crop to output resolution using LANCZOS
        pil_crop = Image.fromarray(crop)
        pil_crop = pil_crop.resize(
            (output_width, output_height), Image.Resampling.LANCZOS
        )
        frame = np.array(pil_crop)

        # Step 6: Ensure contiguous memory layout for MoviePy
        frame = np.ascontiguousarray(frame)

        return frame

    # ------------------------------------------------------------------
    # 6. Construct and return the VideoClip
    # ------------------------------------------------------------------
    # Performance expectations (Task 04.02.10):
    #
    # The dominant per-frame cost is the Pillow LANCZOS resize.  For a
    # crop of ~1477×831 → 1920×1080, each resize takes ~5–15 ms on a
    # modern CPU (Intel i5/i7, AMD Ryzen 5/7).  This yields a frame
    # generation rate of ~67–200 FPS — well above the 5 FPS minimum.
    #
    # For a typical 12-segment project (5 s per segment, 30 FPS):
    #   total_frames  = 12 × 5 × 30 = 1800
    #   frame_gen     ≈ 1800 × 10 ms ≈ 18 seconds
    #   MP4 encoding  ≈ 2–5 × frame_gen ≈ 36–90 seconds total
    #
    # All per-segment computations (image loading, crop dimensions,
    # direction selection, start/end coordinates) are executed once and
    # captured by the make_frame closure.  No per-frame re-computation
    # of these values occurs.
    #
    # No multithreading is used — MoviePy calls make_frame sequentially.
    # No frame caching is implemented — memory cost would be ~935 MB
    # for a single 5 s clip at 1080p/30fps.
    total_frames = int(duration * fps)
    logger.debug(
        "  Expected frame count for this clip: %d "
        "(%.2f s × %d fps)",
        total_frames, duration, fps,
    )

    clip = VideoClip(make_frame, duration=duration)
    clip = clip.with_fps(fps)

    return clip
