# Feature 2.4 — Zoom Level Control Per Segment

> **Status:** Planned  
> **Category:** Core Engine / Visual Storytelling  
> **Primary Files:** `backend/api/models.py`, `backend/core_engine/fast_compositor.py`, `backend/core_engine/video_renderer.py`  
> **Estimated Complexity:** Medium  
> **Impact:** Enables per-segment zoom intensity for expressive visual storytelling  
> **Date Created:** March 10, 2026  

---

## Table of Contents

1. [Document Overview](#1-document-overview)
2. [Flow Diagram](#2-flow-diagram)
3. [Step-by-Step Instructions](#3-step-by-step-instructions)
4. [Expected Outcome](#4-expected-outcome)
5. [Verification Checklist](#5-verification-checklist)
6. [Notes for AI Agent](#6-notes-for-ai-agent)

---

## 1. Document Overview

### 1.1 Problem Statement

The Ken Burns zoom-and-pan effect is a core visual element of every
rendered StoryFlow video.  Currently, a **single global**
`zoom_intensity` value is applied uniformly to every segment in a
project.  This value flows through the system as follows:

1. **`Project.zoom_intensity`** — a `FloatField(default=1.3)` on the
   `Project` model (`backend/api/models.py`, line ~57).
2. **`GlobalSettings.zoom_intensity`** — a `FloatField(default=1.3)` on
   the `GlobalSettings` singleton (`backend/api/models.py`, line ~197).
3. **`render_project()`** — reads `project.zoom_intensity` once at
   line ~652 of `backend/core_engine/video_renderer.py` and passes it
   as a scalar to `fast_render_segments()`.
4. **`fast_render_segments()`** — receives `zoom_intensity` as a single
   `float` parameter (`backend/core_engine/fast_compositor.py`,
   line ~493) and applies it identically to every segment in
   Phase 1 (lines 563–606).
5. **Ken Burns helpers** — `load_and_prepare_image()` (line 76) and
   `calculate_crop_dimensions()` (line 196) both accept
   `zoom_intensity` as a scalar argument.

The `Segment` model (`backend/api/models.py`, line 130) has **no**
`zoom_intensity` field.  Every segment therefore renders with the
exact same zoom factor, regardless of its narrative content.

This is limiting because:

- **Dramatic scenes** (action, revelation) benefit from a higher zoom
  (e.g. 1.5×) — the camera feels like it's pushing in.
- **Calm / wide-establishing scenes** work better with a subtle zoom
  (e.g. 1.05–1.1×) — the camera gently drifts.
- **Static title cards** may want zoom_intensity = 1.0 (no zoom at
  all).

Without per-segment control, the creator must choose a single
compromise value for the entire project, which weakens the emotional
arc of the video.

### 1.2 Proposed Solution

Add an **optional** `zoom_intensity` field to the `Segment` model.
When the field is `NULL` (the default), the segment inherits the
project-level zoom_intensity — preserving full backward compatibility.
When a value is explicitly set (e.g. `1.5`), it overrides the project
default for that segment only.

The resolution cascade is:

```
Per-segment zoom_intensity  →  if NULL  →  Project zoom_intensity  →  if NULL  →  1.3 (hardcoded default)
```

This approach:

- **Zero migration risk** — existing segments get `NULL`, and behaviour
  is identical to today.
- **Minimal API surface change** — only `SegmentSerializer` gains
  one optional field.
- **Frontend-friendly** — a simple slider per segment, defaulting to
  "Use project default".
- **Render pipeline** — each segment carries its own effective zoom;
  the fast compositor reads it from the per-segment descriptor.

### 1.3 Files to Modify

| # | File | Change |
|---|------|--------|
| 1 | `backend/api/models.py` | Add `zoom_intensity` to `Segment` model |
| 2 | `backend/api/serializers.py` | Add `zoom_intensity` to `SegmentSerializer` |
| 3 | `backend/api/migrations/` | Auto-generated Django migration |
| 4 | `backend/core_engine/video_renderer.py` | Include per-segment zoom in `segment_data_list` |
| 5 | `backend/core_engine/fast_compositor.py` | Read per-segment zoom in Phase 1; pass to Ken Burns helpers |
| 6 | `frontend/lib/types.ts` | Add `zoom_intensity` to `Segment` interface and `UpdateSegmentPayload` |
| 7 | `frontend/components/SegmentCard.tsx` | Add zoom intensity slider UI |
| 8 | `frontend/lib/api.ts` | No changes needed (uses generic `UpdateSegmentPayload`) |
| 9 | `frontend/lib/stores.ts` | No changes needed (`updateSegment` is already generic) |

### 1.4 Dependencies

- Django ORM (`models.FloatField`)
- Django REST Framework (`serializers.ModelSerializer`)
- `backend/core_engine/ken_burns.py` — `load_and_prepare_image()`,
  `calculate_crop_dimensions()` (both accept `zoom_intensity` already)
- Frontend: `shadcn/ui` Slider component

### 1.5 Risk Assessment

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Migration breaks existing data | Low | Field is `null=True, blank=True`; NULL → use project default |
| Zoom < 1.0 causes crop overflow | Medium | Clamp to `[1.0, 2.0]` at serializer and renderer level |
| Frontend state sync issues | Low | Optimistic update already implemented in store |
| Performance regression | Very Low | Per-segment zoom is a constant read, not a computation |

---

## 2. Flow Diagram

### 2.1 Current Data Flow (Global Zoom Only)

```
┌──────────────────────────────────────────────────────────────────┐
│                         CURRENT FLOW                             │
│                                                                  │
│  ┌──────────────┐        ┌──────────────────┐                    │
│  │ GlobalSettings│───────▶│   Project        │                    │
│  │ zoom: 1.3    │ copy   │   zoom: 1.3      │                    │
│  └──────────────┘  on    └────────┬─────────┘                    │
│                   create          │                               │
│                                   │ read once                    │
│                                   ▼                               │
│                          ┌────────────────────┐                  │
│                          │  render_project()   │                  │
│                          │  zoom_intensity=1.3 │                  │
│                          └────────┬───────────┘                  │
│                                   │ pass single float            │
│                                   ▼                               │
│                          ┌────────────────────┐                  │
│                          │fast_render_segments │                  │
│                          │ zoom_intensity=1.3  │                  │
│                          └────────┬───────────┘                  │
│                                   │                               │
│              ┌────────────────────┼────────────────────┐         │
│              ▼                    ▼                    ▼          │
│      ┌──────────────┐   ┌──────────────┐   ┌──────────────┐     │
│      │  Segment 0   │   │  Segment 1   │   │  Segment 2   │     │
│      │  zoom: 1.3   │   │  zoom: 1.3   │   │  zoom: 1.3   │     │
│      │  (global)    │   │  (global)    │   │  (global)    │     │
│      └──────────────┘   └──────────────┘   └──────────────┘     │
│                                                                  │
│  ALL segments use the SAME zoom_intensity value.                 │
└──────────────────────────────────────────────────────────────────┘
```

### 2.2 Proposed Data Flow (Per-Segment Zoom Override)

```
┌──────────────────────────────────────────────────────────────────┐
│                        PROPOSED FLOW                             │
│                                                                  │
│  ┌──────────────┐        ┌──────────────────┐                    │
│  │ GlobalSettings│───────▶│   Project        │                    │
│  │ zoom: 1.3    │ copy   │   zoom: 1.3      │                    │
│  └──────────────┘  on    └────────┬─────────┘                    │
│                   create          │                               │
│                                   │ read project zoom as default │
│                                   ▼                               │
│                          ┌────────────────────┐                  │
│                          │  render_project()   │                  │
│                          │  zoom_intensity=1.3 │                  │
│                          │  (project default)  │                  │
│                          └────────┬───────────┘                  │
│                                   │                               │
│                                   │ per-segment: seg.zoom or     │
│                                   │              project default  │
│                                   ▼                               │
│                  ┌────────────────────────────────┐              │
│                  │    segment_data_list[]          │              │
│                  │  Each dict now includes:        │              │
│                  │  "zoom_intensity": effective    │              │
│                  └────────────────┬───────────────┘              │
│                                   │ pass list                    │
│                                   ▼                               │
│                          ┌────────────────────┐                  │
│                          │fast_render_segments │                  │
│                          │ reads per-segment   │                  │
│                          │ zoom from each dict │                  │
│                          └────────┬───────────┘                  │
│                                   │                               │
│              ┌────────────────────┼────────────────────┐         │
│              ▼                    ▼                    ▼          │
│      ┌──────────────┐   ┌──────────────┐   ┌──────────────┐     │
│      │  Segment 0   │   │  Segment 1   │   │  Segment 2   │     │
│      │  zoom: NULL   │   │  zoom: 1.5   │   │  zoom: 1.1   │     │
│      │  → uses 1.3  │   │  → uses 1.5  │   │  → uses 1.1  │     │
│      │  (project)   │   │  (override)  │   │  (override)  │     │
│      └──────────────┘   └──────────────┘   └──────────────┘     │
│                                                                  │
│  Each segment uses its OWN zoom_intensity, falling back to the   │
│  project default when not explicitly set.                        │
└──────────────────────────────────────────────────────────────────┘
```

### 2.3 Render Pipeline Detail — Per-Segment Zoom Path

```
┌─────────────────────────────────────────────────────────────────────┐
│                    RENDER PIPELINE (FAST COMPOSITOR)                 │
│                                                                     │
│  video_renderer.py :: render_project()                              │
│  ─────────────────────────────────────                              │
│                                                                     │
│  for segment in segments:                                           │
│    │                                                                │
│    ├─ effective_zoom = segment.zoom_intensity                       │
│    │                    if segment.zoom_intensity is not None        │
│    │                    else project_zoom_intensity                  │
│    │                                                                │
│    ├─ segment_data_list.append({                                    │
│    │      "image_path": ...,                                        │
│    │      "audio_duration": ...,                                    │
│    │      "text_content": ...,                                      │
│    │      "sequence_index": ...,                                    │
│    │      "zoom_intensity": effective_zoom,       ◄── NEW KEY       │
│    │  })                                                            │
│    │                                                                │
│    └─ continue                                                      │
│                                                                     │
│  fast_render_segments(segment_data=segment_data_list, ...)          │
│  ──────────────────────────────────────────────────────             │
│                                                                     │
│  Phase 1 loop:                                                      │
│    for idx, seg in enumerate(segment_data):                         │
│      │                                                              │
│      │  seg_zoom = seg.get("zoom_intensity", zoom_intensity)        │
│      │                           │                 │                │
│      │                           │           fallback to fn param   │
│      │                           ▼                                  │
│      ├─ load_and_prepare_image(path, res, seg_zoom)                 │
│      ├─ calculate_crop_dimensions(w, h, seg_zoom)                   │
│      ├─ get_pan_direction(index)                                    │
│      ├─ get_start_end_coords(...)                                   │
│      │                                                              │
│      └─ segments_info.append({                                      │
│            "source_image": ...,                                     │
│            "crop_w": crop_w,    ◄── computed with seg_zoom          │
│            "crop_h": crop_h,    ◄── computed with seg_zoom          │
│            "start_coords": ...,                                     │
│            "end_coords": ...,                                       │
│            ...                                                      │
│         })                                                          │
│                                                                     │
│  Phase 4 (frame loop): No changes needed — crop_w/crop_h are       │
│  already stored per-segment in segments_info[].                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.4 Frontend Component Hierarchy

```
┌──────────────────────────────────────────────────────┐
│  ProjectPage                                          │
│  └── Timeline                                         │
│      └── SegmentCard (for each segment)               │
│          ├── Header (index badge, lock, menu)         │
│          ├── SegmentTextEditor                        │
│          ├── ImageUploader + ImagePromptDisplay       │
│          ├── AudioPlayer + GenerateAudioButton        │
│          ├── ZoomIntensitySlider        ◄── NEW       │
│          │   ├── Label: "Zoom Intensity"              │
│          │   ├── Slider [1.0 — 2.0]                   │
│          │   ├── Current value display (e.g. "1.3×")  │
│          │   └── "Reset to default" button            │
│          └── Footer / Actions                         │
└──────────────────────────────────────────────────────┘
```

---

## 3. Step-by-Step Instructions

### Step 1: Add `zoom_intensity` Field to `Segment` Model

**File:** `backend/api/models.py`  
**Location:** `Segment` model class, after `is_locked` field (line ~140)

#### 1.1 Current Code (lines 130–143)

```python
class Segment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='segments')
    sequence_index = models.IntegerField(default=0)
    text_content = models.TextField(blank=True, default='')
    image_prompt = models.TextField(blank=True, default='')
    image_file = models.ImageField(upload_to=segment_image_path, blank=True, null=True)
    audio_file = models.FileField(upload_to=segment_audio_path, blank=True, null=True)
    audio_duration = models.FloatField(null=True, blank=True)
    is_locked = models.BooleanField(default=False)
```

#### 1.2 Add After `is_locked`

```python
    is_locked = models.BooleanField(default=False)

    # Per-segment zoom intensity override.
    # NULL → inherit from Project.zoom_intensity (default behaviour).
    # Explicit value (e.g. 1.5) → override for this segment only.
    zoom_intensity = models.FloatField(null=True, blank=True, default=None)
```

#### 1.3 Why `null=True, blank=True, default=None`?

- **`null=True`** — Allows the database column to store `NULL`,
  meaning "no override; use project default."
- **`blank=True`** — Allows the field to be omitted in forms
  and API requests (not required).
- **`default=None`** — New segments start with `NULL`, which
  preserves backward compatibility — they'll use the project-level
  zoom just like before.

#### 1.4 Validation Consideration

The model itself does not enforce a range.  We rely on the
**serializer** (Step 2) to validate that the value, if provided,
is between 1.0 and 2.0.  The renderer (Step 5) also includes a
defensive clamp.

---

### Step 2: Update `SegmentSerializer`

**File:** `backend/api/serializers.py`  
**Location:** `SegmentSerializer` class (line ~52)

#### 2.1 Current Code

```python
class SegmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Segment
        fields = [
            'id', 'project', 'sequence_index', 'text_content',
            'image_prompt', 'image_file', 'audio_file',
            'audio_duration', 'is_locked',
        ]
        read_only_fields = [
            'id', 'project', 'sequence_index',
            'image_file', 'audio_file', 'audio_duration',
        ]
```

#### 2.2 Updated Code

```python
class SegmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Segment
        fields = [
            'id', 'project', 'sequence_index', 'text_content',
            'image_prompt', 'image_file', 'audio_file',
            'audio_duration', 'is_locked', 'zoom_intensity',
        ]
        read_only_fields = [
            'id', 'project', 'sequence_index',
            'image_file', 'audio_file', 'audio_duration',
        ]

    def validate_zoom_intensity(self, value):
        """Validate zoom_intensity if provided (not None)."""
        if value is None:
            return value  # NULL means "use project default"
        if value < 1.0 or value > 2.0:
            raise serializers.ValidationError(
                "zoom_intensity must be between 1.0 and 2.0 "
                "(or null to use project default)."
            )
        return round(value, 2)  # Normalize to 2 decimal places
```

#### 2.3 Key Points

- `zoom_intensity` is added to `fields` but NOT to `read_only_fields`,
  so it can be written via PATCH requests.
- The `validate_zoom_intensity` method is a DRF field-level validator
  that fires automatically when the field is present in the request.
- `None` / `null` is explicitly allowed (maps to "use project default").
- Values are clamped to the range `[1.0, 2.0]` with a validation
  error outside that range.
- Values are rounded to 2 decimal places for consistency.

---

### Step 3: Generate and Apply Django Migration

**Directory:** `backend/`

#### 3.1 Command

```bash
cd backend
python manage.py makemigrations api -n add_segment_zoom_intensity
python manage.py migrate
```

#### 3.2 Expected Migration

Django will auto-generate a migration file like:

```python
# backend/api/migrations/XXXX_add_segment_zoom_intensity.py

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '<previous_migration>'),
    ]

    operations = [
        migrations.AddField(
            model_name='segment',
            name='zoom_intensity',
            field=models.FloatField(blank=True, default=None, null=True),
        ),
    ]
```

#### 3.3 Verification

After running `migrate`, verify the column exists:

```bash
python manage.py shell -c "
from api.models import Segment
print(Segment._meta.get_field('zoom_intensity'))
print('nullable:', Segment._meta.get_field('zoom_intensity').null)
"
```

Expected output:

```
api.Segment.zoom_intensity
nullable: True
```

---

### Step 4: No Changes Needed in `views.py`

**File:** `backend/api/views.py`

The existing segment CRUD views use `SegmentSerializer` generically.
Since we added `zoom_intensity` to the serializer's `fields` (and it
is writable), the following operations work automatically:

- **GET** `/api/segments/{id}/` → Returns `zoom_intensity` (null or float)
- **PATCH** `/api/segments/{id}/` with `{"zoom_intensity": 1.5}` → Sets override
- **PATCH** `/api/segments/{id}/` with `{"zoom_intensity": null}` → Clears override
- **GET** `/api/projects/{id}/` → `segments[]` includes `zoom_intensity`

No view code changes are required.

---

### Step 5: Pass Per-Segment Zoom in `render_project()`

**File:** `backend/core_engine/video_renderer.py`  
**Function:** `render_project()` at line ~582  
**Location:** Segment data collection loop at lines 798–862

#### 5.1 Current Code (lines 854–860)

```python
            segment_data_list.append({
                "image_path": image_path,
                "audio_duration": audio_duration,
                "text_content": text_content,
                "sequence_index": segment.sequence_index,
            })
```

#### 5.2 Updated Code

```python
            # Resolve effective zoom: per-segment override → project default
            seg_zoom = segment.zoom_intensity
            if seg_zoom is None or seg_zoom <= 0:
                seg_zoom = zoom_intensity  # project-level default

            segment_data_list.append({
                "image_path": image_path,
                "audio_duration": audio_duration,
                "text_content": text_content,
                "sequence_index": segment.sequence_index,
                "zoom_intensity": seg_zoom,
            })
```

#### 5.3 Explanation

- `segment.zoom_intensity` reads the new database field.
- If `None` (not set), falls back to `zoom_intensity`, which is the
  project-level value already read at line ~652.
- The effective zoom is embedded directly in the segment data dict,
  so downstream consumers don't need to know about the fallback logic.

#### 5.4 Logging (Optional Enhancement)

Add a log line to confirm per-segment zoom is being used:

```python
            logger.info(
                "%s: effective zoom_intensity=%.2f (segment=%s, project=%.2f)",
                seg_label, seg_zoom,
                segment.zoom_intensity, zoom_intensity,
            )
```

---

### Step 6: Update `fast_render_segments()` to Use Per-Segment Zoom

**File:** `backend/core_engine/fast_compositor.py`  
**Function:** `fast_render_segments()` at line ~488  
**Location:** Phase 1 segment descriptor loop (lines 563–606)

#### 6.1 Current Code (lines 589–597)

```python
        # Prepare Ken Burns frame generator
        source_image = load_and_prepare_image(
            seg["image_path"], resolution, zoom_intensity,
        )
        src_h, src_w = source_image.shape[:2]
        crop_w, crop_h = calculate_crop_dimensions(width, height, zoom_intensity)
        start_name, end_name = get_pan_direction(seg["sequence_index"])
```

#### 6.2 Updated Code

```python
        # Resolve per-segment zoom (falls back to global if not present)
        seg_zoom = seg.get("zoom_intensity", zoom_intensity)

        # Prepare Ken Burns frame generator
        source_image = load_and_prepare_image(
            seg["image_path"], resolution, seg_zoom,
        )
        src_h, src_w = source_image.shape[:2]
        crop_w, crop_h = calculate_crop_dimensions(width, height, seg_zoom)
        start_name, end_name = get_pan_direction(seg["sequence_index"])
```

#### 6.3 Key Points

- `seg.get("zoom_intensity", zoom_intensity)` — reads the per-segment
  value from the segment data dict.  Falls back to the function-level
  `zoom_intensity` parameter if the key is missing.
- This is the **only line** that determines which zoom factor is used
  for the Ken Burns image preparation and crop calculation.
- No changes needed in Phase 4 (frame loop) because `crop_w`,
  `crop_h`, `start_coords`, and `end_coords` are already stored
  per-segment in `segments_info[]`.
- The function signature does **not** change — the `zoom_intensity`
  parameter remains as the global fallback.

#### 6.4 Logging (Optional Enhancement)

```python
        logger.info(
            "Segment %d/%d: zoom_intensity=%.2f (per-segment=%s, global=%.2f)",
            idx + 1, total_segments, seg_zoom,
            seg.get("zoom_intensity"), zoom_intensity,
        )
```

---

### Step 7: Verify Ken Burns Functions — No Changes Needed

**File:** `backend/core_engine/ken_burns.py`

Both `load_and_prepare_image()` (line 76) and
`calculate_crop_dimensions()` (line 196) already accept
`zoom_intensity` as a parameter.  They do not read any global
state — they use only the value passed to them.

```python
def load_and_prepare_image(
    image_path: str,
    resolution: Tuple[int, int],
    zoom_intensity: float,          # ← already parameterized
) -> np.ndarray:
```

```python
def calculate_crop_dimensions(
    output_width: int,
    output_height: int,
    zoom_intensity: float,          # ← already parameterized
) -> Tuple[int, int]:
```

Since Step 6 passes the per-segment zoom value into these functions,
no changes to `ken_burns.py` are required.

The legacy `apply_ken_burns()` function (line 497) also accepts
`zoom_intensity` as a parameter and forwards it to both helpers,
so if any code path still uses it, per-segment zoom will work
there too (once the caller passes the correct value).

---

### Step 8: Update Frontend TypeScript Types

**File:** `frontend/lib/types.ts`

#### 8.1 Update `Segment` Interface (line ~51)

**Current:**

```typescript
export interface Segment {
  id: string;
  project: string;
  sequence_index: number;
  text_content: string;
  image_prompt: string;
  image_file: string | null;
  audio_file: string | null;
  audio_duration: number | null;
  is_locked: boolean;
}
```

**Updated:**

```typescript
export interface Segment {
  id: string;
  project: string;
  sequence_index: number;
  text_content: string;
  image_prompt: string;
  image_file: string | null;
  audio_file: string | null;
  audio_duration: number | null;
  is_locked: boolean;
  zoom_intensity: number | null;
}
```

#### 8.2 Update `UpdateSegmentPayload` Interface (line ~111)

**Current:**

```typescript
export interface UpdateSegmentPayload {
  text_content?: string;
  image_prompt?: string;
  is_locked?: boolean;
}
```

**Updated:**

```typescript
export interface UpdateSegmentPayload {
  text_content?: string;
  image_prompt?: string;
  is_locked?: boolean;
  zoom_intensity?: number | null;
}
```

#### 8.3 Key Points

- `zoom_intensity: number | null` on `Segment` — matches the nullable
  backend field (`null` = use project default).
- `zoom_intensity?: number | null` on `UpdateSegmentPayload` — the `?`
  makes it optional so existing PATCH calls that only update
  `text_content` or `is_locked` remain unaffected.

---

### Step 9: Add Zoom Intensity Slider to SegmentCard

**File:** `frontend/components/SegmentCard.tsx`

#### 9.1 Import Slider Component

At the top of the file (after existing imports):

```typescript
import { Slider } from '@/components/ui/slider';
import { Label } from '@/components/ui/label';
import { ZoomIn } from 'lucide-react';
```

> **Note:** Ensure `@/components/ui/slider` exists (it's a standard
> shadcn/ui component).  If not, generate it:
> ```bash
> cd frontend && npx shadcn@latest add slider
> ```

#### 9.2 Add State and Callback

Inside `SegmentCardComponent` (after existing state declarations
around line ~65):

```typescript
  // Zoom intensity state
  const [localZoom, setLocalZoom] = useState<number | null>(segment.zoom_intensity);

  // Sync local state when segment prop changes (e.g. after API response)
  React.useEffect(() => {
    setLocalZoom(segment.zoom_intensity);
  }, [segment.zoom_intensity]);

  // Debounced handler to avoid excessive API calls while sliding
  const zoomUpdateTimeout = React.useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleZoomChange = useCallback((value: number[]) => {
    const newZoom = value[0];
    setLocalZoom(newZoom);

    // Debounce the API call
    if (zoomUpdateTimeout.current) {
      clearTimeout(zoomUpdateTimeout.current);
    }
    zoomUpdateTimeout.current = setTimeout(() => {
      onUpdate(segment.id, { zoom_intensity: newZoom });
    }, 300);
  }, [onUpdate, segment.id]);

  const handleResetZoom = useCallback(() => {
    setLocalZoom(null);
    onUpdate(segment.id, { zoom_intensity: null });
  }, [onUpdate, segment.id]);

  // Cleanup timeout on unmount
  React.useEffect(() => {
    return () => {
      if (zoomUpdateTimeout.current) {
        clearTimeout(zoomUpdateTimeout.current);
      }
    };
  }, []);
```

#### 9.3 Add Slider UI

Add the following JSX block inside the `<Card>` component, after the
existing audio section and before the card closing tag.  A good
location is after the `<Separator />` following the audio controls:

```tsx
      {/* Zoom Intensity Control */}
      <Separator />
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label className="flex items-center gap-1.5 text-sm text-muted-foreground">
            <ZoomIn className="h-3.5 w-3.5" />
            Zoom Intensity
          </Label>
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono tabular-nums text-muted-foreground">
              {localZoom !== null ? `${localZoom.toFixed(1)}×` : 'Default'}
            </span>
            {localZoom !== null && (
              <Button
                variant="ghost"
                size="sm"
                className="h-6 px-2 text-xs"
                onClick={handleResetZoom}
                disabled={isGenerating}
              >
                Reset
              </Button>
            )}
          </div>
        </div>
        <Slider
          min={1.0}
          max={2.0}
          step={0.05}
          value={[localZoom ?? 1.3]}
          onValueChange={handleZoomChange}
          disabled={segment.is_locked || isGenerating}
          className="cursor-pointer"
        />
        <div className="flex justify-between text-[10px] text-muted-foreground/60">
          <span>1.0× (no zoom)</span>
          <span>1.5× (moderate)</span>
          <span>2.0× (dramatic)</span>
        </div>
      </div>
```

#### 9.4 Visual Behaviour

| State | Slider Appearance |
|-------|-------------------|
| `zoom_intensity = null` | Slider at project default (1.3), label says "Default" |
| `zoom_intensity = 1.5` | Slider at 1.5, label says "1.5×", Reset button visible |
| Segment is locked | Slider is disabled (greyed out) |
| Segment is generating audio | Slider is disabled |

#### 9.5 UX Notes

- The slider uses `step={0.05}` for fine-grained control while still
  being easy to use on touch/trackpad.
- The debounce (300ms) prevents spamming the API with PATCH requests
  while the user is still dragging.
- On "Reset", the value is set back to `null`, which the backend
  interprets as "use project default."
- The scale labels ("no zoom", "moderate", "dramatic") give users
  intuitive guidance without requiring documentation.

---

## 4. Expected Outcome

### 4.1 Backend Behaviour

After implementation, the following should hold true:

1. **Database**: The `api_segment` table has a new nullable column
   `zoom_intensity` of type `REAL` (SQLite) or `DOUBLE PRECISION`
   (PostgreSQL).

2. **API Response**: `GET /api/projects/{id}/` returns segments with
   the `zoom_intensity` field:
   ```json
   {
     "segments": [
       {
         "id": "abc-123",
         "sequence_index": 0,
         "zoom_intensity": null,
         ...
       },
       {
         "id": "def-456",
         "sequence_index": 1,
         "zoom_intensity": 1.5,
         ...
       }
     ]
   }
   ```

3. **PATCH**: Setting per-segment zoom works:
   ```bash
   curl -X PATCH /api/segments/def-456/ \
     -H "Content-Type: application/json" \
     -d '{"zoom_intensity": 1.5}'
   ```
   Response: `200 OK` with updated segment including `"zoom_intensity": 1.5`

4. **PATCH**: Clearing per-segment zoom works:
   ```bash
   curl -X PATCH /api/segments/def-456/ \
     -H "Content-Type: application/json" \
     -d '{"zoom_intensity": null}'
   ```
   Response: `200 OK` with `"zoom_intensity": null`

5. **Validation**: Out-of-range values are rejected:
   ```bash
   curl -X PATCH /api/segments/def-456/ \
     -H "Content-Type: application/json" \
     -d '{"zoom_intensity": 3.0}'
   ```
   Response: `400 Bad Request` with validation error message.

### 4.2 Render Behaviour

1. **Segment with `zoom_intensity = null`**: Renders with the
   project-level zoom_intensity (e.g. 1.3).  Visually identical to
   current behaviour.

2. **Segment with `zoom_intensity = 1.5`**: Renders with a tighter
   crop (more zoomed in).  The Ken Burns pan-and-zoom feels more
   dramatic — the camera appears to push in closer to the subject.

3. **Segment with `zoom_intensity = 1.05`**: Renders with a very
   wide crop (barely zoomed).  The Ken Burns effect is subtle —
   the camera gently drifts, creating a calm, wide-angle feel.

4. **Mixed project** (some segments overridden, some not):
   Each segment uses its own effective zoom.  Transitions between
   segments with different zoom levels create a natural cinematic
   rhythm.

### 4.3 Frontend Behaviour

1. **SegmentCard** displays a zoom slider below the audio controls.
2. When the slider is untouched (null), the label shows "Default".
3. Dragging the slider updates the value locally with debouncing,
   then sends a PATCH to update the backend.
4. A "Reset" button appears when a custom zoom is set, allowing
   the user to return to the project default.
5. Locked segments have the slider disabled.

### 4.4 Backward Compatibility

- **Existing segments**: All have `zoom_intensity = NULL` after
  migration → zero behaviour change.
- **Existing API consumers**: Responses now include `zoom_intensity`
  (a new field), which is additive and non-breaking.
- **Existing render pipeline**: If `segment_data_list` entries lack
  `zoom_intensity` (e.g. from an older code path), the fast
  compositor falls back to the function-level `zoom_intensity`
  parameter — exactly the current behaviour.

---

## 5. Verification Checklist

### 5.1 Model & Migration

- [ ] `Segment` model in `backend/api/models.py` has
      `zoom_intensity = models.FloatField(null=True, blank=True, default=None)`
- [ ] Migration file exists in `backend/api/migrations/`
- [ ] `python manage.py migrate` runs without errors
- [ ] `python manage.py shell` confirms field exists on `Segment`:
      ```python
      from api.models import Segment
      assert Segment._meta.get_field('zoom_intensity').null is True
      ```
- [ ] Existing segments have `zoom_intensity = None` (not modified)

### 5.2 Serializer

- [ ] `SegmentSerializer.Meta.fields` includes `'zoom_intensity'`
- [ ] `zoom_intensity` is NOT in `read_only_fields`
- [ ] `validate_zoom_intensity()` rejects values < 1.0
- [ ] `validate_zoom_intensity()` rejects values > 2.0
- [ ] `validate_zoom_intensity()` accepts `None` / `null`
- [ ] `validate_zoom_intensity()` accepts values in `[1.0, 2.0]`
- [ ] Values are rounded to 2 decimal places (e.g. 1.333 → 1.33)

### 5.3 API

- [ ] `GET /api/segments/{id}/` includes `zoom_intensity` in response
- [ ] `PATCH /api/segments/{id}/` with `{"zoom_intensity": 1.5}` succeeds
- [ ] `PATCH /api/segments/{id}/` with `{"zoom_intensity": null}` succeeds
- [ ] `PATCH /api/segments/{id}/` with `{"zoom_intensity": 0.5}` returns 400
- [ ] `PATCH /api/segments/{id}/` with `{"zoom_intensity": 2.5}` returns 400
- [ ] `GET /api/projects/{id}/` → segments include `zoom_intensity`
- [ ] Existing PATCH calls (e.g. updating `text_content` only) still work

### 5.4 Render Pipeline — video_renderer.py

- [ ] `render_project()` reads `segment.zoom_intensity` for each segment
- [ ] Per-segment zoom falls back to project zoom when segment value is `None`
- [ ] `segment_data_list` entries include `"zoom_intensity"` key
- [ ] Log output shows effective zoom per segment

### 5.5 Render Pipeline — fast_compositor.py

- [ ] Phase 1 reads `seg.get("zoom_intensity", zoom_intensity)`
- [ ] `load_and_prepare_image()` receives per-segment zoom
- [ ] `calculate_crop_dimensions()` receives per-segment zoom
- [ ] Built `segments_info[]` entries have correct per-segment crop dimensions
- [ ] Rendering a project with mixed zoom values produces visually
      different Ken Burns intensities across segments

### 5.6 Frontend Types

- [ ] `Segment` interface includes `zoom_intensity: number | null`
- [ ] `UpdateSegmentPayload` includes `zoom_intensity?: number | null`
- [ ] TypeScript compiles without errors

### 5.7 Frontend UI

- [ ] Slider component exists in `@/components/ui/slider`
- [ ] SegmentCard renders zoom slider below audio controls
- [ ] Slider range is 1.0 to 2.0 with step 0.05
- [ ] Label shows "Default" when zoom is null
- [ ] Label shows "1.5×" format when zoom is set
- [ ] "Reset" button appears when zoom is set
- [ ] "Reset" button sends `{ zoom_intensity: null }` to API
- [ ] Slider is disabled when segment is locked
- [ ] Slider is disabled when audio is generating
- [ ] Debounce prevents rapid API calls while sliding
- [ ] Slider value syncs when segment prop changes from parent

### 5.8 End-to-End Render Test

- [ ] Create a project with 3+ segments
- [ ] Set segment 0: zoom = null (default)
- [ ] Set segment 1: zoom = 1.5
- [ ] Set segment 2: zoom = 1.05
- [ ] Render the project
- [ ] Observe segment 1 has noticeably tighter (more dramatic) zoom
- [ ] Observe segment 2 has noticeably wider (calmer) zoom
- [ ] Observe segment 0 looks the same as before (project default)
- [ ] Transitions between segments render without errors
- [ ] Audio sync is unaffected by zoom changes

---

## 6. Notes for AI Agent

### 6.1 Implementation Order

Follow the steps in exact order:

1. **Model** (Step 1) — Must be first so the migration can be created.
2. **Migration** (Step 3) — Must run before serializer changes are tested.
3. **Serializer** (Step 2) — Add field and validator.
4. **video_renderer.py** (Step 5) — Pass per-segment zoom to data list.
5. **fast_compositor.py** (Step 6) — Read per-segment zoom in Phase 1.
6. **Frontend types** (Step 8) — Update TypeScript interfaces.
7. **Frontend UI** (Step 9) — Add slider to SegmentCard.
8. **Verify** (Step 4, Step 7) — Confirm no-change files.

### 6.2 Critical Code Patterns

#### Pattern A: Nullable Float Field in Django

```python
# CORRECT — nullable with None default (segment inherits project value)
zoom_intensity = models.FloatField(null=True, blank=True, default=None)

# WRONG — non-nullable with 0.0 default (can't distinguish "not set" from "set to 0")
zoom_intensity = models.FloatField(default=0.0)

# WRONG — non-nullable with 1.3 default (can't distinguish "not set" from "explicitly 1.3")
zoom_intensity = models.FloatField(default=1.3)
```

#### Pattern B: Fallback Chain in Python

```python
# CORRECT — explicit None check with fallback
seg_zoom = segment.zoom_intensity
if seg_zoom is None or seg_zoom <= 0:
    seg_zoom = zoom_intensity  # project-level default

# WRONG — truthiness check (0.0 would also trigger fallback)
seg_zoom = segment.zoom_intensity or zoom_intensity

# WRONG — no fallback (would pass None to ken_burns functions)
seg_zoom = segment.zoom_intensity
```

#### Pattern C: Dict `.get()` Fallback in Fast Compositor

```python
# CORRECT — falls back to function parameter if key missing
seg_zoom = seg.get("zoom_intensity", zoom_intensity)

# WRONG — would return None if key missing, then break ken_burns
seg_zoom = seg.get("zoom_intensity")

# WRONG — hardcoded fallback instead of using function parameter
seg_zoom = seg.get("zoom_intensity", 1.3)
```

#### Pattern D: TypeScript Nullable Type

```typescript
// CORRECT — matches backend nullable float
zoom_intensity: number | null;

// WRONG — undefined is different from null in JSON
zoom_intensity?: number;

// WRONG — 0 is a valid number, can't distinguish from "not set"
zoom_intensity: number;
```

### 6.3 Files You Must NOT Modify

- `backend/core_engine/ken_burns.py` — Functions already accept
  `zoom_intensity` as a parameter; no changes needed.
- `backend/api/views.py` — The serializer handles the new field
  automatically through DRF's generic views.
- `backend/api/urls.py` — No new endpoints needed.
- `frontend/lib/api.ts` — Uses `UpdateSegmentPayload` generically;
  adding the field to the type is sufficient.
- `frontend/lib/stores.ts` — `updateSegment` already accepts
  `UpdateSegmentPayload` generically.

### 6.4 Edge Cases to Handle

| Edge Case | Expected Behaviour |
|-----------|-------------------|
| Segment zoom = `null`, project zoom = `1.3` | Effective zoom = 1.3 |
| Segment zoom = `1.5`, project zoom = `1.3` | Effective zoom = 1.5 |
| Segment zoom = `1.0` (no zoom) | Effective zoom = 1.0, crop = full resolution |
| Segment zoom = `2.0` (maximum) | Effective zoom = 2.0, tight crop |
| Old `segment_data_list` without `zoom_intensity` key | `seg.get("zoom_intensity", zoom_intensity)` falls back to global |
| API request with `zoom_intensity: 0` | Rejected by serializer (< 1.0) |
| API request with `zoom_intensity: -1` | Rejected by serializer (< 1.0) |
| API request with `zoom_intensity: 2.5` | Rejected by serializer (> 2.0) |
| API request without `zoom_intensity` key | Field unchanged (PATCH is partial) |
| Multiple rapid slider drags | Debounced — only last value sent |

### 6.5 Testing Suggestions

#### Unit Tests (Backend)

```python
# backend/api/tests/test_segment_zoom.py

from django.test import TestCase
from api.models import Project, Segment

class SegmentZoomIntensityTests(TestCase):
    def setUp(self):
        self.project = Project.objects.create(title="Test", zoom_intensity=1.3)

    def test_default_zoom_is_none(self):
        seg = Segment.objects.create(project=self.project, sequence_index=0)
        self.assertIsNone(seg.zoom_intensity)

    def test_explicit_zoom_is_stored(self):
        seg = Segment.objects.create(
            project=self.project, sequence_index=0, zoom_intensity=1.5
        )
        seg.refresh_from_db()
        self.assertEqual(seg.zoom_intensity, 1.5)

    def test_zoom_can_be_cleared(self):
        seg = Segment.objects.create(
            project=self.project, sequence_index=0, zoom_intensity=1.5
        )
        seg.zoom_intensity = None
        seg.save()
        seg.refresh_from_db()
        self.assertIsNone(seg.zoom_intensity)
```

#### Serializer Tests

```python
from rest_framework.test import APITestCase

class SegmentSerializerZoomTests(APITestCase):
    def test_patch_zoom_valid(self):
        # Create project + segment, then PATCH with valid zoom
        response = self.client.patch(
            f'/api/segments/{seg_id}/',
            {'zoom_intensity': 1.5},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['zoom_intensity'], 1.5)

    def test_patch_zoom_null(self):
        response = self.client.patch(
            f'/api/segments/{seg_id}/',
            {'zoom_intensity': None},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data['zoom_intensity'])

    def test_patch_zoom_out_of_range(self):
        response = self.client.patch(
            f'/api/segments/{seg_id}/',
            {'zoom_intensity': 3.0},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
```

#### Frontend Tests

```typescript
// frontend/__tests__/segment-zoom.test.ts

describe('Segment zoom_intensity', () => {
  it('should accept null zoom_intensity', () => {
    const segment: Segment = {
      ...baseSegment,
      zoom_intensity: null,
    };
    expect(segment.zoom_intensity).toBeNull();
  });

  it('should accept numeric zoom_intensity', () => {
    const segment: Segment = {
      ...baseSegment,
      zoom_intensity: 1.5,
    };
    expect(segment.zoom_intensity).toBe(1.5);
  });

  it('UpdateSegmentPayload should accept zoom_intensity', () => {
    const payload: UpdateSegmentPayload = {
      zoom_intensity: 1.5,
    };
    expect(payload.zoom_intensity).toBe(1.5);
  });

  it('UpdateSegmentPayload should accept null zoom_intensity', () => {
    const payload: UpdateSegmentPayload = {
      zoom_intensity: null,
    };
    expect(payload.zoom_intensity).toBeNull();
  });
});
```

### 6.6 Line Reference Summary

| File | Key Location | Line (approx.) | What's There |
|------|-------------|-----------------|--------------|
| `backend/api/models.py` | `Segment` class | L130 | Model definition — add field here |
| `backend/api/models.py` | `is_locked` field | L140 | Last current Segment field — add after this |
| `backend/api/serializers.py` | `SegmentSerializer` | L52 | Serializer — add field + validator |
| `backend/core_engine/video_renderer.py` | `render_project()` | L582 | Main render function |
| `backend/core_engine/video_renderer.py` | `segment_data_list.append()` | L854 | Add `zoom_intensity` to dict |
| `backend/core_engine/video_renderer.py` | `zoom_intensity = ...` | L652 | Project-level zoom read |
| `backend/core_engine/fast_compositor.py` | `fast_render_segments()` | L488 | Function signature (keep as-is) |
| `backend/core_engine/fast_compositor.py` | `load_and_prepare_image()` call | L590 | Replace `zoom_intensity` → `seg_zoom` |
| `backend/core_engine/fast_compositor.py` | `calculate_crop_dimensions()` call | L595 | Replace `zoom_intensity` → `seg_zoom` |
| `backend/core_engine/ken_burns.py` | `load_and_prepare_image()` | L76 | Already parameterized — no change |
| `backend/core_engine/ken_burns.py` | `calculate_crop_dimensions()` | L196 | Already parameterized — no change |
| `frontend/lib/types.ts` | `Segment` interface | L51 | Add `zoom_intensity` field |
| `frontend/lib/types.ts` | `UpdateSegmentPayload` | L111 | Add optional `zoom_intensity` |
| `frontend/components/SegmentCard.tsx` | `SegmentCardComponent` | L41 | Add slider UI |

### 6.7 Potential Future Enhancements

These are NOT part of this feature but could be built on top of it:

1. **Bulk zoom preset** — Apply a zoom profile (e.g. "dramatic arc":
   1.1, 1.2, 1.4, 1.5, 1.3 across segments) with one click.
2. **AI-driven zoom** — Analyze image content (faces, text, landscapes)
   to automatically suggest optimal zoom per segment.
3. **Zoom preview** — Show a tiny Ken Burns animation preview in the
   SegmentCard when the user adjusts the slider.
4. **Per-segment ken_burns_zoom** — Similar pattern for the
   `ken_burns_zoom` project-level field, allowing even more granular
   camera control.
5. **Zoom curve** — Instead of a single zoom factor, define start/end
   zoom values per segment (zoom-in vs zoom-out vs static).
6. **Copy zoom to all segments** — Right-click context menu option to
   apply one segment's zoom to all others in the project.

### 6.8 Rollback Plan

If this feature causes issues:

1. **Backend**: Remove the `zoom_intensity` field from the `Segment`
   model and create a reverse migration:
   ```bash
   python manage.py makemigrations api -n remove_segment_zoom_intensity
   python manage.py migrate
   ```
2. **Serializer**: Remove `zoom_intensity` from `fields` and delete
   the `validate_zoom_intensity` method.
3. **video_renderer.py**: Revert the data collection loop to not
   include `zoom_intensity` in `segment_data_list`.
4. **fast_compositor.py**: Revert to using the function-parameter
   `zoom_intensity` directly instead of `seg.get(...)`.
5. **Frontend**: Remove `zoom_intensity` from TypeScript types and
   remove the slider from SegmentCard.

The fast compositor's `.get()` fallback pattern means the backend
changes are safe to partially revert — if `zoom_intensity` is
missing from segment data, it falls back to the global value
automatically.

---

*End of Feature 2.4 — Zoom Level Control Per Segment*
