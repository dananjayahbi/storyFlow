# Task 04.01.03 — Image Cover Resize Logic

> **Sub-Phase:** 04.01 — Basic Video Assembly
> **Phase:** Phase 04 — The Vision
> **Complexity:** Medium
> **Dependencies:** Task 04.01.01 (Render Utils Module)
> **Parent Document:** [SubPhase_04_01_Overview.md](./SubPhase_04_01_Overview.md)

---

## Objective

Implement the "cover" resize algorithm that scales and center-crops any image to fill the target resolution (1920×1080 by default) exactly, preventing letterboxing or black bars — equivalent to CSS `object-fit: cover`.

---

## Instructions

### Step 1 — Load and convert the image

In `backend/core_engine/render_utils.py`, implement `resize_image_to_resolution(image_path: str, width: int, height: int) -> np.ndarray`. Open the image with `PIL.Image.open(image_path).convert("RGB")`. The `.convert("RGB")` call handles RGBA images (strips alpha) and grayscale images (converts to 3 channels).

### Step 2 — Calculate aspect ratios

Compute the source aspect ratio (`src_width / src_height`) and the target aspect ratio (`target_width / target_height`). These ratios determine whether the image needs to be cropped horizontally or vertically.

### Step 3 — Implement the cover resize algorithm

Apply the following logic:
- If the source ratio is greater than the target ratio (image is relatively wider), scale the image so its height matches the target height. The width will be larger than needed, so crop equal amounts from the left and right edges.
- If the source ratio is less than or equal to the target ratio (image is relatively taller or the same), scale the image so its width matches the target width. The height will be larger than needed, so crop equal amounts from the top and bottom.

Use `Image.Resampling.LANCZOS` for high-quality resampling on both upscaling and downscaling.

### Step 4 — Center-crop to exact dimensions

After scaling, center-crop the image to the exact target dimensions. Calculate the left and top offsets as half the difference between the scaled dimension and the target dimension. Use Pillow's `.crop((left, top, left + target_width, top + target_height))` method.

### Step 5 — Convert to NumPy array

Convert the final Pillow image to a NumPy array with `np.array(cropped_image)`. The result must have shape `(height, width, 3)` and dtype `uint8`. This format is directly consumed by MoviePy's `ImageClip`.

### Step 6 — Handle edge cases

- Image already matches target dimensions: skip resize, just convert to NumPy.
- Image is smaller than target in both dimensions: upscale using LANCZOS.
- Corrupted or unreadable image: raise a descriptive `ValueError` with the file path.

### Step 7 — Validate the output

Assert that the returned array's shape is exactly `(height, width, 3)` and dtype is `uint8` before returning. This guards against subtle resize bugs.

---

## Expected Output

```
backend/
└── core_engine/
    └── render_utils.py ← MODIFIED
```

---

## Validation

- [ ] 16:9 source (2560×1440) → 1920×1080: output shape is `(1080, 1920, 3)`.
- [ ] 4:3 source (1600×1200) → 1920×1080: output shape is `(1080, 1920, 3)`, top/bottom cropped.
- [ ] 1:1 source (1080×1080) → 1920×1080: output shape is `(1080, 1920, 3)`, top/bottom cropped.
- [ ] Portrait source (800×1200) → 1920×1080: output shape is `(1080, 1920, 3)`, top/bottom cropped.
- [ ] RGBA image → converted to RGB (3 channels, no alpha).
- [ ] Grayscale image → converted to RGB (3 channels).
- [ ] Output dtype is always `uint8`.
- [ ] Corrupted image raises `ValueError`.

---

## Notes

- The "cover" algorithm is identical to CSS `object-fit: cover`. The image always fills the entire frame with no black bars, at the cost of cropping some content from the edges.
- `Image.Resampling.LANCZOS` is the highest-quality resampling filter available in Pillow. It is appropriate for both downscaling (most common) and upscaling.
- Do NOT use OpenCV for image loading — it produces BGR arrays, which would require an extra conversion step. Pillow's RGB output aligns directly with MoviePy's expected format.

---

> **Parent:** [SubPhase_04_01_Overview.md](./SubPhase_04_01_Overview.md) (Layer 2)
> **Phase:** [Phase_04_Overview.md](../Phase_04_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_04_01_02_FFmpeg_Availability_Check.md](./Task_04_01_02_FFmpeg_Availability_Check.md)
> **Next Task:** [Task_04_01_04_Implement_Video_Renderer.md](./Task_04_01_04_Implement_Video_Renderer.md)
