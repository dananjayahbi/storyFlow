# Task 05.03.03 — Build SubtitleSettingsForm

## Layer 3 Task Document

---

| **Field**              | **Value**                                                                                      |
| ---------------------- | ---------------------------------------------------------------------------------------------- |
| **Task ID**            | 05.03.03                                                                                       |
| **Task Name**          | Build SubtitleSettingsForm                                                                     |
| **Sub-Phase**          | 05.03 — Final UI Polish & Testing                                                              |
| **Phase**              | Phase 05 — The Polish                                                                          |
| **Layer**              | Layer 3 (Task Document)                                                                        |
| **Status**             | Not Started                                                                                    |
| **Estimated Complexity** | High                                                                                         |
| **Parent Document**    | [SubPhase_05_03_Overview.md](./SubPhase_05_03_Overview.md) (Layer 2)                           |
| **Dependencies**       | Task 05.03.12 (Zustand store must include uploadFont action and settings types)                |
| **Output Files**       | `frontend/components/SubtitleSettingsForm.tsx` (NEW)                                           |

---

## Objective

Build a form component providing subtitle font selection/upload and subtitle color picking capabilities. The font section allows users to upload custom `.ttf` or `.otf` font files, while the color section provides a hex color picker for the subtitle text color. Both settings auto-save to the backend.

---

## Instructions

### Step 1 — Create the SubtitleSettingsForm Component

Create `frontend/components/SubtitleSettingsForm.tsx` as a client component. The component accepts props for the current `font` (font file path string), the current `color` (hex color string), and an `onChange` callback for persisting changes.

### Step 2 — Build the Font Selector Section

Display the current font name, parsed from the file path. If the font path is something like "/fonts/custom.ttf", extract and display "custom". If the font path is empty or points to the default bundled font, display "Default (Roboto Bold)" as the label.

Add an "Upload Font" button that triggers a hidden `<input type="file" accept=".ttf,.otf">` element. When the user selects a file, validate the file extension (must be `.ttf` or `.otf`) and file size (maximum 10 MB as defined in the `VALIDATION` constants). If validation passes, construct a `FormData` object with the font file and call the `uploadFont` action from the Zustand store, which sends a `POST /api/settings/font/upload/` request. On success, show a success toast with "Font uploaded successfully". On failure, show an error toast with the error message.

Show a loading spinner or progress indicator while the font upload is in progress.

### Step 3 — Build the Color Picker Section

Display the current subtitle color as a small colored square (swatch) next to the hex value text. The user can click on the swatch or the hex value to activate editing.

Provide a color input mechanism — either a native `<input type="color">` for the browser's built-in color picker, or a text input that accepts hex color strings. Validate the input against the hex color regex pattern from `VALIDATION.HEX_COLOR_REGEX` (must match `#RGB` or `#RRGGBB`).

Debounce color changes by 300 milliseconds to avoid sending a PATCH request for every character typed. After the debounce period, call `onChange({ subtitle_color: newColor })` to persist the change.

### Step 4 — Add Section Labels and Icons

Add a section header with a text/pencil icon and the label "Subtitles". Below it, add sub-labels for "Font" and "Color" to clearly separate the two settings areas.

### Step 5 — Handle Validation Errors

For the font upload: if the user selects a file with an invalid extension (not `.ttf` or `.otf`), show an inline error message below the upload button: "Only .ttf and .otf files are accepted". If the file exceeds the size limit, show: "Font file must be under 10 MB". Do not send the request to the server if client-side validation fails.

For the color picker: if the user enters an invalid hex string, show an inline error message below the color input: "Enter a valid hex color (e.g., #FFFFFF)". Do not send the request to the server until the value passes validation.

---

## Expected Output

A `SubtitleSettingsForm.tsx` component with a font upload section (displaying current font name, upload button, validation) and a color picker section (swatch display, hex input, validation), both auto-saving changes to the backend with toast notifications.

---

## Validation

- [ ] Current font name displays correctly (parsed from path or showing "Default").
- [ ] "Upload Font" button triggers file selection limited to `.ttf` and `.otf` files.
- [ ] Font upload sends the file via `POST /api/settings/font/upload/`.
- [ ] Success toast appears after successful font upload.
- [ ] Error toast appears if font upload fails.
- [ ] Invalid font file extensions are rejected with an inline error before upload.
- [ ] Font files over 10 MB are rejected with an inline error.
- [ ] Color swatch displays the current subtitle color.
- [ ] Color input accepts valid hex values (`#RGB` or `#RRGGBB`).
- [ ] Invalid hex values show an inline validation error.
- [ ] Color changes are debounced (300ms) before persisting.

---

## Notes

- The font upload uses `multipart/form-data` — Axios handles this correctly when passing a `FormData` object with the appropriate content type header.
- The hex color validation on the frontend mirrors the backend validation in `GlobalSettingsSerializer` — both use the same regex pattern, preventing round-trip failures.
- The color picker debounce is important to avoid API request floods. Without debouncing, a user typing "#FF0000" character by character would trigger 7 PATCH requests.

---

> **Parent:** [SubPhase_05_03_Overview.md](./SubPhase_05_03_Overview.md) (Layer 2)
> **Phase:** [Phase_05_Overview.md](../Phase_05_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
