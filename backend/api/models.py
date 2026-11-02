import uuid
from django.db import models

from core_engine.tts import (
    ENGINE_CHOICES,
    ENGINE_KOKORO,
    QWEN_DEFAULT_LANGUAGE,
    QWEN_DEFAULT_SPEAKER,
    QWEN_MAX_TOKENS_DEFAULT,
    QWEN_MODE_CHOICES,
    QWEN_MODE_CUSTOM,
)

from .storage_paths import project_relpath

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


SECTION_CHOICES = [
    ('facebook', 'Facebook Reels'),
    ('youtube', 'YouTube Videos'),
]

DEFAULT_ACCOUNT_NAME = 'Default Account'


class Account(models.Model):
    """A Facebook page or YouTube account owned by one workspace section.

    Accounts are the top-level content containers: every project belongs to
    exactly one account, and each account has its own gallery, storage folder
    and (in the future) its own side-specific tools and rules.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    section = models.CharField(
        max_length=20,
        choices=SECTION_CHOICES,
        default='facebook',
        db_index=True,
    )
    description = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['section', 'name'],
                name='unique_account_name_per_section',
            ),
        ]

    def __str__(self):
        return f'{self.name} ({self.section})'

    @classmethod
    def default_for_section(cls, section):
        """Return the fallback account for *section*, creating it if needed."""
        account, _ = cls.objects.get_or_create(
            section=section or 'facebook',
            name=DEFAULT_ACCOUNT_NAME,
        )
        return account


class Project(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    section = models.CharField(
        max_length=20,
        choices=SECTION_CHOICES,
        default='facebook',
    )
    account = models.ForeignKey(
        Account,
        on_delete=models.CASCADE,
        related_name='projects',
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    resolution_width = models.IntegerField(default=1920)
    resolution_height = models.IntegerField(default=1080)
    framerate = models.IntegerField(default=30)
    output_path = models.CharField(max_length=500, blank=True, null=True)

    # ── Per-project settings (copied from GlobalSettings on creation) ──

    # TTS
    default_voice_id = models.CharField(max_length=100, default='af_bella')
    tts_speed = models.FloatField(default=1.0)

    # TTS engine selection ("kokoro" is fast/CPU, "qwen" is GPU + cloning)
    tts_engine = models.CharField(
        max_length=20, choices=ENGINE_CHOICES, default=ENGINE_KOKORO,
    )
    qwen_mode = models.CharField(
        max_length=20, choices=QWEN_MODE_CHOICES, default=QWEN_MODE_CUSTOM,
    )
    qwen_speaker = models.CharField(
        max_length=40, default=QWEN_DEFAULT_SPEAKER,
    )
    qwen_language = models.CharField(
        max_length=40, default=QWEN_DEFAULT_LANGUAGE,
    )
    qwen_instruct = models.TextField(blank=True, default='')
    qwen_max_new_tokens = models.PositiveIntegerField(
        default=QWEN_MAX_TOKENS_DEFAULT,
    )
    qwen_clone_x_vector_only = models.BooleanField(default=True)
    active_voice_reference = models.ForeignKey(
        'VoiceReference', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='projects_using',
    )

    # Subtitle styling
    subtitle_font_family = models.CharField(max_length=200, default='Arial')
    subtitle_font_size = models.PositiveIntegerField(default=48)
    subtitle_font_color = models.CharField(max_length=7, default='#FFFFFF')
    subtitle_position = models.CharField(
        max_length=10,
        choices=SUBTITLE_POSITION_CHOICES,
        default='bottom',
    )
    subtitle_y_position = models.PositiveIntegerField(
        null=True, blank=True, default=None,
    )
    subtitle_font = models.CharField(max_length=255, blank=True, default='')
    subtitle_color = models.CharField(max_length=7, default='#FFFFFF')
    subtitles_enabled = models.BooleanField(default=True)
    custom_font_file = models.FileField(
        upload_to='fonts/', null=True, blank=True,
    )

    # Render / Ken-Burns
    zoom_intensity = models.FloatField(default=1.3)
    ken_burns_zoom = models.FloatField(default=1.2)
    transition_duration = models.FloatField(default=0.5)

    # Audio / timing
    inter_segment_silence = models.FloatField(default=0.3)

    # Logo watermark
    logo_enabled = models.BooleanField(default=False)
    active_logo = models.ForeignKey(
        'Logo', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='projects_using',
    )
    logo_scale = models.FloatField(default=0.15)
    logo_position = models.CharField(
        max_length=20,
        choices=LOGO_POSITION_CHOICES,
        default='bottom-right',
    )
    logo_opacity = models.FloatField(default=1.0)
    logo_margin = models.IntegerField(default=20)

    # Outro video
    outro_enabled = models.BooleanField(default=False)
    active_outro = models.ForeignKey(
        'OutroVideo', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='projects_using',
    )

    # Image upscaling (GAN)
    UPSCALE_MODEL_CHOICES = [
        ('RealESRGAN_x4plus', 'Real-ESRGAN x4 (General)'),
        ('RealESRGAN_x2plus', 'Real-ESRGAN x2 (General)'),
        ('RealESRGAN_x4plus_anime_6B', 'Real-ESRGAN x4 (Anime)'),
    ]
    upscale_enabled = models.BooleanField(default=False)
    upscale_model = models.CharField(
        max_length=40,
        choices=UPSCALE_MODEL_CHOICES,
        default='RealESRGAN_x4plus',
    )
    upscale_denoise_strength = models.FloatField(default=0.5)

    def save(self, *args, **kwargs):
        """Guarantee every project has an account (legacy/test compatibility)."""
        if not self.account_id:
            self.account = Account.default_for_section(self.section)
            update_fields = kwargs.get('update_fields')
            if update_fields is not None:
                kwargs['update_fields'] = set(update_fields) | {'account'}
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['-created_at']


def segment_image_path(instance, filename):
    """Store images in Storage/<Section>/<account-id>/<project-id>/images/."""
    return project_relpath(
        instance.project.section,
        instance.project.id,
        'images',
        filename,
        account_id=instance.project.account_id,
    )


def segment_audio_path(instance, filename):
    """Store generated audio in Storage/<Section>/<account-id>/<project-id>/audio/."""
    return project_relpath(
        instance.project.section,
        instance.project.id,
        'audio',
        filename,
        account_id=instance.project.account_id,
    )


class Segment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='segments')
    sequence_index = models.IntegerField(default=0)
    text_content = models.TextField(blank=True, default='')
    image_prompt = models.TextField(blank=True, default='')
    # 500 chars: account UUID + project UUID + section + filename can exceed
    # Django's 100-char default and would otherwise raise SuspiciousFileOperation.
    image_file = models.ImageField(
        upload_to=segment_image_path, blank=True, null=True, max_length=500,
    )
    audio_file = models.FileField(
        upload_to=segment_audio_path, blank=True, null=True, max_length=500,
    )
    audio_duration = models.FloatField(null=True, blank=True)
    # Which engine produced the current audio ("kokoro" or "qwen"), so the UI
    # can show whether a segment is still on the fast draft voice.
    audio_engine = models.CharField(max_length=20, blank=True, default='')
    is_locked = models.BooleanField(default=False)

    def __str__(self):
        return f"Segment {self.sequence_index} of {self.project.title}"

    class Meta:
        ordering = ['sequence_index']


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


def voice_reference_upload_path(instance, filename):
    """Reference clips for Qwen zero-shot voice cloning."""
    return f'voice_references/{filename}'


class VoiceReference(models.Model):
    """An uploaded reference clip used by Qwen3-TTS voice cloning.

    Multiple references can be stored; the project/global settings pick one via
    ``active_voice_reference``.  3-10 second clean speech clips work best.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    file = models.FileField(upload_to=voice_reference_upload_path)
    transcript = models.TextField(blank=True, default='')
    duration = models.FloatField(null=True, blank=True)
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

    # ── TTS engine defaults ──
    tts_engine = models.CharField(
        max_length=20, choices=ENGINE_CHOICES, default=ENGINE_KOKORO,
    )
    qwen_mode = models.CharField(
        max_length=20, choices=QWEN_MODE_CHOICES, default=QWEN_MODE_CUSTOM,
    )
    qwen_speaker = models.CharField(
        max_length=40, default=QWEN_DEFAULT_SPEAKER,
    )
    qwen_language = models.CharField(
        max_length=40, default=QWEN_DEFAULT_LANGUAGE,
    )
    qwen_instruct = models.TextField(blank=True, default='')
    qwen_max_new_tokens = models.PositiveIntegerField(
        default=QWEN_MAX_TOKENS_DEFAULT,
    )
    qwen_clone_x_vector_only = models.BooleanField(default=True)
    active_voice_reference = models.ForeignKey(
        'VoiceReference', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='active_in_settings',
    )

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

    # ── Image upscaling (GAN) ──
    upscale_enabled = models.BooleanField(default=False)
    upscale_model = models.CharField(
        max_length=40,
        choices=Project.UPSCALE_MODEL_CHOICES,
        default='RealESRGAN_x4plus',
    )
    upscale_denoise_strength = models.FloatField(default=0.5)

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
