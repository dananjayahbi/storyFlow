"""Audio Mix settings and the Settings-page demo playground."""

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
from core_engine.music_generator import apply_music_echo

PLAYGROUND_URL = '/api/settings/playground/'
GENERATE_URL = '/api/settings/playground/generate/'
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

    def test_saving_mix_updates_existing_projects_only_in_the_account(self):
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

        self.project.refresh_from_db()
        self.assertEqual(self.project.bgm_gain_db, -24)
        self.assertEqual(self.project.bgm_ducking_db, -8)
        self.assertEqual(self.project.bgm_echo_percent, 35)
        self.assertEqual(self.project.tts_gain_db, 4)

        other_project.refresh_from_db()
        self.assertEqual(other_project.bgm_gain_db, -18)
        self.assertEqual(other_project.tts_gain_db, 0)

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
