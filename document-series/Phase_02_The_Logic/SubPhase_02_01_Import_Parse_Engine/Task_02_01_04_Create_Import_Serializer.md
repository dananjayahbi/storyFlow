# Task 02.01.04 — Create Import Serializer

> **Sub-Phase:** 02.01 — Import & Parse Engine
> **Phase:** Phase 02 — The Logic
> **Complexity:** Medium
> **Dependencies:** Task 02.01.03 (Validator Module)
> **Parent Document:** [SubPhase_02_01_Overview.md](./SubPhase_02_01_Overview.md)

---

## Objective

Implement `ProjectImportSerializer` in the existing `backend/api/serializers.py` file. This serializer orchestrates the full import pipeline: receives raw input → selects the appropriate parser → validates the normalized output → creates a `Project` with all `Segment` records in a single atomic database transaction.

---

## Instructions

### Step 1 — Add imports to `backend/api/serializers.py`

Add these imports to the top of the existing serializers file:

```python
from django.db import transaction
from rest_framework import serializers

from .parsers import JSONParser, TextParser, ParseError
from .validators import validate_import_data
from .models import Project, Segment
```

### Step 2 — Define `ProjectImportSerializer`

Add the serializer class below the existing serializers (`ProjectSerializer`, `SegmentSerializer`, etc.):

```python
class ProjectImportSerializer(serializers.Serializer):
    """Handles the import pipeline: parse → validate → create Project + Segments."""

    FORMAT_CHOICES = [('json', 'JSON'), ('text', 'Text')]

    format = serializers.ChoiceField(choices=FORMAT_CHOICES)
    title = serializers.CharField(max_length=200)
    segments = serializers.ListField(child=serializers.DictField(), required=False)
    raw_text = serializers.CharField(required=False)

    def validate(self, attrs):
        fmt = attrs.get('format')
        title = attrs.get('title', '')

        # Select parser and parse
        if fmt == 'json':
            parser = JSONParser()
            parsed = parser.parse({
                'title': title,
                'segments': attrs.get('segments', []),
            })
        elif fmt == 'text':
            parser = TextParser()
            parsed = parser.parse(
                title=title,
                raw_text=attrs.get('raw_text', ''),
            )
        else:
            raise serializers.ValidationError({'format': ["Must be 'json' or 'text'."]})

        # Validate normalized data
        validated = validate_import_data(parsed)

        # Store for create()
        attrs['_parsed_data'] = validated
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        parsed = validated_data['_parsed_data']

        # 1. Create Project
        project = Project.objects.create(
            title=parsed['title'],
            status='DRAFT',
        )

        # 2. Bulk create Segments
        segment_objects = [
            Segment(
                project=project,
                sequence_index=seg['sequence_index'],
                text_content=seg['text_content'],
                image_prompt=seg['image_prompt'],
            )
            for seg in parsed['segments']
        ]
        Segment.objects.bulk_create(segment_objects)

        # 3. Re-fetch with segments for response
        project = Project.objects.prefetch_related('segments').get(pk=project.pk)
        return project
```

### Step 3 — Understand the pipeline flow

```
Request data
    ↓
ProjectImportSerializer.validate()
    ├── format == "json" → JSONParser.parse(data)
    └── format == "text" → TextParser.parse(title, raw_text)
    ↓
validate_import_data(parsed_data)
    ↓
attrs['_parsed_data'] = validated_data
    ↓
ProjectImportSerializer.create(validated_data)
    ├── Project.objects.create(...)
    ├── Segment.objects.bulk_create(...)
    └── return project (with prefetched segments)
```

### Step 4 — Key design rules

- **`@transaction.atomic`** on `create()` ensures that if segment creation fails partway through, the project creation is also rolled back. No orphaned records.
- **`bulk_create`** is used for efficiency instead of creating segments one-by-one in a loop.
- This serializer handles **INPUT only**. The view will use the existing `ProjectDetailSerializer` (with nested `SegmentSerializer`) to serialize the **response**.
- `ParseError` from the parsers will propagate up through `validate()`. The view catches it and converts to an HTTP 400 response.
- The `_parsed_data` key is a private convention to pass validated/normalized data from `validate()` to `create()`.

---

## Expected Output

```
backend/
└── api/
    └── serializers.py      ← MODIFIED (ProjectImportSerializer added)
```

---

## Validation

- [ ] `ProjectImportSerializer` exists in `backend/api/serializers.py`.
- [ ] `validate()` routes to `JSONParser` when `format="json"`.
- [ ] `validate()` routes to `TextParser` when `format="text"`.
- [ ] `validate()` calls `validate_import_data()` on the parsed output.
- [ ] `create()` is decorated with `@transaction.atomic`.
- [ ] `create()` creates a `Project` record with `status='DRAFT'`.
- [ ] `create()` uses `Segment.objects.bulk_create()` for all segments.
- [ ] `create()` returns a project instance with prefetched segments.
- [ ] A failed segment creation rolls back the project creation (atomicity).

---

## Notes

- The `segments` field (ListField) is only required when `format="json"`. The `raw_text` field is only required when `format="text"`. Both are marked `required=False` on the serializer, with conditional validation inside `validate()`.
- Do NOT put parsing logic directly in `validate()` — call the parser classes. This maintains the separation of concerns (parsers.py → validators.py → serializers.py).

---

> **Parent:** [SubPhase_02_01_Overview.md](./SubPhase_02_01_Overview.md) (Layer 2)
> **Phase:** [Phase_02_Overview.md](../Phase_02_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_02_01_03_Create_Validator_Module.md](./Task_02_01_03_Create_Validator_Module.md)
> **Next Task:** [Task_02_01_05_Build_Import_Endpoint.md](./Task_02_01_05_Build_Import_Endpoint.md)
