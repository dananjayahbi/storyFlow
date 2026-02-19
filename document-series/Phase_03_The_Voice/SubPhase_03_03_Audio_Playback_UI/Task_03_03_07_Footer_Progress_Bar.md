# Task 03.03.07 — Footer Progress Bar

> **Sub-Phase:** 03.03 — Audio Playback UI
> **Phase:** Phase 03 — The Voice
> **Complexity:** Medium
> **Dependencies:** Task 03.03.01 (Shadcn Progress), Task 03.03.06 (Generate All Button), Task 03.03.08 (Zustand Audio State)
> **Parent Document:** [SubPhase_03_03_Overview.md](./SubPhase_03_03_Overview.md)

---

## Objective

Add a footer-level progress bar that displays real-time progress during bulk audio generation, showing the number of completed segments and a percentage.

---

## Instructions

### Step 1 — Add the progress bar container

In `frontend/app/projects/[id]/page.tsx`, below the "Generate All Audio" button area, add a container that renders conditionally when `bulkGenerationProgress` is not null in the Zustand store.

### Step 2 — Render the Shadcn Progress component

Use the Shadcn `Progress` component (installed in Task 03.03.01). Set its `value` prop to the percentage calculated from `bulkGenerationProgress.completed / bulkGenerationProgress.total * 100`.

### Step 3 — Add the progress label

Above or below the progress bar, render a text label showing "Generating audio... X/Y segments complete (Z%)" where X is the completed count, Y is the total count, and Z is the rounded percentage.

### Step 4 — Handle completion

When bulk generation completes (all segments processed), show a brief success summary for a few seconds: "Audio generation complete — X of Y segments succeeded." Use a timeout (e.g., 3 seconds) to auto-dismiss the summary and clear `bulkGenerationProgress`.

### Step 5 — Handle partial failure

If some segments failed during bulk generation, show a summary indicating how many succeeded and how many failed: "Audio generation complete — X succeeded, Z failed." The failed segments can be individually retried from their SegmentCards.

### Step 6 — Ensure full-width layout

The progress bar should span the full width of the footer area. On narrow screens, the progress label should wrap naturally below the bar. Use Tailwind responsive utilities to maintain a clean layout at all breakpoints.

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

- [ ] Progress bar appears only during bulk audio generation.
- [ ] Shadcn Progress component displays correct percentage.
- [ ] Label shows "X/Y segments complete (Z%)" during generation.
- [ ] Success summary appears briefly after completion, then auto-dismisses.
- [ ] Partial failure summary shows succeeded/failed counts.
- [ ] Progress bar spans full width of footer area.
- [ ] Layout is clean at narrow screen widths.
- [ ] No TypeScript errors.

---

## Notes

- The `bulkGenerationProgress` object in the Zustand store contains `total` (number of segments being processed), `completed` (number finished so far), and `failed` (number that encountered errors). This data is updated by the task polling integration (Task 03.03.09).
- The progress bar is purely visual — it reads from Zustand state and renders accordingly. It does not manage its own state or trigger any actions.
- The auto-dismiss timeout should use a `useEffect` cleanup to prevent memory leaks if the component unmounts before the timeout fires.

---

> **Parent:** [SubPhase_03_03_Overview.md](./SubPhase_03_03_Overview.md) (Layer 2)
> **Phase:** [Phase_03_Overview.md](../Phase_03_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_03_03_06_Activate_Generate_All_Audio_Button.md](./Task_03_03_06_Activate_Generate_All_Audio_Button.md)
> **Next Task:** [Task_03_03_08_Update_Zustand_Audio_State.md](./Task_03_03_08_Update_Zustand_Audio_State.md)
