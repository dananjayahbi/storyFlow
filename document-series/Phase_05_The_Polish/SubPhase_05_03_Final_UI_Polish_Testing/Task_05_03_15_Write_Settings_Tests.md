# Task 05.03.15 — Write Settings Tests

## Layer 3 Task Document

---

| **Field**              | **Value**                                                                                      |
| ---------------------- | ---------------------------------------------------------------------------------------------- |
| **Task ID**            | 05.03.15                                                                                       |
| **Task Name**          | Write Settings Tests                                                                           |
| **Sub-Phase**          | 05.03 — Final UI Polish & Testing                                                              |
| **Phase**              | Phase 05 — The Polish                                                                          |
| **Layer**              | Layer 3 (Task Document)                                                                        |
| **Status**             | Not Started                                                                                    |
| **Estimated Complexity** | Medium                                                                                       |
| **Parent Document**    | [SubPhase_05_03_Overview.md](./SubPhase_05_03_Overview.md) (Layer 2)                           |
| **Dependencies**       | Task 05.03.14 (GlobalSettings Backend API must be implemented to test against)                 |
| **Output Files**       | `backend/tests/test_settings.py` (NEW)                                                         |

---

## Objective

Write a comprehensive suite of Django REST Framework API tests covering all GlobalSettings endpoints — settings retrieval, partial updates, validation enforcement, voice listing, and font file upload — ensuring that the settings backend behaves correctly under normal and edge-case conditions.

---

## Instructions

### Step 1 — Set Up the Test Class

Create `backend/tests/test_settings.py` with a `GlobalSettingsAPITests` class that extends Django REST Framework's `APITestCase`. Import the necessary testing utilities, the GlobalSettings model, and set up the base URL constants for the four settings endpoints. In the `setUp` method, clear any existing GlobalSettings records to ensure a clean state for each test. No authentication setup is needed since StoryFlow has no authentication system.

### Step 2 — Write Settings Retrieval Tests

Write tests covering the GET settings endpoint:

- **Test auto-creation on first access** — Send a GET request when no GlobalSettings record exists. Assert that the response returns 200 OK, that a GlobalSettings record was created in the database, and that all returned values match the defined defaults (default voice, default font, default resolution, etc.).
- **Test retrieving existing settings** — Pre-create a GlobalSettings record with custom values. Send a GET request and assert that the returned values match the custom values, not the defaults.
- **Test response structure** — Assert that the response JSON contains all expected fields (default_voice, subtitle_font_family, subtitle_font_size, subtitle_font_color, subtitle_position, render_width, render_height, render_fps, ken_burns_zoom, transition_duration, created_at, updated_at).

### Step 3 — Write Settings Update Tests

Write tests covering the PATCH settings endpoint:

- **Test partial update of a single field** — Send a PATCH request changing only `default_voice` to a different value. Assert 200 OK, that the returned settings show the new voice, and that all other fields remain unchanged.
- **Test partial update of multiple fields** — Send a PATCH request changing `subtitle_font_size`, `subtitle_font_color`, and `subtitle_position` simultaneously. Assert that all three fields are updated and other fields are unchanged.
- **Test update persistence** — After a successful PATCH, send a GET request and confirm the changes are persisted in the database.
- **Test no-op update** — Send a PATCH request with an empty body. Assert 200 OK and that the settings remain unchanged.

### Step 4 — Write Validation Tests

Write tests covering serializer validation on the PATCH endpoint:

- **Test font size below minimum** — Send a PATCH with `subtitle_font_size: 5`. Assert 400 Bad Request with an appropriate error message.
- **Test font size above maximum** — Send a PATCH with `subtitle_font_size: 200`. Assert 400 Bad Request.
- **Test invalid hex color format** — Send a PATCH with `subtitle_font_color: "red"`. Assert 400 Bad Request. Also test `subtitle_font_color: "#GGG"` (invalid hex characters) and `subtitle_font_color: "#FF"` (too short).
- **Test invalid subtitle position** — Send a PATCH with `subtitle_position: "left"`. Assert 400 Bad Request.
- **Test zoom level out of range** — Send a PATCH with `ken_burns_zoom: 0.5`. Assert 400. Test with `ken_burns_zoom: 3.0`. Assert 400.
- **Test transition duration out of range** — Send a PATCH with `transition_duration: -1.0`. Assert 400. Test with `transition_duration: 5.0`. Assert 400.
- **Test invalid FPS value** — Send a PATCH with `render_fps: 45`. Assert 400 (only 24, 30, 60 allowed).
- **Test valid boundary values** — Send a PATCH with values at the exact minimum and maximum boundaries (font size 12, font size 120, zoom 1.0, zoom 2.0, etc.). Assert 200 OK for all boundary values.

### Step 5 — Write Voice Listing Tests

Write tests covering the GET voices endpoint:

- **Test voices list returned** — Send a GET request to the voices endpoint. Assert 200 OK and that the response is a non-empty JSON array.
- **Test voice object structure** — Assert that each voice object in the response contains at minimum: identifier, display_name, and language fields.
- **Test voice count** — Assert that the number of returned voices matches the expected count of available Kokoro voices.

### Step 6 — Write Font Upload Tests

Write tests covering the POST font upload endpoint:

- **Test successful font upload** — Create a temporary `.ttf` file using Django's `SimpleUploadedFile`. Send a POST request with the font file as multipart form data. Assert 200 OK, that the response contains the updated settings, and that the `custom_font_file` field is now populated.
- **Test invalid file extension** — Attempt to upload a `.txt` file. Assert 400 Bad Request with an error message about invalid file type.
- **Test oversized file** — Attempt to upload a file exceeding the 10 MB limit. Assert 400 Bad Request.
- **Test font replacement** — Upload a font file, then upload a second font file. Assert that the second upload succeeds, the settings reflect the new font, and the first font file is cleaned up from disk (or at minimum, the settings no longer reference it).

---

## Expected Output

A `test_settings.py` file containing approximately 19 test methods organized in a single `GlobalSettingsAPITests` class, covering settings retrieval (3 tests), settings updates (4 tests), validation (8 tests), voice listing (3 tests), and font upload (4 tests). All tests should be runnable via `python manage.py test`.

---

## Validation

- [ ] All tests pass when run via `python manage.py test`.
- [ ] Auto-creation test confirms the singleton is lazily initialized on first GET.
- [ ] Partial update tests confirm that unmodified fields are preserved.
- [ ] All validation boundary conditions (min, max, invalid) are tested.
- [ ] Invalid hex color format is rejected with a descriptive error.
- [ ] Invalid FPS values are rejected.
- [ ] Voices endpoint returns the expected number of voices with correct structure.
- [ ] Font upload test uploads a valid file and confirms settings are updated.
- [ ] Invalid font file extensions and oversized files are rejected.
- [ ] Font replacement test confirms old files are cleaned up.
- [ ] Test class uses `setUp` to ensure clean state between tests.

---

## Notes

- These tests form the safety net for the entire settings subsystem. Every validation rule in the serializer should have a corresponding negative test (send invalid data, expect 400) and a boundary test (send the minimum/maximum valid value, expect 200).
- Font upload tests require creating temporary files. Use Django's `SimpleUploadedFile` which creates in-memory file objects that behave like uploaded files without needing to write actual files to disk.
- The test count of ~19 is approximate. Additional edge cases discovered during implementation should be added. The goal is comprehensive coverage, not hitting a specific number.
- These backend tests complement the frontend E2E tests (Task 05.03.16). The backend tests validate the API contract in isolation, while the E2E tests validate the full stack integration.

---

> **Parent:** [SubPhase_05_03_Overview.md](./SubPhase_05_03_Overview.md) (Layer 2)
> **Phase:** [Phase_05_Overview.md](../Phase_05_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
