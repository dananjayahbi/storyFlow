# Feature 2.1 — Background Music Track Support

| Field | Value |
|---|---|
| **Feature ID** | 2.1 |
| **Title** | Background Music Track Support |
| **Status** | 🟡 Planned |
| **Priority** | High |
| **Complexity** | Medium |
| **Estimated Effort** | 4 days |
| **Dependencies** | FFmpeg installed and accessible on PATH, `video_renderer.py` render pipeline stable, `Project` model migration infrastructure |
| **Output Files (NEW)** | None — modifies the existing final rendered video in-place |
| **Files Modified** | `backend/api/models.py`, `backend/api/serializers.py`, `backend/api/views.py`, `backend/api/urls.py`, `backend/core_engine/video_renderer.py`, new migration file under `backend/api/migrations/` |

---

## 1. Document Overview

### 1.1 Problem Statement

StoryFlow currently produces videos with TTS narration as the only audio layer. There is no background music. This is a critical gap for social media video content — virtually every successful short-form video on platforms like TikTok, Instagram Reels, and YouTube Shorts uses background music as a foundational element of its emotional impact and audience retention.

TTS-only narration sounds clinical and sterile. Even a subtle, low-volume ambient music track underneath the narration dramatically increases perceived production quality and viewer engagement. Without this feature, StoryFlow output videos are immediately recognizable as raw AI-generated content, which reduces their effectiveness for real social media use.

The absence of music also means StoryFlow cannot compete with tools like Canva Video, CapCut, or Pictory, all of which provide music track support as a basic feature.

### 1.2 Proposed Solution

Add a background music layer to the StoryFlow render pipeline. The feature has three tiers of scope:

1. **Model layer** — Add three new fields to the `Project` model: `music_enabled` (a boolean toggle), `music_file` (a file upload field for user-provided MP3 or WAV files), and `music_volume` (a float between 0.0 and 1.0 controlling music loudness relative to narration).
2. **Render layer** — After the main video render completes, if `music_enabled` is true and a `music_file` has been uploaded, run a post-processing FFmpeg command that mixes the music track under the combined narration audio at the specified volume. Music is looped if it is shorter than the video duration, and trimmed if it is longer. The output overwrites the rendered video file.
3. **API layer** — Expose the new model fields through the serializer, add a dedicated music file upload endpoint, and ensure the render task reads the new fields correctly.

On the frontend, the project settings panel gains a music section: a file upload control, a volume slider (0–100%, displayed as percentage, stored as 0.0–1.0), and an enable/disable toggle.

### 1.3 Scope

| In Scope | Out of Scope |
|---|---|
| `music_enabled`, `music_file`, `music_volume` fields on `Project` model | Per-segment music (music is project-level only) |
| User-uploaded MP3 and WAV files as music source | Built-in royalty-free music library (future feature) |
| FFmpeg post-processing to mix music under narration | Real-time music preview in the editor |
| Music looped to match video duration (`-stream_loop`) | Fade-in / fade-out effects for music (future feature) |
| Music trimmed to match video duration (`-t` flag) | Music ducking / auto-volume reduction during speech detection |
| Music volume controlled via FFmpeg `[0:a]volume=X` filter | MIDI or generative music (out of scope) |
| Database migration for new Project fields | Beat-sync or music-aware cut timing |
| Serializer and API exposure of new fields | Per-segment volume overrides |
| Music file upload endpoint | Streaming music during render (batch post-process only) |
| Frontend music section (upload, volume slider, toggle) | YouTube/Spotify API music integration |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| `backend/api/models.py` | Defines `Project` and `Segment` models | `Project` has `voice_id`, `tts_speed`, `resolution_width/height`, `framerate` — no music fields |
| `backend/core_engine/video_renderer.py` | `render_project()` orchestrates TTS generation, compositing, and final output | Produces a final video file; no audio mixing post-step exists |
| `backend/api/serializers.py` | DRF serializers for `Project` and `Segment` | Exposes current project fields; new fields must be added |
| `backend/api/views.py` | REST API views | Has project CRUD and render trigger; needs music upload endpoint |
| `backend/api/urls.py` | URL routing | Needs new URL for music file upload |
| `backend/api/migrations/` | Django migration files | New migration file needed for the three new `Project` fields |

---

## 2. Flow Diagram

```
User uploads music file via frontend
        |
        v
POST /api/projects/{id}/upload-music/
  - Validate file type (MP3 or WAV only)
  - Save to media/projects/{id}/music/{filename}
  - Store path in Project.music_file
  - Return 200 + updated project data
        |
User sets music_volume slider and enables music_enabled toggle
        |
        v
PATCH /api/projects/{id}/  (standard project update)
  - Updates music_enabled and music_volume on Project model
        |
User triggers render
        |
        v
render_project_task (Celery) calls render_project(project_id)
        |
        v
video_renderer.py: render_project()
  [existing pipeline runs unchanged]
  → TTS generation per segment
  → Frame compositing
  → Video assembly
  → Output: final_video.mp4 (narration audio, no music yet)
        |
        v
video_renderer.py: _mix_background_music(project, output_video_path)
  - Check: project.music_enabled is True AND project.music_file is not empty
  - If conditions not met: skip step entirely, return
  - If conditions met:
      - Read project.music_volume (e.g., 0.2)
      - Probe video duration using FFmpeg -show_entries format=duration
      - Build FFmpeg filter_complex command:
          * Input 0: output_video.mp4 (video + narration audio)
          * Input 1: music_file.mp3/wav with -stream_loop -1 (infinite loop)
          * filter_complex: mix narration at full volume with music at project.music_volume
          * Output: temp_mixed_video.mp4
      - Run FFmpeg command
      - Replace output_video.mp4 with temp_mixed_video.mp4
      - Clean up temp file
        |
        v
Render complete — final video contains narration + background music
```

---

## 3. Step-by-Step Instructions

### Step 3.1 — Add new fields to the `Project` model in `models.py`

Open `backend/api/models.py`.

Locate the `Project` model class definition. After the existing audio/render-related fields (such as `voice_id`, `tts_speed`, `framerate`), add three new fields:

- A `BooleanField` named `music_enabled` with `default=False` and `blank=True`. This controls whether background music is mixed into the final render.
- A `FileField` named `music_file` that accepts uploads to a subdirectory under the project's media folder (e.g., `upload_to=` a callable or string that places files under `projects/{project_id}/music/`). This field should be `null=True` and `blank=True` since music is optional.
- A `FloatField` named `music_volume` with `default=0.2`, `null=False`, `blank=True`. This represents the music volume as a linear multiplier (0.0 is silent, 1.0 is full volume). Document in code comments that the intended range is 0.0 to 1.0, though no database-level constraint is applied — validation is enforced in the serializer.

Do not remove or modify any existing fields.

### Step 3.2 — Create and apply the database migration

After saving `models.py`, generate a new migration using Django's `makemigrations` command. Name it descriptively to reflect background music support. Verify the generated migration file in `backend/api/migrations/` correctly adds all three new fields with the right defaults and nullable settings.

Apply the migration to update the development database. Confirm no errors occur and the existing project records receive their default values for the new fields.

### Step 3.3 — Update the serializer in `serializers.py`

Open `backend/api/serializers.py`.

Find the `ProjectSerializer` class. Add `music_enabled`, `music_file`, and `music_volume` to the serializer's explicit field list (or `fields = '__all__'` if that pattern is used — verify which pattern the file uses).

Add a validator for `music_volume` in the serializer's `validate_music_volume` method (or in the `validate` method). The validator should raise a `serializers.ValidationError` if the value is less than 0.0 or greater than 1.0.

The `music_file` field in the serializer should be read-only for standard project update requests. It will be written only through the dedicated music upload endpoint (Step 3.4). Mark it as `read_only=True` in the serializer, or create a separate serializer for the upload endpoint.

### Step 3.4 — Add the music upload endpoint to `views.py`

Open `backend/api/views.py`.

Add a new view function (or class-based view) named `upload_project_music`. This view should:

- Accept POST requests only.
- Extract `project_id` from the URL.
- Retrieve the `Project` object or return 404.
- Read the uploaded file from `request.FILES` under the key `music_file`.
- Validate that the uploaded file has a `.mp3` or `.wav` extension (case-insensitive). Return a 400 error with a clear message if the format is not supported.
- Validate that the file size is within a reasonable limit (e.g., reject files over 50 MB). Return a 400 error if too large.
- Save the file to the project's media directory using Django's `FileField.save()` mechanism, which handles path construction and storage backend.
- Update `project.music_file` with the saved file reference and call `project.save()`.
- Return a JSON response with the updated project data (serialized using `ProjectSerializer`).

### Step 3.5 — Register the new URL in `urls.py`

Open `backend/api/urls.py`.

Add a new URL pattern mapping `projects/<int:project_id>/upload-music/` to the `upload_project_music` view. Use a `name=` of `project-upload-music` or follow the existing naming convention in the file.

Verify that this new pattern does not conflict with any existing patterns. Place it logically near other project-level action URLs.

### Step 3.6 — Add `_mix_background_music()` to `video_renderer.py`

Open `backend/core_engine/video_renderer.py`.

Add a new private helper function named `_mix_background_music` that accepts a `Project` model instance and the path to the current final output video file.

Inside this function:

- Check if `project.music_enabled` is `True` and `project.music_file` is not empty. If either condition is false, return immediately without doing anything.
- Resolve the absolute filesystem path of the music file from `project.music_file.path`.
- Check that the music file actually exists on disk. If it does not (e.g., file was deleted externally), log a warning and return without raising an exception — a missing music file should not abort the entire render.
- Construct a temporary output path for the mixed video (e.g., append `_music_mixed` to the video filename before the extension, in the same directory).
- Build the FFmpeg command as a list of arguments (to pass to `subprocess.run` or the equivalent wrapper used in `video_renderer.py`):
  - Input 0: the final output video path
  - Input 1: the music file path, preceded by `-stream_loop -1` to enable infinite looping
  - Use `-filter_complex` to:
    - Extract the narration audio from input 0 at full volume (volume=1.0)
    - Extract the music from input 1 at `project.music_volume` (e.g., volume=0.2)
    - Mix them together using the `amix` filter with `inputs=2` and `duration=first` (narration length governs duration)
  - Apply the mixed audio to the video stream from input 0
  - Add `-t` set to the video's duration to prevent the looped music from extending the video length
  - Output to the temporary path
- Run the FFmpeg command. Capture stderr. If the command fails (non-zero return code), log the FFmpeg stderr output and raise an exception with a clear message.
- If FFmpeg succeeds: replace the original output video file with the temporary mixed file (delete original, rename temp to original filename).
- Clean up the temporary file if it still exists after the rename operation.

### Step 3.7 — Call `_mix_background_music()` from `render_project()`

Inside `video_renderer.py`, find the `render_project()` function. Locate the point where the final video file has been assembled and is at its final output path.

After that point — as the last step before the function returns — call `_mix_background_music(project, final_video_path)`.

Because `_mix_background_music` checks `music_enabled` internally, wrapping the call in an external `if` is not required (though it is acceptable). The function is safe to call unconditionally at the end of every render.

Ensure the `Project` object is loaded (or re-fetched from the database) at this point in the function to get the latest field values.

### Step 3.8 — Add the music section to the frontend project settings

Open the frontend project settings component (likely under `frontend/components/` in a file related to project configuration or settings).

Add a new "Background Music" section to the settings panel. This section should contain:

- A toggle switch bound to `music_enabled` that sends a PATCH request to `/api/projects/{id}/` when changed.
- A file upload input that accepts `.mp3` and `.wav` files only (use `accept=".mp3,.wav"` on the HTML input). On file selection, send a POST request to `/api/projects/{id}/upload-music/` using a `FormData` body. Show a progress indicator during upload.
- A volume slider ranging from 0 to 100 (displayed as a percentage integer). Map this to the `music_volume` float (divide by 100 before sending to the API). Send a PATCH request to `/api/projects/{id}/` when the slider value is committed (on mouse release, not on every drag event).
- A small label showing the currently uploaded music filename if one exists (from `project.music_file`).
- A "Remove Music" button that clears the `music_file` field — this requires a backend endpoint or a PATCH with `music_file: null` depending on how the serializer handles it.

The music section should be visually disabled (grayed out controls) when `music_enabled` is false, to clearly indicate that uploaded music is present but not active.

---

## 4. Expected Outcome

1. The `Project` model has three new fields: `music_enabled`, `music_file`, and `music_volume`, accessible via the Django admin panel.
2. The database migration applies cleanly without errors on a fresh and on an existing development database.
3. A GET request to `/api/projects/{id}/` returns `music_enabled`, `music_file`, and `music_volume` in the response JSON.
4. A POST to `/api/projects/{id}/upload-music/` with a valid MP3 or WAV file saves the file to disk and updates `project.music_file`.
5. A POST with an unsupported file type (e.g., `.ogg`) returns HTTP 400 with a descriptive error message.
6. After a render with `music_enabled=True` and a valid `music_file`, the output video contains both narration audio and the background music track.
7. The background music volume in the final video matches the configured `music_volume` level (e.g., at 0.2, music is clearly audible but noticeably quieter than the narration).
8. If the music file is shorter than the video, the music loops seamlessly to fill the entire video duration.
9. If the music file is longer than the video, the music is trimmed so the video duration is not extended.
10. After a render with `music_enabled=False`, the output video contains narration only — identical behavior to the pre-feature baseline.
11. If `music_file` is set but `music_enabled` is False, the render completes without mixing music — the file is stored but ignored.
12. If `music_file` has been deleted from disk but the field still holds a value, the render completes with narration only and logs a warning — it does not crash.
13. The frontend music section allows upload, volume adjustment, and toggle with no console errors.
14. Removing a music file via the frontend clears the `music_file` field in the database.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] `_mix_background_music()` returns without action when `music_enabled=False`
- [ ] `_mix_background_music()` returns without action when `music_file` is empty/None
- [ ] `_mix_background_music()` logs a warning and returns without crashing when `music_file` path does not exist on disk
- [ ] `_mix_background_music()` calls FFmpeg with `-stream_loop -1` for music input
- [ ] `_mix_background_music()` applies the correct volume multiplier from `project.music_volume`
- [ ] `_mix_background_music()` uses `duration=first` in `amix` to prevent length extension
- [ ] `_mix_background_music()` replaces the original video file with the mixed output on success
- [ ] `_mix_background_music()` raises an exception with stderr info when FFmpeg fails
- [ ] `ProjectSerializer.validate_music_volume` raises a validation error for values below 0.0
- [ ] `ProjectSerializer.validate_music_volume` raises a validation error for values above 1.0
- [ ] `ProjectSerializer.validate_music_volume` accepts 0.0, 0.5, and 1.0 as valid values
- [ ] `upload_project_music` view rejects files with extensions other than `.mp3` and `.wav`
- [ ] `upload_project_music` view rejects files exceeding the size limit

### 5.2 Integration / Manual Tests

- [ ] Database migration runs without errors on a clean database
- [ ] Database migration runs without errors on a database with existing Project records
- [ ] PATCH `/api/projects/{id}/` with `music_enabled=true` updates the field and returns the value in the response
- [ ] PATCH `/api/projects/{id}/` with `music_volume=0.3` updates the field and returns 0.3 in the response
- [ ] PATCH `/api/projects/{id}/` with `music_volume=1.5` returns HTTP 400
- [ ] POST to `/api/projects/{id}/upload-music/` with a valid MP3 returns HTTP 200 and saves the file
- [ ] POST to `/api/projects/{id}/upload-music/` with a `.ogg` file returns HTTP 400
- [ ] A full render with music enabled produces a video with audible background music
- [ ] A full render with music disabled produces a video identical to pre-feature output
- [ ] Rendered video duration is not extended when music is longer than the narration
- [ ] Rendered video music loops when narration is longer than the music track
- [ ] A render proceeds to completion (narration only) when the music file is missing from disk
- [ ] The frontend volume slider sends `music_volume` as a float (e.g., slider at 30 → 0.30 in API)
- [ ] The frontend toggle correctly enables/disables the music section controls

### 5.3 Regression Tests

- [ ] Renders with `music_enabled=False` produce output identical in audio to pre-feature renders
- [ ] Existing project fields (`voice_id`, `tts_speed`, `resolution_width`, `resolution_height`, `framerate`) are unaffected by the migration
- [ ] `render_project()` function still raises the same exceptions it did before for invalid inputs unrelated to music
- [ ] Segment TTS generation is unaffected by the new render step
- [ ] Project creation with no music-related fields in the request body succeeds and uses correct defaults (`music_enabled=False`, `music_volume=0.2`)
- [ ] Existing project serializer tests continue to pass
- [ ] Django admin still loads the Project model without errors

---

## 6. Notes for AI Agent

**Implementation order:** Follow this sequence to minimize risk: models.py → migration → serializers.py → views.py → urls.py → video_renderer.py → frontend. Complete and test each layer before moving to the next.

**FFmpeg availability:** Before implementing `_mix_background_music()`, verify how `video_renderer.py` currently invokes FFmpeg. Match the same invocation pattern (whether it uses `subprocess.run`, a helper wrapper, or a library like `ffmpeg-python`). Do not introduce a different FFmpeg invocation style.

**Temporary file cleanup:** The mixing step writes a temporary file to disk. Ensure cleanup happens even if the rename fails — use a try/finally block in `_mix_background_music()` that deletes the temp file if it still exists, regardless of success or failure.

**Volume filter precision:** The FFmpeg `volume` filter accepts float values. Pass `project.music_volume` directly as a string in the filter (e.g., `volume=0.2`). Do not round to integers. Music at 0.20 is a common default for ambient background music under speech.

**Loop + trim interaction:** The `-stream_loop -1` flag must be placed before the second input (`-i music_file`) in the FFmpeg argument list, not after. Placement order matters for FFmpeg input options. The `-t` flag limiting duration should be placed before the output path, not as an input option.

**Migration defaults:** The migration for `music_volume` should use `default=0.2`. The migration for `music_enabled` should use `default=False`. The migration for `music_file` should use `blank=True, null=True` since existing projects have no music file. Verify the generated migration file reflects these values before applying.

**File type validation:** Validate by checking the file extension of the uploaded filename, not by MIME type — MIME types are browser-reported and unreliable. Use `.lower().endswith(('.mp3', '.wav'))` on the filename string.

**Upload path for music files:** Choose an upload directory that is separate from segment audio files to avoid naming conflicts. A path like `projects/{project_id}/music/` is clean and consistent with the rest of the media structure.

**`music_file: null` on removal:** To support clearing the music file from the frontend, the backend must handle a PATCH request that sets `music_file` to null. Verify that the Django serializer handles nullable FileFields correctly when a null value is passed. A dedicated "remove music" endpoint is an acceptable alternative if nullable FileField PATCH is complex.

**No per-segment music in this feature.** If a future feature adds per-segment music overrides, it should be a separate feature (e.g., Feature 2.2). Keep this implementation strictly project-level.
