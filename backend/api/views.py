import os
import shutil

from django.conf import settings
from django.core.files.storage import default_storage
from django.db import transaction
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .models import Project, Segment
from .serializers import ProjectSerializer, ProjectDetailSerializer, ProjectImportSerializer, SegmentSerializer
from .parsers import ParseError
from .validators import validate_image_upload


class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ProjectDetailSerializer
        return ProjectSerializer

    def perform_destroy(self, instance):
        """Delete project with full media directory cleanup.

        Order matters:
          1. Delete media directory (while segment records still exist for reference)
          2. Delete DB record (CASCADE removes all segments)
        """
        # 1. Build and remove media directory
        media_path = os.path.join(
            settings.MEDIA_ROOT, 'projects', str(instance.id)
        )
        if os.path.isdir(media_path):
            shutil.rmtree(media_path, ignore_errors=True)

        # 2. Delete database record (CASCADE handles segments)
        instance.delete()


class SegmentViewSet(viewsets.ModelViewSet):
    """ViewSet for segment CRUD operations.

    Segments are created exclusively via the import endpoint.
    This ViewSet provides list, retrieve, partial_update, and destroy.
    """
    queryset = Segment.objects.all()
    serializer_class = SegmentSerializer

    # No create (POST on collection) — segments are created via import only
    # 'post' is needed for custom actions like upload-image
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def create(self, request, *args, **kwargs):
        """Disable direct segment creation — segments are created via import only."""
        return Response(
            {'error': 'Segments cannot be created directly. Use the import endpoint.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def get_queryset(self):
        queryset = Segment.objects.all()
        project_id = self.request.query_params.get('project')
        if project_id is not None:
            queryset = queryset.filter(project_id=project_id)
        elif self.action == 'list':
            return Segment.objects.none()  # Require project filter for list
        return queryset

    def perform_update(self, serializer):
        instance = self.get_object()

        if instance.is_locked:
            # Allow ONLY the is_locked field to be updated (unlock operation)
            requested_fields = set(serializer.validated_data.keys())
            if requested_fields - {'is_locked'}:
                raise ValidationError({
                    "error": "Cannot edit a locked segment. Unlock it first."
                })

        serializer.save()

    @action(detail=True, methods=['post'], url_path='upload-image')
    def upload_image(self, request, pk=None):
        segment = self.get_object()

        # 1. Lock check
        if segment.is_locked:
            return Response(
                {'error': 'Cannot modify a locked segment.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 2. Get uploaded file
        file = request.FILES.get('image')
        if not file:
            return Response(
                {'error': 'No image file provided'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 3. Validate
        validate_image_upload(file)

        # 4. Delete old image if exists
        if segment.image_file:
            old_path = segment.image_file.path
            if os.path.isfile(old_path):
                os.remove(old_path)

        # 5. Build storage path and save
        relative_path = f'projects/{segment.project_id}/images/{segment.id}_{file.name}'
        saved_path = default_storage.save(relative_path, file)

        # 6. Update model field
        segment.image_file.name = saved_path
        segment.save()

        return Response({
            'id': segment.id,
            'image_file': segment.image_file.url,
            'message': 'Image uploaded successfully',
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['delete'], url_path='remove-image')
    def remove_image(self, request, pk=None):
        segment = self.get_object()

        # 1. Lock check
        if segment.is_locked:
            return Response(
                {'error': 'Cannot modify a locked segment.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 2. Check image exists
        if not segment.image_file:
            return Response(
                {'error': 'No image to remove'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 3. Delete file from disk (self-healing if already missing)
        try:
            if os.path.isfile(segment.image_file.path):
                os.remove(segment.image_file.path)
        except FileNotFoundError:
            pass  # File already gone — clear field anyway

        # 4. Clear model field
        segment.image_file = None
        segment.save()

        return Response({
            'id': segment.id,
            'image_file': None,
            'message': 'Image removed successfully',
        }, status=status.HTTP_200_OK)

    def perform_destroy(self, instance):
        """Delete segment with media file cleanup."""
        # Delete image file from disk
        if instance.image_file:
            if os.path.isfile(instance.image_file.path):
                os.remove(instance.image_file.path)

        # Delete audio file from disk (future-proofing)
        if instance.audio_file:
            if os.path.isfile(instance.audio_file.path):
                os.remove(instance.audio_file.path)

        # Delete database record
        instance.delete()


@api_view(['POST'])
def import_project(request):
    """Import a story as a new project with segments.

    Accepts JSON or text format via the 'format' field.
    Returns the created project with nested segments.
    """
    serializer = ProjectImportSerializer(data=request.data)

    try:
        serializer.is_valid(raise_exception=True)
        project = serializer.save()
    except ParseError as e:
        return Response(
            {'error': e.message, 'details': e.details},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Serialize response with full project + nested segments
    response_serializer = ProjectDetailSerializer(project)
    return Response(response_serializer.data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
def reorder_segments(request):
    """Atomically reorder all segments within a project.

    Request body:
        {
            "project_id": 1,
            "segment_order": ["uuid1", "uuid2", "uuid3"]  // segment IDs in desired order
        }
    """
    project_id = request.data.get('project_id')
    segment_order = request.data.get('segment_order')

    # 1. Validate project_id
    if project_id is None:
        return Response(
            {'error': 'project_id is required'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        project = Project.objects.get(pk=project_id)
    except Project.DoesNotExist:
        return Response(
            {'error': 'Project not found'},
            status=status.HTTP_404_NOT_FOUND,
        )

    # 2. Validate segment_order
    if not isinstance(segment_order, list) or len(segment_order) == 0:
        return Response(
            {'error': 'segment_order must be a non-empty list of segment IDs'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # 3. Verify all IDs belong to the project
    actual_segments = Segment.objects.filter(project=project)
    actual_ids = set(str(sid) for sid in actual_segments.values_list('id', flat=True))
    requested_ids = set(str(sid) for sid in segment_order)

    if requested_ids != actual_ids:
        missing = actual_ids - requested_ids
        extra = requested_ids - actual_ids
        details = []
        if missing:
            details.append(f"Missing IDs: {sorted(missing)}")
        if extra:
            details.append(f"Invalid IDs: {sorted(extra)}")
        return Response(
            {'error': 'Invalid segment IDs', 'details': '; '.join(details)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # 4. Atomic batch update
    with transaction.atomic():
        segments_to_update = []
        for new_index, seg_id in enumerate(segment_order):
            seg = actual_segments.get(id=seg_id)
            seg.sequence_index = new_index
            segments_to_update.append(seg)
        Segment.objects.bulk_update(segments_to_update, ['sequence_index'])

    # 5. Return updated order
    return Response({
        'message': 'Segments reordered successfully',
        'segments': [
            {'id': str(seg.id), 'sequence_index': seg.sequence_index}
            for seg in segments_to_update
        ],
    }, status=status.HTTP_200_OK)
