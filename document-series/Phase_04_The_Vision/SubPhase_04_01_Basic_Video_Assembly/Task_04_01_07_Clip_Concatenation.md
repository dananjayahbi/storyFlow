# Task 04.01.07 — Clip Concatenation

> **Sub-Phase:** 04.01 — Basic Video Assembly
> **Phase:** Phase 04 — The Vision
> **Complexity:** Medium
> **Dependencies:** Task 04.01.06 (Duration Synchronization)
> **Parent Document:** [SubPhase_04_01_Overview.md](./SubPhase_04_01_Overview.md)

---

## Objective

Implement the logic that joins all individual segment clips into a single, continuous video timeline using MoviePy's concatenation function.

---

## Instructions

### Step 1 — Validate the clips list

Before concatenation, check that the clips list is not empty. If no clips were created (no segments, or all segments were skipped due to zero-duration audio), raise a `ValueError("No segments to render")`.

### Step 2 — Concatenate clips

Call `concatenate_videoclips(clips, method="compose")` to join all segment clips into a single timeline. The `method="compose"` argument is a requirement from the architecture — it handles clips that might have slightly different resolutions gracefully, making it more defensive than `method="chain"` which requires all clips to be exactly the same size.

### Step 3 — Validate the result

After concatenation, verify that `final.duration > 0`. Log the total duration and the number of clips concatenated. If a single clip was provided, `concatenate_videoclips` handles it gracefully by returning the clip unchanged.

### Step 4 — Preserve clips in memory

The concatenated result lazily references the original clips. The original clips must remain in memory (not closed) until after the export step completes. Closing individual clips before export would cause MoviePy to fail when trying to render frames.

---

## Expected Output

```
backend/
└── core_engine/
    └── video_renderer.py ← MODIFIED (concatenation step)
```

---

## Validation

- [ ] `concatenate_videoclips` is called with `method="compose"`.
- [ ] Empty clips list raises `ValueError("No segments to render")`.
- [ ] Single clip is handled gracefully.
- [ ] Total duration is logged after concatenation.
- [ ] Original clips remain in memory until after export.
- [ ] Clips are ordered by `sequence_index` (hard cuts, no transitions).

---

## Notes

- **No transitions in SubPhase 04.01.** Clips are placed end-to-end with hard cuts. Crossfade transitions are a Phase 05 feature.
- The `clips` list order is guaranteed by the `order_by('sequence_index')` query, so no additional sorting is needed.
- `concatenate_videoclips` returns a `CompositeVideoClip` that is a virtual composition of the input clips. It is lightweight — the actual rendering happens during export.

---

> **Parent:** [SubPhase_04_01_Overview.md](./SubPhase_04_01_Overview.md) (Layer 2)
> **Phase:** [Phase_04_Overview.md](../Phase_04_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_04_01_06_Duration_Synchronization.md](./Task_04_01_06_Duration_Synchronization.md)
> **Next Task:** [Task_04_01_08_MP4_Export_With_Codecs.md](./Task_04_01_08_MP4_Export_With_Codecs.md)
