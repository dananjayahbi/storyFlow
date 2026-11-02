"""Pure storage-path helpers for the StoryFlow asset store.

All user-generated assets live under ``backend/Storage`` (``MEDIA_ROOT``):

    Storage/
      Facebook/<project-id>/...
      YouTube/<project-id>/...
      logos/...
      outros/...
      fonts/...

Project folders intentionally mirror the workspace section so an asset can
never be confused between Facebook Reels and YouTube Videos.
"""

from pathlib import PurePosixPath
from pathlib import Path

from django.conf import settings

SECTION_FOLDERS = {
    'facebook': 'Facebook',
    'youtube': 'YouTube',
}


def section_folder(section: str | None) -> str:
    """Return the on-disk folder name for a workspace section."""
    return SECTION_FOLDERS.get((section or '').lower(), 'Facebook')


def storage_root() -> Path:
    """Absolute path to the asset storage root (``Storage/``)."""
    return Path(settings.MEDIA_ROOT)


def project_dir(section: str | None, project_id) -> Path:
    """Absolute project asset directory: ``Storage/<Section>/<project-id>``."""
    return storage_root() / section_folder(section) / str(project_id)


def ensure_project_dir(section: str | None, project_id) -> Path:
    """Create (if needed) and return a project's asset directory."""
    directory = project_dir(section, project_id)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def project_relpath(section: str | None, project_id, *parts: str) -> str:
    """Return a POSIX path relative to ``MEDIA_ROOT`` for a project asset."""
    return PurePosixPath(section_folder(section), str(project_id), *parts).as_posix()


def upgrade_legacy_project_path(name: str | None, section: str | None) -> str:
    """Translate an old ``projects/<id>/...`` path to the section layout.

    ``projects/<id>/images/x.png`` -> ``YouTube/<id>/images/x.png``
    Other paths are returned unchanged (normalized to forward slashes).
    """
    if not name:
        return name or ''
    normalized = str(name).replace('\\', '/')
    if normalized.startswith('projects/'):
        remainder = normalized[len('projects/'):]
        return f"{section_folder(section)}/{remainder}"
    return normalized


def media_url(relative_path: str | None) -> str | None:
    """Convert a stored path (absolute or relative) into a ``/media/...`` URL."""
    if not relative_path:
        return None

    raw = str(relative_path).replace('\\', '/')
    root = str(storage_root()).replace('\\', '/')

    if raw.startswith(root.rstrip('/') + '/'):
        raw = raw[len(root.rstrip('/')) + 1:]
    elif '/Storage/' in raw:
        raw = raw.split('/Storage/', 1)[1]

    return f"/media/{raw.lstrip('/')}"
