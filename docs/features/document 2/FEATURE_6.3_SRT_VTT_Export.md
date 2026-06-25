# Feature 6.3 — SRT / VTT Subtitle Export

| Field | Value |
|---|---|
| **Feature ID** | 6.3 |
| **Title** | SRT and VTT Subtitle File Export |
| **Status** | 🟡 Planned |
| **Priority** | Medium |
| **Complexity** | Low |
| **Estimated Effort** | 2–3 days |
| **Dependencies** | Subtitle engine (subtitle_engine.py), render pipeline (video_renderer.py), Project model (models.py) |
| **Output Files (NEW)** | `backend/media/projects/{id}/subtitles.srt` (at render time), `backend/media/projects/{id}/subtitles.vtt` (at render time), `backend/api/migrations/xxxx_add_export_flags.py` |
| **Files Modified** | `backend/core_engine/subtitle_engine.py`, `backend/core_engine/video_renderer.py`, `backend/api/models.py`, `backend/api/serializers.py` |

---

## 1. Document Overview

### 1.1 Problem Statement

StoryFlow's subtitle system is currently hardcoded to burn subtitle text directly into video frames. During rendering, `subtitle_engine.py` computes the timing for each subtitle chunk — which word group appears on screen, at what second it begins, and at what second it ends. This timing data is then used by `fast_compositor.py` to draw text overlays onto the individual frames of the output video.

While burned-in subtitles work well for social media platforms that auto-play muted content, they create significant problems in the following situations:

- **YouTube closed captions:** YouTube's system cannot extract burned-in subtitles for its own caption track. Creators must separately upload an SRT or VTT file to enable proper closed captions, which are searchable, translatable, and can be styled by the viewer.
- **Accessibility compliance:** Web Content Accessibility Guidelines (WCAG) and similar standards require separate caption tracks for video content distributed on websites or apps. Burned-in subtitles do not satisfy this requirement.
- **Content repurposing:** A creator who wants to translate their video to another language cannot extract the original subtitle timing from the video file. A separate SRT or VTT file would allow translation tools to work directly on the caption data.
- **Edit flexibility:** Post-production editors who receive StoryFlow output cannot adjust subtitle timing or text without re-rendering the entire video. Editable subtitle files allow non-destructive post-processing.

The core timing data required to generate these files already exists inside the render pipeline. The problem is purely one of output — no code currently writes that data to a standalone subtitle file format.

### 1.2 Proposed Solution

At the end of the render pipeline, after `fast_render_segments()` completes and the video file is written, optionally write the subtitle timing data to one or both of the following file formats:

- **SRT (SubRip Text):** The most universally supported subtitle format. Accepted by YouTube, VLC, DaVinci Resolve, Premiere Pro, and virtually every platform. Format consists of numbered subtitle blocks, each with a timecode line and text.
- **VTT (WebVTT):** The web-native subtitle format supported natively in HTML5 video elements. Required for subtitles on web applications and used by many streaming platforms.

The feature is controlled by two new boolean flags on the `Project` model: `export_srt` and `export_vtt`. When a flag is set to `True`, the corresponding file is generated and saved alongside the `output.mp4` in the project's media directory at the end of every render. The flags default to `False` to preserve existing behavior unchanged.

Two new functions — `generate_srt` and `generate_vtt` — are added to `subtitle_engine.py`. They accept the same subtitle chunk and timing data that is already computed during the render, format it according to the respective specification, and return the file content as a plain string. `video_renderer.py` then writes this string to disk.

The URLs of any generated subtitle files are included in the render result dictionary returned by `render_project`, allowing the API to surface download links for the frontend.

### 1.3 Scope

| In Scope | Out of Scope |
|---|---|
| `generate_srt()` function in `subtitle_engine.py` producing valid SRT output | Automatic upload of subtitle files to YouTube or any external platform |
| `generate_vtt()` function in `subtitle_engine.py` producing valid VTT output | Subtitle translation or localization |
| `export_srt` and `export_vtt` boolean fields on the `Project` model | A subtitle editor UI in the frontend |
| Django migration for the two new model fields | ASS/SSA or other subtitle format support |
| Subtitle files written to `media/projects/{id}/` at the end of render | Real-time subtitle preview in the project editor |
| Subtitle file paths returned in the render result dict | Per-segment subtitle granularity or chapter markers |
| API serializer updated to expose `export_srt` and `export_vtt` fields | Modifying burned-in subtitle behavior in any way |
| Django migration applies cleanly on existing databases | Streaming subtitle data via WebSocket during render |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| `backend/core_engine/subtitle_engine.py` | Computes subtitle chunks and timing; provides data to compositor | Contains `chunk_text(text)` and `calculate_subtitle_timing(chunks, audio_duration)`; no file-writing functions exist |
| `backend/core_engine/fast_compositor.py` | Pre-renders subtitle overlays onto video frames | Consumes subtitle timing data from `subtitle_engine.py`; outputs burned frames only |
| `backend/core_engine/video_renderer.py` | Orchestrates the full render: calls subtitle engine, compositor, audio merge | `render_project(project_id)` is the entry point; subtitle data is computed internally and used for frame overlays but never written to a file |
| `backend/api/models.py` | Database models | `Project` model exists without subtitle export flags |
| `backend/api/serializers.py` | REST API JSON layer | `ProjectSerializer` exists; needs `export_srt` and `export_vtt` fields added |

---

## 2. Flow Diagram

    Project settings include export_srt=True and/or export_vtt=True
                       │
                       ▼
           render_project(project_id) called
                       │
                       ▼
        Load project from database, read export flags
                       │
                       ▼
        For each segment: compute subtitle chunks + timings
        via calculate_subtitle_timing(chunks, audio_duration)
                       │
                       ▼
        fast_render_segments() burns subtitles into frames
        (existing behavior — unchanged)
                       │
                       ▼
        Collect all subtitle chunks + timings from all segments
        into a single ordered list (full-video timeline)
                       │
              ┌────────┴────────┐
              │                 │
        export_srt=True    export_vtt=True
              │                 │
              ▼                 ▼
        generate_srt(    generate_vtt(
         subtitle_data)    subtitle_data)
              │                 │
              ▼                 ▼
        Write to             Write to
        subtitles.srt        subtitles.vtt
        in media/projects/   in media/projects/
        {id}/                {id}/
              │                 │
              └────────┬────────┘
                       │
                       ▼
        Include subtitle file URLs in render result dict
                       │
                       ▼
        API response includes downloadable subtitle URLs

---

## 3. Step-by-Step Instructions

### Step 3.1 — Add Export Flags to the Project Model

Open `backend/api/models.py` and locate the `Project` model class. Add two new fields to the model:

- `export_srt` as a BooleanField with a default of `False` and a help text string that briefly describes its purpose (e.g., "Generate a standalone SRT subtitle file after rendering").
- `export_vtt` as a BooleanField with a default of `False` and a help text string (e.g., "Generate a standalone VTT subtitle file after rendering").

Both fields should be straightforward boolean columns with no special constraints. After adding the fields, generate a new Django migration. Confirm the migration file is created in `backend/api/migrations/` and run it to update the local development database. Verify that the two new columns appear in the `api_project` table.

### Step 3.2 — Update the Project Serializer

Open `backend/api/serializers.py` and locate the `ProjectSerializer`. Add `export_srt` and `export_vtt` to the list of fields included in the serializer. Both fields should be writable so that API clients (and eventually the frontend) can toggle them when creating or updating a project. No special validation logic is required — these are simple boolean toggles.

### Step 3.3 — Implement generate_srt in subtitle_engine.py

Open `backend/core_engine/subtitle_engine.py` and add a new function called `generate_srt`. This function accepts one argument: a list of subtitle block dictionaries, where each dictionary contains the subtitle text, the start time in seconds (as a float), and the end time in seconds (as a float). The list covers all subtitle blocks across the entire video in chronological order.

Inside the function, iterate over the list with a counter starting at 1. For each subtitle block:

First, format the start time into the SRT timecode format. SRT timecodes use the pattern `HH:MM:SS,mmm` where `HH` is zero-padded hours, `MM` is zero-padded minutes, `SS` is zero-padded seconds, and `mmm` is zero-padded milliseconds. The millisecond separator in SRT is a comma, not a period — this is a common mistake to avoid.

Second, format the end time in the same pattern.

Third, assemble a subtitle block string in the following structure: the index number on its own line, then the timecode range on the next line in the format `{start} --> {end}`, then the subtitle text on the next line, then a blank line to separate it from the next block.

After iterating over all blocks, join all assembled block strings and return the complete SRT content as a single string. Do not write to disk inside this function — that is the responsibility of the caller.

### Step 3.4 — Implement generate_vtt in subtitle_engine.py

Add a second new function called `generate_vtt` to `subtitle_engine.py`, directly below `generate_srt`. This function accepts the same argument as `generate_srt` — a list of subtitle block dictionaries with text, start time, and end time.

The VTT format differs from SRT in two ways:

First, the file must begin with the header line `WEBVTT` followed by a blank line before any subtitle blocks.

Second, the timecode separator uses a period for milliseconds instead of a comma — the format is `HH:MM:SS.mmm --> HH:MM:SS.mmm`.

VTT blocks do not require an index number, though including one does not break the format. For simplicity and for compatibility with tools that expect consistently formatted VTT files, include an optional cue identifier (the block number) above each timecode line.

Assemble the full file content: start with `WEBVTT\n\n`, then append each formatted cue block separated by blank lines. Return the complete string.

### Step 3.5 — Build the Full-Video Subtitle Timeline in video_renderer.py

Open `backend/core_engine/video_renderer.py` and locate the `render_project` function. Inside the function, identify where subtitle timing is currently computed for each segment. The timing for each segment is computed by calling `calculate_subtitle_timing` with the segment's subtitle chunks and audio duration.

Currently, this timing data is consumed immediately by the compositor for burned-in rendering and is not retained after that step. To support SRT/VTT export, the timing data needs to be accumulated into a running timeline that tracks the absolute video time position of each subtitle block across all segments.

As each segment's subtitle chunks are computed, convert their relative (per-segment) timestamps into absolute video timestamps by adding the cumulative duration of all previously processed segments. Collect each adjusted block — containing text, absolute start time, and absolute end time — into a master list that represents the complete subtitle timeline for the video.

This accumulation step should happen in the same loop that already processes segments for rendering, without requiring a second pass over the data.

### Step 3.6 — Write the Subtitle Files After Rendering

Still in `video_renderer.py`, in the `render_project` function, locate the section of code that runs after `fast_render_segments()` has completed and the video file has been written. This is where the SRT and VTT output should be generated.

Load the `export_srt` and `export_vtt` flags from the current project object. If `export_srt` is `True`, call `generate_srt` with the accumulated subtitle timeline built in Step 3.5. Write the returned string content to a file named `subtitles.srt` in the project's media directory (`backend/media/projects/{project_id}/subtitles.srt`). Create the directory if it does not already exist.

If `export_vtt` is `True`, call `generate_vtt` with the same timeline data and write the result to `subtitles.vtt` in the same directory.

After writing each file, construct a relative or absolute URL path to the file. Store the SRT path under a key such as `srt_file_url` and the VTT path under `vtt_file_url` in the render result dictionary. If a file was not exported, store `None` under its key.

### Step 3.7 — Verify Timecode Arithmetic

The most error-prone part of this feature is the timecode calculation. Before writing any output, manually trace through a simple example with a two-segment project:

Segment 1: 4 seconds of audio, 2 subtitle chunks — first chunk from 0.0 to 2.0 seconds, second chunk from 2.0 to 4.0 seconds.
Segment 2: 3 seconds of audio, 1 subtitle chunk — chunk runs from 0.0 to 3.0 seconds relative to segment start.

After accumulation, the expected absolute timecodes for segment 2's chunk should be 4.0 to 7.0 seconds (shifted by segment 1's total duration).

Verify that the `generate_srt` output for this example would contain correct timecodes — segment 1's second chunk ending at `00:00:04,000` and segment 2's chunk starting at `00:00:04,000`. The SRT format requires exact millisecond precision and any off-by-one in conversion from seconds to milliseconds will produce subtitles that are visibly misaligned from the audio.

### Step 3.8 — Write Tests

Add test cases to `backend/core_engine/tests/` (or the appropriate test file). The tests should cover:

- `generate_srt` correctly formats a single subtitle block with the comma millisecond separator.
- `generate_srt` produces correctly numbered sequential blocks when given multiple blocks.
- `generate_vtt` starts with the `WEBVTT` header line.
- `generate_vtt` correctly formats timecodes with the period millisecond separator.
- The cumulative timestamp offset in `render_project` is computed correctly for a multi-segment project.
- When `export_srt=False`, no SRT file is created on disk.
- When `export_srt=True`, an SRT file is created at the expected path after a render.
- The render result dictionary contains `srt_file_url` and `vtt_file_url` keys — set to a path or `None` based on the export flags.

---

## 4. Expected Outcome

1. The `Project` model has two new boolean fields — `export_srt` and `export_vtt` — visible and editable through the REST API.
2. When `export_srt` is enabled on a project and a render completes, a valid `subtitles.srt` file is written to `backend/media/projects/{id}/subtitles.srt`.
3. When `export_vtt` is enabled, a valid `subtitles.vtt` file is written to `backend/media/projects/{id}/subtitles.vtt`.
4. Both export flags can be enabled simultaneously, producing both file formats from the same render pass without any duplicate work.
5. The subtitle timecodes in the exported files accurately reflect the absolute position of each subtitle block in the final video, accounting for multi-segment composition.
6. The render result dictionary returned by `render_project` includes download URLs for any subtitle files that were generated.
7. Projects with both export flags set to `False` (the default) behave identically to the current system — no new files are written, no performance overhead.
8. The `generate_srt` and `generate_vtt` functions are pure string-generation utilities with no file system side effects, making them easy to test in isolation.
9. The SRT and VTT files pass format validation when imported into YouTube Studio, VLC, and a standard HTML5 video element respectively.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- `generate_srt` with one block: output contains exactly one numbered block, correct timecodes with comma separator, correct text.
- `generate_srt` with three blocks: blocks are numbered 1, 2, 3 in order, separated by blank lines.
- `generate_srt` timecode for a 62.5-second timestamp formats as `00:01:02,500`.
- `generate_vtt` output starts with `WEBVTT` on the first line followed by a blank line.
- `generate_vtt` uses a period as the millisecond separator (not a comma).
- `generate_vtt` with one block: timecodes are formatted correctly.
- Cumulative offset function: given segment durations of 5.0, 3.2, and 4.8 seconds, the third segment's subtitle starts are shifted by 8.2 seconds.
- A subtitle block starting at 0.0 and ending at 2.0 seconds in the second segment of a two-segment project where the first segment is 5.5 seconds long should have absolute start of 5.5 and absolute end of 7.5.

### 5.2 Integration / Manual Tests

- Create a project with two segments, enable `export_srt`, trigger a render, and confirm `subtitles.srt` exists in the media directory.
- Open the generated `subtitles.srt` in VLC and verify subtitles appear in sync with the video.
- Import the SRT file into YouTube Studio and confirm it is accepted without errors.
- Enable `export_vtt`, trigger a render, and verify `subtitles.vtt` exists in the media directory.
- Create a minimal HTML page with an HTML5 video element referencing the rendered `output.mp4` and the generated `subtitles.vtt` as a `<track>` element. Confirm subtitles appear correctly in the browser.
- Enable both flags simultaneously and confirm both files are generated in the same render, each with correct content.
- Disable both flags (defaults) on a project and confirm no subtitle files are created and the render result dictionary has `None` for both URL keys.
- Confirm the render result dict returned by the API includes `srt_file_url` and `vtt_file_url` fields when files were exported.

### 5.3 Regression Tests

- Render a project with both export flags disabled and confirm the `output.mp4` video is identical to pre-feature behavior (burned-in subtitles still work, no changes to frame rendering).
- Confirm that `fast_compositor.py` is not modified in any way and its behavior is unchanged.
- Confirm that `chunk_text` and `calculate_subtitle_timing` functions in `subtitle_engine.py` have unchanged signatures and produce the same output as before.
- Confirm the Django migration applies to an existing populated database without data loss.
- Run the full backend test suite and confirm no previously passing tests fail.

---

## 6. Notes for AI Agent

- The `generate_srt` and `generate_vtt` functions must be pure functions — they should accept data as arguments and return strings. They must not perform any file I/O, database queries, or logging. All file writing happens in `video_renderer.py` exclusively.
- The SRT timecode format uses a comma as the millisecond separator. `00:00:01,500` is correct. `00:00:01.500` is the VTT format and is wrong for SRT. Mixing these up is the single most common SRT/VTT implementation bug.
- When assembling the full-video subtitle timeline across multiple segments, the timing offset must be computed from the actual audio duration of each segment — not from a target duration or a segment metadata field. The actual audio duration is already available during rendering since audio generation precedes subtitle timing in the pipeline.
- Ensure the subtitle output directory (`media/projects/{id}/`) is created if it does not exist before writing either file. The video output code already handles a similar check for `output.mp4` — follow the same pattern.
- The SRT specification requires a blank line between every subtitle block. A blank line at the very end of the file (after the last block) is acceptable. Do not omit this trailing blank line as some parsers are strict about it.
- The VTT specification requires the `WEBVTT` header to be the very first bytes of the file. Do not add a BOM (byte order mark) or any whitespace before this header. Write the file with UTF-8 encoding without BOM.
- Do not modify `fast_compositor.py` as part of this feature. Burned-in subtitle rendering is completely separate from subtitle file export and must remain fully functional and unchanged.
- The timeline accumulation logic in `video_renderer.py` should be implemented incrementally within the existing segment-processing loop, not as a separate second pass. This avoids loading all segment data twice and keeps the render performance characteristics the same.
- At a later phase, the frontend will need to surface the subtitle export toggles in the project settings form and display download buttons for the generated files. This feature stops at the backend API layer. Do not create any frontend components as part of this feature.
- If `export_srt` or `export_vtt` flags are `True` but the render fails before the subtitle data is computed, ensure the partial subtitle files are not written. Only write the files if the render fully completes and the timeline data is complete.
- The test for timecode formatting should use exact float-to-millisecond conversion to catch floating-point rounding errors. For instance, 3599.999 seconds should format as `00:59:59,999` and not round up to `01:00:00,000`. Use integer math (multiply by 1000, then use integer division and modulo operations) rather than floating-point division to extract hours, minutes, seconds, and milliseconds cleanly.
