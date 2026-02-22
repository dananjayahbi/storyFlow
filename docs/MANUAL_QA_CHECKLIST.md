# StoryFlow — Manual QA Checklist

> **Version:** 1.0  
> **Created:** Task 05.03.17 — Final Manual QA Checklist  
> **Purpose:** Final gate before StoryFlow v1.0 is considered complete.  
> **Instructions:** Open this file in a Markdown viewer. Check off each item (`[x]`) after manual verification. Every item must pass before the application is ready for use.

---

## Section 1 — Project Management

### 1.1 Project CRUD

- [ok] Create a new project using the **"+ New Project"** button — verify the "Create New Project" dialog appears with a title input and "Create" button.
- [ok] Enter a project title and submit — verify the project card appears on the dashboard with the correct title.
- [ok] Verify the "Create" button shows **"Creating…"** and is disabled while the request is in progress.
- [ok] Delete a project using the trash icon on its card — verify the "Delete Project" confirmation dialog appears warning about permanent removal.
- [ok] Confirm deletion — verify the project is removed from the dashboard and all associated segments are deleted.
- [ok] Create multiple projects (3+) — verify all appear in the dashboard card grid (responsive: 1 col mobile, 2 col md, 3 col lg).

### 1.2 Dashboard Display

- [x] Verify each project card displays: cover image thumbnail (gradient placeholder with image icon), project title (truncated with `line-clamp-1`), segment count ("{N} segment(s)"), and relative time ("Just now", "X minutes ago", etc.).
- [ok] Hover over the relative time — verify a tooltip shows the absolute date.
- [ok] Verify status badges display correctly for each state: **Draft** (muted), **In Progress** (amber, pulsing), **Rendered** (green), **Error** (red/destructive).
- [ ] Verify the **"🎬 Watch"** button appears only on rendered projects and opens the video player.
- [ ] Verify project cards are `opacity-75` when the project status is Error.

### 1.3 Search and Sort

- [ ] Type in the **"Search projects…"** search bar — verify projects are filtered by title in real-time (case-insensitive).
- [ ] Search for a term with no matches — verify the EmptyState shows "No matching projects" with a **"Clear search"** button.
- [ ] Click the **"Clear search"** button — verify all projects reappear.
- [ ] Click the sort toggle button — verify it cycles through: "Newest first", "Oldest first", "Title A–Z", "Title Z–A".
- [ ] Verify each sort mode correctly reorders the project cards.

### 1.4 Loading and Empty States

- [ ] Refresh the page — verify 3 loading skeleton placeholders with `animate-pulse` shimmer appear during initial load.
- [ ] Delete all projects — verify the EmptyState component appears with the FileText icon, title **"No projects yet"**, description "Create your first story to get started!", and CTA button **"+ New Project"**.
- [ ] Stop the backend server and refresh — verify the error message **"Failed to load projects. Is the backend server running?"** appears in red.

### 1.5 Import Story

- [ ] Click **"Import Story"** — verify the ImportDialog opens with **JSON** and **Text** format toggle buttons.
- [ ] Verify the JSON format shows the correct placeholder template with `title` and `segments` array.
- [ ] Toggle to **Text** format — verify the placeholder updates to the text-based format with `Text:` and `Prompt:` lines separated by `---`.
- [ ] Verify the **"Import"** button is disabled when the textarea is empty.
- [ ] Paste valid JSON content and click Import — verify the project is created and appears on the dashboard.
- [ ] Paste invalid JSON content and click Import — verify a red error box appears with field-specific or general error messages.
- [ ] Verify the optional title input field works — entering a title overrides the JSON title.
- [ ] Verify the character counter appears in the bottom-right of the textarea.
- [ ] Verify **Ctrl+Enter** submits the form from within the textarea.

---

## Section 2 — Segment Management

### 2.1 Segment Display

- [ ] Open a project with segments — verify the Timeline component displays all segments as SegmentCards in a scrollable list.
- [ ] Verify each SegmentCard displays: sequence badge (#1, #2, etc.), audio status badge, text content area, and image upload zone.
- [ ] Verify long narrative text (>150 chars) is truncated with a **"Show more"** / **"Show less"** toggle using ChevronDown/ChevronUp icons.

### 2.2 Text Editing

- [ ] Click into the SegmentTextEditor textarea — verify it is editable with placeholder "Segment text content...".
- [ ] Type new text and wait 500ms — verify the **"Saving…"** indicator appears briefly (debounced auto-save).
- [ ] Refresh the page — verify the edited text persists.

### 2.3 Image Upload

- [ ] Click the image upload drop zone (dashed border, "Drop image here or click to browse") — verify the file picker opens.
- [ ] Upload a valid image (JPEG, PNG, or WebP, under 20 MB) — verify the image preview appears (h-32 / h-40 on md).
- [ ] Hover over the image preview — verify the remove button (X icon, destructive variant) appears.
- [ ] Click the remove button — verify the image is removed and the drop zone reappears.
- [ ] Upload an invalid file type — verify a red error message appears below the zone.
- [ ] Upload an oversized file (>20 MB) — verify a red error message appears.
- [ ] Drag a valid image onto the drop zone — verify the border highlights on drag-over and the upload succeeds on drop.
- [ ] Verify keyboard support — press Enter or Space on the focused drop zone to open the file picker.

### 2.4 Image Prompt

- [ ] Verify the ImagePromptDisplay shows the prompt text in a mono-font muted box titled "Image Prompt".
- [ ] Click the copy button (Copy icon) — verify it changes to a Check icon for 2 seconds and the prompt is copied to clipboard.
- [ ] Verify segments with no image prompt show **"No image prompt"** in italic text.

### 2.5 Segment Locking

- [ ] Click the lock/unlock toggle on a segment — verify the icon switches between Lock and Unlock with appropriate tooltip ("Lock segment" / "Unlock segment").
- [ ] Lock a segment — verify the text editor becomes disabled, the image upload zone shows a disabled state, and the "Generate Audio" button is disabled with title "Unlock segment to generate audio".
- [ ] Verify a locked segment has an amber border visual indicator.

### 2.6 Segment Deletion

- [ ] Click the delete button (Trash icon) on a segment — verify the "Delete Segment" confirmation dialog appears warning about permanent removal including uploaded images.
- [ ] Confirm deletion — verify the segment is removed from the list and sequence numbers re-index.

### 2.7 Subtitle Preview

- [ ] Click the Subtitles icon toggle on a SegmentCard — verify the "Subtitle Preview" section expands.
- [ ] Verify generated subtitles display as inline Badge components showing word chunks.
- [ ] Verify segments without subtitles show **"No subtitles generated"** message.

### 2.8 Stale Audio Warning

- [ ] Generate audio for a segment, then edit the segment's text — verify an amber banner appears: **"Text changed — audio may be out of sync."** with a "Regenerate" link.

### 2.9 Error States

- [ ] Trigger a segment failure (e.g., corrupted data) — verify a red border appears on the card and an inline error banner shows with an AlertCircle icon, error message, and **"Retry"** button.
- [ ] Verify the SegmentCard pulses with animation during audio generation.

---

## Section 3 — Audio Generation

### 3.1 Single Segment Audio

- [ ] Click **"Generate Audio"** on a single segment (Volume2 icon + "Generate Audio" label) — verify the button changes to a spinner + **"Generating…"** (disabled).
- [ ] Wait for completion — verify the AudioStatusBadge changes from "No Audio" (gray) to "Ready" (green) with formatted duration.
- [ ] Verify the AudioPlayer appears with play/pause button, seek slider, and time display in "MM:SS / MM:SS" format.

### 3.2 Audio Playback

- [ ] Click the play button on an AudioPlayer — verify audio plays and the icon switches from Play to Pause.
- [ ] Drag the seek slider — verify playback position updates.
- [ ] Verify time display updates in real-time during playback.
- [ ] Verify the AudioPlayer shows a spinner + **"Loading audio…"** while the audio file loads.
- [ ] Verify mobile touch targets are appropriately sized (44×44px).

### 3.3 Bulk Audio Generation

- [ ] Click **"Generate All Audio"** in the action bar footer — verify generation starts for all eligible segments.
- [ ] Verify the **"Cancel"** button appears during bulk generation.
- [ ] Verify the bulk progress bar shows **"{completed}/{total} segments complete ({%})"** with a Progress bar.
- [ ] Wait for completion — verify the completion message shows success/fail counts.

### 3.4 Audio Regeneration

- [ ] Open the SegmentCard's more actions dropdown (MoreVertical icon) — verify **"Regenerate Audio"** option appears with RefreshCw icon.
- [ ] Click "Regenerate Audio" — verify the new audio replaces the previous one (cache busting via `?t={timestamp}` on audio URL).
- [ ] Verify the "Regenerate Audio" option is disabled when the segment is locked or generating.

### 3.5 Voice Selection

- [ ] Open the GlobalSettings panel — verify the VoiceSelector dropdown shows all 7 voices: Bella, Sarah, Nicole, Adam, Michael, Emma, George.
- [ ] Verify each voice displays as "Name (Gender)" or "Name (Accent Gender)" (e.g., "Emma (British Female)").
- [ ] Change the voice — verify a warning toast appears: **"Voice changed. Re-generate audio to hear the new voice."**
- [ ] Generate audio after changing the voice — verify the new voice is audible.

### 3.6 Audio Error Handling

- [ ] Trigger an audio generation failure — verify the AudioStatusBadge changes to "Failed" (red, AlertCircle icon) with a tooltip showing the error.
- [ ] Verify the GenerateAudioButton shows red error text + **"Retry"** button in the failed state.
- [ ] Verify the AudioPlayer shows an AlertCircle icon + **"Audio unavailable"** in red when the audio file is missing.

### 3.7 TTS Speed

- [ ] Adjust the **TTS Speed** slider in GlobalSettings (range 0.5x – 2.0x, step 0.1) — verify the current value displays as "{N}x".
- [ ] Generate audio after changing speed — verify the speech rate reflects the setting.

---

## Section 4 — Video Rendering

### 4.1 Render Trigger

- [ ] With a fully provisioned project (all segments have images and audio), verify the **"🎬 Export Video"** button is enabled (blue primary).
- [ ] With an incomplete project, verify the button is disabled with a tooltip listing what's missing (e.g., "3 segment(s) need images").
- [ ] Click the enabled Export Video button — verify the render starts and the button changes to spinner + **"Rendering…"** (disabled).

### 4.2 Render Progress

- [ ] During rendering, verify the RenderProgress component shows a Progress bar with percentage.
- [ ] Verify the status text shows **"Segment {X} of {Y} ({Z}%)"** plus the current phase text.
- [ ] Verify progress polling occurs every 3 seconds via the render-status endpoint.
- [ ] Verify the starting state shows **"Starting render…"** with an empty progress bar.
- [ ] Wait for render to complete — verify progress reaches 100% and the "Complete" state is displayed.

### 4.3 Render Output

- [ ] After successful render, verify the button changes to **"⬇️ Download Video"** (green).
- [ ] Click "Download Video" — verify the rendered MP4 file downloads.
- [ ] Verify the dropdown arrow reveals a **"🔄 Re-Render"** option.
- [ ] Click "Watch" on the project card — verify the VideoPreview component shows an HTML5 video player with native controls.
- [ ] Verify the VideoPreview shows **"Duration: MM:SS"** and a **"⬇️ Download Video"** button (outline variant).

### 4.4 Video Quality

- [ ] Play the rendered video — verify Ken Burns zoom effect is visible (image slowly zooms/pans).
- [ ] Verify subtitle text appears in the rendered video at correct timing.
- [ ] For multi-segment projects, verify crossfade transitions appear between segments.
- [ ] Render with custom GlobalSettings (different resolution, different FPS) — verify the output video resolution and frame rate match the settings.

### 4.5 Render Error Handling

- [ ] Attempt to render while a render is already in progress — verify the system blocks the second render with a 409 Conflict response and appropriate toast message.
- [ ] If render fails, verify the button changes to **"🔁 Retry Render"** (destructive red).
- [ ] Verify the VideoPreview shows **"Failed to load video"** + "The video file may have been deleted. Try re-rendering the project." when the video file is missing.

---

## Section 5 — GlobalSettings Panel

### 5.1 Panel Interaction

- [ ] Click the **Settings** gear icon in the left sidebar — verify the settings panel expands/collapses.
- [ ] Close the settings panel — verify the collapsed state persists to `localStorage` key `storyflow-settings-collapsed`.
- [ ] Reopen the settings panel — verify all previously saved values are still displayed.
- [ ] Verify loading skeletons (shimmer placeholders) appear while settings are loading.
- [ ] Trigger a settings load failure — verify red error text + **"Retry"** button with RefreshCw icon appears.

### 5.2 Voice Settings

- [ ] Verify the **VOICE** section shows a Mic icon and heading.
- [ ] Verify the VoiceSelector dropdown lists all 7 available voices with correct labels.
- [ ] Change the voice — verify the selection persists after page refresh.
- [ ] Verify the dropdown is disabled with placeholder **"Loading voices…"** during initial voice list fetch.

### 5.3 Subtitle Settings

- [ ] Verify the **SUBTITLES** section shows a Type icon and heading.
- [ ] Verify the current font name is displayed (parsed from path), defaulting to **"Default (Roboto Bold)"**.
- [ ] Click **"Upload Font"** — verify the file picker opens accepting `.ttf` and `.otf` files.
- [ ] Upload a valid `.ttf` font — verify the font name updates in settings.
- [ ] Attempt to upload an invalid file extension — verify error message: **"Only .ttf and .otf files are accepted"**.
- [ ] Attempt to upload an oversized file (>10 MB) — verify error message: **"Font file must be under 10 MB"**.
- [ ] Verify the **"Upload Font"** button shows **"Uploading…"** with a spinner during upload.
- [ ] Click the native color picker swatch — verify the color changes.
- [ ] Type a hex color in the mono-font input (placeholder "#FFFFFF", max 7 chars) — verify it accepts valid `#RGB` and `#RRGGBB` formats.
- [ ] Type an invalid hex color — verify error message: **"Enter a valid hex color (e.g., #FFFFFF)"**.
- [ ] Verify the **SubtitlePreview** (dark video-frame simulation, 120px tall) updates in real-time with the chosen color, showing sample text "The quick brown fox jumps over" with text shadow.

### 5.4 Render Settings

- [ ] Verify the **RENDER SETTINGS** section shows a Film icon and heading.
- [ ] Adjust the **Zoom Intensity** slider (range 1.0x – 2.0x, step 0.1) — verify the current value displays.
- [ ] Verify the **Resolution** field shows **"1920 × 1080 (1080p)"** as read-only with an info tooltip: "Resolution is not configurable in v1.0".
- [ ] Verify the **Framerate** field shows **"30 fps"** as read-only.

### 5.5 Settings Persistence

- [ ] Change multiple settings (voice, font color, zoom intensity) — verify a success toast appears: **"Settings saved successfully"**.
- [ ] Refresh the page — verify all changed settings are still displayed with the saved values.
- [ ] Trigger a save failure — verify error toast: **"Failed to save settings"**.

---

## Section 6 — Keyboard Shortcuts

### 6.1 Shortcut Actions

- [ ] Press **Ctrl+Enter** on a project page — verify audio generation triggers for all segments (or toast if no project/no segments).
- [ ] Press **Ctrl+Shift+Enter** on a project page — verify render triggers (or toast if no project, no audio, or render already in progress).
- [ ] Press **Ctrl+S** while the settings panel is open — verify settings save and the browser's native Save dialog does **not** appear.
- [ ] Press **Ctrl+S** with settings panel closed — verify toast: **"Open the Settings panel"**.
- [ ] Press **Escape** while a modal/dialog is open — verify the modal closes.
- [ ] Press **?** — verify the Keyboard Shortcuts help dialog opens.

### 6.2 Help Dialog

- [ ] Verify the help dialog lists all 5 shortcuts with styled key badges.
- [ ] Verify the note at the bottom reads: **"Shortcuts are disabled while typing in text fields (except Esc)."**

### 6.3 Input Guard

- [ ] Focus a text input field (e.g., SegmentTextEditor) and press shortcut keys — verify shortcuts do **not** fire while typing.
- [ ] Press **Escape** while focused in an input field — verify it still works (blurs the active element).

---

## Section 7 — Error Handling and Edge Cases

### 7.1 Navigation Errors

- [ ] Navigate to a non-existent project URL (e.g., `/projects/00000000-0000-0000-0000-000000000000`) — verify a meaningful error message appears: "Project not found" with a **"Back to Dashboard"** link.

### 7.2 Backend Disconnection

- [ ] Stop the Django backend server and attempt to create a project — verify an error toast appears.
- [ ] Stop the backend and attempt to generate audio — verify an error toast appears.
- [ ] Stop the backend and refresh the dashboard — verify the error message about backend connectivity appears.

### 7.3 Input Extremes

- [ ] Create a project with an extremely long title (500+ characters) — verify it does not break the layout (title truncation via `line-clamp-1`).
- [ ] Create a segment with empty narrative text — verify appropriate handling (empty text is allowed but no audio can be generated).
- [ ] Upload an image file that is not a valid image format — verify error handling in the ImageUploader.

### 7.4 ErrorBoundary

- [ ] Verify the ErrorBoundary wraps the application in `layout.tsx`.
- [ ] Trigger a rendering error — verify the fallback page displays: AlertTriangle icon, **"Something went wrong"**, description text, and **"Reload Page"** button.
- [ ] Click **"Show/Hide Details"** — verify the error message and stack trace appear in a `<pre>` block.
- [ ] Click **"Reload Page"** — verify `window.location.reload()` is called.

### 7.5 Concurrent Operations

- [ ] Start a render, then immediately try to start another render — verify the second attempt is blocked with a 409 error and appropriate user feedback.
- [ ] Start bulk audio generation, then try to delete a segment — verify graceful handling.

---

## Section 8 — Visual Polish and UX

### 8.1 Responsive Layout

- [ ] Verify the dashboard looks correct on a **1920×1080** screen (3-column project grid).
- [ ] Verify the dashboard looks correct on a **1366×768** screen (2-column project grid, smaller laptop).
- [ ] Verify the timeline editor looks correct on both screen sizes (sidebar + main content).
- [ ] Verify the dashboard search bar, sort toggle, and buttons are properly aligned at all breakpoints.

### 8.2 Animations and Transitions

- [ ] Verify all hover effects animate smoothly (no snapping or jittering) — check buttons, cards, and interactive elements.
- [ ] Verify SegmentCards pulse with animation during audio generation.
- [ ] Verify the loading skeletons use smooth `animate-pulse` animation.
- [ ] Verify the In Progress status badge pulses with animation.

### 8.3 Toast Notifications

- [ ] Verify toast notifications appear in the **bottom-right** position.
- [ ] Verify toasts auto-dismiss after approximately 4 seconds.
- [ ] Verify the close button (`closeButton` enabled) works on toasts.
- [ ] Verify rich colors are enabled for success (green), error (red), warning (amber), and info (blue) toasts.

### 8.4 Loading States

- [ ] Verify loading skeletons appear on the dashboard during initial project fetch.
- [ ] Verify loading skeletons appear on the timeline editor during project detail fetch (header, sidebar, main content).
- [ ] Verify loading skeletons appear in the GlobalSettings panel during settings fetch.
- [ ] Verify all buttons show appropriate disabled states during asynchronous operations (creating, importing, generating, rendering, uploading).
- [ ] Verify spinners (Loader2 with `animate-spin`) appear on buttons during processing.

### 8.5 Typography and Spacing

- [ ] Verify consistent font usage across all pages (sans-serif body, monospace for code/prompts).
- [ ] Verify consistent spacing between sections, cards, and form elements.
- [ ] Verify consistent color palette usage: primary (blue), destructive (red), success (green), warning (amber), muted (gray).

### 8.6 Accessibility

- [ ] Verify all interactive elements are keyboard-navigable (Tab, Enter, Space, Escape).
- [ ] Verify tooltips appear on hover for icon-only buttons (delete, lock, copy, etc.).
- [ ] Verify AlertDialog and Dialog components trap focus correctly.
- [ ] Verify the image upload drop zone supports keyboard activation (Enter/Space).

### 8.7 Known Limitations

- [ ] **Dark mode** is explicitly out of scope for StoryFlow v1.0. Note this as a known limitation, not a bug.
- [ ] **Drag-and-drop segment reorder** in the UI is not yet implemented. The backend supports it via `/api/projects/{id}/reorder-segments/`, but the frontend does not expose this.
- [ ] **Export button** on the timeline header is currently disabled/placeholder.

---

## Summary

| Section | Items | Status |
|---------|-------|--------|
| 1. Project Management | 21 | ☐ |
| 2. Segment Management | 22 | ☐ |
| 3. Audio Generation | 20 | ☐ |
| 4. Video Rendering | 16 | ☐ |
| 5. GlobalSettings Panel | 22 | ☐ |
| 6. Keyboard Shortcuts | 9 | ☐ |
| 7. Error Handling & Edge Cases | 13 | ☐ |
| 8. Visual Polish & UX | 19 | ☐ |
| **Total** | **142** | ☐ |

---

> **Note:** This checklist is a living document. Additional items may be added as the implementation progresses and new edge cases are discovered. This version represents the initial baseline for StoryFlow v1.0.
>
> **Parent:** [SubPhase_05_03_Overview.md](../document-series/Phase_05_The_Polish/SubPhase_05_03_Final_UI_Polish_Testing/SubPhase_05_03_Overview.md) (Layer 2)  
> **Phase:** [Phase_05_Overview.md](../document-series/Phase_05_The_Polish/Phase_05_Overview.md) (Layer 1)  
> **Master:** [00_Project_Overview.md](../document-series/00_Project_Overview.md) (Layer 0)
