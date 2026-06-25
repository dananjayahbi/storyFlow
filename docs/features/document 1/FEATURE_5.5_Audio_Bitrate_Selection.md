# Feature 5.5 — Audio Bitrate Selection

## Table of Contents

1. [Document Overview](#1-document-overview)
2. [Flow Diagram](#2-flow-diagram)
3. [Step-by-Step Instructions](#3-step-by-step-instructions)
4. [Expected Outcome](#4-expected-outcome)
5. [Verification Checklist](#5-verification-checklist)
6. [Notes for AI Agent](#6-notes-for-ai-agent)

---

## 1. Document Overview

### 1.1 Summary

This feature introduces a user-selectable **audio bitrate** setting that controls
the quality of the AAC audio stream in rendered MP4 videos. Currently the audio
bitrate is hardcoded as `"192k"` in a single location within
`backend/core_engine/fast_compositor.py` (line 443). This task replaces that
hardcoded value with a configurable option that flows through the full stack:

```
GlobalSettings model  →  Project model  →  serializers  →  video_renderer  →  fast_compositor  →  FFmpeg
```

On the frontend the value is exposed as a dropdown selector inside the existing
Render Settings form and the Global Settings panel, allowing users to choose
from four AAC bitrate presets: **128 kbps**, **192 kbps** (default), **256 kbps**,
and **320 kbps**.

### 1.2 Motivation

- **File-size control** — Lower bitrates (128k) dramatically reduce file size
  for social-media shorts where audio fidelity is less critical.
- **Quality headroom** — Higher bitrates (256k, 320k) preserve audio fidelity
  for long-form narration-heavy content or high-quality voice-over projects.
- **Consistency** — Every other encoding parameter (resolution, fps, video
  codec, zoom, etc.) is already user-configurable. Audio bitrate is the last
  hardcoded FFmpeg value.

### 1.3 Scope of Changes

| Layer       | File(s)                                                         | Nature of Change                 |
|-------------|-----------------------------------------------------------------|----------------------------------|
| **Models**  | `backend/api/models.py`                                         | New choices constant + 2 model fields |
| **Serializers** | `backend/api/serializers.py`                                | New fields + validators in 3 serializers |
| **Renderer** | `backend/core_engine/video_renderer.py`                        | Read from project + pass downstream |
| **Compositor** | `backend/core_engine/fast_compositor.py`                     | Accept param + use in FFmpeg cmd |
| **Migration** | `backend/api/migrations/XXXX_add_audio_bitrate.py`            | Auto-generated Django migration  |
| **Frontend Types** | `frontend/lib/types.ts`                                  | Add field to 2 interfaces        |
| **Frontend UI** | `frontend/components/RenderSettingsForm.tsx`                 | New Select dropdown              |
| **Frontend UI** | `frontend/components/GlobalSettingsPanel.tsx`                | New Select dropdown              |

### 1.4 Allowed Bitrate Values

| Value    | Label             | Use Case                                     |
|----------|-------------------|----------------------------------------------|
| `128k`   | 128 kbps (Compact) | Social media shorts, small file size          |
| `192k`   | 192 kbps (Default) | Balanced quality & size (current behaviour) |
| `256k`   | 256 kbps (High)    | Narration-heavy, long-form content           |
| `320k`   | 320 kbps (Maximum) | Studio-quality, lossless-like AAC output     |

### 1.5 Default Behaviour

The default value is **`192k`** so that existing projects and new installations
behave identically to the current hardcoded value. No existing render output
changes unless the user explicitly selects a different bitrate.

---

## 2. Flow Diagram

### 2.1 Data Flow — Setting Propagation

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (Next.js)                           │
│                                                                     │
│  ┌──────────────────────┐     ┌──────────────────────────────────┐  │
│  │ GlobalSettingsPanel   │     │ RenderSettingsForm               │  │
│  │ ┌──────────────────┐  │     │ ┌──────────────────────────────┐ │  │
│  │ │ Audio Bitrate     │  │     │ │ Audio Bitrate                │ │  │
│  │ │ [Select: 192k ▼]  │  │     │ │ [Select: 192k ▼]            │ │  │
│  │ └──────────────────┘  │     │ └──────────────────────────────┘ │  │
│  └──────────┬───────────┘     └──────────────┬──────────────────┘  │
│             │ PATCH /api/settings/            │ PATCH /api/projects/{id}/ │
│             │                                 │                     │
└─────────────┼─────────────────────────────────┼─────────────────────┘
              │                                 │
              ▼                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     BACKEND (Django REST Framework)                  │
│                                                                     │
│  ┌────────────────────────┐    ┌────────────────────────────────┐   │
│  │ GlobalSettingsSerializer│    │ ProjectDetailSerializer        │   │
│  │ validate_audio_bitrate()│    │ validate_audio_bitrate()      │   │
│  └───────────┬────────────┘    └──────────────┬─────────────────┘   │
│              │                                │                     │
│              ▼                                ▼                     │
│  ┌────────────────────────┐    ┌────────────────────────────────┐   │
│  │ GlobalSettings model    │    │ Project model                  │   │
│  │ audio_bitrate='192k'   │    │ audio_bitrate='192k'          │   │
│  └───────────┬────────────┘    └──────────────┬─────────────────┘   │
│              │                                │                     │
│              │  ProjectImportSerializer        │                     │
│              │  copies audio_bitrate ──────────┘                     │
│              │  on project creation                                  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Render Pipeline — Audio Bitrate Propagation

```
┌──────────────────────────────────────────────────────────────────┐
│                     RENDER PIPELINE                               │
│                                                                   │
│  render_project(project_id)                                       │
│  │                                                                │
│  ├─ B. Load project from DB                                       │
│  │   └── project = Project.objects.get(id=project_id)             │
│  │                                                                │
│  ├─ C6. Read audio_bitrate from Project  ◄── NEW STEP             │
│  │   └── audio_bitrate = getattr(project, "audio_bitrate", "192k")│
│  │                                                                │
│  ├─ H. Fast render pipeline                                       │
│  │   └── render_stats = fast_render_segments(                     │
│  │           ...                                                  │
│  │           audio_bitrate=audio_bitrate,    ◄── NEW PARAM        │
│  │       )                                                        │
│  │                                                                │
│  └───────────────────────┬────────────────────────────────────────┘
│                          │
│                          ▼
│  ┌────────────────────────────────────────────────────────────────┐
│  │  fast_render_segments(...)                                      │
│  │  │                                                              │
│  │  ├─ Phase 3: Start FFmpeg writer                                │
│  │  │   └── writer = FFmpegFrameWriter(                            │
│  │  │           ...                                                │
│  │  │           audio_bitrate=audio_bitrate,  ◄── NEW PARAM        │
│  │  │       )                                                      │
│  │  │                                                              │
│  │  └────────────────────┬─────────────────────────────────────────┘
│                          │
│                          ▼
│  ┌────────────────────────────────────────────────────────────────┐
│  │  FFmpegFrameWriter.__init__(...)                                │
│  │  │  self.audio_bitrate = audio_bitrate                          │
│  │  │                                                              │
│  │  ├─ _build_command()                                            │
│  │  │   └── cmd.extend(["-c:a", "aac", "-b:a", self.audio_bitrate])│
│  │  │       ▲                                                      │
│  │  │       │ REPLACES hardcoded "192k"                            │
│  │  │                                                              │
│  │  └─ start()  →  subprocess.Popen(cmd, ...)                      │
│  │                                                                 │
│  └─────────────────────────────────────────────────────────────────┘
│
└──────────────────────────────────────────────────────────────────────
```

### 2.3 Settings Inheritance on Project Creation

```
                   POST /api/projects/import/
                            │
                            ▼
              ┌──────────────────────────┐
              │ ProjectImportSerializer   │
              │ .create()                 │
              │                           │
              │  gs = GlobalSettings.load()│
              │                           │
              │  Project.objects.create(  │
              │    ...                    │
              │    audio_bitrate =        │
              │      gs.audio_bitrate,    │  ◄── NEW LINE
              │    ...                    │
              │  )                        │
              └──────────────────────────┘
```

---

## 3. Step-by-Step Instructions

### Step 1 — Define the Choices Constant in `models.py`

**File:** `backend/api/models.py`
**Location:** After `LOGO_POSITION_CHOICES` (line 33), before the `Project` class (line 36)

Add a new top-level choices list:

```python
AUDIO_BITRATE_CHOICES = [
    ('128k', '128 kbps (Compact)'),
    ('192k', '192 kbps (Default)'),
    ('256k', '256 kbps (High)'),
    ('320k', '320 kbps (Maximum)'),
]
```

**Why top-level?** Both `Project` and `GlobalSettings` reference this constant,
following the same pattern as `SUBTITLE_POSITION_CHOICES` and
`LOGO_POSITION_CHOICES`.

---

### Step 2 — Add `audio_bitrate` Field to the `Project` Model

**File:** `backend/api/models.py`
**Location:** Inside the `Project` class, in the "Audio / timing" section, after
the `inter_segment_silence` field (line 80).

Add:

```python
    # Audio / timing
    inter_segment_silence = models.FloatField(default=0.3)
    audio_bitrate = models.CharField(
        max_length=10,
        choices=AUDIO_BITRATE_CHOICES,
        default='192k',
    )
```

**Notes:**
- `max_length=10` accommodates the longest value (`"320k"` = 4 chars) with
  headroom for future formats (e.g. `"512kbps"`).
- `default='192k'` preserves current behaviour for existing rows and new
  projects.
- `choices=AUDIO_BITRATE_CHOICES` enables Django admin validation and
  auto-generated human-readable labels.

---

### Step 3 — Add `audio_bitrate` Field to the `GlobalSettings` Model

**File:** `backend/api/models.py`
**Location:** Inside the `GlobalSettings` class, in the "Audio / timing" section,
after `inter_segment_silence` (around line 246).

Add:

```python
    # ── Audio / timing ──
    inter_segment_silence = models.FloatField(default=0.3)
    audio_bitrate = models.CharField(
        max_length=10,
        choices=AUDIO_BITRATE_CHOICES,
        default='192k',
    )
```

---

### Step 4 — Generate and Apply the Django Migration

Run from the `backend/` directory:

```bash
python manage.py makemigrations api --name add_audio_bitrate
python manage.py migrate
```

This creates a migration file that adds the `audio_bitrate` column with
`default='192k'` to both the `api_project` and `api_globalsettings` tables.
Existing rows automatically receive the default.

---

### Step 5 — Add `audio_bitrate` to `GlobalSettingsSerializer`

**File:** `backend/api/serializers.py`
**Location:** `GlobalSettingsSerializer.Meta.fields` list (lines 82–97).

Add `'audio_bitrate'` to the fields list, logically after `'inter_segment_silence'`:

```python
class GlobalSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = GlobalSettings
        fields = [
            'default_voice_id', 'tts_speed',
            'subtitle_font_family', 'subtitle_font_size',
            'subtitle_font_color', 'subtitle_position',
            'subtitle_y_position',
            'subtitle_font', 'subtitle_color',
            'render_width', 'render_height', 'render_fps',
            'ken_burns_zoom', 'transition_duration', 'zoom_intensity',
            'inter_segment_silence', 'audio_bitrate',   # ◄── ADD
            'subtitles_enabled',
            'custom_font_file',
            'logo_enabled', 'active_logo', 'logo_scale',
            'logo_position', 'logo_opacity', 'logo_margin',
            'outro_enabled', 'active_outro',
            'upscale_enabled', 'upscale_model', 'upscale_denoise_strength',
            'created_at', 'updated_at',
        ]
```

Then add a field-level validator method inside `GlobalSettingsSerializer`, after
`validate_inter_segment_silence`:

```python
    def validate_audio_bitrate(self, value):
        allowed = {'128k', '192k', '256k', '320k'}
        if value not in allowed:
            raise serializers.ValidationError(
                f'Audio bitrate must be one of: {", ".join(sorted(allowed))}.'
            )
        return value
```

---

### Step 6 — Add `audio_bitrate` to `ProjectDetailSerializer`

**File:** `backend/api/serializers.py`
**Location:** `ProjectDetailSerializer.Meta.fields` list (lines 248–266).

Add `'audio_bitrate'` to the fields list, logically after `'inter_segment_silence'`:

```python
class ProjectDetailSerializer(serializers.ModelSerializer):
    segments = SegmentSerializer(many=True, read_only=True)

    class Meta:
        model = Project
        fields = [
            'id', 'title', 'created_at', 'updated_at',
            'status', 'resolution_width', 'resolution_height',
            'framerate', 'output_path', 'segments',
            # ── Per-project settings ──
            'default_voice_id', 'tts_speed',
            'subtitle_font_family', 'subtitle_font_size',
            'subtitle_font_color', 'subtitle_position',
            'subtitle_y_position',
            'subtitle_font', 'subtitle_color',
            'subtitles_enabled', 'custom_font_file',
            'zoom_intensity', 'ken_burns_zoom', 'transition_duration',
            'inter_segment_silence', 'audio_bitrate',   # ◄── ADD
            'logo_enabled', 'active_logo', 'logo_scale',
            'logo_position', 'logo_opacity', 'logo_margin',
            'outro_enabled', 'active_outro',
            'upscale_enabled', 'upscale_model', 'upscale_denoise_strength',
        ]
```

Then add a mirrored validator inside `ProjectDetailSerializer`, after
`validate_inter_segment_silence`:

```python
    def validate_audio_bitrate(self, value):
        allowed = {'128k', '192k', '256k', '320k'}
        if value not in allowed:
            raise serializers.ValidationError(
                f'Audio bitrate must be one of: {", ".join(sorted(allowed))}.'
            )
        return value
```

---

### Step 7 — Copy `audio_bitrate` in `ProjectImportSerializer.create()`

**File:** `backend/api/serializers.py`
**Location:** Inside `ProjectImportSerializer.create()`, within the
`Project.objects.create(...)` call (lines 451–475).

Add a new keyword argument to the create call, logically with the other
Audio / timing settings:

```python
            inter_segment_silence=gs.inter_segment_silence,
            audio_bitrate=gs.audio_bitrate,              # ◄── ADD
            logo_enabled=gs.logo_enabled,
```

This ensures every newly imported project inherits the global audio bitrate
default, matching the inheritance pattern already used for all other settings.

---

### Step 8 — Accept `audio_bitrate` in `FFmpegFrameWriter.__init__()`

**File:** `backend/core_engine/fast_compositor.py`
**Location:** `FFmpegFrameWriter.__init__()` signature (line 381).

Add a new `audio_bitrate` parameter with a default of `"192k"`:

```python
    def __init__(
        self,
        output_path: str,
        width: int,
        height: int,
        fps: int,
        audio_path: Optional[str] = None,
        use_nvenc: bool = False,
        bitrate: str = "8M",
        audio_bitrate: str = "192k",       # ◄── ADD
    ):
        self.output_path = output_path
        self.width = width
        self.height = height
        self.fps = fps
        self.audio_path = audio_path
        self.use_nvenc = use_nvenc
        self.bitrate = bitrate
        self.audio_bitrate = audio_bitrate  # ◄── ADD
        self._proc: Optional[subprocess.Popen] = None
```

---

### Step 9 — Use `self.audio_bitrate` in `_build_command()`

**File:** `backend/core_engine/fast_compositor.py`
**Location:** `FFmpegFrameWriter._build_command()`, audio encoding section
(line 443).

Replace the hardcoded string:

```python
        # BEFORE (hardcoded):
        if self.audio_path and os.path.isfile(self.audio_path):
            cmd.extend(["-c:a", "aac", "-b:a", "192k"])

        # AFTER (configurable):
        if self.audio_path and os.path.isfile(self.audio_path):
            cmd.extend(["-c:a", "aac", "-b:a", self.audio_bitrate])
```

---

### Step 10 — Accept `audio_bitrate` in `fast_render_segments()`

**File:** `backend/core_engine/fast_compositor.py`
**Location:** `fast_render_segments()` signature (line 488).

Add a new keyword argument after `inter_segment_silence`:

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
    audio_bitrate: str = "192k",          # ◄── ADD
) -> dict:
```

Update the docstring's Args section to include:

```python
        audio_bitrate: AAC audio bitrate string (e.g. "128k", "192k",
            "256k", "320k"). Defaults to "192k".
```

---

### Step 11 — Pass `audio_bitrate` to `FFmpegFrameWriter` Instantiation

**File:** `backend/core_engine/fast_compositor.py`
**Location:** Inside `fast_render_segments()`, where `FFmpegFrameWriter` is
instantiated (line 646).

Add the `audio_bitrate` keyword:

```python
    writer = FFmpegFrameWriter(
        output_path=output_path,
        width=width,
        height=height,
        fps=fps,
        audio_path=audio_path,
        use_nvenc=use_nvenc,
        bitrate="8M",
        audio_bitrate=audio_bitrate,   # ◄── ADD
    )
```

---

### Step 12 — Read `audio_bitrate` from Project in `render_project()`

**File:** `backend/core_engine/video_renderer.py`
**Location:** After the section "C5. Read image upscale settings from Project"
(around line 760) and before the warnings accumulator.

Add a new section:

```python
    # ------------------------------------------------------------------
    # C6. Read audio bitrate from Project
    # ------------------------------------------------------------------
    audio_bitrate = getattr(project, "audio_bitrate", "192k") or "192k"
    _ALLOWED_AUDIO_BITRATES = {"128k", "192k", "256k", "320k"}
    if audio_bitrate not in _ALLOWED_AUDIO_BITRATES:
        logger.warning(
            "Invalid audio_bitrate '%s'. Falling back to 192k.",
            audio_bitrate,
        )
        audio_bitrate = "192k"
    logger.info("Audio bitrate: %s", audio_bitrate)
```

---

### Step 13 — Pass `audio_bitrate` to `fast_render_segments()` Call

**File:** `backend/core_engine/video_renderer.py`
**Location:** The `fast_render_segments()` call site (lines 1039–1053).

Add the new keyword argument:

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
            audio_bitrate=audio_bitrate,      # ◄── ADD
        )
```

---

### Step 14 — Add `audio_bitrate` to Frontend TypeScript Interfaces

**File:** `frontend/lib/types.ts`

**14a.** Add to `ProjectDetail` interface, after `inter_segment_silence`:

```typescript
export interface ProjectDetail extends Omit<Project, 'segment_count'> {
  // ... existing fields ...
  inter_segment_silence: number;
  audio_bitrate: '128k' | '192k' | '256k' | '320k';  // ◄── ADD
  logo_enabled: boolean;
  // ... rest ...
}
```

**14b.** Add to `GlobalSettings` interface, after `inter_segment_silence`:

```typescript
export interface GlobalSettings {
  // ... existing fields ...
  inter_segment_silence: number;
  audio_bitrate: '128k' | '192k' | '256k' | '320k';  // ◄── ADD
  subtitles_enabled: boolean;
  // ... rest ...
}
```

---

### Step 15 — Add Audio Bitrate Selector to `RenderSettingsForm.tsx`

**File:** `frontend/components/RenderSettingsForm.tsx`

**15a.** Update the `RenderSettingsFormProps` interface to accept the new field:

```typescript
interface RenderSettingsFormProps {
  zoomIntensity: number;
  renderWidth: number;
  renderHeight: number;
  renderFps: number;
  audioBitrate: '128k' | '192k' | '256k' | '320k';  // ◄── ADD
  onChange: (data: {
    zoom_intensity?: number;
    render_width?: number;
    render_height?: number;
    render_fps?: number;
    audio_bitrate?: string;                            // ◄── ADD
  }) => Promise<void>;
}
```

**15b.** Add the prop to the function destructuring:

```typescript
export function RenderSettingsForm({
  zoomIntensity,
  renderWidth,
  renderHeight,
  renderFps,
  audioBitrate,      // ◄── ADD
  onChange,
}: RenderSettingsFormProps) {
```

**15c.** Define the bitrate options constant (at the top of the file, alongside
`FPS_OPTIONS`):

```typescript
const AUDIO_BITRATE_OPTIONS = [
  { value: '128k', label: '128 kbps (Compact)' },
  { value: '192k', label: '192 kbps (Default)' },
  { value: '256k', label: '256 kbps (High)' },
  { value: '320k', label: '320 kbps (Maximum)' },
] as const;
```

**15d.** Add a new Select dropdown after the Framerate Selector section, before
the closing `</div>`:

```tsx
      {/* ── Audio Bitrate Selector ── */}
      <div className="space-y-1.5">
        <label className="text-xs text-muted-foreground font-medium">
          Audio Bitrate
        </label>
        <Select
          value={audioBitrate}
          onValueChange={(value) => onChange({ audio_bitrate: value })}
        >
          <SelectTrigger className="h-9 text-sm">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {AUDIO_BITRATE_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <p className="text-[10px] text-muted-foreground">
          Higher bitrate = better audio quality, larger file size
        </p>
      </div>
```

---

### Step 16 — Add Audio Bitrate Selector to `GlobalSettingsPanel.tsx`

**File:** `frontend/components/GlobalSettingsPanel.tsx`

Follow the same pattern as Step 15 but within the Global Settings panel
component. Add the `AUDIO_BITRATE_OPTIONS` constant (or import it from a shared
constants file) and add a `<Select>` dropdown in the Audio / Timing section of
the panel, after the inter-segment silence control.

The `onChange` handler should call the settings update API with
`{ audio_bitrate: value }`.

---

### Step 17 — Pass `audioBitrate` Prop from Parent Components

Locate every parent component that renders `<RenderSettingsForm>` and pass
the new `audioBitrate` prop sourced from the project detail or global settings
object.

**Pattern:**

```tsx
<RenderSettingsForm
  zoomIntensity={project.zoom_intensity}
  renderWidth={project.resolution_width}
  renderHeight={project.resolution_height}
  renderFps={project.framerate}
  audioBitrate={project.audio_bitrate}     // ◄── ADD
  onChange={handleSettingsChange}
/>
```

Similarly, any parent rendering `<GlobalSettingsPanel>` must pass
`settings.audio_bitrate` into the panel.

---

### Step 18 — Update Frontend Type in `types/settings.ts` (if applicable)

**File:** `frontend/types/settings.ts`

If this file contains a separate `GlobalSettings` interface (some projects
duplicate types), add `audio_bitrate` there as well to keep both type
declarations in sync:

```typescript
audio_bitrate: '128k' | '192k' | '256k' | '320k';
```

---

## 4. Expected Outcome

### 4.1 Backend Behaviour

| Scenario                         | Expected Result                                            |
|----------------------------------|------------------------------------------------------------|
| Fresh install (`migrate`)        | Both tables get `audio_bitrate` column, default `'192k'`   |
| Existing DB (`migrate`)          | All existing rows receive `'192k'` via migration default   |
| GET `/api/settings/`             | Response includes `"audio_bitrate": "192k"`                |
| PATCH `/api/settings/` `{"audio_bitrate": "320k"}` | Saved; subsequent GET returns `"320k"` |
| PATCH `/api/settings/` `{"audio_bitrate": "999k"}` | 400 error with validation message |
| POST `/api/projects/import/`     | New project's `audio_bitrate` == GlobalSettings value      |
| GET `/api/projects/{id}/`        | Response includes `"audio_bitrate": "192k"` (or override)  |
| PATCH `/api/projects/{id}/` `{"audio_bitrate": "256k"}` | Saved per-project       |
| Render with `audio_bitrate="128k"` | FFmpeg receives `-b:a 128k`; output AAC is ~128 kbps    |
| Render with `audio_bitrate="320k"` | FFmpeg receives `-b:a 320k`; output AAC is ~320 kbps    |
| Render with default (no change)    | FFmpeg receives `-b:a 192k`, identical to current        |
| Invalid value in DB (edge case)    | `render_project()` logs warning, falls back to `192k`    |

### 4.2 Frontend Behaviour

| Scenario                                     | Expected Result                                 |
|----------------------------------------------|-------------------------------------------------|
| Open Render Settings panel                   | Audio Bitrate dropdown visible, shows current   |
| Change bitrate to "256 kbps (High)"          | API PATCH fires, dropdown reflects new value    |
| Open Global Settings panel                   | Audio Bitrate dropdown visible, shows global    |
| Create new project after changing global     | New project inherits the changed global bitrate |
| Refresh page                                 | Values persist (fetched from API)               |

### 4.3 FFmpeg Command Verification

Before (hardcoded):
```
ffmpeg -y -f rawvideo ... -c:a aac -b:a 192k -pix_fmt yuv420p ...
```

After (user selects 320k):
```
ffmpeg -y -f rawvideo ... -c:a aac -b:a 320k -pix_fmt yuv420p ...
```

### 4.4 File Size Impact

Approximate audio track sizes for a 5-minute video:

| Bitrate | Audio Track Size | Typical Total File Size Impact |
|---------|------------------|-------------------------------|
| 128 kbps | ~4.7 MB        | ▼ ~2 MB saved vs 192k         |
| 192 kbps | ~7.0 MB        | Baseline (current)             |
| 256 kbps | ~9.4 MB        | ▲ ~2.4 MB overhead             |
| 320 kbps | ~11.7 MB       | ▲ ~4.7 MB overhead             |

---

## 5. Verification Checklist

### 5.1 Migration & Database

- [ ] `python manage.py makemigrations api --name add_audio_bitrate` generates
      exactly one migration file with two `AddField` operations.
- [ ] `python manage.py migrate` applies cleanly with no errors.
- [ ] Existing `Project` rows show `audio_bitrate='192k'` in the DB.
- [ ] Existing `GlobalSettings` row shows `audio_bitrate='192k'` in the DB.
- [ ] `python manage.py makemigrations --check` reports "No changes detected"
      after migration.

### 5.2 API — GlobalSettings

- [ ] `GET /api/settings/` response body contains `"audio_bitrate": "192k"`.
- [ ] `PATCH /api/settings/` with `{"audio_bitrate": "128k"}` → 200 OK.
- [ ] `PATCH /api/settings/` with `{"audio_bitrate": "128k"}` → subsequent
      GET returns `"audio_bitrate": "128k"`.
- [ ] `PATCH /api/settings/` with `{"audio_bitrate": "999k"}` → 400 Bad
      Request with a specific validation error message.
- [ ] `PATCH /api/settings/` with `{"audio_bitrate": ""}` → 400 Bad Request.

### 5.3 API — Project Detail

- [ ] `GET /api/projects/{id}/` response body contains `"audio_bitrate"`.
- [ ] `PATCH /api/projects/{id}/` with `{"audio_bitrate": "320k"}` → 200 OK.
- [ ] `PATCH /api/projects/{id}/` with `{"audio_bitrate": "abc"}` → 400 Bad
      Request with validation error.
- [ ] Changing one project's bitrate does NOT affect other projects.

### 5.4 Project Import Inheritance

- [ ] Set GlobalSettings `audio_bitrate` to `"256k"`.
- [ ] POST `/api/projects/import/` to create a new project.
- [ ] GET the new project's detail → `audio_bitrate` is `"256k"`.
- [ ] Confirm the GlobalSettings value did not change.

### 5.5 Render Pipeline — End to End

- [ ] Render a project with the default `audio_bitrate` (`192k`).
- [ ] Inspect the server logs for: `Audio bitrate: 192k`.
- [ ] Inspect the FFmpeg command log for: `-b:a 192k`.
- [ ] Output MP4 plays correctly with audio.
- [ ] Change the project's `audio_bitrate` to `"320k"` and re-render.
- [ ] Inspect the FFmpeg command log for: `-b:a 320k`.
- [ ] Use `ffprobe` to verify:
      ```bash
      ffprobe -v quiet -select_streams a:0 -show_entries stream=bit_rate \
          -of default=noprint_wrappers=1 output.mp4
      ```
      Expected: `bit_rate` approximately matches the selected bitrate.
- [ ] Render with `"128k"` — output file audio track is noticeably smaller
      than a `"320k"` render of the same content.

### 5.6 Fallback / Defence

- [ ] If `audio_bitrate` is somehow `None` or an invalid value in the DB,
      `render_project()` logs a warning and falls back to `"192k"`.
- [ ] No Python exception is raised for missing/invalid DB values.

### 5.7 Frontend — Global Settings Panel

- [ ] Audio Bitrate selector is visible in the Global Settings panel.
- [ ] Selecting a different bitrate fires a PATCH to `/api/settings/`.
- [ ] The selected value persists after page refresh.
- [ ] The selector shows the correct label (e.g. "192 kbps (Default)").

### 5.8 Frontend — Render Settings Form

- [ ] Audio Bitrate selector is visible in the per-project Render Settings form.
- [ ] Selecting a different bitrate fires a PATCH to
      `/api/projects/{id}/`.
- [ ] The selected value persists after page refresh.
- [ ] The selector shows the correct label.

### 5.9 TypeScript Type Safety

- [ ] `frontend/lib/types.ts` — `ProjectDetail.audio_bitrate` exists and is a
      string union type.
- [ ] `frontend/lib/types.ts` — `GlobalSettings.audio_bitrate` exists and is a
      string union type.
- [ ] No TypeScript compilation errors (`npx tsc --noEmit` passes).
- [ ] No ESLint errors on changed files (`npx eslint --no-error-on-unmatched-pattern`).

### 5.10 Backward Compatibility

- [ ] Old frontend versions that don't send `audio_bitrate` can still create
      and render projects (field has a model default).
- [ ] Existing rendered videos are NOT affected (no re-render triggered).
- [ ] The Django admin panel shows the new field with a dropdown for both
      Project and GlobalSettings.

---

## 6. Notes for AI Agent

### 6.1 Key Files and Exact Edit Locations

Below is a precise map of every file and the exact location where edits are required.
Line numbers reference the **current** state of the codebase (before this feature).

| # | File | Line(s) | Action |
|---|------|---------|--------|
| 1 | `backend/api/models.py` | After L33 (after `LOGO_POSITION_CHOICES`) | Insert `AUDIO_BITRATE_CHOICES` constant |
| 2 | `backend/api/models.py` | L80 (`inter_segment_silence` in `Project`) | Insert `audio_bitrate` field after it |
| 3 | `backend/api/models.py` | ~L246 (`inter_segment_silence` in `GlobalSettings`) | Insert `audio_bitrate` field after it |
| 4 | `backend/api/serializers.py` | L93 (`'inter_segment_silence'` in `GlobalSettingsSerializer.Meta.fields`) | Append `'audio_bitrate'` |
| 5 | `backend/api/serializers.py` | After `validate_inter_segment_silence` in `GlobalSettingsSerializer` (~L165) | Insert `validate_audio_bitrate` method |
| 6 | `backend/api/serializers.py` | L261 (`'inter_segment_silence'` in `ProjectDetailSerializer.Meta.fields`) | Append `'audio_bitrate'` |
| 7 | `backend/api/serializers.py` | After `validate_inter_segment_silence` in `ProjectDetailSerializer` (~L348) | Insert `validate_audio_bitrate` method |
| 8 | `backend/api/serializers.py` | ~L469 (inside `ProjectImportSerializer.create()`) | Add `audio_bitrate=gs.audio_bitrate` to `Project.objects.create()` |
| 9 | `backend/core_engine/fast_compositor.py` | L381–L398 (`FFmpegFrameWriter.__init__`) | Add `audio_bitrate: str = "192k"` param + `self.audio_bitrate` |
| 10 | `backend/core_engine/fast_compositor.py` | L443 (`"-b:a", "192k"`) | Replace `"192k"` with `self.audio_bitrate` |
| 11 | `backend/core_engine/fast_compositor.py` | L488–L500 (`fast_render_segments` signature) | Add `audio_bitrate: str = "192k"` param |
| 12 | `backend/core_engine/fast_compositor.py` | L646–L654 (`FFmpegFrameWriter(...)` call) | Add `audio_bitrate=audio_bitrate` kwarg |
| 13 | `backend/core_engine/video_renderer.py` | After ~L760 (after section C5) | Insert section C6 to read `audio_bitrate` from project |
| 14 | `backend/core_engine/video_renderer.py` | L1039–L1053 (`fast_render_segments(...)` call) | Add `audio_bitrate=audio_bitrate` kwarg |
| 15 | `frontend/lib/types.ts` | L38 (after `inter_segment_silence` in `ProjectDetail`) | Insert `audio_bitrate` field |
| 16 | `frontend/lib/types.ts` | L73 (after `inter_segment_silence` in `GlobalSettings`) | Insert `audio_bitrate` field |
| 17 | `frontend/components/RenderSettingsForm.tsx` | Props interface (~L18–L30) | Add `audioBitrate` prop + `audio_bitrate` to `onChange` |
| 18 | `frontend/components/RenderSettingsForm.tsx` | After framerate selector (~L220) | Insert Audio Bitrate `<Select>` dropdown |
| 19 | `frontend/components/GlobalSettingsPanel.tsx` | Audio/timing section | Insert Audio Bitrate `<Select>` dropdown |

### 6.2 Code Patterns to Follow

**Choices constant pattern** — Copy the structure of `SUBTITLE_POSITION_CHOICES`
(line 20 of `models.py`): top-level list of `(db_value, human_label)` tuples.

**Model field pattern** — Copy the structure of `subtitle_position` (line 56 of
`models.py`): `CharField` with `max_length`, `choices`, and `default`.

**Serializer field list pattern** — Fields are listed one per line in the `Meta.fields`
list. The new field goes after `'inter_segment_silence'` to keep audio-related
settings grouped together.

**Serializer validator pattern** — Copy the structure of `validate_upscale_model`
(line 186 of `serializers.py`): define an `allowed` set, check `value not in
allowed`, raise `ValidationError` with a descriptive message listing allowed
values.

**ProjectImportSerializer.create() copy pattern** — Every GlobalSettings field
is copied to the new Project as a keyword argument with `gs.<field_name>`. Add
`audio_bitrate=gs.audio_bitrate` immediately after `inter_segment_silence`.

**video_renderer reading pattern** — Copy the structure of the upscale settings
section (C5, around line 755): use `getattr()` with a sensible default, log the
value, and validate with a fallback.

**Frontend Select dropdown pattern** — Copy the structure of the Framerate
Selector in `RenderSettingsForm.tsx` (lines 201–224): a `<Select>` with
`value`, `onValueChange`, and mapped `<SelectItem>`s.

### 6.3 Important Constraints

1. **Do NOT change the default behaviour.** Default must be `"192k"` everywhere
   so that existing projects render identically.

2. **Do NOT rename the video `bitrate` parameter.** The existing `bitrate="8M"`
   param in `FFmpegFrameWriter` controls the *video* bitrate. The new parameter
   must be named `audio_bitrate` to avoid confusion.

3. **Migration must be safe for production.** The migration adds a column with a
   default, which is a non-locking operation in SQLite (the current DB engine).
   No data migration is required since the default handles backfill.

4. **All four bitrate values must be validated** at both the serializer level
   (DRF) and the render pipeline level (`video_renderer.py` fallback). Do not
   rely on model-level `choices` alone since raw `.objects.create()` calls
   bypass choices validation.

5. **Frontend type must use a string union**, not a generic `string`, so that
   TypeScript catches typos at compile time.

6. **The `fast_render_segments` signature change is backward-compatible** because
   the new parameter has a default value. Any existing callers (tests, etc.)
   that don't pass `audio_bitrate` will get `"192k"` automatically.

### 6.4 Testing Hints

- To manually verify the FFmpeg command, look for the log line:
  `FFmpeg command: ffmpeg -y -f rawvideo ...` — the `-b:a` flag should reflect
  the selected bitrate.
- Use `ffprobe` to inspect the output:
  ```bash
  ffprobe -v quiet -select_streams a:0 \
      -show_entries stream=codec_name,bit_rate,sample_rate \
      -of default=noprint_wrappers=1 output.mp4
  ```
- Run the existing test suite to ensure no regressions:
  ```bash
  python manage.py test api
  python manage.py test tests
  ```
- Frontend type check:
  ```bash
  cd frontend && npx tsc --noEmit
  ```

### 6.5 Order of Implementation

The recommended implementation order to avoid errors:

1. **Models** (Steps 1–3) — Define the data layer first.
2. **Migration** (Step 4) — Create and apply the DB schema change.
3. **Serializers** (Steps 5–7) — Expose the field to the API.
4. **Compositor** (Steps 8–11) — Wire the value into FFmpeg.
5. **Renderer** (Steps 12–13) — Connect the project setting to the compositor.
6. **Frontend types** (Steps 14, 18) — Update TypeScript interfaces.
7. **Frontend UI** (Steps 15–17) — Add the selector components.

This order ensures each layer has its dependencies in place before it is
modified, minimizing intermediate breakage.

### 6.6 Files That Should NOT Be Modified

- `backend/api/urls.py` — No new endpoints needed.
- `backend/api/views.py` — Views use serializers which handle the new field.
- `backend/core_engine/audio_utils.py` — Audio mixing is unaffected.
- `backend/core_engine/tts_wrapper.py` — TTS generation is unaffected.
- `backend/core_engine/subtitle_engine.py` — Subtitles are unaffected.
- `backend/core_engine/ken_burns.py` — Visual effects are unaffected.
- `backend/storyflow_backend/settings.py` — No Django settings changes needed.

### 6.7 Rollback Plan

If the feature must be reverted:

1. Revert all code changes.
2. Generate a reverse migration: `python manage.py makemigrations api --name remove_audio_bitrate`.
3. Apply: `python manage.py migrate`.
4. The column default ensures no data loss if migration is not reverted
   immediately.

---

*End of Feature 5.5 implementation document.*
