# Feature 2.3 — Built-In Royalty-Free Music Library

| Field | Value |
|---|---|
| **Feature ID** | 2.3 |
| **Title** | Built-In Royalty-Free Music Library |
| **Status** | 🟡 Planned |
| **Priority** | Medium |
| **Complexity** | Low (technical) / Medium (licensing) |
| **Estimated Effort** | 3 days |
| **Dependencies** | Feature 2.1 (Background Music Mixing) must be planned; Feature 2.3 can be built in parallel but is consumed by 2.1 |
| **Output Files (NEW)** | `backend/media/music_library/` directory tree, `backend/api/management/commands/load_music_library.py`, Django migration file |
| **Files Modified** | `backend/api/models.py`, `backend/api/serializers.py`, `backend/api/views.py`, `backend/api/urls.py`, `backend/api/admin.py` |

---

## 1. Document Overview

### 1.1 Problem Statement

Currently StoryFlow has no built-in audio tracks. Users who want background music must source and upload their own files every time they create a project. This creates significant friction — the majority of users lack access to royalty-free music, do not know where to find legally safe tracks, and should not need to leave the application to acquire them. The result is that the background music feature (Feature 2.1), once implemented, will go underused because the on-ramp is too steep.

### 1.2 Proposed Solution

Bundle a curated set of 20–50 royalty-free music tracks directly into the StoryFlow backend, organized by mood category. A new `MusicTrack` database model stores track metadata (title, artist, mood, duration). A Django management command scans the on-disk library and populates the database. Two new API endpoints expose the library to the frontend as a browsable, filterable list. The `Project` model gains a `music_library_track` foreign key so a user can select a built-in track rather than uploading a file. Music files themselves are not committed to the Git repository; they are distributed as a separate downloadable pack and loaded via the management command.

### 1.3 Scope

| In Scope | Out of Scope |
|---|---|
| `MusicTrack` model with mood, title, artist, duration, file path | Audio preview streaming endpoint |
| Directory structure `media/music_library/{mood}/` | Waveform visualization |
| Management command to scan and register tracks | User-uploaded custom tracks (that is Feature 2.1) |
| `GET /api/music-library/` list endpoint with mood filter | Music recommendation / AI mood matching |
| `GET /api/music-library/{id}/` detail endpoint | Paid music licensing integration |
| `music_library_track` FK on `Project` model | Automatic mood detection from story content |
| Admin registration of `MusicTrack` | CDN hosting of music files |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| `backend/api/models.py` | Defines all Django ORM models | Has `Project`, `Segment` models; no `MusicTrack` |
| `backend/api/serializers.py` | DRF serializers for API I/O | No `MusicTrack` serializer exists |
| `backend/api/views.py` | DRF ViewSets and API views | No music library view exists |
| `backend/api/urls.py` | URL routing for the API | No music library routes |
| `backend/api/admin.py` | Django admin registrations | Does not register `MusicTrack` |
| `backend/media/music_library/` | On-disk home for audio files | Does not exist yet |
| `backend/api/management/commands/` | Django management command directory | May not exist yet |

---

## 2. Flow Diagram

```
User opens "Music Settings" panel in Frontend
         |
         v
Frontend calls GET /api/music-library/?mood=calm
         |
         v
Django view queries MusicTrack table filtered by mood
         |
         v
Returns JSON list: [{ id, title, artist, mood, duration, file_url }, ...]
         |
         v
User selects a track → Frontend stores music_library_track ID on Project form
         |
         v
User saves project → PATCH /api/projects/{id}/ with music_library_track=<id>
         |
         v
Project model stores FK to MusicTrack
         |
         v
At render time (Feature 2.1), video_renderer.py reads project.music_library_track
and resolves the on-disk file path via MusicTrack.file.path
         |
         v
FFmpeg mixes that file as background audio
```

```
Admin / Deployment: on-disk music pack
         |
         v
Operator runs: python manage.py load_music_library
         |
         v
Command scans media/music_library/ subdirectories
         |
         v
For each .mp3 / .wav found → create or update MusicTrack row
         |
         v
MusicTrack table is now populated and ready for API queries
```

---

## 3. Step-by-Step Instructions

### Step 3.1 — Create the music library directory structure

Navigate to `backend/media/` and create a folder named `music_library`. Inside it, create seven subdirectories, one per mood: `dramatic`, `upbeat`, `calm`, `motivational`, `suspenseful`, `sad`, `educational`. These directories will hold the actual audio files once the music pack is downloaded. Place a `.gitkeep` file inside each subdirectory so Git tracks the empty directories. Do not add any audio files to the repository.

### Step 3.2 — Define the MusicTrack model in models.py

Open `backend/api/models.py`. At the end of the file, after the existing model definitions, add a new class called `MusicTrack`. It needs the following fields:

- `title` — a CharField with max length 200, blank is not allowed.
- `artist` — a CharField with max length 200, with a blank-allowed default of empty string. Many tracks from free sources list the artist as the platform.
- `mood` — a CharField with max length 50 using a choices list. The valid choices are: dramatic, upbeat, calm, motivational, suspenseful, sad, educational. Store the lowercase slug as the value and a human-readable label as the display name.
- `duration` — a FloatField representing track length in seconds. This is populated by the management command by reading the audio file metadata.
- `file` — a FileField with `upload_to` pointing to `music_library/`. Django will preserve the subdirectory structure under `MEDIA_ROOT`.
- `created_at` — a DateTimeField with `auto_now_add=True`.

Add a `__str__` method that returns the title and mood together for readability in the admin.

Add a `Meta` class with `ordering = ['mood', 'title']` so the admin and API list always returns tracks sorted predictably.

### Step 3.3 — Add the music_library_track foreign key to Project

Still in `backend/api/models.py`, find the `Project` model. Add a new field: `music_library_track` — a ForeignKey to `MusicTrack`, with `null=True`, `blank=True`, `on_delete=SET_NULL`, and `related_name='projects'`. This allows a project to optionally reference a built-in track. When the referenced track is deleted (e.g. the library is refreshed), the project's reference becomes null rather than causing an error.

### Step 3.4 — Generate and apply the migration

Run `python manage.py makemigrations api` to generate a new migration file that creates the `MusicTrack` table and adds the `music_library_track` column to the `Project` table. Then run `python manage.py migrate` to apply it to the database.

### Step 3.5 — Create the management command

Create the directory path `backend/api/management/commands/` if it does not exist. Inside `management/`, add an `__init__.py`. Inside `commands/`, add another `__init__.py`. Then create the file `load_music_library.py`.

The command class should extend Django's `BaseCommand`. Its `handle` method should:

1. Determine the absolute path to `backend/media/music_library/` using Django's `settings.MEDIA_ROOT`.
2. Iterate over each mood subdirectory (dramatic, upbeat, calm, motivational, suspenseful, sad, educational).
3. Within each subdirectory, find all files with `.mp3` or `.wav` extensions.
4. For each file found, derive the title from the filename by stripping the extension and replacing underscores/hyphens with spaces. Title-case the result.
5. Use `mutagen` (a Python audio metadata library) to read the actual duration of the file in seconds. If `mutagen` is not available or the read fails, fall back to a duration of 0.0 and log a warning.
6. Call `MusicTrack.objects.update_or_create(file=relative_path, defaults={title, artist, mood, duration})` where `relative_path` is the path relative to `MEDIA_ROOT`.
7. Print a summary line for each processed file, and a final count of how many tracks were created versus updated.

Add `mutagen` to `backend/requirements.txt`.

### Step 3.6 — Create the MusicTrack serializer

Open `backend/api/serializers.py`. Add a new serializer class called `MusicTrackSerializer` using `ModelSerializer`. Include all fields: `id`, `title`, `artist`, `mood`, `duration`, and `file`. The `file` field should be exposed as an absolute URL using a `SerializerMethodField` or by ensuring the serializer context receives the request object (so `file.url` becomes an absolute URL the frontend can use directly).

### Step 3.7 — Create the API views

Open `backend/api/views.py`. Add a new ViewSet or APIView for `MusicTrack`. The simplest approach is a `ReadOnlyModelViewSet` (list and retrieve only — users do not upload tracks through this endpoint). Configure `queryset = MusicTrack.objects.all()` and `serializer_class = MusicTrackSerializer`. Add filter support: allow filtering by `mood` query parameter. Use Django's built-in queryset filtering — if `?mood=calm` is present in the request, filter the queryset to `mood='calm'` before returning. No authentication should be required for this endpoint (it is public data).

### Step 3.8 — Register the URL routes

Open `backend/api/urls.py`. Register the `MusicTrackViewSet` with the existing DRF router. The resulting routes will be:

- `GET /api/music-library/` — list all tracks (filterable by mood)
- `GET /api/music-library/{id}/` — retrieve a single track

Ensure the router prefix is `music-library` to match the path above.

### Step 3.9 — Register MusicTrack in admin

Open `backend/api/admin.py`. Register `MusicTrack` with a custom `ModelAdmin` class. Configure `list_display` to show `title`, `artist`, `mood`, `duration`, and `file`. Add `list_filter` for `mood` so staff can browse tracks by category. Add `search_fields` on `title` and `artist`. This makes it easy to audit and manage the library from the Django admin panel.

### Step 3.10 — Update Project serializer

Open `backend/api/serializers.py`. Find the `ProjectSerializer`. Add `music_library_track` as a writable field — accept an integer ID on write (PrimaryKeyRelatedField) and optionally a nested `MusicTrackSerializer` for read, or just expose the FK ID for simplicity. Confirm that the `music_library_track` field is included in `Meta.fields`.

---

## 4. Expected Outcome

1. The directory `backend/media/music_library/` exists with seven mood subdirectories, each containing a `.gitkeep` placeholder.
2. Running `python manage.py load_music_library` after placing audio files in the mood directories populates the `MusicTrack` table without errors.
3. `GET /api/music-library/` returns a JSON array of track objects, each containing id, title, artist, mood, duration (seconds), and an absolute file URL.
4. `GET /api/music-library/?mood=calm` returns only tracks with mood equal to "calm".
5. `GET /api/music-library/3/` returns the detail for the track with id 3.
6. The Django admin panel shows a "Music Tracks" section under the API app with functional list display, filter sidebar, and search box.
7. A `Project` record can be saved with a non-null `music_library_track` FK referencing a valid `MusicTrack` row.
8. Deleting a `MusicTrack` row sets `music_library_track` to null on all referencing `Project` records rather than cascading the delete.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] `MusicTrack` model can be created with all seven mood choices without validation errors
- [ ] `MusicTrack.__str__` returns expected string
- [ ] `MusicTrack.objects.filter(mood='calm')` returns only calm-mood tracks
- [ ] `MusicTrackSerializer` produces the expected JSON shape including absolute file URL when request context is provided
- [ ] `ProjectSerializer` correctly accepts and returns a `music_library_track` integer FK
- [ ] Management command `load_music_library` creates new `MusicTrack` entries when called with a populated test directory
- [ ] Management command is idempotent — running it twice does not duplicate entries

### 5.2 Integration / Manual Tests

- [ ] Start the Django dev server; call `GET /api/music-library/` and confirm 200 response with correct JSON structure
- [ ] Call `GET /api/music-library/?mood=dramatic` and confirm only dramatic tracks are returned
- [ ] Call `GET /api/music-library/?mood=invalid` and confirm an empty list is returned (not a 500 error)
- [ ] Call `GET /api/music-library/999/` for a non-existent ID and confirm a 404 response
- [ ] Open the Django admin and navigate to Music Tracks; confirm list_display columns appear and the mood filter sidebar is functional
- [ ] PATCH a Project record with `music_library_track: 1` and confirm the FK is saved in the database
- [ ] Delete the MusicTrack with id 1 via admin and confirm the Project's `music_library_track` becomes null

### 5.3 Regression Tests

- [ ] Existing `GET /api/projects/` endpoint still works correctly after the migration
- [ ] Existing project create/update/delete flows are unaffected
- [ ] Running `python manage.py migrate` on a fresh database applies all migrations cleanly including the new one
- [ ] Running the test suite (`python manage.py test`) passes with no regressions in existing tests

---

## 6. Notes for AI Agent

**Implementation order:** Steps 3.1 → 3.2 → 3.3 → 3.4 (migration) → 3.5 → 3.6 → 3.7 → 3.8 → 3.9 → 3.10. Do not attempt to run migations before all model changes in 3.2 and 3.3 are complete, since they should be captured in a single migration file.

**mutagen dependency:** Add `mutagen` to `requirements.txt` before implementing the management command. If the deployment environment cannot install it, the management command should degrade gracefully — catch the ImportError and set duration to 0.0 rather than crashing.

**File URLs in serializer:** The `file` field on `MusicTrack` is a Django `FileField`. Its `.url` property returns a relative path like `/media/music_library/calm/track.mp3`. To make it absolute, the serializer needs access to the HTTP request object so it can build the full URL. Pass `context={'request': request}` when instantiating the serializer in the view, or use a `SerializerMethodField` that calls `request.build_absolute_uri(obj.file.url)`.

**Music files are not in Git:** The `.gitkeep` files mark the directory structure. Instructions for the deployment operator should specify where to download the CC0 music pack ZIP and how to extract it into the mood subdirectories before running the management command. Suitable CC0 sources include Pixabay Music (pixabay.com/music), Free Music Archive (freemusicarchive.org), and ccMixter (ccmixter.org) — filter strictly for CC0 or Public Domain licenses.

**Naming convention for audio files:** Recommend snake_case filenames without special characters for maximum OS compatibility. The management command derives the track title from the filename, so `calm_morning_breeze.mp3` becomes "Calm Morning Breeze". Document this convention in a README inside `media/music_library/`.

**Feature 2.1 interaction:** This feature adds the `music_library_track` FK to `Project`. Feature 2.1 adds `music_file`, `music_enabled`, and `music_volume`. At render time, `video_renderer.py` (Feature 2.1) should check: if `music_library_track` is set and `music_file` is not, resolve the audio path from `project.music_library_track.file.path`. If both are set, prefer the user-uploaded `music_file`. Document this precedence rule in Feature 2.1.

**Mood choices consistency:** The seven mood slugs used as database values must match exactly between the model choices, the management command directory names, and any frontend filter values. Define them as a constant list or tuple in `models.py` and import it everywhere else rather than duplicating the strings.

**Duration field edge case:** If a track file is corrupt or zero-length, `mutagen` may raise an exception or return None for duration. The management command must handle this with a try/except and log a warning rather than failing the entire import run.

**Admin file path display:** In the admin list, the `file` column will show the relative storage path. Consider adding a `get_file_url` method on the ModelAdmin that renders it as a clickable link for easy auditing.
