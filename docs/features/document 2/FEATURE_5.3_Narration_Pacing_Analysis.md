# Feature 5.3 — Narration Pacing Analysis

| Field | Value |
|---|---|
| **Feature ID** | 5.3 |
| **Title** | Narration Pacing Analysis |
| **Status** | 🟡 Planned |
| **Priority** | Medium |
| **Complexity** | Low |
| **Estimated Effort** | 2 day(s) |
| **Dependencies** | TTS pipeline must be functional; `get_audio_duration()` in `audio_utils.py` must be working |
| **Output Files (NEW)** | None |
| **Files Modified** | `backend/core_engine/audio_utils.py`, `backend/api/models.py`, `backend/api/serializers.py`, `backend/api/views.py`, `backend/api/urls.py`, `backend/api/tasks.py` |

---

## 1. Document Overview

### 1.1 Problem Statement

Once a creator writes script text for a segment and generates TTS audio in StoryFlow, they currently receive no automated feedback about the narration speed. The only way to evaluate pacing is to listen to the full audio, which requires the generation step to have already completed successfully. If the narration is too fast, words blur together and the audience cannot absorb the content. If it is too slow, the video feels sluggish and viewers disengage. Creators of educational and explainer content typically need to target specific words-per-minute ranges to match audience expectations, yet the platform gives them no objective metric to guide those decisions. The absence of pacing feedback means creators must rely entirely on subjective listening, often after spending time waiting for audio generation, and then must re-write and regenerate if the pacing is wrong. Repeating this loop across many segments is slow and errors compound across a full project.

### 1.2 Proposed Solution

Add a lightweight pacing analysis calculation that runs automatically whenever TTS audio is generated for a segment, stores the result in the database, and is also available on demand through a dedicated read endpoint.

Key solution components:

- A new `calculate_pacing` function in `audio_utils.py` that accepts raw text and audio duration in seconds, computes words-per-minute, classifies the result against defined WPM threshold ranges, and returns a structured result dictionary.
- A new `pacing_wpm` nullable float field on the `Segment` model to persist the most recent pacing metric alongside the audio file reference.
- Updates to the `generate_segment_tts_task` Celery task so that after audio generation succeeds, pacing is calculated and stored on the segment, and also included in the task result payload so the frontend can display it inline with the generation completion event.
- A new `GET /api/projects/{id}/segments/{seg_id}/pacing/` endpoint that computes and returns pacing on demand for segments that already have audio, without needing to regenerate TTS.
- Serializer updates to expose `pacing_wpm` on the segment representation so dashboard and timeline components can read it without additional API calls.
- Defined WPM classification ranges: below 130 = "slow", 130–150 = "calm/educational", 150–170 = "normal", 170–200 = "fast/energetic", above 200 = "very fast".

### 1.3 Scope

| In Scope | Out of Scope |
|---|---|
| Computing WPM from word count and audio duration | Syllable-rate or phoneme-level analysis |
| Classifying WPM into five named speed categories | Machine-learning based quality scoring |
| Storing `pacing_wpm` on the `Segment` model | Storing full pacing history per segment over time |
| Returning pacing in the TTS task completion result | Real-time pacing preview before audio generation |
| A dedicated GET endpoint for on-demand pacing retrieval | Bulk pacing analysis across all segments in one call |
| Handling missing audio gracefully (returning null pacing) | Audio waveform or rhythm analysis |
| Serializer field for `pacing_wpm` | Automatic script rewriting suggestions based on pacing |
| Frontend WPM badge and color classification display (described, not implemented here) | Frontend implementation details beyond API contract |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| `backend/core_engine/audio_utils.py` | Audio utility functions; houses `get_audio_duration()` and `normalize_audio()` | Functional; needs new `calculate_pacing()` function |
| `backend/api/models.py` | Django ORM models for `Project` and `Segment` | Functional; `Segment` needs new `pacing_wpm` FloatField |
| `backend/api/serializers.py` | DRF serializers for API response shaping | Functional; `SegmentSerializer` needs `pacing_wpm` field added |
| `backend/api/views.py` | REST API view handlers | Functional; needs new `PacingView` for the GET endpoint |
| `backend/api/urls.py` | URL routing configuration | Functional; needs one new URL pattern |
| `backend/api/tasks.py` | Celery tasks; `generate_segment_tts_task` creates audio | Functional; task must call `calculate_pacing` and store result after audio creation |
| `backend/api/migrations/` | Django database migrations | New migration needed for `pacing_wpm` field addition |

---

## 2. Flow Diagram

```
  ┌───────────────────────────────────────────────────────────┐
  │                AUTOMATIC PATH (on TTS generation)         │
  └───────────────────────────────────────────────────────────┘

User triggers TTS generation for a segment
              │
              ▼
  tasks.py: generate_segment_tts_task(project_id, segment_id)
              │
              ├─ Fetch Segment from DB (text_content)
              ├─ Call generate_audio(...) → writes WAV to disk
              ├─ Call get_audio_duration(audio_path) → duration_seconds
              ├─ Call calculate_pacing(text_content, duration_seconds)
              │         │
              │         ▼
              │   audio_utils.py: calculate_pacing()
              │         ├─ word_count = len(text.split())
              │         ├─ wpm = (word_count / duration_seconds) * 60
              │         ├─ classification = classify_wpm(wpm)
              │         └─ return { wpm, classification, word_count, duration }
              │
              ├─ Update Segment.pacing_wpm = result.wpm
              ├─ Save Segment to DB
              └─ Return task result including pacing dict
                          │
                          ▼
          Frontend receives task completion event
          Displays WPM badge and color classification inline
          (no second API call needed)


  ┌───────────────────────────────────────────────────────────┐
  │              ON-DEMAND PATH (dedicated endpoint)          │
  └───────────────────────────────────────────────────────────┘

User opens a segment that already has audio
              │
              ▼
GET /api/projects/{id}/segments/{seg_id}/pacing/
              │
              ▼
  views.py: PacingView
              │
              ├─ Fetch Project (404 if not found)
              ├─ Fetch Segment belonging to Project (404 if not found)
              ├─ Check Segment.audio_file is set (400 if missing)
              ├─ Call get_audio_duration(segment.audio_file path)
              ├─ Call calculate_pacing(segment.text_content, duration)
              └─ Return { wpm, classification, word_count, duration,
                          segment_id, cached_wpm: segment.pacing_wpm }

              │
              ▼
          Frontend renders color-coded WPM badge

  CLASSIFICATION MAP:
  ─────────────────────────────────────────────────
  < 130 WPM     →  "slow"              (blue)
  130–150 WPM   →  "calm/educational"  (blue)
  150–170 WPM   →  "normal"            (green)
  170–200 WPM   →  "fast/energetic"    (yellow)
  > 200 WPM     →  "very fast"         (red)
  ─────────────────────────────────────────────────
```

---

## 3. Step-by-Step Instructions

### Step 3.1 — Add `calculate_pacing` to `audio_utils.py`

Open `backend/core_engine/audio_utils.py`. At the bottom of the file, after all existing utility functions, add a new function named `calculate_pacing`. This function takes two arguments: `text` (a string containing the narration script) and `audio_duration_seconds` (a float representing the total length of the generated audio).

Inside the function, start by handling the edge cases. If `audio_duration_seconds` is zero, None, or negative, the function should return a dictionary with `wpm` set to zero, `classification` set to `"unknown"`, `word_count` set to zero, and `duration` set to the provided value. This prevents a division-by-zero error.

Next, calculate the word count by splitting the text on whitespace after stripping leading and trailing spaces. Use a simple whitespace split — do not attempt to strip punctuation or use elaborate tokenisation, since the goal is a fast and repeatable metric consistent with how most WPM calculators work. Store this as `word_count`.

Calculate WPM as `(word_count / audio_duration_seconds) * 60` and store it as a float rounded to two decimal places.

Determine the classification by comparing WPM to the defined thresholds. If WPM is below 130, the classification is `"slow"`. If WPM is between 130 (inclusive) and 150 (exclusive), the classification is `"calm"`. If WPM is between 150 (inclusive) and 170 (exclusive), the classification is `"normal"`. If WPM is between 170 (inclusive) and 200 (exclusive), the classification is `"fast"`. If WPM is 200 or above, the classification is `"very_fast"`. Store this as a string.

Return a dictionary with the keys `wpm`, `classification`, `word_count`, and `duration`. The `duration` key should echo back the `audio_duration_seconds` argument for convenience.

Add a companion helper function named `classify_wpm` that only takes a float WPM value and returns the classification string. Call this from `calculate_pacing` so the classification logic is independently testable.

### Step 3.2 — Add `pacing_wpm` field to the `Segment` model

Open `backend/api/models.py`. Locate the `Segment` model class definition. After the `duration` field (or after `audio_file`, whichever is more logical given the existing field ordering), add a new field named `pacing_wpm` using `models.FloatField`. Set it to be nullable (`null=True`) and blank-able (`blank=True`) with a default of `None`. Add a `help_text` argument explaining that this field stores the words-per-minute value from the most recent TTS generation and is `None` until audio has been generated.

Do not add any logic directly to the model class for computing pacing — the model field is a storage-only concern, and the calculation lives in `audio_utils.py` as described in Step 3.1.

After saving the model file, create a new database migration. Run `python manage.py makemigrations api` from the `backend/` directory with the migration name `add_pacing_wpm_to_segment`. Review the generated migration file to confirm it adds a single nullable float column to the `api_segment` table.

### Step 3.3 — Expose `pacing_wpm` in `SegmentSerializer`

Open `backend/api/serializers.py`. Locate the `SegmentSerializer` class. Add `pacing_wpm` to the serializer's `fields` declaration (whether it uses `Meta.fields = '__all__'` or an explicit list). If an explicit field list is used, append `"pacing_wpm"` to it.

If the existing serializer uses any field-level configuration such as `read_only_fields` or `extra_kwargs`, add `pacing_wpm` to `read_only_fields` since it is computed server-side and should not be writable through the standard segment update endpoint. The client should never be able to submit a fake pacing value via a PATCH or PUT request.

No new serializer class is needed for the pacing endpoint — that view will return a plain dictionary response built directly in the view function.

### Step 3.4 — Update `generate_segment_tts_task` in `tasks.py`

Open `backend/api/tasks.py`. Locate the `generate_segment_tts_task` function. This task currently calls `generate_audio` to produce the WAV file and then updates `Segment.audio_file`. Extend it as follows.

After the audio file has been successfully written to disk and before the function returns its result, add the pacing calculation. Import `calculate_pacing` from `core_engine.audio_utils` at the top of the file (or within the function body if circular imports are a concern). Import `get_audio_duration` from the same module if it is not already imported.

Call `get_audio_duration` with the newly created audio file path to obtain the duration in seconds. Then call `calculate_pacing` with the segment's `text_content` and the duration. Store the returned dictionary in a local variable named something like `pacing_result`.

Update `Segment.pacing_wpm` with the `wpm` value from the result. Call `segment.save(update_fields=["audio_file", "pacing_wpm", "duration"])` to persist both the audio file path and the new pacing value in a single database write. Wrap this entire pacing calculation block in a try/except so that if `calculate_pacing` or `get_audio_duration` raises an unexpected error, the task still completes successfully and only logs a warning — the audio generation itself should not fail due to a pacing calculation error.

In the dictionary that the task returns as its result, add a `pacing` key whose value is the `pacing_result` dictionary. This lets the frontend Celery result consumer read pacing data from the task result without making a second HTTP request.

### Step 3.5 — Add the `PacingView` in `views.py`

Open `backend/api/views.py`. Add a new view class or function named `PacingView` that handles `GET` requests only.

In the handler, extract `project_id` and `segment_id` from the URL kwargs. Query the database for the `Project` and return a 404 if not found. Query for the `Segment` filtered by both its own ID and the project foreign key, returning a 404 if not found. This double-filtering ensures that a segment ID from another project cannot be accessed through a different project's URL.

Check that `segment.audio_file` has a value and that the referenced file actually exists on disk. If the field is empty, return a 400 response with a message stating that no audio has been generated for this segment yet. If the field has a value but the file is missing from disk, return a 404 with a message indicating the audio file is not present.

Call `get_audio_duration` with the full absolute path to the audio file. Then call `calculate_pacing` with `segment.text_content` and the duration. Build a response dictionary containing `segment_id`, `wpm`, `classification`, `word_count`, `duration`, and `cached_wpm` (which is `segment.pacing_wpm` — the last stored value from the most recent generation). Include `cached_wpm` so the frontend can compare the live calculation to the stored value and detect any inconsistency (which would indicate the text was edited after audio was generated). Return this dictionary with a 200 status code.

### Step 3.6 — Register the new URL pattern in `urls.py`

Open `backend/api/urls.py`. Add one new URL pattern to `urlpatterns`. Route `projects/<int:project_id>/segments/<int:segment_id>/pacing/` to `PacingView` with the name `segment-pacing`. Place this pattern near the other segment-level URL patterns for readability.

### Step 3.7 — Apply the migration

From the `backend/` directory, run `python manage.py migrate` to apply the migration that adds `pacing_wpm` to the `api_segment` table. Verify the migration completes without errors. If the project uses a CI pipeline, ensure the new migration file is committed to version control. After migration, perform a quick sanity check by opening the Django shell and confirming that `Segment` instances have a `pacing_wpm` attribute that returns `None` for existing records.

### Step 3.8 — Document the API contract for the new pacing endpoint

Add an inline docstring to `PacingView` that describes the endpoint behaviour. The GET endpoint accepts no request body. The URL parameters are `project_id` (integer) and `segment_id` (integer). The optional query parameter `?live=true` forces a live recalculation from disk rather than returning the cached value. The success response (HTTP 200) is a JSON object containing `segment_id` (integer), `wpm` (float), `classification` (string — one of `"slow"`, `"calm"`, `"normal"`, `"fast"`, `"very_fast"`, or `"unknown"`), `word_count` (integer), `duration` (float, seconds), and `cached_wpm` (float or null). Document error responses: 400 when no audio has been generated, 404 when the project or segment is not found, and 404 when the audio file is referenced in the database but absent from disk.

### Step 3.9 — Wire pacing data into the segment list endpoint

Open `backend/api/views.py` and locate the existing segment list or segment detail view. Confirm that these views use `SegmentSerializer` to produce their responses. Because `pacing_wpm` has been added to the serializer in Step 3.3, no additional change is required for these views to return pacing data. Perform a manual API call against the segment list endpoint after completing Steps 3.1 through 3.7 to confirm that `pacing_wpm` appears in the response payload. If it does not, double-check the `Meta.fields` setting in `SegmentSerializer`.

---

## API Contract Reference

| Endpoint | Method | Query Params | Response Fields | Key Error Codes |
|---|---|---|---|---|
| `/api/projects/{id}/segments/{seg_id}/pacing/` | GET | `live=true` (optional) | `segment_id`, `wpm`, `classification`, `word_count`, `duration`, `cached_wpm` | 400 no audio; 404 segment not found; 404 file missing |
| Segment list / detail (existing) | GET | — | Includes `pacing_wpm` (float or null) via serializer | — |

## WPM Classification Reference Table

| WPM Range | Classification Key | Recommended Use Case | Frontend Badge Colour |
|---|---|---|---|
| Below 130 | `slow` | Meditation, guided exercises | Blue |
| 130 – 149 | `calm` | Educational lectures, tutorials | Light blue |
| 150 – 169 | `normal` | General narration, explainers | Green |
| 170 – 199 | `fast` | Marketing, energetic content | Yellow |
| 200 and above | `very_fast` | Rapid summaries, trailers | Red |

---

## 4. Expected Outcome

1. After TTS generation completes for any segment, the segment's `pacing_wpm` field in the database is populated with the computed WPM value.
2. The Celery task result payload for `generate_segment_tts_task` includes a `pacing` dictionary with `wpm`, `classification`, `word_count`, and `duration` keys.
3. A `GET` request to `/api/projects/1/segments/3/pacing/` for a segment with existing audio returns a JSON object containing `wpm`, `classification`, `word_count`, `duration`, and `cached_wpm`.
4. A `GET` request to the pacing endpoint for a segment with no audio file returns a clear 400 error.
5. The `SegmentSerializer` response includes a `pacing_wpm` field for every segment, which is `null` for segments that have not yet had audio generated and a float value for those that have.
6. The `calculate_pacing` function correctly maps WPM values to the five defined classifications across the full range from below 130 to above 200 WPM.
7. Passing zero duration or empty text to `calculate_pacing` returns a safe fallback result without raising an exception.
8. The pacing calculation does not affect the outcome of TTS generation — if pacing calculation fails internally, the audio file is still saved and the task result still indicates success.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- Test that `classify_wpm` returns `"slow"` for values below 130.
- Test that `classify_wpm` returns `"calm"` for values of exactly 130 and for values of 149.
- Test that `classify_wpm` returns `"normal"` for values of exactly 150 and for values of 169.
- Test that `classify_wpm` returns `"fast"` for values of exactly 170 and for values of 199.
- Test that `classify_wpm` returns `"very_fast"` for values of exactly 200 and above.
- Test that `calculate_pacing` returns `wpm = 0` and `classification = "unknown"` when `audio_duration_seconds` is zero.
- Test that `calculate_pacing` returns the correct `word_count` for a known sentence (e.g., "The quick brown fox" has 4 words).
- Test that `calculate_pacing` computes WPM correctly for a 30-word passage at 10 seconds duration (expected: 180.0 WPM, classification: "fast").
- Test that `PacingView` returns 400 when the segment has no `audio_file`.
- Test that `PacingView` returns 404 when the audio file field is set but the file does not exist on disk.
- Test that the `SegmentSerializer` includes the `pacing_wpm` field and treats it as read-only.
- Test that `pacing_wpm` is a nullable field on the `Segment` model and accepts `None` without a database error.

### 5.2 Integration / Manual Tests

- Generate TTS for a segment with a known script of counted words, then check the API response from the pacing endpoint and confirm the WPM matches the manual calculation.
- Open the Django admin and navigate to a segment record after TTS generation — confirm that `pacing_wpm` has been populated with a non-null float value.
- Request the segment detail endpoint and confirm `pacing_wpm` appears in the JSON response.
- Generate audio for a long, dense segment and a short, sparse one, and confirm the classifications differ as expected.
- Edit a segment's text after generation and re-request the pacing endpoint to confirm it recalculates from the current text and current audio (i.e., the endpoint is live and not purely cached).
- Simulate a failed `get_audio_duration` call inside the Celery task (e.g., by temporarily corrupting a media path in a test environment) and confirm that the task still marks itself as successful and that `pacing_wpm` remains `None` rather than crashing.

### 5.3 Regression Tests

- Confirm that the existing `generate_segment_tts_task` still produces a correctly shaped task result with its original fields intact after the new `pacing` key is added.
- Confirm that the `SegmentSerializer` still serialises all previously present fields correctly after adding `pacing_wpm`.
- Run all existing segment-related API tests (list, retrieve, create, update, delete) and confirm none are broken by the model migration or serializer change.
- Confirm that segments created before the migration (with `pacing_wpm = None`) are still returned correctly by the serializer without error.
- Run the full migration history in reverse (migrate back to the prior state) and then forward again to confirm the `add_pacing_wpm_to_segment` migration is reversible without data loss.

---

## 6. Notes for AI Agent

- The `calculate_pacing` function should use a plain whitespace split for word counting because TTS models in StoryFlow also operate on raw text — consistency between how the text is processed for synthesis and how it is counted for pacing analysis prevents confusing discrepancies where the WPM metric does not match the audible pace.
- When updating the Celery task, use `save(update_fields=...)` rather than a full `save()` to avoid accidentally overwriting other field changes that may have occurred between when the task fetched the segment and when it saves the result.
- The `cached_wpm` field in the pacing endpoint response creates a useful diagnostic signal: if `cached_wpm` differs substantially from the live `wpm` calculation on the endpoint, it suggests the segment text was edited after the last TTS generation. The frontend can use this to prompt the user to regenerate audio.
- The pacing classification names in `calculate_pacing` should match exactly what is specified in the `IDEAS_02_Audio_TTS_Music.md` reference document. Future features may introduce a mapping from classification name to display label, but the internal string keys should remain stable once defined.
- The `pacing_wpm` field should be a `FloatField` rather than an `IntegerField` because raw WPM calculated from short segments with short audio durations can differ meaningfully at the sub-integer level. Rounding to an integer too early discards information.
- Do not store the full pacing dictionary (e.g., as a `JSONField`) on the `Segment` model. Storing only `pacing_wpm` keeps the schema minimal. The `classification`, `word_count`, and `duration` components can always be recomputed on the fly from `pacing_wpm` and the stored `text_content` and `duration` fields that already exist on the model.
- The pacing endpoint should not trigger TTS regeneration — it is a read-only analysis endpoint. Any write side effects belong exclusively in the task pipeline. Keeping analysis and generation concerns separate makes the system easier to reason about and test.
- The WPM thresholds defined in this document (130, 150, 170, 200) should be extracted into module-level constants in `audio_utils.py` rather than being embedded as magic numbers in the condition chain. Named constants make the thresholds easy to discover and adjust without hunting through conditional logic.
- If the segment's `text_content` is empty or None when the pacing endpoint is called, the function should return a response with `word_count = 0` and `wpm = 0` with `classification = "unknown"` rather than raising a 400 error — an empty text is a valid state for a segment that hasn't been written yet, and the client should handle it gracefully.
- When computing `word_count`, strip Markdown or HTML markup from the text before splitting if the `text_content` field is known to occasionally contain lightweight formatting. Counting HTML tags as words would inflate the WPM metric. A simple regex strip of angle-bracket tags is sufficient — do not introduce an HTML parsing library for this.
- The `PacingView` should support an optional query parameter `?live=true` that, when present, recalculates pacing from the actual audio file on disk and returns it without reading the cached `pacing_wpm` from the database. When `?live=false` or the parameter is absent, the endpoint may return the cached value directly if it is non-null, saving the cost of a disk read for `get_audio_duration`. Implement cache-first as the default behaviour.
- The `classify_wpm` helper function should be exported from `audio_utils.py` as a public function rather than being a private implementation detail. Downstream tests and future features (such as a project-level pacing summary) will need to call it independently of `calculate_pacing`.
- When generating the new migration for `pacing_wpm`, check whether any existing data fixtures or test fixtures in the `tests/` directory include `Segment` model entries. If they do, confirm that the `null=True` default means those fixtures remain valid after migration without requiring updates.
- The Celery task should log the computed WPM and classification at the DEBUG level after storing the result. This allows server operators to trace pacing behaviour from logs without needing to query the database.
- If the project later adds a concept of a target content type per project (educational, entertainment, vlog), the `PacingView` response could include a `target_range` field showing the recommended WPM range for that content type. Reserve a field name in the response now by documenting it as `null` so its addition later is non-breaking.
- The `calculate_pacing` function is deliberately free of any I/O — it only performs in-memory string and arithmetic operations. Keep it this way. Functions that mix computation with I/O are harder to unit test and harder to reuse across contexts.
- For the migration step, generate the migration in a local development environment first and review the generated SQL using `sqlmigrate` before committing. The column addition is a simple nullable float, but confirming the SQL output guards against unexpected behaviour with certain database backends.

---

## 7. Future Enhancements

The following ideas are explicitly out of scope for this document's implementation scope but are recorded here to inform future feature planning.

- **Project-level pacing summary:** A `GET /api/projects/{id}/pacing-summary/` endpoint that aggregates `pacing_wpm` values from all segments in a project and returns the mean, min, max, and a per-segment breakdown. Useful for identifying outlier segments within a long-form project.
- **Pacing target setting per project:** Allow the creator to set a target content type (educational, vlog, narrative, fast-cut) on the `Project` model. The pacing endpoint then returns a `deviation` field showing how far the current WPM is from the centre of the target range, and a `recommendation` string like "Consider slowing the script by 15 words" or "Add more detail to this segment."
- **Pre-generation pacing estimate:** Add a lightweight endpoint that accepts raw text and a TTS speed setting and estimates the likely audio duration using an average character-per-second rate, then returns a predicted WPM. This would allow the frontend to display a rough pacing estimate before audio is generated, helping creators refine scripts without triggering full TTS inference.
- **Pacing history per segment:** Add a `SegmentPacingLog` model that records WPM and classification each time TTS is regenerated. This would let creators see how pacing changed across edit iterations, building a revision history.
- **Bulk pacing report export:** A management command or admin action that computes pacing for all segments across all projects and exports a CSV file. Useful for content managers auditing a large library of generated videos.
