"""Audio helpers for the BGM library.

Uploads can be any ffmpeg-readable audio container; they are always converted
to MP3 before being stored so the in-app player and future render pipeline see a
single format.  Standard library only.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import sys

logger = logging.getLogger(__name__)


class AudioConversionError(Exception):
    """Raised when FFmpeg cannot convert or inspect an audio file."""


def find_ffmpeg() -> str | None:
    """Return the FFmpeg executable path, or ``None`` when unavailable."""
    found = shutil.which('ffmpeg')
    if found:
        return found
    candidates = [
        r'C:\ffmpeg\bin\ffmpeg.exe',
        r'C:\Program Files\ffmpeg\bin\ffmpeg.exe',
        '/usr/local/bin/ffmpeg',
        '/opt/homebrew/bin/ffmpeg',
    ]
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return None


def find_ffprobe() -> str | None:
    found = shutil.which('ffprobe')
    if found:
        return found
    ffmpeg = find_ffmpeg()
    if ffmpeg:
        candidate = os.path.join(
            os.path.dirname(ffmpeg),
            'ffprobe.exe' if sys.platform == 'win32' else 'ffprobe',
        )
        if os.path.isfile(candidate):
            return candidate
    return None


def _run(command: list[str], timeout: int = 600) -> subprocess.CompletedProcess:
    kwargs = {}
    if sys.platform == 'win32':
        kwargs['creationflags'] = getattr(
            subprocess, 'CREATE_NO_WINDOW', 0
        )
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            **kwargs,
        )
    except FileNotFoundError as exc:
        raise AudioConversionError(
            'FFmpeg is not installed or not on PATH.'
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise AudioConversionError(
            'Audio conversion timed out. Try a shorter file.'
        ) from exc


def convert_to_mp3(source_path: str, output_path: str, bitrate: str = '192k') -> None:
    """Convert any supported audio file to MP3 at ``output_path``."""
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise AudioConversionError(
            'FFmpeg is required to convert background music. Install it and '
            'make sure the "ffmpeg" command is on PATH.'
        )

    command = [
        ffmpeg,
        '-nostdin',
        '-y',
        '-i', source_path,
        '-vn',
        '-map_metadata', '-1',
        '-codec:a', 'libmp3lame',
        '-b:a', bitrate,
        output_path,
    ]
    result = _run(command)
    if result.returncode != 0 or not os.path.isfile(output_path):
        detail = (result.stderr or result.stdout or '').strip().splitlines()
        tail = ' '.join(detail[-3:])[:600]
        raise AudioConversionError(
            f'Could not convert this audio file to MP3. {tail}'.strip()
        )
    if os.path.getsize(output_path) == 0:
        raise AudioConversionError('The converted MP3 is empty.')


def probe_duration(path: str) -> float | None:
    """Return the media duration in seconds when FFprobe knows it."""
    ffprobe = find_ffprobe()
    if ffprobe:
        result = _run([
            ffprobe,
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            path,
        ], timeout=60)
        if result.returncode == 0:
            try:
                return round(float((result.stdout or '').strip()), 2)
            except (TypeError, ValueError):
                pass

    # Fallback: parse the "Duration: 00:03:21.45" line from ffmpeg -i.
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        return None
    result = _run([ffmpeg, '-i', path], timeout=60)
    match = re.search(
        r'Duration:\s*(\d+):(\d+):([\d.]+)', result.stderr or ''
    )
    if not match:
        return None
    hours, minutes, seconds = match.groups()
    return round(int(hours) * 3600 + int(minutes) * 60 + float(seconds), 2)
