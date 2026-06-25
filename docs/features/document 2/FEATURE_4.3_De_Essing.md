# Feature 4.3 — De-Essing

| Field | Value |
|---|---|
| **Feature ID** | 4.3 |
| **Title** | De-Essing |
| **Status** | 🟡 Planned |
| **Priority** | Medium |
| **Complexity** | Low |
| **Estimated Effort** | 1 day |
| **Dependencies** | FFmpeg (already required by the project); FFmpeg 4.4+ for `deesser` filter (with EQ fallback for older versions) |
| **Output Files (NEW)** | None (processes segment audio in-place via temp path) |
| **Files Modified** | `backend/core_engine/audio_utils.py`, `backend/core_engine/video_renderer.py`, `backend/api/models.py`, `backend/api/serializers.py` |

---

## 1. Document Overview

### 1.1 Problem Statement

The Kokoro ONNX TTS engine generates realistic speech but can produce overly sharp, harsh sibilance on fricative phonemes — specifically the "s", "sh", "z", and "ch" sounds. This sibilance typically manifests as a concentration of energy in the 6–10 kHz frequency range. When heard through headphones or small phone speakers, these sounds stand out as an uncomfortable sharpness that draws attention and undermines the professional quality of the narration.

This is a well-known characteristic of synthetic TTS voices and is distinct from the overall loudness or dynamic range. Peak normalization and compression (Features 4.1 and 4.2) do not address frequency-specific harshness. A de-esser is required to specifically reduce this high-frequency energy on sibilant sounds.

### 1.2 Proposed Solution

Add a de-essing step applied per-segment to each TTS WAV file, executed before concatenation but after the existing peak normalization step in the pipeline.

Two implementation approaches are supported:

**Primary approach — FFmpeg `deesser` filter:** Available in FFmpeg 4.4 and later. This filter is purpose-built for de-essing and uses a frequency-selective sidechain detector. It directly identifies sibilant events and attenuates only those, leaving the rest of the audio untouched. Parameters: `i=0.5` (intensity, half-strength for subtlety) and `m=6dB` (maximum attenuation of 6 dB on detected sibilants).

**Fallback approach — Parametric EQ reduction:** For environments with FFmpeg older than 4.4, apply a simple parametric equalizer cut centered at 8 kHz using the `equalizer` filter. Parameters: center frequency 8000 Hz, bandwidth type octave, width 2 octaves, gain -6 dB. This is a static cut rather than a dynamic detector, so it is less precise but universally available.

The function should attempt to detect whether the `deesser` filter is available in the installed FFmpeg version and select the appropriate approach automatically.

### 1.3 Scope

| In Scope | Out of Scope |
|---|---|
| FFmpeg `deesser` filter (primary, FFmpeg 4.4+) | De-essing background music |
| FFmpeg `equalizer` filter fallback (-6 dB at 8 kHz) | Per-phoneme or word-level sibilance detection |
| `de_essing_enabled` BooleanField on Project model | User-configurable frequency, gain, or intensity |
| Per-segment application before concatenation | Broadband high-frequency limiting |
| Automatic FFmpeg version detection to select filter | Real-time de-essing preview in frontend |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| `backend/core_engine/audio_utils.py` | Houses all audio utility functions | No de-essing function; no frequency EQ function |
| `backend/core_engine/video_renderer.py` | Render pipeline; per-segment audio loop | No de-essing step present |
| `backend/api/models.py` | Django ORM `Project` model | No de-essing field present |
| `backend/api/serializers.py` | DRF serializer for `Project` | Must expose the new `de_essing_enabled` field |

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
  → peak normalization applied inside tts_wrapper.py
        │
        ▼
┌───────────────────────────────────────────────┐
│  de_essing_enabled == True?                   │
│                                               │
│  YES → apply_de_essing(                       │
│            seg_wav_path,                      │
│            seg_deessed_wav_path               │
│        )                                      │
│        update path → seg_deessed_wav          │
│                                               │
│        (auto-selects deesser filter or        │
│         EQ fallback based on FFmpeg version)  │
│                                               │
│  NO  → use seg_wav_path unchanged             │
└───────────────────────────────────────────────┘
        │
        ▼
[Optional: compression — Feature 4.2]
[Optional: LUFS normalization — Feature 4.1]
[Optional: reverb — Feature 4.4]
        │
        ▼
Concatenation → final_audio.wav
        │
        ▼
Final FFmpeg video render → output.mp4
```

---

## 3. Step-by-Step Instructions

### Step 3.1 — Add `de_essing_enabled` to the Project Model

Open `backend/api/models.py`. Locate the `Project` model class. Add a new `BooleanField` named `de_essing_enabled` with a default of `False`. Place it near the other audio processing fields. Set a help text string: "Apply de-essing to reduce harsh sibilance in TTS audio per segment".

### Step 3.2 — Create and Run the Migration

After saving the model change, run `python manage.py makemigrations api` and then `python manage.py migrate`. This adds a single new boolean column to the `api_project` table.

### Step 3.3 — Update the Project Serializer

Open `backend/api/serializers.py`. In the `ProjectSerializer`'s `Meta` class `fields` list, add `de_essing_enabled`. No additional validation is needed — it is a simple boolean toggle.

### Step 3.4 — Implement FFmpeg Version Detection Helper in `audio_utils.py`

Open `backend/core_engine/audio_utils.py`. Before implementing `apply_de_essing()`, add a small private helper function (name it `_ffmpeg_has_deesser` or similar) that determines whether the installed FFmpeg supports the `deesser` filter.

The helper should run `ffmpeg -filters` as a subprocess, capture the output, and search the output text for the string `deesser`. If found, return `True`. If not found or if the subprocess fails, return `False`. This allows the de-essing function to select the appropriate filter automatically without hard-coding a version number.

Cache the result in a module-level variable (e.g., `_DEESSER_AVAILABLE = None`) so that the detection subprocess runs only once per Python process lifetime, not once per segment.

### Step 3.5 — Implement `apply_de_essing()` in `audio_utils.py`

Add a new function `apply_de_essing` to `audio_utils.py` below the FFmpeg version helper. The function should accept two string parameters: `input_wav_path` and `output_wav_path`.

The function body should work as follows:

- Call the `_ffmpeg_has_deesser()` helper to determine which filter to use.
- **If `deesser` is available:** Build an FFmpeg subprocess command that reads the input WAV and applies `-af "deesser=i=0.5:m=6dB"`. The intensity value `i=0.5` applies de-essing at half strength to avoid over-processing — Kokoro TTS sibilance is moderate, not extreme. The `m=6dB` sets the maximum attenuation on detected sibilants to 6 dB.
- **If `deesser` is not available (fallback):** Build an FFmpeg subprocess command that reads the input WAV and applies `-af "equalizer=f=8000:width_type=o:width=2:g=-6"`. This applies a -6 dB parametric EQ cut centered at 8000 Hz (the core sibilance frequency for Kokoro TTS) with a 2-octave width (covering approximately 4000–16000 Hz at the -3 dB points), reducing broad high-frequency harshness.
- Both paths should write PCM WAV output to `output_wav_path`.
- Raise a `RuntimeError` with a descriptive message if FFmpeg exits with a non-zero return code.
- Return `output_wav_path` on success.
- Include a docstring that explains the two filter strategies and the rationale for the 8 kHz center frequency.

### Step 3.6 — Wire De-Essing into the Per-Segment Loop in `video_renderer.py`

Open `backend/core_engine/video_renderer.py`. In the per-segment audio generation loop within `render_project()`, find where each segment's WAV path is determined after calling `generate_audio()`.

Insert a conditional block immediately after the `generate_audio()` call:

- If `project.de_essing_enabled` is `True`, build a de-essed output path by appending `_deessed` to the segment WAV filename, call `apply_de_essing(seg_wav_path, deessed_path)`, and update the working path variable to `deessed_path`.
- If `project.de_essing_enabled` is `False`, leave the path unchanged.

De-essing must be the **first** processing step applied to each segment — it runs before compression (4.2), before LUFS normalization (4.1), and before reverb (4.4). This ordering matters because applying compression before de-essing would increase the relative energy of sibilants rather than reduce it.

Add the import for `apply_de_essing` at the top of `video_renderer.py` alongside other imports from `audio_utils`.

---

## 4. Expected Outcome

1. When `de_essing_enabled` is `False` (default), the render pipeline is entirely unchanged.
2. When `de_essing_enabled` is `True`, each segment WAV is processed through the de-esser before concatenation.
3. Listening to the output narration, sibilant "s" and "sh" sounds are noticeably less harsh and piercing, particularly on headphones — without the overall audio sounding dull or high frequencies being broadly removed.
4. The FFmpeg version detection helper runs once and caches its result, causing negligible performance overhead.
5. On systems with FFmpeg older than 4.4, the EQ fallback is automatically used and produces a useful (though less precise) result.
6. The `de_essing_enabled` field is readable and writable via the Project REST API endpoint.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] `_ffmpeg_has_deesser()` returns `True` when the subprocess output contains "deesser"
- [ ] `_ffmpeg_has_deesser()` returns `False` when the subprocess output does not contain "deesser"
- [ ] `_ffmpeg_has_deesser()` returns `False` when the FFmpeg subprocess raises an exception
- [ ] `apply_de_essing()` calls FFmpeg with the `deesser` filter string when `_ffmpeg_has_deesser()` returns `True` (mock detection helper)
- [ ] `apply_de_essing()` calls FFmpeg with the `equalizer` filter string when `_ffmpeg_has_deesser()` returns `False`
- [ ] `apply_de_essing()` raises `RuntimeError` on non-zero FFmpeg exit code
- [ ] `ProjectSerializer` serializes `de_essing_enabled` correctly as a boolean

### 5.2 Integration / Manual Tests

- [ ] Create a Project with `de_essing_enabled: true`; confirm the field is saved to the database
- [ ] Run a full render with de-essing enabled; inspect the output waveform's frequency spectrum in Audacity — verify reduced energy around 8 kHz on sibilant sounds compared to the non-de-essed version
- [ ] Run a full render with de-essing disabled; confirm output is identical to pre-feature behavior
- [ ] On a machine with FFmpeg 4.4+, confirm that the `deesser` filter path is taken (check render logs if logging is added)
- [ ] On a machine with FFmpeg older than 4.4 (or by mocking the detection), confirm the EQ fallback is used and no crash occurs

### 5.3 Regression Tests

- [ ] Renders with default `de_essing_enabled: false` are byte-for-byte identical to pre-feature renders
- [ ] The `_ffmpeg_has_deesser` result is cached — running two segments does not invoke the `ffmpeg -filters` subprocess twice
- [ ] Existing `normalize_audio()` behavior in `tts_wrapper.py` is unaffected
- [ ] All existing Project API tests pass without modification

---

## 6. Notes for AI Agent

- The `equalizer` filter in FFmpeg uses octave-based width when `width_type=o`. A `width=2` with `width_type=o` spans roughly 4000–16000 Hz at the -3 dB points around the 8 kHz center. This is intentionally broad for the fallback case. Do not change to `width_type=h` (Hz) without recalculating the width value.
- The `deesser` filter's `m` parameter specifies **maximum attenuation**. In some FFmpeg documentation, this is written as `m=0.5` (as a fraction) rather than `m=6dB`. Check the installed FFmpeg version's filter help output (`ffmpeg -h filter=deesser`) to confirm the expected parameter format before hardcoding it.
- Sibilance in Kokoro TTS concentrates most strongly around 7–9 kHz. The chosen center of 8 kHz is a reasonable midpoint. If testing reveals Kokoro's harshness is more concentrated at 6 kHz or 10 kHz on specific voices, the constant can be adjusted.
- The `_ffmpeg_has_deesser` helper uses a module-level cache. Initialize the cache variable as `None` at the top of `audio_utils.py` (e.g., `_DEESSER_AVAILABLE = None`). The first call to `_ffmpeg_has_deesser()` sets it to `True` or `False`; subsequent calls return the cached value immediately.
- Processing order across all audio features: de-essing (4.3 first) → compression (4.2) → LUFS normalization (4.1) → reverb (4.4 last). De-essing must come first so that downstream compressors do not amplify sibilant artifacts.
- Implementation order: models → migration → serializer → `_ffmpeg_has_deesser` helper → `apply_de_essing` → video_renderer wiring.
