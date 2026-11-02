"""Tests for the optional Qwen3-TTS engine integration.

No GPU is required: the engine subprocess is never started here.  Availability
checks, dispatch and persistence are exercised with mocks so the suite runs on
CI and on machines without CUDA.
"""

import os
import shutil
import tempfile
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import GlobalSettings, Project, Segment, VoiceReference

SETTINGS_URL = '/api/settings/'
ENGINES_URL = '/api/settings/tts-engines/'
VOICE_REFS_URL = '/api/settings/voice-references/'


class InlineTaskManager:
    """Runs submitted tasks synchronously so assertions are deterministic."""

    def is_cancelled(self, task_id):
        return False

    def update_task_progress(self, *args, **kwargs):
        return None

    def add_completed_segment(self, *args, **kwargs):
        return None

    def add_error(self, *args, **kwargs):
        return None

    def submit_task(self, task_fn, task_id=None):
        task_fn()
        return task_id


class VoiceReferenceTests(APITestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.tmp)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))
        GlobalSettings.load()

    def _upload(self, name='sample.wav', content=b'RIFF' + b'\x00' * 64):
        upload = SimpleUploadedFile(name, content, content_type='audio/wav')
        return self.client.post(
            VOICE_REFS_URL, {'file': upload, 'name': 'Narrator'}, format='multipart'
        )

    def test_upload_lists_and_stores_reference(self):
        response = self._upload()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        reference = VoiceReference.objects.get()
        self.assertEqual(reference.name, 'Narrator')
        self.assertTrue(reference.file.name.startswith('voice_references/'))
        self.assertTrue(os.path.isfile(reference.file.path))

        listing = self.client.get(VOICE_REFS_URL)
        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertEqual(len(listing.data), 1)
        self.assertEqual(listing.data[0]['name'], 'Narrator')

    def test_rejects_unsupported_extension(self):
        response = self._upload('notes.txt', b'not audio')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(VoiceReference.objects.exists())

    def test_delete_detaches_active_reference(self):
        self._upload()
        reference = VoiceReference.objects.get()

        settings_obj = GlobalSettings.load()
        settings_obj.active_voice_reference = reference
        settings_obj.save()

        project = Project.objects.create(title='Clone project')
        project.active_voice_reference = reference
        project.save()

        stored_path = reference.file.path
        response = self.client.delete(f'{VOICE_REFS_URL}{reference.id}/')

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(VoiceReference.objects.exists())
        settings_obj.refresh_from_db()
        project.refresh_from_db()
        self.assertIsNone(settings_obj.active_voice_reference)
        self.assertIsNone(project.active_voice_reference)
        self.assertFalse(os.path.isfile(stored_path))

    def test_patch_updates_transcript(self):
        self._upload()
        reference = VoiceReference.objects.get()

        response = self.client.patch(
            f'{VOICE_REFS_URL}{reference.id}/',
            {'transcript': 'This is the exact script.'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        reference.refresh_from_db()
        self.assertEqual(reference.transcript, 'This is the exact script.')


class TtsEngineSettingsTests(APITestCase):
    def setUp(self):
        GlobalSettings.load()

    def test_kokoro_is_the_default_engine(self):
        response = self.client.get(SETTINGS_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['tts_engine'], 'kokoro')
        self.assertEqual(response.data['qwen_mode'], 'custom_voice')
        self.assertEqual(response.data['qwen_speaker'], 'Aiden')

    def test_patch_persists_qwen_settings(self):
        response = self.client.patch(
            SETTINGS_URL,
            {
                'tts_engine': 'qwen',
                'qwen_mode': 'clone',
                'qwen_speaker': 'Ryan',
                'qwen_language': 'English',
                'qwen_max_new_tokens': 1536,
                'qwen_clone_x_vector_only': False,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['tts_engine'], 'qwen')
        self.assertEqual(response.data['qwen_mode'], 'clone')
        self.assertEqual(response.data['qwen_speaker'], 'Ryan')
        self.assertEqual(response.data['qwen_max_new_tokens'], 1536)
        self.assertFalse(response.data['qwen_clone_x_vector_only'])

    def test_rejects_unknown_speaker_and_token_bounds(self):
        bad_speaker = self.client.patch(
            SETTINGS_URL, {'qwen_speaker': 'Nobody'}, format='json'
        )
        self.assertEqual(bad_speaker.status_code, status.HTTP_400_BAD_REQUEST)

        too_many = self.client.patch(
            SETTINGS_URL, {'qwen_max_new_tokens': 99999}, format='json'
        )
        self.assertEqual(too_many.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('core_engine.qwen_client.probe')
    @patch('core_engine.tts.qwen_available', return_value=False)
    @patch('core_engine.tts.kokoro_available', return_value=True)
    def test_engines_endpoint_lists_both_engines(self, _kokoro, _qwen, _probe):
        response = self.client.get(ENGINES_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        engines = {item['id']: item for item in response.data['engines']}
        self.assertEqual(set(engines), {'kokoro', 'qwen'})
        self.assertTrue(engines['kokoro']['available'])
        self.assertFalse(engines['qwen']['available'])
        self.assertTrue(engines['qwen']['supports_cloning'])
        self.assertEqual(response.data['default_engine'], 'kokoro')

    def test_project_inherits_engine_settings_on_import(self):
        settings_obj = GlobalSettings.load()
        settings_obj.tts_engine = 'qwen'
        settings_obj.qwen_speaker = 'Serena'
        settings_obj.save()

        response = self.client.post(
            '/api/projects/import/',
            {
                'format': 'json',
                'title': 'Inherited Settings',
                'segments': [{'text_content': 'Hello', 'image_prompt': ''}],
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        project = Project.objects.get(title='Inherited Settings')
        self.assertEqual(project.tts_engine, 'qwen')
        self.assertEqual(project.qwen_speaker, 'Serena')


class AudioEngineDispatchTests(APITestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.tmp)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))
        self.project = Project.objects.create(title='Engine Test')
        self.segment = Segment.objects.create(
            project=self.project, sequence_index=0, text_content='Hello there.'
        )
        GlobalSettings.load()

    @patch('core_engine.tts.qwen_available', return_value=True)
    @patch('core_engine.tts.synthesize')
    def test_bulk_qwen_marks_audio_engine(self, mock_synthesize, _available):
        mock_synthesize.return_value = {
            'success': True,
            'duration': 1.75,
            'sample_rate': 24000,
            'engine': 'qwen',
        }

        with patch('api.views.get_task_manager', return_value=InlineTaskManager()):
            response = self.client.post(
                f'/api/projects/{self.project.id}/generate-all-audio/',
                {'engine': 'qwen'},
                format='json',
            )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data['engine'], 'qwen')

        self.segment.refresh_from_db()
        self.assertEqual(self.segment.audio_engine, 'qwen')
        self.assertAlmostEqual(self.segment.audio_duration, 1.75)
        self.assertTrue(
            self.segment.audio_file.name.startswith(
                f'Facebook/{self.project.account_id}/{self.project.id}/audio/'
            )
        )

        kwargs = mock_synthesize.call_args.kwargs
        self.assertEqual(kwargs['engine'], 'qwen')

    @patch('core_engine.tts.qwen_available', return_value=False)
    def test_bulk_qwen_unavailable_returns_503(self, _available):
        response = self.client.post(
            f'/api/projects/{self.project.id}/generate-all-audio/',
            {'engine': 'qwen'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertIn('Qwen', response.data['error'])

    @patch('core_engine.tts.qwen_available', return_value=True)
    def test_bulk_qwen_clone_without_reference_returns_400(self, _available):
        self.project.qwen_mode = 'clone'
        self.project.save()

        response = self.client.post(
            f'/api/projects/{self.project.id}/generate-all-audio/',
            {'engine': 'qwen'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('reference', response.data['error'].lower())

    @patch('core_engine.tts.qwen_available', return_value=True)
    @patch('core_engine.tts.synthesize')
    def test_switching_engine_regenerates_existing_audio(
        self, mock_synthesize, _available
    ):
        mock_synthesize.return_value = {
            'success': True, 'duration': 1.0, 'sample_rate': 24000,
            'engine': 'qwen',
        }
        self.segment.audio_file.name = (
            f'Facebook/{self.project.account_id}/{self.project.id}/audio/{self.segment.id}.wav'
        )
        self.segment.audio_engine = 'kokoro'
        self.segment.save()

        with patch('api.views.get_task_manager', return_value=InlineTaskManager()):
            response = self.client.post(
                f'/api/projects/{self.project.id}/generate-all-audio/',
                {'engine': 'qwen'},
                format='json',
            )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data['segments_to_process'], 1)
        self.segment.refresh_from_db()
        self.assertEqual(self.segment.audio_engine, 'qwen')

    def test_bulk_invalid_voice_reference_returns_400(self):
        response = self.client.post(
            f'/api/projects/{self.project.id}/generate-all-audio/',
            {
                'engine': 'qwen',
                'voice_reference_id': 'not-a-uuid',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('voice_reference_id', response.data)

    @patch('core_engine.tts.qwen_available', return_value=False)
    def test_single_segment_qwen_unavailable_returns_503(self, _available):
        response = self.client.post(
            f'/api/segments/{self.segment.id}/generate-audio/',
            {'engine': 'qwen'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    def test_invalid_engine_returns_400(self):
        response = self.client.post(
            f'/api/segments/{self.segment.id}/generate-audio/',
            {'engine': 'elevenlabs'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('core_engine.tts.qwen_available', return_value=False)
    def test_tts_test_endpoint_reports_missing_qwen(self, _available):
        response = self.client.post(
            '/api/settings/tts-test/',
            {'text': 'Hello', 'engine': 'qwen'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertIn('Qwen', response.data['error'])

