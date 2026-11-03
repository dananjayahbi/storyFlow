"""Range-capable media serving for the in-app audio/video players.

Django's development ``static()`` helper (``django.views.static.serve``) does
not implement HTTP Range requests.  Chromium-based browsers need Range support
to seek inside an audio/video element: without it the timeline thumb jumps
back and ``audio.currentTime`` appears to be ignored.

This view implements the single-range subset of RFC 7233 (``bytes=start-end``,
``bytes=start-`` and ``bytes=-suffix``) which is all media elements need.
"""

from __future__ import annotations

import mimetypes
import os
import posixpath
import re

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse, StreamingHttpResponse
from django.views.decorators.http import require_http_methods

_RANGE_RE = re.compile(r'^bytes=(\d*)-(\d*)$')


def _safe_path(relative_path: str) -> str:
    """Resolve *relative_path* under MEDIA_ROOT, rejecting traversal."""
    relative_path = posixpath.normpath(str(relative_path or '')).lstrip('/')
    if relative_path in ('', '.'):
        raise Http404('Media path is empty.')
    if relative_path.startswith('../') or os.path.isabs(relative_path):
        raise Http404('Invalid media path.')

    root = os.path.abspath(str(settings.MEDIA_ROOT))
    full_path = os.path.abspath(os.path.join(root, relative_path))
    if full_path != root and not full_path.startswith(root + os.sep):
        raise Http404('Invalid media path.')
    if not os.path.isfile(full_path):
        raise Http404('Media file not found.')
    return full_path


def parse_range_header(range_header: str, file_size: int) -> tuple[int, int] | None:
    """Return inclusive ``(start, end)`` bytes, or ``None`` when malformed.

    ``file_size`` is the number of bytes in the file.  A syntactically valid
    but unsatisfiable range returns ``(file_size, file_size - 1)`` so the
    caller can answer with 416 and the correct ``Content-Range``.
    """
    match = _RANGE_RE.match((range_header or '').strip())
    if not match:
        return None

    raw_start, raw_end = match.groups()
    if not raw_start and not raw_end:
        return None

    if not raw_start:
        # Suffix range: bytes=-500 → the final 500 bytes.
        suffix = int(raw_end)
        if suffix <= 0:
            return (file_size, file_size - 1)
        start = max(0, file_size - suffix)
        end = file_size - 1
    else:
        start = int(raw_start)
        end = int(raw_end) if raw_end else file_size - 1

    if start >= file_size or start < 0:
        return (file_size, file_size - 1)
    end = min(end, file_size - 1)
    if end < start:
        return (file_size, file_size - 1)
    return start, end


def _iter_file(file_path: str, start: int, length: int, chunk_size: int = 64 * 1024):
    with open(file_path, 'rb') as handle:
        handle.seek(start)
        remaining = length
        while remaining > 0:
            data = handle.read(min(chunk_size, remaining))
            if not data:
                break
            remaining -= len(data)
            yield data


@require_http_methods(['GET', 'HEAD'])
def serve_media(request, path):
    """Serve ``MEDIA_ROOT/<path>`` with byte-range support."""
    file_path = _safe_path(path)
    file_size = os.path.getsize(file_path)
    content_type = (
        mimetypes.guess_type(file_path)[0] or 'application/octet-stream'
    )

    range_header = request.headers.get('Range')
    head_only = request.method == 'HEAD'

    if range_header:
        parsed = parse_range_header(range_header, file_size)
        if parsed is None:
            response = HttpResponse(status=416)
            response['Content-Range'] = f'bytes */{file_size}'
            response['Accept-Ranges'] = 'bytes'
            return response

        start, end = parsed
        if start >= file_size:
            response = HttpResponse(status=416)
            response['Content-Range'] = f'bytes */{file_size}'
            response['Accept-Ranges'] = 'bytes'
            return response

        length = end - start + 1
        if head_only:
            response = HttpResponse(status=206, content_type=content_type)
        else:
            response = StreamingHttpResponse(
                _iter_file(file_path, start, length),
                status=206,
                content_type=content_type,
            )
        response['Content-Length'] = str(length)
        response['Content-Range'] = f'bytes {start}-{end}/{file_size}'
        response['Accept-Ranges'] = 'bytes'
        response['Cache-Control'] = 'public, max-age=3600'
        return response

    if head_only:
        response = HttpResponse(status=200, content_type=content_type)
    else:
        response = FileResponse(open(file_path, 'rb'), content_type=content_type)
    response['Content-Length'] = str(file_size)
    response['Accept-Ranges'] = 'bytes'
    response['Cache-Control'] = 'public, max-age=3600'
    return response
