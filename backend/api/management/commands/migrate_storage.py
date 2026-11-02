"""Move legacy assets into the account-scoped Storage tree.

Two migrations are performed (both are idempotent):

1. ``backend/media`` (pre-Issue-#7) -> ``backend/Storage``
2. ``Storage/<Section>/<project-id>`` -> ``Storage/<Section>/<account-id>/<project-id>``
"""

from django.core.management.base import BaseCommand

from api.storage import (
    migrate_legacy_storage,
    migrate_project_folders_to_accounts,
)


class Command(BaseCommand):
    help = (
        "Move existing files into backend/Storage/<Section>/<account-id>/"
        "<project-id>/ and refresh project artifacts."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--legacy-root',
            default=None,
            help='Legacy media root (default: backend/media).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report what would move without touching files or the DB.',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)

        legacy_report = migrate_legacy_storage(
            legacy_root=options.get('legacy_root'),
            dry_run=dry_run,
        )
        account_report = migrate_project_folders_to_accounts(dry_run=dry_run)

        mode = 'DRY RUN — ' if dry_run else ''
        self.stdout.write(
            self.style.SUCCESS(
                f"{mode}Storage migration complete\n"
                f"  legacy root : {legacy_report['legacy_root']}\n"
                f"  storage root: {legacy_report['storage_root']}\n"
                f"  files moved : {legacy_report['files_moved']}\n"
                f"  segments    : {legacy_report['segments_updated']} paths updated\n"
                f"  projects    : {legacy_report['projects_updated']} output paths updated\n"
                f"  account dirs: {account_report['folders_moved']} folders moved\n"
                f"  account segs: {account_report['segments_updated']} paths updated"
            )
        )
