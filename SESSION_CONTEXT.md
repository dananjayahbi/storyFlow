# SESSION_CONTEXT.md — Handover Document

> **Generated:** Session ending after Tasks 05.03.02 and 05.03.03  
> **Next Task:** Task 05.03.04  
> **Delete this file** after the next session picks it up.

---

## 1. Overall Progress

### Completed Phases & SubPhases
- ✅ SubPhase 05.01 — Tasks 05.01.01 through 05.01.11 (all 11 tasks)
- ✅ SubPhase 05.02 — Tasks 05.02.01 through 05.02.08 (all 8 tasks)

### SubPhase 05.03 — Final UI Polish & Testing (In Progress)
- ✅ Task 05.03.01 — Build GlobalSettingsPanel
- ✅ Task 05.03.02 — Build VoiceSelector
- ✅ Task 05.03.03 — Build SubtitleSettingsForm
- 🔲 Task 05.03.04 — **NEXT** (find in `document-series/Phase_05_The_Polish/SubPhase_05_03_Final_UI_Polish_Testing/`)

### Test Counts (all passing)
| Suite | Count | Notes |
|-------|-------|-------|
| Backend API (`api`) | 154 | All pass |
| Backend core_engine | 102 | 3 skipped (2 ImageMagick, 1 visual inspection) |
| Frontend Jest | 85 | 13 suites, all pass |

---

## 2. Technical Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Backend | Django 5.2.11 + DRF 3.16.1 | Python 3.14.0, venv at `backend/venv/` |
| Database | SQLite | Dev only, `backend/db.sqlite3` |
| Frontend | Next.js 16.1.6 | Tailwind v4, TypeScript |
| State | Zustand | Two stores: `useProjectStore`, `useSettingsStore` |
| UI | shadcn/ui | See installed components below |
| Toasts | Sonner v2.0.7 | `import { toast } from 'sonner'`, mounted in `layout.tsx` |
| Video | MoviePy 2.1.2 | Immutable API: `clip.with_effects(...)`, `clip.with_audio(...)` |
| TTS | Kokoro ONNX | Model at `models/kokoro-v0_19.onnx`, voices in `models/voices/` |

### Installed shadcn/ui Components
`slider`, `skeleton`, `button`, `input`, `separator`, `badge`, `progress`, `tooltip`, `card`, `dialog`, `alert-dialog`, `dropdown-menu`, `scroll-area`, `textarea`, `sonner`, **`select`** (added in Task 05.03.02)

**NOT installed:** `label`, `checkbox`, `switch`, `tabs`, `popover`, `command`

### Run Commands
```bash
# Backend tests
cd backend && .\venv\Scripts\python.exe manage.py test api --verbosity 1
cd backend && .\venv\Scripts\python.exe manage.py test core_engine --verbosity 1

# Frontend tests
cd frontend && npx jest --passWithNoTests

# Validation scripts: create temp .py files in root, run with `python <file>.py`, delete after
```

---

## 3. What Was Done This Session

### Task 05.03.02 — Build VoiceSelector

**New files created:**
- `frontend/components/VoiceSelector.tsx` (80 lines) — Shadcn/ui `Select` dropdown for Kokoro TTS voices
- `frontend/lib/constants.ts` (43 lines) — `Voice` interface, `AVAILABLE_VOICES` fallback list, `VALIDATION` constants
- `frontend/components/ui/select.tsx` (177 lines) — Installed via `npx shadcn@latest add select`

**Modified files:**
- `backend/api/views.py` — Added `VOICE_METADATA` dict and `available_voices_view()` (GET /api/settings/voices/)
- `backend/api/urls.py` — Added `path('settings/voices/', ...)`
- `frontend/lib/api.ts` — Added `getVoices()` function, imported `Voice` from constants
- `frontend/lib/stores.ts` — Added `availableVoices`, `isVoicesLoading`, `fetchVoices()` to `useSettingsStore`
- `frontend/components/GlobalSettingsPanel.tsx` — Replaced inline `<select>` with `<VoiceSelector />`, removed `VOICE_OPTIONS` constant

**Key design decisions:**
- Backend scans `models/voices/` for `.pt` files, falls back to `VALID_VOICE_IDS` set when none found
- Frontend falls back to hardcoded `AVAILABLE_VOICES` list when API call fails
- Warning toast on voice change: "Voice changed. Re-generate audio to hear the new voice."
- VoiceSelector has its own section label with Mic icon

### Task 05.03.03 — Build SubtitleSettingsForm

**New files created:**
- `frontend/components/SubtitleSettingsForm.tsx` (223 lines) — Font upload + color picker with validation

**Modified files:**
- `backend/api/validators.py` — Added `ALLOWED_FONT_EXTENSIONS`, `MAX_FONT_SIZE`, `HEX_COLOR_REGEX`, `validate_font_upload()`
- `backend/api/serializers.py` — Added `validate_subtitle_color()` to `GlobalSettingsSerializer`, imported `HEX_COLOR_REGEX`
- `backend/api/views.py` — Added `upload_font_view()` (POST /api/settings/font/upload/)
- `backend/api/urls.py` — Added `path('settings/font/upload/', ...)`
- `frontend/lib/constants.ts` — Added `VALIDATION` object with `ALLOWED_FONT_EXTENSIONS`, `MAX_FONT_SIZE`, `HEX_COLOR_REGEX`
- `frontend/lib/api.ts` — Added `uploadFont()` function using FormData
- `frontend/lib/stores.ts` — Added `isFontUploading`, `uploadFont()` to `useSettingsStore`
- `frontend/components/GlobalSettingsPanel.tsx` — Replaced inline subtitle section with `<SubtitleSettingsForm />`, removed `Input` and `Type` imports

**Key design decisions:**
- Font upload saves to `MEDIA_ROOT/fonts/`, updates `GlobalSettings.subtitle_font` with full path
- `parseFontName()` extracts display name from path, shows "Default (Roboto Bold)" when empty
- Client-side validation before upload: extension (.ttf/.otf) and size (10 MB max)
- Color changes debounced by 300ms, validated with HEX_COLOR_REGEX (#RGB or #RRGGBB)
- Preview box shows "Sample subtitle text" in the current color

---

## 4. Current File Inventory (Key Files)

### Backend
| File | Lines | Purpose |
|------|------:|---------|
| `backend/api/views.py` | 812 | All API views (ProjectViewSet, SegmentViewSet, settings, voices, font upload) |
| `backend/api/urls.py` | 19 | 6 custom paths + DRF router |
| `backend/api/validators.py` | 226 | Image, font, import, render validation + HEX_COLOR_REGEX |
| `backend/api/serializers.py` | 131 | 5 serializer classes (Project, Segment, GlobalSettings, ProjectDetail, ProjectImport) |
| `backend/api/models.py` | ~82 | Project, Segment, GlobalSettings models |

### Frontend
| File | Lines | Purpose |
|------|------:|---------|
| `frontend/lib/api.ts` | 216 | All API functions (22 exported) |
| `frontend/lib/stores.ts` | 713 | `useProjectStore` + `useSettingsStore` |
| `frontend/lib/types.ts` | 155 | TypeScript interfaces |
| `frontend/lib/constants.ts` | 43 | Voice list, VALIDATION constants |
| `frontend/components/GlobalSettingsPanel.tsx` | 254 | Settings sidebar panel (voice + render + subtitle sections) |
| `frontend/components/VoiceSelector.tsx` | 80 | Voice dropdown with shadcn Select |
| `frontend/components/SubtitleSettingsForm.tsx` | 223 | Font upload + color picker |
| `frontend/app/projects/[id]/page.tsx` | ~223 | Project detail page with settings sidebar |

---

## 5. API Endpoints

| Method | Path | View | Added |
|--------|------|------|-------|
| GET/PATCH | `/api/settings/` | `global_settings_view` | Task 05.03.01 |
| GET | `/api/settings/voices/` | `available_voices_view` | Task 05.03.02 |
| POST | `/api/settings/font/upload/` | `upload_font_view` | Task 05.03.03 |

---

## 6. GlobalSettings Model (Singleton)

```python
class GlobalSettings(models.Model):
    default_voice_id = models.CharField(max_length=100, default='af_bella')
    tts_speed = models.FloatField(default=1.0)
    zoom_intensity = models.FloatField(default=1.3)
    subtitle_font = models.CharField(max_length=255, blank=True, default='')
    subtitle_color = models.CharField(max_length=7, default='#FFFFFF')
    
    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj
```

**Valid voice IDs:** `af_bella`, `af_sarah`, `af_nicole`, `am_adam`, `am_michael`, `bf_emma`, `bm_george`

---

## 7. useSettingsStore Interface

```typescript
interface SettingsStore {
  globalSettings: GlobalSettings | null;
  isSettingsLoading: boolean;
  settingsError: string | null;
  fetchSettings: () => Promise<void>;
  updateSettings: (data: Partial<GlobalSettings>) => Promise<void>;
  availableVoices: Voice[];
  isVoicesLoading: boolean;
  fetchVoices: () => Promise<void>;
  isFontUploading: boolean;
  uploadFont: (file: File) => Promise<void>;
}
```

---

## 8. Important Process Notes

1. **Validation scripts:** Always create a temporary Python file in the project root, run it, then delete it. Do NOT use `python -c "..."` inline code.
2. **flow.py:** Run `python E:\My_GitHub_Repos\flow\flow.py` after every task for user review.
3. **Subagents:** Use subagents to research file contents and manage context window.
4. **TRANSITION_DURATION = 0.5:** Fixed constant in `video_renderer.py`, NOT user-configurable.
5. **MoviePy 2.1.2 API:** Immutable — use `clip.with_effects(...)`, NOT `clip.fx(...)`.

---

## 9. Next Steps

1. Find and read `Task_05_03_04_*.md` in `document-series/Phase_05_The_Polish/SubPhase_05_03_Final_UI_Polish_Testing/`
2. Implement its requirements following the established workflow
3. Run validation + all tests
4. Run flow.py for review
