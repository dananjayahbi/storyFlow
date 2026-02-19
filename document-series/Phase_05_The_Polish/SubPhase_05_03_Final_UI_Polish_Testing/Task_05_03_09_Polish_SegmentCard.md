# Task 05.03.09 — Polish SegmentCard

## Layer 3 Task Document

---

| **Field**              | **Value**                                                                                      |
| ---------------------- | ---------------------------------------------------------------------------------------------- |
| **Task ID**            | 05.03.09                                                                                       |
| **Task Name**          | Polish SegmentCard                                                                             |
| **Sub-Phase**          | 05.03 — Final UI Polish & Testing                                                              |
| **Phase**              | Phase 05 — The Polish                                                                          |
| **Layer**              | Layer 3 (Task Document)                                                                        |
| **Status**             | Not Started                                                                                    |
| **Estimated Complexity** | Medium                                                                                       |
| **Parent Document**    | [SubPhase_05_03_Overview.md](./SubPhase_05_03_Overview.md) (Layer 2)                           |
| **Dependencies**       | Task 05.03.07 (EmptyState for empty segments), Task 05.03.06 (ToastProvider for error toasts)  |
| **Output Files**       | `frontend/components/SegmentCard.tsx` (MODIFIED)                                               |

---

## Objective

Upgrade the existing SegmentCard component from its functional baseline to a polished, production-quality card with subtitle preview capabilities, proper loading and error states, smooth visual transitions, and content truncation for long narrative text.

---

## Instructions

### Step 1 — Add Subtitle Preview Toggle

Add a small toggle button or collapsible section within the SegmentCard that shows how the subtitle text will appear. When toggled on, render the subtitle chunks as a series of inline pill/badge elements — each pill represents one word chunk as split by `chunk_text`. Use the same Tailwind styling conventions used throughout the application (rounded, muted background, small font). When the segment has no subtitle data yet, show a brief "No subtitles generated" message in muted text. The toggle should default to collapsed (hidden) so that the card remains compact by default.

### Step 2 — Add Loading State Indicators

When the segment is in a processing state (audio generation in progress, render in progress), overlay the card content with a loading indicator. Use `animate-pulse` on the card body or a specific skeleton pattern to indicate that data is being fetched or processed. The loading state should be driven by the segment's status field from the Zustand store. Ensure that during the loading state, interactive controls (edit, delete, regenerate buttons) are disabled to prevent conflicting user actions.

### Step 3 — Add Inline Error Display

When a segment has an error (failed audio generation, failed render), display the error message inline within the card rather than relying solely on toast notifications. Use a small destructive-colored text block below the main content area showing the error message. Include a "Retry" button adjacent to the error message that triggers the appropriate regeneration action. This ensures errors are visible even if the user dismissed the toast notification.

### Step 4 — Add Smooth CSS Transitions

Apply `transition-all duration-200 ease-in-out` to the card container so that hover effects (shadow elevation, border color changes) animate smoothly rather than snapping instantly. Apply similar transitions to the subtitle preview toggle expand/collapse (use `max-height` transition or a height animation approach). When a segment status changes (idle → processing → completed → error), animate the background color or border color change subtly.

### Step 5 — Add Content Truncation

For segments with long narrative text, truncate the displayed text using Tailwind's `line-clamp-3` utility class so that only three lines are visible by default. Add a "Show more" / "Show less" toggle that expands the full text. This prevents segments with lengthy narratives from dominating the vertical space in the segment list and keeps the overall layout compact and scannable.

---

## Expected Output

A polished SegmentCard component that includes a subtitle preview toggle (word chunk pills), animated loading states with disabled controls, inline error messages with retry buttons, smooth CSS transitions for all state changes, and truncated text with show more/less for long narratives.

---

## Validation

- [ ] Subtitle preview toggle renders word chunks as pill elements when expanded.
- [ ] Subtitle preview toggle defaults to collapsed.
- [ ] "No subtitles generated" message shown for segments without subtitle data.
- [ ] Loading states use `animate-pulse` or skeleton pattern during processing.
- [ ] Interactive controls are disabled during loading/processing state.
- [ ] Error messages display inline within the card in destructive color.
- [ ] Retry button appears alongside inline error messages.
- [ ] Hover and state transitions animate smoothly with `transition-all duration-200`.
- [ ] Long narrative text is truncated to three lines with `line-clamp-3`.
- [ ] "Show more" / "Show less" toggle expands and collapses full text.

---

## Notes

- The SegmentCard is the most frequently viewed component in the entire application — users interact with it for every segment they create. Polish here has an outsized impact on perceived quality.
- The subtitle preview is a CSS-only approximation. It does not need to replicate the exact rendered subtitle appearance from MoviePy; it exists to give users a quick visual confirmation that their text was chunked correctly.
- Loading states should be tested with both short and long processing durations. The `animate-pulse` animation should look correct whether it runs for 1 second or 30 seconds.

---

> **Parent:** [SubPhase_05_03_Overview.md](./SubPhase_05_03_Overview.md) (Layer 2)
> **Phase:** [Phase_05_Overview.md](../Phase_05_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
