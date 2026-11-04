"""Project cover thumbnails and the persisted Projects page layout."""

import os
import shutil
import tempfile
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import Account, AccountSettings, Project, Segment

TEMP_MEDIA_ROOT = tempfile.mkdtemp()


def png_upload(name):
    buffer = BytesIO()
    Image.new('RGB', (4, 4), (20, 120, 90)).save(buffer, format='PNG')
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/png')


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class ProjectPresentationTests(APITestCase):
    def setUp(self):
        self.account = Account.objects.create(
            name='Presentation Page', section='facebook'
        )
        self.project = Project.objects.create(
            title='Cover Story',
            section='facebook',
            account=self.account,
        )
        self.scope = (
            f'?section=facebook&account={self.account.id}'
        )

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def _project_payload(self):
        response = self.client.get(f'/api/projects/{self.scope}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        projects = response.data['results']
        return next(
            item
            for item in projects
            if item['id'] == str(self.project.id)
        )

    def test_thumbnail_falls_back_to_first_segment_image(self):
        Segment.objects.create(
            project=self.project,
            sequence_index=2,
            text_content='second',
            image_file=png_upload('second.png'),
        )
        Segment.objects.create(
            project=self.project,
            sequence_index=1,
            text_content='first',
            image_file=png_upload('first.png'),
        )

        payload = self._project_payload()

        self.assertEqual(payload['thumbnail_source'], 'segment')
        self.assertFalse(payload['has_manual_thumbnail'])
        self.assertIsNone(payload['manual_thumbnail_url'])
        self.assertIn(
            f'Facebook/{self.account.id}/{self.project.id}/images/first.png',
            payload['thumbnail_url'],
        )

    def test_manual_thumbnail_wins_and_can_be_removed(self):
        Segment.objects.create(
            project=self.project,
            sequence_index=1,
            text_content='first',
            image_file=png_upload('first.png'),
        )

        response = self.client.patch(
            f'/api/projects/{self.project.id}/{self.scope}',
            {'thumbnail': png_upload('cover.png')},
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['thumbnail_source'], 'manual')
        self.assertTrue(response.data['has_manual_thumbnail'])
        self.assertIn(
            f'Facebook/{self.account.id}/{self.project.id}/thumbnail.png',
            response.data['thumbnail_url'],
        )

        self.project.refresh_from_db()
        stored = self.project.thumbnail.path
        self.assertTrue(os.path.isfile(stored))

        removed = self.client.patch(
            f'/api/projects/{self.project.id}/{self.scope}',
            {'thumbnail': None},
            format='json',
        )
        self.assertEqual(removed.status_code, status.HTTP_200_OK)
        self.assertEqual(removed.data['thumbnail_source'], 'segment')
        self.assertFalse(removed.data['has_manual_thumbnail'])
        self.assertIn('/images/first.png', removed.data['thumbnail_url'])

    def test_project_without_images_has_no_thumbnail(self):
        payload = self._project_payload()
        self.assertIsNone(payload['thumbnail_url'])
        self.assertIsNone(payload['thumbnail_source'])

    def test_projects_view_mode_is_saved_per_account(self):
        response = self.client.get(f'/api/settings/{self.scope}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['projects_view_mode'], 'table')

        updated = self.client.patch(
            f'/api/settings/{self.scope}',
            {'projects_view_mode': 'tiles'},
            format='json',
        )
        self.assertEqual(updated.status_code, status.HTTP_200_OK)
        self.assertEqual(updated.data['projects_view_mode'], 'tiles')

        reloaded = self.client.get(f'/api/settings/{self.scope}')
        self.assertEqual(reloaded.data['projects_view_mode'], 'tiles')
        self.assertEqual(
            AccountSettings.objects.get(account=self.account).projects_view_mode,
            'tiles',
        )

    def test_projects_view_mode_rejects_unknown_values(self):
        response = self.client.patch(
            f'/api/settings/{self.scope}',
            {'projects_view_mode': 'carousel'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
