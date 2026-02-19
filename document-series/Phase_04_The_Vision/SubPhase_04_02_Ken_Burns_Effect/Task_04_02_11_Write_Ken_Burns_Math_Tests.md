# Task 04.02.11 — Write Ken Burns Math Tests

## Metadata

| Field         | Value                                                                |
| ------------- | -------------------------------------------------------------------- |
| **Task ID**   | 04.02.11                                                             |
| **Task Name** | Write Ken Burns Math Tests                                           |
| **Sub-Phase** | 04.02 — Ken Burns Effect Implementation                              |
| **Phase**     | Phase 04 — The Vision: Video Rendering Engine                        |
| **Complexity**| Medium                                                               |
| **Dependencies** | Tasks 04.02.02, 04.02.03, 04.02.04, 04.02.05 (all math functions must exist to be tested) |
| **Parent**    | [SubPhase_04_02_Overview.md](./SubPhase_04_02_Overview.md)           |

---

## Objective

Write a comprehensive suite of unit tests that validate the mathematical correctness of all Ken Burns algorithm components: crop box dimension calculation, linear interpolation, pan direction cycling, and position-to-coordinate mapping. These tests are pure math tests with no file I/O, no image processing, and no MoviePy dependency, ensuring they execute in under one second and provide fast feedback during development.

---

## Instructions

### Step 1 — Create the Test Class

Add a new test class named KenBurnsMathTests to backend/api/tests.py. This class extends Django's TestCase. Import the necessary functions from core_engine.ken_burns: calculate_crop_dimensions, interpolate_position, get_pan_direction, position_to_coords, and the DIRECTIONS constant.

### Step 2 — Test Crop Box Dimensions at Default Zoom

Write a test method that verifies crop box dimensions at the standard zoom intensity of 1.3 with output resolution 1920 by 1080. Call calculate_crop_dimensions with these inputs and assert that the returned crop_width is approximately 1476 and crop_height is approximately 830. Use exact integer comparison since the function uses floor division. Also assert that both values are positive integers.

### Step 3 — Test Crop Box Dimensions With No Zoom

Write a test method that verifies crop box dimensions when zoom intensity is exactly 1.0. At 1920 by 1080 output, the crop dimensions should equal the output dimensions exactly (1920, 1080), meaning no zoom occurs. Assert exact equality.

### Step 4 — Test Crop Box Dimensions at High Zoom

Write a test method that verifies crop box dimensions when zoom intensity is 2.0. At 1920 by 1080 output, the crop dimensions should be (960, 540) — exactly half the output in each dimension. Assert exact equality.

### Step 5 — Test Crop Box Invalid Zoom

Write a test method that verifies ValueError is raised when zoom intensity is zero or negative. Call calculate_crop_dimensions with zoom values of 0.0 and -1.0 separately, and assert that each call raises ValueError. Use the assertRaises context manager for clean assertion syntax.

### Step 6 — Test Linear Interpolation at Start

Write a test method that verifies the interpolation returns the start position exactly when t equals 0. Use start position (0, 0), end position (100, 200), t equals 0, duration equals 5. Assert the result is (0.0, 0.0).

### Step 7 — Test Linear Interpolation at End

Write a test method that verifies the interpolation returns the end position exactly when t equals the duration. Use start (0, 0), end (100, 200), t equals 5, duration equals 5. Assert the result is (100.0, 200.0).

### Step 8 — Test Linear Interpolation at Midpoint

Write a test method that verifies the interpolation returns the exact midpoint when t equals duration divided by 2. Use start (0, 0), end (100, 200), t equals 2.5, duration equals 5. Assert the result is (50.0, 100.0).

### Step 9 — Test Linear Interpolation at Quarter Point

Write a test method using non-zero start values to verify generality. Use start (10, 20), end (110, 220), t equals 1.25, duration equals 5. The progress is 0.25, so the expected result is (35.0, 70.0). This verifies the formula works correctly with non-origin start positions.

### Step 10 — Test Linear Interpolation With Zero Duration

Write a test method that verifies the function handles zero duration gracefully without a division-by-zero error. Use start (10, 20), end (110, 220), t equals 0, duration equals 0. Assert the result equals the start position (10, 20). The function should detect zero duration and short-circuit to returning start.

### Step 11 — Test Linear Interpolation With No Movement

Write a test method that verifies correct behavior when start and end positions are identical. Use start (50, 50), end (50, 50), and test at multiple t values (0, 2.5, and 5 with duration 5). Assert that all calls return (50.0, 50.0). This corresponds to the center-to-center direction.

### Step 12 — Test Pan Direction Cycling

Write a test method that calls get_pan_direction for segment indices 0 through 13 (two full cycles). Assert that the first 7 results (indices 0 through 6) match the 7 entries in the DIRECTIONS constant in order. Assert that results for indices 7 through 13 repeat the pattern from the beginning (indices 7 through 13 match indices 0 through 6).

### Step 13 — Test Pan Direction Determinism

Write a test method that calls get_pan_direction(3) twice and asserts both calls return identical results. This confirms the function is deterministic with no hidden randomness.

### Step 14 — Test Position to Coords Center

Write a test method that verifies the center position mapping. Use source image dimensions 2496 by 1404 with crop dimensions 1476 by 830 (corresponding to 1920x1080 at zoom 1.3). The max_x is 1020 and max_y is 574. The center position should map to (510, 287) — which is (1020 // 2, 574 // 2).

### Step 15 — Test Position to Coords Corners

Write a test method that verifies all four corner positions with the same image and crop dimensions as the center test. Assert:

- top_left maps to (0, 0).
- top_right maps to (1020, 0).
- bottom_left maps to (0, 574).
- bottom_right maps to (1020, 574).

### Step 16 — Test Position to Coords Invalid Name

Write a test method that verifies ValueError is raised when an unrecognized position name is passed. Call position_to_coords with "middle_left" and assert that ValueError is raised.

### Step 17 — Verify Floating-Point Tolerance

For interpolation tests that involve floating-point arithmetic, use assertAlmostEqual with a tolerance of 1e-6 or compare tuples element-by-element with a small delta. This prevents false test failures from floating-point precision differences across platforms.

---

## Expected Output

A test class named KenBurnsMathTests in backend/api/tests.py containing at least 16 test methods (one per step above, excluding Step 1 which is the class definition and Step 17 which is a general guideline). All tests are pure math with no I/O, and the entire class executes in under one second.

---

## Validation

- [ ] KenBurnsMathTests class exists in backend/api/tests.py.
- [ ] The class contains at least 12 test methods covering all four math functions.
- [ ] Crop box tests cover default zoom, no zoom, high zoom, and invalid zoom.
- [ ] Interpolation tests cover start, end, midpoint, quarter, zero duration, and no movement.
- [ ] Direction tests cover cycling behavior and determinism.
- [ ] Position tests cover center, all four corners, and invalid names.
- [ ] All tests pass when run with python manage.py test.
- [ ] Tests run in under one second (no file I/O, no images, no MoviePy).
- [ ] Floating-point comparisons use appropriate tolerance.

---

## Notes

- These tests are designed to catch mathematical errors in the Ken Burns algorithm, such as off-by-one errors in coordinate calculations, incorrect interpolation formulas, or wrong modulo cycling. They provide confidence that the low-level computation is correct before integration testing validates the full pipeline.
- The test values are chosen to exercise specific properties: zero-origin starts, non-zero starts, midpoints, quarter-points, exact boundaries, and edge cases like zero duration or identical positions. Each test validates a specific mathematical invariant.
- Since these tests import functions directly from ken_burns.py and test them in isolation, they do not require Django models, test databases, or file fixtures. They are the fastest tests in the project and should be run frequently during development.
- The DIRECTIONS constant is imported directly in the test to verify cycling behavior against the authoritative list. If DIRECTIONS changes in the future, the cycling tests will need to be updated accordingly.

---

> **Parent:** [SubPhase_04_02_Overview.md](./SubPhase_04_02_Overview.md) (Layer 2)
> **Phase:** [Phase_04_Overview.md](../Phase_04_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
