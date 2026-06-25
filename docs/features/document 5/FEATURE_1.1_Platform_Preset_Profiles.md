# Feature 1.1 — Platform Preset Profiles

| Field | Value |
|---|---|
| Feature ID | 1.1 |
| Title | Platform Preset Profiles |
| Status | 🟡 Planned |
| Priority | High |
| Complexity | Low |
| Estimated Effort | 2–3 days |
| Dependencies | None |
| Output Files (NEW) | frontend/constants/platformPresets.ts, backend/api/constants.py |
| Files Modified | backend/api/models.py, backend/api/serializers.py, backend/api/views.py, frontend/app/projects/[id]/page.tsx, frontend/app/settings/page.tsx |

---

## 1. Document Overview

### 1.1 Problem Statement

Currently, users must manually configure resolution, aspect ratio, frames-per-second, bitrate, and codec every time they create a new project targeting a specific platform, which demands a level of technical encoding knowledge that most content creators do not have.
Each social media platform maintains its own distinct optimal encoding requirements — TikTok requires 1080×1920 portrait orientation at 30fps with H.264 encoding up to 8Mbps, while YouTube expects 1920×1080 landscape with up to 16Mbps — and these specifications change periodically without notice to creators.
Creators waste significant time researching platform-specific requirements before each project, and risk uploading incorrectly-configured videos that platforms may silently transcode to lower quality, deprioritize in algorithmic distribution, or in some cases reject outright.
There is no guided workflow in StoryFlow to validate that the output video matches platform standards before the rendering process begins, meaning rendering failures or quality downgrades are only discovered after time-intensive CPU work has already completed.

### 1.2 Proposed Solution

The Platform Preset Profiles feature introduces a first-class concept of "target platform" into every StoryFlow project, giving creators a single dropdown selection that automatically configures all rendering parameters to match the chosen platform's documented requirements. Rather than demanding technical encoding knowledge from the creator, the system encodes best-practice specifications into a centralized constant registry maintained on both the frontend and the backend, ensuring that those specifications are applied consistently at both the display layer and the render pipeline layer. The preset is designed as a smart starting point that populates fields rather than locking them, so experienced users who need a non-standard configuration can still override individual parameters after the preset is applied. A badge system on the project list surface gives at-a-glance platform identification across multiple projects, and an estimated file-size calculation gives creators a realistic expectation of output volume before they commit time to rendering.

- A new `target_platform` field is added to the `Project` model as a CharField with enumerated choices, stored as a short platform key string in the SQLite database.
- A frontend TypeScript constants file maps each platform key to a full typed specification object including width, height, aspect ratio string, fps, bitrate in kilobits per second, codec, and maximum duration where applicable.
- A backend Python constants file mirrors the specification as a native dictionary inside `backend/api/constants.py` to supply encoding parameters directly to the FFmpeg command builder without any frontend involvement.
- The project editor page gains a clearly labeled "Platform" dropdown that, on change, reads the matching preset and programmatically fills the resolution, fps, and codec fields in the settings panel.
- A rendered platform badge appears next to each project title in the project list, using a visually distinct colored label that allows creators to scan their library and identify platform targets at a glance.
- An "Estimated render size" stat label is displayed dynamically on the project editor, computed from the preset bitrate multiplied by an estimated total duration derived from the current segment count.
- Individual parameters remain fully editable after a preset is applied, and user overrides take priority over preset defaults in the render pipeline, ensuring power users are never constrained by automation.

### 1.3 Scope

| Category | Item |
|---|---|
| In Scope | Adding `target_platform` CharField with choices to the Project model and running migration |
| In Scope | Creating the frontend platform preset constants file with all eight platform entries |
| In Scope | Auto-populating resolution, FPS, and codec fields in the project editor on platform selection |
| In Scope | Displaying a platform badge on the project list and an estimated render size indicator on the editor |
| Out of Scope | Automatic video upload or publishing to any social media platform |
| Out of Scope | OAuth integration or any form of social media API authentication |
| Out of Scope | Allowing users to define and save custom platform presets beyond the eight built-in options |
| Out of Scope | Dynamic bitrate adjustment based on runtime encoder capability detection |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| backend/api/models.py | Defines the Project model and all its database-level fields | Exists; Project has render_settings JSONField but no target_platform field |
| backend/api/serializers.py | DRF serializers converting Project and Segment model instances to JSON | Exists; needs target_platform included in ProjectSerializer fields list |
| backend/api/views.py | DRF views that handle project CRUD and render job triggering | Exists; render trigger reads render_settings but currently has no preset-lookup step |
| frontend/app/projects/[id]/page.tsx | Main project editor page containing the settings panel | Exists; has resolution and FPS input fields but no platform selector or badge |
| frontend/constants/platformPresets.ts | Typed constants mapping platform keys to full encoding spec objects | Does not exist yet — must be created as part of this feature |
| backend/api/constants.py | Python dictionary of per-platform encoding specs for the render pipeline | Does not exist yet — must be created as part of this feature |

---

## 2. Flow Diagram

    User opens project editor page
                |
                v
    Platform Dropdown rendered in settings panel (top of form)
                |
         User selects "TikTok" from dropdown
                |
                v
    onChange handler fires in frontend
                |
                v
    Frontend reads PLATFORM_PRESETS["tiktok"]
    --> { width: 1080, height: 1920, fps: 30, bitrateKbps: 8000, codec: "H.264" }
                |
                v
    Resolution, FPS, Codec fields auto-populated in UI
                |
         User optionally overrides individual fields
                |
                v
    User clicks Save  -->  PATCH /api/projects/{id}/
    Body includes: target_platform="tiktok", plus current field values
                |
                v
    Backend stores target_platform = "tiktok" in database row
                |
                v
    Project list page renders badge "TikTok" next to project name
                |
                v
    User triggers render  -->  POST /api/projects/{id}/render/
                |
                v
    Backend imports PLATFORM_PRESETS from backend/api/constants.py
    Merges preset into render params (user overrides take priority)
                |
                v
    FFmpeg receives correct resolution, bitrate, and codec arguments

---

## 3. Step-by-Step Instructions

### Step 1 — Extend the Project Model with target_platform

Open `backend/api/models.py` and locate the `Project` model class definition.
Immediately above the class body, define a module-level `PLATFORM_CHOICES` tuple of two-tuples, where each entry is a pair of the database key string and the human-readable label — for example `("tiktok", "TikTok")`, covering all eight platforms: youtube, youtube_shorts, tiktok, instagram_reel, instagram_post, facebook, twitter_x, and linkedin.
Inside the Project class, add a new field `target_platform` defined as a `CharField` with `max_length=30`, `choices=PLATFORM_CHOICES`, `blank=True`, and `default=""` so that existing projects remain valid after migration and the field is optional on all project creation forms.
After saving the model, run `python manage.py makemigrations api` from inside the `backend/` directory to generate a new migration file, then run `python manage.py migrate` to apply the change to the SQLite database.
Open `backend/api/serializers.py` and add the string `"target_platform"` to the `fields` list in the `ProjectSerializer` Meta inner class so that the platform key is included in all project API responses and accepted in PATCH request bodies.
Verify the change by opening the Django admin panel or running a quick shell query to confirm the new column exists and accepts valid choice values without error.

### Step 2 — Create the Backend Constants File

Create a brand-new file at `backend/api/constants.py` — this file will serve as the single authoritative source of platform encoding parameters for the entire Python render pipeline.
At the top of the file, write a module-level docstring explaining that values are sourced from each platform's official creator documentation as of the document date, and that a corresponding frontend constants file must be kept manually in sync.
Define a Python dictionary named `PLATFORM_PRESETS` where each top-level key is the lowercase platform string matching the model choices (e.g., `"tiktok"`, `"youtube"`) and each value is a nested dictionary containing: `width` (int), `height` (int), `fps` (int), `bitrate_kbps` (int), `codec` (str), `aspect_ratio` (str), and `max_duration_seconds` (int or None for unlimited).
Populate all eight platform entries using the following specifications: YouTube — 1920×1080, 16:9, 30fps, 16000Kbps, H.264; YouTube Shorts — 1080×1920, 9:16, 30fps, 10000Kbps; TikTok — 1080×1920, 9:16, 30fps, 8000Kbps; Instagram Reel — 1080×1920, 9:16, 30fps, 8000Kbps, max 90s; Instagram Post — 1080×1080, 1:1, 30fps, 8000Kbps, max 60s; Facebook — 1920×1080, 16:9, 30fps, 16000Kbps; Twitter/X — 1920×1080, 16:9, 30fps, 6400Kbps, max 140s; LinkedIn — 1920×1080, 16:9, 30fps, 10000Kbps, max 600s.
No imports are needed in this file — keep it as a pure data module so it can be safely imported anywhere in the project without circular dependency risk.

### Step 3 — Create the Frontend Constants File

Create a brand-new file at `frontend/constants/platformPresets.ts` — this is a pure data module with no React imports, no side effects, and no runtime logic.
First, define a TypeScript interface named `PlatformPreset` containing the following typed properties: `label` (string), `width` (number), `height` (number), `aspectRatio` (string), `fps` (number), `bitrateKbps` (number), `codec` (string), `maxDurationSeconds` (number or null), and `description` (string, a short human-readable note about the platform's use case).
Then define and export a `PlatformKey` union type that enumerates all eight string literals plus an empty string `""` to represent the "no platform selected" state.
Export a `PLATFORM_PRESETS` constant typed as `Record<Exclude<PlatformKey, "">, PlatformPreset>` with all eight platform entries fully populated with the same specification values present in the backend constants file.
Export a second constant named `PLATFORM_OPTIONS` typed as `Array<{ value: PlatformKey; label: string }>`, which is derived by mapping over the `PLATFORM_PRESETS` entries and adding a leading `{ value: "", label: "No Platform" }` entry so the dropdown always has a neutral default option.
Add a comment at the top of the file noting that `backend/api/constants.py` must be updated whenever values in this file change, since the two files are manually synchronized for now.

### Step 4 — Add Platform Dropdown to the Project Editor

Open `frontend/app/projects/[id]/page.tsx` and locate the project settings form panel, which currently contains input fields for resolution, FPS, and codec.
Add a new labeled `select` element at the top of the settings panel, populated using the `PLATFORM_OPTIONS` array imported from `frontend/constants/platformPresets.ts`, with the current value bound to the project state's `target_platform` field.
Write an `onChange` handler for the dropdown that, when a real (non-empty) platform key is selected, retrieves the matching `PlatformPreset` from `PLATFORM_PRESETS` and dispatches updates to the component state or the Zustand project store to set the width, height, fps, and codec fields simultaneously in one operation.
When the user selects the empty "No Platform" option, the handler should reset the resolution and codec fields to their global default values — read these from `frontend/app/settings/page.tsx` or a separate defaults constant rather than hard-coding them.
After the user blurs or explicitly saves, dispatch a PATCH request to `/api/projects/{id}/` that includes `target_platform` in the request body so the selection is persisted in the database and restored correctly on the next page load.
Define a small inline `PLATFORM_COLORS` object inside the same file (or in a `lib/platformColors.ts` utility) mapping each platform key to a Tailwind background-color class, then render a small badge span next to the project title using the resolved class.

### Step 5 — Wire Preset Parameters into the Render Pipeline

Open `backend/api/views.py` and navigate to the view function or class method that handles the POST request to the render endpoint (e.g., a function that calls into `core_engine/video_renderer.py`).
At the beginning of the render logic, import `PLATFORM_PRESETS` from `backend/api/constants` using a relative import.
After the project object is fetched from the database, check whether `project.target_platform` is a non-empty string; if it is, retrieve the matching preset dictionary from `PLATFORM_PRESETS` and create a merged render-parameters dictionary that starts with the preset values.
Apply the user's explicit `render_settings` values on top of the preset values using a dict-update or dict-merge pattern that gives user-provided fields highest priority, so that any manual override survives the merge even when a platform is selected.
Pass the merged parameter dictionary to whichever function in `core_engine/` accepts render settings — update the call signature if necessary to accept an explicit resolution tuple alongside the existing settings dictionary.
Add a structured log line at the INFO level (using Python's standard `logging` module) that records the project ID, the applied platform key, and the final resolved dimensions so that render issues traceable to incorrect preset values can be diagnosed directly from server logs.

---

## 4. Expected Outcome

1. When a user opens any project in the editor, a clearly labeled "Platform" dropdown appears at the top of the settings panel and displays all eight supported platform options plus a blank "No Platform" default, requiring no documentation to understand.
2. Selecting a platform immediately and visibly updates the resolution width, height, FPS, and codec fields in the settings panel, providing instant visual confirmation that auto-population worked without any page reload.
3. The project list page renders a small colored badge next to each project name indicating the selected platform, making it trivially easy to scan a library of projects and identify which targets which destination.
4. When a project with a selected platform is rendered, the FFmpeg subprocess is launched with the correct platform-specific resolution and bitrate without any manual encoding parameter entry from the user.
5. A user who selects a platform and then manually edits the resolution field sees their custom value applied at render time — the preset is a helpful starting point, never an enforced constraint.
6. An "Estimated render size" label on the project editor reflects the current preset's bitrate multiplied by the segment-derived duration, displaying a human-friendly string such as "~320 MB for an estimated 5 minutes".
7. Both the frontend TypeScript file and the backend Python file serve as the solitary authoritative sources for platform encoding specifications, meaning a future platform requirement change requires only single-file edits on each layer.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] Test that `ProjectSerializer` correctly serializes and deserializes the `target_platform` field for all eight valid platform choice values without validation errors.
- [ ] Test that `PLATFORM_PRESETS` in `backend/api/constants.py` contains exactly eight keys and that every entry includes all required fields (`width`, `height`, `fps`, `bitrate_kbps`, `codec`, `aspect_ratio`, `max_duration_seconds`) with correct Python types.
- [ ] Test that the render view's merge logic correctly gives user-provided `render_settings` fields higher priority than preset fields when both define the same key.
- [ ] Test that when `project.target_platform` is blank or None, the render view falls back to using only the project's own `render_settings` without raising a KeyError.
- [ ] Test that `PLATFORM_OPTIONS` exported from `frontend/constants/platformPresets.ts` contains exactly nine entries (eight platforms plus the empty-string default) with non-empty `label` values on all real platform entries.

### 5.2 Integration / Manual Tests

- [ ] Create a new project, select "TikTok" from the platform dropdown, save the form, close and reopen the project editor page, then verify that the "TikTok" selection is still shown and the resolution fields display 1080×1920.
- [ ] Trigger a render on a TikTok-configured project, then inspect the Django server logs to confirm the INFO log line references `tiktok` and the resolved dimensions are 1080×1920.
- [ ] Select "YouTube" as the platform preset, then manually change the resolution width to 1280, trigger render, and confirm via server logs that 1280 is used rather than the preset 1920.
- [ ] Verify that existing projects created before this feature that have no `target_platform` value set complete a render without errors.
- [ ] Open the project list page with several projects of different platforms and confirm that each project displays the correct platform badge color, and projects with no platform show no badge.
- [ ] Verify that the "Estimated render size" label updates in real time when the user selects a different platform preset without saving, reflecting the new preset's bitrate.

### 5.3 Regression Tests

- [ ] Confirm that all existing project API endpoints (GET list, GET detail, POST create, PATCH update, DELETE) continue to function correctly and return expected response shapes after `target_platform` is added to the model and serializer.
- [ ] Confirm that the project editor page loads without JavaScript console errors for projects created before this feature, where `target_platform` arrives from the API as an empty string.
- [ ] Confirm that the render pipeline's existing `render_settings` JSONField behavior is entirely unaffected and that platform preset values are injected additively without overwriting or deleting any existing keys the user had already set.

---

## 6. Notes for AI Agent

- When adding `target_platform` to the Project model, always include both `blank=True` and `default=""` together so that the generated migration file does not prompt for a one-time default value and existing database rows receive an empty string automatically; omitting `default=""` in a Django CharField addition to an existing table is one of the most common migration errors.
- The frontend `onChange` handler for the platform dropdown must explicitly differentiate between the user selecting an actual platform key (which should trigger the auto-populate logic) and the user selecting the blank "No Platform" option (which must clear or reset the auto-populated fields back to global defaults rather than silently leaving stale preset values in the form).
- The estimated render size formula on the project editor is `bitrateKbps * 1000 / 8 / 1024 / 1024 * estimatedDurationSeconds` to produce a megabyte value — wrap this calculation in a named helper function inside `frontend/lib/renderEstimates.ts` rather than inlining it in the component, so it can be reused by the Production Dashboard feature without code duplication.
- Do not hard-code platform brand colors in multiple places across different component files; define them in a single `PLATFORM_COLORS` map inside `frontend/constants/platformColors.ts` and import that map wherever badge colors are needed, so a future brand color correction requires editing only one file.
- The backend `PLATFORM_PRESETS` dictionary and the frontend `PLATFORM_PRESETS` constant must be manually kept in sync for now — add a comment to the top of each file that explicitly names the other file as its required counterpart, making the synchronization obligation visible to any future developer who opens either file.
