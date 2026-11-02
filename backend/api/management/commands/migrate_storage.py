"""Move legacy backend/media assets into the section-scoped Storage tree."""

from django.core.management.base import BaseCommand

from api.storage import migrate_legacy_storage


class Command(BaseCommand):
    help = (
        "Move existing files from backend/media into "
        "backend/Storage/<Section>/<project-id>/ and refresh project artifacts."
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
        report = migrate_legacy_storage(
            legacy_root=options.get('legacy_root'),
            dry_run=options.get('dry_run', False),
        )
        mode = 'DRY RUN — ' if report['dry_run'] else ''
        self.stdout.write(
            self.style.SUCCESS(
                f"{mode}Storage migration complete\n"
                f"  legacy root : {report['legacy_root']}\n"
                f"  storage root: {report['storage_root']}\n"
                f"  projects    : {report['projects']}\n"
                f"  files moved : {report['files_moved']}\n"
                f"  segments    : {report['segments_updated']} paths updated\n"
                f"  projects    : {report['projects_updated']} output paths updated"
            )
        )
