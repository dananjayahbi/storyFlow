"""Background task glue for MusicGen soundtrack generation.

Keeping the ORM/background-task code out of :mod:`core_engine` lets the music
maths stay importable (and unit-testable) without Django.  This module owns:

* converting a Project or a raw script payload into measured segments,
* running the (single) MusicGen job through the existing TaskManager,
* writing the result into the account's BGM Library as a generated clip,
* optionally attaching the clip to the project for the next render.
"""

from __future__ import annotations

import logging
import os
import tempfile
import threading
import uuid

from core_engine import audio_convert, music_generator

logger = logging.getLogger(__name__)

# Belt-and-braces guard on top of TaskManager(max_workers=1).  The 6 GB
# target GPU must never have two MusicGen sessions resident at once.
_GENERATION_LOCK = threading.Lock()


class SoundtrackCancelled(RuntimeError):
    """Raised when the operator cancels an in-flight generation."""


def segments_from_project(project):
    """Return measured :class:`MusicSegment` objects for *project*.

    The script JSON does not hardcode durations; the duration of each TTS
    ``segment_i`` file is authoritative.  Segments without audio are rejected
    because MusicGen output must line up with the narration timeline.
    """
    raw = []
    missing = []
    for index, segment in enumerate(
        project.segments.order_by('sequence_index')
    ):
        duration = segment.audio_duration
        if duration is None and segment.audio_file:
            try:
                duration = audio_convert.probe_duration(
                    segment.audio_file.path
                )
            except Exception:
                duration = None
        if not duration or duration <= 0:
            missing.append(index + 1)
        raw.append({
            'text_content': segment.text_content or '',
            'image_prompt': segment.image_prompt or '',
            'duration': duration or 0.0,
        })

    if not raw:
        raise music_generator.MusicGenerationError(
            'The project has no segments to score.'
        )
    if missing:
        joined = ', '.join(str(number) for number in missing)
        raise music_generator.MusicGenerationError(
            'Generate TTS audio first. Segments without a measured duration: '
            f'{joined}.'
        )
    return music_generator.normalise_segments(raw)


def segments_from_payload(data):
    """Normalise a raw script JSON body into measured segments."""
    script = data.get('script') if hasattr(data, 'get') else None
    if script is None:
        script = data.get('segments') if hasattr(data, 'get') else data
    return music_generator.normalise_segments(script)


def _sanitise_filename(value: str) -> str:
    stem = ''.join(
        char for char in (value or 'soundtrack')
        if char.isalnum() or char in (' ', '-', '_')
    ).strip()
    return (stem or 'soundtrack')[:80]


def music_progress_percent(current: int, total: int) -> int:
    """Map a MusicGen segment step onto the 5–90 % slice of the task bar.

    Model loading and every generated segment live in this slice; MP3
    encoding and persistence use the remaining 5–100 %.  The value is clamped
    so a worker reporting ``0/N`` (loading) never moves the bar backwards.
    """
    fraction = 0.0
    if total > 0:
        fraction = max(0.0, min(1.0, current / total))
    return 5 + int(fraction * 85 + 0.5)


def generate_soundtrack_task(
    *,
    task_id: str,
    account_id: str,
    section: str,
    segments,
    project_id: str | None = None,
    name: str = '',
    plan_options: dict | None = None,
    attach_to_project: bool = True,
    progress_start: int = 0,
    progress_end: int = 100,
) -> dict:
    """Background entry point: synthesise, encode and persist a soundtrack.

    Runs inside the TaskManager worker (max_workers=1) and additionally takes
    ``_GENERATION_LOCK`` so no other caller can start a second GPU session.

    ``progress_start`` / ``progress_end`` let a caller that embeds music
    generation inside a larger job (the Settings playground generates music and
    then mixes it into an existing video) reserve only a slice of the progress
    bar for this task.
    """
    from api.models import Account, BGMClip, Project
    from api.tasks import get_task_manager

    options = dict(plan_options or {})
    manager = get_task_manager()
    project = Project.objects.filter(pk=project_id).first() if project_id else None
    account = Account.objects.get(pk=account_id)
    total = len(segments)

    range_start = max(0, min(100, int(progress_start)))
    range_end = max(range_start, min(100, int(progress_end)))
    span = range_end - range_start

    def scaled(percent: float) -> int:
        """Map a 0–100 MusicGen percentage onto the reserved slice."""
        bounded = max(0.0, min(100.0, float(percent)))
        return range_start + int(round(span * bounded / 100.0))

    manager.update_task_progress(
        task_id,
        current=0,
        total=total,
        description='Preparing MusicGen soundtrack…',
        percentage_override=scaled(0),
    )

    def on_progress(current, total_segments, description):
        if manager.is_cancelled(task_id):
            raise SoundtrackCancelled('Soundtrack generation cancelled.')
        # MusicGen owns 5–90 % of the bar (model load + each segment); the
        # remaining 10 % covers MP3 encoding and persistence.  Using an
        # override keeps the bar monotonic even when the worker reports its
        # "loading model" event as 0/segment_count.
        manager.update_task_progress(
            task_id,
            current=current,
            total=total_segments,
            description=description,
            percentage_override=scaled(
                music_progress_percent(current, total_segments)
            ),
        )

    with _GENERATION_LOCK:
        handle, wav_path = tempfile.mkstemp(suffix='.wav')
        os.close(handle)
        mp3_path = wav_path[:-4] + '.mp3'
        try:
            # 6 GB VRAM: evict Kokoro/Qwen TTS before allocating MusicGen.
            manager.update_task_progress(
                task_id,
                current=0,
                total=total,
                description='Unloading TTS models to free VRAM…',
                percentage_override=scaled(2),
            )
            released = music_generator.release_tts_resources()
            logger.info(
                'VRAM hand-off before MusicGen: %s',
                ', '.join(released) or 'no resident TTS model',
            )

            result = music_generator.synthesize_soundtrack(
                segments,
                wav_path,
                bpm=options.get('bpm'),
                root_key=options.get('root_key') or options.get('key'),
                mode=options.get('mode'),
                style=options.get('style')
                or 'instrumental cinematic documentary score',
                progress=on_progress,
            )

            if manager.is_cancelled(task_id):
                raise SoundtrackCancelled('Soundtrack generation cancelled.')

            manager.update_task_progress(
                task_id,
                current=total,
                total=total,
                description='Encoding soundtrack to MP3…',
                percentage_override=scaled(95),
            )
            audio_convert.convert_to_mp3(wav_path, mp3_path)

            clip_name = (name or '').strip()
            if not clip_name:
                base = project.title if project else 'Documentary'
                clip_name = f'{base} — Generated Soundtrack'
            metadata = {
                'engine': 'musicgen',
                'model': music_generator.MUSICGEN_MODEL,
                'generated': True,
                **result.get('plan', {}),
            }

            clip = BGMClip(
                account=account,
                section=section,
                name=clip_name[:255],
                is_shared=False,
                original_name=clip_name[:255],
                original_format='wav',
                duration=result['duration'],
                file_size=os.path.getsize(mp3_path),
                source='generated',
                project=project,
                generation_metadata=metadata,
            )
            with open(mp3_path, 'rb') as converted:
                from django.core.files import File

                clip.file.save(
                    f'{_sanitise_filename(clip_name)}.mp3',
                    File(converted),
                    save=False,
                )
            clip.save()

            if project is not None and attach_to_project:
                project.active_bgm = clip
                project.bgm_enabled = True
                project.save(update_fields=['active_bgm', 'bgm_enabled'])

            manager.update_task_progress(
                task_id,
                current=total,
                total=total,
                description='Soundtrack ready',
                percentage_override=scaled(100),
                generated_clip_id=str(clip.id),
                output_url=clip.file.url,
                duration=result['duration'],
            )
            manager.add_completed_segment(
                task_id,
                project_id or account_id,
                {'audio_url': clip.file.url, 'duration': result['duration']},
            )
            logger.info(
                'Generated soundtrack %s for account %s (%d segments, %.2fs)',
                clip.id,
                account_id,
                total,
                result['duration'],
            )
            return {
                'clip_id': str(clip.id),
                'output_url': clip.file.url,
                'duration': result['duration'],
                'segments': total,
            }
        finally:
            for path in (wav_path, mp3_path):
                try:
                    os.remove(path)
                except OSError:
                    pass


def new_task_id(prefix: str = 'music') -> str:
    return f'{prefix}_{uuid.uuid4().hex[:12]}'
