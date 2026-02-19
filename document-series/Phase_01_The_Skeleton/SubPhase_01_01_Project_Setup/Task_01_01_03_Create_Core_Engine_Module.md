# Task 01.01.03 — Create Core Engine Module

## Metadata

| Field                    | Value                                                                                  |
| ------------------------ | -------------------------------------------------------------------------------------- |
| **Sub-Phase**            | SubPhase 01.01 — Project Initialization & Tooling Setup                                |
| **Phase**                | Phase 01 — The Skeleton                                                                |
| **Document Type**        | Layer 3 — Task Document                                                                |
| **Estimated Complexity** | Low                                                                                    |
| **Dependencies**         | [Task_01_01_01](Task_01_01_01_Initialize_Django_Project.md) — `/backend` directory must exist |
| **Parent Document**      | [SubPhase_01_01_Overview.md](SubPhase_01_01_Overview.md) (Layer 2, §5.3)               |

---

## Objective

Create the `core_engine` Python package inside `/backend` with an `__init__.py` and three placeholder files (`tts_wrapper.py`, `video_renderer.py`, `ken_burns.py`). Each placeholder contains only a module docstring describing its future purpose. This is a **regular Python package**, NOT a Django app.

---

## Instructions

### Step 1: Create the Core Engine Directory

```bash
cd backend
mkdir core_engine
```

---

### Step 2: Create `__init__.py`

Create an empty `__init__.py` to make `core_engine` a valid Python package:

**File:** `backend/core_engine/__init__.py`

```python
```

*(Empty file — no content needed.)*

---

### Step 3: Create `tts_wrapper.py` (Placeholder)

**File:** `backend/core_engine/tts_wrapper.py`

```python
"""
StoryFlow TTS Wrapper Module.

Provides text-to-speech functionality using Kokoro-82M ONNX model.
Implementation deferred to Phase 03 — The Voice.
"""
```

---

### Step 4: Create `video_renderer.py` (Placeholder)

**File:** `backend/core_engine/video_renderer.py`

```python
"""
StoryFlow Video Renderer Module.

Orchestrates MoviePy-based video assembly from image and audio segments.
Implementation deferred to Phase 04 — The Vision.
"""
```

---

### Step 5: Create `ken_burns.py` (Placeholder)

**File:** `backend/core_engine/ken_burns.py`

```python
"""
StoryFlow Ken Burns Effect Module.

Implements cinematic pan-and-zoom transformations on still images.
Implementation deferred to Phase 04 — The Vision.
"""
```

---

## Expected Output

```
backend/
├── manage.py
├── storyflow_backend/
├── api/
├── core_engine/               ← NEW
│   ├── __init__.py            ← Empty
│   ├── tts_wrapper.py         ← Docstring only
│   ├── video_renderer.py      ← Docstring only
│   └── ken_burns.py           ← Docstring only
└── venv/
```

Each placeholder file contains **only** a module-level docstring. No imports, no classes, no functions, no variables.

---

## Validation

- [ ] `backend/core_engine/` directory exists.
- [ ] `backend/core_engine/__init__.py` exists (empty file).
- [ ] `backend/core_engine/tts_wrapper.py` exists and contains only a docstring.
- [ ] `backend/core_engine/video_renderer.py` exists and contains only a docstring.
- [ ] `backend/core_engine/ken_burns.py` exists and contains only a docstring.
- [ ] None of the placeholder files contain import statements, classes, or functions.
- [ ] `core_engine` is NOT added to Django's `INSTALLED_APPS` — it is a regular Python package, not a Django app.
- [ ] Running `python -c "import core_engine"` from `/backend` (with venv activated) succeeds without errors.

---

## Notes

- `core_engine` is a **utility module**, NOT a Django app. It has no `models.py`, `admin.py`, `apps.py`, or `migrations/` directory. It must NOT be added to `INSTALLED_APPS`.
- The placeholder docstrings reference the phases where each module will be implemented: `tts_wrapper.py` in Phase 03, `video_renderer.py` and `ken_burns.py` in Phase 04. Additional files (e.g., `subtitle_engine.py`, `render_utils.py`) will be added to this package in Phase 05.
- These files establish the package structure early so that later phases can import from `core_engine` without restructuring.

---

> **Parent:** [SubPhase_01_01_Overview.md](SubPhase_01_01_Overview.md) (Layer 2)
> **Phase:** [Phase_01_Overview.md](../Phase_01_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_01_01_02_Create_Api_App.md](Task_01_01_02_Create_Api_App.md)
> **Next Task:** [Task_01_01_04_Write_Requirements_File.md](Task_01_01_04_Write_Requirements_File.md)
