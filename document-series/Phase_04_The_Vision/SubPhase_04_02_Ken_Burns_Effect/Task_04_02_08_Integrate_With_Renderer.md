# Task 04.02.08 — Integrate With Renderer

## Metadata

| Field         | Value                                                                |
| ------------- | -------------------------------------------------------------------- |
| **Task ID**   | 04.02.08                                                             |
| **Task Name** | Integrate With Renderer                                              |
| **Sub-Phase** | 04.02 — Ken Burns Effect Implementation                              |
| **Phase**     | Phase 04 — The Vision: Video Rendering Engine                        |
| **Complexity**| Medium                                                               |
| **Dependencies** | Task 04.02.06 (make_frame must be functional), Task 04.02.09 (zoom intensity reading) |
| **Parent**    | [SubPhase_04_02_Overview.md](./SubPhase_04_02_Overview.md)           |

---

## Objective

Modify the existing video_renderer.py to replace the static ImageClip approach (from SubPhase 04.01) with the animated Ken Burns effect for each segment's visual clip. After this integration, every segment in a rendered video features smooth camera zoom-and-pan motion over its cover image instead of a static display. The audio pairing, clip concatenation, and MP4 export logic from SubPhase 04.01 remain unchanged — only the visual clip construction for each segment changes.

---

## Instructions

### Step 1 — Add the Ken Burns Import

At the top of backend/core_engine/video_renderer.py, add an import statement that brings in the apply_ken_burns function from the core_engine.ken_burns module. This import sits alongside the existing imports for render_utils, MoviePy components, and other dependencies established in SubPhase 04.01.

### Step 2 — Read Zoom Intensity From GlobalSettings

At the beginning of the render_project function (after loading the Project instance and its segments), read the zoom_intensity value from the GlobalSettings model. Import GlobalSettings from api.models. Query for the first (and only) GlobalSettings row. If a GlobalSettings instance exists, extract its zoom_intensity attribute. If no GlobalSettings instance exists (the row has not been created yet), fall back to the default value of 1.3 and log a warning explaining that the default is being used.

Validate the retrieved zoom_intensity value: if it is less than or equal to zero (which could happen if corrupt data exists in the database), fall back to 1.3 and log a warning about the invalid value. Log the zoom_intensity value being used at INFO level.

This GlobalSettings reading logic is shared with Task 04.02.09, which provides more detailed specification. The integration here ensures the value flows into the per-segment loop.

### Step 3 — Replace Static ImageClip With Ken Burns Clip

In the per-segment rendering loop inside render_project, locate the existing code that creates a static image clip for each segment. The SubPhase 04.01 implementation loads the segment's cover image using render_utils.resize_image_to_resolution, creates an ImageClip from the resulting array, and sets its duration to match the audio clip's duration.

Replace this entire block with a call to apply_ken_burns. Pass the following arguments:

- image_path: the file system path to the segment's image file, obtained from the segment model's image_file field path attribute.
- duration: the audio clip's duration, maintaining the synchronization established in SubPhase 04.01.
- resolution: a tuple of (output width, output height) from the project's resolution settings.
- zoom_intensity: the value read from GlobalSettings in Step 2.
- fps: the project's framerate setting.
- segment_index: the segment's sequence_index value, which determines the pan direction.

The returned VideoClip replaces the old ImageClip. The subsequent set_audio call remains the same — audio pairing works identically regardless of whether the visual clip is static or animated.

### Step 4 — Remove Redundant Image Resize Call

The render_utils.resize_image_to_resolution call that was used in SubPhase 04.01 to prepare the segment image is no longer needed in the per-segment loop. The apply_ken_burns function handles its own image loading and preparation internally via load_and_prepare_image. Remove the resize call from the loop to avoid loading the image twice.

Keep the resize_image_to_resolution function itself in render_utils.py — it may still be needed for other purposes such as thumbnail generation or as a fallback if Ken Burns is ever disabled. Only remove its invocation from the per-segment loop.

### Step 5 — Update Progress Callback Messages

If the render_project function emits progress callbacks (an on_progress function called after each segment is processed), update the progress message to reflect that the Ken Burns effect is being applied. The message should indicate which segment is being processed and that Ken Burns animation is being generated.

### Step 6 — Update Clip Cleanup Logic

The finally block in render_project (or equivalent cleanup section) must properly close all clips after rendering is complete. Ken Burns clips are VideoClip objects with make_frame closures that hold references to source image arrays. These must be explicitly closed using the clip's close method to release memory.

Ensure the cleanup logic handles both the individual segment clips and the final concatenated clip. If a clip has an audio attribute, close the audio clip as well. This prevents file handle leaks and high memory usage during and after rendering.

### Step 7 — Handle ImageClip Import

After this integration, ImageClip may no longer be used directly in video_renderer.py (since Ken Burns clips are VideoClip objects, not ImageClips). If ImageClip is no longer referenced anywhere in the file, remove its import to keep the import section clean. If it is still used elsewhere (for example, in a fallback path), keep the import.

---

## Expected Output

After completing this task, calling render_project produces a video where every segment features Ken Burns zoom-and-pan motion over its cover image. The output MP4 file has:

- Animated camera motion on each segment (instead of static images).
- Different pan directions for consecutive segments (cycling through the 7 predefined directions).
- Correct audio synchronization (unchanged from SubPhase 04.01).
- Proper codec settings (libx264/aac/8000k, unchanged from SubPhase 04.01).

The file backend/core_engine/video_renderer.py is modified with the Ken Burns integration, GlobalSettings read, and updated cleanup logic.

---

## Validation

- [ ] video_renderer.py imports apply_ken_burns from core_engine.ken_burns.
- [ ] GlobalSettings.zoom_intensity is read at the start of render_project.
- [ ] A default of 1.3 is used when GlobalSettings is missing.
- [ ] Each segment's visual clip is created using apply_ken_burns instead of ImageClip.
- [ ] The apply_ken_burns call passes the correct image_path, duration, resolution, zoom_intensity, fps, and segment_index.
- [ ] Audio-image synchronization is preserved (duration matching unchanged).
- [ ] The redundant render_utils.resize_image_to_resolution call is removed from the loop.
- [ ] Clip cleanup in the finally block handles VideoClip objects properly.
- [ ] The output MP4 is valid and playable.
- [ ] render_project still produces correct results end-to-end.

---

## Notes

- This integration represents the transition point where StoryFlow videos go from static slideshows to animated presentations. The visual quality improvement is significant and directly visible to the user.
- The render_utils.resize_image_to_resolution function remains available in render_utils.py for potential future use. Only its invocation in the per-segment loop is removed.
- SubPhase 04.01 tests that validated static-image rendering may need adjustment after this change. With Ken Burns integrated by default, those tests will now produce videos with animated motion. Setting zoom_intensity to 1.0 effectively disables visible zoom (crop equals output), which can be used to approximate static-image behavior for backward-compatible testing.
- The set_audio call is completely unchanged by this integration. Whether the visual clip is a static ImageClip or an animated Ken Burns VideoClip, MoviePy pairs the audio identically. The duration synchronization logic from SubPhase 04.01 remains the authoritative mechanism for audio-visual alignment.

---

> **Parent:** [SubPhase_04_02_Overview.md](./SubPhase_04_02_Overview.md) (Layer 2)
> **Phase:** [Phase_04_Overview.md](../Phase_04_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
