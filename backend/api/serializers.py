import re

from django.db import transaction
from rest_framework import serializers

from .models import (
    Account, Project, Segment, GlobalSettings, AccountSettings, Logo,
    OutroVideo, VoiceReference, Script, ChatSession, BGMClip, Rendering,
    DefaultProjectSettings, ProjectThumbnail, SECTION_CHOICES,
    apply_project_profile, resolve_project_defaults, normalize_subtitle_y,
)
from .parsers import JSONParser, TextParser, ParseError
from .storage_paths import media_url
from .validators import validate_import_data, HEX_COLOR_REGEX
from core_engine.tts import (
    ENGINE_CHOICES,
    QWEN_LANGUAGES,
    QWEN_MODE_CHOICES,
    QWEN_MAX_TOKENS_MAX,
    QWEN_MAX_TOKENS_MIN,
    QWEN_SPEAKERS,
)
from core_engine.metadata_prompts import thumbnail_readiness

# ── Allowed resolution presets (width × height) ──
ALLOWED_RESOLUTIONS = {
    # 16:9 Landscape (YouTube, standard widescreen)
    (1280, 720),
    (1920, 1080),
    (3840, 2160),
    # 9:16 Portrait (TikTok, Instagram Reels, YouTube Shorts)
    (720, 1280),
    (1080, 1920),
    # 1:1 Square (Instagram post, Facebook post)
    (720, 720),
    (1080, 1080),
    # 4:5 Portrait (Instagram post, Facebook feed)
    (864, 1080),
    (1080, 1350),
    # 4:3 Landscape (classic)
    (1440, 1080),
    # 3:4 Portrait
    (1080, 1440),
}

ALLOWED_FPS = {24, 30, 60}

#: Upper bound on the number of marked Ken Burns subject areas per segment.
MAX_IMAGE_FOCUS_AREAS = 1


class TtsEngineValidationMixin:
    """Shared validation for the TTS-engine fields on settings/projects."""

    def validate_tts_engine(self, value):
        allowed = {choice[0] for choice in ENGINE_CHOICES}
        if value not in allowed:
            raise serializers.ValidationError(
                f'Engine must be one of: {", ".join(sorted(allowed))}.'
            )
        return value

    def validate_qwen_mode(self, value):
        allowed = {choice[0] for choice in QWEN_MODE_CHOICES}
        if value not in allowed:
            raise serializers.ValidationError(
                f'Qwen mode must be one of: {", ".join(sorted(allowed))}.'
            )
        return value

    def validate_qwen_speaker(self, value):
        if value not in QWEN_SPEAKERS:
            raise serializers.ValidationError(
                f'Unknown Qwen speaker. Choose one of: {", ".join(QWEN_SPEAKERS)}.'
            )
        return value

    def validate_qwen_language(self, value):
        if value not in QWEN_LANGUAGES:
            raise serializers.ValidationError(
                f'Unknown Qwen language. Choose one of: {", ".join(QWEN_LANGUAGES)}.'
            )
        return value

    def validate_qwen_max_new_tokens(self, value):
        if value < QWEN_MAX_TOKENS_MIN or value > QWEN_MAX_TOKENS_MAX:
            raise serializers.ValidationError(
                f'Max new tokens must be between {QWEN_MAX_TOKENS_MIN} and '
                f'{QWEN_MAX_TOKENS_MAX}.'
            )
        return value


class AccountSerializer(serializers.ModelSerializer):
    project_count = serializers.SerializerMethodField()
    gallery_count = serializers.SerializerMethodField()

    class Meta:
        model = Account
        fields = [
            'id', 'name', 'section', 'description', 'project_count',
            'gallery_count', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_project_count(self, obj):
        return obj.projects.filter(is_playground=False).count()

    def get_gallery_count(self, obj):
        return Rendering.objects.filter(
            project__account=obj, project__is_playground=False
        ).count()

    def validate_name(self, value):
        name = (value or '').strip()
        if not name:
            raise serializers.ValidationError('Account name is required.')
        return name

    def validate_section(self, value):
        """Accounts cannot be moved between Facebook and YouTube."""
        if self.instance and value != self.instance.section:
            raise serializers.ValidationError(
                'An account cannot move to a different workspace section.'
            )
        return value

    def validate(self, attrs):
        name = attrs.get('name', getattr(self.instance, 'name', ''))
        section = attrs.get(
            'section', getattr(self.instance, 'section', 'facebook')
        )
        duplicates = Account.objects.filter(section=section, name=name)
        if self.instance:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError({
                'name': 'An account with this name already exists in this section.'
            })
        return attrs


class ProjectThumbnailSerializer(serializers.ModelSerializer):
    """Serialise one metadata-management thumbnail candidate."""

    url = serializers.SerializerMethodField()

    class Meta:
        model = ProjectThumbnail
        fields = ['id', 'url', 'prompt', 'is_active', 'created_at']
        read_only_fields = fields

    def get_url(self, obj):
        if not obj.image:
            return None
        url = media_url(obj.image.name)
        if not url:
            return None
        request = self.context.get('request')
        return request.build_absolute_uri(url) if request else url


class ProjectThumbnailMixin:
    """Expose a project's cover image and the first segment-image fallback.

    Priority:
      1. The active thumbnail uploaded from Metadata management (YouTube).
      2. The legacy manual cover.
      3. The first segment that actually has an image.

    Projects with none return ``null`` and the frontend renders its animated
    placeholder.
    """

    def _absolute_media_url(self, path):
        url = media_url(path)
        if not url:
            return None
        request = self.context.get('request')
        return request.build_absolute_uri(url) if request else url

    def _active_thumbnail(self, obj):
        cache = getattr(self, '_active_thumbnail_cache', None)
        if cache is None:
            cache = self._active_thumbnail_cache = {}
        key = str(obj.pk)
        if key not in cache:
            cache[key] = (
                obj.thumbnails.filter(is_active=True).first()
                if hasattr(obj, 'thumbnails')
                else None
            )
        return cache[key]

    def _segment_thumbnail(self, obj):
        cache = getattr(self, '_segment_thumbnail_cache', None)
        if cache is None:
            cache = self._segment_thumbnail_cache = {}
        key = str(obj.pk)
        if key not in cache:
            segment = (
                obj.segments.exclude(image_file='')
                .exclude(image_file__isnull=True)
                .order_by('sequence_index')
                .first()
            )
            cache[key] = (
                segment.image_file.name
                if segment and segment.image_file
                else None
            )
        return cache[key]

    def get_active_thumbnail_url(self, obj):
        thumbnail = self._active_thumbnail(obj)
        if not thumbnail or not thumbnail.image:
            return None
        return self._absolute_media_url(thumbnail.image.name)

    def get_has_active_thumbnail(self, obj):
        thumbnail = self._active_thumbnail(obj)
        return bool(thumbnail and thumbnail.image)

    def get_manual_thumbnail_url(self, obj):
        if not obj.thumbnail:
            return None
        return self._absolute_media_url(obj.thumbnail.name)

    def get_has_manual_thumbnail(self, obj):
        return bool(obj.thumbnail)

    def get_thumbnail_source(self, obj):
        if self.get_has_active_thumbnail(obj):
            return 'active'
        if obj.thumbnail:
            return 'manual'
        return 'segment' if self._segment_thumbnail(obj) else None

    def get_thumbnail_url(self, obj):
        active = self.get_active_thumbnail_url(obj)
        if active:
            return active
        if obj.thumbnail:
            return self._absolute_media_url(obj.thumbnail.name)
        return self._absolute_media_url(self._segment_thumbnail(obj))


class ProjectSerializer(ProjectThumbnailMixin, serializers.ModelSerializer):
    segment_count = serializers.SerializerMethodField()
    rendering_count = serializers.SerializerMethodField()
    account_name = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    manual_thumbnail_url = serializers.SerializerMethodField()
    has_manual_thumbnail = serializers.SerializerMethodField()
    active_thumbnail_url = serializers.SerializerMethodField()
    has_active_thumbnail = serializers.SerializerMethodField()
    thumbnail_source = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            'id', 'title', 'section', 'account', 'account_name',
            'created_at', 'updated_at', 'status', 'resolution_width',
            'resolution_height', 'framerate', 'segment_count',
            'rendering_count',
            'thumbnail', 'thumbnail_url', 'manual_thumbnail_url',
            'has_manual_thumbnail', 'active_thumbnail_url',
            'has_active_thumbnail', 'thumbnail_source',
        ]
        read_only_fields = [
            'id', 'account', 'created_at', 'updated_at', 'status',
        ]

    def get_segment_count(self, obj):
        return obj.segments.count()

    def get_rendering_count(self, obj):
        return obj.renderings.count()

    def get_account_name(self, obj):
        return obj.account.name if obj.account_id else None


class SegmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Segment
        fields = [
            'id', 'project', 'sequence_index', 'text_content', 'tts_text',
            'image_prompt', 'image_file', 'audio_file',
            'audio_duration', 'audio_engine', 'audio_timings', 'is_locked',
            'image_focus_x', 'image_focus_y', 'image_focus_area',
            'image_focus_areas',
        ]
        read_only_fields = [
            'id', 'project', 'sequence_index',
            'image_file', 'audio_file', 'audio_duration', 'audio_engine',
            'audio_timings',
        ]

    def validate_image_focus_x(self, value):
        if value is None or not 0.0 <= value <= 1.0:
            raise serializers.ValidationError(
                'Image focus X must be between 0.0 and 1.0.'
            )
        return value

    def validate_image_focus_y(self, value):
        if value is None or not 0.0 <= value <= 1.0:
            raise serializers.ValidationError(
                'Image focus Y must be between 0.0 and 1.0.'
            )
        return value

    def validate_image_focus_area(self, value):
        """Validate the optional Ken Burns focus rectangle.

        Coordinates are normalised to the visible render frame:
        ``{"x": 0..1, "y": 0..1, "w": 0..1, "h": 0..1}``.
        """
        if value is None:
            return None
        return self._validate_focus_rectangle(value)

    def validate_image_focus_areas(self, value):
        """Validate the single optional Ken Burns focus rectangle.

        Each entry uses the same normalised ``x``/``y``/``w``/``h`` shape as
        :attr:`image_focus_area`.  Only one rectangle may be marked per image.
        The list may be empty (or ``null``) to fall back to the default Ken
        Burns animation.
        """
        if value is None:
            return None
        if not isinstance(value, (list, tuple)):
            raise serializers.ValidationError(
                'Image focus areas must be a list of rectangles.'
            )
        if len(value) > MAX_IMAGE_FOCUS_AREAS:
            raise serializers.ValidationError(
                'Only one focus area can be marked per image.'
            )
        return [self._validate_focus_rectangle(item) for item in value]

    @staticmethod
    def _validate_focus_rectangle(value):
        if isinstance(value, dict):
            try:
                x = float(value['x'])
                y = float(value['y'])
                w = float(value['w'])
                h = float(value['h'])
            except (KeyError, TypeError, ValueError):
                raise serializers.ValidationError(
                    'Image focus area needs numeric x, y, w and h values.'
                )
        elif isinstance(value, (list, tuple)) and len(value) == 4:
            try:
                x, y, w, h = (float(number) for number in value)
            except (TypeError, ValueError):
                raise serializers.ValidationError(
                    'Image focus area needs numeric x, y, w and h values.'
                )
        else:
            raise serializers.ValidationError(
                'Image focus area must be an object with x, y, w and h.'
            )
        if not all(0.0 <= number <= 1.0 for number in (x, y, w, h)):
            raise serializers.ValidationError(
                'Image focus area values must be between 0.0 and 1.0.'
            )
        if w <= 0.0 or h <= 0.0:
            raise serializers.ValidationError(
                'Image focus area width and height must be greater than zero.'
            )
        if x + w > 1.001 or y + h > 1.001:
            raise serializers.ValidationError(
                'Image focus area must stay inside the render frame.'
            )
        return {'x': x, 'y': y, 'w': w, 'h': h}

    def update(self, instance, validated_data):
        """Keep the legacy single area in sync with the ordered list."""
        if 'image_focus_areas' in validated_data:
            areas = validated_data.get('image_focus_areas') or []
            validated_data['image_focus_area'] = areas[0] if areas else None
        elif 'image_focus_area' in validated_data:
            area = validated_data.get('image_focus_area')
            validated_data['image_focus_areas'] = [area] if area else None
        return super().update(instance, validated_data)


class VoiceReferenceSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    audio_url = serializers.SerializerMethodField()

    class Meta:
        model = VoiceReference
        fields = [
            'id', 'name', 'file', 'file_url', 'audio_url',
            'transcript', 'duration', 'uploaded_at',
        ]
        read_only_fields = [
            'id', 'file', 'uploaded_at', 'duration', 'file_url', 'audio_url',
        ]

    def _url(self, obj):
        if not obj.file:
            return None
        try:
            return obj.file.url
        except Exception:
            return None

    def get_file_url(self, obj):
        return self._url(obj)

    def get_audio_url(self, obj):
        return self._url(obj)


class ScriptSerializer(serializers.ModelSerializer):
    """A generated script stored in an account's Script Library."""

    segment_count = serializers.SerializerMethodField()

    class Meta:
        model = Script
        fields = [
            'id', 'account', 'section', 'title', 'pitch', 'content',
            'model_used', 'segment_count', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'account', 'section', 'model_used', 'segment_count',
            'created_at', 'updated_at',
        ]

    def get_segment_count(self, obj):
        segments = obj.content.get('segments') if isinstance(obj.content, dict) else None
        return len(segments) if isinstance(segments, list) else 0

    def validate_title(self, value):
        title = (value or '').strip()
        if not title:
            raise serializers.ValidationError('A script title is required.')
        return title[:255]

    def validate_content(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError('Script content must be an object.')
        segments = value.get('segments')
        if not isinstance(segments, list) or not segments:
            raise serializers.ValidationError(
                'Script content must contain a non-empty segments list.'
            )
        for index, segment in enumerate(segments, start=1):
            if not isinstance(segment, dict) or not str(
                segment.get('text_content', '')
            ).strip():
                raise serializers.ValidationError(
                    f'Segment {index} has no text_content.'
                )
        return value


class BGMClipSerializer(serializers.ModelSerializer):
    """A background-music track, including shared clips from other accounts."""

    file_url = serializers.SerializerMethodField()
    account_name = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()

    class Meta:
        model = BGMClip
        fields = [
            'id', 'account', 'account_name', 'section', 'name', 'file',
            'file_url', 'is_shared', 'source', 'project',
            'generation_metadata', 'original_name', 'original_format',
            'duration', 'file_size', 'can_edit', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'account', 'account_name', 'section', 'file', 'file_url',
            'source', 'project', 'generation_metadata', 'original_name',
            'original_format', 'duration', 'file_size', 'can_edit',
            'created_at', 'updated_at',
        ]

    def get_file_url(self, obj):
        if not obj.file:
            return None
        try:
            return obj.file.url
        except Exception:
            return None

    def get_account_name(self, obj):
        return obj.account.name if obj.account_id else None

    def _request_account_id(self):
        request = self.context.get('request')
        if request is None:
            return None
        cached = getattr(request, '_storyflow_account', None)
        if cached is not None:
            return cached.pk
        raw = None
        if hasattr(request, 'query_params'):
            raw = request.query_params.get('account')
        if not raw and hasattr(request, 'GET'):
            raw = request.GET.get('account')
        return raw

    def get_can_edit(self, obj):
        account_id = self._request_account_id()
        return bool(account_id and str(account_id) == str(obj.account_id))

    def validate_name(self, value):
        name = (value or '').strip()
        if not name:
            raise serializers.ValidationError('A track name is required.')
        return name[:255]


class ChatSessionSerializer(serializers.ModelSerializer):
    """A Script Craft chat session, optionally with its full transcript."""

    message_count = serializers.SerializerMethodField()
    script_count = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = ChatSession
        fields = [
            'id', 'account', 'section', 'title', 'summary',
            'messages', 'scripts', 'pending_steer', 'stop_requested',
            'compacted_at', 'message_count', 'script_count', 'last_message',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'account', 'section', 'summary', 'messages', 'scripts',
            'pending_steer', 'stop_requested', 'compacted_at', 'message_count',
            'script_count', 'last_message', 'created_at', 'updated_at',
        ]

    def get_message_count(self, obj):
        return len(obj.messages) if isinstance(obj.messages, list) else 0

    def get_script_count(self, obj):
        return len(obj.scripts) if isinstance(obj.scripts, list) else 0

    def get_last_message(self, obj):
        if not isinstance(obj.messages, list) or not obj.messages:
            return ''
        last = obj.messages[-1]
        if not isinstance(last, dict):
            return ''
        return str(last.get('content') or '')[:160]

    def validate_title(self, value):
        return (value or '').strip()[:255]


class LogoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Logo
        fields = ['id', 'name', 'file', 'uploaded_at']
        read_only_fields = ['id', 'uploaded_at']


class OutroVideoSerializer(serializers.ModelSerializer):
    class Meta:
        model = OutroVideo
        fields = ['id', 'name', 'file', 'uploaded_at']
        read_only_fields = ['id', 'uploaded_at']


class GlobalSettingsSerializer(TtsEngineValidationMixin, serializers.ModelSerializer):
    class Meta:
        model = GlobalSettings
        fields = [
            'default_voice_id', 'tts_speed',
            'tts_engine', 'qwen_mode', 'qwen_speaker', 'qwen_language',
            'qwen_instruct', 'qwen_max_new_tokens',
            'qwen_clone_x_vector_only', 'active_voice_reference',
            'subtitle_font_family', 'subtitle_font_size',
            'subtitle_font_color', 'subtitle_position',
            'subtitle_y_position',
            'subtitle_font', 'subtitle_color',
            'render_width', 'render_height', 'render_fps',
            'ken_burns_zoom', 'transition_duration', 'zoom_intensity',
            'inter_segment_silence', 'subtitles_enabled',
            'custom_font_file',
            'logo_enabled', 'active_logo', 'logo_scale',
            'logo_position', 'logo_opacity', 'logo_margin',
            'outro_enabled', 'active_outro',
            'upscale_enabled', 'upscale_model', 'upscale_denoise_strength',
            'bgm_gain_db', 'bgm_ducking_db', 'bgm_echo_percent', 'tts_gain_db',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['custom_font_file', 'created_at', 'updated_at']

    # ── Field-level validators ──────────────────────────────────────

    def validate_subtitle_font_color(self, value):
        """Must be a 7-char hex colour string (#RRGGBB)."""
        if value and not HEX_COLOR_REGEX.match(value):
            raise serializers.ValidationError(
                'Enter a valid hex color (e.g., #FFFFFF).'
            )
        return value

    def validate_subtitle_color(self, value):
        """Legacy field — same hex validation."""
        if value and not HEX_COLOR_REGEX.match(value):
            raise serializers.ValidationError(
                'Enter a valid hex color (e.g., #FFFFFF).'
            )
        return value

    def validate_subtitle_font_size(self, value):
        if value < 12 or value > 120:
            raise serializers.ValidationError(
                'Font size must be between 12 and 120.'
            )
        return value

    def validate_subtitle_position(self, value):
        allowed = {'bottom', 'center', 'top'}
        if value not in allowed:
            raise serializers.ValidationError(
                f'Position must be one of: {", ".join(sorted(allowed))}.'
            )
        return value

    def validate_subtitle_y_position(self, value):
        """Must be None (use preset) or a positive integer within frame."""
        if value is not None and value < 0:
            raise serializers.ValidationError(
                'Subtitle Y position must be a non-negative integer.'
            )
        return value

    def validate_ken_burns_zoom(self, value):
        if value < 1.0 or value > 2.0:
            raise serializers.ValidationError(
                'Ken Burns zoom must be between 1.0 and 2.0.'
            )
        return value

    def validate_transition_duration(self, value):
        if value < 0.0 or value > 2.0:
            raise serializers.ValidationError(
                'Transition duration must be between 0.0 and 2.0 seconds.'
            )
        return value

    def validate_render_fps(self, value):
        if value not in ALLOWED_FPS:
            raise serializers.ValidationError(
                f'FPS must be one of: {", ".join(str(f) for f in sorted(ALLOWED_FPS))}.'
            )
        return value

    def validate_inter_segment_silence(self, value):
        if value < 0.0 or value > 5.0:
            raise serializers.ValidationError(
                'Inter-segment silence must be between 0.0 and 5.0 seconds.'
            )
        return value

    def validate_logo_scale(self, value):
        if value < 0.05 or value > 0.50:
            raise serializers.ValidationError(
                'Logo scale must be between 0.05 and 0.50.'
            )
        return value

    def validate_logo_position(self, value):
        allowed = {'top-left', 'top-right', 'bottom-left', 'bottom-right'}
        if value not in allowed:
            raise serializers.ValidationError(
                f'Logo position must be one of: {", ".join(sorted(allowed))}.'
            )
        return value

    def validate_logo_opacity(self, value):
        if value < 0.0 or value > 1.0:
            raise serializers.ValidationError(
                'Logo opacity must be between 0.0 and 1.0.'
            )
        return value

    def validate_logo_margin(self, value):
        if value < 0 or value > 200:
            raise serializers.ValidationError(
                'Logo margin must be between 0 and 200 pixels.'
            )
        return value

    def validate_upscale_model(self, value):
        allowed = {'RealESRGAN_x4plus', 'RealESRGAN_x2plus', 'RealESRGAN_x4plus_anime_6B'}
        if value not in allowed:
            raise serializers.ValidationError(
                f'Upscale model must be one of: {", ".join(sorted(allowed))}.'
            )
        return value

    def validate_upscale_denoise_strength(self, value):
        if value < 0.0 or value > 1.0:
            raise serializers.ValidationError(
                'Upscale denoise strength must be between 0.0 and 1.0.'
            )
        return value

    def validate_bgm_gain_db(self, value):
        if value < -60.0 or value > 0.0:
            raise serializers.ValidationError(
                'Music gain must be between -60 and 0 dB.'
            )
        return value

    def validate_bgm_ducking_db(self, value):
        if value < -30.0 or value > 0.0:
            raise serializers.ValidationError(
                'Ducking must be between -30 and 0 dB.'
            )
        return value

    def validate_bgm_echo_percent(self, value):
        if value < 0.0 or value > 100.0:
            raise serializers.ValidationError(
                'Echo must be between 0 and 100 percent.'
            )
        return value

    def validate_tts_gain_db(self, value):
        if value < -24.0 or value > 12.0:
            raise serializers.ValidationError(
                'TTS voice volume must be between -24 and +12 dB.'
            )
        return value

    # ── Cross-field validation ──────────────────────────────────────

    def validate(self, attrs):
        """Validate that render_width × render_height form an allowed preset."""
        width = attrs.get('render_width')
        height = attrs.get('render_height')

        # Only validate if at least one dimension is being updated
        if width is not None or height is not None:
            instance = self.instance
            effective_w = width if width is not None else (instance.render_width if instance else 1920)
            effective_h = height if height is not None else (instance.render_height if instance else 1080)

            if (effective_w, effective_h) not in ALLOWED_RESOLUTIONS:
                labels = ', '.join(
                    f'{w}×{h}' for w, h in sorted(ALLOWED_RESOLUTIONS)
                )
                raise serializers.ValidationError({
                    'render_resolution': (
                        f'Resolution {effective_w}×{effective_h} is not allowed. '
                        f'Allowed presets: {labels}.'
                    )
                })

        return attrs


class AccountSettingsSerializer(GlobalSettingsSerializer):
    """Same shape and validators as GlobalSettings, scoped to one account."""

    class Meta(GlobalSettingsSerializer.Meta):
        model = AccountSettings
        fields = GlobalSettingsSerializer.Meta.fields + ['projects_view_mode']


class DefaultProjectSettingsSerializer(GlobalSettingsSerializer):
    """Resolution-specific defaults for new projects on one account."""

    class Meta(GlobalSettingsSerializer.Meta):
        model = DefaultProjectSettings
        fields = [
            'id', 'resolution_width', 'resolution_height',
            'default_voice_id', 'tts_speed',
            'tts_engine', 'qwen_mode', 'qwen_speaker', 'qwen_language',
            'qwen_instruct', 'qwen_max_new_tokens',
            'qwen_clone_x_vector_only', 'active_voice_reference',
            'subtitle_font_family', 'subtitle_font_size',
            'subtitle_font_color', 'subtitle_position',
            'subtitle_y_position',
            'subtitle_font', 'subtitle_color', 'subtitles_enabled',
            'custom_font_file',
            'framerate', 'ken_burns_zoom', 'transition_duration',
            'zoom_intensity', 'inter_segment_silence',
            'logo_enabled', 'active_logo', 'logo_scale',
            'logo_position', 'logo_opacity', 'logo_margin',
            'outro_enabled', 'active_outro',
            'upscale_enabled', 'upscale_model', 'upscale_denoise_strength',
            'bgm_gain_db', 'bgm_ducking_db', 'bgm_echo_percent', 'tts_gain_db',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'custom_font_file', 'created_at', 'updated_at',
        ]

    def validate(self, attrs):
        """Validate that the profile's resolution is an allowed preset."""
        width = attrs.get(
            'resolution_width',
            self.instance.resolution_width if self.instance else None,
        )
        height = attrs.get(
            'resolution_height',
            self.instance.resolution_height if self.instance else None,
        )
        if width is not None and height is not None:
            if (width, height) not in ALLOWED_RESOLUTIONS:
                labels = ', '.join(
                    f'{w}×{h}' for w, h in sorted(ALLOWED_RESOLUTIONS)
                )
                raise serializers.ValidationError({
                    'resolution': (
                        f'Resolution {width}×{height} is not allowed. '
                        f'Allowed presets: {labels}.'
                    )
                })
        return attrs


class ProjectDetailSerializer(
    ProjectThumbnailMixin,
    TtsEngineValidationMixin,
    serializers.ModelSerializer,
):
    segments = SegmentSerializer(many=True, read_only=True)
    thumbnails = ProjectThumbnailSerializer(many=True, read_only=True)
    rendering_count = serializers.SerializerMethodField()
    latest_rendering = serializers.SerializerMethodField()
    account_name = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    manual_thumbnail_url = serializers.SerializerMethodField()
    has_manual_thumbnail = serializers.SerializerMethodField()
    active_thumbnail_url = serializers.SerializerMethodField()
    has_active_thumbnail = serializers.SerializerMethodField()
    thumbnail_source = serializers.SerializerMethodField()
    thumbnail_readiness = serializers.SerializerMethodField()
    # Write-only switch used by the UI to re-apply the matching default
    # profile after the user explicitly asks for it.
    reset_settings = serializers.BooleanField(write_only=True, required=False)

    class Meta:
        model = Project
        fields = [
            'id', 'title', 'section', 'account', 'account_name',
            'created_at', 'updated_at', 'status', 'resolution_width',
            'resolution_height', 'framerate', 'output_path', 'segments',
            'rendering_count', 'latest_rendering', 'thumbnails',
            'thumbnail_readiness',
            'thumbnail', 'thumbnail_url', 'manual_thumbnail_url',
            'has_manual_thumbnail', 'active_thumbnail_url',
            'has_active_thumbnail', 'thumbnail_source',
            'thumbnail_system_prompt',
            'title_system_prompt', 'description_system_prompt',
            'upload_title', 'upload_description',
            'reset_settings',
            # ── Per-project settings ──
            'default_voice_id', 'tts_speed',
            'tts_engine', 'qwen_mode', 'qwen_speaker', 'qwen_language',
            'qwen_instruct', 'qwen_max_new_tokens',
            'qwen_clone_x_vector_only', 'active_voice_reference',
            'subtitle_font_family', 'subtitle_font_size',
            'subtitle_font_color', 'subtitle_position',
            'subtitle_y_position',
            'subtitle_font', 'subtitle_color',
            'subtitles_enabled', 'custom_font_file',
            'zoom_intensity', 'ken_burns_zoom', 'transition_duration',
            'render_pipeline',
            'inter_segment_silence',
            'logo_enabled', 'active_logo', 'logo_scale',
            'logo_position', 'logo_opacity', 'logo_margin',
            'outro_enabled', 'active_outro',
            'bgm_enabled', 'active_bgm', 'bgm_gain_db', 'bgm_ducking_db',
            'bgm_echo_percent', 'bgm_crossfade_ms', 'tts_gain_db',
            'upscale_enabled', 'upscale_model', 'upscale_denoise_strength',
        ]
        # A project cannot be moved between Facebook/YouTube or between
        # accounts by a PATCH; both are fixed at creation time.
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'custom_font_file', 'section',
            'account',
        ]

    def get_rendering_count(self, obj):
        return obj.renderings.count()

    def get_latest_rendering(self, obj):
        """Return the newest render's timing metadata for the editor banner."""
        latest = obj.renderings.order_by('-created_at').first()
        if latest is None:
            return None
        return {
            'id': str(latest.id),
            'created_at': latest.created_at.isoformat(),
            'status': latest.status,
            'status_label': latest.get_status_display(),
            'duration': latest.duration,
            'render_time_seconds': latest.render_time_seconds,
        }

    def get_account_name(self, obj):
        return obj.account.name if obj.account_id else None

    def get_thumbnail_readiness(self, obj):
        return thumbnail_readiness(obj)

    def update(self, instance, validated_data):
        """Replace/clear the manual cover and remove the stale file.

        Selecting a new resolution pulls that resolution's default profile
        into this project.  The project then owns that snapshot: editing it
        afterwards never changes another project or the saved defaults.
        ``reset_settings`` re-applies the profile without changing resolution.

        Subtitle placement is resolution-aware: the manual Y override is
        recomputed for the new frame height, and choosing a preset position
        clears the manual override so the preset can take effect.
        """
        reset_settings = validated_data.pop('reset_settings', False)
        old_thumbnail = instance.thumbnail.name if instance.thumbnail else ''
        resolution_changed = (
            'resolution_width' in validated_data
            or 'resolution_height' in validated_data
        )
        position_changed = 'subtitle_position' in validated_data
        instance = super().update(instance, validated_data)
        if 'thumbnail' in validated_data and old_thumbnail:
            new_thumbnail = instance.thumbnail.name if instance.thumbnail else ''
            if new_thumbnail != old_thumbnail:
                try:
                    instance.thumbnail.storage.delete(old_thumbnail)
                except Exception:  # pragma: no cover - file may already be gone
                    pass

        if reset_settings or resolution_changed:
            # The selected resolution is the profile key; restore it before
            # applying defaults so Y scaling uses the final frame height.
            if resolution_changed:
                instance.resolution_width = validated_data.get(
                    'resolution_width', instance.resolution_width,
                )
                instance.resolution_height = validated_data.get(
                    'resolution_height', instance.resolution_height,
                )
            defaults = resolve_project_defaults(
                instance.account,
                instance.resolution_width,
                instance.resolution_height,
            )
            apply_project_profile(instance, defaults)
            instance.save()

        if position_changed and 'subtitle_y_position' not in validated_data:
            # Picking Bottom/Center/Top must actually move the subtitle;
            # otherwise a stale manual Y would keep overriding the preset.
            instance.subtitle_y_position = None
            instance.save(update_fields=['subtitle_y_position'])
        elif instance.subtitle_y_position is not None:
            # A direct Y edit is also clamped so it can never leave the frame.
            clamped = normalize_subtitle_y(
                instance.subtitle_y_position,
                None,
                instance.resolution_height,
                instance.subtitle_font_size,
            )
            if clamped != instance.subtitle_y_position:
                instance.subtitle_y_position = clamped
                instance.save(update_fields=['subtitle_y_position'])
        return instance

    # ── Field-level validators (mirror GlobalSettingsSerializer) ──

    def validate_subtitle_font_color(self, value):
        if value and not HEX_COLOR_REGEX.match(value):
            raise serializers.ValidationError(
                'Enter a valid hex color (e.g., #FFFFFF).'
            )
        return value

    def validate_subtitle_color(self, value):
        if value and not HEX_COLOR_REGEX.match(value):
            raise serializers.ValidationError(
                'Enter a valid hex color (e.g., #FFFFFF).'
            )
        return value

    def validate_subtitle_font_size(self, value):
        if value < 12 or value > 120:
            raise serializers.ValidationError(
                'Font size must be between 12 and 120.'
            )
        return value

    def validate_subtitle_position(self, value):
        allowed = {'bottom', 'center', 'top'}
        if value not in allowed:
            raise serializers.ValidationError(
                f'Position must be one of: {", ".join(sorted(allowed))}.'
            )
        return value

    def validate_subtitle_y_position(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                'Subtitle Y position must be a non-negative integer.'
            )
        return value

    def validate_ken_burns_zoom(self, value):
        if value < 1.0 or value > 2.0:
            raise serializers.ValidationError(
                'Ken Burns zoom must be between 1.0 and 2.0.'
            )
        return value

    def validate_transition_duration(self, value):
        if value < 0.0 or value > 2.0:
            raise serializers.ValidationError(
                'Transition duration must be between 0.0 and 2.0 seconds.'
            )
        return value

    def validate_inter_segment_silence(self, value):
        if value < 0.0 or value > 5.0:
            raise serializers.ValidationError(
                'Inter-segment silence must be between 0.0 and 5.0 seconds.'
            )
        return value

    def validate_active_bgm(self, value):
        """Only clips from this account/section (or shared ones) may be used."""
        if value is None:
            return value
        project = self.instance
        if project is None:
            return value
        if value.section != project.section:
            raise serializers.ValidationError(
                'The selected music track belongs to a different workspace.'
            )
        if value.account_id != project.account_id and not value.is_shared:
            raise serializers.ValidationError(
                'Select a track from this account or one shared by its domain.'
            )
        return value

    def validate_bgm_gain_db(self, value):
        if value < -60.0 or value > 0.0:
            raise serializers.ValidationError(
                'Music gain must be between -60 and 0 dB.'
            )
        return value

    def validate_bgm_ducking_db(self, value):
        if value < -30.0 or value > 0.0:
            raise serializers.ValidationError(
                'Ducking must be between -30 and 0 dB.'
            )
        return value

    def validate_bgm_echo_percent(self, value):
        if value < 0.0 or value > 100.0:
            raise serializers.ValidationError(
                'Echo must be between 0 and 100 percent.'
            )
        return value

    def validate_tts_gain_db(self, value):
        if value < -24.0 or value > 12.0:
            raise serializers.ValidationError(
                'TTS voice volume must be between -24 and +12 dB.'
            )
        return value

    def validate_bgm_crossfade_ms(self, value):
        if value < 0 or value > 10000:
            raise serializers.ValidationError(
                'Music crossfade must be between 0 and 10000 milliseconds.'
            )
        return value

    def validate_logo_scale(self, value):
        if value < 0.05 or value > 0.50:
            raise serializers.ValidationError(
                'Logo scale must be between 0.05 and 0.50.'
            )
        return value

    def validate_logo_position(self, value):
        allowed = {'top-left', 'top-right', 'bottom-left', 'bottom-right'}
        if value not in allowed:
            raise serializers.ValidationError(
                f'Logo position must be one of: {", ".join(sorted(allowed))}.'
            )
        return value

    def validate_logo_opacity(self, value):
        if value < 0.0 or value > 1.0:
            raise serializers.ValidationError(
                'Logo opacity must be between 0.0 and 1.0.'
            )
        return value

    def validate_logo_margin(self, value):
        if value < 0 or value > 200:
            raise serializers.ValidationError(
                'Logo margin must be between 0 and 200 pixels.'
            )
        return value

    def validate_upscale_model(self, value):
        allowed = {'RealESRGAN_x4plus', 'RealESRGAN_x2plus', 'RealESRGAN_x4plus_anime_6B'}
        if value not in allowed:
            raise serializers.ValidationError(
                f'Upscale model must be one of: {', '.join(sorted(allowed))}.'
            )
        return value

    def validate_upscale_denoise_strength(self, value):
        if value < 0.0 or value > 1.0:
            raise serializers.ValidationError(
                'Upscale denoise strength must be between 0.0 and 1.0.'
            )
        return value

    def validate(self, attrs):
        """Validate that resolution is an allowed preset."""
        width = attrs.get('resolution_width')
        height = attrs.get('resolution_height')

        if width is not None or height is not None:
            instance = self.instance
            effective_w = width if width is not None else (
                instance.resolution_width if instance else 1920
            )
            effective_h = height if height is not None else (
                instance.resolution_height if instance else 1080
            )

            if (effective_w, effective_h) not in ALLOWED_RESOLUTIONS:
                labels = ', '.join(
                    f'{w}×{h}' for w, h in sorted(ALLOWED_RESOLUTIONS)
                )
                raise serializers.ValidationError({
                    'render_resolution': (
                        f'Resolution {effective_w}×{effective_h} is not '
                        f'allowed. Allowed presets: {labels}.'
                    )
                })

        return attrs


class ProjectImportSerializer(serializers.Serializer):
    """Handles the import pipeline: parse → validate → create Project + Segments."""

    FORMAT_CHOICES = [('json', 'JSON'), ('text', 'Text')]

    format = serializers.ChoiceField(choices=FORMAT_CHOICES)
    title = serializers.CharField(max_length=200)
    section = serializers.ChoiceField(
        choices=SECTION_CHOICES,
        required=False,
        default='facebook',
    )
    segments = serializers.ListField(child=serializers.DictField(), required=False)
    raw_text = serializers.CharField(required=False)

    def validate(self, attrs):
        fmt = attrs.get('format')
        title = attrs.get('title', '')

        # Select parser and parse
        if fmt == 'json':
            parser = JSONParser()
            parsed = parser.parse({
                'title': title,
                'segments': attrs.get('segments', []),
            })
        elif fmt == 'text':
            parser = TextParser()
            parsed = parser.parse(
                title=title,
                raw_text=attrs.get('raw_text', ''),
            )
        else:
            raise serializers.ValidationError({'format': ["Must be 'json' or 'text'."]})

        # Validate normalized data
        validated = validate_import_data(parsed)

        # Store for create()
        attrs['_parsed_data'] = validated
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        parsed = validated_data['_parsed_data']

        # 1. Create Project with the resolution-specific defaults for its
        # account.  Projects own this snapshot; later edits stay local.
        account = validated_data.get('account')
        fallback = (
            AccountSettings.load(account) if account else GlobalSettings.load()
        )
        width = fallback.render_width
        height = fallback.render_height
        project = Project.objects.create(
            title=parsed['title'],
            section=validated_data.get('section', 'facebook'),
            account=account,
            status='DRAFT',
            resolution_width=width,
            resolution_height=height,
        )
        defaults = resolve_project_defaults(account, width, height)
        apply_project_profile(project, defaults)
        project.resolution_width = width
        project.resolution_height = height
        project.save()

        # 2. Bulk create Segments
        segment_objects = [
            Segment(
                project=project,
                sequence_index=seg['sequence_index'],
                text_content=seg['text_content'],
                image_prompt=seg['image_prompt'],
            )
            for seg in parsed['segments']
        ]
        Segment.objects.bulk_create(segment_objects)

        # 3. Re-fetch with segments for response
        project = Project.objects.prefetch_related('segments').get(pk=project.pk)
        return project
