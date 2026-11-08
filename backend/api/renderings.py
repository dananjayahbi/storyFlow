"""Helpers for the Gallery's rendering assets.

A :class:`~api.models.Rendering` is one concrete rendered MP4 produced from a
project.  Render task callbacks use :func:`register_rendering` to move the
freshly exported ``output/render-<uuid>.mp4`` into a permanent per-rendering
file, while the Gallery API uses :func:`resolve_rendering_video` and
:func:`delete_rendering` to stream and remove those assets.

The functions here deliberately avoid importing ``api.views`` at module import
time: views import this module, so a top-level import back into views would
create a circular dependency.
"""

from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path

from django.conf import settings
from django.db import transaction

from .models import (
    Project,
    Rendering,
    RENDERING_STATUS_RENDERED,
    STATUS_COMPLETED,
    STATUS_DRAFT,
)
from .storage_paths import project_relpath, upgrade_legacy_project_path


def _media_root() -> Path:
    return Path(settings.MEDIA_ROOT)


def _stored_path(path: str | None) -> str:
    """Store absolute paths relative to MEDIA_ROOT when they live inside it."""
    if not path:
        return ''
    try:
        relative = os.path.relpath(path, settings.MEDIA_ROOT)
    except (TypeError, ValueError):
        return path
    if relative.startswith('..'):
        return path
    return relative.replace('\\', '/')


def _absolute_candidate(stored: str | None, project: Project) -> str | None:
    """Turn a stored rendering path into an absolute candidate path."""
    if not stored:
        return None

    raw = str(stored).replace('\\', '/')
    if os.path.isabs(raw):
        return raw

    # Old stores may still contain ``projects/<id>/...`` or
    # ``<Section>/<id>/...`` paths.  Translate them to the account layout.
    upgraded = upgrade_legacy_project_path(
        raw,
        project.section,
        project.id,
        project.account_id,
    )
    return str(_media_root() / upgraded)


def resolve_rendering_video(rendering: Rendering) -> str | None:
    """Return the absolute path of a rendering's playable MP4, if it exists."""
    project = rendering.project
    candidates = []

    if rendering.file_path:
        candidates.append(_absolute_candidate(rendering.file_path, project))
    elif project.output_path:
        # Legacy rows created before the file was copied to renderings/.
        candidates.append(_absolute_candidate(project.output_path, project))

    # Conventional account-scoped location for renderings registered before a
    # file move completed (or for rows created by the data migration).
    candidates.append(
        str(
            _media_root()
            / project_relpath(
                project.section,
                project.id,
                'renderings',
                f'{rendering.id}.mp4',
                account_id=project.account_id,
            )
        )
    )

    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            return candidate
    return None


def register_rendering(project: Project, output_path: str, **metadata) -> Rendering:
    """Persist one completed render and move its file into renderings/.

    ``output_path`` is the absolute export path returned by the render
    pipeline.  It is moved to ``.../renderings/<rendering-id>.mp4`` so a later
    re-render cannot overwrite it.  The project's ``output_path`` continues to
    point at the newest rendering for the project-detail player.
    """
    rendering_id = uuid.uuid4()
    relative_path = project_relpath(
        project.section,
        project.id,
        'renderings',
        f'{rendering_id}.mp4',
        account_id=project.account_id,
    )
    target = _media_root() / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)

    source = Path(output_path) if output_path else None
    if source and source.is_file():
        try:
            if source.resolve() != target.resolve():
                shutil.move(str(source), str(target))
            stored_path = relative_path
        except OSError:
            # If the move fails (for example another process holds the file
            # open on Windows) keep using the exported file instead of losing
            # the rendering row entirely.
            stored_path = str(source)
    else:
        # Test doubles and older pipelines can report a logical path without
        # a physical file.  Keep that path so the project still exposes an
        # output and the gallery row remains addressable.
        stored_path = _stored_path(output_path)

    file_size = metadata.pop('file_size', None)
    if not file_size and target.is_file():
        try:
            file_size = target.stat().st_size
        except OSError:
            file_size = 0

    with transaction.atomic():
        # The newest render is always the project's primary video.  Older
        # versions stay in the gallery so nothing is lost.
        Rendering.objects.filter(project=project).update(is_primary=False)
        rendering = Rendering.objects.create(
            id=rendering_id,
            project=project,
            title=project.title,
            file_path=stored_path,
            status=RENDERING_STATUS_RENDERED,
            resolution_width=project.resolution_width,
            resolution_height=project.resolution_height,
            framerate=project.framerate,
            segment_count=metadata.pop('segment_count', None)
            or project.segments.count(),
            file_size=file_size or 0,
            duration=metadata.pop('duration', None),
            is_primary=True,
            **metadata,
        )

    project.output_path = stored_path
    project.status = STATUS_COMPLETED
    project.save(update_fields=['output_path', 'status'])
    return rendering


def delete_rendering(rendering: Rendering) -> None:
    """Delete one rendering row and its MP4, keeping the project consistent."""
    project = rendering.project
    rendering_path = str(rendering.file_path or '').replace('\\', '/')
    project_path = str(project.output_path or '').replace('\\', '/')
    was_current = (
        rendering_path == project_path
        if rendering_path
        else bool(project_path)
    )
    was_primary = bool(rendering.is_primary)

    video_path = resolve_rendering_video(rendering)
    rendering.delete()

    if video_path:
        # Never delete a file outside the managed media root.
        try:
            root = _media_root().resolve()
            candidate = Path(video_path).resolve()
            if root == candidate or root in candidate.parents:
                candidate.unlink(missing_ok=True)
        except OSError:
            pass

    latest = project.renderings.order_by('-created_at').first()

    # Deleting the hero video promotes the newest remaining version so a
    # project with any renderings always has exactly one primary asset.
    if was_primary and latest:
        Rendering.objects.filter(project=project).update(is_primary=False)
        latest.is_primary = True
        latest.save(update_fields=['is_primary'])

    if not was_current:
        return

    if latest:
        project.output_path = latest.file_path
        project.status = STATUS_COMPLETED
    else:
        project.output_path = ''
        project.status = STATUS_DRAFT
    project.save(update_fields=['output_path', 'status'])
