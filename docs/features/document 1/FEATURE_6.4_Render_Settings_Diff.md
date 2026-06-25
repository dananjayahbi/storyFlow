# FEATURE 6.4 — Render Settings Diff

---

## 1. Document Overview

### Metadata

| Field               | Value                                                            |
| ------------------- | ---------------------------------------------------------------- |
| Feature ID          | 6.4                                                              |
| Title               | Render Settings Diff                                             |
| Source               | IDEAS_01_Core_Engine_Enhancements.md                            |
| Complexity          | Low                                                              |
| Primary Files       | backend/api/models.py, backend/api/serializers.py, backend/api/render_hash.py (new), backend/core_engine/video_renderer.py |
| Frontend Files      | frontend/components/, frontend/types/, frontend/hooks/           |
| Author              | AI Agent                                                         |
| Created             | 2026-03-10                                                       |
| Status              | Planned                                                          |

---

### Problem Statement

StoryFlow currently provides no mechanism for users to determine whether
the render-affecting settings or segment data of a project have changed
since the last successful render.  When a user modifies any project
setting — resolution, framerate, subtitle styling, logo configuration,
upscaling options, Ken Burns zoom — or edits segment text, replaces an
image, or re-generates audio, there is zero feedback indicating that the
existing rendered video is now stale.

Users are left guessing whether they need to re-render.  This leads to
two failure modes:

1. **Unnecessary re-renders** — Users re-render projects that have not
   changed, wasting compute time and wearing out patience.

2. **Missed re-renders** — Users assume the existing video is up to
   date when it is not, publishing or sharing a video that does not
   reflect their latest changes.

Both scenarios erode trust in the tool and slow down the creative
workflow.

---

### Proposed Solution

Introduce a deterministic SHA-256 hash of all render-affecting fields
on both the Project model and its associated Segment records.  Store
this hash at render completion time, and compare it to a freshly
computed live hash whenever the project detail is requested through
the API.

The comparison result is surfaced as a boolean field called
`render_settings_changed` on the ProjectDetailSerializer response,
which the frontend can use to display a visual badge or warning to
the user.

Key properties of the solution:

- **Deterministic** — Identical inputs always produce the same hash,
  regardless of the order segments are iterated (segments are sorted
  by `sequence_index` before hashing).

- **Lightweight** — SHA-256 computation on a handful of string fields
  is sub-millisecond, adding negligible overhead to API responses.

- **Non-breaking** — The new model field has a default empty string
  value, so existing projects migrate cleanly.  Until a project is
  rendered for the first time after migration, the `render_settings_changed`
  field will report True (empty stored hash never matches a live hash),
  which is the safe default.

- **Future-proof** — Adding new render-affecting fields to the hash
  computation requires only appending them to the ordered field list
  in the hash utility function.

---

### Scope

| In Scope                                                         | Out of Scope                                                      |
| ---------------------------------------------------------------- | ----------------------------------------------------------------- |
| New `last_render_settings_hash` field on Project model           | Automatic re-render when settings change                          |
| New utility file `backend/api/render_hash.py`                    | Per-segment change tracking or fine-grained diff display          |
| `compute_render_hash()` function computing SHA-256               | Hashing of binary file contents (images, audio)                   |
| Storing hash after successful render in `render_project()`       | Hash invalidation on GlobalSettings changes                       |
| `render_settings_changed` computed field on ProjectDetailSerializer | Version history or audit trail of changes                        |
| Frontend badge on Dashboard and Timeline Editor                  | Undo/redo of setting changes                                     |
| Migration file for the new field                                 | Hash comparison for partial re-renders                            |

---

### Key Files

| File Path                                        | Role in Feature                                    | Lines of Interest       |
| ------------------------------------------------ | -------------------------------------------------- | ----------------------- |
| backend/api/models.py                            | Project model — add `last_render_settings_hash`    | L35 (Project class), L124 (Segment class) |
| backend/api/render_hash.py                       | NEW — `compute_render_hash()` utility              | Entire file (new)       |
| backend/api/serializers.py                       | ProjectDetailSerializer — add computed field       | L244 (ProjectDetailSerializer class) |
| backend/core_engine/video_renderer.py            | `render_project()` — save hash after render        | L580 (render_project start), L1160 (result dict section) |
| backend/api/views.py                             | ProjectViewSet — no changes needed                 | L27 (ProjectViewSet)    |
| frontend/types/                                  | Add `render_settings_changed` to Project type      | TypeScript interfaces   |
| frontend/components/                             | Dashboard and Timeline — display badge             | Various components      |

---

## 2. Flow Diagram

### 2.1 Hash Computation Data Flow

The following diagram shows which fields feed into the SHA-256 hash
computation and where the result is stored and compared.

```
                 ┌─────────────────────────────────────┐
                 │         PROJECT MODEL (L35)          │
                 │                                      │
                 │  resolution_width ─────┐             │
                 │  resolution_height ────┤             │
                 │  framerate ────────────┤             │
                 │  zoom_intensity ───────┤             │
                 │  ken_burns_zoom ───────┤             │
                 │  transition_duration ──┤             │
                 │  inter_segment_silence ┤             │
                 │  subtitle_font ────────┤             │
                 │  subtitle_color ───────┤             │
                 │  subtitle_font_size ───┤             │
                 │  subtitle_font_family ─┤             │
                 │  subtitle_font_color ──┤             │
                 │  subtitle_position ────┤             │
                 │  subtitle_y_position ──┤             │
                 │  subtitles_enabled ────┤             │
                 │  logo_enabled ─────────┤             │
                 │  active_logo (id) ─────┤             │
                 │  logo_scale ───────────┤             │
                 │  logo_position ────────┤             │
                 │  logo_opacity ─────────┤             │
                 │  logo_margin ──────────┤             │
                 │  outro_enabled ────────┤             │
                 │  active_outro (id) ────┤             │
                 │  upscale_enabled ──────┤             │
                 │  upscale_model ────────┤             │
                 │  upscale_denoise_      │             │
                 │    strength ───────────┤             │
                 │  default_voice_id ─────┤             │
                 │  tts_speed ────────────┘             │
                 │                                      │
                 │  last_render_settings_hash  (stored) │
                 └──────────────────┬───────────────────┘
                                    │
                     ┌──────────────┴──────────────┐
                     │    SEGMENT MODEL (L124)      │
                     │    (for each segment,        │
                     │     sorted by sequence_index) │
                     │                              │
                     │  text_content ───────────┐   │
                     │  image_file (name) ──────┤   │
                     │  audio_file (name) ──────┤   │
                     │  audio_duration ─────────┤   │
                     │  sequence_index ─────────┘   │
                     └──────────────┬───────────────┘
                                    │
                                    ▼
                     ┌──────────────────────────────┐
                     │   compute_render_hash()       │
                     │   (backend/api/render_hash.py)│
                     │                              │
                     │  1. Collect project fields   │
                     │  2. Sort segments by index   │
                     │  3. Append segment fields    │
                     │  4. Join into canonical str  │
                     │  5. SHA-256 hex digest       │
                     └──────────────┬───────────────┘
                                    │
                           ┌────────┴────────┐
                           │                 │
                           ▼                 ▼
                  ┌─────────────┐   ┌──────────────────┐
                  │  RENDER TIME │   │   API READ TIME   │
                  │  (save hash) │   │   (compare hash)  │
                  └──────┬──────┘   └────────┬─────────┘
                         │                   │
                         ▼                   ▼
              ┌────────────────┐   ┌────────────────────┐
              │ project.last_  │   │ live_hash !=        │
              │ render_settings│   │ stored_hash         │
              │ _hash = hash   │   │                     │
              │                │   │ => render_settings_  │
              │ project.save() │   │    changed = True    │
              └────────────────┘   └─────────┬──────────┘
                                             │
                                             ▼
                                   ┌──────────────────┐
                                   │  API JSON Response │
                                   │  {                 │
                                   │   "render_settings │
                                   │    _changed": true │
                                   │  }                 │
                                   └──────────────────┘
```

### 2.2 Render Pipeline Integration Point

This diagram shows exactly where in the render pipeline the hash is
computed and persisted.

```
  render_project()  (video_renderer.py L580)
       │
       ▼
  ┌─────────────────────────────────┐
  │  A. FFmpeg check                │
  │  B. Load project                │
  │  C. Read settings               │
  │  D. Query segments              │
  │  E. Validate segments           │
  │  F. Determine output path       │
  │  G. Collect data + export audio │
  │  H. Fast render pipeline        │
  │  I. Append outro (if enabled)   │
  │  K. Verify output file          │
  │  M. Get file size               │
  └─────────────┬───────────────────┘
                │
                ▼
  ┌─────────────────────────────────┐
  │  *** NEW STEP: Compute and      │
  │      save render hash ***       │
  │                                 │
  │  1. Re-fetch project from DB    │
  │     (to get latest state)       │
  │  2. Call compute_render_hash()  │
  │  3. Save hash to project.       │
  │     last_render_settings_hash   │
  │  4. project.save()              │
  └─────────────┬───────────────────┘
                │
                ▼
  ┌─────────────────────────────────┐
  │  N. Return result dict          │
  │  (includes output_path,         │
  │   duration, file_size)          │
  └─────────────────────────────────┘
```

### 2.3 Frontend Display Flow

```
  ┌──────────────────────────────────────────┐
  │        Frontend Component Tree            │
  └──────────┬───────────────────────────────┘
             │
             ▼
  ┌──────────────────────┐
  │  API Call:            │
  │  GET /api/projects/   │
  │       {id}/           │
  └──────────┬───────────┘
             │
             ▼
  ┌──────────────────────┐
  │  Response JSON:       │
  │  {                    │
  │    ...                │
  │    "status":          │
  │      "COMPLETED",     │
  │    "render_settings   │
  │      _changed": true  │
  │  }                    │
  └──────────┬───────────┘
             │
      ┌──────┴──────┐
      │             │
      ▼             ▼
  ┌────────┐   ┌──────────┐
  │Dashboard│   │ Timeline │
  │  Card   │   │  Editor  │
  │         │   │          │
  │ [!] Re- │   │ [!] Stale│
  │ render  │   │  render  │
  │ needed  │   │  warning │
  └────────┘   └──────────┘
```

### 2.4 Hash Stability Guarantee

The canonical string construction must produce identical output for
identical inputs regardless of Python dict ordering or database query
ordering.  The diagram below illustrates the canonical ordering.

```
  Input Fields (unordered)
  ────────────────────────
  resolution_width, subtitle_color, framerate, ...

       │  Step 1: Sort by hard-coded ordered list
       ▼

  Ordered Project Fields
  ──────────────────────
  resolution_width | resolution_height | framerate |
  zoom_intensity | ken_burns_zoom | transition_duration |
  ... (alphabetical or logical grouping — fixed order)

       │  Step 2: Append segment data
       ▼

  Segment Data (sorted by sequence_index)
  ────────────────────────────────────────
  seg[0]: text_content | image_file.name | audio_file.name |
          audio_duration | sequence_index
  seg[1]: text_content | image_file.name | ...
  ...

       │  Step 3: Join with delimiter
       ▼

  Canonical String
  ────────────────
  "1920|1080|30|1.3|1.2|0.5|...|seg:0|Once upon...|img.jpg|..."

       │  Step 4: SHA-256
       ▼

  Hash: "a3f2b8c9d1e4f567..."  (64-char hex digest)
```

---

## 3. Step-by-Step Instructions

### Phase A — Backend Model Changes

#### Step 1: Add the `last_render_settings_hash` field to the Project model

Open backend/api/models.py.  Locate the Project class definition which
begins at line 35.

After the last field in the "Image upscaling (GAN)" section — which is
the `upscale_denoise_strength` field at approximately line 112 — and
before the `__str__` method, add a new field called
`last_render_settings_hash`.

This field should be a Django CharField with a max_length of 64 (SHA-256
hex digests are exactly 64 characters).  It should have `blank=True` and
`default=''` so that existing projects and new projects start with an
empty hash, meaning they will always show as "changed" until their first
render.

Add a brief comment above the field explaining its purpose: it stores
the SHA-256 hash of all render-affecting settings and segment data at the
time of the last successful render.

#### Step 2: Create and run the database migration

After saving the model change, run the Django makemigrations command to
generate the migration file.  This will create a new migration file in
backend/api/migrations/ that adds the `last_render_settings_hash` column
to the project table with a default empty string.

Then run the migrate command to apply the migration to the SQLite
database at backend/db.sqlite3.

Verify the migration succeeded by checking that the command completes
without errors.

---

### Phase B — Hash Computation Utility

#### Step 3: Create the new file backend/api/render_hash.py

Create a new Python file at backend/api/render_hash.py.  This file will
contain a single public function, `compute_render_hash`, along with a
private helper constant that defines the ordered list of render-affecting
fields.

#### Step 4: Define the ordered list of render-affecting project fields

At the top of render_hash.py (after imports), define a module-level
tuple or list constant called `RENDER_AFFECTING_PROJECT_FIELDS`.  This
constant should contain all the field names from the Project model that
influence the rendered output, listed in a stable, fixed order.

The fields to include, in this exact order, are:

1.  resolution_width
2.  resolution_height
3.  framerate
4.  zoom_intensity
5.  ken_burns_zoom
6.  transition_duration
7.  inter_segment_silence
8.  subtitle_font
9.  subtitle_color
10. subtitle_font_size
11. subtitle_font_family
12. subtitle_font_color
13. subtitle_position
14. subtitle_y_position
15. subtitles_enabled
16. logo_enabled
17. active_logo_id  (note: use the FK _id suffix to get the UUID, not the related object)
18. logo_scale
19. logo_position
20. logo_opacity
21. logo_margin
22. outro_enabled
23. active_outro_id  (same: FK _id suffix)
24. upscale_enabled
25. upscale_model
26. upscale_denoise_strength
27. default_voice_id
28. tts_speed

This ordering must never change once deployed, or all existing hashes
will become invalid (which is acceptable for a migration but not for
routine updates).

#### Step 5: Define the ordered list of render-affecting segment fields

Define a second constant called `RENDER_AFFECTING_SEGMENT_FIELDS`
containing the Segment model fields that affect rendering:

1. sequence_index
2. text_content
3. image_file  (the file name, not the binary content)
4. audio_file  (the file name, not the binary content)
5. audio_duration

#### Step 6: Implement the `compute_render_hash` function

Write a function called `compute_render_hash` that accepts a single
argument: a Project model instance (already fetched from the database
with its segments prefetched or accessible via the reverse relation).

The function should perform the following operations:

1. Import the `hashlib` module from the Python standard library.

2. Create a list called `parts` that will accumulate string
   representations of each field value.

3. Iterate over `RENDER_AFFECTING_PROJECT_FIELDS`.  For each field name,
   use `getattr(project, field_name, '')` to retrieve the value.  Convert
   the value to a string using `str()`.  Append this string to `parts`.

4. Query the project's segments, ordered by `sequence_index` (ascending).
   This is critical for determinism — the query must always return
   segments in the same order.

5. For each segment, iterate over `RENDER_AFFECTING_SEGMENT_FIELDS`.
   For `image_file` and `audio_file`, extract only the file name (the
   `.name` attribute of the FieldFile object, which gives the relative
   upload path like `projects/uuid/images/filename.jpg`).  If the field
   is None or empty, use an empty string.  Append a segment marker like
   `"seg:"` followed by each field value as a string to the `parts` list.

6. Join all parts with a pipe delimiter `"|"`.  This creates the
   canonical string representation.

7. Compute the SHA-256 hash of the canonical string encoded as UTF-8.

8. Return the hex digest (a 64-character lowercase hex string).

#### Step 7: Add a docstring and logging

Add a comprehensive docstring to `compute_render_hash` explaining its
purpose, the determinism guarantee, and the field ordering contract.

Import the `logging` module and create a module-level logger.  Log a
debug message showing the number of project fields, number of segments,
and the first 12 characters of the computed hash (for troubleshooting
without exposing the full hash in logs).

---

### Phase C — Store Hash at Render Time

#### Step 8: Identify the insertion point in render_project()

Open backend/core_engine/video_renderer.py.  The `render_project`
function begins at line 580.  The function follows a lettered step
sequence: A through N.

The hash should be computed and saved after step M (get file size) and
before step N (return result dict).  This is approximately around line
1160, after the `file_size_mb` logging statement and before the final
`if on_progress:` call that reports 100 percent completion.

#### Step 9: Add the hash computation and persistence

At the identified insertion point, add a new commented section header
(matching the existing style, e.g., "# L2. Save render settings hash").

In this new section:

1. Re-import `compute_render_hash` from `api.render_hash` using a lazy
   import (matching the existing pattern at line 608 where `Project` and
   `Segment` are imported inside the function body).

2. Re-fetch the project from the database to ensure you are hashing the
   absolutely latest state.  Use `Project.objects.get(id=project_id)`.

3. Call `compute_render_hash(project)` to get the hash string.

4. Set `project.last_render_settings_hash = hash_value`.

5. Call `project.save(update_fields=['last_render_settings_hash'])` to
   persist only the hash field without triggering a full model save (this
   avoids updating `updated_at` which is an auto_now field and could
   itself affect the user's perception of "last modified").

   Note: Django's `auto_now` field on `updated_at` will still be updated
   when save() is called even with `update_fields`, unless `updated_at`
   is excluded.  To avoid this side effect, include `updated_at` in
   `update_fields` explicitly set to the current value, or accept that
   the `updated_at` will be bumped (which is actually semantically
   correct — a render did just happen).

6. Log an info-level message confirming the hash was saved, showing the
   first 12 characters of the hash.

#### Step 10: Handle hash computation failure gracefully

Wrap the hash computation and save in a try/except block.  If any
exception occurs (database error, attribute error, etc.), log a warning
but do NOT let it fail the entire render.  The render itself succeeded —
the hash is a nice-to-have, not a critical requirement.

---

### Phase D — Expose Hash Comparison in the API

#### Step 11: Add the computed field to ProjectDetailSerializer

Open backend/api/serializers.py.  Locate the `ProjectDetailSerializer`
class, which starts at approximately line 244.

Add a new SerializerMethodField called `render_settings_changed` to the
serializer.  This field will be computed dynamically on every API read.

In the `Meta.fields` list, add `'render_settings_changed'` and also
`'last_render_settings_hash'`.  The hash field itself is purely
informational and useful for debugging; the boolean
`render_settings_changed` is what the frontend will use.

#### Step 12: Implement the `get_render_settings_changed` method

Add a method called `get_render_settings_changed` to the
`ProjectDetailSerializer` class.  This method receives `self` and `obj`
(the Project instance).

The method should:

1. Import `compute_render_hash` from `api.render_hash`.

2. Retrieve the stored hash from `obj.last_render_settings_hash`.

3. If the stored hash is empty (the project has never been rendered with
   this feature active), return True.  This is the safe default: an
   unknown previous state should be treated as "changed."

4. Compute the live hash by calling `compute_render_hash(obj)`.

5. Compare the live hash to the stored hash.  If they differ, return
   True (settings have changed since last render).  If they match,
   return False.

6. Wrap the entire method in a try/except.  If hash computation fails
   for any reason, return True (the safe default).

#### Step 13: Add `render_settings_changed` to ProjectListSerializer (optional)

Consider whether the project list endpoint should also include this
field.  For the list endpoint (ProjectSerializer at line 37), adding a
computed hash comparison for every project in the list could be expensive
if there are many projects with many segments.

Recommendation: Add it to the list serializer as well but use a
lightweight approach — only compute if the project status is "COMPLETED"
(no point showing "changed" for a DRAFT project that has never been
rendered).  For DRAFT projects, always return False since there is
nothing to compare against.

#### Step 14: Add `last_render_settings_hash` to read_only_fields

In the ProjectDetailSerializer Meta class, add
`'last_render_settings_hash'` to the `read_only_fields` list.  This
field should never be writable through the API — it is only set
internally by the render pipeline.

Also add `'render_settings_changed'` to `read_only_fields` since it is
a computed field.

---

### Phase E — Frontend Integration

#### Step 15: Update the TypeScript Project type

Locate the TypeScript type definition for a Project in the frontend
types directory (likely in frontend/types/).  Add two new optional
fields:

- `render_settings_changed` of type boolean or undefined
- `last_render_settings_hash` of type string or undefined

Both should be optional since they may not be present in list responses
or older API versions.

#### Step 16: Add the "stale render" badge to the Dashboard project card

In the Dashboard component that renders the project list, add a
conditional visual indicator.  When a project's `status` is "COMPLETED"
and `render_settings_changed` is `true`, display a small warning badge
or icon near the project card's status area.

The badge should use a distinct color (e.g., amber/yellow) and include
text like "Re-render needed" or an icon with a tooltip explaining that
settings have changed since the last render.

Do not show the badge when:
- The project status is DRAFT (never rendered)
- The project status is PROCESSING (render in progress)
- `render_settings_changed` is false or undefined

#### Step 17: Add the "stale render" warning to the Timeline Editor

In the Timeline Editor view (the main project editing interface), add a
more prominent warning.  This could be a banner at the top of the editor
or a visual indicator near the Render button.

When `render_settings_changed` is true and the project status is
COMPLETED, display a message like: "Settings or segments have changed
since the last render.  Re-render to update your video."

Consider making the Render button visually distinct (e.g., pulsing
border, different color) when a re-render is advisable.

#### Step 18: Update any cached data or store state

If the frontend uses a state management store (e.g., Zustand, Redux, or
React context) for project data, ensure that the
`render_settings_changed` field is included in the store's Project type
and is updated when project data is fetched or refreshed.

---

### Phase F — Testing

#### Step 19: Write unit tests for `compute_render_hash`

Create a new test file at backend/api/tests/test_render_hash.py (or add
tests to the existing backend/tests/ directory).

Write the following test cases:

1. **Determinism** — Call `compute_render_hash` twice on the same
   project with the same segments.  Assert the two hashes are identical.

2. **Sensitivity to project field changes** — Change a single
   render-affecting field (e.g., `resolution_width` from 1920 to 1080)
   and verify the hash changes.

3. **Sensitivity to segment text changes** — Modify a segment's
   `text_content` and verify the hash changes.

4. **Sensitivity to segment image changes** — Change a segment's
   `image_file` name and verify the hash changes.

5. **Sensitivity to segment order** — Add a segment with a different
   `sequence_index` and verify the hash changes.

6. **Insensitivity to non-render fields** — Change the project title
   (which is not a render-affecting field) and verify the hash does
   NOT change.

7. **Empty project** — Call `compute_render_hash` on a project with
   zero segments and verify it returns a valid 64-character hex string.

8. **None values** — Ensure that None field values are handled
   gracefully (converted to empty string) and do not cause crashes.

#### Step 20: Write integration tests for the serializer field

Add tests that verify the ProjectDetailSerializer includes the
`render_settings_changed` field and that it returns the correct
boolean value before and after a simulated render (i.e., after setting
`last_render_settings_hash` to the current hash).

#### Step 21: Write a test for the render pipeline integration

Create or extend an existing render test to verify that after
`render_project()` completes successfully, the project's
`last_render_settings_hash` field is populated with a non-empty
64-character hex string.

---

## 4. Expected Outcome

### After Implementation

When this feature is fully implemented, the following changes will be
observable in the StoryFlow application:

#### Backend Changes

1. The Project model in backend/api/models.py will have a new CharField
   called `last_render_settings_hash` with a max_length of 64.

2. A new utility file backend/api/render_hash.py will exist containing
   the `compute_render_hash()` function.

3. The ProjectDetailSerializer in backend/api/serializers.py will include
   two new fields in its JSON response: `last_render_settings_hash` (the
   raw stored hash) and `render_settings_changed` (the boolean comparison
   result).

4. The `render_project()` function in backend/core_engine/video_renderer.py
   will compute and store the render hash after every successful render,
   just before returning the result dictionary.

5. A new database migration file will exist in backend/api/migrations/.

#### API Response Changes

The GET response for a project detail endpoint will include:

- `render_settings_changed`: a boolean that is true when the current
  project settings or segment data differ from the state at the last
  render; false when they match.

- `last_render_settings_hash`: a 64-character hex string, or empty
  string if the project has never been rendered.

#### Frontend Changes

1. The project list on the Dashboard will show a small warning badge
   (amber/yellow color) on projects where `render_settings_changed` is
   true and the status is COMPLETED.

2. The Timeline Editor will display a banner or warning message when
   the current project needs a re-render.

3. The Render button may have a visual distinction (color change,
   animation) when a re-render is advisable.

#### User Experience

- Users will immediately see after changing a setting that their video
  is out of date.

- Users will have confidence that their rendered video matches the
  current settings when no warning is displayed.

- The badge disappears automatically after a successful re-render,
  because the new hash matches the stored hash.

- No additional clicks or actions are required from the user — the
  comparison is computed automatically on every project detail fetch.

#### Performance Impact

- Hash computation adds less than 1 millisecond to each project detail
  API response.  Even for projects with 50 segments, the string
  concatenation and SHA-256 computation is near-instantaneous.

- Hash storage at render time adds a single database UPDATE query
  (using `save(update_fields=[...])`) which is negligible compared
  to the render itself.

- No additional database queries are needed for hash comparison if
  the project's segments are already prefetched (which they are in
  the ProjectDetailSerializer via the `segments` field).

---

## 5. Verification Checklist

### Model and Migration

- [ ] The `last_render_settings_hash` field exists on the Project model
      in backend/api/models.py.
- [ ] The field is a CharField with max_length=64, blank=True, default=''.
- [ ] A migration file has been generated and applied successfully.
- [ ] Existing projects have an empty string for the new field.
- [ ] The field is NOT listed in any serializer's writable fields.

### Hash Computation

- [ ] The file backend/api/render_hash.py exists and contains the
      `compute_render_hash()` function.
- [ ] The function accepts a Project model instance as its sole argument.
- [ ] The function returns a 64-character lowercase hex string.
- [ ] Calling the function twice with the same data returns the same hash.
- [ ] Changing any single render-affecting project field changes the hash.
- [ ] Changing segment text_content changes the hash.
- [ ] Changing segment image_file name changes the hash.
- [ ] Changing segment audio_file name changes the hash.
- [ ] Adding, removing, or reordering segments changes the hash.
- [ ] Changing a non-render field (title, status, output_path) does NOT
      change the hash.
- [ ] None values in fields do not cause exceptions.
- [ ] Empty strings in file fields do not cause exceptions.
- [ ] A project with zero segments produces a valid hash.

### Render Pipeline Integration

- [ ] After a successful call to render_project(), the project's
      `last_render_settings_hash` is set to a non-empty string.
- [ ] The hash saved after render matches the hash computed immediately
      before render (assuming no concurrent modifications).
- [ ] If hash computation fails, the render still completes successfully
      and a warning is logged.
- [ ] The hash is saved using save(update_fields=[...]) to minimize
      side effects.

### Serializer and API

- [ ] ProjectDetailSerializer includes `render_settings_changed` in its
      fields list.
- [ ] ProjectDetailSerializer includes `last_render_settings_hash` in its
      fields list.
- [ ] Both fields are in read_only_fields.
- [ ] For a freshly created project (never rendered), `render_settings_changed`
      returns True.
- [ ] For a project rendered and then not modified, `render_settings_changed`
      returns False.
- [ ] For a project rendered and then modified (e.g., resolution changed),
      `render_settings_changed` returns True.
- [ ] If compute_render_hash raises an exception in the serializer,
      `render_settings_changed` returns True (safe default).

### Frontend

- [ ] The Project TypeScript type includes `render_settings_changed` as
      an optional boolean.
- [ ] The Dashboard project card displays a warning badge when
      `render_settings_changed` is true and status is COMPLETED.
- [ ] The badge does NOT appear for DRAFT or PROCESSING projects.
- [ ] The Timeline Editor displays a warning when `render_settings_changed`
      is true.
- [ ] The warning disappears after a successful re-render.
- [ ] The badge/warning has appropriate styling (amber/yellow) and is
      visually distinct from error indicators.

### Edge Cases

- [ ] A project with no segments produces a valid hash and the serializer
      field works correctly.
- [ ] A project with segments that have None image_file or audio_file
      values has the hash compute correctly.
- [ ] Concurrent modification during hash computation (unlikely but
      possible) does not crash the system.
- [ ] The hash handles Unicode text_content correctly (UTF-8 encoding).
- [ ] The hash handles special characters in file names correctly.
- [ ] Very long text_content values (10,000+ characters) do not cause
      performance issues.

---

## 6. Notes for AI Agent

### Precise File Locations

#### backend/api/models.py

- The Project class begins at line 35 with `class Project(models.Model):`.
- The `upscale_denoise_strength` field is at approximately line 112.
- The `__str__` method is at line 114.
- The new `last_render_settings_hash` field should be inserted between
  `upscale_denoise_strength` and `__str__`.
- The Segment class begins at line 124 (after the helper functions
  `segment_image_path` at line 118 and `segment_audio_path` at line 122).
- Segment fields of interest: `text_content` (L128), `image_file` (L130),
  `audio_file` (L131), `audio_duration` (L132), `sequence_index` (L127).

#### backend/api/render_hash.py (NEW FILE)

- This file does not yet exist and must be created from scratch.
- Place it alongside the other API module files in backend/api/.
- Required imports: `hashlib`, `logging`.
- The function should NOT import Django models at the top level — use
  type hints with string annotations (from __future__ import annotations)
  and let the caller pass in the model instance.
- The function should be importable from outside Django (for testing).

#### backend/api/serializers.py

- ProjectDetailSerializer starts at approximately line 244.
- Its Meta.fields list starts at approximately line 248.
- Its read_only_fields list is at approximately line 260.
- The `get_render_settings_changed` method should be added after the
  existing `validate` method at the end of the class (approximately
  line 406).
- Import `compute_render_hash` at the top of the file, alongside the
  existing imports from .models and .parsers.

#### backend/core_engine/video_renderer.py

- The `render_project` function starts at line 580.
- Lazy imports of Project and Segment are at line 608.
- Section M (get file size) is at approximately line 1155.
- Section N (return result dict) starts at approximately line 1168.
- The hash computation block should be inserted between M and N.
- Follow the existing lazy import pattern: import `compute_render_hash`
  from `api.render_hash` inside the function body.
- Re-fetch the project at this point because the function only holds a
  reference from line 620 and the render may have taken minutes.

### Patterns to Follow

#### Field naming convention

Existing fields on Project use snake_case with descriptive names.  The
new field `last_render_settings_hash` follows this pattern.  Do NOT use
a shorter name like `render_hash` — the `last_render_` prefix clarifies
that this is a snapshot from the last render, not a live computation.

#### Error handling pattern

The render pipeline uses try/except blocks that log warnings and continue
(e.g., the logo settings block at lines 730-745, the upscale block at
lines 900-920).  Follow this same pattern for the hash save step.

#### Serializer method field pattern

The ProjectSerializer already uses SerializerMethodField for
`segment_count` (line 39-40, method at line 47).  Follow this same
pattern for `render_settings_changed`.

#### Testing patterns

Existing tests in backend/core_engine/tests/test_crossfade.py use
Django's TestCase class and MagicMock for mocking.  Follow this
pattern for new tests.

### Constraints

1. The hash must be SHA-256.  Do NOT use MD5 (weak) or CRC32 (collision
   prone).  SHA-256 provides a good balance of speed and collision
   resistance for this use case.

2. The canonical string must use a pipe `|` delimiter between fields.
   This prevents ambiguity (e.g., a field value of "12" followed by
   "34" would be indistinguishable from "1234" without a delimiter).

3. Segment data in the canonical string must be prefixed with a marker
   (e.g., `"seg:"`) to clearly separate project fields from segment
   fields.  This prevents a contrived scenario where project field
   values could collide with segment field values.

4. File fields (image_file, audio_file) must be hashed by their NAME
   (the relative path string), not by their binary content.  Hashing
   binary content would be prohibitively slow for large images and
   would not even be correct — two different files could produce the
   same rendered result if they happen to have the same visual content.

5. The `active_logo` and `active_outro` foreign key fields must be
   hashed by their `_id` value (the UUID), not by fetching the related
   object.  This avoids unnecessary database queries and is sufficient
   — if the logo file changes, the user would select a different Logo
   record, changing the FK value.

6. Do NOT include `status`, `title`, `created_at`, `updated_at`, or
   `output_path` in the hash.  These fields do not affect rendering.

7. Do NOT include `is_locked` from Segment in the hash.  The lock
   status affects workflow but not rendering.

8. Do NOT include `image_prompt` from Segment in the hash.  The prompt
   is used for image generation, not rendering.

### Implementation Order

Execute these phases in strict order:

1. **Phase A** (Model) — Must be done first because everything depends
   on the new field existing.

2. **Phase B** (Hash utility) — Must be done second because the
   serializer and render pipeline both depend on it.

3. **Phase C** (Render integration) — Can be done in parallel with
   Phase D, but logically comes first since it populates the hash.

4. **Phase D** (Serializer) — Depends on Phase B.  Exposes the hash
   comparison to the API.

5. **Phase E** (Frontend) — Depends on Phase D.  Consumes the API
   field.

6. **Phase F** (Testing) — Can be done incrementally after each phase,
   but full integration tests require all backend phases complete.

### Field Values to Hash — Complete Reference

For absolute clarity, here is the full list of field values that must
contribute to the hash, with the exact way to access each value from
a Project instance `p` and a Segment instance `s`:

Project fields:
- str(p.resolution_width)
- str(p.resolution_height)
- str(p.framerate)
- str(p.zoom_intensity)
- str(p.ken_burns_zoom)
- str(p.transition_duration)
- str(p.inter_segment_silence)
- str(p.subtitle_font or '')
- str(p.subtitle_color or '')
- str(p.subtitle_font_size)
- str(p.subtitle_font_family or '')
- str(p.subtitle_font_color or '')
- str(p.subtitle_position or '')
- str(p.subtitle_y_position) — note: can be None, str(None) is "None"
- str(p.subtitles_enabled)
- str(p.logo_enabled)
- str(p.active_logo_id or '')
- str(p.logo_scale)
- str(p.logo_position or '')
- str(p.logo_opacity)
- str(p.logo_margin)
- str(p.outro_enabled)
- str(p.active_outro_id or '')
- str(p.upscale_enabled)
- str(p.upscale_model or '')
- str(p.upscale_denoise_strength)
- str(p.default_voice_id or '')
- str(p.tts_speed)

Segment fields (for each segment, in sequence_index order):
- "seg:" marker indicating start of a new segment's data
- str(s.sequence_index)
- str(s.text_content or '')
- str(s.image_file.name if s.image_file else '')
- str(s.audio_file.name if s.audio_file else '')
- str(s.audio_duration if s.audio_duration is not None else '')

### Potential Pitfalls

1. **auto_now on updated_at** — Calling `project.save()` will trigger
   the `auto_now` behavior on `updated_at`, bumping the timestamp even
   though the user did not make any changes.  Using
   `save(update_fields=['last_render_settings_hash'])` still triggers
   auto_now unless the field is explicitly excluded.  The recommended
   approach is to accept this behavior — a render DID just happen, so
   updating `updated_at` is semantically appropriate.

2. **Segment prefetch** — When calling `compute_render_hash` from the
   serializer, the segments may already be prefetched (since
   ProjectDetailSerializer includes `segments` as a related field).
   The hash function should use `project.segments.all()` which will
   use the prefetch cache if available, avoiding a duplicate query.

3. **Race condition** — If a user modifies settings while a render is
   in progress, the hash saved at render completion will reflect the
   state at render time, while the live hash will reflect the new
   settings.  This is the CORRECT behavior — the saved hash should
   represent what was actually rendered.  However, re-fetching the
   project in the hash-save step (Step 9, point 2) should use the
   project state as it was DURING the render, not after.  Actually,
   using the project as loaded at the start of render_project is more
   correct for this purpose — it represents what was actually rendered.
   Consider NOT re-fetching and instead using the project instance
   already loaded in the function (line 620).

4. **Custom font file** — The `custom_font_file` field on Project is a
   FileField.  Whether to include it in the hash depends on whether
   changing the font file source affects rendering.  Since the font path
   is resolved through `render_utils.get_font_path()`, and the
   `subtitle_font` field already captures which font is selected, the
   `custom_font_file` field does NOT need to be in the hash.

5. **GlobalSettings changes** — If a user changes GlobalSettings and
   then renders, the render uses Project-level settings (which are
   copied from GlobalSettings at project creation time).  Therefore,
   only Project fields matter for the hash.  GlobalSettings does not
   need to be included.

---

### Summary of Files to Create or Modify

| Action   | File                                              |
| -------- | ------------------------------------------------- |
| CREATE   | backend/api/render_hash.py                        |
| MODIFY   | backend/api/models.py (add field)                 |
| MODIFY   | backend/api/serializers.py (add computed field)   |
| MODIFY   | backend/core_engine/video_renderer.py (save hash) |
| MODIFY   | frontend/types/ (add TS field)                    |
| MODIFY   | frontend/components/ (add badge)                  |
| CREATE   | backend/api/tests/test_render_hash.py (or similar)|
| RUN      | python manage.py makemigrations                   |
| RUN      | python manage.py migrate                          |
