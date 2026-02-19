# Task 04.03.11 — Update Zustand Render State

## Metadata

| Field         | Value                                                                |
| ------------- | -------------------------------------------------------------------- |
| **Task ID**   | 04.03.11                                                             |
| **Task Name** | Update Zustand Render State                                          |
| **Sub-Phase** | 04.03 — Render Pipeline & Progress API                               |
| **Phase**     | Phase 04 — The Vision: Video Rendering Engine                        |
| **Complexity**| High                                                                 |
| **Dependencies** | Task 04.03.13 (API client functions for render and status calls)  |
| **Parent**    | [SubPhase_04_03_Overview.md](./SubPhase_04_03_Overview.md)           |

---

## Objective

Extend the existing Zustand project store with render-specific state properties and actions. This includes state for tracking the render task ID, current render status, segment-level progress, and the output video URL. The actions coordinate the render workflow: triggering the render API, polling for progress, handling completion, initiating downloads, and resetting render state. The store serves as the single source of truth for all render-related UI state.

---

## Instructions

### Step 1 — Add Render State Properties

In frontend/stores.ts, add four new properties to the project store's state:

- renderTaskId: a nullable string holding the TaskManager task identifier returned by the render endpoint. Defaults to null.
- renderStatus: a string representing the current render state. Possible values are "idle", "validating", "rendering", "completed", and "failed". Defaults to "idle". Note these are frontend-specific labels that map to the backend Project.status values.
- renderProgress: a nullable object with current_segment (number), total_segments (number), percentage (number), and current_phase (string). Defaults to null.
- outputUrl: a nullable string holding the relative URL to the rendered video file. Defaults to null.

### Step 2 — Implement startRender Action

Add a startRender action that orchestrates the render trigger flow:

1. Set renderStatus to "validating".
2. Call the renderProject API function (from Task 04.03.13) with the current project ID.
3. On success (202 response): store the returned task_id in renderTaskId, set renderStatus to "rendering", and immediately call pollRenderStatus to begin tracking.
4. On validation error (400 response): set renderStatus back to "idle" and surface the error details (e.g., via a toast notification or by storing the error message in state).
5. On conflict (409 response): set renderStatus to "rendering" (already in progress) and begin polling.
6. On other errors: set renderStatus to "failed" and log the error.

### Step 3 — Implement pollRenderStatus Action

Add a pollRenderStatus action that sets up the polling loop:

1. Call the getRenderStatus API function with the current project ID.
2. Update renderProgress with the response's progress data.
3. If the response status is "COMPLETED": set renderStatus to "completed", set outputUrl to the response's output_url, and stop polling.
4. If the response status is "FAILED": set renderStatus to "failed" and stop polling.
5. If the response status is "PROCESSING": schedule another poll after 3 seconds using setTimeout.
6. Store the timeout ID so it can be cleared on cleanup.

### Step 4 — Implement downloadVideo Action

Add a downloadVideo action that handles the cross-origin file download:

1. Use fetch to retrieve the video file from the full backend URL plus outputUrl as a blob.
2. Create an object URL from the blob response.
3. Programmatically create an anchor element, set its href to the object URL, set the download attribute to "final.mp4", append it to the document body, click it, remove it, and revoke the object URL.

### Step 5 — Implement resetRenderState Action

Add a resetRenderState action that clears all render-related state back to defaults: renderTaskId to null, renderStatus to "idle", renderProgress to null, and outputUrl to null. Also clear any active polling timeout.

### Step 6 — Update fetchProject Action

Modify the existing fetchProject action (which runs when navigating to a project detail page) to detect the project's current status from the API response. If the status is PROCESSING, set renderStatus to "rendering" and start polling. If the status is COMPLETED and output_path is set, set renderStatus to "completed" and outputUrl accordingly. This ensures the UI correctly reflects render state when the user navigates back to a project that is mid-render or has a completed video.

---

## Expected Output

The Zustand store in frontend/stores.ts is extended with renderTaskId, renderStatus, renderProgress, outputUrl properties and startRender, pollRenderStatus, downloadVideo, resetRenderState actions. The existing fetchProject action is updated to detect render state on navigation.

---

## Validation

- [ ] Store contains renderTaskId, renderStatus, renderProgress, and outputUrl properties.
- [ ] startRender calls the render API and transitions through validating → rendering states.
- [ ] startRender handles 400, 409, and error responses appropriately.
- [ ] pollRenderStatus updates renderProgress every 3 seconds during rendering.
- [ ] Polling stops on COMPLETED or FAILED status.
- [ ] downloadVideo triggers a file download using the fetch-blob approach.
- [ ] resetRenderState clears all render properties and stops active polling.
- [ ] fetchProject detects PROCESSING status and starts polling automatically.
- [ ] fetchProject detects COMPLETED status and sets outputUrl.

---

## Notes

- The renderStatus uses frontend-specific values ("idle", "validating", "rendering", "completed", "failed") that are distinct from the backend Project.status values ("DRAFT", "PROCESSING", "COMPLETED", "FAILED"). The mapping between them is handled in fetchProject and pollRenderStatus.
- The polling uses setTimeout chaining rather than setInterval. This prevents overlapping requests if the API call takes longer than 3 seconds — the next poll is only scheduled after the current one completes.
- The downloadVideo action uses the fetch-blob approach because the frontend (port 3000) and backend (port 8000) are different origins, making the native anchor download attribute ineffective for cross-origin resources.
- The resetRenderState action should be called when navigating away from a project detail page to prevent stale render state from appearing when viewing a different project.

---

> **Parent:** [SubPhase_04_03_Overview.md](./SubPhase_04_03_Overview.md) (Layer 2)
> **Phase:** [Phase_04_Overview.md](../Phase_04_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
