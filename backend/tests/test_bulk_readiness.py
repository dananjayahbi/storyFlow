"""Bulk Create preflight endpoint: exact, file-aware render readiness."""

import os
import shutil
import tempfile
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import Account, Project, Segment

TEMP_MEDIA_ROOT = tempfile.mkdtemp()


def png_upload(name):
    buffer = BytesIO()
    Image.new('RGB', (4, 4), (20, 120, 90)).save(buffer, format='PNG')
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/png')


def audio_upload(name):
    return SimpleUploadedFile(name, b'ID3-bulk-readiness', content_type='audio/mpeg')


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class BulkReadinessTests(APITestCase):
    def setUp(self):
        self.account = Account.objects.create(name='Bulk Page', section='facebook')
        self.other_account = Account.objects.create(
            name='Other Bulk Page', section='facebook'
        )
        self.scope = f'?section=facebook&account={self.account.id}'

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def _project(self, title, account=None, status='DRAFT'):
        return Project.objects.create(
            title=title,
            section='facebook',
            account=account or self.account,
            status=status,
        )

    def _segment(self, project, index, *, image=True, audio=True):
        return Segment.objects.create(
            project=project,
            sequence_index=index,
            text_content=f'Segment {index}',
            image_file=png_upload(f'image-{index}.png') if image else None,
            audio_file=audio_upload(f'audio-{index}.mp3') if audio else None,
        )

    def _results(self):
        response = self.client.get(f'/api/projects/render-readiness/{self.scope}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return {item['project_id']: item for item in response.data['results']}

    def test_ready_project_passes_and_missing_media_is_reported(self):
        ready = self._project('Ready')
        self._segment(ready, 1)
        self._segment(ready, 2)

        missing_image = self._project('Missing image')
        self._segment(missing_image, 1, image=False)

        missing_audio = self._project('Missing audio')
        self._segment(missing_audio, 1, audio=False)

        results = self._results()

        self.assertTrue(results[str(ready.id)]['ready'])
        self.assertTrue(results[str(ready.id)]['renderable'])
        self.assertFalse(results[str(ready.id)]['is_processing'])
        self.assertEqual(results[str(ready.id)]['segment_count'], 2)

        not_ready = results[str(missing_image.id)]
        self.assertFalse(not_ready['ready'])
        self.assertTrue(not_ready['renderable'])
        self.assertEqual(len(not_ready['missing_images']), 1)
        self.assertEqual(not_ready['missing_audio'], [])

        self.assertFalse(results[str(missing_audio.id)]['ready'])
        self.assertEqual(len(results[str(missing_audio.id)]['missing_audio']), 1)

    def test_missing_file_on_disk_is_not_ready(self):
        project = self._project('Deleted media')
        segment = self._segment(project, 1)
        os.remove(segment.image_file.path)

        result = self._results()[str(project.id)]

        self.assertFalse(result['ready'])
        self.assertEqual(len(result['missing_images']), 1)
        self.assertIn('missing image', result['message'].lower())

    def test_empty_and_processing_projects(self):
        empty = self._project('Empty')
        processing = self._project('Rendering', status='PROCESSING')
        self._segment(processing, 1)

        results = self._results()

        self.assertFalse(results[str(empty.id)]['ready'])
        self.assertEqual(results[str(empty.id)]['segment_count'], 0)

        self.assertTrue(results[str(processing.id)]['is_processing'])
        self.assertFalse(results[str(processing.id)]['ready'])
        self.assertFalse(results[str(processing.id)]['renderable'])

    def test_only_the_selected_account_projects_are_returned(self):
        own = self._project('Own account')
        self._segment(own, 1)
        other = self._project('Other account', account=self.other_account)
        self._segment(other, 1)

        results = self._results()

        self.assertIn(str(own.id), results)
        self.assertNotIn(str(other.id), results)
