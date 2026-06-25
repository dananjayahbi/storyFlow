# Feature 8.6 — Enhanced React Error Boundary with Retry and Diagnostics

| Field | Value |
|---|---|
| Feature ID | 8.6 |
| Title | Enhanced React Error Boundary with Retry and Diagnostics |
| Status | 🟡 Planned |
| Priority | Medium |
| Complexity | Low |
| Estimated Effort | 1–2 days |
| Dependencies | None — uses built-in React class component lifecycle methods and browser Clipboard API |
| Output Files (NEW) | None |
| Files Modified | `frontend/components/ErrorBoundary.tsx`, `frontend/app/projects/[id]/page.tsx`, any component file that renders SegmentCard instances |

---

## 1. Document Overview

### 1.1 Problem Statement

The current `ErrorBoundary` component in StoryFlow successfully catches React rendering
errors and prevents a full application white-screen-of-death, but it presents the user
with a blank, featureless panel containing only a static "Something went wrong" message
and no actionable path to recover. When a rendering error occurs — for example, a null
reference inside `SegmentCard` when an audio file record unexpectedly lacks a URL field —
the entire section guarded by the boundary goes blank and the user's only option is a full
browser page refresh. A forced refresh discards all unsaved form state including any
edited segment text, manually adjusted timings, re-ordered clips, and in-progress uploads.
This high-friction recovery experience makes transient, self-correcting errors feel
catastrophic to users who have been working in the editor for any length of time. The
problem is compounded in the developer workflow: because the boundary suppresses the error
after catching it, developers and support engineers receive no visible error detail from
the production UI, making diagnosis of intermittent null-reference or data-shape issues
difficult without setting up a dedicated remote crash reporting service.

### 1.2 Proposed Solution

Enhance the existing `ErrorBoundary` component to present a structured, actionable recovery
UI that allows users to retry without losing their session state, access the full technical
error for reporting, and optionally display fallback content while the error state persists.
All changes are confined to a single component file and a small number of usage sites; no
new infrastructure or backend changes are required.

The enhancement introduces several meaningful behavior improvements:

- Replace the generic blank-panel fallback UI with a clearly titled, appropriately styled
  error card that communicates the affected section failed without implying the entire
  application is broken or that data has been lost.

- Add a "Retry" button to the error card that resets the `hasError` state flag to false,
  causing React to re-mount the failed subtree from scratch. This recovers from transient
  errors — for example, a null audio URL that is populated by the time the component re-
  renders after a 200 ms state update — without requiring a full page reload.

- Add a "Copy Error Details" button that uses the browser's native Clipboard API to place
  the full error message and component stack trace on the clipboard, so a user can paste the
  complete diagnostic string directly into a support ticket or Slack message.

- Add a collapsible HTML details element beneath the main card that toggles a monospace-
  formatted block showing the error message and component stack, giving technical users and
  developers immediate in-page visibility without cluttering the default collapsed view.

- Accept an optional `fallback` prop that, when provided, renders a caller-supplied React
  node in place of or alongside the failed subtree, preserving layout structure. A typical
  usage is a blank SegmentCard placeholder so the Timeline row height and ordering remain
  intact while one card is in its error state.

- Accept an optional `onError` callback prop invoked inside `componentDidCatch` with the
  error and component info, enabling parent pages to log errors to the browser console or
  forward them to a future error reporting service without modifying the boundary itself.

- Wrap each individual `SegmentCard` rendering site in its own `ErrorBoundary` instance so
  that one broken segment does not tear down the entire Timeline — all other cards remain
  interactive while only the failing card occupies its own isolated error UI.

### 1.3 Scope

| Category | Item |
|---|---|
| In Scope | Retry button that resets hasError state to re-mount the failed subtree |
| In Scope | Copy Error Details button using the Clipboard API |
| In Scope | Collapsible technical details block for error message and component stack |
| In Scope | Optional fallback prop and onError callback prop on ErrorBoundary |
| Out of Scope | Remote error reporting or integration with any third-party crash service |
| Out of Scope | Storing or persisting error logs to the backend database |
| Out of Scope | Animated transitions in the error card UI |
| Out of Scope | Changes to error handling in non-React backend or Celery task code |

### 1.4 Key Files Reference

| File | Role |
|---|---|
| `frontend/components/ErrorBoundary.tsx` | Primary — all logic and UI for the enhanced boundary |
| `frontend/app/projects/[id]/page.tsx` | Add onError prop to top-level boundary; console.error log |
| `frontend/components/SegmentCard.tsx` | Wrap each card in its own ErrorBoundary with fallback prop |
| `frontend/components/ProgressBar.tsx` | Secondary candidate for individual ErrorBoundary wrapping |
| `frontend/__tests__/ErrorBoundary.test.tsx` | Unit tests for retry, copy-to-clipboard, and fallback logic |

---

### 1.5 Design Rationale

React's class-component-based error boundary API (`getDerivedStateFromError` and
`componentDidCatch`) is deliberately not available to function components, which means
this feature must remain a class component. The existing `ErrorBoundary.tsx` is already
a class component, so no architectural change is required — only new props and a richer
render method.

The decision to use the native HTML `details` and `summary` elements for the collapsible
diagnostics block is intentional. These elements provide built-in keyboard accessibility
(they are focusable and togglable with Enter or Space) and require zero JavaScript toggle
state. Using a custom useState-based collapse would add unnecessary code complexity and
could itself throw during an error state if the surrounding component context is broken.

The "Retry" mechanism works by resetting `hasError` to false in state, which causes React
to call the `render` method again with the original children. If the children throw
immediately on the retry attempt, `getDerivedStateFromError` fires again and the error UI
reappears — the boundary does not enter an infinite loop. This makes the retry safe to
provide unconditionally without requiring the caller to understand the error cause first.

Using the Clipboard API rather than a textarea-select-copy fallback is appropriate here
because the project's frontend already targets modern browsers. The catch handler that
falls back to `console.error` covers non-secure HTTP contexts (such as `http://localhost`
in some CI environments) where the Clipboard API is unavailable.

---

## 2. Flow Diagram

```
React renders subtree (e.g., SegmentCard)
           |
           | render() throws an error (e.g., null URL reference)
           v
  ErrorBoundary.getDerivedStateFromError()
           |
    sets hasError = true, stores error + componentStack
           |
           v
  ErrorBoundary.componentDidCatch()
           |
    calls optional onError(error, info) prop if provided
           |
           v
  ErrorBoundary renders fallback UI:
  +---------------------------------------------+
  |  "Something went wrong in this section"      |
  |                                              |
  |  [Retry]   [Copy Error Details]              |
  |                                              |
  |  <details> Technical Details (collapsed)     |
  |    error.message + componentStack            |
  |  </details>                                  |
  |                                              |
  |  (optional fallback prop renders here)       |
  +---------------------------------------------+
           |
    User clicks [Retry]
           |
    setState({ hasError: false })
           |
    React re-mounts the original subtree
           |
    If error is gone → normal render resumes
    If error persists → boundary catches again → UI reappears
```

---

## 3. Step-by-Step Instructions

### Step 1 — Update ErrorBoundary State and Props Interface

File: `frontend/components/ErrorBoundary.tsx`

The goal of this step is to give the component storage for the caught error data so that
subsequent UI steps (copy button, technical details block) have something to display.

Expand the TypeScript props interface to add two optional fields. The first is `fallback`
typed as `React.ReactNode` — this accepts any valid React renderable. The second is
`onError` typed as `(error: Error, info: React.ErrorInfo) => void` — matching exactly
the signature that `componentDidCatch` receives, so callers do not need to reshape the
arguments before forwarding them to a logger.

Expand the state interface to add two nullable fields alongside the existing `hasError`
boolean: an `error` field of type `Error | null` and a `componentStack` field of type
`string | null`. Initialize both to `null` in the class constructor's initial state.

Update the static `getDerivedStateFromError` method to return `{ hasError: true, error }`
so the Error object from the thrown exception is stored in state at the moment React first
catches it. This is intentionally a static method — it must not access instance properties
or call any side effects.

Update `componentDidCatch` to call `this.setState({ componentStack: info.componentStack })`
so the React component trace is stored alongside the error object. Also inside
`componentDidCatch`, add a guard that checks whether `this.props.onError` is defined and,
if so, calls it with `error` and `info`. Keep this call inside a try-catch to ensure that
a throwing `onError` callback does not corrupt the boundary's own error state.

### Step 2 — Build the Retry Button and Copy Error Button

File: `frontend/components/ErrorBoundary.tsx`

This step replaces the current static blank-panel fallback with an actionable error card.

In the `render` method, locate the existing branch where `this.state.hasError` is true and
replace its return value with a structured JSX block. Wrap everything in a div with
Tailwind classes that give the error card a visible border, a light red or amber background,
appropriate padding, and rounded corners so the card is clearly distinguishable from healthy
content without being alarming.

Inside the card, place a heading element (h3 or a bold paragraph) with the text
"Something went wrong in this section" as the first element. This phrasing deliberately
scopes the error to a section rather than the whole application, reducing user anxiety.

Below the heading, render two buttons horizontally using a flex div. The "Retry" button
calls `this.setState({ hasError: false, error: null, componentStack: null })` in its
onClick. The complete state reset ensures that no stale error data persists if the
re-mounted subtree renders successfully and a different error occurs later.

The "Copy Error Details" button onClick should: build a plain-text string by concatenating
`this.state.error?.message ?? "Unknown error"`, a double newline, and
`this.state.componentStack ?? "No stack available"`; pass that string to
`navigator.clipboard.writeText()`; chain a `.then()` that sets a local boolean flag
`copySuccess` in component state to briefly change the button label to "Copied!"; and
chain a `.catch()` that calls `console.error` with a descriptive message. The copySuccess
flag should be reset after approximately 2 seconds using a `setTimeout`.

### Step 3 — Add the Collapsible Technical Details Block

File: `frontend/components/ErrorBoundary.tsx`

Below the button row, add a native HTML `details` element containing a `summary` child
with the text "Technical Details". The `details` element is collapsed by default and
toggles open when the user clicks the summary text, with no JavaScript toggle logic
required. Give the `details` element a top margin class so it has visual breathing room
separating it from the button row above.

Inside the `details` element, render the error content in a `pre` or `p` element styled
with a monospace font (the Tailwind `font-mono` class), a small font size, overflow-x
auto for horizontal scrolling on narrow viewports, and a slightly darker background than
the outer card container. The content should display `this.state.error?.message` on the
first line, a blank line separator, and `this.state.componentStack` as the remaining text.

Wrap the entire `details` element in a conditional check on `this.state.error !== null`.
This guard prevents React from attempting to render a `details` element populated with
null content during the narrow timing window between when `getDerivedStateFromError` sets
`hasError: true` and when `componentDidCatch` populates the `error` field via `setState`.
Without the guard, users could briefly see an empty closed details block before the error
object arrives, which looks like a layout artifact.

### Step 4 — Render Optional Fallback Content

File: `frontend/components/ErrorBoundary.tsx`

After the error card div (heading, buttons, and details block), add a single conditional
render expression: if `this.props.fallback` is defined and non-null, render it inside a
wrapper div with a top margin class. If the prop is absent or null, render nothing at
that position — do not render an empty div, which would introduce unexpected spacing.

The purpose of this output slot is layout preservation. Consider a Timeline rendered as
a vertical list of SegmentCard components. Without a fallback, the error card for one
broken segment occupies a different height than an intact card, causing all downstream
cards to shift position. When the caller provides a blank SegmentCard placeholder as the
fallback, the broken card's total rendered height (error card + blank placeholder) matches
the typical card height, preventing any layout shift for the surrounding segments.

Add a JSDoc comment directly above the `ErrorBoundaryProps` interface (or above the class
declaration if there is no separate interface) that documents both new props:

The `fallback` prop comment should note that the provided node must be a stable, non-
throwing React element. If the fallback itself throws during render, it will be caught by
the nearest parent ErrorBoundary, not by this one.

The `onError` prop comment should note that it fires synchronously inside
`componentDidCatch` and must not throw. If it throws, the exception will be silently
suppressed by the try-catch guard added in Step 1.

### Step 5 — Wrap SegmentCard Instances and Wire the onError Prop

Files: Timeline or segment-list component, and `frontend/app/projects/[id]/page.tsx`

This step applies the enhanced ErrorBoundary in the two highest-value locations: the
individual segment cards and the project page top-level boundary.

Locate the component responsible for mapping over the project's segments and rendering
a `SegmentCard` for each one. This is likely a Timeline component or the segment section
within `app/projects/[id]/page.tsx`. Wrap each individual SegmentCard JSX element in an
`ErrorBoundary` with a stable `key` derived from the segment ID (the same key used for the
SegmentCard itself). Pass a blank placeholder component as the `fallback` prop — a simple
div with the same dimensions and border style as a SegmentCard but containing only a muted
"Unavailable" label is sufficient. Do not pass any of the segment data into the fallback;
the fallback should be entirely static and carry no references to the potentially corrupted
data that caused the error.

In `frontend/app/projects/[id]/page.tsx`, update the top-level `ErrorBoundary` wrapper
that guards the main page content. Pass it an `onError` prop that calls `console.error`
with a distinctive prefix string such as `"[StoryFlow ErrorBoundary]"` followed by the
error object and the component info. This single log line ensures that during development
every caught error remains visible in the browser console even when the UI handles it
gracefully, and it provides a clear hook point where a future integration — such as
passing the error to a dedicated logging endpoint or a third-party crash service — can
be added by modifying only this callback in this one file.

---

## 4. Expected Outcome

- When a rendering error occurs inside any `SegmentCard`, only that card's slot shows the
  error UI; all other segment cards in the Timeline remain fully interactive and unaffected.

- The user can click "Retry" on the failed card and, if the underlying error was transient,
  the card re-renders successfully without a page refresh, preserving all unsaved form state
  across the rest of the editor including segment text, timings, and in-progress uploads.

- Clicking "Copy Error Details" places a complete plain-text diagnostic string on the user's
  clipboard, containing both the error message and the React component stack trace, ready
  to paste directly into a support ticket or Slack thread.

- Expanding the "Technical Details" disclosure element reveals the error message and
  component stack inline in a readable monospace format with no page navigation or modal.

- When a parent component provides an `onError` callback, every caught error is routed to
  that callback synchronously inside `componentDidCatch`, enabling consistent logging to
  the browser console and a clear integration point for future error reporting services.

- When the `fallback` prop is provided, a neutral placeholder renders in the position of
  the failed subtree, preserving the page layout's row height and order so no downstream
  components shift position when one card enters the error state.

- The top-level `ErrorBoundary` on the project detail page continues to catch any rendering
  errors that escape all lower-level boundaries and presents the same improved recovery UI
  at the full-page level, ensuring no rendering error can produce a blank white screen.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] Test that `getDerivedStateFromError` returns `{ hasError: true, error }` with the
  thrown Error object stored in the returned state fragment.

- [ ] Test that clicking the Retry button calls `setState` with `hasError: false` and that
  the component subsequently renders `this.props.children` on the next render pass.

- [ ] Test that the Copy Error Details button calls `navigator.clipboard.writeText` with a
  string containing both the error message and the component stack; mock the Clipboard API
  in the jest test environment using `Object.defineProperty(navigator, 'clipboard', ...)`.

- [ ] Test that the `onError` prop callback is invoked exactly once inside
  `componentDidCatch` with the Error and ErrorInfo arguments, and that a throwing `onError`
  callback does not propagate the exception out of the boundary.

- [ ] Test that when `fallback` is provided it renders inside the error UI, and when omitted
  the fallback slot renders nothing and does not introduce empty DOM nodes.

### 5.2 Integration / Manual Tests

- [ ] Introduce a deliberate `throw new Error("test")` inside a SegmentCard render and
  confirm in the browser that only that single card's slot shows the error UI while all
  neighboring cards remain interactive and display their normal content.

- [ ] After the deliberate throw is removed, click "Retry" on the error card and confirm
  the card re-renders its normal content in place without any full page reload and without
  any other part of the editor losing its current state.

- [ ] Click "Copy Error Details" and paste into a plain-text editor; confirm the paste
  contains the error message on the first line and the full component stack on subsequent
  lines, and that the button label briefly changes to "Copied!" after the click.

- [ ] Click the "Technical Details" `summary` element and confirm the details block expands
  to show the error and stack in a monospace font; click again to confirm it collapses.

- [ ] Confirm that the top-level project page ErrorBoundary's `onError` callback fires and
  the browser console receives the `[StoryFlow ErrorBoundary]`-prefixed log message when
  any error anywhere in the page is caught by any boundary level.

### 5.3 Regression Tests

- [ ] Confirm that all components currently wrapped by `ErrorBoundary` render their children
  without interference when no error is thrown — the boundary must be fully transparent in
  the happy path and add no visible DOM elements.

- [ ] Confirm that the existing ErrorBoundary unit tests (if any exist in the test suite)
  continue to pass after the props interface and state interface are extended, verifying
  that `hasError` still initializes to false and children render normally on first mount.

- [ ] Confirm that instantiating `ErrorBoundary` without the `fallback` or `onError` props
  compiles without TypeScript errors and behaves identically to the baseline, validating
  that both props are correctly typed as optional.

---

## 6. Notes for AI Agent

- The `setState({ hasError: false })` call in the Retry handler is intentionally simple
  and requires no additional guard. React automatically calls `getDerivedStateFromError`
  again if the re-mounted children throw on the retry attempt, so the boundary enters its
  error UI again on the second throw without any risk of an infinite render loop. Do not
  add a retry-attempt counter or a disabled state to the Retry button unless the product
  requirements explicitly ask for it.

- The Clipboard API `navigator.clipboard.writeText()` is only available in secure contexts
  (HTTPS or localhost). In non-secure HTTP contexts the call rejects immediately. The catch
  handler that falls back to `console.error` is mandatory — without it, a rejected promise
  becomes an unhandled promise rejection that surfaces as a red console error, which is
  particularly confusing when the message appears alongside the error being diagnosed.

- When wrapping individual `SegmentCard` instances in their own `ErrorBoundary`, never
  pass the segment data object or any state derived from it as the `fallback` prop. The
  fallback must be a fully static, zero-dependency React element. Passing segment data into
  the fallback creates a reference to the same potentially corrupt data that caused the
  error in the first place, and could cause the fallback component itself to throw.

- The HTML `details` and `summary` elements are natively collapsible across all modern
  supported browsers with no JavaScript required. Do not replace them with a custom toggle
  built on `useState` — doing so would add state that needs to be reset when the boundary
  retries, complicates the component lifecycle, and provides no user-facing benefit.

- After completing Step 5, run a grep across the `frontend/` directory for the string
  `SegmentCard` to find every JSX usage site and confirm each one is wrapped in an
  `ErrorBoundary`. Document any additional wrapping sites discovered in the PR description
  so reviewers know the scope of the change accurately.

---

## 7. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Clipboard API unavailable in dev HTTP context | Medium | Low | Catch the rejected promise; fall back to console.error |
| Fallback prop holds stale segment reference | Low | Medium | Document prop contract; use static placeholder only |
| onError callback throws, corrupting boundary state | Low | High | Wrap the onError call in try-catch in componentDidCatch |
| SegmentCard wrapping missed at one usage site | Medium | Low | Post-implementation grep search for all SegmentCard uses |
| details element not supported in target browser | Very Low | Low | All browsers in support matrix implement details natively |
