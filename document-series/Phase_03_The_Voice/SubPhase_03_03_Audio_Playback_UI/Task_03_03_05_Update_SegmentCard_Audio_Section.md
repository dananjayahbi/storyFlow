# Task 03.03.05 — Update SegmentCard Audio Section

> **Sub-Phase:** 03.03 — Audio Playback UI
> **Phase:** Phase 03 — The Voice
> **Complexity:** High
> **Dependencies:** Task 03.03.02 (AudioPlayer), Task 03.03.03 (GenerateAudioButton), Task 03.03.04 (AudioStatusBadge), Task 03.03.08 (Zustand Audio State)
> **Parent Document:** [SubPhase_03_03_Overview.md](./SubPhase_03_03_Overview.md)

---

## Objective

Replace the "Coming in Phase 03" placeholder in the SegmentCard component with a fully functional audio section that conditionally renders AudioPlayer, GenerateAudioButton, and AudioStatusBadge based on the segment's audio state.

---

## Instructions

### Step 1 — Import new audio components

Open `frontend/components/SegmentCard.tsx`. Import `AudioPlayer`, `GenerateAudioButton`, and `AudioStatusBadge` from their respective component files.

### Step 2 — Read audio generation status from the Zustand store

Use the Zustand store to read the `audioGenerationStatus` for the current segment. Use a Zustand selector that subscribes only to the specific segment's status entry to avoid unnecessary re-renders of unrelated cards.

### Step 3 — Add AudioStatusBadge to the card header

Insert the `AudioStatusBadge` component into the SegmentCard header row, alongside the existing segment number and any controls. Pass the segment's `audio_file`, `audio_duration`, and `generationStatus` as props.

### Step 4 — Remove the Phase 03 placeholder

Locate the "Coming in Phase 03" placeholder section (added during Phase 02) and remove it entirely. This placeholder was a deliberate deferred marker that this task resolves.

### Step 5 — Add conditional audio section

In the area previously occupied by the placeholder, implement the following conditional logic:
- If `audio_file` exists AND the segment is not currently generating, render the `AudioPlayer` component with the audio file URL and duration.
- Otherwise, render the `GenerateAudioButton` component with the segment ID, lock status, generation status, and an `onGenerate` callback wired to the Zustand store's `generateAudio(segmentId)` action.

### Step 6 — Add pulsing animation during generation

When the segment's audio generation status is "generating," apply a subtle pulsing amber border animation to the SegmentCard. Use Tailwind's `animate-pulse` utility combined with an amber border color class. This gives the user an immediate visual cue that work is happening on this segment.

### Step 7 — Handle the transition between states

Ensure smooth visual transitions as the segment moves through states:
- Idle with no audio → GenerateAudioButton visible.
- Generating → GenerateAudioButton disabled with spinner, pulsing border on card.
- Completed → AudioPlayer appears, pulsing border removed, badge turns green.
- Failed → GenerateAudioButton shows error and retry, badge turns red.

---

## Expected Output

```
frontend/
└── components/
    └── SegmentCard.tsx ← MODIFIED
```

---

## Validation

- [ ] "Coming in Phase 03" placeholder is completely removed.
- [ ] AudioStatusBadge displays in the card header with correct variant.
- [ ] AudioPlayer renders when audio_file exists and segment is not generating.
- [ ] GenerateAudioButton renders when no audio_file or segment has not generated yet.
- [ ] Clicking "Generate Audio" triggers Zustand store action.
- [ ] Pulsing amber border animates during generation.
- [ ] State transitions (idle → generating → completed/failed) render correctly.
- [ ] Only the affected SegmentCard re-renders (Zustand selector optimization).
- [ ] No TypeScript errors.

---

## Notes

- This is the central integration task for the audio playback UI. It ties together three new components (AudioPlayer, GenerateAudioButton, AudioStatusBadge) with the Zustand store and the existing SegmentCard layout.
- The audio file URL is constructed from the Django media path, which is the segment's `audio_file` field value. Ensure the URL includes a cache-busting query parameter (e.g., appending a timestamp) to prevent stale audio after regeneration.
- The Zustand selector pattern is critical for performance. A project with many segments should not cause every SegmentCard to re-render when one segment's audio status changes. Subscribe to `state.audioGenerationStatus[segmentId]` rather than the entire `audioGenerationStatus` map.
- Lock status is already available on the segment data from the Phase 02 implementation.

---

> **Parent:** [SubPhase_03_03_Overview.md](./SubPhase_03_03_Overview.md) (Layer 2)
> **Phase:** [Phase_03_Overview.md](../Phase_03_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_03_03_04_Build_AudioStatusBadge.md](./Task_03_03_04_Build_AudioStatusBadge.md)
> **Next Task:** [Task_03_03_06_Activate_Generate_All_Audio_Button.md](./Task_03_03_06_Activate_Generate_All_Audio_Button.md)
