# Task 05.01.08 — Font Validation Utility

## Metadata

| Field         | Value                                                                |
| ------------- | -------------------------------------------------------------------- |
| **Task ID**   | 05.01.08                                                             |
| **Task Name** | Font Validation Utility                                              |
| **Sub-Phase** | 05.01 — Subtitle Generation & Overlay                                |
| **Phase**     | Phase 05 — The Polish                                                |
| **Complexity**| Low                                                                  |
| **Dependencies** | Task 05.01.07 (default font must exist for fallback path)         |
| **Parent**    | [SubPhase_05_01_Overview.md](./SubPhase_05_01_Overview.md)           |

---

## Objective

Implement font path validation and default fallback logic in render_utils.py. The primary function get_font_path takes a configured font path string and returns a guaranteed-valid font file path, falling back to the bundled default font when the configured path is empty, missing, or has an invalid extension. A secondary helper validate_font_file checks whether a given file path is a valid font file.

---

## Instructions

### Step 1 — Define the Default Font Path Constant

In backend/core_engine/render_utils.py, define a module-level constant DEFAULT_FONT_PATH constructed using Django's BASE_DIR setting: os.path.join(django_settings.BASE_DIR, 'fonts', 'default.ttf'). Import Django settings for this purpose.

### Step 2 — Implement get_font_path

Add a function named get_font_path that accepts a single string parameter (the configured font path from GlobalSettings.subtitle_font) and returns a string (a validated font file path). The function's logic:

1. If the input is empty, None, or whitespace-only, log an info message and return DEFAULT_FONT_PATH.
2. Resolve relative paths by joining with BASE_DIR.
3. Check if the resolved path exists on the filesystem using os.path.exists. If not, log a warning and return DEFAULT_FONT_PATH.
4. Check if the file extension is .ttf or .otf (case-insensitive). If not, log a warning and return DEFAULT_FONT_PATH.
5. If all checks pass, return the resolved path.

This function always returns a valid path — it never returns None or an empty string.

### Step 3 — Implement validate_font_file

Add a helper function named validate_font_file that accepts a file path string and returns a boolean. It checks two things: the file exists on disk and the file extension is .ttf or .otf. This simpler function is used by the font upload endpoint in SubPhase 05.03.

### Step 4 — Implement verify_default_font (Optional)

Add an optional function verify_default_font that returns a boolean indicating whether the bundled default font exists at DEFAULT_FONT_PATH. If it does not exist, log an error. This can be called at application startup to catch deployment issues early.

### Step 5 — Add Imports

Ensure os and Django's settings are imported in render_utils.py.

---

## Expected Output

The render_utils.py file contains get_font_path (always returns a valid font path with fallback), validate_font_file (boolean check), and optionally verify_default_font (startup check). The DEFAULT_FONT_PATH constant points to backend/fonts/default.ttf.

---

## Validation

- [ ] get_font_path("") returns DEFAULT_FONT_PATH.
- [ ] get_font_path(None) returns DEFAULT_FONT_PATH.
- [ ] get_font_path("/nonexistent/font.ttf") returns DEFAULT_FONT_PATH.
- [ ] get_font_path("/valid/path/font.woff") returns DEFAULT_FONT_PATH (invalid extension).
- [ ] get_font_path("/valid/path/font.ttf") returns the given path when the file exists.
- [ ] get_font_path accepts .otf extension as valid.
- [ ] validate_font_file returns True for existing .ttf files.
- [ ] validate_font_file returns False for missing files or non-font extensions.
- [ ] DEFAULT_FONT_PATH correctly resolves to backend/fonts/default.ttf.

---

## Notes

- get_font_path is called once per render in video_renderer.py (Task 05.01.05), before the segment loop. It does not need to be called per-segment.
- The function does not validate that the file is internally a valid TrueType font — it only checks existence and extension. MoviePy/ImageMagick will catch corrupted font files when creating TextClips.
- Relative path resolution (joining with BASE_DIR) handles the case where GlobalSettings.subtitle_font stores a path like "fonts/custom.ttf" rather than an absolute path.

---

> **Parent:** [SubPhase_05_01_Overview.md](./SubPhase_05_01_Overview.md) (Layer 2)
> **Phase:** [Phase_05_Overview.md](../Phase_05_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
