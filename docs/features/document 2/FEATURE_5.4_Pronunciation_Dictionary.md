# Feature 5.4 — Pronunciation Dictionary

| Field | Value |
|---|---|
| **Feature ID** | 5.4 |
| **Title** | Pronunciation Dictionary for TTS Preprocessing |
| **Status** | 🟡 Planned |
| **Priority** | High |
| **Complexity** | Medium |
| **Estimated Effort** | 4–6 days |
| **Dependencies** | Kokoro ONNX TTS pipeline (tts_wrapper.py), Project model (models.py), REST API layer |
| **Output Files (NEW)** | `backend/api/migrations/xxxx_add_pronunciationentry.py` |
| **Files Modified** | `backend/api/models.py`, `backend/api/serializers.py`, `backend/api/views.py`, `backend/api/urls.py`, `backend/api/admin.py`, `backend/core_engine/tts_wrapper.py` |

---

## 1. Document Overview

### 1.1 Problem Statement

StoryFlow uses the Kokoro ONNX text-to-speech engine to narrate video segments. While Kokoro produces natural-sounding speech for common English words, it consistently mispronounces a class of terms that are extremely common in the types of content StoryFlow is designed to produce — brand names, technical acronyms, proper nouns, and initialisms.

Examples of currently broken pronunciation include:

- "NVIDIA" — spoken as "En-VID-ee-uh" or similar distortion instead of the brand-standard "en-VID-ee-uh" (which may itself need a custom phonetic string)
- "AWS" — spoken as a single syllable or phonetically mangled instead of "A-W-S"
- "GIF" — Kokoro chooses "JIFF" or "GIFF" depending on context, inconsistently
- "SQL" — spoken as a garbled word rather than "S-Q-L" or "sequel" depending on user preference
- "PyTorch" — spoken as "pie-torch" but some content creators prefer "pee-torch" (as per Meta)
- "GTA" — spoken by letter but sometimes merged into one sound

These mispronunciations undermine the professionalism of generated content and require users to manually rewrite their narration text with phonetic workarounds — defeating the purpose of having a template narration system.

There is currently no mechanism in StoryFlow to inject pronunciation corrections either at the global level (affecting all projects) or at the per-project level (for a project-specific brand or term).

### 1.2 Proposed Solution

Introduce a two-layer pronunciation override system composed of:

1. A **global pronunciation dictionary** — a database table of word-to-replacement mappings that apply across every project. These are maintained by administrators and contain universally agreed-upon overrides (such as always expanding "NASA" to "N.A.S.A." for TTS clarity).

2. A **project-level pronunciation dictionary** — per-project entries that override or supplement the global dictionary. A user working on a video about a specific company can add that company's name and its phonetic equivalent without affecting any other project.

Both layers are stored in a new database model called `PronunciationEntry`. Before passing any narration text to the Kokoro TTS engine, a preprocessing function loads all applicable entries for the current project and applies case-insensitive whole-word substitutions. The substituted text is what the TTS engine receives — the original text stored in the segment is never modified.

Additionally, a built-in fallback behavior handles acronyms (words composed entirely of uppercase letters) by inserting periods between letters, converting "NASA" to "N.A.S.A." automatically. This fallback only activates if no explicit dictionary entry is found for that word.

### 1.3 Scope

| In Scope | Out of Scope |
|---|---|
| New `PronunciationEntry` database model with word, replacement, scope, and project fields | Phoneme-level editing (IPA input, SSML markup injection) |
| Global pronunciation entries — created and managed by admin | Automatic pronunciation suggestion powered by any AI/ML model |
| Project-level pronunciation entries — created and managed per-project via API | A visual pronunciation editor UI in the frontend (future feature) |
| Text preprocessing function in `tts_wrapper.py` applied before every TTS call | Modifying the Kokoro model itself or its tokenizer |
| Acronym auto-expansion fallback (uppercase-only words get period-separated letters) | Real-time preview of pronunciation changes without re-rendering |
| Admin registration of `PronunciationEntry` in Django admin panel | Batch import of pronunciation dictionaries from external file formats |
| REST API endpoints for CRUD on both scopes | Per-segment pronunciation overrides (segment granularity is not needed at this stage) |
| Django migration generated for the new model | Support for languages other than English |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| `backend/core_engine/tts_wrapper.py` | Runs text through the Kokoro ONNX model, saves WAV output | Contains `generate_audio(text, voice_id, speed, output_path)` — text is passed directly to the TTS model with no preprocessing |
| `backend/api/models.py` | Defines database models for the application | Contains `Project` and `Segment` models; no pronunciation-related model exists |
| `backend/api/serializers.py` | Converts model instances to/from JSON for the API | Contains serializers for Project and Segment; needs new serializer for `PronunciationEntry` |
| `backend/api/views.py` | Handles HTTP requests and delegates to business logic | Contains DRF viewsets for Project and Segment; needs new viewsets for pronunciation endpoints |
| `backend/api/urls.py` | Maps URL patterns to views | Needs two new URL groups: per-project and global pronunciation routes |
| `backend/api/admin.py` | Registers models for the Django admin interface | Currently registers Project and Segment; needs `PronunciationEntry` registered |

---

## 2. Flow Diagram

    User saves a pronunciation entry via API
               │
               ▼
    PronunciationEntry stored in database
    (scope: "global" or "project", with optional project FK)
               │
               ▼
    Render job triggered — render_project(project_id) called
               │
               ▼
    For each segment in the project:
               │
               ▼
    generate_audio(text, voice_id, speed, output_path) called
               │
               ▼
    preprocess_text_for_tts(text, project_id) called FIRST
               │
       ┌───────┴───────┐
       │               │
    Load global     Load project-level
    entries         entries for project_id
       │               │
       └───────┬───────┘
               │
               ▼
    For each entry: apply regex whole-word case-insensitive
    substitution to text string
               │
               ▼
    Run acronym fallback: any remaining ALL-CAPS words
    get period insertion (e.g., "AWS" → "A.W.S.")
               │
               ▼
    Return modified text → pass to Kokoro TTS engine
               │
               ▼
    WAV file saved to media/projects/{id}/audio/{seg_id}.wav

---

## 3. Step-by-Step Instructions

### Step 3.1 — Define the PronunciationEntry Model

Open `backend/api/models.py` and add a new model class named `PronunciationEntry` beneath the existing models. The model should have the following fields:

- A `word` field as a CharField with a reasonable max length (e.g., 200 characters). This stores the original word or phrase as it would appear in narration text — the thing to be matched and replaced.
- A `replacement` field as a CharField with a slightly longer max length (e.g., 500 characters). This stores the phonetic substitute or alternative text that will be spoken by the TTS engine instead.
- A `scope` field as a CharField with choices restricted to the strings "global" and "project". The default value should be "project". This determines whether the entry applies to all projects or just one.
- A `project` field as a ForeignKey to the `Project` model, with `on_delete=SET_NULL`, `null=True`, and `blank=True`. When `scope` is "global", this field is left null. When `scope` is "project", this field points to the owning project.
- A `created_at` field as an auto-populated DateTimeField.

Add a `Meta` class with `unique_together` set to prevent duplicate word entries within the same project (and separately, duplicate global entries for the same word). Also add a `__str__` method that returns something descriptive like the word and its scope.

After adding the model, generate a migration by running the standard Django migration command in the terminal. Confirm the migration file appears in `backend/api/migrations/`.

### Step 3.2 — Write the Serializer

Open `backend/api/serializers.py` and add a `PronunciationEntrySerializer` class that targets the `PronunciationEntry` model. All fields should be included. The `project` field should be read-only or set automatically from the URL context — it should not be a writable field that users supply in the request body, since it is inferred from the URL parameter. Add a validation method that checks: if `scope` is "global", the `project` field must be null; if `scope` is "project", a project reference is required.

### Step 3.3 — Create the Views

Open `backend/api/views.py` and add two new viewsets:

First, a `ProjectPronunciationViewSet` that handles CRUD for pronunciation entries scoped to a specific project. The queryset for this view should filter `PronunciationEntry` objects by the project ID taken from the URL kwargs. The `perform_create` method should automatically assign the project and set `scope` to "project" before saving. Only the owning user of the project (or staff) should be allowed to read or modify its pronunciation entries.

Second, a `GlobalPronunciationViewSet` that handles CRUD for global pronunciation entries. The queryset should filter for entries where `scope` is "global". Write operations on this viewset should be restricted to admin/staff users only. Read operations can be available to any authenticated user.

### Step 3.4 — Register the URL Routes

Open `backend/api/urls.py` and add the new routes. The project-scoped pronunciation endpoints should live at the path `api/projects/{project_id}/pronunciation/`, supporting list, create, detail, update, and delete operations. The global pronunciation endpoints should live at `api/pronunciation-global/`, also with full CRUD support.

Make sure the URL configuration correctly passes the `project_id` as a kwarg available to the Project-scoped viewset.

### Step 3.5 — Register in Admin

Open `backend/api/admin.py` and register the `PronunciationEntry` model. Add a ModelAdmin class that customises the list display to show the word, replacement, scope, and project fields for rapid browsing. Add a list filter for `scope` so administrators can quickly toggle between global and project-level entries. Add a search field over the `word` and `replacement` columns.

### Step 3.6 — Write the Preprocessing Function

Open `backend/core_engine/tts_wrapper.py` and add a new standalone function called `preprocess_text_for_tts`. This function accepts two arguments: `text` (the narration string) and `project_id` (an integer or None).

Inside the function, perform the following steps in order:

First, query the database for all `PronunciationEntry` records where `scope` is "global". Query separately for all entries where `scope` is "project" and `project_id` matches the supplied value. Combine both lists into a single ordered list where project-level entries take priority over global entries for the same word (meaning, if both a global and a project entry exist for "GIF", use the project one).

Second, iterate over the combined entry list. For each entry, construct a regular expression pattern using the `word` value as the match target, applying word-boundary anchors on both sides and the case-insensitive flag. Apply the substitution to the running text string, replacing matches with the `replacement` value.

Third, after all explicit entries have been applied, apply the acronym auto-expansion fallback. Scan the resulting text for any remaining token that consists entirely of two or more uppercase ASCII letters (using a word-boundary regex). For each such token that was not already substituted in the previous step, insert a period between each letter. For example, "AWS" becomes "A.W.S." and "SQL" becomes "S.Q.L.".

Return the fully preprocessed text string.

### Step 3.7 — Integrate the Preprocessor into generate_audio

Open `backend/core_engine/tts_wrapper.py` and locate the `generate_audio` function. At the very beginning of the function body — before any interaction with the Kokoro model or any audio-related code — add a call to `preprocess_text_for_tts`, passing the incoming `text` argument and the `project_id`. Replace the local `text` variable with the returned preprocessed string. All subsequent code within `generate_audio` should use this preprocessed text.

Ensure that `generate_audio`'s signature is updated to accept a `project_id` parameter. This parameter should default to `None` so that existing calls that do not pass a project ID continue to work (in that case, only global entries are applied, and the acronym fallback still runs).

### Step 3.8 — Update Callers of generate_audio

Identify every place in the codebase that calls `generate_audio` and passes a text string. The primary caller is `video_renderer.py`. Update each call site to also pass the `project_id` of the currently rendering project. Since `render_project(project_id)` already has the project ID in scope, this change is straightforward.

Also check `backend/api/tasks.py` (Celery task definitions) for any direct calls to `generate_audio` and update those as well.

### Step 3.9 — Write Tests

Create or extend a test file at `backend/api/tests.py` (or a dedicated test module). Write unit tests that cover:

- Inserting a global pronunciation entry and verifying that preprocessing replaces the word.
- Inserting a project-level entry and verifying it replaces the word only for that project.
- Verifying project-level entries override global entries when both exist for the same word.
- Verifying the acronym fallback correctly expands an all-caps word that has no explicit entry.
- Verifying that a word with a mixed-case entry is matched case-insensitively.
- Verifying that the `generate_audio` function calls `preprocess_text_for_tts` internally (mock the preprocessor and assert it was called with the correct arguments).

---

## 4. Expected Outcome

1. A `PronunciationEntry` table exists in the database with the correct schema, accessible through Django admin.
2. Administrators can create global pronunciation entries that apply to every project on the platform.
3. Project owners can create, update, and delete project-specific pronunciation entries through the REST API without touching any other project.
4. Before every TTS audio generation call, the narration text is silently preprocessed — all matching words are replaced with their configured alternatives.
5. Brand names, technical acronyms, and initialisms that previously caused garbled audio now produce correct and consistent pronunciation in rendered videos.
6. Any all-uppercase word that lacks an explicit dictionary entry is automatically expanded with period separators, improving TTS clarity for unrecognized acronyms.
7. The original narration text stored in the `Segment` model is never modified — preprocessing is ephemeral and only affects what is passed to the TTS engine at render time.
8. The full CRUD API for pronunciation entries is functional and documented, enabling future frontend integration.
9. All new code is covered by unit and integration tests that pass in CI.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- `PronunciationEntry` model saves correctly with valid data for both scopes.
- `PronunciationEntry` model raises a validation error when `scope` is "global" but a `project` FK is supplied.
- `PronunciationEntry` model raises a validation error when `scope` is "project" but no project FK is supplied.
- `preprocess_text_for_tts` applies a global entry correctly to input text.
- `preprocess_text_for_tts` applies a project entry correctly when a matching project ID is passed.
- `preprocess_text_for_tts` applies project entry in preference to a conflicting global entry.
- `preprocess_text_for_tts` does not apply a project entry when `project_id=None` is passed.
- Acronym fallback expands "AWS" to "A.W.S." in the absence of an explicit entry.
- Acronym fallback does not double-expand a word that already has an explicit entry.
- Word-boundary enforcement: the word "GIF" inside "GIFTED" is not replaced.

### 5.2 Integration / Manual Tests

- POST a new project-level pronunciation entry via the API, then trigger a render and confirm the generated WAV file (transcribed manually or by ear) reflects the substitution.
- POST a new global pronunciation entry via the admin panel, then confirm it is applied in a render for a project that has no project-level entry for the same word.
- POST both a project-level and a global entry for the same word, trigger a render, and confirm the project-level entry wins.
- Confirm that the pronunciation endpoint returns a 403 for unauthenticated requests.
- Confirm that the global pronunciation endpoint returns a 403 for non-admin authenticated requests on write operations.
- Confirm the admin list view correctly filters entries by scope.

### 5.3 Regression Tests

- Render a project that has no pronunciation entries and confirm output is identical to pre-feature behavior (no regressions in audio quality or file paths).
- Confirm that `generate_audio` called without a `project_id` argument still works correctly (default None fallback).
- Confirm that existing TTS rendering tests in `backend/core_engine/tests/` are still passing after the signature change to `generate_audio`.
- Confirm that the Django migration applies cleanly on a fresh database and on a database that already contains existing project data.

---

## 6. Notes for AI Agent

- The preprocessing function must be positioned as the absolute first operation inside `generate_audio`, before any model loading or inference call. Do not place it after any lazy-loading checks or device-detection logic.
- When applying substitutions, the order of entries matters. Apply project-level entries before global entries in the replacement loop so that a project entry can intentionally override a global one for the same word.
- The regex pattern for each entry must use `re.IGNORECASE` so entries created in one casing match text in any casing. The replacement string should preserve whatever casing the user specified in the `replacement` field — do not auto-case the replacement.
- The acronym fallback regex should only target tokens of two or more uppercase characters. Single-letter uppercase words like "I" or "A" must not be expanded.
- The fallback should be applied after all explicit substitutions are complete so that explicitly replaced words are not also run through the fallback logic.
- The `project_id` parameter added to `generate_audio` should be a keyword argument with default `None` to maintain backward compatibility with any test or utility code that calls it without a project context.
- If the database is unavailable during a render (e.g., in a test environment with mocked Django ORM), the preprocessing function should gracefully return the original unmodified text rather than raising an exception.
- Future frontend work (Feature 5.4-UI) will add a pronunciation management screen — this feature intentionally stops at the API layer. Do not build any frontend components as part of this feature.
- The `unique_together` constraint on `PronunciationEntry` should cover the combination of `word` and `project` (for project-scoped entries) and separately `word` with a null project check (for global entries). This may require a custom database constraint or a model-level `validate_unique` override since Django does not natively support unique constraints involving null fields in all database backends. A clean solution is to use a partial unique index in the migration rather than relying solely on Django's `unique_together`.
- When writing tests, mock the database query inside `preprocess_text_for_tts` using Django's test fixtures or factory methods rather than hitting the actual SQLite database in unit tests — this keeps tests fast and isolated.
