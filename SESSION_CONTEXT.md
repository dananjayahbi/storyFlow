# StoryFlow — Session Handoff Context Document

> **Created:** 2026-02-19 ~12:32  
> **Purpose:** Enable the next session to continue exactly where this session left off.  
> **Delete after use:** Yes — this file is temporary.

---

## 1. Overall Progress

### SubPhase 01.01 — Project Initialization & Tooling Setup ✅ COMPLETE (13/13 tasks)

| Task | Title | Status |
|------|-------|--------|
| 01.01.01 | Initialize Django Project | ✅ Done |
| 01.01.02 | Create API App | ✅ Done |
| 01.01.03 | Create Core Engine Module | ✅ Done |
| 01.01.04 | Write Requirements File | ✅ Done |
| 01.01.05 | Configure Django Settings | ✅ Done |
| 01.01.06 | Initialize Next.js Project | ✅ Done |
| 01.01.07 | Configure Tailwind CSS | ✅ Done |
| 01.01.08 | Initialize Shadcn/UI | ✅ Done |
| 01.01.09 | Configure CORS (Verification) | ✅ Done |
| 01.01.10 | Create .gitignore | ✅ Done |
| 01.01.11 | Create Dev Run Scripts | ✅ Done |
| 01.01.12 | Create Media & Model Directories | ✅ Done |
| 01.01.13 | Create Root README | ✅ Done |

### SubPhase 01.02 — Database Models & Migrations 🔄 IN PROGRESS (2/11 tasks)

| Task | Title | Status |
|------|-------|--------|
| 01.02.01 | Define Project Model | ✅ Done |
| 01.02.02 | Define Segment Model | ✅ Done |
| 01.02.03 | Create GlobalSettings Model | ⬜ Next |
| 01.02.04 | Run Migrations | ⬜ Pending |
| 01.02.05 | Register Admin | ⬜ Pending |
| 01.02.06 | Configure DRF Settings | ⬜ Pending |
| 01.02.07 | Create Project Serializer | ⬜ Pending |
| 01.02.08 | Create Segment Serializer | ⬜ Pending |
| 01.02.09 | Create GlobalSettings Serializer | ⬜ Pending |
| 01.02.10 | Create ProjectDetail Serializer | ⬜ Pending |
| 01.02.11 | Create Superuser | ⬜ Pending |

---

## 2. Technical Environment

| Component | Details |
|-----------|---------|
| **OS** | Windows |
| **Python** | 3.14.0 (system) |
| **Django** | 5.2.11 |
| **DRF** | 3.16.1 |
| **django-cors-headers** | 4.9.0 |
| **Pillow** | 12.1.1 (≥11.0 required for Python 3.14) |
| **Node.js** | 18+ (system) |
| **Next.js** | 16.1.6 (Turbopack) |
| **Tailwind CSS** | v4 (CSS-based config, NOT v3) |
| **Shadcn/UI** | 3.8.5 (new-york style, neutral base color) |
| **Axios** | 1.13.5 |
| **Virtual env** | `backend/venv/` (Python 3.14.0) |
| **Database** | SQLite (Django default) |
| **Workspace** | `E:\My_GitHub_Repos\storyFlow` |
| **Git repo** | dananjayahbi/storyFlow, branch: main |

---

## 3. Key Deviations from Task Documents

1. **Pillow version:** Task docs specify `>=10.0,<11.0` but Python 3.14 requires Pillow ≥11.0. We use `>=11.0,<13.0` in requirements.txt (installed: 12.1.1).

2. **No `tailwind.config.ts`:** Tailwind CSS v4 uses CSS-based configuration (`@import "tailwindcss"` in globals.css) instead of a JS/TS config file. Added `@source` directives in globals.css for explicit content path coverage.

3. **Next.js `src/` directory:** `create-next-app@latest` created `src/` directory despite `--src-dir=false`. Manually moved `app/` to root and updated `tsconfig.json` paths from `"./src/*"` to `"./*"`.

4. **Shadcn/UI CLI command:** Used `npx shadcn@latest` instead of `npx shadcn-ui@latest` (package has been renamed).

---

## 4. Current Directory Structure

```
E:\My_GitHub_Repos\storyFlow\
├── .gitignore
├── README.md
├── SESSION_CONTEXT.md          ← THIS FILE (temporary)
├── start-backend.bat
├── start-backend.sh
├── start-frontend.bat
├── start-frontend.sh
├── backend/
│   ├── manage.py
│   ├── requirements.txt
│   ├── db.sqlite3              (auto-generated, git-ignored)
│   ├── storyflow_backend/
│   │   ├── __init__.py
│   │   ├── asgi.py
│   │   ├── settings.py         ← MODIFIED (INSTALLED_APPS, MIDDLEWARE, CORS, MEDIA)
│   │   ├── urls.py
│   │   └── wsgi.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── admin.py            (default boilerplate — not yet modified)
│   │   ├── apps.py
│   │   ├── models.py           ← MODIFIED (Project + Segment models defined)
│   │   ├── tests.py
│   │   ├── views.py            (default boilerplate — not yet modified)
│   │   └── migrations/
│   │       └── __init__.py     (NO migrations generated yet — waiting for Task 01.02.04)
│   ├── core_engine/
│   │   ├── __init__.py         (empty)
│   │   ├── tts_wrapper.py      (placeholder docstring only)
│   │   ├── video_renderer.py   (placeholder docstring only)
│   │   └── ken_burns.py        (placeholder docstring only)
│   ├── media/
│   │   └── projects/
│   │       └── .gitkeep
│   └── venv/                   (Python 3.14.0 virtual environment)
├── frontend/
│   ├── app/
│   │   ├── globals.css         ← MODIFIED (Tailwind v4 + @source directives + Shadcn vars)
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   └── favicon.ico
│   ├── components/
│   │   └── ui/
│   │       ├── badge.tsx
│   │       ├── button.tsx
│   │       ├── card.tsx
│   │       ├── dialog.tsx
│   │       └── input.tsx
│   ├── lib/
│   │   └── utils.ts            (cn() helper from Shadcn)
│   ├── public/
│   ├── .gitignore
│   ├── components.json
│   ├── eslint.config.mjs
│   ├── next-env.d.ts
│   ├── next.config.ts
│   ├── package.json            ← MODIFIED (axios added)
│   ├── package-lock.json
│   ├── postcss.config.mjs
│   ├── tsconfig.json           ← MODIFIED (paths: "./*" instead of "./src/*")
│   └── README.md
├── models/
│   └── .gitkeep
└── document-series/            (task documents — read-only reference)
```

---

## 5. Current State of Key Files

### `backend/storyflow_backend/settings.py`
- `INSTALLED_APPS`: includes `'rest_framework'`, `'corsheaders'`, `'api'`
- `MIDDLEWARE`: `'corsheaders.middleware.CorsMiddleware'` is FIRST entry
- `ALLOWED_HOSTS`: `['localhost', '127.0.0.1']`
- `CORS_ALLOWED_ORIGINS`: `["http://localhost:3000"]`
- `MEDIA_URL`: `'/media/'`
- `MEDIA_ROOT`: `BASE_DIR / 'media'`
- `DEFAULT_AUTO_FIELD`: `'django.db.models.BigAutoField'`

### `backend/api/models.py`
- `STATUS_CHOICES`: 4 entries (DRAFT, PROCESSING, COMPLETED, FAILED)
- `Project` model: 9 fields (id=UUID, title, created_at, updated_at, status, resolution_width, resolution_height, framerate, output_path)
- `segment_image_path()` and `segment_audio_path()`: module-level upload path callables
- `Segment` model: 9 fields (id=UUID, project=FK, sequence_index, text_content, image_prompt, image_file, audio_file, audio_duration, is_locked)
- **No migrations generated yet** — waiting for all models to be defined (Task 01.02.04)

### `backend/requirements.txt`
```
Django>=5.0,<6.0
djangorestframework>=3.15,<4.0
django-cors-headers>=4.3,<5.0
Pillow>=11.0,<13.0
```

### `frontend/app/globals.css`
- Uses `@import "tailwindcss"` (Tailwind v4)
- Has `@source` directives for `app/`, `components/`, `lib/`
- Shadcn/UI CSS variables injected by `shadcn init`

### `frontend/tsconfig.json`
- `paths`: `"@/*": ["./*"]` (NOT `./src/*`)
- `strict: true`

---

## 6. What to Do Next

1. **Read and implement:** `document-series/Phase_01_The_Skeleton/SubPhase_01_02_Database_Models/Task_01_02_03_Create_GlobalSettings_Model.md`
2. Continue with Tasks 01.02.04 through 01.02.11 sequentially.
3. Follow the established workflow: read doc → implement → verify → run flow.py.

---

## 7. Workflow Notes

- **flow.py location:** `python "E:\My_GitHub_Repos\flow\flow.py"` — must run after every task for user review
- **Python commands in backend:** Always use `.\venv\Scripts\python.exe` or activate venv first
- **Django check command:** `.\venv\Scripts\python.exe manage.py check`
- **TypeScript check:** `npx tsc --noEmit` (from frontend/)
- **Dev servers:** Backend on :8000, Frontend on :3000
- **No `serializers.py` or `urls.py` in api/ yet** — these are created in later tasks
- **No migrations yet** — `makemigrations` runs in Task 01.02.04 after all 3 models are defined
