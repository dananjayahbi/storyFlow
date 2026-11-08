from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0035_project_render_pipeline'),
    ]

    operations = [
        migrations.AddField(
            model_name='segment',
            name='ken_burns_config',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
