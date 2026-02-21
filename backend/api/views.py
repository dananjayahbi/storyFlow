import logging
import os
import shutil
import uuid as uuid_mod

from django.conf import settings
from django.core.files.storage import default_storage
from django.db import transaction
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .models import Project, Segment, GlobalSettings
from .serializers import ProjectSerializer, ProjectDetailSerializer, ProjectImportSerializer, SegmentSerializer
from .parsers import ParseError
from .tasks import get_task_manager
from .validators import validate_image_upload
from core_engine.model_loader import KokoroModelLoader
from core_engine.tts_wrapper import construct_audio_path

logger = logging.getLogger(__name__)


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

    @action(detail=True, methods=['post'], url_path='generate-all-audio')
    def generate_all_audio(self, request, pk=None):
        """Generate TTS audio for all eligible segments in a project.

        Spawns a single background task that processes segments
        sequentially. Locked, empty-text, and already-generated
        segments can be skipped based on request options.
        """
        project = self.get_object()

        # 1. Parse request options
        skip_locked = request.data.get('skip_locked', True)
        force_regenerate = request.data.get('force_regenerate', False)

        # 2. Fetch and filter segments
        all_segments = Segment.objects.filter(project=project).order_by('sequence_index')
        total_segments = all_segments.count()

        segments_to_process = []
        skipped_locked = 0
        skipped_existing = 0
        skipped_empty = 0

        for seg in all_segments:
            if not seg.text_content or not seg.text_content.strip():
                skipped_empty += 1
                continue
            if seg.is_locked and skip_locked:
                skipped_locked += 1
                continue
            if seg.audio_file and not force_regenerate:
                skipped_existing += 1
                continue
            segments_to_process.append(str(seg.id))

        # 3. Handle empty processing list
        if not segments_to_process:
            return Response(
                {
                    'message': 'No segments to process.',
                    'total_segments': total_segments,
                    'segments_to_process': 0,
                    'skipped_locked': skipped_locked,
                    'skipped_existing': skipped_existing,
                    'skipped_empty': skipped_empty,
                },
                status=status.HTTP_200_OK,
            )

        # 4. TTS model check
        if not KokoroModelLoader.is_model_available():
            return Response(
                {'error': 'TTS model not available. Please install the Kokoro ONNX model file.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # 5. Read global TTS settings (capture as plain values for thread safety)
        settings_obj = GlobalSettings.load()
        voice_id = settings_obj.default_voice_id
        speed = settings_obj.tts_speed

        # Capture project ID as string (not ORM object)
        project_id = str(project.id)
        segment_ids = list(segments_to_process)  # plain list of string IDs

        # 6. Generate task ID
        hex8 = uuid_mod.uuid4().hex[:8]
        task_id = f"tts_batch_{project_id}_{hex8}"

        task_manager = get_task_manager()

        # 7. Define batch task function
        def batch_task_fn():
            from core_engine.tts_wrapper import (
                generate_audio as tts_generate,
                construct_audio_path,
                construct_audio_url,
            )
            from api.models import Segment as SegmentModel

            for idx, seg_id in enumerate(segment_ids):
                # Check cancellation before each segment
                if task_manager.is_cancelled(task_id):
                    break

                # Update progress BEFORE processing
                task_manager.update_task_progress(
                    task_id,
                    current=idx + 1,
                    total=len(segment_ids),
                    current_segment_id=seg_id,
                )

                try:
                    seg = SegmentModel.objects.get(pk=seg_id)

                    output_path = str(construct_audio_path(project_id, seg_id))
                    result = tts_generate(
                        text=seg.text_content,
                        voice_id=voice_id,
                        speed=speed,
                        output_path=output_path,
                    )

                    if result["success"]:
                        audio_url = construct_audio_url(project_id, seg_id)
                        seg.audio_file.name = audio_url.lstrip("/")
                        seg.audio_duration = result["duration"]
                        seg.save(update_fields=["audio_file", "audio_duration"])

                        task_manager.add_completed_segment(task_id, seg_id, {
                            "audio_url": audio_url,
                            "duration": result["duration"],
                        })
                    else:
                        task_manager.add_error(task_id, seg_id, result["error"])

                except Exception as exc:
                    task_manager.add_error(task_id, seg_id, str(exc))

        # 8. Submit and return 202
        task_manager.submit_task(batch_task_fn, task_id=task_id)

        return Response(
            {
                'task_id': task_id,
                'project_id': project_id,
                'status': 'PENDING',
                'total_segments': total_segments,
                'segments_to_process': len(segment_ids),
                'skipped_locked': skipped_locked,
                'skipped_existing': skipped_existing,
                'skipped_empty': skipped_empty,
                'message': (
                    f'Audio generation started for {len(segment_ids)} segments. '
                    f'Skipped: {skipped_locked} locked, {skipped_existing} existing, '
                    f'{skipped_empty} empty.'
                ),
            },
            status=status.HTTP_202_ACCEPTED,
        )


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

    @action(detail=True, methods=['post'], url_path='generate-audio')
    def generate_audio(self, request, pk=None):
        """Generate TTS audio for a single segment (async).

        Validates the segment, reads global TTS settings, and spawns
        a background task. Returns 202 Accepted with a task_id that
        the client can poll for progress.
        """
        segment = self.get_object()

        # 1. Text content check
        if not segment.text_content or not segment.text_content.strip():
            return Response(
                {'error': 'Segment has no text content to generate audio from.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 2. Lock check
        if segment.is_locked:
            return Response(
                {'error': 'Segment is locked. Unlock it before generating audio.'},
                status=status.HTTP_409_CONFLICT,
            )

        # 3. TTS model check
        if not KokoroModelLoader.is_model_available():
            return Response(
                {'error': 'TTS model not available. Please install the Kokoro ONNX model file.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # 4. Read global TTS settings
        settings_obj = GlobalSettings.load()
        voice_id = settings_obj.default_voice_id
        speed = settings_obj.tts_speed

        # 5. Define background task
        segment_id = str(segment.id)
        project_id = str(segment.project_id)

        def task_fn():
            from core_engine.tts_wrapper import (
                generate_audio as tts_generate,
                construct_audio_path,
                construct_audio_url,
            )

            output_path = str(construct_audio_path(project_id, segment_id))
            result = tts_generate(
                text=segment.text_content,
                voice_id=voice_id,
                speed=speed,
                output_path=output_path,
            )

            if result["success"]:
                audio_url = construct_audio_url(project_id, segment_id)
                seg = Segment.objects.get(pk=segment_id)
                seg.audio_file.name = audio_url.lstrip("/")
                seg.audio_duration = result["duration"]
                seg.save(update_fields=["audio_file", "audio_duration"])
            else:
                raise Exception(result["error"])

        # 6. Submit and return 202
        hex8 = uuid_mod.uuid4().hex[:8]
        task_id = f"tts_{segment_id}_{hex8}"
        get_task_manager().submit_task(task_fn, task_id=task_id)

        return Response(
            {
                'task_id': task_id,
                'segment_id': segment_id,
                'status': 'PENDING',
                'message': 'Audio generation started.',
            },
            status=status.HTTP_202_ACCEPTED,
        )

    def perform_destroy(self, instance):
        """Delete segment with media file cleanup.

        Cleans up both image and audio files BEFORE deleting
        the database record, because field values are lost
        after deletion.
        """
        # 1. Delete image file from disk
        if instance.image_file:
            if os.path.isfile(instance.image_file.path):
                os.remove(instance.image_file.path)
            else:
                logger.debug(
                    "Image file not on disk for segment %s",
                    instance.id,
                )

        # 2. Delete audio file from disk using centralised path
        audio_path = construct_audio_path(instance.project_id, instance.id)
        if os.path.isfile(str(audio_path)):
            os.remove(str(audio_path))
        else:
            logger.debug(
                "Audio file not on disk for segment %s (path: %s)",
                instance.id,
                audio_path,
            )

        # 3. Delete database record
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


@api_view(['GET'])
def task_status_view(request, task_id):
    """Return real-time progress of a background TTS task.

    Lightweight endpoint — no database queries, just a dict lookup
    in the TaskManager registry. Returns a snapshot of the task
    state that may be slightly stale (acceptable for polling).
    """
    task_state = get_task_manager().get_task_status(task_id)

    if task_state is None:
        return Response(
            {'error': 'Task not found'},
            status=status.HTTP_404_NOT_FOUND,
        )

    return Response(
        {
            'task_id': task_id,
            'status': task_state['status'],
            'progress': task_state.get('progress', {}),
            'completed_segments': task_state.get('completed_segments', []),
            'errors': task_state.get('errors', []),
        },
        status=status.HTTP_200_OK,
    )
