# Task 02.01.01 — Create JSON Parser

> **Sub-Phase:** 02.01 — Import & Parse Engine
> **Phase:** Phase 02 — The Logic
> **Complexity:** Medium
> **Dependencies:** None
> **Parent Document:** [SubPhase_02_01_Overview.md](./SubPhase_02_01_Overview.md)

---

## Objective

Implement the `JSONParser` class and the shared `ParseError` exception in a new `backend/api/parsers.py` module. The parser converts a JSON import payload into the normalized internal data format consumed by the validator and serializer.

---

## Instructions

### Step 1 — Create the parsers module

Create the file `backend/api/parsers.py`.

### Step 2 — Define `ParseError` exception

```python
class ParseError(Exception):
    """Raised when import data cannot be parsed into the normalized format."""

    def __init__(self, message: str, details: str | None = None):
        self.message = message
        self.details = details
        super().__init__(self.message)
```

- This is a **custom** exception, NOT `rest_framework.exceptions.ParseError`.
- Both `message` (human-readable summary) and `details` (optional specifics) are stored as attributes for the view/serializer to construct error responses.

### Step 3 — Implement `JSONParser` class

```python
class JSONParser:
    """Parses a JSON import payload into the normalized data format."""

    def parse(self, data: dict) -> dict:
        # 1. Extract and validate title
        title = data.get('title', '').strip()
        if not title:
            raise ParseError("Missing or empty title")

        # 2. Extract and validate segments list
        segments = data.get('segments')
        if not isinstance(segments, list) or len(segments) == 0:
            raise ParseError("Missing or empty segments array")

        # 3. Build normalized segments
        normalized_segments = []
        for i, segment in enumerate(segments):
            if not isinstance(segment, dict):
                raise ParseError(
                    "Invalid segment format",
                    details=f"Segment at index {i} is not an object"
                )

            text_content = segment.get('text_content', '').strip()
            if not text_content:
                raise ParseError(
                    "Missing text_content",
                    details=f"Segment at index {i} is missing text_content"
                )

            image_prompt = segment.get('image_prompt', '')
            if not isinstance(image_prompt, str):
                image_prompt = str(image_prompt)

            normalized_segments.append({
                'text_content': text_content,
                'image_prompt': image_prompt.strip(),
                'sequence_index': i,
            })

        # 4. Return normalized format
        return {
            'title': title,
            'segments': normalized_segments,
        }
```

### Step 4 — Verify design rules

- The parser does **NOT** interact with the database — it is a pure data transformation utility.
- Extra keys in the input (e.g., `author`, `metadata`) are silently ignored via selective `data.get()`.
- `title` comes from the request body top level, NOT from within segments.
- `image_prompt` defaults to `""` when missing from a segment.
- `text_content` is required — a `ParseError` identifies the offending segment index.
- `sequence_index` is auto-assigned based on array position (0, 1, 2, …).

---

## Expected Output

```
backend/
└── api/
    └── parsers.py          ← NEW (contains ParseError + JSONParser)
```

---

## Validation

- [ ] `backend/api/parsers.py` exists and is importable.
- [ ] `ParseError` class has `message` and `details` attributes.
- [ ] `JSONParser().parse()` converts valid JSON data to the normalized format with correct `sequence_index` values.
- [ ] `JSONParser().parse()` raises `ParseError` when `title` is missing or empty.
- [ ] `JSONParser().parse()` raises `ParseError` when `segments` is missing, not a list, or empty.
- [ ] `JSONParser().parse()` raises `ParseError` when any segment lacks `text_content`.
- [ ] `JSONParser().parse()` defaults `image_prompt` to `""` when absent.
- [ ] Extra keys in the input are silently ignored.

---

## Notes

- This file will also contain `TextParser` (Task 02.01.02) — leave room for it below `JSONParser`.
- Do NOT confuse this `ParseError` with `rest_framework.exceptions.ParseError` — they are separate classes. The view/serializer will catch `api.parsers.ParseError` specifically.
- Whitespace-only `title` or `text_content` should be treated as empty (`.strip()` before checking).

---

> **Parent:** [SubPhase_02_01_Overview.md](./SubPhase_02_01_Overview.md) (Layer 2)
> **Phase:** [Phase_02_Overview.md](../Phase_02_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** — (first task in SubPhase 02.01)
> **Next Task:** [Task_02_01_02_Create_Text_Parser.md](./Task_02_01_02_Create_Text_Parser.md)
