# Task 04.02.06 — Make Frame Callback

## Metadata

| Field         | Value                                                                |
| ------------- | -------------------------------------------------------------------- |
| **Task ID**   | 04.02.06                                                             |
| **Task Name** | Make Frame Callback                                                  |
| **Sub-Phase** | 04.02 — Ken Burns Effect Implementation                              |
| **Phase**     | Phase 04 — The Vision: Video Rendering Engine                        |
| **Complexity**| High                                                                 |
| **Dependencies** | Task 04.02.03 (interpolation), Task 04.02.05 (position coordinates), Task 04.02.07 (prepared image) |
| **Parent**    | [SubPhase_04_02_Overview.md](./SubPhase_04_02_Overview.md)           |

---

## Objective

Implement the make_frame closure within the apply_ken_burns function in ken_burns.py. This closure is the heart of the Ken Burns effect — it is called by MoviePy once for every frame during video rendering, and it must return a NumPy array representing the rendered frame at time t. The closure captures the pre-computed source image, start and end coordinates, crop dimensions, output resolution, and duration from its enclosing scope, then uses linear interpolation to determine the current crop position, extracts the crop from the source image using NumPy array slicing, and resizes the crop to the output resolution using Pillow LANCZOS resampling.

---

## Instructions

### Step 1 — Define the Closure Inside apply_ken_burns

Within the apply_ken_burns function body (after all pre-computations from Tasks 04.02.02 through 04.02.07 have been performed), define an inner function named make_frame that accepts a single parameter t (float representing the current time in seconds). This function must be defined as a closure so it can capture the following variables from the enclosing scope:

- source_image: the prepared NumPy array of the source image (from load_and_prepare_image).
- start_coords: the (x, y) tuple of the crop-box starting position.
- end_coords: the (x, y) tuple of the crop-box ending position.
- crop_w and crop_h: the crop box dimensions (from calculate_crop_dimensions).
- output_width and output_height: extracted from the resolution parameter of apply_ken_burns.
- duration: the clip duration in seconds.

The closure pattern is essential because MoviePy's VideoClip stores a reference to this function and calls it repeatedly during rendering. All per-segment data must be captured at definition time, not passed as arguments (since MoviePy only passes t).

### Step 2 — Interpolate the Current Position

As the first operation inside make_frame, call interpolate_position with the captured start_coords, end_coords, the current time t, and the duration. This returns a tuple of two floats representing the crop-box top-left corner at the current moment.

Convert the float coordinates to integer pixel coordinates using int(round(x)) and int(round(y)). Rounding (rather than truncating) provides the most accurate pixel selection because the true position often falls between two pixels, and rounding selects the nearer one.

### Step 3 — Clamp Coordinates to Valid Bounds

After rounding, clamp both coordinates to ensure the crop box remains entirely within the source image boundaries:

- x must be at least 0 and at most (source image width minus crop_w).
- y must be at least 0 and at most (source image height minus crop_h).

This clamping is a safety net against floating-point edge cases where interpolation might produce a position infinitesimally outside the valid range. Use the max and min built-in functions for clamping.

### Step 4 — Extract the Crop Region

Use NumPy array slicing to extract the crop region from the source image. The slice operation uses the standard NumPy indexing convention where the first axis is rows (y) and the second axis is columns (x):

- The crop is source_image sliced from y to y plus crop_h along the first axis, and from x to x plus crop_w along the second axis.

This slicing operation is extremely efficient — NumPy creates a view into the existing array rather than copying data, making it an O(1) operation regardless of the crop size. The actual data copy happens in the subsequent resize step.

### Step 5 — Resize the Crop to Output Resolution

Convert the NumPy crop array to a Pillow Image object using Image.fromarray. Then resize this image to the output resolution (output_width by output_height) using Image.Resampling.LANCZOS as the resampling filter. LANCZOS produces the highest quality upscaling with minimal aliasing artifacts.

Convert the resized Pillow Image back to a NumPy array for return. The resulting array must have shape (output_height, output_width, 3) with dtype uint8, matching MoviePy's expected frame format. Note the shape convention: height comes first in NumPy array dimensions, followed by width, followed by channels.

### Step 6 — Return the Frame Array

Return the NumPy array from make_frame. MoviePy uses this array directly as the frame data for the current timestamp. The array must be contiguous in memory and have the correct dtype (uint8) and shape (h, w, 3). If the array is not contiguous (which can happen after certain NumPy operations), call np.ascontiguousarray on it before returning.

### Step 7 — Wire the Closure into VideoClip

After defining the make_frame closure, construct a MoviePy VideoClip by passing make_frame as the frame-generating function. Set the clip's duration to the duration parameter and its FPS to the fps parameter. Return this VideoClip from apply_ken_burns.

The VideoClip construction differs slightly between MoviePy versions:

- In MoviePy 1.0.3, VideoClip accepts make_frame as a positional argument, and duration and fps are set via method chaining (set_duration and set_fps) or as constructor keyword arguments.
- In MoviePy 2.0, the constructor interface may differ. The try/except import pattern from Task 04.02.01 handles version differences at the import level, and the constructor call should use whichever interface is available.

---

## Expected Output

After completing this task, the make_frame closure is fully implemented within apply_ken_burns. When MoviePy calls make_frame(t) for any value of t between 0 and the clip duration:

- The closure computes the interpolated crop position for time t.
- It extracts a crop_w by crop_h region from the source image at that position.
- It resizes the crop to output_width by output_height using LANCZOS.
- It returns a NumPy array of shape (output_height, output_width, 3) with dtype uint8.

For a non-center direction, frames at different times show different regions of the source image, creating visible camera motion. For the center-to-center direction, all frames show the same zoomed-in center region.

---

## Validation

- [ ] make_frame is defined as a closure inside apply_ken_burns.
- [ ] It accepts a single parameter t (float).
- [ ] It calls interpolate_position with the correct arguments.
- [ ] Coordinates are converted to integers using int(round(...)).
- [ ] Coordinates are clamped to valid bounds before array slicing.
- [ ] NumPy slicing uses the correct [y:y+h, x:x+w] convention.
- [ ] The crop is resized to output resolution using Pillow LANCZOS.
- [ ] The returned array has shape (output_height, output_width, 3) and dtype uint8.
- [ ] The VideoClip is constructed with make_frame, duration, and fps.
- [ ] Frames at t equals 0 and t equals duration differ for non-center directions.
- [ ] Frames at t equals 0 and t equals duration are identical for center-to-center direction.

---

## Notes

- The make_frame closure is called once per frame during rendering. For a 5-second clip at 30 FPS, this means 150 calls. Each call involves one interpolation (trivial), one NumPy slice (O(1) view), one Pillow Image creation from array, one Pillow resize (the expensive step), and one conversion back to NumPy array. The per-frame cost is dominated by the Pillow resize operation, which typically takes 5-15 milliseconds for 1080p output.
- The NumPy array indexing convention (y first, x second) is a common source of bugs. The source image is stored as shape (height, width, channels), so slicing must be [y:y+crop_h, x:x+crop_w], not [x:x+crop_w, y:y+crop_h]. Getting this wrong would produce a visually incorrect crop from the wrong image region.
- MoviePy may call make_frame with t values slightly beyond the clip duration due to floating-point precision. The interpolation clamping (Task 04.02.03) and the coordinate clamping in this task together ensure that such edge cases do not cause index-out-of-bounds errors.
- The closure captures variable references, not values. If any captured variable were mutated after the closure is defined but before make_frame is called, the closure would see the mutated value. In practice this is not a concern because all captured values are computed once and never modified, but it is important to understand for debugging purposes.

---

> **Parent:** [SubPhase_04_02_Overview.md](./SubPhase_04_02_Overview.md) (Layer 2)
> **Phase:** [Phase_04_Overview.md](../Phase_04_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
