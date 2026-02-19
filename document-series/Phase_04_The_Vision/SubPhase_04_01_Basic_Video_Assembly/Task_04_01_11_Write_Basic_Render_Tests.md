# Task 04.01.11 — Write Basic Render Tests

> **Sub-Phase:** 04.01 — Basic Video Assembly
> **Phase:** Phase 04 — The Vision
> **Complexity:** High
> **Dependencies:** Task 04.01.08 (MP4 Export — entire pipeline complete)
> **Parent Document:** [SubPhase_04_01_Overview.md](./SubPhase_04_01_Overview.md)

---

## Objective

Create a comprehensive test suite that validates the entire basic video assembly pipeline using synthetic test data — generated images and silent audio — covering image resizing, clip pairing, concatenation, MP4 export, error handling, and progress callbacks.

---

## Instructions

### Step 1 — Create the test class

In `backend/api/tests.py`, add a new `VideoRendererTests(TestCase)` class (or create a separate test file if preferred). Set up synthetic test data in the `setUp` method.

### Step 2 — Generate synthetic test data in setUp

Create a test Project with small resolution values (`resolution_width=640`, `resolution_height=360`, `framerate=24`) for fast test execution. Create 3 test Segment objects with sequential `sequence_index` values. For each segment, generate a synthetic Pillow image using `Image.new("RGB", (800, 600), color=...)` and save it to a temporary path. Generate a silent `.wav` audio file using `soundfile`: write a NumPy array of zeros at 24000 Hz for 1 second. Set each segment's `image_file` and `audio_file` fields and `audio_duration`.

### Step 3 — Test FFmpeg check

Write `test_check_ffmpeg` that calls `render_utils.check_ffmpeg()` and asserts it returns `True`. FFmpeg must be installed for the render tests to function.

### Step 4 — Test image cover resize with multiple aspect ratios

Write four test methods covering the aspect ratio matrix:
- `test_cover_resize_16_9`: 2560×1440 source → 640×360 output. Assert shape is `(360, 640, 3)` and dtype is `uint8`.
- `test_cover_resize_4_3`: 1600×1200 source → 640×360 output. Assert correct shape.
- `test_cover_resize_square`: 1080×1080 source → 640×360 output. Assert correct shape.
- `test_cover_resize_portrait`: 800×1200 source → 640×360 output. Assert correct shape.

### Step 5 — Test output path management

Write `test_get_output_path` that calls `render_utils.get_output_path(project_id)`, asserts the returned path ends with `/output/final.mp4`, and asserts the output directory was created on disk.

### Step 6 — Test single-segment render

Write `test_render_single_segment` that sets up a project with 1 segment (image + audio), calls `render_project(project_id)`, and asserts: the output file exists, the result dict contains `output_path`, `duration`, and `file_size` keys, and `file_size > 0`.

### Step 7 — Test multi-segment render

Write `test_render_multiple_segments` using the 3-segment setup from setUp. Call `render_project(project_id)` and assert: the output file exists, file size is greater than zero, and total duration is approximately the sum of all audio durations (within 0.5 seconds tolerance).

### Step 8 — Test progress callback

Write `test_render_progress_callback` that defines a list-based callback which records each invocation. Call `render_project(project_id, on_progress=callback)` and assert the callback was called at least `total_segments + 1` times (once per segment plus the export phase).

### Step 9 — Test missing image error

Write `test_render_missing_image` that sets one segment's `image_file` to a non-existent path, calls `render_project(project_id)`, and asserts `FileNotFoundError` or `ValueError` is raised.

### Step 10 — Test missing audio error

Write `test_render_missing_audio` that sets one segment's `audio_file` to a non-existent path, calls `render_project(project_id)`, and asserts `FileNotFoundError` or `ValueError` is raised.

### Step 11 — Clean up in tearDown

In `tearDown`, remove all temporary image, audio, and output files created during tests. Clean up test database records. Use try/except around file deletions to handle already-deleted or locked files gracefully.

---

## Expected Output

```
backend/
└── api/
    └── tests.py ← MODIFIED (add VideoRendererTests class)
```

---

## Validation

- [ ] `VideoRendererTests` class exists with at least 10 test methods.
- [ ] Tests use synthetic data (generated images + silent audio).
- [ ] Tests use small resolution (640×360) and short audio (1 second) for speed.
- [ ] All four aspect ratio resize tests pass.
- [ ] Output path test verifies directory creation.
- [ ] Single-segment render produces a valid MP4.
- [ ] Multi-segment render duration matches sum of audio durations.
- [ ] Progress callback is invoked the expected number of times.
- [ ] Missing image/audio tests verify proper error handling.
- [ ] `tearDown` cleans up all temporary files.
- [ ] All tests pass: `python manage.py test`.
- [ ] Total test suite execution time under 30 seconds.

---

## Notes

- Tests use small resolutions (640×360) and short audio (1 second per segment) to keep execution time reasonable. The full 1920×1080 resolution is tested via the aspect ratio resize tests at the unit level.
- `soundfile` (installed in Phase 03) is used to generate synthetic `.wav` audio. A 1-second silent file is `np.zeros(24000)` at 24000 Hz sample rate.
- The test framerate is set to 24 (lower than the default 30) for slightly faster export.
- Tests validate functional correctness, not visual quality. Verifying that the MP4 exists and has the expected duration and file size is sufficient.
- On Windows, file locking can cause tearDown failures if clips are not properly closed. The test should be resilient to this with try/except in cleanup.

---

> **Parent:** [SubPhase_04_01_Overview.md](./SubPhase_04_01_Overview.md) (Layer 2)
> **Phase:** [Phase_04_Overview.md](../Phase_04_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_04_01_10_Output_Path_Management.md](./Task_04_01_10_Output_Path_Management.md)
> **Next Task:** SubPhase 04.02 — Ken Burns Effect
