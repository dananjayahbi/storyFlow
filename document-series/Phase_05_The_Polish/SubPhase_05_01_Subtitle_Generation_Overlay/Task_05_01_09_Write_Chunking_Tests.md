# Task 05.01.09 — Write Chunking Tests

## Metadata

| Field         | Value                                                                |
| ------------- | -------------------------------------------------------------------- |
| **Task ID**   | 05.01.09                                                             |
| **Task Name** | Write Chunking Tests                                                 |
| **Sub-Phase** | 05.01 — Subtitle Generation & Overlay                                |
| **Phase**     | Phase 05 — The Polish                                                |
| **Complexity**| Medium                                                               |
| **Dependencies** | Task 05.01.02 (chunking algorithm must be implemented)            |
| **Parent**    | [SubPhase_05_01_Overview.md](./SubPhase_05_01_Overview.md)           |

---

## Objective

Write comprehensive unit tests for the chunk_text function covering various text lengths, punctuation patterns, edge cases, and the "no words lost" invariant. These tests validate that the chunking algorithm produces natural, readable subtitle chunks within the expected word-count range.

---

## Instructions

### Step 1 — Create or Extend the Test File

In backend/core_engine/tests.py, create (or extend) the file and add a test class named ChunkTextTests. Import chunk_text from core_engine.subtitle_engine. Use standard unittest.TestCase or Django's TestCase as the base class (no database access is needed for these pure function tests).

### Step 2 — Write Edge Case Tests

Add tests for boundary conditions:

- test_empty_text: pass an empty string, assert the result is an empty list.
- test_whitespace_only: pass a string of spaces and newlines, assert empty list.
- test_single_word: pass "Hello", assert result is ["Hello"].
- test_few_words_under_max: pass a string with fewer words than max_words (e.g., "The quick brown fox"), assert a single chunk containing the full text.
- test_exactly_max_words: pass exactly max_words words, assert a single chunk.

### Step 3 — Write Basic Chunking Tests

- test_basic_chunking: pass 12+ words with no punctuation, assert the result has 2+ chunks, each with at most max_words words.
- test_long_text_30_words: pass a 30-word paragraph, assert 5–6 chunks of 5–7 words each.

### Step 4 — Write Boundary-Preference Tests

- test_sentence_boundary_break: pass text with a period mid-way (e.g., "First sentence. Second sentence follows here."), assert the chunks break at the period.
- test_comma_boundary_break: pass text with a comma at a reasonable position, assert the chunk breaks at the comma when the chunk is long enough.
- test_multiple_sentences: pass 3+ short sentences, assert each sentence is approximately one chunk.

### Step 5 — Write Orphan Prevention Tests

- test_no_orphan_single_word: craft text where the last word would naturally be orphaned, assert it is merged into the previous chunk instead of standing alone.

### Step 6 — Write Invariant Tests

- test_preserves_all_words: pass any text, join all chunks with spaces, split both the original and result by whitespace, assert the word lists are equal (no words lost, no words added).
- test_no_empty_chunks: pass various texts, assert no chunk in the result is an empty string.

### Step 7 — Write Custom Parameter Tests

- test_custom_max_words: pass text with max_words=4, assert all chunks have at most 4 words.
- test_newlines_and_extra_spaces: pass text with embedded newlines and multiple spaces, assert whitespace is normalized and chunking is correct.
- test_punctuation_mid_word: pass text with contractions (don't, won't, can't), assert they are treated as single words.

---

## Expected Output

A ChunkTextTests class in backend/core_engine/tests.py containing approximately 15 test methods that thoroughly validate the chunk_text function's behavior across all scenarios.

---

## Validation

- [ ] ChunkTextTests class exists in the test file.
- [ ] Empty and whitespace inputs return empty lists.
- [ ] Short texts return single chunks.
- [ ] Long texts produce appropriately-sized chunks.
- [ ] Sentence boundaries trigger breaks.
- [ ] Clause boundaries trigger breaks when chunk is long enough.
- [ ] No orphan single-word chunks.
- [ ] All original words are preserved across chunks.
- [ ] Custom max_words parameter is respected.
- [ ] Whitespace normalization works correctly.
- [ ] All tests pass and run quickly (no I/O, no external dependencies).

---

## Notes

- These are pure unit tests — no database, no ImageMagick, no MoviePy, no file I/O. They run in milliseconds.
- The "no words lost" invariant test is the most critical: it proves that the chunking algorithm is a pure partitioning operation on the word sequence.
- Tests should use assertEqual for exact chunk comparisons where the expected output is deterministic, and assertLessEqual for chunk size constraints where exact output depends on boundary detection heuristics.

---

> **Parent:** [SubPhase_05_01_Overview.md](./SubPhase_05_01_Overview.md) (Layer 2)
> **Phase:** [Phase_05_Overview.md](../Phase_05_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
