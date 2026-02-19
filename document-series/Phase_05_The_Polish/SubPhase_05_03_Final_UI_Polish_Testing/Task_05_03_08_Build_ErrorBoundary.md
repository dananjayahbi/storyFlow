# Task 05.03.08 — Build ErrorBoundary

## Layer 3 Task Document

---

| **Field**              | **Value**                                                                                      |
| ---------------------- | ---------------------------------------------------------------------------------------------- |
| **Task ID**            | 05.03.08                                                                                       |
| **Task Name**          | Build ErrorBoundary                                                                            |
| **Sub-Phase**          | 05.03 — Final UI Polish & Testing                                                              |
| **Phase**              | Phase 05 — The Polish                                                                          |
| **Layer**              | Layer 3 (Task Document)                                                                        |
| **Status**             | Not Started                                                                                    |
| **Estimated Complexity** | Low                                                                                          |
| **Parent Document**    | [SubPhase_05_03_Overview.md](./SubPhase_05_03_Overview.md) (Layer 2)                           |
| **Dependencies**       | None (safety-net component — independent of other tasks)                                       |
| **Output Files**       | `frontend/components/ErrorBoundary.tsx` (NEW), `frontend/app/layout.tsx` (MODIFIED)            |

---

## Objective

Build a React error boundary that wraps the entire application and catches unhandled JavaScript rendering errors, displaying a user-friendly fallback page instead of a blank white screen.

---

## Instructions

### Step 1 — Create the ErrorBoundary Class Component

Create `frontend/components/ErrorBoundary.tsx` as a client component using a React class component (error boundaries require class components — function components cannot use `getDerivedStateFromError`). The component accepts `children` as its only prop and maintains internal state tracking whether an error has occurred and the error object itself.

### Step 2 — Implement Error Lifecycle Methods

Implement `getDerivedStateFromError(error)` as a static method that sets the state to `{ hasError: true, error }` when a rendering error is thrown. Implement `componentDidCatch(error, errorInfo)` to log the error and component stack trace to `console.error` for developer debugging.

### Step 3 — Render Fallback UI

When `hasError` is true, render a centered full-screen layout with: a warning/alert triangle icon (from Lucide React) in a destructive color, a heading "Something went wrong", a brief description "An unexpected error occurred. Please try reloading the page.", and a "Reload Page" button that calls `window.location.reload()`. Optionally include a "Show Details" toggle that reveals the error message and stack trace for debugging.

### Step 4 — Render Children Normally

When `hasError` is false, render `this.props.children` without modification — the error boundary is transparent during normal operation.

### Step 5 — Mount in Root Layout

Wrap the main content in `frontend/app/layout.tsx` with `<ErrorBoundary>`. The error boundary should wrap the `{children}` render but be inside the HTML/body tags and after any providers (like ToastProvider) so that toast notifications still work even if the main content throws.

---

## Expected Output

An `ErrorBoundary.tsx` class component mounted in the root layout that catches unhandled rendering errors and displays a friendly fallback page with a reload button, preventing the app from showing a blank white screen.

---

## Validation

- [ ] ErrorBoundary is a class component with `getDerivedStateFromError` and `componentDidCatch`.
- [ ] Unhandled rendering errors trigger the fallback UI.
- [ ] Fallback UI shows a warning icon, error message heading, description, and "Reload Page" button.
- [ ] "Reload Page" button calls `window.location.reload()`.
- [ ] Error details are logged to `console.error` in the browser DevTools.
- [ ] ErrorBoundary wraps the main content in `app/layout.tsx`.
- [ ] Normal rendering (no errors) passes children through without modification.

---

## Notes

- This is the only class component in the entire StoryFlow frontend — everything else uses function components with hooks. React 19 still requires class components for error boundaries; there is no hook-based equivalent.
- The error boundary catches rendering errors only. Errors in event handlers, asynchronous code (promises, setTimeout), or server-side rendering are not caught by error boundaries. Those are handled by individual try/catch blocks and toast notifications throughout the application.
- The error boundary serves as a last-resort safety net. In a well-tested application, it should rarely trigger. Its value is preventing the catastrophic "blank white screen" scenario that confuses non-technical users.

---

> **Parent:** [SubPhase_05_03_Overview.md](./SubPhase_05_03_Overview.md) (Layer 2)
> **Phase:** [Phase_05_Overview.md](../Phase_05_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
