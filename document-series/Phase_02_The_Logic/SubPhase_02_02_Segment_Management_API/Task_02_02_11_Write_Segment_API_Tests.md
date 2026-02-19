# Task 02.02.11 — Write Segment API Tests

> **Sub-Phase:** 02.02 — Segment Management API
> **Phase:** Phase 02 — The Logic
> **Complexity:** High
> **Dependencies:** Task 02.02.08 (URL Routing)
> **Parent Document:** [SubPhase_02_02_Overview.md](./SubPhase_02_02_Overview.md)

---

## Objective

Write comprehensive backend tests for segment list, PATCH, delete, reorder, and project delete operations in `backend/api/tests.py`.

---

## Instructions

### Step 1 — Add `TestSegmentList` class

```python
from rest_framework.test import APITestCase
from rest_framework import status
from api.models import Project, Segment


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
        self.assertEqual(len(response.data), 3)
        # Verify ordering
        indices = [s['sequence_index'] for s in response.data]
        self.assertEqual(indices, [0, 1, 2])

    def test_list_without_project_filter_returns_empty(self):
        response = self.client.get('/api/segments/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

    def test_retrieve_single_segment(self):
        seg = Segment.objects.first()
        response = self.client.get(f'/api/segments/{seg.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['id'], seg.id)
```

### Step 2 — Add `TestSegmentUpdate` class

```python
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
```

### Step 3 — Add `TestSegmentDelete` class

```python
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
        response = self.client.delete('/api/segments/99999/')
        self.assertEqual(response.status_code, 404)
```

### Step 4 — Add `TestSegmentReorder` class

```python
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
            'segment_order': [self.seg_c.id, self.seg_a.id, self.seg_b.id],
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.seg_c.refresh_from_db()
        self.assertEqual(self.seg_c.sequence_index, 0)

    def test_reorder_missing_ids_returns_400(self):
        response = self.client.post('/api/segments/reorder/', {
            'project_id': self.project.id,
            'segment_order': [self.seg_a.id],  # Missing b and c
        }, format='json')
        self.assertEqual(response.status_code, 400)

    def test_reorder_extra_ids_returns_400(self):
        response = self.client.post('/api/segments/reorder/', {
            'project_id': self.project.id,
            'segment_order': [self.seg_a.id, self.seg_b.id, self.seg_c.id, 99999],
        }, format='json')
        self.assertEqual(response.status_code, 400)

    def test_reorder_wrong_project_returns_404(self):
        response = self.client.post('/api/segments/reorder/', {
            'project_id': 99999,
            'segment_order': [1, 2, 3],
        }, format='json')
        self.assertEqual(response.status_code, 404)
```

### Step 5 — Add `TestProjectDelete` class

```python
import tempfile
import shutil
import os
from django.test import override_settings

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
```

### Step 6 — Run tests

```bash
cd backend
python manage.py test api
```

---

## Expected Output

```
backend/
└── api/
    └── tests.py            ← MODIFIED (5 test classes added)
```

---

## Validation

- [ ] `TestSegmentList` — all 3 tests pass.
- [ ] `TestSegmentUpdate` — all 5 tests pass.
- [ ] `TestSegmentDelete` — all 2 tests pass.
- [ ] `TestSegmentReorder` — all 4 tests pass.
- [ ] `TestProjectDelete` — all 3 tests pass.
- [ ] `python manage.py test api` runs with zero failures.

---

## Notes

- Use `@override_settings(MEDIA_ROOT=tempfile.mkdtemp())` for tests involving file operations to avoid polluting the real media directory.
- Clean up temporary directories in `tearDown()`.
- Image upload/removal tests are in the separate Task 02.02.12 to keep test classes focused.

---

> **Parent:** [SubPhase_02_02_Overview.md](./SubPhase_02_02_Overview.md) (Layer 2)
> **Phase:** [Phase_02_Overview.md](../Phase_02_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_02_02_10_Update_TypeScript_Types.md](./Task_02_02_10_Update_TypeScript_Types.md)
> **Next Task:** [Task_02_02_12_Write_Image_Upload_Tests.md](./Task_02_02_12_Write_Image_Upload_Tests.md)
