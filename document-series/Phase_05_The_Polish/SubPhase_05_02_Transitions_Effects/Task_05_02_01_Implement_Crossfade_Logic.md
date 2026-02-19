# Task 05.02.01 — Implement Crossfade Logic

## Layer 3 Task Document

---

| **Field**              | **Value**                                                                                      |
| ---------------------- | ---------------------------------------------------------------------------------------------- |
| **Task ID**            | 05.02.01                                                                                       |
| **Task Name**          | Implement Crossfade Logic                                                                      |
| **Sub-Phase**          | 05.02 — Transitions & Effects                                                                  |
| **Phase**              | Phase 05 — The Polish                                                                          |
| **Layer**              | Layer 3 (Task Document)                                                                        |
| **Status**             | Not Started                                                                                    |
| **Estimated Complexity** | Medium                                                                                       |
| **Parent Document**    | [SubPhase_05_02_Overview.md](./SubPhase_05_02_Overview.md) (Layer 2)                           |
| **Dependencies**       | SubPhase 05.01 complete (subtitle-composited clips available)                                  |
| **Output Files**       | `backend/core_engine/video_renderer.py` (MODIFIED)                                             |

---

## Objective

Create the core crossfade transition utility function that applies MoviePy's `crossfadein()` and `crossfadeout()` effects to a list of video clips, preparing them for overlapping concatenation. This function serves as the foundation for all crossfade transition behavior throughout SubPhase 05.02 — every subsequent task depends on this implementation being in place.

---

## Instructions

### Step 1 — Define the Transition Constant

Open `backend/core_engine/video_renderer.py` and define a module-level constant named `TRANSITION_DURATION` set to `0.5` (seconds). This constant is fixed for v1.0 and is not user-configurable. Place it near the top of the file alongside other module-level constants and logger definitions. Add a comment clarifying that this value is intentionally fixed and must not be exposed to users or the settings UI.

### Step 2 — Implement the Crossfade Application Function

Create a function named `apply_crossfade_transitions` that accepts two parameters: a list of video clip objects and an optional `transition_duration` parameter defaulting to the `TRANSITION_DURATION` constant. The function returns the same list of clips with crossfade effects applied according to the following rules:

- **Guard clause**: If the list has one or zero clips, return the list unchanged immediately. No crossfade makes sense for a single clip, and an empty list is a no-op.
- **First clip** (index 0): Apply only `crossfadeout(transition_duration)`. The video should start cleanly at full opacity — no fade-in at the beginning.
- **Middle clips** (indices 1 through N-2): Apply both `crossfadein(transition_duration)` and `crossfadeout(transition_duration)`. These clips blend with their predecessor and successor.
- **Last clip** (index N-1): Apply only `crossfadein(transition_duration)`. The video should end cleanly at full opacity — no fade-out at the end.

Iterate through the clips using an enumerated loop. For each clip, check whether it has a predecessor (index greater than 0) and whether it has a successor (index less than the list length minus 1). Apply the appropriate crossfade methods based on these conditions. Collect the modified clips into a new list and return it.

Important technical detail: MoviePy's `crossfadein()` and `crossfadeout()` methods return new clip objects — they do not mutate the original clip in place. The return value from each method call must be captured and used for subsequent operations on the same clip.

### Step 3 — Understand Crossfade vs. Fade Distinction

The function must use `crossfadein` and `crossfadeout` specifically — NOT `fadein` and `fadeout`. These are different MoviePy methods with different visual results:

- `crossfadein(d)` modifies the clip's opacity (alpha channel), ramping from 0.0 to 1.0 over the first `d` seconds. The clip's pixel data remains present but is made transparent. This is designed for compositing with another clip underneath — the two clips blend together during the transition.
- `fadein(d)` fades from solid black to the clip's pixels. This creates a "fade from black" effect, not a crossfade between two clips. Using `fadein` instead of `crossfadein` would produce a black flash between clips instead of a smooth visual blend.

The same distinction applies to `crossfadeout` versus `fadeout`. Always use the "cross" variants for transitions between clips.

### Step 4 — Add Logging

Add an info-level log message at the start of the function (after the guard clause) reporting the number of clips receiving crossfade effects and the transition duration being used. Add a debug-level log message listing the duration of each clip before crossfade application. This aids in diagnosing transition-related issues during development and production usage.

### Step 5 — Placement Decision

The preferred placement for this function is directly within `video_renderer.py` as either a module-level function or a prefixed private function (e.g., `_apply_crossfade_transitions`). This keeps all rendering logic consolidated in a single file. If `video_renderer.py` has grown excessively large by this point, an alternative is to create a new module at `backend/core_engine/transition_utils.py` and import the function into the renderer. The choice should be made based on the current file size, but the default is to keep it in the renderer file for simplicity.

### Step 6 — Validate Crossfade Duration Against Clip Duration

Before applying crossfade effects, iterate through the clips and check whether any clip's duration is shorter than the transition duration. If a clip is shorter than 0.5 seconds, log a warning indicating the clip's index and duration. Do not raise an error or skip the clip — the crossfade will still be applied, but the visual result may be unusual (the entire clip consumed by the transition). In practice this should never occur because TTS segments from Kokoro-82M are always at least 0.5–1.0 seconds, but the defensive check prevents confusing behavior if it somehow happens.

---

## Expected Output

After completing this task, `video_renderer.py` contains:

- A module-level constant `TRANSITION_DURATION = 0.5` with a descriptive comment.
- A function `apply_crossfade_transitions(clips, transition_duration)` that correctly applies `crossfadein` and `crossfadeout` to a list of clips based on their position (first, middle, last).
- The function returns the list unchanged for zero or one clips.
- The function includes info and debug logging.
- The function includes a defensive warning for clips shorter than the transition duration.

---

## Validation

- [ ] `TRANSITION_DURATION` constant is defined at module level with value `0.5`.
- [ ] `apply_crossfade_transitions` exists and accepts a list of clips and an optional duration parameter.
- [ ] Single-clip input returns the clip unchanged (no crossfade applied).
- [ ] Empty list input returns an empty list.
- [ ] For two clips: first clip gets `crossfadeout` only, second clip gets `crossfadein` only.
- [ ] For three or more clips: first gets `crossfadeout`, middle clips get both, last gets `crossfadein`.
- [ ] The function uses `crossfadein`/`crossfadeout` — NOT `fadein`/`fadeout`.
- [ ] Logging statements are present at info and debug levels.
- [ ] A warning is logged if any clip's duration is shorter than the transition duration.
- [ ] The function does not mutate the original clips list (returns a new list).

---

## Notes

- This function only prepares the clips with crossfade effects — it does NOT perform the actual concatenation. The concatenation with negative padding is handled separately in Task 05.02.02.
- The crossfade effects modify both video and audio simultaneously. When `crossfadein(0.5)` is applied, the clip's audio volume also ramps from 0.0 to 1.0 over the first 0.5 seconds. This audio behavior is intentional and desired for smooth transitions.
- The 0.5-second transition duration is a v1.0 design decision based on standard video editing practices. It is long enough to be visually perceptible but short enough to avoid sluggish pacing.
- MoviePy's crossfade methods work on any clip type, including `CompositeVideoClip` (which is what subtitle-composited clips are). The crossfade applies to the entire composite — Ken Burns visuals and subtitle text fade together.

---

> **Parent:** [SubPhase_05_02_Overview.md](./SubPhase_05_02_Overview.md) (Layer 2)
> **Phase:** [Phase_05_Overview.md](../Phase_05_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
