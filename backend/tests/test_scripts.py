"""Script Craft + Script Library tests.

Covers the per-account AI configuration, AI generation endpoint (with the
network client mocked) and account-scoped script library CRUD.
"""

from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APITestCase

from api.models import Account, GlobalSettings, Script
from core_engine.ai_client import (
    AIClientError,
    normalize_script,
)

AI_SETTINGS_URL = '/api/settings/ai/'
GENERATE_URL = '/api/script-craft/generate/'
SCRIPTS_URL = '/api/scripts/'

SAMPLE_SCRIPT = {
    'title': 'The Hidden Ocean',
    'segments': [
        {'text_content': 'The sea is deeper than we imagine.', 'image_prompt': 'Cinematic ocean'},
        {'text_content': 'Light dies a hundred meters down.', 'image_prompt': 'Dark water'},
    ],
}


class AISettingsTests(APITestCase):
    def setUp(self):
        GlobalSettings.load()
        self.fb = Account.objects.create(name='Page One', section='facebook')
        self.fb_other = Account.objects.create(name='Page Two', section='facebook')
        self.yt = Account.objects.create(name='Channel One', section='youtube')

    def test_ai_settings_require_account(self):
        response = self.client.get(AI_SETTINGS_URL)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_ai_settings_return_shared_defaults(self):
        response = self.client.get(f'{AI_SETTINGS_URL}?section=facebook&account={self.fb.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['model'], '')
        self.assertEqual(response.data['base_url'], 'http://localhost:11434/v1')
        self.assertFalse(response.data['apply_to_all'])

    def test_ai_settings_are_account_specific(self):
        self.client.patch(
            f'{AI_SETTINGS_URL}?section=facebook&account={self.fb.id}',
            {'model': 'model-a', 'system_prompt': 'Voice A'},
            format='json',
        )
        self.client.patch(
            f'{AI_SETTINGS_URL}?section=facebook&account={self.fb_other.id}',
            {'model': 'model-b', 'system_prompt': 'Voice B'},
            format='json',
        )
        self.fb.refresh_from_db()
        self.fb_other.refresh_from_db()
        self.assertEqual(self.fb.ai_model, 'model-a')
        self.assertEqual(self.fb_other.ai_model, 'model-b')
        self.assertEqual(self.fb.ai_system_prompt, 'Voice A')

    def test_apply_to_all_replaces_every_account_model(self):
        self.fb_other.ai_model = 'old-model'
        self.fb_other.save(update_fields=['ai_model'])
        self.yt.ai_model = 'old-model'
        self.yt.save(update_fields=['ai_model'])

        response = self.client.patch(
            f'{AI_SETTINGS_URL}?section=facebook&account={self.fb.id}',
            {'model': 'shared-model', 'apply_to_all': True},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['apply_to_all'])
        for account in (self.fb, self.fb_other, self.yt):
            account.refresh_from_db()
            self.assertEqual(account.ai_model, 'shared-model')
        # Applying the model must not wipe per-account prompts.
        self.assertEqual(self.fb_other.ai_system_prompt, '')

    def test_temperature_is_validated(self):
        response = self.client.patch(
            f'{AI_SETTINGS_URL}?section=facebook&account={self.fb.id}',
            {'temperature': 9},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ScriptGenerationTests(APITestCase):
    def setUp(self):
        GlobalSettings.load()
        self.account = Account.objects.create(name='Writer', section='youtube')
        self.url = f'{GENERATE_URL}?section=youtube&account={self.account.id}'

    def test_generation_requires_pitch(self):
        response = self.client.post(self.url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_generation_requires_configured_model(self):
        response = self.client.post(
            self.url, {'pitch': 'A documentary about rain'}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('AI model', response.data['error'])

    def test_generation_returns_parsed_script(self):
        self.account.ai_model = 'test-model'
        self.account.save(update_fields=['ai_model'])

        with patch('core_engine.ai_client.generate_script', return_value={
            'script': SAMPLE_SCRIPT,
            'raw': '{}',
            'model': 'test-model',
        }) as mocked:
            response = self.client.post(
                self.url,
                {
                    'pitch': 'A short film about the ocean',
                    'history': [
                        {'role': 'user', 'content': 'Make it cinematic'},
                        {'role': 'assistant', 'content': 'Sure.'},
                    ],
                },
                format='json',
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['script']['title'], 'The Hidden Ocean')
        self.assertEqual(response.data['segment_count'], 2)
        self.assertIn('Drafted', response.data['reply'])
        mocked.assert_called_once()
        kwargs = mocked.call_args.kwargs
        self.assertEqual(kwargs['model'], 'test-model')
        self.assertEqual(len(kwargs['history']), 2)

    def test_generation_maps_client_errors_to_502(self):
        self.account.ai_model = 'test-model'
        self.account.save(update_fields=['ai_model'])

        with patch(
            'core_engine.ai_client.generate_script',
            side_effect=AIClientError('endpoint down'),
        ):
            response = self.client.post(
                self.url, {'pitch': 'Anything'}, format='json'
            )

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertIn('endpoint down', response.data['error'])


class ScriptLibraryTests(APITestCase):
    def setUp(self):
        GlobalSettings.load()
        self.fb = Account.objects.create(name='Page One', section='facebook')
        self.fb_other = Account.objects.create(name='Page Two', section='facebook')
        self.yt = Account.objects.create(name='Channel One', section='youtube')

    def _create(self, account, title='Ocean script'):
        return self.client.post(
            f'{SCRIPTS_URL}?section={account.section}&account={account.id}',
            {
                'title': title,
                'pitch': 'A short documentary',
                'content': SAMPLE_SCRIPT,
                'model_used': 'test-model',
            },
            format='json',
        )

    def test_save_requires_account(self):
        response = self.client.post(
            f'{SCRIPTS_URL}?section=facebook',
            {'title': 'X', 'content': SAMPLE_SCRIPT},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_save_and_list_are_account_scoped(self):
        response = self._create(self.fb)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['segment_count'], 2)
        self.assertEqual(response.data['model_used'], 'test-model')

        self._create(self.fb_other, title='Other script')

        listing = self.client.get(
            f'{SCRIPTS_URL}?section=facebook&account={self.fb.id}'
        )
        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        titles = [item['title'] for item in listing.data['results']]
        self.assertEqual(titles, ['Ocean script'])

    def test_cross_section_script_is_hidden(self):
        script = Script.objects.create(
            account=self.fb,
            section='facebook',
            title='Facebook only',
            content=SAMPLE_SCRIPT,
        )
        response = self.client.get(
            f'{SCRIPTS_URL}/{script.id}/?section=youtube&account={self.yt.id}'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_script(self):
        created = self._create(self.fb).data
        response = self.client.delete(
            f'/api/scripts/{created["id"]}/?section=facebook&account={self.fb.id}'
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Script.objects.filter(pk=created['id']).exists())

    def test_content_validation_rejects_empty_segments(self):
        response = self.client.post(
            f'{SCRIPTS_URL}?section=facebook&account={self.fb.id}',
            {'title': 'Broken', 'content': {'title': 'Broken', 'segments': []}},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class AIClientParsingTests(APITestCase):
    def test_normalize_accepts_code_fences_and_aliases(self):
        script = normalize_script({
            'title': 'Alias script',
            'segments': [
                {'text': 'First beat', 'image': 'A first image'},
                {'narration': 'Second beat', 'prompt': 'A second image'},
            ],
        })
        self.assertEqual(script['title'], 'Alias script')
        self.assertEqual(script['segments'][0]['text_content'], 'First beat')
        self.assertEqual(script['segments'][1]['image_prompt'], 'A second image')

    def test_normalize_rejects_empty_scripts(self):
        with self.assertRaises(AIClientError):
            normalize_script({'title': 'Empty', 'segments': []})
