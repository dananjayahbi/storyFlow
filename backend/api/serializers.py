from rest_framework import serializers
from .models import Project, Segment, GlobalSettings


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
        read_only_fields = ['id']


class GlobalSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = GlobalSettings
        fields = [
            'default_voice_id', 'tts_speed', 'zoom_intensity',
            'subtitle_font', 'subtitle_color',
        ]


class ProjectDetailSerializer(serializers.ModelSerializer):
    segments = SegmentSerializer(many=True, read_only=True)

    class Meta:
        model = Project
        fields = [
            'id', 'title', 'created_at', 'updated_at',
            'status', 'resolution_width', 'resolution_height',
            'framerate', 'output_path', 'segments',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
