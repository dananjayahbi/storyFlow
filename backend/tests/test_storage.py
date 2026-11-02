"""Storage layout tests (Issue #7).

Assets must live under ``Storage/<Section>/<project-id>/`` with per-project
JSON snapshots, scripts, images, audio, outputs and upscaled images.
"""

import io
import json
import os
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase
from PIL import Image as PILImage

from api.models import GlobalSettings, Project, Segment
from api.storage import migrate_legacy_storage
from core_engine.render_utils import get_output_path
from core_engine.tts_wrapper import construct_audio_path


class StorageLayoutTests(APITestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.tmp)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))
        GlobalSettings.load()

    def _project(self, section='facebook', title='Storage Test'):
        return Project.objects.create(title=title, section=section)

    def test_project_folder_and_artifacts_are_created(self):
        project = self._project('youtube')
        folder = os.path.join(self.tmp, 'YouTube', str(project.account_id), str(project.id))

        self.assertTrue(os.path.isdir(folder))
        self.assertTrue(os.path.isfile(os.path.join(folder, 'project.json')))
        self.assertTrue(os.path.isfile(os.path.join(folder, 'script.txt')))

        with open(os.path.join(folder, 'project.json'), encoding='utf-8') as f:
            snapshot = json.load(f)
        self.assertEqual(snapshot['id'], str(project.id))
        self.assertEqual(snapshot['section'], 'youtube')

    def test_segment_changes_refresh_json_and_script(self):
        project = self._project('facebook')
        Segment.objects.create(
            project=project, sequence_index=0, text_content='First line'
        )
        Segment.objects.create(
            project=project, sequence_index=1, text_content='Second line'
        )

        folder = os.path.join(self.tmp, 'Facebook', str(project.account_id), str(project.id))
        with open(os.path.join(folder, 'project.json'), encoding='utf-8') as f:
            snapshot = json.load(f)
        with open(os.path.join(folder, 'script.txt'), encoding='utf-8') as f:
            script = f.read()

        self.assertEqual(len(snapshot['segments']), 2)
        self.assertEqual(snapshot['segments'][0]['text_content'], 'First line')
        self.assertIn('First line', script)
        self.assertIn('Second line', script)

    def test_image_upload_uses_section_folder(self):
        project = self._project('youtube')
        segment = Segment.objects.create(
            project=project, sequence_index=0, text_content='x'
        )

        buffer = io.BytesIO()
        PILImage.new('RGB', (10, 10), 'red').save(buffer, format='JPEG')
        upload = SimpleUploadedFile(
            'scene.jpg', buffer.getvalue(), content_type='image/jpeg'
        )

        response = self.client.post(
            f'/api/segments/{segment.id}/upload-image/',
            {'image': upload},
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        segment.refresh_from_db()
        self.assertTrue(segment.image_file.name.startswith(
            f'YouTube/{project.account_id}/{project.id}/images/'
        ))
        self.assertTrue(os.path.isfile(segment.image_file.path))

    def test_audio_and_output_paths_are_section_scoped(self):
        project = self._project('youtube')

        audio = construct_audio_path(str(project.id), 'seg-1')
        output = get_output_path(str(project.id))

        self.assertEqual(
            os.path.normpath(str(audio)),
            os.path.normpath(
                os.path.join(
                    self.tmp, 'YouTube', str(project.account_id), str(project.id), 'audio', 'seg-1.wav'
                )
            ),
        )
        self.assertEqual(
            os.path.normpath(output),
            os.path.normpath(
                os.path.join(
                    self.tmp, 'YouTube', str(project.account_id), str(project.id), 'output', 'final.mp4'
                )
            ),
        )

    def test_import_writes_story_and_project_json(self):
        response = self.client.post(
            '/api/projects/import/?section=facebook',
            {
                'format': 'json',
                'title': 'Imported Story',
                'section': 'facebook',
                'segments': [
                    {'text_content': 'Hello', 'image_prompt': 'A scene'},
                ],
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        project = Project.objects.get(title='Imported Story')
        folder = os.path.join(self.tmp, 'Facebook', str(project.account_id), str(project.id))
        self.assertTrue(os.path.isfile(os.path.join(folder, 'story.json')))

        with open(os.path.join(folder, 'story.json'), encoding='utf-8') as f:
            story = json.load(f)
        self.assertEqual(story['title'], 'Imported Story')
        self.assertEqual(len(story['segments']), 1)

        with open(os.path.join(folder, 'project.json'), encoding='utf-8') as f:
            snapshot = json.load(f)
        self.assertEqual(len(snapshot['segments']), 1)

    def test_referenced_logo_is_copied_into_project_assets(self):
        from api.models import Logo

        project = self._project('facebook')
        buffer = io.BytesIO()
        PILImage.new('RGB', (12, 12), 'blue').save(buffer, format='PNG')
        logo = Logo.objects.create(
            name='Brand',
            file=SimpleUploadedFile(
                'brand.png', buffer.getvalue(), content_type='image/png'
            ),
        )
        project.active_logo = logo
        project.save(update_fields=['active_logo'])

        copied = os.path.join(
            self.tmp, 'Facebook', str(project.account_id), str(project.id), 'assets', 'brand.png'
        )
        self.assertTrue(os.path.isfile(copied))

    def test_legacy_media_migration(self):
        legacy = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(legacy, ignore_errors=True))

        project = self._project('facebook')
        segment = Segment.objects.create(
            project=project,
            sequence_index=0,
            text_content='Legacy',
            image_file=f'projects/{project.id}/images/old.jpg',
            audio_file=f'projects/{project.id}/audio/old.wav',
        )
        project.output_path = f'projects/{project.id}/output/final.mp4'
        project.save(update_fields=['output_path'])

        # Build the old media/projects layout.
        for relative in (
            f'projects/{project.id}/images/old.jpg',
            f'projects/{project.id}/audio/old.wav',
            f'projects/{project.id}/output/final.mp4',
            'logos/logo.png',
        ):
            path = os.path.join(legacy, *relative.split('/'))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'wb') as f:
                f.write(b'data')

        report = migrate_legacy_storage(legacy)

        self.assertEqual(report['projects'], 1)
        segment.refresh_from_db()
        project.refresh_from_db()
        self.assertEqual(
            segment.image_file.name,
            f'Facebook/{project.account_id}/{project.id}/images/old.jpg',
        )
        self.assertEqual(
            segment.audio_file.name,
            f'Facebook/{project.account_id}/{project.id}/audio/old.wav',
        )
        self.assertEqual(
            project.output_path,
            f'Facebook/{project.account_id}/{project.id}/output/final.mp4',
        )
        self.assertTrue(os.path.isfile(segment.image_file.path))
        self.assertTrue(os.path.isfile(segment.audio_file.path))
        self.assertTrue(os.path.isfile(os.path.join(self.tmp, 'logos', 'logo.png')))
        self.assertTrue(
            os.path.isfile(
                os.path.join(self.tmp, 'Facebook', str(project.account_id), str(project.id), 'project.json')
            )
        )

