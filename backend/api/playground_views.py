"""API endpoints for the Settings-page Audio Mix playground."""

from __future__ import annotations

import logging
import os
import uuid

from django.core.files.storage import default_storage
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import BGMClip, STATUS_PROCESSING
from .playground_service import (
    PLAYGROUND_BLOCK_COUNT,
    cancel_generation,
    get_or_create_playground,
    has_reusable_generated_music,
    ordered_blocks,
    playground_payload,
    playground_task_id,
    save_playground,
    start_generation,
    start_remix,
    validate_playground,
    validate_playground_remix,
)
from .storage_paths import project_relpath
from .tasks import get_task_manager
from .validators import validate_image_upload
from .views import get_requested_account

logger = logging.getLogger(__name__)


def _require_account(request):
    account = get_requested_account(request)
    if account is None:
        return None, Response(
            {'error': 'Select an account before using the Audio Mix playground.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return account, None


def _resolve_bgm(request, account):
    raw = request.data.get('bgm_clip')
    if raw in (None, '', 'none'):
        return None
    try:
        clip = BGMClip.objects.get(pk=raw)
    except (BGMClip.DoesNotExist, ValueError):
        return 'invalid'
    if clip.section != account.section:
        return 'invalid'
    if clip.account_id != account.id and not clip.is_shared:
        return 'invalid'
    return clip


def _as_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ('1', 'true', 'on', 'yes')


def _requested_music(request, account, project):
    """Resolve the requested music source for generate/apply.

    Returns ``(music_source, clip, generate_music, regenerate_music, error)``.
    Old clients that only send ``bgm_clip`` keep the previous behaviour: use
    that library track (or the currently attached one) and never start
    MusicGen implicitly.
    """
    raw = request.data.get('music_source')
    if raw is None:
        update_bgm = 'bgm_clip' in request.data
        clip = _resolve_bgm(request, account) if update_bgm else None
        if clip == 'invalid':
            return None, None, False, False, Response(
                {
                    'error': (
                        'Select a music track from this account or a shared '
                        'track.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if update_bgm:
            source = 'library' if clip is not None else 'none'
        else:
            source = 'library' if project.active_bgm_id else 'none'
        return source, clip, False, False, None

    source = str(raw or '').strip().lower() or 'none'
    if source not in ('generated', 'library', 'none'):
        return None, None, False, False, Response(
            {'error': "music_source must be 'generated', 'library' or 'none'."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    clip = None
    if source == 'library':
        clip = _resolve_bgm(request, account)
        if clip == 'invalid':
            return None, None, False, False, Response(
                {
                    'error': (
                        'Select a music track from this account or a shared '
                        'track.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

    generate_music = source == 'generated'
    regenerate_music = generate_music and _as_bool(
        request.data.get('regenerate_music')
    )
    return source, clip, generate_music, regenerate_music, None


def _music_engine_error(project, *, generate_music, regenerate_music):
    """Reject a generation request early when MusicGen cannot run."""
    if not generate_music:
        return None
    if not regenerate_music and has_reusable_generated_music(project):
        return None

    from core_engine import music_generator

    engine = music_generator.engine_status()
    if engine.get('available'):
        return None
    return Response(
        {
            'error': (
                engine.get('reason')
                or 'MusicGen is not available in this environment.'
            ),
            'engine': engine,
        },
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


def _active_job(project):
    """Return the running task state for *project*, or None."""
    task_id = playground_task_id(project)
    state = get_task_manager().get_task_status(task_id)
    if state and state.get('status') in ('PENDING', 'PROCESSING'):
        return state
    return None


def _busy_response(project, task_id):
    return Response(
        {
            'error': 'The demo is already generating.',
            'task_id': task_id,
            'project_id': str(project.id),
            'status': project.status,
        },
        status=status.HTTP_409_CONFLICT,
    )


def _reject_if_busy(project):
    task_id = playground_task_id(project)
    state = _active_job(project)
    if state is not None or project.status == STATUS_PROCESSING:
        return _busy_response(project, task_id)
    return None


@api_view(['GET', 'PUT', 'PATCH'])
def playground_view(request):
    """Read or save the three-block Audio Mix demo project."""
    account, error = _require_account(request)
    if error is not None:
        return error

    project = get_or_create_playground(account)
    if request.method == 'GET':
        return Response(playground_payload(project))

    blocks = request.data.get('blocks')
    if blocks is not None:
        if not isinstance(blocks, list) or len(blocks) != PLAYGROUND_BLOCK_COUNT:
            return Response(
                {
                    'error': (
                        f'The playground needs exactly '
                        f'{PLAYGROUND_BLOCK_COUNT} blocks.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
    else:
        blocks = [segment.text_content for segment in ordered_blocks(project)]

    update_bgm = 'bgm_clip' in request.data
    clip = _resolve_bgm(request, account) if update_bgm else None
    if clip == 'invalid':
        return Response(
            {'error': 'Select a music track from this account or a shared track.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    payload = save_playground(
        project,
        blocks=blocks,
        bgm_clip=clip,
        update_bgm=update_bgm,
    )
    return Response(payload)


@api_view(['POST', 'DELETE'])
def playground_block_image_view(request, index: int):
    """Upload or remove one playground block's image."""
    account, error = _require_account(request)
    if error is not None:
        return error

    if index < 0 or index >= PLAYGROUND_BLOCK_COUNT:
        return Response(
            {'error': 'Playground block index is out of range.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    project = get_or_create_playground(account)
    segment = ordered_blocks(project)[index]

    if request.method == 'DELETE':
        if segment.image_file:
            try:
                if os.path.isfile(segment.image_file.path):
                    os.remove(segment.image_file.path)
            except (FileNotFoundError, ValueError, NotImplementedError):
                pass
            segment.image_file = None
        # Changing an image invalidates the cached demo video.
        segment.audio_file = None
        segment.audio_duration = None
        segment.audio_engine = ''
        segment.save(update_fields=[
            'image_file', 'audio_file', 'audio_duration', 'audio_engine',
        ])
        return Response({
            'index': index,
            'image_url': None,
        })

    upload = request.FILES.get('image')
    if upload is None:
        return Response(
            {'error': 'No image file provided.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    validate_image_upload(upload)

    if segment.image_file:
        try:
            old_path = segment.image_file.path
            if os.path.isfile(old_path):
                os.remove(old_path)
        except (ValueError, NotImplementedError):
            pass

    # Keep the on-disk filename ASCII-only: OpenCV (used by the Ken Burns
    # renderer) cannot open Unicode paths on Windows.  The renderer also has a
    # Pillow fallback, but a stable generated name avoids the problem entirely.
    extension = os.path.splitext(upload.name or '')[1].lower() or '.img'
    relative = project_relpath(
        project.section,
        project.id,
        'images',
        f'playground_{index}_{uuid.uuid4().hex}{extension}',
        account_id=project.account_id,
    )
    saved_path = default_storage.save(relative, upload)
    segment.image_file.name = saved_path
    # The cached base video was rendered with the old image; clear narration
    # so the UI asks for a fresh base render before re-mixing.
    segment.audio_file = None
    segment.audio_duration = None
    segment.audio_engine = ''
    segment.save(update_fields=[
        'image_file', 'audio_file', 'audio_duration', 'audio_engine',
    ])

    return Response({
        'index': index,
        'image_url': segment.image_file.url,
    })


@api_view(['POST'])
def playground_generate_view(request):
    """Generate (or regenerate) the playground TTS + base video."""
    account, error = _require_account(request)
    if error is not None:
        return error

    project = get_or_create_playground(account)
    busy = _reject_if_busy(project)
    if busy is not None:
        return busy

    (
        _source,
        clip,
        generate_music,
        regenerate_music,
        music_error,
    ) = _requested_music(request, account, project)
    if music_error is not None:
        return music_error

    validation_error = validate_playground(project)
    if validation_error:
        return Response(
            {'error': validation_error},
            status=status.HTTP_400_BAD_REQUEST,
        )

    engine_error = _music_engine_error(
        project,
        generate_music=generate_music,
        regenerate_music=regenerate_music,
    )
    if engine_error is not None:
        return engine_error

    if request.data.get('music_source') is None:
        start_clip = clip if 'bgm_clip' in request.data else project.active_bgm
    else:
        start_clip = clip

    task_id = start_generation(
        project,
        bgm_clip=start_clip,
        generate_music=generate_music,
        regenerate_music=regenerate_music,
    )
    return Response(
        {
            'task_id': task_id,
            'project_id': str(project.id),
            'status': project.status,
            'message': (
                'Demo generation started in the background. You can reload '
                'this page without interrupting it.'
            ),
        },
        status=status.HTTP_202_ACCEPTED,
    )


@api_view(['POST'])
def playground_apply_view(request):
    """Apply the selected background music to the existing demo base video."""
    account, error = _require_account(request)
    if error is not None:
        return error

    project = get_or_create_playground(account)
    busy = _reject_if_busy(project)
    if busy is not None:
        return busy

    (
        source,
        clip,
        generate_music,
        regenerate_music,
        music_error,
    ) = _requested_music(request, account, project)
    if music_error is not None:
        return music_error

    validation_error = validate_playground_remix(project)
    if validation_error:
        return Response(
            {'error': validation_error},
            status=status.HTTP_400_BAD_REQUEST,
        )

    engine_error = _music_engine_error(
        project,
        generate_music=generate_music,
        regenerate_music=regenerate_music,
    )
    if engine_error is not None:
        return engine_error

    if request.data.get('music_source') is None:
        start_clip = clip if 'bgm_clip' in request.data else project.active_bgm
    else:
        start_clip = clip

    task_id = start_remix(
        project,
        bgm_clip=start_clip,
        generate_music=generate_music,
        regenerate_music=regenerate_music,
    )
    message = (
        'Composing a MusicGen soundtrack and applying it to the demo video.'
        if generate_music
        else 'Applying background music to the existing demo video.'
    )
    return Response(
        {
            'task_id': task_id,
            'project_id': str(project.id),
            'status': project.status,
            'music_source': source,
            'generate_music': generate_music,
            'message': message,
        },
        status=status.HTTP_202_ACCEPTED,
    )


@api_view(['POST'])
def playground_cancel_view(request):
    """Stop the running playground job without discarding its base video."""
    account, error = _require_account(request)
    if error is not None:
        return error

    project = get_or_create_playground(account)
    job = _active_job(project)
    if job is None and project.status != STATUS_PROCESSING:
        return Response(
            {
                'error': 'No demo job is running.',
                'project_id': str(project.id),
            },
            status=status.HTTP_409_CONFLICT,
        )

    cancel_generation(project)
    job = _active_job(project)
    payload = playground_payload(project)
    payload['message'] = 'Stopping the demo job…'
    payload['cancel_requested'] = True
    return Response(payload, status=status.HTTP_202_ACCEPTED)
