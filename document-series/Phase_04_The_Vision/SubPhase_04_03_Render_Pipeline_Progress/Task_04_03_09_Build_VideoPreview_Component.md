# Task 04.03.09 — Build VideoPreview Component

## Metadata

| Field         | Value                                                                |
| ------------- | -------------------------------------------------------------------- |
| **Task ID**   | 04.03.09                                                             |
| **Task Name** | Build VideoPreview Component                                         |
| **Sub-Phase** | 04.03 — Render Pipeline & Progress API                               |
| **Phase**     | Phase 04 — The Vision: Video Rendering Engine                        |
| **Complexity**| Medium                                                               |
| **Dependencies** | Task 04.03.11 (Zustand store provides outputUrl)                  |
| **Parent**    | [SubPhase_04_03_Overview.md](./SubPhase_04_03_Overview.md)           |

---

## Objective

Build the VideoPreview component that displays the rendered video using the native HTML5 video element. The component appears when the project's render status is COMPLETED and the output URL is available. It provides standard playback controls, displays video metadata (duration and file size), and offers a download button for saving the final video to the user's local machine.

---

## Instructions

### Step 1 — Create the Component File

Create a new file at frontend/components/VideoPreview.tsx. Mark it as a client component since it uses refs, event handlers, and state management for video metadata.

### Step 2 — Accept Props and Read Store State

The component reads outputUrl from the Zustand store or receives it as a prop. It should only render when outputUrl is a non-empty string. Destructure downloadVideo from the store for the download button action.

### Step 3 — Render the HTML5 Video Element

Render a standard HTML5 video element with the controls attribute, which provides native browser playback controls (play/pause, volume, seek, fullscreen). Set the src attribute to the full backend URL concatenated with outputUrl. Set the type attribute to "video/mp4" to help the browser select the correct decoder.

### Step 4 — Implement Cache Busting

Append a timestamp query parameter to the video src URL to prevent browser caching issues when the user re-renders a project. Construct the URL as the base output URL followed by "?t=" and the current timestamp (Date.now()). This ensures the browser fetches the fresh video file after a re-render instead of serving a stale cached version.

### Step 5 — Extract Video Metadata

Attach a ref to the video element and listen for the "loadedmetadata" event. When the event fires, read the video's duration from the ref's current duration property. Store the duration in component-level state and display it formatted as "MM:SS" using a utility function.

### Step 6 — Implement the Download Button

Below the video element, render a download button. Due to cross-origin restrictions between the frontend (port 3000) and backend (port 8000), the native anchor tag with the download attribute may not trigger a file download correctly. Instead, implement the fetch-and-blob approach: when the user clicks download, use fetch to retrieve the video file as a blob, create an object URL from the blob, programmatically create an anchor element with the download attribute set to "final.mp4", click it, and then revoke the object URL to free memory.

### Step 7 — Handle Loading and Error States

While the video is loading, show a loading placeholder. If the video fails to load (e.g., the file was deleted), handle the "error" event and display an error message suggesting the user re-render the project.

---

## Expected Output

A new file frontend/components/VideoPreview.tsx that renders the completed video with playback controls, metadata display, and a download button that works across the cross-origin boundary.

---

## Validation

- [ ] VideoPreview.tsx exists as a client component.
- [ ] Renders an HTML5 video element with controls.
- [ ] Sets the correct src with the backend base URL and output path.
- [ ] Appends a cache-busting timestamp to the video src.
- [ ] Displays video duration in MM:SS format from the loadedmetadata event.
- [ ] Download button triggers a file download using the fetch-blob approach.
- [ ] Only renders when outputUrl is available.
- [ ] Handles video loading and error states gracefully.

---

## Notes

- The native HTML5 video element is used instead of a third-party video player to minimize dependencies and keep the bundle size small. Browser-native controls are sufficient for previewing rendered content.
- The cache-busting parameter is critical for the re-render workflow. Without it, the browser may serve the previously cached video after the user re-renders, leading to confusion.
- The fetch-blob download workaround is necessary because the frontend and backend run on different ports (3000 and 8000), making them different origins. The HTML download attribute does not work for cross-origin resources due to browser security policies.
- The video format is always MP4 (libx264/aac) as specified by the render pipeline, so no format detection is needed.

---

> **Parent:** [SubPhase_04_03_Overview.md](./SubPhase_04_03_Overview.md) (Layer 2)
> **Phase:** [Phase_04_Overview.md](../Phase_04_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
