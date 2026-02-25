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


SUBTITLE_POSITION_CHOICES = [
    ('bottom', 'Bottom'),
    ('center', 'Center'),
    ('top', 'Top'),
]

LOGO_POSITION_CHOICES = [
    ('top-left', 'Top Left'),
    ('top-right', 'Top Right'),
    ('bottom-left', 'Bottom Left'),
    ('bottom-right', 'Bottom Right'),
]


def logo_upload_path(instance, filename):
    return f'logos/{filename}'


def outro_video_upload_path(instance, filename):
    return f'outros/{filename}'


class Logo(models.Model):
    """An uploaded logo image that can be burned into rendered videos."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    file = models.ImageField(upload_to=logo_upload_path)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['-uploaded_at']


class OutroVideo(models.Model):
    """An uploaded video clip to append at the end of rendered videos."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    file = models.FileField(upload_to=outro_video_upload_path)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['-uploaded_at']


class GlobalSettings(models.Model):
    """Singleton application-wide configuration record (pk always == 1)."""

    # ── TTS defaults ──
    default_voice_id = models.CharField(max_length=100, default='af_bella')
    tts_speed = models.FloatField(default=1.0)

    # ── Subtitle styling ──
    subtitle_font_family = models.CharField(max_length=200, default='Arial')
    subtitle_font_size = models.PositiveIntegerField(default=48)
    subtitle_font_color = models.CharField(max_length=7, default='#FFFFFF')
    subtitle_position = models.CharField(
        max_length=10,
        choices=SUBTITLE_POSITION_CHOICES,
        default='bottom',
    )
    # Manual vertical position override (pixels from top at render resolution).
    # ``None`` means use the preset position from ``subtitle_position``.
    subtitle_y_position = models.PositiveIntegerField(null=True, blank=True, default=None)

    # Legacy fields kept for backward compatibility
    subtitle_font = models.CharField(max_length=255, blank=True, default='')
    subtitle_color = models.CharField(max_length=7, default='#FFFFFF')

    # ── Render parameters ──
    render_width = models.PositiveIntegerField(default=1920)
    render_height = models.PositiveIntegerField(default=1080)
    render_fps = models.PositiveIntegerField(default=30)

    # ── Ken Burns & transitions ──
    ken_burns_zoom = models.FloatField(default=1.2)
    transition_duration = models.FloatField(default=0.5)
    zoom_intensity = models.FloatField(default=1.3)  # legacy

    # ── Audio / timing ──
    inter_segment_silence = models.FloatField(default=0.3)

    # ── Subtitle toggle ──
    subtitles_enabled = models.BooleanField(default=True)

    # ── Custom font file ──
    custom_font_file = models.FileField(
        upload_to='fonts/', null=True, blank=True,
    )

    # ── Logo watermark ──
    logo_enabled = models.BooleanField(default=False)
    active_logo = models.ForeignKey(
        'Logo', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='active_in_settings',
    )
    logo_scale = models.FloatField(default=0.15)       # 0.05–0.50
    logo_position = models.CharField(
        max_length=20,
        choices=LOGO_POSITION_CHOICES,
        default='bottom-right',
    )
    logo_opacity = models.FloatField(default=1.0)      # 0.0–1.0
    logo_margin = models.IntegerField(default=20)      # pixels

    # ── Outro video ──
    outro_enabled = models.BooleanField(default=False)
    active_outro = models.ForeignKey(
        'OutroVideo', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='active_in_settings',
    )

    # ── Timestamps ──
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ── Singleton enforcement ──

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return "Global Settings"

    class Meta:
        verbose_name = 'Global Settings'
        verbose_name_plural = 'Global Settings'
