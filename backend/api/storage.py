"""Project asset store + artifact synchronisation.

Every project gets a self-contained folder under ``Storage/<Section>/<id>``:

    project.json   – full project metadata + segments snapshot (the draft)
    story.json     – the imported story source, when the project was imported
    script.txt     – plain narration script assembled from segment texts
    images/        – segment images
    audio/         – generated TTS audio
    output/        – rendered videos
    upscaled_images/ – GAN-upscaled images (when enabled)

Django signals keep ``project.json`` and ``script.txt`` in sync whenever a
project or segment changes.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import shutil
import uuid as _uuid
from pathlib import Path

from django.db import models
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from api.models import Project, Segment
from api.storage_paths import (
    ensure_project_dir,
    project_dir,
    project_relpath,
    storage_root,
    upgrade_legacy_project_path,
)

logger = logging.getLogger(__name__)

PROJECT_JSON = 'project.json'
STORY_JSON = 'story.json'
SCRIPT_TXT = 'script.txt'
ASSETS_DIR = 'assets'


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------

def _json_value(value):
    """Make a model field value JSON-serialisable."""
    if isinstance(value, models.Model):
        return str(value.pk)
    if hasattr(value, 'name'):  # FieldFile / ImageFieldFile
        return value.name or None
    if isinstance(value, (_uuid.UUID, _dt.datetime, _dt.date, _dt.time)):
        return value.isoformat()
    return value


def _model_dict(obj) -> dict:
    return {
        field.name: _json_value(getattr(obj, field.name))
        for field in obj._meta.fields
        if field.name != 'id'
    }


def project_snapshot(project: Project, assets: dict | None = None) -> dict:
    """Build the canonical JSON snapshot written to ``project.json``."""
    segments = project.segments.order_by('sequence_index')
    return {
        'id': str(project.id),
        'title': project.title,
        'section': project.section,
        'status': project.status,
        'created_at': _json_value(project.created_at),
        'updated_at': _json_value(project.updated_at),
        'storage_folder': project_relpath(project.section, project.id),
        'assets': assets or {},
        'project': _model_dict(project),
        'segments': [_model_dict(segment) for segment in segments],
    }


def build_script(project: Project) -> str:
    """Assemble the narration script from segment text."""
    lines = [project.title.strip(), '=' * max(len(project.title.strip()), 1)]
    lines.append('')
    for index, segment in enumerate(
        project.segments.order_by('sequence_index'), start=1
    ):
        text = (segment.text_content or '').strip()
        lines.append(f'[{index}]')
        lines.append(text or '(empty segment)')
        lines.append('')
    return '\n'.join(lines).rstrip() + '\n'


# ---------------------------------------------------------------------------
# Artifact writers
# ---------------------------------------------------------------------------

def _copy_related_assets(project: Project, directory: Path) -> dict:
    """Copy referenced logo/outro/font files into the project folder.

    This keeps each project self-contained even though logo/outro assets are
    also managed globally on the Settings page.
    """
    sources = {
        'logo': project.active_logo.file if project.active_logo_id else None,
        'outro': project.active_outro.file if project.active_outro_id else None,
        'font': project.custom_font_file if project.custom_font_file else None,
    }

    copied = {}
    for key, field in sources.items():
        if not field or not getattr(field, 'name', ''):
            continue
        try:
            source = Path(field.path)
        except (NotImplementedError, ValueError):
            continue
        if not source.is_file():
            continue

        target_dir = directory / ASSETS_DIR
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / source.name
        if (
            not target.exists()
            or target.stat().st_size != source.stat().st_size
            or target.stat().st_mtime < source.stat().st_mtime
        ):
            shutil.copy2(source, target)

        copied[key] = project_relpath(
            project.section, project.id, ASSETS_DIR, source.name
        )

    return copied


def write_project_artifacts(project: Project) -> None:
    """Write/refresh ``project.json`` and ``script.txt`` for a project."""
    directory = ensure_project_dir(project.section, project.id)
    assets = _copy_related_assets(project, directory)
    snapshot = project_snapshot(project, assets=assets)

    (directory / PROJECT_JSON).write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False),
        encoding='utf-8',
    )
    (directory / SCRIPT_TXT).write_text(
        build_script(project),
        encoding='utf-8',
    )


def save_story_json(project: Project, story: dict) -> None:
    """Persist the imported source story (draft input) next to the project."""
    directory = ensure_project_dir(project.section, project.id)
    payload = {
        'title': project.title,
        'section': project.section,
        'saved_at': _dt.datetime.now(_dt.timezone.utc).isoformat(),
        **story,
    }
    (directory / STORY_JSON).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding='utf-8',
    )


# ---------------------------------------------------------------------------
# Signals — keep the asset store in sync with the database
# ---------------------------------------------------------------------------

@receiver(post_save, sender=Project)
def _project_saved(sender, instance, raw=False, **kwargs):
    if raw:
        return
    try:
        write_project_artifacts(instance)
    except Exception:  # never break a DB save because of storage I/O
        logger.warning('Could not write project artifacts for %s', instance.pk, exc_info=True)


@receiver(post_save, sender=Segment)
def _segment_saved(sender, instance, raw=False, **kwargs):
    if raw:
        return
    try:
        write_project_artifacts(instance.project)
    except Exception:
        logger.warning('Could not refresh project artifacts for %s', instance.project_id, exc_info=True)


@receiver(post_delete, sender=Segment)
def _segment_deleted(sender, instance, **kwargs):
    try:
        project = Project.objects.get(pk=instance.project_id)
        write_project_artifacts(project)
    except Project.DoesNotExist:
        pass
    except Exception:
        logger.warning('Could not refresh project artifacts after segment delete', exc_info=True)


@receiver(post_delete, sender=Project)
def _project_deleted(sender, instance, **kwargs):
    try:
        shutil.rmtree(project_dir(instance.section, instance.id), ignore_errors=True)
    except Exception:
        logger.warning('Could not remove project storage for %s', instance.pk, exc_info=True)


# ---------------------------------------------------------------------------
# Legacy media/ -> Storage/ migration
# ---------------------------------------------------------------------------

def _move_tree(source: Path, destination: Path) -> int:
    """Merge *source* into *destination*, moving files. Returns file count."""
    moved = 0
    if not source.exists():
        return moved
    destination.mkdir(parents=True, exist_ok=True)
    for item in source.rglob('*'):
        if not item.is_file():
            continue
        relative = item.relative_to(source)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            item.unlink()
        else:
            shutil.move(str(item), str(target))
        moved += 1
    return moved


def _legacy_relative(name: str | None, legacy_root: Path) -> str:
    """Normalize a stored path or absolute path to a MEDIA_ROOT-relative one."""
    if not name:
        return ''
    raw = str(name).replace('\\', '/')
    legacy = str(legacy_root).replace('\\', '/')
    if raw.startswith(legacy.rstrip('/') + '/'):
        return raw[len(legacy.rstrip('/')) + 1:]
    return raw.lstrip('/')


def migrate_legacy_storage(legacy_root: Path | None = None, dry_run: bool = False) -> dict:
    """Move files from the old ``backend/media`` tree into ``Storage``.

    Also rewrites segment image/audio names and project output paths to the
    new section-scoped layout, then regenerates project artifacts. Safe to
    run repeatedly.
    """
    from django.conf import settings

    legacy_root = Path(legacy_root or (Path(settings.BASE_DIR) / 'media'))
    root = storage_root()

    report = {
        'legacy_root': str(legacy_root),
        'storage_root': str(root),
        'projects': 0,
        'files_moved': 0,
        'segments_updated': 0,
        'projects_updated': 0,
        'dry_run': dry_run,
    }

    if not legacy_root.exists():
        return report

    for project in Project.objects.all():
        legacy_project = legacy_root / 'projects' / str(project.id)
        destination = project_dir(project.section, project.id)
        if legacy_project.exists():
            report['projects'] += 1
            if not dry_run:
                report['files_moved'] += _move_tree(legacy_project, destination)

        updates = []
        for segment in Segment.objects.filter(project=project):
            changed = False
            if segment.image_file:
                relative = _legacy_relative(segment.image_file.name, legacy_root)
                new_name = upgrade_legacy_project_path(relative, project.section)
                if new_name != segment.image_file.name:
                    segment.image_file.name = new_name
                    changed = True
            if segment.audio_file:
                relative = _legacy_relative(segment.audio_file.name, legacy_root)
                new_name = upgrade_legacy_project_path(relative, project.section)
                if new_name != segment.audio_file.name:
                    segment.audio_file.name = new_name
                    changed = True
            if changed:
                updates.append(segment)

        if updates:
            report['segments_updated'] += len(updates)
            if not dry_run:
                Segment.objects.bulk_update(
                    updates, ['image_file', 'audio_file']
                )

        if project.output_path:
            relative = _legacy_relative(project.output_path, legacy_root)
            new_relative = upgrade_legacy_project_path(relative, project.section)
            if new_relative != project.output_path:
                report['projects_updated'] += 1
                if not dry_run:
                    Project.objects.filter(pk=project.pk).update(
                        output_path=new_relative
                    )
                    project.output_path = new_relative

        if not dry_run:
            write_project_artifacts(project)

    # Global assets keep their relative names (logos/..., outros/..., fonts/...)
    for folder in ('logos', 'outros', 'fonts'):
        source = legacy_root / folder
        if source.exists():
            if not dry_run:
                report['files_moved'] += _move_tree(source, root / folder)

    return report
