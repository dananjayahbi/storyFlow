# Task 02.01.06 — Write Import Tests

> **Sub-Phase:** 02.01 — Import & Parse Engine
> **Phase:** Phase 02 — The Logic
> **Complexity:** High
> **Dependencies:** Task 02.01.05 (Import Endpoint fully wired)
> **Parent Document:** [SubPhase_02_01_Overview.md](./SubPhase_02_01_Overview.md)

---

## Objective

Write comprehensive backend unit tests covering the entire import pipeline — parsers, validator, serializer, and endpoint — in `backend/api/tests.py`.

---

## Instructions

### Step 1 — Add `TestJSONParser` class

```python
from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework import status

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
```

### Step 2 — Add `TestTextParser` class

```python
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
```

### Step 3 — Add `TestImportValidator` class

```python
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
```

### Step 4 — Add `TestImportEndpoint` class

```python
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
```

### Step 5 — Run tests

```bash
cd backend
python manage.py test api
```

All tests must pass with zero failures.

---

## Expected Output

```
backend/
└── api/
    └── tests.py            ← MODIFIED (4 test classes added)
```

---

## Validation

- [ ] `TestJSONParser` — all 6 tests pass.
- [ ] `TestTextParser` — all 7 tests pass.
- [ ] `TestImportValidator` — all 5 tests pass.
- [ ] `TestImportEndpoint` — all 6 tests pass.
- [ ] `python manage.py test api` runs with zero failures.
- [ ] Atomicity test confirms no partial data on failed import.
- [ ] Uses Django `TestCase` for unit tests (no DB) and DRF `APITestCase` for endpoint tests (with DB).

---

## Notes

- Parser and validator tests use `TestCase` (no database needed). Endpoint tests use `APITestCase` (database required for creating records).
- Tests should be self-contained — no reliance on fixtures or external state.
- Test method names should be descriptive (`test_missing_title_raises_parse_error`, not `test_1`).

---

> **Parent:** [SubPhase_02_01_Overview.md](./SubPhase_02_01_Overview.md) (Layer 2)
> **Phase:** [Phase_02_Overview.md](../Phase_02_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_02_01_05_Build_Import_Endpoint.md](./Task_02_01_05_Build_Import_Endpoint.md)
> **Next Task:** [Task_02_01_07_Build_ImportDialog_Component.md](./Task_02_01_07_Build_ImportDialog_Component.md)
