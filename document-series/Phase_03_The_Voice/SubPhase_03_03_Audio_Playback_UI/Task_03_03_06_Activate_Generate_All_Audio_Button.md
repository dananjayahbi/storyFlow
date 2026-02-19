# Task 03.03.06 — Activate Generate All Audio Button

> **Sub-Phase:** 03.03 — Audio Playback UI
> **Phase:** Phase 03 — The Voice
> **Complexity:** Medium
> **Dependencies:** Task 03.03.08 (Zustand Audio State)
> **Parent Document:** [SubPhase_03_03_Overview.md](./SubPhase_03_03_Overview.md)

---

## Objective

Enable the previously disabled "Generate All Audio" footer button, wire it to the Zustand store's bulk generation action, and provide visual feedback during the bulk operation including a Cancel option.

---

## Instructions

### Step 1 — Locate the disabled footer button

Open `frontend/app/projects/[id]/page.tsx`. Find the "Generate All Audio" button that was added during Phase 02 in a disabled state with a tooltip indicating it would be activated in Phase 03.

### Step 2 — Remove the disabled state

Remove the `disabled` attribute and the Phase 03 tooltip. The button should now be fully interactive.

### Step 3 — Wire the click handler to Zustand

On click, call the Zustand store's `generateAllAudio()` action. This action triggers the backend bulk audio generation endpoint and begins task polling.

### Step 4 — Disable during active bulk generation

While a bulk generation task is in progress (i.e., `bulkGenerationProgress` is not null), disable the button to prevent duplicate requests. Change the button label to "Generating..." and show a spinner icon.

### Step 5 — Add a Cancel button

When bulk generation is active, render a secondary "Cancel" button next to the primary button. Clicking Cancel calls the store's `cancelGeneration()` action, which stops polling and resets the bulk progress state. Note that cancellation is client-side only — it stops polling but does not abort server-side work already in progress.

### Step 6 — Handle completion and error states

When the bulk task completes, the button returns to its normal "Generate All Audio" state. If the task fails entirely, display a brief toast or inline error message. Individual segment failures are handled at the SegmentCard level, not here.

---

## Expected Output

```
frontend/
└── app/
    └── projects/
        └── [id]/
            └── page.tsx ← MODIFIED
```

---

## Validation

- [ ] "Generate All Audio" button is enabled and clickable.
- [ ] Clicking triggers the Zustand `generateAllAudio()` action.
- [ ] Button shows spinner and "Generating..." during bulk operation.
- [ ] Button is disabled during active generation (no duplicate triggers).
- [ ] Cancel button appears during generation.
- [ ] Cancellation stops polling and resets the UI to idle.
- [ ] Button returns to normal state after completion.
- [ ] No TypeScript errors.

---

## Notes

- The Cancel button stops client-side polling only. The server task will continue running to completion. This is an acceptable trade-off since the server work is idempotent (re-generating audio simply overwrites existing files).
- The button should only generate audio for unlocked segments. The Zustand action handles this filtering logic, but the button itself does not need to be aware of which segments are locked.
- Consider adding keyboard shortcut support in a future enhancement, but it is not required for this task.

---

> **Parent:** [SubPhase_03_03_Overview.md](./SubPhase_03_03_Overview.md) (Layer 2)
> **Phase:** [Phase_03_Overview.md](../Phase_03_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_03_03_05_Update_SegmentCard_Audio_Section.md](./Task_03_03_05_Update_SegmentCard_Audio_Section.md)
> **Next Task:** [Task_03_03_07_Footer_Progress_Bar.md](./Task_03_03_07_Footer_Progress_Bar.md)
