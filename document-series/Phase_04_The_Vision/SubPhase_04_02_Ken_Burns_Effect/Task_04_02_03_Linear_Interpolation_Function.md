# Task 04.02.03 — Linear Interpolation Function

## Metadata

| Field         | Value                                                                |
| ------------- | -------------------------------------------------------------------- |
| **Task ID**   | 04.02.03                                                             |
| **Task Name** | Linear Interpolation Function                                        |
| **Sub-Phase** | 04.02 — Ken Burns Effect Implementation                              |
| **Phase**     | Phase 04 — The Vision: Video Rendering Engine                        |
| **Complexity**| Medium                                                               |
| **Dependencies** | Task 04.02.01 (ken_burns.py module scaffold must exist)           |
| **Parent**    | [SubPhase_04_02_Overview.md](./SubPhase_04_02_Overview.md)           |

---

## Objective

Implement the interpolate_position function within the ken_burns.py module. This function computes the camera's crop-box position at any given time t during a clip by linearly interpolating between a start position and an end position over the clip's duration. Linear interpolation is the core animation math that drives the smooth pan motion in the Ken Burns effect, producing a constant-velocity movement from one image region to another.

---

## Instructions

### Step 1 — Define the Function Signature

Create a function named interpolate_position within backend/core_engine/ken_burns.py. The function accepts four parameters:

- start (tuple of two floats or ints): the (x, y) pixel coordinates of the crop-box top-left corner at the beginning of the clip (t equals 0).
- end (tuple of two floats or ints): the (x, y) pixel coordinates of the crop-box top-left corner at the end of the clip (t equals duration).
- t (float): the current time in seconds, provided by MoviePy's make_frame callback.
- duration (float): the total duration of the clip in seconds.

The function returns a tuple of two floats: (x, y) representing the interpolated position at time t.

Add a docstring explaining the linear interpolation formula and the clamping behavior for edge cases.

### Step 2 — Handle Edge Cases

Before computing the interpolation, handle the following edge cases:

- If duration is zero or negative, return the start position immediately. A zero-duration clip has no time span over which to interpolate, so the camera remains at the start position.
- If t is less than zero (which can happen due to floating-point precision in MoviePy), treat it as t equals zero. This is implemented by clamping the progress ratio.
- If t exceeds duration (again possible due to floating-point precision), treat it as t equals duration. The camera should not overshoot past its end position.

### Step 3 — Implement the Linear Interpolation Formula

Calculate the interpolation progress as a ratio: progress equals t divided by duration. Clamp this ratio to the range zero to one inclusive to handle the floating-point edge cases described above.

Apply the standard linear interpolation formula independently to each coordinate axis:

- x_position equals start_x plus (end_x minus start_x) multiplied by progress.
- y_position equals start_y plus (end_y minus start_y) multiplied by progress.

This produces a position that starts at the start coordinates when progress is 0, reaches the end coordinates when progress is 1, and moves at a constant velocity between them.

### Step 4 — Verify Mathematical Properties

The implementation must satisfy these mathematical invariants:

- At t equals 0, the returned position must exactly equal the start position.
- At t equals duration, the returned position must exactly equal the end position.
- At t equals duration divided by 2, the returned position must equal the exact midpoint between start and end.
- When start and end are identical, the returned position must equal that same point for any value of t. This corresponds to the center-to-center direction where no pan movement occurs.
- The function must be monotonic: as t increases from 0 to duration, each coordinate moves steadily from its start value to its end value without reversing direction.

### Step 5 — Return Float Values

Return the interpolated x and y as floats, not integers. The conversion to integer pixel coordinates happens in the make_frame callback (Task 04.02.06) using int(round(x)), which provides better accuracy than truncating early. Keeping the interpolation in floating-point avoids cumulative rounding errors across frames.

---

## Expected Output

The function interpolate_position is defined in backend/core_engine/ken_burns.py. Given standard inputs:

- interpolate_position((0, 0), (100, 200), 0, 5) returns (0.0, 0.0).
- interpolate_position((0, 0), (100, 200), 5, 5) returns (100.0, 200.0).
- interpolate_position((0, 0), (100, 200), 2.5, 5) returns (50.0, 100.0).
- interpolate_position((10, 20), (110, 220), 1.25, 5) returns (35.0, 70.0).
- interpolate_position((10, 20), (110, 220), 0, 0) returns (10.0, 20.0).
- interpolate_position((50, 50), (50, 50), 2.5, 5) returns (50.0, 50.0).

---

## Validation

- [ ] The function interpolate_position exists in ken_burns.py.
- [ ] At t equals 0, it returns the start position exactly.
- [ ] At t equals duration, it returns the end position exactly.
- [ ] At the midpoint, it returns the exact midpoint between start and end.
- [ ] Progress is clamped to the range 0 to 1 for robustness against floating-point overshoot.
- [ ] Zero duration returns the start position without division-by-zero errors.
- [ ] Identical start and end positions return that same position for any t.
- [ ] The function returns float values, not integers.
- [ ] The function has a docstring and type hints.

---

## Notes

- This implementation uses strictly linear interpolation with no easing curves. The architecture explicitly defers easing (ease-in, ease-out, ease-in-out) to a future enhancement. Linear motion produces a constant-velocity pan that is simple, predictable, and easy to validate mathematically.
- The clamping of progress to the 0-to-1 range is essential for robustness. MoviePy may call make_frame with t values that are infinitesimally negative (for example, -1e-15) or slightly beyond the clip duration (for example, 5.000000001). Without clamping, these values would cause the crop box to move outside the intended start-end range, potentially exceeding image boundaries.
- The Python built-in min and max functions provide the simplest clamping implementation: progress equals max(0.0, min(1.0, t / duration)).

---

> **Parent:** [SubPhase_04_02_Overview.md](./SubPhase_04_02_Overview.md) (Layer 2)
> **Phase:** [Phase_04_Overview.md](../Phase_04_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
