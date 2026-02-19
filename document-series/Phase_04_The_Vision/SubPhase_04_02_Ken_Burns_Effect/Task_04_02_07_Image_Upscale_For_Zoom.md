# Task 04.02.07 — Image Upscale For Zoom

## Metadata

| Field         | Value                                                                |
| ------------- | -------------------------------------------------------------------- |
| **Task ID**   | 04.02.07                                                             |
| **Task Name** | Image Upscale For Zoom                                               |
| **Sub-Phase** | 04.02 — Ken Burns Effect Implementation                              |
| **Phase**     | Phase 04 — The Vision: Video Rendering Engine                        |
| **Complexity**| Medium                                                               |
| **Dependencies** | Task 04.02.02 (crop dimensions inform minimum image size requirements) |
| **Parent**    | [SubPhase_04_02_Overview.md](./SubPhase_04_02_Overview.md)           |

---

## Objective

Implement the load_and_prepare_image function within the ken_burns.py module. This function loads a source image from disk, ensures it meets the minimum size requirements for Ken Burns animation at the given zoom intensity and output resolution, upscales it if necessary using Pillow LANCZOS resampling, applies a center-crop to the target minimum dimensions for consistent memory usage, and returns the prepared image as a NumPy array. This function is called once per segment before the make_frame loop begins, so its performance is not frame-rate-critical.

---

## Instructions

### Step 1 — Define the Function Signature

Create a function named load_and_prepare_image within backend/core_engine/ken_burns.py. The function accepts three parameters:

- image_path (str): the absolute file system path to the source cover image.
- resolution (tuple of two ints): the output video dimensions as (width, height).
- zoom_intensity (float): the zoom factor, used to determine the minimum image size.

The function returns a NumPy array of shape (height, width, 3) with dtype uint8, representing the prepared RGB image.

Add a docstring explaining the zoom-headroom concept and the upscaling/cropping logic.

### Step 2 — Load the Image

Open the image file using Pillow's Image.open with the provided image_path. Immediately convert the image to RGB mode using the convert method. This handles source images that may be in RGBA (with transparency), grayscale, palette mode, or other formats — the Ken Burns algorithm always works with 3-channel RGB data. If the image file cannot be opened or is corrupted, let the Pillow exception propagate, but wrap it in a ValueError with a descriptive message that includes the file path so the error can be traced back to a specific segment.

### Step 3 — Calculate Minimum Required Dimensions

The minimum image dimensions for Ken Burns animation are the output resolution multiplied by the zoom intensity:

- min_w equals the output width multiplied by zoom_intensity, cast to an integer.
- min_h equals the output height multiplied by zoom_intensity, cast to an integer.

For example, at 1920 by 1080 output with zoom intensity 1.3, the minimum image size is 2496 by 1404 pixels. This ensures that the crop box (1476 by 830 at this zoom) can be positioned at any of the five defined positions (corners and center) without extending outside the image boundaries.

### Step 4 — Determine Whether Upscaling Is Needed

Compare the source image dimensions (obtained from the Pillow Image's size attribute, which returns width then height) against the minimum required dimensions:

- If the source width is greater than or equal to min_w AND the source height is greater than or equal to min_h, the image is large enough and no upscaling is needed.
- If either dimension is smaller than the minimum, the image must be upscaled.

### Step 5 — Upscale If Necessary

When upscaling is required, calculate the uniform scale factor needed to bring the smaller dimension up to the minimum. The scale factor is the maximum of min_w divided by source_width and min_h divided by source_height. Using the maximum ensures both dimensions meet or exceed the minimum after scaling.

Compute the new dimensions by multiplying the source dimensions by this scale factor and converting to integers. Resize the image using Pillow's resize method with LANCZOS resampling for the highest quality upscaling.

Log an INFO-level message when upscaling occurs, including the original dimensions, the new dimensions, and the minimum required dimensions. This alerts developers that source images may be lower quality than ideal.

### Step 6 — Apply Cover Crop to Minimum Dimensions

After upscaling (or if the image was already large enough), the image may exceed the minimum dimensions in one or both axes. To limit memory usage during frame generation, center-crop the image to exactly min_w by min_h. This cover-crop logic is:

- Calculate the horizontal offset as (image width minus min_w) divided by 2.
- Calculate the vertical offset as (image height minus min_h) divided by 2.
- Crop the image using Pillow's crop method with the box (left, upper, right, lower) computed from these offsets.

However, if the image is only moderately larger than the minimum (within 50 percent extra — meaning image dimensions are less than min_w times 1.5 by min_h times 1.5), keep the full image without cropping. The extra pixels provide slightly better quality during the crop-and-resize step in make_frame. Only crop if the image is significantly larger than needed, to prevent loading massive images (such as 8000 by 6000 pixels) entirely into RAM.

### Step 7 — Handle Edge Cases

Address the following special situations:

- Image is exactly the minimum size: no upscaling needed, but the crop box has zero movement range in that axis. This means the Ken Burns effect reduces to zoom-only (no pan) in that dimension. Log a warning at DEBUG level.
- Image is much larger than the minimum (for example, 8000 by 6000 when only 2496 by 1404 is needed): downscale or crop to a reasonable working size as described in Step 6 to prevent excessive memory consumption.
- Corrupted or unreadable image file: raise a ValueError with the file path included in the message so the error can be diagnosed.
- Image is in RGBA mode: the convert("RGB") call in Step 2 handles this automatically by dropping the alpha channel.

### Step 8 — Convert to NumPy Array and Return

Convert the final Pillow Image to a NumPy array using np.array. The resulting array has shape (height, width, 3) with dtype uint8. This array is what make_frame will slice into on every frame. Return this array.

---

## Expected Output

The function load_and_prepare_image is defined in backend/core_engine/ken_burns.py. Given various inputs:

- A 3000 by 2000 source image at 1920x1080 output with zoom 1.3: no upscaling needed (3000 is greater than 2496 and 2000 is greater than 1404). Image is kept at full size or cropped slightly for memory efficiency. Returns a NumPy array.
- A 400 by 300 source image at 640x360 output with zoom 1.3 (minimum 832x468): image is upscaled by a factor of approximately 2.08 (832/400) to at least 832 by 624, then center-cropped to 832 by 468. Returns a NumPy array.
- A corrupted file path: raises ValueError with the file path.

---

## Validation

- [ ] The function load_and_prepare_image exists in ken_burns.py.
- [ ] It loads images using Pillow and converts to RGB.
- [ ] Images smaller than the minimum are upscaled using LANCZOS.
- [ ] The upscale factor ensures both dimensions meet the minimum.
- [ ] Very large images are optionally cropped to limit memory usage.
- [ ] An INFO log message is emitted when upscaling occurs.
- [ ] Corrupted or unreadable images raise ValueError with the file path.
- [ ] The returned NumPy array has shape (H, W, 3) and dtype uint8.
- [ ] RGBA images are correctly converted to RGB.
- [ ] The function has a docstring and type hints.

---

## Notes

- This function is called once per segment, not once per frame. Its performance is therefore not frame-rate-critical. A 50-millisecond image load and resize is negligible compared to the frame generation time for a multi-second clip.
- The "zoom headroom" concept is central to the Ken Burns effect: the source image must be larger than the output resolution by a factor of zoom_intensity so that the crop box (which is output_size divided by zoom) can be positioned at any corner without extending outside the image. Without this headroom, corner positions would produce black bars or crashes from out-of-bounds array access.
- Upscaling a small source image degrades visual quality because new pixels are interpolated rather than containing real image data. The Ken Burns motion helps mask this quality loss by keeping the viewer's attention on the movement rather than pixel-level detail. However, developers should be aware that very small source images (for example, 200 by 150) will look noticeably blurry even with LANCZOS upscaling.
- The cover-crop step after upscaling maintains a consistent aspect ratio. Without it, a 4:3 source image upscaled for 16:9 output would have extra vertical space, causing the crop box to wander into regions that do not correspond to the output aspect ratio.

---

> **Parent:** [SubPhase_04_02_Overview.md](./SubPhase_04_02_Overview.md) (Layer 2)
> **Phase:** [Phase_04_Overview.md](../Phase_04_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
