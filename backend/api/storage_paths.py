"""Pure storage-path helpers for the StoryFlow asset store.

All user-generated assets live under ``backend/Storage`` (``MEDIA_ROOT``):

    Storage/
      Facebook/<account-id>/<project-id>/...
      YouTube/<account-id>/<project-id>/...
      logos/...
      outros/...
      fonts/...

Each workspace (Facebook Reels / YouTube Videos) can contain many accounts
(Facebook pages or YouTube channels).  Every project belongs to one account,
and the account UUID is part of the path so two accounts can never share or
overwrite assets.  Project folders still mirror the workspace section so an
asset can never be confused between the two sides.
"""

from pathlib import PurePosixPath
from pathlib import Path

from django.conf import settings

SECTION_FOLDERS = {
    'facebook': 'Facebook',
    'youtube': 'YouTube',
}

# Folder used only when a project has no account (should not happen for rows
# created through the application; kept as a safe fallback for raw SQL/tests).
FALLBACK_ACCOUNT_FOLDER = '_unassigned'


def section_folder(section: str | None) -> str:
    """Return the on-disk folder name for a workspace section."""
    return SECTION_FOLDERS.get((section or '').lower(), 'Facebook')


def account_folder(account_id) -> str:
    """Return the on-disk folder name for an account (its immutable UUID)."""
    return str(account_id) if account_id else FALLBACK_ACCOUNT_FOLDER


def storage_root() -> Path:
    """Absolute path to the asset storage root (``Storage/``)."""
    return Path(settings.MEDIA_ROOT)


def _resolve_account_id(project_id):
    """Look up a project's account without importing models at module load."""
    try:
        from api.models import Project

        return Project.objects.values_list('account_id', flat=True).get(
            pk=project_id
        )
    except Exception:
        return None


def project_dir(section: str | None, project_id, account_id=None) -> Path:
    """Absolute project asset directory.

    ``Storage/<Section>/<account-id>/<project-id>``.  When *account_id* is
    omitted it is resolved from the database so existing call sites keep
    working with the new account-scoped layout.
    """
    if account_id is None:
        account_id = _resolve_account_id(project_id)
    return (
        storage_root()
        / section_folder(section)
        / account_folder(account_id)
        / str(project_id)
    )


def ensure_project_dir(section: str | None, project_id, account_id=None) -> Path:
    """Create (if needed) and return a project's asset directory."""
    directory = project_dir(section, project_id, account_id=account_id)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def project_relpath(
    section: str | None,
    project_id,
    *parts: str,
    account_id=None,
) -> str:
    """Return a POSIX path relative to ``MEDIA_ROOT`` for a project asset."""
    if account_id is None:
        account_id = _resolve_account_id(project_id)
    return PurePosixPath(
        section_folder(section),
        account_folder(account_id),
        str(project_id),
        *parts,
    ).as_posix()


def upgrade_legacy_project_path(
    name: str | None,
    section: str | None,
    project_id=None,
    account_id=None,
) -> str:
    """Translate an old project path to the account-scoped layout.

    Handles both historical layouts::

        projects/<id>/images/x.png        -> <Section>/<account>/<id>/images/x.png
        <Section>/<id>/images/x.png       -> <Section>/<account>/<id>/images/x.png

    Paths that already contain the account folder are returned unchanged.
    Other asset paths (logos/..., outros/..., fonts/...) are also unchanged.
    """
    if not name:
        return name or ''
    normalized = str(name).replace('\\', '/')
    section_name = section_folder(section)
    folder = account_folder(account_id)

    if normalized.startswith('projects/'):
        remainder = normalized[len('projects/'):]
        return f"{section_name}/{folder}/{remainder}"

    if project_id is not None:
        old_prefix = f"{section_name}/{project_id}/"
        if normalized.startswith(old_prefix):
            return f"{section_name}/{folder}/" + normalized[len(section_name) + 1:]

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
