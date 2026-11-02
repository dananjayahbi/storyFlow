"""Create the first account for each side and move existing projects into it.

This migration makes the account layer backwards compatible:

* a ``Default Account`` is created for Facebook Reels and YouTube Videos;
* every pre-existing project is attached to its side's default account;
* project asset folders are moved from
  ``Storage/<Section>/<project-id>`` to
  ``Storage/<Section>/<account-id>/<project-id>``;
* stored image/audio/output paths are rewritten to the new layout.

It is intentionally defensive: a missing or partially migrated Storage tree
never blocks the database migration.
"""

import shutil
from pathlib import Path

from django.conf import settings
from django.db import migrations

DEFAULT_ACCOUNT_NAME = 'Default Account'
SECTION_FOLDERS = {
    'facebook': 'Facebook',
    'youtube': 'YouTube',
}


def _move_merge(source: Path, destination: Path) -> None:
    """Merge *source* into *destination*, moving files without overwriting."""
    if not source.exists() or source == destination:
        return
    destination.mkdir(parents=True, exist_ok=True)
    for item in source.rglob('*'):
        if not item.is_file():
            continue
        target = destination / item.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            item.unlink()
        else:
            shutil.move(str(item), str(target))
    shutil.rmtree(source, ignore_errors=True)


def _upgrade_path(name, folder, project_id, account_id):
    if not name:
        return name
    normalized = str(name).replace('\\', '/')
    if normalized.startswith('projects/'):
        remainder = normalized[len('projects/'):]
        return f'{folder}/{account_id}/{remainder}'
    old_prefix = f'{folder}/{project_id}/'
    if normalized.startswith(old_prefix):
        return f'{folder}/{account_id}/' + normalized[len(folder) + 1:]
    return normalized


def forwards(apps, schema_editor):
    Account = apps.get_model('api', 'Account')
    Project = apps.get_model('api', 'Project')
    Segment = apps.get_model('api', 'Segment')

    root = Path(settings.MEDIA_ROOT)

    accounts = {}
    for section in ('facebook', 'youtube'):
        account, _ = Account.objects.get_or_create(
            section=section,
            name=DEFAULT_ACCOUNT_NAME,
        )
        accounts[section] = account

    for project in Project.objects.all().iterator():
        section = project.section or 'facebook'
        folder = SECTION_FOLDERS.get(section, 'Facebook')
        account = accounts.get(section)
        if account is None:
            account, _ = Account.objects.get_or_create(
                section=section,
                name=DEFAULT_ACCOUNT_NAME,
            )
            accounts[section] = account

        if not project.account_id:
            Project.objects.filter(pk=project.pk).update(account=account)
            project.account_id = account.pk

        old_dir = root / folder / str(project.pk)
        new_dir = root / folder / str(account.pk) / str(project.pk)
        _move_merge(old_dir, new_dir)

        for segment in Segment.objects.filter(project_id=project.pk).iterator():
            changed = []
            for field_name in ('image_file', 'audio_file'):
                value = getattr(segment, field_name)
                if not value:
                    continue
                upgraded = _upgrade_path(
                    value, folder, project.pk, account.pk
                )
                if upgraded != value:
                    setattr(segment, field_name, upgraded)
                    changed.append(field_name)
            if changed:
                Segment.objects.filter(pk=segment.pk).update(
                    **{field: getattr(segment, field) for field in changed}
                )

        if project.output_path:
            upgraded = _upgrade_path(
                project.output_path, folder, project.pk, account.pk
            )
            if upgraded != project.output_path:
                Project.objects.filter(pk=project.pk).update(
                    output_path=upgraded
                )


def backwards(apps, schema_editor):
    """No-op: moving assets back would risk data loss on rollback."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0012_account_project_account'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
