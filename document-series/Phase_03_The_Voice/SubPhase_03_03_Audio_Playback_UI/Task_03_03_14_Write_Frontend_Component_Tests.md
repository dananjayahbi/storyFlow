# Task 03.03.14 — Write Frontend Component Tests

> **Sub-Phase:** 03.03 — Audio Playback UI
> **Phase:** Phase 03 — The Voice
> **Complexity:** High
> **Dependencies:** All Tasks 03.03.01–03.03.13
> **Parent Document:** [SubPhase_03_03_Overview.md](./SubPhase_03_03_Overview.md)

---

## Objective

Write comprehensive frontend tests for all audio playback UI components and Zustand audio state actions to ensure correct behavior, state transitions, and integration.

---

## Instructions

### Step 1 — Set up audio test utilities

Create a test setup file or utility module that provides common test helpers: a mock `HTMLAudioElement` (since JSDOM does not implement the HTML5 Audio API), mock functions for `lib/api.ts` audio endpoints, and a helper to render components with a pre-configured Zustand store state.

### Step 2 — Write AudioPlayer tests

Create a test file for `AudioPlayer.tsx`. Cover the following scenarios:
- Renders play button, slider, and time display with the provided audio source.
- Clicking the play button calls `audio.play()` and toggles the icon to pause.
- Clicking the pause button calls `audio.pause()` and toggles back to play.
- Slider value updates when the audio `timeupdate` event fires.
- Dragging the slider updates `audio.currentTime`.
- The `formatTime` utility correctly converts seconds to "M:SS" format (test edge cases: 0, 59, 60, 600, NaN).
- Shows a loading spinner while audio is loading (before `canplay` event).
- Handles audio error events gracefully.

### Step 3 — Write GenerateAudioButton tests

Create a test file for `GenerateAudioButton.tsx`. Cover the following scenarios:
- Renders "Generate Audio" button with microphone icon when idle and unlocked.
- Renders disabled button with lock icon when locked.
- Renders spinner with "Generating..." when generating.
- Renders error message and "Retry" button when failed.
- Clicking the idle button calls the `onGenerate` callback.
- Clicking "Retry" calls the `onGenerate` callback.
- Locked button does not respond to clicks.
- Generating button does not respond to clicks.

### Step 4 — Write AudioStatusBadge tests

Create a test file for `AudioStatusBadge.tsx`. Cover the following scenarios:
- Renders gray "No Audio" badge when no audio file and status is idle.
- Renders amber "Generating" badge when status is generating.
- Renders green badge with formatted duration when audio file exists and status is completed.
- Renders red "Failed" badge when status is failed.

### Step 5 — Write SegmentCard audio integration tests

Create or extend the test file for `SegmentCard.tsx` to cover audio integration. Cover the following scenarios:
- The "Coming in Phase 03" placeholder is no longer rendered.
- AudioPlayer renders when `audio_file` exists and status is not generating.
- GenerateAudioButton renders when no `audio_file` exists.
- Pulsing amber border class is applied during generation.
- "Regenerate Audio" appears in the dropdown menu only when audio_file exists.
- Stale warning appears after text is edited on a segment with existing audio.

### Step 6 — Write Zustand audio action tests

Create a test file for the audio-related actions in `stores.ts`. Cover the following scenarios:
- `generateAudio(segmentId)` sets the segment status to "generating" and calls the API.
- `generateAllAudio()` initializes bulkGenerationProgress and calls the API.
- `cancelGeneration()` stops polling and resets generating segments to idle.
- `refreshSegmentAudio(segmentId)` fetches updated segment data and replaces it in the segments array.
- `setSegmentAudioStatus()` updates the correct segment's status in the map.
- `clearBulkProgress()` resets `bulkGenerationProgress` to null.
- `staleAudioSegments` Set is populated on text edit and cleared on regeneration.

### Step 7 — Mock external dependencies

Ensure all tests mock `lib/api.ts` functions rather than making actual HTTP requests. Mock `HTMLAudioElement` with a minimal implementation that supports `play()`, `pause()`, `currentTime`, `duration`, and event listeners for `timeupdate`, `canplay`, `ended`, and `error`. Mock `setInterval` and `clearInterval` for polling tests.

---

## Expected Output

```
frontend/
└── __tests__/
    ├── AudioPlayer.test.tsx ← CREATED
    ├── GenerateAudioButton.test.tsx ← CREATED
    ├── AudioStatusBadge.test.tsx ← CREATED
    ├── SegmentCard.audio.test.tsx ← CREATED
    └── stores.audio.test.ts ← CREATED
```

---

## Validation

- [ ] AudioPlayer tests cover render, play/pause, slider, formatTime, loading, and error states.
- [ ] GenerateAudioButton tests cover all four visual states and click handlers.
- [ ] AudioStatusBadge tests cover all four badge variants.
- [ ] SegmentCard tests confirm placeholder removal, conditional rendering, pulsing border, regenerate menu, and stale warning.
- [ ] Zustand store tests cover all audio actions and state transitions.
- [ ] All tests mock API calls and HTMLAudioElement appropriately.
- [ ] All tests pass with zero failures.
- [ ] No TypeScript errors in test files.

---

## Notes

- The HTMLAudioElement mock is the most critical test utility. JSDOM does not implement the Web Audio API, so a custom mock class is necessary. The mock should support adding and removing event listeners, and test code should be able to programmatically fire events (e.g., `timeupdate`, `ended`, `error`) to simulate audio playback behavior.
- For Zustand store tests, create a fresh store instance for each test to avoid state leakage between test cases. Use Zustand's `create` function directly in tests rather than importing the singleton store.
- Polling tests should use Jest's fake timers (`jest.useFakeTimers()`) to control `setInterval` and `setTimeout` without introducing real delays. Advance timers with `jest.advanceTimersByTime()` to simulate polling cycles.
- The test file organization places tests in a `__tests__` directory. If the project already uses a different convention (e.g., colocated `.test.tsx` files next to components), follow the established convention instead.

---

> **Parent:** [SubPhase_03_03_Overview.md](./SubPhase_03_03_Overview.md) (Layer 2)
> **Phase:** [Phase_03_Overview.md](../Phase_03_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_03_03_13_Responsive_Audio_Layout.md](./Task_03_03_13_Responsive_Audio_Layout.md)
> **Next Task:** Phase 04 Sub-Phase Documents
