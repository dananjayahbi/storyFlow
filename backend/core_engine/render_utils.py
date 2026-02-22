"""
StoryFlow Render Utilities Module.

Provides utility functions for the video rendering pipeline including:
- FFmpeg availability checking
- Image resizing to target resolutions (cover mode)
- Output path management for rendered videos
- Temporary file cleanup during rendering

This module is the central hub for all rendering helper functions
used throughout Phase 04 — The Vision.
"""

import logging
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FFmpeg availability cache
# ---------------------------------------------------------------------------

_ffmpeg_available: Optional[bool] = None


def get_ffmpeg_error_message() -> str:
    """
    Return a human-readable error message with platform-specific
    FFmpeg installation instructions.

    Detects the current operating system and provides the appropriate
    package-manager command for installing FFmpeg.

    Returns:
        str: Multi-line installation guidance string.
    """
    system = platform.system().lower()

    if system == "windows":
        install_hint = (
            "Install FFmpeg on Windows:\n"
            "  • choco install ffmpeg   (Chocolatey)\n"
            "  • winget install ffmpeg  (WinGet)\n"
            "  • Or download from https://ffmpeg.org/download.html "
            "and add to PATH."
        )
    elif system == "darwin":
        install_hint = (
            "Install FFmpeg on macOS:\n"
            "  • brew install ffmpeg  (Homebrew)"
        )
    else:
        # Linux and other Unix-like systems
        install_hint = (
            "Install FFmpeg on Linux:\n"
            "  • sudo apt install ffmpeg   (Debian/Ubuntu)\n"
            "  • sudo dnf install ffmpeg   (Fedora)\n"
            "  • sudo pacman -S ffmpeg     (Arch)"
        )

    return (
        "FFmpeg is not installed or not found on the system PATH.\n"
        f"{install_hint}\n"
        "Ensure the 'ffmpeg' command is accessible from your terminal."
    )


def reset_ffmpeg_cache() -> None:
    """
    Reset the cached FFmpeg availability status.

    Useful for testing or after installing FFmpeg at runtime.
    """
    global _ffmpeg_available
    _ffmpeg_available = None
    logger.debug("FFmpeg availability cache has been reset.")


def check_ffmpeg() -> bool:
    """
    Verify that FFmpeg is installed and operational.

    Checks for the ``ffmpeg`` binary on the system PATH by attempting
    to execute ``ffmpeg -version``.  The result is cached so that
    subsequent calls do not spawn a new subprocess.

    Returns:
        bool: ``True`` if FFmpeg is available, ``False`` otherwise.
    """
    global _ffmpeg_available

    if _ffmpeg_available is not None:
        logger.debug("Returning cached FFmpeg availability: %s", _ffmpeg_available)
        return _ffmpeg_available

    # First try shutil.which for a fast PATH lookup
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path is None:
        logger.warning("FFmpeg not found on system PATH.")
        _ffmpeg_available = False
        return _ffmpeg_available

    # Verify the binary actually runs
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        _ffmpeg_available = result.returncode == 0
        if _ffmpeg_available:
            # Log the first line of version output for diagnostics
            version_line = result.stdout.split("\n")[0]
            logger.info("FFmpeg detected: %s", version_line.strip())
        else:
            logger.warning("FFmpeg found but returned non-zero exit code.")
    except (FileNotFoundError, OSError):
        logger.warning("FFmpeg binary not found.\n%s", get_ffmpeg_error_message())
        _ffmpeg_available = False
    except subprocess.TimeoutExpired:
        logger.warning("FFmpeg version check timed out (10s limit).")
        _ffmpeg_available = False
    except Exception as exc:  # noqa: BLE001
        logger.warning("Unexpected error checking FFmpeg: %s", exc)
        _ffmpeg_available = False

    return _ffmpeg_available


# ---------------------------------------------------------------------------
# Image utilities
# ---------------------------------------------------------------------------


def resize_image_to_resolution(
    image_path: str, width: int, height: int
) -> np.ndarray:
    """
    Load an image and resize it using *cover* mode to fill the target
    resolution exactly.

    Cover mode scales the image so the shorter dimension matches the
    target, then centre-crops the longer dimension.  The returned
    array always has shape ``(height, width, 3)`` in RGB.

    Args:
        image_path: Filesystem path to the source image.
        width: Target width in pixels.
        height: Target height in pixels.

    Returns:
        numpy.ndarray: Resized image array with shape
        ``(height, width, 3)`` and dtype ``uint8``.

    Raises:
        FileNotFoundError: If *image_path* does not exist.
        ValueError: If *width* or *height* is not a positive integer.
        PIL.UnidentifiedImageError: If the file cannot be read as an image.
    """
    if width <= 0 or height <= 0:
        raise ValueError(
            f"Width and height must be positive integers, got {width}x{height}."
        )

    img_path = Path(image_path)
    if not img_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    logger.debug("Loading image for resize: %s → %dx%d", image_path, width, height)

    try:
        img = Image.open(image_path).convert("RGB")
    except Exception as exc:
        raise ValueError(
            f"Cannot read image file '{image_path}': {exc}"
        ) from exc

    src_w, src_h = img.size

    # Edge case: image already matches target dimensions exactly
    if src_w == width and src_h == height:
        logger.debug("Image already matches target dimensions, skipping resize.")
        result = np.array(img, dtype=np.uint8)
        assert result.shape == (height, width, 3) and result.dtype == np.uint8
        return result

    # Calculate aspect ratios for cover mode decision
    src_ratio = src_w / src_h
    target_ratio = width / height

    if src_ratio > target_ratio:
        # Image is relatively wider → scale height to match, crop width
        new_h = height
        new_w = int(src_w * (height / src_h))
    else:
        # Image is relatively taller (or same) → scale width to match, crop height
        new_w = width
        new_h = int(src_h * (width / src_w))

    img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    # Centre-crop to exact target dimensions
    left = (new_w - width) // 2
    top = (new_h - height) // 2
    img = img.crop((left, top, left + width, top + height))

    result = np.array(img, dtype=np.uint8)

    # Guard against subtle resize bugs
    assert result.shape == (height, width, 3), (
        f"Resize produced unexpected shape {result.shape}, "
        f"expected ({height}, {width}, 3)"
    )
    assert result.dtype == np.uint8, (
        f"Resize produced unexpected dtype {result.dtype}, expected uint8"
    )

    logger.debug("Image resized and cropped to %dx%d", width, height)
    return result


# ---------------------------------------------------------------------------
# Output path management
# ---------------------------------------------------------------------------


def get_output_path(project_id: str) -> str:
    """
    Return the output file path for a rendered video and ensure the
    output directory exists.

    The path is constructed relative to ``settings.MEDIA_ROOT``::

        <MEDIA_ROOT>/projects/<project_id>/output/final.mp4

    Args:
        project_id: The unique identifier of the project.

    Returns:
        str: Absolute path to the output video file.

    Raises:
        ValueError: If ``MEDIA_ROOT`` is not configured.
    """
    from django.conf import settings  # noqa: E402 — deferred import

    media_root = getattr(settings, "MEDIA_ROOT", None)
    if not media_root:
        raise ValueError(
            "MEDIA_ROOT is not configured in Django settings. "
            "This setting is required for video output path resolution."
        )

    output_dir = Path(media_root) / "projects" / str(project_id) / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / "final.mp4"
    logger.debug("Output path for project %s: %s", project_id, output_path)
    return str(output_path)


# ---------------------------------------------------------------------------
# Temporary file cleanup
# ---------------------------------------------------------------------------


def cleanup_temp_files(temp_dir: str) -> None:
    """
    Remove temporary files created during the rendering process.

    Removes all files in the specified temporary directory, logging
    each file removed.  If the directory is empty after cleanup,
    removes the directory itself.  Handles non-existent directories
    gracefully.

    Args:
        temp_dir: Filesystem path to the temporary directory to remove.
    """
    temp_path = Path(temp_dir)

    if not temp_path.exists():
        logger.debug("Temp directory does not exist, nothing to clean: %s", temp_dir)
        return

    try:
        # Remove individual files and log each one
        removed_count = 0
        for item in temp_path.rglob("*"):
            if item.is_file():
                item.unlink()
                logger.debug("Removed temp file: %s", item)
                removed_count += 1

        # Remove empty directories (bottom-up)
        for item in sorted(temp_path.rglob("*"), reverse=True):
            if item.is_dir():
                try:
                    item.rmdir()
                except OSError:
                    pass  # Directory not empty or other issue

        # Remove the root temp directory if now empty
        try:
            temp_path.rmdir()
        except OSError:
            pass  # Directory not empty

        logger.info(
            "Cleaned up temp directory: %s (%d files removed)",
            temp_dir, removed_count,
        )
    except OSError as exc:
        logger.warning("Failed to clean up temp directory %s: %s", temp_dir, exc)


# ---------------------------------------------------------------------------
# ImageMagick availability check
# ---------------------------------------------------------------------------

_imagemagick_available: Optional[bool] = None


def check_imagemagick() -> bool:
    """
    Check whether ImageMagick is available on the system.

    Looks for the ``magick`` command (ImageMagick 7) or ``convert``
    (ImageMagick 6 and earlier).  The result is cached so subsequent
    calls are essentially free.

    Returns:
        bool: ``True`` if ImageMagick is detected, ``False`` otherwise.
    """
    global _imagemagick_available

    if _imagemagick_available is not None:
        return _imagemagick_available

    # Try ImageMagick 7 first, then legacy v6 ``convert``
    for cmd in ("magick", "convert"):
        if shutil.which(cmd) is not None:
            logger.info("ImageMagick detected via '%s' command.", cmd)
            _imagemagick_available = True
            return True

    logger.warning(
        "ImageMagick not found on the system. "
        "Subtitle overlay will be skipped."
    )
    _imagemagick_available = False
    return False


def reset_imagemagick_cache() -> None:
    """Reset the cached ImageMagick availability flag (useful for tests)."""
    global _imagemagick_available
    _imagemagick_available = None


# ---------------------------------------------------------------------------
# Font path resolution
# ---------------------------------------------------------------------------


def get_font_path(font_name: Optional[str] = None) -> Optional[str]:
    """
    Resolve a font name to a filesystem path usable by MoviePy TextClip.

    Strategy:
    1. If *font_name* is an existing file path, return it directly.
    2. On Windows look under ``C:/Windows/Fonts`` for common extensions.
    3. On Linux/macOS run ``fc-match`` to locate the font.
    4. If nothing is found, return ``None`` and let MoviePy use its
       built-in default.

    Args:
        font_name: A font family name (e.g. ``"Arial"``) or an
            absolute/relative path to a ``.ttf`` / ``.otf`` file.
            Pass ``None`` or ``""`` to get the system default.

    Returns:
        str | None: Absolute path to the resolved font file, or
        ``None`` if the font could not be located.
    """
    if not font_name:
        return None

    # Already an existing file path?
    if os.path.isfile(font_name):
        logger.debug("Font path provided directly: %s", font_name)
        return font_name

    # Windows: search the system Fonts directory
    if platform.system() == "Windows":
        fonts_dir = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
        for ext in (".ttf", ".otf", ".ttc"):
            candidate = fonts_dir / f"{font_name}{ext}"
            if candidate.exists():
                logger.debug("Found font at %s", candidate)
                return str(candidate)
            # Also try lower-case version
            candidate_lower = fonts_dir / f"{font_name.lower()}{ext}"
            if candidate_lower.exists():
                logger.debug("Found font at %s", candidate_lower)
                return str(candidate_lower)

    # Linux / macOS: use fc-match
    if shutil.which("fc-match"):
        try:
            result = subprocess.run(
                ["fc-match", "--format=%{file}", font_name],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                resolved = result.stdout.strip()
                if os.path.isfile(resolved):
                    logger.debug(
                        "fc-match resolved '%s' → %s", font_name, resolved
                    )
                    return resolved
        except (subprocess.TimeoutExpired, OSError) as exc:
            logger.debug("fc-match failed for '%s': %s", font_name, exc)

    logger.warning(
        "Could not resolve font '%s' to a file path. "
        "MoviePy will fall back to its default font.",
        font_name,
    )
    return None
