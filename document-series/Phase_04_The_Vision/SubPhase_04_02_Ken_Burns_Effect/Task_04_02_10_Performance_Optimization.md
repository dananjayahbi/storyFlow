# Task 04.02.10 — Performance Optimization

## Metadata

| Field         | Value                                                                |
| ------------- | -------------------------------------------------------------------- |
| **Task ID**   | 04.02.10                                                             |
| **Task Name** | Performance Optimization                                             |
| **Sub-Phase** | 04.02 — Ken Burns Effect Implementation                              |
| **Phase**     | Phase 04 — The Vision: Video Rendering Engine                        |
| **Complexity**| High                                                                 |
| **Dependencies** | Task 04.02.06 (make_frame must be functional before optimization) |
| **Parent**    | [SubPhase_04_02_Overview.md](./SubPhase_04_02_Overview.md)           |

---

## Objective

Optimize the Ken Burns frame generation pipeline to achieve acceptable rendering speed on a modern CPU. The target is greater than 5 frames per second for 1080p output, which translates to approximately 30 to 90 seconds of total render time for a typical 12-segment project with 5-second segments. This task focuses on ensuring that computations are performed at the right granularity (once per segment versus once per frame), working image sizes are bounded, and the overall resource usage remains within the constraints of a local desktop application.

---

## Instructions

### Step 1 — Pre-Compute Start and End Positions

Verify that the start coordinates and end coordinates for the crop box are computed once in the apply_ken_burns function body, outside the make_frame closure. The make_frame closure captures these as immutable values and uses them on every frame call without re-computation.

If Tasks 04.02.01 through 04.02.06 were implemented correctly, this is already the case. The orchestration in apply_ken_burns calls get_start_end_coords once, stores the results, and the make_frame closure references them via closure capture. Confirm this pattern is in place and that no per-frame re-computation of positions, directions, or coordinates is occurring.

### Step 2 — Pre-Load the Source Image Once

Verify that load_and_prepare_image is called once in apply_ken_burns, before the make_frame closure is defined. The resulting NumPy array is captured by the closure and accessed on every frame via array slicing. No disk I/O should occur inside make_frame.

Confirm that the source image is stored as a NumPy array (not a Pillow Image) in the closure. NumPy array slicing creates a view rather than a copy, making the crop operation O(1). If the source image were stored as a Pillow Image, each crop would require a Pillow crop call which is slower than NumPy slicing.

### Step 3 — Verify NumPy Slicing for Crop

The crop operation inside make_frame should use NumPy array slicing (source_image[y:y+h, x:x+w]) rather than Pillow's crop method. NumPy slicing returns a memory view into the existing array, which is an O(1) operation regardless of the crop size. The actual data transfer happens during the subsequent Pillow resize step, which needs to read the crop pixels. This is the optimal approach within the current dependency constraints.

### Step 4 — Limit Working Image Size

In the load_and_prepare_image function (Task 04.02.07), add logic to limit the working image size when the source image is significantly larger than needed. If the source image exceeds the minimum required dimensions (output resolution times zoom_intensity) by more than 50 percent in both axes, downscale or center-crop it to approximately 1.5 times the minimum dimensions.

For example, at 1920 by 1080 with zoom 1.3, the minimum is 2496 by 1404. If the source image is 8000 by 6000, crop or downscale it to approximately 3744 by 2106 (1.5 times the minimum). This reduces the per-frame data volume without affecting visual quality, since the crop box only ever touches a 1476 by 830 region at any given position.

The 50-percent headroom beyond the minimum provides slightly better quality than cropping to exactly the minimum size, because it gives the crop box a small margin that avoids edge effects during LANCZOS resizing.

### Step 5 — Document Resize Quality vs Speed Tradeoff

The LANCZOS resampling filter used in make_frame produces the highest quality but is also the slowest option. Document the available alternatives and their tradeoffs for future reference:

- LANCZOS: highest quality, slowest. Best for final renders where visual quality is paramount.
- BILINEAR: good quality, approximately two times faster than LANCZOS. Acceptable for previews or draft renders.
- NEAREST: lowest quality (pixelated), fastest at approximately five times faster than LANCZOS. Only suitable for debugging or performance testing.

For the current implementation, LANCZOS is used for all renders. A future enhancement could add a "render quality" setting that selects the resampling filter, but this is out of scope for Phase 04.

### Step 6 — Avoid Unnecessary Per-Frame Object Creation

Review the make_frame implementation to minimize object creation per frame. The primary per-frame operations are:

- Creating a Pillow Image from the NumPy crop array (Image.fromarray). This is unavoidable since Pillow resize operates on Image objects, not raw arrays.
- Resizing the Image to output resolution. This is the core operation and cannot be eliminated.
- Converting the resized Image back to a NumPy array (np.array). This is unavoidable since MoviePy expects NumPy array frames.

These three steps represent the minimal required per-frame work within the current dependency constraints (Pillow and NumPy only, no OpenCV or SciPy). Document that alternative libraries (OpenCV's cv2.resize, scipy.ndimage.zoom) could reduce overhead but are explicitly excluded from the dependency list per project constraints.

### Step 7 — Add Performance Logging

At the end of apply_ken_burns (before returning the VideoClip), log a DEBUG-level message showing the expected frame count for this clip. The frame count is the clip duration multiplied by the FPS, cast to an integer. This helps with performance profiling — if rendering a specific segment takes unusually long, the frame count log narrows down whether the issue is duration, FPS, or per-frame cost.

### Step 8 — Verify Acceptable Performance Targets

The main performance bottleneck is the Pillow resize inside make_frame. Each frame requires resizing a crop of approximately 1477 by 831 pixels to 1920 by 1080 output. On a modern CPU, each resize operation takes approximately 5 to 15 milliseconds, giving a frame rate of approximately 67 to 200 frames per second — well above the 5 FPS minimum target.

For a 12-segment project with 5-second segments at 30 FPS, the total frame count is 1800 frames. At 10 milliseconds per frame, total frame generation takes approximately 18 seconds. Adding MP4 encoding overhead (approximately 2 to 5 times the frame generation time), total render time is approximately 36 to 90 seconds. This is acceptable for a local application.

Document these performance expectations in the module or in comments so future developers understand the baseline.

### Step 9 — Confirm No Multithreading or Caching

Explicitly confirm that the implementation does NOT use multithreading for frame generation. MoviePy calls make_frame sequentially and does not support parallel frame generation. Adding threading would create complexity without benefit.

Also confirm that frame caching is not implemented. For a 5-second clip at 30 FPS at 1080p, caching all frames would require approximately 150 frames times 1920 times 1080 times 3 bytes, which is approximately 935 megabytes. This is not feasible for a local desktop application.

---

## Expected Output

After completing this task, the Ken Burns rendering pipeline is verified to be optimally structured:

- All per-segment computations happen once in apply_ken_burns, not per frame.
- Source image is loaded once and stored as a NumPy array.
- Crop operations use NumPy array slicing (O(1) views).
- Working image size is bounded for memory efficiency.
- LANCZOS is used for quality, with documented alternatives for future speed modes.
- Performance expectations are documented (greater than 5 FPS for 1080p, 30 to 90 seconds for a typical project).
- No multithreading or frame caching is attempted.

---

## Validation

- [ ] Start and end coordinates are pre-computed once per segment, not per frame.
- [ ] Source image is loaded once per segment, not per frame.
- [ ] NumPy slicing is used for crop operations (not Pillow crop).
- [ ] Very large source images are bounded to a reasonable working size.
- [ ] LANCZOS resampling is used for quality, with alternatives documented.
- [ ] Per-frame object creation is minimized to the unavoidable minimum.
- [ ] A DEBUG log shows expected frame count per clip.
- [ ] No multithreading is used for frame generation.
- [ ] No frame caching is implemented.
- [ ] Rendering achieves greater than 5 FPS for 1080p output on a modern CPU.

---

## Notes

- This task is primarily a verification and refinement task rather than a new-feature task. If Tasks 04.02.01 through 04.02.07 were implemented correctly, most of the optimizations described here are already in place. The task ensures this is the case and documents the performance characteristics.
- The 5 FPS target is conservative and should be easily achieved. On modern hardware (Intel i5/i7, AMD Ryzen 5/7 or better), frame generation typically exceeds 50 FPS for 1080p, making the Pillow resize the dominant cost at approximately 10 milliseconds per frame.
- The decision to not add OpenCV (which would enable faster array-based resizing without the NumPy-to-Pillow-to-NumPy conversion) is a deliberate architectural choice to keep the dependency footprint small. OpenCV is a 50+ MB dependency that would significantly increase the application's footprint for a modest performance gain.
- MoviePy's write_videofile method internally calls make_frame for each frame sequentially. The write process also involves FFmpeg encoding, which runs as a subprocess and consumes additional CPU. The total render time is therefore frame_generation_time plus encoding_time, with encoding typically taking 2 to 5 times the frame generation time.

---

> **Parent:** [SubPhase_04_02_Overview.md](./SubPhase_04_02_Overview.md) (Layer 2)
> **Phase:** [Phase_04_Overview.md](../Phase_04_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
