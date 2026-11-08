from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0036_segment_ken_burns_config'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='tts_system_prompt',
            field=models.TextField(blank=True, default=''),
        ),
    ]
