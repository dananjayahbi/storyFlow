# Task 04.01.10 — Output Path Management

> **Sub-Phase:** 04.01 — Basic Video Assembly
> **Phase:** Phase 04 — The Vision
> **Complexity:** Low
> **Dependencies:** Task 04.01.01 (Render Utils Module)
> **Parent Document:** [SubPhase_04_01_Overview.md](./SubPhase_04_01_Overview.md)

---

## Objective

Implement the output path resolution and directory creation logic for rendered video files, along with a temporary file cleanup utility.

---

## Instructions

### Step 1 — Implement get_output_path

In `backend/core_engine/render_utils.py`, implement `get_output_path(project_id: str) -> str`. Build the output directory path as `{MEDIA_ROOT}/projects/{project_id}/output/`. Create the directory if it does not exist using `os.makedirs(output_dir, exist_ok=True)`. Return the full file path `{output_dir}/final.mp4`. Use `pathlib.Path` or `os.path.join` for cross-platform path construction.

### Step 2 — Access Django's MEDIA_ROOT

Import `django.conf.settings` and read `settings.MEDIA_ROOT`. If `MEDIA_ROOT` is not set or empty, raise a `ValueError` with a clear message indicating the setting is required.

### Step 3 — Implement cleanup_temp_files

Implement `cleanup_temp_files(temp_dir: str) -> None`. Remove all files in the specified temporary directory. If the directory is empty after cleanup, remove it. Handle `FileNotFoundError` gracefully (the directory may not exist). Log each file removed.

### Step 4 — Handle edge cases

Ensure the function handles paths with special characters or spaces by using `pathlib.Path` for safe path construction. Let `OSError` propagate naturally if the output directory cannot be created due to insufficient permissions.

---

## Expected Output

```
backend/
└── core_engine/
    └── render_utils.py ← MODIFIED
```

---

## Validation

- [ ] `get_output_path()` returns a path ending in `/output/final.mp4`.
- [ ] Output directory is created if it does not exist.
- [ ] Re-render scenario: function works when directory already exists (`exist_ok=True`).
- [ ] Missing `MEDIA_ROOT` raises `ValueError`.
- [ ] `cleanup_temp_files` removes files and empty directories.
- [ ] `cleanup_temp_files` handles non-existent directories gracefully.

---

## Notes

- The output file is always named `final.mp4` — this is a constraint from the Phase 04 architecture.
- Django's media serving (configured in Phase 01) already serves files from `MEDIA_ROOT`, so the rendered MP4 is automatically accessible at `http://localhost:8000/media/projects/{project_id}/output/final.mp4`.
- Re-rendering overwrites the existing `final.mp4` without versioning. This is intentional — the user can re-render as many times as needed, and only the latest output is kept.
- The `cleanup_temp_files` utility is available for future use (e.g., cleaning up intermediate frames if needed in SubPhase 04.02) but may not be called directly in SubPhase 04.01.

---

> **Parent:** [SubPhase_04_01_Overview.md](./SubPhase_04_01_Overview.md) (Layer 2)
> **Phase:** [Phase_04_Overview.md](../Phase_04_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_04_01_09_Update_Requirements_Txt.md](./Task_04_01_09_Update_Requirements_Txt.md)
> **Next Task:** [Task_04_01_11_Write_Basic_Render_Tests.md](./Task_04_01_11_Write_Basic_Render_Tests.md)
