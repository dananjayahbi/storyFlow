# Task 04.03.02 — Build Render Status Endpoint

## Metadata

| Field         | Value                                                                |
| ------------- | -------------------------------------------------------------------- |
| **Task ID**   | 04.03.02                                                             |
| **Task Name** | Build Render Status Endpoint                                         |
| **Sub-Phase** | 04.03 — Render Pipeline & Progress API                               |
| **Phase**     | Phase 04 — The Vision: Video Rendering Engine                        |
| **Complexity**| Medium                                                               |
| **Dependencies** | Task 04.03.01 (render endpoint must exist for status to be meaningful) |
| **Parent**    | [SubPhase_04_03_Overview.md](./SubPhase_04_03_Overview.md)           |

---

## Objective

Implement the GET /api/projects/{id}/status/ endpoint as a custom DRF action on ProjectViewSet. This endpoint returns the project's current render status, per-segment progress data during rendering, and the output video URL when rendering is complete. The frontend polls this endpoint every 3 seconds during rendering to display real-time progress updates.

---

## Instructions

### Step 1 — Add the Custom Action

In backend/api/views.py, add a new method to ProjectViewSet decorated with the action decorator using detail=True, methods=['get'], and url_path='status'. The url_path parameter is critical — without it, DRF would generate the URL from the method name, producing /render_status/ instead of /status/.

### Step 2 — Build the Base Response

Retrieve the project with self.get_object() and construct a base response dictionary containing: project_id as a string, status from the project model, progress set to None, and output_url set to None. These defaults are returned for the DRAFT state.

### Step 3 — Handle PROCESSING State

When the project status is PROCESSING, look up the render task progress from the TaskManager. Use the deterministic task ID convention "render_{project_id}" to find the task. If progress data is available, include it in the response as an object with current_segment, total_segments, percentage (computed as current divided by total multiplied by 100, cast to integer), and current_phase (a descriptive string from the video renderer's progress callback).

### Step 4 — Handle COMPLETED State

When the project status is COMPLETED and output_path is set, construct the output_url as a relative media URL path (for example, /media/projects/{id}/output/final.mp4). Set the progress to 100 percent with current_phase as "Export complete" and current_segment equal to total_segments.

### Step 5 — Handle FAILED State

When the project status is FAILED, include the last known progress data if available from TaskManager, and set output_url to None. The frontend uses this state to show a "Retry Render" button.

### Step 6 — Return the Response

Return the constructed response dictionary with HTTP 200 OK status.

---

## Expected Output

GET /api/projects/{id}/status/ returns a JSON response appropriate to the project's current state:
- DRAFT: status with null progress and null output_url.
- PROCESSING: status with real-time progress data.
- COMPLETED: status with 100% progress and a valid output_url.
- FAILED: status with last known progress and null output_url.

---

## Validation

- [ ] GET /api/projects/{id}/status/ returns 200 for all project states.
- [ ] DRAFT projects return null progress and null output_url.
- [ ] PROCESSING projects return current segment progress and percentage.
- [ ] COMPLETED projects return percentage 100 and a valid output_url.
- [ ] FAILED projects return status "FAILED" with null output_url.
- [ ] The url_path='status' parameter produces /api/projects/{id}/status/ URL.
- [ ] Progress percentage is calculated correctly as an integer.

---

## Notes

- The task ID convention "render_{project_id}" allows O(1) lookup of the render task in TaskManager without maintaining a separate mapping or adding a model field.
- The progress data structure matches what the frontend RenderProgress component expects: current_segment, total_segments, percentage, and current_phase.
- The output_url is a relative URL. The frontend Axios client prepends the backend base URL (http://localhost:8000) automatically.
- This endpoint is designed to be polled frequently (every 3 seconds), so it must be lightweight. All data comes from in-memory TaskManager state or a single database read — no expensive queries.

---

> **Parent:** [SubPhase_04_03_Overview.md](./SubPhase_04_03_Overview.md) (Layer 2)
> **Phase:** [Phase_04_Overview.md](../Phase_04_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
