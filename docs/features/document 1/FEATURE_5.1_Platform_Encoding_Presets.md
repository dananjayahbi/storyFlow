# Feature 5.1 — Platform-Specific Encoding Presets

| Field                  | Value                                                                                          |
| ---------------------- | ---------------------------------------------------------------------------------------------- |
| **Feature ID**         | 5.1                                                                                            |
| **Title**              | Platform-Specific Encoding Presets                                                             |
| **Status**             | 🟡 Planned                                                                                     |
| **Priority**           | High                                                                                           |
| **Complexity**         | Medium-High                                                                                    |
| **Estimated Effort**   | 3–4 days                                                                                       |
| **Dependencies**       | None (independent of other pending features)                                                   |
| **Output Files (NEW)** | `backend/core_engine/encoding_presets.py`, frontend preset selector component                  |
| **Files Modified**     | `fast_compositor.py`, `video_renderer.py`, `models.py`, `serializers.py`, `views.py`, frontend |

---

## 1. Document Overview

### 1.1 Problem Statement

The current StoryFlow rendering pipeline uses **hardcoded encoding parameters** throughout:

- `FFmpegFrameWriter` in `backend/core_engine/fast_compositor.py` (L365–480) always encodes
  with **CRF 23**, a fixed **8 Mbps** bitrate cap, and generic H.264 settings.
- `fast_render_segments()` (L487) passes `bitrate="8M"` unconditionally.
- `video_renderer.py` `render_project()` (L1008–1063) calls `fast_render_segments()` with no
  encoding preset concept — only resolution, FPS, and the hardcoded bitrate.
- The `Project` model has `resolution_width`, `resolution_height`, and `framerate` but **no**
  `encoding_preset` field.
- The frontend `RenderSettingsForm.tsx` offers 10 resolution presets plus an FPS selector, but
  has **no** platform encoding preset selector.

This means every rendered video — whether targeted at YouTube, TikTok, Instagram, or
Twitter/X — receives identical encoding quality. Users who need platform-optimized output
must manually re-encode outside StoryFlow, defeating the purpose of a one-click render tool.

### 1.2 Proposed Solution

Introduce a **platform encoding preset system** that bundles resolution, aspect ratio, CRF,
bitrate, audio bitrate, max duration, and codec flags into named presets. When a user selects
"YouTube" or "TikTok" the system auto-configures all encoding parameters. A "Custom" preset
preserves the current manual-configuration workflow.

### 1.3 Scope

| In Scope                                                       | Out of Scope                                      |
| -------------------------------------------------------------- | ------------------------------------------------- |
| Backend preset definitions module                              | Auto-upload / publishing to platforms              |
| `FFmpegFrameWriter` refactor to accept preset dicts            | Multi-output (rendering to N platforms in one job) |
| Duration warning when content exceeds platform max             | AV1 / VP9 codec support (future feature)          |
| `Project` model `encoding_preset` field + migration            | Per-segment encoding overrides                    |
| `GlobalSettings` model `encoding_preset` field + migration     | HDR / 10-bit color depth                          |
| Serializer + API changes                                       | Audio-only export                                 |
| Frontend preset selector that auto-sets resolution + encoding  |                                                   |
| Frontend duration warning toast                                |                                                   |

### 1.4 Key Files Reference

| File                                             | Role                                    | Current State                                    |
| ------------------------------------------------ | --------------------------------------- | ------------------------------------------------ |
| `backend/core_engine/fast_compositor.py`         | FFmpeg frame writer + fast render       | Hardcoded CRF 23, 8M bitrate, generic H.264     |
| `backend/core_engine/video_renderer.py`          | Orchestrates full render pipeline       | No preset awareness, passes hardcoded bitrate    |
| `backend/api/models.py`                          | Django data models                      | No `encoding_preset` field                       |
| `backend/api/serializers.py`                     | DRF serializers                         | No preset serialization                          |
| `backend/api/views.py`                           | API endpoints                           | No preset endpoint                               |
| `frontend/components/RenderSettingsForm.tsx`      | Resolution + zoom UI                    | No platform preset selector                      |
| `frontend/lib/constants.ts`                      | `VALIDATION.RESOLUTION_PRESETS`         | Resolution-only presets, no encoding metadata     |
| `frontend/types/settings.ts`                     | TypeScript settings interfaces          | No `encoding_preset` type                        |

---

## 2. Flow Diagram

### 2.1 User Interaction Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (Next.js)                               │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  RenderSettingsForm.tsx                                         │    │
│  │                                                                 │    │
│  │  ┌──────────────────────┐    ┌──────────────────────────────┐  │    │
│  │  │ Platform Preset      │───▶│ Auto-fill:                   │  │    │
│  │  │ Selector (NEW)       │    │  • Resolution                │  │    │
│  │  │                      │    │  • FPS                       │  │    │
│  │  │  ○ YouTube           │    │  • CRF / Bitrate (display)  │  │    │
│  │  │  ○ TikTok            │    │  • Max Duration warning      │  │    │
│  │  │  ○ Instagram Reel    │    └──────────────────────────────┘  │    │
│  │  │  ○ Facebook          │                                      │    │
│  │  │  ○ Twitter/X         │    ┌──────────────────────────────┐  │    │
│  │  │  ○ LinkedIn          │    │ Resolution Selector          │  │    │
│  │  │  ○ Custom            │    │ (existing, read-only when    │  │    │
│  │  └──────────────────────┘    │  platform preset selected)   │  │    │
│  │                               └──────────────────────────────┘  │    │
│  └────────────────────────────────┬────────────────────────────────┘    │
│                                   │                                     │
│                          PATCH /api/projects/:id/                       │
│                   { encoding_preset: "youtube" }                        │
│                                   │                                     │
└───────────────────────────────────┼─────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        BACKEND (Django)                                  │
│                                                                         │
│  ┌──────────────┐     ┌───────────────────┐     ┌───────────────────┐  │
│  │ API View     │────▶│ Serializer        │────▶│ Project Model     │  │
│  │ (views.py)   │     │ (serializers.py)  │     │ encoding_preset = │  │
│  │              │     │ validate preset    │     │ "youtube"         │  │
│  └──────────────┘     └───────────────────┘     └───────────────────┘  │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ Render Pipeline (on POST /api/projects/:id/render/)             │   │
│  │                                                                  │   │
│  │  video_renderer.py :: render_project()                          │   │
│  │     │                                                            │   │
│  │     ▼                                                            │   │
│  │  encoding_presets.py :: get_preset("youtube")                   │   │
│  │     │                                                            │   │
│  │     ├── Returns EncodingPreset dict:                            │   │
│  │     │   { crf: 18, bitrate: "16M", maxrate: "20M",             │   │
│  │     │     profile: "high", audio_bitrate: "192k",              │   │
│  │     │     faststart: True, max_duration: None }                 │   │
│  │     │                                                            │   │
│  │     ▼                                                            │   │
│  │  ┌─ Duration check ─────────────────────────────┐               │   │
│  │  │ if max_duration and estimated > max_duration: │               │   │
│  │  │   log warning (render proceeds anyway)        │               │   │
│  │  └───────────────────────────────────────────────┘               │   │
│  │     │                                                            │   │
│  │     ▼                                                            │   │
│  │  fast_compositor.py :: FFmpegFrameWriter(preset=preset_dict)    │   │
│  │     │                                                            │   │
│  │     ▼                                                            │   │
│  │  _build_command() uses preset values for:                       │   │
│  │     -crf, -b:v, -maxrate, -bufsize, -profile:v,                │   │
│  │     -b:a, -movflags                                             │   │
│  │                                                                  │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Data Flow Sequence

```
 User          Frontend              API                  Renderer           FFmpeg
  │                │                   │                      │                 │
  │ Select preset  │                   │                      │                 │
  │───────────────▶│                   │                      │                 │
  │                │ PATCH project     │                      │                 │
  │                │ { encoding_preset │                      │                 │
  │                │   resolution_w/h }│                      │                 │
  │                │──────────────────▶│                      │                 │
  │                │                   │ validate + save      │                 │
  │                │                   │─────┐                │                 │
  │                │                   │◀────┘                │                 │
  │                │        200 OK     │                      │                 │
  │                │◀──────────────────│                      │                 │
  │                │                   │                      │                 │
  │ Click Render   │                   │                      │                 │
  │───────────────▶│                   │                      │                 │
  │                │ POST …/render/    │                      │                 │
  │                │──────────────────▶│                      │                 │
  │                │                   │ load preset          │                 │
  │                │                   │─────────────────────▶│                 │
  │                │                   │                      │ resolve_preset()│
  │                │                   │                      │─────┐           │
  │                │                   │                      │◀────┘           │
  │                │                   │                      │ duration check  │
  │                │                   │                      │─────┐           │
  │                │                   │                      │◀────┘           │
  │                │                   │                      │ build FFmpeg cmd│
  │                │                   │                      │────────────────▶│
  │                │                   │                      │                 │ encode
  │                │                   │                      │                 │─────┐
  │                │                   │                      │                 │◀────┘
  │                │                   │                      │◀────────────────│
  │                │◀─────────────────────────────────────────│                 │
  │◀───────────────│                   │                      │                 │
  │  Render done   │                   │                      │                 │
```

### 2.3 Module Dependency Graph

```
  encoding_presets.py (NEW)
        │
        ├──────────────────────────────┐
        │                              │
        ▼                              ▼
  video_renderer.py              fast_compositor.py
  (reads preset by name)         (FFmpegFrameWriter uses
                                  preset dict for encoding)
        │
        ▼
  models.py ◀── serializers.py ◀── views.py
  (stores encoding_preset          (API layer)
   field on Project +
   GlobalSettings)
```

---

## 3. Step-by-Step Instructions

### Step 1 — Create `backend/core_engine/encoding_presets.py`

Create a new module that defines all platform encoding presets as a Python dictionary
registry. This is the **single source of truth** for encoding parameters.

**File:** `backend/core_engine/encoding_presets.py` (NEW)

```python
"""Platform-specific encoding presets for FFmpeg video output.

Each preset is a dict with the following keys:
    name          – Human-readable display name
    slug          – URL-safe identifier (used in DB + API)
    width         – Output width in pixels
    height        – Output height in pixels
    aspect        – Aspect ratio label (e.g. "16:9")
    fps           – Frames per second
    crf           – Constant Rate Factor (lower = better quality)
    bitrate       – Target video bitrate (FFmpeg notation, e.g. "16M")
    maxrate       – Maximum video bitrate cap
    bufsize       – VBV buffer size (typically 1.5–2× maxrate)
    audio_bitrate – AAC audio bitrate
    profile       – H.264 profile ("high", "main", "baseline")
    faststart     – Whether to add -movflags +faststart
    max_duration  – Maximum video duration in seconds, or None
    category      – Grouping key for frontend UI
    description   – Short description for tooltip / help text

Usage:
    from core_engine.encoding_presets import get_preset, PRESETS, PRESET_CHOICES

    preset = get_preset("youtube")
    crf = preset["crf"]
"""

from typing import Dict, List, Optional, Tuple

# ── Preset Definitions ─────────────────────────────────────────────

PRESETS: Dict[str, dict] = {
    "youtube": {
        "name": "YouTube (1080p)",
        "slug": "youtube",
        "width": 1920,
        "height": 1080,
        "aspect": "16:9",
        "fps": 30,
        "crf": 18,
        "bitrate": "16M",
        "maxrate": "20M",
        "bufsize": "30M",
        "audio_bitrate": "192k",
        "profile": "high",
        "faststart": True,
        "max_duration": None,
        "category": "landscape",
        "description": "Optimal for YouTube standard HD uploads.",
    },
    "youtube_4k": {
        "name": "YouTube (4K)",
        "slug": "youtube_4k",
        "width": 3840,
        "height": 2160,
        "aspect": "16:9",
        "fps": 30,
        "crf": 18,
        "bitrate": "35M",
        "maxrate": "45M",
        "bufsize": "60M",
        "audio_bitrate": "256k",
        "profile": "high",
        "faststart": True,
        "max_duration": None,
        "category": "landscape",
        "description": "Optimal for YouTube 4K UHD uploads.",
    },
    "youtube_shorts": {
        "name": "YouTube Shorts",
        "slug": "youtube_shorts",
        "width": 1080,
        "height": 1920,
        "aspect": "9:16",
        "fps": 30,
        "crf": 20,
        "bitrate": "10M",
        "maxrate": "12M",
        "bufsize": "18M",
        "audio_bitrate": "192k",
        "profile": "high",
        "faststart": True,
        "max_duration": 60,
        "category": "portrait",
        "description": "YouTube Shorts — max 60 seconds, 9:16 vertical.",
    },
    "tiktok": {
        "name": "TikTok",
        "slug": "tiktok",
        "width": 1080,
        "height": 1920,
        "aspect": "9:16",
        "fps": 30,
        "crf": 20,
        "bitrate": "8M",
        "maxrate": "10M",
        "bufsize": "15M",
        "audio_bitrate": "192k",
        "profile": "high",
        "faststart": True,
        "max_duration": 600,
        "category": "portrait",
        "description": "TikTok — max 10 minutes, 9:16 vertical.",
    },
    "instagram_reel": {
        "name": "Instagram Reel",
        "slug": "instagram_reel",
        "width": 1080,
        "height": 1920,
        "aspect": "9:16",
        "fps": 30,
        "crf": 20,
        "bitrate": "8M",
        "maxrate": "10M",
        "bufsize": "15M",
        "audio_bitrate": "192k",
        "profile": "high",
        "faststart": True,
        "max_duration": 90,
        "category": "portrait",
        "description": "Instagram Reel — max 90 seconds, 9:16 vertical.",
    },
    "instagram_post": {
        "name": "Instagram Post",
        "slug": "instagram_post",
        "width": 1080,
        "height": 1080,
        "aspect": "1:1",
        "fps": 30,
        "crf": 21,
        "bitrate": "6M",
        "maxrate": "8M",
        "bufsize": "12M",
        "audio_bitrate": "192k",
        "profile": "high",
        "faststart": True,
        "max_duration": 60,
        "category": "square",
        "description": "Instagram square video post — max 60 seconds.",
    },
    "facebook": {
        "name": "Facebook",
        "slug": "facebook",
        "width": 1920,
        "height": 1080,
        "aspect": "16:9",
        "fps": 30,
        "crf": 21,
        "bitrate": "12M",
        "maxrate": "16M",
        "bufsize": "24M",
        "audio_bitrate": "192k",
        "profile": "high",
        "faststart": True,
        "max_duration": None,
        "category": "landscape",
        "description": "Facebook video — optimized for feed playback.",
    },
    "twitter": {
        "name": "Twitter / X",
        "slug": "twitter",
        "width": 1920,
        "height": 1080,
        "aspect": "16:9",
        "fps": 30,
        "crf": 22,
        "bitrate": "5M",
        "maxrate": "6.4M",
        "bufsize": "10M",
        "audio_bitrate": "128k",
        "profile": "high",
        "faststart": True,
        "max_duration": 140,
        "category": "landscape",
        "description": "Twitter/X video — max 2 min 20 sec.",
    },
    "linkedin": {
        "name": "LinkedIn",
        "slug": "linkedin",
        "width": 1920,
        "height": 1080,
        "aspect": "16:9",
        "fps": 30,
        "crf": 21,
        "bitrate": "10M",
        "maxrate": "12M",
        "bufsize": "18M",
        "audio_bitrate": "192k",
        "profile": "high",
        "faststart": True,
        "max_duration": 600,
        "category": "landscape",
        "description": "LinkedIn video — max 10 minutes.",
    },
    "custom": {
        "name": "Custom",
        "slug": "custom",
        "width": None,       # Use project resolution_width
        "height": None,      # Use project resolution_height
        "aspect": None,      # Derived from resolution
        "fps": None,         # Use project framerate
        "crf": 23,
        "bitrate": "8M",
        "maxrate": "12M",
        "bufsize": "16M",
        "audio_bitrate": "192k",
        "profile": "high",
        "faststart": True,
        "max_duration": None,
        "category": "custom",
        "description": "Manual settings — uses project resolution and default encoding.",
    },
}

# ── Django model choices tuple ─────────────────────────────────────

PRESET_CHOICES: List[Tuple[str, str]] = [
    (slug, preset["name"]) for slug, preset in PRESETS.items()
]

# ── NVENC overrides ────────────────────────────────────────────────

# When NVENC is used, CRF is replaced by -cq (constant quality) and
# the bitrate / maxrate / bufsize values are still honored.

NVENC_CQ_MAPPING: Dict[int, int] = {
    18: 20,   # YouTube quality → NVENC CQ 20
    20: 22,   # TikTok / Reels quality
    21: 23,   # Facebook / LinkedIn quality
    22: 24,   # Twitter quality
    23: 25,   # Custom / default
}

# ── Public API ─────────────────────────────────────────────────────


def get_preset(slug: str) -> dict:
    """Return a **copy** of the preset dict for the given slug.

    Falls back to ``"custom"`` if the slug is not recognised.
    """
    preset = PRESETS.get(slug, PRESETS["custom"])
    return dict(preset)  # shallow copy to prevent mutation


def get_preset_names() -> List[dict]:
    """Return a list of ``{slug, name, category, description}`` for the
    frontend preset selector dropdown."""
    return [
        {
            "slug": p["slug"],
            "name": p["name"],
            "category": p["category"],
            "description": p["description"],
        }
        for p in PRESETS.values()
    ]


def get_nvenc_cq(crf: int) -> int:
    """Map a CRF value to a roughly-equivalent NVENC constant-quality value."""
    return NVENC_CQ_MAPPING.get(crf, crf + 2)


def resolve_preset_for_project(project) -> dict:
    """Given a Project model instance, return the fully resolved encoding dict.

    For ``"custom"`` presets, ``width``/``height``/``fps`` are filled from the
    project's own resolution and framerate fields.  For named presets the
    preset values override the project fields.
    """
    slug = getattr(project, "encoding_preset", "custom") or "custom"
    preset = get_preset(slug)

    if preset["width"] is None:
        preset["width"] = project.resolution_width
    if preset["height"] is None:
        preset["height"] = project.resolution_height
    if preset["fps"] is None:
        preset["fps"] = project.framerate

    return preset
```

> **Why a dict rather than a dataclass?** The preset is passed directly into
> `FFmpegFrameWriter` and later serialised to JSON for the API. Dicts keep
> things simple and avoid serialisation boilerplate at this stage.

---

### Step 2 — Add `encoding_preset` Field to Django Models

#### 2a. `Project` model — `backend/api/models.py`

Add the field **after** the existing `framerate` field (around line 44):

```python
from core_engine.encoding_presets import PRESET_CHOICES

class Project(models.Model):
    # ... existing fields ...
    framerate = models.IntegerField(default=30)
    encoding_preset = models.CharField(
        max_length=30,
        choices=PRESET_CHOICES,
        default='custom',
        help_text='Platform encoding preset slug (e.g. "youtube", "tiktok").',
    )
    output_path = models.CharField(max_length=500, blank=True, null=True)
    # ... rest of fields ...
```

#### 2b. `GlobalSettings` model — `backend/api/models.py`

Add the field in the "Render parameters" section (after `render_fps`):

```python
    # ── Render parameters ──
    render_width = models.PositiveIntegerField(default=1920)
    render_height = models.PositiveIntegerField(default=1080)
    render_fps = models.PositiveIntegerField(default=30)
    encoding_preset = models.CharField(
        max_length=30,
        choices=PRESET_CHOICES,
        default='custom',
        help_text='Default platform encoding preset for new projects.',
    )
```

#### 2c. Generate and Apply Migration

```bash
cd backend
python manage.py makemigrations api --name add_encoding_preset
python manage.py migrate
```

Expected migration operations:
- `AddField` on `project`, field `encoding_preset`, default `'custom'`
- `AddField` on `globalsettings`, field `encoding_preset`, default `'custom'`

---

### Step 3 — Update Serializers (`backend/api/serializers.py`)

#### 3a. `ProjectSerializer` — Add `encoding_preset` to list fields

In `ProjectSerializer.Meta.fields` (around line 44), add `'encoding_preset'`:

```python
class ProjectSerializer(serializers.ModelSerializer):
    segment_count = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            'id', 'title', 'created_at', 'updated_at',
            'status', 'resolution_width', 'resolution_height',
            'framerate', 'encoding_preset', 'segment_count',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'status']
```

#### 3b. `ProjectDetailSerializer` — Add `encoding_preset` + validation

In `ProjectDetailSerializer.Meta.fields` (around line 246), add `'encoding_preset'`:

```python
        fields = [
            'id', 'title', 'created_at', 'updated_at',
            'status', 'resolution_width', 'resolution_height',
            'framerate', 'encoding_preset', 'output_path', 'segments',
            # ... rest of per-project settings ...
        ]
```

Add a field-level validator:

```python
    def validate_encoding_preset(self, value):
        from core_engine.encoding_presets import PRESETS
        if value not in PRESETS:
            raise serializers.ValidationError(
                f'Unknown encoding preset "{value}". '
                f'Valid options: {", ".join(sorted(PRESETS.keys()))}.'
            )
        return value
```

#### 3c. `GlobalSettingsSerializer` — Add `encoding_preset`

In `GlobalSettingsSerializer.Meta.fields`, add `'encoding_preset'` after `'render_fps'`:

```python
        fields = [
            'default_voice_id', 'tts_speed',
            'subtitle_font_family', 'subtitle_font_size',
            'subtitle_font_color', 'subtitle_position',
            'subtitle_y_position',
            'subtitle_font', 'subtitle_color',
            'render_width', 'render_height', 'render_fps',
            'encoding_preset',
            # ... rest ...
        ]
```

Add the same validation:

```python
    def validate_encoding_preset(self, value):
        from core_engine.encoding_presets import PRESETS
        if value not in PRESETS:
            raise serializers.ValidationError(
                f'Unknown encoding preset "{value}". '
                f'Valid options: {", ".join(sorted(PRESETS.keys()))}.'
            )
        return value
```

---

### Step 4 — Add API Endpoint for Preset Listing (`backend/api/views.py`)

Add a lightweight read-only endpoint so the frontend can fetch available presets
dynamically (avoids hardcoding the list in two places):

```python
@api_view(['GET'])
def encoding_presets_list(request):
    """Return the list of available encoding presets with metadata."""
    from core_engine.encoding_presets import PRESETS
    data = []
    for slug, p in PRESETS.items():
        data.append({
            "slug": p["slug"],
            "name": p["name"],
            "width": p["width"],
            "height": p["height"],
            "aspect": p["aspect"],
            "fps": p["fps"],
            "crf": p["crf"],
            "bitrate": p["bitrate"],
            "maxrate": p["maxrate"],
            "audio_bitrate": p["audio_bitrate"],
            "max_duration": p["max_duration"],
            "category": p["category"],
            "description": p["description"],
        })
    return Response(data)
```

Register in `backend/api/urls.py`:

```python
from .views import encoding_presets_list

urlpatterns = [
    # ... existing patterns ...
    path('encoding-presets/', encoding_presets_list, name='encoding-presets-list'),
]
```

---

### Step 5 — Refactor `FFmpegFrameWriter` (`backend/core_engine/fast_compositor.py`)

This is the **core encoding change**. The writer must accept a `preset` dict (or fall back to
legacy defaults) and use it to build the FFmpeg command.

#### 5a. Update `__init__` signature

```python
class FFmpegFrameWriter:
    def __init__(
        self,
        output_path: str,
        width: int,
        height: int,
        fps: int,
        audio_path: Optional[str] = None,
        use_nvenc: bool = False,
        bitrate: str = "8M",
        preset: Optional[dict] = None,   # ← NEW
    ):
        self.output_path = output_path
        self.width = width
        self.height = height
        self.fps = fps
        self.audio_path = audio_path
        self.use_nvenc = use_nvenc
        self.bitrate = bitrate
        self.preset = preset or {}
        self._proc: Optional[subprocess.Popen] = None
```

#### 5b. Refactor `_build_command()` to use preset values

```python
    def _build_command(self) -> List[str]:
        """Build the FFmpeg command line using preset values when available."""
        p = self.preset  # shorthand

        # Resolve encoding parameters from preset or legacy defaults
        crf       = str(p.get("crf", 23))
        bitrate   = p.get("bitrate", self.bitrate)
        maxrate   = p.get("maxrate", "12M")
        bufsize   = p.get("bufsize", "16M")
        profile   = p.get("profile", "high")
        a_bitrate = p.get("audio_bitrate", "192k")
        faststart = p.get("faststart", True)

        cmd = [
            "ffmpeg", "-y",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-pix_fmt", "rgb24",
            "-s", f"{self.width}x{self.height}",
            "-r", str(self.fps),
            "-i", "pipe:0",
        ]

        # Audio input
        if self.audio_path and os.path.isfile(self.audio_path):
            cmd.extend(["-i", self.audio_path])

        # Video encoding
        if self.use_nvenc:
            from core_engine.encoding_presets import get_nvenc_cq
            nvenc_cq = str(get_nvenc_cq(int(crf)))
            cmd.extend([
                "-c:v", "h264_nvenc",
                "-preset", "p4",
                "-tune", "hq",
                "-rc", "vbr",
                "-cq", nvenc_cq,
                "-b:v", bitrate,
                "-maxrate", maxrate,
                "-bufsize", bufsize,
                "-profile:v", profile,
            ])
        else:
            cmd.extend([
                "-c:v", "libx264",
                "-preset", "fast",
                "-tune", "film",
                "-crf", crf,
                "-b:v", bitrate,
                "-maxrate", maxrate,
                "-bufsize", bufsize,
                "-profile:v", profile,
            ])

        # Audio encoding
        if self.audio_path and os.path.isfile(self.audio_path):
            cmd.extend(["-c:a", "aac", "-b:a", a_bitrate])

        # Output flags
        cmd.extend(["-pix_fmt", "yuv420p"])
        if faststart:
            cmd.extend(["-movflags", "+faststart"])
        cmd.append(self.output_path)

        return cmd
```

**Key difference from current code:**
- CRF is now variable per preset (18–23) instead of hardcoded 23.
- Bitrate, maxrate, bufsize, profile, and audio bitrate are all preset-driven.
- NVENC CQ value maps from the preset CRF via `get_nvenc_cq()`.
- `-b:v` and `-maxrate` are added for the libx264 path (currently missing).
- `-movflags +faststart` is conditional on the preset `faststart` flag.

#### 5c. Update `fast_render_segments()` signature

Add the `preset` parameter and pass it to `FFmpegFrameWriter`:

```python
def fast_render_segments(
    segment_data: List[dict],
    output_path: str,
    resolution: Tuple[int, int],
    fps: int,
    zoom_intensity: float,
    subtitle_settings: dict,
    logo_settings: Optional[dict],
    audio_path: str,
    use_nvenc: bool = False,
    on_progress: Optional[Callable[[int, int, str], None]] = None,
    crossfade_duration: float = 0.5,
    inter_segment_silence: float = 0.3,
    encoding_preset: Optional[dict] = None,   # ← NEW
) -> dict:
```

Then when creating the writer (currently around L640):

```python
    writer = FFmpegFrameWriter(
        output_path, width, height, fps, audio_path, use_nvenc,
        bitrate=encoding_preset.get("bitrate", "8M") if encoding_preset else "8M",
        preset=encoding_preset,
    )
```

---

### Step 6 — Update `video_renderer.py` to Pass Encoding Preset

In `render_project()` (around L1008), after reading project settings and before calling
`fast_render_segments()`:

#### 6a. Resolve the encoding preset

```python
    from core_engine.encoding_presets import resolve_preset_for_project

    encoding_preset = resolve_preset_for_project(project)
    logger.info(
        "Encoding preset: %s (CRF %s, bitrate %s, maxrate %s)",
        encoding_preset["slug"],
        encoding_preset["crf"],
        encoding_preset["bitrate"],
        encoding_preset["maxrate"],
    )
```

#### 6b. Add duration warning

```python
    # Duration check against platform limit
    max_duration = encoding_preset.get("max_duration")
    if max_duration:
        estimated_duration = sum(
            seg["audio_duration"] + inter_segment_silence
            for seg in segment_data_list
        )
        if estimated_duration > max_duration:
            logger.warning(
                "⚠ Estimated video duration (%.1fs) exceeds %s max (%ds). "
                "The platform may reject or truncate the upload.",
                estimated_duration,
                encoding_preset["name"],
                max_duration,
            )
            # Store warning on project for frontend to display
            # (render proceeds — user made a conscious choice)
```

#### 6c. Pass preset to `fast_render_segments()`

```python
    render_stats = fast_render_segments(
        segment_data=segment_data_list,
        output_path=output_path,
        resolution=(res_width, res_height),
        fps=fps,
        zoom_intensity=zoom_intensity,
        subtitle_settings=sub_settings,
        logo_settings=logo_settings_dict,
        audio_path=temp_audio_path,
        use_nvenc=use_nvenc,
        on_progress=on_progress,
        crossfade_duration=TRANSITION_DURATION,
        inter_segment_silence=inter_segment_silence,
        encoding_preset=encoding_preset,       # ← NEW
    )
```

---

### Step 7 — Frontend: Add TypeScript Types

#### 7a. Create `frontend/types/encoding-preset.ts` (NEW)

```typescript
/**
 * Encoding preset as returned by GET /api/encoding-presets/.
 */
export interface EncodingPreset {
  slug: string;
  name: string;
  width: number | null;
  height: number | null;
  aspect: string | null;
  fps: number | null;
  crf: number;
  bitrate: string;
  maxrate: string;
  audio_bitrate: string;
  max_duration: number | null;
  category: string;
  description: string;
}
```

#### 7b. Update `frontend/types/settings.ts`

Add `encoding_preset` to the `GlobalSettings` interface:

```typescript
export interface GlobalSettings {
  // ... existing fields ...
  /** Active encoding preset slug (e.g. "youtube", "tiktok", "custom"). */
  encoding_preset: string;
}
```

---

### Step 8 — Frontend: Add API Function

In `frontend/api/` (wherever project API functions live), add:

```typescript
/**
 * Fetch available encoding presets from the backend.
 */
export async function getEncodingPresets(): Promise<EncodingPreset[]> {
  const res = await fetch(`${API_BASE}/encoding-presets/`);
  if (!res.ok) throw new Error('Failed to fetch encoding presets');
  return res.json();
}
```

---

### Step 9 — Frontend: Add Encoding Preset Constants (Fallback)

In `frontend/lib/constants.ts`, add a fallback preset list (used when the API is
unreachable) and the `ENCODING_PRESETS` constant:

```typescript
// ── Encoding Preset type ──────────────────────────────────────────

export interface EncodingPresetOption {
  slug: string;
  name: string;
  category: 'landscape' | 'portrait' | 'square' | 'custom';
  description: string;
  icon: string;    // lucide icon name for UI
}

export const ENCODING_PRESETS: readonly EncodingPresetOption[] = [
  { slug: 'youtube',         name: 'YouTube (1080p)',   category: 'landscape', description: 'CRF 18, 20Mbps cap, -faststart',    icon: 'Youtube' },
  { slug: 'youtube_4k',      name: 'YouTube (4K)',      category: 'landscape', description: 'CRF 18, 45Mbps cap, 4K UHD',        icon: 'Youtube' },
  { slug: 'youtube_shorts',  name: 'YouTube Shorts',    category: 'portrait',  description: 'CRF 20, 12Mbps cap, max 60s',       icon: 'Youtube' },
  { slug: 'tiktok',          name: 'TikTok',            category: 'portrait',  description: 'CRF 20, 10Mbps cap, max 10min',     icon: 'Music' },
  { slug: 'instagram_reel',  name: 'Instagram Reel',    category: 'portrait',  description: 'CRF 20, 10Mbps cap, max 90s',       icon: 'Instagram' },
  { slug: 'instagram_post',  name: 'Instagram Post',    category: 'square',    description: 'CRF 21, 8Mbps cap, max 60s',        icon: 'Instagram' },
  { slug: 'facebook',        name: 'Facebook',          category: 'landscape', description: 'CRF 21, 16Mbps cap, -faststart',    icon: 'Facebook' },
  { slug: 'twitter',         name: 'Twitter / X',       category: 'landscape', description: 'CRF 22, 6.4Mbps cap, max 2:20',     icon: 'Twitter' },
  { slug: 'linkedin',        name: 'LinkedIn',          category: 'landscape', description: 'CRF 21, 12Mbps cap, max 10min',     icon: 'Linkedin' },
  { slug: 'custom',          name: 'Custom',            category: 'custom',    description: 'Manual resolution + default encoding', icon: 'Settings' },
] as const;
```

---

### Step 10 — Frontend: Build Preset Selector Component

Create `frontend/components/EncodingPresetSelector.tsx` (NEW):

```tsx
'use client';

import { useCallback, useMemo } from 'react';
import {
  Select, SelectContent, SelectGroup, SelectItem,
  SelectLabel, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import {
  Youtube, Music, Instagram, Facebook, Twitter,
  Linkedin, Settings, Monitor, Smartphone, Square,
} from 'lucide-react';
import { ENCODING_PRESETS, type EncodingPresetOption } from '@/lib/constants';

interface EncodingPresetSelectorProps {
  value: string;
  onChange: (slug: string) => void;
}

const iconMap: Record<string, React.ElementType> = {
  Youtube, Music, Instagram, Facebook, Twitter, Linkedin, Settings,
};

const categoryIcons: Record<string, React.ElementType> = {
  landscape: Monitor,
  portrait: Smartphone,
  square: Square,
  custom: Settings,
};

export function EncodingPresetSelector({ value, onChange }: EncodingPresetSelectorProps) {
  const grouped = useMemo(() => {
    const groups: Record<string, EncodingPresetOption[]> = {};
    for (const p of ENCODING_PRESETS) {
      if (!groups[p.category]) groups[p.category] = [];
      groups[p.category].push(p);
    }
    return groups;
  }, []);

  const current = ENCODING_PRESETS.find((p) => p.slug === value);

  return (
    <div className="space-y-1.5">
      <label className="text-xs text-muted-foreground font-medium">
        Platform Preset
      </label>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger className="h-9 text-sm">
          <SelectValue placeholder="Select platform">
            {current ? current.name : 'Custom'}
          </SelectValue>
        </SelectTrigger>
        <SelectContent>
          {(['landscape', 'portrait', 'square', 'custom'] as const).map((cat) => {
            const presets = grouped[cat];
            if (!presets?.length) return null;
            const CatIcon = categoryIcons[cat] ?? Settings;
            return (
              <SelectGroup key={cat}>
                <SelectLabel className="flex items-center gap-1.5 text-xs">
                  <CatIcon className="h-3 w-3" />
                  {cat.charAt(0).toUpperCase() + cat.slice(1)}
                </SelectLabel>
                {presets.map((p) => {
                  const Icon = iconMap[p.icon] ?? Settings;
                  return (
                    <SelectItem key={p.slug} value={p.slug}>
                      <span className="flex items-center gap-2">
                        <Icon className="h-3.5 w-3.5 text-muted-foreground" />
                        <span>{p.name}</span>
                        <span className="text-muted-foreground text-xs ml-auto">
                          {p.description}
                        </span>
                      </span>
                    </SelectItem>
                  );
                })}
              </SelectGroup>
            );
          })}
        </SelectContent>
      </Select>
      <p className="text-[10px] text-muted-foreground">
        Selects optimal CRF, bitrate, and aspect ratio for the target platform
      </p>
    </div>
  );
}
```

---

### Step 11 — Frontend: Integrate Selector into `RenderSettingsForm.tsx`

#### 11a. Import and wire up

At the top of `RenderSettingsForm.tsx`:

```tsx
import { EncodingPresetSelector } from '@/components/EncodingPresetSelector';
import { ENCODING_PRESETS } from '@/lib/constants';
```

Add `encodingPreset` to props interface:

```tsx
interface RenderSettingsFormProps {
  zoomIntensity: number;
  renderWidth: number;
  renderHeight: number;
  renderFps: number;
  encodingPreset: string;    // ← NEW
  onChange: (data: {
    zoom_intensity?: number;
    render_width?: number;
    render_height?: number;
    render_fps?: number;
    encoding_preset?: string;   // ← NEW
  }) => Promise<void>;
}
```

#### 11b. Add handler and render the selector

Inside the component body:

```tsx
  // ── Encoding preset handler ──
  const handlePresetChange = useCallback(
    (slug: string) => {
      // Find the matching backend preset to auto-apply resolution
      const matched = ENCODING_PRESETS.find((p) => p.slug === slug);
      if (matched && matched.category !== 'custom') {
        // Auto-update resolution when switching to a named preset
        // The backend will supply width/height from encoding_presets.py,
        // but we optimistically set it here for instant UI feedback
        onChange({ encoding_preset: slug });
      } else {
        onChange({ encoding_preset: slug });
      }
    },
    [onChange],
  );
```

Render the `EncodingPresetSelector` **above** the Resolution Selector in the JSX:

```tsx
      {/* ── Platform Preset Selector ── */}
      <EncodingPresetSelector
        value={encodingPreset}
        onChange={handlePresetChange}
      />

      {/* ── Resolution Selector (existing) ── */}
```

#### 11c. Conditionally disable resolution selector

When a non-custom preset is selected, make the resolution selector read-only:

```tsx
  const isPresetLocked = encodingPreset !== 'custom';

  // ... in JSX:
  <Select
    value={currentKey}
    onValueChange={handleResolutionChange}
    disabled={isPresetLocked}
  >
```

---

### Step 12 — Frontend: Wire Into `GlobalSettingsPanel.tsx`

In the component that composes `RenderSettingsForm`, pass the new prop:

```tsx
<RenderSettingsForm
  zoomIntensity={settings.zoom_intensity}
  renderWidth={settings.render_width ?? settings.resolution_width}
  renderHeight={settings.render_height ?? settings.resolution_height}
  renderFps={settings.render_fps ?? settings.framerate}
  encodingPreset={settings.encoding_preset ?? 'custom'}    // ← NEW
  onChange={updateSettings}
/>
```

---

### Step 13 — Auto-Apply Resolution on Preset Change (Backend)

When the API receives a `PATCH` with `encoding_preset` set to a named platform, the
serializer should **auto-update** the project's resolution and framerate to match:

In `ProjectDetailSerializer.validate()` or `update()`:

```python
    def update(self, instance, validated_data):
        preset_slug = validated_data.get('encoding_preset')
        if preset_slug and preset_slug != 'custom':
            from core_engine.encoding_presets import get_preset
            preset = get_preset(preset_slug)
            if preset.get('width'):
                validated_data.setdefault('resolution_width', preset['width'])
            if preset.get('height'):
                validated_data.setdefault('resolution_height', preset['height'])
            if preset.get('fps'):
                validated_data.setdefault('framerate', preset['fps'])
        return super().update(instance, validated_data)
```

This ensures the database stays consistent: when a user picks "TikTok", the project's
resolution is set to 1080×1920 and FPS to 30 even if the frontend doesn't send them.

---

### Step 14 — Copy Encoding Preset on Project Creation

When a new project is created, it should inherit the `encoding_preset` from
`GlobalSettings`. Currently, `Project` creation copies settings in the backend.

In `ProjectViewSet.perform_create()` (or wherever defaults are applied), add:

```python
    gs = GlobalSettings.load()
    project.encoding_preset = gs.encoding_preset
```

---

## 4. Expected Outcome

### 4.1 Backend Behaviour

| Action                          | Expected Result                                                              |
| ------------------------------- | ---------------------------------------------------------------------------- |
| `GET /api/encoding-presets/`    | Returns list of 10 presets with all metadata                                 |
| `PATCH /api/projects/:id/`      | Accepts `encoding_preset` field; auto-sets resolution/fps for named presets  |
| `POST /api/projects/:id/render/`| Renders with platform-specific CRF, bitrate, maxrate, audio bitrate         |
| Render YouTube preset           | FFmpeg cmd contains: `-crf 18 -b:v 16M -maxrate 20M -movflags +faststart`  |
| Render TikTok preset            | FFmpeg cmd contains: `-crf 20 -b:v 8M -maxrate 10M`, output is 1080×1920   |
| Render Twitter preset           | FFmpeg cmd contains: `-crf 22 -b:v 5M -maxrate 6.4M -b:a 128k`            |
| Duration exceeds platform max   | Warning logged; render proceeds; frontend shows toast                        |
| Custom preset                   | Uses project resolution/fps + CRF 23 / 8M bitrate (current behaviour)       |
| NVENC enabled + YouTube preset  | FFmpeg cmd contains: `-cq 20` (mapped from CRF 18)                          |

### 4.2 Frontend Behaviour

| Action                            | Expected Result                                                              |
| --------------------------------- | ---------------------------------------------------------------------------- |
| Open Render Settings panel        | Platform Preset selector appears above Resolution selector                   |
| Select "YouTube"                  | Resolution auto-sets to 1920×1080; resolution selector becomes disabled      |
| Select "TikTok"                   | Resolution auto-sets to 1080×1920; resolution selector becomes disabled      |
| Select "Instagram Post"           | Resolution auto-sets to 1080×1080; resolution selector becomes disabled      |
| Select "Custom"                   | Resolution selector becomes enabled; user can pick any resolution            |
| Hover preset option               | Tooltip/description shows CRF, bitrate, max duration                         |
| Render with Twitter preset        | If estimated duration > 140s, toast warning appears                          |

### 4.3 FFmpeg Command Examples

**YouTube (1080p):**
```
ffmpeg -y -f rawvideo -vcodec rawvideo -pix_fmt rgb24 -s 1920x1080 -r 30 -i pipe:0
  -i /tmp/audio.wav
  -c:v libx264 -preset fast -tune film
  -crf 18 -b:v 16M -maxrate 20M -bufsize 30M -profile:v high
  -c:a aac -b:a 192k
  -pix_fmt yuv420p -movflags +faststart output.mp4
```

**TikTok (NVENC):**
```
ffmpeg -y -f rawvideo -vcodec rawvideo -pix_fmt rgb24 -s 1080x1920 -r 30 -i pipe:0
  -i /tmp/audio.wav
  -c:v h264_nvenc -preset p4 -tune hq -rc vbr
  -cq 22 -b:v 8M -maxrate 10M -bufsize 15M -profile:v high
  -c:a aac -b:a 192k
  -pix_fmt yuv420p -movflags +faststart output.mp4
```

**Twitter/X (libx264):**
```
ffmpeg -y -f rawvideo -vcodec rawvideo -pix_fmt rgb24 -s 1920x1080 -r 30 -i pipe:0
  -i /tmp/audio.wav
  -c:v libx264 -preset fast -tune film
  -crf 22 -b:v 5M -maxrate 6.4M -bufsize 10M -profile:v high
  -c:a aac -b:a 128k
  -pix_fmt yuv420p -movflags +faststart output.mp4
```

### 4.4 Database Changes

```
project table:
  + encoding_preset  VARCHAR(30)  DEFAULT 'custom'

globalsettings table:
  + encoding_preset  VARCHAR(30)  DEFAULT 'custom'
```

### 4.5 Backward Compatibility

- Existing projects get `encoding_preset='custom'` via migration default.
- The "custom" preset produces **identical** output to the current hardcoded behaviour
  (CRF 23, 8M bitrate, High profile, faststart), so no regression for existing projects.
- The `bitrate` parameter on `FFmpegFrameWriter.__init__()` is preserved for backward
  compatibility but is overridden by `preset["bitrate"]` when a preset dict is provided.

---

## 5. Verification Checklist

### 5.1 Backend Unit Tests

- [ ] `encoding_presets.py` — `get_preset("youtube")` returns expected dict
- [ ] `encoding_presets.py` — `get_preset("nonexistent")` returns "custom" fallback
- [ ] `encoding_presets.py` — `get_preset_names()` returns 10 entries
- [ ] `encoding_presets.py` — `get_nvenc_cq(18)` returns 20
- [ ] `encoding_presets.py` — `resolve_preset_for_project()` fills width/height/fps for "custom"
- [ ] `encoding_presets.py` — `resolve_preset_for_project()` uses preset width for "tiktok"
- [ ] `FFmpegFrameWriter._build_command()` — with youtube preset produces `-crf 18`
- [ ] `FFmpegFrameWriter._build_command()` — with no preset produces `-crf 23` (backward compat)
- [ ] `FFmpegFrameWriter._build_command()` — NVENC + youtube preset produces `-cq 20`
- [ ] `FFmpegFrameWriter._build_command()` — twitter preset produces `-b:a 128k`
- [ ] `FFmpegFrameWriter._build_command()` — preset with `faststart=False` omits `-movflags`

### 5.2 API Tests

- [ ] `GET /api/encoding-presets/` returns 200 with 10 items
- [ ] `PATCH /api/projects/:id/` with `encoding_preset="youtube"` sets resolution to 1920×1080
- [ ] `PATCH /api/projects/:id/` with `encoding_preset="tiktok"` sets resolution to 1080×1920
- [ ] `PATCH /api/projects/:id/` with `encoding_preset="invalid"` returns 400
- [ ] `PATCH /api/projects/:id/` with `encoding_preset="custom"` preserves existing resolution
- [ ] `GET  /api/projects/:id/` includes `encoding_preset` field in response
- [ ] `GET  /api/settings/` includes `encoding_preset` field
- [ ] `PATCH /api/settings/` with `encoding_preset="facebook"` persists correctly

### 5.3 Migration Tests

- [ ] `python manage.py makemigrations --check` reports no missing migrations
- [ ] `python manage.py migrate` runs without errors
- [ ] Existing projects have `encoding_preset='custom'` after migration
- [ ] `GlobalSettings.load().encoding_preset` is `'custom'` after migration

### 5.4 Integration / E2E Tests

- [ ] Render a project with "youtube" preset → output file uses CRF 18 encoding
  - Verify with: `ffprobe -show_streams output.mp4 | grep bit_rate`
- [ ] Render a project with "tiktok" preset → output is 1080×1920
  - Verify with: `ffprobe -show_streams output.mp4 | grep width`
- [ ] Render a project with "custom" preset → matches current default output
- [ ] Render a project with "twitter" preset where duration > 140s → warning in logs
- [ ] Render with NVENC + "youtube" preset → `-cq 20` in FFmpeg command log

### 5.5 Frontend Tests

- [ ] `EncodingPresetSelector` renders with all 10 preset options
- [ ] Selecting "YouTube" calls `onChange` with `{ encoding_preset: "youtube" }`
- [ ] Resolution selector becomes disabled when a named preset is selected
- [ ] Resolution selector becomes enabled when "Custom" is selected
- [ ] `RenderSettingsForm` passes `encodingPreset` prop to selector
- [ ] Duration warning toast renders when content exceeds platform max duration
- [ ] `GET /api/encoding-presets/` is called on mount (or fallback constants used)

### 5.6 Manual QA Checklist

- [ ] Create a new project → verify `encoding_preset` defaults to "custom"
- [ ] Change global settings encoding preset → create project → verify inherited
- [ ] Switch between each platform preset → verify resolution/fps update correctly
- [ ] Render a short video with YouTube preset and verify file quality is noticeably higher
      than current default (CRF 18 vs CRF 23)
- [ ] Render a short video with Twitter preset → check audio bitrate is 128k
- [ ] Attempt to render a 3-minute video with Instagram Reel preset → verify warning
- [ ] Verify the rendered file plays correctly on the target platform (upload test)

---

## 6. Notes for AI Agent

### 6.1 Implementation Order

Execute the steps in this exact sequence to avoid import errors and migration issues:

1. **Step 1** — Create `encoding_presets.py` first (no dependencies).
2. **Step 2** — Add model fields (imports `PRESET_CHOICES` from Step 1).
3. **Step 2c** — Run `makemigrations` + `migrate` immediately after model changes.
4. **Step 3** — Update serializers (depends on model fields existing).
5. **Step 4** — Add API endpoint (depends on `encoding_presets.py` existing).
6. **Step 5** — Refactor `FFmpegFrameWriter` (depends on `encoding_presets.py`).
7. **Step 6** — Update `video_renderer.py` (depends on Steps 5 + 1).
8. **Steps 7–12** — Frontend changes (can be done in any order once backend is ready).
9. **Steps 13–14** — Backend auto-apply + inheritance (final touches).

### 6.2 Critical Code Locations

| What to Find                                | Where to Look                                                   |
| ------------------------------------------- | --------------------------------------------------------------- |
| `FFmpegFrameWriter` class                   | `backend/core_engine/fast_compositor.py` lines 365–480          |
| `_build_command()` with hardcoded CRF       | `fast_compositor.py` lines 402–450                              |
| `fast_render_segments()` function signature  | `fast_compositor.py` lines 487–530                              |
| Writer instantiation in `fast_render_segments`| `fast_compositor.py` ~line 640 (search for `FFmpegFrameWriter(`)  |
| `render_project()` calling `fast_render_segments` | `video_renderer.py` lines 1043–1060                        |
| `Project` model class                       | `api/models.py` lines 36–118                                    |
| `GlobalSettings` model class                | `api/models.py` lines 200–279                                   |
| `ProjectSerializer.Meta.fields`             | `api/serializers.py` ~line 43                                   |
| `ProjectDetailSerializer.Meta.fields`       | `api/serializers.py` ~line 244                                  |
| `GlobalSettingsSerializer.Meta.fields`      | `api/serializers.py` ~line 88                                   |
| Resolution presets (frontend)               | `frontend/lib/constants.ts` lines 59–76                         |
| `RenderSettingsForm` component              | `frontend/components/RenderSettingsForm.tsx`                     |
| `GlobalSettingsPanel` composing render form | `frontend/components/GlobalSettingsPanel.tsx` ~line 309          |
| URL patterns                                | `backend/api/urls.py`                                           |

### 6.3 Import Gotchas

- **Circular import risk:** `models.py` imports `PRESET_CHOICES` from
  `core_engine/encoding_presets.py`. Since `encoding_presets.py` has **no** Django imports
  and does **not** import from `models.py`, there is no circular dependency. Keep it this way.
- In `_build_command()`, the `get_nvenc_cq` import is **inside** the NVENC branch to avoid
  loading the module when NVENC is not used. This is a micro-optimization; a top-level
  import is also acceptable.
- The `resolve_preset_for_project()` function accesses `project.encoding_preset`,
  `project.resolution_width`, etc. It does **not** import the `Project` model — it works
  with any object that has those attributes (duck typing).

### 6.4 Naming Conventions

- Preset slugs: `snake_case` (e.g. `youtube_shorts`, `instagram_reel`).
- Model field: `encoding_preset` (matches existing `_` naming in `resolution_width`, etc.).
- Frontend prop: `encodingPreset` (camelCase per React convention).
- API field: `encoding_preset` (snake_case per DRF convention; frontend maps as needed).
- URL path: `/api/encoding-presets/` (kebab-case per REST convention).

### 6.5 Testing Commands

```bash
# Backend unit tests
cd backend
python manage.py test core_engine.tests.test_encoding_presets -v2

# API integration tests
python manage.py test api.tests -v2

# Frontend component tests
cd frontend
npx jest --testPathPattern="EncodingPresetSelector" --verbose
npx jest --testPathPattern="RenderSettingsForm" --verbose

# Quick smoke test: verify FFmpeg command output
python -c "
from core_engine.encoding_presets import get_preset
from core_engine.fast_compositor import FFmpegFrameWriter
w = FFmpegFrameWriter('/tmp/test.mp4', 1920, 1080, 30, preset=get_preset('youtube'))
print(' '.join(w._build_command()))
"
```

### 6.6 Edge Cases to Handle

1. **Preset slug is `None` or empty string** → treat as `"custom"`.
2. **Project has a preset slug that no longer exists** (removed in a future update) →
   `get_preset()` falls back to `"custom"`. Log a warning.
3. **User changes preset from "tiktok" to "custom"** → resolution should NOT revert
   automatically. The user manually chose "custom" and should adjust resolution themselves.
4. **NVENC not available but preset is set** → falls back to libx264 path automatically
   (existing `_detect_nvenc()` logic handles this).
5. **Audio path is `None`** → audio encoding flags are skipped entirely (existing behaviour).
6. **`bufsize` not in preset dict** → default to `"16M"` (backward compatibility).

### 6.7 What NOT to Change

- Do **not** remove the `bitrate` parameter from `FFmpegFrameWriter.__init__()`. It serves
  as a backward-compatible fallback when no preset dict is provided.
- Do **not** change the existing `VALIDATION.RESOLUTION_PRESETS` in
  `frontend/lib/constants.ts`. The encoding preset system is **additive** — resolution
  presets continue to work independently for the "Custom" encoding preset.
- Do **not** enforce duration limits at render time (i.e., do not truncate the video). Only
  **warn** the user. Truncation would be a separate feature.
- Do **not** modify the `Segment` model. Encoding is a project-level concern.

### 6.8 File Checklist Summary

| #  | File                                              | Action   | Key Changes                                            |
| -- | ------------------------------------------------- | -------- | ------------------------------------------------------ |
| 1  | `backend/core_engine/encoding_presets.py`         | **NEW**  | PRESETS dict, get_preset(), resolve_preset_for_project()|
| 2  | `backend/api/models.py`                           | MODIFY   | Add `encoding_preset` field to Project + GlobalSettings|
| 3  | `backend/api/serializers.py`                      | MODIFY   | Add field to 3 serializers + validation                |
| 4  | `backend/api/views.py`                            | MODIFY   | Add `encoding_presets_list` view                       |
| 5  | `backend/api/urls.py`                             | MODIFY   | Add URL pattern for presets endpoint                   |
| 6  | `backend/core_engine/fast_compositor.py`          | MODIFY   | Refactor FFmpegFrameWriter + fast_render_segments      |
| 7  | `backend/core_engine/video_renderer.py`           | MODIFY   | Resolve preset, duration check, pass to renderer       |
| 8  | `frontend/types/encoding-preset.ts`               | **NEW**  | EncodingPreset interface                               |
| 9  | `frontend/types/settings.ts`                      | MODIFY   | Add encoding_preset to GlobalSettings                  |
| 10 | `frontend/lib/constants.ts`                       | MODIFY   | Add ENCODING_PRESETS constant                          |
| 11 | `frontend/components/EncodingPresetSelector.tsx`  | **NEW**  | Preset selector dropdown component                     |
| 12 | `frontend/components/RenderSettingsForm.tsx`       | MODIFY   | Integrate preset selector, lock resolution on preset   |
| 13 | `frontend/components/GlobalSettingsPanel.tsx`      | MODIFY   | Pass encodingPreset prop                               |
| 14 | `frontend/api/` (relevant API file)               | MODIFY   | Add getEncodingPresets() function                      |
| 15 | `backend/api/migrations/XXXX_add_encoding_preset.py` | **NEW** | Auto-generated Django migration                      |

### 6.9 Preset Reference Table

For quick reference during implementation, here is the complete encoding matrix:

| Preset           | Res         | Aspect | FPS | CRF | Bitrate | Maxrate | Bufsize | Audio  | Max Dur | Faststart | NVENC CQ |
| ---------------- | ----------- | ------ | --- | --- | ------- | ------- | ------- | ------ | ------- | --------- | -------- |
| `youtube`        | 1920×1080   | 16:9   | 30  | 18  | 16M     | 20M     | 30M     | 192k   | —       | ✓         | 20       |
| `youtube_4k`     | 3840×2160   | 16:9   | 30  | 18  | 35M     | 45M     | 60M     | 256k   | —       | ✓         | 20       |
| `youtube_shorts` | 1080×1920   | 9:16   | 30  | 20  | 10M     | 12M     | 18M     | 192k   | 60s     | ✓         | 22       |
| `tiktok`         | 1080×1920   | 9:16   | 30  | 20  | 8M      | 10M     | 15M     | 192k   | 600s    | ✓         | 22       |
| `instagram_reel` | 1080×1920   | 9:16   | 30  | 20  | 8M      | 10M     | 15M     | 192k   | 90s     | ✓         | 22       |
| `instagram_post` | 1080×1080   | 1:1    | 30  | 21  | 6M      | 8M      | 12M     | 192k   | 60s     | ✓         | 23       |
| `facebook`       | 1920×1080   | 16:9   | 30  | 21  | 12M     | 16M     | 24M     | 192k   | —       | ✓         | 23       |
| `twitter`        | 1920×1080   | 16:9   | 30  | 22  | 5M      | 6.4M    | 10M     | 128k   | 140s    | ✓         | 24       |
| `linkedin`       | 1920×1080   | 16:9   | 30  | 21  | 10M     | 12M     | 18M     | 192k   | 600s    | ✓         | 23       |
| `custom`         | Project val | —      | —   | 23  | 8M      | 12M     | 16M     | 192k   | —       | ✓         | 25       |

---

*End of Feature 5.1 Implementation Document*
