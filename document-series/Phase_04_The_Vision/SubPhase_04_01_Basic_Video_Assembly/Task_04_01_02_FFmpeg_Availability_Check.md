# Task 04.01.02 — FFmpeg Availability Check

> **Sub-Phase:** 04.01 — Basic Video Assembly
> **Phase:** Phase 04 — The Vision
> **Complexity:** Low
> **Dependencies:** Task 04.01.01 (Render Utils Module)
> **Parent Document:** [SubPhase_04_01_Overview.md](./SubPhase_04_01_Overview.md)

---

## Objective

Implement a reliable, cached check for FFmpeg availability on the system PATH, with clear error reporting and platform-specific installation guidance.

---

## Instructions

### Step 1 — Implement check_ffmpeg

In `backend/core_engine/render_utils.py`, implement `check_ffmpeg() -> bool`. Use `shutil.which("ffmpeg")` for PATH lookup. If found, run `subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=10)` to verify it executes. Handle `subprocess.TimeoutExpired` and `OSError` gracefully. Return `True` if operational, `False` otherwise.

### Step 2 — Add lazy caching

Introduce a module-level `_ffmpeg_available` variable initialized to `None`. On the first call to `check_ffmpeg()`, perform the actual check and store the result. Subsequent calls return the cached value without re-running the subprocess. This avoids slowing down Django startup.

### Step 3 — Add reset_ffmpeg_cache

Implement `reset_ffmpeg_cache() -> None` that sets `_ffmpeg_available` back to `None`, forcing the next `check_ffmpeg()` call to re-run the detection. This is needed for testing scenarios.

### Step 4 — Implement get_ffmpeg_error_message

Implement `get_ffmpeg_error_message() -> str` that returns a human-readable error message with platform-specific installation instructions: Windows (choco install ffmpeg / winget install ffmpeg), Linux (sudo apt install ffmpeg), macOS (brew install ffmpeg). This message is consumed by the render endpoint in SubPhase 04.03 and can be logged by the renderer.

---

## Expected Output

```
backend/
└── core_engine/
    └── render_utils.py ← MODIFIED
```

---

## Validation

- [ ] `check_ffmpeg()` returns `True` when FFmpeg is installed.
- [ ] `check_ffmpeg()` returns `False` when FFmpeg is not on PATH.
- [ ] Result is cached after first call (no subprocess on subsequent calls).
- [ ] `reset_ffmpeg_cache()` clears the cache for testing.
- [ ] `get_ffmpeg_error_message()` returns a string with installation instructions.
- [ ] Function never raises exceptions — always returns a boolean.
- [ ] Timeout of 10 seconds prevents hanging on unresponsive FFmpeg.

---

## Notes

- The check is lazy by design — it does NOT run at Django startup. This is important because FFmpeg checking involves subprocess execution, which would add latency to every server boot.
- `ffmpeg -version` is preferred over `ffmpeg -h` because it exits immediately with minimal output.
- MoviePy's dependency `imageio-ffmpeg` bundles a minimal FFmpeg, but the system FFmpeg is preferred for better codec support and reliability.

---

> **Parent:** [SubPhase_04_01_Overview.md](./SubPhase_04_01_Overview.md) (Layer 2)
> **Phase:** [Phase_04_Overview.md](../Phase_04_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_04_01_01_Create_Render_Utils_Module.md](./Task_04_01_01_Create_Render_Utils_Module.md)
> **Next Task:** [Task_04_01_03_Image_Cover_Resize_Logic.md](./Task_04_01_03_Image_Cover_Resize_Logic.md)
