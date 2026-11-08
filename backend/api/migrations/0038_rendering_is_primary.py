from django.db import migrations, models


def backfill_primary_renderings(apps, schema_editor):
    """Mark the newest rendering of every project as its primary video."""
    Rendering = apps.get_model('api', 'Rendering')
    project_ids = (
        Rendering.objects.values_list('project_id', flat=True).distinct()
    )
    for project_id in project_ids:
        latest = (
            Rendering.objects.filter(project_id=project_id)
            .order_by('-created_at')
            .first()
        )
        if latest is None:
            continue
        Rendering.objects.filter(project_id=project_id).update(
            is_primary=False
        )
        Rendering.objects.filter(pk=latest.pk).update(is_primary=True)


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0037_project_tts_system_prompt'),
    ]

    operations = [
        migrations.AddField(
            model_name='rendering',
            name='is_primary',
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.RunPython(
            backfill_primary_renderings,
            migrations.RunPython.noop,
        ),
    ]
