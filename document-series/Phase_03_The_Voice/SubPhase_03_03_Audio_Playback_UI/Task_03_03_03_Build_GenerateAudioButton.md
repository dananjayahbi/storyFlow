# Task 03.03.03 — Build GenerateAudioButton Component

> **Sub-Phase:** 03.03 — Audio Playback UI
> **Phase:** Phase 03 — The Voice
> **Complexity:** Medium
> **Dependencies:** Task 03.03.01 (Shadcn Components)
> **Parent Document:** [SubPhase_03_03_Overview.md](./SubPhase_03_03_Overview.md)

---

## Objective

Build a per-segment "Generate Audio" button that handles four visual states: idle, locked, generating, and failed — with retry support.

---

## Instructions

### Step 1 — Create the component file

Create `frontend/components/GenerateAudioButton.tsx`. Define a props interface with `segmentId` (string), `isLocked` (boolean), `generationStatus` (AudioGenerationState from the Zustand store), `onGenerate` (callback), and optional `className`.

### Step 2 — Implement the idle state

When `status === "idle"` and `isLocked === false`, render a Shadcn `Button` with a microphone icon and "Generate Audio" label. On click, call the `onGenerate` callback.

### Step 3 — Implement the locked state

When `isLocked === true`, render a disabled button with a lock icon and "Generate Audio" label. Add a tooltip explaining: "Unlock segment to generate audio."

### Step 4 — Implement the generating state

When `status === "generating"`, render a disabled button with a spinning `Loader2` icon and "Generating..." label. This provides visual feedback while the background task runs.

### Step 5 — Implement the failed state

When `status === "failed"`, render an error message from `generationStatus.error` styled in red, along with a "Retry" button. The retry button calls the same `onGenerate` callback, which resets the state and re-triggers generation.

---

## Expected Output

```
frontend/
└── components/
    └── GenerateAudioButton.tsx ← CREATED
```

---

## Validation

- [ ] Shows "Generate Audio" button with microphone icon when idle and unlocked.
- [ ] Shows disabled button with lock icon and tooltip when locked.
- [ ] Shows spinner with "Generating..." when generating.
- [ ] Shows error message and "Retry" button when failed.
- [ ] Click calls `onGenerate` callback.
- [ ] "Retry" re-triggers `onGenerate`.
- [ ] Component disappears when audio is generated (parent shows AudioPlayer instead).

---

## Notes

- This component does NOT call the API directly. The `onGenerate` callback is provided by the parent `SegmentCard`, which calls the Zustand store action `generateAudio(segmentId)`.
- After successful generation, this component is no longer rendered — the parent conditionally renders `AudioPlayer` instead. The component itself does not handle the "completed" state.
- Use Lucide React icons: `Mic` for microphone, `Lock` for lock, `Loader2` for spinner, `RefreshCw` for retry.

---

> **Parent:** [SubPhase_03_03_Overview.md](./SubPhase_03_03_Overview.md) (Layer 2)
> **Phase:** [Phase_03_Overview.md](../Phase_03_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_03_03_02_Build_AudioPlayer_Component.md](./Task_03_03_02_Build_AudioPlayer_Component.md)
> **Next Task:** [Task_03_03_04_Build_AudioStatusBadge.md](./Task_03_03_04_Build_AudioStatusBadge.md)
