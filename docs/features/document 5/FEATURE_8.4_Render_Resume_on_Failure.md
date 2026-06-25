# Feature 8.4 — Render Resume on Failure

| Field | Value |
|---|---|
| Feature ID | 8.4 |
| Title | Render Resume on Failure |
| Status | 🟡 Planned |
| Priority | Medium–High |
| Complexity | High |
| Estimated Effort | 5–8 days |
| Dependencies | Feature 1.0 (core render pipeline), FFmpeg installed, Celery + Redis for async task management |
| Output Files (NEW) | backend/core_engine/checkpoint_manager.py |
| Files Modified | backend/core_engine/video_renderer.py, backend/api/models.py, backend/api/views.py, backend/api/urls.py, backend/api/tasks.py, frontend/app/projects/[id]/page.tsx, frontend/components/RenderProgressPanel.tsx |

---

## 1. Document Overview

### 1.1 Problem Statement

A 4K video render in StoryFlow can take between 20 and 60 minutes depending on segment count, image resolution, upscaling settings, and machine hardware — for a long-form YouTube video with 40 or more segments, the render is a significant time investment that cannot practically be restarted on demand without real cost to the creator.
If the render fails partway through — due to a power outage, operating system crash, an out-of-memory condition that terminates the Python process, a corrupt image file that causes FFmpeg to fail on a specific segment, or a network-mounted storage timeout — the entire render restarts from segment 1, discarding all intermediate progress and wasting potentially an hour of CPU and GPU time.
This failure mode is not hypothetical: long renders on consumer hardware regularly encounter transient errors such as thermal throttling causing FFmpeg to produce malformed frames, temporary disk I/O contention, or GPU driver errors that cause a single segment encode to fail without affecting subsequent segments — all of which should be recoverable without a full restart.
The absence of checkpointing makes StoryFlow unreliable for professional creators producing high-segment-count content, and directly contradicts the goal of being a viable production tool for long-form creators who need confidence that render failures are survivable without starting from scratch.

### 1.2 Proposed Solution

Implement a checkpoint-based two-phase rendering architecture that splits the render pipeline into a per-segment clip generation phase and a final concatenation phase, saves each completed segment clip to a dedicated checkpoint directory on disk, and resumes rendering from the first incomplete segment on any subsequent start, effectively making every individual segment clip an independently resumable unit of work.

- Modify backend/core_engine/video_renderer.py to separate rendering into Phase 1 (per-segment MP4 clip generation) and Phase 2 (FFmpeg concat demuxer concatenation), where Phase 1 saves each clip as segment_{index}_rendered.mp4 in a project-specific checkpoint subdirectory before Phase 2 stitches them into the final output.
- Create backend/core_engine/checkpoint_manager.py to centralize all checkpoint directory management: creating the checkpoint directory, scanning for existing valid clips, validating each clip (non-zero size and valid MP4 header check), deleting corrupt clips, and computing the resume list of segments still to be rendered.
- Add render_checkpoint_path and render_segments_completed fields to the Project model in backend/api/models.py so checkpoint state is persisted to the database and survives server restarts, Celery worker crashes, and browser refreshes.
- Implement a GET /api/projects/{id}/checkpoint-status/ endpoint in backend/api/views.py that the frontend calls on project page load to determine whether a partial checkpoint exists and how many segments have already been rendered, enabling the "Resume Render" button to appear only when relevant.
- Display a "Resume Render" button in the project detail page alongside the standard "Start Render" button when checkpoint-status reports that a partial render exists and the project's render_status is "failed" or "pending", making the resume action visible and clearly distinct from a full restart.
- After successful final concatenation in Phase 2, delete the checkpoint directory to reclaim disk space and reset render_checkpoint_path to blank in the model, keeping the media folder clean for completed projects.
- Validate every checkpoint clip before including it in the resume list by checking both file size (non-zero) and the first four bytes of the file for the MP4 ftyp box signature, ensuring corrupt or partial files written during a mid-write crash are detected and re-rendered rather than passed to the concat stage.

### 1.3 Scope

**In Scope**

| Item | Description |
|---|---|
| Per-segment clip checkpointing | Saving each rendered segment as an individual MP4 before concatenation, resuming from the first un-rendered segment |
| Database checkpoint state | Persisting checkpoint path and completed segment count in the Project model for durability across restarts |
| Resume Render UI button | Frontend button appearing only when a valid partial checkpoint exists for a failed or pending project |
| Corrupt clip detection | Validating file size and MP4 header before including a clip in the resume set to prevent concat failures |

**Out of Scope**

| Item | Description |
|---|---|
| Cloud checkpoint storage | Checkpoint clips are saved only to local disk; no S3, GCS, or remote storage integration |
| Partial segment recovery | If a single segment render fails mid-frame, that segment is fully re-rendered; sub-segment frame checkpointing is not implemented |
| Celery task-level durability | If the Celery worker process itself is killed, the task is re-queued but resume logic depends on on-disk checkpoint state, not Celery task state |
| User-configurable checkpoint frequency | All segments are checkpointed individually; no option to checkpoint every N segments or disable checkpointing |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| backend/core_engine/video_renderer.py | Main render orchestration: calls FFmpeg per segment and for final concat | Exists; must be refactored to save per-segment clips to checkpoint directory |
| backend/core_engine/checkpoint_manager.py | New helper managing checkpoint directory lifecycle and clip validation | Does not exist; must be created with directory, scan, validate, and cleanup functions |
| backend/api/models.py | Project model with render status, output path, and segment relationships | Exists; two new fields (render_checkpoint_path, render_segments_completed) must be added |
| backend/api/tasks.py | Celery async task that calls the render pipeline and updates project status | Exists; must call the modified renderer and update checkpoint fields after each segment |
| backend/api/views.py | DRF views including render start and project detail endpoints | Exists; checkpoint-status endpoint must be added |
| frontend/components/RenderProgressPanel.tsx | Frontend component displaying render progress | Exists or partially exists; must show per-segment progress and Resume Render button |

---

## 2. Flow Diagram

    POST /api/projects/{id}/render/
              |
              v
    Celery task starts: render_project_task()
              |
              v
    checkpoint_manager.get_resume_list(project)
    Scans checkpoint dir for valid segment clips
              |
              v
    PHASE 1 LOOP — for each segment:
         Already rendered?       Not rendered
              |                       |
              v                       v
         Skip (log "HIT")      Run FFmpeg per-segment
                                Save segment_{i}_rendered.mp4
                                Validate clip (size + header)
                                Update Project.render_segments_completed
                                Update Project via DB save
              |
              v
    All segments complete?
              |
              v
    PHASE 2 — FFmpeg concat demuxer
    Reads concat list of all segment clips
    Produces final output.mp4
              |
         +----+----+
         |         |
      Success    Failure
         |         |
         v         v
    Delete        Set project
    checkpoint    status="failed"
    directory     Leave checkpoint
    Set status    intact for resume
    ="completed"

---

## 3. Step-by-Step Instructions

### Step 1 — Create checkpoint_manager.py and define all checkpoint directory operations

Create the file backend/core_engine/checkpoint_manager.py and define a constant CHECKPOINT_DIR_TEMPLATE as the string "project_{id}_checkpoint" which will be used to derive the subdirectory name for each project's checkpoint folder inside the Django MEDIA_ROOT path.
Write a function called get_checkpoint_dir that accepts a project database object and returns the absolute path to the checkpoint directory by joining Django's MEDIA_ROOT with the formatted CHECKPOINT_DIR_TEMPLATE string — the function should also call os.makedirs with exist_ok=True to ensure the directory is created if it does not already exist.
Write a function called get_resume_list that accepts the project object and a list of all Segment objects for the project, computes the expected checkpoint clip filename for each segment using the segment's sequence_index value, checks each expected file using the validate_clip helper (described next), and returns a list of segment objects where already_rendered is False — that is, only the segments whose clip files are absent or invalid.
Write a validate_clip function that accepts a file path string and returns True only if two conditions are both satisfied: the file exists and has a size greater than zero bytes as determined by os.path.getsize, and the first eight bytes of the file read using a plain open in binary mode contain the string "ftyp" at offset 4 (bytes 4 through 8), which is the standard MP4 file type box signature indicating a structurally valid MP4 container.
Write a cleanup_checkpoint_dir function that accepts a project object, resolves the checkpoint directory path using get_checkpoint_dir, and deletes the entire directory and all its contents using shutil.rmtree — this function should only be called after successful concatenation and should log a confirmation message at INFO level using Django's standard logger before performing the deletion.

### Step 2 — Refactor video_renderer.py into a two-phase checkpointed render pipeline

Open backend/core_engine/video_renderer.py and identify the current render function that loops through segments and calls FFmpeg — refactor this loop into a new function called render_segments_to_clips that accepts the project, the list of segments to render (the resume list from checkpoint_manager), and the checkpoint directory path, so the function signature cleanly separates "which segments to render" from "where to save the clips".
Inside render_segments_to_clips, for each segment in the provided list, construct the per-segment FFmpeg command that produces a short MP4 clip for that segment only — using the segment's image, audio, and timing data — and write the output to checkpoint_dir/segment_{sequence_index}_rendered.mp4; after each successful clip write, call validate_clip on the output file to confirm it is valid before moving to the next segment.
After each segment clip is successfully validated, update the project object in the database: increment the render_segments_completed field by one and set render_checkpoint_path to the checkpoint directory path — use Django's Project.objects.filter(id=...).update(...) for an atomic field-level update rather than a full model save, to avoid race conditions with other fields being updated by the Celery task status tracker.
Write a new function called concatenate_clips that accepts the checkpoint directory path and the final output video file path, generates a temporary FFmpeg concat list file (a plain text file listing each segment clip path prefixed with "file " on its own line), calls FFmpeg with the concat demuxer flag (-f concat -safe 0), and produces the final output MP4 — after FFmpeg exits successfully, delete the temporary concat list file.
Update the top-level render_video function in video_renderer.py to call checkpoint_manager.get_resume_list to determine which segments still need rendering, call render_segments_to_clips with only those segments, then call concatenate_clips once all clips are present, and finally call checkpoint_manager.cleanup_checkpoint_dir on success — wrapping the entire sequence in a try-except block that sets project status to "failed" on any exception while leaving the checkpoint directory intact for a future resume.

### Step 3 — Update the Project model and create the database migration

Open backend/api/models.py and add two new fields to the Project model class: render_checkpoint_path as a CharField with max_length=500, blank=True, and default of an empty string so it is non-required and backward-compatible with existing project rows; and render_segments_completed as a PositiveIntegerField with a default of zero so new projects start with no checkpoint progress.
Run python manage.py makemigrations to generate the migration file for the two new fields, review the generated migration to confirm it adds exactly the two new columns with the correct defaults, and then run python manage.py migrate to apply the migration to the local development database.
Add a computed property or method to the Project model called has_partial_checkpoint that returns True when render_checkpoint_path is non-empty AND render_segments_completed is greater than zero AND the render_status field is one of "failed" or "pending" — this property will be used by the serializer and the checkpoint-status endpoint to communicate the resume-eligible state to the frontend.
Update the ProjectSerializer in backend/api/serializers.py to include render_checkpoint_path, render_segments_completed, and has_partial_checkpoint in the serialized fields list so the frontend can access all three values from the standard project detail API response without requiring a separate endpoint for most use cases.
Verify the model changes in a Django shell session by creating a test Project object, manually setting render_checkpoint_path to a mock directory string and render_segments_completed to 5, calling project.save(), fetching the project back from the database by its primary key, and asserting that both fields return the expected values after the round-trip.

### Step 4 — Add the checkpoint-status endpoint and update the Celery render task

Open backend/api/views.py and add a new function-based view called checkpoint_status_view decorated with @api_view(["GET"]) that retrieves the project by primary key, counts the total number of Segment objects related to the project, computes the estimated remaining seconds by multiplying the remaining segment count by the average per-segment render duration (read from a configurable settings constant with a default of 90 seconds), and returns a JSON response containing total_segments, completed_segments (from the model field), checkpoint_exists (the has_partial_checkpoint boolean), and estimated_remaining_seconds.
Register the new URL in backend/api/urls.py using the path "projects/{id}/checkpoint-status/" pointing to checkpoint_status_view, following the same naming convention and URL parameter style used by the existing project-scoped endpoints.
Open backend/api/tasks.py and find the Celery task function that initiates rendering (likely named render_project or similar), update it to call the refactored video_renderer.render_video function which now internally handles checkpoint detection and resume logic, and ensure the task updates Project.render_status to "rendering" at the start and to "completed" or "failed" at the end regardless of whether the render was a fresh start or a resume.
Add a per-segment progress callback mechanism: either pass a callback lambda to render_segments_to_clips that is called after each segment completes and updates Project.render_segments_completed via Django ORM, or use Celery's update_state mechanism to emit a custom state with metadata containing the completed segment count so the frontend progress panel can read it from the task result.
Test the checkpoint-status endpoint manually by creating a project, manually setting render_segments_completed to 8 and render_checkpoint_path to a non-empty string, calling GET /api/projects/{id}/checkpoint-status/ from the browser or curl, and verifying the response contains the expected values and that checkpoint_exists is True only when the field conditions defined in has_partial_checkpoint are all met.

### Step 5 — Build the Resume Render button in the frontend and validate the full recovery flow

Open frontend/app/projects/[id]/page.tsx and update the render controls section to fetch the checkpoint status from GET /api/projects/{id}/checkpoint-status/ on page load using a useEffect hook, storing the result in state variables for totalSegments, completedSegments, and checkpointExists.
Add a "Resume Render" button to the render controls section that renders only when the checkpointExists value is true, positioned adjacent to the existing "Start Render" button and styled with a distinct secondary color (amber or yellow) to visually differentiate it from a full re-render, with a label that includes the completed segment count such as "Resume (12/40 done)".
Wire the Resume Render button's onClick handler to call the same render start endpoint (POST /api/projects/{id}/render/) as the Start Render button — the resume behavior is handled transparently by the backend checkpoint detection logic, so no separate resume endpoint is needed; the frontend simply communicates the creator's intent by starting the task, and the backend skips already-completed segments automatically.
Update the RenderProgressPanel.tsx component to show both a "X / Y segments rendered" progress counter (driven by polling checkpoint-status or the Celery task state) and a standard progress bar, replacing the previous in-memory-only progress indication with durable database-backed progress that correctly reflects the true position even after a page reload or server restart.
Perform a complete failure-and-resume simulation: start a render with 10 or more segments, let it complete 4–6 segments, manually kill the Celery worker process to simulate a crash, reload the project page, confirm the "Resume Render (N/Y done)" button appears with the correct count, click it, and confirm the render completes successfully by rendering only the remaining segments and producing a correct final output MP4 with all segments present and in order.

---

## 4. Expected Outcome

1. A render failure at any point in the segment-rendering loop is survivable without restarting from segment 1 — on the next render start, the system automatically skips all segments whose clip files already exist and are valid, resuming from the exact segment where the failure occurred.
2. The checkpoint directory and all per-segment clip files persist on disk through Django server restarts, Celery worker crashes, and browser refreshes, making the checkpoint state durable against the entire class of transient infrastructure failures that currently cause full re-renders.
3. The project page shows a "Resume Render (X/Y done)" button with an accurate segment count whenever a valid partial checkpoint exists and the project's render status is failed or pending, giving creators a clear and actionable recovery path with no ambiguity about what will happen when they click it.
4. A corrupt or partially written checkpoint clip (resulting from a crash during the FFmpeg write operation itself) is detected by the MP4 header validation check, automatically excluded from the skip list, and re-rendered rather than passed to the concat stage where it would cause a silent quality defect or a hard concatenation error.
5. The checkpoint directory is automatically deleted after successful final concatenation, leaving the project's media folder containing only the final output MP4 with no stale intermediate files accumulating over time, even after multiple partial renders and resumes.
6. The render_segments_completed database field provides a durable, server-independent record of render progress that the frontend can read on page load to display an accurate progress indicator without relying on in-memory Celery task state that is lost when the worker process restarts.
7. The orphan cleanup behavior in the project delete endpoint ensures that if a project is deleted before its render completes, any remaining checkpoint directory is also removed, preventing disk space leakage from abandoned partial renders that would otherwise accumulate indefinitely.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] checkpoint_manager.validate_clip returns True for a real valid MP4 file on disk, returns False for an empty file (zero bytes), and returns False for a file that contains arbitrary non-MP4 binary data without raising an exception
- [ ] checkpoint_manager.get_resume_list returns only the segments whose expected clip files are absent or invalid, and returns an empty list when all expected clip files are present and valid
- [ ] checkpoint_manager.cleanup_checkpoint_dir removes the checkpoint directory and all its contents from disk and does not raise an error if the directory does not exist (handles idempotent calls gracefully)
- [ ] The Project.has_partial_checkpoint property returns True only when render_checkpoint_path is non-empty AND render_segments_completed is greater than zero AND render_status is "failed" or "pending", and returns False in all other combinations
- [ ] The checkpoint-status view returns a 404 response for a non-existent project ID, returns correct total_segments and completed_segments counts for an existing project, and correctly reflects the checkpoint_exists boolean based on model field state

### 5.2 Integration / Manual Tests

- [ ] Start a render with at least 8 segments on a real project, wait for 3–4 segment clips to be written to the checkpoint directory, manually kill the Celery worker, and verify that the expected segment clip files exist on disk with non-zero sizes
- [ ] After the kill, reload the project page and verify the "Resume Render (3/8 done)" button appears with the correct segment count matching the number of actually completed clip files on disk
- [ ] Click Resume Render and verify in the Django and Celery logs that the renderer logs "HIT" or a skip message for the already-completed segments and only runs FFmpeg for the remaining segments
- [ ] Verify the final output MP4 after a resume render plays correctly from start to finish with all segments present, in the correct order, with no audio gaps or video artifacts at the splice points between pre-rendered and newly rendered clips
- [ ] Manually corrupt a checkpoint clip by overwriting its contents with zeros, trigger a resume render, and verify that the corrupted clip is re-rendered (the validator rejects it) and the final video is correct
- [ ] Delete a project that has an active checkpoint directory on disk and verify that both the project database record and the checkpoint directory on disk are removed by the delete endpoint

### 5.3 Regression Tests

- [ ] Confirm that a fresh render on a project with no existing checkpoint directory completes successfully end-to-end with the refactored two-phase render pipeline, producing an identical output MP4 to what the original single-phase pipeline produced
- [ ] Confirm that the existing render start, render status polling, and Celery task infrastructure continues to work correctly after the model migration and task.py updates, with no 500 errors on the project detail or render endpoints
- [ ] Confirm that the ProjectSerializer correctly includes the two new model fields (render_checkpoint_path and render_segments_completed) in both the project detail and project list API responses, and that the frontend TypeScript project type definition is updated to include these fields without causing type errors

---

## 6. Notes for AI Agent

- The MP4 validation in validate_clip must read only the first 8 bytes of the file (not load the entire file into memory) because checkpoint clips can be hundreds of megabytes in size and memory-loading them during the resume-list scan would be prohibitively slow and memory-intensive when a project has many segments.
- When implementing the per-segment FFmpeg clip generation, ensure that each segment clip is encoded with the same codec, resolution, frame rate, and pixel format as the final output will be, because FFmpeg's concat demuxer requires all input clips to have identical stream parameters — mismatched parameters cause silent video corruption or a hard concat error.
- The render_segments_to_clips function should update Project.render_segments_completed in the database after each successful clip rather than batching the updates, so that a crash immediately after a segment completes still reflects the accurate completed count when the checkpoint-status endpoint is queried during a subsequent resume.
- The cleanup of the checkpoint directory after successful concatenation must happen only after the final output MP4 has been fully written and verified — validate the output file's size and MP4 header before calling cleanup_checkpoint_dir to guard against the edge case where the concat step starts writing but FFmpeg terminates before completing the output file.
- When the project's delete endpoint is updated to clean up orphaned checkpoint directories, use a try-except around the shutil.rmtree call and log a warning rather than raising an exception if the directory does not exist, because the deletion may be triggered on projects that never reached the checkpoint phase and therefore have no checkpoint directory on disk.
