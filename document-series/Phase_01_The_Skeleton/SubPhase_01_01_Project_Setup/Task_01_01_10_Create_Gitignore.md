# Task 01.01.10 — Create .gitignore

## Metadata

| Field                    | Value                                                                   |
| ------------------------ | ----------------------------------------------------------------------- |
| **Sub-Phase**            | SubPhase 01.01 — Project Initialization & Tooling Setup                 |
| **Phase**                | Phase 01 — The Skeleton                                                 |
| **Document Type**        | Layer 3 — Task Document                                                 |
| **Estimated Complexity** | Low                                                                     |
| **Dependencies**         | None (can be created at any time)                                       |
| **Parent Document**      | [SubPhase_01_01_Overview.md](SubPhase_01_01_Overview.md) (Layer 2, §5.10) |

---

## Objective

Create a root-level `.gitignore` file that covers all categories relevant to the StoryFlow project: Python, Django, Node.js, ONNX models, IDE files, and OS artifacts.

---

## Instructions

### Step 1: Create the `.gitignore` File

Create `.gitignore` at the **project root** (same level as `backend/` and `frontend/`) with the following content:

```gitignore
# ========================
# Python
# ========================
__pycache__/
*.py[cod]
*$py.class
*.so
venv/
.env

# ========================
# Django
# ========================
db.sqlite3
backend/media/projects/

# ========================
# Node.js
# ========================
node_modules/
.next/
out/

# ========================
# ONNX Models (large binary files)
# ========================
models/*.onnx
models/*.bin

# ========================
# IDE
# ========================
.vscode/
.idea/
*.swp
*.swo
*~

# ========================
# OS
# ========================
.DS_Store
Thumbs.db

# ========================
# Build
# ========================
dist/
build/
*.egg-info/
```

---

### Step 2: Verify Patterns

Confirm the `.gitignore` covers these critical items:

| Pattern                      | Purpose                                                         |
| ---------------------------- | --------------------------------------------------------------- |
| `__pycache__/`               | Compiled Python bytecode directories                            |
| `*.py[cod]`                  | Compiled Python files (`.pyc`, `.pyo`, `.pyd`)                  |
| `venv/`                      | Python virtual environment (Task 01.01.01)                      |
| `.env`                       | Environment variables file (if added later)                     |
| `db.sqlite3`                 | Django SQLite database (auto-generated on first migrate)        |
| `backend/media/projects/`   | User-uploaded and generated media files                         |
| `node_modules/`              | npm dependencies (Task 01.01.06)                                |
| `.next/`                     | Next.js build output                                            |
| `models/*.onnx`              | ONNX model weight files — large binaries (Phase 03)            |
| `models/*.bin`               | Model binary files (Phase 03)                                   |
| `.vscode/` / `.idea/`        | IDE-specific configuration directories                          |
| `.DS_Store` / `Thumbs.db`    | macOS / Windows system files                                    |

---

## Expected Output

```
StoryFlow/
├── .gitignore               ← NEW
├── backend/
├── frontend/
└── ...
```

---

## Validation

- [ ] `.gitignore` file exists at the project root.
- [ ] Python patterns are present (`__pycache__/`, `*.py[cod]`, `venv/`).
- [ ] Django patterns are present (`db.sqlite3`, `backend/media/projects/`).
- [ ] Node.js patterns are present (`node_modules/`, `.next/`).
- [ ] ONNX model patterns are present (`models/*.onnx`, `models/*.bin`).
- [ ] IDE and OS patterns are present.

---

## Notes

- The `.gitignore` is placed at the **project root** to cover both `backend/` and `frontend/` directories with a single file. Individual subdirectory `.gitignore` files are not needed.
- `backend/media/projects/` is ignored because user media files (images, audio, video) should not be committed. However, the `.gitkeep` file inside it (created in Task 01.01.12) uses a trick — Git tracks `.gitkeep` explicitly even inside an ignored directory, which is why `backend/media/projects/.gitkeep` can still be committed.
- The `models/` patterns use wildcards (`*.onnx`, `*.bin`) rather than ignoring the entire directory, so `models/.gitkeep` remains trackable.

---

> **Parent:** [SubPhase_01_01_Overview.md](SubPhase_01_01_Overview.md) (Layer 2)
> **Previous Task:** [Task_01_01_09_Configure_CORS.md](Task_01_01_09_Configure_CORS.md)
> **Next Task:** [Task_01_01_11_Create_Dev_Run_Scripts.md](Task_01_01_11_Create_Dev_Run_Scripts.md)
