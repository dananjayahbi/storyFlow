# Task 03.02.08 — Update Segment Delete for Audio Cleanup

> **Sub-Phase:** 03.02 — Audio Generation API
> **Phase:** Phase 03 — The Voice
> **Complexity:** Low
> **Dependencies:** None (independent of the task system)
> **Parent Document:** [SubPhase_03_02_Overview.md](./SubPhase_03_02_Overview.md)

---

## Objective

Enhance the segment deletion logic in `SegmentViewSet.perform_destroy()` to also delete the associated `.wav` audio file from disk, preventing orphaned files in the media directory.

---

## Instructions

### Step 1 — Locate the existing `perform_destroy` method

Phase 02 already implemented `perform_destroy()` on `SegmentViewSet` for image file cleanup. This task extends that method — do NOT replace it.

### Step 2 — Add audio file cleanup

Before calling `instance.delete()`, check if the segment has an `audio_file` value. If so, construct the absolute filesystem path (either from `settings.MEDIA_ROOT` joined with the `audio_file` field, or using `construct_audio_path(instance.project_id, instance.id)` from `core_engine.tts_wrapper`). Check if the file exists on disk with `os.path.exists()`. If it exists, delete it with `os.remove()`.

### Step 3 — Handle missing audio file gracefully

If the audio file does not exist on disk (segment was never generated, or file was manually deleted), log a debug-level message and continue with the deletion. Do NOT raise an error — the segment should always be deletable regardless of the audio file state.

### Step 4 — Verify project-level delete coverage

Phase 02's project delete already uses `shutil.rmtree()` to remove the entire project media directory (which includes `/audio/`). Verify that this still works correctly — no changes should be needed for project-level deletion, but confirm it.

---

## Expected Output

```
backend/
└── api/
    └── views.py                ← MODIFIED (perform_destroy extended with audio cleanup)
```

---

## Validation

- [ ] Deleting a segment with a generated `.wav` file also removes the file from disk.
- [ ] Deleting a segment without audio works normally (no error).
- [ ] The image cleanup from Phase 02 is preserved (both image and audio are cleaned up).
- [ ] Project-level deletion still removes the entire project media directory.

---

## Notes

- This task is independent of the TaskManager and can be implemented at any point.
- The cleanup must happen BEFORE `instance.delete()` because the segment's field values (needed to construct the path) are lost after deletion.
- Using `construct_audio_path()` is preferred over manual path construction because it centralizes the path convention in one place.
- Edge case: if a TTS background task is currently writing the `.wav` file while the segment is being deleted, the delete may fail with a "file in use" error on Windows. This is unlikely in single-user use but worth noting.

---

> **Parent:** [SubPhase_03_02_Overview.md](./SubPhase_03_02_Overview.md) (Layer 2)
> **Phase:** [Phase_03_Overview.md](../Phase_03_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_03_02_07_Update_URL_Routing.md](./Task_03_02_07_Update_URL_Routing.md)
> **Next Task:** [Task_03_02_09_Update_Frontend_API_Client.md](./Task_03_02_09_Update_Frontend_API_Client.md)
