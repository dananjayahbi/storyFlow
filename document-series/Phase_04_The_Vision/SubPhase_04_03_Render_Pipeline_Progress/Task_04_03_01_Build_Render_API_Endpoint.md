# Task 04.03.01 — Build Render API Endpoint

## Metadata

| Field         | Value                                                                |
| ------------- | -------------------------------------------------------------------- |
| **Task ID**   | 04.03.01                                                             |
| **Task Name** | Build Render API Endpoint                                            |
| **Sub-Phase** | 04.03 — Render Pipeline & Progress API                               |
| **Phase**     | Phase 04 — The Vision: Video Rendering Engine                        |
| **Complexity**| High                                                                 |
| **Dependencies** | Task 04.03.03 (validation), Task 04.03.04 (background task), Task 04.03.05 (status transitions) |
| **Parent**    | [SubPhase_04_03_Overview.md](./SubPhase_04_03_Overview.md)           |

---

## Objective

Implement the POST /api/projects/{id}/render/ endpoint as a custom DRF action on the ProjectViewSet. This endpoint is the entry point for the entire render pipeline — it validates the project is ready for rendering, checks that FFmpeg is available, sets the project status to PROCESSING, spawns a background render task via the TaskManager, and returns a 202 Accepted response with the task ID. The endpoint handles multiple error conditions including missing assets, already-rendering projects, and missing system dependencies.

---

## Instructions

### Step 1 — Add the Custom Action to ProjectViewSet

In backend/api/views.py, add a new method to ProjectViewSet decorated with DRF's action decorator. The decorator should specify detail=True (requires a project ID in the URL) and methods=['post'] (only accepts POST requests). The method name should be "render".

### Step 2 — Retrieve the Project

Inside the action, call self.get_object() to retrieve the project instance. DRF automatically handles the 404 case if the project does not exist.

### Step 3 — Run Pre-Render Validation

Import and call validate_project_for_render (from Task 04.03.03) with the project instance. If the function returns a non-None error dict, return a 400 Bad Request response containing the error details, including lists of segment IDs with missing images or audio and a human-readable message.

### Step 4 — Check Project Status

Verify the project's current status allows rendering to begin. If the status is PROCESSING, return a 409 Conflict response indicating the project is already being rendered. If the status is DRAFT, COMPLETED, or FAILED, rendering is allowed to proceed. For COMPLETED projects, this enables re-rendering; for FAILED projects, this enables retry.

### Step 5 — Check FFmpeg Availability

Call render_utils.check_ffmpeg() to verify that FFmpeg is installed and accessible on the system PATH. If FFmpeg is not found, return a 500 Internal Server Error response with a message explaining that FFmpeg is required for video rendering and must be installed.

### Step 6 — Set Status to PROCESSING

Update the project's status field to PROCESSING and save using update_fields to avoid overwriting other fields. This marks the beginning of the render pipeline.

### Step 7 — Spawn Background Task

Get the TaskManager singleton instance and call submit_task with the render_task_function (from Task 04.03.04) and the project ID as a string argument. Use the task ID convention "render_{project_id}" for deterministic lookup by the status endpoint. Store the returned task ID for the response.

### Step 8 — Return 202 Accepted Response

Construct and return a response with HTTP 202 status containing: the task_id, the project_id as a string, the status "PROCESSING", the total_segments count (queried from the database), and a human-readable message "Video rendering started".

---

## Expected Output

The endpoint POST /api/projects/{id}/render/ is functional and returns:
- 202 Accepted with task details when the project is ready and rendering begins.
- 400 Bad Request when segments are missing images or audio files.
- 409 Conflict when the project is already in PROCESSING status.
- 500 Internal Server Error when FFmpeg is not available.

---

## Validation

- [ ] POST /api/projects/{id}/render/ returns 202 for a valid, ready project.
- [ ] Returns 400 with detailed error info when segments lack assets.
- [ ] Returns 409 when the project is already PROCESSING.
- [ ] Returns 500 when FFmpeg is missing.
- [ ] Allows re-render of COMPLETED projects (returns 202).
- [ ] Allows retry of FAILED projects (returns 202).
- [ ] Sets Project.status to PROCESSING on successful trigger.
- [ ] Spawns a background task via TaskManager.
- [ ] Response includes task_id, project_id, status, total_segments, and message.

---

## Notes

- The action decorator with detail=True automatically generates the URL pattern /api/projects/{id}/render/ when using DRF's DefaultRouter.
- The task ID uses the convention "render_{project_id}" so the status endpoint can look up the task without a separate mapping table or a new model field (models are frozen).
- The endpoint does not wait for rendering to complete — it returns immediately with 202 Accepted. The client polls the status endpoint (Task 04.03.02) for progress updates.
- The "force" parameter for re-rendering is not strictly necessary since the endpoint already allows rendering from COMPLETED status. However, including it in the request body as an optional parameter provides explicit intent documentation.

---

> **Parent:** [SubPhase_04_03_Overview.md](./SubPhase_04_03_Overview.md) (Layer 2)
> **Phase:** [Phase_04_Overview.md](../Phase_04_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
