"""Settings-page Audio Mix playground.

The settings page exposes a small three-block demo project so the operator can
hear the current base level, echo and TTS voice volume before applying them to
a real project.  The demo is an ordinary :class:`~api.models.Project` with
``is_playground=True`` and three :class:`~api.models.Segment` rows; it is hidden
from the project list, gallery and account counts.

Unlike a real project, the playground separates the two halves of the render:

1. **Base generation** narrates the three blocks and renders a video with no
   subtitles and no background music.  The narration WAV is kept next to the
   base video.
2. **Remix** applies the selected music track and the current Audio Mix values
   to that existing base video.  It only re-encodes the audio track, so the
   video does not change until the operator explicitly regenerates it.

This makes it cheap to tune the background-music settings repeatedly.  The
same account-level settings are still written to every real project by the
``/api/settings/`` endpoint.
"""

from __future__ import annotations

import hashlib
import logging
import os

from django.conf import settings

from .models import (
    BGMClip,
    BGM_SOURCE_GENERATED,
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

PLAYGROUND_JOB_BASE = 'BASE'
PLAYGROUND_JOB_MIX = 'MIX'

_BASE_FILENAME = 'playground_base.mp4'
_NARRATION_FILENAME = 'playground_narration.wav'
_ACTIVE_TASK_STATUSES = ('PENDING', 'PROCESSING')


class PlaygroundCancelled(RuntimeError):
    """Raised inside a playground worker when the operator stops the job."""


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

    _recover_stale_job(project)
    return project


def ordered_blocks(project: Project):
    """Return the three playground blocks in display order."""
    return list(project.segments.order_by('sequence_index')[:PLAYGROUND_BLOCK_COUNT])


def playground_task_id(project: Project) -> str:
    """Return the stable task id used for every playground background job."""
    return f'playground_{project.id}'


def _media_path(relative_path: str | None) -> str | None:
    """Resolve a stored media-relative path to an absolute file path."""
    if not relative_path:
        return None
    return os.path.join(settings.MEDIA_ROOT, str(relative_path))


def base_video_relpath(project: Project) -> str:
    return project_relpath(
        project.section,
        project.id,
        'output',
        _BASE_FILENAME,
        account_id=project.account_id,
    )


def narration_relpath(project: Project) -> str:
    return project_relpath(
        project.section,
        project.id,
        'output',
        _NARRATION_FILENAME,
        account_id=project.account_id,
    )


def _final_output_path(project: Project) -> str:
    from core_engine.render_utils import get_output_path

    return get_output_path(str(project.id))


def _has_files(project: Project) -> tuple[bool, bool]:
    base_path = _media_path(project.playground_base_video)
    narration_path = _media_path(project.playground_narration_audio)
    return (
        bool(base_path and os.path.isfile(base_path)),
        bool(narration_path and os.path.isfile(narration_path)),
    )


def _has_output(project: Project) -> bool:
    output_path = _media_path(project.output_path)
    return bool(output_path and os.path.isfile(output_path))


def _media_version(relative_path: str | None) -> int | None:
    """Return a cache-busting version for a media file (its mtime)."""
    path = _media_path(relative_path)
    if not path or not os.path.isfile(path):
        return None
    try:
        # Milliseconds keep repeated re-mixes inside the same second distinct.
        return int(os.path.getmtime(path) * 1000)
    except OSError:
        return None


def blocks_fingerprint(project: Project) -> str:
    """Fingerprint the narration the generated music has to match.

    MusicGen is driven by the block text and the measured narration duration.
    Any change to either one means the old soundtrack no longer lines up with
    the video, so it must be generated again instead of silently re-used.
    """
    parts = []
    for segment in ordered_blocks(project):
        parts.append(
            '|'.join((
                str(segment.sequence_index),
                (segment.text_content or '').strip(),
                f'{float(segment.audio_duration or 0.0):.3f}',
            ))
        )
    return hashlib.sha256('\n'.join(parts).encode('utf-8')).hexdigest()[:16]


def _clip_file_exists(clip: BGMClip | None) -> bool:
    if clip is None or not clip.file:
        return False
    try:
        return os.path.isfile(clip.file.path)
    except (ValueError, NotImplementedError, OSError):
        return False


def find_generated_music(
    project: Project, fingerprint: str | None = None
) -> BGMClip | None:
    """Return a MusicGen soundtrack that matches the current demo, if any."""
    fingerprint = fingerprint or blocks_fingerprint(project)
    candidates = []
    if project.active_bgm_id:
        candidates.append(project.active_bgm)
    candidates.extend(
        BGMClip.objects.filter(
            project=project, source=BGM_SOURCE_GENERATED
        ).order_by('-created_at')
    )

    seen: set = set()
    for clip in candidates:
        if clip is None or clip.pk in seen:
            continue
        seen.add(clip.pk)
        if clip.project_id != project.id:
            continue
        if clip.source != BGM_SOURCE_GENERATED:
            continue
        metadata = clip.generation_metadata or {}
        if metadata.get('fingerprint') != fingerprint:
            continue
        if not _clip_file_exists(clip):
            continue
        return clip
    return None


def playground_music_state(project: Project) -> dict:
    """Describe what the Apply Background Music action will do next."""
    fingerprint = blocks_fingerprint(project)
    active = project.active_bgm
    source = 'none'
    name = None
    if active is not None:
        name = active.name
        if (
            active.source == BGM_SOURCE_GENERATED
            and active.project_id == project.id
        ):
            source = 'generated'
        else:
            source = 'library'

    reusable = find_generated_music(project, fingerprint)
    has_generated = BGMClip.objects.filter(
        project=project, source=BGM_SOURCE_GENERATED
    ).exists()
    return {
        'music_source': source,
        'music_clip_name': name,
        'generated_music_ready': reusable is not None,
        'generated_music_stale': bool(has_generated and reusable is None),
        'music_fingerprint': fingerprint,
    }


def has_reusable_generated_music(project: Project) -> bool:
    """True when Apply Background Music can skip a new MusicGen run."""
    return find_generated_music(project) is not None


def _task_state(project: Project) -> dict | None:
    state = get_task_manager().get_task_status(playground_task_id(project))
    if state and state.get('status') in _ACTIVE_TASK_STATUSES:
        return state
    return None


def _recover_stale_job(project: Project) -> None:
    """Clear a PROCESSING flag whose worker no longer exists.

    Reloading the settings page must never cancel a running job, but a server
    restart (or a crashed worker) can leave the project stuck in PROCESSING.
    """
    if project.status != STATUS_PROCESSING:
        return
    if _task_state(project) is not None:
        return

    project.playground_job = ''
    project.status = STATUS_COMPLETED if _has_output(project) else STATUS_DRAFT
    project.save(update_fields=['playground_job', 'status'])
    logger.info('Recovered stale playground job for project %s', project.id)


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

    base_exists, narration_exists = _has_files(project)
    audio_ready = all(block['has_audio'] for block in blocks)
    output_url = media_url(project.output_path) if project.output_path else None
    task_state = _task_state(project)
    progress = (task_state or {}).get('progress') or {}
    music = playground_music_state(project)

    return {
        'project_id': str(project.id),
        'title': project.title,
        'status': project.status,
        'job': project.playground_job or '',
        'output_url': output_url,
        'output_version': _media_version(project.output_path),
        'base_video_url': (
            media_url(project.playground_base_video) if base_exists else None
        ),
        'base_video_version': _media_version(project.playground_base_video),
        'has_base_video': base_exists,
        'can_remix': base_exists and narration_exists and audio_ready,
        'bgm_clip': str(project.active_bgm_id) if project.active_bgm_id else None,
        **music,
        'blocks': blocks,
        'task_status': (task_state or {}).get('status') if task_state else None,
        'progress': progress.get('percentage'),
        'progress_description': progress.get('description'),
        'cancel_requested': bool(
            (task_state or {}).get('cancel_requested', False)
        ),
    }


def save_playground(project: Project, *, blocks, bgm_clip=None, update_bgm=False) -> dict:
    """Persist block texts and the selected music track.

    Changing a block's text clears its generated audio so the next demo
    generation cannot silently reuse narration for a different script.  The
    existing base video stays on disk until the operator regenerates it, but
    the playground reports that it can no longer be re-mixed.
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


def validate_playground_remix(project: Project):
    """Return why the existing base video cannot be re-mixed, or None."""
    base_exists, narration_exists = _has_files(project)
    if not base_exists or not narration_exists:
        return (
            'Generate the demo video first. Background music is applied to '
            'that video without re-running TTS or the video render.'
        )
    blocks = ordered_blocks(project)
    if any(
        not block.text_content.strip()
        or not block.image_file
        or not block.audio_file
        for block in blocks
    ):
        return (
            'The demo blocks changed. Generate the demo video again before '
            'applying background music.'
        )
    return None


def _build_tts_options(project: Project) -> dict:
    """Snapshot the project's current TTS settings for a worker thread."""
    from .views import build_tts_options  # local import avoids a cycle

    reference = project.active_voice_reference
    if reference is None:
        reference = AccountSettings.load(project.account).active_voice_reference
    return build_tts_options(project, project.tts_engine, reference)


def _check_cancelled(manager, task_id: str) -> None:
    if manager.is_cancelled(task_id):
        raise PlaygroundCancelled('Demo generation cancelled.')


def _update(manager, task_id: str, current: int, total: int, phase: str, percentage: int):
    manager.update_task_progress(
        task_id,
        current=current,
        total=total,
        description=phase,
        percentage_override=max(0, min(100, int(percentage))),
    )


def _render_base_video(project: Project, manager, task_id: str) -> dict:
    """Run TTS for every block, then render the un-mixed base video."""
    from core_engine.tts import synthesize
    from core_engine.tts_script import prepare_tts_text
    from core_engine import subtitle_sync
    from core_engine.tts_wrapper import construct_audio_path
    from core_engine.video_renderer import render_project

    blocks = ordered_blocks(project)
    total = len(blocks)
    options = _build_tts_options(project)

    # 1. Narrate every block with the current account voice settings.
    for index, segment in enumerate(blocks, start=1):
        _check_cancelled(manager, task_id)
        _update(
            manager,
            task_id,
            index,
            total,
            f'Generating demo narration {index}/{total}…',
            int((index - 1) / max(total, 1) * 35),
        )
        output_path = str(construct_audio_path(project.id, segment.id))
        result = synthesize(
            prepare_tts_text(segment.tts_text or segment.text_content),
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
        segment.audio_timings = subtitle_sync.build_audio_timings(
            segment.text_content,
            output_path,
            result.get('duration') or 0,
        )
        segment.save(update_fields=[
            'audio_file', 'audio_duration', 'audio_engine', 'audio_timings',
        ])

    _check_cancelled(manager, task_id)

    # 2. Render a subtitle-free, music-free base video and keep its narration.
    base_rel = base_video_relpath(project)
    narration_rel = narration_relpath(project)
    base_path = _media_path(base_rel)
    narration_path = _media_path(narration_rel)
    temp_base = f'{base_path}.tmp.mp4'
    temp_narration = f'{narration_path}.tmp.wav'

    def on_render_progress(current, render_total, phase):
        _check_cancelled(manager, task_id)
        fraction = (current / render_total) if render_total else 0.0
        _update(
            manager,
            task_id,
            current,
            render_total,
            phase,
            35 + int(min(max(fraction, 0.0), 1.0) * 45),
        )

    try:
        result = render_project(
            str(project.id),
            on_progress=on_render_progress,
            output_path=temp_base,
            include_bgm=False,
            include_outro=False,
            subtitles_override=False,
            narration_output_path=temp_narration,
        )
        os.replace(temp_base, base_path)
        os.replace(temp_narration, narration_path)
    finally:
        for temporary in (temp_base, temp_narration):
            try:
                if os.path.isfile(temporary):
                    os.remove(temporary)
            except OSError:
                pass

    project.playground_base_video = base_rel
    project.playground_narration_audio = narration_rel
    project.save(update_fields=[
        'playground_base_video',
        'playground_narration_audio',
    ])
    logger.info('Playground base video rendered for project %s', project.id)
    return result


def _ensure_generated_music(
    project: Project,
    manager,
    task_id: str,
    *,
    regenerate: bool = False,
    progress_start: int = 0,
    progress_end: int = 80,
) -> BGMClip:
    """Generate (or re-use) a MusicGen soundtrack for the demo blocks.

    The soundtrack is tied to the current block text and measured narration
    durations.  Pressing Apply again re-uses the matching clip so tuning the
    mix sliders stays cheap; ``regenerate=True`` composes a brand-new track.
    """
    from . import music_service

    fingerprint = blocks_fingerprint(project)
    if not regenerate:
        existing = find_generated_music(project, fingerprint)
        if existing is not None:
            if project.active_bgm_id != existing.id or not project.bgm_enabled:
                project.active_bgm = existing
                project.bgm_enabled = True
                project.save(update_fields=['active_bgm', 'bgm_enabled'])
            _update(
                manager,
                task_id,
                1,
                1,
                'Using the generated soundtrack…',
                progress_end,
            )
            logger.info(
                'Re-using generated soundtrack %s for playground %s',
                existing.id,
                project.id,
            )
            return existing

    _check_cancelled(manager, task_id)
    _update(
        manager,
        task_id,
        0,
        1,
        'Composing background music with MusicGen…',
        progress_start,
    )

    segments = music_service.segments_from_project(project)
    try:
        result = music_service.generate_soundtrack_task(
            task_id=task_id,
            account_id=str(project.account_id),
            section=project.section,
            segments=segments,
            project_id=str(project.id),
            name=f'{project.title} — Generated Soundtrack',
            plan_options={
                'style': 'instrumental cinematic documentary score',
            },
            attach_to_project=True,
            progress_start=progress_start,
            progress_end=progress_end,
        )
    except music_service.SoundtrackCancelled as exc:
        # Normalise the music service's cancellation so the playground worker
        # restores the previous demo instead of marking it FAILED.
        raise PlaygroundCancelled(str(exc)) from exc
    clip = BGMClip.objects.filter(pk=result.get('clip_id')).first()
    if clip is None:
        raise RuntimeError('MusicGen did not return a soundtrack clip.')

    metadata = dict(clip.generation_metadata or {})
    metadata['fingerprint'] = fingerprint
    metadata['playground'] = True
    clip.generation_metadata = metadata
    clip.save(update_fields=['generation_metadata'])
    logger.info(
        'Generated soundtrack %s for playground %s (%.2fs)',
        clip.id,
        project.id,
        float(result.get('duration') or 0.0),
    )
    return clip


def _apply_mix(
    project: Project,
    manager,
    task_id: str,
    *,
    start: int = 80,
    generate_music: bool = False,
    regenerate_music: bool = False,
) -> dict:
    """Apply the background music and Audio Mix values to the base video.

    With ``generate_music=True`` the MusicGen model composes a new soundtrack
    for the demo first, so pressing Apply Background Music works without the
    operator having to put a track in the BGM Library beforehand.
    """
    from core_engine import render_utils
    from core_engine.music_generator import (
        apply_narration_gain,
        mix_background_music,
    )

    _check_cancelled(manager, task_id)

    base_exists, narration_exists = _has_files(project)
    if not base_exists or not narration_exists:
        raise RuntimeError(
            'The demo base video is missing. Generate the demo video again.'
        )

    progress = start
    if generate_music:
        music_end = start + int((100 - start) * 0.75)
        _ensure_generated_music(
            project,
            manager,
            task_id,
            regenerate=regenerate_music,
            progress_start=start,
            progress_end=music_end,
        )
        # The music task attaches the generated clip to the project row.
        project.refresh_from_db()
        progress = music_end
        _check_cancelled(manager, task_id)
    _update(manager, task_id, 1, 1, 'Applying Audio Mix…', progress)

    base_path = _media_path(project.playground_base_video)
    narration_path = _media_path(project.playground_narration_audio)
    output_path = _final_output_path(project)
    temp_audio = f'{output_path}.mix.wav'
    temp_video = f'{output_path}.mix.mp4'

    bgm_path = None
    if project.bgm_enabled and project.active_bgm_id:
        clip = project.active_bgm
        if clip is not None and clip.file:
            try:
                candidate = clip.file.path
                if os.path.isfile(candidate):
                    bgm_path = candidate
            except (ValueError, NotImplementedError):
                bgm_path = None
    if project.bgm_enabled and not bgm_path:
        logger.warning(
            'Playground %s has BGM enabled but no playable track.', project.id
        )
    if generate_music and not bgm_path:
        raise RuntimeError(
            'MusicGen finished but its soundtrack file could not be opened.'
        )

    try:
        if bgm_path:
            mix_result = mix_background_music(
                narration_path,
                bgm_path,
                temp_audio,
                music_gain_db=project.bgm_gain_db,
                ducking_db=project.bgm_ducking_db,
                echo_percent=project.bgm_echo_percent,
                narration_gain_db=project.tts_gain_db,
            )
            duration = mix_result['duration']
        else:
            gain_result = apply_narration_gain(
                narration_path,
                temp_audio,
                project.tts_gain_db,
            )
            duration = gain_result['duration']

        _check_cancelled(manager, task_id)
        _update(
            manager,
            task_id,
            1,
            1,
            'Muxing demo video…',
            min(99, progress + 10),
        )
        render_utils.mux_audio_into_video(base_path, temp_audio, temp_video)
        os.replace(temp_video, output_path)

        project.output_path = _media_relative_path(output_path)
        project.status = STATUS_COMPLETED
        project.playground_job = ''
        project.save(update_fields=[
            'output_path', 'status', 'playground_job',
        ])
        _update(manager, task_id, 1, 1, 'Demo ready', 100)
        logger.info(
            'Playground re-mixed for project %s (%s, %.2fs)',
            project.id,
            os.path.basename(bgm_path) if bgm_path else 'narration only',
            duration,
        )
        return {
            'output_path': output_path,
            'duration': duration,
            'bgm': bool(bgm_path),
            'music_generated': bool(
                generate_music and bgm_path
            ),
        }
    finally:
        for temporary in (temp_audio, temp_video):
            try:
                if os.path.isfile(temporary):
                    os.remove(temporary)
            except OSError:
                pass


def _finish_interrupted(project_id: str) -> None:
    """Restore a sensible status after a cancelled playground job."""
    try:
        project = Project.objects.get(pk=project_id)
        project.playground_job = ''
        project.status = STATUS_COMPLETED if _has_output(project) else STATUS_DRAFT
        project.save(update_fields=['playground_job', 'status'])
    except Exception:
        logger.debug('Could not restore playground status', exc_info=True)


def generate_playground_task(
    project_id: str,
    task_id: str,
    *,
    generate_music: bool = False,
    regenerate_music: bool = False,
) -> None:
    """Narrate all three blocks, render the base video, then apply the mix."""
    manager = get_task_manager()

    try:
        project = Project.objects.get(pk=project_id)
        _check_cancelled(manager, task_id)
        _render_base_video(project, manager, task_id)

        project.refresh_from_db()
        project.playground_job = PLAYGROUND_JOB_MIX
        project.save(update_fields=['playground_job'])
        _apply_mix(
            project,
            manager,
            task_id,
            start=80,
            generate_music=generate_music,
            regenerate_music=regenerate_music,
        )
    except PlaygroundCancelled:
        logger.info('Playground generation cancelled for project %s', project_id)
        _finish_interrupted(project_id)
        raise
    except Exception as exc:
        logger.exception('Audio Mix demo failed for project %s', project_id)
        try:
            project = Project.objects.get(pk=project_id)
            project.status = STATUS_FAILED
            project.playground_job = ''
            project.save(update_fields=['status', 'playground_job'])
        except Exception:
            pass
        raise exc


def remix_playground_task(
    project_id: str,
    task_id: str,
    *,
    generate_music: bool = False,
    regenerate_music: bool = False,
) -> None:
    """Apply the current Audio Mix values to the existing base video."""
    manager = get_task_manager()

    try:
        project = Project.objects.get(pk=project_id)
        _apply_mix(
            project,
            manager,
            task_id,
            start=0,
            generate_music=generate_music,
            regenerate_music=regenerate_music,
        )
    except PlaygroundCancelled:
        logger.info('Playground remix cancelled for project %s', project_id)
        _finish_interrupted(project_id)
        raise
    except Exception as exc:
        logger.exception('Audio Mix re-mix failed for project %s', project_id)
        try:
            project = Project.objects.get(pk=project_id)
            project.status = STATUS_FAILED
            project.playground_job = ''
            project.save(update_fields=['status', 'playground_job'])
        except Exception:
            pass
        raise exc


def _prepare_project(project: Project) -> None:
    """Copy account settings onto the playground row before a job starts."""
    apply_settings_to_project(project, AccountSettings.load(project.account))


def start_generation(
    project: Project,
    *,
    bgm_clip=None,
    generate_music: bool = False,
    regenerate_music: bool = False,
) -> str:
    """Apply the current account settings and queue a full demo generation."""
    _prepare_project(project)
    if generate_music:
        project.bgm_enabled = True
    else:
        project.active_bgm = bgm_clip
        project.bgm_enabled = bool(bgm_clip)
    project.status = STATUS_PROCESSING
    project.playground_job = PLAYGROUND_JOB_BASE
    project.save()

    task_id = playground_task_id(project)
    get_task_manager().submit_task(
        lambda: generate_playground_task(
            str(project.id),
            task_id,
            generate_music=generate_music,
            regenerate_music=regenerate_music,
        ),
        task_id=task_id,
    )
    return task_id


def start_remix(
    project: Project,
    *,
    bgm_clip=None,
    generate_music: bool = False,
    regenerate_music: bool = False,
) -> str:
    """Queue a background-music re-mix of the existing base video."""
    _prepare_project(project)
    if generate_music:
        project.bgm_enabled = True
    else:
        project.active_bgm = bgm_clip
        project.bgm_enabled = bool(bgm_clip)
    project.status = STATUS_PROCESSING
    project.playground_job = PLAYGROUND_JOB_MIX
    project.save()

    task_id = playground_task_id(project)
    get_task_manager().submit_task(
        lambda: remix_playground_task(
            str(project.id),
            task_id,
            generate_music=generate_music,
            regenerate_music=regenerate_music,
        ),
        task_id=task_id,
    )
    return task_id


def cancel_generation(project: Project) -> bool:
    """Request cancellation of the project's running playground task."""
    return get_task_manager().cancel_task(playground_task_id(project))


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
