"""Section isolation tests (Issue #6).

StoryFlow hosts two independent workspaces — Facebook Reels and YouTube
Videos.  These tests guarantee that project, segment and gallery data can
never bleed from one workspace into the other.
"""

import os
import tempfile
import shutil
from unittest.mock import patch

from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import Project, Segment, GlobalSettings

TEMP_MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class SectionIsolationTests(APITestCase):
    def setUp(self):
        GlobalSettings.load()
        self.facebook = Project.objects.create(title='FB Project', section='facebook')
        self.youtube = Project.objects.create(title='YT Project', section='youtube')
        self.fb_segment = Segment.objects.create(
            project=self.facebook, sequence_index=0, text_content='fb'
        )
        self.yt_segment = Segment.objects.create(
            project=self.youtube, sequence_index=0, text_content='yt'
        )

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    # ── Project list / detail ──────────────────────────────────────────

    def test_list_projects_is_scoped_by_section(self):
        fb = self.client.get('/api/projects/?section=facebook')
        yt = self.client.get('/api/projects/?section=youtube')

        self.assertEqual(fb.status_code, status.HTTP_200_OK)
        self.assertEqual(yt.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [p['id'] for p in fb.data['results']], [str(self.facebook.id)]
        )
        self.assertEqual(
            [p['id'] for p in yt.data['results']], [str(self.youtube.id)]
        )

    def test_list_without_section_keeps_legacy_behaviour(self):
        response = self.client.get('/api/projects/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)

    def test_detail_is_not_visible_from_other_section(self):
        cross = self.client.get(
            f'/api/projects/{self.facebook.id}/?section=youtube'
        )
        own = self.client.get(
            f'/api/projects/{self.facebook.id}/?section=facebook'
        )
        self.assertEqual(cross.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(own.status_code, status.HTTP_200_OK)
        self.assertEqual(own.data['section'], 'facebook')

    def test_invalid_section_is_rejected(self):
        response = self.client.get('/api/projects/?section=instagram')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_project_uses_requested_section(self):
        response = self.client.post(
            '/api/projects/?section=youtube',
            {'title': 'New YT', 'section': 'youtube'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['section'], 'youtube')

    def test_create_project_rejects_cross_section_payload(self):
        response = self.client.post(
            '/api/projects/?section=facebook',
            {'title': 'Mismatch', 'section': 'youtube'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Project.objects.filter(title='Mismatch').exists())

    def test_import_project_is_section_scoped(self):
        response = self.client.post(
            '/api/projects/import/?section=youtube',
            {
                'format': 'json',
                'title': 'Imported YT',
                'section': 'youtube',
                'segments': [
                    {'text_content': 'One', 'image_prompt': 'scene'},
                ],
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['section'], 'youtube')

    # ── Segments ───────────────────────────────────────────────────────

    def test_segment_list_is_section_scoped(self):
        fb = self.client.get(
            f'/api/segments/?project={self.facebook.id}&section=facebook'
        )
        cross = self.client.get(
            f'/api/segments/?project={self.facebook.id}&section=youtube'
        )
        self.assertEqual(fb.status_code, status.HTTP_200_OK)
        self.assertEqual(len(fb.data['results']), 1)
        self.assertEqual(cross.status_code, status.HTTP_200_OK)
        self.assertEqual(len(cross.data['results']), 0)

    def test_segment_detail_is_not_visible_from_other_section(self):
        cross = self.client.get(
            f'/api/segments/{self.fb_segment.id}/?section=youtube'
        )
        own = self.client.get(
            f'/api/segments/{self.fb_segment.id}/?section=facebook'
        )
        self.assertEqual(cross.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(own.status_code, status.HTTP_200_OK)

    def test_segment_cannot_be_created_in_other_section(self):
        response = self.client.post(
            '/api/segments/?section=youtube',
            {'project': str(self.facebook.id), 'text_content': 'leak'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            Segment.objects.filter(text_content='leak').count(), 0
        )

    # ── Gallery ────────────────────────────────────────────────────────

    def test_gallery_is_section_scoped(self):
        # Both projects are COMPLETED and resolve to an existing dummy file.
        dummy = os.path.join(TEMP_MEDIA_ROOT, 'dummy.mp4')
        with open(dummy, 'wb') as f:
            f.write(b'not-a-real-video')
        Project.objects.filter(pk=self.facebook.pk).update(status='COMPLETED')
        Project.objects.filter(pk=self.youtube.pk).update(status='COMPLETED')

        with patch('api.views._resolve_video_path', return_value=dummy):
            fb = self.client.get('/api/gallery/?section=facebook')
            yt = self.client.get('/api/gallery/?section=youtube')

        self.assertEqual(fb.status_code, status.HTTP_200_OK)
        self.assertEqual(yt.status_code, status.HTTP_200_OK)
        self.assertEqual([i['id'] for i in fb.data], [str(self.facebook.id)])
        self.assertEqual([i['id'] for i in yt.data], [str(self.youtube.id)])

    def test_gallery_stream_rejects_other_section(self):
        dummy = os.path.join(TEMP_MEDIA_ROOT, 'dummy-stream.mp4')
        with open(dummy, 'wb') as f:
            f.write(b'not-a-real-video')
        Project.objects.filter(pk=self.facebook.pk).update(status='COMPLETED')

        with patch('api.views._resolve_video_path', return_value=dummy):
            cross = self.client.get(
                f'/api/gallery/{self.facebook.id}/stream/?section=youtube'
            )
            own = self.client.get(
                f'/api/gallery/{self.facebook.id}/stream/?section=facebook'
            )

        self.assertEqual(cross.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(own.status_code, status.HTTP_200_OK)
