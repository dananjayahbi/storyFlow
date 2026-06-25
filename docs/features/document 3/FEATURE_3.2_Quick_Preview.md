# Feature 3.2 — Quick Preview Player

| Field | Value |
|---|---|
| Feature ID | 3.2 |
| Title | Quick Preview Player |
| Status | 🟡 Planned |
| Priority | High |
| Complexity | Medium–High |
| Estimated Effort | 4–6 days |
| Dependencies | Segments must expose `image_url`, `audio_url`, `duration`, `text_content`, `subtitle_chunks` via API; Feature 3.1 (optional, independent) |
| Output Files (NEW) | `frontend/components/QuickPreviewPlayer.tsx`, `frontend/hooks/usePreviewEngine.ts` |
| Files Modified | `frontend/app/projects/[id]/page.tsx`, `frontend/components/Timeline.tsx` |

---

## 1. Document Overview

### 1.1 Problem Statement

Every time a user wants to check how a project feels in motion — timing, narrative pacing, whether
the audio and images complement each other — they must trigger a full server-side render. That
process involves FFmpeg composition, subtitle baking, and audio mixing on the backend, taking
anywhere from two to five minutes for a five-segment project. This turnaround makes rapid iteration
effectively impossible. Users have no way to quickly sanity-check a change to a segment's text or
audio without committing to a long wait. The problem compounds as projects grow: a twelve-segment
project may take ten or more minutes to render, making experimentation expensive and slow.

### 1.2 Proposed Solution

Introduce a "Quick Preview" button in the project page header that opens a full-screen modal overlay
and plays the project entirely client-side in the browser. The preview approximates the final video
without any server involvement: images are displayed in sequence, audio segments play back-to-back,
Ken Burns motion is approximated with CSS transform transitions, and subtitle text is overlaid in
real time. The experience is not render-quality, but it is accurate enough to verify timing and
narrative flow in seconds.

Key elements of the solution:

- Add a "Quick Preview" button to the project page header, positioned alongside the existing
  "Render" button so it is always visible and one click away.
- Create `QuickPreviewPlayer.tsx` — a modal dialog component that occupies most of the viewport
  and acts as the preview screen.
- Extract the playback sequencing logic into `usePreviewEngine.ts` — a custom React hook — so the
  player component stays focused on presentation and the timing logic is independently testable.
- For each segment in order: display the segment image inside a container that applies a CSS
  `transform: scale()` keyframe animation over the duration of the segment to approximate Ken Burns
  zoom; simultaneously invoke `new Audio(segment.audio_url)` and call `audio.play()`.
- Subtitle text is overlaid at the bottom center of the preview screen as plain text in a
  high-contrast pill, updated in sync with the currently playing segment.
- When a segment's audio ends (`audio.onended`), the preview engine advances to the next segment
  automatically.
- Player controls include Play, Pause, and Restart; a progress bar shows elapsed time relative to
  total estimated duration across all segments.
- Segments with no audio use `segment.duration` as a fallback timer via `setTimeout`.
- Segments with no image show a dark gray placeholder with the segment number centered.
- The modal closes when the user clicks outside it or presses Escape; playback stops on close.
- A non-dismissable notice at the bottom of the modal clearly states this is a browser approximation.

### 1.3 Scope

| # | In Scope | Out of Scope |
|---|---|---|
| 1 | Client-side sequential playback of images and audio with subtitle overlay | Server-side rendering or any FFmpeg call triggered from this feature |
| 2 | CSS-based Ken Burns approximation (scale transition over segment duration) | Accurate Ken Burns replication using canvas or WebGL compositing |
| 3 | Play, Pause, Restart controls and a total-duration progress bar | Per-segment seeking or scrubbing to an arbitrary time position |
| 4 | Graceful fallback for segments missing image or audio | Downloading or exporting the preview as a video file |
| 5 | Subtitle overlay from `text_content` or `subtitle_chunks` | Rendering styled subtitles that match the final burn-in font and position |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| `frontend/app/projects/[id]/page.tsx` | Project detail page; holds segment state array; hosts the Render button | Exists; "Render" button present; no "Quick Preview" button |
| `frontend/components/QuickPreviewPlayer.tsx` | New modal player component; receives segments array as prop | Does not exist; to be created |
| `frontend/hooks/usePreviewEngine.ts` | New custom hook managing playback state, timing, and segment transitions | Does not exist; to be created |
| `frontend/components/Timeline.tsx` | Timeline and segment list; used for context but not modified by this feature | Exists; no changes required |
| `frontend/components/SegmentCard.tsx` | Individual segment editor; data shape informs the preview engine | Exists; read-only reference for segment data structure |
| `backend/api/views.py` | Serves `GET /api/projects/{id}/` with `audio_url`, `image_url`, `duration`, `subtitle_chunks` | Exists; no changes required for this feature |

---

## 2. Flow Diagram

```
User clicks "Quick Preview" in project page header
        │
        ▼
QuickPreviewPlayer modal opens (full-screen overlay)
        │
        ▼
usePreviewEngine initialises with segments array
  - Calculates total duration
  - Sets currentIndex = 0, state = "paused"
        │
User clicks Play
        │
        ▼
Engine starts segment[0]
  ├── Display image → apply CSS scale animation over duration
  ├── Play audio via HTML5 Audio API
  └── Show subtitle text overlay
        │
        ▼
audio.onended fires (or setTimeout if no audio)
        │
        ▼
currentIndex++
        │
        ├──[More segments?]──Yes──► Repeat for segment[N]
        │
        └──[No more segments]
                │
                ▼
        Playback ends → show "Preview complete" state
        Progress bar reaches 100%
                │
        User clicks Restart or closes modal
                │
                ▼
        Audio objects paused and nulled → modal closes
```

---

## 3. Step-by-Step Instructions

### Step 1 — Add the "Quick Preview" button to the project page header

- File: `frontend/app/projects/[id]/page.tsx`
- Function: the header/toolbar JSX section near the existing "Render" button
- Add a new button element with the label "Quick Preview" and a play-circle icon from the existing
  icon library used by the project
- On click, set a local boolean state flag `isPreviewOpen` to true; pass this flag and a close
  handler down to the `QuickPreviewPlayer` component rendered at the bottom of the page JSX tree
- The button should be disabled when the project has zero segments and show a tooltip in that case

### Step 2 — Create the usePreviewEngine custom hook

- File: `frontend/hooks/usePreviewEngine.ts` (new file)
- Function: default export hook accepting a `segments` array and an `isActive` boolean
- Internal state: `currentIndex` (number), `playbackState` ("idle", "playing", "paused", "ended"),
  `elapsedTime` (number in seconds), `totalDuration` (sum of all segment durations or estimates)
- The hook manages a `React.useRef` holding the current `Audio` object so it can be paused and
  cleaned up without stale closures
- Expose: `play`, `pause`, `restart` functions; `currentIndex`; `playbackState`; `elapsedTime`;
  `totalDuration` — return all as a plain object
- On `isActive` becoming false, pause audio and reset state to "idle" to clean up on modal close

### Step 3 — Implement segment advancement logic inside usePreviewEngine

- File: `frontend/hooks/usePreviewEngine.ts`
- Function: `startSegment(index)` — private function inside the hook
- Create a new `Audio` object pointed at `segments[index].audio_url`; store it in the ref
- Attach `audio.onended` to call `startSegment(index + 1)` or set state to "ended" if index is
  the last segment
- If `audio_url` is null or audio loading fails, use `setTimeout` with the segment's `duration`
  field (or a fallback of 3 seconds) instead of relying on `audio.onended`
- Update `elapsedTime` every 250 milliseconds using a `setInterval` ref while playback is active;
  clear the interval when playback pauses or ends

### Step 4 — Create QuickPreviewPlayer.tsx

- File: `frontend/components/QuickPreviewPlayer.tsx` (new file)
- Function: default export functional component accepting `segments`, `isOpen`, and `onClose` props
- Render a fixed-position full-viewport backdrop div with a centered content panel (~85vw × 75vh)
- Inside the panel: an image display area (top ~70%) showing `segments[currentIndex].image_url` with
  a CSS keyframe animation that transitions `transform: scale(1.0)` to `transform: scale(1.08)`
  over the segment duration; a subtitle overlay absolutely positioned at the bottom center of the
  image area; a control bar below the image area with Play/Pause, Restart buttons and a progress bar
- Consume all playback state from `usePreviewEngine`; the component itself contains no timing logic
- On Escape key press (via `useEffect` keydown listener) and on backdrop click, call `onClose`

### Step 5 — Build the subtitle overlay logic

- File: `frontend/components/QuickPreviewPlayer.tsx`
- Function: subtitle display block within the component JSX
- Read `segments[currentIndex].subtitle_chunks` first; if it is a non-empty array, join the chunks
  with a space and display the full text; fall back to `segments[currentIndex].text_content` if
  `subtitle_chunks` is absent or empty
- The overlay is a div absolutely positioned at 90% from the top of the image area, centered
  horizontally, with a semi-transparent dark background pill and white text
- Hide the overlay entirely when both `subtitle_chunks` and `text_content` are absent for the current
  segment to avoid rendering an empty box

### Step 6 — Add the approximation disclaimer and close behaviour

- File: `frontend/components/QuickPreviewPlayer.tsx`
- Function: footer section below the player controls
- Render a small muted-text paragraph: "This is a browser approximation. The final render uses
  server-side compositing and may differ in timing, Ken Burns motion, and subtitle styling."
- Ensure that when `onClose` is called (via button, backdrop click, or Escape), the hook's `pause`
  function is called first, then the Audio object reference is paused and nulled, before the modal
  unmounts — preventing audio from continuing to play after the modal is dismissed
- Add a close button (X icon) in the top-right corner of the modal panel as a third close path

---

## 4. Expected Outcome

1. A "Quick Preview" button appears in the project page header beside the "Render" button.
2. Clicking "Quick Preview" opens a large modal overlay with a dark background and centered player.
3. Pressing Play begins image display and audio playback for the first segment simultaneously.
4. Each subsequent segment's image, audio, and subtitle load automatically when the previous
   audio ends, creating a seamless preview sequence.
5. A slow CSS scale animation on each image approximates the Ken Burns zoom effect from the final
   render without any canvas or video element.
6. The subtitle text for each segment is overlaid at the bottom of the image area in real time.
7. Segments missing an image show a dark placeholder; segments missing audio advance on a timer.
8. The progress bar fills continuously across all segments from start to finish.
9. The modal closes cleanly via the X button, Escape key, or backdrop click, with audio stopping
   immediately.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] `usePreviewEngine` advances `currentIndex` correctly after each `audio.onended` callback.
- [ ] `usePreviewEngine` uses `setTimeout` fallback when a segment has a null `audio_url`.
- [ ] `pause` action stops the Audio object and freezes `elapsedTime` with no further increments.
- [ ] `restart` action resets `currentIndex` to 0 and `elapsedTime` to 0.
- [ ] `totalDuration` is computed correctly as the sum of all segment durations with a 3-second
     default applied to any segment whose `duration` field is null.

### 5.2 Integration / Manual Tests

- [ ] Open a 5-segment project, click Quick Preview, and confirm all five segments play through in
     the correct order with correct images, audio, and subtitle text.
- [ ] With a segment that has no audio URL, confirm the preview waits for the segment's duration
     then advances to the next segment without hanging.
- [ ] With a segment that has no image URL, confirm the dark placeholder renders and no broken image
     element appears.
- [ ] Click Pause mid-segment, wait ten seconds, click Play again, and confirm audio resumes from
     where it left off for that segment.
- [ ] Click Restart and confirm the preview begins again from segment one.
- [ ] Press Escape while the modal is open and confirm audio stops and the modal unmounts.
- [ ] Click "Quick Preview" when a project has zero segments and confirm the button is disabled and
     no modal opens.

### 5.3 Regression Tests

- [ ] The existing "Render" button in the project header continues to trigger the server-side render
     endpoint without any interference from the new Quick Preview button.
- [ ] Navigating away from the project page while the preview modal is open does not leave orphaned
     Audio objects playing in the background.
- [ ] The segments array displayed in the Timeline edit view is not mutated or reordered by the
     preview engine at any point.

---

## 6. Notes for AI Agent

- The `Audio` objects must be created inside the hook and stored in a `useRef`, never in component
  state, to avoid unnecessary re-renders every time the audio position updates.
- The CSS Ken Burns animation should be applied by dynamically setting an `animationDuration` inline
  style equal to the segment's duration in seconds; a fixed CSS keyframe defined in a global
  stylesheet or a CSS module handles the actual scale transform so no JavaScript computes the
  intermediate frames.
- Be careful with `audio.play()` returning a Promise in modern browsers — attach a catch handler to
  that Promise to suppress the `NotAllowedError` that fires if the browser blocks autoplay; log the
  error and fall back to the timer-based advancement in that case.
- The modal must use a `React.createPortal` targeting `document.body` to avoid z-index stacking
  context issues with the existing Timeline and page header layout.
- Do not pass the raw `Audio` DOM object through React props or context — keep it entirely inside
  the `usePreviewEngine` hook and expose only serialisable state values to the component layer.
- The disclaimer text about this being an approximation must always be visible and must not be
  hidden behind the player controls; position it below the control bar in normal document flow.
