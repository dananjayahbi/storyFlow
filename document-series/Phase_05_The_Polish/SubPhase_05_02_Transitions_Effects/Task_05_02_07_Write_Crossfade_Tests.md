# Task 05.02.07 — Write Crossfade Tests

## Layer 3 Task Document

---

| **Field**              | **Value**                                                                                      |
| ---------------------- | ---------------------------------------------------------------------------------------------- |
| **Task ID**            | 05.02.07                                                                                       |
| **Task Name**          | Write Crossfade Tests                                                                          |
| **Sub-Phase**          | 05.02 — Transitions & Effects                                                                  |
| **Phase**              | Phase 05 — The Polish                                                                          |
| **Layer**              | Layer 3 (Task Document)                                                                        |
| **Status**             | Not Started                                                                                    |
| **Estimated Complexity** | Medium                                                                                       |
| **Parent Document**    | [SubPhase_05_02_Overview.md](./SubPhase_05_02_Overview.md) (Layer 2)                           |
| **Dependencies**       | Task 05.02.01 (crossfade function), Task 05.02.05 (duration math function)                    |
| **Output Files**       | `backend/core_engine/tests.py` (MODIFIED)                                                      |

---

## Objective

Write unit tests for the crossfade transition logic and the duration adjustment calculation function. These tests verify that `apply_crossfade_transitions()` correctly applies crossfade effects to clips based on their position in the list, and that `calculate_total_duration_with_transitions()` produces mathematically correct results for all input scenarios. All tests use mock clip objects — no actual video rendering, ImageMagick, or FFmpeg is required.

---

## Instructions

### Step 1 — Create a CrossfadeTransitionTests Test Class

Add a new test class named `CrossfadeTransitionTests` to `backend/core_engine/tests.py`, inheriting from Django's `TestCase`. This class will contain all unit tests for the crossfade transition functions.

### Step 2 — Create a Mock Clip Factory Helper

Create a helper function (either as a module-level utility or a method on the test class) named `create_mock_clip` that accepts a `duration` parameter and returns a `MagicMock` object configured to behave like a MoviePy `VideoClip`. The mock should have:

- A `duration` attribute set to the provided value.
- `crossfadein` as a `MagicMock` that returns the mock itself (simulating MoviePy's method chaining pattern where crossfade methods return a new clip).
- `crossfadeout` as a `MagicMock` that also returns the mock itself.

This factory pattern avoids creating real MoviePy clips, making the tests fast and independent of video processing dependencies.

### Step 3 — Write Tests for apply_crossfade_transitions

Implement the following test cases:

**test_empty_clips:** Pass an empty list to `apply_crossfade_transitions`. Assert the returned list is also empty. Neither `crossfadein` nor `crossfadeout` should be called.

**test_single_clip_no_transition:** Pass a list with one mock clip. Assert the returned list contains that same clip. Assert that neither `crossfadein` nor `crossfadeout` was called on the clip — single clips receive no crossfade effects.

**test_two_clips_crossfade:** Pass a list with two mock clips. Assert the first clip received `crossfadeout` with the transition duration (0.5) but NOT `crossfadein`. Assert the second clip received `crossfadein` with 0.5 but NOT `crossfadeout`. This verifies the first/last clip behavior: the video starts clean and ends clean.

**test_three_clips_crossfade:** Pass a list with three mock clips. Assert the first clip received only `crossfadeout`. Assert the middle clip received both `crossfadein` and `crossfadeout`. Assert the last clip received only `crossfadein`. This tests the full first/middle/last pattern.

**test_clip_count_preserved:** Pass a list of five mock clips. Assert the returned list has exactly five elements. The crossfade function should never add or remove clips — it only modifies them.

**test_custom_transition_duration:** Pass two mock clips with `transition_duration=1.0`. Assert that `crossfadeout` was called with `1.0` on the first clip and `crossfadein` was called with `1.0` on the second clip. This verifies the function respects the custom duration parameter rather than always using the default.

### Step 4 — Write Tests for calculate_total_duration_with_transitions

Implement the following test cases:

**test_empty_durations:** Pass an empty list. Assert the result is `0.0`.

**test_single_duration:** Pass `[5.0]`. Assert the result is `5.0`. One clip has zero transitions.

**test_two_clips_duration:** Pass `[5.0, 5.0]`. Assert the result is `9.5`. Two clips have one transition: 10.0 minus 0.5 equals 9.5.

**test_three_clips_duration:** Pass `[5.0, 5.0, 5.0]`. Assert the result is `14.0`. Three clips have two transitions: 15.0 minus 1.0 equals 14.0.

**test_five_clips_duration:** Pass `[3.0, 3.0, 3.0, 3.0, 3.0]`. Assert the result is `13.0`. Five clips have four transitions: 15.0 minus 2.0 equals 13.0.

**test_varying_durations:** Pass `[2.0, 5.0, 3.0]`. Assert the result is `9.0`. Sum is 10.0, two transitions reduce by 1.0.

**test_custom_transition_duration_math:** Pass `[5.0, 5.0]` with `transition_duration=1.0`. Assert the result is `9.0`. The custom duration of 1.0 removes 1.0 second from the total.

**test_very_short_clips_duration:** Pass `[0.1, 0.1]` with the default 0.5-second transition. Assert the result is `-0.3` (or whatever the raw mathematical result is). This edge case verifies the function does not clamp to zero — it returns honest arithmetic. While this scenario cannot occur in StoryFlow (TTS segments are always longer than 0.5 seconds), the function should be mathematically correct.

### Step 5 — Verify Method Call Assertions

For each crossfade test, use MagicMock assertion methods to verify the exact calls made. Use `assert_called_once_with` to verify that crossfade methods were called with the correct transition duration. Use `assert_not_called` to verify that inappropriate methods were NOT called (e.g., `crossfadein` should not be called on the first clip).

### Step 6 — Run All Tests and Verify Green

After writing all test cases, run the Django test suite for the `core_engine` app to confirm all new tests pass. The test class should integrate cleanly with the existing test structure without conflicting with tests from earlier phases and sub-phases.

---

## Expected Output

After completing this task, `backend/core_engine/tests.py` contains:

- A `CrossfadeTransitionTests` class with at least 14 test methods.
- A `create_mock_clip` helper for generating mock VideoClip objects.
- Tests for `apply_crossfade_transitions`: empty list, single clip, two clips, three clips, clip count preservation, custom duration.
- Tests for `calculate_total_duration_with_transitions`: empty list, single clip, two clips, three clips, five clips, varying durations, custom duration, very short clips.
- All tests pass with zero failures.

---

## Validation

- [ ] `CrossfadeTransitionTests` class exists in `backend/core_engine/tests.py`.
- [ ] `create_mock_clip` helper creates mock clips with `duration`, `crossfadein`, and `crossfadeout` attributes.
- [ ] All `apply_crossfade_transitions` test cases pass.
- [ ] All `calculate_total_duration_with_transitions` test cases pass.
- [ ] Tests verify correct method calls using MagicMock assertions.
- [ ] Tests verify that inappropriate methods are NOT called (e.g., no `crossfadein` on the first clip).
- [ ] No test requires actual video rendering, ImageMagick, or FFmpeg.
- [ ] All tests are fast (complete in under 1 second combined).
- [ ] The new test class integrates cleanly with existing tests — no conflicts or failures in other test classes.

---

## Notes

- These are pure unit tests with no external dependencies. They should run in any environment, including CI servers without ImageMagick or FFmpeg installed.
- The mock clip factory is designed to simulate MoviePy's API where `crossfadein()` and `crossfadeout()` return new clip objects. In the mock, the same mock object is returned for simplicity — this is sufficient for verifying that the methods were called with the correct arguments.
- The duration math tests are straightforward arithmetic assertions. They serve as regression guards to ensure the formula is not accidentally modified in future changes.
- The "very short clips" edge case test documents expected behavior for an extreme scenario. Even though it cannot occur in practice, having a test for it prevents future confusion about whether the function should clamp negative results.

---

> **Parent:** [SubPhase_05_02_Overview.md](./SubPhase_05_02_Overview.md) (Layer 2)
> **Phase:** [Phase_05_Overview.md](../Phase_05_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
