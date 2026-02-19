# Task 04.03.07 — Build RenderButton Component

## Metadata

| Field         | Value                                                                |
| ------------- | -------------------------------------------------------------------- |
| **Task ID**   | 04.03.07                                                             |
| **Task Name** | Build RenderButton Component                                         |
| **Sub-Phase** | 04.03 — Render Pipeline & Progress API                               |
| **Phase**     | Phase 04 — The Vision: Video Rendering Engine                        |
| **Complexity**| High                                                                 |
| **Dependencies** | Task 04.03.11 (Zustand store render state and actions)            |
| **Parent**    | [SubPhase_04_03_Overview.md](./SubPhase_04_03_Overview.md)           |

---

## Objective

Build the RenderButton component that serves as the primary user interaction point for triggering video rendering. The button adapts its appearance and behavior based on the current render state, presenting five distinct visual states: Ready (blue, clickable), Not Ready (gray, disabled with tooltip), Rendering (disabled with spinner), Complete (green with download action and re-render dropdown), and Failed (red with retry action). This component replaces the disabled "Export Video" placeholder from Phase 03.

---

## Instructions

### Step 1 — Create the Component File

Create a new file at frontend/components/RenderButton.tsx. Mark it as a client component with the "use client" directive since it uses Zustand hooks and event handlers.

### Step 2 — Import Dependencies

Import the Shadcn Button component, DropdownMenu components (DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem), Tooltip components, and the useProjectStore hook from the Zustand store.

### Step 3 — Read Render State From Store

Inside the component, destructure renderStatus, startRender, and downloadVideo from the useProjectStore hook. Also read the segments array to determine whether the project has all required assets.

### Step 4 — Implement Client-Side Readiness Check

Determine whether the project is ready for rendering by checking if all segments have both image_file and audio_file set. This is a quick client-side check that provides immediate visual feedback without an API call. The server-side validation (Task 04.03.03) provides the authoritative check when the button is clicked.

### Step 5 — Implement State-Based Rendering

Render different button variants based on the renderStatus value:

- When idle and ready: show a blue primary button labeled "Export Video" with a film emoji. On click, call startRender.
- When idle but not ready: show a gray disabled button with a Tooltip explaining which assets are missing (e.g., "3 segments need audio files").
- When validating or rendering: show a disabled button with "Rendering..." text and an animated spinner icon using Tailwind's animate-spin class.
- When completed: show a green success-styled button labeled "Download Video" with a download arrow. On click, call downloadVideo. Include a DropdownMenu with a "Re-Render" option that calls startRender.
- When failed: show a red destructive-styled button labeled "Retry Render". On click, call startRender.

### Step 6 — Implement the Re-Render Dropdown

For the completed state, use a split-button pattern: the main button area triggers download, and a small dropdown arrow on the right reveals a "Re-Render" option. Use Shadcn DropdownMenu for this. The re-render option calls startRender, which transitions the state back to rendering.

### Step 7 — Place in the Timeline Footer

This component is placed in the project detail page's timeline footer area, alongside the "Generate All Audio" button from Phase 03. The parent page component imports and renders RenderButton in the appropriate layout position.

---

## Expected Output

A new file frontend/components/RenderButton.tsx containing a client component that adapts its appearance and behavior across five render states. The component reads from and triggers actions on the Zustand store.

---

## Validation

- [ ] RenderButton.tsx exists as a client component.
- [ ] Shows "Export Video" when idle and all segments have assets.
- [ ] Shows disabled state with tooltip when segments are missing assets.
- [ ] Shows "Rendering..." with spinner during rendering.
- [ ] Shows "Download Video" with dropdown when completed.
- [ ] Shows "Retry Render" when failed.
- [ ] Clicking Export Video calls startRender from the store.
- [ ] Clicking Download Video calls downloadVideo from the store.
- [ ] Re-Render dropdown option calls startRender.
- [ ] Disabled during rendering to prevent duplicate triggers.

---

## Notes

- The client-side readiness check is a convenience — it prevents the user from clicking "Export Video" and immediately getting a 400 error. The server-side validation is still the authoritative check.
- The download action should work across the cross-origin boundary between the frontend (port 3000) and backend (port 8000). If the native download attribute does not work cross-origin, the downloadVideo store action should use the fetch-blob-createObjectURL pattern described in the overview notes.
- The spinner animation uses Tailwind's animate-spin utility on a circular SVG icon, consistent with existing loading patterns in the application.

---

> **Parent:** [SubPhase_04_03_Overview.md](./SubPhase_04_03_Overview.md) (Layer 2)
> **Phase:** [Phase_04_Overview.md](../Phase_04_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
