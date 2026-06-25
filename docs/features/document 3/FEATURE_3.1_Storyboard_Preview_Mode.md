# Feature 3.1 — Storyboard Preview Mode

| Field | Value |
|---|---|
| Feature ID | 3.1 |
| Title | Storyboard Preview Mode |
| Status | 🟡 Planned |
| Priority | High |
| Complexity | Medium |
| Estimated Effort | 3–5 days |
| Dependencies | Segments must expose `image_url`, `audio_url`, `duration`, `text_content` via API |
| Output Files (NEW) | `frontend/components/StoryboardView.tsx` |
| Files Modified | `frontend/components/Timeline.tsx`, `frontend/app/projects/[id]/page.tsx`, `frontend/store/` (view mode state) |

---

## 1. Document Overview

### 1.1 Problem Statement

The current project editor uses a vertical list layout where each segment occupies its own card.
When a project has many segments, understanding the full narrative arc requires significant scrolling
and mental effort to piece together the flow. There is no way to visually compare segment images side
by side, assess whether audio durations feel balanced, or spot a missing image without individually
opening each card. The editor was designed for fine-grained editing, not for bird's-eye review,
and users are forced to hold the entire composition in their heads while making changes.

### 1.2 Proposed Solution

Introduce a "Storyboard" view toggle in the Timeline header that replaces the vertical edit list
with a horizontally scrolling filmstrip of compact storyboard cards. Each card summarises a single
segment at a glance without exposing editing controls. The toggle persists across page refreshes
so users do not have to switch views every time they return to a project.

Key elements of the solution:

- Add a two-state toggle button ("Edit" / "Storyboard") to the Timeline header toolbar area.
- Create a new `StoryboardView` component that renders a horizontally scrollable row of cards.
- Each storyboard card is a fixed-width (~180px) and fixed-height (~250px) tile.
- The top half of each card displays the segment image thumbnail using `segment.image_url`, or a
  neutral placeholder icon when no image has been assigned to the segment yet.
- A duration label (e.g., "3.2s") is displayed below the image, derived from `segment.duration`;
  if duration is null, a calculated estimate from text length is shown instead.
- A mini audio waveform strip occupies the lower portion of the card, drawn on a small canvas
  element using the Web Audio API `AnalyserNode` after decoding the segment audio URL; when no
  audio has been generated, a static placeholder bar renders in its place.
- A subtitle snippet shows the first 30 characters of `text_content` with an ellipsis truncation.
- A segment number badge is pinned to the top-left corner of each card.
- Clicking any card in Storyboard view switches the layout back to Edit view, scrolled to that card.
- The active view mode (edit vs. storyboard) is persisted to `localStorage` under a project-scoped key.

### 1.3 Scope

| # | In Scope | Out of Scope |
|---|---|---|
| 1 | Rendering storyboard cards for all segments in a read-only horizontal strip | Inline editing of any segment field from within the Storyboard view |
| 2 | Image thumbnail display with placeholder fallback | Uploading or replacing segment images from the storyboard |
| 3 | Static or live waveform strip per card using Web Audio API | Full interactive audio scrubbing or playback from storyboard cards |
| 4 | Duration label and subtitle snippet per card | Re-ordering segments by dragging in storyboard mode |
| 5 | View mode toggle with localStorage persistence | Synchronising storyboard scroll position with edit list scroll position in real time |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| `frontend/components/Timeline.tsx` | Renders the list of all SegmentCards; contains the header toolbar | Exists; header toolbar area is present but has no view toggle |
| `frontend/components/SegmentCard.tsx` | Full editing card for one segment | Exists; used exclusively in edit view |
| `frontend/components/StoryboardView.tsx` | New horizontally scrolling filmstrip component | Does not exist; to be created |
| `frontend/app/projects/[id]/page.tsx` | Project detail page; holds the segment state array | Exists; passes segments array down to Timeline |
| `frontend/store/` | Zustand stores for project and UI state | Exists; no view mode slice yet |
| `frontend/components/ImageUploader.tsx` | Handles image preview and upload interaction | Exists; not directly modified but thumbnail logic mirrors its preview URL usage |
| `backend/api/views.py` | Provides `GET /api/projects/{id}/` with image_url, audio_url, duration | Exists; no changes required for this feature |

---

## 2. Flow Diagram

```
User opens project page
        │
        ▼
Timeline.tsx renders header toolbar
        │
        ├──[Edit mode]──────────────────────────────────────┐
        │                                                    │
        ▼                                                    ▼
SegmentCard list (vertical)              StoryboardView.tsx (horizontal strip)
  - Full editing controls                  - Fixed-width cards, read-only
  - Image uploader                         - Image thumbnail or placeholder
  - Audio player                           - Duration label
  - Voice controls                         - Waveform canvas strip
                                           - Subtitle snippet (30 chars)
                                           - Segment number badge
                                                    │
                                           User clicks a card
                                                    │
                                                    ▼
                                          Switch to Edit mode
                                          Scroll to that segment
                                                    │
                                                    ▼
                                          localStorage updated
                                          ("storyboard" → "edit")
```

---

## 3. Step-by-Step Instructions

### Step 1 — Add view mode state to the Zustand store

- File: `frontend/store/` (create or extend a UI store slice)
- Function: new `viewMode` field with values `"edit"` or `"storyboard"`
- Add a `setViewMode` action that writes the new value and syncs it to `localStorage`
- On store initialisation, read the persisted value from `localStorage` under the key
  `storyflow_view_mode_{projectId}` and default to `"edit"` if not found
- No API calls needed; this is purely client-side UI state

### Step 2 — Add the toggle button to Timeline.tsx

- File: `frontend/components/Timeline.tsx`
- Function: the header toolbar JSX block at the top of the component
- Import `viewMode` and `setViewMode` from the UI store
- Render a button group with two options: "Edit" and "Storyboard"; apply an active style to
  whichever is currently selected
- When the user clicks "Storyboard", call `setViewMode("storyboard")`; when they click "Edit",
  call `setViewMode("edit")`
- Conditionally render either the existing SegmentCard list or the new `StoryboardView` component
  based on the current `viewMode` value

### Step 3 — Create StoryboardView.tsx

- File: `frontend/components/StoryboardView.tsx` (new file)
- Function: default export functional component accepting a `segments` prop (array of segment objects)
- Render an outer container with `overflow-x: auto`, `display: flex`, `flex-direction: row`,
  fixed height of 250px, and horizontal padding
- For each segment, render a card div fixed at 180px width containing: image or placeholder on top,
  duration label centered below image, canvas element for waveform strip, subtitle snippet text
- Attach an `onClick` handler to each card that calls `setViewMode("edit")` and then scrolls the
  matching SegmentCard into view using a segment ID ref lookup

### Step 4 — Implement the waveform canvas drawing

- File: `frontend/components/StoryboardView.tsx`
- Function: a `useEffect` hook inside each storyboard card (or a child component `WaveformStrip`)
- After mount, fetch the segment's `audio_url` with the Fetch API and decode the array buffer using
  `AudioContext.decodeAudioData`; extract the channel data Float32Array and downsample it to 60
  data points by averaging; draw the amplitude bars on the canvas with a loop
- Guard against missing or failed audio: if `audio_url` is null or the fetch fails, render a flat
  static bar using a single horizontal rectangle fill instead
- Clean up the AudioContext in the `useEffect` return to prevent memory leaks

### Step 5 — Wire segment click navigation back to Edit view

- File: `frontend/app/projects/[id]/page.tsx`
- Function: segment ref registration — attach a `React.useRef` map keyed by segment ID to each
  rendered SegmentCard so that the storyboard click handler can call `.scrollIntoView`
- Export a `scrollToSegment(segmentId)` helper function via context or prop drilling down to
  `StoryboardView` so clicking a card in storyboard mode triggers the scroll in edit mode
- Switching view mode and scrolling should happen in sequence with a small timeout (one animation
  frame) to allow the edit list to mount before the scroll fires

### Step 6 — Add optional segment status mini-map

- File: `frontend/components/StoryboardView.tsx` (bottom section of the component)
- Function: a secondary strip rendered below the main card row
- Render one small colored square per segment: green if the segment has both an image and audio,
  yellow if it has one of the two, and red if it has neither
- Add a tooltip on hover that shows "Segment N — image: yes/no, audio: yes/no"
- This sub-strip is positioned at the bottom of the StoryboardView container and does not scroll
  independently; it reacts to the same segments array

---

## 4. Expected Outcome

1. A "Storyboard" button appears in the Timeline header toolbar alongside the existing edit controls.
2. Clicking "Storyboard" replaces the vertical segment list with a horizontal filmstrip of compact cards.
3. Every segment is represented by a 180×250px card showing image thumbnail, duration, waveform, and
   subtitle snippet.
4. Segments without an assigned image display a neutral placeholder icon instead of a broken image.
5. Segments without generated audio display a flat static bar in place of a live waveform strip.
6. Clicking any storyboard card switches back to Edit view and scrolls that segment into the viewport.
7. The selected view mode ("edit" or "storyboard") survives a full page refresh via localStorage.
8. A color-coded mini-map at the bottom of the storyboard indicates which segments are complete,
   partial, or empty at a glance.
9. No regressions in the existing Edit view — all SegmentCard editing functionality remains intact.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] `StoryboardView` renders the correct number of cards for a given segments array.
- [ ] Cards with `image_url: null` render the placeholder element and not a broken img tag.
- [ ] Cards with `audio_url: null` render the static bar and do not attempt to fetch audio.
- [ ] Duration label displays "N/A" or a computed estimate when `segment.duration` is null.
- [ ] `viewMode` Zustand action correctly updates state and writes to localStorage mock.

### 5.2 Integration / Manual Tests

- [ ] Toggle between Edit and Storyboard views multiple times without layout breakage or React errors.
- [ ] Refresh the page in storyboard mode and confirm the view loads directly in storyboard layout.
- [ ] With a project of 10+ segments, confirm horizontal scroll works across the full card strip.
- [ ] Click each storyboard card and confirm the Edit view scrolls to the corresponding segment.
- [ ] Load a segment whose audio URL returns a 404 and confirm the waveform degrades gracefully to
     the static bar.
- [ ] Confirm the mini-map color codes update immediately after an image or audio is added in Edit view
     and the user switches back to Storyboard view.
- [ ] Test on a mobile-width viewport (375px) to ensure the storyboard strip does not break layout.

### 5.3 Regression Tests

- [ ] All existing SegmentCard edit interactions (image upload, voice selection, text edit) remain
     fully functional after this feature is merged.
- [ ] The Timeline header toolbar renders correctly on projects with zero segments.
- [ ] Switching to Storyboard view does not cause duplicate API calls to the project detail endpoint.

---

## 6. Notes for AI Agent

- The waveform canvas drawing must run inside a `useEffect` with the `audio_url` as a dependency;
  avoid running it at render time as `AudioContext` creation must be triggered by user gesture or
  deferred until the component is mounted and visible.
- Do not use any third-party waveform libraries; the requirement is a lightweight canvas draw loop
  using only the Web Audio API already available in the browser.
- The storyboard card click handler must handle the asynchronous gap between calling `setViewMode`
  and the SegmentCard DOM nodes becoming available; use `requestAnimationFrame` or a `setTimeout`
  of zero milliseconds before calling `scrollIntoView`.
- All new UI text labels ("Storyboard", "Edit", "This is a read-only view") must be plain string
  literals so they are straightforward to internationalise later.
- The `localStorage` key must include the project ID to avoid collisions when users have multiple
  projects open in separate tabs.
- Keep `StoryboardView.tsx` as a purely presentational component that receives its data entirely
  via props; do not fetch data from inside it so it remains independently testable.
