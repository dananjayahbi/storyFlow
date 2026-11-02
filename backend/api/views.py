import logging
import os
import shutil
import uuid as uuid_mod

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.storage import default_storage
from django.db import models, transaction
from django.http import FileResponse, StreamingHttpResponse
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .models import (
    Account, Project, Segment, GlobalSettings, Logo, OutroVideo,
    VoiceReference, STATUS_PROCESSING, STATUS_COMPLETED, STATUS_FAILED,
    RENDERABLE_STATUSES, SECTION_CHOICES,
)
from .serializers import (
    AccountSerializer, ProjectSerializer, ProjectDetailSerializer,
    ProjectImportSerializer, SegmentSerializer, GlobalSettingsSerializer,
    LogoSerializer, OutroVideoSerializer, VoiceReferenceSerializer,
)
from .parsers import ParseError
from .storage import write_project_artifacts, save_story_json
from .storage_paths import (
    media_url,
    project_dir,
    project_relpath,
    section_folder,
    upgrade_legacy_project_path,
)
from .tasks import get_task_manager, render_task_function
from .validators import (
    validate_image_upload, validate_project_for_render, validate_font_upload,
    validate_voice_reference_upload,
)
from core_engine import tts as tts_engine
from core_engine.model_loader import KokoroModelLoader
from core_engine.tts_wrapper import construct_audio_path, VALID_VOICE_IDS
from core_engine import render_utils

logger = logging.getLogger(__name__)

VALID_SECTIONS = {choice[0] for choice in SECTION_CHOICES}


def get_requested_section(request):
    """Return the workspace section requested by the client, if any.

    The frontend always sends ``?section=facebook`` or ``?section=youtube``
    on every API call.  All project-scoped endpoints use this helper so
    Facebook and YouTube data can never be mixed, even if a client
    accidentally knows a project UUID from the other section.
    """
    section = request.query_params.get('section') if hasattr(request, 'query_params') else request.GET.get('section')
    if not section:
        # Optional custom header for non-browser clients.
        section = request.headers.get('X-StoryFlow-Section')
    if not section:
        return None
    if section not in VALID_SECTIONS:
        raise ValidationError({
            'section': f"Invalid section '{section}'. Must be one of: {', '.join(sorted(VALID_SECTIONS))}."
        })
    return section


def get_requested_account(request):
    """Return the account requested by the client, if any.

    Every account-scoped API call carries ``?account=<uuid>`` (the frontend
    also sends it automatically).  The account must belong to the active
    workspace section so a Facebook page can never read YouTube content and
    two accounts on the same side can never see each other's projects.
    """
    if hasattr(request, '_storyflow_account'):
        return request._storyflow_account

    raw = None
    if hasattr(request, 'query_params'):
        raw = request.query_params.get('account')
    if not raw:
        raw = request.GET.get('account')
    if not raw:
        raw = request.headers.get('X-StoryFlow-Account')

    if not raw:
        request._storyflow_account = None
        return None

    try:
        account = Account.objects.get(pk=raw)
    except (Account.DoesNotExist, ValueError, DjangoValidationError):
        raise ValidationError({'account': 'Account not found.'})

    section = get_requested_section(request)
    if section and account.section != section:
        raise ValidationError({
            'account': (
                f"Account '{account.name}' belongs to '{account.section}', "
                f"not '{section}'."
            )
        })

    request._storyflow_account = account
    return account


def scoped_projects(request):
    """Return a Project queryset restricted to the requested section/account."""
    queryset = Project.objects.all()
    section = get_requested_section(request)
    if section:
        queryset = queryset.filter(section=section)
    account = get_requested_account(request)
    if account:
        queryset = queryset.filter(account=account)
    return queryset


# ---------------------------------------------------------------------------
# TTS engine helpers (Kokoro default, Qwen optional)
# ---------------------------------------------------------------------------

def resolve_tts_engine(data, default='kokoro'):
    """Validate an explicit ``engine`` in a request body and return it."""
    requested = data.get('engine') if hasattr(data, 'get') else None
    if requested and requested not in tts_engine.VALID_ENGINES:
        raise ValidationError({
            'engine': (
                f"Invalid engine '{requested}'. Must be one of: "
                f"{', '.join(sorted(tts_engine.VALID_ENGINES))}."
            )
        })
    return tts_engine.normalize_engine(requested, default=default)


def resolve_voice_reference(project, requested_id):
    """Resolve an explicit voice reference, else the project's active one."""
    if requested_id:
        try:
            return VoiceReference.objects.get(pk=requested_id)
        except (
            VoiceReference.DoesNotExist,
            ValueError,
            DjangoValidationError,
        ):
            raise ValidationError({
                'voice_reference_id': 'Voice reference not found.'
            })
    return project.active_voice_reference


def voice_reference_path(reference):
    """Absolute path to a reference clip, or ``None`` if it is missing."""
    if not reference or not reference.file:
        return None
    try:
        path = reference.file.path
    except (ValueError, NotImplementedError):
        return None
    return path if os.path.isfile(path) else None


def build_tts_options(project, engine, reference=None):
    """Snapshot engine settings into plain values (thread-safe for tasks)."""
    return {
        'engine': engine,
        'voice_id': project.default_voice_id,
        'speed': project.tts_speed,
        'qwen_mode': project.qwen_mode,
        'qwen_speaker': project.qwen_speaker,
        'qwen_language': project.qwen_language,
        'qwen_instruct': project.qwen_instruct,
        'qwen_max_new_tokens': project.qwen_max_new_tokens,
        'qwen_x_vector_only': project.qwen_clone_x_vector_only,
        'reference_audio_path': voice_reference_path(reference),
        'reference_text': (reference.transcript if reference else '') or '',
    }


def engine_ready_response(engine):
    """Return a 503 response when *engine* cannot run, else ``None``."""
    if tts_engine.engine_available(engine):
        return None
    return Response(
        {'error': tts_engine.unavailable_message(engine)},
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


class AccountViewSet(viewsets.ModelViewSet):
    """CRUD for workspace accounts (Facebook pages / YouTube channels).

    Accounts are always scoped by the ``section`` query parameter.  Deleting
    an account removes every project it owns, including their asset folders.
    """

    queryset = Account.objects.all()
    serializer_class = AccountSerializer
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        queryset = Account.objects.all()
        section = get_requested_section(self.request)
        if section:
            queryset = queryset.filter(section=section)
        return queryset

    def perform_create(self, serializer):
        section = get_requested_section(self.request)
        data_section = serializer.validated_data.get('section')
        if section and data_section and section != data_section:
            raise ValidationError({
                'section': (
                    f"Request is scoped to '{section}' but the account was "
                    f"created for '{data_section}'."
                )
            })
        serializer.save(section=section or data_section or 'facebook')

    def perform_destroy(self, instance):
        for project in instance.projects.all():
            shutil.rmtree(
                project_dir(
                    project.section,
                    project.id,
                    account_id=instance.id,
                ),
                ignore_errors=True,
            )
        instance.delete()


class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_serializer_class(self):
        if self.action in ('retrieve', 'partial_update', 'update'):
            return ProjectDetailSerializer
        return ProjectSerializer

    def get_queryset(self):
        """Scope every project read/write to the active workspace section.

        Without this filter a Facebook page could list — or open by UUID —
        a YouTube project (and vice versa).  The section is supplied by the
        frontend as a query parameter on every request.
        """
        return scoped_projects(self.request)

    def perform_create(self, serializer):
        """Keep the created project inside the section requested by the client."""
        section = get_requested_section(self.request)
        data_section = serializer.validated_data.get('section')
        if section and data_section and section != data_section:
            raise ValidationError({
                'section': (
                    f"Request is scoped to '{section}' but the project was "
                    f"created for '{data_section}'."
                )
            })

        account = get_requested_account(self.request)
        data_account = serializer.validated_data.get('account')
        if account and data_account and account != data_account:
            raise ValidationError({
                'account': (
                    "Request is scoped to a different account than the "
                    "project payload."
                )
            })
        effective_section = section or data_section or 'facebook'
        account = account or data_account or Account.default_for_section(
            effective_section
        )
        if account.section != effective_section:
            raise ValidationError({
                'account': 'Account does not belong to this workspace section.'
            })
        serializer.save(section=effective_section, account=account)

    def perform_destroy(self, instance):
        """Delete project with its complete section-scoped asset folder.

        Order matters:
          1. Delete the Storage/<Section>/<project-id>/ directory
          2. Delete DB record (CASCADE removes all segments)
        """
        # 1. Remove the project's self-contained asset folder
        shutil.rmtree(
            project_dir(
                instance.section,
                instance.id,
                account_id=instance.account_id,
            ),
            ignore_errors=True,
        )

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
        engine = resolve_tts_engine(request.data, default=project.tts_engine)
        voice_reference = resolve_voice_reference(
            project, request.data.get('voice_reference_id')
        )

        if engine == tts_engine.ENGINE_QWEN:
            if project.qwen_mode == tts_engine.QWEN_MODE_CLONE and \
                    not voice_reference_path(voice_reference):
                return Response(
                    {
                        'error': (
                            'Qwen voice cloning needs a reference voice. '
                            'Upload one in Settings -> Voice References and '
                            'select it for this project.'
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # 2. TTS model check (per engine)
        engine_error = engine_ready_response(engine)
        if engine_error is not None:
            return engine_error

        # 3. Fetch and filter segments
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
                # Skip only audio already produced by the requested engine, so
                # switching Kokoro draft -> Qwen final regenerates naturally.
                current_engine = seg.audio_engine or tts_engine.ENGINE_KOKORO
                if current_engine == engine:
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

        # 5. Snapshot engine settings as plain values for thread safety
        tts_options = build_tts_options(project, engine, voice_reference)

        # Capture project ID as string (not ORM object)
        project_id = str(project.id)
        segment_ids = list(segments_to_process)  # plain list of string IDs

        # 6. Generate task ID
        hex8 = uuid_mod.uuid4().hex[:8]
        task_id = f"tts_batch_{project_id}_{hex8}"

        task_manager = get_task_manager()

        # 7. Define batch task function
        def batch_task_fn():
            from core_engine.tts import synthesize
            from core_engine.tts_wrapper import (
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
                    result = synthesize(
                        seg.text_content,
                        output_path,
                        **tts_options,
                    )

                    if result["success"]:
                        audio_url = construct_audio_url(project_id, seg_id)
                        seg.audio_file.name = project_relpath(
                            project.section, project_id, 'audio', f'{seg_id}.wav'
                        )
                        seg.audio_duration = result["duration"]
                        seg.audio_engine = result.get("engine", engine)
                        seg.save(update_fields=[
                            "audio_file", "audio_duration", "audio_engine",
                        ])

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
                'engine': engine,
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
            if task_state:
                # If the task has been cancelled, report FAILED immediately
                if task_state.get('cancel_requested') or task_state.get('status') == 'CANCELLED':
                    data['status'] = STATUS_FAILED
                    prog = task_state.get('progress', {})
                    data['progress'] = {
                        'current_segment': prog.get('current', 0),
                        'total_segments': prog.get('total', total_segments),
                        'percentage': int(prog.get('percentage', 0)),
                        'current_phase': 'Cancelled by user',
                    }
                elif task_state.get('progress'):
                    prog = task_state['progress']
                    # Percentage is pre-scaled by on_progress():
                    #   0–80 % → segment processing
                    #  80–99 % → export phase
                    # During the export phase, show total_segments from
                    # the DB instead of the raw progress total (100).
                    is_export = prog.get('is_export_phase', False)
                    data['progress'] = {
                        'current_segment': total_segments if is_export else prog.get('current', 0),
                        'total_segments': total_segments,
                        'percentage': int(prog.get('percentage', 0)),
                        'current_phase': prog.get('description', 'Rendering…'),
                    }

        # Step 4 — COMPLETED: output URL + 100 % progress
        elif project.status == STATUS_COMPLETED:
            if project.output_path:
                data['output_url'] = media_url(project.output_path)
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

    @action(detail=True, methods=['post'], url_path='cancel-render')
    def cancel_render(self, request, pk=None):
        """Cancel an in-progress render for a project.

        Sets the cooperative cancellation flag in TaskManager so the
        render task aborts between segments.  The project status is
        set back to FAILED to indicate an incomplete render.

        Returns:
            200 OK — cancellation requested.
            409 Conflict — project is not currently rendering.
        """
        project = self.get_object()
        project_id = str(project.id)

        if project.status != STATUS_PROCESSING:
            return Response(
                {
                    'error': 'Project is not currently rendering.',
                    'project_id': project_id,
                    'status': project.status,
                },
                status=status.HTTP_409_CONFLICT,
            )

        task_id = f"render_{project_id}"
        task_manager = get_task_manager()
        cancelled = task_manager.cancel_task(task_id)

        if not cancelled:
            # Task not found in registry — reset project status
            project.status = STATUS_FAILED
            project.save(update_fields=['status'])

        return Response(
            {
                'project_id': project_id,
                'status': 'CANCELLING',
                'message': 'Render cancellation requested.',
            },
            status=status.HTTP_200_OK,
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
            project = scoped_projects(request).get(id=project_id)
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
        queryset = Segment.objects.select_related('project')
        section = get_requested_section(self.request)
        if section:
            # Hard section boundary: segments only exist through a project.
            queryset = queryset.filter(project__section=section)
        account = get_requested_account(self.request)
        if account:
            # Hard account boundary inside the section.
            queryset = queryset.filter(project__account=account)

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
        relative_path = project_relpath(
            segment.project.section,
            segment.project_id,
            'images',
            f'{segment.id}_{file.name}',
        )
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

        # 3. Resolve the engine (per-request override or project default)
        project = segment.project
        engine = resolve_tts_engine(request.data, default=project.tts_engine)
        voice_reference = resolve_voice_reference(
            project, request.data.get('voice_reference_id')
        )

        if engine == tts_engine.ENGINE_QWEN and \
                project.qwen_mode == tts_engine.QWEN_MODE_CLONE and \
                not voice_reference_path(voice_reference):
            return Response(
                {
                    'error': (
                        'Qwen voice cloning needs a reference voice. Upload '
                        'one in Settings -> Voice References and select it.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 4. Model availability check (per engine)
        engine_error = engine_ready_response(engine)
        if engine_error is not None:
            return engine_error

        # 5. Snapshot engine settings as plain values for the worker thread
        tts_options = build_tts_options(project, engine, voice_reference)
        section = project.section
        text_content = segment.text_content

        # 6. Define background task
        segment_id = str(segment.id)
        project_id = str(project.id)

        def task_fn():
            from core_engine.tts import synthesize
            from core_engine.tts_wrapper import (
                construct_audio_path,
                construct_audio_url,
            )

            output_path = str(construct_audio_path(project_id, segment_id))
            result = synthesize(text_content, output_path, **tts_options)

            if result["success"]:
                seg = Segment.objects.get(pk=segment_id)
                seg.audio_file.name = project_relpath(
                    section, project_id, 'audio', f'{segment_id}.wav'
                )
                seg.audio_duration = result["duration"]
                seg.audio_engine = result.get("engine", engine)
                seg.save(update_fields=[
                    "audio_file", "audio_duration", "audio_engine",
                ])
            else:
                raise Exception(result["error"])

        # 7. Submit and return 202
        hex8 = uuid_mod.uuid4().hex[:8]
        task_id = f"tts_{segment_id}_{hex8}"
        get_task_manager().submit_task(task_fn, task_id=task_id)

        return Response(
            {
                'task_id': task_id,
                'segment_id': segment_id,
                'status': 'PENDING',
                'engine': engine,
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

    requested_section = get_requested_section(request)
    payload_section = request.data.get('section')
    if requested_section and payload_section and requested_section != payload_section:
        return Response(
            {
                'error': (
                    f"Request is scoped to '{requested_section}' but the "
                    f"import targets '{payload_section}'."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    effective_section = requested_section or payload_section or 'facebook'
    account = get_requested_account(request) or Account.default_for_section(
        effective_section
    )
    if account.section != effective_section:
        return Response(
            {'error': 'Account does not belong to this workspace section.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        serializer.is_valid(raise_exception=True)
        project = serializer.save(
            section=effective_section,
            account=account,
        )
    except ParseError as e:
        return Response(
            {'error': e.message, 'details': e.details},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Persist the imported draft/story and refresh project.json + script.txt.
    # Segments are bulk-created by the serializer, so signals do not fire
    # for each one — sync explicitly here.
    save_story_json(
        project,
        {
            'format': request.data.get('format', 'json'),
            'segments': request.data.get('segments', []),
            'raw_text': request.data.get('raw_text', ''),
        },
    )
    write_project_artifacts(project)

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
    # 1. Validate project exists (and belongs to the requested section)
    try:
        project = scoped_projects(request).get(pk=project_id)
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

    # Refresh project.json + script.txt (bulk_create bypasses signals)
    write_project_artifacts(project)

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
        project = scoped_projects(request).get(pk=project_id)
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

    # Keep the project snapshot/script in sync (bulk_update bypasses signals)
    write_project_artifacts(project)

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
    """Generate a test audio clip from arbitrary text with any engine.

    Request body::

        {
            "text": "Hello world, this is a test.",
            "engine": "kokoro" | "qwen",      # optional, defaults to settings
            "voice": "af_bella",              # Kokoro voice
            "speed": 1.0,
            "mode": "custom_voice" | "clone", # Qwen mode
            "speaker": "Aiden",               # Qwen preset speaker
            "language": "English",
            "instruct": "",
            "max_new_tokens": 1024,
            "voice_reference_id": "<uuid>",   # Qwen cloning reference
            "x_vector_only": true
        }

    Returns the generated WAV file as an ``audio/wav`` response.
    """
    text = request.data.get('text', '').strip()
    if not text:
        return Response(
            {'error': 'text is required'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    settings_obj = GlobalSettings.load()
    engine = resolve_tts_engine(request.data, default=settings_obj.tts_engine)
    engine_error = engine_ready_response(engine)
    if engine_error is not None:
        return engine_error

    voice = request.data.get('voice', settings_obj.default_voice_id)
    speed = float(request.data.get('speed', settings_obj.tts_speed))

    mode = request.data.get('mode', settings_obj.qwen_mode)
    reference = resolve_voice_reference(
        settings_obj, request.data.get('voice_reference_id')
    )
    reference_path = voice_reference_path(reference)

    if engine == tts_engine.ENGINE_QWEN and mode == tts_engine.QWEN_MODE_CLONE \
            and not reference_path:
        return Response(
            {'error': 'Voice cloning needs a reference voice. Upload one first.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Generate audio to a temporary file
    import tempfile
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
        output_path = tmp.name

    try:
        from core_engine.tts import synthesize

        result = synthesize(
            text,
            output_path,
            engine=engine,
            voice_id=voice,
            speed=speed,
            qwen_mode=mode,
            qwen_speaker=request.data.get(
                'speaker', settings_obj.qwen_speaker
            ),
            qwen_language=request.data.get(
                'language', settings_obj.qwen_language
            ),
            qwen_instruct=request.data.get(
                'instruct', settings_obj.qwen_instruct
            ),
            qwen_max_new_tokens=int(request.data.get(
                'max_new_tokens', settings_obj.qwen_max_new_tokens
            )),
            qwen_x_vector_only=bool(request.data.get(
                'x_vector_only', settings_obj.qwen_clone_x_vector_only
            )),
            reference_audio_path=reference_path,
            reference_text=(reference.transcript if reference else ''),
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


# ===================================================================
# TTS Engines (Kokoro default + optional Qwen3-TTS on GPU)
# ===================================================================

@api_view(['GET'])
def tts_engines_view(request):
    """Report availability and capabilities of both speech engines.

    ``available`` for Qwen additionally requires a working CUDA device, since
    the engine never falls back to CPU.
    """
    from core_engine import qwen_client

    kokoro_ready = tts_engine.kokoro_available()
    qwen_installed = tts_engine.qwen_available()
    qwen_info = qwen_client.probe() if qwen_installed else {}

    qwen_cuda = bool(qwen_info.get('cuda'))
    qwen_ready = bool(qwen_installed and qwen_info.get('ok') and qwen_cuda)

    qwen_error = qwen_info.get('error')
    if qwen_installed and qwen_info.get('ok') and not qwen_cuda:
        qwen_error = (
            'No CUDA GPU detected. Qwen3-TTS runs on the GPU only and never '
            'falls back to CPU.'
        )

    engines = [
        {
            'id': tts_engine.ENGINE_KOKORO,
            'label': 'Kokoro (fast, default)',
            'available': kokoro_ready,
            'device': 'CPU (ONNX runtime)',
            'supports_cloning': False,
            'description': (
                'Lightweight Kokoro-82M ONNX voice. Fast enough to build a '
                'complete draft video, then finalize the audio with Qwen.'
            ),
        },
        {
            'id': tts_engine.ENGINE_QWEN,
            'label': 'Qwen3-TTS (GPU)',
            'available': qwen_ready,
            'installed': qwen_installed,
            'device': qwen_info.get('device', 'unavailable'),
            'cuda': qwen_cuda,
            'python': qwen_client.resolve_qwen_python(),
            'base_model': qwen_info.get('base_model'),
            'custom_voice_model': qwen_info.get('custom_voice_model'),
            'supports_cloning': True,
            'error': qwen_error,
            'speakers': qwen_info.get('speakers') or {
                name: name for name in tts_engine.QWEN_SPEAKERS
            },
            'languages': qwen_info.get('languages') or tts_engine.QWEN_LANGUAGES,
            'modes': [
                {'id': mode, 'label': label}
                for mode, label in tts_engine.QWEN_MODE_CHOICES
            ],
            'description': (
                'Qwen3-TTS 0.6B on the GPU. High quality and zero-shot voice '
                'cloning from uploaded reference clips. Heavy: only one '
                'checkpoint is resident at a time.'
            ),
        },
    ]

    return Response({
        'default_engine': tts_engine.ENGINE_KOKORO,
        'engines': engines,
    })


@api_view(['POST'])
def qwen_unload_view(request):
    """Unload the Qwen checkpoint to release VRAM."""
    from core_engine import qwen_client

    result = qwen_client.unload()
    if not result.get('ok'):
        return Response(
            {'error': result.get('error', 'Could not unload Qwen.')},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return Response(result)


# ===================================================================
# Voice references (Qwen zero-shot cloning)
# ===================================================================

@api_view(['GET', 'POST'])
def voice_references_view(request):
    """List or upload reference clips used by Qwen voice cloning."""
    if request.method == 'GET':
        refs = VoiceReference.objects.all()
        return Response(VoiceReferenceSerializer(refs, many=True).data)

    file = request.FILES.get('file') or request.FILES.get('audio')
    if not file:
        return Response(
            {'error': 'No reference audio file provided.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    validate_voice_reference_upload(file)

    raw_name = request.data.get('name') or os.path.splitext(
        os.path.basename(file.name)
    )[0]
    name = (raw_name or 'Voice reference').strip()[:255]

    reference = VoiceReference.objects.create(
        name=name,
        file=file,
        transcript=request.data.get('transcript', '') or '',
    )

    # Best-effort duration for the UI.  Any codec soundfile cannot read is
    # still usable by the engine (it decodes via ffmpeg).
    try:
        from core_engine.audio_utils import get_audio_duration

        reference.duration = get_audio_duration(reference.file.path)
        reference.save(update_fields=['duration'])
    except Exception:
        logger.debug('Could not read voice reference duration', exc_info=True)

    return Response(
        VoiceReferenceSerializer(reference).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(['PATCH', 'DELETE'])
def voice_reference_detail_view(request, reference_id):
    """Rename/retranscribe or delete a reference clip."""
    try:
        reference = VoiceReference.objects.get(pk=reference_id)
    except (VoiceReference.DoesNotExist, ValueError, DjangoValidationError):
        return Response(
            {'error': 'Voice reference not found.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == 'PATCH':
        if 'name' in request.data:
            reference.name = (request.data.get('name') or '').strip()[:255] or reference.name
        if 'transcript' in request.data:
            reference.transcript = request.data.get('transcript') or ''
        reference.save(update_fields=['name', 'transcript'])
        return Response(VoiceReferenceSerializer(reference).data)

    # DELETE — detach from settings/projects, then remove the file
    GlobalSettings.objects.filter(active_voice_reference=reference).update(
        active_voice_reference=None
    )
    Project.objects.filter(active_voice_reference=reference).update(
        active_voice_reference=None
    )
    try:
        reference.file.delete(save=False)
    except Exception:
        logger.debug('Could not delete voice reference file', exc_info=True)
    reference.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


# ── Gallery API ──


def _resolve_video_path(project):
    """Resolve the absolute path to a project's rendered video.

    Checks:
    1. The stored output_path (absolute or relative to MEDIA_ROOT)
    2. The conventional path: <MEDIA_ROOT>/<Section>/<id>/output/final.mp4
    3. The legacy media/projects/<id>/output/final.mp4 path
    Returns the path if it exists on disk, or None.
    """
    candidates = []

    if project.output_path:
        stored = project.output_path
        candidates.append(stored)
        # Legacy relative paths (projects/<id>/... or <Section>/<id>/...)
        upgraded = upgrade_legacy_project_path(
            stored.replace('\\', '/'),
            project.section,
            project.id,
            project.account_id,
        )
        candidates.append(upgraded)
        candidates.append(os.path.join(settings.MEDIA_ROOT, upgraded))

    # Conventional account-scoped path
    candidates.append(
        os.path.join(
            project_dir(
                project.section,
                project.id,
                account_id=project.account_id,
            ),
            'output',
            'final.mp4',
        )
    )

    # Pre-account layout, kept for stores that have not been migrated yet
    candidates.append(
        os.path.join(
            settings.MEDIA_ROOT,
            section_folder(project.section),
            str(project.id),
            'output',
            'final.mp4',
        )
    )

    # Legacy location, kept for stores that have not been migrated yet
    candidates.append(
        os.path.join(
            settings.BASE_DIR, 'media', 'projects',
            str(project.id), 'output', 'final.mp4',
        )
    )

    for candidate in candidates:
        if not candidate:
            continue
        if os.path.isfile(candidate):
            return candidate

    return None


@api_view(['GET'])
def gallery_list_view(request):
    """List all completed projects that have rendered videos.

    Returns a JSON array of gallery items with project metadata and video info.
    Only projects with status COMPLETED and an existing video file are included.

    GET /api/gallery/
    """
    projects = scoped_projects(request).filter(status=STATUS_COMPLETED).order_by('-updated_at')
    items = []

    for project in projects:
        video_path = _resolve_video_path(project)
        if not video_path:
            continue

        # Get file metadata
        try:
            file_size = os.path.getsize(video_path)
        except OSError:
            file_size = 0

        segment_count = Segment.objects.filter(project=project).count()

        items.append({
            'id': str(project.id),
            'title': project.title,
            'created_at': project.created_at.isoformat(),
            'updated_at': project.updated_at.isoformat(),
            'resolution_width': project.resolution_width,
            'resolution_height': project.resolution_height,
            'framerate': project.framerate,
            'segment_count': segment_count,
            'file_size': file_size,
            'stream_url': f'/api/gallery/{project.id}/stream/',
            'download_url': f'/api/gallery/{project.id}/download/',
        })

    return Response(items)


@api_view(['GET'])
def gallery_stream_view(request, project_id):
    """Stream a rendered video for in-browser playback.

    Supports HTTP Range requests for seeking/progressive playback.

    GET /api/gallery/<project_id>/stream/
    """
    try:
        project = scoped_projects(request).get(id=project_id)
    except Project.DoesNotExist:
        return Response(
            {'error': 'Project not found'},
            status=status.HTTP_404_NOT_FOUND,
        )

    video_path = _resolve_video_path(project)
    if not video_path:
        return Response(
            {'error': 'Video file not found'},
            status=status.HTTP_404_NOT_FOUND,
        )

    file_size = os.path.getsize(video_path)
    content_type = 'video/mp4'

    # Handle Range requests for video seeking
    range_header = request.META.get('HTTP_RANGE')
    if range_header:
        try:
            range_spec = range_header.strip().replace('bytes=', '')
            range_parts = range_spec.split('-')
            start = int(range_parts[0]) if range_parts[0] else 0
            end = int(range_parts[1]) if range_parts[1] else file_size - 1
            end = min(end, file_size - 1)
            length = end - start + 1

            def file_range_iterator(path, start, length, chunk_size=8192):
                with open(path, 'rb') as f:
                    f.seek(start)
                    remaining = length
                    while remaining > 0:
                        read_size = min(chunk_size, remaining)
                        data = f.read(read_size)
                        if not data:
                            break
                        remaining -= len(data)
                        yield data

            response = StreamingHttpResponse(
                file_range_iterator(video_path, start, length),
                status=206,
                content_type=content_type,
            )
            response['Content-Length'] = str(length)
            response['Content-Range'] = f'bytes {start}-{end}/{file_size}'
            response['Accept-Ranges'] = 'bytes'
            return response
        except (ValueError, IndexError):
            pass  # Fall through to full file response

    # Full file response
    response = FileResponse(
        open(video_path, 'rb'),
        content_type=content_type,
    )
    response['Content-Length'] = str(file_size)
    response['Accept-Ranges'] = 'bytes'
    response['Content-Disposition'] = f'inline; filename="{project.title}.mp4"'
    return response


@api_view(['GET'])
def gallery_download_view(request, project_id):
    """Download a rendered video as an attachment.

    GET /api/gallery/<project_id>/download/
    """
    try:
        project = scoped_projects(request).get(id=project_id)
    except Project.DoesNotExist:
        return Response(
            {'error': 'Project not found'},
            status=status.HTTP_404_NOT_FOUND,
        )

    video_path = _resolve_video_path(project)
    if not video_path:
        return Response(
            {'error': 'Video file not found'},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Sanitize filename for Content-Disposition
    safe_title = project.title.replace('"', "'").replace('\n', ' ').strip()
    if not safe_title:
        safe_title = str(project.id)

    response = FileResponse(
        open(video_path, 'rb'),
        content_type='video/mp4',
    )
    response['Content-Disposition'] = f'attachment; filename="{safe_title}.mp4"'
    response['Content-Length'] = str(os.path.getsize(video_path))
    return response


# ===================================================================
# Logo Management Endpoints
# ===================================================================

@api_view(['GET', 'POST'])
def logos_view(request):
    """List all logos (GET) or upload a new logo (POST).

    GET  /api/settings/logos/
    POST /api/settings/logos/  (multipart with 'file' field)
    """
    if request.method == 'GET':
        logos = Logo.objects.all()
        serializer = LogoSerializer(logos, many=True)
        return Response(serializer.data)

    # POST — upload
    logo_file = request.FILES.get('file')
    if not logo_file:
        return Response(
            {'error': 'No file provided.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Validate extension
    ext = os.path.splitext(logo_file.name)[1].lower()
    allowed_exts = {'.png', '.webp', '.jpg', '.jpeg'}
    if ext not in allowed_exts:
        return Response(
            {'error': f'Only {", ".join(sorted(allowed_exts))} files are allowed.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Validate size (5 MB max)
    if logo_file.size > 5 * 1024 * 1024:
        return Response(
            {'error': 'Logo file must be under 5 MB.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Ensure logos directory exists
    logos_dir = os.path.join(settings.MEDIA_ROOT, 'logos')
    os.makedirs(logos_dir, exist_ok=True)

    # Derive name from filename
    name = os.path.splitext(os.path.basename(logo_file.name))[0]

    logo = Logo.objects.create(name=name, file=logo_file)
    serializer = LogoSerializer(logo)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(['DELETE'])
def logo_detail_view(request, logo_id):
    """Delete a logo by ID.

    DELETE /api/settings/logos/<logo_id>/
    """
    try:
        logo = Logo.objects.get(id=logo_id)
    except Logo.DoesNotExist:
        return Response(
            {'error': 'Logo not found.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    # If this logo is the active logo, null it out
    gs = GlobalSettings.load()
    if gs.active_logo_id == logo.id:
        gs.active_logo = None
        gs.logo_enabled = False
        gs.save()

    # Delete file from disk
    if logo.file:
        try:
            file_path = logo.file.path
            if os.path.isfile(file_path):
                os.remove(file_path)
        except Exception:
            pass

    logo.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


# ═══════════════════════════════════════════════════════════════════
#  Outro Video Management
# ═══════════════════════════════════════════════════════════════════


@api_view(['GET', 'POST'])
def outros_view(request):
    """List all outro videos (GET) or upload a new one (POST).

    GET  /api/settings/outros/
    POST /api/settings/outros/  (multipart with 'file' field)
    """
    if request.method == 'GET':
        outros = OutroVideo.objects.all()
        serializer = OutroVideoSerializer(outros, many=True)
        return Response(serializer.data)

    # POST — upload
    video_file = request.FILES.get('file')
    if not video_file:
        return Response(
            {'error': 'No file provided.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Validate extension
    ext = os.path.splitext(video_file.name)[1].lower()
    allowed_exts = {'.mp4', '.mov', '.webm', '.avi', '.mkv'}
    if ext not in allowed_exts:
        return Response(
            {'error': f'Only {", ".join(sorted(allowed_exts))} files are allowed.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Validate size (100 MB max)
    if video_file.size > 100 * 1024 * 1024:
        return Response(
            {'error': 'Outro video file must be under 100 MB.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Ensure outros directory exists
    outros_dir = os.path.join(settings.MEDIA_ROOT, 'outros')
    os.makedirs(outros_dir, exist_ok=True)

    # Derive name from filename
    name = os.path.splitext(os.path.basename(video_file.name))[0]

    outro = OutroVideo.objects.create(name=name, file=video_file)
    serializer = OutroVideoSerializer(outro)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(['DELETE'])
def outro_detail_view(request, outro_id):
    """Delete an outro video by ID.

    DELETE /api/settings/outros/<outro_id>/
    """
    try:
        outro = OutroVideo.objects.get(id=outro_id)
    except OutroVideo.DoesNotExist:
        return Response(
            {'error': 'Outro video not found.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    # If this outro is the active outro, null it out
    gs = GlobalSettings.load()
    if gs.active_outro_id == outro.id:
        gs.active_outro = None
        gs.outro_enabled = False
        gs.save()

    # Delete file from disk
    if outro.file:
        try:
            file_path = outro.file.path
            if os.path.isfile(file_path):
                os.remove(file_path)
        except Exception:
            pass

    outro.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


# -- Simple local auth --

from rest_framework.decorators import api_view as _api_view


@_api_view(['POST'])
def login_view(request):
    username = request.data.get('username') or request.data.get('email') or ''
    password = request.data.get('password') or ''
    if not username or not password:
        return Response({'error': 'Username and password are required.'}, status=status.HTTP_400_BAD_REQUEST)
    return Response({'token': 'local-token', 'username': username}, status=status.HTTP_200_OK)


@_api_view(['POST'])
def logout_view(request):
    return Response({'message': 'Logged out.'}, status=status.HTTP_200_OK)


@_api_view(['GET'])
def me_view(request):
    return Response({'username': 'local-user', 'authenticated': True}, status=status.HTTP_200_OK)
