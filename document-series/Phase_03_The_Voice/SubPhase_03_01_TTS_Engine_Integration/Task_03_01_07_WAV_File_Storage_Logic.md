# Task 03.01.07 — WAV File Storage Logic

> **Sub-Phase:** 03.01 — TTS Engine Integration
> **Phase:** Phase 03 — The Voice
> **Complexity:** Low
> **Dependencies:** Task 03.01.02 (Audio Utils)
> **Parent Document:** [SubPhase_03_01_Overview.md](./SubPhase_03_01_Overview.md)

---

## Objective

Implement deterministic audio file path construction so that generated WAV files are consistently stored at `media/projects/{project_id}/audio/{segment_id}.wav`, and provide both the absolute filesystem path (for writing) and the relative URL path (for serving to the frontend).

---

## Instructions

### Step 1 — Implement `construct_audio_path(project_id, segment_id) → Path`

Build and return an absolute filesystem path by joining `settings.MEDIA_ROOT`, `"projects"`, the string representation of `project_id`, `"audio"`, and `"{segment_id}.wav"`. Return a `pathlib.Path` object for downstream compatibility with `soundfile` and standard file operations.

### Step 2 — Implement `construct_audio_url(project_id, segment_id) → str`

Build and return a URL-relative path in the form `"/media/projects/{project_id}/audio/{segment_id}.wav"`. This path is stored in the Segment model's `audio_file` field and served by Django's static/media file handling in development.

### Step 3 — Ensure parent directory creation

Before the caller writes the WAV file, the directory `media/projects/{project_id}/audio/` must exist. Either the path construction function itself should call `os.makedirs(..., exist_ok=True)` on the parent directory, or the `save_audio_wav()` function (from Task 03.01.02) should handle directory creation. Choose one location and document the decision — do not duplicate the creation logic.

### Step 4 — Deterministic naming enables automatic overwrite

Because the filename is derived directly from the segment's primary key, regenerating audio for the same segment produces the same path. This means the old WAV file is overwritten automatically — no cleanup or deletion logic is needed.

---

## Expected Output

```
backend/
└── core_engine/
    └── tts_wrapper.py          ← MODIFIED (path construction functions added)
```

---

## Validation

- [ ] `construct_audio_path(1, 5)` returns an absolute `Path` ending in `projects/1/audio/5.wav`.
- [ ] `construct_audio_url(1, 5)` returns `"/media/projects/1/audio/5.wav"`.
- [ ] Parent directory is created if it does not exist.
- [ ] Regenerating audio for the same segment overwrites the previous file.
- [ ] Path uses `settings.MEDIA_ROOT` — no hardcoded absolute paths.

---

## Notes

- The `MEDIA_ROOT` is set in Django settings, typically pointing to a `media/` directory at the project root.
- In production, Django does not serve media files directly — a reverse proxy would handle this. For StoryFlow (local-only), Django's built-in media serving in development mode is sufficient.
- The segment ID is the database primary key (integer), which guarantees uniqueness within a project.
- The functions can live in `tts_wrapper.py` since they are used primarily during audio generation, but `audio_utils.py` is also a reasonable home if a cleaner separation is preferred.

---

> **Parent:** [SubPhase_03_01_Overview.md](./SubPhase_03_01_Overview.md) (Layer 2)
> **Phase:** [Phase_03_Overview.md](../Phase_03_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_03_01_06_Audio_Normalization_Pipeline.md](./Task_03_01_06_Audio_Normalization_Pipeline.md)
> **Next Task:** [Task_03_01_08_Model_Missing_Graceful_Degrade.md](./Task_03_01_08_Model_Missing_Graceful_Degrade.md)
