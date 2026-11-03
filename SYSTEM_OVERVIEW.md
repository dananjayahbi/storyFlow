# StoryFlow — System Overview

StoryFlow is a **local-first web application for producing faceless narrative
videos from text scripts**. It turns a script into narration, visuals, optional
background music and a finished video, with a human-in-the-loop editor at every
stage. It runs on one machine: no Docker, no cloud database, no cloud rendering
and no authentication.

This document is a short, AI-friendly explanation of what the system is, what it
can do and how the pieces fit together.

---

## 1. What StoryFlow does

A typical StoryFlow job is:

1. Write or generate a documentary-style script split into blocks (segments).
2. Generate or upload an image for each block.
3. Generate narration for each block with a TTS engine.
4. Optionally add background music, a logo watermark, subtitles and an outro.
5. Render the blocks into one video.
6. Preview and download the result from the Gallery.

The application is designed for short-form “faceless” videos such as Facebook
Reels and YouTube documentaries.

---

## 2. Two workspaces, many accounts

StoryFlow has two independent workspaces:

- **Facebook Reels** (`/facebook`)
- **YouTube Videos** (`/youtube`)

Each workspace contains one or more **accounts** (Facebook pages or YouTube
channels). Projects, gallery items, script chats, script libraries, BGM tracks
and settings are scoped to the active account. Facebook and YouTube data never
mix, and two accounts on the same side never see each other's projects.

Account-specific settings are stored in an `AccountSettings` row. New projects
snapshot those values when they are created. The frontend resolves the Django
origin through `NEXT_PUBLIC_API_URL` or, when unset, by probing
`/api/health/` for the `storyflow-backend` service marker. Account pages show
the origin they tried and support retrying after a backend restart.

---

## 3. Main features

### 3.1 Projects and the timeline editor

- Create an empty project or import a script as JSON/text.
- Each project contains ordered **segments** (blocks).
- Each block has narration text, an image prompt, an optional uploaded image,
  an optional generated audio file and a lock flag.
- Images are previewed inside the project's render aspect ratio and can be
  dragged to choose which part of the source is visible. The saved focus
  (`image_focus_x` / `image_focus_y`) is used by the renderer to cover-crop the
  source before Ken Burns pans and zooms inside that frame. All seven camera
  presets move, so the first block animates like every other block.
- The editor supports adding, deleting, reordering, renaming and locking blocks.
- The left sidebar has one **Settings** panel. The old Details tab was removed;
  the Story Template JSON reference now lives on the Settings page.
- Per-project settings include voice/engine, speed, subtitles, Ken Burns zoom,
  transitions, silence, logo watermark, outro, background-music track and image
  upscaling.

### 3.2 Text-to-speech

Two engines are supported:

| Engine | Device | Speed | Voice cloning | Role |
| --- | --- | --- | --- | --- |
| Kokoro-82M ONNX | CPU | fast | no | Default draft narration |
| Qwen3-TTS 0.6B | CUDA GPU | slower | yes | Final narration / cloned voice |

- Generate one block or all blocks.
- Switch a project from Kokoro draft audio to a Qwen final pass; existing
  Kokoro blocks are regenerated while Qwen blocks can be kept.
- Each block shows which engine produced its current audio.
- Download a block's narration as **WAV** or **MP3** from its overflow menu.

### 3.3 Background music (BGM Library)

- Upload MP3, WAV, FLAC, M4A, AAC, OGG, OPUS, WMA, AIFF, ALAC or WebM; every
  upload is converted to MP3 with FFmpeg.
- Play tracks in the library.
- Share a track with every account in the same workspace. Only the owner can
  rename, share or delete it.
- Generate a continuous soundtrack with **MusicGen-Small**.
- Media playback supports HTTP Range requests, so audio/video seeking works.

### 3.4 Dynamic soundtrack generation (MusicGen)

- The narration's measured TTS durations drive the music length.
- A deterministic planner keeps one BPM and root key and changes only mood.
- Music is generated in short hops with continuation and crossfades.
- Mastering includes loudness matching, noise-floor reduction, high-band tilt,
  peak taming and a tail fade.
- At render time the music bed is mixed under the narration with voice-activated
  side-chain ducking.

### 3.5 Audio Mix and the demo playground

Account-wide **Settings → Audio Mix** controls:

- **Base music level** — how loud the bed sits under the narration.
- **Voice-over ducking** — how much the music drops while speech is active.
- **Echo** — a short reflected tail applied only to the music.
- **TTS voice volume** — raises or lowers the narration against the music.

Saving propagates the values to every existing project on the account; new
projects inherit them. The project editor keeps only the track picker, the
MusicGen button and the enable checkbox.

The same tab has a three-block **demo playground**:

- upload an image and paste script text for each of three blocks;
- choose any BGM track;
- generate narration and render a demo video in place;
- every run replaces the previous demo, so settings can be tuned repeatedly.

### 3.6 Subtitles

- Optional burned-in subtitles.
- Configurable font, size, colour and position (top/center/bottom).
- Optional manual vertical position.
- Custom font upload.
- A subtitle preview is available inside the editor.

### 3.7 Logos, outros and image upscaling

- Upload logo images and burn them as watermarks with configurable scale,
  position, opacity and margin.
- Upload outro videos and append them with a crossfade.
- Optional Real-ESRGAN upscaling for source images.

### 3.8 Video rendering and Gallery

- Render all blocks into one MP4 with FFmpeg.
- Background music is mixed under the narration during rendering.
- Progress is reported per phase (segments, frames, encoding, finalising).
- Renders can be cancelled.
- Completed videos appear in the **Gallery**, with hover previews, in-browser
  playback, seeking, download and fullscreen.

### 3.9 Script Craft (AI writer)

- Chat with an OpenAI-compatible model to write documentary scripts.
- Streaming answers with visible “Thinking” and tool activity.
- The right-hand **script book** holds pages created in the session; the agent
  can read every page.
- Steering: send a follow-up while the agent is still writing.
- History: restore earlier sessions.
- Ask-user questions with optional quick replies.
- Slash commands: `/compact`, `/new`, `/stop`, `/scripts`, `/help`.
- Chat and script book are independent scroll panes; the chat does not
  auto-scroll while streaming or after a reload.
- Thinking blocks stay expandable after completion and keep reasoning from every
  tool round.
- The agent can research with a configurable web search tool
  (DuckDuckGo by default, Brave optional).

### 3.10 Script Library

- Save any Script Craft page to the account's Script Library.
- Search saved scripts by title or pitch.
- View a script in a dialog.
- **Create** a new project from a saved script: the modal lets the title be kept
  or changed, imports the script's blocks, and opens the new project. The
  original library script is untouched.

### 3.11 Settings

The Settings page is scoped to the active account and includes:

- Audio tester.
- TTS engine status and VRAM unload.
- Voice reference clips for cloning.
- Subtitle defaults.
- Logo and outro libraries.
- **Audio Mix** and the demo playground.
- **Story Template** JSON reference.
- AI model/endpoint/prompt and web search configuration.

---

## 4. Architecture

```
Next.js 16 frontend (port 3847)
        │ REST + SSE
        ▼
Django 5 + DRF backend (port 8765)
        │
        ├── SQLite database
        ├── backend/Storage/<section>/<account>/<project>/
        ├── Kokoro ONNX (CPU, in-process)
        ├── Qwen TTS worker (Python 3.11 + CUDA subprocess)
        ├── MusicGen worker (Python 3.11 + CUDA subprocess)
        └── FFmpeg / MoviePy / NumPy video pipeline
```

- The Django web process is CPU-only (Python 3.14).
- GPU work runs in isolated Python 3.11 workers so a model cannot freeze the web
  server and VRAM is released when a worker exits.
- Background jobs (TTS batches, MusicGen, rendering) run through a single-worker
  `TaskManager`, so GPU/CPU-heavy operations never overlap.
- The frontend uses Zustand stores and a typed API client. Every request is
  scoped by `section` and `account` query parameters.
- Chat streaming uses server-sent events.

---

## 5. Storage layout

```
backend/Storage/
  Facebook/<account-id>/<project-id>/
    images/  audio/  output/  assets/
  YouTube/<account-id>/<project-id>/
  bgm/<section>/<account-id>/
  logos/  outros/  fonts/  voice_references/
```

Assets are account-scoped so two accounts cannot overwrite each other's files.

---

## 6. Key API surfaces

| Area | Endpoints |
| --- | --- |
| Accounts | `/api/accounts/` |
| Projects | `/api/projects/`, `/api/projects/import/` |
| Segments | `/api/segments/`, per-segment image/audio actions |
| Narration download | `/api/segments/<id>/download-audio/?audio_format=wav|mp3` |
| Rendering | `/api/projects/<id>/render/`, `/status/`, `/cancel-render/` |
| Tasks | `/api/tasks/<task_id>/status/` |
| Settings | `/api/settings/`, `/api/settings/ai/`, `/api/settings/playground/` |
| TTS | `/api/settings/tts-test/`, project/segment audio actions |
| Scripts | `/api/scripts/` |
| Script Craft | `/api/chat/sessions/`, `/stream/`, `/steer/`, `/stop/`, `/compact/` |
| BGM | `/api/bgm/`, `/api/bgm/generate/`, `/api/bgm/engine-status/` |
| Gallery | `/api/gallery/`, per-project stream/download |

---

## 7. Current limitations

- Single-user, local-only; there is no real authentication or multi-user access
  control.
- SQLite is the only database.
- Qwen TTS and MusicGen require a CUDA GPU; CPU-only installations fall back to
  Kokoro.
- FFmpeg must be installed and on `PATH`.
- Rendering is intentionally serialised and can be slow on low-end hardware.
- The application is under active development; features and APIs may change.

---

## 8. Quick start

```bash
# Backend
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 8765

# Frontend
cd frontend
npm install
npm run dev -- -p 3847
```

Or from the project root on Windows:

```bat
start-all.bat
```

Then open <http://localhost:3847>, choose a workspace and an account, and start
a project.

---

## 9. Terminology

- **Section / workspace** — Facebook Reels or YouTube Videos.
- **Account** — a page or channel that owns projects and libraries.
- **Project** — one video; contains ordered segments and render settings.
- **Segment / block** — one image + narration + optional music timing unit.
- **BGM clip** — a background-music track owned by an account and optionally
  shared within its workspace.
- **Script page** — one generated script inside a Script Craft session.
- **Saved script** — a script page stored in the account's Script Library.
- **Playground** — a hidden three-block demo project used only by Settings.

For setup details, feature deep dives and diagnostics, see
[`README.md`](README.md).
