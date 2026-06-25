# Feature 6.2 — Karaoke Word Highlighting (Word-by-Word Subtitle Animation)

| Field | Value |
|---|---|
| **Feature ID** | 6.2 |
| **Title** | Word-by-Word Karaoke Subtitle Highlighting |
| **Status** | 🟡 Planned |
| **Priority** | High |
| **Complexity** | Medium |
| **Estimated Effort** | 4–7 days |
| **Dependencies** | Feature 6.1 (Forced Alignment) must be fully implemented and tested; `forced_alignment_enabled` must be True on the project at render time for karaoke mode to produce correct output |
| **Output Files (NEW)** | None — all changes extend existing files |
| **Files Modified** | `backend/core_engine/subtitle_engine.py`, `backend/core_engine/fast_compositor.py`, `backend/core_engine/video_renderer.py`, `backend/api/models.py`, `backend/api/serializers.py` |

---

## 1. Document Overview

### 1.1 Problem Statement

StoryFlow currently renders subtitles by displaying one complete text chunk at a time. A chunk — typically a full line of three to six words — appears on screen all at once at its start time and disappears at its end time. Every word in the chunk carries equal visual weight from the moment the chunk appears to the moment it vanishes.

This static chunk display approach, while clean and readable, is passive. The viewer's eye stops moving once the chunk appears. The viewer reads ahead of the speaker within the first second, then waits — disconnected from the audio — for the next chunk to appear. The visual and auditory experience are decoupled.

For short-form social media content — TikTok, YouTube Shorts, and Instagram Reels in particular — the passive chunk style has become a marker of lower production effort. Creators who produce content at the highest perceived quality standard use a word-by-word highlight approach: the full current line is visible throughout the line's spoken duration, but the specifically active word — the one currently being spoken — is rendered in a high-contrast highlight color while all surrounding words remain at reduced visual weight. Viewers perceive this highlight moving from word to word in real time, synchronized to the audio, like lyrics on a karaoke screen.

The psychological effect of this technique is significant. The moving highlight keeps the viewer's eye anchored to the subtitles even when they are not deliberately reading. It creates a sense of forward motion and rhythm. It ties the visual medium to the audio without requiring the viewer to consciously track both. TikTok's auto-caption feature, which uses this technique by default, is cited in content creator communities as one of the highest-retention subtitle styles available.

StoryFlow's rendering pipeline is well-positioned to support this feature. Subtitles are already rendered as RGBA image overlays composited onto video frames. The feature requires generating more overlay images per segment — one per word boundary event rather than one per chunk — but does not require restructuring the compositing approach. The bottleneck concern, the word-level timestamps needed to drive the highlight position, is solved by Feature 6.1. Feature 6.2 consumes that data to make the rendering behavioral upgrade possible.

The risk of not implementing this feature is competitive: StoryFlow-generated videos will look visually older and less polished than videos produced by creators using CapCut, Opus Clip, or similar tools that offer karaoke captions as a default or easily accessible style.

### 1.2 Proposed Solution

Introduce a two-mode subtitle rendering system to the project. The existing static chunk display becomes "chunk" mode and remains the default for all existing projects. The new behavior is "karaoke" mode.

In karaoke mode, the subtitle compositor generates one visual overlay image per word boundary event within each display line. Each overlay image depicts the full current line with all words rendered in the base subtitle color (typically white), then redraws the currently active word on top in a configurable highlight color. When the alignment data advances to the next word, a new overlay image takes over for the subsequent frames. The net effect, when the resulting frame sequence is played back at full video speed, is a smoothly advancing highlight that tracks the spoken audio word by word.

The rendering mode and highlight color are stored as fields on the Project model. A request to use karaoke mode without forced alignment data available is handled gracefully: the system falls back to chunk mode and logs a specific warning rather than rendering incorrect highlights driven by proportional timing.

This solution is implemented through five coordinated changes:

A mode and color field added to the Project model. A new helper function in `subtitle_engine.py` that restructures word timing data into display-line groups suitable for karaoke rendering. An extended rendering branch in `fast_compositor.pre_render_subtitles()` that generates per-word highlight overlays. Updated wiring in `video_renderer.py` that detects the mode and passes the appropriate data to the compositor. Updated `serializers.py` to expose the new fields via the existing REST layer.

### 1.3 Scope

| Category | Items |
|---|---|
| **In Scope** | `subtitle_mode` CharField with "chunk" and "karaoke" choices on Project model; `subtitle_highlight_color` CharField on Project model; Django migration for both fields; both fields in ProjectSerializer; `chunk_words_for_karaoke()` function in `subtitle_engine.py`; karaoke rendering branch in `pre_render_subtitles()` in `fast_compositor.py`; automatic fallback to chunk mode when alignment data is absent; wiring in `video_renderer.py` to pass karaoke groups and highlight color to compositor |
| **Out of Scope** | Animated word transitions (fade-in, scale pop, bounce); per-segment subtitle mode override; custom font weight or size for highlighted word only; real-time karaoke preview in the frontend editor (frontend work); karaoke mode operating without Feature 6.1 word timing data; any change to the audio generation pipeline; multi-color highlight configurations |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| `backend/core_engine/subtitle_engine.py` | Chunk splitting and proportional timing; new `chunk_words_for_karaoke()` helper added here | Functional — existing functions present and tested; no existing functions modified |
| `backend/core_engine/fast_compositor.py` | RGBA subtitle overlay rendering; `pre_render_subtitles()` extended with karaoke branch | Functional — chunk mode fully implemented in `pre_render_subtitles()` |
| `backend/core_engine/forced_aligner.py` | Provides per-word timestamps that karaoke rendering requires | NEW as of Feature 6.1 — must exist and be functional before Feature 6.2 begins |
| `backend/core_engine/video_renderer.py` | Render orchestrator; passes subtitle mode and karaoke timing to compositor | Functional — updated in Feature 6.1 to carry alignment data |
| `backend/api/models.py` | Project model; receives two new fields | Functional — `forced_alignment_enabled` already added in Feature 6.1 |
| `backend/api/serializers.py` | REST serialization; two new fields must be added to ProjectSerializer | Functional — updated in Feature 6.1 for `forced_alignment_enabled` |

---

## 2. Flow Diagram

```
Project fields read:
  subtitle_mode ("chunk" or "karaoke")
  subtitle_highlight_color (hex string)
  forced_alignment_enabled (bool, from Feature 6.1)
          |
          v
Per-segment TTS + alignment pipeline (Feature 6.1 path)
          |
          v
word_timings: per-word {word, start, end} list   (None if alignment failed)
chunk_timings: per-chunk {text, start, end} list  (proportional or real)
          |
          |
          +------- subtitle_mode == "chunk" OR word_timings is None? ──────────┐
          |                                                                     |
          |                                                     [ pre_render_subtitles(
          |                                                       chunks, chunk_timings,
          |                                                       resolution, ...) ]
          |                                                                     |
          |                                                     one RGBA image per chunk
          |                                                                     |
          +------- subtitle_mode == "karaoke" AND word_timings is not None?    |
                             |                                                  |
                             v                                                  |
              [ subtitle_engine.chunk_words_for_karaoke(                       |
                word_timings, chunk_texts) ]                                   |
                             |                                                  |
                             v                                                  |
              karaoke_groups: list of display-line groups                      |
              each group = {                                                    |
                line_text: str,                                                 |
                start: float,                                                   |
                end: float,                                                     |
                words: [{word, start, end, index}, ...]                        |
              }                                                                 |
                             |                                                  |
                             v                                                  |
              [ pre_render_subtitles(chunks, chunk_timings,                    |
                karaoke_word_timings=karaoke_groups,                           |
                highlight_color=subtitle_highlight_color) ]                    |
                             |                                                  |
                             v                                                  |
              For each word event in each chunk:                               |
                - render full line: all words in base color                    |
                - re-draw active word at its pixel offset in highlight_color   |
                - store RGBA image tagged with word.start and word.end         |
                             |                                                  v
                             +──────────────────────────────────────────────────+
                                                      |
                                                      v
                                         RGBA subtitle overlay list
                                         (more items in karaoke than chunk)
                                                      |
                                                      v
                                       video_renderer composites onto frames
                                                      |
                                                      v
                                            Final rendered video
```

---

## 3. Step-by-Step Instructions

### Step 3.1 — Add subtitle_mode and subtitle_highlight_color to the Project model

Open `backend/api/models.py`. Locate the Project model class. Find the area where other rendering-quality fields are defined — the `forced_alignment_enabled` field added in Feature 6.1 is a natural neighbor. Add the following two fields immediately after `forced_alignment_enabled`:

The first field is `subtitle_mode`. It is a `CharField` with `max_length=10`. Define a `choices` argument with two tuples: `("chunk", "Chunk Mode")` and `("karaoke", "Karaoke Mode")`. Set `default="chunk"`. Set `help_text` to: "Subtitle display mode. 'chunk' shows the full text chunk at once. 'karaoke' highlights each word as it is spoken. Karaoke mode requires forced_alignment_enabled=True and falls back to chunk mode if word timing data is unavailable."

The second field is `subtitle_highlight_color`. It is a `CharField` with `max_length=20`. Set `default="#FFD700"` (gold-yellow, the standard TikTok-style caption highlight color). Set `help_text` to: "CSS hex color string for the active word highlight in karaoke mode. Default is #FFD700 (gold-yellow). Any valid CSS hex color (3-digit or 6-digit, with or without leading hash) is accepted, though no format validation is enforced at the model level."

After saving, create and apply the migration. Run `python manage.py makemigrations api` from the `backend/` directory. Inspect the generated migration file to confirm it adds exactly the two new fields. Run `python manage.py migrate` and confirm it applies cleanly. Since `forced_alignment_enabled` was added in the Feature 6.1 migration, this migration must list the Feature 6.1 migration as its prior dependency — Django's automatic migration sequencing handles this, but verify by checking the `dependencies` list in the generated migration class.

### Step 3.2 — Expose both new fields in the serializer

Open `backend/api/serializers.py`. Locate the ProjectSerializer class and its Meta inner class or fields specification. Add `subtitle_mode` and `subtitle_highlight_color` to the fields definition.

No custom validation is required for `subtitle_mode` — Django REST Framework reflects the model's `choices` constraint and will reject unknown values at the serializer validation stage. For `subtitle_highlight_color`, add an inline comment noting that hex color format validation (ensuring the value is a valid CSS hex string) is deferred to a future phase. Currently, any string up to 20 characters is accepted; an invalid color string will produce a rendering error at render time rather than an API validation error at save time.

Verify both fields are present in the serializer response by reading a Project object through the REST API and confirming the two new keys appear in the JSON response with their correct default values.

### Step 3.3 — Write chunk_words_for_karaoke() in subtitle_engine.py

Open `backend/core_engine/subtitle_engine.py`. Add a new function at the bottom of the file, after the last existing function, named `chunk_words_for_karaoke`. Do not modify any existing functions in this file.

This function accepts two arguments. The first argument is `chunk_timings`, the list of chunk timing dicts as produced by either `calculate_subtitle_timing()` or `forced_aligner.group_words_to_chunks()`. Each dict has "text", "start", and "end" keys. The second argument is `word_timings`, the flat per-word list produced by `forced_aligner.align_text_to_audio()`, where each dict has "word", "start", and "end" keys.

The function transforms from chunk-level data to a per-word karaoke group structure. The logic proceeds as follows:

Walk through `chunk_timings` in order. For each chunk, split the chunk's "text" value on whitespace to get the individual display words (preserving original casing and punctuation for display — do not normalize here, this is the display layer). The word list derived from the split defines both the display content and the count of expected words for this chunk.

Now map the display words to entries in `word_timings`. Maintain a sequential index into `word_timings` that advances across all chunks — do not reset to zero for each chunk. For the first display word of the chunk, look at `word_timings[current_index]` and advance the index. For the second display word, use `word_timings[current_index + 1]`, and so on. This sequential consumption works because `word_timings` is ordered identically to the original text.

For each chunk, build a karaoke group dict with four keys: "line_text" (the full chunk display string as-is), "start" (the chunk's start time from `chunk_timings`), "end" (the chunk's end time from `chunk_timings`), and "words" (a list of per-word dicts). Each per-word dict contains: "word" (the original display string with punctuation preserved for display), "start" (the float start time from `word_timings`), "end" (the float end time from `word_timings`), and "index" (the zero-based position of this word within its display line).

If the sequential word_timings index would exceed the length of `word_timings` before all chunks are processed — indicating that Whisper produced fewer word entries than the text contains — use the parent chunk's start and end times for all remaining unmatched words within that chunk and log a DEBUG-level message identifying the chunk by its text and index.

Return the list of karaoke group dicts. The list length equals the length of `chunk_timings`.

### Step 3.4 — Extend pre_render_subtitles() in fast_compositor.py

Open `backend/core_engine/fast_compositor.py`. Locate the `pre_render_subtitles()` function. Read through its current implementation to understand: how it iterates over chunks, how it calls the text rendering and layout functions, how it constructs the return list, and how it measures text width for positioning.

Add two new keyword arguments to the function signature: `karaoke_word_timings` with a default value of None, and `highlight_color` with a default value of `"#FFD700"`. These must be keyword-only arguments with defaults so that all existing calls to the function with positional arguments remain valid without modification.

At the top of the function body, before the main iteration, add a mode-selection check: if `karaoke_word_timings` is not None and its length equals the length of the chunks input, set a local variable `mode` to `"karaoke"`. Otherwise, set `mode` to `"chunk"`. This guard prevents an index-length mismatch between chunks and karaoke groups from causing an IndexError.

In the chunk mode branch (when `mode == "chunk"`): execute the existing code entirely unchanged. Do not modify a single line of the existing chunk rendering logic.

In the karaoke mode branch (when `mode == "karaoke"`): replace the chunk-per-iteration rendering with a word-per-iteration approach. For each chunk at index `i`:

Retrieve the karaoke group from `karaoke_word_timings[i]`. Iterate over each word entry in the group's "words" list. For word at position `j` within the line, construct one RGBA overlay image as follows:

First, render the full "line_text" string using the same font, font size, color settings, and canvas dimensions that chunk mode uses. This produces the complete line in the base subtitle color. Use the same rendering utility calls that chunk mode uses — do not replicate the font loading or draw setup separately.

Second, calculate the pixel x-offset of word `j` within the line. Measure the combined pixel width of all words at positions 0 through j-1, including inter-word spaces, using the same font metrics object used in the first render step. This measurement must use identical font object and size to the one that drew the full line, otherwise the offset drifts.

Third, draw the word at position `j` again at the computed x-offset, in the `highlight_color`, on top of the already-rendered line. This overwrites the base-color instance of the word with the highlight-color version.

Store the resulting RGBA image in the output list as a dict with "image", "start" set to the word's "start" time from the karaoke group, and "end" set to the word's "end" time. This means the output list will have one entry per word event, not one entry per chunk.

### Step 3.5 — Wire karaoke mode through video_renderer.py

Open `backend/core_engine/video_renderer.py`. Locate the per-segment processing loop, specifically the area where chunk timings are assembled and where `pre_render_subtitles()` is called.

After the block added in Feature 6.1 (which resolves chunk timings via alignment or proportion), add a karaoke data preparation step:

Check whether the project's `subtitle_mode` equals "karaoke". If it does, and if the raw word timings from the alignment step are available (not None), call `subtitle_engine.chunk_words_for_karaoke()` with the chunk timings and the word timings. Store the result as `karaoke_groups`.

If `subtitle_mode` is "karaoke" but word timings are None (alignment was disabled or failed), log a WARNING stating that karaoke mode cannot run without aligned word timings for this segment, and that the segment will render in chunk mode. Set `karaoke_groups` to None.

Pass `karaoke_groups` to `pre_render_subtitles()` as the `karaoke_word_timings` argument, and pass `project.subtitle_highlight_color` as the `highlight_color` argument. When `karaoke_groups` is None, `pre_render_subtitles()` will detect it and use chunk mode automatically by design.

### Step 3.6 — Verify pixel-level highlight accuracy

After wiring the end-to-end karaoke path, isolate and test the highlight alignment visually. Render a single short test segment — exactly five or six words, one chunk — in karaoke mode. Inspect the individual overlay RGBA images saved during that render (add a debug export step temporarily if needed). For each overlay image, verify:

Exactly one word appears in the highlight color. The highlighted word is at the correct position in the line sequence — the first overlay highlights word one, the second highlights word two, and so on. The highlighted word's text content matches the word's "word" field in the karaoke group. The highlighted word is pixel-aligned with the same word in the base-color full-line render — no horizontal offset, no partial overlap with adjacent words.

This visual validation is essential because the pixel offset calculation is the most precision-sensitive part of the implementation. Errors here cause the wrong word to appear highlighted even when the timing logic is correct.

### Step 3.7 — Test fallback behavior for each fallback trigger

There are three distinct conditions that should cause karaoke mode to fall back to chunk mode. Test each separately:

Test 1 — mode is "chunk" (default): Set `subtitle_mode = "chunk"` on a project with `forced_alignment_enabled = True`. Render and confirm the output uses static chunk display with no highlighting. Confirm no karaoke-related code paths were entered by checking that `chunk_words_for_karaoke()` was not called.

Test 2 — karaoke requested but alignment disabled: Set `subtitle_mode = "karaoke"` and `forced_alignment_enabled = False`. Render and confirm the output uses chunk-mode display. Confirm a WARNING log message is written with the segment ID and project ID. Confirm no exception is raised.

Test 3 — karaoke requested but alignment failed: Set `subtitle_mode = "karaoke"` and `forced_alignment_enabled = True`, but simulate alignment failure (pass a bad WAV path temporarily). Confirm the output uses chunk-mode display. Confirm a WARNING log message is written. Confirm no exception is raised.

All three tests must pass before the feature is considered complete.

### Step 3.8 — Write a word-count verification test

Create a test where the narration text for a segment contains exactly eight words distributed across two chunks — four words per chunk. Enable both `forced_alignment_enabled` and `subtitle_mode = "karaoke"`. Run the render and retrieve the subtitle overlay count for that segment from the render output. Assert the count equals eight (one overlay per word event). Assert the first four overlays all display the same first line, with each successively highlighting words one through four. Assert the second four overlays all display the same second line, with each highlighting words one through four of that line.

---

## 4. Expected Outcome

1. When `subtitle_mode` is "karaoke" and `forced_alignment_enabled` is True, the rendered video displays the currently spoken word in the highlight color while all other visible words in the same line appear in the base subtitle color.
2. The highlight position advances from word to word in precise synchronization with the Kokoro TTS audio, with timing accuracy matching the forced alignment quality from Feature 6.1.
3. The `subtitle_highlight_color` field controls the active word color and defaults to gold-yellow (`#FFD700`) when the field has not been set.
4. When `subtitle_mode` is "karaoke" but word timing data is unavailable (alignment disabled, or alignment failed), the system falls back to chunk mode automatically. A WARNING log message is written with the project ID, segment ID, and the specific reason for the fallback.
5. When `subtitle_mode` is "chunk" (the default for all existing and new projects), behavior is entirely identical to the pre-feature state. No visual change, no performance change, no additional log output.
6. The total number of subtitle overlay images per segment in karaoke mode equals the total word count for that segment, compared to the much smaller chunk count that chunk mode produces.
7. Both new Project model fields are readable and writable via the existing Project REST endpoints without new routes.
8. A Django migration for both fields is created and applies cleanly as a continuation of the Feature 6.1 migration sequence.
9. `chunk_text()` and `calculate_subtitle_timing()` in `subtitle_engine.py` remain completely unmodified.
10. All existing chunk-mode renders remain visually and structurally identical to their pre-feature baselines — zero regression risk on the default code path.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- Call `chunk_words_for_karaoke()` with a pre-built two-chunk timing list and a matching mock flat word list (eight words, four per chunk). Assert the return list has length two. Assert each item is a dict with "line_text", "start", "end", and "words" keys. Assert the "words" list in the first item has length four and that the "index" field of each word is 0, 1, 2, 3 respectively.
- Call `chunk_words_for_karaoke()` with a single-word chunk (one chunk, one word). Assert the "words" list in the returned group has exactly one entry. Assert its "start" and "end" match the word timing entry for that word.
- Call `chunk_words_for_karaoke()` with a `word_timings` list that is shorter than the total word count implied by `chunk_timings`. Assert the function returns a list of the same length as the chunks input, with no None items or missing keys — unmatched words receive fallback timing from their parent chunk's start and end.
- Call `pre_render_subtitles()` with `karaoke_word_timings=None` and assert the return list length equals the length of the chunks input (confirming chunk mode activates when the parameter is None).
- Call `pre_render_subtitles()` with a `karaoke_word_timings` list of different length than the chunks list. Assert the function falls back to chunk mode (return count equals chunk count) rather than raising an IndexError.
- Test the Project model defaults: create a Project instance without specifying `subtitle_mode` or `subtitle_highlight_color`. Assert `subtitle_mode == "chunk"` and `subtitle_highlight_color == "#FFD700"`.
- Test the Project model validation: attempt to assign `subtitle_mode = "invalid_mode"` and run full model validation. Assert a ValidationError is raised.

### 5.2 Integration / Manual Tests

- Render a project with the default `subtitle_mode = "chunk"` after the feature is deployed. Compare the output frame-by-frame (or byte-by-byte on the subtitle overlay images) against the pre-feature baseline. Assert zero visual difference.
- Render a project with `subtitle_mode = "karaoke"` and `forced_alignment_enabled = True`. Play back the video and confirm that the highlighted word visibly tracks the spoken audio. No word should appear highlighted before it is spoken or after it has ended.
- Change `subtitle_highlight_color` to `"#FF0000"` (red) on a project and render in karaoke mode. Confirm the active word appears in red in the output video rather than the default gold-yellow.
- Render a segment whose text contains a long technical term (e.g., 14+ character word). Confirm that the highlight overlay for that word covers only that word and does not bleed horizontally into adjacent words in the display line.
- Render a segment whose text consists of a single very short word per chunk. Confirm that each karaoke group "words" list has exactly one entry and that the single-word chunk renders correctly without index errors.
- Test the karaoke-without-alignment fallback: set `subtitle_mode = "karaoke"` and `forced_alignment_enabled = False`. Render a project. Confirm the output uses chunk-mode subtitles, that the render log contains a WARNING with the project ID and segment ID, and that no exception was raised.
- Send REST API requests to set both `subtitle_mode` and `subtitle_highlight_color` to various values and confirm persistence and retrieval.

### 5.3 Regression Tests

- Run the entire backend test suite (`test_e2e.py`, `test_settings.py`) after all changes are applied. Confirm zero new failures.
- Confirm that `chunk_text()` and `calculate_subtitle_timing()` in `subtitle_engine.py` are unchanged at the source level (git diff confirms zero changes) and pass all their existing tests.
- Render an existing test project in chunk mode after the feature is deployed. Assert the subtitle overlay image list has the same length as before the feature was added (one overlay per chunk, not one per word).
- Confirm `pre_render_subtitles()` called without the new keyword arguments (as all existing call sites do) produces identical output to pre-feature renders — the new optional parameters must not change behavior when absent.
- Confirm the migration sequence in `backend/api/migrations/` is valid: the Feature 6.2 migration lists the Feature 6.1 migration as its dependency, and both apply in order on a fresh database.
- Confirm that the Feature 6.1 alignment path (`align_text_to_audio()` and `group_words_to_chunks()`) is not disrupted by Feature 6.2 changes. Run the Feature 6.1 unit tests after applying all Feature 6.2 changes and assert they still pass.
- Confirm that the ProjectSerializer response for an existing project created before this feature includes `subtitle_mode` (defaulting to "chunk") and `subtitle_highlight_color` (defaulting to "#FFD700") without error.

---

## 6. Notes for AI Agent

**Feature 6.1 must be complete and fully tested before Feature 6.2 begins.** The `chunk_words_for_karaoke()` function depends on the flat word timing list from `forced_aligner.align_text_to_audio()`. Without that data, the entire karaoke path produces nothing useful and cannot be meaningfully tested. Do not start any Feature 6.2 implementation tasks until `forced_aligner.py` passes all its unit tests.

**The pre_render_subtitles() return format must not change structurally.** The compositing step in `video_renderer.py` consumes its output as a list of dicts with "image", "start", and "end" keys. In karaoke mode, the list simply contains more items with narrower time windows. Any structural deviation — a renamed key, a different type for any value, a nested list where a flat list was expected — breaks compositing for both modes simultaneously.

**Font metrics consistency is the most fragile step.** The pixel offset calculation in Step 3.4 measures the width of words to position the highlight. If the font object and font size used for measuring differ even slightly from the font used to draw the full line, the highlight will be misaligned — covering part of one word and part of the next. Identify the exact font object reference used in the existing compositor's draw calls and use that same reference for all measuring operations. Do not create a new font object for measurement.

**The karaoke overlay count is equal to the word count, not chunk count.** For a 200-word project with five segments, karaoke mode produces approximately 200 overlay image objects instead of the 40–60 that chunk mode produces. Each object is a small RGBA image covering the subtitle strip area, not a full-resolution frame, so memory pressure is moderate. Document this fact with a comment in `pre_render_subtitles()` so future optimization work knows the scale.

**Mode selection guard must be in pre_render_subtitles(), not only in video_renderer.py.** If karaoke groups and chunks have different lengths due to any upstream bug, the compositor must not raise an IndexError — it must detect the mismatch and fall back to chunk mode. Guard against this inside the compositor itself, not just in the caller.

**Fallback logging must be specific.** When karaoke mode falls back to chunk mode in `video_renderer.py`, the warning log must state the project ID, the segment ID, and the exact reason (alignment not enabled, alignment returned None, karaoke group length mismatch). Vague fallback messages create debugging investigations that could be avoided with a 10-character addition to the log string.

**Test all three fallback scenarios independently.** Fallback 1 (chunk mode selected) and Fallback 2 (karaoke selected, alignment disabled) and Fallback 3 (karaoke selected, alignment failed) are three separate code branches in `video_renderer.py`. Each must be exercised by its own test case. A single test that confirms "chunk mode renders correctly" does not validate that all three fallback triggers are wired and logging correctly.

**Do not apply highlight color validation at the model level in this phase.** The `subtitle_highlight_color` field accepts free-form strings. An invalid string (for example "redish") will cause a rendering error at compositor time, not at API save time. This is acceptable for Phase 6.2 but must be noted in the serializer with a comment. A hex color regex validator on the serializer field is the correct long-term fix — mark it as a TODO for the Phase 5 polish work.

**The transition at a word boundary must be binary, not gradual.** At the exact video frame where the active word changes — where one word's end timestamp is passed and the next word's start timestamp begins — the compositor must switch immediately to the next word's overlay image. The comparison rule must be consistent: a word's overlay is active for all frames where the frame timestamp is greater than or equal to the word's start and strictly less than the word's end time. Using greater-than (rather than greater-than-or-equal) for the start comparison creates gap frames where no word appears highlighted. Using less-than-or-equal for the end comparison creates overlap frames where two words appear simultaneously. Both errors are visible at normal playback speed on slow-motion review.

**subtitle_mode choices validation.** Django's CharField choices constraint enforces allowed values during full model validation, not on every `.save()` call. To catch invalid mode strings at the REST API level, ensure the serializer uses `choices` validation. DRF's CharField with a model that has choices defined will perform validation automatically during deserialization, but confirm this behavior with a test passing an invalid mode string through the serializer.

---

## 7. Data Structures Reference

This section documents every data structure that Feature 6.2 introduces or depends on. All structures are plain Python dicts. No new classes are introduced.

### 7.1 Karaoke Word Dict

Produced by: `subtitle_engine.chunk_words_for_karaoke()` (nested inside karaoke groups)

Consumed by: `fast_compositor.pre_render_subtitles()` in karaoke rendering branch

Description: Represents a single word within a display line for karaoke rendering purposes. The word text preserves original casing and punctuation for display — this is the render layer and normalization is not appropriate here. The start and end times come from the forced alignment word timing list from Feature 6.1. The index field identifies the word's position within its display line for pixel offset calculation.

| Key | Type | Description |
|---|---|---|
| word | str | Display text (original casing, punctuation preserved) |
| start | float | Time in seconds when this word begins in the audio |
| end | float | Time in seconds when this word ends in the audio |
| index | int | Zero-based position of this word within its display line |

### 7.2 Karaoke Group Dict

Produced by: `subtitle_engine.chunk_words_for_karaoke()`

Consumed by: `fast_compositor.pre_render_subtitles()` as the `karaoke_word_timings` list entries

Description: Represents one display line (one chunk) in karaoke mode. Contains the full line text for rendering the base-color backdrop and the constituent per-word dicts for generating the highlight overlays. The start and end times represent the full chunk window and are used as fallback timing context if individual word timing is unavailable.

| Key | Type | Description |
|---|---|---|
| line_text | str | Full display string for the entire chunk (original casing, punctuation preserved) |
| start | float | Chunk start time in seconds (from chunk_timings input) |
| end | float | Chunk end time in seconds (from chunk_timings input) |
| words | list | Ordered list of Karaoke Word Dicts for the words in this line |

The length of the karaoke_groups list passed to `pre_render_subtitles()` must equal the length of the chunks list. This invariant is enforced by the compositor's mode-selection guard: if lengths differ, chunk mode activates automatically.

### 7.3 Subtitle Overlay Dict (extended)

Produced by: `fast_compositor.pre_render_subtitles()` — unchanged structure, different cardinality in karaoke mode

Consumed by: the compositing step in `video_renderer.py`

Description: This dict structure is unchanged from the chunk-mode implementation. In karaoke mode, the compositor simply produces one of these dicts per word boundary event rather than per chunk. The downstream compositing code consumes this list identically in both modes.

| Key | Type | Description |
|---|---|---|
| image | numpy RGBA array | The rendered subtitle overlay image for this time window |
| start | float | Time in seconds at which this overlay begins displaying |
| end | float | Time in seconds at which this overlay stops displaying |

### 7.4 New Model Field Summary

The following table summarizes the two new fields added to the Project model by Feature 6.2, their types, defaults, and constraints:

| Field name | Type | Default | Valid values | Serializer behavior |
|---|---|---|---|---|
| subtitle_mode | CharField (max 10) | "chunk" | "chunk", "karaoke" | Choices validated by DRF on deserialize |
| subtitle_highlight_color | CharField (max 20) | "#FFD700" | Any string up to 20 chars | No format validation in this phase |

---

## 8. Performance Considerations

### 8.1 Overlay Count Increase in Karaoke Mode

The most significant performance difference between chunk mode and karaoke mode is the number of RGBA overlay images generated per segment. In chunk mode, one overlay is generated per display chunk. A typical 15-second segment with 30 words split into 7 chunks produces 7 overlay images. In karaoke mode, the same segment produces 30 overlay images — one per word boundary event.

This increase is approximately four to five times the chunk-mode overlay count for typical narration. Each overlay image is a small RGBA array covering the subtitle strip area of the frame (not the full resolution frame), so the memory and compute cost per overlay is low. However, the compositing loop in `video_renderer.py` must handle a longer list per segment, which adds a proportional but sub-linear processing cost to the compositing phase.

Estimated karaoke-mode overhead relative to chunk-mode for the overlay generation step only: 2–4 times longer for the `pre_render_subtitles()` call. Total render time increase accounting for all pipeline stages: approximately 10–20 percent on a typical project. This is acceptable for the visual quality gain.

### 8.2 Pixel Offset Calculation Cost

For each karaoke word overlay, the compositor must calculate the pixel x-offset of the highlighted word within the line. This requires measuring the rendered width of each preceding word using the font metrics object. For a line with N words, calculating word position j requires measuring j−1 word widths.

For a five-word line, the most expensive word (position 4) requires four font metric measurements. For typical subtitle font sizes (say 20-point to 30-point), each measurement is a fast in-memory operation taking under 0.1 ms. Even for a 40-word segment rendered as karaoke overlays, the total pixel offset calculation cost is under 10 ms and does not represent a bottleneck.

However, the font metrics object must be identical between the full-line render and the offset measurement calls. Instantiating a new font object for each measurement call would introduce unnecessary object creation overhead. Cache the font metrics object as a local variable at the start of the karaoke rendering branch and reuse it throughout.

### 8.3 Memory Profile

In chunk mode, the overlay image list for one segment holds 7–12 RGBA arrays. In karaoke mode, the same segment holds 25–50 RGBA arrays. Each array is sized to the subtitle strip dimensions, not the full frame. For a 1080p video with a subtitle strip of approximately 1920 x 120 pixels at 4 channels (RGBA), each overlay is 1920 × 120 × 4 bytes = roughly 900 KB. For 50 overlays, total peak memory for one segment's overlay list is approximately 45 MB.

This memory is held during the compositing phase and released as soon as compositing is complete. For a 10-segment project rendered sequentially, peak overlay memory at any given moment is approximately 45 MB (one segment at a time). This is well within acceptable limits for all expected deployment configurations.

If future work parallelizes segment rendering across multiple threads or processes, overlay memory must be carefully scoped per-segment to avoid accumulating all segments' overlays simultaneously, which would scale by segment count.

### 8.4 Frame-Level Compositing Overhead

The video renderer must look up the correct overlay image for each rendered video frame. In chunk mode, the lookup table has 7–12 entries per segment. In karaoke mode, it has 25–50 entries. The lookup is an ordered scan against start/end time ranges.

For a 30 fps video at 15 seconds per segment, there are 450 frames per segment. Each frame does one lookup through at most 50 entries in karaoke mode. Even a naive linear scan is 450 × 50 = 22,500 comparisons per segment — negligible for modern hardware. A binary search by start time would be even faster but is not necessary to implement in this phase.

### 8.5 Interaction with Feature 6.1 Overhead

Karaoke mode requires forced alignment to be enabled. Any project using karaoke mode will already be paying the Feature 6.1 Whisper inference overhead (3–8 seconds per segment on CPU). The Feature 6.2 karaoke rendering overhead (extra overlay generation and compositing) adds less than 1 second per segment on top of that. In total, a project with both features enabled will render approximately 6–15 seconds slower per segment than a baseline chunk-mode render, dominated almost entirely by the Whisper inference time from Feature 6.1.

This combined overhead is fixed regardless of whether the user chooses chunk mode or karaoke mode after enabling forced alignment. If a user enables `forced_alignment_enabled = True` for the timing accuracy benefit but wants to stay in chunk mode for the visual style, they get better chunk timing with no karaoke overhead. The karaoke overlay generation overhead only activates when `subtitle_mode = "karaoke"` is also set.

### 8.6 Recommendation Summary

Enable forced alignment first, observe improved timing quality in chunk mode, and then enable karaoke mode as a second step. This two-step rollout strategy allows users to evaluate alignment quality independently of the visual karaoke style and isolates the source of any rendering issue that may arise during testing.
