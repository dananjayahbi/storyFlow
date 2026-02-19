# Task 05.02.05 — Duration Adjustment Math

## Layer 3 Task Document

---

| **Field**              | **Value**                                                                                      |
| ---------------------- | ---------------------------------------------------------------------------------------------- |
| **Task ID**            | 05.02.05                                                                                       |
| **Task Name**          | Duration Adjustment Math                                                                       |
| **Sub-Phase**          | 05.02 — Transitions & Effects                                                                  |
| **Phase**              | Phase 05 — The Polish                                                                          |
| **Layer**              | Layer 3 (Task Document)                                                                        |
| **Status**             | Not Started                                                                                    |
| **Estimated Complexity** | Low                                                                                          |
| **Parent Document**    | [SubPhase_05_02_Overview.md](./SubPhase_05_02_Overview.md) (Layer 2)                           |
| **Dependencies**       | None (independent pure function — can be implemented in parallel with Task 05.02.01)           |
| **Output Files**       | `backend/core_engine/video_renderer.py` (MODIFIED)                                             |

---

## Objective

Implement a utility function that calculates the expected total video duration accounting for crossfade overlaps between consecutive clips. This function is used for progress reporting, render result metadata, and validation of the final output duration against the mathematically expected value.

---

## Instructions

### Step 1 — Implement the Duration Calculation Function

Create a function named `calculate_total_duration_with_transitions` in `video_renderer.py` that accepts two parameters: a list of float values representing individual clip durations, and an optional `transition_duration` parameter defaulting to `TRANSITION_DURATION` (0.5 seconds).

The function applies the formula: total duration equals the sum of all individual clip durations minus the number of transitions multiplied by the transition duration. The number of transitions is always one less than the number of clips (each pair of adjacent clips has one transition between them).

For a concrete example: three clips of 5.0 seconds each with a 0.5-second transition produce a total of 15.0 minus 2 times 0.5, equaling 14.0 seconds. The two 0.5-second overlap regions account for the 1.0-second reduction from the naive sum.

### Step 2 — Handle Edge Cases

The function must handle the following edge cases gracefully:

**Empty list:** Return 0.0. This case should not occur in practice because pre-render validation rejects projects with no segments, but the function should behave correctly regardless.

**Single clip:** Return the clip's duration unchanged. With only one clip there are zero transitions and zero overlap — the total duration is simply the clip's own duration.

**Very short clips:** If any clip's duration is shorter than the transition duration, the mathematical formula still produces a valid result, but the visual output may look unusual (a clip entirely consumed by a transition). The function should compute the result honestly without clamping. Log a warning if any clip in the list has a duration shorter than the transition duration, reporting the number of such clips.

**Negative result:** In extreme edge cases (many very short clips with a long transition duration), the formula could produce a negative total duration. In practice this cannot happen in StoryFlow because TTS segments are always at least 0.5–1.0 seconds and the transition is 0.5 seconds. The function should return the raw mathematical result without clamping to zero — a negative value would indicate a configuration error that should be caught during testing.

### Step 3 — Add Type Hints and Docstring

The function should include full Python type hints for the parameters and return type. The docstring should explain the formula, provide worked examples for 1, 2, 3, and 5 clips, and note that the function is pure (no side effects, no I/O, no external dependencies).

### Step 4 — Integrate Into Progress Reporting

After the crossfade transitions are applied and clips are concatenated (Tasks 05.02.01 and 05.02.02), call `calculate_total_duration_with_transitions()` with the original clip durations (captured before crossfade application) and log the expected total duration at the info level. The log message should include both the naive sum of durations and the adjusted total, making it easy to verify the overlap math.

### Step 5 — Integrate Into Result Validation

After the final MP4 is rendered, compare the actual output clip's duration against the expected duration calculated by this function. If the difference exceeds 0.2 seconds (a tolerance that accounts for MoviePy and FFmpeg encoding precision), log a warning indicating the mismatch with both expected and actual values. This warning does not fail the render — it serves as a diagnostic signal that something may be off.

### Step 6 — Include Duration in Render Result Metadata

Add the following fields to the render result dictionary returned by `render_project()`: the actual duration of the final clip, the expected duration from the transition calculation, and the number of transitions applied. This metadata is available to the API layer and frontend for display and debugging.

---

## Expected Output

After completing this task:

- `calculate_total_duration_with_transitions()` is implemented as a pure function in `video_renderer.py`.
- The function correctly computes total duration using the overlap formula for any number of clips.
- Edge cases (empty list, single clip, very short clips) are handled correctly.
- The function is integrated into the render pipeline for logging, validation, and result metadata.
- A warning is logged if actual duration deviates from expected duration by more than 0.2 seconds.

---

## Validation

- [ ] `calculate_total_duration_with_transitions([])` returns `0.0`.
- [ ] `calculate_total_duration_with_transitions([5.0])` returns `5.0`.
- [ ] `calculate_total_duration_with_transitions([5.0, 5.0])` returns `9.5`.
- [ ] `calculate_total_duration_with_transitions([5.0, 5.0, 5.0])` returns `14.0`.
- [ ] `calculate_total_duration_with_transitions([3.0, 3.0, 3.0, 3.0, 3.0])` returns `13.0`.
- [ ] `calculate_total_duration_with_transitions([2.0, 5.0, 3.0])` returns `9.0`.
- [ ] Custom transition duration works: `calculate_total_duration_with_transitions([5.0, 5.0], 1.0)` returns `9.0`.
- [ ] A warning is logged for clips shorter than the transition duration.
- [ ] The function has proper type hints and a docstring with examples.
- [ ] Expected duration is logged after concatenation.
- [ ] Duration mismatch warning fires when actual differs from expected by more than 0.2 seconds.
- [ ] Render result metadata includes `duration`, `expected_duration`, and `num_transitions` fields.

---

## Notes

- This function is pure arithmetic — it contains no I/O, no video processing, and no external dependencies. It is trivially testable and is tested in Task 05.02.07.
- The duration calculation matters for user experience because users expect the output video length to be approximately equal to the sum of their narration lengths. The crossfade overlaps reduce the total by a small amount (e.g., a 10-segment project with 0.5-second transitions loses 4.5 seconds total). This reduction should be imperceptible to most users but is good to report accurately.
- The 0.2-second tolerance for duration validation accounts for slight differences in how MoviePy computes clip boundaries and how FFmpeg encodes the output. Exact frame-level precision is not guaranteed across the pipeline.

---

> **Parent:** [SubPhase_05_02_Overview.md](./SubPhase_05_02_Overview.md) (Layer 2)
> **Phase:** [Phase_05_Overview.md](../Phase_05_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
