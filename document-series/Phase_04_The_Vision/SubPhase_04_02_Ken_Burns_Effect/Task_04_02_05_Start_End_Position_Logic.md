# Task 04.02.05 — Start End Position Logic

## Metadata

| Field         | Value                                                                |
| ------------- | -------------------------------------------------------------------- |
| **Task ID**   | 04.02.05                                                             |
| **Task Name** | Start End Position Logic                                             |
| **Sub-Phase** | 04.02 — Ken Burns Effect Implementation                              |
| **Phase**     | Phase 04 — The Vision: Video Rendering Engine                        |
| **Complexity**| Medium                                                               |
| **Dependencies** | Task 04.02.02 (crop dimensions needed for coordinate calculation), Task 04.02.04 (direction names needed as input) |
| **Parent**    | [SubPhase_04_02_Overview.md](./SubPhase_04_02_Overview.md)           |

---

## Objective

Implement the position_to_coords and get_start_end_coords functions within the ken_burns.py module. These functions translate the human-readable position names (center, top_left, top_right, bottom_left, bottom_right) into concrete pixel coordinates that define where the crop box is placed on the source image. The position_to_coords function handles the mapping for a single position name, while get_start_end_coords is a convenience wrapper that computes both start and end coordinates in a single call, ready for use by the interpolation function.

---

## Instructions

### Step 1 — Define the position_to_coords Function

Create a function named position_to_coords within backend/core_engine/ken_burns.py. The function accepts five parameters:

- position (str): one of the five recognized position names — center, top_left, top_right, bottom_left, or bottom_right.
- img_w (int): the width of the prepared source image in pixels.
- img_h (int): the height of the prepared source image in pixels.
- crop_w (int): the width of the crop box in pixels (from calculate_crop_dimensions).
- crop_h (int): the height of the crop box in pixels (from calculate_crop_dimensions).

The function returns a tuple of two integers: (x, y) representing the top-left corner of the crop box when placed at the specified position.

Add a docstring explaining how each position name maps to coordinates and the meaning of max_x and max_y.

### Step 2 — Compute Maximum Coordinates

Before mapping position names, calculate the maximum valid crop-box coordinates:

- max_x equals img_w minus crop_w. This is the rightmost x-coordinate where the crop box can be placed without exceeding the image width.
- max_y equals img_h minus crop_h. This is the bottommost y-coordinate where the crop box can be placed without exceeding the image height.

These maximum values define the movement range of the crop box. If max_x or max_y is zero, the crop box fits exactly in that dimension with no room for horizontal or vertical movement respectively. If either is negative, the source image is too small for the given crop dimensions, which should not happen if load_and_prepare_image (Task 04.02.07) has been called correctly.

### Step 3 — Implement Position Name Mapping

Map each position name to pixel coordinates as follows:

- "top_left" maps to (0, 0). The crop box is in the upper-left corner of the source image.
- "top_right" maps to (max_x, 0). The crop box is in the upper-right corner.
- "bottom_left" maps to (0, max_y). The crop box is in the lower-left corner.
- "bottom_right" maps to (max_x, max_y). The crop box is in the lower-right corner.
- "center" maps to (max_x // 2, max_y // 2). The crop box is centered on the source image. Integer division is used to keep coordinates as whole numbers.

If the position name does not match any of the five recognized names, raise a ValueError with a descriptive message listing the valid position names.

### Step 4 — Handle Degenerate Cases

When max_x or max_y is zero, certain positions collapse to the same coordinates. For example, if max_x is zero, both top_left and top_right produce x equals 0 because there is no horizontal movement range. This is valid behavior — it means the Ken Burns effect can only pan vertically (or not at all if both are zero). Log a warning at DEBUG level if either max_x or max_y is zero to alert developers that the source image may be too small for meaningful pan motion in that axis.

### Step 5 — Define the get_start_end_coords Wrapper

Create a convenience function named get_start_end_coords that accepts:

- start_name (str): the position name for the start of the pan.
- end_name (str): the position name for the end of the pan.
- img_w, img_h, crop_w, crop_h: same as position_to_coords.

This function calls position_to_coords twice (once for start_name, once for end_name) and returns two tuples: (start_x, start_y) and (end_x, end_y). This wrapper simplifies the calling code in apply_ken_burns by combining two position lookups into a single function call.

### Step 6 — Validate Coordinate Bounds

Both functions must ensure all returned coordinates are non-negative. While the mapping logic inherently produces non-negative values for valid inputs, adding an explicit guard (clamping x and y to be at least 0) protects against unexpected edge cases. Coordinates must also not exceed max_x and max_y respectively, which is guaranteed by the mapping definitions.

---

## Expected Output

For a source image of 2496 by 1404 pixels with a crop box of 1476 by 830 pixels (corresponding to 1920x1080 output at zoom 1.3):

- max_x equals 1020, max_y equals 574.
- position_to_coords("center", 2496, 1404, 1476, 830) returns (510, 287).
- position_to_coords("top_left", 2496, 1404, 1476, 830) returns (0, 0).
- position_to_coords("top_right", 2496, 1404, 1476, 830) returns (1020, 0).
- position_to_coords("bottom_left", 2496, 1404, 1476, 830) returns (0, 574).
- position_to_coords("bottom_right", 2496, 1404, 1476, 830) returns (1020, 574).
- position_to_coords("middle_left", ...) raises ValueError.

get_start_end_coords("top_left", "bottom_right", 2496, 1404, 1476, 830) returns ((0, 0), (1020, 574)).

---

## Validation

- [ ] The function position_to_coords exists in ken_burns.py.
- [ ] It correctly maps all five position names to pixel coordinates.
- [ ] "center" maps to (max_x // 2, max_y // 2).
- [ ] "top_left" maps to (0, 0).
- [ ] "top_right" maps to (max_x, 0).
- [ ] "bottom_left" maps to (0, max_y).
- [ ] "bottom_right" maps to (max_x, max_y).
- [ ] Invalid position names raise ValueError.
- [ ] All returned coordinates are non-negative integers.
- [ ] The get_start_end_coords wrapper correctly returns two coordinate tuples.
- [ ] Both functions have docstrings and type hints.

---

## Notes

- The position names use underscores (top_left, not topLeft or top-left) to maintain consistency with Python naming conventions and the DIRECTIONS constant.
- The center coordinate uses integer division (max_x // 2), which rounds down. For an odd max_x (for example, 1021), center_x would be 510 rather than 510.5. This one-pixel discrepancy is visually imperceptible in a full-resolution video.
- The maximum coordinate values (max_x, max_y) represent the total movement range available for the crop box. Larger source images (or smaller crop boxes from higher zoom) produce larger movement ranges and more pronounced pan motion. This is why zoom_intensity affects both the zoom level and the pan distance simultaneously.
- These functions operate entirely in pixel-space integer arithmetic. The float interpolation between start and end positions happens in interpolate_position (Task 04.02.03), and the rounding back to integers for array indexing happens in make_frame (Task 04.02.06).

---

> **Parent:** [SubPhase_04_02_Overview.md](./SubPhase_04_02_Overview.md) (Layer 2)
> **Phase:** [Phase_04_Overview.md](../Phase_04_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
