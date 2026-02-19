# Task 05.01.06 — ImageMagick Check And Fallback

## Metadata

| Field         | Value                                                                |
| ------------- | -------------------------------------------------------------------- |
| **Task ID**   | 05.01.06                                                             |
| **Task Name** | ImageMagick Check And Fallback                                       |
| **Sub-Phase** | 05.01 — Subtitle Generation & Overlay                                |
| **Phase**     | Phase 05 — The Polish                                                |
| **Complexity**| Medium                                                               |
| **Dependencies** | None (standalone utility)                                         |
| **Parent**    | [SubPhase_05_01_Overview.md](./SubPhase_05_01_Overview.md)           |

---

## Objective

Implement the check_imagemagick function in render_utils.py that verifies whether ImageMagick is installed and accessible on the system PATH. MoviePy's TextClip requires ImageMagick's binary to rasterize text onto video frames. If ImageMagick is missing, the render pipeline should gracefully degrade by producing video without subtitles rather than failing entirely.

---

## Instructions

### Step 1 — Add the Function to render_utils.py

In backend/core_engine/render_utils.py, add a function named check_imagemagick that returns a boolean indicating whether ImageMagick is available.

### Step 2 — Check for ImageMagick 7 (magick binary)

Use shutil.which to look for the "magick" binary on the system PATH. ImageMagick 7+ uses "magick" as its primary command. If found, return True.

### Step 3 — Check for ImageMagick 6 (convert binary)

If "magick" is not found, use shutil.which to look for the "convert" binary. However, on Windows, a system utility also named "convert.exe" exists (for FAT32-to-NTFS conversion) that is NOT ImageMagick. To distinguish, run the convert binary with the "--version" flag using subprocess.run with capture_output=True, text=True, and a 5-second timeout. Check if the string "ImageMagick" appears in the stdout output. If it does, return True. If the subprocess times out, raises FileNotFoundError, or the output does not contain "ImageMagick", continue to the next check.

### Step 4 — Return False

If neither check succeeds, return False.

### Step 5 — Add Caching

Apply functools.lru_cache(maxsize=1) to the function. ImageMagick availability does not change during a single process lifetime, so caching the result avoids running subprocess checks on repeated calls. Import functools at the top of the file.

### Step 6 — Add Required Imports

Ensure subprocess, shutil, and functools are imported in render_utils.py.

### Step 7 — Windows PATH Considerations

On Windows, ImageMagick's install directory may not be in PATH by default. If the standard PATH checks fail, optionally check common Windows install paths (e.g., C:\Program Files\ImageMagick-7.*). If found at a non-standard location, MoviePy may need the IMAGEMAGICK_BINARY environment variable set, which can be done by calling moviepy.config.change_settings.

---

## Expected Output

The function check_imagemagick exists in render_utils.py. It returns True when ImageMagick (v6 or v7) is installed and accessible, False otherwise. The result is cached for process lifetime.

---

## Validation

- [ ] check_imagemagick exists in render_utils.py.
- [ ] Returns True when ImageMagick 7 (magick) is on PATH.
- [ ] Returns True when ImageMagick 6 (convert with "ImageMagick" in output) is on PATH.
- [ ] Returns False when neither is available.
- [ ] Distinguishes Windows system "convert.exe" from ImageMagick "convert".
- [ ] Subprocess call has a 5-second timeout to prevent hanging.
- [ ] Result is cached with lru_cache.
- [ ] The function mirrors the existing check_ffmpeg pattern in render_utils.py.

---

## Notes

- This function follows the same pattern as the existing check_ffmpeg function from SubPhase 04.01. Both check for system binaries required by the render pipeline.
- The lru_cache is important for performance: the check is called once at the start of render_project (Task 05.01.05), but if called again elsewhere, the subprocess is not re-executed.
- The Windows "convert.exe" ambiguity is a well-known ImageMagick gotcha. The "--version" check with "ImageMagick" string verification is the standard workaround.
- If the check returns False, the entire subtitle pipeline is skipped for that render — the video is produced with Ken Burns animation but no text overlay. A warning is added to the render result.

---

> **Parent:** [SubPhase_05_01_Overview.md](./SubPhase_05_01_Overview.md) (Layer 2)
> **Phase:** [Phase_05_Overview.md](../Phase_05_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
