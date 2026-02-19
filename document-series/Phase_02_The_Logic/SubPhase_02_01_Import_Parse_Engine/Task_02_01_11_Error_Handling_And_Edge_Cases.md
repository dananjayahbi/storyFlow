# Task 02.01.11 — Error Handling & Edge Cases

> **Sub-Phase:** 02.01 — Import & Parse Engine
> **Phase:** Phase 02 — The Logic
> **Complexity:** Medium
> **Dependencies:** Task 02.01.06 (Backend Tests), Task 02.01.10 (Frontend Tests)
> **Parent Document:** [SubPhase_02_01_Overview.md](./SubPhase_02_01_Overview.md)

---

## Objective

Harden the entire import pipeline against edge cases and ensure consistent error handling across both backend and frontend layers. This is a finalization pass done after the core pipeline works end-to-end.

---

## Instructions

### Step 1 — Backend parser edge cases

**File:** `backend/api/parsers.py`

| Edge Case | Expected Behavior |
|---|---|
| `title` is only whitespace (e.g., `"   "`) | Treat as empty → `ParseError` |
| `text_content` is only whitespace | Treat as empty → `ParseError` |
| Extremely long text (>10,000 chars per segment) | Allow — no limit defined |
| Unicode characters in text and prompts (emoji, CJK, etc.) | Must work correctly — no ASCII restrictions |
| `segments` array with 100+ items | Allow — no limit defined, but verify performance |
| Segment is not a dict (e.g., a string or number) | `ParseError` identifying the index |

Ensure `.strip()` is applied before emptiness checks on `title` and `text_content`.

### Step 2 — Backend endpoint edge cases

**File:** `backend/api/views.py`

| Edge Case | Expected Response |
|---|---|
| `format` field missing from request | 400: `{"format": ["This field is required."]}` |
| `format` value is not "json" or "text" | 400: `{"format": ["\"xyz\" is not a valid choice."]}` |
| JSON format request missing `segments` key | 400: ParseError — "Missing or empty segments array" |
| Text format request missing `raw_text` key | 400: ParseError — "Missing or empty raw_text" |
| Request body is not valid JSON at all | 400: DRF's default parse error (automatic) |
| `GET /api/projects/import/` | 405: Method Not Allowed (automatic from `@api_view`) |

### Step 3 — Frontend UI edge cases

**File:** `frontend/components/ImportDialog.tsx`

| Edge Case | Expected Behavior |
|---|---|
| Network error (API unreachable) | Show generic "Import failed. Please try again." message |
| Very long error messages from backend | Scroll within the error display area (use `overflow-y-auto max-h-32`) |
| Rapid double-clicks on "Import" button | Debounced by `isSubmitting` state — second click is ignored |
| Dialog close during active request | Let the request complete silently (no crash if component unmounts) |
| Pasting malformed JSON in JSON mode | Show client-side "Invalid JSON format" error before hitting API |

For the unmount safety, wrap the state updates in the `handleSubmit` catch/finally blocks:

```typescript
// Use a ref to track if component is still mounted
const mountedRef = useRef(true);
useEffect(() => {
  return () => { mountedRef.current = false; };
}, []);

// In handleSubmit, guard state updates:
if (mountedRef.current) {
  setErrors(...);
  setIsSubmitting(false);
}
```

### Step 4 — Add edge case tests

**Backend tests** — add to `backend/api/tests.py`:

```python
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
```

### Step 5 — Verify all tests pass

```bash
cd backend
python manage.py test api

cd ../frontend
npm test
```

---

## Expected Output

```
backend/
└── api/
    ├── parsers.py          ← MODIFIED (edge case handling hardened)
    ├── validators.py       ← (reviewed — no changes if already robust)
    ├── views.py            ← (reviewed — no changes if already robust)
    └── tests.py            ← MODIFIED (edge case test classes added)

frontend/
└── components/
    └── ImportDialog.tsx     ← MODIFIED (unmount safety, error overflow)
```

---

## Validation

- [ ] Whitespace-only `title` is rejected by parsers.
- [ ] Whitespace-only `text_content` is rejected by parsers.
- [ ] Unicode characters work correctly in both parsers.
- [ ] 100+ segments are handled without errors.
- [ ] Missing `format` field returns 400 with appropriate error.
- [ ] Invalid `format` value returns 400 with appropriate error.
- [ ] `GET /api/projects/import/` returns 405.
- [ ] Network errors show a generic user-friendly message in the frontend.
- [ ] Rapid double-clicks are debounced by `isSubmitting`.
- [ ] Dialog close during active request does not crash.
- [ ] All backend tests pass: `python manage.py test api`.
- [ ] All frontend tests pass: `npm test`.

---

## Notes

- This task is a **hardening pass** — it should only be done AFTER the core pipeline works end-to-end (Tasks 01–10).
- Focus on cases real users would encounter: pasting malformed content, network flakiness, whitespace issues.
- Do NOT add arbitrary limits on segment count or text length unless explicitly specified in the project design.
- This is the final task in SubPhase 02.01.

---

> **Parent:** [SubPhase_02_01_Overview.md](./SubPhase_02_01_Overview.md) (Layer 2)
> **Phase:** [Phase_02_Overview.md](../Phase_02_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_02_01_10_Write_Frontend_Import_Tests.md](./Task_02_01_10_Write_Frontend_Import_Tests.md)
> **Next Task:** — (last task in SubPhase 02.01; next is SubPhase 02.02)
