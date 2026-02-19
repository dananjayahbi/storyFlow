# Task 05.02.08 — Write Multi Segment Integration Tests

## Layer 3 Task Document

---

| **Field**              | **Value**                                                                                      |
| ---------------------- | ---------------------------------------------------------------------------------------------- |
| **Task ID**            | 05.02.08                                                                                       |
| **Task Name**          | Write Multi Segment Integration Tests                                                          |
| **Sub-Phase**          | 05.02 — Transitions & Effects                                                                  |
| **Phase**              | Phase 05 — The Polish                                                                          |
| **Layer**              | Layer 3 (Task Document)                                                                        |
| **Status**             | Not Started                                                                                    |
| **Estimated Complexity** | High                                                                                         |
| **Parent Document**    | [SubPhase_05_02_Overview.md](./SubPhase_05_02_Overview.md) (Layer 2)                           |
| **Dependencies**       | Task 05.02.06 (all transition logic must be integrated and verified before integration testing) |
| **Output Files**       | `backend/core_engine/tests.py` (MODIFIED), `backend/api/tests.py` (MODIFIED)                  |

---

## Objective

Write full pipeline integration tests that render multi-segment projects with subtitles AND crossfade transitions, verifying the complete rendered output. These tests exercise the entire rendering pipeline from segment loading through Ken Burns effects, subtitle compositing, crossfade transitions, concatenation, and MP4 export — proving that all components work together correctly to produce a valid, properly-timed video file.

---

## Instructions

### Step 1 — Create a MultiSegmentIntegrationTests Test Class

Add a new test class named `MultiSegmentIntegrationTests` to `backend/core_engine/tests.py`, inheriting from Django's `TransactionTestCase` (or `TestCase` depending on database isolation needs). This class holds the full pipeline integration tests that exercise real video rendering.

### Step 2 — Implement Test Setup

Create a `setUp` method that prepares the test environment:

**Project creation:** Create a test `Project` instance with a small resolution such as 640 by 360 pixels. Small resolution keeps rendering fast while still exercising the full pipeline.

**GlobalSettings:** Create a `GlobalSettings` instance with subtitle-related settings configured (subtitle font size, color, position from SubPhase 05.01).

**Test media generation:** For each test segment, generate minimal test media files:
- **Images:** Create small solid-color images using Pillow (e.g., red, green, blue rectangles). These are easy to visually distinguish during debugging and fast to render.
- **Audio:** Create short synthetic WAV files using NumPy and soundfile. Generate arrays of silence at 22050 Hz with durations of 1–3 seconds per segment. These provide valid audio tracks without requiring TTS processing.

**Segment creation:** Create test `Segment` instances linked to the project, each with `text_content` (for subtitles), `image_file` pointing to the test image, `audio_file` pointing to the test WAV, and `audio_duration` matching the WAV duration.

**Temporary directories:** Use `tempfile.mkdtemp()` for test media directories and configure Django's `MEDIA_ROOT` to point to the temporary directory. This isolates test files from the real media storage.

### Step 3 — Implement Test Teardown

Create a `tearDown` method that cleans up all temporary files and directories created during testing. Remove all generated images, audio files, and rendered MP4 outputs. Use `shutil.rmtree` on the temporary media directory to ensure complete cleanup. This prevents test artifacts from accumulating and consuming disk space.

### Step 4 — Write the Two-Segment Crossfade Test

Create `test_two_segments_with_crossfade` that sets up a project with two segments of 2.0 seconds each. Call `render_project()` directly with the project ID. Assert the output MP4 file exists and has a non-zero file size. Assert the reported duration is approximately 3.5 seconds (4.0 minus one transition of 0.5) with a tolerance of 0.2 seconds to account for encoding precision.

### Step 5 — Write the Three-Segment Crossfade Test

Create `test_three_segments_with_crossfade` with three segments of 3.0 seconds each. Assert the output duration is approximately 8.0 seconds (9.0 minus two transitions of 0.5 each). Verify the MP4 file is valid and non-empty.

### Step 6 — Write the Five-Segment Crossfade Test

Create `test_five_segments_with_crossfade` with five segments of varying durations (e.g., 2.0, 3.0, 1.5, 2.5, 2.0 seconds). Calculate the expected duration as the sum of all durations minus four transitions of 0.5 each (total overlap of 2.0 seconds). Assert the output duration matches within tolerance.

### Step 7 — Write the Single-Segment Test

Create `test_single_segment_no_crossfade` with one segment of 3.0 seconds. Assert the output duration is approximately 3.0 seconds — no transition overlap should be subtracted. This verifies the single-segment guard clause from Task 05.02.03.

### Step 8 — Write the Crossfade With Subtitles Test

Create `test_crossfade_with_subtitles` with three segments, each having non-empty `text_content`. Render the project and assert a valid MP4 is produced with no errors. This test exercises the full subtitle-plus-transition pipeline. The assertion focuses on error-free completion rather than visual inspection (visual quality is verified manually in Task 05.02.06).

### Step 9 — Write the Crossfade Without Subtitles Test

Create `test_crossfade_without_subtitles` with three segments where `text_content` is empty or null. Render and assert a valid MP4 is produced. This ensures the transition logic works independently of the subtitle system.

### Step 10 — Write the ImageMagick Fallback Test

Create `test_crossfade_without_imagemagick` that mocks the `check_imagemagick()` function from `render_utils.py` to return `False`. Render a multi-segment project with subtitle text. Assert the render completes successfully, producing a valid MP4 with transitions but without subtitles (since ImageMagick is required for subtitle rendering). Assert the render result includes a warning about ImageMagick not being available.

### Step 11 — Write the Render Result Metadata Test

Create `test_render_result_includes_duration` that renders any multi-segment project and inspects the returned result dictionary. Assert it contains a `duration` field (actual duration), an `expected_duration` field (calculated from the overlap formula), and a `num_transitions` field (equal to the number of segments minus one). Verify the `duration` and `expected_duration` values are within 0.2 seconds of each other.

### Step 12 — Write the Render Warnings Test

Create `test_render_result_includes_warnings` that mocks ImageMagick as unavailable and renders a project with subtitle text. Assert the render result contains a `warnings` list with at least one entry about missing ImageMagick. When ImageMagick is available and subtitles render normally, the warnings list should be empty.

### Step 13 — Optional Visual Inspection Test

Add a test method decorated with `@unittest.skip("Manual visual test")` named `test_visual_crossfade_inspection`. This test renders a multi-segment video and prints the output file path to the console. It is normally skipped in automated test runs but can be un-skipped by a developer who wants to visually inspect the output in VLC or another media player. The method body simply renders the project, prints the path, and asserts the file exists.

### Step 14 — Add API-Level Integration Test

In `backend/api/tests.py`, add at least one API-level test that calls the render endpoint (POST) with a multi-segment project and verifies the response includes the expected duration and transition metadata. This confirms the transition behavior is exposed correctly through the REST API, not just at the core engine level.

### Step 15 — Duration Assertion Helper

Create a helper method on the test class named `assertDurationApproximate` that accepts an expected duration, an actual duration, and a tolerance (defaulting to 0.2 seconds). This helper calls `assertAlmostEqual` with a `delta` parameter and provides a descriptive error message including both values. Using a helper keeps the individual test methods concise and consistent.

---

## Expected Output

After completing this task:

- `backend/core_engine/tests.py` contains a `MultiSegmentIntegrationTests` class with at least 9 test methods.
- `backend/api/tests.py` contains at least one API-level render-with-transitions test.
- Tests cover: two-segment crossfade, three-segment crossfade, five-segment crossfade, single segment, crossfade with subtitles, crossfade without subtitles, ImageMagick fallback, render result metadata, render warnings, and optional visual inspection.
- All tests pass with zero failures.
- Test setup creates minimal test media (small images, short audio files) for fast execution.
- Test teardown cleans up all temporary files.

---

## Validation

- [ ] `MultiSegmentIntegrationTests` class exists in `backend/core_engine/tests.py`.
- [ ] Test setup creates a test project, segments, images, and audio files.
- [ ] Test teardown removes all temporary files and directories.
- [ ] Two-segment test asserts duration approximately equals sum minus one transition.
- [ ] Three-segment test asserts duration approximately equals sum minus two transitions.
- [ ] Five-segment test with varying durations produces correct expected duration.
- [ ] Single-segment test confirms no transition overlap is subtracted.
- [ ] Crossfade-with-subtitles test produces a valid MP4 without errors.
- [ ] Crossfade-without-subtitles test produces a valid MP4 without errors.
- [ ] ImageMagick fallback test mocks `check_imagemagick` and verifies warnings.
- [ ] Render result metadata test verifies `duration`, `expected_duration`, and `num_transitions` fields.
- [ ] API-level test verifies transition metadata through the REST endpoint.
- [ ] Duration tolerance is set to 0.2 seconds for all duration assertions.
- [ ] Each individual test completes within approximately 30 seconds (small resolution, short audio).
- [ ] All tests pass in both local development and CI environments (ImageMagick-dependent tests are skippable).

---

## Notes

- Integration tests are inherently slower than unit tests because they perform actual video rendering. Using 640 by 360 resolution and 1–3 second audio files keeps each test under 30 seconds while still exercising the full pipeline.
- The `render_project()` function is called directly in core engine tests (not through the API). This tests the rendering logic without HTTP overhead. The API-level test in `api/tests.py` adds the additional HTTP layer verification.
- Synthetic test media (solid-color images, silence audio) is sufficient for integration testing. The tests verify correct pipeline behavior and duration math — they do not assess visual or audio quality, which is done manually in Tasks 05.02.04 and 05.02.06.
- Tests that depend on ImageMagick should use `@unittest.skipUnless(check_imagemagick(), "ImageMagick not installed")` to gracefully skip in environments where ImageMagick is unavailable. The `test_crossfade_without_imagemagick` test mocks ImageMagick absence and should always run.
- The visual inspection test is deliberately skipped by default. It serves as a developer tool for ad-hoc quality checks during development.

---

> **Parent:** [SubPhase_05_02_Overview.md](./SubPhase_05_02_Overview.md) (Layer 2)
> **Phase:** [Phase_05_Overview.md](../Phase_05_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
