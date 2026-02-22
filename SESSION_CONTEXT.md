# StoryFlow — Session Handoff Context

> **Created:** Session ending after Task 05.01.05  
> **Purpose:** Enable the next session to continue seamlessly from where this one left off.  
> **Delete after use.**

---

## 1. Overall Progress

| Phase | Sub-Phase | Status |
|-------|-----------|--------|
| Phase 01 — The Skeleton | 01.01 Project Setup | ✅ COMPLETE |
| | 01.02 Database Models | ✅ COMPLETE |
| | 01.03 Dashboard UI | ✅ COMPLETE |
| Phase 02 — The Logic | 02.01 Import/Parse Engine | ✅ COMPLETE |
| | 02.02 Segment Management API | ✅ COMPLETE |
| | 02.03 Image Upload / Timeline Editor | ✅ COMPLETE |
| Phase 03 — The Voice | 03.01 TTS Engine Integration | ✅ COMPLETE |
| | 03.02 Audio Generation API | ✅ COMPLETE |
| | 03.03 Audio Playback UI | ✅ COMPLETE |
| Phase 04 — The Vision | 04.01 Basic Video Assembly | ✅ COMPLETE (11 tasks) |
| | 04.02 Ken Burns Effect | ✅ COMPLETE (12 tasks) |
| | 04.03 Render Pipeline & Progress | ✅ COMPLETE (14 tasks) |
| **Phase 05 — The Polish** | **05.01 Subtitle Generation & Overlay** | **🔶 IN PROGRESS (5/11 tasks done)** |
| | 05.02 Transitions & Effects | ⬜ NOT STARTED (8 tasks) |
| | 05.03 Final UI Polish & Testing | ⬜ NOT STARTED (17 tasks) |

---

## 2. Current Position

**Next task to implement:** `Task 05.01.06 — ImageMagick Check And Fallback`

### SubPhase 05.01 Task Status

| Task | Title | Status |
|------|-------|--------|
| 05.01.01 | Create Subtitle Engine Module | ✅ COMPLETE |
| 05.01.02 | Word Chunking Algorithm | ✅ COMPLETE |
| 05.01.03 | Subtitle Timing Calculator | ✅ COMPLETE |
| 05.01.04 | TextClip YouTube Styling | ✅ COMPLETE |
| 05.01.05 | Subtitle Compositing In Renderer | ✅ COMPLETE |
| **05.01.06** | **ImageMagick Check And Fallback** | **⬜ NEXT** |
| 05.01.07 | Bundle Default Font | ⬜ NOT STARTED |
| 05.01.08 | Font Validation Utility | ⬜ NOT STARTED |
| 05.01.09 | Write Chunking Tests | ⬜ NOT STARTED |
| 05.01.10 | Write Timing Tests | ⬜ NOT STARTED |
| 05.01.11 | Write Integration Subtitle Tests | ⬜ NOT STARTED |

**Note on 05.01.06 & 05.01.08:** During Task 05.01.05, `check_imagemagick()` and `get_font_path()` were already implemented in `render_utils.py` because the renderer compositing code needed them. Tasks 05.01.06 and 05.01.08 may need to *enhance* or *expand* these existing implementations rather than create them from scratch. Read the task documents carefully and compare with what already exists.

---

## 3. Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Backend | Django | 5.2.11 |
| Backend | Django REST Framework | 3.16.1 |
| Backend | Python | 3.14.0 |
| Backend | SQLite | (dev DB) |
| Backend | MoviePy | 2.1.2 |
| Backend venv | `backend/venv/` | — |
| Frontend | Next.js | 16.1.6 |
| Frontend | Tailwind CSS | v4 |
| Frontend | Shadcn/UI | new-york style |
| Frontend | Zustand | (state management) |

### MoviePy 2.x API (CRITICAL — differs from 1.x)

```python
# Correct MoviePy 2.x parameter names:
TextClip(text=, font_size=, font=, color=, stroke_color=, stroke_width=, method=, size=, text_align=)
# NOT: txt=, fontsize=, align=

# Immutable chaining:
clip.with_position()   # NOT set_position()
clip.with_start()      # NOT set_start()
clip.with_duration()   # NOT set_duration()
clip.with_audio()      # NOT set_audio()

# Imports:
from moviepy import TextClip, AudioFileClip, CompositeVideoClip, concatenate_videoclips
```

---

## 4. Test Counts

| Suite | Tests | Status |
|-------|-------|--------|
| Backend Django (`api/tests.py`) | 153 | ✅ ALL PASS |
| Backend core_engine tests | ~42 | ✅ ALL PASS |
| Frontend Jest | 85 | ✅ ALL PASS |
| TypeScript errors | 0 | ✅ CLEAN |

**Run commands:**
```bash
# Backend
cd E:\My_GitHub_Repos\storyFlow\backend
.\venv\Scripts\python.exe manage.py test api --verbosity 2

# Frontend
cd E:\My_GitHub_Repos\storyFlow\frontend
npx jest --forceExit
```

---

## 5. Key Backend Files Modified This Session

### `backend/core_engine/subtitle_engine.py` (NEW — 282 lines)

Full subtitle pipeline module with:
- **Constants:** `DEFAULT_MAX_WORDS=6`, `MIN_CHUNK_WORDS=4`, `MIN_DISPLAY_DURATION=0.5`, `FONT_SIZE_DIVISOR=18`, `TEXT_WIDTH_RATIO=0.9`, `SUBTITLE_Y_RATIO=0.85`, `DEFAULT_STROKE_COLOR="#000000"`, `DEFAULT_STROKE_WIDTH=2`
- **`_is_boundary_word(word)`** — Checks if a word ends with sentence/clause punctuation
- **`chunk_text(text, max_words=6)`** — Splits text into display-sized chunks with boundary-aware breaking and orphan prevention
- **`calculate_subtitle_timing(chunks, total_duration, min_duration=0.5)`** — Word-proportional duration assignment with normalization
- **`generate_subtitle_clips(chunks, timings, resolution, font, color)`** — Creates MoviePy TextClips with YouTube-style positioning
- **`create_subtitles_for_segment(text_content, audio_duration, resolution, font, color)`** — Entry-point chaining all steps

### `backend/core_engine/video_renderer.py` (MODIFIED — 480 lines)

Changes in Task 05.01.05:
- Added `CompositeVideoClip` to MoviePy imports (both 1.x and 2.x blocks)
- Added `from core_engine.subtitle_engine import create_subtitles_for_segment`
- **Section C3:** Reads `subtitle_font` and `subtitle_color` from GlobalSettings, resolves font path via `render_utils.get_font_path()`
- **Section C4:** Single `check_imagemagick()` call before the segment loop; initializes `warnings: list[str] = []`
- **Step 3b** (per-segment loop): After Ken Burns clip creation, generates subtitles and composites them with `CompositeVideoClip([ken_burns_clip] + subtitle_clips).with_duration(audio_duration)`, wrapped in try/except for graceful degradation
- **Progress callback:** Includes `" + subtitles composited"` note when subtitles are applied
- **Result dict:** Now returns `{"output_path", "duration", "file_size", "warnings"}`

### `backend/core_engine/render_utils.py` (MODIFIED — ~450 lines)

New functions added in Task 05.01.05:
- **`check_imagemagick()`** — Cached detection via `shutil.which("magick")` or `"convert"`
- **`reset_imagemagick_cache()`** — Test helper to clear cache
- **`get_font_path(font_name)`** — Resolves font name to filesystem path: direct file → Windows Fonts dir → Linux `fc-match` → `None` fallback

### `backend/api/tests.py` (~1,951 lines, 21 test classes)

Last class added: `RenderPipelineTests(APITestCase)` with 14 test methods including:
- `run_synchronously` helper that mocks `submit_task` to run tasks in the same thread (avoids SQLite in-memory DB locking from background threads)
- Failure test uses try/except since `render_task_function` re-raises after setting FAILED status

---

## 6. Key Model Fields (GlobalSettings)

```python
class GlobalSettings(models.Model):
    zoom_intensity = models.FloatField(default=1.3)
    default_voice_id = models.CharField(max_length=100, default='af_heart')
    tts_speed = models.FloatField(default=1.0)
    subtitle_font = models.CharField(max_length=200, blank=True, default='')
    subtitle_color = models.CharField(max_length=7, default='#FFFFFF')
```

---

## 7. Workflow Pattern

The user follows a strict sequential task workflow:

1. **User instruction:** "proceed with the next document... and implement its tasks... Then run flow.py again for my review."
2. **Read** the task document from `document-series/`
3. **Implement** exactly what the document specifies
4. **Validate** using a temporary `_temp_validate_*.py` script (create → run → delete)
5. **Run all tests** (backend 153 + frontend 85)
6. **Run flow.py:** `python E:\My_GitHub_Repos\flow\flow.py`
7. **Wait** for user approval via flow.py GUI
8. **Repeat** for next task

### Important Rules
- Use **subagents** to manage context window when gathering extensive information
- Use **temp Python files** for validation (not inline `-c` commands)
- flow.py command: `python E:\My_GitHub_Repos\flow\flow.py` (with drive letter `E:`, NOT `/e/...`)
- Task documents live in: `document-series/Phase_0X_*/SubPhase_0X_0Y_*/Task_0X_0Y_ZZ_*.md`
- Always check existing implementations before creating stubs (some tasks may partially exist already)

---

## 8. Project Structure (Key Paths)

```
storyFlow/
├── backend/
│   ├── venv/                          # Python virtual environment
│   ├── manage.py
│   ├── db.sqlite3
│   ├── requirements.txt
│   ├── api/
│   │   ├── models.py                  # Project, Segment, GlobalSettings
│   │   ├── views.py                   # ViewSets + standalone views
│   │   ├── serializers.py
│   │   ├── tasks.py                   # TaskManager, background task system
│   │   ├── tests.py                   # 21 test classes, 153 tests
│   │   ├── urls.py
│   │   ├── parsers.py
│   │   └── validators.py
│   ├── core_engine/
│   │   ├── subtitle_engine.py         # NEW — subtitle pipeline
│   │   ├── video_renderer.py          # render_project() with subtitle compositing
│   │   ├── ken_burns.py               # Ken Burns animation
│   │   ├── render_utils.py            # FFmpeg/ImageMagick checks, image resize, font resolution
│   │   ├── tts_wrapper.py             # Kokoro TTS integration
│   │   ├── audio_utils.py
│   │   ├── model_loader.py
│   │   └── tests/                     # core_engine test files
│   ├── media/projects/                # Uploaded media files
│   └── storyflow_backend/settings.py
├── frontend/
│   ├── app/                           # Next.js pages
│   ├── components/                    # React components (17 custom + 15 shadcn/ui)
│   ├── lib/                           # api.ts, stores.ts, types.ts, utils.ts
│   ├── __tests__/                     # 12 test files, 85 tests
│   └── package.json
├── models/
│   ├── kokoro-v0_19.onnx              # TTS model
│   └── voices/                        # Voice files
└── document-series/                   # Task documentation
    └── Phase_05_The_Polish/
        ├── SubPhase_05_01_Subtitle_Generation_Overlay/  # 11 tasks (5 done)
        ├── SubPhase_05_02_Transitions_Effects/          # 8 tasks
        └── SubPhase_05_03_Final_UI_Polish_Testing/      # 17 tasks
```

---

## 9. Remaining Work Summary

| Phase | Tasks Remaining | Description |
|-------|----------------|-------------|
| SubPhase 05.01 | 6 tasks (06-11) | ImageMagick fallback, font bundling, font validation, chunking/timing/integration tests |
| SubPhase 05.02 | 8 tasks | Crossfade transitions, audio cross-mix, duration math, subtitle interaction, tests |
| SubPhase 05.03 | 17 tasks | GlobalSettings UI, voice selector, subtitle settings, render settings, toast notifications, empty states, error boundaries, polish, keyboard shortcuts, Zustand types, constants, backend API, tests, QA |
| **Total** | **31 tasks** | — |
