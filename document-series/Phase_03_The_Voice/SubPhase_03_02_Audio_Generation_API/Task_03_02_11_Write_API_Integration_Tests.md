# Task 03.02.11 — Write API Integration Tests

> **Sub-Phase:** 03.02 — Audio Generation API
> **Phase:** Phase 03 — The Voice
> **Complexity:** High
> **Dependencies:** Task 03.02.03 (Generate Audio), Task 03.02.04 (Generate All), Task 03.02.05 (Task Status), Task 03.02.08 (Segment Delete)
> **Parent Document:** [SubPhase_03_02_Overview.md](./SubPhase_03_02_Overview.md)

---

## Objective

Write comprehensive integration tests for all new API endpoints and the TaskManager, covering success paths, error paths, edge cases, background task completion, and audio file cleanup — all without requiring the actual Kokoro model file.

---

## Instructions

### Step 1 — Set up test infrastructure

Use Django's `TestCase` or `TransactionTestCase`. Mock `tts_wrapper.generate_audio` to return a synthetic success dict with `success: True`, a `duration` float, and an `audio_path`. Mock `KokoroModelLoader.is_model_available()` to return `True` by default. Use `@override_settings(MEDIA_ROOT=tempdir)` and `tempfile.mkdtemp()` to isolate file I/O. Create test fixtures: a project, multiple segments with text content, and a GlobalSettings instance.

### Step 2 — Write Generate Audio endpoint tests

Test successful generation: POST returns 202 with `task_id`, `segment_id`, `status`, and `message`. Test empty text content: returns 400. Test locked segment: returns 409. Test missing model (mock `is_model_available` → `False`): returns 503. Test non-existent segment: returns 404. Test that the background task completes: poll the task status endpoint until `COMPLETED`, then verify the segment's `audio_file` and `audio_duration` are populated.

### Step 3 — Write Generate All Audio endpoint tests

Test successful bulk generation: POST returns 202 with counts. Test `skip_locked=true`: locked segments are excluded from `segments_to_process`. Test `force_regenerate=true`: segments with existing audio are re-processed. Test with no segments to process: returns 200. Test non-existent project: returns 404. Test progress tracking: submit a batch, poll until completion, verify final `current` equals `total`.

### Step 4 — Write Task Status endpoint tests

Test successful retrieval: returns 200 with all expected fields. Test unknown task ID: returns 404. Test status transitions: verify a task moves through PENDING → PROCESSING → COMPLETED. Test error reporting: verify that a failed segment appears in the `errors` array.

### Step 5 — Write Segment Delete Audio Cleanup tests

Test that deleting a segment with a `.wav` file on disk also removes the file. Test that deleting a segment without audio works normally without errors.

### Step 6 — Write TaskManager unit tests

Test singleton behavior: two `TaskManager()` calls return the same instance. Test `submit_task`: creates a `PENDING` task. Test status transitions through the full lifecycle. Test `add_error` and `add_completed_segment` accumulation. Test `cancel_task` sets the flag. Test `_cleanup_old_tasks` removes expired tasks (manipulate `completed_at` timestamps).

### Step 7 — Handle async testing

For tests that verify background task completion, either wait with a polling loop (call `time.sleep(0.5)` in a bounded loop checking status), or bypass the executor by patching `submit_task` to run the task function synchronously. Reset the TaskManager singleton in `setUp()`/`tearDown()` to prevent cross-test contamination.

---

## Expected Output

```
backend/
└── api/
    └── tests.py                ← MODIFIED (test classes added)
```

---

## Validation

- [ ] All tests pass with `python manage.py test api`.
- [ ] Tests pass WITHOUT the Kokoro model file present.
- [ ] Generate Audio endpoint tests cover: 202 success, 400, 409, 503, 404.
- [ ] Generate All Audio endpoint tests cover: 202, skip locked, force regenerate, 200 no-op, 404.
- [ ] Task Status tests cover: 200, 404, transitions, error reporting.
- [ ] Segment delete tests verify audio file cleanup.
- [ ] TaskManager tests verify singleton, lifecycle, cancel, cleanup.
- [ ] All file operations use temporary directories.
- [ ] TaskManager singleton is reset between tests.

---

## Notes

- Mocking `tts_wrapper.generate_audio` is essential — these are API integration tests, not TTS engine tests. The TTS engine is tested separately in SubPhase 03.01.
- Background task testing is inherently timing-dependent. Use bounded polling loops with a maximum wait time (e.g., 10 seconds) to prevent tests from hanging forever.
- The TaskManager singleton must be reset between tests to ensure isolation. Access the internal `_instance` attribute and set it to `None`, and also clear the `_tasks` dict.
- Use `unittest.mock.patch` as decorators or context managers to mock `is_model_available`, `generate_audio`, and other dependencies.
- For synchronous testing of background tasks, an alternative to `time.sleep` polling is to patch `TaskManager.submit_task` to call the task function directly (bypassing the executor).

---

> **Parent:** [SubPhase_03_02_Overview.md](./SubPhase_03_02_Overview.md) (Layer 2)
> **Phase:** [Phase_03_Overview.md](../Phase_03_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_03_02_10_Update_TypeScript_Types.md](./Task_03_02_10_Update_TypeScript_Types.md)
> **Next Task:** [Task_03_02_12_Task_Cleanup_Memory_Management.md](./Task_03_02_12_Task_Cleanup_Memory_Management.md)
