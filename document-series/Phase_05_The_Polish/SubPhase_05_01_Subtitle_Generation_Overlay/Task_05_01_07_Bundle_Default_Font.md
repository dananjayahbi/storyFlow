# Task 05.01.07 — Bundle Default Font

## Metadata

| Field         | Value                                                                |
| ------------- | -------------------------------------------------------------------- |
| **Task ID**   | 05.01.07                                                             |
| **Task Name** | Bundle Default Font                                                  |
| **Sub-Phase** | 05.01 — Subtitle Generation & Overlay                                |
| **Phase**     | Phase 05 — The Polish                                                |
| **Complexity**| Low                                                                  |
| **Dependencies** | None (independent binary asset)                                   |
| **Parent**    | [SubPhase_05_01_Overview.md](./SubPhase_05_01_Overview.md)           |

---

## Objective

Include a permissively-licensed bold .ttf font file in the project repository as the default subtitle font. This font serves as the fallback when GlobalSettings.subtitle_font is empty or points to a missing file. It must be committed to the repository so the subtitle engine always has a usable font without requiring user configuration.

---

## Instructions

### Step 1 — Create the Fonts Directory

Create the directory backend/fonts/ to house the default font and any future user-uploaded fonts.

### Step 2 — Select and Download a Font

Choose a permissively-licensed bold font suitable for video subtitles. The recommended choice is Roboto Bold (Apache License 2.0) from Google Fonts. Alternatives include Open Sans Bold (Apache 2.0), Noto Sans Bold (OFL), or Inter Bold (OFL). The font must be a .ttf file (not .woff, .woff2, or .otf) and a bold weight for readability against video backgrounds.

### Step 3 — Place the Font File

Save the selected font file as backend/fonts/default.ttf. This exact path is referenced by the font validation utility (Task 05.01.08) and the subtitle engine.

### Step 4 — Add License Attribution

Create a backend/fonts/LICENSE.txt file documenting the font name, its license type, the original source URL, and any required attribution text. This satisfies the legal requirements for bundling open-source fonts.

### Step 5 — Verify .gitignore Exclusion

Ensure the backend/fonts/ directory is NOT listed in .gitignore. The default font must be committed to version control so it is available on every clone of the repository.

### Step 6 — Verify Font Works with MoviePy

Test that MoviePy's TextClip can use the bundled font by creating a test TextClip with the font path. The TextClip constructor should not raise an error when ImageMagick is available.

---

## Expected Output

Two new files: backend/fonts/default.ttf (a bold .ttf font, approximately 100–300 KB) and backend/fonts/LICENSE.txt (font license attribution). The font works correctly with MoviePy TextClip.

---

## Validation

- [ ] backend/fonts/ directory exists.
- [ ] backend/fonts/default.ttf exists and is a valid .ttf font file.
- [ ] backend/fonts/LICENSE.txt exists with proper attribution.
- [ ] The font is bold weight (suitable for subtitle readability).
- [ ] The font license is permissive (Apache 2.0, OFL, or similar).
- [ ] The fonts/ directory is not in .gitignore.
- [ ] MoviePy TextClip accepts the font path without errors (when ImageMagick is present).

---

## Notes

- The font file is typically 100–300 KB — small enough for repository inclusion without concern.
- The runtime absolute path to the font is constructed using Django's BASE_DIR: os.path.join(settings.BASE_DIR, 'fonts', 'default.ttf'). This is handled by the font validation utility (Task 05.01.08).
- Custom user-uploaded fonts (from SubPhase 05.03's font upload API) will also be stored in the backend/fonts/ directory alongside the default.

---

> **Parent:** [SubPhase_05_01_Overview.md](./SubPhase_05_01_Overview.md) (Layer 2)
> **Phase:** [Phase_05_Overview.md](../Phase_05_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
