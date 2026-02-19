from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'projects', views.ProjectViewSet)
router.register(r'segments', views.SegmentViewSet)

urlpatterns = [
    path('projects/import/', views.import_project, name='project-import'),
    path('segments/reorder/', views.reorder_segments, name='segment-reorder'),
    path('', include(router.urls)),
]
