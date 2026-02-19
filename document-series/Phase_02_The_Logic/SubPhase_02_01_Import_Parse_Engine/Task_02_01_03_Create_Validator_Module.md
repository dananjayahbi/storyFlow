# Task 02.01.03 — Create Validator Module

> **Sub-Phase:** 02.01 — Import & Parse Engine
> **Phase:** Phase 02 — The Logic
> **Complexity:** Medium
> **Dependencies:** Task 02.01.01, Task 02.01.02 (validates the normalized format they produce)
> **Parent Document:** [SubPhase_02_01_Overview.md](./SubPhase_02_01_Overview.md)

---

## Objective

Implement the `validate_import_data()` function in a new `backend/api/validators.py` module that verifies the normalized data format produced by the parsers before it reaches the serializer for database writes.

---

## Instructions

### Step 1 — Create the validators module

Create the file `backend/api/validators.py`.

### Step 2 — Implement `validate_import_data`

```python
from rest_framework.exceptions import ValidationError


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
```

### Step 3 — Key design rules

| Rule | Detail |
|---|---|
| Collect all errors | Do NOT short-circuit on the first error — report every problem. |
| DRF-compatible format | Use `rest_framework.exceptions.ValidationError` so the endpoint can pass errors through directly. |
| No database interaction | The validator is a pure data-checking utility. |
| Called after parser | The parser converts raw input → normalized dict. The validator checks that dict. |
| Called before serializer | Only validated data reaches the serializer's `create()` method. |

---

## Expected Output

```
backend/
└── api/
    └── validators.py       ← NEW
```

---

## Validation

- [ ] `backend/api/validators.py` exists and is importable.
- [ ] `validate_import_data()` accepts valid normalized data and returns it unchanged.
- [ ] Rejects titles over 200 characters with `["Title must not exceed 200 characters."]`.
- [ ] Rejects empty or missing title with `["This field is required."]`.
- [ ] Rejects empty segments list with `["At least one segment is required."]`.
- [ ] Rejects segments with empty `text_content`.
- [ ] Rejects non-string `image_prompt` values.
- [ ] Rejects non-contiguous `sequence_index` values.
- [ ] Collects ALL errors (multiple segments with issues are all reported).
- [ ] Raises `rest_framework.exceptions.ValidationError` (not a plain `Exception`).

---

## Notes

- The error structure uses `{'index': i, 'errors': {...}}` for per-segment errors, allowing the frontend to highlight specific problem areas.
- This module is deliberately separate from `parsers.py` — separation of concerns: parsers transform, validators verify.

---

> **Parent:** [SubPhase_02_01_Overview.md](./SubPhase_02_01_Overview.md) (Layer 2)
> **Phase:** [Phase_02_Overview.md](../Phase_02_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_02_01_02_Create_Text_Parser.md](./Task_02_01_02_Create_Text_Parser.md)
> **Next Task:** [Task_02_01_04_Create_Import_Serializer.md](./Task_02_01_04_Create_Import_Serializer.md)
