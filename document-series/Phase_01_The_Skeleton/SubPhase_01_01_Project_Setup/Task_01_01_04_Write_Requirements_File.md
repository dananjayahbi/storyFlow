# Task 01.01.04 — Write Requirements File

## Metadata

| Field                    | Value                                                                                  |
| ------------------------ | -------------------------------------------------------------------------------------- |
| **Sub-Phase**            | SubPhase 01.01 — Project Initialization & Tooling Setup                                |
| **Phase**                | Phase 01 — The Skeleton                                                                |
| **Document Type**        | Layer 3 — Task Document                                                                |
| **Estimated Complexity** | Low                                                                                    |
| **Dependencies**         | [Task_01_01_01](Task_01_01_01_Initialize_Django_Project.md) — packages already installed via pip |
| **Parent Document**      | [SubPhase_01_01_Overview.md](SubPhase_01_01_Overview.md) (Layer 2, §5.4)               |

---

## Objective

Create `backend/requirements.txt` with pinned dependency version ranges for the four foundational Python packages. This file records the packages that were installed in Task 01.01.01 and allows reproducible environment setup via `pip install -r requirements.txt`.

---

## Instructions

### Step 1: Create `requirements.txt`

**File:** `backend/requirements.txt`

```
Django>=5.0,<6.0
djangorestframework>=3.15,<4.0
django-cors-headers>=4.3,<5.0
Pillow>=10.0,<11.0
```

Each line specifies a minimum version (inclusive) and a maximum version (exclusive) to allow patch updates while preventing breaking major version changes.

| Package                 | Purpose                                            | Used Starting In  |
| ----------------------- | -------------------------------------------------- | ----------------- |
| Django                  | Web framework, ORM, admin                          | Phase 01          |
| djangorestframework     | REST API serializers, viewsets, routing             | Phase 01          |
| django-cors-headers     | Cross-origin request handling (frontend ↔ backend) | Phase 01          |
| Pillow                  | Image processing, required for `ImageField`        | Phase 01 (model), Phase 04 (processing) |

> **Critical:** Do NOT add any of the following packages — they are installed in later phases:
>
> | Package         | Deferred To | Reason                                       |
> | --------------- | ----------- | -------------------------------------------- |
> | `onnxruntime`   | Phase 03    | TTS model inference                          |
> | `moviepy`       | Phase 04    | Video assembly and rendering                 |
> | `numpy`         | Phase 03    | Array operations for audio/video processing  |
> | `soundfile`     | Phase 03    | WAV file I/O for TTS output                  |
> | `phonemizer`    | Phase 03    | Text-to-phoneme conversion for Kokoro        |

---

## Expected Output

```
backend/
├── manage.py
├── requirements.txt           ← NEW (4 lines, 4 packages)
├── storyflow_backend/
├── api/
├── core_engine/
└── venv/
```

The file contains exactly 4 package specifications, one per line, with version range constraints.

---

## Validation

- [ ] `backend/requirements.txt` exists.
- [ ] The file contains exactly 4 package lines: Django, djangorestframework, django-cors-headers, Pillow.
- [ ] Each package has a version range (not a pinned exact version or unpinned).
- [ ] Running `pip install -r requirements.txt` (in a fresh venv) completes without errors.
- [ ] No processing libraries (onnxruntime, moviepy, numpy, soundfile) are listed.

---

## Notes

- The packages were already installed in [Task 01.01.01](Task_01_01_01_Initialize_Django_Project.md) via direct `pip install`. This file simply records those dependencies for reproducibility.
- Version ranges (e.g., `>=5.0,<6.0`) are preferred over exact pins (e.g., `==5.1.4`) to allow security patches while preventing breaking changes.
- This file will be extended in later phases as new dependencies are needed (e.g., `moviepy` in Phase 04, `onnxruntime` in Phase 03).

---

> **Parent:** [SubPhase_01_01_Overview.md](SubPhase_01_01_Overview.md) (Layer 2)
> **Phase:** [Phase_01_Overview.md](../Phase_01_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_01_01_03_Create_Core_Engine_Module.md](Task_01_01_03_Create_Core_Engine_Module.md)
> **Next Task:** [Task_01_01_05_Configure_Django_Settings.md](Task_01_01_05_Configure_Django_Settings.md)
