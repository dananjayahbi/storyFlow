# Task 04.01.01 — Create Render Utils Module

> **Sub-Phase:** 04.01 — Basic Video Assembly
> **Phase:** Phase 04 — The Vision
> **Complexity:** Medium
> **Dependencies:** Task 04.01.09 (MoviePy in requirements.txt)
> **Parent Document:** [SubPhase_04_01_Overview.md](./SubPhase_04_01_Overview.md)

---

## Objective

Create the `core_engine/render_utils.py` utility module that serves as the central hub for all rendering helper functions used throughout Phase 04: FFmpeg checking, image resizing, output path management, and temporary file cleanup.

---

## Instructions

### Step 1 — Create the module file

Create `backend/core_engine/render_utils.py`. Add a module-level docstring explaining that this module provides utility functions for the video rendering pipeline.

### Step 2 — Configure the module logger

Set up a module-level logger using `logging.getLogger(__name__)` so all utility functions can log diagnostics consistently.

### Step 3 — Add required imports

Import the necessary standard library and third-party modules: `PIL.Image` for image loading, `numpy` for array conversion, `subprocess` and `shutil` for FFmpeg detection, `os` and `pathlib` for path operations, and `logging` for diagnostics.

### Step 4 — Define function stubs with signatures

Define all four function signatures with type hints and docstrings, but leave the implementation bodies as placeholders (or implement them if preferred — Tasks 04.01.02, 04.01.03, and 04.01.10 provide the detailed specs):
- `check_ffmpeg() -> bool` — Verifies FFmpeg is installed and operational.
- `resize_image_to_resolution(image_path: str, width: int, height: int) -> np.ndarray` — Loads an image and resizes it using "cover" mode to fill the target resolution exactly.
- `get_output_path(project_id: str) -> str` — Returns the output file path for a rendered video and ensures the output directory exists.
- `cleanup_temp_files(temp_dir: str) -> None` — Removes temporary files created during the rendering process.

### Step 5 — Add supporting private helpers (as needed)

If any functions benefit from internal helpers (e.g., `get_ffmpeg_error_message()` or `reset_ffmpeg_cache()`), define them as module-level functions with a leading underscore or as plain functions — their details are specified in the dependent tasks.

### Step 6 — Ensure all functions are pure (no Django ORM)

All functions must be pure utility functions that do not import or query Django models. The only exception is `get_output_path`, which reads `django.conf.settings.MEDIA_ROOT` to construct the output directory path.

---

## Expected Output

```
backend/
└── core_engine/
    └── render_utils.py ← CREATED
```

---

## Validation

- [ ] File `core_engine/render_utils.py` exists.
- [ ] Module-level docstring present.
- [ ] Module-level logger configured via `logging.getLogger(__name__)`.
- [ ] All four functions defined with full type hints and docstrings.
- [ ] Imports include PIL, numpy, subprocess, shutil, os, pathlib, logging.
- [ ] No Django model imports (only `django.conf.settings` in `get_output_path`).
- [ ] File imports cleanly: `from core_engine import render_utils` succeeds.

---

## Notes

- This module is the foundation for all of Phase 04. Tasks 04.01.02, 04.01.03, and 04.01.10 fill in the detailed implementation of each function. Task 04.01.01 ensures the file structure and interface are in place.
- Functions should be designed for testability — no hidden global state except the FFmpeg cache (which has a reset function).
- The `core_engine/` directory already exists from Phase 01 (it contains `video_renderer.py` stub and `ken_burns.py` stub).

---

> **Parent:** [SubPhase_04_01_Overview.md](./SubPhase_04_01_Overview.md) (Layer 2)
> **Phase:** [Phase_04_Overview.md](../Phase_04_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** None (first task in SubPhase 04.01)
> **Next Task:** [Task_04_01_02_FFmpeg_Availability_Check.md](./Task_04_01_02_FFmpeg_Availability_Check.md)
