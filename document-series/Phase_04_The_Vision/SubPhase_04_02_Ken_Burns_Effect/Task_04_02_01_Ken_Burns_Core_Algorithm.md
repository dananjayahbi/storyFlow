# Task 04.02.01 — Ken Burns Core Algorithm

## Metadata

| Field         | Value                                                                |
| ------------- | -------------------------------------------------------------------- |
| **Task ID**   | 04.02.01                                                             |
| **Task Name** | Ken Burns Core Algorithm                                             |
| **Sub-Phase** | 04.02 — Ken Burns Effect Implementation                              |
| **Phase**     | Phase 04 — The Vision: Video Rendering Engine                        |
| **Complexity**| High                                                                 |
| **Dependencies** | SubPhase 04.01 complete (MoviePy installed, render pipeline functional, ken_burns.py stub exists) |
| **Parent**    | [SubPhase_04_02_Overview.md](./SubPhase_04_02_Overview.md)           |

---

## Objective

Replace the existing stub implementation of ken_burns.py with the full Ken Burns algorithm module. This task creates the foundational module file, defines the primary apply_ken_burns entry-point function, handles MoviePy version compatibility for imports, and establishes the orchestration flow that the remaining SubPhase 04.02 helper functions will plug into. The apply_ken_burns function serves as the single public interface that the video renderer calls for each segment, receiving an image path, duration, resolution, zoom intensity, FPS, and segment index, and returning a fully constructed MoviePy VideoClip with animated camera motion.

---

## Instructions

### Step 1 — Remove Stub Content

Open the existing ken_burns.py file located at backend/core_engine/ken_burns.py. This file currently contains a placeholder stub created during the Phase 01 scaffolding step. Delete the entire stub content. The file will be rebuilt from scratch as a complete, production-ready module.

### Step 2 — Write Module-Level Docstring and Imports

Begin the module with a docstring that explains the purpose of the Ken Burns effect algorithm module: it provides zoom-and-pan animation for still images used in narrative video segments. The module converts static cover images into MoviePy VideoClip objects with per-frame camera motion computed through linear interpolation of crop-box positions.

Add the necessary imports. The module requires:

- logging (standard library) for structured debug and info messages throughout the algorithm.
- numpy for array manipulation — specifically for slicing the source image to extract crop regions and for holding the prepared image data in memory as a NumPy array.
- PIL (Pillow) for image loading via Image.open, image resizing via Image.resize with LANCZOS resampling, and RGB conversion.
- MoviePy for constructing the output VideoClip. Because MoviePy 1.0.3 and 2.0 have different import paths, the module must attempt importing VideoClip from moviepy.editor first, and if that import fails (ImportError), fall back to importing from moviepy. This try/except pattern ensures the module works across both MoviePy versions without requiring the developer to know which version is installed.

Create a module-level logger instance using logging.getLogger with the module name.

### Step 3 — Define the DIRECTIONS Constant

Define a module-level constant named DIRECTIONS as a tuple of seven two-element tuples. Each inner tuple contains a start-position name and an end-position name representing a camera pan trajectory. The seven predefined directions are:

1. center to center (zoom-only, no pan)
2. top_left to bottom_right (diagonal pan)
3. bottom_right to top_left (reverse diagonal)
4. top_right to bottom_left (opposite diagonal)
5. bottom_left to top_right (reverse opposite diagonal)
6. center to top_left (drift upward-left)
7. center to bottom_right (drift downward-right)

This constant is consumed by the get_pan_direction helper function (Task 04.02.04) and must remain immutable. The order matters because segment_index modulo 7 determines which direction each segment receives, and the sequence is designed to provide visual variety across consecutive segments.

### Step 4 — Define the apply_ken_burns Function Signature

Create the main public function named apply_ken_burns. It accepts six parameters:

- image_path (str): absolute file system path to the source cover image for this segment.
- duration (float): length in seconds that this clip should play, matching the corresponding audio duration.
- resolution (tuple of two ints): output video dimensions as (width, height), for example (1920, 1080).
- zoom_intensity (float): the zoom factor read from GlobalSettings, defaulting to 1.3. A value of 1.0 means no zoom (crop equals output), values above 1.0 mean the crop box is smaller than the output, creating a zoom-in effect.
- fps (int): frames per second for the output VideoClip, matching the project framerate setting.
- segment_index (int): the zero-based index of this segment within the project, used to deterministically select the pan direction.

The function returns a MoviePy VideoClip instance with the specified duration and FPS, whose make_frame callback generates each frame by interpolating the camera position and extracting the appropriate crop from the source image.

Add a comprehensive docstring to this function explaining the parameter semantics, return type, and the high-level algorithm flow.

### Step 5 — Implement the Orchestration Logic

Inside apply_ken_burns, implement the following sequential orchestration steps. Each step calls a helper function that is defined in subsequent tasks (04.02.02 through 04.02.07). For now, the function body should reference these helpers by their intended names, assuming they will be defined in the same module:

1. Load and prepare the source image by calling load_and_prepare_image with the image_path, resolution, and zoom_intensity. This returns a NumPy array of the source image, upscaled if necessary to provide sufficient zoom headroom.

2. Calculate crop dimensions by calling calculate_crop_dimensions with the output width, output height, and zoom_intensity. This returns the width and height of the crop box that will be extracted from the source image on each frame.

3. Select the pan direction by calling get_pan_direction with the segment_index. This returns a tuple of two position names (start_name, end_name) indicating where the camera begins and ends its motion.

4. Compute the start and end pixel coordinates by calling get_start_end_coords with the start_name, end_name, source image width, source image height, crop width, and crop height. This returns two tuples: (start_x, start_y) and (end_x, end_y) representing the top-left corner of the crop box at the beginning and end of the clip.

5. Define the make_frame closure (Task 04.02.06) that captures the source image array, start coordinates, end coordinates, crop dimensions, output resolution, and duration. This closure is called by MoviePy for every frame during rendering.

6. Construct the VideoClip by passing the make_frame closure, set its duration, and set its FPS. Return this clip.

### Step 6 — Add Logging Throughout

Add logging statements at key points in the orchestration flow:

- Log at INFO level when apply_ken_burns is called, including the image path, duration, resolution, zoom intensity, and segment index.
- Log at DEBUG level after each helper function returns, showing the computed values (crop dimensions, selected direction, start/end coordinates).
- Log at DEBUG level the total expected frame count (duration multiplied by FPS, cast to integer) before returning the clip.

These log messages are essential for debugging rendering issues since the Ken Burns algorithm involves multiple interacting computations where a mistake in any one produces visually incorrect but non-crashing results.

### Step 7 — Ensure Pure Computation Boundary

The apply_ken_burns function and all its helpers must be pure computation functions with no Django ORM access. The zoom_intensity value is passed in as a parameter by the caller (video_renderer.py), which reads it from GlobalSettings (Task 04.02.09). This separation ensures the ken_burns module can be tested independently without a Django database, and keeps the mathematical algorithm decoupled from the web framework.

The only I/O operation within the ken_burns module is reading the source image file from disk (in load_and_prepare_image). All other operations are in-memory computations on NumPy arrays and Pillow Image objects.

---

## Expected Output

After completing this task, the file backend/core_engine/ken_burns.py contains:

- A module-level docstring explaining the Ken Burns effect module.
- All necessary imports with MoviePy version compatibility handling.
- A module-level logger instance.
- The DIRECTIONS constant with seven predefined pan direction tuples.
- The apply_ken_burns function with full signature, docstring, orchestration logic calling helper functions, structured logging, and VideoClip construction.
- Placeholder function stubs (or forward references) for the helper functions that will be implemented in Tasks 04.02.02 through 04.02.07.

The module replaces the previous stub entirely. At this point, the module is not yet functional because the helper functions are stubs — it becomes functional after Tasks 04.02.02 through 04.02.07 are completed.

---

## Validation

- [ ] The file backend/core_engine/ken_burns.py exists and is no longer a stub.
- [ ] The apply_ken_burns function is defined with the correct six-parameter signature.
- [ ] The function returns a MoviePy VideoClip instance (once helpers are implemented).
- [ ] The DIRECTIONS constant contains exactly seven tuples of two-string tuples.
- [ ] MoviePy imports are wrapped in a try/except for version compatibility.
- [ ] The module contains no Django ORM imports or database access.
- [ ] All functions have docstrings and type hints.
- [ ] Logging statements are present at INFO and DEBUG levels.

---

## Notes

- This task establishes the skeleton that all other SubPhase 04.02 tasks fill in. The execution order is critical: this task must be completed first before any of the helper function tasks (04.02.02–04.02.07) can begin.
- The DIRECTIONS constant uses string identifiers (center, top_left, etc.) rather than raw pixel coordinates. The mapping from names to pixel coordinates happens in the position_to_coords function (Task 04.02.05), which provides a clean separation between direction semantics and pixel-level computation.
- The module deliberately avoids randomness. Direction selection is deterministic based on segment_index modulo 7, ensuring that re-rendering the same project produces identical output. This is critical for reproducibility and testability.
- The try/except import pattern for MoviePy may produce IDE warnings about unused imports. This is acceptable and should be documented with an inline comment explaining the version compatibility intent.

---

> **Parent:** [SubPhase_04_02_Overview.md](./SubPhase_04_02_Overview.md) (Layer 2)
> **Phase:** [Phase_04_Overview.md](../Phase_04_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
