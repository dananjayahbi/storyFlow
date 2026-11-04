"""Audio Mix settings and the Settings-page demo playground."""

import os
import tempfile
from unittest.mock import MagicMock, patch

import numpy as np
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import (
    Account,
    AccountSettings,
    BGMClip,
    GlobalSettings,
    Project,
    Segment,
)
from api.playground_service import (
    _ensure_generated_music,
    blocks_fingerprint,
    find_generated_music,
    get_or_create_playground,
    playground_payload,
)
from core_engine.music_generator import apply_music_echo

AVAILABLE_ENGINE = {'available': True, 'reason': None}
UNAVAILABLE_ENGINE = {
    'available': False,
    'reason': 'CUDA is not available.',
}

PLAYGROUND_URL = '/api/settings/playground/'
GENERATE_URL = '/api/settings/playground/generate/'
APPLY_URL = '/api/settings/playground/apply/'
CANCEL_URL = '/api/settings/playground/cancel/'
SETTINGS_URL = '/api/settings/'


def image_upload(name='block.png'):
    from io import BytesIO

    from PIL import Image

    buffer = BytesIO()
    Image.new('RGB', (2, 2), (24, 160, 88)).save(buffer, format='PNG')
    return SimpleUploadedFile(
        name,
        buffer.getvalue(),
        content_type='image/png',
    )


class AudioMixSettingsTests(APITestCase):
    def setUp(self):
        GlobalSettings.objects.all().delete()
        GlobalSettings.load()
        self.account = Account.objects.create(name='Page One', section='facebook')
        self.other = Account.objects.create(name='Page Two', section='facebook')
        self.project = Project.objects.create(
            title='Real project', section='facebook', account=self.account
        )

    def _url(self, account=None):
        account = account or self.account
        return f'{SETTINGS_URL}?section=facebook&account={account.id}'

    def test_mix_defaults_and_validation(self):
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['bgm_gain_db'], -18.0)
        self.assertEqual(response.data['bgm_ducking_db'], -12.0)
        self.assertEqual(response.data['bgm_echo_percent'], 0.0)
        self.assertEqual(response.data['tts_gain_db'], 0.0)

        bad_echo = self.client.patch(
            self._url(), {'bgm_echo_percent': 150}, format='json'
        )
        self.assertEqual(bad_echo.status_code, status.HTTP_400_BAD_REQUEST)

        bad_voice = self.client.patch(
            self._url(), {'tts_gain_db': 30}, format='json'
        )
        self.assertEqual(bad_voice.status_code, status.HTTP_400_BAD_REQUEST)

    def test_saving_mix_does_not_rewrite_existing_projects(self):
        other_project = Project.objects.create(
            title='Other project', section='facebook', account=self.other
        )
        response = self.client.patch(
            self._url(),
            {
                'bgm_gain_db': -24,
                'bgm_ducking_db': -8,
                'bgm_echo_percent': 35,
                'tts_gain_db': 4,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['bgm_gain_db'], -24)

        # Existing projects own their settings snapshot.
        self.project.refresh_from_db()
        self.assertEqual(self.project.bgm_gain_db, -18)
        self.assertEqual(self.project.bgm_ducking_db, -12)
        self.assertEqual(self.project.bgm_echo_percent, 0)
        self.assertEqual(self.project.tts_gain_db, 0)

        other_project.refresh_from_db()
        self.assertEqual(other_project.bgm_gain_db, -18)
        self.assertEqual(other_project.tts_gain_db, 0)

    def test_saving_tts_engine_does_not_rewrite_existing_projects(self):
        other_project = Project.objects.create(
            title='Other project', section='facebook', account=self.other
        )
        response = self.client.patch(
            self._url(),
            {'tts_engine': 'qwen'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['tts_engine'], 'qwen')

        self.project.refresh_from_db()
        self.assertEqual(self.project.tts_engine, 'kokoro')

        other_project.refresh_from_db()
        self.assertEqual(other_project.tts_engine, 'kokoro')

    def test_new_project_inherits_mix_values(self):
        self.client.patch(
            self._url(),
            {'bgm_gain_db': -22, 'bgm_echo_percent': 50, 'tts_gain_db': 6},
            format='json',
        )
        response = self.client.post(
            f'/api/projects/?section=facebook&account={self.account.id}',
            {'title': 'Inherited', 'section': 'facebook'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        project = Project.objects.get(pk=response.data['id'])
        self.assertEqual(project.bgm_gain_db, -22)
        self.assertEqual(project.bgm_echo_percent, 50)
        self.assertEqual(project.tts_gain_db, 6)


class PlaygroundAPITests(APITestCase):
    def setUp(self):
        GlobalSettings.objects.all().delete()
        GlobalSettings.load()
        self.account = Account.objects.create(name='Page One', section='facebook')
        self.other = Account.objects.create(name='Page Two', section='facebook')
        self.url = f'{PLAYGROUND_URL}?section=facebook&account={self.account.id}'
        self.generate_url = (
            f'{GENERATE_URL}?section=facebook&account={self.account.id}'
        )

    def test_get_creates_three_blocks_and_hides_the_project(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['blocks']), 3)
        self.assertEqual(
            [block['index'] for block in response.data['blocks']], [0, 1, 2]
        )

        playground = Project.objects.get(
            account=self.account, is_playground=True
        )
        self.assertEqual(playground.segments.count(), 3)

        listing = self.client.get(
            f'/api/projects/?section=facebook&account={self.account.id}'
        )
        ids = {item['id'] for item in listing.data['results']}
        self.assertNotIn(str(playground.id), ids)

        account_response = self.client.get(
            f'/api/accounts/?section=facebook&account={self.account.id}'
        )
        row = next(
            item for item in account_response.data['results']
            if item['id'] == str(self.account.id)
        )
        self.assertEqual(row['project_count'], 0)
        self.assertEqual(row['gallery_count'], 0)

    def test_save_blocks_clears_audio_for_changed_text(self):
        self.client.get(self.url)
        playground = Project.objects.get(
            account=self.account, is_playground=True
        )
        segment = playground.segments.order_by('sequence_index').first()
        segment.audio_file = 'fake/audio.wav'
        segment.audio_duration = 4.2
        segment.save()

        response = self.client.put(
            self.url,
            {
                'blocks': [
                    {'text_content': 'New text'},
                    {'text_content': ''},
                    {'text_content': ''},
                ]
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        segment.refresh_from_db()
        self.assertEqual(segment.text_content, 'New text')
        self.assertFalse(segment.audio_file)
        self.assertIsNone(segment.audio_duration)

    def test_image_upload_and_remove(self):
        self.client.get(self.url)
        upload = self.client.post(
            f'{PLAYGROUND_URL}blocks/0/image/?section=facebook&account={self.account.id}',
            {'image': image_upload()},
            format='multipart',
        )
        self.assertEqual(upload.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(upload.data['image_url'])

        # The generated filename must stay ASCII-only so OpenCV can read it
        # on Windows even when the operator uploaded a Unicode filename.
        saved_segment = (
            Project.objects.get(account=self.account, is_playground=True)
            .segments.order_by('sequence_index')
            .first()
        )
        self.assertTrue(saved_segment.image_file.name.isascii())

        remove = self.client.delete(
            f'{PLAYGROUND_URL}blocks/0/image/?section=facebook&account={self.account.id}'
        )
        self.assertEqual(remove.status_code, status.HTTP_200_OK)
        self.assertIsNone(remove.data['image_url'])

        segment = (
            Project.objects.get(account=self.account, is_playground=True)
            .segments.order_by('sequence_index')
            .first()
        )
        self.assertFalse(segment.image_file)

    def test_generate_requires_text_and_images(self):
        self.client.get(self.url)
        response = self.client.post(self.generate_url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('text', response.data['error'].lower())

    def test_generate_starts_a_replacing_task(self):
        self.client.get(self.url)
        for segment in Project.objects.get(
            account=self.account, is_playground=True
        ).segments.all():
            segment.text_content = f'Text {segment.sequence_index}'
            segment.image_file = f'images/block-{segment.sequence_index}.png'
            segment.save()

        with __import__('unittest').mock.patch(
            'api.playground_views.start_generation', return_value='playground_task'
        ) as start:
            response = self.client.post(
                self.generate_url,
                {'bgm_clip': None},
                format='json',
            )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data['task_id'], 'playground_task')
        start.assert_called_once()

    def test_playground_is_account_scoped(self):
        response = self.client.get(
            f'{PLAYGROUND_URL}?section=facebook&account={self.other.id}'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        playgrounds = Project.objects.filter(is_playground=True)
        self.assertEqual(playgrounds.count(), 1)
        self.assertEqual(playgrounds.first().account, self.other)

    def test_apply_requires_a_generated_base_video(self):
        self.client.get(self.url)
        response = self.client.post(
            f'{APPLY_URL}?section=facebook&account={self.account.id}',
            {},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('generate', response.data['error'].lower())

    def test_apply_starts_a_remix_for_an_existing_base_video(self):
        import os
        import tempfile

        from django.test import override_settings

        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                self.client.get(self.url)
                playground = Project.objects.get(
                    account=self.account, is_playground=True
                )
                for segment in playground.segments.all():
                    segment.text_content = f'Text {segment.sequence_index}'
                    segment.image_file = f'images/block-{segment.sequence_index}.png'
                    segment.audio_file = f'audio/block-{segment.sequence_index}.wav'
                    segment.save()

                base_rel = (
                    f'Facebook/{self.account.id}/{playground.id}/'
                    'output/playground_base.mp4'
                )
                narration_rel = (
                    f'Facebook/{self.account.id}/{playground.id}/'
                    'output/playground_narration.wav'
                )
                for relative in (base_rel, narration_rel):
                    path = os.path.join(media_root, relative)
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    with open(path, 'wb') as handle:
                        handle.write(b'x')
                playground.playground_base_video = base_rel
                playground.playground_narration_audio = narration_rel
                playground.save(update_fields=[
                    'playground_base_video', 'playground_narration_audio',
                ])

                with __import__('unittest').mock.patch(
                    'api.playground_views.start_remix',
                    return_value='remix_task',
                ) as start:
                    response = self.client.post(
                        f'{APPLY_URL}?section=facebook&account={self.account.id}',
                        {'bgm_clip': None},
                        format='json',
                    )

                self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
                self.assertEqual(response.data['task_id'], 'remix_task')
                start.assert_called_once()

    def _prepare_remixable_playground(self, media_root):
        """Create a base video, narration and measured blocks on disk."""
        self.client.get(self.url)
        playground = Project.objects.get(
            account=self.account, is_playground=True
        )
        for index, segment in enumerate(
            playground.segments.order_by('sequence_index')
        ):
            segment.text_content = f'Text {index}'
            segment.image_file = f'images/block-{index}.png'
            segment.audio_file = f'audio/block-{index}.wav'
            segment.audio_duration = 5.0 + index
            segment.save()

        base_rel = (
            f'Facebook/{self.account.id}/{playground.id}/'
            'output/playground_base.mp4'
        )
        narration_rel = (
            f'Facebook/{self.account.id}/{playground.id}/'
            'output/playground_narration.wav'
        )
        for relative in (base_rel, narration_rel):
            path = os.path.join(media_root, relative)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'wb') as handle:
                handle.write(b'x')
        playground.playground_base_video = base_rel
        playground.playground_narration_audio = narration_rel
        playground.save(update_fields=[
            'playground_base_video', 'playground_narration_audio',
        ])
        return playground

    def test_apply_generated_music_starts_musicgen(self):
        """Apply Background Music must trigger the MusicGen model."""
        apply_url = (
            f'{APPLY_URL}?section=facebook&account={self.account.id}'
        )
        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                self._prepare_remixable_playground(media_root)

                with patch(
                    'api.playground_views.start_remix',
                    return_value='remix_task',
                ) as start, patch(
                    'core_engine.music_generator.engine_status',
                    return_value=AVAILABLE_ENGINE,
                ):
                    response = self.client.post(
                        apply_url,
                        {'music_source': 'generated'},
                        format='json',
                    )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertTrue(response.data['generate_music'])
        self.assertEqual(response.data['music_source'], 'generated')
        start.assert_called_once()
        kwargs = start.call_args.kwargs
        self.assertTrue(kwargs['generate_music'])
        self.assertFalse(kwargs['regenerate_music'])
        self.assertIsNone(kwargs['bgm_clip'])

    def test_apply_generated_music_can_force_a_new_soundtrack(self):
        apply_url = (
            f'{APPLY_URL}?section=facebook&account={self.account.id}'
        )
        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                self._prepare_remixable_playground(media_root)

                with patch(
                    'api.playground_views.start_remix',
                    return_value='remix_task',
                ) as start, patch(
                    'core_engine.music_generator.engine_status',
                    return_value=AVAILABLE_ENGINE,
                ):
                    response = self.client.post(
                        apply_url,
                        {
                            'music_source': 'generated',
                            'regenerate_music': True,
                        },
                        format='json',
                    )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertTrue(start.call_args.kwargs['regenerate_music'])

    def test_apply_generated_music_reports_unavailable_engine(self):
        apply_url = (
            f'{APPLY_URL}?section=facebook&account={self.account.id}'
        )
        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                self._prepare_remixable_playground(media_root)

                with patch(
                    'api.playground_views.start_remix',
                    return_value='remix_task',
                ) as start, patch(
                    'core_engine.music_generator.engine_status',
                    return_value=UNAVAILABLE_ENGINE,
                ):
                    response = self.client.post(
                        apply_url,
                        {'music_source': 'generated'},
                        format='json',
                    )

        self.assertEqual(
            response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE
        )
        self.assertIn('CUDA', response.data['error'])
        start.assert_not_called()

    def test_cancel_reports_idle_and_stops_a_running_job(self):
        self.client.get(self.url)
        idle = self.client.post(
            f'{CANCEL_URL}?section=facebook&account={self.account.id}',
            {},
            format='json',
        )
        self.assertEqual(idle.status_code, status.HTTP_409_CONFLICT)

        with __import__('unittest').mock.patch(
            'api.playground_views._active_job',
            return_value={'status': 'PROCESSING'},
        ), __import__('unittest').mock.patch(
            'api.playground_views.cancel_generation',
            return_value=True,
        ) as cancel:
            response = self.client.post(
                f'{CANCEL_URL}?section=facebook&account={self.account.id}',
                {},
                format='json',
            )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertTrue(response.data['cancel_requested'])
        cancel.assert_called_once()


class PlaygroundGeneratedMusicTests(APITestCase):
    """MusicGen soundtracks are re-used only while they match the demo."""

    def setUp(self):
        GlobalSettings.objects.all().delete()
        GlobalSettings.load()
        self.account = Account.objects.create(
            name='Music Page', section='facebook'
        )
        self.project = Project.objects.create(
            title='Settings Playground',
            section='facebook',
            account=self.account,
            is_playground=True,
        )
        for index, duration in enumerate((5.0, 6.0, 7.0)):
            Segment.objects.create(
                project=self.project,
                sequence_index=index,
                text_content=f'Block {index}',
                audio_duration=duration,
            )

    def _make_clip(self, media_root, fingerprint, name='Generated'):
        relative = f'bgm/facebook/{self.account.id}/track.mp3'
        path = os.path.join(media_root, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as handle:
            handle.write(b'mp3')
        return BGMClip.objects.create(
            account=self.account,
            section='facebook',
            name=name,
            file=relative,
            source='generated',
            project=self.project,
            generation_metadata={
                'generated': True,
                'fingerprint': fingerprint,
            },
        )

    def test_matching_generated_music_is_reported_ready(self):
        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                clip = self._make_clip(
                    media_root, blocks_fingerprint(self.project)
                )
                self.assertEqual(
                    find_generated_music(self.project).id, clip.id
                )

                self.project.active_bgm = clip
                self.project.bgm_enabled = True
                self.project.save(update_fields=['active_bgm', 'bgm_enabled'])

                payload = playground_payload(self.project)

        self.assertEqual(payload['music_source'], 'generated')
        self.assertEqual(payload['music_clip_name'], 'Generated')
        self.assertTrue(payload['generated_music_ready'])
        self.assertFalse(payload['generated_music_stale'])

    def test_changed_script_marks_generated_music_stale(self):
        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                self._make_clip(
                    media_root, blocks_fingerprint(self.project)
                )
                segment = self.project.segments.order_by(
                    'sequence_index'
                ).first()
                segment.text_content = 'A completely different story'
                segment.audio_duration = 11.0
                segment.save()

                self.assertIsNone(find_generated_music(self.project))
                payload = playground_payload(self.project)

        self.assertFalse(payload['generated_music_ready'])
        self.assertTrue(payload['generated_music_stale'])

    def test_cancelled_music_generation_stops_the_playground_job(self):
        from api import music_service
        from api.playground_service import PlaygroundCancelled

        manager = MagicMock()
        manager.is_cancelled.return_value = False

        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root), patch(
                'api.music_service.generate_soundtrack_task',
                side_effect=music_service.SoundtrackCancelled('stopped'),
            ):
                with self.assertRaises(PlaygroundCancelled):
                    _ensure_generated_music(self.project, manager, 'task')

    def test_ensure_generated_music_reuses_then_regenerates(self):
        manager = MagicMock()
        manager.is_cancelled.return_value = False
        calls = []

        def fake_generate(**kwargs):
            calls.append(kwargs)
            clip = self._make_clip(
                media_root,
                blocks_fingerprint(self.project),
                name=f'Generated {len(calls)}',
            )
            self.project.active_bgm = clip
            self.project.bgm_enabled = True
            self.project.save(update_fields=['active_bgm', 'bgm_enabled'])
            return {'clip_id': str(clip.id), 'duration': 18.0}

        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root), patch(
                'api.music_service.generate_soundtrack_task',
                side_effect=fake_generate,
            ):
                first = _ensure_generated_music(
                    self.project, manager, 'task'
                )
                self.assertEqual(len(calls), 1)
                self.assertEqual(
                    first.generation_metadata['fingerprint'],
                    blocks_fingerprint(self.project),
                )
                self.assertTrue(first.generation_metadata['playground'])

                # A matching soundtrack is re-used on the next Apply.
                reused = _ensure_generated_music(
                    self.project, manager, 'task'
                )
                self.assertEqual(reused.id, first.id)
                self.assertEqual(len(calls), 1)

                # Forcing a new soundtrack calls MusicGen again.
                regenerated = _ensure_generated_music(
                    self.project, manager, 'task', regenerate=True
                )
                self.assertEqual(len(calls), 2)
                self.assertNotEqual(regenerated.id, first.id)

        self.project.refresh_from_db()
        self.assertEqual(self.project.active_bgm_id, regenerated.id)


class PlaygroundPersistenceTests(APITestCase):
    """A running background job must survive a page reload (a fresh GET)."""

    def setUp(self):
        GlobalSettings.objects.all().delete()
        GlobalSettings.load()
        self.account = Account.objects.create(
            name='Persistent Page', section='facebook'
        )
        self.project = Project.objects.create(
            title='Persistent playground',
            section='facebook',
            account=self.account,
            is_playground=True,
            status='PROCESSING',
            playground_job='BASE',
        )

    def test_active_task_keeps_processing_state_on_reload(self):
        fake_manager = __import__('unittest').mock.Mock()
        fake_manager.get_task_status.return_value = {
            'status': 'PROCESSING',
            'progress': {
                'percentage': 37,
                'description': 'Rendering frames…',
            },
            'cancel_requested': False,
        }

        with __import__('unittest').mock.patch(
            'api.playground_service.get_task_manager',
            return_value=fake_manager,
        ):
            reloaded = get_or_create_playground(self.account)
            payload = playground_payload(reloaded)

        self.project.refresh_from_db()
        self.assertEqual(self.project.status, 'PROCESSING')
        self.assertEqual(self.project.playground_job, 'BASE')
        self.assertEqual(payload['status'], 'PROCESSING')
        self.assertEqual(payload['task_status'], 'PROCESSING')
        self.assertEqual(payload['progress'], 37)

    def test_missing_task_clears_a_stale_processing_flag(self):
        fake_manager = __import__('unittest').mock.Mock()
        fake_manager.get_task_status.return_value = None

        with __import__('unittest').mock.patch(
            'api.playground_service.get_task_manager',
            return_value=fake_manager,
        ):
            get_or_create_playground(self.account)

        self.project.refresh_from_db()
        self.assertEqual(self.project.status, 'DRAFT')
        self.assertEqual(self.project.playground_job, '')


class PlaygroundRenderWorkflowTests(APITestCase):
    """The playground can render a base video and re-mix it without TTS."""

    def test_unicode_image_path_can_be_loaded(self):
        import os
        import tempfile

        from PIL import Image
        from core_engine.ken_burns import load_and_prepare_image

        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(
                directory,
                'playground_0_Ayurvedic_backg\u2026_2K.jpeg',
            )
            Image.new('RGB', (320, 180), (30, 120, 220)).save(path)
            prepared = load_and_prepare_image(path, (320, 180), 1.2)
            self.assertEqual(prepared.ndim, 3)
            self.assertEqual(prepared.shape[2], 3)
            self.assertGreater(prepared.shape[0], 0)
            self.assertGreater(prepared.shape[1], 0)

    def test_base_render_then_audio_remix(self):
        import os
        import tempfile

        import soundfile as sf
        from django.test import override_settings
        from PIL import Image
        from core_engine.music_generator import mix_background_music
        from core_engine.render_utils import mux_audio_into_video
        from core_engine.video_renderer import render_project

        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                account = Account.objects.create(
                    name='Render Account', section='facebook'
                )
                project = Project.objects.create(
                    title='Render playground',
                    section='facebook',
                    account=account,
                    resolution_width=320,
                    resolution_height=180,
                    framerate=12,
                )
                segment = Segment.objects.create(
                    project=project,
                    sequence_index=0,
                    text_content='Base render',
                    audio_duration=0.6,
                )

                image_rel = (
                    f'Facebook/{account.id}/{project.id}/images/block.png'
                )
                audio_rel = (
                    f'Facebook/{account.id}/{project.id}/audio/block.wav'
                )
                image_path = os.path.join(media_root, image_rel)
                audio_path = os.path.join(media_root, audio_rel)
                os.makedirs(os.path.dirname(image_path), exist_ok=True)
                os.makedirs(os.path.dirname(audio_path), exist_ok=True)
                Image.new('RGB', (320, 180), (30, 120, 220)).save(image_path)
                sf.write(
                    audio_path,
                    np.zeros(26460, dtype=np.float32),
                    44100,
                )
                segment.image_file.name = image_rel
                segment.audio_file.name = audio_rel
                segment.save()

                output_dir = os.path.join(media_root, 'render')
                os.makedirs(output_dir, exist_ok=True)
                base_path = os.path.join(output_dir, 'base.mp4')
                narration_path = os.path.join(output_dir, 'narration.wav')
                mixed_path = os.path.join(output_dir, 'mixed.wav')
                final_path = os.path.join(output_dir, 'final.mp4')
                bgm_path = os.path.join(output_dir, 'bgm.wav')
                sf.write(
                    bgm_path,
                    np.zeros(44100, dtype=np.float32),
                    44100,
                )

                result = render_project(
                    str(project.id),
                    output_path=base_path,
                    include_bgm=False,
                    subtitles_override=False,
                    narration_output_path=narration_path,
                )
                self.assertTrue(os.path.isfile(base_path))
                self.assertTrue(os.path.isfile(narration_path))
                self.assertGreater(result['duration'], 0)

                mix_result = mix_background_music(
                    narration_path,
                    bgm_path,
                    mixed_path,
                    music_gain_db=-24,
                    ducking_db=-10,
                    echo_percent=20,
                    narration_gain_db=2,
                )
                self.assertTrue(os.path.isfile(mixed_path))
                self.assertGreater(mix_result['duration'], 0)

                mux_audio_into_video(base_path, mixed_path, final_path)
                self.assertTrue(os.path.isfile(final_path))
                self.assertGreater(os.path.getsize(final_path), 0)


class MusicEchoTests(APITestCase):
    def test_dry_signal_is_unchanged(self):
        audio = np.linspace(-0.5, 0.5, 1000, dtype=np.float32).reshape(-1, 1)
        dry = apply_music_echo(audio, 44100, 0)
        np.testing.assert_array_equal(dry, audio)

    def test_echo_adds_a_delayed_copy(self):
        sample_rate = 1000
        audio = np.zeros((2000, 1), dtype=np.float32)
        audio[0, 0] = 1.0
        echoed = apply_music_echo(
            audio, sample_rate, 100, delay_ms=100, feedback=0.5, taps=2
        )
        delay = 100
        self.assertAlmostEqual(float(echoed[delay, 0]), 0.5, places=5)
        self.assertAlmostEqual(float(echoed[delay * 2, 0]), 0.25, places=5)
        self.assertEqual(float(echoed[0, 0]), 1.0)

    def test_echo_never_changes_shape(self):
        audio = np.ones((500, 1), dtype=np.float32) * 0.1
        echoed = apply_music_echo(audio, 44100, 100)
        self.assertEqual(echoed.shape, audio.shape)
        self.assertTrue(np.isfinite(echoed).all())
