import os
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
    # ── Script Craft AI configuration (per account) ──
    # Empty ``ai_model`` falls back to GlobalSettings.ai_default_model.
    ai_model = models.CharField(max_length=120, blank=True, default='')
    ai_system_prompt = models.TextField(blank=True, default='')
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

    # Background music (uploads or generated MusicGen soundtracks)
    bgm_enabled = models.BooleanField(default=False)
    active_bgm = models.ForeignKey(
        'BGMClip', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='projects_using',
    )
    # Level of the music bed relative to the narration and the side-chain
    # attenuation applied while the voiceover is active.  The values are
    # account-level defaults copied here at creation time and refreshed when
    # the Audio Mix settings are saved.
    bgm_gain_db = models.FloatField(default=-18.0)
    bgm_ducking_db = models.FloatField(default=-12.0)
    bgm_echo_percent = models.FloatField(default=0.0)
    bgm_crossfade_ms = models.PositiveIntegerField(default=3000)
    tts_gain_db = models.FloatField(default=0.0)
    # A hidden project owned by the Settings page.  It never appears in the
    # project list, gallery or account counts; it exists only to preview the
    # Audio Mix settings with a three-block demo render.
    is_playground = models.BooleanField(default=False, db_index=True)
    # Playground-only assets.  The base video is rendered once (TTS + images,
    # no subtitles and no background music) and can then be re-mixed with new
    # Audio Mix values without re-running TTS or the video compositor.
    playground_base_video = models.CharField(
        max_length=500, blank=True, null=True,
    )
    playground_narration_audio = models.CharField(
        max_length=500, blank=True, null=True,
    )
    # Current playground background job: "BASE" (TTS + video) or "MIX"
    # (apply the selected music track to the existing base video).
    playground_job = models.CharField(
        max_length=10, blank=True, default='',
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


RENDERING_STATUS_RENDERED = 'rendered'
RENDERING_STATUS_READY = 'ready_to_publish'
RENDERING_STATUS_PUBLISHED = 'published'

RENDERING_STATUS_CHOICES = [
    (RENDERING_STATUS_RENDERED, 'Rendered'),
    (RENDERING_STATUS_READY, 'Ready to publish'),
    (RENDERING_STATUS_PUBLISHED, 'Published'),
]

RENDERING_STATUSES = {
    RENDERING_STATUS_RENDERED,
    RENDERING_STATUS_READY,
    RENDERING_STATUS_PUBLISHED,
}


class Rendering(models.Model):
    """One rendered video produced from a project.

    A project can be rendered any number of times (for example after editing
    its segments).  Every render is stored as its own immutable asset so the
    Gallery can keep the complete history and track the publishing workflow
    independently for each version.  The project remains the source script;
    this row is the link between that project and one rendered file.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='renderings',
    )
    # Snapshot of the project title at render time.  Renaming the project
    # later must not change the name of an already published asset.
    title = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500, blank=True, default='')
    status = models.CharField(
        max_length=20,
        choices=RENDERING_STATUS_CHOICES,
        default=RENDERING_STATUS_RENDERED,
        db_index=True,
    )
    resolution_width = models.PositiveIntegerField(default=1920)
    resolution_height = models.PositiveIntegerField(default=1080)
    framerate = models.PositiveIntegerField(default=30)
    segment_count = models.PositiveIntegerField(default=0)
    file_size = models.PositiveBigIntegerField(default=0)
    duration = models.FloatField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} ({self.get_status_display()})'


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
    # Normalised (0..1) position of the image inside the render frame.
    # 0.5/0.5 is the centred cover crop; dragging the image in the editor
    # moves the frame window across the source image.
    image_focus_x = models.FloatField(default=0.5)
    image_focus_y = models.FloatField(default=0.5)
    # Optional rectangle (normalised x/y/w/h inside the rendered frame) that
    # marks the subject.  Ken Burns keeps this area in view and centres the
    # camera path around it.  Retained for older clients; new edits write the
    # list below and mirror its first entry here.
    image_focus_area = models.JSONField(null=True, blank=True, default=None)
    # Optional ordered list of subject rectangles.  With more than one area
    # the Ken Burns camera travels through their centres over the clip so the
    # highlighted subjects are centred dynamically instead of blindly.
    image_focus_areas = models.JSONField(null=True, blank=True, default=None)

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


def bgm_upload_path(instance, filename):
    """Background music lives under the account's BGM folder."""
    safe = os.path.basename(filename or 'track.mp3')
    stem, _ext = os.path.splitext(safe)
    stem = ''.join(
        char for char in stem if char.isalnum() or char in (' ', '-', '_')
    ).strip() or 'track'
    return (
        f'bgm/{instance.section}/{instance.account_id}/'
        f'{uuid.uuid4().hex[:12]}_{stem[:80]}.mp3'
    )


BGM_SOURCE_UPLOADED = 'uploaded'
BGM_SOURCE_GENERATED = 'generated'
BGM_SOURCE_CHOICES = [
    (BGM_SOURCE_UPLOADED, 'Uploaded'),
    (BGM_SOURCE_GENERATED, 'Generated (MusicGen)'),
]


class BGMClip(models.Model):
    """A background-music track in the account's BGM Library.

    Every upload is converted to MP3 before it is stored.  Clips belong to one
    account and one workspace section; ``is_shared`` makes the clip visible to
    every account in the same section (the owner keeps edit/delete rights).

    Generated clips additionally point at the project (and store the MusicGen
    plan) that produced them so a soundtrack can be regenerated or audited.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(
        Account,
        on_delete=models.CASCADE,
        related_name='bgm_clips',
    )
    section = models.CharField(
        max_length=20,
        choices=SECTION_CHOICES,
        default='facebook',
        db_index=True,
    )
    name = models.CharField(max_length=255)
    file = models.FileField(upload_to=bgm_upload_path, max_length=500)
    is_shared = models.BooleanField(default=False)
    source = models.CharField(
        max_length=20,
        choices=BGM_SOURCE_CHOICES,
        default=BGM_SOURCE_UPLOADED,
        db_index=True,
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='generated_bgm_clips',
    )
    generation_metadata = models.JSONField(default=dict, blank=True)
    original_name = models.CharField(max_length=255, blank=True, default='')
    original_format = models.CharField(max_length=20, blank=True, default='')
    duration = models.FloatField(null=True, blank=True)
    file_size = models.PositiveBigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class Script(models.Model):
    """A generated documentary script saved to an account's Script Library.

    ``content`` stores the same JSON shape the import pipeline accepts::

        {
          "title": "...",
          "segments": [
            {"text_content": "...", "image_prompt": "..."}
          ]
        }
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(
        Account,
        on_delete=models.CASCADE,
        related_name='scripts',
    )
    section = models.CharField(
        max_length=20,
        choices=SECTION_CHOICES,
        default='facebook',
        db_index=True,
    )
    title = models.CharField(max_length=255)
    pitch = models.TextField(blank=True, default='')
    content = models.JSONField(default=dict, blank=True)
    model_used = models.CharField(max_length=120, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.title


class ChatSession(models.Model):
    """A Script Craft conversation with its own script "book".

    The conversation is stored as JSON rather than one row per message so the
    streaming endpoint can persist a turn (including partial output after a
    stop) in a single write.  ``scripts`` holds every script page created in
    the session; the AI agent can read and edit all of them through tools.

    Message shape::

        {
          "id": "...",
          "role": "user" | "assistant",
          "content": "...",
          "thinking": "...",          # optional reasoning trace
          "tools": [{"name": "...", "status": "completed", "label": "..."}],
          "question": "...",           # optional ask_user question
          "stopped": false,
          "created_at": "..."
        }
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(
        Account,
        on_delete=models.CASCADE,
        related_name='chat_sessions',
    )
    section = models.CharField(
        max_length=20,
        choices=SECTION_CHOICES,
        default='facebook',
        db_index=True,
    )
    title = models.CharField(max_length=255, blank=True, default='')
    summary = models.TextField(blank=True, default='')
    messages = models.JSONField(default=list, blank=True)
    scripts = models.JSONField(default=list, blank=True)
    # A steering message submitted while the agent is still streaming.
    pending_steer = models.TextField(blank=True, default='')
    stop_requested = models.BooleanField(default=False)
    compacted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.title or f'Chat {self.pk}'


class GlobalSettings(models.Model):
    """Singleton application-wide configuration record (pk always == 1)."""

    # ── Script Craft AI defaults (shared connection, per-account model) ──
    ai_default_model = models.CharField(max_length=120, blank=True, default='')
    ai_base_url = models.CharField(
        max_length=500,
        blank=True,
        default='http://localhost:11434/v1',
    )
    ai_api_key = models.CharField(max_length=500, blank=True, default='')
    ai_temperature = models.FloatField(default=0.7)
    # When enabled, saving the AI settings copies the model to every account.
    ai_apply_to_all = models.BooleanField(default=False)

    # ── Script Craft web search ──
    # DuckDuckGo works without a key; Brave is optional and needs an API key.
    search_enabled = models.BooleanField(default=True)
    search_provider = models.CharField(
        max_length=20,
        choices=[
            ('duckduckgo', 'DuckDuckGo'),
            ('brave', 'Brave Search'),
        ],
        default='duckduckgo',
    )
    search_brave_api_key = models.CharField(max_length=500, blank=True, default='')
    search_region = models.CharField(max_length=20, blank=True, default='wt-wt')

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

    # ── Audio mix (background music + narration) ──
    # These are account-level defaults for the render pipeline.  Saving them
    # propagates the values to every project owned by the account.
    bgm_gain_db = models.FloatField(default=-18.0)
    bgm_ducking_db = models.FloatField(default=-12.0)
    bgm_echo_percent = models.FloatField(default=0.0)
    tts_gain_db = models.FloatField(default=0.0)

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


class AccountSettings(models.Model):
    """Per-account copy of the workspace settings.

    The settings page is scoped to the active Facebook page / YouTube channel.
    Each account gets its own TTS, subtitle, render, logo, outro and upscale
    configuration.  New rows are seeded from GlobalSettings so existing
    installations keep their current behaviour until an account overrides a
    value.
    """

    account = models.OneToOneField(
        Account,
        on_delete=models.CASCADE,
        related_name='settings',
    )

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
    qwen_speaker = models.CharField(max_length=40, default=QWEN_DEFAULT_SPEAKER)
    qwen_language = models.CharField(max_length=40, default=QWEN_DEFAULT_LANGUAGE)
    qwen_instruct = models.TextField(blank=True, default='')
    qwen_max_new_tokens = models.PositiveIntegerField(
        default=QWEN_MAX_TOKENS_DEFAULT,
    )
    qwen_clone_x_vector_only = models.BooleanField(default=True)
    active_voice_reference = models.ForeignKey(
        'VoiceReference', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='account_settings_using',
    )

    # ── Subtitle styling ──
    subtitle_font_family = models.CharField(max_length=200, default='Arial')
    subtitle_font_size = models.PositiveIntegerField(default=48)
    subtitle_font_color = models.CharField(max_length=7, default='#FFFFFF')
    subtitle_position = models.CharField(
        max_length=10, choices=SUBTITLE_POSITION_CHOICES, default='bottom',
    )
    subtitle_y_position = models.PositiveIntegerField(
        null=True, blank=True, default=None,
    )
    subtitle_font = models.CharField(max_length=255, blank=True, default='')
    subtitle_color = models.CharField(max_length=7, default='#FFFFFF')

    # ── Render parameters ──
    render_width = models.PositiveIntegerField(default=1920)
    render_height = models.PositiveIntegerField(default=1080)
    render_fps = models.PositiveIntegerField(default=30)

    # ── Ken Burns & transitions ──
    ken_burns_zoom = models.FloatField(default=1.2)
    transition_duration = models.FloatField(default=0.5)
    zoom_intensity = models.FloatField(default=1.3)

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
        related_name='account_settings_using',
    )
    logo_scale = models.FloatField(default=0.15)
    logo_position = models.CharField(
        max_length=20, choices=LOGO_POSITION_CHOICES, default='bottom-right',
    )
    logo_opacity = models.FloatField(default=1.0)
    logo_margin = models.IntegerField(default=20)

    # ── Outro video ──
    outro_enabled = models.BooleanField(default=False)
    active_outro = models.ForeignKey(
        'OutroVideo', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='account_settings_using',
    )

    # ── Image upscaling (GAN) ──
    upscale_enabled = models.BooleanField(default=False)
    upscale_model = models.CharField(
        max_length=40,
        choices=Project.UPSCALE_MODEL_CHOICES,
        default='RealESRGAN_x4plus',
    )
    upscale_denoise_strength = models.FloatField(default=0.5)

    # ── Audio mix (background music + narration) ──
    bgm_gain_db = models.FloatField(default=-18.0)
    bgm_ducking_db = models.FloatField(default=-12.0)
    bgm_echo_percent = models.FloatField(default=0.0)
    tts_gain_db = models.FloatField(default=0.0)

    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Account Settings'
        verbose_name_plural = 'Account Settings'

    def __str__(self):
        return f'Settings for {self.account}'

    @classmethod
    def load(cls, account):
        """Return this account's settings, seeding from GlobalSettings once."""
        existing = cls.objects.filter(account=account).first()
        if existing:
            return existing

        defaults = GlobalSettings.load()
        return cls.objects.create(
            account=account,
            default_voice_id=defaults.default_voice_id,
            tts_speed=defaults.tts_speed,
            tts_engine=defaults.tts_engine,
            qwen_mode=defaults.qwen_mode,
            qwen_speaker=defaults.qwen_speaker,
            qwen_language=defaults.qwen_language,
            qwen_instruct=defaults.qwen_instruct,
            qwen_max_new_tokens=defaults.qwen_max_new_tokens,
            qwen_clone_x_vector_only=defaults.qwen_clone_x_vector_only,
            active_voice_reference=defaults.active_voice_reference,
            subtitle_font_family=defaults.subtitle_font_family,
            subtitle_font_size=defaults.subtitle_font_size,
            subtitle_font_color=defaults.subtitle_font_color,
            subtitle_position=defaults.subtitle_position,
            subtitle_y_position=defaults.subtitle_y_position,
            subtitle_font=defaults.subtitle_font,
            subtitle_color=defaults.subtitle_color,
            render_width=defaults.render_width,
            render_height=defaults.render_height,
            render_fps=defaults.render_fps,
            ken_burns_zoom=defaults.ken_burns_zoom,
            transition_duration=defaults.transition_duration,
            zoom_intensity=defaults.zoom_intensity,
            inter_segment_silence=defaults.inter_segment_silence,
            subtitles_enabled=defaults.subtitles_enabled,
            custom_font_file=(
                defaults.custom_font_file.name
                if defaults.custom_font_file else None
            ),
            logo_enabled=defaults.logo_enabled,
            active_logo=defaults.active_logo,
            logo_scale=defaults.logo_scale,
            logo_position=defaults.logo_position,
            logo_opacity=defaults.logo_opacity,
            logo_margin=defaults.logo_margin,
            outro_enabled=defaults.outro_enabled,
            active_outro=defaults.active_outro,
            upscale_enabled=defaults.upscale_enabled,
            upscale_model=defaults.upscale_model,
            upscale_denoise_strength=defaults.upscale_denoise_strength,
            bgm_gain_db=defaults.bgm_gain_db,
            bgm_ducking_db=defaults.bgm_ducking_db,
            bgm_echo_percent=defaults.bgm_echo_percent,
            tts_gain_db=defaults.tts_gain_db,
        )


# Settings fields copied from GlobalSettings/AccountSettings onto a new
# Project.  Project uses slightly different names for the render dimensions.
PROJECT_SETTINGS_FIELD_MAP = {
    'resolution_width': 'render_width',
    'resolution_height': 'render_height',
    'framerate': 'render_fps',
    'default_voice_id': 'default_voice_id',
    'tts_speed': 'tts_speed',
    'tts_engine': 'tts_engine',
    'qwen_mode': 'qwen_mode',
    'qwen_speaker': 'qwen_speaker',
    'qwen_language': 'qwen_language',
    'qwen_instruct': 'qwen_instruct',
    'qwen_max_new_tokens': 'qwen_max_new_tokens',
    'qwen_clone_x_vector_only': 'qwen_clone_x_vector_only',
    'active_voice_reference': 'active_voice_reference',
    'subtitle_font_family': 'subtitle_font_family',
    'subtitle_font_size': 'subtitle_font_size',
    'subtitle_font_color': 'subtitle_font_color',
    'subtitle_position': 'subtitle_position',
    'subtitle_y_position': 'subtitle_y_position',
    'subtitle_font': 'subtitle_font',
    'subtitle_color': 'subtitle_color',
    'subtitles_enabled': 'subtitles_enabled',
    'custom_font_file': 'custom_font_file',
    'zoom_intensity': 'zoom_intensity',
    'ken_burns_zoom': 'ken_burns_zoom',
    'transition_duration': 'transition_duration',
    'inter_segment_silence': 'inter_segment_silence',
    'logo_enabled': 'logo_enabled',
    'active_logo': 'active_logo',
    'logo_scale': 'logo_scale',
    'logo_position': 'logo_position',
    'logo_opacity': 'logo_opacity',
    'logo_margin': 'logo_margin',
    'outro_enabled': 'outro_enabled',
    'active_outro': 'active_outro',
    'upscale_enabled': 'upscale_enabled',
    'upscale_model': 'upscale_model',
    'upscale_denoise_strength': 'upscale_denoise_strength',
    'bgm_gain_db': 'bgm_gain_db',
    'bgm_ducking_db': 'bgm_ducking_db',
    'bgm_echo_percent': 'bgm_echo_percent',
    'tts_gain_db': 'tts_gain_db',
}


def apply_settings_to_project(project, source):
    """Copy account/global settings onto *project* before it is saved."""
    for target_field, source_field in PROJECT_SETTINGS_FIELD_MAP.items():
        value = getattr(source, source_field)
        # FileField values are bound to the source model; copy the path text
        # instead of sharing the FieldFile instance.
        if source_field == 'custom_font_file':
            value = value.name if value else None
        setattr(project, target_field, value)
    return project
