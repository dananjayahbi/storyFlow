# Task 05.01.10 — Write Timing Tests

## Metadata

| Field         | Value                                                                |
| ------------- | -------------------------------------------------------------------- |
| **Task ID**   | 05.01.10                                                             |
| **Task Name** | Write Timing Tests                                                   |
| **Sub-Phase** | 05.01 — Subtitle Generation & Overlay                                |
| **Phase**     | Phase 05 — The Polish                                                |
| **Complexity**| Medium                                                               |
| **Dependencies** | Task 05.01.03 (timing calculator must be implemented)             |
| **Parent**    | [SubPhase_05_01_Overview.md](./SubPhase_05_01_Overview.md)           |

---

## Objective

Write comprehensive unit tests for the calculate_subtitle_timing function verifying proportional duration distribution, minimum duration enforcement, no-gap continuity, and exact total-duration summation. These tests validate the mathematical correctness of the timing algorithm.

---

## Instructions

### Step 1 — Create the Test Class

In backend/core_engine/tests.py, add a test class named SubtitleTimingTests. Import calculate_subtitle_timing from core_engine.subtitle_engine.

### Step 2 — Write Edge Case Tests

- test_empty_chunks: pass an empty list with any duration, assert the result is an empty list.
- test_single_chunk: pass a single chunk with duration 3.0, assert the result is [(0.0, 3.0)].

### Step 3 — Write Distribution Tests

- test_equal_word_count: pass 3 chunks each containing 3 words with duration 6.0. Assert each gets 2.0 seconds.
- test_proportional_distribution: pass two chunks with different word counts (e.g., 6 words and 3 words) with duration 9.0. Assert the durations are proportional (approximately 6.0 and 3.0 seconds).

### Step 4 — Write Continuity Tests

- test_no_gaps: pass multiple chunks and assert that for every consecutive pair, start[i+1] equals start[i] + duration[i] within floating-point precision (use assertAlmostEqual with places=6).
- test_start_at_zero: pass any chunks and assert the first tuple's start time is 0.0.
- test_total_duration_matches: pass any chunks and assert the sum of all durations equals total_duration (use assertAlmostEqual with places=6).

### Step 5 — Write Minimum Duration Tests

- test_minimum_duration_enforced: pass 10 chunks of 1 word each with duration 3.0. After normalization, verify each duration is positive and the total equals 3.0.
- test_single_word_chunks: pass 5 single-word chunks with duration 5.0. Assert each gets at least 0.5 seconds (or proportionally normalized if total minimum exceeds duration).

### Step 6 — Write Stress Tests

- test_very_short_duration: pass 2 chunks with duration 0.3 seconds. Assert the function still produces valid timings without errors.
- test_many_chunks: pass 20 chunks with duration 60.0. Assert all timings are valid and the total is correct.

---

## Expected Output

A SubtitleTimingTests class in backend/core_engine/tests.py containing approximately 11 test methods that validate the timing calculator's mathematical properties across all scenarios.

---

## Validation

- [ ] SubtitleTimingTests class exists in the test file.
- [ ] Empty chunks returns empty list.
- [ ] Single chunk gets the full duration.
- [ ] Equal-word chunks get equal durations.
- [ ] Proportional distribution is correct.
- [ ] No gaps between consecutive subtitles.
- [ ] First subtitle starts at 0.0.
- [ ] Sum of durations equals total_duration.
- [ ] Minimum duration is enforced (within normalization constraints).
- [ ] Very short durations and many chunks are handled without errors.
- [ ] All assertions use assertAlmostEqual for float comparisons.

---

## Notes

- These are pure math tests — no I/O, no external dependencies. They run in milliseconds.
- Use assertAlmostEqual with places=6 for all floating-point comparisons to avoid false failures from float precision.
- The minimum duration guarantee is "best effort" — when normalization is applied to fit total_duration, some chunks may end up below min_duration. Tests should verify the total-duration constraint takes priority.
- The no-gap invariant is the most important property to test: subtitles must be continuous with no silent gaps between them.

---

> **Parent:** [SubPhase_05_01_Overview.md](./SubPhase_05_01_Overview.md) (Layer 2)
> **Phase:** [Phase_05_Overview.md](../Phase_05_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
