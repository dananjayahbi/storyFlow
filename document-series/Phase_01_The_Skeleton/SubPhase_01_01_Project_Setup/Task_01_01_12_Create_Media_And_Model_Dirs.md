# Task 01.01.12 — Create Media & Model Directories

## Metadata

| Field                    | Value                                                                                  |
| ------------------------ | -------------------------------------------------------------------------------------- |
| **Sub-Phase**            | SubPhase 01.01 — Project Initialization & Tooling Setup                                |
| **Phase**                | Phase 01 — The Skeleton                                                                |
| **Document Type**        | Layer 3 — Task Document                                                                |
| **Estimated Complexity** | Low                                                                                    |
| **Dependencies**         | [Task_01_01_01](Task_01_01_01_Initialize_Django_Project.md) — `/backend` must exist    |
| **Parent Document**      | [SubPhase_01_01_Overview.md](SubPhase_01_01_Overview.md) (Layer 2, §5.12)              |

---

## Objective

Create the empty directory placeholders for user media file storage and ONNX model weights, each with a `.gitkeep` file so the directories are tracked by Git even when empty.

---

## Instructions

### Step 1: Create the Media Projects Directory

```bash
mkdir -p backend/media/projects
```

Then create an empty `.gitkeep` file inside it:

```bash
# Windows (PowerShell)
New-Item -Path backend\media\projects\.gitkeep -ItemType File

# Windows (CMD)
type nul > backend\media\projects\.gitkeep

# macOS/Linux
touch backend/media/projects/.gitkeep
```

> **Purpose:** This directory will store per-project media files (uploaded images, generated audio, rendered video) in later phases. The `.gitkeep` ensures the directory structure is committed to Git, even though the media files themselves are git-ignored.

---

### Step 2: Create the Models Directory

Create the `models/` directory at the **project root** (NOT inside `backend/`):

```bash
mkdir models
```

Then create an empty `.gitkeep` file inside it:

```bash
# Windows (PowerShell)
New-Item -Path models\.gitkeep -ItemType File

# Windows (CMD)
type nul > models\.gitkeep

# macOS/Linux
touch models/.gitkeep
```

> **Purpose:** This directory will store ONNX model weight files (e.g., Kokoro-82M for TTS) in Phase 03. These are large binary files (50–200 MB) and MUST be git-ignored — only the directory structure is committed.

---

### Step 3: Verify `.gitignore` Compatibility

Cross-check with the `.gitignore` created in Task 01.01.10:

| `.gitignore` Pattern            | Effect                                                    |
| ------------------------------- | --------------------------------------------------------- |
| `backend/media/projects/`      | Ignores media files inside the directory                  |
| `models/*.onnx`                | Ignores ONNX weight files but NOT `.gitkeep`              |
| `models/*.bin`                 | Ignores binary model files but NOT `.gitkeep`             |

Confirm that `.gitkeep` files are **not** excluded by any pattern. Since `.gitkeep` has no extension matching `*.onnx` or `*.bin`, it will be tracked.

---

## Expected Output

```
StoryFlow/
├── backend/
│   └── media/
│       └── projects/
│           └── .gitkeep         ← NEW
├── models/
│   └── .gitkeep                 ← NEW
├── frontend/
└── ...
```

---

## Validation

- [ ] `backend/media/projects/` directory exists.
- [ ] `backend/media/projects/.gitkeep` file exists (can be empty).
- [ ] `models/` directory exists at the project root.
- [ ] `models/.gitkeep` file exists (can be empty).
- [ ] `models/` is NOT inside `backend/` — it is at the project root level.

---

## Notes

- The `models/` directory is at the **project root** rather than inside `backend/` because model files are shared resources that may be referenced by multiple backend modules. Keeping them at the root also makes the path simpler and avoids deeply nested references.
- `.gitkeep` is a convention (not a Git feature). It is simply an empty file whose sole purpose is to force Git to track an otherwise-empty directory.
- The actual model files will be downloaded in Phase 03 (Task 03.01.01). Do NOT download any models now.

---

> **Parent:** [SubPhase_01_01_Overview.md](SubPhase_01_01_Overview.md) (Layer 2)
> **Previous Task:** [Task_01_01_11_Create_Dev_Run_Scripts.md](Task_01_01_11_Create_Dev_Run_Scripts.md)
> **Next Task:** [Task_01_01_13_Create_Root_README.md](Task_01_01_13_Create_Root_README.md)
