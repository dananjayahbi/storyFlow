# Task 03.01.05 — Voice ID Validation & Fallback

> **Sub-Phase:** 03.01 — TTS Engine Integration
> **Phase:** Phase 03 — The Voice
> **Complexity:** Low
> **Dependencies:** Task 03.01.01 (Model Loader)
> **Parent Document:** [SubPhase_03_01_Overview.md](./SubPhase_03_01_Overview.md)

---

## Objective

Implement voice ID validation with automatic fallback to the default voice (`"af_bella"`) for invalid or unknown IDs, and implement voice embedding lookup for preparing model input tensors.

---

## Instructions

### Step 1 — Define the valid voice ID list

Define a module-level constant `VALID_VOICE_IDS` containing all supported Kokoro-82M voices: `"af_bella"`, `"af_sarah"`, `"af_nicole"`, `"am_adam"`, `"am_michael"`, `"bf_emma"`, `"bm_george"`. Define `DEFAULT_VOICE_ID = "af_bella"`.

### Step 2 — Implement `validate_voice_id(voice_id) → str`

Accept a voice ID string. If it exists in `VALID_VOICE_IDS`, return it unchanged. If it is invalid, empty, or `None`, log a warning with the invalid value and return `DEFAULT_VOICE_ID`. This is a soft validation — it never raises an error.

### Step 3 — Implement `get_voice_embedding(voice_id) → numpy array`

Load or compute the voice embedding tensor for the given voice ID. The exact mechanism depends on the model: it may be a lookup table stored in a separate file, an index into an embedding matrix within the model, or embedded in the model itself. The implementer must inspect the model's expected input to determine the correct approach.

### Step 4 — Integrate with `generate_audio()`

Call `validate_voice_id()` at the start of `generate_audio()` before preparing input tensors. Pass the validated ID to `get_voice_embedding()` when constructing the inference input dict.

---

## Expected Output

```
backend/
└── core_engine/
    └── tts_wrapper.py          ← MODIFIED (voice validation added)
```

---

## Validation

- [ ] Valid voice IDs (`"af_bella"`, `"am_adam"`, etc.) pass through unchanged.
- [ ] Invalid voice ID falls back to `"af_bella"` with a logged warning.
- [ ] Empty string falls back to `"af_bella"`.
- [ ] `None` value is handled gracefully (falls back to default).
- [ ] TTS output uses the correct voice (audibly different for different IDs).

---

## Notes

- The voice ID list may need updating if the Kokoro model version changes.
- The validation is intentionally soft — TTS should never fail solely because of a bad voice ID.
- The `GlobalSettings.default_voice_id` field defaults to `"af_bella"`, but a user or migration could set it to an invalid value — the fallback handles that.
- Place `VALID_VOICE_IDS` and `DEFAULT_VOICE_ID` in `tts_wrapper.py` or `model_loader.py` — whichever module is more appropriate for the voice embedding lookup mechanism.

---

> **Parent:** [SubPhase_03_01_Overview.md](./SubPhase_03_01_Overview.md) (Layer 2)
> **Phase:** [Phase_03_Overview.md](../Phase_03_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_03_01_04_Kokoro_Tokenization_Logic.md](./Task_03_01_04_Kokoro_Tokenization_Logic.md)
> **Next Task:** [Task_03_01_06_Audio_Normalization_Pipeline.md](./Task_03_01_06_Audio_Normalization_Pipeline.md)
