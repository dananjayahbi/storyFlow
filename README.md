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
python manage.py runserver 8765
```

The backend server will start at **http://localhost:8765**.

### Frontend (Next.js)

```bash
cd frontend
npm install
npm run dev -- -p 3847
```

The frontend server will start at **http://localhost:3847**.

### Quick Start Scripts

For convenience, use the provided start script from the project root:

```bash
# Windows
start-all.bat
```

---

## Workspaces & Accounts

StoryFlow has two independent workspaces: **Facebook Reels** and **YouTube
Videos**. Each workspace can hold multiple accounts (Facebook pages or YouTube
channels):

1. Open a workspace from `/select` (`/facebook` or `/youtube`).
2. The account picker lists every page/channel on that side with project and
   render counts. Create, rename or delete accounts here.
3. Click an account to enter its dashboard. Projects, gallery, bulk rendering
   and settings are then scoped to that account.
4. Switch accounts from the account chip in the top navigation; switch
   workspaces with the Facebook/YouTube buttons.

The account picker is a standalone screen: while choosing a page/channel it
shows only the Logout control, because Dashboard, Projects, Script Craft and the
other workspace pages require an account first. Selecting an account loads the
dashboard for that account. After that, the account chip in the header switches
accounts and reloads the dashboard with the newly selected account's data.

The header is a fixed 56 px rail. Navigation is a single horizontal row (it
scrolls sideways on narrow screens), so no vertical scrollbar appears in the
header. The active-page underline sits inside each link instead of overflowing
below it.

### Per-account settings

Settings are account-specific. TTS voice/engine, subtitles, render resolution,
Ken Burns/transitions, logo/outro selection and upscaling are stored in an
`AccountSettings` row per account, so one page or channel can use a completely
different setup from another. New accounts are seeded once from the workspace
defaults and then diverge. New projects snapshot the selected account's values
at creation time. The shared asset libraries (logos, outros, voice references,
fonts) remain available to every account, while each account chooses which one
to use.

Storage mirrors this hierarchy:
`backend/Storage/<Section>/<account-id>/<project-id>/`. Migration
`0013_seed_default_accounts` creates a default account on each side and moves
existing projects into it automatically.

---

## Script Craft & Script Library

StoryFlow can draft narrative scripts with an in-app AI agent instead of
maintaining JSON files outside the app.

1. Open **Script Craft** from the top navigation (it is scoped to the active
   Facebook page or YouTube channel).
2. Describe the pitch in the chat, e.g. *“A documentary video script of World
   War 2 for 20 minutes.”* The agent returns a structured script with narration
   segments and cinematic image prompts.
3. The right-hand panel parses the JSON into a readable storyboard: title,
   segment count, narration and image prompt per beat.
4. Click **Save to Library** to keep the draft in **Script Library**, also in
   the top navigation and scoped to the same account.

### Configuring the AI model

Each account has its own model and system prompt. Open
**Settings → AI Model**:

- **API base URL** — any OpenAI-compatible endpoint (Ollama, LM Studio,
  llama.cpp, vLLM, OpenAI, OpenRouter, …).
- **API key** — optional; local servers usually do not need one.
- **Model** — account-specific model id. Empty falls back to the workspace
  default.
- **System prompt** — account-specific voice, style and rules. StoryFlow always
  appends the required JSON format instructions.
- **Use this model for all accounts** — off by default. When enabled and saved,
  the model is copied to every Facebook and YouTube account, replacing their
  individual choices. A confirmation modal warns before overwriting.

The model name/prompt live on the account; the endpoint, key and temperature
are shared by the local installation. Scripts are stored per account and never
leak between accounts or between Facebook and YouTube.

---

## Directory Structure

```
StoryFlow/
├── backend/                 # Django REST API
│   ├── api/                 # Main API app (views, serializers, URLs)
│   ├── core_engine/         # Processing modules (TTS, video, effects)
│   │   ├── tts.py           # Engine dispatcher (Kokoro default / Qwen optional)
│   │   ├── qwen_client.py   # Django-side RPC client (never imports torch)
│   │   └── qwen_engine.py   # GPU worker, runs under Python 3.11
│   ├── qwen_tts/.venv/      # Isolated Qwen GPU env (git-ignored, ~5 GB)
│   ├── storyflow_backend/   # Django project settings
│   ├── Storage/             # Account-scoped project assets (git-ignored)
│   │   ├── Facebook/<account-id>/<project-id>/
│   │   ├── YouTube/<account-id>/<project-id>/
│   │   │                    # project.json, story.json, script.txt,
│   │   │                    # images/, audio/, output/, assets/
│   │   └── logos/ outros/ fonts/ voice_references/
│   ├── requirements.txt     # Python dependencies
│   └── manage.py
├── frontend/                # Next.js + TypeScript UI
│   ├── app/                 # App Router pages
│   ├── components/ui/       # Shadcn/UI components
│   ├── lib/                 # Utilities and helpers
│   └── package.json
├── models/                  # ONNX model weights (git-ignored)
├── scripts/
│   └── setup_qwen_tts.ps1   # Copy the Qwen GPU venv (no re-download)
├── start-all.bat            # Start backend + frontend
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
| TTS      | Kokoro-82M ONNX (default) + Qwen3-TTS 0.6B (optional, GPU) |
| Video    | MoviePy + Pillow (coming Phase 04)         |

---

## TTS Engines

StoryFlow ships with two speech engines and keeps Kokoro as the default.

| Engine | Device | Speed | Voice cloning | Role |
| ------ | ------ | ----- | ------------- | ---- |
| Kokoro-82M ONNX | CPU | fast | no | Default. Build a complete draft video quickly. |
| Qwen3-TTS 0.6B | CUDA GPU (required) | slower | yes | Final narration, optionally cloned from a reference clip. |

Qwen cannot run on CPU: the engine refuses to start without CUDA rather than
silently producing very slow output.

### Why Qwen lives in a separate virtualenv

Django runs on Python 3.14, but `qwen-tts` supports Python 3.10–3.12 only.
Torch/CUDA work is also kept out of the web process so sampling cannot freeze
the server. StoryFlow therefore launches a dedicated Python 3.11 worker:

```
Django (3.14) ──JSON lines──▶ backend/core_engine/qwen_engine.py (3.11 + CUDA)
```

### Setup (copy the existing venv — no re-download)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_qwen_tts.ps1
```

The script copies `E:\test_repos\TTS-test\.venv` (~5 GB, torch 2.6.0+cu124)
into `backend/qwen_tts/.venv` and verifies CUDA. Use `-Source <path>` for a
different venv and `-Force` to replace an existing copy. A fresh install is
also possible with `backend/qwen_tts/requirements-qwen.txt`.

Tuned for a GTX 1660 Ti (6 GB):

- `bfloat16` (float16 trips a device-side assert in the code predictor)
- `sdpa` attention (no prebuilt FlashAttention-2 Windows wheels)
- VRAM capped with `QWEN_TTS_VRAM_FRACTION` (default `0.72` ≈ 4.3 GB) so
  PyTorch raises a clean OOM instead of spilling into shared GPU memory

### Workflow: draft with Kokoro → finalize with Qwen

1. Open **Settings → TTS Engines** and confirm both engines are available.
2. Open **Settings → Voice References** and upload one or more clean 3–10 s
   clips (WAV/MP3/M4A/FLAC). Add the transcript for better cloning accuracy.
3. Build the project, then **Generate All Audio** (Kokoro draft).
4. Export and review the video for visual issues.
5. In the project editor, open the split-button dropdown → **Qwen — finalize
   audio**. Segments generated with Kokoro are automatically regenerated with
   Qwen, and each segment shows a Kokoro/Qwen badge.
6. Use **Settings → TTS Engines → Unload VRAM** when you are done with Qwen.

Engine choice is stored per project (default inherited from global settings),
so a project can mix a fast draft pass with a final Qwen pass at any time.

---

## Important Notes

- **Local-only application** — no Docker, no cloud APIs, no authentication, no deployment.
- **Privacy-first** — all data stays on your machine.
- This project is designed for a single-user, local development workflow.
