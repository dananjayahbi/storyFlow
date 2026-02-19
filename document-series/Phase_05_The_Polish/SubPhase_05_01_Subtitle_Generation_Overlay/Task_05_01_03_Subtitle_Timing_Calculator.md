# Task 05.01.03 — Subtitle Timing Calculator

## Metadata

| Field         | Value                                                                |
| ------------- | -------------------------------------------------------------------- |
| **Task ID**   | 05.01.03                                                             |
| **Task Name** | Subtitle Timing Calculator                                           |
| **Sub-Phase** | 05.01 — Subtitle Generation & Overlay                                |
| **Phase**     | Phase 05 — The Polish                                                |
| **Complexity**| Medium                                                               |
| **Dependencies** | Task 05.01.01 (module skeleton must exist)                        |
| **Parent**    | [SubPhase_05_01_Overview.md](./SubPhase_05_01_Overview.md)           |

---

## Objective

Implement the calculate_subtitle_timing function that distributes a segment's audio duration proportionally across word-chunks. Chunks with more words receive more display time. The function enforces a minimum display time per chunk and guarantees zero gaps between consecutive subtitles — subtitles are continuous throughout the segment's duration.

---

## Instructions

### Step 1 — Replace the Stub

In backend/core_engine/subtitle_engine.py, replace the calculate_subtitle_timing function stub with the full implementation.

### Step 2 — Handle Edge Cases

If the chunks list is empty, return an empty list. If there is exactly one chunk, return a single tuple: (0.0, total_duration).

### Step 3 — Count Words Per Chunk

For each chunk, count the number of words by splitting on whitespace. Calculate the total word count across all chunks. If total words is zero (should not happen with valid chunks), return an empty list.

### Step 4 — Calculate Proportional Durations

For each chunk, compute the raw duration as the chunk's word count divided by total words, multiplied by total_duration. This gives longer chunks more time proportionally.

The formula for chunk $i$: $d_i = \frac{w_i}{\sum w_j} \times D_{\text{total}}$

### Step 5 — Enforce Minimum Duration

Apply the minimum duration floor: each chunk's duration becomes the maximum of its raw duration and min_duration (default 0.5 seconds). This ensures even single-word chunks are displayed long enough to be readable.

### Step 6 — Normalize to Fit Total Duration

After enforcing minimums, the sum of all durations may exceed total_duration. Scale all durations by a normalization factor so they sum to exactly total_duration. The normalization factor is total_duration divided by the current sum of durations.

The normalization formula: $d''_i = d'_i \times \frac{D_{\text{total}}}{\sum d'_j}$

### Step 7 — Build Start-Time Tuples

Compute cumulative start times: the first chunk starts at 0.0, each subsequent chunk starts where the previous one ends. Return a list of (start_time, duration) tuples.

### Step 8 — Handle Floating-Point Remainder

To prevent the last chunk's end time from being fractionally different from total_duration due to float precision, adjust the last chunk's duration to absorb any remainder: set it to total_duration minus its start_time.

---

## Expected Output

The calculate_subtitle_timing function is fully implemented. Given a list of text chunks and a total duration, it returns a list of (start_time, duration) tuples with proportional timing, minimum duration enforcement, no gaps, and exact total duration.

---

## Validation

- [ ] Empty chunks list returns empty list.
- [ ] Single chunk returns [(0.0, total_duration)].
- [ ] Equal-word chunks get equal durations.
- [ ] Longer chunks (more words) get proportionally more time.
- [ ] Sum of all durations equals total_duration (within float precision).
- [ ] No gaps: start[i+1] equals start[i] + duration[i] for all consecutive pairs.
- [ ] First subtitle starts at 0.0.
- [ ] Minimum duration (0.5s) is enforced per chunk.
- [ ] After normalization, durations still sum to total_duration.
- [ ] Works correctly with very short total durations (e.g., 0.3s).

---

## Notes

- All timing values are relative to the segment's clip, not absolute video time. Start time 0.0 means the beginning of this segment's clip.
- The normalization step is essential — without it, enforcing minimum durations would cause the total to exceed audio_duration, leading to subtitles extending beyond the audio.
- In extreme cases (many chunks with a very short total_duration), normalization may scale durations below the min_duration threshold. This is acceptable — the normalization guarantee (sum equals total_duration) takes priority over the minimum guarantee.
- This function is pure math with no I/O or dependencies beyond Python stdlib, making it fast and easy to test.

---

> **Parent:** [SubPhase_05_01_Overview.md](./SubPhase_05_01_Overview.md) (Layer 2)
> **Phase:** [Phase_05_Overview.md](../Phase_05_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
