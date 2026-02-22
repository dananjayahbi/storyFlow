"""
Task 05.03.16 — Write End-to-End Tests

Comprehensive E2E integration tests exercising the complete StoryFlow
workflow: project creation → segment management → audio generation →
video rendering, plus settings persistence and error-path coverage.
"""

import os
import shutil
import tempfile
import time
from unittest.mock import patch, MagicMock

from django.conf import settings as django_settings
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import GlobalSettings, Project, Segment, STATUS_PROCESSING

# ── Temp media root for file-based tests ──
TEMP_MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class EndToEndWorkflowTests(APITestCase):
    """E2E tests validating cross-component integration."""

    # ──────────────────── helpers ────────────────────

    def setUp(self):
        Project.objects.all().delete()
        Segment.objects.all().delete()
        GlobalSettings.objects.all().delete()

        # Re-create the settings singleton
        GlobalSettings.load()

        # Ensure temp media dirs exist
        os.makedirs(os.path.join(TEMP_MEDIA_ROOT, 'projects'), exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        if os.path.isdir(TEMP_MEDIA_ROOT):
            shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def _import_project(self, title='Test Story', num_segments=2):
        """Import a project with *num_segments* segments via the API."""
        segments = [
            {
                'text_content': f'Segment {i} narration text.',
                'image_prompt': f'A scenic view {i}',
                'sequence_index': i,
            }
            for i in range(num_segments)
        ]
        return self.client.post(
            '/api/projects/import/',
            {'format': 'json', 'title': title, 'segments': segments},
            format='json',
        )

    def _provision_segment_files(self, project_id):
        """Create dummy image + audio files for every segment in *project_id*."""
        segments = Segment.objects.filter(project_id=project_id).order_by(
            'sequence_index'
        )
        proj_dir = os.path.join(TEMP_MEDIA_ROOT, 'projects', str(project_id))
        img_dir = os.path.join(proj_dir, 'images')
        aud_dir = os.path.join(proj_dir, 'audio')
        os.makedirs(img_dir, exist_ok=True)
        os.makedirs(aud_dir, exist_ok=True)

        for seg in segments:
            # Image file
            img_name = f'{seg.id}.png'
            img_path = os.path.join(img_dir, img_name)
            with open(img_path, 'wb') as f:
                f.write(b'\x89PNG\r\n\x1a\n' + b'\x00' * 50)
            seg.image_file.name = f'projects/{project_id}/images/{img_name}'

            # Audio file
            aud_name = f'{seg.id}.wav'
            aud_path = os.path.join(aud_dir, aud_name)
            with open(aud_path, 'wb') as f:
                f.write(b'RIFF' + b'\x00' * 40)
            seg.audio_file.name = f'projects/{project_id}/audio/{aud_name}'
            seg.audio_duration = 3.5
            seg.save()

    # ──────────────────── Step 2 — Happy Path ────────────────────

    @patch('api.views.render_task_function')
    @patch('core_engine.render_utils.check_ffmpeg', return_value=True)
    def test_complete_happy_path(self, _mock_ffmpeg, mock_render):
        """Full workflow: import → provision files → render → verify."""

        # 1. Create project via import
        resp = self._import_project(title='My E2E Story', num_segments=2)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        project_id = resp.json()['id']
        segments = resp.json()['segments']
        self.assertEqual(len(segments), 2)

        # 2. Verify segments are accessible
        seg_resp = self.client.get(f'/api/segments/?project={project_id}')
        self.assertEqual(seg_resp.status_code, status.HTTP_200_OK)
        seg_list = seg_resp.json()
        # Handle DRF pagination if configured
        if isinstance(seg_list, dict) and 'results' in seg_list:
            seg_list = seg_list['results']
        self.assertEqual(len(seg_list), 2)

        # 3. Provision image + audio files (simulates TTS + image upload)
        self._provision_segment_files(project_id)

        # 4. Verify segments now have files
        for seg_data in seg_list:
            seg = Segment.objects.get(pk=seg_data['id'])
            self.assertTrue(seg.image_file)
            self.assertTrue(seg.audio_file)

        # 5. Trigger render
        render_resp = self.client.post(f'/api/projects/{project_id}/render/')
        self.assertEqual(render_resp.status_code, status.HTTP_202_ACCEPTED)
        data = render_resp.json()
        self.assertEqual(data['status'], 'PROCESSING')
        self.assertEqual(data['total_segments'], 2)
        self.assertIn('task_id', data)
        self.assertEqual(data['project_id'], str(project_id))

        # 6. Verify project status changed to PROCESSING in the database
        project = Project.objects.get(pk=project_id)
        self.assertEqual(project.status, 'PROCESSING')

        # 7. Verify render_task_function was dispatched with correct args
        # (The actual render runs in a background thread via TaskManager;
        #  we confirm it was called by the mock.)
        time.sleep(0.3)
        mock_render.assert_called_once_with(
            str(project_id), f'render_{project_id}'
        )

    # ──────────────────── Step 3 — Settings Persistence ────────────────────

    def test_settings_persist_across_requests(self):
        """PATCH settings, then fresh GET returns the saved values."""
        custom = {
            'subtitle_font_family': 'Courier New',
            'subtitle_font_size': 72,
            'subtitle_font_color': '#00FF00',
            'subtitle_position': 'top',
            'render_width': 1280,
            'render_height': 720,
            'render_fps': 24,
            'ken_burns_zoom': 1.8,
            'transition_duration': 1.5,
        }

        patch_resp = self.client.patch(
            '/api/settings/', custom, format='json'
        )
        self.assertEqual(patch_resp.status_code, status.HTTP_200_OK)

        # Fresh GET — no in-memory state should leak
        get_resp = self.client.get('/api/settings/')
        data = get_resp.json()

        for key, value in custom.items():
            self.assertEqual(
                data[key], value,
                msg=f'{key}: expected {value}, got {data[key]}',
            )

    @patch('api.views.render_task_function')
    @patch('core_engine.render_utils.check_ffmpeg', return_value=True)
    def test_settings_affect_rendering(self, _mock_ffmpeg, mock_render):
        """Updated settings are visible when render pipeline reads them."""
        # Change resolution
        self.client.patch(
            '/api/settings/',
            {'render_width': 3840, 'render_height': 2160, 'render_fps': 60},
            format='json',
        )

        # Import + provision
        resp = self._import_project(num_segments=1)
        project_id = resp.json()['id']
        self._provision_segment_files(project_id)

        # Render
        self.client.post(f'/api/projects/{project_id}/render/')

        # Verify settings object reflects the update
        settings = GlobalSettings.load()
        self.assertEqual(settings.render_width, 3840)
        self.assertEqual(settings.render_height, 2160)
        self.assertEqual(settings.render_fps, 60)

    # ──────────────────── Step 4 — Error Paths ────────────────────

    @patch('core_engine.render_utils.check_ffmpeg', return_value=True)
    def test_render_with_no_segments(self, _mock_ffmpeg):
        """Rendering a project with zero segments returns 400."""
        resp = self.client.post(
            '/api/projects/',
            {'title': 'Empty Project'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        project_id = resp.json()['id']

        render_resp = self.client.post(
            f'/api/projects/{project_id}/render/'
        )
        self.assertEqual(render_resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('no segments', render_resp.json()['message'].lower())

    @patch('core_engine.render_utils.check_ffmpeg', return_value=True)
    def test_render_with_missing_audio(self, _mock_ffmpeg):
        """Rendering segments without audio files returns 400."""
        resp = self._import_project(num_segments=2)
        project_id = resp.json()['id']

        # Only provision images, NOT audio
        segments = Segment.objects.filter(project_id=project_id)
        proj_dir = os.path.join(TEMP_MEDIA_ROOT, 'projects', str(project_id))
        img_dir = os.path.join(proj_dir, 'images')
        os.makedirs(img_dir, exist_ok=True)

        for seg in segments:
            img_name = f'{seg.id}.png'
            img_path = os.path.join(img_dir, img_name)
            with open(img_path, 'wb') as f:
                f.write(b'\x89PNG' + b'\x00' * 50)
            seg.image_file.name = f'projects/{project_id}/images/{img_name}'
            seg.save()

        render_resp = self.client.post(
            f'/api/projects/{project_id}/render/'
        )
        self.assertEqual(render_resp.status_code, status.HTTP_400_BAD_REQUEST)
        data = render_resp.json()
        self.assertEqual(len(data['missing_audio']), 2)

    def test_invalid_import_data(self):
        """Importing with missing required fields returns 400."""
        # Missing segments entirely
        resp = self.client.post(
            '/api/projects/import/',
            {'format': 'json', 'title': 'Bad Import'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_project_deletion_cascading(self):
        """Deleting a project removes its segments via CASCADE."""
        resp = self._import_project(num_segments=3)
        project_id = resp.json()['id']
        segment_ids = [s['id'] for s in resp.json()['segments']]

        self.assertEqual(Segment.objects.filter(project_id=project_id).count(), 3)

        # Delete the project
        del_resp = self.client.delete(f'/api/projects/{project_id}/')
        self.assertEqual(del_resp.status_code, status.HTTP_204_NO_CONTENT)

        # Segments should be gone
        self.assertEqual(Segment.objects.filter(project_id=project_id).count(), 0)

        # Accessing deleted segments returns 404
        for sid in segment_ids:
            seg_resp = self.client.get(f'/api/segments/{sid}/')
            self.assertEqual(seg_resp.status_code, status.HTTP_404_NOT_FOUND)

    # ──────────────────── Step 5 — Concurrent Render Blocking ────────────────────

    @patch('core_engine.render_utils.check_ffmpeg', return_value=True)
    def test_concurrent_render_blocking(self, _mock_ffmpeg):
        """Second render request is rejected while project is PROCESSING."""
        resp = self._import_project(num_segments=1)
        project_id = resp.json()['id']
        self._provision_segment_files(project_id)

        # Manually set project to PROCESSING (simulates in-flight render)
        project = Project.objects.get(pk=project_id)
        project.status = STATUS_PROCESSING
        project.save(update_fields=['status'])

        # Attempt a second render
        render_resp = self.client.post(
            f'/api/projects/{project_id}/render/'
        )
        self.assertEqual(render_resp.status_code, status.HTTP_409_CONFLICT)
        self.assertIn('already being rendered', render_resp.json()['error'])
