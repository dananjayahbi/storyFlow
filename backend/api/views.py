import logging
import os
import shutil
import uuid as uuid_mod

from django.conf import settings
from django.core.files.storage import default_storage
from django.db import models, transaction
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .models import Project, Segment, GlobalSettings, STATUS_PROCESSING, STATUS_COMPLETED, STATUS_FAILED, RENDERABLE_STATUSES
from .serializers import ProjectSerializer, ProjectDetailSerializer, ProjectImportSerializer, SegmentSerializer, GlobalSettingsSerializer
from .parsers import ParseError
from .tasks import get_task_manager, render_task_function
from .validators import validate_image_upload, validate_project_for_render, validate_font_upload
from core_engine.model_loader import KokoroModelLoader
from core_engine.tts_wrapper import construct_audio_path, VALID_VOICE_IDS
from core_engine import render_utils

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
                        seg.audio_file.name = f"projects/{project_id}/audio/{seg_id}.wav"
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

    @action(detail=True, methods=['get'], url_path='status')
    def render_status(self, request, pk=None):
        """Return the current render status for a project.

        Designed for frequent polling (every ~3 s). All data comes from
        the in-memory TaskManager registry or a single DB read — no
        expensive queries.

        Returns:
            200 OK — JSON with project_id, status, progress, and output_url.
        """
        # Step 2 — base response
        project = self.get_object()
        project_id = str(project.id)
        total_segments = Segment.objects.filter(project=project).count()

        data = {
            'project_id': project_id,
            'status': project.status,
            'progress': None,
            'output_url': None,
        }

        # Step 3 — PROCESSING: real-time progress from TaskManager
        if project.status == STATUS_PROCESSING:
            task_id = f"render_{project_id}"
            task_state = get_task_manager().get_task_status(task_id)
            if task_state and task_state.get('progress'):
                prog = task_state['progress']
                data['progress'] = {
                    'current_segment': prog.get('current', 0),
                    'total_segments': prog.get('total', total_segments),
                    'percentage': int(prog.get('percentage', 0)),
                    'current_phase': prog.get('description', 'Rendering…'),
                }

        # Step 4 — COMPLETED: output URL + 100 % progress
        elif project.status == STATUS_COMPLETED:
            if project.output_path:
                data['output_url'] = f"/media/{project.output_path}"
            data['progress'] = {
                'current_segment': total_segments,
                'total_segments': total_segments,
                'percentage': 100,
                'current_phase': 'Export complete',
            }

        # Step 5 — FAILED: last known progress, no output_url
        elif project.status == STATUS_FAILED:
            task_id = f"render_{project_id}"
            task_state = get_task_manager().get_task_status(task_id)
            if task_state and task_state.get('progress'):
                prog = task_state['progress']
                data['progress'] = {
                    'current_segment': prog.get('current', 0),
                    'total_segments': prog.get('total', total_segments),
                    'percentage': int(prog.get('percentage', 0)),
                    'current_phase': prog.get('description', 'Failed'),
                }

        # Step 6 — Return 200
        return Response(data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='render')
    def render(self, request, pk=None):
        """Trigger video rendering for a project.

        Validates the project is ready (all segments have images and
        audio), checks FFmpeg availability, sets project status to
        PROCESSING, spawns a background render task, and returns 202
        Accepted with the task ID.

        Returns:
            202 Accepted — rendering started successfully.
            400 Bad Request — segments missing image or audio files.
            409 Conflict — project is already being rendered.
            500 Internal Server Error — FFmpeg not available.
        """
        # Step 2: Retrieve the project (404 handled by DRF)
        project = self.get_object()

        # Step 3: Pre-render validation
        validation_error = validate_project_for_render(project)
        if validation_error is not None:
            return Response(validation_error, status=status.HTTP_400_BAD_REQUEST)

        # Step 4: Check project status — only PROCESSING is blocked
        if project.status == STATUS_PROCESSING:
            return Response(
                {
                    'error': 'Project is already being rendered.',
                    'project_id': str(project.id),
                    'status': project.status,
                },
                status=status.HTTP_409_CONFLICT,
            )

        # Step 5: Check FFmpeg availability
        if not render_utils.check_ffmpeg():
            return Response(
                {
                    'error': (
                        'FFmpeg is required for video rendering but was '
                        'not found on the system PATH. Please install '
                        'FFmpeg and try again.'
                    ),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Step 6: Set status to PROCESSING
        project.status = STATUS_PROCESSING
        project.save(update_fields=['status'])

        # Step 7: Spawn background task
        project_id = str(project.id)
        task_id = f"render_{project_id}"

        task_manager = get_task_manager()

        # Use the standalone render_task_function from tasks.py
        # (wraps render_project with progress callback and status updates)
        def task_wrapper():
            render_task_function(project_id, task_id)

        task_manager.submit_task(task_wrapper, task_id=task_id)

        # Step 8: Return 202 Accepted
        total_segments = Segment.objects.filter(project=project).count()

        return Response(
            {
                'task_id': task_id,
                'project_id': project_id,
                'status': STATUS_PROCESSING,
                'total_segments': total_segments,
                'message': 'Video rendering started.',
            },
            status=status.HTTP_202_ACCEPTED,
        )


class SegmentViewSet(viewsets.ModelViewSet):
    """ViewSet for segment CRUD operations.

    Segments can be created individually via POST with a project ID,
    or in bulk via the import endpoint.
    This ViewSet provides create, list, retrieve, partial_update, and destroy.
    """
    queryset = Segment.objects.all()
    serializer_class = SegmentSerializer

    # No create (POST on collection) — segments are created via import only
    # 'post' is needed for custom actions like upload-image
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def create(self, request, *args, **kwargs):
        """Create a new segment within an existing project."""
        project_id = request.data.get('project')
        if not project_id:
            return Response(
                {'error': 'The "project" field is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            return Response(
                {'error': 'Project not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Calculate next sequence_index
        max_index = project.segments.aggregate(
            max_idx=models.Max('sequence_index')
        )['max_idx']
        next_index = (max_index + 1) if max_index is not None else 0

        segment = Segment.objects.create(
            project=project,
            sequence_index=next_index,
            text_content=request.data.get('text_content', ''),
            image_prompt=request.data.get('image_prompt', ''),
        )

        serializer = self.get_serializer(segment)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

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

    @action(detail=True, methods=['delete'], url_path='remove-audio')
    def remove_audio(self, request, pk=None):
        segment = self.get_object()

        # 1. Lock check
        if segment.is_locked:
            return Response(
                {'error': 'Cannot modify a locked segment.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 2. Check audio exists
        if not segment.audio_file:
            return Response(
                {'error': 'No audio to remove'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 3. Delete file from disk (self-healing if already missing)
        try:
            audio_path = construct_audio_path(segment.project_id, segment.id)
            if os.path.isfile(str(audio_path)):
                os.remove(str(audio_path))
        except FileNotFoundError:
            pass  # File already gone — clear field anyway

        # 4. Clear model fields
        segment.audio_file = None
        segment.audio_duration = None
        segment.save(update_fields=['audio_file', 'audio_duration'])

        return Response({
            'id': str(segment.id),
            'audio_file': None,
            'audio_duration': None,
            'message': 'Audio removed successfully',
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
                seg = Segment.objects.get(pk=segment_id)
                seg.audio_file.name = f"projects/{project_id}/audio/{segment_id}.wav"
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
def import_segments(request, project_id):
    """Import segments into an existing project.

    Accepts JSON or text format via the 'format' field.
    Appends parsed segments to the project (existing segments are preserved).
    Returns the updated list of segments.
    """
    # 1. Validate project exists
    try:
        project = Project.objects.get(pk=project_id)
    except Project.DoesNotExist:
        return Response(
            {'error': 'Project not found'},
            status=status.HTTP_404_NOT_FOUND,
        )

    # 2. Parse the incoming data using the same parsers
    fmt = request.data.get('format', 'json')
    if fmt == 'json':
        from .parsers import JSONParser as StoryJSONParser
        parser = StoryJSONParser()
        try:
            parsed = parser.parse({
                'title': project.title,
                'segments': request.data.get('segments', []),
            })
        except ParseError as e:
            return Response(
                {'error': e.message, 'details': e.details},
                status=status.HTTP_400_BAD_REQUEST,
            )
    elif fmt == 'text':
        from .parsers import TextParser
        parser = TextParser()
        try:
            parsed = parser.parse(
                title=project.title,
                raw_text=request.data.get('raw_text', ''),
            )
        except ParseError as e:
            return Response(
                {'error': e.message, 'details': e.details},
                status=status.HTTP_400_BAD_REQUEST,
            )
    else:
        return Response(
            {'error': "format must be 'json' or 'text'"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # 3. Validate parsed segments
    from .validators import validate_import_data
    try:
        validated = validate_import_data(parsed)
    except ParseError as e:
        return Response(
            {'error': e.message, 'details': e.details},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # 4. Determine starting sequence_index
    max_index = project.segments.aggregate(
        max_idx=models.Max('sequence_index')
    )['max_idx']
    start_index = (max_index + 1) if max_index is not None else 0

    # 5. Create segments atomically
    with transaction.atomic():
        segment_objects = [
            Segment(
                project=project,
                sequence_index=start_index + i,
                text_content=seg['text_content'],
                image_prompt=seg.get('image_prompt', ''),
            )
            for i, seg in enumerate(validated['segments'])
        ]
        Segment.objects.bulk_create(segment_objects)

    # 6. Return all segments for the project
    all_segments = project.segments.order_by('sequence_index')
    serializer = SegmentSerializer(all_segments, many=True)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


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


# ===================================================================
# Global Settings Endpoint (Task 05.03.01)
# ===================================================================

@api_view(['GET', 'PATCH'])
def global_settings_view(request):
    """Retrieve or update the singleton GlobalSettings instance.

    GET  → Returns the current settings (creates defaults if no row exists).
    PATCH → Partial-update of any settings fields.
    """
    settings_obj = GlobalSettings.load()

    if request.method == 'GET':
        serializer = GlobalSettingsSerializer(settings_obj)
        return Response(serializer.data)

    # PATCH
    serializer = GlobalSettingsSerializer(
        settings_obj, data=request.data, partial=True
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


# ===================================================================
# Available Voices Endpoint (Task 05.03.02)
# ===================================================================

# Voice metadata: maps voice IDs to user-friendly names and genders.
# This is the canonical source — the frontend falls back to a
# hardcoded copy if this endpoint is unreachable.
VOICE_METADATA = {
    'af_bella':    {'id': 'af_bella',    'name': 'Bella',    'gender': 'Female', 'language': 'en-US'},
    'af_sarah':    {'id': 'af_sarah',    'name': 'Sarah',    'gender': 'Female', 'language': 'en-US'},
    'af_nicole':   {'id': 'af_nicole',   'name': 'Nicole',   'gender': 'Female', 'language': 'en-US'},
    'af_sky':      {'id': 'af_sky',      'name': 'Sky',      'gender': 'Female', 'language': 'en-US'},
    'af_alloy':    {'id': 'af_alloy',    'name': 'Alloy',    'gender': 'Female', 'language': 'en-US'},
    'af_aoede':    {'id': 'af_aoede',    'name': 'Aoede',    'gender': 'Female', 'language': 'en-US'},
    'af_jessica':  {'id': 'af_jessica',  'name': 'Jessica',  'gender': 'Female', 'language': 'en-US'},
    'af_kore':     {'id': 'af_kore',     'name': 'Kore',     'gender': 'Female', 'language': 'en-US'},
    'af_nova':     {'id': 'af_nova',     'name': 'Nova',     'gender': 'Female', 'language': 'en-US'},
    'af_river':    {'id': 'af_river',    'name': 'River',    'gender': 'Female', 'language': 'en-US'},
    'am_adam':     {'id': 'am_adam',     'name': 'Adam',     'gender': 'Male',   'language': 'en-US'},
    'am_michael':  {'id': 'am_michael',  'name': 'Michael',  'gender': 'Male',   'language': 'en-US'},
    'am_echo':     {'id': 'am_echo',     'name': 'Echo',     'gender': 'Male',   'language': 'en-US'},
    'am_eric':     {'id': 'am_eric',     'name': 'Eric',     'gender': 'Male',   'language': 'en-US'},
    'am_fenrir':   {'id': 'am_fenrir',   'name': 'Fenrir',   'gender': 'Male',   'language': 'en-US'},
    'am_liam':     {'id': 'am_liam',     'name': 'Liam',     'gender': 'Male',   'language': 'en-US'},
    'am_onyx':     {'id': 'am_onyx',     'name': 'Onyx',     'gender': 'Male',   'language': 'en-US'},
    'am_puck':     {'id': 'am_puck',     'name': 'Puck',     'gender': 'Male',   'language': 'en-US'},
    'bf_emma':     {'id': 'bf_emma',     'name': 'Emma',     'gender': 'Female', 'accent': 'British', 'language': 'en-GB'},
    'bf_alice':    {'id': 'bf_alice',    'name': 'Alice',    'gender': 'Female', 'accent': 'British', 'language': 'en-GB'},
    'bf_isabella': {'id': 'bf_isabella', 'name': 'Isabella', 'gender': 'Female', 'accent': 'British', 'language': 'en-GB'},
    'bf_lily':     {'id': 'bf_lily',     'name': 'Lily',     'gender': 'Female', 'accent': 'British', 'language': 'en-GB'},
    'bm_george':   {'id': 'bm_george',   'name': 'George',   'gender': 'Male',   'accent': 'British', 'language': 'en-GB'},
    'bm_daniel':   {'id': 'bm_daniel',   'name': 'Daniel',   'gender': 'Male',   'accent': 'British', 'language': 'en-GB'},
    'bm_fable':    {'id': 'bm_fable',    'name': 'Fable',    'gender': 'Male',   'accent': 'British', 'language': 'en-GB'},
    'bm_lewis':    {'id': 'bm_lewis',    'name': 'Lewis',    'gender': 'Male',   'accent': 'British', 'language': 'en-GB'},
}


@api_view(['GET'])
def available_voices_view(request):
    """Return the list of available Kokoro TTS voices.

    Scans the voice directory for .pt files and enriches each entry
    with metadata (name, gender).  Falls back to the full
    VALID_VOICE_IDS list if no .pt files are found on disk.
    """
    voices_dir = os.path.join(settings.BASE_DIR, '..', 'models', 'voices')
    discovered_ids: set[str] = set()

    if os.path.isdir(voices_dir):
        for fname in os.listdir(voices_dir):
            if fname.endswith('.pt'):
                voice_id = fname[:-3]  # strip .pt
                if voice_id in VALID_VOICE_IDS:
                    discovered_ids.add(voice_id)

    # Fall back to the full set if no .pt files were found
    if not discovered_ids:
        discovered_ids = set(VALID_VOICE_IDS)

    voices = []
    for vid in sorted(discovered_ids):
        meta = VOICE_METADATA.get(vid)
        if meta:
            voices.append(meta)
        else:
            # Unknown voice file — use the raw ID
            voices.append({'id': vid, 'name': vid, 'gender': 'Unknown'})

    return Response(voices)


# ===================================================================
# Font Upload Endpoint (Task 05.03.03)
# ===================================================================

@api_view(['POST'])
def upload_font_view(request):
    """Upload a custom subtitle font (.ttf or .otf).

    Accepts a multipart/form-data POST with a 'font' file field.
    Saves the file to MEDIA_ROOT/fonts/, updates subtitle_font_family
    to the font filename (without extension), and cleans up old files.
    """
    font_file = request.FILES.get('font')
    if not font_file:
        return Response(
            {'error': 'No font file provided.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Validate extension and size
    validate_font_upload(font_file)

    # Ensure fonts directory exists
    fonts_dir = os.path.join(settings.MEDIA_ROOT, 'fonts')
    os.makedirs(fonts_dir, exist_ok=True)

    settings_obj = GlobalSettings.load()

    # Delete old custom font file from disk if it exists
    if settings_obj.custom_font_file:
        try:
            old_path = settings_obj.custom_font_file.path
            if os.path.isfile(old_path):
                os.remove(old_path)
                logger.info("Removed previous custom font: %s", old_path)
        except Exception:
            pass  # file may already be gone

    # Save the file
    safe_name = os.path.basename(font_file.name)
    dest_path = os.path.join(fonts_dir, safe_name)

    with open(dest_path, 'wb') as f:
        for chunk in font_file.chunks():
            f.write(chunk)

    # Derive font family from filename (strip extension)
    font_family = os.path.splitext(safe_name)[0]

    settings_obj.custom_font_file.name = os.path.join('fonts', safe_name)
    settings_obj.subtitle_font_family = font_family
    settings_obj.subtitle_font = dest_path  # legacy field
    settings_obj.save()

    logger.info("Custom font uploaded: %s (family: %s)", dest_path, font_family)

    serializer = GlobalSettingsSerializer(settings_obj)
    return Response(serializer.data)


# ===================================================================
# TTS Test Endpoint
# ===================================================================

@api_view(['POST'])
def tts_test_view(request):
    """Generate a test audio clip from arbitrary text.

    Request body:
        {
            "text": "Hello world, this is a test.",
            "voice": "af_bella",   // optional, defaults to settings
            "speed": 1.0           // optional, defaults to settings
        }

    Returns the generated WAV file as an audio/wav response.
    """
    text = request.data.get('text', '').strip()
    if not text:
        return Response(
            {'error': 'text is required'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    settings_obj = GlobalSettings.load()
    voice = request.data.get('voice', settings_obj.default_voice_id)
    speed = float(request.data.get('speed', settings_obj.tts_speed))

    # Generate audio to a temporary file
    import tempfile
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
        output_path = tmp.name

    try:
        from core_engine.tts_wrapper import generate_audio as tts_generate
        result = tts_generate(
            text=text,
            output_path=output_path,
            voice_id=voice,
            speed=speed,
        )

        if not result.get('success'):
            return Response(
                {'error': result.get('error', 'TTS generation failed')},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Return the audio file
        from django.http import FileResponse
        response = FileResponse(
            open(output_path, 'rb'),
            content_type='audio/wav',
        )
        response['Content-Disposition'] = 'inline; filename="tts_test.wav"'
        return response

    except Exception as e:
        logger.error("TTS test failed: %s", str(e))
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
