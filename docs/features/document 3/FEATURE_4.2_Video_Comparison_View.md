# Feature 4.2 — Video Comparison View

| Field | Value |
|---|---|
| Feature ID | 4.2 |
| Title | Video Comparison View |
| Status | 🟡 Planned |
| Priority | Medium |
| Complexity | Medium |
| Estimated Effort | 2–3 days |
| Dependencies | Feature 4.3 (Render History) — requires at least two stored render versions for the same project |
| Output Files (NEW) | `frontend/components/VideoComparisonView.tsx`, `frontend/hooks/useVideoSync.ts` |
| Files Modified | `frontend/app/projects/[id]/page.tsx`, `frontend/store/projectStore.ts`, `frontend/types/project.ts`, `frontend/components/ui/` (ShadCN dialog if not already present) |

---

## 1. Document Overview

### 1.1 Problem Statement

When a creator renders the same project script more than once — changing the TTS voice, adjusting subtitle font color, or modifying Ken Burns intensity between runs — there is currently no mechanism to evaluate the two outputs side by side. The only options are to open the project page twice in separate browser tabs and manually switch between them, or to download both MP4 files and open them in an external video player. Neither approach is fast or practical. Without a direct comparison tool, fine-tuning render parameters becomes guesswork rather than an informed A/B evaluation, slowing creative iteration significantly.

### 1.2 Proposed Solution

Introduce a dedicated Comparison View as a full-screen modal that displays two video players side by side, each playing a different render version of the same project, with optional synchronized playback controls.

- The feature is accessed from the project detail page via a "Compare Renders" button that becomes visible only when two or more render history entries exist for the project — this button is inactive or hidden until the Render History feature (4.3) is in place.
- Create a new component `VideoComparisonView.tsx` built on the ShadCN Dialog primitive, rendering the modal at full viewport width with two `<video>` elements laid out in a horizontal flex row, each taking approximately 48% of the available width with a small gap between them.
- Each video player is self-contained with its own native browser controls as a baseline, but the modal also exposes unified sync controls above the two players.
- The "Sync Play/Pause" toggle, when turned on, binds a single Play/Pause button that calls the HTML video element's `.play()` and `.pause()` methods on both players simultaneously, removing individual play buttons to avoid confusion.
- The "Sync Scrub" toggle, when active, listens to the `timeupdate` event on Video A and sets `videoB.currentTime` to match, so dragging the scrubber on the left player scrubs the right player to the same position.
- Version labels appear above each player showing the render timestamp (formatted as a human-readable date and time), the render number, and a settings diff section that highlights only the fields that differ between the two chosen render snapshots — for example, "Voice: af_sky → af_bella" or "Font color: white → yellow".
- Selection of the two versions to compare is handled by a two-step picker in the modal header: two dropdowns (or a two-slot selector) each populated with the available render history items for the project.

### 1.3 Scope

| Category | Item |
|---|---|
| In Scope | Full-screen modal with two `<video>` elements side by side |
| In Scope | Sync Play/Pause toggle binding both video elements to one control |
| In Scope | Sync Scrub toggle via `timeupdate` event listener |
| In Scope | Settings diff label showing only keys that differ between the two render snapshots |
| Out of Scope | Frame-accurate sync using WebRTC or SharedArrayBuffer |
| Out of Scope | Comparing videos from two different projects |
| Out of Scope | Exporting or merging the two comparison videos |
| Out of Scope | Mobile or touch-optimized layout for the comparison modal |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| `frontend/app/projects/[id]/page.tsx` | Project detail page — renders project info, segments, render controls | Present; has no render history section or Compare button |
| `frontend/types/project.ts` | TypeScript interfaces for project and related data | Has `Project` interface; no `RenderHistoryItem` type yet |
| `frontend/store/projectStore.ts` | Zustand store for project detail state | Manages selected project data; no render history slice |
| `frontend/components/ProjectCard.tsx` | Gallery card component, not directly involved | Not modified by this feature |
| `backend/api/views.py` | Django REST views providing project and segment data | Has project detail view; render history endpoint added by Feature 4.3 |

---

## 2. Flow Diagram

```
Project Detail Page
         |
         v
  [Render History loaded? >= 2 items]
         |
    -----+------
    |           |
  [Yes]        [No]
    |           |
    v           v
["Compare    [Button hidden
 Renders"     or disabled]
  button]
    |
    v
[User clicks "Compare Renders"]
    |
    v
[VideoComparisonView modal opens]
    |
    v
[Version picker: select Version A + Version B]
    |
    v
[Both <video> elements load their src URLs]
    |
    v
[Labels rendered: timestamp + settings diff]
    |
         +-----------------+
         |                 |
  [Sync disabled]   [Sync enabled]
         |                 |
         v                 v
  [Each player      [Single Play/Pause
   independent]      controls both]
                          |
                          v
                 [Sync Scrub on?]
                    |         |
                  [Yes]      [No]
                    |         |
                    v         v
             [timeupdate   [Scrubbers
              syncs B       independent]
              to A time]
```

---

## 3. Step-by-Step Instructions

### Step 1 — Add `RenderHistoryItem` type and store slice
- File: `frontend/types/project.ts`
- Add a `RenderHistoryItem` interface with `id`, `renderNumber`, `createdAt`, `fileSizeBytes`, `durationSeconds`, `outputFileUrl`, and `renderSettingsSnapshot` (typed as `Record<string, unknown>`).
- File: `frontend/store/projectStore.ts`
- Add a `renderHistory` array of `RenderHistoryItem` to the store's state shape and a `setRenderHistory` action.
- The fetch of render history should be triggered inside the project detail page's `useEffect` that already loads the project, calling the `GET /api/projects/{id}/render-history/` endpoint added by Feature 4.3.

### Step 2 — Create the `useVideoSync` hook
- File: `frontend/hooks/useVideoSync.ts` (new file)
- This hook accepts two React refs pointing to the two `HTMLVideoElement` nodes plus two boolean flags: `syncPlayPause` and `syncScrub`.
- When `syncPlayPause` is true, the hook exposes a unified `handlePlayPause` function that reads the current paused state of Video A and calls `.play()` or `.pause()` on both refs.
- When `syncScrub` is true, the hook attaches a `timeupdate` listener to Video A's element that sets `videoB.currentTime = videoA.currentTime`, and returns a cleanup function to remove the listener when the flag is toggled off or the modal unmounts.
- Keep the hook free of any UI logic; it is purely a DOM synchronization utility.

### Step 3 — Build `VideoComparisonView.tsx`
- File: `frontend/components/VideoComparisonView.tsx` (new file)
- Use the ShadCN `Dialog` and `DialogContent` components as the modal wrapper with `max-w-[98vw]` and a dark background to match the app theme.
- Render two version-picker dropdowns at the top of the modal body, each populated from the `renderHistory` array; default Version A to the most recent item and Version B to the second most recent.
- Below the pickers, render the sync toggles using ShadCN `Switch` components labeled "Sync Play/Pause" and "Sync Scrub".
- In the main body, use a flex row with two equally-sized columns; in each column render a version label (timestamp, render number, settings diff computed inline) and a `<video>` element with `controls`, `loop`, and `className="w-full rounded-lg"`.
- Wire the two `videoRef` refs and the two sync boolean states into `useVideoSync`.

### Step 4 — Add settings diff computation utility
- File: `frontend/lib/renderDiff.ts` (new file, small utility)
- Write a plain function `computeSettingsDiff` that accepts two `Record<string, unknown>` objects (the render settings snapshots) and returns an array of diff entries, each with `key`, `valueA`, and `valueB`, containing only keys whose values differ between the two snapshots.
- Use this function inside `VideoComparisonView.tsx` when computing the label text for each player; display each diff entry as "Key: valueA → valueB".
- This function requires no external dependencies — plain loop over `Object.keys`.

### Step 5 — Wire the Compare button into the project detail page
- File: `frontend/app/projects/[id]/page.tsx`
- Import `VideoComparisonView` and add a `compareOpen` boolean state variable.
- In the render history section (added by Feature 4.3), conditionally render a "Compare Renders" button when `renderHistory.length >= 2`.
- Clicking the button sets `compareOpen` to true, which opens the `VideoComparisonView` dialog.
- Pass `renderHistory`, `compareOpen`, and `onClose` (sets `compareOpen` to false) as props to `VideoComparisonView`.

---

## 4. Expected Outcome

1. The "Compare Renders" button is visible on the project detail page only when at least two render history items exist, and is absent or visually disabled otherwise.
2. Clicking "Compare Renders" opens a full-screen dark modal containing two video players side by side with their respective version labels.
3. With "Sync Play/Pause" enabled, pressing the unified Play button starts both videos simultaneously from their current positions; pressing Pause halts both.
4. With "Sync Scrub" enabled, dragging the scrubber bar on Video A causes Video B to jump to the same playback position within approximately one `timeupdate` tick (roughly 250ms precision).
5. The settings diff label above each player shows only the fields that differ between the two selected render snapshots — identical fields are omitted to keep the label concise.
6. Each version picker dropdown can be changed independently, allowing the creator to swap in any combination of available render history entries without closing the modal.
7. Closing the modal returns the user to the project detail page with no state changes to the project or its render history.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] Test `computeSettingsDiff` returns only keys with differing values and omits matching keys
- [ ] Test `computeSettingsDiff` returns an empty array when both snapshots are identical
- [ ] Test `useVideoSync` calls `.play()` on both video element mocks when `handlePlayPause` is invoked and Video A is paused
- [ ] Test `useVideoSync` attaches a `timeupdate` listener when `syncScrub` is true and removes it when the flag becomes false
- [ ] Test that `VideoComparisonView` renders two `<video>` elements when provided two valid `RenderHistoryItem` objects

### 5.2 Integration / Manual Tests

- [ ] Navigate to a project with two or more render history entries and confirm the "Compare Renders" button is visible
- [ ] Open the comparison modal and verify both videos load and display their thumbnails/first frames in the player areas
- [ ] Enable "Sync Play/Pause", click Play, and confirm both videos begin playing at the same moment
- [ ] Enable "Sync Scrub", drag the left video scrubber, and visually confirm the right video jumps to the same position
- [ ] Change the Version B dropdown to a different render entry and confirm the right video reloads to the new source
- [ ] Confirm the settings diff label correctly shows "Voice: af_sky → af_bella" when those are the only differing fields

### 5.3 Regression Tests

- [ ] Project detail page renders without errors for projects that have zero render history entries (Compare button absent, no modal triggered)
- [ ] Existing project detail page behavior — segment list, render settings panel, render button — is unchanged
- [ ] The Zustand store's existing project fields are unaffected by the addition of the `renderHistory` slice

---

## 6. Notes for AI Agent

- The `timeupdate` sync approach is intentionally imprecise (browser fires the event roughly every 250ms) — do not attempt frame-accurate sync via `requestAnimationFrame` unless the user explicitly requests it, as it significantly raises complexity.
- Always null-check both video refs before calling `.play()`, `.pause()`, or setting `.currentTime` — React may render the `<video>` elements conditionally and the refs can be null during initial mount or when the source changes.
- The `computeSettingsDiff` function should do a shallow comparison of the top-level keys of the snapshot objects; deep diffing nested render settings is out of scope for the label display.
- The version picker dropdowns must prevent the same render history item from being selected in both slots simultaneously — add a simple guard that swaps the selections rather than allowing a duplicate match.
- This feature has a hard dependency on Feature 4.3: without the `RenderHistory` model and the `GET /api/projects/{id}/render-history/` endpoint, the comparison modal has no data source and cannot function. Implement 4.3 first.
