# Task 03.03.10 — Real-Time Segment Updates

> **Sub-Phase:** 03.03 — Audio Playback UI
> **Phase:** Phase 03 — The Voice
> **Complexity:** Medium
> **Dependencies:** Task 03.03.08 (Zustand Audio State), Task 03.03.09 (Task Polling)
> **Parent Document:** [SubPhase_03_03_Overview.md](./SubPhase_03_03_Overview.md)

---

## Objective

Ensure that individual SegmentCards update in real time as their audio generation completes, using optimized Zustand selectors to prevent unnecessary re-renders across unrelated cards.

---

## Instructions

### Step 1 — Implement granular Zustand selectors

In `frontend/components/SegmentCard.tsx`, ensure the component subscribes to only the specific segment's audio generation status rather than the entire `audioGenerationStatus` map. Use a Zustand selector function that returns `state.audioGenerationStatus[segmentId]` so that the component only re-renders when its own segment's status changes.

### Step 2 — Verify the transition from idle to generating

When `generateAudio(segmentId)` is called from a SegmentCard, confirm that only that specific card's UI transitions to the generating state (spinner on button, pulsing border). All other SegmentCards should remain unchanged.

### Step 3 — Verify the transition from generating to completed

When the polling callback updates a segment's status to "completed" and calls `refreshSegmentAudio(segmentId)`, confirm that the specific SegmentCard re-renders to show the AudioPlayer with the new audio file. The transition should be seamless — the GenerateAudioButton disappears and the AudioPlayer appears.

### Step 4 — Verify the transition from generating to failed

When the polling callback updates a segment's status to "failed," confirm that the SegmentCard shows the GenerateAudioButton in its failed state (error message and retry button). The pulsing border should stop.

### Step 5 — Optimize refreshSegmentAudio updates

When `refreshSegmentAudio` fetches updated segment data from the API, ensure that only the specific segment object in the store's `segments` array is replaced. Use an immutable update pattern: map over the array and replace the matching segment by ID. This prevents all SegmentCards from re-rendering due to a new array reference.

### Step 6 — Test bulk generation real-time updates

During a bulk generation operation, confirm that SegmentCards update individually as each segment's audio completes. The updates should appear progressively — not all at once after the bulk task finishes. This is achieved by the polling integration updating individual segment statuses incrementally.

---

## Expected Output

```
frontend/
├── lib/
│   └── stores.ts ← MODIFIED (selector optimization in refreshSegmentAudio)
└── components/
    └── SegmentCard.tsx ← MODIFIED (selector pattern)
```

---

## Validation

- [ ] SegmentCard subscribes to `state.audioGenerationStatus[segmentId]` specifically.
- [ ] Generating one segment does not cause other SegmentCards to re-render.
- [ ] Idle → generating transition shows spinner and pulsing border on the correct card only.
- [ ] Generating → completed transition replaces GenerateAudioButton with AudioPlayer.
- [ ] Generating → failed transition shows error state with retry option.
- [ ] `refreshSegmentAudio` replaces only the specific segment in the array.
- [ ] Bulk generation updates SegmentCards progressively as each completes.
- [ ] React DevTools (if used) confirms minimal re-renders.

---

## Notes

- This task is primarily about verification and optimization rather than building new components. The components and state are created in earlier tasks; this task ensures they work together efficiently.
- Zustand's default shallow comparison for selectors returning primitives or stable references works well. However, if the selector returns a new object reference each time (e.g., due to the spread operator), it will cause unnecessary re-renders. Use Zustand's `shallow` equality function from `zustand/shallow` if needed.
- The immutable update pattern in `refreshSegmentAudio` is critical. Replacing the entire `segments` array with a new reference that only has one changed element is the correct approach. React's reconciliation will handle the DOM diffing efficiently.
- For projects with a large number of segments (e.g., 50+), the performance optimization matters more. For typical projects with 10–20 segments, the difference may be negligible, but the pattern should be correct regardless.

---

> **Parent:** [SubPhase_03_03_Overview.md](./SubPhase_03_03_Overview.md) (Layer 2)
> **Phase:** [Phase_03_Overview.md](../Phase_03_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_03_03_09_Implement_Task_Polling_UI.md](./Task_03_03_09_Implement_Task_Polling_UI.md)
> **Next Task:** [Task_03_03_11_Add_Regenerate_Audio_Option.md](./Task_03_03_11_Add_Regenerate_Audio_Option.md)
