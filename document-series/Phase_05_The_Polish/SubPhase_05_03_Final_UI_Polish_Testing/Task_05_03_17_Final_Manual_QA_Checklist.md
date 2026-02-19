# Task 05.03.17 — Final Manual QA Checklist

## Layer 3 Task Document

---

| **Field**              | **Value**                                                                                      |
| ---------------------- | ---------------------------------------------------------------------------------------------- |
| **Task ID**            | 05.03.17                                                                                       |
| **Task Name**          | Final Manual QA Checklist                                                                      |
| **Sub-Phase**          | 05.03 — Final UI Polish & Testing                                                              |
| **Phase**              | Phase 05 — The Polish                                                                          |
| **Layer**              | Layer 3 (Task Document)                                                                        |
| **Status**             | Not Started                                                                                    |
| **Estimated Complexity** | Low                                                                                          |
| **Parent Document**    | [SubPhase_05_03_Overview.md](./SubPhase_05_03_Overview.md) (Layer 2)                           |
| **Dependencies**       | All preceding tasks in all phases (this is the final validation of the complete system)        |
| **Output Files**       | `docs/MANUAL_QA_CHECKLIST.md` (NEW)                                                            |

---

## Objective

Create a comprehensive manual QA checklist document that covers every user-facing feature, edge case, and quality standard across the entire StoryFlow application. This checklist is the final gate before the application is considered complete — every item must be manually verified by a human tester.

---

## Instructions

### Step 1 — Project Management Section

Create a checklist section covering project CRUD operations:

- Create a new project with a title and description — verify it appears on the dashboard.
- Edit an existing project's title and description — verify changes persist after page refresh.
- Delete a project — verify it is removed from the dashboard and all associated segments are deleted.
- Create multiple projects — verify all appear in the dashboard card grid.
- Verify the dashboard displays correct status badges (Draft, In Progress, Rendered, Error) for each project.
- Verify sort controls (by date, by title) work correctly.
- Verify search/filter bar filters projects by title in real-time.
- Verify loading skeletons appear during initial page load.
- Verify the EmptyState component appears when no projects exist.

### Step 2 — Segment Management Section

Create a checklist section covering segment CRUD operations within a project:

- Add a new segment with narrative text and an image file — verify it appears in the segment list.
- Edit a segment's narrative text — verify changes persist.
- Delete a segment — verify it is removed from the list.
- Reorder segments (if drag-and-drop is implemented) — verify new order persists.
- Verify long narrative text is truncated with "Show more" / "Show less" toggle.
- Verify the SegmentCard displays subtitle preview pills when toggled on.
- Verify loading state indicators appear during segment processing.
- Verify inline error messages appear when a segment fails.

### Step 3 — Audio Generation Section

Create a checklist section covering TTS audio generation:

- Generate audio for a single segment — verify audio file is created and playable.
- Generate audio for multiple segments — verify all audio files are created.
- Regenerate audio for a segment — verify the new audio replaces the previous one.
- Change the default voice in GlobalSettings and generate audio — verify the new voice is used.
- Verify progress indication during audio generation.
- Verify error handling when audio generation fails (e.g., corrupt image file).

### Step 4 — Video Rendering Section

Create a checklist section covering the render pipeline:

- Render a single-segment project — verify output video is created.
- Render a multi-segment project — verify all segments are assembled in order.
- Verify Ken Burns zoom effect is visible in the rendered video.
- Verify subtitle text appears in the rendered video at correct times.
- Verify crossfade transitions appear between segments in a multi-segment project.
- Verify render progress polling updates correctly on the frontend.
- Verify render progress reaches 100 percent and the "Complete" state is displayed.
- Attempt to render while a render is already in progress — verify the system blocks the second render.
- Render with custom GlobalSettings (different resolution, different FPS) — verify output matches the settings.

### Step 5 — GlobalSettings Section

Create a checklist section covering the settings panel:

- Open the GlobalSettings panel — verify it slides in from the right side.
- Change the default voice using the VoiceSelector dropdown — verify the change persists after saving.
- Change subtitle font size, color, and position — verify the SubtitlePreview updates in real-time.
- Upload a custom font file (.ttf) — verify the font family updates in settings.
- Attempt to upload an invalid file (wrong extension) — verify a descriptive error message appears.
- Attempt to upload an oversized file — verify a descriptive error message appears.
- Change render resolution and FPS — verify the RenderSettingsForm reflects the changes.
- Verify the zoom slider adjusts the Ken Burns zoom level.
- Save settings — verify a success toast notification appears.
- Close the settings panel with Escape — verify it closes.
- Reopen the settings panel — verify all previously saved values are still displayed.

### Step 6 — Keyboard Shortcuts Section

Create a checklist section covering keyboard shortcuts:

- Press Ctrl+Enter with a segment selected — verify audio generation triggers.
- Press Ctrl+Shift+Enter on a project page — verify render triggers.
- Press Escape while a modal is open — verify the modal closes.
- Press Ctrl+S while the settings panel is open — verify settings save and the browser Save dialog does not appear.
- Press ? — verify the keyboard shortcuts help dialog opens.
- Type in an input field and press shortcut keys — verify shortcuts do not fire while typing (except Escape).

### Step 7 — Error Handling and Edge Cases Section

Create a checklist section covering error conditions:

- Navigate to a non-existent project URL — verify a meaningful error or redirect is shown.
- Disconnect from the backend (stop the Django server) and attempt actions — verify error toasts appear.
- Create a project with an extremely long title — verify it does not break the layout.
- Create a segment with an empty narrative text — verify appropriate validation.
- Upload an image file that is not a valid image — verify error handling.
- Verify the ErrorBoundary catches rendering errors and displays the fallback page with "Reload Page" button.

### Step 8 — Visual Polish and UX Section

Create a checklist section covering visual quality:

- Verify the application looks correct on a 1920×1080 screen.
- Verify the application looks correct on a 1366×768 screen (smaller laptop).
- Verify all hover effects animate smoothly (no snapping or jittering).
- Verify toast notifications appear and auto-dismiss correctly.
- Verify loading states (skeletons, spinners, animate-pulse) appear during all asynchronous operations.
- Verify all buttons have appropriate disabled states during processing.
- Verify consistent spacing, typography, and color usage across all pages.
- Verify dark mode compatibility if applicable (or note if dark mode is out of scope).

---

## Expected Output

A `docs/MANUAL_QA_CHECKLIST.md` file containing 8 sections with approximately 60–80 individual checklist items formatted as Markdown checkboxes. Each item should be specific and testable — a tester should be able to unambiguously determine whether the item passes or fails.

---

## Validation

- [ ] Checklist covers all 5 phases of StoryFlow functionality (project management, segment management, audio generation, video rendering, UI polish).
- [ ] Each checklist item is specific and pass/fail testable.
- [ ] Edge cases and error conditions are included.
- [ ] Keyboard shortcuts are tested.
- [ ] GlobalSettings panel is thoroughly tested.
- [ ] Visual polish items are included.
- [ ] The checklist is formatted as Markdown checkboxes for easy tracking.
- [ ] The checklist is comprehensive enough that completing it gives confidence the application is ready for use.

---

## Notes

- This is the final task in the entire StoryFlow Document-Driven Development series. Completing this checklist document represents the completion of all planning documentation for StoryFlow v1.0.
- The checklist is a document, not automated tests. It is designed to be printed or opened in a Markdown viewer and checked off manually by a human tester. Automated tests (Tasks 05.03.15 and 05.03.16) cover the programmatic verification; this checklist covers the subjective, visual, and experiential aspects that automated tests cannot capture.
- The checklist should be treated as a living document — additional items may be added as the implementation progresses and new edge cases are discovered. The version created in this task is the initial baseline.
- Dark mode support is explicitly out of scope for StoryFlow v1.0. If this comes up during QA, note it as a known limitation rather than a bug.

---

> **Parent:** [SubPhase_05_03_Overview.md](./SubPhase_05_03_Overview.md) (Layer 2)
> **Phase:** [Phase_05_Overview.md](../Phase_05_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
