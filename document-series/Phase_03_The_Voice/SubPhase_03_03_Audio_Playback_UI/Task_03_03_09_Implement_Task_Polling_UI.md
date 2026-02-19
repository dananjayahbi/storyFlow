# Task 03.03.09 — Implement Task Polling UI Integration

> **Sub-Phase:** 03.03 — Audio Playback UI
> **Phase:** Phase 03 — The Voice
> **Complexity:** High
> **Dependencies:** Task 03.02.05 (Task Status Endpoint), Task 03.02.09 (Frontend API Client), Task 03.03.08 (Zustand Audio State)
> **Parent Document:** [SubPhase_03_03_Overview.md](./SubPhase_03_03_Overview.md)

---

## Objective

Wire the frontend task polling mechanism to the Zustand store actions and UI components, enabling real-time progress tracking for both single-segment and bulk audio generation.

---

## Instructions

### Step 1 — Implement the pollTaskStatus utility

In `frontend/lib/stores.ts` (or a dedicated utility file if preferred), implement a `pollTaskStatus` function that periodically calls the task status API endpoint. The function accepts a task ID and a callback that receives the task status response. It uses `setInterval` with a configurable polling interval (default 2 seconds). The function returns the interval ID so callers can stop polling.

### Step 2 — Wire single-segment polling flow

Within the `generateAudio(segmentId)` action (defined in Task 03.03.08), after receiving the task ID from the API response, start polling with `pollTaskStatus`. On each poll response:
- If status is "PENDING" or "PROCESSING," do nothing (polling continues).
- If status is "COMPLETED," stop polling, call `setSegmentAudioStatus(segmentId, { status: "completed" })`, and call `refreshSegmentAudio(segmentId)` to fetch the updated segment with its new audio file.
- If status is "FAILED," stop polling and call `setSegmentAudioStatus(segmentId, { status: "failed", error: response.error })`.

### Step 3 — Wire bulk generation polling flow

Within the `generateAllAudio()` action (defined in Task 03.03.08), after receiving the task ID from the bulk API response, start polling with `pollTaskStatus`. The bulk task status response includes a `result` object with per-segment outcomes. On each poll response:
- If the task is still processing, examine the result for any newly completed segments. Use a `handledSegments` Set to track which segments have already been processed in previous poll cycles. For each newly completed segment, update its individual status to "completed," call `refreshSegmentAudio` for that segment, and increment `bulkGenerationProgress.completed`.
- For each newly failed segment, update its status to "failed" with the error message and increment `bulkGenerationProgress.failed`.
- When the overall task status is "COMPLETED" or "FAILED," stop polling.

### Step 4 — Implement polling cleanup on cancel

Ensure that `cancelGeneration()` clears the polling interval. Store the interval ID in a module-level variable or within the store state (as a non-serializable property). When cancel is called, call `clearInterval` on the stored ID and set it to null.

### Step 5 — Implement polling cleanup on unmount

In the project detail page component, add a `useEffect` cleanup that calls `cancelGeneration()` when the component unmounts. This prevents orphaned polling intervals if the user navigates away from the project page during active generation.

### Step 6 — Handle polling errors

If a poll request itself fails (network error, server error), implement a retry strategy: allow up to 3 consecutive failed poll attempts before treating the task as failed. On transient failure, log a warning and continue polling. On 3 consecutive failures, stop polling and set the generation status to failed with a "Lost connection to server" error message.

---

## Expected Output

```
frontend/
├── lib/
│   └── stores.ts ← MODIFIED
└── app/
    └── projects/
        └── [id]/
            └── page.tsx ← MODIFIED (cleanup useEffect)
```

---

## Validation

- [ ] Single-segment polling starts after generate-audio API returns task ID.
- [ ] Polling stops and status updates to "completed" on task success.
- [ ] Polling stops and status updates to "failed" on task failure.
- [ ] `refreshSegmentAudio` is called after successful single-segment generation.
- [ ] Bulk polling tracks per-segment outcomes using a handledSegments Set.
- [ ] `bulkGenerationProgress` is updated incrementally as segments complete.
- [ ] Cancel stops polling and resets generating segments to idle.
- [ ] Component unmount clears polling interval.
- [ ] Polling tolerates up to 3 transient network failures before failing.
- [ ] No orphaned intervals after navigation or cancellation.
- [ ] No TypeScript errors.

---

## Notes

- The polling interval of 2 seconds is a balance between responsiveness and server load. Since StoryFlow is local-only, server load is minimal, so a shorter interval is acceptable.
- The `handledSegments` Set is essential for bulk polling. Without it, the polling callback would re-process segments that completed in earlier cycles, potentially causing duplicate `refreshSegmentAudio` calls and redundant state updates.
- The polling function should be robust against race conditions. If the user triggers a new generation while a previous one is still polling, the old polling interval should be cleared before starting the new one.
- Consider using `AbortController` for the polling fetch calls to allow clean cancellation of in-flight requests. This is optional but improves cleanup behavior.

---

> **Parent:** [SubPhase_03_03_Overview.md](./SubPhase_03_03_Overview.md) (Layer 2)
> **Phase:** [Phase_03_Overview.md](../Phase_03_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_03_03_08_Update_Zustand_Audio_State.md](./Task_03_03_08_Update_Zustand_Audio_State.md)
> **Next Task:** [Task_03_03_10_Real_Time_Segment_Updates.md](./Task_03_03_10_Real_Time_Segment_Updates.md)
