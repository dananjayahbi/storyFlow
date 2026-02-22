from rest_framework.exceptions import ValidationError

import os
import re

ALLOWED_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp']
MAX_IMAGE_SIZE = 20 * 1024 * 1024  # 20MB

# ── Font upload constants (Task 05.03.03 + 05.03.14) ──
ALLOWED_FONT_EXTENSIONS = ['.ttf', '.otf', '.woff', '.woff2']
MAX_FONT_SIZE = 10 * 1024 * 1024  # 10MB

# ── Hex color validation (Task 05.03.03) ──
HEX_COLOR_REGEX = re.compile(r'^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$')


def validate_project_for_render(project):
    """Validate that a project is ready for video rendering.

    Checks that the project has at least one segment and that every
    segment has both an image file and an audio file assigned **and**
    present on disk.  Collects all errors in a single pass (no
    short-circuiting) so the caller can report everything at once.

    Args:
        project: A ``Project`` model instance.

    Returns:
        ``None`` if the project is ready to render, or a ``dict`` with:
        - ``missing_images``: list of segment ID strings lacking images.
        - ``missing_audio``: list of segment ID strings lacking audio.
        - ``message``: human-readable summary of the validation errors.
    """
    from api.models import Segment  # noqa: E402

    segments = Segment.objects.filter(project=project).order_by("sequence_index")

    if not segments.exists():
        return {
            "missing_images": [],
            "missing_audio": [],
            "message": "Project has no segments to render.",
        }

    missing_images = []
    missing_audio = []

    for seg in segments:
        # Check image file
        if not seg.image_file:
            missing_images.append(str(seg.id))
        elif not os.path.exists(seg.image_file.path):
            missing_images.append(str(seg.id))

        # Check audio file
        if not seg.audio_file:
            missing_audio.append(str(seg.id))
        elif not os.path.exists(seg.audio_file.path):
            missing_audio.append(str(seg.id))

    if missing_images or missing_audio:
        parts = []
        if missing_images:
            parts.append(
                f"{len(missing_images)} segment(s) missing image files"
            )
        if missing_audio:
            parts.append(
                f"{len(missing_audio)} segment(s) missing audio files"
            )
        return {
            "missing_images": missing_images,
            "missing_audio": missing_audio,
            "message": "; ".join(parts) + ".",
        }

    return None


def validate_image_upload(file):
    """Validate an uploaded image file.

    Checks:
      1. File extension is JPEG, PNG, or WebP.
      2. File size ≤ 20MB.
      3. File is a valid image (Pillow verify).

    Returns the validated file with pointer reset to 0.
    """
    import os
    from PIL import Image

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


def validate_import_data(data: dict) -> dict:
    """Validate the normalized import data format.

    Collects ALL errors before raising — does NOT short-circuit
    on the first error.

    Args:
        data: Normalized dict with 'title' and 'segments' keys.

    Returns:
        The validated data (unchanged) if valid.

    Raises:
        ValidationError: DRF-style error dict with all validation failures.
    """
    errors = {}

    # 1. Validate title
    title = data.get('title', '')
    if not isinstance(title, str) or not title.strip():
        errors['title'] = ['This field is required.']
    elif len(title) > 200:
        errors['title'] = ['Title must not exceed 200 characters.']

    # 2. Validate segments list
    segments = data.get('segments')
    if not isinstance(segments, list) or len(segments) == 0:
        errors['segments'] = ['At least one segment is required.']
    else:
        segment_errors = []
        seen_indices = set()

        for i, segment in enumerate(segments):
            seg_errs = {}

            # 2a. text_content — required, non-empty string
            tc = segment.get('text_content', '')
            if not isinstance(tc, str) or not tc.strip():
                seg_errs['text_content'] = ['This field is required.']

            # 2b. image_prompt — must be a string (can be empty)
            ip = segment.get('image_prompt', '')
            if not isinstance(ip, str):
                seg_errs['image_prompt'] = ['Must be a string.']

            # 2c. sequence_index — non-negative integer
            si = segment.get('sequence_index')
            if not isinstance(si, int) or si < 0:
                seg_errs['sequence_index'] = ['Must be a non-negative integer.']
            else:
                seen_indices.add(si)

            if seg_errs:
                segment_errors.append({'index': i, 'errors': seg_errs})

        # 2d. Verify contiguous sequence starting from 0
        if segments and not segment_errors:
            expected = set(range(len(segments)))
            if seen_indices != expected:
                errors['segments'] = [
                    'sequence_index values must form a contiguous sequence starting from 0.'
                ]

        if segment_errors:
            errors.setdefault('segments', [])
            if isinstance(errors['segments'], list):
                errors['segments'].extend(segment_errors)
            else:
                errors['segments'] = segment_errors

    # 3. Raise if any errors collected
    if errors:
        raise ValidationError(errors)

    return data


def validate_font_upload(file):
    """Validate an uploaded font file (.ttf or .otf).

    Checks:
      1. File extension is .ttf or .otf.
      2. File size ≤ 10 MB.

    Returns the validated file with pointer reset to 0.
    """
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in ALLOWED_FONT_EXTENSIONS:
        raise ValidationError({
            'error': 'Invalid font file',
            'details': 'Only .ttf, .otf, .woff, and .woff2 files are accepted.',
        })

    if file.size > MAX_FONT_SIZE:
        raise ValidationError({
            'error': 'File too large',
            'details': f'Font file must be under 10 MB. Got: {file.size / (1024*1024):.1f}MB',
        })

    file.seek(0)
    return file
