from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'projects', views.ProjectViewSet)
router.register(r'segments', views.SegmentViewSet)

urlpatterns = [
    path('projects/import/', views.import_project, name='project-import'),
    path('projects/<str:project_id>/import-segments/', views.import_segments, name='project-import-segments'),
    path('segments/reorder/', views.reorder_segments, name='segment-reorder'),
    path('tasks/<str:task_id>/status/', views.task_status_view, name='task-status'),
    path('settings/', views.global_settings_view, name='global-settings'),
    path('settings/voices/', views.available_voices_view, name='available-voices'),
    path('settings/font/upload/', views.upload_font_view, name='upload-font'),
    path('settings/tts-test/', views.tts_test_view, name='tts-test'),
    path('', include(router.urls)),
]
