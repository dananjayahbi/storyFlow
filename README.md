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
below it. The project editor sidebar starts directly with the project title and
status; the StoryFlow mark is shown only once, in the shared top header. The
editor sidebar has a single **Settings** panel — the old Details tab was
removed. The **Story Template** JSON reference now lives on the account
Settings page under **Settings → Story Template**. The expanded editor sidebar
is 298 px wide (10 px wider than the original 288 px) and collapses to 56 px.

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
   War 2 for 20 minutes.”* The agent streams its answer and its reasoning
   (“Thinking”) into the chat as it works.
3. The right-hand panel is a **script book**: each script the agent creates is
   a page. Use the page tabs or the arrows to move between them. The agent can
   read every page in the session through its tools, so follow-up questions can
   refer to earlier scripts.
4. Click **Save to Library** to keep the current page in **Script Library**,
   also in the top navigation and scoped to the same account.
5. In **Script Library**, each saved script has a **Create** button. It opens a
   dialog where the title can be kept or changed, then imports the script into a
   new project and opens that project. The original library script is not
   modified or removed.
6. Select a block in the current page and either type an instruction or press
   **Rewrite**. The agent rewrites only that segment and keeps the rest of the
   script intact.

### Chat controls

- **Stop** interrupts a streaming answer. The partial reply is kept.
- **Steering** — while the agent is writing, send another message; it is
  delivered mid-turn and the agent adapts immediately.
- **History** restores earlier sessions. The last session used by an account is
  reopened automatically when you return to the page.
- **Questions** — the agent can call an `ask_user` tool and pause with a
  question (plus optional quick-reply buttons) instead of guessing.
- **Manual scrolling** — the chat and the script book are separate scroll
  panes. The chat never auto-scrolls to the bottom while streaming or after a
  reload, so the book stays where you left it.
- **Thinking** — the reasoning block stays expandable after the answer
  completes and keeps the reasoning from every tool round, not just the last
  one.
- **Slash commands** — type `/` in the composer. The command panel scrolls
  inside the chat pane, so it is never clipped by the viewport:
  - `/compact` summarises earlier turns into a note so the context stays small
    (the visible history is kept).
  - `/new` starts a fresh chat with an empty book.
  - `/stop` stops the current answer.
  - `/scripts` lists the pages in this session.
  - `/help` lists the commands.

Chat sessions, messages, compaction summaries and script pages are stored in
the database per account, so reloading or leaving the page does not lose work.

### Agent tools

The agent uses standard OpenAI-compatible tool calls. If a local model ignores
tools and prints a JSON script instead, StoryFlow still detects it and adds the
page to the book.

| Tool | Purpose |
| --- | --- |
| `create_script` | Add a new page to the session's book. |
| `update_script` | Replace a page's title and/or segments. |
| `rewrite_segment` | Rewrite one selected block. |
| `list_scripts` | List every page in the session. |
| `read_script` | Read all segments of a page. |
| `ask_user` | Ask the human a question and pause. |

Streaming uses server-sent events (`/api/chat/sessions/<id>/stream/`), with
separate endpoints for steering, stopping and compaction. No third-party AI
SDK is required; the client speaks the OpenAI-compatible protocol using
Python's standard library.

### BGM Library

Open **BGM Library** in the top navigation to manage background music for the
active account. The library is scoped by domain (Facebook/YouTube) and by
account.

- Upload **MP3, WAV, FLAC, M4A, AAC, OGG, OPUS, WMA, AIFF, ALAC or WebM**.
  Every upload is converted to MP3 with FFmpeg before it is stored, so a single
  format is used everywhere. FFmpeg must be installed and on `PATH`.
- Play tracks directly in the library with the inbuilt player.
- **Share** a track to make it visible to every account in the same domain
  (Facebook tracks stay on Facebook, YouTube tracks stay on YouTube). Shared
  tracks carry a **Shared** badge and the owner account name. Only the account
  that uploaded a track can rename, share or delete it.
- Track names and sharing can be changed after upload; delete removes the MP3
  as well.
- The upload grid labels every control (Audio file, Track name and Sharing) and
  aligns the three fields on the same top baseline, so the helper text under the
  file input no longer pushes the other labels down. Track cards reserve two
  title lines and keep the MP3/Shared badges, player, Share button and
  rename/delete actions on consistent heights, including when one title wraps.

Files live under `Storage/bgm/<section>/<account-id>/` and the metadata is
stored per account in the database.

#### Audio/video seeking

The library player's timeline uses the browser's native media element. Seeking
requires the server to answer HTTP `Range` requests, which Django's default
`static()` development handler does not implement. StoryFlow therefore replaces
`/media/` with a range-capable view (`api/media_views.py`): it returns `206
Partial Content` and `Accept-Ranges: bytes` for media files. The player also
keeps a single `<audio>` element mounted for the lifetime of the component and
commits the final slider value on pointer/key release, so dragging the timeline
never fights with `timeupdate` events.

### Dynamic soundtrack generation (MusicGen)

StoryFlow can compose a continuous soundtrack for a documentary script with
Meta AudioCraft **MusicGen-Small** (`facebook/musicgen-small`, 300 M
parameters). Unlike a static music loop, the score follows the narration:

1. Every segment's **measured TTS duration** (not a hard-coded timing) becomes
   the target length for that block.
2. A deterministic planner keeps **the same BPM and root key** for all scenes
   and only changes instrumentation/mood (`quiet mystery → rising tension`), so
   the music cannot drift into a different key.
3. Segment 0 is generated cold from its text prompt. Every later hop uses
   `generate_continuation()` with the **trailing 3 seconds** of the previous raw
   audio tensor.
4. Chunks are joined with a **3-second crossfade** so there is no loudness dip
   at scene changes.
5. At render time the finished music bed is multiplexed under the narration
   with **voice-activated side-chain ducking** (default −12 dB, configurable
   −30…0 dB), then mixed with the Ken Burns video frames.

##### Short hops and mastering (block continuity)

MusicGen drifts during long continuations. Measured on the 6 GB target GPU
(`scripts/diagnose_musicgen_seams.py`), a 33 s hop produced peaks above 1.5
with thousands of samples over full scale, a 10 dB block-to-block loudness
spread and a 27 dB swing inside one block, while 12 s hops stayed clean
(peak 0.43, no overs, 1.8 dB spread). Every block is therefore generated in
hops of at most `MAX_GENERATION_SECONDS` (12 s), each conditioned on the
previous hop's tail and reusing its block prompt, and the result is mastered
before it is written:

- **Loudness matching** — each hop's body is scaled to
  `TARGET_CHUNK_RMS_DBFS` (−16 dBFS), so changing block no longer sounds like
  a hard cut to a different level. Boosts are capped at `MAX_CHUNK_BOOST_DB`
  (18 dB) so a near-silent passage is not amplified into hiss.
- **Level-gliding seam** — the crossfade region is the previous hop's tail
  repeated by the continuation prompt, so it receives a gain ramp that opens
  at the outgoing tail's level and closes on the target loudness. The seam
  therefore never steps, whichever way the two hops' own gains differ.
- **Correlation-corrected crossfade** — a textbook equal-power pair raises
  duplicated audio by up to +3 dB mid-seam; the overlap's real correlation is
  measured, so identical material blends linearly (flat level) while unrelated
  material keeps constant power.
- **Peak taming then scale, never clip** — isolated over-range peaks (raw hops
  reach ±2.2) are ridden down with a fast-attack / 80 ms-release gain curve
  *before* the track is fitted to `MASTER_PEAK_CEILING` (0.95). Scaling the
  whole track instead would cost ~8 dB of loudness everywhere, and
  `np.clip`-ing to ±1.0 is what made the end of a soundtrack sound harsh and
  unrealistic.

The generation result reports `generation_steps`, `chunk_gains_db`,
`target_rms_dbfs`, `noise_reduction_db`, `tail_fade_seconds`, `master_peak`
and `master_tail_level_db` for diagnostics.

##### High-frequency noise and a smooth ending (Issue #13)

Two problems were measured on a reported soundtrack: a high-frequency noise
that appeared after ~40 s and grew much worse towards the end, and an ending
that stopped dead instead of resolving.

**Why the noise appeared where it did.** MusicGen leaves a broadband floor
between the notes whose absolute level barely changes from hop to hop, while
the music around it swings by 15 dB or more. Loudness matching therefore pumps
that floor exactly where the music is quietest — the closing hops. On the
reported track the 2–6 kHz band sat at **−80 dB** through the loud middle and
at **−31 dB** in the quiet final hops, so the floor switched on and off *at hop
boundaries*: audibly, noise interrupting the music, worst at the end. Two
stages now remove it, in this order:

- **Noise-floor gate** (`reduce_noise_floor`, per hop, *before* the boost) —
  each bin's floor is taken from its `NOISE_PERCENTILE` magnitude over time and
  subtracted (`NOISE_FLOOR_SCALE` compensates for a low percentile sitting
  under the noise's mean), capped at `MAX_NOISE_REDUCTION_DB` (12 dB). A bin
  standing `NOISE_PEAK_PROTECT_DB` above its spectral neighbours is a musical
  partial and is never touched, and everything below `NOISE_CUTOFF_HZ` is
  exempt, so sustained notes, bright timbres and bass fundamentals survive.
  Measured on reference material: ~9 dB of floor removed with a sustained
  chord within 0.3 dB.
- **High-band tilt** (`tilt_high_band`, on the stitched track) — the gate
  deliberately leaves spectral peaks alone, so the bright high-register
  remainder is handled separately. The 2–8 kHz band is compared with the
  500 Hz–2 kHz body frame by frame and anything above `HF_TILT_TARGET_DB`
  (18 dB) is pulled back, capped at `HF_TILT_MAX_DB` (10 dB). The correction
  is smoothed over `HF_TILT_SMOOTH_SECONDS` (3 s) and rolled in over
  `HF_TILT_RAMP_BAND` (1.4–2.6 kHz — starting just above the melody's
  fundamentals, whose harmonics sit there, and fully in by the band where the
  reported ending's excess actually lives), so it is a slow shelf that glides
  across hop seams rather than a gate that steps.

Measured on the reported file itself, with its high band fed through both
stages in pipeline order: the worst 5 s window goes from **−8.9 dB to
−12.3 dB** relative to the body, the last 10 s from −14.1 dB to −17.5 dB and
the high band's peak share from 0.361 % to 0.152 % — while the track's
loudness moves by 0.07 dB and the clean middle stays within 0.3 dB. On real
GPU hops the gate alone takes the 2–6 kHz floor down **4.7–7.7 dB** for a
0.04–0.37 dB change in the hop's level.

**Why the track stopped dead.** The writer simply ran out of samples: the
reported file's last second was still at about −12.5 dB and *rising*, final
sample 0.128. The master now ends with `apply_tail_fade`: a cosine
(equal-power) curve over `TAIL_FADE_SECONDS` (4 s, capped at
`TAIL_FADE_MAX_FRACTION` of the clip for short ones), so perceived loudness
falls smoothly and the last sample is exactly zero — measured at −30.3 dB for
the last second against a −16.4 dB body, with a zero final sample.

The render is kept consistent with that:

- `mix_background_music` detects an existing fade (`detect_tail_fade_seconds`,
  which only reports one when the tail decays monotonically to near silence
  from around the loudest level of the region) and **skips its own tail fade**
  in that case — two fades stacked would pull the music out of the video far
  too early.
- When the bed does have to be looped to cover a longer narration,
  `loop_music_bed` strips the baked fade from the copies it joins and
  crossfades them (`MUSIC_LOOP_CROSSFADE_SECONDS`, 2 s). The old `np.tile`
  produced a hard cut at every loop point.

Generated tracks are saved to the account's BGM Library with `source=generated`
and can be attached to a project automatically. Uploaded tracks can be selected
in the same place.

#### Timeline controls and progress

When a project has background music enabled, the timeline action bar shows the
track picker and **Generate with MusicGen** next to **Generate All Audio**.
Starting a soundtrack from either surface uses the same shared store, so the
detailed progress meter (phase description, `n/N` segments, percentage and bar)
appears above the action bar exactly like the TTS bulk-generation meter. The
project settings panel keeps the full background-music controls (enable/disable,
track selection, music level, ducking and crossfade); the toolbar is the fast
path used while editing.

#### Setup

Django itself is deliberately **CPU-only** (Python 3.14), so MusicGen runs in
the same Python 3.11 + CUDA environment already used by Qwen TTS. StoryFlow
launches `core_engine/musicgen_worker.py` as a one-shot subprocess: the worker
loads the model, generates on CUDA, writes the WAV, and exits (freeing VRAM).

1. Download the checkpoint from Hugging Face (about 2.4 GB):

   ```bash
   backend\qwen_tts\.venv\Scripts\python.exe scripts\download_musicgen.py
   ```

   The official model page is
   <https://huggingface.co/facebook/musicgen-small>; the architecture reference
   is <https://github.com/facebookresearch/audiocraft>. The script fetches only
   the files Transformers needs and writes them to `models/musicgen-small`.

   The script verifies the 2.36 GB `model.safetensors` against Hugging Face's
   SHA-256 (`1bdc99d4…5090d`). This matters: a truncated or partially-resumed
   file still loads without an error, but MusicGen then outputs **pure noise**.
   The GPU worker repeats the check before inference (cached by size + mtime),
   so a corrupt checkpoint is reported as unavailable instead of producing
   static. To re-check an existing download without fetching anything:

   ```bash
   backend\qwen_tts\.venv\Scripts\python.exe scripts\download_musicgen.py --verify-only
   ```

2. Verify the CUDA worker:

   ```bash
   backend\qwen_tts\.venv\Scripts\python.exe backend\core_engine\musicgen_worker.py ^
     --probe --model models\musicgen-small
   ```

   Generate a short two-segment smoke test (cold start + continuation):

   ```bash
   backend\qwen_tts\.venv\Scripts\python.exe scripts\test_musicgen_gpu.py --seconds 2
   ```

   On the target GTX 1660 Ti this measured **96 % GPU utilisation**, about
   **3.0 GB peak VRAM** and returned to the ~1.4 GB desktop baseline as soon as
   the worker exited. CPU inference is never used when the CUDA worker is
   available.

3. Check the runtime from Django:

   ```bash
   backend\venv\Scripts\python.exe backend\manage.py shell -c ^
     "from core_engine import music_generator; print(music_generator.engine_status())"
   ```

The worker uses `MUSICGEN_PYTHON` (default:
`backend/qwen_tts/.venv/Scripts/python.exe`) and `MUSICGEN_MODEL_DIR`
(default: `models/musicgen-small`). Both can be overridden through environment
variables. `/api/bgm/engine-status/` reports the CUDA device, GPU name, VRAM,
Transformers version, whether the weights passed the checksum, and any missing
model files.

The Transformers implementation of the same `facebook/musicgen-small`
checkpoint is used instead of installing AudioCraft into Python 3.14. It
produces identical MusicGen weights while fitting the existing Python 3.11
CUDA venv. Set `MUSICGEN_ALLOW_CPU=1` only for slow smoke tests; the target
GTX 1660 Ti uses CUDA FP16 (~1.2 GB of weights).

#### Soundtrack quality diagnostics

Three scripts reproduce the failure modes that have made generated music sound
wrong, so regressions are measurable instead of a matter of taste:

- `scripts/diagnose_musicgen_seams.py [--durations 12,12,12]` — generates the
  blocks on the GPU and prints, per hop, its loudness, peak, crest factor,
  count of samples above full scale, 5 s level profile and 2–6 kHz
  mean/floor/share, plus every seam's level step and correlation. It then shows
  the noise-floor gate's raw → gated figures for each hop, runs the same chunks
  through the mastering chain (denoise, loudness match, high-band tilt, peak
  ceiling, tail fade) and prints the finished block spread, seam steps, tail
  level and a 5 s profile of high-band share *and* high-minus-body balance.
  `--prompts`, `--bpm`, `--root-key` and `--mode` reproduce a specific track;
  `--no-hops` falls back to the old one-chunk-per-block generation.

  ```bash
  backend\qwen_tts\.venv\Scripts\python.exe scripts\diagnose_musicgen_seams.py --durations 30,30,30
  ```

- `scripts/diagnose_musicgen_quality.py` — spectral flatness / zero-crossing
  rate for a generated file: flatness near `0.00005` is tonal music, above
  `0.05` is noise.
- `scripts/verify_issue17.py` — end-to-end check (Django → CUDA worker → MP3 →
  BGM clip) of block levels, seam steps, clipping, the high-band balance every
  5 s and the level of the track's last second, for a three-block script
  (Issues #17 and #13):

  ```bash
  backend\venv\Scripts\python.exe backend\manage.py shell -c ^
    "exec(open(r'scripts\verify_issue17.py', encoding='utf-8-sig').read())"
  ```

#### VRAM hand-off (6 GB GPU)

MusicGen never shares the GPU with a TTS model. Before a generation job starts,
StoryFlow unloads the resident **Kokoro ONNX session** and stops the **Qwen TTS
worker process**, then flushes the CUDA cache. Generation itself is serialised
through the single `TaskManager` worker (plus an internal lock), so TTS, image
generation, MusicGen and video rendering cannot overlap. The GPU work happens
in a dedicated one-shot worker process, so when generation finishes the process
exits and the CUDA context (including the model, EnCodec encoder and KV cache)
is destroyed. The worker also calls `gc.collect()` and
`torch.cuda.empty_cache()` before exiting.

#### API

```http
POST /api/bgm/generate/?section=facebook&account=<uuid>
Content-Type: application/json

{"project": "<project-uuid>", "name": "Optional clip name"}
```

or score a raw script whose segment durations were measured elsewhere:

```http
POST /api/bgm/generate/?section=facebook&account=<uuid>
Content-Type: application/json

{"segments": [
  {"text_content": "...", "image_prompt": "...", "duration": 12.4}
]}
```

The response is `202 Accepted` with a `task_id`; poll
`GET /api/tasks/<task_id>/status/` for progress. Optional body fields are `bpm`,
`root_key` (or `key`), `mode` (`major`/`minor`), `style` and `attach` (default
`true`). A missing/CPU-only MusicGen runtime returns `503` with setup
instructions instead of failing silently.

#### Render settings

Each project stores `bgm_enabled`, `active_bgm`, `bgm_gain_db` (default −18 dB),
`bgm_ducking_db` (default −12 dB) and `bgm_crossfade_ms`. They can be changed
from **Project → Settings → Background Music** or with a normal `PATCH` to
`/api/projects/<id>/`. If music mixing fails, the video still renders with
narration only and the failure is returned in the render warnings.

#### Audio Mix & demo playground

The music level, voice-over ducking, echo and TTS voice volume are
account-wide controls on **Settings → Audio Mix**:

- **Base music level** (`bgm_gain_db`) — level of the bed under the narration.
- **Voice-over ducking** (`bgm_ducking_db`) — attenuation while speech is active.
- **Echo** (`bgm_echo_percent`) — short reflected tail applied to the music only.
- **TTS voice volume** (`tts_gain_db`) — raises or lowers the narration against
  the music.

Saving these values writes them to the account's `AccountSettings` row and
propagates them to every existing project, so the next render uses the new
tuning. New projects inherit the values at creation time. The project editor
keeps only the track picker, the MusicGen button and the enable checkbox.

The same tab contains a three-block demo playground. Upload an image and paste
the script text for each block, choose a BGM track, then press **Generate Demo
Video**. StoryFlow narrates the blocks with the current account voice settings,
mixes them with the current Audio Mix values and renders a preview in place.
Every run replaces the previous demo video, so the controls can be tuned
repeatedly without creating projects. The playground is stored as a hidden
`Project` (`is_playground=True`) and never appears in the project list, gallery
or account counts.

Run the checks:

```bash
backend\venv\Scripts\python.exe backend\manage.py test tests.test_playground
cd frontend && npm test
```

### Gallery

The Gallery shows rendered videos as a responsive masonry of compact
thumbnails: 2 columns on phones, scaling up to 6 columns on wide screens. Hover
a tile for a muted preview, click it for the full player (seek, volume, speed,
loop, picture-in-picture and fullscreen), or use the download button.

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

### Web search

The agent can research facts with a `web_search` tool. Configure it in the same
**Settings → AI Model** tab:

- **Enable web search** — on by default.
- **Search provider** — **DuckDuckGo** works without a key and is the default.
  **Brave Search** is optional and requires a Brave Search API subscription
  token.
- **Region** — DuckDuckGo region/language code such as `us-en`, `gb-en` or
  `wt-wt` (no preference).

Search settings are shared by the installation, like the AI endpoint and API
key. Brave is only queried when selected; if it is selected without a key the
agent reports the misconfiguration instead of guessing. No search SDK is
required — both providers use Python's standard library.

---

## Directory Structure

```
StoryFlow/
├── backend/                 # Django REST API
│   ├── api/                 # Main API app (views, serializers, URLs)
│   ├── core_engine/         # Processing modules (TTS, video, effects)
│   │   ├── tts.py           # Engine dispatcher (Kokoro default / Qwen optional)
│   │   ├── qwen_client.py   # Django-side RPC client (never imports torch)
│   │   ├── qwen_engine.py   # GPU worker, runs under Python 3.11
│   │   ├── music_generator.py # MusicGen planner, continuation, crossfade, ducking
│   │   └── audio_convert.py # FFmpeg probe/convert helpers for BGM
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
6. Use the segment's overflow menu to download its narration as **WAV** or
   **MP3**; MP3 conversion uses FFmpeg.
7. Use **Settings → TTS Engines → Unload VRAM** when you are done with Qwen.

Engine choice is stored per project (default inherited from global settings),
so a project can mix a fast draft pass with a final Qwen pass at any time.

---

## Important Notes

- **Local-only application** — no Docker, no cloud APIs, no authentication, no deployment.
- **Privacy-first** — all data stays on your machine.
- This project is designed for a single-user, local development workflow.
- Source files and user-facing strings are UTF-8. Use real Unicode punctuation
  (`—`, `…`, `·`) rather than double-encoded mojibake; the frontend encoding
  regression test fails if those characters reappear.
