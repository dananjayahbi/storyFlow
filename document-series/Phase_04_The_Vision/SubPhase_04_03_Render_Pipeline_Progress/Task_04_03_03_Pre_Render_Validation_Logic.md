# Task 04.03.03 — Pre-Render Validation Logic

## Metadata

| Field         | Value                                                                |
| ------------- | -------------------------------------------------------------------- |
| **Task ID**   | 04.03.03                                                             |
| **Task Name** | Pre-Render Validation Logic                                          |
| **Sub-Phase** | 04.03 — Render Pipeline & Progress API                               |
| **Phase**     | Phase 04 — The Vision: Video Rendering Engine                        |
| **Complexity**| Medium                                                               |
| **Dependencies** | None (standalone validation utility)                              |
| **Parent**    | [SubPhase_04_03_Overview.md](./SubPhase_04_03_Overview.md)           |

---

## Objective

Implement a comprehensive validation function that checks whether a project is ready for video rendering. The function verifies that the project has at least one segment, that all segments have both image and audio files assigned, and that those files actually exist on the filesystem. This validation runs before the render endpoint spawns a background task, providing immediate feedback to the user about any missing assets.

---

## Instructions

### Step 1 — Define the Function

Add a function named validate_project_for_render to backend/api/validators.py. The function accepts a single parameter: the Project model instance. It returns None if the project passes all validation checks, or a dictionary containing error details if any check fails.

### Step 2 — Check for Segments

Query all Segment objects associated with the project, ordered by sequence_index. If no segments exist, return an error dictionary with a message indicating the project has no segments.

### Step 3 — Check Asset Completeness

Iterate through all segments in a single pass, collecting two separate lists: segment IDs with missing image files and segment IDs with missing audio files. For each segment, check both the database field (is image_file or audio_file set and non-empty) and the filesystem (does the referenced file actually exist on disk using os.path.exists). Add the segment ID to the appropriate missing list if either check fails.

### Step 4 — Return Results

If both missing lists are empty, return None (project is valid). If either list has entries, return a dictionary containing: the missing_images list, the missing_audio list, and a human-readable message summarizing the total count of missing assets.

### Step 5 — Import Dependencies

Add the necessary imports to validators.py: os for filesystem checks and the Segment model from api.models.

---

## Expected Output

The function validate_project_for_render exists in backend/api/validators.py. It returns None for valid projects or a descriptive error dictionary for invalid ones, with segment-level detail about which assets are missing.

---

## Validation

- [ ] validate_project_for_render exists in validators.py.
- [ ] Returns None when all segments have valid image and audio files.
- [ ] Returns error dict when project has no segments.
- [ ] Returns error dict with missing_images when segments lack image files.
- [ ] Returns error dict with missing_audio when segments lack audio files.
- [ ] Checks filesystem existence (not just database field presence).
- [ ] Collects all errors in a single pass (does not short-circuit on first failure).
- [ ] Error dict includes segment IDs for targeted feedback.

---

## Notes

- Checking os.path.exists on every segment's files catches the scenario where the database references a file that was manually deleted from disk. This is a practical concern in a local-only application where users may manipulate the filesystem directly.
- The function does not check project.status — that check is performed by the render endpoint itself (Task 04.03.01) since the status check has different semantics (409 Conflict vs 400 Bad Request).
- The single-pass collection approach means the user sees all validation errors at once, rather than fixing one issue and discovering another on the next attempt.

---

> **Parent:** [SubPhase_04_03_Overview.md](./SubPhase_04_03_Overview.md) (Layer 2)
> **Phase:** [Phase_04_Overview.md](../Phase_04_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
