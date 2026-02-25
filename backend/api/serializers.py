import re

from django.db import transaction
from rest_framework import serializers

from .models import Project, Segment, GlobalSettings, Logo, OutroVideo
from .parsers import JSONParser, TextParser, ParseError
from .validators import validate_import_data, HEX_COLOR_REGEX

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


class ProjectSerializer(serializers.ModelSerializer):
    segment_count = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            'id', 'title', 'created_at', 'updated_at',
            'status', 'resolution_width', 'resolution_height',
            'framerate', 'segment_count',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'status']

    def get_segment_count(self, obj):
        return obj.segments.count()


class SegmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Segment
        fields = [
            'id', 'project', 'sequence_index', 'text_content',
            'image_prompt', 'image_file', 'audio_file',
            'audio_duration', 'is_locked',
        ]
        read_only_fields = [
            'id', 'project', 'sequence_index',
            'image_file', 'audio_file', 'audio_duration',
        ]


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


class GlobalSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = GlobalSettings
        fields = [
            'default_voice_id', 'tts_speed',
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


class ProjectDetailSerializer(serializers.ModelSerializer):
    segments = SegmentSerializer(many=True, read_only=True)

    class Meta:
        model = Project
        fields = [
            'id', 'title', 'created_at', 'updated_at',
            'status', 'resolution_width', 'resolution_height',
            'framerate', 'output_path', 'segments',
            # ── Per-project settings ──
            'default_voice_id', 'tts_speed',
            'subtitle_font_family', 'subtitle_font_size',
            'subtitle_font_color', 'subtitle_position',
            'subtitle_y_position',
            'subtitle_font', 'subtitle_color',
            'subtitles_enabled', 'custom_font_file',
            'zoom_intensity', 'ken_burns_zoom', 'transition_duration',
            'inter_segment_silence',
            'logo_enabled', 'active_logo', 'logo_scale',
            'logo_position', 'logo_opacity', 'logo_margin',
            'outro_enabled', 'active_outro',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'custom_font_file']

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

        # 1. Create Project with settings copied from GlobalSettings
        gs = GlobalSettings.load()
        project = Project.objects.create(
            title=parsed['title'],
            status='DRAFT',
            # Copy per-project settings from global defaults
            resolution_width=gs.render_width,
            resolution_height=gs.render_height,
            framerate=gs.render_fps,
            default_voice_id=gs.default_voice_id,
            tts_speed=gs.tts_speed,
            subtitle_font_family=gs.subtitle_font_family,
            subtitle_font_size=gs.subtitle_font_size,
            subtitle_font_color=gs.subtitle_font_color,
            subtitle_position=gs.subtitle_position,
            subtitle_y_position=gs.subtitle_y_position,
            subtitle_font=gs.subtitle_font,
            subtitle_color=gs.subtitle_color,
            subtitles_enabled=gs.subtitles_enabled,
            custom_font_file=gs.custom_font_file if gs.custom_font_file else None,
            zoom_intensity=gs.zoom_intensity,
            ken_burns_zoom=gs.ken_burns_zoom,
            transition_duration=gs.transition_duration,
            inter_segment_silence=gs.inter_segment_silence,
            logo_enabled=gs.logo_enabled,
            active_logo=gs.active_logo,
            logo_scale=gs.logo_scale,
            logo_position=gs.logo_position,
            logo_opacity=gs.logo_opacity,
            logo_margin=gs.logo_margin,
            outro_enabled=gs.outro_enabled,
            active_outro=gs.active_outro,
        )

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
