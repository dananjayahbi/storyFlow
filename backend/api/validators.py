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
