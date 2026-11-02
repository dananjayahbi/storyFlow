from django.contrib import admin
from .models import Account, Project, Segment, GlobalSettings


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ['name', 'section', 'created_at', 'updated_at']
    list_filter = ['section', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['title', 'account', 'section', 'status', 'created_at', 'updated_at']
    list_filter = ['section', 'status', 'created_at']
    search_fields = ['title']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(Segment)
class SegmentAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'project', 'sequence_index', 'is_locked']
    list_filter = ['is_locked', 'project']
    search_fields = ['text_content', 'image_prompt']
    readonly_fields = ['id']


@admin.register(GlobalSettings)
class GlobalSettingsAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'default_voice_id', 'tts_speed', 'zoom_intensity']

    def has_add_permission(self, request):
        # Prevent creating multiple GlobalSettings instances
        if GlobalSettings.objects.exists():
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        # Prevent deleting the singleton
        return False
