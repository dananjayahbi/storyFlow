from django.test import TestCase
from django.test import override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase
from rest_framework import status

import io
import os
import shutil
import tempfile

from PIL import Image as PILImage

from api.parsers import JSONParser, TextParser, ParseError
from api.validators import validate_import_data
from api.models import Project, Segment


class TestJSONParser(TestCase):
    """Tests for JSONParser.parse()."""

    def setUp(self):
        self.parser = JSONParser()

    def test_valid_json_with_two_segments(self):
        """Valid JSON with title and 2 segments → normalized output."""
        data = {
            'title': 'Test Story',
            'segments': [
                {'text_content': 'Segment one', 'image_prompt': 'Prompt one'},
                {'text_content': 'Segment two', 'image_prompt': 'Prompt two'},
            ],
        }
        result = self.parser.parse(data)
        self.assertEqual(result['title'], 'Test Story')
        self.assertEqual(len(result['segments']), 2)
        self.assertEqual(result['segments'][0]['sequence_index'], 0)
        self.assertEqual(result['segments'][1]['sequence_index'], 1)

    def test_missing_title_raises_parse_error(self):
        data = {'segments': [{'text_content': 'Text'}]}
        with self.assertRaises(ParseError):
            self.parser.parse(data)

    def test_empty_segments_raises_parse_error(self):
        data = {'title': 'Title', 'segments': []}
        with self.assertRaises(ParseError):
            self.parser.parse(data)

    def test_missing_text_content_raises_parse_error(self):
        data = {'title': 'Title', 'segments': [{'image_prompt': 'Prompt'}]}
        with self.assertRaises(ParseError):
            self.parser.parse(data)

    def test_missing_image_prompt_defaults_to_empty(self):
        data = {'title': 'Title', 'segments': [{'text_content': 'Text'}]}
        result = self.parser.parse(data)
        self.assertEqual(result['segments'][0]['image_prompt'], '')

    def test_extra_keys_ignored(self):
        data = {
            'title': 'Title',
            'author': 'Ignored',
            'segments': [{'text_content': 'Text', 'image_prompt': 'P', 'mood': 'dark'}],
        }
        result = self.parser.parse(data)
        self.assertNotIn('author', result)
        self.assertNotIn('mood', result['segments'][0])


class TestTextParser(TestCase):
    """Tests for TextParser.parse()."""

    def setUp(self):
        self.parser = TextParser()

    def test_valid_text_with_two_blocks(self):
        raw = "Text: Segment one\nPrompt: Prompt one\n---\nText: Segment two\nPrompt: Prompt two"
        result = self.parser.parse('Test Story', raw)
        self.assertEqual(len(result['segments']), 2)
        self.assertEqual(result['segments'][0]['text_content'], 'Segment one')
        self.assertEqual(result['segments'][1]['sequence_index'], 1)

    def test_empty_raw_text_raises_parse_error(self):
        with self.assertRaises(ParseError):
            self.parser.parse('Title', '')

    def test_block_without_text_raises_parse_error(self):
        raw = "Prompt: Only a prompt here"
        with self.assertRaises(ParseError):
            self.parser.parse('Title', raw)

    def test_missing_prompt_defaults_to_empty(self):
        raw = "Text: Just narration text"
        result = self.parser.parse('Title', raw)
        self.assertEqual(result['segments'][0]['image_prompt'], '')

    def test_multiple_text_lines_concatenated(self):
        raw = "Text: Line one\nText: Line two\nPrompt: A prompt"
        result = self.parser.parse('Title', raw)
        self.assertEqual(result['segments'][0]['text_content'], 'Line one Line two')

    def test_consecutive_delimiters_skipped(self):
        raw = "Text: Segment one\nPrompt: P1\n---\n---\nText: Segment two\nPrompt: P2"
        result = self.parser.parse('Title', raw)
        self.assertEqual(len(result['segments']), 2)

    def test_case_insensitive_prefixes(self):
        raw = "text: Lower case text\nprompt: Lower case prompt"
        result = self.parser.parse('Title', raw)
        self.assertEqual(result['segments'][0]['text_content'], 'Lower case text')
        self.assertEqual(result['segments'][0]['image_prompt'], 'Lower case prompt')


class TestImportValidator(TestCase):
    """Tests for validate_import_data()."""

    def test_valid_data_passes(self):
        data = {
            'title': 'Valid Title',
            'segments': [
                {'text_content': 'Text', 'image_prompt': 'Prompt', 'sequence_index': 0},
            ],
        }
        result = validate_import_data(data)
        self.assertEqual(result, data)

    def test_title_over_200_chars_raises_error(self):
        data = {
            'title': 'A' * 201,
            'segments': [{'text_content': 'T', 'image_prompt': '', 'sequence_index': 0}],
        }
        from rest_framework.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            validate_import_data(data)

    def test_empty_segments_raises_error(self):
        data = {'title': 'Title', 'segments': []}
        from rest_framework.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            validate_import_data(data)

    def test_empty_text_content_raises_error(self):
        data = {
            'title': 'Title',
            'segments': [{'text_content': '', 'image_prompt': '', 'sequence_index': 0}],
        }
        from rest_framework.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            validate_import_data(data)

    def test_non_contiguous_indices_raises_error(self):
        data = {
            'title': 'Title',
            'segments': [
                {'text_content': 'A', 'image_prompt': '', 'sequence_index': 0},
                {'text_content': 'B', 'image_prompt': '', 'sequence_index': 5},
            ],
        }
        from rest_framework.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            validate_import_data(data)


class TestImportEndpoint(APITestCase):
    """Integration tests for POST /api/projects/import/."""

    def test_json_import_creates_project_with_segments(self):
        payload = {
            'format': 'json',
            'title': 'Imported Story',
            'segments': [
                {'text_content': 'First segment', 'image_prompt': 'Forest scene'},
                {'text_content': 'Second segment', 'image_prompt': 'Mountain scene'},
            ],
        }
        response = self.client.post('/api/projects/import/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['title'], 'Imported Story')
        self.assertEqual(len(response.data['segments']), 2)
        self.assertEqual(response.data['segments'][0]['sequence_index'], 0)
        self.assertEqual(response.data['segments'][1]['sequence_index'], 1)

    def test_text_import_creates_project_with_segments(self):
        payload = {
            'format': 'text',
            'title': 'Text Story',
            'raw_text': 'Text: First segment\nPrompt: Forest\n---\nText: Second segment\nPrompt: Mountain',
        }
        response = self.client.post('/api/projects/import/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data['segments']), 2)

    def test_invalid_json_returns_400(self):
        payload = {'format': 'json', 'title': '', 'segments': []}
        response = self.client.post('/api/projects/import/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_text_returns_400(self):
        payload = {'format': 'text', 'title': 'Title', 'raw_text': ''}
        response = self.client.post('/api/projects/import/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_atomicity_no_partial_data_on_failure(self):
        """If import fails, neither Project nor Segments are created."""
        initial_projects = Project.objects.count()
        initial_segments = Segment.objects.count()
        payload = {'format': 'json', 'title': '', 'segments': []}
        self.client.post('/api/projects/import/', payload, format='json')
        self.assertEqual(Project.objects.count(), initial_projects)
        self.assertEqual(Segment.objects.count(), initial_segments)

    def test_sequence_index_values_correct(self):
        payload = {
            'format': 'json',
            'title': 'Indexed Story',
            'segments': [
                {'text_content': 'A', 'image_prompt': ''},
                {'text_content': 'B', 'image_prompt': ''},
                {'text_content': 'C', 'image_prompt': ''},
            ],
        }
        response = self.client.post('/api/projects/import/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        indices = [s['sequence_index'] for s in response.data['segments']]
        self.assertEqual(indices, [0, 1, 2])


class TestEdgeCases(TestCase):
    """Edge case tests for the import pipeline."""

    def test_whitespace_only_title(self):
        parser = JSONParser()
        with self.assertRaises(ParseError):
            parser.parse({'title': '   ', 'segments': [{'text_content': 'T'}]})

    def test_whitespace_only_text_content(self):
        parser = JSONParser()
        with self.assertRaises(ParseError):
            parser.parse({'title': 'Title', 'segments': [{'text_content': '   '}]})

    def test_unicode_content(self):
        parser = JSONParser()
        result = parser.parse({
            'title': 'ストーリー 🎬',
            'segments': [{'text_content': '日本語テスト', 'image_prompt': '🌸 cherry blossoms'}],
        })
        self.assertEqual(result['title'], 'ストーリー 🎬')
        self.assertEqual(result['segments'][0]['text_content'], '日本語テスト')

    def test_large_segment_count(self):
        parser = JSONParser()
        segments = [{'text_content': f'Segment {i}', 'image_prompt': ''} for i in range(100)]
        result = parser.parse({'title': 'Big Story', 'segments': segments})
        self.assertEqual(len(result['segments']), 100)


class TestEndpointEdgeCases(APITestCase):
    """Edge case tests for the import endpoint."""

    def test_missing_format_field(self):
        response = self.client.post('/api/projects/import/', {'title': 'T'}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_invalid_format_value(self):
        response = self.client.post('/api/projects/import/', {'format': 'xml', 'title': 'T'}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_get_method_not_allowed(self):
        response = self.client.get('/api/projects/import/')
        self.assertEqual(response.status_code, 405)


class TestSegmentList(APITestCase):
    """Tests for GET /api/segments/?project={id}."""

    def setUp(self):
        self.project = Project.objects.create(title='Test Project')
        for i in range(3):
            Segment.objects.create(
                project=self.project,
                sequence_index=i,
                text_content=f'Segment {i}',
                image_prompt=f'Prompt {i}',
            )

    def test_list_segments_by_project(self):
        response = self.client.get(f'/api/segments/?project={self.project.id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 3)
        # Verify ordering
        indices = [s['sequence_index'] for s in response.data['results']]
        self.assertEqual(indices, [0, 1, 2])

    def test_list_without_project_filter_returns_empty(self):
        response = self.client.get('/api/segments/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 0)

    def test_retrieve_single_segment(self):
        seg = Segment.objects.first()
        response = self.client.get(f'/api/segments/{seg.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['id'], str(seg.id))


class TestSegmentUpdate(APITestCase):
    """Tests for PATCH /api/segments/{id}/."""

    def setUp(self):
        self.project = Project.objects.create(title='Test')
        self.segment = Segment.objects.create(
            project=self.project, sequence_index=0,
            text_content='Original', image_prompt='Original prompt',
        )

    def test_patch_text_content(self):
        response = self.client.patch(
            f'/api/segments/{self.segment.id}/',
            {'text_content': 'Updated text'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['text_content'], 'Updated text')

    def test_patch_image_prompt(self):
        response = self.client.patch(
            f'/api/segments/{self.segment.id}/',
            {'image_prompt': 'New prompt'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['image_prompt'], 'New prompt')

    def test_lock_segment(self):
        response = self.client.patch(
            f'/api/segments/{self.segment.id}/',
            {'is_locked': True},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['is_locked'])

    def test_edit_locked_segment_returns_400(self):
        self.segment.is_locked = True
        self.segment.save()
        response = self.client.patch(
            f'/api/segments/{self.segment.id}/',
            {'text_content': 'Should fail'},
            format='json',
        )
        self.assertEqual(response.status_code, 400)

    def test_unlock_locked_segment_succeeds(self):
        self.segment.is_locked = True
        self.segment.save()
        response = self.client.patch(
            f'/api/segments/{self.segment.id}/',
            {'is_locked': False},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['is_locked'])


class TestSegmentDelete(APITestCase):
    """Tests for DELETE /api/segments/{id}/."""

    def setUp(self):
        self.project = Project.objects.create(title='Test')
        self.segment = Segment.objects.create(
            project=self.project, sequence_index=0,
            text_content='Text', image_prompt='Prompt',
        )

    def test_delete_segment(self):
        response = self.client.delete(f'/api/segments/{self.segment.id}/')
        self.assertEqual(response.status_code, 204)
        self.assertEqual(Segment.objects.count(), 0)

    def test_delete_nonexistent_segment(self):
        import uuid
        fake_id = uuid.uuid4()
        response = self.client.delete(f'/api/segments/{fake_id}/')
        self.assertEqual(response.status_code, 404)


class TestSegmentReorder(APITestCase):
    """Tests for POST /api/segments/reorder/."""

    def setUp(self):
        self.project = Project.objects.create(title='Test')
        self.seg_a = Segment.objects.create(
            project=self.project, sequence_index=0, text_content='A', image_prompt='',
        )
        self.seg_b = Segment.objects.create(
            project=self.project, sequence_index=1, text_content='B', image_prompt='',
        )
        self.seg_c = Segment.objects.create(
            project=self.project, sequence_index=2, text_content='C', image_prompt='',
        )

    def test_reorder_valid(self):
        response = self.client.post('/api/segments/reorder/', {
            'project_id': self.project.id,
            'segment_order': [str(self.seg_c.id), str(self.seg_a.id), str(self.seg_b.id)],
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.seg_c.refresh_from_db()
        self.assertEqual(self.seg_c.sequence_index, 0)

    def test_reorder_missing_ids_returns_400(self):
        response = self.client.post('/api/segments/reorder/', {
            'project_id': self.project.id,
            'segment_order': [str(self.seg_a.id)],  # Missing b and c
        }, format='json')
        self.assertEqual(response.status_code, 400)

    def test_reorder_extra_ids_returns_400(self):
        import uuid
        fake_id = str(uuid.uuid4())
        response = self.client.post('/api/segments/reorder/', {
            'project_id': self.project.id,
            'segment_order': [str(self.seg_a.id), str(self.seg_b.id), str(self.seg_c.id), fake_id],
        }, format='json')
        self.assertEqual(response.status_code, 400)

    def test_reorder_wrong_project_returns_404(self):
        response = self.client.post('/api/segments/reorder/', {
            'project_id': 99999,
            'segment_order': ['fake-id-1', 'fake-id-2', 'fake-id-3'],
        }, format='json')
        self.assertEqual(response.status_code, 404)


TEMP_MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class TestProjectDelete(APITestCase):
    """Tests for DELETE /api/projects/{id}/."""

    def setUp(self):
        self.project = Project.objects.create(title='Test')
        self.segment = Segment.objects.create(
            project=self.project, sequence_index=0,
            text_content='Text', image_prompt='Prompt',
        )

    def tearDown(self):
        # Clean up temp media
        if os.path.isdir(TEMP_MEDIA):
            shutil.rmtree(TEMP_MEDIA, ignore_errors=True)
            os.makedirs(TEMP_MEDIA, exist_ok=True)

    def test_delete_project_cascades_segments(self):
        response = self.client.delete(f'/api/projects/{self.project.id}/')
        self.assertEqual(response.status_code, 204)
        self.assertEqual(Project.objects.count(), 0)
        self.assertEqual(Segment.objects.count(), 0)

    def test_delete_project_removes_media_directory(self):
        media_dir = os.path.join(TEMP_MEDIA, 'projects', str(self.project.id))
        os.makedirs(media_dir, exist_ok=True)
        # Create a dummy file
        with open(os.path.join(media_dir, 'test.jpg'), 'w') as f:
            f.write('fake')
        self.client.delete(f'/api/projects/{self.project.id}/')
        self.assertFalse(os.path.isdir(media_dir))

    def test_delete_nonexistent_project(self):
        response = self.client.delete('/api/projects/99999/')
        self.assertEqual(response.status_code, 404)


# --- Image Upload/Removal Tests ---

TEMP_MEDIA_UPLOAD = tempfile.mkdtemp()


def create_test_image(name='test.jpg', fmt='JPEG', size=(100, 100)):
    """Generate a valid in-memory image file for upload testing."""
    buf = io.BytesIO()
    img = PILImage.new('RGB', size, color='red')
    img.save(buf, format=fmt)
    buf.seek(0)
    ext_map = {'JPEG': 'image/jpeg', 'PNG': 'image/png', 'WEBP': 'image/webp'}
    content_type = ext_map.get(fmt, 'image/jpeg')
    return SimpleUploadedFile(name, buf.read(), content_type=content_type)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_UPLOAD)
class TestImageUpload(APITestCase):
    """Tests for POST /api/segments/{id}/upload-image/."""

    def setUp(self):
        self.project = Project.objects.create(title='Test')
        self.segment = Segment.objects.create(
            project=self.project, sequence_index=0,
            text_content='Text', image_prompt='Prompt',
        )

    def tearDown(self):
        if os.path.isdir(TEMP_MEDIA_UPLOAD):
            shutil.rmtree(TEMP_MEDIA_UPLOAD, ignore_errors=True)
            os.makedirs(TEMP_MEDIA_UPLOAD, exist_ok=True)

    # --- Valid format tests ---

    def test_upload_valid_jpeg(self):
        image = create_test_image('photo.jpg', 'JPEG')
        response = self.client.post(
            f'/api/segments/{self.segment.id}/upload-image/',
            {'image': image},
            format='multipart',
        )
        self.assertEqual(response.status_code, 200)
        self.segment.refresh_from_db()
        self.assertTrue(self.segment.image_file)

    def test_upload_valid_png(self):
        image = create_test_image('photo.png', 'PNG')
        response = self.client.post(
            f'/api/segments/{self.segment.id}/upload-image/',
            {'image': image},
            format='multipart',
        )
        self.assertEqual(response.status_code, 200)

    def test_upload_valid_webp(self):
        image = create_test_image('photo.webp', 'WEBP')
        response = self.client.post(
            f'/api/segments/{self.segment.id}/upload-image/',
            {'image': image},
            format='multipart',
        )
        self.assertEqual(response.status_code, 200)

    # --- Invalid file tests ---

    def test_upload_non_image_returns_400(self):
        fake_file = SimpleUploadedFile(
            'document.txt', b'Not an image', content_type='text/plain',
        )
        response = self.client.post(
            f'/api/segments/{self.segment.id}/upload-image/',
            {'image': fake_file},
            format='multipart',
        )
        self.assertEqual(response.status_code, 400)

    def test_upload_corrupt_image_returns_400(self):
        corrupt = SimpleUploadedFile(
            'corrupt.jpg', b'\xff\xd8\xff\xe0broken', content_type='image/jpeg',
        )
        response = self.client.post(
            f'/api/segments/{self.segment.id}/upload-image/',
            {'image': corrupt},
            format='multipart',
        )
        self.assertEqual(response.status_code, 400)

    def test_upload_over_20mb_returns_400(self):
        """Generate a file exceeding 20 MB with valid extension."""
        # Create data that exceeds 20MB
        data = b'\x00' * (20 * 1024 * 1024 + 1)
        oversized = SimpleUploadedFile('huge.jpg', data, content_type='image/jpeg')
        response = self.client.post(
            f'/api/segments/{self.segment.id}/upload-image/',
            {'image': oversized},
            format='multipart',
        )
        self.assertEqual(response.status_code, 400)

    # --- Lock test ---

    def test_upload_to_locked_segment_returns_400(self):
        self.segment.is_locked = True
        self.segment.save()
        image = create_test_image()
        response = self.client.post(
            f'/api/segments/{self.segment.id}/upload-image/',
            {'image': image},
            format='multipart',
        )
        self.assertEqual(response.status_code, 400)

    # --- Re-upload / cleanup test ---

    def test_reupload_removes_old_file(self):
        # First upload
        image1 = create_test_image('first.jpg', 'JPEG')
        self.client.post(
            f'/api/segments/{self.segment.id}/upload-image/',
            {'image': image1},
            format='multipart',
        )
        self.segment.refresh_from_db()
        old_path = self.segment.image_file.path if self.segment.image_file else None

        # Second upload
        image2 = create_test_image('second.jpg', 'JPEG')
        self.client.post(
            f'/api/segments/{self.segment.id}/upload-image/',
            {'image': image2},
            format='multipart',
        )
        self.segment.refresh_from_db()
        # Old file should no longer exist on disk
        if old_path:
            self.assertFalse(os.path.isfile(old_path))

    # --- Missing file test ---

    def test_upload_no_file_returns_400(self):
        response = self.client.post(
            f'/api/segments/{self.segment.id}/upload-image/',
            {},
            format='multipart',
        )
        self.assertEqual(response.status_code, 400)

    # --- Storage path test ---

    def test_stored_path_includes_project_id(self):
        image = create_test_image()
        self.client.post(
            f'/api/segments/{self.segment.id}/upload-image/',
            {'image': image},
            format='multipart',
        )
        self.segment.refresh_from_db()
        self.assertIn(str(self.project.id), self.segment.image_file.name)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_UPLOAD)
class TestImageRemoval(APITestCase):
    """Tests for DELETE /api/segments/{id}/remove-image/."""

    def setUp(self):
        self.project = Project.objects.create(title='Test')
        self.segment = Segment.objects.create(
            project=self.project, sequence_index=0,
            text_content='Text', image_prompt='Prompt',
        )

    def tearDown(self):
        if os.path.isdir(TEMP_MEDIA_UPLOAD):
            shutil.rmtree(TEMP_MEDIA_UPLOAD, ignore_errors=True)
            os.makedirs(TEMP_MEDIA_UPLOAD, exist_ok=True)

    def _upload_image(self):
        """Helper to upload an image to self.segment."""
        image = create_test_image()
        self.client.post(
            f'/api/segments/{self.segment.id}/upload-image/',
            {'image': image},
            format='multipart',
        )
        self.segment.refresh_from_db()

    def test_remove_existing_image(self):
        self._upload_image()
        old_path = self.segment.image_file.path if self.segment.image_file else None
        response = self.client.delete(
            f'/api/segments/{self.segment.id}/remove-image/',
        )
        self.assertEqual(response.status_code, 200)
        self.segment.refresh_from_db()
        self.assertFalse(bool(self.segment.image_file))
        # File should be deleted from disk
        if old_path:
            self.assertFalse(os.path.isfile(old_path))

    def test_remove_when_no_image_returns_400(self):
        response = self.client.delete(
            f'/api/segments/{self.segment.id}/remove-image/',
        )
        self.assertEqual(response.status_code, 400)

    def test_remove_locked_segment_returns_400(self):
        self._upload_image()
        self.segment.is_locked = True
        self.segment.save()
        response = self.client.delete(
            f'/api/segments/{self.segment.id}/remove-image/',
        )
        self.assertEqual(response.status_code, 400)

    def test_remove_when_file_already_missing_succeeds(self):
        """Self-healing: if DB has path but file is gone, still clears the field."""
        self._upload_image()
        # Manually delete the file from disk
        full = self.segment.image_file.path
        if os.path.isfile(full):
            os.remove(full)
        response = self.client.delete(
            f'/api/segments/{self.segment.id}/remove-image/',
        )
        self.assertEqual(response.status_code, 200)
        self.segment.refresh_from_db()
        self.assertFalse(bool(self.segment.image_file))


# ==========================================================================
# Phase 03 — Audio Generation & Task System Integration Tests
# ==========================================================================

from unittest.mock import patch, MagicMock
from api.tasks import TaskManager, TASK_PENDING, TASK_PROCESSING, TASK_COMPLETED, TASK_FAILED
from api.models import GlobalSettings

TEMP_MEDIA_AUDIO = tempfile.mkdtemp()


def _reset_task_manager():
    """Reset TaskManager singleton for test isolation."""
    TaskManager._instance = None
    tm = TaskManager()
    tm._tasks.clear()
    return tm


# --------------------------------------------------------------------------
# Generate Audio endpoint tests
# --------------------------------------------------------------------------

@override_settings(MEDIA_ROOT=TEMP_MEDIA_AUDIO)
class TestGenerateAudioEndpoint(APITestCase):
    """Tests for POST /api/segments/{id}/generate-audio/."""

    def setUp(self):
        self.tm = _reset_task_manager()
        self.project = Project.objects.create(title='Audio Test')
        self.segment = Segment.objects.create(
            project=self.project, sequence_index=0,
            text_content='Hello world.', image_prompt='Test',
        )
        GlobalSettings.objects.all().delete()
        GlobalSettings.objects.create()

    def tearDown(self):
        self.tm.shutdown(wait=True)
        _reset_task_manager()
        if os.path.isdir(TEMP_MEDIA_AUDIO):
            shutil.rmtree(TEMP_MEDIA_AUDIO, ignore_errors=True)
            os.makedirs(TEMP_MEDIA_AUDIO, exist_ok=True)

    @patch('core_engine.model_loader.KokoroModelLoader.is_model_available', return_value=True)
    @patch('core_engine.tts_wrapper.generate_audio')
    def test_generate_audio_returns_202(self, mock_gen, mock_model):
        mock_gen.return_value = {
            'success': True, 'duration': 2.5,
            'audio_path': '/fake/path.wav', 'error': None,
        }
        response = self.client.post(
            f'/api/segments/{self.segment.id}/generate-audio/',
        )
        self.assertEqual(response.status_code, 202)
        self.assertIn('task_id', response.data)
        self.assertEqual(response.data['segment_id'], str(self.segment.id))
        self.assertEqual(response.data['status'], 'PENDING')

    def test_empty_text_returns_400(self):
        self.segment.text_content = ''
        self.segment.save()
        response = self.client.post(
            f'/api/segments/{self.segment.id}/generate-audio/',
        )
        self.assertEqual(response.status_code, 400)

    def test_whitespace_text_returns_400(self):
        self.segment.text_content = '   '
        self.segment.save()
        response = self.client.post(
            f'/api/segments/{self.segment.id}/generate-audio/',
        )
        self.assertEqual(response.status_code, 400)

    def test_locked_segment_returns_409(self):
        self.segment.is_locked = True
        self.segment.save()
        response = self.client.post(
            f'/api/segments/{self.segment.id}/generate-audio/',
        )
        self.assertEqual(response.status_code, 409)

    @patch('core_engine.model_loader.KokoroModelLoader.is_model_available', return_value=False)
    def test_missing_model_returns_503(self, mock_model):
        response = self.client.post(
            f'/api/segments/{self.segment.id}/generate-audio/',
        )
        self.assertEqual(response.status_code, 503)

    def test_nonexistent_segment_returns_404(self):
        import uuid as uuid_lib
        fake_id = uuid_lib.uuid4()
        response = self.client.post(
            f'/api/segments/{fake_id}/generate-audio/',
        )
        self.assertEqual(response.status_code, 404)

    @patch('core_engine.model_loader.KokoroModelLoader.is_model_available', return_value=True)
    @patch('core_engine.tts_wrapper.generate_audio')
    def test_background_task_updates_segment(self, mock_gen, mock_model):
        """After task completion, segment audio_file and audio_duration are populated.

        Runs the task function synchronously to avoid SQLite
        thread/transaction isolation issues in the test runner.
        """
        mock_gen.return_value = {
            'success': True, 'duration': 3.14,
            'audio_path': '/fake/path.wav', 'error': None,
        }

        # Capture the task function and run it synchronously
        captured = {}
        original_submit = self.tm.submit_task

        def capture_submit(task_fn, task_id=None):
            tid = original_submit(lambda: None, task_id=task_id)  # register task only
            captured['fn'] = task_fn
            captured['tid'] = tid
            return tid

        with patch.object(self.tm, 'submit_task', side_effect=capture_submit):
            response = self.client.post(
                f'/api/segments/{self.segment.id}/generate-audio/',
            )

        # Run the actual task function synchronously in the test thread
        import time as time_mod
        time_mod.sleep(0.5)  # let no-op task finish
        captured['fn']()

        self.segment.refresh_from_db()
        self.assertIsNotNone(self.segment.audio_file)
        self.assertAlmostEqual(self.segment.audio_duration, 3.14, places=2)


# --------------------------------------------------------------------------
# Generate All Audio endpoint tests
# --------------------------------------------------------------------------

@override_settings(MEDIA_ROOT=TEMP_MEDIA_AUDIO)
class TestGenerateAllAudioEndpoint(APITestCase):
    """Tests for POST /api/projects/{id}/generate-all-audio/."""

    def setUp(self):
        self.tm = _reset_task_manager()
        self.project = Project.objects.create(title='Batch Test')
        self.seg1 = Segment.objects.create(
            project=self.project, sequence_index=0,
            text_content='Segment one.', image_prompt='P1',
        )
        self.seg2 = Segment.objects.create(
            project=self.project, sequence_index=1,
            text_content='Segment two.', image_prompt='P2',
        )
        self.seg3 = Segment.objects.create(
            project=self.project, sequence_index=2,
            text_content='Segment three.', image_prompt='P3',
        )
        GlobalSettings.objects.all().delete()
        GlobalSettings.objects.create()

    def tearDown(self):
        self.tm.shutdown(wait=True)
        _reset_task_manager()
        if os.path.isdir(TEMP_MEDIA_AUDIO):
            shutil.rmtree(TEMP_MEDIA_AUDIO, ignore_errors=True)
            os.makedirs(TEMP_MEDIA_AUDIO, exist_ok=True)

    @patch('core_engine.model_loader.KokoroModelLoader.is_model_available', return_value=True)
    @patch('core_engine.tts_wrapper.generate_audio')
    def test_generate_all_returns_202(self, mock_gen, mock_model):
        mock_gen.return_value = {
            'success': True, 'duration': 2.0,
            'audio_path': '/fake.wav', 'error': None,
        }
        response = self.client.post(
            f'/api/projects/{self.project.id}/generate-all-audio/',
        )
        self.assertEqual(response.status_code, 202)
        self.assertIn('task_id', response.data)
        self.assertEqual(response.data['segments_to_process'], 3)

    @patch('core_engine.model_loader.KokoroModelLoader.is_model_available', return_value=True)
    @patch('core_engine.tts_wrapper.generate_audio')
    def test_skip_locked_true(self, mock_gen, mock_model):
        """Locked segments are skipped when skip_locked=True."""
        mock_gen.return_value = {
            'success': True, 'duration': 2.0,
            'audio_path': '/fake.wav', 'error': None,
        }
        self.seg2.is_locked = True
        self.seg2.save()
        response = self.client.post(
            f'/api/projects/{self.project.id}/generate-all-audio/',
            {'skip_locked': True},
            format='json',
        )
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.data['segments_to_process'], 2)

    @patch('core_engine.model_loader.KokoroModelLoader.is_model_available', return_value=True)
    @patch('core_engine.tts_wrapper.generate_audio')
    def test_force_regenerate(self, mock_gen, mock_model):
        """With force_regenerate=True, segments with existing audio are re-processed."""
        mock_gen.return_value = {
            'success': True, 'duration': 2.0,
            'audio_path': '/fake.wav', 'error': None,
        }
        self.seg1.audio_file = 'projects/1/audio/existing.wav'
        self.seg1.save()
        response = self.client.post(
            f'/api/projects/{self.project.id}/generate-all-audio/',
            {'force_regenerate': True},
            format='json',
        )
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.data['segments_to_process'], 3)

    def test_no_segments_to_process_returns_200(self):
        """All segments empty → 200 with message."""
        self.seg1.text_content = ''
        self.seg2.text_content = ''
        self.seg3.text_content = ''
        self.seg1.save()
        self.seg2.save()
        self.seg3.save()
        response = self.client.post(
            f'/api/projects/{self.project.id}/generate-all-audio/',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['segments_to_process'], 0)

    def test_nonexistent_project_returns_404(self):
        response = self.client.post(
            '/api/projects/99999/generate-all-audio/',
        )
        self.assertEqual(response.status_code, 404)

    @patch('core_engine.model_loader.KokoroModelLoader.is_model_available', return_value=False)
    def test_missing_model_returns_503(self, mock_model):
        response = self.client.post(
            f'/api/projects/{self.project.id}/generate-all-audio/',
        )
        self.assertEqual(response.status_code, 503)

    @patch('core_engine.model_loader.KokoroModelLoader.is_model_available', return_value=True)
    @patch('core_engine.tts_wrapper.generate_audio')
    def test_progress_tracking(self, mock_gen, mock_model):
        """After batch completes, progress.current == progress.total.

        Runs the task function synchronously to avoid SQLite
        thread/transaction isolation issues in the test runner.
        """
        mock_gen.return_value = {
            'success': True, 'duration': 1.0,
            'audio_path': '/fake.wav', 'error': None,
        }

        # Capture the task function and run it synchronously
        captured = {}
        original_submit = self.tm.submit_task

        def capture_submit(task_fn, task_id=None):
            tid = original_submit(lambda: None, task_id=task_id)
            captured['fn'] = task_fn
            captured['tid'] = tid
            return tid

        with patch.object(self.tm, 'submit_task', side_effect=capture_submit):
            response = self.client.post(
                f'/api/projects/{self.project.id}/generate-all-audio/',
            )

        import time as time_mod
        time_mod.sleep(0.5)  # let no-op task finish
        captured['fn']()

        s = self.tm.get_task_status(captured['tid'])
        self.assertEqual(s['progress']['current'], s['progress']['total'])


# --------------------------------------------------------------------------
# Task Status endpoint tests
# --------------------------------------------------------------------------

class TestTaskStatusEndpoint(APITestCase):
    """Tests for GET /api/tasks/{task_id}/status/."""

    def setUp(self):
        self.tm = _reset_task_manager()

    def tearDown(self):
        self.tm.shutdown(wait=True)
        _reset_task_manager()

    def test_known_task_returns_200(self):
        task_id = self.tm.submit_task(lambda: None)
        import time as time_mod
        time_mod.sleep(0.5)
        response = self.client.get(f'/api/tasks/{task_id}/status/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['task_id'], task_id)
        self.assertIn('status', response.data)
        self.assertIn('progress', response.data)
        self.assertIn('completed_segments', response.data)
        self.assertIn('errors', response.data)

    def test_unknown_task_returns_404(self):
        response = self.client.get('/api/tasks/nonexistent-task-id/status/')
        self.assertEqual(response.status_code, 404)

    def test_status_transitions(self):
        """Verify task transitions PENDING → PROCESSING → COMPLETED."""
        import time as time_mod

        def slow_task():
            time_mod.sleep(1)

        task_id = self.tm.submit_task(slow_task)

        # Should start as PENDING or PROCESSING
        s = self.tm.get_task_status(task_id)
        self.assertIn(s['status'], [TASK_PENDING, TASK_PROCESSING])

        # Wait for completion
        for _ in range(20):
            time_mod.sleep(0.5)
            s = self.tm.get_task_status(task_id)
            if s['status'] == TASK_COMPLETED:
                break

        self.assertEqual(s['status'], TASK_COMPLETED)

    def test_error_reporting(self):
        """Failed segments appear in the errors array."""
        import time as time_mod

        def failing_task():
            self.tm.add_error('test-err', 'seg-1', 'Something went wrong')

        task_id = self.tm.submit_task(failing_task, task_id='test-err')

        for _ in range(20):
            time_mod.sleep(0.5)
            s = self.tm.get_task_status(task_id)
            if s['status'] in (TASK_COMPLETED, TASK_FAILED):
                break

        self.assertEqual(len(s['errors']), 1)
        self.assertEqual(s['errors'][0]['segment_id'], 'seg-1')
        self.assertEqual(s['errors'][0]['error'], 'Something went wrong')


# --------------------------------------------------------------------------
# Segment Delete Audio Cleanup tests
# --------------------------------------------------------------------------

@override_settings(MEDIA_ROOT=TEMP_MEDIA_AUDIO)
class TestSegmentDeleteAudioCleanup(APITestCase):
    """Tests for audio file cleanup when deleting a segment."""

    def setUp(self):
        self.project = Project.objects.create(title='Cleanup Test')
        self.segment = Segment.objects.create(
            project=self.project, sequence_index=0,
            text_content='Cleanup segment', image_prompt='',
        )

    def tearDown(self):
        if os.path.isdir(TEMP_MEDIA_AUDIO):
            shutil.rmtree(TEMP_MEDIA_AUDIO, ignore_errors=True)
            os.makedirs(TEMP_MEDIA_AUDIO, exist_ok=True)

    def test_delete_segment_removes_audio_file(self):
        """Deleting a segment with a .wav on disk removes the file."""
        from core_engine.tts_wrapper import construct_audio_path
        audio_path = construct_audio_path(self.project.id, self.segment.id)
        # Create a dummy wav file
        with open(str(audio_path), 'w') as f:
            f.write('fake audio data')
        self.assertTrue(os.path.isfile(str(audio_path)))

        self.client.delete(f'/api/segments/{self.segment.id}/')

        self.assertFalse(os.path.isfile(str(audio_path)))
        self.assertEqual(Segment.objects.count(), 0)

    def test_delete_segment_without_audio_succeeds(self):
        """Deleting a segment that has no audio file works without errors."""
        response = self.client.delete(f'/api/segments/{self.segment.id}/')
        self.assertEqual(response.status_code, 204)
        self.assertEqual(Segment.objects.count(), 0)


# --------------------------------------------------------------------------
# TaskManager unit tests
# --------------------------------------------------------------------------

class TestTaskManagerUnit(TestCase):
    """Unit tests for TaskManager singleton and lifecycle."""

    def setUp(self):
        self.tm = _reset_task_manager()

    def tearDown(self):
        self.tm.shutdown(wait=True)
        _reset_task_manager()

    def test_singleton_returns_same_instance(self):
        tm1 = TaskManager()
        tm2 = TaskManager()
        self.assertIs(tm1, tm2)

    def test_submit_task_creates_pending(self):
        import time as time_mod

        def slow():
            time_mod.sleep(5)

        # Submit a slow task to fill the executor
        self.tm.submit_task(slow, task_id='blocker')

        # Submit a second task — it should be queued as PENDING
        tid = self.tm.submit_task(lambda: None, task_id='test-pending')
        s = self.tm.get_task_status(tid)
        self.assertEqual(s['status'], TASK_PENDING)

    def test_lifecycle_pending_to_completed(self):
        import time as time_mod

        tid = self.tm.submit_task(lambda: None)

        for _ in range(20):
            time_mod.sleep(0.5)
            s = self.tm.get_task_status(tid)
            if s['status'] == TASK_COMPLETED:
                break

        self.assertEqual(s['status'], TASK_COMPLETED)

    def test_lifecycle_failed_on_exception(self):
        import time as time_mod

        def failing():
            raise ValueError('Test failure')

        tid = self.tm.submit_task(failing)

        for _ in range(20):
            time_mod.sleep(0.5)
            s = self.tm.get_task_status(tid)
            if s['status'] == TASK_FAILED:
                break

        self.assertEqual(s['status'], TASK_FAILED)

    def test_add_completed_segment_accumulates(self):
        tid = self.tm.submit_task(lambda: None, task_id='acc-test')
        self.tm.add_completed_segment(tid, 'seg-1', {'audio_url': '/a.wav', 'duration': 1.0})
        self.tm.add_completed_segment(tid, 'seg-2', {'audio_url': '/b.wav', 'duration': 2.0})
        s = self.tm.get_task_status(tid)
        self.assertEqual(len(s['completed_segments']), 2)

    def test_add_error_accumulates(self):
        tid = self.tm.submit_task(lambda: None, task_id='err-test')
        self.tm.add_error(tid, 'seg-1', 'Error one')
        self.tm.add_error(tid, 'seg-2', 'Error two')
        s = self.tm.get_task_status(tid)
        self.assertEqual(len(s['errors']), 2)

    def test_cancel_task_sets_flag(self):
        import time as time_mod

        def slow():
            time_mod.sleep(5)

        tid = self.tm.submit_task(slow)
        self.tm.cancel_task(tid)
        self.assertTrue(self.tm.is_cancelled(tid))

    def test_cleanup_old_tasks(self):
        """Tasks older than threshold are cleaned up."""
        import time as time_mod

        tid = self.tm.submit_task(lambda: None)
        for _ in range(20):
            time_mod.sleep(0.5)
            s = self.tm.get_task_status(tid)
            if s['status'] == TASK_COMPLETED:
                break

        # Manipulate completed_at to be old
        with self.tm._tasks_lock:
            self.tm._tasks[tid]['completed_at'] = time_mod.time() - 7200

        self.tm._cleanup_old_tasks()
        self.assertIsNone(self.tm.get_task_status(tid))

    def test_get_status_unknown_returns_none(self):
        result = self.tm.get_task_status('does-not-exist')
        self.assertIsNone(result)

    def test_update_progress_unknown_id_no_crash(self):
        """Updating progress on unknown task silently does nothing."""
        self.tm.update_task_progress('fake-id', 1, 10)
        # Should not raise


# ==========================================================================
# Phase 04 — Video Renderer Tests
# ==========================================================================

import numpy as np
import soundfile as sf
from django.core.files import File
from core_engine import render_utils
from core_engine.render_utils import (
    check_ffmpeg,
    reset_ffmpeg_cache,
    get_ffmpeg_error_message,
    resize_image_to_resolution,
    get_output_path,
    cleanup_temp_files,
)


class VideoRendererTests(TestCase):
    """
    Tests for the Phase 04 basic video assembly pipeline.

    Uses synthetic test data (generated images + silent audio)
    at small resolution (640×360) for fast execution.
    """

    def setUp(self):
        """Create a test project with 3 segments (synthetic images + silent audio)."""
        self.temp_dir = tempfile.mkdtemp()

        # Create project with small resolution for fast tests
        self.project = Project.objects.create(
            title="Test Render Project",
            resolution_width=640,
            resolution_height=360,
            framerate=24,
        )

        self.segments = []
        self.image_paths = []
        self.audio_paths = []

        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]

        for i in range(3):
            # Generate synthetic image (800×600)
            img = PILImage.new("RGB", (800, 600), color=colors[i])
            img_path = os.path.join(self.temp_dir, f"seg_{i}.png")
            img.save(img_path)
            self.image_paths.append(img_path)

            # Generate silent WAV audio (1 second at 24000 Hz)
            audio_data = np.zeros(24000, dtype=np.float32)
            audio_path = os.path.join(self.temp_dir, f"seg_{i}.wav")
            sf.write(audio_path, audio_data, 24000)
            self.audio_paths.append(audio_path)

            # Create segment with files
            segment = Segment.objects.create(
                project=self.project,
                sequence_index=i,
                text_content=f"Test segment {i}",
                audio_duration=1.0,
            )

            # Assign file fields using Django's File wrapper
            with open(img_path, 'rb') as f:
                segment.image_file.save(f"seg_{i}.png", File(f), save=False)
            with open(audio_path, 'rb') as f:
                segment.audio_file.save(f"seg_{i}.wav", File(f), save=False)
            segment.save()

            self.segments.append(segment)

    def tearDown(self):
        """Clean up all temporary files and test data."""
        # Reset FFmpeg cache
        reset_ffmpeg_cache()

        # Clean up output directory
        try:
            output_path = get_output_path(str(self.project.id))
            output_dir = os.path.dirname(output_path)
            if os.path.exists(output_dir):
                shutil.rmtree(output_dir, ignore_errors=True)
        except Exception:
            pass

        # Clean up temp directory
        try:
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception:
            pass

        # Clean up media files created by Django's FileField
        try:
            project_media_dir = os.path.join(
                'media', 'projects', str(self.project.id)
            )
            if os.path.exists(project_media_dir):
                shutil.rmtree(project_media_dir, ignore_errors=True)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # FFmpeg Check Tests
    # ------------------------------------------------------------------

    def test_check_ffmpeg(self):
        """FFmpeg must be available for render tests to function."""
        reset_ffmpeg_cache()
        result = check_ffmpeg()
        self.assertTrue(result)

    def test_check_ffmpeg_cached(self):
        """Second call returns cached result without subprocess."""
        reset_ffmpeg_cache()
        result1 = check_ffmpeg()
        result2 = check_ffmpeg()
        self.assertEqual(result1, result2)

    def test_reset_ffmpeg_cache(self):
        """reset_ffmpeg_cache clears the cached value."""
        check_ffmpeg()  # Populate cache
        reset_ffmpeg_cache()
        self.assertIsNone(render_utils._ffmpeg_available)

    def test_get_ffmpeg_error_message(self):
        """Error message contains installation instructions."""
        msg = get_ffmpeg_error_message()
        self.assertIn("not found", msg.lower())
        self.assertIsInstance(msg, str)
        self.assertGreater(len(msg), 50)

    # ------------------------------------------------------------------
    # Image Cover Resize Tests
    # ------------------------------------------------------------------

    def test_cover_resize_16_9(self):
        """16:9 source (2560×1440) → 640×360 output."""
        img = PILImage.new("RGB", (2560, 1440), color=(128, 128, 128))
        path = os.path.join(self.temp_dir, "resize_16_9.png")
        img.save(path)

        result = resize_image_to_resolution(path, 640, 360)
        self.assertEqual(result.shape, (360, 640, 3))
        self.assertEqual(result.dtype, np.uint8)

    def test_cover_resize_4_3(self):
        """4:3 source (1600×1200) → 640×360 output."""
        img = PILImage.new("RGB", (1600, 1200), color=(128, 128, 128))
        path = os.path.join(self.temp_dir, "resize_4_3.png")
        img.save(path)

        result = resize_image_to_resolution(path, 640, 360)
        self.assertEqual(result.shape, (360, 640, 3))
        self.assertEqual(result.dtype, np.uint8)

    def test_cover_resize_square(self):
        """1:1 source (1080×1080) → 640×360 output."""
        img = PILImage.new("RGB", (1080, 1080), color=(128, 128, 128))
        path = os.path.join(self.temp_dir, "resize_square.png")
        img.save(path)

        result = resize_image_to_resolution(path, 640, 360)
        self.assertEqual(result.shape, (360, 640, 3))
        self.assertEqual(result.dtype, np.uint8)

    def test_cover_resize_portrait(self):
        """Portrait source (800×1200) → 640×360 output."""
        img = PILImage.new("RGB", (800, 1200), color=(128, 128, 128))
        path = os.path.join(self.temp_dir, "resize_portrait.png")
        img.save(path)

        result = resize_image_to_resolution(path, 640, 360)
        self.assertEqual(result.shape, (360, 640, 3))
        self.assertEqual(result.dtype, np.uint8)

    def test_cover_resize_rgba_to_rgb(self):
        """RGBA image is converted to RGB (3 channels)."""
        img = PILImage.new("RGBA", (800, 600), color=(128, 128, 128, 255))
        path = os.path.join(self.temp_dir, "resize_rgba.png")
        img.save(path)

        result = resize_image_to_resolution(path, 640, 360)
        self.assertEqual(result.shape, (360, 640, 3))

    def test_cover_resize_missing_image(self):
        """Missing image raises FileNotFoundError."""
        with self.assertRaises(FileNotFoundError):
            resize_image_to_resolution("/nonexistent/image.png", 640, 360)

    def test_cover_resize_invalid_dimensions(self):
        """Zero or negative dimensions raise ValueError."""
        path = self.image_paths[0]
        with self.assertRaises(ValueError):
            resize_image_to_resolution(path, 0, 360)
        with self.assertRaises(ValueError):
            resize_image_to_resolution(path, 640, -1)

    # ------------------------------------------------------------------
    # Output Path Management Tests
    # ------------------------------------------------------------------

    def test_get_output_path(self):
        """Output path ends with /output/final.mp4 and directory is created."""
        path = get_output_path(str(self.project.id))
        self.assertTrue(path.endswith("final.mp4"))
        self.assertIn("output", path)
        output_dir = os.path.dirname(path)
        self.assertTrue(os.path.isdir(output_dir))

    def test_get_output_path_idempotent(self):
        """Re-calling get_output_path works (exist_ok=True)."""
        path1 = get_output_path(str(self.project.id))
        path2 = get_output_path(str(self.project.id))
        self.assertEqual(path1, path2)

    def test_cleanup_temp_files(self):
        """cleanup_temp_files removes files and directory."""
        tmp = tempfile.mkdtemp()
        with open(os.path.join(tmp, "file1.txt"), 'w') as f:
            f.write("test")
        cleanup_temp_files(tmp)
        self.assertFalse(os.path.exists(tmp))

    def test_cleanup_temp_files_nonexistent(self):
        """cleanup_temp_files handles non-existent directory gracefully."""
        cleanup_temp_files("/nonexistent/path/xyz123")
        # Should not raise

    # ------------------------------------------------------------------
    # Render Pipeline Tests
    # ------------------------------------------------------------------

    def test_render_single_segment(self):
        """Single-segment render produces a valid MP4."""
        # Keep only the first segment
        for seg in self.segments[1:]:
            seg.delete()

        from core_engine.video_renderer import render_project
        result = render_project(str(self.project.id))

        self.assertIn("output_path", result)
        self.assertIn("duration", result)
        self.assertIn("file_size", result)
        self.assertTrue(os.path.exists(result["output_path"]))
        self.assertGreater(result["file_size"], 0)

    def test_render_multiple_segments(self):
        """Multi-segment render: duration ≈ sum of audio durations."""
        from core_engine.video_renderer import render_project
        result = render_project(str(self.project.id))

        self.assertTrue(os.path.exists(result["output_path"]))
        self.assertGreater(result["file_size"], 0)

        # Total duration should be approximately 3 seconds (3 × 1s audio)
        expected_duration = 3.0
        self.assertAlmostEqual(
            result["duration"], expected_duration, delta=0.5
        )

    def test_render_progress_callback(self):
        """Progress callback is invoked for each segment + export phase."""
        from core_engine.video_renderer import render_project

        progress_calls = []

        def callback(current, total, description):
            progress_calls.append((current, total, description))

        render_project(str(self.project.id), on_progress=callback)

        # At least 3 segments + 1 export phase = 4 calls
        self.assertGreaterEqual(len(progress_calls), 4)

        # Last call should mention export
        last_desc = progress_calls[-1][2]
        self.assertIn("Export", last_desc)

    def test_render_missing_image_error(self):
        """Missing image file raises appropriate error."""
        from core_engine.video_renderer import render_project

        # Point segment's image_file to a non-existent path
        seg = self.segments[0]
        seg.image_file.name = "nonexistent/missing_image.png"
        seg.save()

        with self.assertRaises((FileNotFoundError, ValueError, RuntimeError)):
            render_project(str(self.project.id))

    def test_render_missing_audio_error(self):
        """Missing audio file raises appropriate error."""
        from core_engine.video_renderer import render_project

        # Point segment's audio_file to a non-existent path
        seg = self.segments[0]
        seg.audio_file.name = "nonexistent/missing_audio.wav"
        seg.save()

        with self.assertRaises((FileNotFoundError, ValueError, RuntimeError)):
            render_project(str(self.project.id))

    def test_render_no_segments_error(self):
        """Rendering a project with no segments raises ValueError."""
        from core_engine.video_renderer import render_project

        for seg in self.segments:
            seg.delete()

        with self.assertRaises(ValueError):
            render_project(str(self.project.id))


# ===================================================================
# Ken Burns Math Tests (Task 04.02.11)
# ===================================================================

class KenBurnsMathTests(TestCase):
    """Pure math tests for Ken Burns algorithm components.

    These tests validate the mathematical correctness of crop-box
    dimension calculation, linear interpolation, pan direction cycling,
    and position-to-coordinate mapping.  They involve no file I/O, no
    image processing, and no MoviePy dependency, and should execute
    in under one second.
    """

    # ------------------------------------------------------------------
    # Crop Box Dimension Tests
    # ------------------------------------------------------------------

    def test_crop_dimensions_default_zoom(self):
        """Crop box at default zoom 1.3 for 1920×1080 output."""
        from core_engine.ken_burns import calculate_crop_dimensions

        crop_w, crop_h = calculate_crop_dimensions(1920, 1080, 1.3)
        self.assertEqual(crop_w, 1476)
        self.assertEqual(crop_h, 830)
        self.assertIsInstance(crop_w, int)
        self.assertIsInstance(crop_h, int)
        self.assertGreater(crop_w, 0)
        self.assertGreater(crop_h, 0)

    def test_crop_dimensions_no_zoom(self):
        """Crop box at zoom 1.0 equals output resolution exactly."""
        from core_engine.ken_burns import calculate_crop_dimensions

        crop_w, crop_h = calculate_crop_dimensions(1920, 1080, 1.0)
        self.assertEqual(crop_w, 1920)
        self.assertEqual(crop_h, 1080)

    def test_crop_dimensions_high_zoom(self):
        """Crop box at zoom 2.0 is exactly half the output."""
        from core_engine.ken_burns import calculate_crop_dimensions

        crop_w, crop_h = calculate_crop_dimensions(1920, 1080, 2.0)
        self.assertEqual(crop_w, 960)
        self.assertEqual(crop_h, 540)

    def test_crop_dimensions_invalid_zoom_zero(self):
        """ValueError raised when zoom intensity is zero."""
        from core_engine.ken_burns import calculate_crop_dimensions

        with self.assertRaises(ValueError):
            calculate_crop_dimensions(1920, 1080, 0.0)

    def test_crop_dimensions_invalid_zoom_negative(self):
        """ValueError raised when zoom intensity is negative."""
        from core_engine.ken_burns import calculate_crop_dimensions

        with self.assertRaises(ValueError):
            calculate_crop_dimensions(1920, 1080, -1.0)

    # ------------------------------------------------------------------
    # Linear Interpolation Tests
    # ------------------------------------------------------------------

    def test_interpolation_at_start(self):
        """Interpolation at t=0 returns start position."""
        from core_engine.ken_burns import interpolate_position

        result = interpolate_position((0, 0), (100, 200), 0, 5)
        self.assertAlmostEqual(result[0], 0.0, places=6)
        self.assertAlmostEqual(result[1], 0.0, places=6)

    def test_interpolation_at_end(self):
        """Interpolation at t=duration returns end position."""
        from core_engine.ken_burns import interpolate_position

        result = interpolate_position((0, 0), (100, 200), 5, 5)
        self.assertAlmostEqual(result[0], 100.0, places=6)
        self.assertAlmostEqual(result[1], 200.0, places=6)

    def test_interpolation_at_midpoint(self):
        """Interpolation at t=duration/2 returns midpoint."""
        from core_engine.ken_burns import interpolate_position

        result = interpolate_position((0, 0), (100, 200), 2.5, 5)
        self.assertAlmostEqual(result[0], 50.0, places=6)
        self.assertAlmostEqual(result[1], 100.0, places=6)

    def test_interpolation_at_quarter(self):
        """Interpolation at t=duration/4 with non-zero start."""
        from core_engine.ken_burns import interpolate_position

        result = interpolate_position((10, 20), (110, 220), 1.25, 5)
        self.assertAlmostEqual(result[0], 35.0, places=6)
        self.assertAlmostEqual(result[1], 70.0, places=6)

    def test_interpolation_zero_duration(self):
        """Zero duration returns start position without division error."""
        from core_engine.ken_burns import interpolate_position

        result = interpolate_position((10, 20), (110, 220), 0, 0)
        self.assertAlmostEqual(result[0], 10.0, places=6)
        self.assertAlmostEqual(result[1], 20.0, places=6)

    def test_interpolation_no_movement(self):
        """Identical start and end returns that position at all times."""
        from core_engine.ken_burns import interpolate_position

        for t in (0, 2.5, 5):
            result = interpolate_position((50, 50), (50, 50), t, 5)
            self.assertAlmostEqual(result[0], 50.0, places=6)
            self.assertAlmostEqual(result[1], 50.0, places=6)

    # ------------------------------------------------------------------
    # Pan Direction Tests
    # ------------------------------------------------------------------

    def test_direction_cycling(self):
        """Direction cycles through DIRECTIONS with modulo 7."""
        from core_engine.ken_burns import get_pan_direction, DIRECTIONS

        # First cycle (indices 0–6 match DIRECTIONS in order)
        for i in range(7):
            self.assertEqual(get_pan_direction(i), DIRECTIONS[i])

        # Second cycle (indices 7–13 repeat from the beginning)
        for i in range(7, 14):
            self.assertEqual(get_pan_direction(i), DIRECTIONS[i - 7])

    def test_direction_determinism(self):
        """Same index always returns the same direction."""
        from core_engine.ken_burns import get_pan_direction

        result1 = get_pan_direction(3)
        result2 = get_pan_direction(3)
        self.assertEqual(result1, result2)

    # ------------------------------------------------------------------
    # Position to Coords Tests
    # ------------------------------------------------------------------

    def test_position_center(self):
        """Center position maps to (max_x//2, max_y//2)."""
        from core_engine.ken_burns import position_to_coords

        # Source 2496×1404, crop 1476×830 → max_x=1020, max_y=574
        x, y = position_to_coords("center", 2496, 1404, 1476, 830)
        self.assertEqual(x, 510)   # 1020 // 2
        self.assertEqual(y, 287)   # 574 // 2

    def test_position_corners(self):
        """All four corners map to correct coordinates."""
        from core_engine.ken_burns import position_to_coords

        # Source 2496×1404, crop 1476×830 → max_x=1020, max_y=574
        img_w, img_h = 2496, 1404
        crop_w, crop_h = 1476, 830

        self.assertEqual(
            position_to_coords("top_left", img_w, img_h, crop_w, crop_h),
            (0, 0),
        )
        self.assertEqual(
            position_to_coords("top_right", img_w, img_h, crop_w, crop_h),
            (1020, 0),
        )
        self.assertEqual(
            position_to_coords("bottom_left", img_w, img_h, crop_w, crop_h),
            (0, 574),
        )
        self.assertEqual(
            position_to_coords("bottom_right", img_w, img_h, crop_w, crop_h),
            (1020, 574),
        )

    def test_position_invalid_name(self):
        """ValueError raised for unrecognised position name."""
        from core_engine.ken_burns import position_to_coords

        with self.assertRaises(ValueError):
            position_to_coords("middle_left", 2496, 1404, 1476, 830)


# ===================================================================
# Ken Burns Integration Tests (Task 04.02.12)
# ===================================================================

class KenBurnsIntegrationTests(TestCase):
    """Integration tests for the full Ken Burns rendering pipeline.

    These tests exercise the complete flow: loading images, preparing
    them for zoom headroom, generating animated frames via make_frame,
    integrating with the video renderer, concatenating segments, and
    exporting a playable MP4 file.  Uses small resolution (640×360) and
    short durations (1 second) for fast execution.
    """

    def setUp(self):
        """Create test project, GlobalSettings, segments, images, and audio."""
        from api.models import GlobalSettings

        self.temp_dir = tempfile.mkdtemp()
        self.output_paths = []

        # Create GlobalSettings with default zoom
        GlobalSettings.objects.all().delete()
        GlobalSettings.objects.create(zoom_intensity=1.3)

        # Create project with small resolution for fast tests
        self.project = Project.objects.create(
            title="Ken Burns Integration Test",
            resolution_width=640,
            resolution_height=360,
            framerate=24,
        )

        self.segments = []
        self.image_paths = []
        self.audio_paths = []

        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]

        for i in range(3):
            # Generate synthetic gradient image (800×600) — gradient
            # ensures different crop positions produce different pixels,
            # which is essential for the "frames differ" test.
            img = PILImage.new("RGB", (800, 600))
            pixels = img.load()
            r_base, g_base, b_base = colors[i]
            for y_px in range(600):
                for x_px in range(800):
                    pixels[x_px, y_px] = (
                        (r_base + x_px) % 256,
                        (g_base + y_px) % 256,
                        (b_base + x_px + y_px) % 256,
                    )
            img_path = os.path.join(self.temp_dir, f"kb_seg_{i}.png")
            img.save(img_path)
            self.image_paths.append(img_path)

            # Generate silent WAV audio (1 second at 24000 Hz)
            audio_data = np.zeros(24000, dtype=np.float32)
            audio_path = os.path.join(self.temp_dir, f"kb_seg_{i}.wav")
            sf.write(audio_path, audio_data, 24000)
            self.audio_paths.append(audio_path)

            # Create segment with files
            segment = Segment.objects.create(
                project=self.project,
                sequence_index=i,
                text_content=f"Ken Burns test segment {i}",
                audio_duration=1.0,
            )

            # Assign file fields using Django's File wrapper
            from django.core.files import File
            with open(img_path, "rb") as f:
                segment.image_file.save(
                    f"kb_seg_{i}.png", File(f), save=False
                )
            with open(audio_path, "rb") as f:
                segment.audio_file.save(
                    f"kb_seg_{i}.wav", File(f), save=False
                )
            segment.save()

            self.segments.append(segment)

    def tearDown(self):
        """Clean up all temporary files and test data."""
        from core_engine.render_utils import get_output_path, reset_ffmpeg_cache

        reset_ffmpeg_cache()

        # Clean up output directory
        try:
            output_path = get_output_path(str(self.project.id))
            output_dir = os.path.dirname(output_path)
            if os.path.exists(output_dir):
                shutil.rmtree(output_dir, ignore_errors=True)
        except Exception:
            pass

        # Clean up any extra output paths
        for p in self.output_paths:
            try:
                if os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass

        # Clean up temp directory
        try:
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception:
            pass

        # Clean up Django media files
        try:
            project_media_dir = os.path.join(
                "media", "projects", str(self.project.id)
            )
            if os.path.exists(project_media_dir):
                shutil.rmtree(project_media_dir, ignore_errors=True)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # apply_ken_burns Direct Tests
    # ------------------------------------------------------------------

    def _get_frame(self, clip, t):
        """Version-safe frame retrieval (MoviePy 1.x vs 2.x)."""
        if hasattr(clip, "get_frame"):
            return clip.get_frame(t)
        return clip.make_frame(t)  # pragma: no cover — MoviePy 1.x

    def test_apply_ken_burns_returns_clip(self):
        """apply_ken_burns returns a VideoClip with correct duration and FPS."""
        from core_engine.ken_burns import apply_ken_burns

        clip = apply_ken_burns(
            image_path=self.image_paths[0],
            duration=1.0,
            resolution=(640, 360),
            zoom_intensity=1.3,
            fps=24,
            segment_index=0,
        )
        try:
            # MoviePy 2.x stores frame callback as frame_function
            frame_fn = getattr(clip, "frame_function", None) or getattr(clip, "make_frame", None)
            self.assertTrue(callable(frame_fn))
            self.assertAlmostEqual(clip.duration, 1.0, places=2)
            self.assertEqual(clip.fps, 24)
        finally:
            clip.close()

    def test_frame_output_shape(self):
        """Frame arrays have shape (360, 640, 3) with dtype uint8."""
        from core_engine.ken_burns import apply_ken_burns

        clip = apply_ken_burns(
            image_path=self.image_paths[0],
            duration=1.0,
            resolution=(640, 360),
            zoom_intensity=1.3,
            fps=24,
            segment_index=0,
        )
        try:
            for t in (0.0, 0.5, 1.0):
                frame = self._get_frame(clip, t)
                self.assertEqual(frame.shape, (360, 640, 3))
                self.assertEqual(frame.dtype, np.uint8)
        finally:
            clip.close()

    def test_frames_differ_non_center_direction(self):
        """Non-center direction produces different start/end frames."""
        from core_engine.ken_burns import apply_ken_burns

        # segment_index=1 selects top_left→bottom_right
        clip = apply_ken_burns(
            image_path=self.image_paths[0],
            duration=1.0,
            resolution=(640, 360),
            zoom_intensity=1.3,
            fps=24,
            segment_index=1,
        )
        try:
            frame_start = self._get_frame(clip, 0.0)
            frame_end = self._get_frame(clip, 1.0)
            self.assertFalse(
                np.array_equal(frame_start, frame_end),
                "Frames at t=0 and t=1 should differ for non-center direction",
            )
        finally:
            clip.close()

    def test_frames_identical_center_direction(self):
        """Center-to-center direction produces identical frames."""
        from core_engine.ken_burns import apply_ken_burns

        # segment_index=0 selects center→center
        clip = apply_ken_burns(
            image_path=self.image_paths[0],
            duration=1.0,
            resolution=(640, 360),
            zoom_intensity=1.3,
            fps=24,
            segment_index=0,
        )
        try:
            frame_start = self._get_frame(clip, 0.0)
            frame_end = self._get_frame(clip, 1.0)
            self.assertTrue(
                np.array_equal(frame_start, frame_end),
                "Frames should be identical for center-to-center direction",
            )
        finally:
            clip.close()

    def test_different_segments_different_directions(self):
        """Different segment indices produce different initial frames."""
        from core_engine.ken_burns import apply_ken_burns

        clip0 = apply_ken_burns(
            image_path=self.image_paths[0],
            duration=1.0,
            resolution=(640, 360),
            zoom_intensity=1.3,
            fps=24,
            segment_index=0,
        )
        clip1 = apply_ken_burns(
            image_path=self.image_paths[0],
            duration=1.0,
            resolution=(640, 360),
            zoom_intensity=1.3,
            fps=24,
            segment_index=1,
        )
        try:
            frame0 = self._get_frame(clip0, 0.0)
            frame1 = self._get_frame(clip1, 0.0)
            self.assertFalse(
                np.array_equal(frame0, frame1),
                "Different segment indices should produce different frames",
            )
        finally:
            clip0.close()
            clip1.close()

    def test_ken_burns_small_image(self):
        """Small image (400×300) is upscaled successfully."""
        from core_engine.ken_burns import apply_ken_burns

        # Create a deliberately small image
        small_img = PILImage.new("RGB", (400, 300), color=(128, 128, 0))
        small_path = os.path.join(self.temp_dir, "small.png")
        small_img.save(small_path)

        clip = apply_ken_burns(
            image_path=small_path,
            duration=1.0,
            resolution=(640, 360),
            zoom_intensity=1.3,
            fps=24,
            segment_index=0,
        )
        try:
            frame = self._get_frame(clip, 0.0)
            self.assertEqual(frame.shape, (360, 640, 3))
            self.assertEqual(frame.dtype, np.uint8)
        finally:
            clip.close()

    def test_ken_burns_large_image(self):
        """Large image (3000×2000) is handled without crashes."""
        from core_engine.ken_burns import apply_ken_burns

        # Create a deliberately large image
        large_img = PILImage.new("RGB", (3000, 2000), color=(0, 128, 128))
        large_path = os.path.join(self.temp_dir, "large.png")
        large_img.save(large_path)

        clip = apply_ken_burns(
            image_path=large_path,
            duration=1.0,
            resolution=(640, 360),
            zoom_intensity=1.3,
            fps=24,
            segment_index=0,
        )
        try:
            frame = self._get_frame(clip, 0.0)
            self.assertEqual(frame.shape, (360, 640, 3))
            self.assertEqual(frame.dtype, np.uint8)
        finally:
            clip.close()

    # ------------------------------------------------------------------
    # Full Render Pipeline Tests
    # ------------------------------------------------------------------

    def test_full_render_produces_mp4(self):
        """Full render_project produces a valid, non-empty MP4 file."""
        from core_engine.video_renderer import render_project

        result = render_project(str(self.project.id))

        self.assertIn("output_path", result)
        self.assertIn("duration", result)
        self.assertIn("file_size", result)

        output_path = result["output_path"]
        self.output_paths.append(output_path)

        self.assertTrue(os.path.exists(output_path))
        self.assertGreater(result["file_size"], 0)

        # 3 segments × 1 second each ≈ 3.0 seconds (±0.5 tolerance)
        self.assertAlmostEqual(result["duration"], 3.0, delta=0.5)

    def test_render_with_zoom_1_0(self):
        """Render succeeds with zoom_intensity 1.0 (no zoom)."""
        from api.models import GlobalSettings
        from core_engine.video_renderer import render_project

        gs = GlobalSettings.objects.first()
        gs.zoom_intensity = 1.0
        gs.save()

        result = render_project(str(self.project.id))

        output_path = result["output_path"]
        self.output_paths.append(output_path)

        self.assertTrue(os.path.exists(output_path))
        self.assertGreater(result["file_size"], 0)

    def test_render_with_zoom_2_0(self):
        """Render succeeds with zoom_intensity 2.0 (high zoom)."""
        from api.models import GlobalSettings
        from core_engine.video_renderer import render_project

        gs = GlobalSettings.objects.first()
        gs.zoom_intensity = 2.0
        gs.save()

        result = render_project(str(self.project.id))

        output_path = result["output_path"]
        self.output_paths.append(output_path)

        self.assertTrue(os.path.exists(output_path))
        self.assertGreater(result["file_size"], 0)


# ── Render Pipeline Tests (Task 04.03.14) ──────────────────────────────────

@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class RenderPipelineTests(APITestCase):
    """Comprehensive tests for the render pipeline endpoints and logic."""

    def setUp(self):
        """Create Project, 3 Segments with real files, and GlobalSettings."""
        from django.core.files.base import File as DjangoFile
        from api.models import Project, Segment, GlobalSettings
        from api.models import STATUS_DRAFT

        self.temp_dir = tempfile.mkdtemp()

        # Create project
        self.project = Project.objects.create(title="Render Test Project", status=STATUS_DRAFT)
        self.project_id = str(self.project.id)

        # Construct endpoint URLs
        self.render_url = f"/api/projects/{self.project_id}/render/"
        self.status_url = f"/api/projects/{self.project_id}/status/"

        # Create GlobalSettings
        GlobalSettings.objects.get_or_create(pk=1, defaults={
            'zoom_intensity': 1.3,
            'default_voice_id': 'af_heart',
            'tts_speed': 1.0,
        })

        # Create 3 segments with real image and audio files
        self.segments = []
        for i in range(3):
            # Generate image
            img = PILImage.new("RGB", (800, 600), color=(i * 80, 100, 200))
            img_path = os.path.join(self.temp_dir, f"seg_{i}.png")
            img.save(img_path)

            # Generate silent WAV audio
            import struct
            audio_path = os.path.join(self.temp_dir, f"seg_{i}.wav")
            sample_rate = 24000
            num_samples = sample_rate  # 1 second
            with open(audio_path, 'wb') as af:
                data_size = num_samples * 2  # 16-bit samples
                af.write(b'RIFF')
                af.write(struct.pack('<I', 36 + data_size))
                af.write(b'WAVE')
                af.write(b'fmt ')
                af.write(struct.pack('<I', 16))
                af.write(struct.pack('<H', 1))    # PCM
                af.write(struct.pack('<H', 1))    # mono
                af.write(struct.pack('<I', sample_rate))
                af.write(struct.pack('<I', sample_rate * 2))
                af.write(struct.pack('<H', 2))    # block align
                af.write(struct.pack('<H', 16))   # bits per sample
                af.write(b'data')
                af.write(struct.pack('<I', data_size))
                af.write(b'\x00' * data_size)

            # Create segment
            segment = Segment.objects.create(
                project=self.project,
                sequence_index=i,
                text_content=f"Test segment {i}",
                audio_duration=1.0,
            )

            # Assign file fields
            with open(img_path, 'rb') as f:
                segment.image_file.save(f"seg_{i}.png", DjangoFile(f), save=False)
            with open(audio_path, 'rb') as f:
                segment.audio_file.save(f"seg_{i}.wav", DjangoFile(f), save=False)
            segment.save()
            self.segments.append(segment)

    def tearDown(self):
        """Clean up temporary files and media directory."""
        from django.conf import settings
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        if os.path.exists(settings.MEDIA_ROOT):
            shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)

    # ── Render Trigger Tests ──

    def test_render_trigger_success(self):
        """POST to render endpoint with valid project returns 202."""
        from api.models import STATUS_PROCESSING
        from unittest.mock import patch

        with patch('api.views.render_utils.check_ffmpeg', return_value=True), \
             patch('api.tasks.render_task_function'):
            response = self.client.post(self.render_url)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertIn('task_id', response.data)
        self.assertEqual(response.data['status'], STATUS_PROCESSING)

        self.project.refresh_from_db()
        self.assertEqual(self.project.status, STATUS_PROCESSING)

    def test_render_trigger_missing_images(self):
        """POST with missing image returns 400 with missing_images."""
        seg = self.segments[0]
        seg.image_file.name = "nonexistent/missing_image.png"
        seg.save()

        response = self.client.post(self.render_url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('missing_images', response.data)

    def test_render_trigger_missing_audio(self):
        """POST with missing audio returns 400 with missing_audio."""
        seg = self.segments[0]
        seg.audio_file.name = "nonexistent/missing_audio.wav"
        seg.save()

        response = self.client.post(self.render_url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('missing_audio', response.data)

    def test_render_trigger_no_segments(self):
        """POST with no segments returns 400."""
        from api.models import Segment
        Segment.objects.filter(project=self.project).delete()

        response = self.client.post(self.render_url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_render_trigger_already_processing(self):
        """POST when project is PROCESSING returns 409 Conflict."""
        from api.models import STATUS_PROCESSING
        self.project.status = STATUS_PROCESSING
        self.project.save()

        response = self.client.post(self.render_url)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn('error', response.data)

    def test_render_trigger_re_render(self):
        """POST when project is COMPLETED allows re-render (202)."""
        from api.models import STATUS_COMPLETED
        from unittest.mock import patch

        self.project.status = STATUS_COMPLETED
        self.project.save()

        with patch('api.views.render_utils.check_ffmpeg', return_value=True), \
             patch('api.tasks.render_task_function'):
            response = self.client.post(self.render_url)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

    # ── Status Endpoint Tests ──

    def test_status_draft_project(self):
        """GET status for DRAFT project returns null progress and output_url."""
        response = self.client.get(self.status_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'DRAFT')
        self.assertIsNone(response.data['progress'])
        self.assertIsNone(response.data['output_url'])

    def test_status_completed_project(self):
        """GET status for COMPLETED project returns 100% and output_url."""
        from api.models import STATUS_COMPLETED
        self.project.status = STATUS_COMPLETED
        self.project.output_path = "projects/test/output.mp4"
        self.project.save()

        response = self.client.get(self.status_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'COMPLETED')
        self.assertEqual(response.data['progress']['percentage'], 100)
        self.assertIsNotNone(response.data['output_url'])
        self.assertIn('output.mp4', response.data['output_url'])

    # ── Validation Function Tests ──

    def test_validation_valid_project(self):
        """validate_project_for_render returns None for a valid project."""
        from api.validators import validate_project_for_render
        result = validate_project_for_render(self.project)
        self.assertIsNone(result)

    def test_validation_invalid_project(self):
        """validate_project_for_render returns error dict for invalid project."""
        from api.validators import validate_project_for_render
        for seg in self.segments:
            seg.image_file.name = "nonexistent/missing.png"
            seg.audio_file.name = "nonexistent/missing.wav"
            seg.save()

        result = validate_project_for_render(self.project)
        self.assertIsNotNone(result)
        self.assertIn('missing_images', result)
        self.assertIn('missing_audio', result)
        self.assertIn('message', result)

    # ── End-to-End Test ──

    def test_end_to_end_render(self):
        """Full render flow: trigger → status check → completed."""
        from unittest.mock import patch, MagicMock
        from api.models import STATUS_COMPLETED, STATUS_PROCESSING
        from api.tasks import get_task_manager

        mock_result = {
            'output_path': f'projects/{self.project_id}/output.mp4',
            'file_size': 1024000,
        }

        # Mock submit_task to run the task synchronously in the same
        # thread, avoiding SQLite locking with in-memory test DB.
        def run_synchronously(task_fn, task_id=None):
            task_fn()

        with patch('api.views.render_utils.check_ffmpeg', return_value=True), \
             patch('core_engine.video_renderer.render_project', return_value=mock_result), \
             patch.object(
                 type(get_task_manager()), 'submit_task',
                 side_effect=run_synchronously,
             ):

            response = self.client.post(self.render_url)
            self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        # After synchronous execution, project should be COMPLETED
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, STATUS_COMPLETED)
        self.assertIsNotNone(self.project.output_path)

        # Status endpoint should reflect completion
        status_response = self.client.get(self.status_url)
        self.assertEqual(status_response.status_code, status.HTTP_200_OK)
        self.assertEqual(status_response.data['status'], 'COMPLETED')
        self.assertIsNotNone(status_response.data['output_url'])

    # ── Failure Handling Test ──

    def test_render_failure_handling(self):
        """Render failure sets project status to FAILED."""
        from unittest.mock import patch
        from api.models import STATUS_FAILED
        from api.tasks import get_task_manager

        # Mock submit_task to run synchronously, avoiding SQLite locking.
        # Catch exceptions since render_task_function re-raises after
        # setting FAILED status — mimics TaskManager wrapper behavior.
        def run_synchronously(task_fn, task_id=None):
            try:
                task_fn()
            except Exception:
                pass  # TaskManager wrapper swallows & logs exceptions

        with patch('api.views.render_utils.check_ffmpeg', return_value=True), \
             patch('core_engine.video_renderer.render_project', side_effect=RuntimeError("FFmpeg crashed")), \
             patch.object(
                 type(get_task_manager()), 'submit_task',
                 side_effect=run_synchronously,
             ):

            response = self.client.post(self.render_url)
            self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        # After synchronous execution with failure, project should be FAILED
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, STATUS_FAILED)

        # Status endpoint should reflect failure
        status_response = self.client.get(self.status_url)
        self.assertEqual(status_response.status_code, status.HTTP_200_OK)
        self.assertEqual(status_response.data['status'], 'FAILED')
        self.assertIsNone(status_response.data['output_url'])

    # ── Additional Status Tests ──

    def test_status_processing_project(self):
        """GET status for PROCESSING project returns current progress."""
        from api.models import STATUS_PROCESSING
        from api.tasks import get_task_manager

        self.project.status = STATUS_PROCESSING
        self.project.save()

        task_id = f"render_{self.project_id}"
        tm = get_task_manager()
        tm._tasks[task_id] = {
            'status': 'PROCESSING',
            'progress': {
                'current': 2,
                'total': 3,
                'percentage': 66,
                'description': 'Rendering segment 2 of 3',
            },
        }

        response = self.client.get(self.status_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'PROCESSING')
        self.assertIsNotNone(response.data['progress'])
        self.assertEqual(response.data['progress']['current_segment'], 2)
        self.assertEqual(response.data['progress']['total_segments'], 3)
        self.assertEqual(response.data['progress']['percentage'], 66)

        # Clean up
        del tm._tasks[task_id]

    def test_status_failed_project(self):
        """GET status for FAILED project returns failure info."""
        from api.models import STATUS_FAILED

        self.project.status = STATUS_FAILED
        self.project.save()

        response = self.client.get(self.status_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'FAILED')
        self.assertIsNone(response.data['output_url'])
