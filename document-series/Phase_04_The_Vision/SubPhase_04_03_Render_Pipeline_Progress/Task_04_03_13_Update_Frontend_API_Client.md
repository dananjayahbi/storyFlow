# Task 04.03.13 — Update Frontend API Client

## Metadata

| Field         | Value                                                                |
| ------------- | -------------------------------------------------------------------- |
| **Task ID**   | 04.03.13                                                             |
| **Task Name** | Update Frontend API Client                                           |
| **Sub-Phase** | 04.03 — Render Pipeline & Progress API                               |
| **Phase**     | Phase 04 — The Vision: Video Rendering Engine                        |
| **Complexity**| Medium                                                               |
| **Dependencies** | Tasks 04.03.01 and 04.03.02 (backend endpoints must be defined)  |
| **Parent**    | [SubPhase_04_03_Overview.md](./SubPhase_04_03_Overview.md)           |

---

## Objective

Extend the frontend API client layer with functions for the render pipeline endpoints, add TypeScript type definitions for render-related request and response objects, and create utility functions for formatting video metadata. These additions provide the typed interface between the frontend components/store and the backend render API.

---

## Instructions

### Step 1 — Add API Functions to api.ts

In frontend/api.ts, add two new functions:

- renderProject: accepts a projectId string and sends a POST request to /api/projects/{projectId}/render/. Returns the response data typed as RenderTriggerResponse. This function is called by the Zustand store's startRender action.

- getRenderStatus: accepts a projectId string and sends a GET request to /api/projects/{projectId}/status/. Returns the response data typed as RenderStatusResponse. This function is called by the Zustand store's pollRenderStatus action and the RenderProgress component.

Both functions use the existing Axios instance configured in api.ts, which handles the base URL and headers.

### Step 2 — Add Type Definitions to types.ts

In frontend/types.ts, add the following TypeScript type definitions:

- ProjectStatus: a union type of the four valid status strings — "DRAFT", "PROCESSING", "COMPLETED", "FAILED".

- RenderProgress: an interface with current_segment (number), total_segments (number), percentage (number), and current_phase (string).

- RenderTriggerResponse: an interface with task_id (string), project_id (string), status (string), total_segments (number), and message (string). This matches the 202 response from the render endpoint.

- RenderStatusResponse: an interface with project_id (string), status (ProjectStatus), progress (RenderProgress or null), and output_url (string or null). This matches the response from the status endpoint.

### Step 3 — Add Utility Functions to utils.ts

In frontend/utils.ts, add two helper functions:

- formatDuration: accepts a number (duration in seconds) and returns a formatted string in "M:SS" or "MM:SS" format. Uses Math.floor for minutes and zero-pads seconds. This is used by the VideoPreview component to display video length.

- formatFileSize: accepts a number (file size in bytes) and returns a human-readable string (e.g., "12.4 MB", "856 KB"). Uses appropriate unit thresholds (bytes, KB, MB, GB). This is used if file size metadata is available from the render result.

---

## Expected Output

Three files are updated: api.ts with renderProject and getRenderStatus functions, types.ts with ProjectStatus, RenderProgress, RenderTriggerResponse, and RenderStatusResponse types, and utils.ts with formatDuration and formatFileSize helpers.

---

## Validation

- [ ] renderProject function exists in api.ts and calls POST /api/projects/{id}/render/.
- [ ] getRenderStatus function exists in api.ts and calls GET /api/projects/{id}/status/.
- [ ] Both functions use the existing Axios instance.
- [ ] ProjectStatus type defines the four valid status strings.
- [ ] RenderProgress interface matches the API response progress structure.
- [ ] RenderTriggerResponse matches the 202 response from the render endpoint.
- [ ] RenderStatusResponse matches the response from the status endpoint.
- [ ] formatDuration correctly formats seconds into M:SS or MM:SS.
- [ ] formatFileSize correctly formats bytes into KB/MB/GB strings.

---

## Notes

- The API functions follow the same pattern as existing functions in api.ts (e.g., generateAllAudio from Phase 03). Consistency in error handling and response unwrapping is important.
- The TypeScript types enforce compile-time correctness when the store and components consume API responses. Any mismatch between the backend response and the frontend type will be caught during development.
- The utility functions are intentionally simple and do not depend on any external libraries. They can be tested independently with pure function unit tests.
- The renderProject function does not pass a request body since no parameters are currently required. The backend infers the project from the URL path. If a "force" parameter is added later, it can be passed as an optional argument.

---

> **Parent:** [SubPhase_04_03_Overview.md](./SubPhase_04_03_Overview.md) (Layer 2)
> **Phase:** [Phase_04_Overview.md](../Phase_04_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
