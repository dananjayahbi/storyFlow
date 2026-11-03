"""API-level tests for the MusicGen soundtrack endpoint (mocked worker)."""

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APITestCase

from api import music_service
from api.models import Account, Project, Segment

GENERATE_URL = '/api/bgm/generate/'

AVAILABLE_ENGINE = {
    'engine': 'musicgen',
    'model': 'facebook/musicgen-small',
    'installed': True,
    'torch_installed': True,
    'torch_version': '2.5.0+cu121',
    'cuda_available': True,
    'device': 'cuda',
    'available': True,
    'python': '3.11.9',
    'reason': None,
    'sample_rate': 32000,
    'continuation_tail_seconds': 3.0,
    'crossfade_ms': 3000,
}

UNAVAILABLE_ENGINE = {
    **AVAILABLE_ENGINE,
    'available': False,
    'cuda_available': False,
    'device': None,
    'reason': 'CUDA is not available.',
}


class MusicGenerationApiTests(APITestCase):
    def setUp(self):
        self.account = Account.objects.create(
            name='Documentary Page', section='facebook'
        )
        self.project = Project.objects.create(
            title='Deep Ocean',
            section='facebook',
            account=self.account,
        )
        for index, duration in enumerate((5.0, 4.0, 3.0)):
            Segment.objects.create(
                project=self.project,
                sequence_index=index,
                text_content=f'Narration block {index}',
                image_prompt='underwater',
                audio_duration=duration,
            )
        self.query = f'?section=facebook&account={self.account.id}'

    def _post(self, payload):
        return self.client.post(
            f'{GENERATE_URL}{self.query}', payload, format='json'
        )

    @patch('api.views.get_task_manager')
    @patch('core_engine.music_generator.engine_status')
    def test_project_generation_is_queued(self, engine_status, task_manager):
        engine_status.return_value = AVAILABLE_ENGINE
        manager = MagicMock()
        task_manager.return_value = manager

        response = self._post({'project': str(self.project.id), 'name': 'Ocean bed'})

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data['engine'], 'musicgen')
        self.assertEqual(response.data['segments'], 3)
        self.assertEqual(response.data['project_id'], str(self.project.id))
        self.assertTrue(response.data['attach_to_project'])
        manager.submit_task.assert_called_once()
        kwargs = manager.submit_task.call_args.kwargs
        self.assertEqual(kwargs['task_id'], response.data['task_id'])

    @patch('api.views.get_task_manager')
    @patch('core_engine.music_generator.engine_status')
    def test_raw_script_with_durations_is_accepted(
        self, engine_status, task_manager
    ):
        engine_status.return_value = AVAILABLE_ENGINE
        task_manager.return_value = MagicMock()

        response = self._post({
            'segments': [
                {'text_content': 'One', 'duration': 2.5},
                {'text_content': 'Two', 'duration': 3.0},
            ]
        })

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data['segments'], 2)
        self.assertIsNone(response.data['project_id'])

    @patch('api.views.get_task_manager')
    @patch('core_engine.music_generator.engine_status')
    def test_missing_duration_is_rejected(self, engine_status, task_manager):
        response = self._post({
            'segments': [{'text_content': 'No timing yet'}]
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('duration', response.data['error'].lower())

    @patch('core_engine.music_generator.engine_status')
    def test_unavailable_engine_returns_503(self, engine_status):
        engine_status.return_value = UNAVAILABLE_ENGINE
        response = self._post({'project': str(self.project.id)})
        self.assertEqual(
            response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE
        )
        self.assertIn('CUDA', response.data['error'])
        self.assertFalse(response.data['engine']['available'])

    def test_generation_requires_an_account(self):
        response = self.client.post(
            GENERATE_URL, {'project': str(self.project.id)}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('core_engine.music_generator.engine_status')
    def test_engine_status_endpoint(self, engine_status):
        engine_status.return_value = AVAILABLE_ENGINE
        response = self.client.get(f'/api/bgm/engine-status/{self.query}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['available'])

    def test_project_without_tts_audio_is_rejected(self):
        empty = Project.objects.create(
            title='Empty project',
            section='facebook',
            account=self.account,
        )
        Segment.objects.create(
            project=empty,
            sequence_index=0,
            text_content='Needs TTS first',
            audio_duration=None,
        )
        response = self._post({'project': str(empty.id)})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('TTS', response.data['error'])


class MusicProgressTests(SimpleTestCase):
    def test_progress_covers_the_musicgen_slice(self):
        self.assertEqual(music_service.music_progress_percent(0, 4), 5)
        self.assertEqual(music_service.music_progress_percent(2, 4), 48)
        self.assertEqual(music_service.music_progress_percent(4, 4), 90)

    def test_progress_is_clamped_and_handles_zero_total(self):
        self.assertEqual(music_service.music_progress_percent(9, 4), 90)
        self.assertEqual(music_service.music_progress_percent(-1, 4), 5)
        self.assertEqual(music_service.music_progress_percent(1, 0), 5)
