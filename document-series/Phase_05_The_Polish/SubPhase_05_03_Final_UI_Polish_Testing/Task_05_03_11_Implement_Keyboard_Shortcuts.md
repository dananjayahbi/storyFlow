# Task 05.03.11 — Implement Keyboard Shortcuts

## Layer 3 Task Document

---

| **Field**              | **Value**                                                                                      |
| ---------------------- | ---------------------------------------------------------------------------------------------- |
| **Task ID**            | 05.03.11                                                                                       |
| **Task Name**          | Implement Keyboard Shortcuts                                                                   |
| **Sub-Phase**          | 05.03 — Final UI Polish & Testing                                                              |
| **Phase**              | Phase 05 — The Polish                                                                          |
| **Layer**              | Layer 3 (Task Document)                                                                        |
| **Status**             | Not Started                                                                                    |
| **Estimated Complexity** | Medium                                                                                       |
| **Parent Document**    | [SubPhase_05_03_Overview.md](./SubPhase_05_03_Overview.md) (Layer 2)                           |
| **Dependencies**       | Task 05.03.01 (GlobalSettingsPanel for Ctrl+S target), Task 05.03.13 (Constants file for shortcut definitions) |
| **Output Files**       | `frontend/hooks/useKeyboardShortcuts.ts` (NEW), `frontend/components/KeyboardShortcutsHelp.tsx` (NEW) |

---

## Objective

Implement a global keyboard shortcuts system that lets power users trigger common actions without reaching for the mouse, improving workflow speed for frequent operations like generating audio, exporting video, saving settings, and closing modals.

---

## Instructions

### Step 1 — Create the useKeyboardShortcuts Hook

Create a custom React hook at `frontend/hooks/useKeyboardShortcuts.ts` that registers global keyboard event listeners using `useEffect`. The hook should accept a map of shortcut definitions (key combination → callback function) and register a single `keydown` event listener on the `document` object. Inside the listener, check for modifier keys (Ctrl, Shift, Alt) and the primary key code, then invoke the matching callback if found.

### Step 2 — Define the Core Shortcuts

Implement the following keyboard shortcuts:

- **Ctrl+Enter** — Generate Audio: Triggers TTS generation for the currently focused or selected segment. Only active when on the project detail page with a segment selected. If no segment is selected, show a toast notification indicating that a segment must be selected first.
- **Ctrl+Shift+Enter** — Export/Render Video: Triggers the full video render pipeline. Only active when on the project detail page and the project has at least one segment with generated audio. If preconditions are not met, show a toast notification explaining what is needed.
- **Escape** — Close Modal/Panel: Closes any currently open modal dialog or side panel (such as the GlobalSettings panel). If nothing is open, this shortcut does nothing.
- **Ctrl+S** — Save Settings: Saves the current global settings if the GlobalSettings panel is open. If the panel is not open, this shortcut does nothing. Must also call `event.preventDefault()` to prevent the browser's native "Save Page" dialog from appearing.
- **?** (Question Mark) — Help Dialog: Opens a help overlay that lists all available keyboard shortcuts with their descriptions. This shortcut is only active when the user is not typing in an input field.

### Step 3 — Skip Shortcuts When Typing in Inputs

Add a guard at the top of the keyboard event listener that checks whether the active element (`document.activeElement`) is an input, textarea, select, or contenteditable element. If the user is typing in any form field, all keyboard shortcuts should be suppressed (except Escape, which should always work to allow closing modals). This prevents shortcuts from firing accidentally while the user is writing narrative text or editing form fields.

### Step 4 — Build the Keyboard Shortcuts Help Dialog

Create a `KeyboardShortcutsHelp.tsx` component that renders as a modal overlay listing all available shortcuts in a two-column table format: the left column shows the key combination (styled as keyboard key badges), and the right column shows the action description. This dialog is opened by pressing `?` and closed by pressing `Escape` or clicking outside the overlay. Use Shadcn/UI Dialog component for the modal container.

### Step 5 — Mount the Hook

Mount the `useKeyboardShortcuts` hook in the appropriate layout or page component so that it is active on all pages. Pass the shortcut definitions along with their callback functions. The callbacks should reference Zustand store actions and toast notification triggers as needed.

---

## Expected Output

A `useKeyboardShortcuts` custom hook that registers global keyboard shortcuts, a `KeyboardShortcutsHelp` dialog component listing all shortcuts, and proper integration into the application layout with input field guards and modifier key handling.

---

## Validation

- [ ] Ctrl+Enter triggers audio generation for the selected segment.
- [ ] Ctrl+Shift+Enter triggers video export/render.
- [ ] Escape closes any open modal or side panel.
- [ ] Ctrl+S saves settings when the GlobalSettings panel is open and prevents the browser Save dialog.
- [ ] ? opens the keyboard shortcuts help dialog.
- [ ] Shortcuts do not fire when the user is typing in input fields (except Escape).
- [ ] Help dialog lists all shortcuts with key combination badges and descriptions.
- [ ] Help dialog closes on Escape or clicking outside.
- [ ] Shortcuts that require preconditions (e.g., segment selected) show informative toast messages when preconditions are not met.

---

## Notes

- Keyboard shortcuts are a power-user feature. They enhance workflow speed but are not required for basic operation — every shortcut action is also accessible via buttons in the UI.
- The Ctrl+S prevention of browser Save is critical. Without `event.preventDefault()`, pressing Ctrl+S would open the browser's "Save Page As" dialog, which is confusing in a web application context.
- Consider using the `code` property of the keyboard event (e.g., `KeyS`, `Enter`) rather than the `key` property for modifier combinations, as `key` values can vary across keyboard layouts.
- The shortcuts map should be defined using the constants file (Task 05.03.13) so that shortcut key combinations are centrally defined and easy to modify.

---

> **Parent:** [SubPhase_05_03_Overview.md](./SubPhase_05_03_Overview.md) (Layer 2)
> **Phase:** [Phase_05_Overview.md](../Phase_05_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
