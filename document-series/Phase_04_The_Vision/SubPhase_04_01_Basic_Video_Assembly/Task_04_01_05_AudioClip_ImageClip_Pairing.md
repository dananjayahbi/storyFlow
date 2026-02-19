# Task 04.01.05 — AudioClip ImageClip Pairing

> **Sub-Phase:** 04.01 — Basic Video Assembly
> **Phase:** Phase 04 — The Vision
> **Complexity:** Medium
> **Dependencies:** Task 04.01.04 (Video Renderer)
> **Parent Document:** [SubPhase_04_01_Overview.md](./SubPhase_04_01_Overview.md)

---

## Objective

Implement the logic within the rendering loop that pairs each segment's audio file with its corresponding image file, ensuring correct 1:1 matching by segment identity and robust error handling for missing or corrupt files.

---

## Instructions

### Step 1 — Verify file existence before loading

Within the per-segment loop in `render_project`, check that both `segment.audio_file.path` and `segment.image_file.path` exist on disk using `os.path.exists()` before attempting to load them. If either file is missing, raise a `FileNotFoundError` that clearly identifies the segment by its ID and `sequence_index`.

### Step 2 — Load the audio clip

Load the segment's audio using `AudioFileClip(segment.audio_file.path)`. Audio files are `.wav` format produced by Phase 03's TTS engine. If `AudioFileClip` raises an exception (corrupt file, unsupported format), catch it, log the segment details, and re-raise with added context.

### Step 3 — Load and resize the image

Load the segment's image using `render_utils.resize_image_to_resolution(segment.image_file.path, width, height)`. Images can be JPEG, PNG, or WebP — Pillow handles all of these. If `Image.open()` raises an exception (corrupt file), catch it, log the segment details, and re-raise with context.

### Step 4 — Create the paired clip

Create the image clip with the audio's duration: `ImageClip(image_array).set_duration(audio_clip.duration)`. Then set the audio on the image clip: `image_clip.set_audio(audio_clip)`. This creates a single composite clip where the static image displays for exactly the duration of the narration.

### Step 5 — Append and continue

Append the composite clip to the clips list. The iteration order is guaranteed by the `order_by('sequence_index')` query, so clips are naturally assembled in the correct narrative order.

---

## Expected Output

```
backend/
└── core_engine/
    └── video_renderer.py ← MODIFIED (pairing logic within render_project)
```

---

## Validation

- [ ] Each segment's image is paired with its own audio (1:1 mapping).
- [ ] File existence is verified before loading (both image and audio).
- [ ] Missing image raises `FileNotFoundError` identifying the segment.
- [ ] Missing audio raises `FileNotFoundError` identifying the segment.
- [ ] Corrupt audio is caught, logged, and re-raised with context.
- [ ] Corrupt image is caught, logged, and re-raised with context.
- [ ] Clips are assembled in `sequence_index` order.
- [ ] Audio files are `.wav` format (no format conversion needed).
- [ ] Image files in various formats (JPEG, PNG, WebP) are handled by Pillow.

---

## Notes

- The pairing is strictly 1:1 — each segment has exactly one image and one audio file. There is no scenario where a segment has multiple images or audio tracks.
- `segment.audio_file.path` and `segment.image_file.path` use Django's `FieldFile.path` property, which returns the absolute filesystem path.
- This task refines the per-segment loop structure introduced in Task 04.01.04. The emphasis here is on the file validation and error handling that makes the pairing robust.

---

> **Parent:** [SubPhase_04_01_Overview.md](./SubPhase_04_01_Overview.md) (Layer 2)
> **Phase:** [Phase_04_Overview.md](../Phase_04_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_04_01_04_Implement_Video_Renderer.md](./Task_04_01_04_Implement_Video_Renderer.md)
> **Next Task:** [Task_04_01_06_Duration_Synchronization.md](./Task_04_01_06_Duration_Synchronization.md)
