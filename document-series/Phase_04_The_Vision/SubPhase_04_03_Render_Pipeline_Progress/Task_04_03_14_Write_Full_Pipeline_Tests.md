# Task 04.03.14 — Write Full Pipeline Tests

## Metadata

| Field         | Value                                                                |
| ------------- | -------------------------------------------------------------------- |
| **Task ID**   | 04.03.14                                                             |
| **Task Name** | Write Full Pipeline Tests                                            |
| **Sub-Phase** | 04.03 — Render Pipeline & Progress API                               |
| **Phase**     | Phase 04 — The Vision: Video Rendering Engine                        |
| **Complexity**| High                                                                 |
| **Dependencies** | All previous tasks in SubPhase 04.03 (tests exercise the full pipeline) |
| **Parent**    | [SubPhase_04_03_Overview.md](./SubPhase_04_03_Overview.md)           |

---

## Objective

Write a comprehensive test class for the render pipeline that validates the render trigger endpoint, status endpoint, pre-render validation logic, status transitions, and the end-to-end render flow. The tests use Django's APITestCase with DRF's APIClient, exercise both success and error paths, and verify that the background task correctly updates project status. This is the final task in SubPhase 04.03 and serves as the integration verification gate.

---

## Instructions

### Step 1 — Create the Test Class

In backend/api/tests.py, add a new test class named RenderPipelineTests that extends APITestCase. This class will contain approximately 15 test methods covering all render pipeline behaviors.

### Step 2 — Implement setUp

In the setUp method, create the test fixtures needed by all test methods:

- Create a Project instance with status DRAFT.
- Create 3 Segment instances associated with the project, each with image_file and audio_file fields populated.
- Create actual temporary files on disk for each segment's image and audio references, so filesystem existence checks pass.
- Create a GlobalSettings instance with default rendering parameters.
- Store the project ID and construct the render and status endpoint URLs for reuse across test methods.

### Step 3 — Implement tearDown

In the tearDown method, clean up any temporary files and directories created during setUp. This prevents test pollution and disk clutter across test runs.

### Step 4 — Configure Test Settings

Use the override_settings decorator on the test class to set MEDIA_ROOT to a temporary directory created with tempfile.mkdtemp(). This isolates test file operations from the real media directory.

### Step 5 — Write Render Trigger Tests

Implement the following test methods for the render endpoint:

- test_render_trigger_success: POST to /api/projects/{id}/render/ with a valid project. Assert 202 response, response contains task_id and "PROCESSING" status, and project status in the database is PROCESSING.
- test_render_trigger_missing_images: Remove image_file from one segment, POST to the endpoint. Assert 400 response with missing_images in the error details.
- test_render_trigger_missing_audio: Remove audio_file from one segment, POST to the endpoint. Assert 400 response with missing_audio in the error details.
- test_render_trigger_no_segments: Delete all segments from the project, POST to the endpoint. Assert 400 response indicating no segments.
- test_render_trigger_already_processing: Set project status to PROCESSING, POST to the endpoint. Assert 409 Conflict response.
- test_render_trigger_re_render: Set project status to COMPLETED, POST to the endpoint. Assert 202 response (re-render allowed).

### Step 6 — Write Status Endpoint Tests

Implement the following test methods for the status endpoint:

- test_status_draft_project: GET /api/projects/{id}/status/ for a DRAFT project. Assert 200 response with status "DRAFT", null progress, and null output_url.
- test_status_completed_project: Set project status to COMPLETED and output_path to a valid path. Assert 200 response with status "COMPLETED", 100% progress, and a valid output_url.

### Step 7 — Write Validation Tests

Implement test methods for the pre-render validation function:

- test_validation_valid_project: Call validate_project_for_render with a fully prepared project. Assert the function returns None.
- test_validation_invalid_project: Remove files from segments and call the validation function. Assert it returns an error dict with missing_images and missing_audio lists.

### Step 8 — Write End-to-End Test

Implement a test_end_to_end_render method that exercises the complete flow:

1. POST to the render endpoint to trigger rendering.
2. Assert 202 response.
3. Poll the status endpoint in a loop (with a maximum iteration count to prevent infinite loops) until the status changes from PROCESSING to either COMPLETED or FAILED.
4. Assert the final status is COMPLETED.
5. Assert the output_url is set and points to a valid path.
6. Refresh the project from the database and assert status is COMPLETED and output_path is set.

This test may need to mock the video renderer to avoid actually performing FFmpeg operations during tests.

### Step 9 — Write Failure Handling Test

Implement a test_render_failure_handling method that mocks the video renderer to raise an exception. Trigger the render and poll until the status changes. Assert the project status is FAILED and the response reflects the error state.

---

## Expected Output

The test class RenderPipelineTests in backend/api/tests.py contains approximately 15 test methods covering render trigger success/failure, status endpoint responses, validation logic, end-to-end rendering, and failure handling. All tests are isolated with temporary files and directories.

---

## Validation

- [ ] RenderPipelineTests class exists in tests.py extending APITestCase.
- [ ] setUp creates a Project, 3 Segments with files, and GlobalSettings.
- [ ] tearDown cleans up temporary files.
- [ ] MEDIA_ROOT is overridden to a temp directory.
- [ ] Render trigger tests cover success, missing images, missing audio, no segments, already processing, and re-render.
- [ ] Status endpoint tests cover DRAFT and COMPLETED states.
- [ ] Validation function tests cover valid and invalid projects.
- [ ] End-to-end test exercises the full render → poll → complete flow.
- [ ] Failure handling test verifies the FAILED status path.
- [ ] Tests are independent and can run in any order.

---

## Notes

- The end-to-end test and failure test may need to mock render_project from core_engine.video_renderer to avoid FFmpeg dependencies in the test environment. Use Python's unittest.mock.patch for this.
- Since the TaskManager uses a ThreadPoolExecutor, the end-to-end test involves actual threading. The polling loop should include a small sleep (e.g., 0.5 seconds) between iterations and a maximum iteration count (e.g., 30) to prevent the test from hanging indefinitely.
- The override_settings decorator for MEDIA_ROOT ensures test files do not pollute the development media directory. The temp directory should be cleaned up in tearDown.
- These tests serve as the integration verification gate for the entire render pipeline. If all 15 tests pass, the render feature is considered functionally complete for Phase 04.

---

> **Parent:** [SubPhase_04_03_Overview.md](./SubPhase_04_03_Overview.md) (Layer 2)
> **Phase:** [Phase_04_Overview.md](../Phase_04_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
