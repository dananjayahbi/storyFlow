# Task 01.01.13 — Create Root README

## Metadata

| Field                    | Value                                                                                                    |
| ------------------------ | -------------------------------------------------------------------------------------------------------- |
| **Sub-Phase**            | SubPhase 01.01 — Project Initialization & Tooling Setup                                                  |
| **Phase**                | Phase 01 — The Skeleton                                                                                  |
| **Document Type**        | Layer 3 — Task Document                                                                                  |
| **Estimated Complexity** | Low                                                                                                      |
| **Dependencies**         | [Task_01_01_05](Task_01_01_05_Configure_Django_Settings.md), [Task_01_01_08](Task_01_01_08_Initialize_Shadcn_UI.md) — Both projects must be fully initialized |
| **Parent Document**      | [SubPhase_01_01_Overview.md](SubPhase_01_01_Overview.md) (Layer 2, §5.13)                                |

---

## Objective

Create a root-level `README.md` that provides a project description, prerequisites, setup instructions for both backend and frontend, and a directory structure overview — reflecting only what exists after Phase 01.

---

## Instructions

### Step 1: Create `README.md`

Create `README.md` at the **project root** with the following content:

```markdown
# StoryFlow — Semi-Automated Narrative Video Engine

A local-first web application for producing "faceless" narrative videos from text scripts. StoryFlow combines AI-powered text-to-speech, automated video assembly, and a human-in-the-loop editing workflow — all running entirely on your machine with no cloud dependencies.

> ⚠️ **Work in Progress:** StoryFlow is under active development. TTS, video rendering, and other core features are coming in future phases.

---

## Prerequisites

| Tool       | Version  | Purpose                       |
| ---------- | -------- | ----------------------------- |
| Python     | 3.11+    | Backend runtime               |
| Node.js    | 18+      | Frontend runtime              |
| npm        | 9+       | Frontend package manager      |
| Git        | Any      | Version control               |

---

## Setup

### Backend (Django)

```bash
cd backend
python -m venv venv

# Activate the virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

The backend server will start at **http://localhost:8000**.

### Frontend (Next.js)

```bash
cd frontend
npm install
npm run dev
```

The frontend server will start at **http://localhost:3000**.

### Quick Start Scripts

For convenience, use the provided start scripts from the project root:

```bash
# Windows
start-backend.bat    # Terminal 1
start-frontend.bat   # Terminal 2

# macOS/Linux
bash start-backend.sh    # Terminal 1
bash start-frontend.sh   # Terminal 2
```

---

## Directory Structure

```
StoryFlow/
├── backend/                 # Django REST API
│   ├── api/                 # Main API app (views, serializers, URLs)
│   ├── core_engine/         # Processing modules (TTS, video, effects)
│   ├── storyflow_backend/   # Django project settings
│   ├── media/projects/      # Generated media files (git-ignored)
│   ├── requirements.txt     # Python dependencies
│   └── manage.py
├── frontend/                # Next.js + TypeScript UI
│   ├── app/                 # App Router pages
│   ├── components/ui/       # Shadcn/UI components
│   ├── lib/                 # Utilities and helpers
│   └── package.json
├── models/                  # ONNX model weights (git-ignored)
├── start-backend.bat/.sh    # Backend start scripts
├── start-frontend.bat/.sh   # Frontend start scripts
├── .gitignore
└── README.md
```

---

## Tech Stack

| Layer    | Technology                                  |
| -------- | ------------------------------------------- |
| Frontend | Next.js 16+, TypeScript, Tailwind CSS 4, Shadcn/UI |
| Backend  | Django 5.x, Django REST Framework           |
| Database | SQLite (local, zero-config)                 |
| TTS      | Kokoro-82M ONNX (coming Phase 03)          |
| Video    | MoviePy + Pillow (coming Phase 04)         |

---

## Important Notes

- **Local-only application** — no Docker, no cloud APIs, no authentication, no deployment.
- **Privacy-first** — all data stays on your machine.
- This project is designed for a single-user, local development workflow.
```

---

### Step 2: Review Content Accuracy

Verify the README reflects ONLY what exists after SubPhase 01.01:

- ✅ Project name and description are accurate.
- ✅ Prerequisites list Python 3.11+ and Node.js 18+.
- ✅ Backend setup instructions match the actual project structure (`storyflow_backend/`).
- ✅ Frontend setup instructions use `npm install` and `npm run dev`.
- ✅ Directory structure matches what has been created in Tasks 01.01.01–01.01.12.
- ✅ "Work in Progress" disclaimer is present.
- ✅ No mention of features that don't exist yet (no TTS commands, no video rendering commands).

---

## Expected Output

```
StoryFlow/
├── README.md                ← NEW
├── backend/
├── frontend/
└── ...
```

---

## Validation

- [ ] `README.md` exists at the project root.
- [ ] Contains project name and one-line description.
- [ ] Lists prerequisites (Python 3.11+, Node.js 18+).
- [ ] Backend setup instructions are correct and complete.
- [ ] Frontend setup instructions are correct and complete.
- [ ] References the quick start scripts (`start-backend.bat`, etc.).
- [ ] Directory structure overview matches the actual project layout.
- [ ] Includes "local-only" / "no deployment" disclaimer.
- [ ] Does NOT describe features that don't exist yet (TTS generation, video rendering commands, etc.).

---

## Notes

- This README is a living document that will be updated as new features are added in later phases. For now, it reflects only the Phase 01 skeleton.
- The "Work in Progress" banner at the top makes it clear that the project is not feature-complete.
- The README intentionally does NOT include API endpoint documentation — that belongs in SubPhase 01.03 when the actual API endpoints are built.
- This is the **last task** in SubPhase 01.01. After this task, all 13 initialization tasks are complete and the project skeleton is ready for SubPhase 01.02 (Data Modelling).

---

> **Parent:** [SubPhase_01_01_Overview.md](SubPhase_01_01_Overview.md) (Layer 2)
> **Phase:** [Phase_01_Overview.md](../../Phase_01_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../../00_Project_Overview.md) (Layer 0)
> **Previous Task:** [Task_01_01_12_Create_Media_And_Model_Dirs.md](Task_01_01_12_Create_Media_And_Model_Dirs.md)
> **Next Task:** None — SubPhase 01.01 Complete ✓
