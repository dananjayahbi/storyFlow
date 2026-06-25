# Feature 6.1 — Forced Alignment (Word-Level Timing)

| Field | Value |
|---|---|
| **Feature ID** | 6.1 |
| **Title** | Forced Alignment — Word-Level Subtitle Timing via Whisper |
| **Status** | 🟡 Planned |
| **Priority** | High |
| **Complexity** | Medium |
| **Estimated Effort** | 5–8 days |
| **Dependencies** | Kokoro TTS pipeline must be fully operational; generated WAV files must be written to disk before alignment runs; Whisper base model (~280 MB) downloaded on first use |
| **Output Files (NEW)** | `backend/core_engine/forced_aligner.py` |
| **Files Modified** | `backend/core_engine/video_renderer.py`, `backend/api/models.py`, `backend/api/serializers.py`, `requirements.txt` |

---

## 1. Document Overview

### 1.1 Problem Statement

StoryFlow computes subtitle display timing through a proportional character-count formula inside `calculate_subtitle_timing()` in `subtitle_engine.py`. The function receives the list of display chunks from `chunk_text()` and the total audio duration for a segment. It divides the total duration by the total character count across all chunks, assigns each chunk a time window proportional to its character length, and returns a list of timing dicts with "text", "start", and "end" keys. This approach requires no additional model inference and is computationally instant.

The fundamental problem is that human speech — and Kokoro TTS in particular — does not proceed at a uniform character-per-second rate. Real speech is highly non-uniform in pace for several compounding reasons:

Technical vocabulary, medical terms, proper nouns, and long compound words require significantly more spoken time than a raw character count predicts. Kokoro spends proportionally more time on each syllable of a complex word to produce natural-sounding prosody. A word like "pathophysiology" takes more than twice as long to speak as its character count relative to "cat" would imply.

Short function words — "a", "the", "is", "in", "of", "to" — are spoken faster than their character share predicts. The TTS engine frequently reduces or blends them into adjacent words, and their real duration in the audio is a fraction of their character-count proportion.

Punctuation creates silence. A sentence-ending period causes a 200–400 millisecond pause. An inline comma causes 100–200 milliseconds of pause. An em-dash creates an even longer dramatic pause. Character-count proportioning is entirely blind to these silence gaps — a segment whose second half contains several commas will have proportional timings that are systematically early for every chunk in the second half.

Sentence-final words carry intonational lengthening — the last word of a declarative sentence is often held slightly longer than mid-sentence words for natural cadence. Character count does not capture this either.

The compounding effect of these deviations causes noticeable subtitle drift within a single segment. On a segment with mixed vocabulary density — a sentence that begins with short words and ends with a technical phrase — the subtitle for the opening chunk may appear and disappear while Kokoro is still speaking it, and the subtitle for the technical phrase may appear a full second before Kokoro reaches it.

This timing drift is especially damaging for social media use cases. Platforms like TikTok, YouTube Shorts, and Instagram Reels have built viewer expectations around perfectly synchronized captions. A video with noticeably late or early subtitles signals low production quality and measurably reduces watch-through rate. The problem cannot be patched post-render with a global offset because the drift is content-dependent and nonlinear even within a single segment.

The current proportional approach is not a bug — it is a deliberate simplification that trades accuracy for speed. Feature 6.1 replaces it with real acoustic measurement while preserving the proportional path as a fallback and default, ensuring existing users experience no change unless they explicitly opt in.

### 1.2 Proposed Solution

The core idea is forced alignment: given the known transcript and the generated WAV, use a speech recognition model to determine the precise time at which each word begins and ends in the audio. Because the transcript is already known — it was the exact text input to TTS — the model's job is alignment rather than open-ended transcription. This is significantly faster and more accurate than full transcription and yields word-level timestamp data.

StoryFlow will use the `whisper-timestamped` Python package to perform this alignment. The package wraps OpenAI Whisper and extends it to produce word-level timestamps alongside the recognized text. Whisper's base model is small enough — approximately 280 MB — to be deployed on standard hardware and fast enough that a 15-second audio clip is aligned in 5–10 seconds on CPU.

The solution is organized into three layers. The first layer is a new isolated module, `forced_aligner.py`, placed inside `backend/core_engine/` alongside the other audio and rendering utilities. This module has no Django or REST framework dependencies. It contains exactly two public functions: `align_text_to_audio()`, which runs Whisper on a WAV file and returns per-word timestamps as a flat list of dicts, and `group_words_to_chunks()`, which maps those per-word timestamps back to the display chunks produced by `chunk_text()`, generating a chunk-level timing list in the same dict format the rest of the pipeline already expects.

The second layer is a per-project opt-in toggle: a new `forced_alignment_enabled` BooleanField on the Project model, defaulting to False. When False, the pipeline is completely unchanged. When True, the alignment pass runs automatically after TTS generation for each segment during a render job.

The third layer is a robust fallback mechanism within `video_renderer.py`. If alignment fails for any reason — model not yet downloaded, WAV file too short, package version mismatch, Whisper hallucination producing no words, or any unhandled exception — the system logs a WARNING with the project ID, segment ID, and failure reason, then reverts to proportional timing for that segment only. The render continues rather than crashing. This guarantee means that enabling forced alignment can never turn a previously successful render into a failed one.

### 1.3 Scope

| Category | Items |
|---|---|
| **In Scope** | New `forced_aligner.py` module with `align_text_to_audio()` and `group_words_to_chunks()` functions; module-level Whisper model caching with lazy load; `forced_alignment_enabled` BooleanField on Project model with Django migration; field exposed in ProjectSerializer; integration point in `video_renderer.py` with explicit fallback and warning logging; `whisper-timestamped` added to `requirements.txt`; documentation of Whisper model download requirement |
| **Out of Scope** | Real-time or preview-mode alignment; alignment for user-uploaded custom audio files (only Kokoro-generated WAV); frontend UI toggle for the field (serializer exposure is sufficient for phase 6.1); manual correction or editing of alignment output; multi-language Whisper model selection; per-segment override of alignment behavior; any change to `subtitle_engine.py` existing functions |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| `backend/core_engine/subtitle_engine.py` | Splits narration into display chunks; provides proportional timing; alignment replaces timing output but does not change or remove this file | Functional — `chunk_text()` and `calculate_subtitle_timing()` present and tested |
| `backend/core_engine/fast_compositor.py` | Pre-renders RGBA subtitle image overlays; consumes timing dicts from either subtitle_engine or forced_aligner | Functional — `pre_render_subtitles()` accepts timing list |
| `backend/core_engine/tts_wrapper.py` | Generates WAV from text using Kokoro ONNX; must write WAV to disk at a known path before alignment runs | Functional — `generate_audio()` writes WAV at 24 kHz mono |
| `backend/core_engine/video_renderer.py` | Orchestrates full render pipeline; alignment step inserted between TTS generation and subtitle pre-render | Functional — subtitle settings dict wired through to compositor |
| `backend/api/models.py` | Project and Segment database models | Functional — no forced alignment field yet |
| `backend/api/serializers.py` | REST serialization for Project model | Functional — new field must be added to ProjectSerializer |
| `requirements.txt` | Python dependency manifest located at `backend/requirements.txt` | Missing `whisper-timestamped` |
| `backend/core_engine/forced_aligner.py` | NEW — all alignment logic lives here | Does not exist yet |

---

## 2. Flow Diagram

```
Segment.text_content retrieved
          |
          v
[ subtitle_engine.chunk_text(text) ]
          |
          v
chunks list (display strings)
          |
          v
[ tts_wrapper.generate_audio(text, voice_id, speed, wav_path) ]
          |
          v
WAV file written to disk (24 kHz, mono)
          |
          |
          +------ forced_alignment_enabled == False? ─────────────────────────┐
          |                                                                    |
          |                                                          [ calculate_subtitle_timing() ]
          |                                                                    |
          |                                                          proportional timings
          |                                                                    |
          +------ forced_alignment_enabled == True?                           |
                    |                                                          |
                    v                                                          |
          [ forced_aligner.align_text_to_audio(text, wav_path) ]              |
                    |                                                          |
                    |--- Returns None? ───────────────────────────────────────┤
                    |    (short audio / model missing / exception)            |
                    |    log WARNING: project_id, segment_id, reason          |
                    |    call calculate_subtitle_timing() as fallback         |
                    |                                                          |
                    |--- Returns word list? ─────────────────────┐            |
                                                                 |            |
                                              per-word {word, start, end}     |
                                              flat list                       |
                                                                 |            |
                                   [ forced_aligner.group_words_to_chunks()   |
                                     (word_timings, chunks) ]                 |
                                                                 |            |
                                              chunk timings with real         |
                                              start/end values                |
                                                                 |            |
                                                                 v            v
                                             [ fast_compositor.pre_render_subtitles(
                                               chunks, timings, resolution, ...) ]
                                                                 |
                                                                 v
                                              RGBA subtitle frame overlays
                                                                 |
                                                                 v
                                                       Final rendered video
```

---

## 3. Step-by-Step Instructions

### Step 3.1 — Add whisper-timestamped to requirements.txt

Open `requirements.txt` at `backend/requirements.txt`. Add `whisper-timestamped` as a new line. If `openai-whisper` is not already present, it will be pulled as a transitive dependency. If `stable-whisper` is preferred — it has a slightly different API but identical word-level timing capability — that may be used instead. The choice must be made once and remain consistent throughout the module. Do not list both.

After editing, install the package in the active environment and verify it imports without errors. The package will not download the Whisper model during import — model download occurs on the first call to the transcription function.

Note on model download: The first call to `align_text_to_audio()` triggers a one-time download of the Whisper base model, approximately 280 MB, cached to the Whisper default directory. On Linux and macOS this is `~/.cache/whisper`. On Windows this is `%USERPROFILE%\.cache\whisper`. On a production server with restricted internet access, the model must be pre-downloaded and placed in this directory before the first render job is submitted. This step must be included in the deployment runbook.

Pin the package version in `requirements.txt`. Whisper-related package APIs have changed across minor versions. A pinned version prevents environment rebuilds from introducing breaking changes silently.

### Step 3.2 — Create forced_aligner.py and define the module structure

Create `backend/core_engine/forced_aligner.py`. This file must have zero Django imports and zero REST framework imports. Its dependencies are: standard library modules only (`os`, `logging`, `wave`, `pathlib`), `numpy` (already present in the project), and the whisper-timestamped package.

At the top of the file, after all imports, declare two module-level names. The first is `_whisper_model`, initialized to `None`. This variable holds the loaded Whisper model instance between calls. The second is `WHISPER_MODEL_SIZE`, a string constant set to `"base"`. This constant is the single place in the codebase that controls which Whisper model size is used for alignment. Any future operator who wants to test "small" or "medium" for improved accuracy changes only this constant.

Write a private helper function named `_load_model()` immediately after those declarations. Its logic: check whether `_whisper_model` is None; if it is, load the model using the whisper-timestamped model-loading call with `WHISPER_MODEL_SIZE`, assign the result to `_whisper_model`, and write an INFO-level log entry stating the model size and confirming load. If `_whisper_model` is already set, return immediately without re-loading. This lazy-loading pattern ensures zero overhead on projects where `forced_alignment_enabled` is False.

Add a comment block at the module level explaining the threading caveat: if multi-threaded rendering is introduced in a future phase, the model-loading section inside `_load_model()` will need a threading lock to prevent two threads from simultaneously loading the model into the shared module-level variable. This is not needed now but must be addressed if concurrency is added.

### Step 3.3 — Implement align_text_to_audio()

Write the function `align_text_to_audio(text, audio_path)` in `forced_aligner.py`. It accepts the segment's full narration text as a plain string and the absolute path to the WAV file as a string or path-like object. It returns either a flat list of dicts or None.

Input validation block — these checks run before any model inference:

Check that `text` is a non-empty string. If it is empty or None, log a WARNING and return None.

Check that the path at `audio_path` refers to an existing file. Use `pathlib.Path(audio_path).exists()`. If the file is absent, log a WARNING that includes the path and return None.

Normalize the path to forward slashes using `pathlib.Path(audio_path).as_posix()`. This resolves Windows backslash handling inconsistencies in some Whisper builds.

Open the WAV file with the standard library `wave` module, read `nframes` and `framerate`, compute the duration in seconds as `nframes / framerate`. If the duration is less than 1.5 seconds, log a WARNING stating the segment duration and the threshold, and return None. Whisper performs unreliably on very short audio clips and may return empty word lists or hallucinations on sub-1.5-second inputs.

Model inference block — wrapped in try-except:

Call `_load_model()` to obtain the Whisper model instance.

Call the whisper-timestamped transcription function on the loaded model and the normalized audio path. Pass the known `text` as an `initial_prompt` argument — this is a standard Whisper parameter that significantly improves alignment accuracy by seeding the model with the expected transcript. Request word-level timestamps (the specific API parameter name varies by package version — check the installed version's documentation).

The result is a dict with a "segments" list. Each segment contains a "words" list. Each word entry has "text", "start", and "end" keys.

Flatten all word entries from all segments into a single list. For each word entry, normalize the "text" value: strip whitespace, remove the characters period, comma, exclamation mark, question mark, colon, semicolon, em-dash (—), and hyphen (-), then convert to lowercase. Store normalized text under the key "word" (not "text") to distinguish it from raw Whisper output.

Return the flat normalized list of dicts.

In the except block: log an ERROR message that includes `audio_path` and the str representation of the caught exception. Return None.

### Step 3.4 — Implement group_words_to_chunks()

Write the function `group_words_to_chunks(word_timings, chunk_texts)` in `forced_aligner.py`. It accepts the list of word dicts from `align_text_to_audio()` and the list of chunk display strings from `chunk_text()`. It returns a list of chunk timing dicts in the exact format of `calculate_subtitle_timing()` output: each dict has "text", "start", and "end" keys.

Implementation approach — sequential pointer matching with fuzzy fallback:

Build a flat expected-word sequence by iterating over `chunk_texts` in order. For each chunk, split on whitespace to get the individual words. Apply the same normalization used in `align_text_to_audio()` — strip punctuation, lowercase. Store each normalized word alongside its originating chunk index. This produces a flat ordered list such as: [(chunk_index=0, word="the"), (chunk_index=0, word="quick"), (chunk_index=1, word="brown"), ...].

Walk the Whisper word list and the expected-word sequence with two independent integer pointers, one for each list. At each step, compare the Whisper word at the Whisper pointer with the expected word at the expected pointer (both already normalized and lowercased). If they match, record the association: this Whisper word's start and end times belong to the chunk identified by the expected word's chunk index. Advance both pointers.

If they do not match, attempt one recovery step: advance the Whisper pointer by one and test again. If the next Whisper word matches, record the association and advance both pointers from their new positions. If that also fails, advance the expected pointer by one and retry. This two-step fuzzy skip handles contractions split differently between the original text and Whisper output (do not vs don't, they are vs they're) and occasional one-word Whisper hallucinations.

After the traversal is complete, consolidate the accumulated Whisper timestamps per chunk. Each chunk's real start is the minimum "start" across all matched words for that chunk. Each chunk's real end is the maximum "end" across all matched words.

For any chunk that received zero matched words during traversal, compute a proportional fallback: divide the remaining audio duration (segment total duration minus the previous chunk's end time) proportionally by the character count of the remaining unmatched chunks. Log a DEBUG-level message for each chunk that falls back to proportional values, including the chunk text and the chunk index.

Return the final list of dicts with "text", "start", and "end" for every chunk, in the same order as the input `chunk_texts`.

### Step 3.5 — Add forced_alignment_enabled to the Project model and migrate

Open `backend/api/models.py`. Find the Project model class. Add the field `forced_alignment_enabled` as a `BooleanField` with `default=False`. Include a `help_text` argument: "When True, Whisper forced alignment runs after TTS generation for each segment, producing real word timestamps instead of proportional estimates. Adds approximately 3–8 seconds per segment during rendering. Falls back to proportional timing if alignment fails."

Save the file. From the `backend/` directory, run `python manage.py makemigrations api`. Inspect the generated migration file in `backend/api/migrations/` to confirm it references exactly the `forced_alignment_enabled` field on the Project model and nothing else. Run `python manage.py migrate` and confirm it applies without errors.

### Step 3.6 — Expose forced_alignment_enabled in the serializer

Open `backend/api/serializers.py`. Find the ProjectSerializer and its Meta inner class. Add `forced_alignment_enabled` to the fields list. No custom validation is needed — DRF's default BooleanField correctly serializes True/False JSON booleans. Verify by sending a PATCH request to the Project REST endpoint with the field and reading it back.

### Step 3.7 — Wire forced alignment into video_renderer.py

Open `backend/core_engine/video_renderer.py`. Add an import for `forced_aligner` at the top of the file, using the same relative import style as the other core_engine imports.

Inside `render_project()`, locate the per-segment processing loop. Find the precise location where `tts_wrapper.generate_audio()` is called and where `calculate_subtitle_timing()` is subsequently called. Between these two calls, insert the alignment conditional block.

If the project's `forced_alignment_enabled` is True: call `forced_aligner.align_text_to_audio()` with the segment's text content and the WAV path that was just passed to `generate_audio()`. If the return value is None, log a WARNING including project ID and segment ID, then call `calculate_subtitle_timing()` as the fallback. If the return value is a non-None word list, call `forced_aligner.group_words_to_chunks()` with the word timings and the chunk list, and use the result as the timing input for `pre_render_subtitles()`.

If `forced_alignment_enabled` is False, skip the entire alignment block and call `calculate_subtitle_timing()` as before.

### Step 3.8 — Validate the fallback path

Before running a full render, explicitly validate the fallback by calling `align_text_to_audio()` with a nonexistent file path from a small test script. Assert that the return value is None and that no exception propagates. Also validate with a valid text file (not a WAV) — again, None with no exception. Then confirm the full render completes successfully (output video file exists, non-zero size) with `forced_alignment_enabled = True` on a real test project.

### Step 3.9 — Document the Whisper model download

Open `docs/ARCHITECTURE.md` or the project-level `README.md`. Add a section titled "Whisper Model for Forced Alignment". Include: model size and name ("base", ~280 MB), cache directory paths for Windows and Linux, instructions for pre-downloading on a restricted-internet server, and a note that the download happens once and persists across restarts. Include a one-line instruction for verifying the model is already cached before a production render job.

---

## 4. Expected Outcome

1. When `forced_alignment_enabled` is True on a project, every segment's subtitle timings are derived from real Kokoro TTS speech timestamps, eliminating the perceptible drift that proportional estimation produces on uneven-paced content.
2. Subtitle chunks appear on screen within approximately one word's worth of timing error — typically under 80 ms deviation from the acoustic boundary — compared to the 0.5–2.0 second drift seen with proportional timing on mixed-vocabulary content.
3. When `forced_alignment_enabled` is False (the default), the render pipeline is 100% identical to the pre-feature state: no performance change, no new log output, no behavioral difference.
4. If Whisper fails on any segment for any reason, that segment's render continues using proportional timing. A WARNING log message identifies the project ID, segment ID, and failure reason.
5. The Whisper model is loaded once per process lifetime and reused for all segments in a render job. Per-segment alignment overhead is 3–8 seconds on CPU, not 20+ seconds.
6. The `forced_alignment_enabled` field is readable and writable via the existing Project REST endpoints without new URL routes or endpoint logic.
7. The Django migration for the new BooleanField applies cleanly with no conflicts against any existing migration in the api app.
8. `requirements.txt` lists `whisper-timestamped` so a clean pip install pulls the dependency automatically on any new deployment.
9. `calculate_subtitle_timing()` and `chunk_text()` in `subtitle_engine.py` are completely unmodified and pass all their existing unit tests without change.
10. `fast_compositor.pre_render_subtitles()` requires no changes — it consumes the timing dict list without needing to know which source produced it.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- Call `align_text_to_audio()` with a real short WAV generated by `tts_wrapper.generate_audio()` from a known five-word sentence. Assert the return value is a non-empty list. Assert each item is a dict with the keys "word", "start", "end". Assert all "start" values are greater than or equal to zero. Assert all "end" values are strictly greater than their corresponding "start" values.
- Call `align_text_to_audio()` with a nonexistent file path string. Assert the return value is None. Assert no exception is raised.
- Call `align_text_to_audio()` with a valid path that points to a real file that is not a WAV (for example a text file). Assert the function returns None without raising an exception.
- Call `align_text_to_audio()` with a WAV file whose duration is under 1.5 seconds. Assert the return value is None.
- Call `align_text_to_audio()` with `text=""`. Assert return value is None.
- Call `group_words_to_chunks()` with a mock word timing list that covers the exact words in a two-chunk input with no missing words. Assert the return value is a list of length two. Assert each item has "text", "start", and "end" keys. Assert the "start" of the first chunk equals the "start" of the first word in the mock timings.
- Call `group_words_to_chunks()` with a word timing list shorter than the words implied by the chunk texts, simulating a partial Whisper output. Assert the function returns a list of the same length as the chunk input with no None items — missing chunks must receive computed fallback values.
- Import `forced_aligner` and immediately assert `forced_aligner._whisper_model is None` — confirming that model loading is deferred and not triggered at import time.
- Call `_load_model()` twice in sequence. Assert that the second return value is the same Python object as the first (identity check confirms caching is working and no double-load occurs).

### 5.2 Integration / Manual Tests

- Render a full project with `forced_alignment_enabled = False`. Play back the resulting video and confirm subtitle timing matches the known proportional behavior.
- Set `forced_alignment_enabled = True` on the same project, re-render it, and play back the video. Confirm that subtitle chunks visibly appear closer to the correct spoken moment — there should be no perceptible early or late offset on a normal-paced sentence.
- Use a test segment whose narration contains a mix of very short words ("I am a...") followed by polysyllabic technical terms. Confirm that aligned timing avoids both: the early-flash problem on the short-word chunks and the late-appear problem on the technical-term chunks.
- Measure per-segment processing time with alignment enabled on a 10-second audio clip. Confirm the Whisper inference overhead for the base model is within the 3–10 second window on the target hardware.
- Simulate an alignment failure mid-render by temporarily making the WAV path unknown to `align_text_to_audio()`. Confirm the render does not crash, the WARNING log is written with project and segment IDs, and the final video is fully rendered using proportional timing.
- Send a PATCH request to the Project REST endpoint with `{"forced_alignment_enabled": true}`. Read the project back and confirm the field value persists as True. Send a second PATCH with `false` and confirm it updates correctly.

### 5.3 Regression Tests

- Run all tests in `backend/tests/test_e2e.py` and `backend/tests/test_settings.py` and confirm zero new failures.
- Render a project that was previously rendered successfully (with `forced_alignment_enabled` defaulting to False). Confirm the output is visually and structurally identical to the pre-feature baseline render.
- Confirm that `subtitle_engine.py` — specifically `chunk_text()` and `calculate_subtitle_timing()` — are unchanged from their pre-feature versions and pass all their existing tests.
- Confirm that `fast_compositor.pre_render_subtitles()` is unchanged and produces correct RGBA output when given either proportional timings or real aligned timings as input.
- Confirm the migration history in `backend/api/migrations/` is linear and that running migrate on a fresh database creates the correct schema including the new `forced_alignment_enabled` column.
- Confirm that all existing Project API endpoint tests pass without modification and that the serializer response now includes `forced_alignment_enabled` where the fields list is fully enumerated.

---

## 6. Notes for AI Agent

**Module-level model caching is the single most important performance requirement.** If the Whisper model is re-loaded inside `align_text_to_audio()` on every invocation, per-segment overhead balloons to 20–30 seconds rather than 3–8. The model instance must be stored in `_whisper_model` at module scope and `_load_model()` must return it immediately on subsequent calls. Verify this behavior in unit tests before integrating with the render pipeline.

**Return format consistency is non-negotiable.** The output of `group_words_to_chunks()` must match the dict format of `calculate_subtitle_timing()` exactly: keys "text", "start", "end", with string and two floats respectively. The compositor and renderer consume this list without caring which function produced it. One mismatched key name causes a KeyError inside `pre_render_subtitles()` during every karaoke or chunk render.

**Step order is strict.** Write and unit-test `forced_aligner.py` completely before editing `video_renderer.py`. The video renderer is a stateful orchestrator and is significantly harder to test in a partially wired state.

**Run makemigrations before testing the serializer.** The database column must exist before DRF can serialize or deserialize the field. Attempting to test the REST endpoint without applying the migration will produce a database error.

**Do not modify subtitle_engine.py.** The proportional timing functions are the fallback path and must remain unchanged. Feature 6.1 adds a new code path alongside the existing one — it does not replace the existing one.

**Whisper "base" model is the correct default.** Larger models (small, medium) provide better transcription accuracy for unknown audio but are slower. For forced alignment on a known transcript, the base model provides sufficient accuracy. Do not default to a larger model. Document the tradeoff in a comment so future developers understand the choice.

**Windows path normalization is not optional.** WAV paths passed into `align_text_to_audio()` will use Windows backslashes in the development and production environments described in this project. Some Whisper package builds fail on paths with backslashes. Always normalize to forward slashes using `pathlib.Path(path).as_posix()` before any path value is passed to Whisper.

**The 1.5-second minimum audio duration guard is required, not optional.** Whisper on clips shorter than roughly one second produces unreliable or empty word lists. Single-word segments generated by TTS are commonly shorter than one second. Without this guard, short segments will silently receive empty alignment and fall through to fallback timing — but only after Whisper has attempted and failed inference, wasting 3–5 seconds per such segment.

**Log messages must be actionable in production.** A log entry reading "alignment failed" provides no diagnostic value. Every warning and error log in `forced_aligner.py` must include the segment identifier, the project identifier, the file path or rejection reason, and the exception message when an exception is caught. These details reduce triage time from minutes to seconds.

**The fallback decision belongs in video_renderer.py, not in forced_aligner.py.** The aligner's sole responsibility is to return data or None. The decision of what to do with a None return — use proportional timing, log the reason, and continue — belongs in the render orchestrator where the full project context is available.

---

## 7. Data Structures Reference

This section documents every data structure that Feature 6.1 introduces or depends on. All structures are plain Python dicts passed between functions. No new classes are introduced.

### 7.1 Word Timing Dict

Produced by: `forced_aligner.align_text_to_audio()`

Consumed by: `forced_aligner.group_words_to_chunks()`

Description: Represents a single spoken word as identified by Whisper forced alignment. The word text is normalized — punctuation stripped, converted to lowercase — for matching purposes. The start and end values are floating-point seconds measured from the beginning of the WAV file.

| Key | Type | Description |
|---|---|---|
| word | str | Normalized word text (lowercase, punctuation stripped) |
| start | float | Time in seconds when this word begins in the audio |
| end | float | Time in seconds when this word ends in the audio |

Example for the phrase "Hello, world!":

- First dict: word is "hello", start is 0.04, end is 0.52
- Second dict: word is "world", start is 0.61, end is 1.10

### 7.2 Chunk Timing Dict

Produced by: `subtitle_engine.calculate_subtitle_timing()` (proportional path) or `forced_aligner.group_words_to_chunks()` (aligned path)

Consumed by: `fast_compositor.pre_render_subtitles()`

Description: Represents a single display-line chunk of subtitle text with its start and end timestamps. This is the primary timing currency of the subtitle pipeline. Both the proportional and aligned paths produce dicts in this identical format — the compositor does not need to know which source produced the list.

| Key | Type | Description |
|---|---|---|
| text | str | Full display string for the subtitle chunk (original casing, punctuation preserved) |
| start | float | Time in seconds when this chunk should first appear on screen |
| end | float | Time in seconds when this chunk should leave the screen |

Critical invariant: the chunk timing list returned by `group_words_to_chunks()` must be the same length as the list returned by `chunk_text()` for that segment. If the lengths differ, `pre_render_subtitles()` will produce incorrect output. Length equality must be asserted in the unit tests for `group_words_to_chunks()`.

### 7.3 forced_alignment_enabled Field Behavior Matrix

The following table summarizes all combinations of the `forced_alignment_enabled` field and alignment outcomes, and the resulting subtitle timing used in the final render:

| forced_alignment_enabled | align_text_to_audio() result | Timing used | Log output |
|---|---|---|---|
| False | Not called | Proportional (calculate_subtitle_timing) | None |
| True | Returns word list | Real aligned (group_words_to_chunks) | INFO: alignment successful |
| True | Returns None (short audio) | Proportional fallback | WARNING with segment ID and reason |
| True | Returns None (model missing) | Proportional fallback | WARNING with segment ID and reason |
| True | Returns None (exception) | Proportional fallback | ERROR with exception message |

---

## 8. Performance Considerations

### 8.1 Per-Segment Overhead Profile

Forced alignment adds inference overhead after each TTS call. The magnitude depends on audio duration, hardware, and the Whisper model variant. Using the base model on a standard CPU development machine, expect the following approximate times:

| Audio clip duration | Whisper inference time (base model, CPU) |
|---|---|
| 5 seconds | 3–5 seconds |
| 10 seconds | 5–8 seconds |
| 20 seconds | 8–15 seconds |
| 30 seconds | 12–20 seconds |

The inference time scales roughly linearly with audio duration. Clips under 5 seconds show a floor overhead of approximately 3 seconds due to model warm-up time even on cached model instances.

For a typical StoryFlow project with 8–12 segments at 10–15 seconds each, total alignment overhead is 50–120 seconds per render job. This is acceptable for a non-realtime render pipeline but should be communicated to users in the UI when they enable the toggle.

### 8.2 Model Load Time vs. Inference Time

Whisper base model load time is approximately 2–5 seconds on a machine that has already downloaded the model weights from disk. This overhead occurs only once per Python process, not once per render. The module-level caching in `_load_model()` ensures that a render job with 10 segments pays the load cost once and incurs only inference cost for segments 2 through 10.

If the model is not cached on disk, the first invocation triggers a network download of approximately 280 MB. On a 100 Mbps connection this takes roughly 25 seconds. On a slow deployment server, it may take several minutes. Pre-downloading the model before the first render job is strongly recommended for any production environment.

### 8.3 Memory Usage

The Whisper base model requires approximately 145 MB of RAM when loaded. Because the model is cached at module scope and not garbage collected between render jobs, this memory remains allocated for the lifetime of the backend Django process. On machines with 4 GB or less of RAM, this represents a meaningful fraction of available memory. On 8 GB or larger machines, it is negligible.

The word timing dicts produced per segment are small — a 200-word segment produces 200 dicts, each with three scalar values, consuming roughly 50 KB. This is negligible relative to the image data in the render pipeline and does not require any special memory management.

### 8.6 Caching Strategy Considerations

The current implementation does not cache alignment results between render jobs. If the same project is re-rendered twice with identical TTS output and the same text, Whisper runs twice and produces the same word timings both times. This is acceptable for Phase 6.1 because render jobs are infrequent and the overhead is bounded.

A future optimization could persist word timing results per segment alongside the WAV file — for example as a sidecar JSON file at the same path with a `.alignment.json` extension. On subsequent renders, the system would check for this sidecar file and skip the Whisper inference step if the sidecar exists and the WAV file modification time has not changed. This would reduce repeated-render overhead to near zero for unchanged segments.

This caching strategy is noted here as a design direction but is explicitly out of scope for Phase 6.1. It should be considered during Phase 5 performance polish if re-render latency is identified as a user pain point.

### 8.4 GPU Acceleration (Future Consideration)

The `whisper-timestamped` and `stable-whisper` packages both support CUDA GPU acceleration if PyTorch with CUDA is available. When forced alignment is enabled on a GPU-equipped server, inference time for a 10-second clip drops to approximately 0.5–1.5 seconds. This brings the feature's overhead from "noticeable" to "negligible" for production scale.

For Phase 6.1, GPU acceleration is not required and not implemented. If the future Phase 5 performance polish work targets render time reduction, enabling CUDA for Whisper inference is a high-value, low-effort addition — simply changing the device argument in `_load_model()` from the default CPU setting to "cuda" if a GPU is detected. A TODO comment should be placed at this location in `_load_model()` for the Phase 5 implementer.

### 8.5 Disk I/O Considerations

The alignment pipeline reads the WAV file once: when `align_text_to_audio()` opens it for duration checking and when Whisper reads it for inference. No additional copies of the WAV are created. The word timing dicts are held only in memory for the duration of the render job segment processing loop and are naturally garbage collected after each segment's overlay generation completes. No additional disk writes are introduced by this feature.
