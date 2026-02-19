# Task 03.03.08 — Update Zustand Audio State

> **Sub-Phase:** 03.03 — Audio Playback UI
> **Phase:** Phase 03 — The Voice
> **Complexity:** High
> **Dependencies:** Task 03.02.09 (Frontend API Client), Task 03.02.10 (TypeScript Types)
> **Parent Document:** [SubPhase_03_03_Overview.md](./SubPhase_03_03_Overview.md)

---

## Objective

Extend the existing `useProjectStore` Zustand store with audio generation state, bulk generation progress tracking, and all actions required to drive the audio playback UI.

---

## Instructions

### Step 1 — Define the AudioGenerationState type

In `frontend/lib/stores.ts`, define an `AudioGenerationState` type with the following shape: a `status` field (one of "idle," "generating," "completed," or "failed"), an optional `error` string for failure messages, and an optional `taskId` string for the associated background task.

### Step 2 — Define the BulkGenerationProgress type

Define a `BulkGenerationProgress` type containing `total` (number of segments being processed), `completed` (number finished), and `failed` (number that encountered errors).

### Step 3 — Add audio state properties to the store

Extend the store's state with:
- `audioTaskId`: string or null — the task ID for single-segment generation, used for polling.
- `audioGenerationStatus`: a Record mapping segment IDs (strings) to `AudioGenerationState` objects. Default is an empty object.
- `bulkGenerationProgress`: `BulkGenerationProgress` or null. Default is null.

### Step 4 — Implement the generateAudio action

Create a `generateAudio(segmentId: string)` action. This action sets the segment's status to "generating" in `audioGenerationStatus`, calls the single-segment audio generation API endpoint via `lib/api.ts`, stores the returned `taskId`, and then initiates task polling (see Task 03.03.09 for polling details). On polling completion with "COMPLETED" status, update the segment's status to "completed" and call `refreshSegmentAudio(segmentId)`. On "FAILED," update status to "failed" with the error message.

### Step 5 — Implement the generateAllAudio action

Create a `generateAllAudio()` action. This action initializes `bulkGenerationProgress` with `total` set to the count of unlocked segments without audio (or all unlocked segments if regenerating), `completed` at 0, and `failed` at 0. It calls the bulk audio generation API endpoint, stores the returned `taskId`, and initiates bulk task polling. During polling, the action updates individual segment statuses and increments `completed` or `failed` counters as each segment finishes. On full completion, the action leaves `bulkGenerationProgress` in place for the footer to show a completion summary.

### Step 6 — Implement the cancelGeneration action

Create a `cancelGeneration()` action. This action stops the active polling interval (if any), resets `bulkGenerationProgress` to null, and sets any segments that are still in "generating" status back to "idle." It does NOT cancel the server-side task.

### Step 7 — Implement the refreshSegmentAudio action

Create a `refreshSegmentAudio(segmentId: string)` action. This action calls the segment detail API endpoint to fetch the latest segment data (which now includes the `audio_file` and `audio_duration` fields) and updates the segment in the store's segments array. This ensures the AudioPlayer receives the correct audio URL after generation completes.

### Step 8 — Implement the setSegmentAudioStatus action

Create a `setSegmentAudioStatus(segmentId: string, status: AudioGenerationState)` action. This is a low-level setter used internally by the polling logic and by other actions to update a specific segment's audio generation status.

### Step 9 — Implement the clearBulkProgress action

Create a `clearBulkProgress()` action. This resets `bulkGenerationProgress` to null. Called by the footer progress bar's auto-dismiss timeout after displaying the completion summary.

---

## Expected Output

```
frontend/
└── lib/
    └── stores.ts ← MODIFIED
```

---

## Validation

- [ ] `AudioGenerationState` type is defined with status, error, and taskId fields.
- [ ] `BulkGenerationProgress` type is defined with total, completed, and failed fields.
- [ ] `audioGenerationStatus` is a Record in the store, defaulting to empty object.
- [ ] `bulkGenerationProgress` defaults to null.
- [ ] `generateAudio(segmentId)` sets status to generating, calls API, starts polling.
- [ ] `generateAllAudio()` initializes bulk progress, calls API, starts polling.
- [ ] `cancelGeneration()` stops polling and resets generating segments to idle.
- [ ] `refreshSegmentAudio(segmentId)` fetches latest segment data and updates store.
- [ ] `setSegmentAudioStatus()` updates individual segment status.
- [ ] `clearBulkProgress()` resets bulk progress to null.
- [ ] All actions maintain immutability via Zustand's `set` function.
- [ ] No TypeScript errors.

---

## Notes

- This is the most architecturally significant task in SubPhase 03.03. It serves as the single source of truth for all audio generation state and drives every audio-related UI component.
- Polling logic details are covered in Task 03.03.09, but the actions defined here provide the callback hooks that the polling integration calls. The boundary is: this task defines what happens (state transitions), Task 03.03.09 defines when it happens (polling lifecycle).
- Use Zustand's immer middleware or spread-based immutable updates to safely modify nested state (the `audioGenerationStatus` Record). Direct mutation will not trigger re-renders.
- The `refreshSegmentAudio` action is separate from the main segment fetch because it targets a single segment. This avoids re-fetching the entire segments list when only one segment's audio changed.
- Store a reference to the polling interval ID so that `cancelGeneration` can clear it. Consider using a `pollingIntervalId` property in the store (not exposed to components) or managing it in a closure within the action.

---

> **Parent:** [SubPhase_03_03_Overview.md](./SubPhase_03_03_Overview.md) (Layer 2)
> **Phase:** [Phase_03_Overview.md](../Phase_03_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_03_03_07_Footer_Progress_Bar.md](./Task_03_03_07_Footer_Progress_Bar.md)
> **Next Task:** [Task_03_03_09_Implement_Task_Polling_UI.md](./Task_03_03_09_Implement_Task_Polling_UI.md)
