"""API endpoints for the Settings-page Audio Mix playground."""

from __future__ import annotations

import logging
import os

from django.core.files.storage import default_storage
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import BGMClip, STATUS_PROCESSING
from .playground_service import (
    PLAYGROUND_BLOCK_COUNT,
    get_or_create_playground,
    ordered_blocks,
    playground_payload,
    save_playground,
    start_generation,
    validate_playground,
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
            segment.save(update_fields=['image_file'])
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

    relative = project_relpath(
        project.section,
        project.id,
        'images',
        f'playground_{index}_{upload.name}',
        account_id=project.account_id,
    )
    saved_path = default_storage.save(relative, upload)
    segment.image_file.name = saved_path
    segment.save(update_fields=['image_file'])

    return Response({
        'index': index,
        'image_url': segment.image_file.url,
    })


@api_view(['POST'])
def playground_generate_view(request):
    """Generate (or replace) the playground demo video."""
    account, error = _require_account(request)
    if error is not None:
        return error

    project = get_or_create_playground(account)
    if project.status == STATUS_PROCESSING:
        task_id = f'playground_{project.id}'
        state = get_task_manager().get_task_status(task_id)
        if state and state.get('status') in ('PENDING', 'PROCESSING'):
            return Response(
                {
                    'error': 'The demo is already generating.',
                    'task_id': task_id,
                    'project_id': str(project.id),
                    'status': project.status,
                },
                status=status.HTTP_409_CONFLICT,
            )

    update_bgm = 'bgm_clip' in request.data
    clip = _resolve_bgm(request, account) if update_bgm else None
    if clip == 'invalid':
        return Response(
            {'error': 'Select a music track from this account or a shared track.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    validation_error = validate_playground(project)
    if validation_error:
        return Response(
            {'error': validation_error},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if update_bgm:
        project.active_bgm = clip
        project.bgm_enabled = bool(clip)
        project.save(update_fields=['active_bgm', 'bgm_enabled'])

    task_id = start_generation(project, bgm_clip=clip if update_bgm else project.active_bgm)
    return Response(
        {
            'task_id': task_id,
            'project_id': str(project.id),
            'status': project.status,
            'message': 'Demo generation started. The next render replaces this one.',
        },
        status=status.HTTP_202_ACCEPTED,
    )
