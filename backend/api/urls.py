from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from . import playground_views

router = DefaultRouter()
router.register(r'accounts', views.AccountViewSet)
router.register(r'projects', views.ProjectViewSet)
router.register(r'segments', views.SegmentViewSet)
router.register(r'scripts', views.ScriptViewSet, basename='script')
router.register(r'bgm', views.BGMClipViewSet, basename='bgm')

urlpatterns = [
    path('health/', views.health_view, name='health'),
    path('auth/login/', views.login_view, name='auth-login'),
    path('auth/logout/', views.logout_view, name='auth-logout'),
    path('auth/me/', views.me_view, name='auth-me'),
    path('login/', views.login_view, name='login'),
    path('projects/import/', views.import_project, name='project-import'),
    path('projects/<str:project_id>/import-segments/', views.import_segments, name='project-import-segments'),
    path('segments/reorder/', views.reorder_segments, name='segment-reorder'),
    path('tasks/<str:task_id>/status/', views.task_status_view, name='task-status'),
    path('settings/', views.global_settings_view, name='global-settings'),
    path(
        'settings/playground/',
        playground_views.playground_view,
        name='settings-playground',
    ),
    path(
        'settings/playground/blocks/<int:index>/image/',
        playground_views.playground_block_image_view,
        name='settings-playground-block-image',
    ),
    path(
        'settings/playground/generate/',
        playground_views.playground_generate_view,
        name='settings-playground-generate',
    ),
    path(
        'settings/playground/apply/',
        playground_views.playground_apply_view,
        name='settings-playground-apply',
    ),
    path(
        'settings/playground/cancel/',
        playground_views.playground_cancel_view,
        name='settings-playground-cancel',
    ),
    path('settings/ai/', views.ai_settings_view, name='ai-settings'),
    path(
        'settings/project-defaults/',
        views.project_defaults_view,
        name='project-defaults',
    ),
    path(
        'settings/project-defaults/<int:width>x<int:height>/',
        views.project_defaults_detail_view,
        name='project-defaults-detail',
    ),
    path('script-craft/generate/', views.script_generate_view, name='script-generate'),
    path('chat/sessions/', views.chat_sessions_view, name='chat-sessions'),
    path(
        'chat/sessions/<str:session_id>/',
        views.chat_session_detail_view,
        name='chat-session-detail',
    ),
    path(
        'chat/sessions/<str:session_id>/stream/',
        views.chat_session_stream_view,
        name='chat-session-stream',
    ),
    path(
        'chat/sessions/<str:session_id>/steer/',
        views.chat_session_steer_view,
        name='chat-session-steer',
    ),
    path(
        'chat/sessions/<str:session_id>/stop/',
        views.chat_session_stop_view,
        name='chat-session-stop',
    ),
    path(
        'chat/sessions/<str:session_id>/compact/',
        views.chat_session_compact_view,
        name='chat-session-compact',
    ),
    path('settings/voices/', views.available_voices_view, name='available-voices'),
    path('settings/tts-engines/', views.tts_engines_view, name='tts-engines'),
    path('settings/tts-engines/qwen/unload/', views.qwen_unload_view, name='qwen-unload'),
    path(
        'settings/voice-references/',
        views.voice_references_view,
        name='voice-references',
    ),
    path(
        'settings/voice-references/<str:reference_id>/',
        views.voice_reference_detail_view,
        name='voice-reference-detail',
    ),
    path('settings/font/upload/', views.upload_font_view, name='upload-font'),
    path('settings/tts-test/', views.tts_test_view, name='tts-test'),
    path('settings/logos/', views.logos_view, name='logos-list'),
    path('settings/logos/<str:logo_id>/', views.logo_detail_view, name='logo-detail'),
    path('settings/outros/', views.outros_view, name='outros-list'),
    path('settings/outros/<str:outro_id>/', views.outro_detail_view, name='outro-detail'),
    path('gallery/', views.gallery_list_view, name='gallery-list'),
    path(
        'gallery/bulk-status/',
        views.gallery_bulk_status_view,
        name='gallery-bulk-status',
    ),
    path(
        'gallery/bulk-delete/',
        views.gallery_bulk_delete_view,
        name='gallery-bulk-delete',
    ),
    path(
        'gallery/<str:rendering_id>/',
        views.gallery_detail_view,
        name='gallery-detail',
    ),
    path('gallery/<str:project_id>/stream/', views.gallery_stream_view, name='gallery-stream'),
    path('gallery/<str:project_id>/download/', views.gallery_download_view, name='gallery-download'),
    path('', include(router.urls)),
]
