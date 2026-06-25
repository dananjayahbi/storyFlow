# Feature 1.8 — TTS Audio Preview in Editor

| Field | Value |
|---|---|
| **Feature ID** | 1.8 |
| **Title** | TTS Audio Preview in Editor |
| **Status** | 🟡 Planned |
| **Priority** | High |
| **Complexity** | Low |
| **Estimated Effort** | 2 days |
| **Dependencies** | Feature 1.0 (Kokoro TTS baseline), `tts_wrapper.py` `generate_audio()` function |
| **Output Files (NEW)** | `media/projects/{id}/audio/{seg_id}_preview.wav` |
| **Files Modified** | `backend/core_engine/tts_wrapper.py`, `backend/api/views.py`, `backend/api/urls.py` |

---

## 1. Document Overview

### 1.1 Problem Statement

Currently, to hear how a segment sounds with a given voice and speed setting, the user must trigger a full TTS generation for the entire segment. This process takes several seconds per segment and requires waiting for the full audio pipeline to complete. When a user is iterating on word choices — trying different phrasings, testing which voice fits the tone, or adjusting speed — this latency makes the editing loop frustratingly slow.

The problem is most acute during two workflows:

1. **Voice Selection** — A user unsure between `af_bella` and `af_nicole` must generate full audio twice to compare, waiting many seconds between each comparison.
2. **Text Wording** — A user refining the opening sentence of a segment must regenerate the full segment audio after every small text edit just to hear the first few words.

Because preview feedback is so slow, users tend to commit to wording and voice choices without adequate testing, leading to costly full re-renders later.

### 1.2 Proposed Solution

Add a lightweight, ephemeral TTS preview mechanism that generates audio for only the first sentence of a segment's text content. This gives the user meaningful audio feedback within 1–2 seconds, without touching the main TTS generation pipeline or storing anything in the database.

The solution has three parts:

1. A new helper function `generate_preview_audio()` in `tts_wrapper.py` that extracts the first sentence from a given text string (splitting on `.`, `!`, or `?`, capped at 200 characters) and calls the existing `generate_audio()` function with that snippet.
2. A new REST API endpoint `POST /api/projects/{id}/segments/{seg_id}/preview-tts/` in `views.py` that invokes the helper and returns the preview audio URL.
3. A new URL registration in `urls.py` pointing to the new view.

The preview audio file is written to `media/projects/{id}/audio/{seg_id}_preview.wav` and is overwritten on every new request — it is intentionally ephemeral and never stored in the database. No model changes are required.

On the frontend side, a "Preview Voice" play button is added to the segment editor panel, which calls the endpoint and plays the returned URL in the browser.

### 1.3 Scope

| In Scope | Out of Scope |
|---|---|
| First-sentence extraction from `text_content` | Full-segment audio preview |
| New `generate_preview_audio()` helper in `tts_wrapper.py` | Streaming audio (response is a file URL, not a stream) |
| New `preview-tts` API endpoint | Background queue / Celery task for preview (runs synchronously) |
| Ephemeral preview WAV file on disk | Storing preview audio path in the database |
| Returning preview audio URL in API response | Any change to the main `generate_segment_tts_task` Celery flow |
| Frontend "Preview Voice" play button | Multi-sentence preview or configurable preview length |
| Overwriting preview file on each request | Preview audio cleanup / garbage collection logic |
| Voice and speed parameters respected in preview | Subtitle or video generation during preview |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| `backend/core_engine/tts_wrapper.py` | Contains `generate_audio()`, `VALID_VOICE_IDS`, `SPEED_MIN/MAX`, `construct_audio_path()` | Stable — generates full segment audio only |
| `backend/api/views.py` | REST API views for projects and segments | Has segment CRUD and TTS generation endpoints; no preview endpoint |
| `backend/api/urls.py` | URL routing for all API endpoints | No preview-tts URL registered |
| `backend/api/models.py` | `Project` and `Segment` models | `Segment` has `text_content`, `audio_file`, `sequence_index` — no preview field needed |
| `backend/api/serializers.py` | DRF serializers | No changes needed for this feature |
| `backend/core_engine/audio_utils.py` | Audio utilities including `validate_audio_file()` | Usable as-is for validating preview output |

---

## 2. Flow Diagram

```
User clicks "Preview Voice" in segment editor
        |
        v
Frontend sends POST /api/projects/{id}/segments/{seg_id}/preview-tts/
  with body: { voice_id, speed }
        |
        v
views.py: preview_tts_view()
  - Fetch Segment by seg_id, verify it belongs to project id
  - Read segment.text_content
        |
        v
tts_wrapper.py: generate_preview_audio(text, voice_id, speed, project_id, segment_id)
  - Extract first sentence from text
      (split on . ! ? — take first token, strip whitespace, cap at 200 chars)
  - Validate voice_id against VALID_VOICE_IDS (fallback to DEFAULT_VOICE_ID)
  - Validate speed within SPEED_MIN / SPEED_MAX (clamp if out of range)
  - Build output path: media/projects/{id}/audio/{seg_id}_preview.wav
  - Call generate_audio(snippet, voice_id, speed, preview_path)
        |
        v
Preview WAV written to disk (overwrites previous preview if exists)
        |
        v
views.py: return JSON { "preview_url": "/media/projects/{id}/audio/{seg_id}_preview.wav" }
        |
        v
Frontend: receives URL, plays audio in browser via <audio> element
```

---

## 3. Step-by-Step Instructions

### Step 3.1 — Add `generate_preview_audio()` to `tts_wrapper.py`

Open `backend/core_engine/tts_wrapper.py`.

Find the section where `generate_audio()` is defined and `construct_audio_path()` lives. Below those functions, add a new helper called `generate_preview_audio`.

This function should accept: the full text string, a voice ID, a speed value, the project ID, and the segment ID.

Inside the function:
- Split the text on the characters `.`, `!`, and `?` using a regex split that preserves the delimiter.  Reconstruct the first sentence by taking everything up to and including the first delimiter. If the text has no such delimiter, use the whole text.
- Strip leading and trailing whitespace from the extracted snippet.
- Cap the snippet at 200 characters by slicing if needed. If slicing cuts mid-word, that is acceptable — the goal is speed, not perfect grammar.
- If the snippet is empty after processing, fall back to the first 200 characters of the original text.
- Validate `voice_id` against `VALID_VOICE_IDS`. If not valid, silently substitute `DEFAULT_VOICE_ID`.
- Clamp `speed` to the range `[SPEED_MIN, SPEED_MAX]`.
- Construct the output path as `media/projects/{project_id}/audio/{segment_id}_preview.wav`. This can reuse the same directory logic as `construct_audio_path()`, but always append `_preview` to the filename before the extension.
- Ensure the directory exists (create it if not).
- Call `generate_audio(snippet, voice_id, speed, output_path)` and return the output path.

No changes to the existing `generate_audio()` function are needed.

### Step 3.2 — Add the preview view to `views.py`

Open `backend/api/views.py`.

Locate where the existing segment-related views are defined (near `generate_segment_tts` or similar). After those, add a new view function (or class-based view, whichever pattern the file uses) called `preview_segment_tts`.

This view should:
- Accept POST requests only.
- Extract `project_id` and `segment_id` from the URL path parameters.
- Retrieve the `Segment` object from the database using `segment_id`. Return a 404 response if not found.
- Verify the segment's parent project matches `project_id`. Return a 400 response if mismatched.
- Read `voice_id` from the request body (JSON). If absent, use the project's own `voice_id` field as the default.
- Read `speed` from the request body (JSON). If absent, use the project's own `tts_speed` field as the default.
- Call `generate_preview_audio()` from `tts_wrapper` with the segment's `text_content`, the resolved `voice_id`, the resolved `speed`, the `project_id`, and the `segment_id`.
- On success, return a JSON response with a `preview_url` key containing the media-relative URL to the generated preview WAV file.
- On any exception from TTS generation, return a 500 response with an `error` key describing the failure.

The view runs synchronously — no Celery task. Preview generation is fast enough (first sentence only) that async queueing adds unnecessary complexity.

### Step 3.3 — Register the URL in `urls.py`

Open `backend/api/urls.py`.

Find the section where segment-related URL patterns are defined. Add a new URL pattern mapping the path `projects/<int:project_id>/segments/<int:segment_id>/preview-tts/` to the `preview_segment_tts` view, for POST requests.

Follow the existing naming convention for URL `name=` parameters (e.g., `segment-preview-tts`).

### Step 3.4 — Add the "Preview Voice" button to the frontend segment editor

Open the frontend segment editor component (likely under `frontend/components/` in a file related to segments or the editor panel).

In the segment editor UI, locate the area near the voice selector and speed slider. Add a button labeled "Preview Voice".

When clicked, the button should:
- Read the currently selected `voice_id` and `speed` from local component state.
- Send a POST fetch request to `/api/projects/{projectId}/segments/{segmentId}/preview-tts/` with those values in the JSON body.
- On a successful response, extract `preview_url` and play it using a browser `<audio>` element (either hidden DOM element with `.play()` call, or an HTML5 audio player shown inline).
- Show a loading indicator on the button while the request is in-flight.
- Show a brief error message if the request fails.

No Redux store changes are needed for this feature. Local component state (loading flag, error message, preview URL) is sufficient.

---

## 4. Expected Outcome

1. The endpoint `POST /api/projects/{id}/segments/{seg_id}/preview-tts/` is registered and returns a 200 response with `{ "preview_url": "..." }` when given a valid project and segment.
2. The preview audio file is created at `media/projects/{id}/audio/{seg_id}_preview.wav` on disk after each call.
3. Calling the endpoint twice in a row overwrites the previous preview file — no accumulation of preview files.
4. The preview audio contains only the first sentence (or up to 200 chars) of the segment's `text_content`.
5. If an invalid `voice_id` is passed, the preview falls back to `af_bella` and still succeeds.
6. If speed values outside `[0.5, 2.0]` are passed, they are clamped and audio is still generated successfully.
7. A segment with no sentence-ending punctuation generates preview audio from the first 200 characters of text.
8. The main segment TTS generation flow (`generate_segment_tts_task`) is completely unaffected.
9. The frontend "Preview Voice" button triggers audible playback within 1–2 seconds on a typical development machine.
10. The `Segment.audio_file` database field is never modified by a preview request.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] `generate_preview_audio()` extracts the first sentence correctly when text contains a period
- [ ] `generate_preview_audio()` extracts the first sentence correctly when text contains a `!`
- [ ] `generate_preview_audio()` extracts the first sentence correctly when text contains a `?`
- [ ] `generate_preview_audio()` uses the full text (capped at 200 chars) when no sentence-ending punctuation is present
- [ ] `generate_preview_audio()` caps output at 200 characters even for very long first sentences
- [ ] `generate_preview_audio()` falls back to `DEFAULT_VOICE_ID` when an unknown voice ID is provided
- [ ] `generate_preview_audio()` clamps speed to `SPEED_MIN` when speed is below 0.5
- [ ] `generate_preview_audio()` clamps speed to `SPEED_MAX` when speed is above 2.0
- [ ] `generate_preview_audio()` returns the correct output path with `_preview` in the filename
- [ ] `generate_preview_audio()` creates the output directory if it does not already exist

### 5.2 Integration / Manual Tests

- [ ] POST to the endpoint with a valid project and segment returns HTTP 200 and a `preview_url`
- [ ] The returned `preview_url` resolves to a playable WAV file when accessed via the browser
- [ ] POST with a missing `voice_id` falls back to the project's `voice_id` field
- [ ] POST with a missing `speed` falls back to the project's `tts_speed` field
- [ ] POST with an invalid `segment_id` returns HTTP 404
- [ ] POST with a `segment_id` that belongs to a different project returns HTTP 400
- [ ] Calling the endpoint twice generates a new preview file and overwrites the old one
- [ ] The frontend "Preview Voice" button shows a loading spinner during the request
- [ ] The frontend plays the preview audio automatically once the response arrives
- [ ] The frontend shows an error message when the endpoint returns a 500

### 5.3 Regression Tests

- [ ] Existing `generate_audio()` function behavior is unchanged
- [ ] Existing `generate_segment_tts_task` Celery task still produces correct full-length audio
- [ ] `Segment.audio_file` field is not modified after a preview request
- [ ] `Project` model fields are read-only in this flow — no model saves occur
- [ ] Existing segment CRUD endpoints continue to work as before
- [ ] URL routing for existing endpoints is unaffected by the new URL pattern

---

## 6. Notes for AI Agent

**Implementation order:** Do `tts_wrapper.py` first, then `views.py`, then `urls.py`, then the frontend. This order allows early testing of the backend logic in isolation.

**Sentence extraction edge cases:**
- Text starting with a number followed by a period (e.g., "1. First item") should not be treated as a sentence ending at the period after the digit — consider trimming leading list markers before extraction, or simply accepting this as an acceptable edge case for a preview feature.
- Very short texts (under 10 characters) should pass through as-is without truncation.
- Text that is already under 200 characters and has no punctuation should use the full text.

**Do not create a Celery task for this.** The synchronous approach is correct. Preview audio is a fast, incidental operation. Introducing a Celery task would add polling complexity to the frontend for no benefit.

**File path collision:** The preview file uses `{seg_id}_preview.wav` as its name, intentionally different from the main audio file `{seg_id}.wav` (or whatever `construct_audio_path` returns). Verify the naming convention in `tts_wrapper.py` before picking the preview filename to avoid any accidental collision.

**Media serving:** Ensure the Django settings have `MEDIA_URL` and `MEDIA_ROOT` configured correctly to serve the preview WAV at the returned URL. This should already be set up if other audio files are being served successfully.

**No database migration is required.** This feature adds no new model fields.

**Frontend audio playback:** Use the simplest possible approach — a hidden `<audio>` DOM element whose `src` is set to the preview URL, then `.play()` is called. Avoid complex media player libraries for this small feature.

**Concurrent preview requests:** If two users request a preview for the same segment simultaneously, they will both write to the same preview file path and one may overwrite the other's result. This is acceptable for a preview feature. No locking is needed.
