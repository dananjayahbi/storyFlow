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
