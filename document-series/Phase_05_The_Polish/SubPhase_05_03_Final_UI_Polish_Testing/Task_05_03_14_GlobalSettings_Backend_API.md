# Task 05.03.14 — GlobalSettings Backend API

## Layer 3 Task Document

---

| **Field**              | **Value**                                                                                      |
| ---------------------- | ---------------------------------------------------------------------------------------------- |
| **Task ID**            | 05.03.14                                                                                       |
| **Task Name**          | GlobalSettings Backend API                                                                     |
| **Sub-Phase**          | 05.03 — Final UI Polish & Testing                                                              |
| **Phase**              | Phase 05 — The Polish                                                                          |
| **Layer**              | Layer 3 (Task Document)                                                                        |
| **Status**             | Not Started                                                                                    |
| **Estimated Complexity** | High                                                                                         |
| **Parent Document**    | [SubPhase_05_03_Overview.md](./SubPhase_05_03_Overview.md) (Layer 2)                           |
| **Dependencies**       | None (backend foundation — other tasks depend on this)                                         |
| **Output Files**       | `backend/models.py` (MODIFIED — add GlobalSettings model), `backend/serializers.py` (MODIFIED — add GlobalSettingsSerializer), `backend/views.py` (MODIFIED — add GlobalSettingsViewSet), `backend/urls.py` (MODIFIED — add settings routes), `backend/migrations/` (NEW — auto-generated migration) |

---

## Objective

Build the complete Django REST Framework backend for the GlobalSettings feature, including the database model, serializer with validation, API viewset with custom endpoints for settings management, voice listing, and font file upload, plus URL routing.

---

## Instructions

### Step 1 — Create the GlobalSettings Model

Add a `GlobalSettings` model to the existing `backend/models.py` file. This model follows the **singleton pattern** — only one record should ever exist in the database, representing the application's global configuration. Define the following fields:

- `default_voice` — CharField, max_length 100, storing the Kokoro voice identifier string, with a sensible default (e.g., "af_heart").
- `subtitle_font_family` — CharField, max_length 200, default "Arial".
- `subtitle_font_size` — PositiveIntegerField, default 48.
- `subtitle_font_color` — CharField, max_length 7, default "#FFFFFF" (hex color format).
- `subtitle_position` — CharField, max_length 10, choices limited to "bottom", "center", "top", default "bottom".
- `render_width` — PositiveIntegerField, default 1920.
- `render_height` — PositiveIntegerField, default 1080.
- `render_fps` — PositiveIntegerField, default 30.
- `ken_burns_zoom` — FloatField, default 1.2.
- `transition_duration` — FloatField, default 0.5.
- `custom_font_file` — FileField, upload_to "fonts/", null and blank allowed, for storing user-uploaded custom font files.
- `created_at` — DateTimeField, auto_now_add.
- `updated_at` — DateTimeField, auto_now.

Add a `save` method override that enforces the singleton pattern: if a GlobalSettings record already exists and the current instance is a new record (no primary key), raise a ValidationError preventing creation of a second record. Alternatively, override the model's `save` method to always use the same primary key (pk=1).

Run `python manage.py makemigrations` and `python manage.py migrate` to create and apply the migration.

### Step 2 — Build the GlobalSettingsSerializer

Add a `GlobalSettingsSerializer` to `backend/serializers.py` using Django REST Framework's `ModelSerializer`. Include all fields from the GlobalSettings model in the serializer's Meta.fields. Add field-level validation for the following constraints:

- `subtitle_font_size` must be between 12 and 120 (inclusive).
- `subtitle_font_color` must be a valid 7-character hex color string starting with "#" followed by exactly 6 hexadecimal characters.
- `subtitle_position` must be one of the allowed choices ("bottom", "center", "top").
- `ken_burns_zoom` must be between 1.0 and 2.0 (inclusive).
- `transition_duration` must be between 0.0 and 2.0 (inclusive).
- `render_fps` must be one of the allowed values (24, 30, or 60).
- `render_width` and `render_height` must form a valid resolution pair from the allowed presets (1280×720, 1920×1080, 3840×2160).

If any validation fails, return a clear error message identifying the invalid field and the constraint that was violated.

### Step 3 — Build the GlobalSettingsViewSet

Add a `GlobalSettingsViewSet` to `backend/views.py`. This is not a standard ModelViewSet because the settings follow the singleton pattern — there is no list, create, or delete operation. Instead, implement the following custom actions:

- **GET /api/settings/** — Retrieve the current global settings. If no GlobalSettings record exists yet, create one with all default values and return it. This ensures that the first GET request always returns a valid settings object without requiring a separate initialization step.
- **PATCH /api/settings/** — Update the global settings with a partial payload. Accept a JSON body with any subset of settings fields, validate using the serializer, save, and return the full updated settings object. Use `partial=True` on the serializer to allow partial updates.
- **GET /api/settings/voices/** — Return a JSON array of available Kokoro TTS voices. Each voice object should contain the voice identifier, display name, and language. This endpoint does not read from the database — it returns a hardcoded or configuration-derived list of voices that the Kokoro TTS engine supports. The response format should match the `Voice` TypeScript interface defined in the frontend.
- **POST /api/settings/font-upload/** — Accept a multipart form data POST request containing a font file. Validate that the uploaded file has an allowed extension (.ttf, .otf, .woff, .woff2) and does not exceed the maximum file size (10 MB). Save the file to the `fonts/` upload directory, update the GlobalSettings record's `custom_font_file` field to point to the new file, and update the `subtitle_font_family` field to the uploaded font's filename (without extension). Return the updated settings object. If a previous custom font file exists, delete the old file from disk before saving the new one to prevent accumulating unused font files.

### Step 4 — Configure URL Routing

Add URL patterns to `backend/urls.py` that route the settings endpoints. Since the GlobalSettings viewset does not follow the standard DRF router pattern (no list/detail URLs), use explicit `path()` entries:

- `api/settings/` — Maps to the GET (retrieve) and PATCH (update) handler.
- `api/settings/voices/` — Maps to the GET voices handler.
- `api/settings/font-upload/` — Maps to the POST font upload handler.

Ensure the URL patterns are consistent with the existing project and segment URL structure in the application.

### Step 5 — Handle Edge Cases

Address the following edge cases in the implementation:

- First-time access: If no GlobalSettings record exists in the database (fresh install), the GET endpoint should auto-create one with default values. This is the lazy-initialization singleton pattern.
- Concurrent PATCH requests: Since StoryFlow is a single-user local application, concurrent write conflicts are unlikely. However, use `select_for_update()` or simply rely on Django's default save behavior.
- Font file cleanup: When uploading a new font, delete the previous custom font file from disk. When the custom font is reset to a system font, delete the custom font file but do not remove the `fonts/` directory.
- Invalid font file: If the uploaded file is not a valid font (wrong extension, zero bytes, exceeds size limit), return a 400 Bad Request with a descriptive error message.

---

## Expected Output

A complete backend implementation for the GlobalSettings API: a singleton Django model with all settings fields, a serializer with comprehensive validation, a viewset with four endpoints (GET settings, PATCH settings, GET voices, POST font upload), and URL routing configured in the application's URL configuration.

---

## Validation

- [ ] GlobalSettings model has all required fields with correct types and defaults.
- [ ] Singleton pattern enforced — only one GlobalSettings record can exist.
- [ ] First GET request auto-creates the singleton with default values.
- [ ] PATCH request accepts partial updates and returns the full updated object.
- [ ] Serializer validates subtitle_font_size range (12–120).
- [ ] Serializer validates subtitle_font_color as 7-character hex string.
- [ ] Serializer validates subtitle_position choices (bottom, center, top).
- [ ] Serializer validates ken_burns_zoom range (1.0–2.0).
- [ ] Serializer validates transition_duration range (0.0–2.0).
- [ ] Serializer validates render_fps allowed values (24, 30, 60).
- [ ] Serializer validates render resolution presets.
- [ ] GET /api/settings/voices/ returns the list of available Kokoro voices.
- [ ] POST /api/settings/font-upload/ accepts multipart font file upload.
- [ ] Font upload validates file extension and file size.
- [ ] Old custom font file is deleted from disk when a new one is uploaded.
- [ ] URL routing is configured and all four endpoints are accessible.
- [ ] Migration is generated and applied without errors.

---

## Notes

- The singleton pattern for GlobalSettings is a deliberate design choice. Unlike projects or segments, there is no concept of "multiple settings configurations" in StoryFlow v1.0. If multi-profile settings are needed in the future, the model can be refactored to add a profile name and remove the singleton constraint.
- The voices endpoint returns a static list rather than querying the Kokoro model at runtime. This is because discovering available voices from the ONNX model dynamically would require loading the model, which is expensive. The voice list is known at build time and changes only when the Kokoro model is updated.
- Font upload is the most complex endpoint in this task. It combines file validation, disk I/O (save new, delete old), and database update in a single request. Test it thoroughly with valid fonts, oversized files, wrong extensions, and empty files.
- The `fonts/` upload directory should be inside Django's `MEDIA_ROOT`. Ensure that `MEDIA_ROOT` and `MEDIA_URL` are configured in `settings.py` if they are not already.

---

> **Parent:** [SubPhase_05_03_Overview.md](./SubPhase_05_03_Overview.md) (Layer 2)
> **Phase:** [Phase_05_Overview.md](../Phase_05_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
