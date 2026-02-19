# Task 05.03.01 — Build GlobalSettingsPanel

## Layer 3 Task Document

---

| **Field**              | **Value**                                                                                      |
| ---------------------- | ---------------------------------------------------------------------------------------------- |
| **Task ID**            | 05.03.01                                                                                       |
| **Task Name**          | Build GlobalSettingsPanel                                                                      |
| **Sub-Phase**          | 05.03 — Final UI Polish & Testing                                                              |
| **Phase**              | Phase 05 — The Polish                                                                          |
| **Layer**              | Layer 3 (Task Document)                                                                        |
| **Status**             | Not Started                                                                                    |
| **Estimated Complexity** | High                                                                                         |
| **Parent Document**    | [SubPhase_05_03_Overview.md](./SubPhase_05_03_Overview.md) (Layer 2)                           |
| **Dependencies**       | Tasks 05.03.02, 05.03.03, 05.03.04, 05.03.05 (all settings sub-components must exist)         |
| **Output Files**       | `frontend/components/GlobalSettingsPanel.tsx` (NEW), `frontend/app/projects/[id]/page.tsx` (MODIFIED) |

---

## Objective

Build the main collapsible settings panel component that appears in the project detail page's left sidebar. This component composes all settings sub-components (VoiceSelector, RenderSettingsForm, SubtitleSettingsForm, SubtitlePreview) into a unified sidebar experience, with auto-save functionality and toast feedback on every setting change.

---

## Instructions

### Step 1 — Create the GlobalSettingsPanel Component

Create `frontend/components/GlobalSettingsPanel.tsx` as a client component (marked with "use client" directive). The component should fetch global settings from the Zustand settings store on mount by calling `fetchSettings()` inside a `useEffect` hook. While settings are loading, render a skeleton placeholder matching the sidebar dimensions.

### Step 2 — Implement Collapsible Header

Add a clickable header at the top of the panel containing a Settings icon (from Lucide React) and the text "Settings". Clicking the header toggles the panel between expanded and collapsed states. Use a local `useState` for the collapsed flag. When collapsed, only the header is visible. When expanded, all three settings sections render below. Display a `ChevronDown` icon when expanded and `ChevronRight` when collapsed.

### Step 3 — Compose the Three Settings Sections

Inside the expanded panel body, render the following sections in order with appropriate spacing:

**Voice Settings section:** Render the `VoiceSelector` component, passing the current `default_voice_id` and the `updateSettings` handler. Below the voice dropdown, render a TTS Speed slider directly within this panel (since it is simple enough to not warrant its own component). The slider should range from 0.5 to 2.0 with a step of 0.1, and display the current value label (e.g., "1.0x"). Debounce slider changes by 300 milliseconds before calling `updateSettings({ tts_speed: value })`.

**Render Settings section:** Render the `RenderSettingsForm` component, passing the current `zoom_intensity` and the `updateSettings` handler.

**Subtitle Settings section:** Render the `SubtitleSettingsForm` component followed by the `SubtitlePreview` component. Pass the current `subtitle_font`, `subtitle_color`, and `updateSettings` handler.

### Step 4 — Wire Up Auto-Save With Toast Feedback

Each settings sub-component calls `updateSettings()` when the user changes a value. This function (from the Zustand store) sends a `PATCH /api/settings/` request to the backend. On success, show a success toast with the message "Settings saved successfully". On failure, show an error toast with the error message from the API response. Use a shared `handleSettingChange` wrapper function that wraps `updateSettings` with try/catch and toast calls.

### Step 5 — Style as a Sidebar

Apply sidebar styling: fixed width of `w-64`, right border (`border-r`), background color matching the app theme (`bg-background`), padding of `p-4`, vertical spacing between sections (`space-y-6`), and `overflow-y-auto` to handle content overflow when the panel has many settings.

### Step 6 — Integrate Into the Project Detail Page

Modify `frontend/app/projects/[id]/page.tsx` to include the `GlobalSettingsPanel` in the page layout. Use a flex layout where the settings panel occupies the left side and the existing timeline editor content occupies the remaining space. The layout should be: `<div className="flex h-screen"><GlobalSettingsPanel /><main className="flex-1 overflow-y-auto">...existing content...</main></div>`.

### Step 7 — Handle Loading and Error States

While `isSettingsLoading` is true, render a skeleton version of the panel showing animated placeholder rectangles where the dropdown, sliders, and color picker would be. If settings fail to load (store has null `globalSettings` after loading completes), display an inline error message with a "Retry" button that calls `fetchSettings()` again.

---

## Expected Output

A fully functional `GlobalSettingsPanel.tsx` component that renders as a collapsible left sidebar on the project detail page, composing all settings sub-components, with auto-save on every change, toast notifications for feedback, and proper loading/error states.

---

## Validation

- [ ] Settings panel appears in the project detail page layout as a left sidebar.
- [ ] Panel collapses and expands when the header is clicked.
- [ ] Settings are fetched from the API on component mount.
- [ ] Loading skeleton displays while settings load.
- [ ] Voice, Render, and Subtitle settings sections are all visible when expanded.
- [ ] TTS Speed slider (0.5–2.0, step 0.1) works and auto-saves with debounce.
- [ ] Success toast fires on successful settings save.
- [ ] Error toast fires on failed settings save.
- [ ] Panel has proper sidebar styling with fixed width and scrollable overflow.

---

## Notes

- This component is a composition container — its primary job is layout and coordination, not business logic. The individual sub-components handle their own input rendering and validation.
- The TTS Speed slider is embedded directly rather than in a separate component because it is a single input with minimal logic.
- The collapsible state should persist across page navigation if possible (consider using localStorage to remember the collapsed/expanded state).

---

> **Parent:** [SubPhase_05_03_Overview.md](./SubPhase_05_03_Overview.md) (Layer 2)
> **Phase:** [Phase_05_Overview.md](../Phase_05_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
