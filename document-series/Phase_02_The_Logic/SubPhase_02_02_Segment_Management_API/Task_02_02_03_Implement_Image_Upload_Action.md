# Task 02.02.03 — Implement Image Upload Action

> **Sub-Phase:** 02.02 — Segment Management API
> **Phase:** Phase 02 — The Logic
> **Complexity:** High
> **Dependencies:** Task 02.02.01 (Segment ViewSet)
> **Parent Document:** [SubPhase_02_02_Overview.md](./SubPhase_02_02_Overview.md)

---

## Objective

Add the `upload-image` custom action to `SegmentViewSet` that accepts `multipart/form-data` image uploads, validates with Pillow, stores files with a structured path, and handles old-image cleanup.

---

## Instructions

### Step 1 — Add `validate_image_upload` to `backend/api/validators.py`

```python
from PIL import Image
from rest_framework.exceptions import ValidationError


ALLOWED_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp']
MAX_IMAGE_SIZE = 20 * 1024 * 1024  # 20MB


def validate_image_upload(file):
    """Validate an uploaded image file.

    Checks:
      1. File extension is JPEG, PNG, or WebP.
      2. File size ≤ 20MB.
      3. File is a valid image (Pillow verify).

    Returns the validated file with pointer reset to 0.
    """
    import os

    # 1. Check extension
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError({
            'error': 'Invalid image file',
            'details': f'Accepted formats: JPEG, PNG, WebP. Got: {ext}'
        })

    # 2. Check file size
    if file.size > MAX_IMAGE_SIZE:
        raise ValidationError({
            'error': 'File too large',
            'details': f'Maximum size is 20MB. Got: {file.size / (1024*1024):.1f}MB'
        })

    # 3. Validate with Pillow
    try:
        img = Image.open(file)
        img.verify()
    except Exception as e:
        raise ValidationError({
            'error': 'Invalid image file',
            'details': f'File is corrupt or not a valid image: {str(e)}'
        })

    # CRITICAL: Reset file pointer after verify()
    file.seek(0)

    return file
```

### Step 2 — Add `upload_image` action to `SegmentViewSet`

```python
import os
from django.conf import settings
from django.core.files.storage import default_storage
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status

from .validators import validate_image_upload


@action(detail=True, methods=['post'], url_path='upload-image')
def upload_image(self, request, pk=None):
    segment = self.get_object()

    # 1. Lock check
    if segment.is_locked:
        return Response(
            {'error': 'Cannot modify a locked segment.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # 2. Get uploaded file
    file = request.FILES.get('image')
    if not file:
        return Response(
            {'error': 'No image file provided'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # 3. Validate
    validate_image_upload(file)

    # 4. Delete old image if exists
    if segment.image_file:
        old_path = segment.image_file.path
        if os.path.isfile(old_path):
            os.remove(old_path)

    # 5. Build storage path and save
    relative_path = f'projects/{segment.project_id}/images/{segment.id}_{file.name}'
    saved_path = default_storage.save(relative_path, file)

    # 6. Update model field
    segment.image_file.name = saved_path
    segment.save()

    return Response({
        'id': segment.id,
        'image_file': segment.image_file.url,
        'message': 'Image uploaded successfully',
    }, status=status.HTTP_200_OK)
```

### Step 3 — Key details

| Detail | Explanation |
|---|---|
| **Pillow `verify()` + `seek(0)`** | `verify()` consumes the file stream. Without `seek(0)`, the saved file will be empty/truncated. |
| **`default_storage.save()`** | Used instead of `ImageField.save()` for explicit control over the storage path structure. |
| **Old image cleanup** | If a segment already has an image, the old file is deleted from disk BEFORE saving the new one to prevent orphaned files. |
| **Storage path** | `media/projects/{project_id}/images/{segment_id}_{original_filename}` |
| **Locked segment check** | Returns 400 if `is_locked` is `True`. |
| **DRF auto-routing** | The `@action(detail=True, url_path='upload-image')` decorator causes the DRF router to auto-generate the `POST /api/segments/{pk}/upload-image/` route. |

---

## Expected Output

```
backend/
└── api/
    ├── views.py            ← MODIFIED (upload_image action added to SegmentViewSet)
    └── validators.py       ← MODIFIED (validate_image_upload function added)
```

---

## Validation

- [ ] `POST /api/segments/{id}/upload-image/` with valid JPEG → 200 with `image_file` URL.
- [ ] Valid PNG → 200.
- [ ] Valid WebP → 200.
- [ ] Uploaded file exists on disk at `media/projects/{project_id}/images/{segment_id}_{filename}`.
- [ ] Non-image file (e.g., `.txt`) → 400 with "Invalid image file" error.
- [ ] Corrupt image → 400 with "File is corrupt" error.
- [ ] File over 20MB → 400 with "File too large" error.
- [ ] No file attached → 400 with "No image file provided" error.
- [ ] Locked segment → 400 with "Cannot modify a locked segment" error.
- [ ] Re-upload deletes the old image file from disk before saving the new one.
- [ ] `file.seek(0)` is called after `Pillow.verify()`.

---

## Notes

- This is the most complex single task in SubPhase 02.02 due to file I/O, Pillow validation, old-image cleanup, and directory creation.
- The storage directory (`media/projects/{project_id}/images/`) is created automatically by `default_storage.save()`.
- Do NOT manually set `Content-Type: multipart/form-data` on the frontend — Axios handles it automatically when sending `FormData` (covered in Task 02.02.09 notes).

---

> **Parent:** [SubPhase_02_02_Overview.md](./SubPhase_02_02_Overview.md) (Layer 2)
> **Phase:** [Phase_02_Overview.md](../Phase_02_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_02_02_02_Implement_Segment_PATCH.md](./Task_02_02_02_Implement_Segment_PATCH.md)
> **Next Task:** [Task_02_02_04_Implement_Image_Remove_Action.md](./Task_02_02_04_Implement_Image_Remove_Action.md)
