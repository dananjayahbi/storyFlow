# Task 05.03.16 — Write End-to-End Tests

## Layer 3 Task Document

---

| **Field**              | **Value**                                                                                      |
| ---------------------- | ---------------------------------------------------------------------------------------------- |
| **Task ID**            | 05.03.16                                                                                       |
| **Task Name**          | Write End-to-End Tests                                                                         |
| **Sub-Phase**          | 05.03 — Final UI Polish & Testing                                                              |
| **Phase**              | Phase 05 — The Polish                                                                          |
| **Layer**              | Layer 3 (Task Document)                                                                        |
| **Status**             | Not Started                                                                                    |
| **Estimated Complexity** | High                                                                                         |
| **Parent Document**    | [SubPhase_05_03_Overview.md](./SubPhase_05_03_Overview.md) (Layer 2)                           |
| **Dependencies**       | All preceding SubPhase 05.03 tasks (the E2E tests exercise the fully assembled system)         |
| **Output Files**       | `backend/tests/test_e2e.py` (NEW)                                                              |

---

## Objective

Write a comprehensive suite of end-to-end integration tests that exercise the complete StoryFlow workflow from project creation through video rendering, validating that all system components work together correctly as an integrated whole — not just individually in isolation.

---

## Instructions

### Step 1 — Set Up the E2E Test Class

Create `backend/tests/test_e2e.py` with an `EndToEndWorkflowTests` class that extends DRF's `APITestCase`. The setUp method should ensure a clean database state (no projects, no segments, fresh GlobalSettings singleton). Define helper methods for common operations that will be reused across multiple test methods: creating a project via the API, creating a segment via the API, and polling a progress endpoint until completion or timeout.

### Step 2 — Write the Complete Happy Path Test

Write the central E2E test that exercises the full "golden path" workflow end to end:

1. **Create a project** — POST to the projects endpoint with a title and description. Assert 201 Created and capture the project ID.
2. **Create segments** — POST to the segments endpoint with narrative text and image path for two segments under the created project. Assert 201 Created for each and capture segment IDs.
3. **Generate audio** — POST to the audio generation endpoint for each segment. Assert that the response indicates audio generation has started. Poll the segment status until audio generation completes (or assert the synchronous response if audio generation is synchronous). Verify that each segment now has an `audio_file` path populated.
4. **Trigger render** — POST to the render endpoint for the project. Assert that the response indicates rendering has started. Poll the render progress endpoint until the render completes. Verify that the progress reaches 100 percent.
5. **Verify output** — After render completion, verify that the project now has an `output_file` path populated. Optionally verify that the output file path points to a location that would exist on disk (the actual file creation depends on FFmpeg being available, which may not be the case in CI; the test can verify the database state without checking the physical file).

This single test validates the complete data flow through the system.

### Step 3 — Write Settings Persistence Tests

Write E2E tests that verify settings integration with the workflow:

- **Test settings affect rendering** — Modify the global settings (change render resolution, change subtitle font size), then trigger a render. Verify that the render pipeline reads the updated settings rather than using stale defaults. This can be validated by checking that the render task receives the correct parameters.
- **Test settings persist across restarts** — Modify settings via PATCH, then simulate a "fresh" API session by clearing any in-memory caches and re-fetching settings via GET. Verify that the persisted values match what was saved.

### Step 4 — Write Error Path Tests

Write E2E tests that exercise error handling across the system:

- **Test render with no segments** — Create a project with zero segments and attempt to trigger a render. Assert that the API returns an appropriate error (e.g., 400 Bad Request with a message indicating that at least one segment is required).
- **Test render with missing audio** — Create a project with segments but skip the audio generation step. Attempt to trigger a render. Assert that the API returns an error indicating that all segments must have generated audio before rendering.
- **Test invalid segment data** — Attempt to create a segment with missing required fields (no narrative text, no image path). Assert 400 Bad Request with descriptive validation errors.
- **Test project deletion cascading** — Create a project with segments, then delete the project. Verify that the segments are also deleted (cascade delete behavior). Attempt to access the deleted segments by ID and assert 404 Not Found.

### Step 5 — Write Concurrent Render Blocking Test

Write a test that validates the system's behavior when a second render is requested while one is already in progress:

- Create a project with segments and generated audio.
- Trigger a render.
- While the first render is still in progress (or immediately after triggering it), attempt to trigger a second render for the same project.
- Assert that the second render request is rejected with an appropriate error (e.g., 409 Conflict or 400 Bad Request with a message indicating that a render is already in progress).
- This test validates the render locking mechanism that prevents concurrent renders from corrupting output files.

---

## Expected Output

A `test_e2e.py` file containing an `EndToEndWorkflowTests` class with approximately 7–10 test methods covering: the complete happy path workflow (1 test), settings persistence and integration (2 tests), error paths (4 tests), and concurrent render blocking (1 test). All tests should be runnable via `python manage.py test`.

---

## Validation

- [ ] Happy path test creates a project, adds segments, generates audio, renders, and verifies output.
- [ ] Each step in the happy path asserts correct HTTP status codes and response data.
- [ ] Settings persistence test confirms PATCH values survive a fresh GET.
- [ ] Settings integration test verifies settings are used during rendering.
- [ ] Render with no segments returns an appropriate error.
- [ ] Render with missing audio returns an appropriate error.
- [ ] Invalid segment data returns 400 with descriptive errors.
- [ ] Project deletion cascades to segments.
- [ ] Concurrent render blocking test rejects the second render attempt.
- [ ] All tests pass via `python manage.py test`.
- [ ] Tests clean up after themselves (no leftover data between tests).

---

## Notes

- E2E tests are the slowest tests in the suite because they exercise multiple API calls per test method. Keep the test count reasonable (under 10) and focus on high-value integration scenarios rather than duplicating unit-level checks.
- The happy path test is the single most important test in the entire StoryFlow test suite. If this test passes, it confirms that the core workflow — the reason the application exists — functions correctly.
- Some E2E tests may require mocking external dependencies (Kokoro TTS model, FFmpeg binary) if they are not available in the test environment. Use Django's `unittest.mock.patch` to mock the TTS generation and video rendering functions so that the tests validate the API and database flow without requiring the actual ML model or media processing tools.
- The concurrent render blocking test may need to use threading or mock timing to simulate an in-progress render. In a synchronous test, the render may complete instantly, making it difficult to test the overlap scenario. Consider setting a flag or using a mock that keeps the render in a "processing" state long enough for the second request to arrive.

---

> **Parent:** [SubPhase_05_03_Overview.md](./SubPhase_05_03_Overview.md) (Layer 2)
> **Phase:** [Phase_05_Overview.md](../Phase_05_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
