"""Per-account settings tests (Issue #9).

The settings page is scoped to the active account: each Facebook page /
YouTube channel keeps its own TTS, subtitle and render configuration.  New
accounts inherit the current workspace defaults once, then diverge.
"""

import os
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import Account, AccountSettings, GlobalSettings, Project

SETTINGS_URL = '/api/settings/'
FONT_UPLOAD_URL = '/api/settings/font/upload/'
TEMP_MEDIA_ROOT = tempfile.mkdtemp()


class AccountSettingsAPITests(APITestCase):
    def setUp(self):
        GlobalSettings.objects.all().delete()
        self.global_settings = GlobalSettings.load()
        self.fb = Account.objects.create(name='Page One', section='facebook')
        self.fb_other = Account.objects.create(name='Page Two', section='facebook')
        self.yt = Account.objects.create(name='Channel One', section='youtube')

    # ── Defaults / isolation ──────────────────────────────────────────────

    def test_account_settings_are_seeded_from_global_defaults(self):
        self.global_settings.subtitle_font_size = 70
        self.global_settings.default_voice_id = 'am_adam'
        self.global_settings.save()

        response = self.client.get(
            f'{SETTINGS_URL}?section=facebook&account={self.fb.id}'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['subtitle_font_size'], 70)
        self.assertEqual(response.data['default_voice_id'], 'am_adam')
        self.assertTrue(
            AccountSettings.objects.filter(account=self.fb).exists()
        )

    def test_patch_updates_only_the_requested_account(self):
        url_a = f'{SETTINGS_URL}?section=facebook&account={self.fb.id}'
        url_b = f'{SETTINGS_URL}?section=facebook&account={self.fb_other.id}'

        response = self.client.patch(
            url_a,
            {
                'subtitle_font_size': 88,
                'subtitle_font_color': '#00FF00',
                'default_voice_id': 'bf_emma',
                'render_width': 1280,
                'render_height': 720,
                'render_fps': 24,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Same section, different account → untouched defaults.
        other = self.client.get(url_b)
        self.assertEqual(other.data['subtitle_font_size'], 48)
        self.assertEqual(other.data['default_voice_id'], 'af_bella')

        # Different section → untouched defaults.
        youtube = self.client.get(
            f'{SETTINGS_URL}?section=youtube&account={self.yt.id}'
        )
        self.assertEqual(youtube.data['subtitle_font_size'], 48)

        # Global (no account) endpoint stays separate.
        global_response = self.client.get(SETTINGS_URL)
        self.assertEqual(global_response.data['subtitle_font_size'], 48)

    def test_duplicate_reads_do_not_create_duplicate_rows(self):
        url = f'{SETTINGS_URL}?section=facebook&account={self.fb.id}'
        self.client.get(url)
        self.client.get(url)
        self.assertEqual(
            AccountSettings.objects.filter(account=self.fb).count(), 1
        )

    def test_validation_still_applies_to_account_settings(self):
        url = f'{SETTINGS_URL}?section=facebook&account={self.fb.id}'
        response = self.client.patch(
            url, {'subtitle_font_size': 500}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ── Projects inherit account settings ─────────────────────────────────

    def test_imported_project_uses_account_settings(self):
        url = f'{SETTINGS_URL}?section=facebook&account={self.fb.id}'
        self.client.patch(
            url,
            {
                'subtitle_font_size': 77,
                'default_voice_id': 'am_liam',
                'render_width': 1080,
                'render_height': 1920,
                'render_fps': 60,
                'subtitles_enabled': False,
            },
            format='json',
        )

        response = self.client.post(
            f'/api/projects/import/?section=facebook&account={self.fb.id}',
            {
                'format': 'json',
                'title': 'Account project',
                'segments': [{'text_content': 'Hello', 'image_prompt': ''}],
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        project = Project.objects.get(pk=response.data['id'])
        self.assertEqual(project.subtitle_font_size, 77)
        self.assertEqual(project.default_voice_id, 'am_liam')
        self.assertEqual(project.resolution_width, 1080)
        self.assertEqual(project.resolution_height, 1920)
        self.assertEqual(project.framerate, 60)
        self.assertFalse(project.subtitles_enabled)

    def test_created_project_uses_account_settings(self):
        self.client.patch(
            f'{SETTINGS_URL}?section=youtube&account={self.yt.id}',
            {'subtitle_font_size': 64, 'render_width': 1280, 'render_height': 720},
            format='json',
        )
        response = self.client.post(
            f'/api/projects/?section=youtube&account={self.yt.id}',
            {'title': 'Channel project', 'section': 'youtube'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        project = Project.objects.get(pk=response.data['id'])
        self.assertEqual(project.subtitle_font_size, 64)
        self.assertEqual(project.resolution_width, 1280)
        self.assertEqual(project.resolution_height, 720)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class AccountFontUploadTests(APITestCase):
    def setUp(self):
        GlobalSettings.objects.all().delete()
        GlobalSettings.load()
        self.fb = Account.objects.create(name='Page One', section='facebook')
        self.fb_other = Account.objects.create(name='Page Two', section='facebook')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def test_font_upload_is_account_scoped(self):
        font = SimpleUploadedFile(
            'AccountFont.ttf', b'\x00' * 64, content_type='font/ttf'
        )
        response = self.client.post(
            f'{FONT_UPLOAD_URL}?section=facebook&account={self.fb.id}',
            {'font': font},
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('AccountFont.ttf', response.data['custom_font_file'])
        self.assertIn(str(self.fb.id), response.data['custom_font_file'])
        self.assertEqual(response.data['subtitle_font_family'], 'AccountFont')

        # The other account still has no custom font.
        other = self.client.get(
            f'{SETTINGS_URL}?section=facebook&account={self.fb_other.id}'
        )
        self.assertIsNone(other.data['custom_font_file'])

        # Global settings were not modified.
        global_response = self.client.get(SETTINGS_URL)
        self.assertIsNone(global_response.data['custom_font_file'])

        expected = os.path.join(
            TEMP_MEDIA_ROOT, 'fonts', str(self.fb.id), 'AccountFont.ttf'
        )
        self.assertTrue(os.path.isfile(expected))
