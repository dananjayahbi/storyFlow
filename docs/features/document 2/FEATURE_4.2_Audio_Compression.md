# Feature 4.2 — Audio Compression / Limiting

| Field | Value |
|---|---|
| **Feature ID** | 4.2 |
| **Title** | Audio Compression / Limiting |
| **Status** | 🟡 Planned |
| **Priority** | Medium |
| **Complexity** | Low |
| **Estimated Effort** | 1 day |
| **Dependencies** | FFmpeg (already required by the project) |
| **Output Files (NEW)** | None (processes segment audio in-place via temp path) |
| **Files Modified** | `backend/core_engine/audio_utils.py`, `backend/core_engine/video_renderer.py`, `backend/api/models.py`, `backend/api/serializers.py` |

---

## 1. Document Overview

### 1.1 Problem Statement

Kokoro ONNX TTS output is generally consistent, but volume can vary noticeably across a single narration when the synthesized speech includes long pauses, changes in sentence energy, or transitions between different phoneme patterns. Some syllables or phrases may peak significantly higher than the average, causing uneven loudness throughout the narration. Without dynamic range compression, these variations carry through to the final video and can feel jarring to viewers.

The current pipeline applies only peak normalization via `normalize_audio()`, which ensures no clipping but does nothing to reduce the gap between the loudest and quietest parts of the audio. A compressor reduces this dynamic range, making quiet passages louder and loud passages softer, resulting in a more consistent, broadcast-quality narration.

### 1.2 Proposed Solution

Add a light audio compression step that is applied independently to each TTS segment WAV file immediately after it is generated, before concatenation. Using per-segment compression (rather than compressing the final mix) ensures that each segment is individually balanced before the clips are joined together.

The implementation uses FFmpeg's built-in `acompressor` audio filter. The default settings are chosen to be conservative and appropriate for TTS narration: a moderate ratio of 4:1, a threshold of -18 dB, a fast attack of 10 ms to catch transients, a moderate release of 100 ms to avoid pumping, and a +2 dB makeup gain to restore perceived loudness lost due to compression.

### 1.3 Scope

| In Scope | Out of Scope |
|---|---|
| FFmpeg `acompressor` filter applied per segment | Multiband compression |
| `audio_compression_enabled` toggle on Project model | Compression applied to background music |
| Fixed conservative default parameters for TTS narration | User-configurable compressor parameters via API |
| Per-segment application before concatenation | Loudness-aware makeup gain (covered by Feature 4.1) |
| New `apply_audio_compression()` function in `audio_utils.py` | Hardware or plugin-based compression |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| `backend/core_engine/audio_utils.py` | Audio utility functions; houses `normalize_audio()` | No compression function present |
| `backend/core_engine/video_renderer.py` | Render orchestration; calls `generate_audio()` per segment then concatenates | No compression step in the per-segment audio loop |
| `backend/api/models.py` | ORM model for `Project` | No compression field present |
| `backend/api/serializers.py` | DRF serializer for `Project` | Must expose new `audio_compression_enabled` field |

---

## 2. Flow Diagram

```
render_project() begins
        │
        ▼
For each segment in project.segments:
        │
        ▼
  generate_audio(text, voice_id, speed, seg_wav_path)
  → produces seg_001.wav, seg_002.wav, ...
        │
        ▼
┌─────────────────────────────────────────────┐
│  audio_compression_enabled == True?         │
│                                             │
│  YES → apply_audio_compression(             │
│            seg_wav_path,                    │
│            seg_compressed_wav_path          │
│        )                                    │
│        update path to seg_compressed_wav    │
│                                             │
│  NO  → use seg_wav_path unchanged           │
└─────────────────────────────────────────────┘
        │
        ▼
 [Optional: de-essing — Feature 4.3]
 [Optional: reverb    — Feature 4.4]
        │
        ▼
Concatenation of all segment WAVs
        │
        ▼
[Optional: LUFS normalization — Feature 4.1]
        │
        ▼
Final FFmpeg video render → output.mp4
```

---

## 3. Step-by-Step Instructions

### Step 3.1 — Add `audio_compression_enabled` to the Project Model

Open `backend/api/models.py`. Locate the `Project` model class. Add a new `BooleanField` named `audio_compression_enabled` with a default of `False`. Place it near other audio processing fields (or after `loudness_normalization_enabled` if Feature 4.1 has already been implemented). Set a help text string such as "Apply light dynamic range compression to each TTS segment before concatenation".

### Step 3.2 — Create and Run the Migration

After modifying the model, generate a migration for the `api` application using `python manage.py makemigrations api`, then apply it with `python manage.py migrate`. The migration will add a single boolean column to the `api_project` database table.

### Step 3.3 — Update the Project Serializer

Open `backend/api/serializers.py`. Find the serializer class that handles the `Project` model — this is the `ProjectSerializer` or equivalent. Add `audio_compression_enabled` to the `fields` list in the inner `Meta` class. No custom validation logic is required for this field since it is a simple boolean.

### Step 3.4 — Implement `apply_audio_compression()` in `audio_utils.py`

Open `backend/core_engine/audio_utils.py`. Add a new function called `apply_audio_compression` below the existing audio utility functions. The function should accept two string parameters: `input_wav_path` (path to the source WAV file for a single TTS segment) and `output_wav_path` (path to write the compressed result).

The function body should construct and execute an FFmpeg subprocess command that reads the input WAV and applies the `acompressor` audio filter with the following fixed parameters:

- `threshold=-18dB` — compression begins when the signal exceeds -18 dBFS, targeting the upper dynamic range of typical TTS output
- `ratio=4` — 4:1 compression ratio; for every 4 dB above threshold, only 1 dB passes through — moderate and transparent for speech
- `attack=10` — attack time of 10 ms; fast enough to catch transients without distorting consonants
- `release=100` — release time of 100 ms; prevents audible "pumping" between syllables
- `makeup=2dB` — 2 dB of makeup gain applied after compression to restore perceived loudness

The output format should be PCM WAV, matching the input format. The function should raise a `RuntimeError` with a descriptive message if the FFmpeg subprocess exits with a non-zero return code. On success, return the `output_wav_path` string.

Include a docstring explaining all five compressor parameters and stating that the settings are tuned for TTS narration, not music.

### Step 3.5 — Wire Compression into the Per-Segment Loop in `video_renderer.py`

Open `backend/core_engine/video_renderer.py`. Locate the section inside `render_project()` — or the private helper method it calls — where the per-segment audio loop runs. This is the loop that calls `generate_audio()` for each story segment and builds up the list of WAV file paths to be concatenated.

After each `generate_audio()` call, and before the resulting path is appended to the concatenation list, insert a conditional block:

- Check if `project.audio_compression_enabled` is `True`.
- If yes, build a compressed output path by appending `_compressed` to the segment WAV filename (keeping the `.wav` extension), then call `apply_audio_compression(seg_wav_path, compressed_path)`.
- Replace the path variable with the compressed output path so that the concatenation list contains the compressed version.
- If `audio_compression_enabled` is `False`, do nothing — the original segment path is used as before.

Ensure the import of `apply_audio_compression` from `audio_utils` is added at the top of `video_renderer.py`.

If Features 4.3 (de-essing) and/or 4.4 (reverb) are also implemented, compression should be applied after de-essing and before LUFS normalization — refer to the processing order defined in Feature 4.4.

---

## 4. Expected Outcome

1. When `audio_compression_enabled` is `False` (default), the render pipeline is unchanged — no new processing is applied to any segment audio.
2. When `audio_compression_enabled` is `True`, each segment WAV file is processed through the `acompressor` FFmpeg filter before concatenation.
3. The resulting narration audio in the final video has noticeably more consistent volume across segments — loud outbursts are tamed and quiet passages are brought up.
4. No clipping is introduced; the compressor's moderate ratio and conservative threshold preserve transient character.
5. The compressed segment WAV files are created in the project's temporary working directory alongside the original segment WAVs.
6. The `audio_compression_enabled` field is visible and settable via the REST API on the Project resource.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] `apply_audio_compression()` accepts valid input and output paths without raising exceptions (mock FFmpeg subprocess)
- [ ] `apply_audio_compression()` raises `RuntimeError` when FFmpeg returns a non-zero exit code
- [ ] `apply_audio_compression()` calls FFmpeg with the `acompressor` filter string containing all five expected parameters
- [ ] `ProjectSerializer` correctly serializes and deserializes `audio_compression_enabled` as a boolean
- [ ] `ProjectSerializer` accepts `audio_compression_enabled: false` and `audio_compression_enabled: true` without error

### 5.2 Integration / Manual Tests

- [ ] Create a Project with `audio_compression_enabled: true` via the API; confirm field is persisted in the database
- [ ] Run a full render with compression enabled; load the output MP4 audio in Audacity or similar and visually confirm the waveform has a reduced dynamic range (quieter peaks and louder troughs compared to the uncompressed version)
- [ ] Run a full render with compression disabled; confirm output is identical to pre-feature behavior
- [ ] Compare the waveforms of a single compressed segment WAV against its uncompressed counterpart; verify the compressed version is more uniform in amplitude
- [ ] Check that the final video duration is unchanged by the compression step

### 5.3 Regression Tests

- [ ] All Projects with default `audio_compression_enabled: false` render identically to before this feature was added
- [ ] `normalize_audio()` still executes in `tts_wrapper.py` independently of this compression step — peak normalization is not removed
- [ ] `apply_audio_compression()` does not write output to the same path as the input (no race condition or self-overwrite)
- [ ] Existing API test fixtures for the Project model still pass — the new field has a default value so old serialized payloads remain valid

---

## 6. Notes for AI Agent

- The FFmpeg `acompressor` filter parameter syntax uses the `=` and `:` delimiter format: `-af "acompressor=threshold=-18dB:ratio=4:attack=10:release=100:makeup=2dB"`. Ensure the entire filter string is passed as a single argument to the `-af` flag.
- `attack` and `release` values for the `acompressor` filter are specified in **milliseconds** when using the filter's default unit. Double-check FFmpeg documentation — the exact unit may be milliseconds or seconds depending on the FFmpeg version. If behavior is unexpected, try `attack=0.01:release=0.1` (seconds) as an alternative.
- This feature applies compression **per segment** rather than to the final mix. This is intentional — it ensures that each segment is individually balanced before joining. Do not move the compression step to after concatenation without revisiting the design.
- Processing order when multiple audio features are enabled: de-essing (4.3) → compression (4.2) → LUFS normalization (4.1) → reverb (4.4). See Feature 4.4 for full ordering rationale.
- The makeup gain of `2dB` is a hardcoded default. There is no need to expose this to users via the API unless a future "advanced audio" settings panel is added. Keep the function signature simple.
- Implementation order: models → migration → serializer → audio_utils → video_renderer. Test `apply_audio_compression()` with a real sample WAV before wiring into the render pipeline.
