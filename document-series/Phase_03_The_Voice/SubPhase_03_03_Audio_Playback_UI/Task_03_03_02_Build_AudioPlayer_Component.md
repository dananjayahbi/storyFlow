# Task 03.03.02 — Build AudioPlayer Component

> **Sub-Phase:** 03.03 — Audio Playback UI
> **Phase:** Phase 03 — The Voice
> **Complexity:** High
> **Dependencies:** Task 03.03.01 (Shadcn Slider)
> **Parent Document:** [SubPhase_03_03_Overview.md](./SubPhase_03_03_Overview.md)

---

## Objective

Build a compact, inline audio player component that uses the HTML5 `<audio>` element for playback, with custom play/pause, seek bar (Shadcn `Slider`), and time display. This component renders inside each `SegmentCard` when audio exists.

---

## Instructions

### Step 1 — Create the component file

Create `frontend/components/AudioPlayer.tsx`. Define a props interface with `audioUrl` (full URL to the .wav file), `duration` (seconds, from database), and optional `className`.

### Step 2 — Set up the audio element and state

Create a `useRef<HTMLAudioElement>` for the hidden `<audio>` element. Manage local state for `isPlaying` (boolean), `currentTime` (number, seconds), and `isLoaded` (boolean, tracks whether `loadedmetadata` has fired).

### Step 3 — Implement play/pause toggle

Create a `togglePlay` function that calls `audioRef.current.play()` or `audioRef.current.pause()` based on current state. Update `isPlaying` accordingly.

### Step 4 — Wire audio events

Listen to `timeupdate` (update `currentTime` state — fires ~4 times/second during playback), `loadedmetadata` (set `isLoaded` to true), `ended` (reset `isPlaying` to false, optionally reset `currentTime` to 0), and `error` (show error state). Use `useEffect` to attach/detach event listeners and clean up on unmount by pausing the audio and clearing the `src`.

### Step 5 — Implement seek via Slider

Render the Shadcn `Slider` with `value={[currentTime]}`, `max={duration}`, `step={0.1}`. On `onValueChange`, set `audioRef.current.currentTime` to the new value and update the `currentTime` state.

### Step 6 — Display formatted time

Create a `formatTime(seconds)` utility function that converts seconds to `M:SS` format (e.g., 65.7 → "1:05", 5.23 → "0:05"). Display as `currentTime / totalDuration` to the right of the slider.

### Step 7 — Handle loading state

Before `loadedmetadata` fires, show a loading spinner instead of the player controls. This prevents interaction before the audio is ready.

### Step 8 — Handle audio URL changes

Use a `useEffect` that watches `audioUrl` and resets `currentTime` to 0, `isPlaying` to false when the URL changes (e.g., after regeneration). Append a cache-busting query parameter (`?t={timestamp}`) to force the browser to re-fetch after regeneration.

### Step 9 — Layout

Arrange horizontally: play/pause button (left), slider (center, `flex-1`), time display (right). The `<audio>` element is rendered but visually hidden — all controls are custom.

---

## Expected Output

```
frontend/
└── components/
    └── AudioPlayer.tsx         ← CREATED
```

---

## Validation

- [ ] Renders play button, slider, and time display.
- [ ] Clicking play starts audio; clicking pause stops it.
- [ ] Slider reflects current playback position in real-time.
- [ ] Dragging the slider seeks to the new position.
- [ ] Time shows `currentTime / totalDuration` in `M:SS` format.
- [ ] Loading spinner appears while audio metadata loads.
- [ ] Playback resets when audio ends.
- [ ] Audio errors are handled gracefully (not a crash).
- [ ] `<audio>` element is hidden — all controls are custom UI.
- [ ] Component cleans up on unmount (pause, clear src).

---

## Notes

- Use `preload="metadata"` on the `<audio>` element — this loads only the header (duration info), not the full file, until play is pressed.
- Browser autoplay policies require user interaction (click) to start playback. Never attempt to auto-play on mount.
- `audio.duration` is `NaN` until `loadedmetadata` fires. Use the `duration` prop from the database as the initial display value, and update if the actual loaded duration differs.
- For cache busting after regeneration, append `?t=${Date.now()}` to the URL. The audio file path stays the same after regeneration (deterministic naming), so the browser may serve a cached version.

---

> **Parent:** [SubPhase_03_03_Overview.md](./SubPhase_03_03_Overview.md) (Layer 2)
> **Phase:** [Phase_03_Overview.md](../Phase_03_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_03_03_01_Install_New_Shadcn_Components.md](./Task_03_03_01_Install_New_Shadcn_Components.md)
> **Next Task:** [Task_03_03_03_Build_GenerateAudioButton.md](./Task_03_03_03_Build_GenerateAudioButton.md)
