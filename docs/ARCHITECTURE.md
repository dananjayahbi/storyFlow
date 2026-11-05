# StoryFlow — Comprehensive Architecture Document

> **Version:** 1.0  
> **Last Updated:** February 26, 2026  
> **Project:** StoryFlow — Semi-Automated Narrative Video Engine

---

## Table of Contents

- [StoryFlow — Comprehensive Architecture Document](#storyflow--comprehensive-architecture-document)
  - [Table of Contents](#table-of-contents)
  - [1. Executive Summary](#1-executive-summary)
    - [What StoryFlow Does](#what-storyflow-does)
  - [2. System Overview](#2-system-overview)
  - [3. High-Level Architecture Diagram](#3-high-level-architecture-diagram)
  - [4. Technology Stack](#4-technology-stack)
    - [Backend](#backend)
    - [Frontend](#frontend)
  - [5. Directory Structure](#5-directory-structure)
  - [6. Backend Architecture](#6-backend-architecture)
    - [6.1 Django Project Configuration](#61-django-project-configuration)
    - [6.2 Data Models](#62-data-models)
      - [Project Model (Core Entity)](#project-model-core-entity)
      - [Rendering Model (Gallery Asset)](#rendering-model-gallery-asset)
      - [Segment Model (Content Unit)](#segment-model-content-unit)
      - [GlobalSettings Model (Singleton)](#globalsettings-model-singleton)
      - [Logo \& OutroVideo Models](#logo--outrovideo-models)
    - [6.3 REST API Layer](#63-rest-api-layer)
      - [Project Endpoints](#project-endpoints)
      - [Segment Endpoints](#segment-endpoints)
      - [Settings Endpoints](#settings-endpoints)
      - [Task \& Gallery Endpoints](#task--gallery-endpoints)
    - [6.4 Serializers \& Validation](#64-serializers--validation)
    - [6.5 Background Task System](#65-background-task-system)
    - [6.6 Import / Parse Engine](#66-import--parse-engine)
      - [JSON Format](#json-format)
      - [Plain Text Format](#plain-text-format)
  - [7. Core Engine — Processing Pipeline](#7-core-engine--processing-pipeline)
    - [7.1 Video Renderer (Orchestrator)](#71-video-renderer-orchestrator)
    - [7.2 Fast Compositor](#72-fast-compositor)
    - [7.3 Ken Burns Effect Engine](#73-ken-burns-effect-engine)
    - [7.4 Text-to-Speech (TTS) Wrapper](#74-text-to-speech-tts-wrapper)
    - [7.4.1 Optional Qwen3-TTS Engine (GPU + voice cloning)](#741-optional-qwen3-tts-engine-gpu--voice-cloning)
    - [7.5 Subtitle Engine](#75-subtitle-engine)
    - [7.6 Image Upscaler (Real-ESRGAN)](#76-image-upscaler-real-esrgan)
    - [7.7 Audio Utilities](#77-audio-utilities)
    - [7.8 Render Utilities](#78-render-utilities)
    - [7.9 Model Loader](#79-model-loader)
  - [8. Frontend Architecture](#8-frontend-architecture)
    - [8.1 Routing \& Pages](#81-routing--pages)
    - [8.2 Layout System](#82-layout-system)
    - [8.3 State Management (Zustand)](#83-state-management-zustand)
      - [`useProjectStore` (Main Store)](#useprojectstore-main-store)
      - [`useSettingsStore` (Settings Store)](#usesettingsstore-settings-store)
    - [8.4 API Client Layer](#84-api-client-layer)
    - [8.5 Component Library](#85-component-library)
    - [8.6 Key UI Features](#86-key-ui-features)
      - [Timeline Editor (Core Workspace)](#timeline-editor-core-workspace)
      - [Keyboard Shortcuts](#keyboard-shortcuts)
      - [Bulk Render Queue](#bulk-render-queue)
      - [Gallery (Video Browser)](#gallery-video-browser)
  - [9. Data Flow Diagrams](#9-data-flow-diagrams)
    - [9.1 Project Creation \& Import Flow](#91-project-creation--import-flow)
    - [9.2 Audio Generation Flow](#92-audio-generation-flow)
    - [9.3 Video Rendering Pipeline](#93-video-rendering-pipeline)
  - [10. Implemented Features List](#10-implemented-features-list)
    - [Project Management](#project-management)
    - [Segment Management](#segment-management)
    - [Text-to-Speech](#text-to-speech)
    - [Video Rendering](#video-rendering)
    - [Gallery \& Media](#gallery--media)
    - [Settings \& Configuration](#settings--configuration)
    - [Bulk Operations](#bulk-operations)
    - [UI/UX](#uiux)
    - [Developer Experience](#developer-experience)
  - [11. API Reference Summary](#11-api-reference-summary)
    - [Projects API](#projects-api)
    - [Segments API](#segments-api)
    - [Settings API](#settings-api)
    - [Tasks \& Gallery API](#tasks--gallery-api)
  - [12. Error Handling Strategy](#12-error-handling-strategy)
  - [13. Performance Optimizations](#13-performance-optimizations)
    - [Backend](#backend-1)
    - [Frontend](#frontend-1)
  - [14. Security \& Design Constraints](#14-security--design-constraints)
    - [Intentional Design Decisions](#intentional-design-decisions)
    - [File Upload Security](#file-upload-security)
    - [Resource Protection](#resource-protection)
  - [15. Appendix](#15-appendix)
    - [A. Environment Requirements](#a-environment-requirements)
    - [B. ML Models](#b-ml-models)
    - [C. Development Phase Documentation](#c-development-phase-documentation)
    - [D. Quick Start](#d-quick-start)

---

## 1. Executive Summary

**StoryFlow** is a local-first, privacy-focused web application designed for producing "faceless" narrative videos from text scripts. It is a **semi-automated narrative video engine** that combines:

- **AI-powered text-to-speech** (Kokoro-82M ONNX model)
- **Automated video assembly** with Ken Burns effects, crossfade transitions, and subtitle overlays
- **A human-in-the-loop editing workflow** via a modern web UI

The entire system runs locally on the user's machine — no cloud APIs, no Docker containers, no authentication, and no deployment infrastructure. It is designed as a **single-user, local development workflow tool**.

### What StoryFlow Does

1. **Import a story script** → Users paste/import JSON or plain-text scripts containing narration segments
2. **Upload images** → Each segment gets a visual (drag-and-drop image upload)
3. **Generate narration** → AI text-to-speech converts text to high-quality speech audio
4. **Render a video** → The system composites everything into a professional narrated video with:
   - Ken Burns zoom-and-pan effects on images
   - Crossfade transitions between segments
   - Timed subtitle overlays
   - Optional logo watermarks
   - Optional outro video clips
   - Optional AI image upscaling (Real-ESRGAN)

---

## 2. System Overview

StoryFlow follows a **client-server architecture** with two independent processes communicating over HTTP REST:

```
┌─────────────────────────────────────────────────────────────┐
│                        USER'S MACHINE                       │
│                                                             │
│  ┌──────────────────┐     HTTP/REST      ┌──────────────────┐
│  │   FRONTEND        │◄────────────────►│    BACKEND         │
│  │   Next.js 16      │   localhost:3000  │    Django 5        │
│  │   React 19        │   ──────────────► │    DRF             │
│  │   TypeScript 5    │   localhost:8000  │    SQLite           │
│  │   Tailwind CSS 4  │                  │    Python 3.11+     │
│  │   Zustand 5       │                  │                     │
│  └──────────────────┘                   │  ┌──────────────────┤
│                                          │  │  CORE ENGINE     │
│                                          │  │  ─────────────── │
│                                          │  │  TTS (Kokoro)    │
│                                          │  │  Video Renderer  │
│                                          │  │  Ken Burns       │
│                                          │  │  Subtitles       │
│                                          │  │  Upscaler        │
│                                          │  │  FFmpeg          │
│                                          │  └──────────────────┤
│                                          └───────────────────┘
│                                                             │
│  ┌──────────────────┐                ┌──────────────────────┐
│  │  models/           │              │  backend/Storage/     │
│  │  kokoro-v0_19.onnx │              │  Facebook/<id>/       │
│  │  voices/           │              │    images/            │
│  │  upscalers/        │              │    audio/             │
│  └──────────────────┘                │    output/            │
│                                      │  YouTube/<id>/        │
│                                      │  logos/               │
│                                      │  outros/              │
│                                      └──────────────────────┘
└─────────────────────────────────────────────────────────────┘
```

---

## 3. High-Level Architecture Diagram

```
                    ┌──────────────────────────────────────────────┐
                    │              FRONTEND (Next.js)               │
                    │                                              │
                    │  ┌─────────┐  ┌──────────┐  ┌────────────┐  │
                    │  │Dashboard│  │ Timeline  │  │  Gallery   │  │
                    │  │  Page   │  │  Editor   │  │   Page     │  │
                    │  └────┬────┘  └─────┬─────┘  └─────┬──────┘  │
                    │       │             │              │          │
                    │  ┌────▼─────────────▼──────────────▼───────┐  │
                    │  │          Zustand State Stores            │  │
                    │  │   useProjectStore  │  useSettingsStore   │  │
                    │  └──────────────────┬──────────────────────┘  │
                    │                     │                         │
                    │  ┌──────────────────▼──────────────────────┐  │
                    │  │          Axios API Client (lib/api.ts)  │  │
                    │  └──────────────────┬──────────────────────┘  │
                    └─────────────────────┼────────────────────────┘
                                          │
                              HTTP REST (localhost:8000)
                                          │
                    ┌─────────────────────┼────────────────────────┐
                    │         BACKEND (Django + DRF)               │
                    │                     │                         │
                    │  ┌──────────────────▼──────────────────────┐  │
                    │  │     URL Router (api/urls.py)            │  │
                    │  └──────┬──────────┬──────────┬────────────┘  │
                    │         │          │          │               │
                    │  ┌──────▼───┐ ┌────▼────┐ ┌──▼──────────┐   │
                    │  │ ViewSets │ │Function │ │ Serializers │   │
                    │  │ Project  │ │ Views   │ │ Validators  │   │
                    │  │ Segment  │ │(import, │ │ Parsers     │   │
                    │  │          │ │settings,│ │             │   │
                    │  │          │ │gallery) │ │             │   │
                    │  └──────┬───┘ └────┬────┘ └─────────────┘   │
                    │         │          │                          │
                    │  ┌──────▼──────────▼──────────────────────┐  │
                    │  │         Django ORM + SQLite             │  │
                    │  │   Project │ Segment │ Logo │ Outro     │  │
                    │  │   GlobalSettings (Singleton)           │  │
                    │  └────────────────────────────────────────┘  │
                    │                                              │
                    │  ┌────────────────────────────────────────┐  │
                    │  │       Task Manager (Singleton)         │  │
                    │  │   ThreadPoolExecutor(max_workers=1)    │  │
                    │  │   In-memory task registry              │  │
                    │  │   Cooperative cancellation             │  │
                    │  └────────────┬───────────────────────────┘  │
                    │               │                               │
                    │  ┌────────────▼───────────────────────────┐  │
                    │  │          CORE ENGINE                    │  │
                    │  │                                        │  │
                    │  │  ┌────────────┐  ┌─────────────────┐   │  │
                    │  │  │ TTS Wrapper│  │ Video Renderer  │   │  │
                    │  │  │ (Kokoro)   │  │ (Orchestrator)  │   │  │
                    │  │  └────────────┘  └────────┬────────┘   │  │
                    │  │                           │            │  │
                    │  │  ┌─────────┐ ┌────────────▼─────────┐  │  │
                    │  │  │Upscaler │ │  Fast Compositor     │  │  │
                    │  │  │(ESRGAN) │ │  (NumPy + FFmpeg)    │  │  │
                    │  │  └─────────┘ └──┬──────┬──────┬─────┘  │  │
                    │  │                 │      │      │         │  │
                    │  │  ┌──────────┐ ┌─▼──┐ ┌▼────┐ ┌▼─────┐  │  │
                    │  │  │Audio Util│ │Ken │ │Sub- │ │Logo  │  │  │
                    │  │  │          │ │Burn│ │title│ │Over- │  │  │
                    │  │  │          │ │    │ │Eng. │ │lay   │  │  │
                    │  │  └──────────┘ └────┘ └─────┘ └──────┘  │  │
                    │  └────────────────────────────────────────┘  │
                    └──────────────────────────────────────────────┘
```

---

## 4. Technology Stack

### Backend

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| Web Framework | Django | 5.x | HTTP server, ORM, admin |
| REST API | Django REST Framework | 3.15+ | Serializers, viewsets, routing |
| Database | SQLite | 3 | Zero-config local database |
| CORS | django-cors-headers | 4.3+ | Cross-origin requests from frontend |
| Image Processing | Pillow | 11.0+ | Validation, resizing, RGB operations |
| TTS Model | Kokoro-82M (ONNX) | v0.19 | Text-to-speech inference |
| ONNX Runtime | onnxruntime | 1.17+ | ML model execution |
| Audio I/O | soundfile | 0.12+ | WAV read/write |
| Video Compositing | MoviePy | 1.0+ | Audio compositing, clip management |
| Computer Vision | OpenCV (headless) | 4.8+ | Ken Burns, upscaling, image ops |
| Deep Learning | PyTorch | (optional) | Real-ESRGAN upscaling |
| Math | NumPy | 1.26+ | Array operations throughout |
| External Tool | FFmpeg | any | Video encoding, probing, muxing |

### Frontend

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| Framework | Next.js | 16.1.6 | React framework (App Router) |
| Language | TypeScript | 5 | Type safety |
| UI Runtime | React | 19.2.3 | Component rendering |
| Styling | Tailwind CSS | 4 | Utility-first CSS |
| Component Library | shadcn/ui | — | Radix UI + Tailwind primitives |
| State Management | Zustand | 5 | Lightweight stores |
| HTTP Client | Axios | 1.13 | API communication |
| Icons | Lucide React | 0.574 | SVG icon library |
| Toasts | Sonner | 2.0 | Notification system |
| Testing | Jest + RTL | 30 | Unit & integration tests |

---

## 5. Directory Structure

```
StoryFlow/
├── README.md                           # Project documentation
├── start-backend.bat / .sh             # Quick-start scripts
├── start-frontend.bat / .sh
│
├── backend/                            # Django REST API server
│   ├── manage.py                       # Django CLI entry point
│   ├── requirements.txt                # Python dependencies
│   ├── db.sqlite3                      # SQLite database file
│   │
│   ├── storyflow_backend/              # Django project configuration
│   │   ├── settings.py                 # All Django settings (DB, CORS, DRF, media)
│   │   ├── urls.py                     # Root URL router (/admin, /api, /media)
│   │   ├── asgi.py                     # ASGI entry point
│   │   └── wsgi.py                     # WSGI entry point
│   │
│   ├── api/                            # Main Django app
│   │   ├── models.py                   # Data models (Project, Segment, Logo, Outro, GlobalSettings)
│   │   ├── views.py                    # API views & ViewSets (~1472 lines)
│   │   ├── serializers.py              # DRF serializers with validation
│   │   ├── urls.py                     # API URL routing
│   │   ├── parsers.py                  # JSON & text import parsers
│   │   ├── validators.py              # Image, font, import data validators
│   │   ├── tasks.py                    # Background task manager (singleton)
│   │   ├── admin.py                    # Django admin registration
│   │   ├── apps.py                     # App configuration
│   │   └── migrations/                 # Database migration files
│   │
│   ├── core_engine/                    # Processing pipeline modules
│   │   ├── video_renderer.py           # Render orchestrator (~1218 lines)
│   │   ├── fast_compositor.py          # High-perf NumPy+FFmpeg compositor (~839 lines)
│   │   ├── ken_burns.py                # Zoom-and-pan effect engine (~694 lines)
│   │   ├── tts_wrapper.py             # Kokoro TTS integration (~335 lines)
│   │   ├── subtitle_engine.py          # Timed subtitle generation (~360 lines)
│   │   ├── image_upscaler.py           # Real-ESRGAN upscaling (~450 lines)
│   │   ├── audio_utils.py              # Audio normalization & validation (~120 lines)
│   │   ├── render_utils.py             # FFmpeg/font/path utilities (~559 lines)
│   │   ├── model_loader.py             # ONNX model singleton loader (~130 lines)
│   │   └── tests/                      # Core engine unit tests
│   │
│   ├── fonts/                          # Bundled default font (+ LICENSE)
│   │   └── LICENSE.txt
│   │
│   ├── Storage/                        # All user/generated assets (git-ignored)
│   │   ├── Facebook/
│   │   │   └── <project-uuid>/         # Self-contained project folder
│   │   │       ├── project.json        # Metadata + segment snapshot (draft)
│   │   │       ├── story.json          # Imported source story (when imported)
│   │   │       ├── script.txt          # Narration script
│   │   │       ├── images/             # Uploaded segment images
│   │   │       ├── audio/              # Generated TTS audio (WAV)
│   │   │       ├── output/             # Rendered final video (MP4)
│   │   │       ├── upscaled_images/    # GAN-upscaled images
│   │   │       └── assets/             # Referenced logo/outro/font copies
│   │   ├── YouTube/
│   │   │   └── <project-uuid>/         # Same layout as Facebook
│   │   ├── logos/                      # Uploaded logo images
│   │   ├── outros/                     # Uploaded outro videos
│   │   └── fonts/                      # Uploaded subtitle fonts
│   │
│   └── tests/                          # Backend integration tests
│       ├── test_e2e.py
│       ├── test_sections.py
│       ├── test_storage.py
│       └── test_settings.py
│
├── frontend/                           # Next.js React application
│   ├── package.json                    # Node.js dependencies & scripts
│   ├── next.config.ts                  # Next.js configuration
│   ├── tsconfig.json                   # TypeScript configuration
│   ├── jest.config.js / jest.setup.ts  # Testing configuration
│   ├── eslint.config.mjs               # Linting rules
│   ├── postcss.config.mjs              # PostCSS (Tailwind)
│   ├── components.json                 # shadcn/ui configuration
│   │
│   ├── app/                            # Next.js App Router pages
│   │   ├── layout.tsx                  # Root layout (providers, AppShell)
│   │   ├── page.tsx                    # Dashboard (/)
│   │   ├── globals.css                 # Global styles
│   │   ├── projects/
│   │   │   ├── page.tsx                # Project list (/projects)
│   │   │   └── [id]/
│   │   │       └── page.tsx            # Timeline Editor (/projects/[id])
│   │   ├── gallery/
│   │   │   └── page.tsx                # Video gallery (/gallery)
│   │   ├── settings/
│   │   │   └── page.tsx                # Global settings (/settings)
│   │   └── bulk-create/
│   │       └── page.tsx                # Bulk render queue (/bulk-create)
│   │
│   ├── components/                     # React components
│   │   ├── AppShell.tsx                # Global sidebar + top bar layout
│   │   ├── SegmentCard.tsx             # Main segment editing card
│   │   ├── Timeline.tsx                # Scrollable segment list
│   │   ├── AudioPlayer.tsx             # Audio playback with seek
│   │   ├── ImageUploader.tsx           # Drag-and-drop image upload
│   │   ├── RenderButton.tsx            # Export/render action
│   │   ├── RenderProgress.tsx          # Multi-phase progress display
│   │   ├── VideoPreview.tsx            # Video player + download
│   │   ├── ImportDialog.tsx            # JSON/text import modal
│   │   ├── CreateProjectDialog.tsx     # New project modal
│   │   ├── GlobalSettingsPanel.tsx     # Per-project settings sidebar
│   │   ├── SubtitleSettingsForm.tsx    # Subtitle configuration form
│   │   ├── SubtitlePreview.tsx         # Live subtitle style preview
│   │   ├── VoiceSelector.tsx           # TTS voice dropdown
│   │   ├── LogoWatermarkModal.tsx      # Logo placement modal
│   │   ├── ... (30+ components)
│   │   ├── skeletons/                  # Loading skeleton components
│   │   └── ui/                         # 18 shadcn/ui primitives
│   │
│   ├── lib/                            # Core utilities
│   │   ├── api.ts                      # Centralized API client (~all endpoints)
│   │   ├── stores.ts                   # Zustand stores (project + settings)
│   │   ├── types.ts                    # TypeScript type definitions
│   │   ├── utils.ts                    # Utility functions (cn, formatTime)
│   │   └── constants.ts               # Voices, presets, validation rules
│   │
│   ├── store/
│   │   └── settingsStore.ts            # Dedicated settings page store
│   │
│   ├── hooks/
│   │   └── useKeyboardShortcuts.ts     # Global keyboard shortcut hook
│   │
│   ├── api/
│   │   └── settingsApi.ts              # Settings-specific API client
│   │
│   ├── types/
│   │   └── settings.ts                 # Settings type definitions
│   │
│   ├── constants/
│   │   └── index.ts                    # Centralized constants
│   │
│   └── __tests__/                      # 13 test files (Jest + RTL)
│
├── models/                             # ML model weights (git-ignored)
│   ├── kokoro-v0_19.onnx              # Kokoro TTS model (82M params)
│   ├── voices/                         # TTS voice embedding files
│   └── upscalers/                      # Real-ESRGAN model weights
│       ├── RealESRGAN_x4plus.pth
│       ├── RealESRGAN_x2plus.pth
│       └── RealESRGAN_x4plus_anime_6B.pth
│
├── docs/                               # Test story JSON files
│   ├── test_story.json
│   ├── test_story_01.json ... test_story_10.json
│   └── ARCHITECTURE.md                 # (This document)
│
├── document-series/                    # Development phase documentation
│   ├── 00_Project_Overview.md
│   ├── Phase_01_The_Skeleton/          # Project setup, DB models, Dashboard UI
│   ├── Phase_02_The_Logic/             # Import engine, segment API, image/timeline
│   ├── Phase_03_The_Voice/             # TTS integration, audio API, playback UI
│   ├── Phase_04_The_Vision/            # Video assembly, Ken Burns, subtitles
│   └── Phase_05_The_Polish/            # Polishing features
│
├── references/                         # Reference implementations
│   └── kokoro.py                       # Kokoro TTS reference code
│
└── image/
    └── SESSION_CONTEXT/                # Session context images
```

---

## 6. Backend Architecture

### 6.1 Django Project Configuration

The Django project lives in `backend/storyflow_backend/` and is configured for **local-only development**:

| Setting | Value |
|---------|-------|
| DEBUG | `True` |
| ALLOWED_HOSTS | `localhost`, `127.0.0.1` |
| Database | SQLite3 (`db.sqlite3`) |
| CORS Origin | `http://localhost:3000` |
| Media Root | `backend/Storage/` |
| Static URL | `/static/` |
| Media URL | `/media/` |
| REST Framework | AllowAny permissions, JSON + Browsable renderers |
| Pagination | PageNumberPagination (page_size=50) |
| Time Zone | UTC |

**Installed Apps:** `rest_framework`, `corsheaders`, `api`  
**Middleware Stack:** CorsMiddleware → SecurityMiddleware → SessionMiddleware → CommonMiddleware → CsrfViewMiddleware → AuthenticationMiddleware → MessageMiddleware → XFrameOptionsMiddleware

---

### 6.2 Data Models

```
┌─────────────────────────────────────────────────────────────┐
│                      Entity Relationship                     │
│                                                             │
│  ┌──────────────────┐          ┌──────────────────┐         │
│  │   GlobalSettings │          │      Logo        │         │
│  │   (Singleton)    │─────────►│   id (UUID)      │         │
│  │   pk = 1 always  │  FK      │   name           │         │
│  │                  │          │   file (image)   │         │
│  │  render_width    │          │   uploaded_at    │         │
│  │  render_height   │          └──────────────────┘         │
│  │  render_fps      │                   ▲                   │
│  │  default_voice   │                   │ FK                │
│  │  tts_speed       │          ┌────────┴─────────┐         │
│  │  subtitle_*      │          │     Project      │         │
│  │  ken_burns_zoom  │          │   id (UUID)      │         │
│  │  transition_dur  │          │   title          │         │
│  │  logo settings   │          │   status         │         │
│  │  outro settings  │          │   resolution     │         │
│  │  upscale settings│          │   framerate      │         │
│  └──────────────────┘          │   output_path    │         │
│                                │   default_voice  │         │
│                                │   tts_speed      │         │
│                                │   subtitle_*     │         │
│                                │   ken_burns_zoom │         │
│                                │   logo settings  │         │
│                                │   outro settings │         │
│                                │   upscale settings│        │
│                                └────────┬─────────┘         │
│                                         │ 1:N (CASCADE)     │
│                                         │                   │
│                                ┌────────▼─────────┐         │
│                                │     Segment      │         │
│  ┌──────────────────┐          │   id (UUID)      │         │
│  │   OutroVideo     │          │   project (FK)   │         │
│  │   id (UUID)      │          │   sequence_index │         │
│  │   name           │◄─────── │   text_content   │         │
│  │   file (video)   │  FK     │   image_prompt   │         │
│  │   uploaded_at    │(Project)│   image_file     │         │
│  └──────────────────┘          │   audio_file     │         │
│                                │   audio_duration │         │
│                                │   is_locked      │         │
│                                └──────────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

#### Account Model

An `Account` is a Facebook page or YouTube channel owned by one workspace
section. It is the top-level content container:

- `id` (UUID, also used as the storage folder name)
- `name` (unique per section), `description`
- `section` (`facebook` / `youtube`, fixed after creation)
- timestamps and reverse relation `projects`

Deleting an account cascades to its projects, segments and asset folder.
A `Default Account` is created for both sides by data migration so existing
projects are adopted automatically.

#### Project Model (Core Entity)

The `Project` model is the central entity representing a single video production. It stores:
- **Identity:** UUID primary key, title, timestamps
- **Workspace section:** `facebook` (Facebook Reels) or `youtube` (YouTube Videos). Fixed at creation and enforced by every API endpoint.
- **Account:** FK to `Account`; fixed at creation and enforced by every API endpoint. `Project.save()` assigns the section's default account when one is not supplied (legacy/test safety).
- **Status lifecycle:** `DRAFT` → `PROCESSING` → `COMPLETED` or `FAILED`
- **Render settings:** Resolution (width × height), framerate
- **TTS settings:** Default voice ID (Kokoro), speech speed
- **TTS engine:** `tts_engine` (`kokoro` default / `qwen`), plus Qwen mode,
  speaker, language, instruct, token budget, cloning flag and active
  `VoiceReference` FK. Copied from GlobalSettings at import time.
- **Subtitle settings:** Font family, size, color (hex), position, optional manual Y override, custom font file, enabled toggle. Manual Y values are resolution-aware: they are scaled and clamped when the frame height changes, and selecting a preset position clears the override.
- **Ken Burns effect:** Zoom intensity, transition duration
- **Audio settings:** Inter-segment silence duration
- **Logo watermark:** Enabled flag, active logo FK, scale, position, opacity, margin
- **Outro video:** Enabled flag, active outro FK
- **Upscaling:** Enabled flag, model selection, denoise strength
- **Output:** Path to the newest rendered video file

#### Rendering Model (Gallery Asset)

Each completed export creates one `Rendering` row. It is the durable link between a project and one MP4 file:

- **Project link:** FK to `Project` (`related_name="renderings"`); deleting the project cascades the rows, while deleting a rendering never deletes the project/script.
- **File:** `file_path` points at `<Section>/<account>/<project>/renderings/<rendering-id>.mp4`, so re-rendering cannot overwrite an earlier version.
- **Publishing workflow:** `status` is `rendered`, `ready_to_publish` or `published`; `published_at` records the transition to published.
- **Metadata:** title snapshot, resolution, framerate, segment count, duration, file size, timestamps, and `render_time_seconds` — the wall-clock time spent in the full video-render pipeline. The editor's completed banner, gallery cards and player footer format it as `2m 13s`; rows created before this measurement simply leave it null.
- **Compatibility:** rows backfilled from pre-feature projects reuse the project id, so old `/api/gallery/<project-id>/...` links continue to resolve.

#### Segment Model (Content Unit)

Each `Segment` belongs to a `Project` and represents one narration unit:
- **Order:** `sequence_index` for timeline ordering
- **Content:** `text_content` (narration text), `image_prompt` (AI prompt used to generate the image)
- **Media:** `image_file` (uploaded image), `audio_file` (generated TTS WAV), `audio_duration`
- **Engine provenance:** `audio_engine` records whether the current WAV came
  from `kokoro` or `qwen`, so switching engines regenerates cleanly
- **Lock:** `is_locked` flag prevents accidental editing during rendering

#### GlobalSettings Model (Singleton)

A singleton model (always `pk=1`) that stores application-wide defaults. When a new project is created, all GlobalSettings values are **copied** into the project, enabling per-project customization while maintaining shared defaults.

#### Logo & OutroVideo Models

Simple asset models for uploaded logo images and outro video clips, referenced by both `Project` and `GlobalSettings` via foreign keys.

#### VoiceReference Model

Stores an uploaded reference clip for Qwen zero-shot voice cloning:
`id`, `name`, `file` (`Storage/voice_references/...`), optional `transcript`
(used for ICL cloning), `duration`, `uploaded_at`. Multiple references can be
stored and selected per project or globally.

#### GlobalSettings Model (Qwen fields)

In addition to Kokoro's `default_voice_id`/`tts_speed`, the singleton stores the
default `tts_engine`, `qwen_mode`, `qwen_speaker`, `qwen_language`,
`qwen_instruct`, `qwen_max_new_tokens`, `qwen_clone_x_vector_only` and
`active_voice_reference`. New projects inherit all of them.

---

### 6.3 REST API Layer

The API is built with Django REST Framework and exposes the following endpoint groups:

#### Account Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/accounts/?section=<side>` | List accounts for a section |
| `POST` | `/api/accounts/?section=<side>` | Create a page/channel account |
| `GET` | `/api/accounts/<id>/?section=<side>` | Account detail + project counts |
| `PATCH` | `/api/accounts/<id>/?section=<side>` | Rename/describe an account |
| `DELETE` | `/api/accounts/<id>/?section=<side>` | Delete account, projects and assets |

All project, segment and gallery endpoints additionally accept
`?account=<uuid>` to scope the request to one account.

#### Project Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/projects/` | List all projects (paginated, summary serializer) |
| `POST` | `/api/projects/` | Create a new project |
| `GET` | `/api/projects/<id>/` | Get project detail with all settings and nested segments |
| `PATCH` | `/api/projects/<id>/` | Update project settings (resolution change re-applies that resolution's defaults) |
| `POST` | `/api/projects/<id>/reset-settings/` | Re-apply the project's resolution defaults to this project |
| `DELETE` | `/api/projects/<id>/` | Delete project and all associated media files |
| `POST` | `/api/projects/import/` | Import a story from JSON or text format |
| `POST` | `/api/projects/<id>/import-segments/` | Append segments to an existing project |
| `POST` | `/api/projects/<id>/generate-all-audio/` | Batch TTS generation for all segments |
| `POST` | `/api/projects/<id>/render/` | Start video rendering (returns task ID) |
| `GET` | `/api/projects/<id>/status/` | Poll render progress |
| `POST` | `/api/projects/<id>/cancel-render/` | Cancel in-progress render |

#### Segment Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/segments/?project=<id>` | List segments for a project |
| `POST` | `/api/segments/` | Create a new segment |
| `GET` | `/api/segments/<id>/` | Get segment detail |
| `PATCH` | `/api/segments/<id>/` | Update segment (blocked if locked) |
| `DELETE` | `/api/segments/<id>/` | Delete segment and cleanup files |
| `POST` | `/api/segments/reorder/` | Reorder all project segments atomically |
| `POST` | `/api/segments/<id>/upload-image/` | Upload image (multipart, validates type/size) |
| `DELETE` | `/api/segments/<id>/remove-image/` | Remove segment image |
| `DELETE` | `/api/segments/<id>/remove-audio/` | Remove segment audio |
| `POST` | `/api/segments/<id>/generate-audio/` | Generate TTS audio for single segment |
| `POST` | `/api/segments/<id>/generate-tts-script/` | Rewrite one block into a TTS-ready spoken script |
| `POST` | `/api/projects/<id>/generate-all-tts-scripts/` | Rewrite every block into TTS-ready scripts (background task) |

#### Settings Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET/PATCH` | `/api/settings/` | Read/update settings for the active account |
| `GET` | `/api/settings/project-defaults/` | List per-resolution project default profiles |
| `GET/PATCH/DELETE` | `/api/settings/project-defaults/<w>x<h>/` | Read, save or reset one resolution's defaults |
| `GET` | `/api/settings/voices/` | List available TTS voices (26 voices) |
| `POST` | `/api/settings/font/upload/` | Upload custom subtitle font |
| `POST` | `/api/settings/tts-test/` | Generate and play test TTS audio |
| `GET/POST` | `/api/settings/logos/` | List/upload logo images |
| `DELETE` | `/api/settings/logos/<id>/` | Delete a logo |
| `GET/POST` | `/api/settings/outros/` | List/upload outro videos |
| `DELETE` | `/api/settings/outros/<id>/` | Delete an outro video |

#### Task & Gallery Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/tasks/<task_id>/status/` | Poll background task progress |
| `GET` | `/api/gallery/` | List rendering assets (`project`, `status`, `q`, `sort` filters) |
| `PATCH` | `/api/gallery/<rendering_id>/` | Change an asset's publishing status |
| `DELETE` | `/api/gallery/<rendering_id>/` | Delete one rendering and its MP4 |
| `POST` | `/api/gallery/bulk-status/` | Change status for several renderings |
| `POST` | `/api/gallery/bulk-delete/` | Delete several renderings and their MP4s |
| `GET` | `/api/gallery/<rendering_id>/stream/` | Stream video (HTTP Range / 206) |
| `GET` | `/api/gallery/<rendering_id>/download/` | Download video as attachment |

---

### 6.4 Serializers & Validation

The API uses layered serializers with extensive field-level and cross-field validation:

**Validation Rules:**
- Hex color format: `#RGB` or `#RRGGBB`
- Subtitle font size: 12–120 px
- Subtitle position: `bottom` / `center` / `top`
- Manual subtitle Y: scaled from the profile/frame height, clamped to `0 … frame height − estimated text block`
- Ken Burns zoom: 1.0–2.0
- Transition duration: 0.0–2.0 seconds
- FPS: 24, 30, or 60 only
- Inter-segment silence: 0.0–5.0 seconds
- Logo scale: 0.05–0.50, opacity: 0.0–1.0, margin: 0–200px
- Upscale denoise strength: 0.0–1.0
- Resolution: must be one of 12 allowed presets (landscape, portrait, square, and special aspect ratios)

**Allowed Resolution Presets:**

| Preset | Dimensions | Aspect Ratio |
|--------|-----------|--------------|
| 720p Landscape | 1280 × 720 | 16:9 |
| 1080p Landscape | 1920 × 1080 | 16:9 |
| 4K Landscape | 3840 × 2160 | 16:9 |
| 720p Portrait | 720 × 1280 | 9:16 |
| 1080p Portrait | 1080 × 1920 | 9:16 |
| 720p Square | 720 × 720 | 1:1 |
| 1080p Square | 1080 × 1080 | 1:1 |
| Social (4:5) | 1080 × 1350 | 4:5 |
| 4:3 | 1440 × 1080 | 4:3 |
| 3:4 | 1080 × 1440 | 3:4 |
| SD (4:3) | 864 × 1080 | 4:5 |

---

### 6.5 Background Task System

All heavy processing (TTS generation, video rendering) runs asynchronously via an in-memory **TaskManager** singleton:

```
┌────────────────────────────────────────────────────────────────┐
│                     TaskManager (Singleton)                     │
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  ThreadPoolExecutor(max_workers=1)                       │  │
│  │  ─────────────────────────────────────────────────────── │  │
│  │  • Sequential execution (avoids GPU/CPU contention)     │  │
│  │  • Auto-recovery after RuntimeError                     │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  In-Memory Task Registry (dict, Lock-guarded)           │  │
│  │  ─────────────────────────────────────────────────────── │  │
│  │  task_id → {status, progress, errors, results, cancel}  │  │
│  │                                                         │  │
│  │  Lifecycle: PENDING → PROCESSING → COMPLETED            │  │
│  │                                    → FAILED             │  │
│  │                                    → CANCELLED          │  │
│  │                                                         │  │
│  │  Auto-cleanup after 3600s (stale completed/failed)      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                │
│  Key Features:                                                 │
│  • Cooperative cancellation (polling flag between segments)   │
│  • Progress reporting (percentage, per-segment status)        │
│  • DB connection safety (closes in finally blocks for SQLite) │
│  • Shallow copy on status reads (thread safety)              │
└────────────────────────────────────────────────────────────────┘
```

**Task Types:**
1. **Audio Generation Tasks** — TTS generation for single or batch segments
2. **Render Tasks** — Full video rendering with two-phase progress:
   - Phase 1 (0–80%): Segment processing (image preparation, audio mixing)
   - Phase 2 (80–99%): FFmpeg export (frame encoding)

---

### 6.6 Import / Parse Engine

StoryFlow supports two import formats:

#### JSON Format
```json
{
  "title": "My Story",
  "segments": [
    {
      "text_content": "Narration text here...",
      "image_prompt": "A description of the image"
    }
  ]
}
```

#### Plain Text Format
```
Text: First segment narration text.
Prompt: Image description for segment 1.
---
Text: Second segment narration text.
Prompt: Image description for segment 2.
```

The parsers normalize both formats into a common internal structure and validate:
- Non-empty title (≤200 characters) 
- Non-empty segments array
- Per-segment `text_content` required, `image_prompt` optional
- Contiguous sequence indices starting from 0

---

### 6.7 Asset Storage Layout

`MEDIA_ROOT` points at `backend/Storage/`. Every project owns a
self-contained folder named after its workspace section, account UUID and
project UUID:

```
backend/Storage/
├── Facebook/<account-uuid>/<project-uuid>/
│   ├── project.json      # Metadata + full segment snapshot (the draft)
│   ├── story.json        # Imported source story (JSON/text source)
│   ├── script.txt        # Human-readable narration script
│   ├── images/           # Segment images
│   ├── audio/            # Generated TTS WAV files
│   ├── output/           # final.mp4
│   ├── upscaled_images/  # Real-ESRGAN output (when enabled)
│   └── assets/           # Copies of the logo/outro/font used by the project
├── YouTube/<account-uuid>/<project-uuid>/  # Identical structure
├── logos/                    # Shared logo assets
├── outros/                   # Shared outro videos
├── fonts/                    # Shared subtitle fonts
├── voice_references/         # Qwen cloning reference clips
└── qwen_tts_engine.log       # GPU worker stderr (created on first run)
```

`project.json` and `script.txt` are refreshed automatically by Django
signals whenever a project or segment changes (including renames, settings
patches and segment edits). Imports additionally write `story.json`.
Model upload paths, TTS audio paths and render output paths are all derived
from the project's section and account, so assets from different sides or
different pages/channels can never be mixed.

Data migration `0013_seed_default_accounts` creates the first account for each
side, adopts all existing projects and moves
`Storage/<Section>/<project-id>` into
`Storage/<Section>/<account-id>/<project-id>`. The same move can be re-run
manually for an older store:

```bash
python manage.py migrate_storage          # add --dry-run to preview
```

---

## 7. Core Engine — Processing Pipeline

The `core_engine/` package contains 9 modules that form the complete image-to-video rendering pipeline.

### 7.1 Video Renderer (Orchestrator)

**File:** `core_engine/video_renderer.py` (~1218 lines)

The top-level orchestrator that coordinates the entire rendering pipeline:

```
render_project(project_id, on_progress) Pipeline
═══════════════════════════════════════════════════

Step 1: ──► Check FFmpeg availability
Step 2: ──► Load project from Django ORM
Step 3: ──► Read all settings (resolution, FPS, effects, subtitles...)
Step 4: ──► Query segments ordered by sequence_index
Step 5: ──► [Optional] Upscale images via Real-ESRGAN
Step 6: ──► Export mixed audio
             ├── Load each segment's WAV
             ├── Stagger with crossfade-matching time offsets
             ├── CompositeAudioClip → temp WAV file
             └── Inter-segment silence padding
Step 7: ──► Fast render (NumPy compositing + FFmpeg pipe)
             ├── Pre-render all subtitle overlays
             ├── Pre-render logo overlay
             ├── For each frame:
             │   ├── Ken Burns: interpolate crop position + size
             │   ├── Extract & resize crop region
             │   ├── Alpha-blit subtitle overlays
             │   ├── Crossfade blend (if overlapping segments)
             │   └── Alpha-blit logo
             └── Pipe frame to FFmpeg subprocess
Step 8: ──► [Optional] Append outro video via FFmpeg filter_complex  
Step 9: ──► Verify output (FFprobe duration + file size)
Step 10: ─► Cleanup temp files (always, via finally block)
```

**Key Design Decisions:**
- Never updates DB status directly (that's the API layer's responsibility)
- Deletes partial output file on failure
- `finally` block guarantees temp file cleanup
- Supports NVENC (GPU) encoding with automatic fallback to `libx264` (CPU)
- Cooperative cancellation via `RenderCancelled` exception

---

### 7.2 Fast Compositor

**File:** `core_engine/fast_compositor.py` (~839 lines)

The performance-critical rendering engine that replaces MoviePy's `CompositeVideoClip`. It achieves **~10–15× faster rendering** than MoviePy 2.x:

| Approach | Per-Frame Cost (1080p) |
|----------|----------------------|
| MoviePy 2.x (Pillow alpha_composite) | ~200+ ms |
| **Fast Compositor** (NumPy + direct FFmpeg pipe) | **~5–10 ms** |

**Architecture:**

```
┌─────────────────────────────────────────────────────┐
│              fast_render_segments()                   │
│                                                     │
│  Phase 1: PRE-COMPUTE (one-time)                    │
│  ├── Pre-render subtitle overlays → OverlaySlice[]  │
│  ├── Pre-render logo overlay → OverlaySlice         │
│  └── Prepare Ken Burns source images                │
│                                                     │
│  Phase 2: TIMELINE CALCULATION                      │
│  └── Build segment frame ranges with crossfade      │
│      overlap windows                                │
│                                                     │
│  Phase 3: START FFMPEG                              │
│  └── FFmpegFrameWriter.start() → subprocess.Popen  │
│                                                     │
│  Phase 4: FRAME GENERATION LOOP                     │
│  For each global frame index:                       │
│  ├── Determine active segments (1 or 2)             │
│  ├── Per active segment:                            │
│  │   ├── Ken Burns: sample motion plan (pos+size)   │
│  │   ├── NumPy slice: extract crop region (O(1))    │
│  │   ├── OpenCV resize to output resolution         │
│  │   └── alpha_blit(): overlay subtitles            │
│  ├── Crossfade blend (if 2 segments active)         │
│  ├── alpha_blit(): overlay logo                     │
│  └── FFmpegFrameWriter.write_frame(rgb_bytes)       │
│                                                     │
│  Phase 5: FINISH                                    │
│  └── Close FFmpeg pipe, verify return code          │
└─────────────────────────────────────────────────────┘
```

**OverlaySlice Structure:**
```python
OverlaySlice:
  rgb:   ndarray (H, W, 3) uint8     # Foreground color
  alpha: ndarray (H, W, 1) float32   # Opacity [0, 1]
  x, y:  int                          # Position in output frame
  start_time, end_time: float         # Visibility window
```

**Alpha Compositing:** Porter-Duff "over" operation via vectorized NumPy:
```
output = foreground × α + background × (1 − α)
```

**FFmpeg Encoding Settings:**
- Input: Raw RGB frames piped via `stdin`
- Codec: `h264_nvenc` (GPU) or `libx264` (CPU)
- CRF: 23 (quality/size balance)
- Preset: `fast`
- Profile: `high`
- Pixel format: `yuv420p`
- Container flag: `+faststart` (web streaming)

---

### 7.3 Ken Burns Effect Engine

**File:** `core_engine/ken_burns.py`

Converts static images into animated video clips with simulated camera motion (zoom + pan).

**Smart motion planner.** `plan_ken_burns_motion()` measures the free space
around an optional highlighted subject and selects one of four motions for the
clip. Preset order is deterministic via `segment_index % 7`, then adapted to
the room actually available:

| Index | Preferred motion |
|-------|------------------|
| 0 | Pan |
| 1 | Slow zoom in |
| 2 | Pan |
| 3 | Slow zoom out |
| 4 | Pan + zoom |
| 5 | Pan |
| 6 | Slow zoom in |

* **Pan** — sweeps along the deterministic 7-direction cycle. The distance is
  `PAN_SPEED_TARGET × duration × frame width` (raised to 0.045 frame/s so
  short clips never look frozen), then capped by the free space left around
  the subject.
* **Zoom in / out** — a subtle 12–15 % crop-scale change, centred on the
  subject for a slow, cinematic move.
* **Pan + zoom** — both motions at reduced strength for extra variety.

**Minimum visible motion.** Before choosing a motion the planner compares the
achievable pan distance and zoom span with a visibility threshold
(`MIN_PAN_TRAVEL` / `MIN_ZOOM_SPAN`, growing with clip length up to
`MAX_REQUIRED_MOTION = 10 %`). A move below the threshold is skipped. When a
large subject leaves too little panning room, the planner substitutes a slow
zoom (or a combined move) instead of producing a nearly static shot. The
preferred preset is therefore a starting point, not a guarantee.

**Subject containment.** Only **one** highlighted rectangle is supported per
image (`MAX_FOCUS_AREAS = 1`). The crop is never allowed to shrink below the
rectangle's size, and every sampled frame is clamped to the subject-safe
bounds. Up to `FOCUS_OVERFLOW_RATIO = 10 %` of the rectangle's own width or
height may leave the frame on one edge; this overflow is what gives panning
the extra room needed for a visible move. The remaining part of the subject
stays visible for the whole animation. Legacy rows with several rectangles
are rendered using the first one without mutating stored data.

**Per-Frame Algorithm:**
1. Sample the motion plan with smoothstep easing.
2. Interpolate crop centre **and** crop size (zoom).
3. Clamp the position to the subject-safe bounds and the prepared frame.
4. Extract crop via NumPy slice (O(1) view — no copy).
5. Resize with OpenCV (`INTER_AREA` for downscale, `INTER_LINEAR` for upscale).

**Performance:** ~2–4 ms/frame at 1080p resolution.

---

### 7.4 Text-to-Speech (TTS) Wrapper

**File:** `core_engine/tts_wrapper.py` (~335 lines)

Integrates the **Kokoro-82M ONNX** model for high-quality text-to-speech generation.

```
generate_audio(text, voice_id, speed, output_path) Pipeline
══════════════════════════════════════════════════════════════

Step 1: ──► Validate text (reject empty/whitespace)
Step 2: ──► Validate voice ID (fallback to "af_bella")
Step 3: ──► Clamp speed to [0.5, 2.0]
Step 4: ──► Get Kokoro singleton instance (thread-safe lazy init)
Step 5: ──► Check voice availability against loaded voices
Step 6: ──► Generate: kokoro.create(text, voice, speed, lang="en-us")
Step 7: ──► Convert float32 → int16, save as WAV (24kHz)
Step 8: ──► Measure duration via audio_utils
Step 9: ──► Return {success, audio_path, duration, sample_rate}
```

**Voice Library (20+ voices):**

| Category | Voices |
|----------|--------|
| American Female | `af_bella`, `af_sarah`, `af_nicole`, `af_sky`, `af_emma`, `af_alloy` |
| American Male | `am_adam`, `am_michael`, `am_echo`, `am_fable`, `am_onyx`, `am_nova` |
| British Female | `bf_emma`, `bf_isabella`, `bf_alice` |
| British Male | `bm_george`, `bm_lewis`, `bm_daniel` |

**Design:** Never raises exceptions — always returns a result dict with `success: true/false`.

---

### 7.4.1 Optional Qwen3-TTS Engine (GPU + voice cloning)

**Files:**

| File | Runs in | Responsibility |
| ---- | ------- | -------------- |
| `core_engine/tts.py` | Django | Engine dispatcher; both engines return the same result dict |
| `core_engine/qwen_client.py` | Django | RPC client + interpreter discovery (**never imports torch**) |
| `core_engine/qwen_engine.py` | Python 3.11 + CUDA | All torch/qwen-tts inference, WAV writing, VRAM management |
| `backend/qwen_tts/.venv` | — | Dedicated GPU environment (copied from the experiment venv) |

**Why a separate process and interpreter:** Django runs on Python 3.14, while
`qwen-tts` supports only Python 3.10–3.12. Sampling also holds the GIL for long
stretches and inflates the CUDA context, which freezes the dev server and the
Windows compositor if run in-process. The client talks newline-delimited JSON
over stdin/stdout; audio is written by the child directly to the project's
`audio/` folder and never crosses the pipe.

```
Django (3.14) ──JSON lines──▶ qwen_engine.py --serve (3.11 + torch)
      ▲                                   │
      └──────── result / error ◀──────────┘
```

**Hardware policy (GTX 1660 Ti, 6 GB):**
- **GPU only.** `torch.cuda.is_available()` is a hard requirement; there is no
  CPU fallback. A missing GPU surfaces as a clear 503/error.
- `bfloat16` — float16 trips a device-side assert in the code predictor.
- `sdpa` attention — no prebuilt FlashAttention-2 Windows wheels.
- VRAM capped via `QWEN_TTS_VRAM_FRACTION` (default `0.72`); PyTorch raises a
  clean OOM instead of spilling into shared GPU memory. Only one checkpoint is
  resident; `empty_cache()` runs after each job and on `--unload`.
- Long narration is split at sentence boundaries (≤360 chars per call) to stay
  inside the `max_new_tokens` budget.

**Modes:**
- `custom_voice` — one of the 9 built-in speakers (Aiden, Ryan, …), optional
  instruct (ignored by the 0.6B checkpoint).
- `clone` — zero-shot cloning from a `VoiceReference`; speaker-embedding-only
  by default, or ICL when a reference transcript is supplied.

**Draft → final workflow:** Kokoro is the default and fast enough to build a
complete draft. `Segment.audio_engine` records provenance, so requesting audio
with a different engine regenerates every segment automatically. The editor
exposes this as a split button: *Kokoro — draft audio* / *Qwen — finalize
audio*.

**Setup:** `scripts/setup_qwen_tts.ps1` copies the existing TTS-test venv
(~5 GB of torch/CUDA wheels) instead of re-downloading. `QWEN_TTS_PYTHON` can
override the interpreter path.

---

### 7.4.2 TTS-ready spoken scripts (Issue #27)

**Files:**

| File | Responsibility |
| ---- | -------------- |
| `core_engine/tts_script.py` | Prompt rules, deterministic normaliser, LLM rewrite |
| `api/models.py` | `Segment.tts_text` stores the optional spoken version |
| `api/views.py` | `generate-tts-script` (one block) and `generate-all-tts-scripts` (background batch) |
| `frontend/components/SegmentCard.tsx` | Per-block generate/edit UI, auto-expanded when a script exists |
| `frontend/app/facebook/projects/[id]/page.tsx` | Footer button loops the per-block endpoint with live progress (Issue #35) |

A project still starts with a single script. After import, each block can be
rewritten on demand into `tts_text` using the same Script Craft model configured
in **Settings → AI Model**. The original `text_content` is never modified, so
subtitles keep their exact spelling and punctuation while the voice engine gets
a normalised spoken version.

The rewrite prompt enforces six groups of rules: strip non-verbal tags and
emojis, normalise years/dates/quantities/decimals, expand acronyms and
abbreviations, convert exotic punctuation into comma/period breath cues, add
phonetic hints for ambiguous words, and preserve 1:1 semantic alignment.
`normalize_tts_text()` is a deterministic safety net used for legacy blocks and
as post-processing after every LLM reply; it is idempotent and also expands
years, ordinals, currency, percentages, fractions and common units.

Both single and batch generation are non-destructive: locked blocks are
skipped, and TTS synthesis automatically uses `tts_text` when present, falling
back to the cleaned subtitle text otherwise.

The footer **Generate TTS Scripts** action loops over every block that still
needs a script and calls the same per-block endpoint as the card button. It
shows `Writing TTS… n/m` while it runs, updates each card as soon as its script
arrives, and skips blocks that already have one. Running the loop on the client
keeps this lightweight LLM work out of the shared TTS background queue, so it
cannot wait behind a long audio batch (Issue #35). Each card's **Regenerate**
button rewrites a single existing script. The TTS editor starts expanded for
blocks that already have a script, so generated scripts remain visible after a
page reload. Returns from the per-block generation are persisted by the API and
mirrored into the store through the normal segment update path.

---

### 7.4.3 Image prompt contract (Issue #28)

**File:** `core_engine/image_prompt_rules.py`

Script Craft image prompts are constrained in three places:

1. `SCRIPT_FORMAT_INSTRUCTIONS`, `DEFAULT_SYSTEM_PROMPT` and
   `chat_agent.AGENT_INSTRUCTIONS` state the rules explicitly.
2. The `create_script` / `update_script` / `rewrite_segment` tool schemas
   describe the same restrictions.
3. `sanitize_image_prompt()` is applied to every AI-generated, chat-edited and
   imported prompt before it reaches a project.

The rules are: no text or lettering of any kind, no comparison/split-screen
composition, and no aspect ratio, resolution or orientation instruction.
The sanitizer is deliberately conservative with normal prose — it strips
explicit instructions and artefacts, then collapses whitespace.

---

### 7.4.4 Music generation readiness (Issue #30)

MusicGen plans are built from the measured duration of every narration block.
`music_service.segments_from_project()` rejects a project as soon as one block
has no `audio_duration`, so a soundtrack can never be generated against a
half-narrated timeline. The editor mirrors that contract in both MusicGen
buttons (`BgmToolbarControls` and the settings panel): they stay disabled until
`segments.length > 0` and every segment has both `audio_file` and
`audio_duration`, with a tooltip that reports how many blocks still need TTS.

---

### 7.4.5 YouTube metadata management — thumbnail prompts (Issue #15)

**Files:** `core_engine/metadata_prompts.py`, `api/views.py` (`ProjectViewSet`),
`components/MetadataManagementModal.tsx`

The YouTube workspace has a full-viewport **Metadata management** dialog on the
project detail page (the Facebook side has no entry point and the backend
rejects metadata routes for Facebook projects). Thumbnail prompt generation is
gated the same way in the UI and the API:

- the project has at least one segment with narration (the script is crafted);
- at least **half of the blocks** have images (`ceil(segment_count / 2)`);
- at least **two storyboard images** are selected as references.

The dialog sends the script, the selected block images, optional extra image
references and PDF/TXT/Markdown/CSV/JSON notes to the account's configured
OpenAI-compatible chat model. Images are re-encoded to compact base64 JPEG data
URLs before they are added as multimodal `image_url` parts; document text is
extracted inline (`pypdf` is used for PDFs when installed). The editable
**system prompt** is collapsed by default and stored per project in
`Project.thumbnail_system_prompt`; an empty value falls back to
`DEFAULT_THUMBNAIL_SYSTEM_PROMPT` in `core_engine/metadata_prompts.py`. The
generated prompt is returned as plain text and shown in a copyable box.

Uploaded thumbnail candidates live in `ProjectThumbnail` and are stored under
`Storage/<Section>/<account>/<project>/thumbnails/`. Exactly one candidate per
project can be active. Cover priority is now:

1. the active `ProjectThumbnail`;
2. the legacy manual `Project.thumbnail`;
3. the first segment image.

Deleting the active candidate promotes the newest remaining candidate so the
project keeps a generated cover. The Projects page and tile view use the same
`thumbnail_url` serializer field, so the active thumbnail appears everywhere
without a second fetch.

**Endpoints (YouTube only)**

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/projects/<id>/metadata/thumbnail-prompt/` | Draft a prompt from the script, block images and references |
| GET/POST | `/api/projects/<id>/metadata/thumbnails/` | List or upload thumbnail candidates |
| PATCH/DELETE | `/api/projects/<id>/metadata/thumbnails/<thumbnail_id>/` | Activate/update or delete a candidate |

The AI model must accept image content parts (a vision-capable model); text-only
models still receive the full script and document references but will reject
the image parts.

---

### 7.4.6 YouTube metadata management — title and description (New feature #16)

**Files:** `core_engine/metadata_prompts.py`, `api/views.py`
(`ProjectViewSet`), `components/MetadataManagementModal.tsx`

The same Metadata management dialog has **Title** and **Description** tabs.
Each tab has its own collapsed, editable system prompt and instruction box,
plus a separate generate button:

- **Title** uses `DEFAULT_TITLE_SYSTEM_PROMPT` (an SEO title strategist) and
  writes one upload-ready title of 60-95 characters.
- **Description** uses `DEFAULT_DESCRIPTION_SYSTEM_PROMPT` (an SEO copywriter)
  and writes a hook, 2-4 paragraphs and a short hashtag line.

Both prompts are stored per project in `Project.title_system_prompt` and
`Project.description_system_prompt`. Generated output is persisted separately
from the internal project title in `Project.upload_title` and
`Project.upload_description`; both are returned by the project detail endpoint
and shown in read-only copyable boxes. The title box has a **Use as project
title** action that promotes the generated title to `Project.title` through the
normal PATCH endpoint, so the working title is never overwritten implicitly.

Title and description generation only need the script (not the storyboard
images), but they include the optional active thumbnail prompt when one exists
so the cover and copy stay consistent.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/projects/<id>/metadata/generate-title/` | Generate and save an upload-ready title |
| POST | `/api/projects/<id>/metadata/generate-description/` | Generate and save an SEO description |

Both endpoints accept `system_prompt`, `message` and `thumbnail_prompt`, and
are YouTube-only like the thumbnail routes.

---

### 7.4.7 Script Craft block density (Feature update #11)

**Files:** `core_engine/ai_client.py`, `core_engine/chat_agent.py`

Every Script Craft path shares the same block-density contract:

- `DEFAULT_SYSTEM_PROMPT` asks for one coherent beat with its own image and
  **45-85 words** of narration per segment.
- `SCRIPT_FORMAT_INSTRUCTIONS` and `chat_agent.AGENT_INSTRUCTIONS` request
  **20-30 segments** for an 8-10 minute video, roughly double the previous
  10-15 block scripts.
- The chat agent's `create_script` / `update_script` tool schemas describe the
  same range so a tool-calling model sees it in the function definition too.

The shorter blocks keep the total narration length stable while giving each
block its own storyboard image, so the visual changes more often during the
finished video. The user can still request a different length explicitly.

---

### 7.5 Subtitle Engine

**File:** `core_engine/subtitle_engine.py` (~360 lines)

Generates timed subtitle overlays synchronized with narration audio.

**Pipeline:**
1. **Chunk text** → Split at sentence/clause boundaries (`.!?,;:—…`), max 6 words per chunk, min 4 words (orphan prevention)
2. **Calculate timing** → Prefer measured sentence spans from `Segment.audio_timings`; otherwise proportional to character count, with a 0.5s minimum per chunk, normalized to exactly fill the audio duration
3. **Generate clips** → Create MoviePy `TextClip` objects with styling (font, color, stroke, position)

**Styling Defaults:**
- Font size: `resolution_height / 18` (~60px at 1080p)
- Text width: 90% of frame width
- Stroke: 2px black outline
- Vertical margin: 8% of frame height
- Max height: 40% of frame (downscaled if exceeded)

---

### 7.5.1 Audio-accurate subtitle alignment (Issue #29)

**File:** `core_engine/subtitle_sync.py`

Proportional word timing drifts when the voice pauses, slows down, or reads a
normalised TTS script. Alignment is now measured per segment:

1. `split_sentences()` splits the subtitle text and understands common
   abbreviations (`Dr.`, `e.g.`, ...).
2. `detect_silences()` runs a tiny RMS VAD over the generated WAV
   (20 ms frames, 110 ms minimum pause). No ASR model or extra install.
3. `build_audio_timings()` snaps each expected sentence boundary to the
   nearest real pause and stores `{version, method, total, sentences[]}` in
   `Segment.audio_timings`.
4. `chunk_text_with_sentence_timings()` distributes each sentence's measured
   span across its subtitle chunks by character weight.
5. `chunk_and_time()` is used by both the fast compositor and MoviePy path;
   it falls back to proportional timing when timings are missing or the
   subtitle text changed after the audio was generated.

Because the timings live on the segment, rendering never re-analyses audio.
The expected boundaries are computed from the subtitle text (the version the
viewer reads), while the pauses come from the audio, so a normalised TTS script
with expanded numbers still aligns.

---

### 7.6 Image Upscaler (Real-ESRGAN)

**File:** `core_engine/image_upscaler.py` (~450 lines)

AI-powered image super-resolution using Real-ESRGAN with inline PyTorch architecture (no external `realesrgan`/`basicsr` dependency).

**Supported Models:**

| Model | Scale | RRDB Blocks | Best For |
|-------|-------|-------------|----------|
| `RealESRGAN_x4plus` | 4× | 23 | General-purpose photos |
| `RealESRGAN_x2plus` | 2× | 23 | Moderate upscale, faster |
| `RealESRGAN_x4plus_anime_6B` | 4× | 6 | Anime / illustrations |

**Architecture:** ResidualDenseBlock → RRDB (3× cascaded) → RRDBNet with pixel-shuffle upsampling.

**Tile-Based Inference:**
- Processes large images in overlapping 512×512 tiles
- 10px tile padding for seamless stitching
- FP16 on CUDA (GPU), FP32 on CPU
- Thread-safe model caching

**Graceful Degradation:** If PyTorch is not installed, upscaling silently returns the original image.

---

### 7.7 Audio Utilities

**File:** `core_engine/audio_utils.py` (~120 lines)

Pure utility functions with no Django dependency:

| Function | Purpose |
|----------|---------|
| `normalize_audio(array, target_db)` | Peak normalization to target dB level |
| `get_audio_duration(path)` | Duration measurement via soundfile |
| `validate_audio_file(path)` | Non-throwing validation check |
| `save_audio_wav(array, path, rate)` | WAV file writer with auto-directory creation |

---

### 7.8 Render Utilities

**File:** `core_engine/render_utils.py` (~559 lines)

Support utilities for the rendering pipeline:

| Function | Purpose |
|----------|---------|
| `check_ffmpeg()` | Cached FFmpeg availability check |
| `get_ffmpeg_error_message()` | Platform-specific install instructions |
| `resize_image_to_resolution()` | PIL cover-mode resize + center-crop |
| `get_output_path()` | Output file path constructor |
| `cleanup_temp_files()` | Recursive temp directory cleanup |
| `check_imagemagick()` | ImageMagick detection + MoviePy config |
| `validate_font_file()` | Font file validation |
| `get_font_path()` | Multi-step font resolution with fallbacks |
| `verify_default_font()` | Startup check for bundled default font |

---

### 7.9 Model Loader

**File:** `core_engine/model_loader.py` (~130 lines)

Thread-safe singleton for ONNX runtime session management:

- Double-checked locking pattern for lazy initialization
- Resolves model path: `{project_root}/models/kokoro-v0_19.onnx`
- Provides model introspection (input/output tensor metadata)
- Separate from `tts_wrapper.py`'s Kokoro instance (both coexist)

---

## 8. Frontend Architecture

### 8.1 Routing & Pages

StoryFlow uses the Next.js App Router with two fully isolated workspace
sections. `/select` is the application home page (the `/` route redirects to
it) and is shown immediately after login.

| Route | Page | Description |
|-------|------|-------------|
| `/select` | Workspace Selection | Choose Facebook Reels or YouTube Videos |
| `/{section}` | **Account Picker** | List/create/edit/delete Facebook pages or YouTube accounts |
| `/{section}/dashboard` | Account Dashboard | Stats cards + recent projects for the selected account |
| `/{section}/projects` | Project List | Full CRUD table with search, sort, import |
| `/{section}/projects/[id]` | **Timeline Editor** | Core workspace for segment editing |
| `/{section}/gallery` | Video Gallery | Masonry grid of rendered videos for the selected account |
| `/{section}/settings` | Global Settings | Tabbed TTS, subtitle, logo, outro, upscale config |
| `/{section}/bulk-create` | Bulk Render | Select & queue multiple projects for rendering |

`{section}` is either `facebook` or `youtube`. Entering a section always shows
its account picker first; after choosing an account, every sub-page is scoped
to that account via `?account=<uuid>`. Both sections contain an identical copy
of every page for now; they will diverge as platform-specific tools are added.
Legacy root routes (`/projects`, `/gallery`, `/settings`, `/bulk-create`,
`/facebook-reels`, `/fb`, `/youtube-videos`) redirect to the selection page (or
the matching section account picker) so no page can be used outside a section.

Every route has a dedicated `loading.tsx` with skeleton components for optimal loading UX.

---

### 8.1.1 Section & Account Data Isolation

All project-scoped API calls send `?section=facebook|youtube` and, once an
account is selected, `?account=<uuid>`. The frontend attaches both
automatically through an Axios request interceptor: the section comes from the
URL, the account from `?account=` (falling back to the per-section localStorage
selection). The backend then:

- filters `Project` and `Segment` querysets by `project__section` and
  `project__account`
- returns 404 when a project/segment UUID is accessed from the other section or
  another account on the same side
- filters the gallery list and rejects cross-section/cross-account
  stream/download URLs
- stores `section` and `account` on imported projects and rejects mismatched
  payloads
- makes `section` and `account` read-only after creation, so a project cannot
  be moved between workspaces or accounts accidentally
- resolves storage paths from both the section and the account UUID, so two
  accounts can never share or overwrite assets

Global settings and shared assets (logos, outro videos) remain app-wide for
now; per-section/per-account settings can be layered on later without changing
route contracts.

---

### 8.2 Layout System

```
┌──────────────────────────────────────────────────────────────┐
│ Root Layout (layout.tsx)                                      │
│  ├── TooltipProvider (Radix)                                 │
│  ├── ErrorBoundary (React class component)                   │
│  ├── AppShell                                                │
│  │   ├── Top Navigation Bar (always visible)                  │
│  │   │   ├── Brand → /select                                   │
│  │   │   ├── Accounts                                          │
│  │   │   ├── Dashboard                                         │
│  │   │   ├── Projects                                          │
│  │   │   ├── Bulk Create                                       │
│  │   │   ├── Gallery                                           │
│  │   │   ├── Settings                                          │
│  │   │   ├── Account switcher (current page/channel)           │
│  │   │   ├── Section switcher (Facebook / YouTube)             │
│  │   │   └── Logout                                            │
│  │   └── Main Content Area (children)                          │
│  ├── KeyboardShortcutProvider                                  │
│  └── ToastProvider (Sonner, bottom-right)                      │
└──────────────────────────────────────────────────────────────┘

The navigation is horizontal (not a collapsible sidebar) and unique per
section. It is rendered on every page, including the Timeline Editor, which
keeps its own inner editing sidebar below the global bar. Account-scoped pages
redirect to the section account picker when no account is selected. /login and
/select are full-page routes without the shell.
```

---

### 8.3 State Management (Zustand)

Two primary Zustand stores power the frontend:

#### `useProjectStore` (Main Store)

```
┌──────────────────────────────────────────────────────────┐
│                   useProjectStore                         │
│                                                          │
│  State:                                                  │
│  ├── project: ProjectDetail | null                       │
│  ├── segments: Segment[]                                 │
│  ├── isLoading / error                                   │
│  ├── audioTaskId: string | null                          │
│  ├── audioGenerationStatus: Record<id, AudioState>       │
│  ├── staleAudioSegments: Set<string>                     │
│  ├── bulkGenerationProgress: BulkProgress | null         │
│  ├── renderTaskId / renderStatus / renderProgress        │
│  └── outputUrl: string | null                            │
│                                                          │
│  Actions:                                                │
│  ├── fetchProject / addSegment / updateSegment           │
│  ├── deleteSegment / reorderSegments                     │
│  ├── uploadImage / removeImage / removeAudio             │
│  ├── generateAudio / generateAllAudio                    │
│  ├── startRender / pollRenderStatus / cancelRender       │
│  ├── downloadVideo / renameProject                       │
│  └── updateProjectSettings (optimistic update)           │
└──────────────────────────────────────────────────────────┘
```

#### `useSettingsStore` (Settings Store)

```
┌──────────────────────────────────────────────────────────┐
│                  useSettingsStore                         │
│                                                          │
│  State:                                                  │
│  ├── globalSettings: GlobalSettings                      │
│  ├── availableVoices: Voice[]                            │
│  ├── logos: Logo[] / outroVideos: OutroVideo[]           │
│  └── Loading/uploading flags                             │
│                                                          │
│  Actions:                                                │
│  ├── fetchSettings / updateSettings                      │
│  ├── fetchVoices / uploadFont                            │
│  ├── fetchLogos / uploadLogo / deleteLogo               │
│  └── fetchOutroVideos / uploadOutroVideo / deleteOutroVideo │
└──────────────────────────────────────────────────────────┘
```

**Optimistic Updates:** Segment text edits and project settings use optimistic updates with rollback on API failure.

---

### 8.4 API Client Layer

A centralized Axios client at `lib/api.ts` communicates with the backend at `http://localhost:8000`. All endpoints are fully typed with TypeScript interfaces.

```
Frontend                          Backend
────────                          ───────
lib/api.ts ──── Axios ────────► /api/projects/
                                /api/segments/
                                /api/tasks/<id>/status/
                                /api/settings/
                                /api/gallery/
                                /api/settings/logos/
                                /api/settings/outros/
```

**Polling Pattern:** For async tasks (TTS generation, video rendering), the frontend polls `GET /api/tasks/<id>/status/` or `GET /api/projects/<id>/status/` at 2-second intervals until completion, failure, or cancellation.

---

### 8.5 Component Library

StoryFlow is built with **30+ custom components** on top of **18 shadcn/ui primitives**:

**Core Custom Components:**

| Component | Purpose |
|-----------|---------|
| `AppShell` | Global collapsible sidebar + top navigation bar |
| `SegmentCard` | Main segment editing card (memoized with React.memo) |
| `Timeline` | Scrollable list of SegmentCards |
| `AudioPlayer` | HTML5 audio playback with custom seek slider |
| `ImageUploader` | Drag-and-drop + click-to-browse image upload |
| `SegmentTextEditor` | Debounced auto-save textarea (500ms) |
| `RenderButton` | Export/render action with validation |
| `RenderProgress` | Multi-phase animated progress bar |
| `VideoPreview` | HTML5 video player with download |
| `ImportDialog` | JSON/text story import modal |
| `CreateProjectDialog` | New project creation modal |
| `GlobalSettingsPanel` | Per-project settings sidebar panel |
| `SubtitleSettingsForm` | Font, color, size, position configuration |
| `SubtitlePreview` | Live subtitle style preview |
| `SubtitlePositionModal` | Visual Y-position drag editor |
| `VoiceSelector` | TTS voice dropdown with metadata |
| `LogoWatermarkModal` | Logo upload/position/scale editor |
| `StoryTemplateModal` | JSON template/example viewer |
| `EmptyState` | Reusable empty-state placeholder |
| `ErrorBoundary` | React class error boundary |
| `KeyboardShortcutProvider` | Global keyboard shortcut registration |

**shadcn/ui Primitives (18):**
`alert-dialog`, `badge`, `button`, `card`, `checkbox`, `dialog`, `dropdown-menu`, `input`, `progress`, `scroll-area`, `select`, `separator`, `skeleton`, `slider`, `sonner`, `table`, `textarea`, `tooltip`

---

### 8.6 Key UI Features

#### Timeline Editor (Core Workspace)

The Timeline Editor (`/projects/[id]`) is the heart of StoryFlow:

```
┌─────────────────────────────────────────────────────────────────┐
│  Top Bar: [Project Title (editable)]    [Render Controls]       │
├──────────┬──────────────────────────────────────────────────────┤
│          │                                                      │
│ Settings │   ┌─────────────── Segment Card ──────────────────┐  │
│ Sidebar  │   │ #1 ● Ready    [🔒 Lock] [🗑 Delete] [⋮ More] │  │
│          │   │                                                │  │
│ ┌──────┐ │   │ ┌── Text Editor ─────────────────────────────┐ │  │
│ │Detail│ │   │ │ "In the heart of the ancient forest..."    │ │  │
│ │ Tab  │ │   │ └────────────────────────────────────────────┘ │  │
│ │      │ │   │                                                │  │
│ │Count │ │   │ ┌── Image ─────────┐ ┌── Image Prompt ──────┐ │  │
│ │Dates │ │   │ │  [Uploaded IMG]  │ │  "A mystical forest  │ │  │
│ │Quick │ │   │ │  [🗑 Remove]     │ │   with ancient trees"│ │  │
│ │Action│ │   │ └──────────────────┘ └──────────────────────┘ │  │
│ └──────┘ │   │                                                │  │
│ ┌──────┐ │   │ ┌── Audio ──────────────────────────────────┐  │  │
│ │Setti-│ │   │ │ [▶ Play] ──●────── [0:03.2 / 0:08.1]     │  │  │
│ │ ngs  │ │   │ │ [⚠ Text changed — Regenerate]             │  │  │
│ │ Tab  │ │   │ └────────────────────────────────────────────┘  │  │
│ │      │ │   └────────────────────────────────────────────────┘  │
│ │Voice │ │                                                      │
│ │Subs  │ │   ┌─────────────── Segment Card ──────────────────┐  │
│ │Render│ │   │ #2 ○ No Audio  [🔒] [🗑] [⋮]                 │  │
│ │Logo  │ │   │ ...                                            │  │
│ │Outro │ │   └────────────────────────────────────────────────┘  │
│ │Upscl │ │                                                      │
│ └──────┘ │                                                      │
└──────────┴──────────────────────────────────────────────────────┘
```

#### Settings Workspace

The settings page uses a two-pane layout instead of a long stacked page:

- a sticky left rail (horizontal scroll on mobile) with Audio Tester, TTS
  Engines, Voice References, Subtitles, Logos and Outros;
- a single focused content panel on the right, so only the active section is
  rendered at a time;
- a responsive `lg:grid-cols-[236px_minmax(0,1fr)]` grid and a compact
  "changes apply to new projects" hint in the header.

This keeps the page short enough to scan while preserving all existing
controls and save behaviour.

#### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+Enter` | Generate All Audio |
| `Ctrl+Shift+Enter` | Export / Render Video |
| `Ctrl+S` | Save Settings |
| `Shift+?` | Show Shortcuts Help |
| `Escape` | Close Modals |

##### Media player shortcuts

`AudioPlayer` and `GalleryVideoPlayerDialog` use the shared
`useMediaKeyboardShortcuts` hook (`frontend/lib/useMediaKeyboardShortcuts.ts`).
The listener is scoped to the inline player so several segment players can
coexist; the gallery dialog attaches it to the document while its modal is
open. Typing fields, the volume range input and focused buttons keep their
native keyboard behaviour.

| Key | Action |
|-----|--------|
| `Space` / `K` | Play or pause |
| `←` / `→` | Seek ±5 s (`Shift` doubles the step) |
| `J` / `L` | Seek ±10 s |
| `↑` / `↓` | Volume ±10 % (dialog ±5 %) |
| `M` | Mute / unmute |
| `Home` / `End` | Jump to start / end |
| `F` | Fullscreen (video only) |

Native `<video controls>` instances already expose the browser's media keys.

#### Bulk Render Queue

The `/bulk-create` page allows batch rendering multiple projects:
1. Load all projects, validate readiness in parallel
2. Checkbox selection of render-ready projects
3. Sequential processing (one at a time)
4. Per-project status tracking (queued → rendering → completed/failed)
5. Cancel entire queue capability

#### Gallery (Video Browser)

The `/gallery` page provides:
- Masonry grid layout of completed videos
- Hover-to-preview (autoplay on mouseover)
- Full-screen player dialog with:
  - Play/pause, seek, volume, mute, loop
  - Playback rate cycling (0.5×–2×)
  - Picture-in-Picture, fullscreen
  - Download button
  - Link back to project

---

## 9. Data Flow Diagrams

### 9.1 Project Creation & Import Flow

```
User Action                    Frontend                     Backend
───────────                    ────────                     ───────

[Paste JSON/Text] ──►  ImportDialog
                        │
                        ▼
                   Parse format ──► POST /api/projects/import/
                   (JSON or text)        │
                                         ▼
                                    parsers.py
                                    ├── JSONParser.parse()
                                    │   or
                                    └── TextParser.parse()
                                         │
                                         ▼
                                    validators.py
                                    └── validate_import_data()
                                         │
                                         ▼
                                    serializers.py
                                    └── ProjectImportSerializer
                                        ├── Copy GlobalSettings → Project
                                        ├── Create Project
                                        └── Create Segments (atomic)
                                         │
                                         ▼
                                    Response: {project_id, segments}
                                         │
                   ◄─────────────────────┘
                   Navigate to /projects/{id}
                   fetchProject() → Load into Zustand store
```

### 9.2 Audio Generation Flow

```
User Action                   Frontend                      Backend
───────────                   ────────                      ───────

[Click "Generate              
 All Audio"] ───────► POST /api/projects/{id}/generate-all-audio/
                              │
                              │                        TaskManager.submit_task()
                              │                        └─► ThreadPoolExecutor
                              │                             │
                              ▼                             ▼
                      Response: {task_id}           For each segment:
                              │                     ├── Skip locked/empty/already-on-this-engine
                              │                     ├── core_engine.tts.synthesize()
                      Poll every 2s:                │   ├── kokoro → Kokoro.create; qwen → GPU worker RPC
                      GET /api/tasks/{id}/status/   │   ├── Save WAV file
                              │                     │   └── Update segment.audio_file
                              │                     └── Report progress
                              │
                              ▼
                      Update per-segment
                      AudioGenerationState
                      in Zustand store
                              │
                              ▼
                      Refresh segments on
                      completion
```

### 9.3 Video Rendering Pipeline

```
User Action                   Frontend                      Backend
───────────                   ────────                      ───────

[Click "Render"] ────► Validate: all segments       POST /api/projects/{id}/render/
                       have images + audio                  │
                              │                             ▼
                              │                    validate_project_for_render()
                              │                             │
                              │                    TaskManager.submit_task(render_task_function)
                              │                             │
                              ▼                             ▼
                      Response: {task_id}           render_project() Pipeline:
                              │                    │
                      Poll every 2s:               ├── 1. Check FFmpeg
                      GET /api/projects/           ├── 2. Load project settings
                          {id}/status/             ├── 3. Query segments
                              │                    ├── 4. [Upscale images]
                              ▼                    ├── 5. Mix audio (CompositeAudioClip → WAV)
                      RenderProgress updates:      ├── 6. fast_render_segments():
                      ├── Phase: "segments"        │       ├── Pre-render subtitles
                      ├── Phase: "frames"          │       ├── Pre-render logo
                      ├── Phase: "encoding"        │       ├── Frame loop:
                      └── Phase: "finalizing"      │       │   ├── Ken Burns interpolation
                              │                    │       │   ├── NumPy crop + resize
                              ▼                    │       │   ├── Alpha-blit overlays
                      Animated progress bar        │       │   └── Write to FFmpeg pipe
                      (requestAnimationFrame)      │       └── Close FFmpeg
                              │                    ├── 7. [Append outro]
                              │                    ├── 8. Verify output (FFprobe)
                              │                    └── 9. Cleanup temps
                              ▼                            │
                      status: "completed"                  ▼
                      Show VideoPreview          Project.status = COMPLETED
                      + Download button          Project.output_path = final.mp4
```

---

## 10. Implemented Features List

### Project Management
- [x] Create projects with title
- [x] Import stories from JSON format
- [x] Import stories from plain text format (delimiter-based)
- [x] Append segments to existing projects via import
- [x] Rename projects inline
- [x] Delete projects with full media cleanup
- [x] Project status lifecycle (DRAFT → PROCESSING → COMPLETED/FAILED)
- [x] Project list with search and multi-sort (title, date, status, segments)
- [x] Dashboard with aggregate statistics
- [x] Per-project settings (copied from global defaults on creation)

### Segment Management
- [x] Create / read / update / delete segments
- [x] Drag-and-drop image upload (JPEG, PNG, WebP; max 20MB)
- [x] Image validation (extension, size, Pillow integrity check)
- [x] Remove segment images
- [x] Atomic segment reordering
- [x] Segment locking (prevent edits during processing)
- [x] Auto-save text editing with debounce (500ms)
- [x] Image prompt display with copy-to-clipboard

### Text-to-Speech
- [x] Kokoro-82M ONNX model integration
- [x] 20+ voice options (American/British, male/female)
- [x] Adjustable speech speed (0.5×–2.0×)
- [x] Single-segment audio generation
- [x] Batch audio generation (all segments)
- [x] Background async processing with progress tracking
- [x] TTS test audio playback (settings page)
- [x] Stale audio detection (text changed after generation)
- [x] Audio playback with custom player (play/pause, seek, time display)

### Video Rendering
- [x] Full video rendering pipeline
- [x] Ken Burns smart pan/zoom motion (deterministic presets adapted to subject space)
- [x] Crossfade transitions between segments
- [x] Timed subtitle overlays (character-proportional timing)
- [x] Subtitle styling (font, size, color, position, stroke)
- [x] Custom font upload (.ttf, .otf, .woff, .woff2)
- [x] Logo watermark overlay (position, scale, opacity, margin)
- [x] Outro video appending (with crossfade transition)
- [x] Optional AI image upscaling (Real-ESRGAN, 3 model variants)
- [x] Hardware-accelerated encoding (NVENC GPU with CPU fallback)
- [x] High-performance compositor (~5–10 ms/frame at 1080p)
- [x] Multi-phase progress tracking (segments → frames → encoding → finalizing)
- [x] Cooperative render cancellation
- [x] Render output verification (FFprobe)
- [x] 12 resolution presets (16:9, 9:16, 1:1, 4:5, 4:3, 3:4)
- [x] Configurable FPS (24, 30, 60)
- [x] Configurable inter-segment silence (0–5 seconds)

### Gallery & Media
- [x] Video gallery with masonry grid layout
- [x] Video streaming with HTTP Range support (206 Partial Content)
- [x] Video download as attachment
- [x] Full-screen video player (play, seek, volume, loop, playback rate, PiP, fullscreen)
- [x] Hover-to-preview in gallery grid

### Settings & Configuration
- [x] Global settings singleton (defaults for new projects)
- [x] Per-project settings override
- [x] TTS settings (voice, speed)
- [x] Subtitle settings (font, size, color, position, custom font, enable/disable)
- [x] Render settings (resolution, FPS, Ken Burns zoom, transition duration)
- [x] Logo management (upload, delete, position, scale, opacity)
- [x] Outro video management (upload, delete)
- [x] Upscaler settings (model selection, denoise strength, enable/disable)
- [x] Live subtitle preview

### Bulk Operations
- [x] Bulk render queue (select and render multiple projects sequentially)
- [x] Per-project validation before queuing
- [x] Queue-level cancel

### UI/UX
- [x] Dark mode only theme
- [x] Collapsible sidebar with persistent state (localStorage)
- [x] Loading skeletons for all pages
- [x] Error boundary (React class component)
- [x] Toast notifications (Sonner)
- [x] Keyboard shortcuts (Ctrl+Enter, Ctrl+Shift+Enter, Ctrl+S, Shift+?, Escape)
- [x] Keyboard shortcuts help dialog
- [x] Responsive layout
- [x] Optimistic updates with rollback

### Developer Experience
- [x] Quick-start scripts (batch/shell for both backend and frontend)
- [x] Jest + React Testing Library test suite (13 test files)
- [x] Backend integration tests
- [x] Comprehensive development documentation (5-phase document series)
- [x] Test story JSON files (11 sample stories)

---

## 11. API Reference Summary

> **Section scoping:** every project-scoped endpoint accepts
> `?section=facebook|youtube`. When present, the response is limited to that
> workspace and cross-section UUIDs return `404`. The frontend sends it
> automatically on every request.

### Projects API

```
GET    /api/projects/?section={section}        → PaginatedResponse<Project>
POST   /api/projects/?section={section}        → Project
GET    /api/projects/{id}/?section={section}   → ProjectDetail (with segments)
PATCH  /api/projects/{id}/?section={section}   → ProjectDetail
DELETE /api/projects/{id}/?section={section}   → 204 No Content
POST   /api/projects/import/?section={section} → ProjectDetail
POST   /api/projects/{id}/import-segments/     → {segments: Segment[]}
POST   /api/projects/{id}/generate-all-audio/  → {task_id: string}
POST   /api/projects/{id}/render/              → {task_id: string}
GET    /api/projects/{id}/status/              → RenderStatusResponse
POST   /api/projects/{id}/cancel-render/       → {status: "cancelled"}
```

### Segments API

```
GET    /api/segments/?project={id}&section={section} → Segment[]
POST   /api/segments/                          → Segment
GET    /api/segments/{id}/                     → Segment
PATCH  /api/segments/{id}/                     → Segment
DELETE /api/segments/{id}/                     → 204 No Content
POST   /api/segments/reorder/                  → {status: "ok"}
POST   /api/segments/{id}/upload-image/        → Segment
DELETE /api/segments/{id}/remove-image/        → Segment
DELETE /api/segments/{id}/remove-audio/        → Segment
POST   /api/segments/{id}/generate-audio/      → {task_id: string}
```

### Settings API

```
GET    /api/settings/                          → GlobalSettings / AccountSettings
PATCH  /api/settings/                          → GlobalSettings / AccountSettings
GET    /api/settings/project-defaults/         → {results: ProjectSettingsProfile[]}
GET    /api/settings/project-defaults/{w}x{h}/ → ProjectSettingsProfile
PATCH  /api/settings/project-defaults/{w}x{h}/ → ProjectSettingsProfile
DELETE /api/settings/project-defaults/{w}x{h}/ → ProjectSettingsProfile (fallback)
GET    /api/settings/voices/                   → Voice[]
GET    /api/settings/tts-engines/              → {default_engine, engines[]}
POST   /api/settings/tts-engines/qwen/unload/  → {ok, message}
GET    /api/settings/voice-references/         → VoiceReference[]
POST   /api/settings/voice-references/         → VoiceReference (multipart)
PATCH  /api/settings/voice-references/{id}/    → VoiceReference
DELETE /api/settings/voice-references/{id}/    → 204 No Content
POST   /api/settings/font/upload/              → {path: string}
POST   /api/settings/tts-test/                 → audio/wav (binary)
GET    /api/settings/logos/                     → Logo[]
POST   /api/settings/logos/                     → Logo
DELETE /api/settings/logos/{id}/               → 204 No Content
GET    /api/settings/outros/                   → OutroVideo[]
POST   /api/settings/outros/                   → OutroVideo
DELETE /api/settings/outros/{id}/             → 204 No Content
```

### Tasks & Gallery API

```
GET    /api/tasks/{task_id}/status/            → TaskStatusResponse
GET    /api/gallery/?section={section}         → GalleryItem[]
GET    /api/gallery/{id}/stream/?section={section}   → video/mp4 (streaming)
GET    /api/gallery/{id}/download/?section={section} → video/mp4 (attachment)
```

---

## 12. Error Handling Strategy

Each layer of StoryFlow employs a distinct error handling approach:

| Layer | Strategy |
|-------|----------|
| **TTS Wrapper** | Never raises — returns `{success: false, error: "message"}` |
| **Video Renderer** | Raises `RuntimeError`/`ValueError` after cleanup; deletes partial output |
| **Fast Compositor** | Raises `RuntimeError` on FFmpeg failure; subtitle errors logged and gracefully skipped |
| **Image Upscaler** | Returns original image path on any failure (graceful degradation) |
| **Ken Burns** | Raises `ValueError` for corrupt images or invalid parameters |
| **Audio Utils** | `get_audio_duration` raises `FileNotFoundError`; `validate_audio_file` returns `False` |
| **Render Utils** | Uses fallback defaults for fonts/FFmpeg/ImageMagick — never crashes |
| **Model Loader** | Raises `FileNotFoundError`/`RuntimeError` with actionable error messages |
| **API Views** | Returns structured JSON error responses with appropriate HTTP status codes |
| **Task Manager** | Captures all exceptions; marks task as `FAILED` with error details |
| **Frontend Stores** | Try/catch with toast notifications; optimistic update rollback on failure |
| **Frontend UI** | React ErrorBoundary catches unhandled render errors |

---

## 13. Performance Optimizations

### Backend

1. **Fast Compositor** — Custom NumPy + direct FFmpeg pipe rendering achieves ~5–10 ms/frame (10–15× faster than MoviePy 2.x)
2. **Pre-rendered Overlays** — Subtitles and logos are rendered to RGBA bitmaps once, then alpha-blitted per frame (no text rendering per frame)
3. **NumPy Crop Views** — Ken Burns crop extraction uses NumPy array slicing (O(1), no memory copy)
4. **Sequential Task Execution** — `max_workers=1` prevents GPU/CPU resource contention
5. **NVENC Auto-Detection** — Automatic GPU encoder usage when available
6. **Tile-Based Upscaling** — Large images processed in overlapping tiles to fit GPU memory
7. **FP16 Inference** — Real-ESRGAN uses half-precision on CUDA for faster inference
8. **Thread-Safe Singletons** — Double-checked locking for Kokoro TTS and upscaler model caches
9. **DB Connection Safety** — Explicit connection closing in task `finally` blocks (SQLite thread safety)
10. **Stale Task Cleanup** — Auto-removal of completed/failed tasks after 1 hour

### Frontend

1. **React.memo** — `SegmentCard` memoization prevents unnecessary re-renders in long timelines
2. **Debounced Auto-Save** — 500ms debounce on text editor input (reduces API calls)
3. **Optimistic Updates** — Instant UI feedback for text edits and settings changes
4. **Loading Skeletons** — Every page has skeleton loading states for perceived performance
5. **Throttled Progress** — Render progress reporting throttled to 2% increments
6. **requestAnimationFrame** — Smooth animated progress bar transitions
7. **localStorage Persistence** — Sidebar collapse state persisted across sessions
8. **Lazy Voice Loading** — Voice list fetched on demand with hardcoded fallback

---

## 14. Security & Design Constraints

### Intentional Design Decisions

| Decision | Rationale |
|----------|-----------|
| **No authentication** | Single-user, local-only application |
| **No Docker** | Simplicity for local development |
| **No cloud APIs** | Privacy-first — all data stays on machine |
| **SQLite database** | Zero-config, no external DB server needed |
| **AllowAny permissions** | No authorization needed for local-only app |
| **DEBUG=True** | Development-only application |
| **Insecure SECRET_KEY** | Not deployed — acceptable for local use |
| **CORS whitelist** | Only `localhost:3000` allowed |

### File Upload Security

| Upload Type | Validations |
|------------|-------------|
| Images | Extension whitelist (.jpg/.jpeg/.png/.webp), max 20MB, Pillow integrity verification |
| Fonts | Extension whitelist (.ttf/.otf/.woff/.woff2), max 10MB |
| Logos | Extension whitelist (.png/.webp/.jpg), max 5MB |
| Outro Videos | Extension whitelist (.mp4/.mov/.webm/.avi/.mkv), max 100MB |

### Resource Protection

- Segment locking (`is_locked`) prevents concurrent edits during rendering
- `ThreadPoolExecutor(max_workers=1)` ensures sequential heavy-task execution
- Cooperative cancellation allows graceful render abort without orphaned processes
- `finally` blocks guarantee temp file cleanup even on failures

---

## 15. Appendix

### A. Environment Requirements

| Requirement | Minimum Version |
|-------------|----------------|
| Python | 3.11+ |
| Node.js | 18+ |
| npm | 9+ |
| FFmpeg | Any (required for video rendering) |
| Git | Any |
| PyTorch | (Optional) Required only for Real-ESRGAN upscaling |
| ImageMagick | (Optional) Used by MoviePy for text rendering fallback |

### B. ML Models

| Model | File | Size | Purpose |
|-------|------|------|---------|
| Kokoro-82M | `models/kokoro-v0_19.onnx` | ~82M params | Text-to-speech |
| Real-ESRGAN x4plus | `models/upscalers/RealESRGAN_x4plus.pth` | 64MB | 4× photo upscale |
| Real-ESRGAN x2plus | `models/upscalers/RealESRGAN_x2plus.pth` | 64MB | 2× photo upscale |
| Real-ESRGAN x4plus anime | `models/upscalers/RealESRGAN_x4plus_anime_6B.pth` | 17MB | 4× anime upscale |
| Qwen3-TTS 0.6B Base | Hugging Face cache (`Qwen/Qwen3-TTS-12Hz-0.6B-Base`) | 0.6B params | Optional GPU TTS + voice cloning |
| Qwen3-TTS 0.6B CustomVoice | Hugging Face cache (`Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice`) | 0.6B params | Optional GPU preset voices |

### C. Development Phase Documentation

The `document-series/` directory tracks the phased development approach:

| Phase | Name | Contents |
|-------|------|----------|
| Phase 01 | "The Skeleton" | Project setup, database models, dashboard UI |
| Phase 02 | "The Logic" | Import/parse engine, segment management API, image upload + timeline editor |
| Phase 03 | "The Voice" | TTS engine integration, audio generation API, audio playback UI |
| Phase 04 | "The Vision" | Basic video assembly, Ken Burns effect, subtitle engine, fast compositor |
| Phase 05 | "The Polish" | Polishing features, logo watermarks, outros, upscaling, bulk render |

### D. Quick Start

**Terminal 1 — Backend:**
```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver   # → http://localhost:8000
```

**Terminal 2 — Frontend:**
```bash
cd frontend
npm install
npm run dev                  # → http://localhost:3000
```

Or use the provided scripts from the project root:
```bash
start-backend.bat    # Windows
start-frontend.bat   # Windows
```

---

*This document was generated from a comprehensive analysis of the StoryFlow codebase. For implementation details, refer to the source code and the phase documentation in `document-series/`.*
