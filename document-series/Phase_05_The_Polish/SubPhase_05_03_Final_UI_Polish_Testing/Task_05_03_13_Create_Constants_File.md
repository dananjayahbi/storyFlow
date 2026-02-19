# Task 05.03.13 — Create Constants File

## Layer 3 Task Document

---

| **Field**              | **Value**                                                                                      |
| ---------------------- | ---------------------------------------------------------------------------------------------- |
| **Task ID**            | 05.03.13                                                                                       |
| **Task Name**          | Create Constants File                                                                          |
| **Sub-Phase**          | 05.03 — Final UI Polish & Testing                                                              |
| **Phase**              | Phase 05 — The Polish                                                                          |
| **Layer**              | Layer 3 (Task Document)                                                                        |
| **Status**             | Not Started                                                                                    |
| **Estimated Complexity** | Low                                                                                          |
| **Parent Document**    | [SubPhase_05_03_Overview.md](./SubPhase_05_03_Overview.md) (Layer 2)                           |
| **Dependencies**       | None (provides constants consumed by other tasks)                                              |
| **Output Files**       | `frontend/constants/index.ts` (NEW)                                                            |

---

## Objective

Create a centralized constants file that consolidates all magic numbers, default values, validation rules, toast messages, keyboard shortcut definitions, and render parameters into named exports, eliminating scattered hardcoded values throughout the frontend codebase.

---

## Instructions

### Step 1 — Define Available Voices

Export an `AVAILABLE_VOICES` constant as a readonly array of objects, each containing a voice identifier string, a human-readable display name, and a language tag. This should list all Kokoro TTS voices that the system supports. These values are used by the VoiceSelector component (Task 05.03.02) to populate the voice dropdown and by the backend voice listing endpoint for cross-reference.

### Step 2 — Define Default Settings

Export a `DEFAULT_SETTINGS` constant object containing the factory default values for all global settings fields: default voice (e.g., the first available voice identifier), default subtitle font family ("Arial"), default subtitle font size (48), default subtitle font color ("#FFFFFF"), default subtitle position ("bottom"), default render resolution (1920×1080), default FPS (30), default Ken Burns zoom level (1.2), and default transition duration (0.5 seconds). These defaults are used when initializing the GlobalSettings for the first time and as fallback values when settings are missing.

### Step 3 — Define Validation Rules

Export a `VALIDATION` constant object containing the min/max boundaries and constraints for all user-configurable values: subtitle font size range (minimum 12, maximum 120), Ken Burns zoom level range (minimum 1.0, maximum 2.0), transition duration range (minimum 0.0, maximum 2.0 seconds), FPS allowed values (24, 30, 60), resolution presets (720p, 1080p, 4K), maximum font file size (10 MB), and allowed font file extensions (".ttf", ".otf", ".woff", ".woff2"). These constants are consumed by form validation logic in the settings UI components.

### Step 4 — Define Toast Messages

Export a `TOAST_MESSAGES` constant object with predefined success and error message strings used throughout the application: settings saved successfully, settings save failed, font uploaded successfully, font upload failed, audio generation started, audio generation completed, audio generation failed, render started, render completed, render failed, project created, project deleted, and any other recurring notification messages. Centralizing these ensures consistent messaging and makes future copy edits trivial.

### Step 5 — Define Keyboard Shortcuts

Export a `KEYBOARD_SHORTCUTS` constant array where each entry contains: the key combination string (e.g., "Ctrl+Enter"), the key code for programmatic matching (e.g., "Enter" with ctrlKey: true), and a human-readable description (e.g., "Generate audio for selected segment"). These definitions are consumed by the `useKeyboardShortcuts` hook (Task 05.03.11) and the KeyboardShortcutsHelp dialog.

### Step 6 — Define Render Constants

Export a `RENDER_CONSTANTS` object containing render pipeline parameters that are referenced across the frontend: polling interval for render progress (2000 milliseconds), maximum polling duration before timeout (600000 milliseconds / 10 minutes), crossfade duration (0.5 seconds), and any other render-related numeric values currently hardcoded in the frontend.

---

## Expected Output

A single `frontend/constants/index.ts` file exporting `AVAILABLE_VOICES`, `DEFAULT_SETTINGS`, `VALIDATION`, `TOAST_MESSAGES`, `KEYBOARD_SHORTCUTS`, and `RENDER_CONSTANTS` as named, typed, readonly constant exports.

---

## Validation

- [ ] All constants are exported as named exports from `frontend/constants/index.ts`.
- [ ] All constants use `as const` or explicit readonly typing to prevent accidental mutation.
- [ ] `AVAILABLE_VOICES` lists all Kokoro TTS voices with identifier, display name, and language.
- [ ] `DEFAULT_SETTINGS` provides factory defaults for every GlobalSettings field.
- [ ] `VALIDATION` defines min/max boundaries for all user-configurable numeric fields.
- [ ] `TOAST_MESSAGES` covers all success and error notification strings used in the app.
- [ ] `KEYBOARD_SHORTCUTS` defines key combinations, codes, and descriptions for all shortcuts.
- [ ] `RENDER_CONSTANTS` defines polling interval, timeout, and crossfade duration values.
- [ ] No magic numbers or hardcoded strings remain in components that should reference these constants.

---

## Notes

- This is a pure data file with no logic, no side effects, and no imports other than possibly TypeScript types. It should be the simplest file in the entire codebase to review.
- The `as const` assertion is important — it narrows string literal types and makes the constants truly immutable at the type level, not just by convention.
- This task should ideally be completed early in SubPhase 05.03 so that other tasks can import from it immediately. However, it has no strict execution-order dependency — other tasks can temporarily use hardcoded values and switch to constants during integration.

---

> **Parent:** [SubPhase_05_03_Overview.md](./SubPhase_05_03_Overview.md) (Layer 2)
> **Phase:** [Phase_05_Overview.md](../Phase_05_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
