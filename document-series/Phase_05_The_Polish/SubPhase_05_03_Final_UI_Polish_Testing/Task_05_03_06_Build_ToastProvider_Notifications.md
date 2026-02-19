# Task 05.03.06 — Build ToastProvider Notifications

## Layer 3 Task Document

---

| **Field**              | **Value**                                                                                      |
| ---------------------- | ---------------------------------------------------------------------------------------------- |
| **Task ID**            | 05.03.06                                                                                       |
| **Task Name**          | Build ToastProvider Notifications                                                              |
| **Sub-Phase**          | 05.03 — Final UI Polish & Testing                                                              |
| **Phase**              | Phase 05 — The Polish                                                                          |
| **Layer**              | Layer 3 (Task Document)                                                                        |
| **Status**             | Not Started                                                                                    |
| **Estimated Complexity** | Medium                                                                                       |
| **Parent Document**    | [SubPhase_05_03_Overview.md](./SubPhase_05_03_Overview.md) (Layer 2)                           |
| **Dependencies**       | None (infrastructure component — independent of other tasks)                                   |
| **Output Files**       | `frontend/components/ToastProvider.tsx` (NEW), `frontend/app/layout.tsx` (MODIFIED), multiple existing components (MODIFIED) |

---

## Objective

Set up a global toast notification system using the Sonner library (recommended over Shadcn/UI Toast for its simplicity and better defaults), and audit the entire frontend codebase to replace all `alert()` calls and user-facing `console.log()` calls with properly typed toast notifications (success, error, warning, info).

---

## Instructions

### Step 1 — Install the Toast Library

Install Sonner via npm. Sonner is the recommended choice because it has a simpler API (`toast.success("msg")` vs. Shadcn's more verbose toast hook pattern), built-in rich colors for different toast types, and requires minimal boilerplate setup.

### Step 2 — Create the ToastProvider Component

Create `frontend/components/ToastProvider.tsx` as a client component. Render the Sonner `Toaster` component with the following configuration: position set to "bottom-right" (keeps toasts out of the way of the left sidebar and main content), `richColors` enabled for automatic color-coding by toast type, `closeButton` enabled so users can manually dismiss toasts, and `duration` set to 4000 milliseconds for auto-dismiss.

### Step 3 — Mount in Root Layout

Add the `<ToastProvider />` component to `frontend/app/layout.tsx`, rendering it inside the body alongside the existing page content. The ToastProvider should be mounted at the root level so toasts are accessible from any page or component in the application.

### Step 4 — Audit and Replace All alert() Calls

Search the entire frontend codebase for all uses of `alert()`. For each occurrence, determine the intent (success feedback, error display, warning, informational) and replace with the appropriate Sonner toast call:

- Successful operations (save, upload, generation complete) → `toast.success(message)`
- Error conditions (API failure, validation error) → `toast.error(message)`
- Warnings (voice change, missing ImageMagick) → `toast.warning(message)`
- Informational (render in progress, loading) → `toast.info(message)`

Use the centralized message strings from `TOAST_MESSAGES` in `lib/constants.ts` (Task 05.03.13) wherever possible to maintain consistency.

### Step 5 — Audit and Replace User-Facing console.log() Calls

Search the frontend codebase for `console.log()` calls that serve as user feedback (e.g., logging "Audio generated successfully" to the console). Replace these with appropriate toast notifications. Preserve `console.log()` and `console.error()` calls that are genuinely for developer debugging — those should remain.

### Step 6 — Establish Toast Usage Patterns

Document the standard toast usage patterns for the team:

- **Success:** Used after successful operations that the user initiated. Short confirmatory message. Example: "Settings saved successfully".
- **Error:** Used when an operation the user initiated fails. Include specific error details when available from the API response. Example: "Failed to upload image: File too large".
- **Warning:** Used for non-blocking warnings that the user should be aware of. Example: "Voice changed. Re-generate audio to hear the new voice."
- **Info:** Used for status updates on long-running operations. Example: "Rendering video..."

---

## Expected Output

A working global toast notification system with Sonner mounted in the root layout, and all existing `alert()` and user-facing `console.log()` calls replaced with properly typed toast notifications across the entire frontend codebase.

---

## Validation

- [ ] Sonner is installed and `ToastProvider` is mounted in `app/layout.tsx`.
- [ ] Toasts appear at the bottom-right of the screen.
- [ ] Success toasts display in green.
- [ ] Error toasts display in red.
- [ ] Warning toasts display in yellow/amber.
- [ ] Info toasts display in blue.
- [ ] Toasts auto-dismiss after 4 seconds.
- [ ] Toasts have a visible close button for manual dismissal.
- [ ] No `alert()` calls remain in the frontend codebase.
- [ ] No user-facing `console.log()` calls remain (developer debug logs are acceptable).
- [ ] Toast messages use centralized strings from `TOAST_MESSAGES` where applicable.

---

## Notes

- Sonner is chosen over Shadcn/UI Toast because it requires less boilerplate. Shadcn Toast needs a toast hook, a toast action component, and more configuration. Sonner's API is a simple function call: `toast.success("msg")`.
- The toast position "bottom-right" is chosen to avoid overlap with the settings sidebar (left side) and the main timeline content (center). This keeps the UI clean.
- The audit of existing `alert()` and `console.log()` calls is the bulk of the work in this task. All frontend components from Phases 01–04 should be checked. Key locations include: audio generation callbacks, render callbacks, import handlers, image upload handlers, and settings save handlers.
- After this task, `alert()` should never be used in the codebase again. All user-facing feedback goes through the toast system.

---

> **Parent:** [SubPhase_05_03_Overview.md](./SubPhase_05_03_Overview.md) (Layer 2)
> **Phase:** [Phase_05_Overview.md](../Phase_05_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
