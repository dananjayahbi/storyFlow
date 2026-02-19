# Task 04.03.08 — Build RenderProgress Component

## Metadata

| Field         | Value                                                                |
| ------------- | -------------------------------------------------------------------- |
| **Task ID**   | 04.03.08                                                             |
| **Task Name** | Build RenderProgress Component                                       |
| **Sub-Phase** | 04.03 — Render Pipeline & Progress API                               |
| **Phase**     | Phase 04 — The Vision: Video Rendering Engine                        |
| **Complexity**| High                                                                 |
| **Dependencies** | Task 04.03.02 (status endpoint), Task 04.03.11 (Zustand render state) |
| **Parent**    | [SubPhase_04_03_Overview.md](./SubPhase_04_03_Overview.md)           |

---

## Objective

Build the RenderProgress component that displays a real-time progress bar and textual status updates during video rendering. The component polls the render status endpoint every 3 seconds, updates the Zustand store with the latest progress data, and renders a Shadcn Progress bar along with segment-level details. It appears only while the project is in the PROCESSING state and automatically disappears when rendering completes or fails.

---

## Instructions

### Step 1 — Create the Component File

Create a new file at frontend/components/RenderProgress.tsx. Mark it as a client component with the "use client" directive since it manages a polling interval and reads from the Zustand store.

### Step 2 — Import Dependencies

Import the Shadcn Progress component, useProjectStore from the Zustand store, useEffect and useRef from React. Also import the getRenderStatus function from the API client (Task 04.03.13).

### Step 3 — Read Render State

Destructure renderStatus, renderProgress, and renderTaskId from the Zustand store. The component should only render content when renderStatus is PROCESSING.

### Step 4 — Set Up the Polling Interval

Use useEffect to set up a setInterval that fires every 3000 milliseconds (3 seconds) when renderStatus is PROCESSING. Inside each interval tick, call the getRenderStatus API function with the current project ID. On each successful response, update the Zustand store with the latest progress data (current_segment, total_segments, percentage, current_phase).

### Step 5 — Implement Cleanup

Return a cleanup function from the useEffect that calls clearInterval. This ensures polling stops when the component unmounts (page navigation) or when renderStatus changes away from PROCESSING. Store the interval ID in a useRef to ensure the cleanup has access to the correct reference.

### Step 6 — Stop Polling on Terminal States

Inside the polling callback, check the response status. If the status is COMPLETED or FAILED, clear the interval immediately and update the Zustand store with the final state. This prevents unnecessary API calls after the render finishes.

### Step 7 — Render the Progress UI

When renderStatus is PROCESSING and renderProgress is available, render:
- The Shadcn Progress component with its value prop set to renderProgress.percentage.
- A text label showing "Segment X of Y (Z%)" using current_segment, total_segments, and percentage.
- A secondary text label showing the current_phase string (e.g., "Applying Ken Burns effect", "Concatenating clips", "Encoding final video").

### Step 8 — Handle Missing Progress Data

During the initial moments of rendering (before the first polling response arrives), renderProgress may be null. Show a loading/initializing state with the text "Starting render..." and a Progress bar with an indeterminate or zero value.

---

## Expected Output

A new file frontend/components/RenderProgress.tsx that displays a real-time progress bar during rendering, polls the status API every 3 seconds, and automatically stops when rendering completes or fails.

---

## Validation

- [ ] RenderProgress.tsx exists as a client component.
- [ ] Displays Shadcn Progress bar during PROCESSING state.
- [ ] Polls /api/projects/{id}/status/ every 3 seconds.
- [ ] Shows "Segment X of Y (Z%)" text during polling.
- [ ] Shows current_phase text from the API response.
- [ ] Stops polling when status changes to COMPLETED or FAILED.
- [ ] Cleans up the interval on component unmount.
- [ ] Shows "Starting render..." state before first poll response.
- [ ] Does not render anything when renderStatus is not PROCESSING.

---

## Notes

- The 3-second polling interval is a deliberate choice balancing responsiveness with server load. Since the status endpoint is lightweight (in-memory TaskManager lookup), this frequency is acceptable.
- The polling pattern reuses the same approach from Phase 03's TTS progress tracking, maintaining consistency across the application.
- The useRef for the interval ID prevents stale closure issues in the useEffect cleanup function — a common React pitfall with setInterval.
- The Progress component from Shadcn/UI accepts a value prop from 0 to 100, which maps directly to the percentage returned by the status API.

---

> **Parent:** [SubPhase_04_03_Overview.md](./SubPhase_04_03_Overview.md) (Layer 2)
> **Phase:** [Phase_04_Overview.md](../Phase_04_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
