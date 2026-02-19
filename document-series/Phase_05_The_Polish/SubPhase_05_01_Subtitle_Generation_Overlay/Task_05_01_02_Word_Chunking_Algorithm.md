# Task 05.01.02 — Word Chunking Algorithm

## Metadata

| Field         | Value                                                                |
| ------------- | -------------------------------------------------------------------- |
| **Task ID**   | 05.01.02                                                             |
| **Task Name** | Word Chunking Algorithm                                              |
| **Sub-Phase** | 05.01 — Subtitle Generation & Overlay                                |
| **Phase**     | Phase 05 — The Polish                                                |
| **Complexity**| High                                                                 |
| **Dependencies** | Task 05.01.01 (module skeleton must exist)                        |
| **Parent**    | [SubPhase_05_01_Overview.md](./SubPhase_05_01_Overview.md)           |

---

## Objective

Implement the chunk_text function that splits a segment's text_content into natural, readable word-chunks of 5–7 words each. The algorithm prefers breaking at sentence boundaries (periods, exclamation marks, question marks) and clause boundaries (commas, semicolons, colons, em dashes) to produce subtitle chunks that read naturally, while enforcing a maximum word count per chunk.

---

## Instructions

### Step 1 — Replace the Stub

In backend/core_engine/subtitle_engine.py, replace the chunk_text function stub (which raises NotImplementedError) with the full implementation.

### Step 2 — Handle Edge Cases Up Front

Before processing, handle edge cases: if text is None, empty, or whitespace-only, return an empty list. Normalize whitespace by joining text.split() — this collapses multiple spaces, tabs, and newlines into single spaces.

### Step 3 — Handle Short Text

If the total word count is less than or equal to max_words, return the entire text as a single-element list. No chunking is needed.

### Step 4 — Define Boundary Detection

Create a helper function _is_boundary_word that checks whether a word ends at a natural sentence or clause boundary. It should strip trailing quotation marks and parentheses before checking, so words like "dog." and "world!)" are both recognized as boundary words. The sentence boundaries are period, exclamation mark, and question mark. The clause boundaries are comma, semicolon, colon, em dash, and ellipsis.

### Step 5 — Implement the Chunking Loop

Iterate through the word list, building chunks one word at a time. For each word added to the current chunk:

- If the current chunk has reached max_words (hard break): finalize the chunk and start a new one.
- If the word is a boundary word AND the chunk has at least MIN_CHUNK_WORDS words (soft break): finalize the chunk and start a new one. This prefers natural breakpoints over arbitrary word-count splits.

### Step 6 — Handle Remaining Words (Orphan Prevention)

After the loop, if there are remaining words that haven't been finalized into a chunk, handle them: if only 1–2 words remain and the last finalized chunk is short enough to absorb them (combined total not exceeding max_words + 1), merge them into the last chunk. Otherwise, create a final chunk from the remaining words. This prevents awkward single-word subtitle chunks at the end of a passage.

### Step 7 — Finalize and Return

Join each chunk's word list into a single string and return the list of chunk strings. Ensure no chunk is an empty string and no chunk has leading or trailing whitespace.

---

## Expected Output

The chunk_text function in subtitle_engine.py is fully implemented. Given any input text, it returns a list of word-chunk strings where each chunk is 4–7 words (typically), preferring natural sentence and clause boundaries for breaks, with no orphan single-word chunks.

---

## Validation

- [ ] chunk_text("") returns an empty list.
- [ ] chunk_text("   ") returns an empty list.
- [ ] chunk_text("Hello") returns ["Hello"].
- [ ] Text with fewer than max_words returns a single chunk.
- [ ] Text with 12+ words produces 2+ chunks, each at most max_words.
- [ ] Sentence boundaries (period, exclamation, question) trigger breaks when chunk is long enough.
- [ ] Clause boundaries (comma, semicolon) trigger breaks when chunk is long enough.
- [ ] No orphan single-word final chunks (merged into previous chunk when feasible).
- [ ] Joining all chunks with spaces recovers all original words (no words lost).
- [ ] Extra whitespace and newlines are normalized.
- [ ] Chunks never contain empty strings.
- [ ] The max_words parameter is respected (customizable, default 6).

---

## Notes

- The algorithm operates on whitespace-split words — it does not perform NLP-level analysis. This keeps it fast and dependency-free.
- The soft break at MIN_CHUNK_WORDS (4) prevents very short chunks: a comma after word 2 is too early to break, but a comma after word 4 is a good breakpoint.
- Contractions (don't, won't) are treated as single words since they contain no whitespace.
- The orphan merge threshold of max_words + 1 allows slightly longer final chunks (e.g., 7 words when max is 6) to avoid creating a tiny orphan chunk.
- This function is pure Python string manipulation with no I/O, making it extremely fast and easy to unit test.

---

> **Parent:** [SubPhase_05_01_Overview.md](./SubPhase_05_01_Overview.md) (Layer 2)
> **Phase:** [Phase_05_Overview.md](../Phase_05_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
