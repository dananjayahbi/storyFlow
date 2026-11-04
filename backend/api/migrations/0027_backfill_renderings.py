"""Backfill one Rendering per already-completed project.

Before gallery asset management existed a project stored a single
``output_path``.  This migration preserves those videos in the new Gallery by
creating a Rendering row whose id is the project id (so old gallery links keep
working).  Projects without any output are skipped; the Gallery view can still
create rows lazily for files that appear later.
"""

from django.db import migrations


def backfill_renderings(apps, schema_editor):
    Project = apps.get_model('api', 'Project')
    Rendering = apps.get_model('api', 'Rendering')

    completed = Project.objects.filter(
        status='COMPLETED', is_playground=False
    ).exclude(output_path__isnull=True).exclude(output_path='')

    for project in completed.iterator():
        if Rendering.objects.filter(project_id=project.id).exists():
            continue
        Rendering.objects.create(
            id=project.id,
            project_id=project.id,
            title=project.title,
            file_path=project.output_path or '',
            status='rendered',
            resolution_width=project.resolution_width,
            resolution_height=project.resolution_height,
            framerate=project.framerate,
            segment_count=project.segments.count(),
            file_size=0,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0026_rendering'),
    ]

    operations = [
        migrations.RunPython(backfill_renderings, migrations.RunPython.noop),
    ]
