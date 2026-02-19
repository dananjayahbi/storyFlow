# Task 04.03.04 — Background Render Task

## Metadata

| Field         | Value                                                                |
| ------------- | -------------------------------------------------------------------- |
| **Task ID**   | 04.03.04                                                             |
| **Task Name** | Background Render Task                                               |
| **Sub-Phase** | 04.03 — Render Pipeline & Progress API                               |
| **Phase**     | Phase 04 — The Vision: Video Rendering Engine                        |
| **Complexity**| High                                                                 |
| **Dependencies** | None (standalone task function, though used by Task 04.03.01)     |
| **Parent**    | [SubPhase_04_03_Overview.md](./SubPhase_04_03_Overview.md)           |

---

## Objective

Implement the background render task function that bridges the TaskManager infrastructure (from Phase 03) with the video renderer (from SubPhases 04.01–04.02). This function runs on the TaskManager's ThreadPoolExecutor, calls render_project with a progress callback that feeds real-time updates into the TaskManager's progress tracking, and handles both success and failure outcomes by updating the Project model's status and output_path fields.

---

## Instructions

### Step 1 — Define the Task Function

Add a function named render_task_function to backend/api/tasks.py. It accepts two parameters: project_id (string, the UUID of the project to render) and task_id (string, the TaskManager-assigned identifier for tracking).

### Step 2 — Import Dependencies Inside the Function

Import render_project from core_engine.video_renderer and the Project model from api.models inside the function body. This deferred import pattern avoids circular import issues since tasks.py may be imported by modules that also import from api.models.

### Step 3 — Define the Progress Callback

Create an inner function named on_progress that accepts three parameters: current (int, the current segment number), total (int, total segment count), and phase (string, a description of the current processing step). This callback calls TaskManager's update_task_progress method with the task_id and progress data. The video renderer calls this function after processing each segment.

### Step 4 — Call render_project

Invoke render_project with the project_id and the on_progress callback. This call blocks until rendering is complete (or an error occurs), which is expected since it runs on a background thread.

### Step 5 — Handle Success

When render_project returns successfully (with a result dictionary containing output_path, duration, and file_size), re-query the Project from the database using the project_id. Update the project's status to COMPLETED and set its output_path to the result's output path. Save with update_fields to avoid overwriting other fields. Mark the task as complete in the TaskManager with the result data.

### Step 6 — Handle Failure

Wrap the render_project call in a try/except block catching Exception. On failure, log the error with the full traceback at ERROR level. Re-query the Project and set its status to FAILED, saving with update_fields. Wrap this database update in its own try/except to prevent cascading failures if the database is also inaccessible. Mark the task as failed in the TaskManager with the error message string.

### Step 7 — Ensure Thread Safety

The function runs on a ThreadPoolExecutor thread, not a Django request thread. Never pass a Project model instance from the request thread — always re-query using the project_id. Django's ORM is thread-safe for independent queries but not for shared model instances across threads.

---

## Expected Output

The function render_task_function exists in backend/api/tasks.py. When submitted to the TaskManager, it runs render_project in the background, updates progress in real time via the callback, and transitions the project to COMPLETED (with output_path) or FAILED (with error logging) upon completion.

---

## Validation

- [ ] render_task_function exists in tasks.py.
- [ ] It calls render_project with the project_id and a progress callback.
- [ ] The progress callback updates TaskManager with current_segment, total, and phase.
- [ ] On success: Project.status is set to COMPLETED and output_path is set.
- [ ] On failure: Project.status is set to FAILED and the error is logged.
- [ ] The task is marked complete or failed in TaskManager.
- [ ] Imports are deferred to avoid circular dependencies.
- [ ] The Project is re-queried from the database (not passed from the request thread).

---

## Notes

- This function reuses the same TaskManager and ThreadPoolExecutor from Phase 03, which has max_workers=1. This means render tasks queue behind any pending TTS tasks and vice versa. For a single-user local application, this sequential processing is acceptable.
- The output_path stored in the project should be a URL-relative path (e.g., /media/projects/{id}/output/final.mp4) consistent with how Django serves media files, not an absolute filesystem path.
- The task ID follows the convention "render_{project_id}", established by the render endpoint (Task 04.03.01), enabling deterministic lookup by the status endpoint without a separate mapping.
- Any partial output files (e.g., an incomplete final.mp4) should ideally be cleaned up on failure. The video renderer itself may handle this, but the task function should be aware of the possibility.

---

> **Parent:** [SubPhase_04_03_Overview.md](./SubPhase_04_03_Overview.md) (Layer 2)
> **Phase:** [Phase_04_Overview.md](../Phase_04_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
