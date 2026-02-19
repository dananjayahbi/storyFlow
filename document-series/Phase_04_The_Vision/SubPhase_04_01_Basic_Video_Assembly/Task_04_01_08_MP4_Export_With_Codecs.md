# Task 04.01.08 — MP4 Export With Codecs

> **Sub-Phase:** 04.01 — Basic Video Assembly
> **Phase:** Phase 04 — The Vision
> **Complexity:** Medium
> **Dependencies:** Task 04.01.07 (Clip Concatenation)
> **Parent Document:** [SubPhase_04_01_Overview.md](./SubPhase_04_01_Overview.md)

---

## Objective

Implement the final export step that writes the concatenated video to an MP4 file using the architecture-specified encoding parameters: H.264 video, AAC audio, and 8 Mbps bitrate.

---

## Instructions

### Step 1 — Call the progress callback before export

If the `on_progress` callback is provided, call it with the "Exporting final MP4..." phase message before starting the export. This gives the frontend (in SubPhase 04.03) a clear signal that processing is entering the export phase.

### Step 2 — Execute write_videofile

Call `final.write_videofile()` with the following parameters:
- `output_path` — the path from `render_utils.get_output_path()`.
- `fps` — the project's `framerate` field (default 30).
- `codec` — `"libx264"` (H.264 video compression, universally supported).
- `audio_codec` — `"aac"` (AAC audio, standard for MP4 containers).
- `bitrate` — `"8000k"` (8 Mbps, high quality suitable for YouTube uploads).
- `logger` — `None` (suppresses MoviePy's noisy tqdm progress bars; progress is reported via the `on_progress` callback instead).

### Step 3 — Verify the output file

After export completes, verify the output file exists using `os.path.exists(output_path)`. Get the file size using `os.path.getsize(output_path)`. Log the export summary: file path, file size in MB, and total duration.

### Step 4 — Handle export errors

`write_videofile` can raise `IOError` (output directory not writable) or `RuntimeError` (FFmpeg encoding failure). On any error, attempt to delete the partial output file if it exists (a partial MP4 is unusable), then re-raise the exception with context.

### Step 5 — Clean up all clips

After export (whether successful or not), close all resources in a finally block:
- Close the final composite clip: `final.close()`.
- Loop through all individual clips and close each one. For each clip, also close its audio sub-clip if it has one (`clip.audio.close()` if `clip.audio` is not None).
- This releases file handles and frees memory, which is especially important on Windows where open handles prevent file deletion.

---

## Expected Output

```
backend/
└── core_engine/
    └── video_renderer.py ← MODIFIED (export step)
```

---

## Validation

- [ ] Export uses `codec="libx264"`, `audio_codec="aac"`, `bitrate="8000k"`.
- [ ] `fps` uses the project's `framerate` field.
- [ ] `logger=None` suppresses MoviePy's console output.
- [ ] Output file existence is verified after export.
- [ ] File size is calculated and logged.
- [ ] Export errors trigger partial file cleanup.
- [ ] All clips (composite + individual + audio) are closed in finally block.
- [ ] Output MP4 is a valid, playable video file.

---

## Notes

- `logger=None` is critical for background task execution. Without it, MoviePy spawns tqdm progress bars that write to stdout/stderr, which is inappropriate and can cause issues in threaded contexts.
- `bitrate="8000k"` produces approximately 60 MB per minute of 1080p video. This is intentionally high-quality for a "faceless" narrative video intended for social media upload.
- The `.wav` audio from Phase 03's TTS engine is automatically converted to AAC by FFmpeg during export. No separate audio conversion step is needed.
- For static images without Ken Burns, the FPS setting doesn't visually matter (every frame is identical), but it must be set correctly for SubPhase 04.02 when Ken Burns animations will produce distinct frames at 30 FPS.

---

> **Parent:** [SubPhase_04_01_Overview.md](./SubPhase_04_01_Overview.md) (Layer 2)
> **Phase:** [Phase_04_Overview.md](../Phase_04_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_04_01_07_Clip_Concatenation.md](./Task_04_01_07_Clip_Concatenation.md)
> **Next Task:** [Task_04_01_09_Update_Requirements_Txt.md](./Task_04_01_09_Update_Requirements_Txt.md)
