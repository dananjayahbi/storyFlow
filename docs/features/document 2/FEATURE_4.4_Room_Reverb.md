# Feature 4.4 — Room Reverb / Ambience

| Field | Value |
|---|---|
| **Feature ID** | 4.4 |
| **Title** | Room Reverb / Ambience |
| **Status** | 🟡 Planned |
| **Priority** | Low |
| **Complexity** | Low |
| **Estimated Effort** | 1 day |
| **Dependencies** | FFmpeg (already required by the project) |
| **Output Files (NEW)** | None (processes segment audio in-place via temp path) |
| **Files Modified** | `backend/core_engine/audio_utils.py`, `backend/core_engine/video_renderer.py`, `backend/api/models.py`, `backend/api/serializers.py` |

---

## 1. Document Overview

### 1.1 Problem Statement

Kokoro ONNX TTS output is entirely dry — it has no acoustic environment. While this is technically clean, it can sound artificial and robotic to listeners because human speech is always recorded in some kind of physical space. The complete absence of room acoustics is itself an audible artifact: it signals to listeners that they are hearing a machine-generated voice rather than a human narrator.

A subtle reverb or echo effect simulating the acoustics of a small room can dramatically improve the perceived naturalness of TTS narration. This does not need to be dramatic — even a very light room simulation (short pre-delay, fast decay) is enough to remove the "too clean" quality and give the voice a sense of physical presence.

### 1.2 Proposed Solution

Add an optional reverb step applied per segment to each TTS WAV file. The feature uses FFmpeg's `aecho` filter, which simulates room acoustics by adding a series of delayed, attenuated echoes to the signal. Three presets are provided corresponding to different room sizes:

- **room** — a small room (60 ms delay, 0.15 decay): subtle, just removes the artificial dryness; suitable for most video content
- **hall** — a medium concert hall (120 ms delay, 0.25 decay): noticeable warmth; good for documentary or narrative content
- **church** — a large reverberant space (250 ms delay, 0.35 decay): prominent reverb; suitable for cinematic or poetic content

Reverb is applied **last** in the per-segment processing chain — after de-essing (4.3) and compression (4.2) and before LUFS normalization (4.1). Applying reverb after compression prevents reverb tails from triggering the compressor's gain reduction on subsequent syllables.

### 1.3 Scope

| In Scope | Out of Scope |
|---|---|
| FFmpeg `aecho` filter with three fixed presets | Convolution reverb using impulse response files |
| `reverb_enabled` BooleanField on Project model | Per-segment reverb preset control |
| `reverb_preset` CharField with choices (room/hall/church) | User-defined reverb parameters via API |
| Per-segment application before concatenation | Reverb on background music |
| Defined processing order across all four audio features | Real-time reverb preview |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| `backend/core_engine/audio_utils.py` | Houses all audio utility functions | No reverb function present |
| `backend/core_engine/video_renderer.py` | Render pipeline; per-segment audio loop | No reverb step present |
| `backend/api/models.py` | Django ORM `Project` model | No reverb fields present |
| `backend/api/serializers.py` | DRF serializer for `Project` | Must expose `reverb_enabled` and `reverb_preset` |

---

## 2. Flow Diagram

```
render_project() begins
        │
        ▼
For each segment in project.segments:
        │
        ▼
  generate_audio() → seg_wav (peak-normalized)
        │
        ▼
[Feature 4.3] de_essing_enabled?
  YES → apply_de_essing() → seg_deessed.wav
        │
        ▼
[Feature 4.2] audio_compression_enabled?
  YES → apply_audio_compression() → seg_compressed.wav
        │
        ▼
┌──────────────────────────────────────────────────┐
│  reverb_enabled == True?                         │
│                                                  │
│  YES → apply_reverb(                             │
│            seg_wav_path,                         │
│            seg_reverb_wav_path,                  │
│            preset=project.reverb_preset          │
│        )                                         │
│        update path → seg_reverb.wav              │
│                                                  │
│  Preset lookup:                                  │
│    "room"   → aecho=0.8:0.88:60:0.15            │
│    "hall"   → aecho=0.8:0.88:120:0.25           │
│    "church" → aecho=0.8:0.88:250:0.35           │
│                                                  │
│  NO  → use current seg path unchanged            │
└──────────────────────────────────────────────────┘
        │
        ▼
Append final segment path to concatenation list
        │
        ▼
Concatenation → final_audio.wav
        │
        ▼
[Feature 4.1] loudness_normalization_enabled?
  YES → normalize_lufs() → final_audio_lufs.wav
        │
        ▼
Final FFmpeg video render → output.mp4
```

---

## 3. Step-by-Step Instructions

### Step 3.1 — Add `reverb_enabled` and `reverb_preset` to the Project Model

Open `backend/api/models.py`. Locate the `Project` model class. Add two new fields:

First, add a `BooleanField` named `reverb_enabled` with a default of `False`. Help text: "Apply room acoustic simulation (reverb) to TTS segments".

Second, add a `CharField` named `reverb_preset` with `max_length=10`, a default of `"room"`, and set `blank=True`. Define the choices directly as a list of tuples on the field: `("room", "Small Room")`, `("hall", "Concert Hall")`, `("church", "Large Church")`. Help text: "Reverb preset controlling the simulated room size and decay".

Place both fields near the other audio processing fields added by Features 4.1, 4.2, and 4.3.

### Step 3.2 — Create and Run the Migration

Run `python manage.py makemigrations api` followed by `python manage.py migrate`. This adds two new columns (`reverb_enabled` boolean and `reverb_preset` varchar) to the `api_project` table.

### Step 3.3 — Update the Project Serializer

Open `backend/api/serializers.py`. Add both `reverb_enabled` and `reverb_preset` to the `fields` list in the `ProjectSerializer`'s `Meta` class.

Optionally, add a `validate_reverb_preset` method that raises a `serializers.ValidationError` if the submitted value is not one of `"room"`, `"hall"`, or `"church"`. This provides a clean API error for invalid preset names rather than allowing a bad value to silently pass through to FFmpeg.

### Step 3.4 — Define the Reverb Preset Configuration in `audio_utils.py`

Open `backend/core_engine/audio_utils.py`. Before the `apply_reverb` function, define a module-level dictionary named `REVERB_PRESETS` (or similar constant name). This dictionary maps preset name strings to their `aecho` filter parameter strings:

- The key `"room"` maps to the string `"aecho=0.8:0.88:60:0.15"`.
- The key `"hall"` maps to the string `"aecho=0.8:0.88:120:0.25"`.
- The key `"church"` maps to the string `"aecho=0.8:0.88:250:0.35"`.

The `aecho` filter takes four values: in-gain (0.8 keeps the dry signal strong), out-gain (0.88 sets the echo level slightly below dry), delay in milliseconds, and decay factor (0.0–1.0 where higher means longer reverberation tail).

### Step 3.5 — Implement `apply_reverb()` in `audio_utils.py`

Add a new function `apply_reverb` below the preset dictionary. The function should accept three parameters: `input_wav_path` (string), `output_wav_path` (string), and `preset` (string, one of `"room"`, `"hall"`, `"church"`).

The function body should:

- Look up the `preset` key in the `REVERB_PRESETS` dictionary. If the preset key is not found, raise a `ValueError` with a message listing the valid preset names.
- Build an FFmpeg subprocess command reading `input_wav_path`, applying `-af` with the resolved `aecho` filter string from the dictionary, and writing PCM WAV output to `output_wav_path`.
- Raise a `RuntimeError` with a descriptive message if FFmpeg exits with a non-zero return code.
- Return `output_wav_path` on success.
- Include a docstring that explains the `aecho` filter parameter meaning (in-gain, out-gain, delay ms, decay) and lists the preset options.

### Step 3.6 — Wire Reverb into the Per-Segment Loop in `video_renderer.py`

Open `backend/core_engine/video_renderer.py`. In the per-segment audio generation loop, find the point where the current working segment WAV path is determined after all other per-segment processing steps (de-essing from 4.3, compression from 4.2) have been applied.

Add a conditional block immediately after the compression step and before the path is appended to the concatenation list:

- If `project.reverb_enabled` is `True`, build a reverb output path by appending `_reverb` to the segment WAV filename, call `apply_reverb(current_seg_path, reverb_path, project.reverb_preset)`, and update the working path variable to `reverb_path`.
- If `project.reverb_enabled` is `False`, leave the path unchanged.

Import `apply_reverb` at the top of `video_renderer.py` alongside the other imports from `audio_utils`.

### Step 3.7 — Document the Full Processing Order

The complete per-segment audio processing order for all four audio features is now established. Add a comment block near the top of the per-segment audio loop in `video_renderer.py` documenting the processing chain order, so future developers understand it is intentional:

Processing chain (per segment):
1. TTS generation and peak normalization — `tts_wrapper.py` → `generate_audio()`
2. De-essing — Feature 4.3 — `apply_de_essing()` — reduces sibilance before compression
3. Compression — Feature 4.2 — `apply_audio_compression()` — levels dynamic range before reverb
4. Reverb — Feature 4.4 — `apply_reverb()` — applies last so echo tails are not compressed
5. (After concat) LUFS normalization — Feature 4.1 — `normalize_lufs()` — final loudness target on full mix

---

## 4. Expected Outcome

1. When `reverb_enabled` is `False` (default), the render pipeline is entirely unchanged.
2. When `reverb_enabled` is `True` with `reverb_preset: "room"`, the narration audio has a subtle warmth — as if recorded in a small studio — without distracting reverberation or echo tails audible between words.
3. With `reverb_preset: "hall"`, a clear but tasteful sense of space is added to the narration.
4. With `reverb_preset: "church"`, a pronounced reverberant tail is audible — suitable for intentionally cinematic content.
5. Submitting an invalid `reverb_preset` value via the API returns a 400 validation error with a message naming the valid options.
6. Both `reverb_enabled` and `reverb_preset` are readable and writable via the Project REST API.
7. The five-step processing chain comment in `video_renderer.py` correctly documents the ordering of all four audio post-processing features.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] `apply_reverb()` raises `ValueError` when given an unrecognized preset name
- [ ] `apply_reverb()` calls FFmpeg with `aecho=0.8:0.88:60:0.15` when preset is `"room"`
- [ ] `apply_reverb()` calls FFmpeg with `aecho=0.8:0.88:120:0.25` when preset is `"hall"`
- [ ] `apply_reverb()` calls FFmpeg with `aecho=0.8:0.88:250:0.35` when preset is `"church"`
- [ ] `apply_reverb()` raises `RuntimeError` on non-zero FFmpeg exit code
- [ ] `ProjectSerializer` accepts `reverb_preset` values `"room"`, `"hall"`, and `"church"`
- [ ] `ProjectSerializer` rejects an invalid `reverb_preset` value with a validation error

### 5.2 Integration / Manual Tests

- [ ] Create a Project via the API with `reverb_enabled: true` and `reverb_preset: "room"`; confirm both fields are persisted in the database
- [ ] Run a full render with `reverb_preset: "room"`; listen to the output — confirm subtle warmth without audible echo between words
- [ ] Run a full render with `reverb_preset: "church"`; listen to confirm a prominent reverb tail is present
- [ ] Run a full render with `reverb_enabled: false`; confirm output is identical to pre-feature behavior
- [ ] Run a full render with all four audio features enabled simultaneously (4.1 + 4.2 + 4.3 + 4.4); confirm all features apply in the documented order and the output is free of artifacts
- [ ] Confirm that the `reverb_preset` field defaults to `"room"` for newly created Projects

### 5.3 Regression Tests

- [ ] All existing renders with `reverb_enabled: false` (default) are unchanged compared to pre-feature outputs
- [ ] Features 4.1, 4.2, and 4.3 continue to function independently when `reverb_enabled` is `False`
- [ ] Existing Project API test fixtures pass without modification — the new fields have defaults so old payloads remain valid
- [ ] The comment block in `video_renderer.py` accurately reflects the actual processing order in the code immediately below it

---

## 6. Notes for AI Agent

- The FFmpeg `aecho` filter signature is `aecho=in_gain:out_gain:delay:decay`. Multiple echoes can be specified by listing multiple delay:decay pairs separated by `|`, but the single-echo approach used here is sufficient and simpler. Do not add extra echo taps unless requested.
- `in_gain=0.8` means the original (dry) signal is attenuated to 80% before mixing. This is intentional — it prevents the combined dry+wet signal from clipping. Do not set `in_gain=1.0` without verifying that the mixed output does not clip.
- `out_gain=0.88` controls the level of the echo (wet) signal. The chosen presets keep the echo clearly behind the dry voice so that speech intelligibility is not compromised.
- The `aecho` filter is available in all common FFmpeg versions and does not require version detection like the `deesser` filter in Feature 4.3.
- The `REVERB_PRESETS` dictionary in `audio_utils.py` should be the single source of truth for all three preset parameter strings. Do not repeat the parameter strings anywhere else in the codebase.
- Processing order rationale: reverb is applied last among the per-segment effects (after de-essing and compression) because the reverb tail creates additional signal energy that would otherwise trigger the compressor's gain reduction on subsequent syllables, causing audible pumping. Reverb after compression avoids this entirely.
- LUFS normalization (Feature 4.1) runs on the final concatenated audio, after all per-segment effects including reverb. This ensures the loudness target is measured on the final mix rather than on individual segments (which would be invalidated by concatenation).
- Implementation order: models → migration → serializer → `REVERB_PRESETS` constant → `apply_reverb()` → video_renderer wiring → processing-order comment block.
