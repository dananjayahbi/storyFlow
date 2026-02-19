# Task 04.02.02 — Crop Box Math

## Metadata

| Field         | Value                                                                |
| ------------- | -------------------------------------------------------------------- |
| **Task ID**   | 04.02.02                                                             |
| **Task Name** | Crop Box Math                                                        |
| **Sub-Phase** | 04.02 — Ken Burns Effect Implementation                              |
| **Phase**     | Phase 04 — The Vision: Video Rendering Engine                        |
| **Complexity**| Medium                                                               |
| **Dependencies** | Task 04.02.01 (ken_burns.py module scaffold must exist)           |
| **Parent**    | [SubPhase_04_02_Overview.md](./SubPhase_04_02_Overview.md)           |

---

## Objective

Implement the calculate_crop_dimensions function within the ken_burns.py module. This function computes the width and height of the rectangular crop box that is extracted from the source image on every frame. The crop box dimensions are derived from the output resolution divided by the zoom intensity, ensuring that when the crop is resized to fill the output, a zoom-in effect is visually produced. This is the foundational geometric calculation that all subsequent position-mapping and frame-generation logic depends on.

---

## Instructions

### Step 1 — Define the Function Signature

Create a function named calculate_crop_dimensions within backend/core_engine/ken_burns.py. The function accepts three parameters:

- output_width (int): the horizontal resolution of the output video in pixels, for example 1920.
- output_height (int): the vertical resolution of the output video in pixels, for example 1080.
- zoom_intensity (float): the zoom factor, typically 1.3. Must be greater than zero.

The function returns a tuple of two integers: (crop_width, crop_height).

Add a docstring that explains the mathematical relationship between crop dimensions, output resolution, and zoom intensity, including the formulae used.

### Step 2 — Implement Input Validation

Before performing any calculation, validate the inputs:

- If zoom_intensity is less than or equal to zero, raise a ValueError with a descriptive message indicating that the zoom intensity must be a positive number.
- If output_width or output_height is less than or equal to zero, raise a ValueError indicating that output dimensions must be positive integers.

These guards protect against corrupt GlobalSettings values or programming errors in the caller.

### Step 3 — Implement the Crop Box Formula

Apply the crop box calculation using the standard Ken Burns relationship:

- crop_width equals output_width divided by zoom_intensity, converted to an integer using floor division (the int constructor in Python truncates toward zero, which is equivalent to floor for positive values).
- crop_height equals output_height divided by zoom_intensity, converted to an integer in the same manner.

For the default values of 1920 by 1080 at zoom intensity 1.3, this produces crop dimensions of approximately 1476 by 830 pixels. The crop box is smaller than the output, so when this smaller crop region is resized up to fill the full output resolution, the viewer perceives a zoomed-in view of the source image.

When zoom_intensity is exactly 1.0, the crop dimensions equal the output dimensions, meaning no zoom occurs — the crop covers the entire output area. This edge case is valid and should produce a functional (though visually static) Ken Burns clip.

### Step 4 — Ensure Integer Output

The returned crop_width and crop_height must always be positive integers. After computing the values, add an assertion or guard that both values are at least 1 pixel. In practice, this should always be true as long as zoom_intensity and output dimensions are valid, but the guard protects against floating-point edge cases with extremely high zoom values.

### Step 5 — Add Debug Logging

Log the computed crop dimensions at DEBUG level, including the input parameters and the resulting values. This aids troubleshooting when the Ken Burns effect produces unexpected framing.

---

## Expected Output

The function calculate_crop_dimensions is defined in backend/core_engine/ken_burns.py. Given standard inputs:

- calculate_crop_dimensions(1920, 1080, 1.3) returns (1476, 830).
- calculate_crop_dimensions(1920, 1080, 1.0) returns (1920, 1080).
- calculate_crop_dimensions(1920, 1080, 2.0) returns (960, 540).
- calculate_crop_dimensions(1920, 1080, 0.0) raises ValueError.
- calculate_crop_dimensions(1920, 1080, -1.0) raises ValueError.

---

## Validation

- [ ] The function calculate_crop_dimensions exists in ken_burns.py.
- [ ] It accepts output_width, output_height, and zoom_intensity as parameters.
- [ ] It returns a tuple of two positive integers (crop_width, crop_height).
- [ ] For zoom 1.3 at 1920x1080, the result is approximately (1476, 830).
- [ ] For zoom 1.0, the crop dimensions equal the output dimensions.
- [ ] For zoom 2.0 at 1920x1080, the result is (960, 540).
- [ ] ValueError is raised when zoom_intensity is zero or negative.
- [ ] ValueError is raised when output dimensions are non-positive.
- [ ] The function has a docstring and type hints.

---

## Notes

- The crop box dimensions define how much of the source image is visible in any single frame. A smaller crop box (higher zoom) means more zoom-in and potentially more visible pan motion, but also requires a larger source image to avoid the crop box exceeding image boundaries.
- The relationship between crop dimensions and the source image minimum size is: the source image must be at least crop_width by crop_height pixels at the position farthest from the center. The load_and_prepare_image function (Task 04.02.07) handles ensuring the source image is large enough.
- Floor division (truncation) is used rather than rounding to ensure the crop box is never larger than the mathematically exact value. A crop box that is one pixel too large could cause an off-by-one error when positioned at the maximum coordinate.

---

> **Parent:** [SubPhase_04_02_Overview.md](./SubPhase_04_02_Overview.md) (Layer 2)
> **Phase:** [Phase_04_Overview.md](../Phase_04_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
