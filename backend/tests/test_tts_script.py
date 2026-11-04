"""Tests for the TTS-ready script pipeline (Issue #27)."""

import os
import shutil
import tempfile
from unittest.mock import patch

from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import Account, GlobalSettings, Project, Segment
from core_engine import tts_script


class InlineTaskManager:
    """Run submitted tasks synchronously for deterministic assertions."""

    def __init__(self):
        self.completed = []
        self.errors = []

    def is_cancelled(self, task_id):
        return False

    def update_task_progress(self, *args, **kwargs):
        return None

    def add_completed_segment(self, task_id, segment_id, payload=None):
        self.completed.append((segment_id, payload))

    def add_error(self, task_id, segment_id, error):
        self.errors.append((segment_id, error))

    def submit_task(self, task_fn, task_id=None):
        task_fn()
        return task_id


class TtsTextNormalizationTests(APITestCase):
    def test_strips_artefacts_and_emotions(self):
        raw = "He paused [laughs] and smiled (chuckles). *sigh* 🔥😂"
        cleaned = tts_script.normalize_tts_text(raw)
        self.assertNotIn('[laughs]', cleaned)
        self.assertNotIn('(chuckles)', cleaned)
        self.assertNotIn('*sigh*', cleaned)
        self.assertNotIn('🔥', cleaned)
        self.assertNotIn('😂', cleaned)
        self.assertIn('He paused', cleaned)

    def test_removes_stage_directions(self):
        cleaned = tts_script.normalize_tts_text(
            '[Music swells] The city wakes. (Visual: map zoom) People move.'
        )
        self.assertNotIn('Music', cleaned)
        self.assertNotIn('Visual', cleaned)
        self.assertIn('The city wakes', cleaned)

    def test_expands_years_and_dates(self):
        self.assertEqual(
            tts_script.year_to_words(1984), 'nineteen eighty-four'
        )
        self.assertEqual(tts_script.year_to_words(2005), 'two thousand five')
        self.assertEqual(tts_script.year_to_words(2024), 'twenty twenty-four')
        cleaned = tts_script.normalize_tts_text('In 1984 and 2024.')
        self.assertIn('nineteen eighty-four', cleaned)
        self.assertIn('twenty twenty-four', cleaned)

    def test_expands_quantities_and_fractions(self):
        cleaned = tts_script.normalize_tts_text(
            'It cost $5.2M, weighed 150kg, rose 40% and covered 3.14 miles, '
            'about 1/2 of the route.'
        )
        self.assertIn('five point two million dollars', cleaned)
        self.assertIn('one hundred fifty kilograms', cleaned)
        self.assertIn('forty percent', cleaned)
        self.assertIn('three point one four', cleaned)
        self.assertIn('one half', cleaned)

    def test_expands_ordinals_abbreviations_and_initialisms(self):
        cleaned = tts_script.normalize_tts_text(
            'Dr. Smith met the CIA in the 21st century vs. the FBI.'
        )
        self.assertIn('Doctor Smith', cleaned)
        self.assertIn('C-I-A', cleaned)
        self.assertIn('F-B-I', cleaned)
        self.assertIn('twenty-first century', cleaned)
        self.assertIn('versus', cleaned)

    def test_keeps_spoken_acronyms(self):
        cleaned = tts_script.normalize_tts_text('NASA and NATO met today.')
        self.assertIn('NASA', cleaned)
        self.assertIn('NATO', cleaned)

    def test_punctuation_is_tts_friendly(self):
        cleaned = tts_script.normalize_tts_text(
            'Wait—he said; "then leave"… and he did.'
        )
        self.assertNotIn('—', cleaned)
        self.assertNotIn(';', cleaned)
        self.assertNotIn('"', cleaned)
        self.assertNotIn('…', cleaned)

    def test_is_idempotent(self):
        once = tts_script.normalize_tts_text(
            'In 1984, the CIA spent $5.2M—about 40% (laughs).'
        )
        twice = tts_script.normalize_tts_text(once)
        self.assertEqual(once, twice)

    def test_prepare_falls_back_to_source_when_cleanup_is_empty(self):
        self.assertEqual(tts_script.prepare_tts_text('🔥😂'), '🔥😂')
        self.assertEqual(tts_script.prepare_tts_text(''), '')


class TtsScriptEndpointTests(APITestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.tmp)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))

        self.account = Account.objects.create(name='TTS Account')
        self.project = Project.objects.create(
            title='TTS Project', account=self.account
        )
        self.segment = Segment.objects.create(
            project=self.project,
            sequence_index=0,
            text_content='In 1984 the CIA arrived. [laughs]',
        )
        settings_obj = GlobalSettings.load()
        settings_obj.ai_default_model = 'test-model'
        settings_obj.ai_base_url = 'http://localhost:1234/v1'
        settings_obj.ai_api_key = ''
        settings_obj.save()

    @patch('core_engine.ai_client.chat_completion')
    def test_single_block_rewrite_persists_tts_text(self, mock_chat):
        mock_chat.return_value = (
            'In nineteen eighty-four the C-I-A arrived.'
        )
        response = self.client.post(
            f'/api/segments/{self.segment.id}/generate-tts-script/'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data['tts_text'],
            'In nineteen eighty-four the C-I-A arrived.',
        )
        self.segment.refresh_from_db()
        self.assertEqual(
            self.segment.tts_text,
            'In nineteen eighty-four the C-I-A arrived.',
        )
        # The subtitle version must never change.
        self.assertEqual(
            self.segment.text_content, 'In 1984 the CIA arrived. [laughs]'
        )

    @patch('core_engine.ai_client.chat_completion', return_value='')
    def test_empty_model_reply_is_rejected(self, _mock_chat):
        response = self.client.post(
            f'/api/segments/{self.segment.id}/generate-tts-script/'
        )
        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.segment.refresh_from_db()
        self.assertEqual(self.segment.tts_text, '')

    def test_missing_model_config_returns_400(self):
        settings_obj = GlobalSettings.load()
        settings_obj.ai_default_model = ''
        settings_obj.save()
        self.account.ai_model = ''
        self.account.save()
        response = self.client.post(
            f'/api/segments/{self.segment.id}/generate-tts-script/'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_locked_segment_cannot_generate_tts_text(self):
        self.segment.is_locked = True
        self.segment.save()
        response = self.client.post(
            f'/api/segments/{self.segment.id}/generate-tts-script/'
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    @patch('core_engine.ai_client.chat_completion')
    def test_batch_generation_rewrites_every_block(self, mock_chat):
        other = Segment.objects.create(
            project=self.project,
            sequence_index=1,
            text_content='The year 2024 was quiet.',
        )
        mock_chat.side_effect = [
            'In nineteen eighty-four the C-I-A arrived.',
            'The year twenty twenty-four was quiet.',
        ]
        manager = InlineTaskManager()
        with patch('api.views.get_task_manager', return_value=manager):
            response = self.client.post(
                f'/api/projects/{self.project.id}/generate-all-tts-scripts/',
                {'only_missing': True},
                format='json',
            )
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data['segments_to_process'], 2)
        self.segment.refresh_from_db()
        other.refresh_from_db()
        self.assertIn('nineteen eighty-four', self.segment.tts_text)
        self.assertIn('twenty twenty-four', other.tts_text)
        self.assertEqual(len(manager.completed), 2)

    @patch('core_engine.ai_client.chat_completion', return_value='Rewritten.')
    def test_batch_skips_blocks_that_already_have_tts_text(self, _mock_chat):
        self.segment.tts_text = 'Existing spoken text.'
        self.segment.save()
        manager = InlineTaskManager()
        with patch('api.views.get_task_manager', return_value=manager):
            response = self.client.post(
                f'/api/projects/{self.project.id}/generate-all-tts-scripts/',
                format='json',
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['segments_to_process'], 0)
        self.segment.refresh_from_db()
        self.assertEqual(self.segment.tts_text, 'Existing spoken text.')


class TtsUsesSpokenTextTests(APITestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.tmp)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))

        self.account = Account.objects.create(name='Audio Account')
        self.project = Project.objects.create(
            title='Audio Project', account=self.account
        )
        self.segment = Segment.objects.create(
            project=self.project,
            sequence_index=0,
            text_content='In 1984 the CIA arrived.',
            tts_text='In nineteen eighty-four the C-I-A arrived.',
        )
        GlobalSettings.load()

    @patch('core_engine.model_loader.KokoroModelLoader.is_model_available', return_value=True)
    @patch('core_engine.tts.synthesize')
    def test_single_generation_uses_normalized_tts_text(
        self, mock_synthesize, _mock_model
    ):
        mock_synthesize.return_value = {
            'success': True,
            'duration': 1.5,
            'engine': 'kokoro',
        }
        manager = InlineTaskManager()
        with patch('api.views.get_task_manager', return_value=manager):
            response = self.client.post(
                f'/api/segments/{self.segment.id}/generate-audio/'
            )
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        spoken = mock_synthesize.call_args.args[0]
        self.assertIn('nineteen eighty-four', spoken)
        self.assertIn('C-I-A', spoken)
        self.assertNotIn('1984', spoken)

    @patch('core_engine.model_loader.KokoroModelLoader.is_model_available', return_value=True)
    @patch('core_engine.tts.synthesize')
    def test_legacy_block_falls_back_to_cleaned_subtitle_text(
        self, mock_synthesize, _mock_model
    ):
        self.segment.tts_text = ''
        self.segment.text_content = 'In 1984 [laughs] the CIA arrived.'
        self.segment.save()
        mock_synthesize.return_value = {
            'success': True,
            'duration': 1.5,
            'engine': 'kokoro',
        }
        manager = InlineTaskManager()
        with patch('api.views.get_task_manager', return_value=manager):
            self.client.post(
                f'/api/segments/{self.segment.id}/generate-audio/'
            )
        spoken = mock_synthesize.call_args.args[0]
        self.assertIn('nineteen eighty-four', spoken)
        self.assertNotIn('[laughs]', spoken)
