# Task 05.03.05 — Build RenderSettingsForm

## Layer 3 Task Document

---

| **Field**              | **Value**                                                                                      |
| ---------------------- | ---------------------------------------------------------------------------------------------- |
| **Task ID**            | 05.03.05                                                                                       |
| **Task Name**          | Build RenderSettingsForm                                                                       |
| **Sub-Phase**          | 05.03 — Final UI Polish & Testing                                                              |
| **Phase**              | Phase 05 — The Polish                                                                          |
| **Layer**              | Layer 3 (Task Document)                                                                        |
| **Status**             | Not Started                                                                                    |
| **Estimated Complexity** | Low                                                                                          |
| **Parent Document**    | [SubPhase_05_03_Overview.md](./SubPhase_05_03_Overview.md) (Layer 2)                           |
| **Dependencies**       | Task 05.03.12 (Zustand store must support settings updates)                                    |
| **Output Files**       | `frontend/components/RenderSettingsForm.tsx` (NEW)                                             |

---

## Objective

Build a form component with an interactive zoom intensity slider and read-only resolution and framerate displays. The zoom slider persists changes to `GlobalSettings.zoom_intensity`, while resolution and framerate are shown as static informational text.

---

## Instructions

### Step 1 — Create the RenderSettingsForm Component

Create `frontend/components/RenderSettingsForm.tsx` as a client component. The component accepts `zoomIntensity` (current value as a number) and `onChange` (update handler callback) as props.

### Step 2 — Build the Zoom Intensity Slider

Render a Shadcn/UI `Slider` component with a range of 1.0 to 2.0 and a step of 0.1. Display the current value as a label next to or below the slider (e.g., "1.3x"). Debounce slider `onChange` events by 300 milliseconds to avoid sending a PATCH request for every incremental slider movement. After the debounce, call `onChange({ zoom_intensity: value })`.

### Step 3 — Display Resolution (Read-Only)

Render static text showing "1920 × 1080 (1080p)". Style this text in a muted/grayed-out color to indicate it is not editable. Optionally add a small info icon with a tooltip explaining "Resolution is not configurable in v1.0".

### Step 4 — Display Framerate (Read-Only)

Render static text showing "30 fps" with the same muted styling as the resolution display.

### Step 5 — Add Section Header

Add a section header with a camera or film icon and the label "Render Settings" to visually identify this section within the GlobalSettingsPanel.

---

## Expected Output

A `RenderSettingsForm.tsx` component with an interactive debounced zoom slider (1.0–2.0), and static read-only displays for resolution and framerate.

---

## Validation

- [ ] Zoom intensity slider renders with range 1.0–2.0, step 0.1.
- [ ] Current zoom value displays as a label (e.g., "1.3x").
- [ ] Slider changes are debounced (300ms) before calling `onChange`.
- [ ] Resolution displays as "1920 × 1080 (1080p)" in muted/read-only styling.
- [ ] Framerate displays as "30 fps" in muted/read-only styling.
- [ ] Section header with icon is visible.

---

## Notes

- This is the simplest settings sub-component — one interactive slider and two static displays. Its low complexity reflects this.
- The resolution and framerate are intentionally non-editable in v1.0. Displaying them in the settings panel informs the user of the render parameters without implying they can be changed.
- The zoom intensity value directly controls the Ken Burns effect's zoom factor in the rendering pipeline (Phase 04). A value of 1.0 means no zoom, while 2.0 means 2× zoom.

---

> **Parent:** [SubPhase_05_03_Overview.md](./SubPhase_05_03_Overview.md) (Layer 2)
> **Phase:** [Phase_05_Overview.md](../Phase_05_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
