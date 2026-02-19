# Task 02.02.12 — Write Image Upload Tests

> **Sub-Phase:** 02.02 — Segment Management API
> **Phase:** Phase 02 — The Logic
> **Complexity:** High
> **Dependencies:** Task 02.02.11 (Segment API Tests)
> **Parent Document:** [SubPhase_02_02_Overview.md](./SubPhase_02_02_Overview.md)

---

## Objective

Write comprehensive backend tests for image upload and image removal endpoints, covering valid formats, invalid files, size limits, lock checks, old-file cleanup, and edge cases.

---

## Instructions

### Step 1 — Create test image helper

Add a helper function at the top of the test section in `backend/api/tests.py` to generate valid in-memory images for upload testing.

```python
import io
import tempfile
import shutil
import os
from PIL import Image as PILImage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APITestCase
from rest_framework import status
from api.models import Project, Segment

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
```

### Step 2 — Add `TestImageUpload` class (10 tests)

```python
@override_settings(MEDIA_ROOT=TEMP_MEDIA_UPLOAD)
class TestImageUpload(APITestCase):
    """Tests for POST /api/segments/{id}/upload_image/."""

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
            f'/api/segments/{self.segment.id}/upload_image/',
            {'image': image},
            format='multipart',
        )
        self.assertEqual(response.status_code, 200)
        self.segment.refresh_from_db()
        self.assertTrue(self.segment.image_path)

    def test_upload_valid_png(self):
        image = create_test_image('photo.png', 'PNG')
        response = self.client.post(
            f'/api/segments/{self.segment.id}/upload_image/',
            {'image': image},
            format='multipart',
        )
        self.assertEqual(response.status_code, 200)

    def test_upload_valid_webp(self):
        image = create_test_image('photo.webp', 'WEBP')
        response = self.client.post(
            f'/api/segments/{self.segment.id}/upload_image/',
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
            f'/api/segments/{self.segment.id}/upload_image/',
            {'image': fake_file},
            format='multipart',
        )
        self.assertEqual(response.status_code, 400)

    def test_upload_corrupt_image_returns_400(self):
        corrupt = SimpleUploadedFile(
            'corrupt.jpg', b'\xff\xd8\xff\xe0broken', content_type='image/jpeg',
        )
        response = self.client.post(
            f'/api/segments/{self.segment.id}/upload_image/',
            {'image': corrupt},
            format='multipart',
        )
        self.assertEqual(response.status_code, 400)

    def test_upload_over_20mb_returns_400(self):
        """Generate a file exceeding 20 MB."""
        buf = io.BytesIO()
        # Create a large image (will be big enough after raw data)
        large = PILImage.new('RGB', (6000, 6000), color='blue')
        large.save(buf, format='BMP')  # BMP is uncompressed → large
        buf.seek(0)
        data = buf.read()
        # If BMP isn't large enough, pad it
        if len(data) < 20 * 1024 * 1024:
            data += b'\x00' * (20 * 1024 * 1024 - len(data) + 1)
        oversized = SimpleUploadedFile('huge.bmp', data, content_type='image/bmp')
        response = self.client.post(
            f'/api/segments/{self.segment.id}/upload_image/',
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
            f'/api/segments/{self.segment.id}/upload_image/',
            {'image': image},
            format='multipart',
        )
        self.assertEqual(response.status_code, 400)

    # --- Re-upload / cleanup test ---

    def test_reupload_removes_old_file(self):
        # First upload
        image1 = create_test_image('first.jpg', 'JPEG')
        self.client.post(
            f'/api/segments/{self.segment.id}/upload_image/',
            {'image': image1},
            format='multipart',
        )
        self.segment.refresh_from_db()
        old_path = self.segment.image_path

        # Second upload
        image2 = create_test_image('second.jpg', 'JPEG')
        self.client.post(
            f'/api/segments/{self.segment.id}/upload_image/',
            {'image': image2},
            format='multipart',
        )
        self.segment.refresh_from_db()
        # Old file should no longer exist on disk
        if old_path:
            full_old = os.path.join(TEMP_MEDIA_UPLOAD, old_path)
            self.assertFalse(os.path.isfile(full_old))

    # --- Missing file test ---

    def test_upload_no_file_returns_400(self):
        response = self.client.post(
            f'/api/segments/{self.segment.id}/upload_image/',
            {},
            format='multipart',
        )
        self.assertEqual(response.status_code, 400)

    # --- Storage path test ---

    def test_stored_path_includes_project_id(self):
        image = create_test_image()
        self.client.post(
            f'/api/segments/{self.segment.id}/upload_image/',
            {'image': image},
            format='multipart',
        )
        self.segment.refresh_from_db()
        self.assertIn(str(self.project.id), self.segment.image_path)
```

### Step 3 — Add `TestImageRemoval` class (4 tests)

```python
@override_settings(MEDIA_ROOT=TEMP_MEDIA_UPLOAD)
class TestImageRemoval(APITestCase):
    """Tests for DELETE /api/segments/{id}/remove_image/."""

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
            f'/api/segments/{self.segment.id}/upload_image/',
            {'image': image},
            format='multipart',
        )
        self.segment.refresh_from_db()

    def test_remove_existing_image(self):
        self._upload_image()
        old_path = self.segment.image_path
        response = self.client.delete(
            f'/api/segments/{self.segment.id}/remove_image/',
        )
        self.assertEqual(response.status_code, 200)
        self.segment.refresh_from_db()
        self.assertFalse(self.segment.image_path)
        # File should be deleted from disk
        if old_path:
            full = os.path.join(TEMP_MEDIA_UPLOAD, old_path)
            self.assertFalse(os.path.isfile(full))

    def test_remove_when_no_image_returns_400(self):
        response = self.client.delete(
            f'/api/segments/{self.segment.id}/remove_image/',
        )
        self.assertEqual(response.status_code, 400)

    def test_remove_locked_segment_returns_400(self):
        self._upload_image()
        self.segment.is_locked = True
        self.segment.save()
        response = self.client.delete(
            f'/api/segments/{self.segment.id}/remove_image/',
        )
        self.assertEqual(response.status_code, 400)

    def test_remove_when_file_already_missing_succeeds(self):
        """Self-healing: if DB has path but file is gone, still clears the field."""
        self._upload_image()
        # Manually delete the file from disk
        full = os.path.join(TEMP_MEDIA_UPLOAD, self.segment.image_path)
        if os.path.isfile(full):
            os.remove(full)
        response = self.client.delete(
            f'/api/segments/{self.segment.id}/remove_image/',
        )
        self.assertEqual(response.status_code, 200)
        self.segment.refresh_from_db()
        self.assertFalse(self.segment.image_path)
```

### Step 4 — Run all tests

```bash
cd backend
python manage.py test api
```

---

## Expected Output

```
backend/
└── api/
    └── tests.py            ← MODIFIED (2 test classes + 1 helper added)
```

---

## Validation

- [ ] `create_test_image()` helper generates valid images for JPEG, PNG, and WebP.
- [ ] `TestImageUpload` — all 10 tests pass (3 valid formats, 3 invalid files, 1 lock, 1 re-upload cleanup, 1 no-file, 1 path check).
- [ ] `TestImageRemoval` — all 4 tests pass (remove existing, no image, locked, file-already-missing).
- [ ] `@override_settings(MEDIA_ROOT=...)` isolates test files from real media directory.
- [ ] `tearDown()` cleans up temporary directories to prevent disk bloat.
- [ ] `python manage.py test api` runs with zero failures across all test classes.

---

## Notes

- Always call `file.seek(0)` or read from a freshly created `BytesIO` — Pillow's `Image.verify()` consumes the stream.
- Use `SimpleUploadedFile` for constructing multipart uploads in DRF test client.
- BMP format is used for the oversized test because it's uncompressed, making it easy to exceed 20 MB.
- The self-healing test (file-already-missing) verifies that `remove_image` doesn't crash if the physical file was deleted outside the app.

---

> **Parent:** [SubPhase_02_02_Overview.md](./SubPhase_02_02_Overview.md) (Layer 2)
> **Phase:** [Phase_02_Overview.md](../Phase_02_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_02_02_11_Write_Segment_API_Tests.md](./Task_02_02_11_Write_Segment_API_Tests.md)
> **Next Task:** [Task_02_03_01](../SubPhase_02_03_Image_Upload_Timeline_Editor/Task_02_03_01*.md) (first task of SubPhase 02.03)
