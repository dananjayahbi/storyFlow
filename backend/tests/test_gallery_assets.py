"""Tests for Gallery asset management (multiple renderings + statuses)."""

import os
import shutil
import tempfile

from django.conf import settings
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import Account, Project, Rendering

TEMP_MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class GalleryAssetTests(APITestCase):
    def setUp(self):
        self.account = Account.objects.create(name='Gallery Page', section='facebook')
        self.project = Project.objects.create(
            title='Launch Story',
            section='facebook',
            account=self.account,
            status='COMPLETED',
        )
        self.other_project = Project.objects.create(
            title='Second Story',
            section='facebook',
            account=self.account,
            status='COMPLETED',
        )

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def _rendering(
        self, project, status='rendered', name='asset.mp4',
        render_time_seconds=None,
    ):
        relative = f'Facebook/{self.account.id}/{project.id}/renderings/{name}'
        absolute = os.path.join(settings.MEDIA_ROOT, relative)
        os.makedirs(os.path.dirname(absolute), exist_ok=True)
        with open(absolute, 'wb') as handle:
            handle.write(b'video-bytes')
        return Rendering.objects.create(
            project=project,
            title=project.title,
            file_path=relative,
            status=status,
            file_size=len(b'video-bytes'),
            render_time_seconds=render_time_seconds,
        )

    def test_list_returns_multiple_renderings_per_project(self):
        first = self._rendering(self.project, name='one.mp4')
        second = self._rendering(self.project, name='two.mp4')

        response = self.client.get('/api/gallery/?section=facebook')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {item['id'] for item in response.data}
        self.assertEqual(ids, {str(first.id), str(second.id)})
        self.assertTrue(
            all(item['project_id'] == str(self.project.id) for item in response.data)
        )

    def test_list_exposes_render_time_seconds(self):
        rendering = self._rendering(
            self.project, name='timed.mp4', render_time_seconds=125.5,
        )

        response = self.client.get('/api/gallery/?section=facebook')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        item = next(
            entry for entry in response.data
            if entry['id'] == str(rendering.id)
        )
        self.assertEqual(item['render_time_seconds'], 125.5)

    def test_project_detail_exposes_latest_render_time_seconds(self):
        rendering = self._rendering(
            self.project, name='latest.mp4', render_time_seconds=91.25,
        )

        response = self.client.get(
            f'/api/projects/{self.project.id}/'
            f'?section=facebook&account={self.account.id}'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        latest = response.data['latest_rendering']
        self.assertEqual(latest['id'], str(rendering.id))
        self.assertEqual(latest['render_time_seconds'], 91.25)
        self.assertEqual(latest['status'], 'rendered')

    def test_filter_by_project_status_and_search(self):
        rendered = self._rendering(self.project, name='rendered.mp4')
        published = self._rendering(
            self.other_project, status='published', name='published.mp4'
        )

        by_project = self.client.get(
            f'/api/gallery/?section=facebook&project={self.project.id}'
        )
        self.assertEqual([item['id'] for item in by_project.data], [str(rendered.id)])

        by_status = self.client.get(
            '/api/gallery/?section=facebook&status=published'
        )
        self.assertEqual([item['id'] for item in by_status.data], [str(published.id)])

        by_search = self.client.get('/api/gallery/?section=facebook&q=second')
        self.assertEqual([item['id'] for item in by_search.data], [str(published.id)])

    def test_bulk_status_updates_and_sets_published_at(self):
        first = self._rendering(self.project, name='one.mp4')
        second = self._rendering(self.project, name='two.mp4')

        response = self.client.post(
            '/api/gallery/bulk-status/',
            {'ids': [str(first.id), str(second.id)], 'status': 'published'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['updated'], 2)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.status, 'published')
        self.assertEqual(second.status, 'published')
        self.assertIsNotNone(first.published_at)

    def test_bulk_delete_removes_rows_and_files(self):
        first = self._rendering(self.project, name='one.mp4')
        second = self._rendering(self.project, name='two.mp4')
        first_path = os.path.join(settings.MEDIA_ROOT, first.file_path)
        second_path = os.path.join(settings.MEDIA_ROOT, second.file_path)

        response = self.client.post(
            '/api/gallery/bulk-delete/',
            {'ids': [str(first.id), str(second.id)]},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['deleted'], 2)
        self.assertFalse(Rendering.objects.exists())
        self.assertFalse(os.path.exists(first_path))
        self.assertFalse(os.path.exists(second_path))

    def test_register_rendering_moves_export_into_renderings_folder(self):
        from api.renderings import register_rendering

        source_relative = (
            f'Facebook/{self.account.id}/{self.project.id}/output/final.mp4'
        )
        source = os.path.join(settings.MEDIA_ROOT, source_relative)
        os.makedirs(os.path.dirname(source), exist_ok=True)
        with open(source, 'wb') as handle:
            handle.write(b'fresh-export')

        rendering = register_rendering(
            self.project,
            source,
            duration=12.5,
            segment_count=3,
            render_time_seconds=42.75,
        )

        self.assertTrue(os.path.isfile(source) is False)
        target = os.path.join(settings.MEDIA_ROOT, rendering.file_path)
        self.assertTrue(os.path.isfile(target))
        self.assertTrue(rendering.file_path.endswith(f'{rendering.id}.mp4'))
        self.assertEqual(rendering.status, 'rendered')
        self.assertEqual(rendering.duration, 12.5)
        self.assertEqual(rendering.render_time_seconds, 42.75)
        self.project.refresh_from_db()
        self.assertEqual(self.project.output_path, rendering.file_path)

    def test_single_delete_clears_project_output(self):
        rendering = self._rendering(self.project, name='only.mp4')
        self.project.output_path = rendering.file_path
        self.project.save(update_fields=['output_path'])

        response = self.client.delete(f'/api/gallery/{rendering.id}/')

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.project.refresh_from_db()
        self.assertEqual(self.project.output_path, '')
        self.assertEqual(self.project.status, 'DRAFT')
