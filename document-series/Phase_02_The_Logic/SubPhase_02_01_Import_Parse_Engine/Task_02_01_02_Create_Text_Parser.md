# Task 02.01.02 — Create Text Parser

> **Sub-Phase:** 02.01 — Import & Parse Engine
> **Phase:** Phase 02 — The Logic
> **Complexity:** High
> **Dependencies:** Task 02.01.01 (shares `parsers.py` file and `ParseError`)
> **Parent Document:** [SubPhase_02_01_Overview.md](./SubPhase_02_01_Overview.md)

---

## Objective

Implement the `TextParser` class in `backend/api/parsers.py` that converts a `---`-delimited plain-text import payload into the same normalized internal format produced by `JSONParser`.

---

## Instructions

### Step 1 — Add `TextParser` to `backend/api/parsers.py`

Add the class below the existing `JSONParser` in the same file.

### Step 2 — Implement the `parse` method

```python
class TextParser:
    """Parses a text-based import payload into the normalized data format.

    Text format:
        Text: Narration content for segment 1...
        Prompt: Image description for segment 1...
        ---
        Text: Narration content for segment 2...
        Prompt: Image description for segment 2...
    """

    def parse(self, title: str, raw_text: str) -> dict:
        # 1. Validate title
        title = title.strip() if title else ''
        if not title:
            raise ParseError("Missing or empty title")

        # 2. Validate raw_text
        if not raw_text or not raw_text.strip():
            raise ParseError("Missing or empty raw_text")

        # 3. Split by --- delimiter (three or more hyphens on their own line)
        import re
        blocks = re.split(r'\n-{3,}\n', raw_text)

        # 4. Process each block
        normalized_segments = []
        block_number = 0

        for block in blocks:
            block = block.strip()
            if not block:
                continue  # Skip empty blocks

            block_number += 1

            # 5. Extract Text: and Prompt: lines using string operations
            text_lines = []
            prompt_lines = []

            for line in block.split('\n'):
                stripped = line.strip()
                lower = stripped.lower()

                if lower.startswith('text:'):
                    text_lines.append(stripped[5:].strip())
                elif lower.startswith('prompt:'):
                    prompt_lines.append(stripped[7:].strip())
                # Lines not matching Text: or Prompt: are silently ignored

            # 6. Validate: block must have at least one Text: line
            if not text_lines:
                raise ParseError(
                    "Text parsing failed",
                    details=f"Could not parse segment at block {block_number}"
                )

            # 7. Build normalized segment
            text_content = ' '.join(text_lines)  # Concatenate multiple Text: lines
            image_prompt = ' '.join(prompt_lines) if prompt_lines else ''

            if not text_content.strip():
                raise ParseError(
                    "Empty text content",
                    details=f"Block {block_number} has empty Text: value"
                )

            normalized_segments.append({
                'text_content': text_content,
                'image_prompt': image_prompt,
                'sequence_index': len(normalized_segments),  # 0-based
            })

        # 8. Must have at least one parsed segment
        if not normalized_segments:
            raise ParseError("No parseable segments found in text")

        return {
            'title': title,
            'segments': normalized_segments,
        }
```

### Step 3 — Verify delimiter handling

The `---` delimiter rules:

| Scenario | Behavior |
|---|---|
| `---` at the very start of `raw_text` | Empty first block → skipped |
| `---` at the very end of `raw_text` | Empty last block → skipped |
| Multiple consecutive `---` | Multiple empty blocks → all skipped |
| `----` (four+ hyphens) | Still treated as delimiter (`-{3,}` regex) |
| `---` inside a `Text:` value (e.g., "She said --- no") | NOT affected — delimiter requires `\n---\n` (own line) |

### Step 4 — Verify field extraction uses string operations

Per the project design decision ([Phase_02_Overview.md](../Phase_02_Overview.md) §4.1): **text parsing uses string splitting, NOT regex for field extraction**. The `Text:` and `Prompt:` prefix matching uses `str.lower().startswith()` and `str[n:].strip()` — no regex.

Regex is only used for the `---` delimiter splitting, which is acceptable.

---

## Expected Output

```
backend/
└── api/
    └── parsers.py          ← MODIFIED (TextParser added alongside JSONParser)
```

---

## Validation

- [ ] `TextParser` class exists in `backend/api/parsers.py`.
- [ ] `TextParser().parse()` correctly splits text by `---` and extracts `Text:` / `Prompt:` fields.
- [ ] `TextParser().parse()` handles case-insensitive `text:` and `prompt:` prefixes.
- [ ] Multiple `Text:` lines within one block are concatenated with a space.
- [ ] Multiple `Prompt:` lines within one block are concatenated with a space.
- [ ] Blocks without a `Text:` line raise `ParseError` identifying the block number.
- [ ] Missing `Prompt:` line defaults `image_prompt` to `""`.
- [ ] Empty blocks from consecutive `---` separators are skipped.
- [ ] `---` at the start or end of `raw_text` does not cause errors.
- [ ] Lines not matching `Text:` or `Prompt:` within a valid block are silently ignored.
- [ ] Empty `raw_text` or no parseable blocks raises `ParseError`.
- [ ] `sequence_index` values are assigned 0, 1, 2, … based on block order.
- [ ] Field extraction uses string splitting, NOT regex.

---

## Notes

- The `import re` statement at the top of `parse()` should ideally be moved to the module-level import. Shown inline here for clarity.
- The parser does NOT interact with the database — pure data transformation.
- `title` is passed as a separate parameter (from the request body's `title` field), not extracted from `raw_text`.
- This is the most complex parser due to the free-form text nature. Thorough testing in Task 02.01.06 is essential.

---

> **Parent:** [SubPhase_02_01_Overview.md](./SubPhase_02_01_Overview.md) (Layer 2)
> **Phase:** [Phase_02_Overview.md](../Phase_02_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_02_01_01_Create_JSON_Parser.md](./Task_02_01_01_Create_JSON_Parser.md)
> **Next Task:** [Task_02_01_03_Create_Validator_Module.md](./Task_02_01_03_Create_Validator_Module.md)
