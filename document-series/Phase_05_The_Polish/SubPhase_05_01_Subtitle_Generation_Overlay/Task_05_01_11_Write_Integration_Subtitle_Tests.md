# Task 05.01.11 — Write Integration Subtitle Tests

## Metadata

| Field         | Value                                                                |
| ------------- | -------------------------------------------------------------------- |
| **Task ID**   | 05.01.11                                                             |
| **Task Name** | Write Integration Subtitle Tests                                     |
| **Sub-Phase** | 05.01 — Subtitle Generation & Overlay                                |
| **Phase**     | Phase 05 — The Polish                                                |
| **Complexity**| High                                                                 |
| **Dependencies** | Task 05.01.05 (subtitle compositing in renderer must be complete) |
| **Parent**    | [SubPhase_05_01_Overview.md](./SubPhase_05_01_Overview.md)           |

---

## Objective

Write integration tests that exercise the full subtitle pipeline end-to-end: from text chunking through TextClip generation to composited video rendering. These tests verify that the subtitle engine integrates correctly with the video renderer, that rendered MP4 files contain subtitle overlays, and that edge cases (empty text, missing font, missing ImageMagick) are handled gracefully.

---

## Instructions

### Step 1 — Create the Test Class

In backend/core_engine/tests.py (and optionally backend/api/tests.py for API-level tests), add a test class named SubtitleIntegrationTests. Use Django's TestCase or APITestCase as the base class since these tests interact with the database.

### Step 2 — Implement setUp

Create the test fixtures:

- A Project instance with a small resolution (640×360) for fast test renders.
- A GlobalSettings instance with subtitle_font pointing to the bundled default font at backend/fonts/default.ttf and subtitle_color set to "#FFFFFF".
- Three Segment instances associated with the project, each with: text_content containing sample narration text, image_file referencing a small synthetic test image (a solid-color 640×360 image created with Pillow), audio_file referencing a short synthetic WAV file (1–2 seconds of silence), and audio_duration matching the audio file length.

Use tempfile.mkdtemp() for the test media directory and override_settings(MEDIA_ROOT=...) to isolate test files.

### Step 3 — Implement tearDown

Clean up all temporary files, directories, and generated output MP4s to prevent test pollution.

### Step 4 — Write Render-With-Subtitles Test

test_render_with_subtitles: call render_project with the test project, assert the output MP4 file exists and has a size greater than zero, and assert no error-level warnings in the render result.

### Step 5 — Write Empty Text Test

test_render_without_text: set all segments' text_content to empty strings, call render_project, assert the output MP4 is produced without errors. This verifies that empty text_content does not cause failures — the renderer simply skips subtitle compositing.

### Step 6 — Write Missing ImageMagick Test

test_render_without_imagemagick: use unittest.mock.patch to mock check_imagemagick to return False, call render_project, assert the output MP4 is produced, and assert the render result's warnings list contains a "Subtitles disabled" message.

### Step 7 — Write Missing Font Fallback Test

test_render_with_missing_font: set GlobalSettings.subtitle_font to a non-existent file path, call render_project, assert the render succeeds (the font validation utility falls back to the default font) and the output MP4 is produced.

### Step 8 — Write Multi-Segment Test

test_render_multiple_segments_with_subtitles: render the project with all 3 test segments, assert the output MP4 is produced and its duration is approximately the sum of all segments' audio_duration values.

### Step 9 — Write Subtitle Function Isolation Tests

test_subtitle_clips_count: call create_subtitles_for_segment with text containing approximately 18 words (expecting 3 chunks), assert the function returns 3 TextClip objects.

test_subtitle_duration_matches_audio: call create_subtitles_for_segment with a 5.0-second audio_duration, sum the durations of the returned TextClips, and assert the total is approximately 5.0 seconds.

### Step 10 — Mark ImageMagick-Dependent Tests

For tests that require ImageMagick to be installed (the render tests that actually produce subtitles), decorate them with unittest.skipUnless(check_imagemagick(), "ImageMagick not installed"). This allows the test suite to run in CI environments without ImageMagick by skipping those specific tests rather than failing.

---

## Expected Output

A SubtitleIntegrationTests class containing approximately 7 test methods that validate the complete subtitle pipeline: rendering with subtitles, empty text handling, ImageMagick fallback, font fallback, multi-segment rendering, clip count verification, and duration matching.

---

## Validation

- [ ] SubtitleIntegrationTests class exists.
- [ ] setUp creates Project, GlobalSettings, Segments with synthetic files.
- [ ] tearDown cleans up all temporary files.
- [ ] MEDIA_ROOT is overridden to a temp directory.
- [ ] Render with subtitles produces a valid MP4 (size > 0).
- [ ] Empty text_content does not cause errors.
- [ ] Missing ImageMagick results in video without subtitles plus a warning.
- [ ] Missing font falls back to default font successfully.
- [ ] Multi-segment render produces correct total duration.
- [ ] create_subtitles_for_segment returns correct number of TextClips.
- [ ] Subtitle durations sum to audio_duration.
- [ ] ImageMagick-dependent tests are skippable.

---

## Notes

- Integration tests with actual rendering are slower than unit tests. Using small resolution (640×360) and short audio (1–2 seconds) keeps each test under 30 seconds.
- The create_subtitles_for_segment isolation tests (Steps 9) are faster because they test TextClip generation without full MP4 encoding. These require ImageMagick but are much quicker than full render tests.
- Synthetic test images can be created with Pillow: a solid-color 640×360 image saved as a temporary JPEG. Synthetic audio can be a WAV file of silence (zero bytes at 16kHz for 1–2 seconds).
- The mock.patch for check_imagemagick should target the import location in video_renderer.py (e.g., 'core_engine.video_renderer.check_imagemagick') rather than the definition location in render_utils.py.
- These integration tests serve as the final validation gate for SubPhase 05.01. If all tests pass, the subtitle engine is considered functionally complete.

---

> **Parent:** [SubPhase_05_01_Overview.md](./SubPhase_05_01_Overview.md) (Layer 2)
> **Phase:** [Phase_05_Overview.md](../Phase_05_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
