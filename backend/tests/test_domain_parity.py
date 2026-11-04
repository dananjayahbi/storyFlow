"""Facebook and YouTube workspaces expose the same features and stay isolated."""

import os
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import (
    Account,
    AccountSettings,
    BGMClip,
    ChatSession,
    Project,
    Rendering,
    Script,
)

TEMP_MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class DomainParityTests(APITestCase):
    def setUp(self):
        self.fb = Account.objects.create(name='Parity FB', section='facebook')
        self.yt = Account.objects.create(name='Parity YT', section='youtube')
        self.fb_project = Project.objects.create(
            title='FB Project', section='facebook', account=self.fb
        )
        self.yt_project = Project.objects.create(
            title='YT Project', section='youtube', account=self.yt
        )
        Script.objects.create(
            title='FB Script', section='facebook', account=self.fb,
            content={'segments': []},
        )
        Script.objects.create(
            title='YT Script', section='youtube', account=self.yt,
            content={'segments': []},
        )
        ChatSession.objects.create(
            title='FB Chat', section='facebook', account=self.fb
        )
        ChatSession.objects.create(
            title='YT Chat', section='youtube', account=self.yt
        )
        BGMClip.objects.create(
            name='FB track', section='facebook', account=self.fb,
            file=SimpleUploadedFile('fb.mp3', b'ID3-fb'),
        )
        BGMClip.objects.create(
            name='YT track', section='youtube', account=self.yt,
            file=SimpleUploadedFile('yt.mp3', b'ID3-yt'),
        )
        self.fb_rendering = self._rendering(self.fb_project, 'fb.mp4')
        self.yt_rendering = self._rendering(self.yt_project, 'yt.mp4')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def _rendering(self, project, name):
        relative = (
            f'{project.section.title()}/{project.account_id}/'
            f'{project.id}/renderings/{name}'
        )
        absolute = os.path.join(TEMP_MEDIA_ROOT, relative)
        os.makedirs(os.path.dirname(absolute), exist_ok=True)
        with open(absolute, 'wb') as handle:
            handle.write(b'video')
        return Rendering.objects.create(
            project=project,
            title=project.title,
            file_path=relative,
            file_size=5,
        )

    def _scope(self, section, account):
        return f'?section={section}&account={account.id}'

    def test_accounts_projects_and_gallery_are_mirrored_and_isolated(self):
        fb_accounts = self.client.get(f'/api/accounts/{self._scope("facebook", self.fb)}')
        yt_accounts = self.client.get(f'/api/accounts/{self._scope("youtube", self.yt)}')
        fb_names = [item['name'] for item in fb_accounts.data['results']]
        yt_names = [item['name'] for item in yt_accounts.data['results']]
        self.assertIn('Parity FB', fb_names)
        self.assertNotIn('Parity YT', fb_names)
        self.assertIn('Parity YT', yt_names)
        self.assertNotIn('Parity FB', yt_names)

        fb_projects = self.client.get(f'/api/projects/{self._scope("facebook", self.fb)}')
        yt_projects = self.client.get(f'/api/projects/{self._scope("youtube", self.yt)}')
        self.assertEqual(
            [item['title'] for item in fb_projects.data['results']],
            ['FB Project'],
        )
        self.assertEqual(
            [item['title'] for item in yt_projects.data['results']],
            ['YT Project'],
        )

        fb_gallery = self.client.get(f'/api/gallery/{self._scope("facebook", self.fb)}')
        yt_gallery = self.client.get(f'/api/gallery/{self._scope("youtube", self.yt)}')
        self.assertEqual([item['id'] for item in fb_gallery.data], [str(self.fb_rendering.id)])
        self.assertEqual([item['id'] for item in yt_gallery.data], [str(self.yt_rendering.id)])

        cross = self.client.get(
            f'/api/projects/{self.fb_project.id}/{self._scope("youtube", self.yt)}'
        )
        self.assertEqual(cross.status_code, status.HTTP_404_NOT_FOUND)

    def test_scripts_chat_and_bgm_libraries_are_mirrored_and_isolated(self):
        scripts = self.client.get(f'/api/scripts/{self._scope("youtube", self.yt)}')
        self.assertEqual([item['title'] for item in scripts.data['results']], ['YT Script'])

        chats = self.client.get(f'/api/chat/sessions/{self._scope("youtube", self.yt)}')
        self.assertEqual([item['title'] for item in chats.data['results']], ['YT Chat'])

        bgm = self.client.get(f'/api/bgm/{self._scope("youtube", self.yt)}')
        self.assertEqual([item['name'] for item in bgm.data['results']], ['YT track'])

        cross_bgm = self.client.get(f'/api/bgm/{self._scope("facebook", self.yt)}')
        self.assertEqual(cross_bgm.status_code, status.HTTP_400_BAD_REQUEST)

    def test_settings_are_account_scoped_and_do_not_leak_between_domains(self):
        fb_scope = self._scope('facebook', self.fb)
        yt_scope = self._scope('youtube', self.yt)

        updated = self.client.patch(
            f'/api/settings/{yt_scope}',
            {'tts_speed': 1.35, 'projects_view_mode': 'tiles'},
            format='json',
        )
        self.assertEqual(updated.status_code, status.HTTP_200_OK)
        self.assertEqual(updated.data['tts_speed'], 1.35)

        fb_settings = self.client.get(f'/api/settings/{fb_scope}')
        self.assertNotEqual(fb_settings.data['tts_speed'], 1.35)
        self.assertEqual(fb_settings.data['projects_view_mode'], 'table')

        self.assertEqual(
            AccountSettings.objects.get(account=self.yt).projects_view_mode,
            'tiles',
        )

    def test_bulk_readiness_and_import_work_on_the_youtube_side(self):
        readiness = self.client.get(
            f'/api/projects/render-readiness/{self._scope("youtube", self.yt)}'
        )
        self.assertEqual(readiness.status_code, status.HTTP_200_OK)
        ids = [item['project_id'] for item in readiness.data['results']]
        self.assertEqual(ids, [str(self.yt_project.id)])

        imported = self.client.post(
            f'/api/projects/import/{self._scope("youtube", self.yt)}',
            {
                'format': 'json',
                'title': 'Imported YT Story',
                'segments': [{'text_content': 'One', 'image_prompt': 'scene'}],
            },
            format='json',
        )
        self.assertEqual(imported.status_code, status.HTTP_201_CREATED)
        self.assertEqual(imported.data['section'], 'youtube')
        self.assertEqual(imported.data['account'], self.yt.id)
