"""Settings-page Audio Mix playground.

The settings page exposes a small three-block demo project so the operator can
hear the current base level, echo and TTS voice volume before applying them to
a real project.  The demo is an ordinary :class:`~api.models.Project` with
``is_playground=True`` and three :class:`~api.models.Segment` rows; it is hidden
from the project list, gallery and account counts.

Each generation replaces the previous render in place.  TTS audio and the video
are regenerated from the three blocks every time, using the account's current
voice and Audio Mix settings.
"""

from __future__ import annotations

import logging
import os

from django.conf import settings

from .models import (
    AccountSettings,
    Project,
    Segment,
    STATUS_COMPLETED,
    STATUS_DRAFT,
    STATUS_FAILED,
    STATUS_PROCESSING,
    apply_settings_to_project,
)
from .storage_paths import media_url, project_relpath
from .tasks import _media_relative_path, get_task_manager

logger = logging.getLogger(__name__)

PLAYGROUND_BLOCK_COUNT = 3
PLAYGROUND_TITLE = 'Settings Playground'


def get_or_create_playground(account) -> Project:
    """Return the account's hidden demo project, creating the three blocks."""
    project = Project.objects.filter(
        account=account, is_playground=True
    ).first()
    if project is None:
        project = Project(
            title=PLAYGROUND_TITLE,
            section=account.section,
            account=account,
            is_playground=True,
        )
        apply_settings_to_project(project, AccountSettings.load(account))
        project.status = STATUS_DRAFT
        project.save()
        logger.info(
            'Created Audio Mix playground %s for account %s',
            project.id,
            account.id,
        )

    existing = {
        segment.sequence_index: segment
        for segment in project.segments.all()
    }
    for index in range(PLAYGROUND_BLOCK_COUNT):
        if index not in existing:
            Segment.objects.create(
                project=project,
                sequence_index=index,
                text_content='',
                image_prompt='',
            )

    return project


def ordered_blocks(project: Project):
    """Return the three playground blocks in display order."""
    return list(project.segments.order_by('sequence_index')[:PLAYGROUND_BLOCK_COUNT])


def playground_payload(project: Project) -> dict:
    """Serialise the playground state for the settings page."""
    blocks = []
    for segment in ordered_blocks(project):
        blocks.append({
            'index': segment.sequence_index,
            'text_content': segment.text_content or '',
            'image_url': segment.image_file.url if segment.image_file else None,
            'has_audio': bool(segment.audio_file),
            'audio_duration': segment.audio_duration,
        })

    output_url = media_url(project.output_path) if project.output_path else None
    return {
        'project_id': str(project.id),
        'title': project.title,
        'status': project.status,
        'output_url': output_url,
        'bgm_clip': str(project.active_bgm_id) if project.active_bgm_id else None,
        'blocks': blocks,
    }


def save_playground(project: Project, *, blocks, bgm_clip=None, update_bgm=False) -> dict:
    """Persist block texts and the selected music track.

    Changing a block's text clears its generated audio so the next demo
    generation cannot silently reuse narration for a different script.
    """
    by_index = {
        segment.sequence_index: segment
        for segment in project.segments.all()
    }
    for index, block in enumerate(blocks):
        segment = by_index.get(index)
        if segment is None:
            segment = Segment.objects.create(
                project=project,
                sequence_index=index,
                text_content='',
                image_prompt='',
            )
        text = block.get('text_content', '') if isinstance(block, dict) else block
        new_text = str(text or '')
        if segment.text_content != new_text:
            segment.text_content = new_text
            segment.audio_file = None
            segment.audio_duration = None
            segment.audio_engine = ''
        segment.save()

    if update_bgm:
        project.active_bgm = bgm_clip
        project.bgm_enabled = bool(bgm_clip)
        project.save(update_fields=['active_bgm', 'bgm_enabled'])

    return playground_payload(project)


def validate_playground(project: Project):
    """Return a human-readable reason the demo cannot be generated, or None."""
    blocks = ordered_blocks(project)
    missing_text = [
        block.sequence_index + 1 for block in blocks if not block.text_content.strip()
    ]
    missing_image = [
        block.sequence_index + 1 for block in blocks if not block.image_file
    ]
    if missing_text:
        return (
            'Add script text to every block first. Empty blocks: '
            + ', '.join(str(number) for number in missing_text)
        )
    if missing_image:
        return (
            'Upload an image for every block first. Missing images: '
            + ', '.join(str(number) for number in missing_image)
        )
    return None


def _build_tts_options(project: Project) -> dict:
    """Snapshot the project's current TTS settings for a worker thread."""
    from .views import build_tts_options  # local import avoids a cycle

    reference = project.active_voice_reference
    if reference is None:
        reference = AccountSettings.load(project.account).active_voice_reference
    return build_tts_options(project, project.tts_engine, reference)


def generate_playground_task(project_id: str, task_id: str) -> None:
    """Synthesise all three blocks, then render the demo video in place."""
    from core_engine.tts import synthesize
    from core_engine.video_renderer import render_project
    from core_engine.tts_wrapper import construct_audio_path

    manager = get_task_manager()

    def update(current, total, phase, *, percentage=None):
        kwargs = {}
        if percentage is not None:
            kwargs['percentage_override'] = percentage
        manager.update_task_progress(
            task_id,
            current=current,
            total=total,
            description=phase,
            **kwargs,
        )

    try:
        project = Project.objects.get(pk=project_id)
        blocks = ordered_blocks(project)
        total = len(blocks)
        options = _build_tts_options(project)

        # 1. Narrate every block with the current account voice settings.
        for index, segment in enumerate(blocks, start=1):
            if manager.is_cancelled(task_id):
                raise RuntimeError('Demo generation cancelled.')
            update(
                index, total, f'Generating demo narration {index}/{total}…',
                percentage=int((index - 1) / max(total, 1) * 45),
            )
            output_path = str(construct_audio_path(project.id, segment.id))
            result = synthesize(
                segment.text_content,
                output_path,
                **options,
            )
            if not result.get('success'):
                raise RuntimeError(result.get('error') or 'TTS generation failed.')
            segment.audio_file.name = project_relpath(
                project.section,
                project.id,
                'audio',
                f'{segment.id}.wav',
                account_id=project.account_id,
            )
            segment.audio_duration = result.get('duration')
            segment.audio_engine = result.get('engine', project.tts_engine)
            segment.save(update_fields=[
                'audio_file', 'audio_duration', 'audio_engine',
            ])

        # 2. Render the final demo video.  The output path is stable, so the
        #    next generation replaces the previous file.
        project.status = STATUS_PROCESSING
        project.save(update_fields=['status'])
        update(total, total, 'Rendering demo video…', percentage=50)

        def on_render_progress(current, render_total, phase):
            if manager.is_cancelled(task_id):
                raise RuntimeError('Demo generation cancelled.')
            fraction = (current / render_total) if render_total else 0.0
            update(
                current,
                render_total,
                phase,
                percentage=50 + int(min(max(fraction, 0.0), 1.0) * 50),
            )

        result = render_project(project_id, on_progress=on_render_progress)

        project = Project.objects.get(pk=project_id)
        project.status = STATUS_COMPLETED
        project.output_path = _media_relative_path(result.get('output_path', ''))
        project.save(update_fields=['status', 'output_path'])
        update(
            total, total, 'Demo ready',
            percentage=100,
        )
        logger.info('Audio Mix demo rendered for project %s', project_id)
    except Exception as exc:
        logger.exception('Audio Mix demo failed for project %s', project_id)
        try:
            project = Project.objects.get(pk=project_id)
            project.status = STATUS_FAILED
            project.save(update_fields=['status'])
        except Exception:
            pass
        raise exc


def start_generation(project: Project, *, bgm_clip=None) -> str:
    """Apply the current account settings and queue a demo generation."""
    account_settings = AccountSettings.load(project.account)
    apply_settings_to_project(project, account_settings)
    if bgm_clip is not None:
        project.active_bgm = bgm_clip
        project.bgm_enabled = bool(bgm_clip)
    project.status = STATUS_PROCESSING
    project.save()

    task_id = f'playground_{project.id}'
    get_task_manager().submit_task(
        lambda: generate_playground_task(str(project.id), task_id),
        task_id=task_id,
    )
    return task_id


def remove_playground_output(project: Project) -> None:
    """Delete the previous demo video (used when its file is being replaced)."""
    if not project.output_path:
        return
    try:
        path = os.path.join(settings.MEDIA_ROOT, str(project.output_path))
        if os.path.isfile(path):
            os.remove(path)
    except OSError:
        logger.debug('Could not remove old demo output', exc_info=True)
