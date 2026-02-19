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
