# Task 04.02.12 — Write Integration Tests

## Metadata

| Field         | Value                                                                |
| ------------- | -------------------------------------------------------------------- |
| **Task ID**   | 04.02.12                                                             |
| **Task Name** | Write Integration Tests                                              |
| **Sub-Phase** | 04.02 — Ken Burns Effect Implementation                              |
| **Phase**     | Phase 04 — The Vision: Video Rendering Engine                        |
| **Complexity**| High                                                                 |
| **Dependencies** | Task 04.02.08 (full pipeline integration), Task 04.02.10 (performance optimization) |
| **Parent**    | [SubPhase_04_02_Overview.md](./SubPhase_04_02_Overview.md)           |

---

## Objective

Write a comprehensive suite of integration tests that validate the full Ken Burns rendering pipeline from source image through to exported MP4 with visible camera motion. Unlike the math tests (Task 04.02.11) which test individual functions in isolation, these tests exercise the complete flow: loading images, preparing them for zoom headroom, generating animated frames via make_frame, integrating with the video renderer, concatenating segments, and exporting a playable MP4 file. These tests confirm that all components work together correctly and that the resulting video exhibits actual Ken Burns motion.

---

## Instructions

### Step 1 — Create the Test Class

Add a new test class named KenBurnsIntegrationTests to backend/api/tests.py. This class extends Django's TestCase. Import apply_ken_burns from core_engine.ken_burns, render_project from core_engine.video_renderer, and all necessary Django models (Project, Segment, GlobalSettings).

### Step 2 — Implement Test Setup

Define a setUp method that creates the test fixtures required for integration testing:

- Create a test Project instance with resolution_width set to 640, resolution_height set to 360, and framerate set to 24. Use small resolution for fast test execution.
- Create a GlobalSettings instance with zoom_intensity set to 1.3.
- Create three test Segment instances with sequential sequence_index values (0, 1, 2), each associated with the test project.
- For each segment, generate a synthetic test image using Pillow. Create a solid-color RGB image at 800 by 600 pixels, using a different color for each segment (for example, red, green, and blue). Save each image to a temporary file path. Set the segment's image_file field to point to this temporary file.
- For each segment, generate a synthetic silent audio file using soundfile. Write a one-second array of zeros at 24000 Hz sample rate in WAV format to a temporary file path. Set the segment's audio_file field and audio_duration field accordingly.
- Store all temporary file paths for cleanup in tearDown.

### Step 3 — Test apply_ken_burns Returns VideoClip

Write a test method that directly calls apply_ken_burns with one of the test images. Pass image_path pointing to the first segment's image, duration of 1.0 seconds, resolution of (640, 360), zoom_intensity of 1.3, fps of 24, and segment_index of 0. Assert that the returned object has the attributes expected of a VideoClip: it should have a make_frame attribute (callable), its duration should equal 1.0, and its fps should equal 24. Close the clip after assertions.

### Step 4 — Test Frame Output Shape

Write a test method that creates a Ken Burns clip and calls its make_frame method directly. Call make_frame with t values of 0.0, 0.5, and 1.0. For each call, assert that the returned NumPy array has shape (360, 640, 3) — height first, then width, then 3 color channels. Assert that the dtype is uint8. Close the clip after all assertions.

### Step 5 — Test Frames Are Different for Non-Center Direction

Write a test method that creates a Ken Burns clip with segment_index set to 1 (which selects the top_left-to-bottom_right direction). Get the frame at t equals 0.0 and the frame at t equals 1.0 (the full duration). Assert that these two frames are NOT identical by comparing them with NumPy's array_equal function and asserting the result is False. Different crop positions at start and end should produce different pixel data, confirming that actual camera motion is happening. Close the clip.

### Step 6 — Test Center Direction Produces Identical Frames

Write a test method that creates a Ken Burns clip with segment_index set to 0 (which selects the center-to-center direction). Get the frame at t equals 0.0 and the frame at t equals 1.0. Assert that these two frames ARE identical using NumPy's array_equal function and asserting the result is True. Since both start and end positions are center, the crop box does not move between frames, producing identical output. Close the clip.

### Step 7 — Test Different Segments Get Different Directions

Write a test method that creates two Ken Burns clips: one with segment_index 0 and one with segment_index 1. Get the frame at t equals 0 for both clips. Assert that the frames are not identical (since different directions produce different initial crop positions). Close both clips.

### Step 8 — Test Ken Burns With Small Image

Write a test method that creates a deliberately small test image (400 by 300 pixels) — smaller than the minimum required for 640 by 360 output at zoom 1.3 (which needs 832 by 468). Call apply_ken_burns with this small image. Assert that the call succeeds without errors (the image should be upscaled internally by load_and_prepare_image). Assert that the frame output shape is correct (360, 640, 3). Close the clip.

### Step 9 — Test Ken Burns With Large Image

Write a test method that creates a deliberately large test image (3000 by 2000 pixels). Call apply_ken_burns with this image. Assert that the call succeeds. Assert that the frame output shape is correct. This validates that the image preparation logic handles large images without crashes or excessive memory usage. Close the clip.

### Step 10 — Test Full Render With Ken Burns

Write a test method that exercises the complete rendering pipeline. Use the three-segment setup from setUp. Call render_project with the test project's ID. Assert that the output MP4 file exists on disk. Assert that the file size is greater than zero. Assert that the returned result dictionary contains the expected keys: output_path, duration, and file_size. Assert that the total duration is approximately 3 seconds (three segments times one second each), allowing a tolerance of plus or minus 0.5 seconds to account for MoviePy's frame alignment. Store the output path for cleanup.

### Step 11 — Test Render With Zoom Intensity 1.0

Write a test method that updates the GlobalSettings zoom_intensity to 1.0 (no zoom). Call render_project and assert that it produces a valid MP4 file. This validates that the pipeline handles the edge case where the crop box equals the output resolution — technically no zoom but the Ken Burns code path still executes.

### Step 12 — Test Render With High Zoom Intensity

Write a test method that updates the GlobalSettings zoom_intensity to 2.0. Call render_project and assert that it produces a valid MP4 file. This validates that higher zoom intensities work correctly with the smaller crop box and more pronounced zoom-in effect.

### Step 13 — Implement Test Teardown

Define a tearDown method that cleans up all temporary files created during testing:

- Remove all temporary image files.
- Remove all temporary audio files.
- Remove any output MP4 files generated by render_project.
- Clean up test database records (Django's TestCase handles this automatically via transaction rollback, but file system artifacts must be manually removed).

Use try/except around file deletions to prevent teardown failures if a file was already deleted or never created.

---

## Expected Output

A test class named KenBurnsIntegrationTests in backend/api/tests.py containing at least 10 test methods. These tests create real images, real audio files, and real video output, exercising the full Ken Burns pipeline. All tests pass when run with python manage.py test. The total execution time for the integration test class should be under 60 seconds due to the use of small resolutions (640 by 360) and short audio durations (1 second per segment).

---

## Validation

- [ ] KenBurnsIntegrationTests class exists in backend/api/tests.py.
- [ ] The class contains at least 10 test methods.
- [ ] setUp creates test Project, Segments, GlobalSettings, images, and audio files.
- [ ] tearDown cleans up all temporary files.
- [ ] apply_ken_burns returns a clip with correct duration and FPS.
- [ ] Frame output shape is (360, 640, 3) with dtype uint8.
- [ ] Frames differ for non-center directions (camera motion verified).
- [ ] Frames are identical for center-to-center direction.
- [ ] Small images are upscaled successfully without errors.
- [ ] Large images are handled without crashes.
- [ ] Full render_project produces a valid, non-empty MP4 file.
- [ ] Render works with zoom_intensity 1.0 (no zoom edge case).
- [ ] Render works with zoom_intensity 2.0 (high zoom).
- [ ] All clips are explicitly closed after testing to prevent resource leaks.
- [ ] All tests pass with python manage.py test.
- [ ] Total integration test time is under 60 seconds.

---

## Notes

- The "frames are different" test (Step 5) is the most important validation in this class. It directly confirms that the Ken Burns effect produces actual camera motion. If the make_frame implementation had a bug (for example, always returning the center crop regardless of time), this test would catch it.
- Integration tests use small resolutions (640 by 360) and short durations (1 second) to keep execution time manageable. At 24 FPS with 3 segments, the total frame count is only 72 frames, which renders in under a second.
- Synthetic test images with solid colors (red, green, blue) are sufficient for validating the pipeline. The Ken Burns effect works on any image content — the important thing is that the crop positions change between frames, producing different pixel data.
- All VideoClip objects must be explicitly closed in tests using their close method. Without explicit closing, the clips hold references to NumPy arrays and Pillow Image objects via closures, which can cause memory accumulation across multiple test runs.
- The soundfile library (installed during Phase 03 for TTS) is used to generate synthetic WAV files. These are one-second silent audio clips that provide the duration information the renderer needs for audio-video synchronization.
- Django's TestCase automatically wraps each test in a transaction that is rolled back after the test completes. This handles database cleanup automatically. However, file system artifacts (temporary images, audio files, and rendered MP4s) are not affected by transaction rollback and must be cleaned up manually in tearDown.

---

> **Parent:** [SubPhase_04_02_Overview.md](./SubPhase_04_02_Overview.md) (Layer 2)
> **Phase:** [Phase_04_Overview.md](../Phase_04_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
