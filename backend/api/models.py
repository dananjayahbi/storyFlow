import uuid
from django.db import models

STATUS_DRAFT = "DRAFT"
STATUS_PROCESSING = "PROCESSING"
STATUS_COMPLETED = "COMPLETED"
STATUS_FAILED = "FAILED"

STATUS_CHOICES = [
    (STATUS_DRAFT, 'Draft'),
    (STATUS_PROCESSING, 'Processing'),
    (STATUS_COMPLETED, 'Completed'),
    (STATUS_FAILED, 'Failed'),
]

# States from which a new render can be started.
RENDERABLE_STATUSES = {STATUS_DRAFT, STATUS_COMPLETED, STATUS_FAILED}


class Project(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    resolution_width = models.IntegerField(default=1920)
    resolution_height = models.IntegerField(default=1080)
    framerate = models.IntegerField(default=30)
    output_path = models.CharField(max_length=500, blank=True, null=True)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['-created_at']


def segment_image_path(instance, filename):
    return f'projects/{instance.project.id}/images/{filename}'


def segment_audio_path(instance, filename):
    return f'projects/{instance.project.id}/audio/{filename}'


class Segment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='segments')
    sequence_index = models.IntegerField(default=0)
    text_content = models.TextField(blank=True, default='')
    image_prompt = models.TextField(blank=True, default='')
    image_file = models.ImageField(upload_to=segment_image_path, blank=True, null=True)
    audio_file = models.FileField(upload_to=segment_audio_path, blank=True, null=True)
    audio_duration = models.FloatField(null=True, blank=True)
    is_locked = models.BooleanField(default=False)

    def __str__(self):
        return f"Segment {self.sequence_index} of {self.project.title}"

    class Meta:
        ordering = ['sequence_index']


class GlobalSettings(models.Model):
    default_voice_id = models.CharField(max_length=100, default='af_bella')
    tts_speed = models.FloatField(default=1.0)
    zoom_intensity = models.FloatField(default=1.3)
    subtitle_font = models.CharField(max_length=255, blank=True, default='')
    subtitle_color = models.CharField(max_length=7, default='#FFFFFF')

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return "Global Settings"

    class Meta:
        verbose_name = 'Global Settings'
        verbose_name_plural = 'Global Settings'
