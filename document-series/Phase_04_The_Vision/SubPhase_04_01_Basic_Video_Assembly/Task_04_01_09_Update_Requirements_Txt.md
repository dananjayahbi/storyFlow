# Task 04.01.09 — Update Requirements Txt

> **Sub-Phase:** 04.01 — Basic Video Assembly
> **Phase:** Phase 04 — The Vision
> **Complexity:** Low
> **Dependencies:** None (first task in execution order)
> **Parent Document:** [SubPhase_04_01_Overview.md](./SubPhase_04_01_Overview.md)

---

## Objective

Add the MoviePy dependency to `backend/requirements.txt` so the video rendering pipeline can be implemented.

---

## Instructions

### Step 1 — Add MoviePy to requirements.txt

Open `backend/requirements.txt` and add `moviepy>=1.0.3` under a new Phase 04 comment header, placed after the Phase 03 dependencies.

### Step 2 — Install the dependency

Run `pip install -r requirements.txt` from the `backend/` directory to install MoviePy and its transitive dependencies (decorator, tqdm, imageio, imageio-ffmpeg, proglog).

### Step 3 — Verify MoviePy imports

Verify that MoviePy is importable by running a quick import check: `from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips`. Confirm this succeeds without errors.

### Step 4 — Verify FFmpeg detection

Verify that MoviePy can locate FFmpeg by checking its configuration. MoviePy's `imageio-ffmpeg` dependency provides a bundled FFmpeg as a fallback, but the system FFmpeg should be the primary binary.

---

## Expected Output

```
backend/
└── requirements.txt ← MODIFIED
```

---

## Validation

- [ ] `moviepy>=1.0.3` appears in `requirements.txt`.
- [ ] `pip install -r requirements.txt` completes without errors.
- [ ] `from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips` succeeds.
- [ ] MoviePy's FFmpeg detection works.

---

## Notes

- This task should be executed first in the sub-phase since all other tasks depend on MoviePy being importable.
- MoviePy 1.0.3 automatically installs `imageio-ffmpeg`, which bundles a minimal FFmpeg binary. The system FFmpeg is still preferred for reliability and broader codec support.
- The `>=1.0.3` specifier allows both MoviePy 1.0.3 and 2.0. The codebase handles both import conventions via try/except.
- NumPy is already installed from Phase 03. Pillow is already installed from Phase 01. No additional image/array dependencies are needed.

---

> **Parent:** [SubPhase_04_01_Overview.md](./SubPhase_04_01_Overview.md) (Layer 2)
> **Phase:** [Phase_04_Overview.md](../Phase_04_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_04_01_08_MP4_Export_With_Codecs.md](./Task_04_01_08_MP4_Export_With_Codecs.md)
> **Next Task:** [Task_04_01_10_Output_Path_Management.md](./Task_04_01_10_Output_Path_Management.md)
