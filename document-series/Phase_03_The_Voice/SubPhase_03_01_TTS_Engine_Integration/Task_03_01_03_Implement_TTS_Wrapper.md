# Task 03.01.03 — Implement TTS Wrapper

> **Sub-Phase:** 03.01 — TTS Engine Integration
> **Phase:** Phase 03 — The Voice
> **Complexity:** High
> **Dependencies:** Task 03.01.01 (Model Loader), Task 03.01.02 (Audio Utils)
> **Parent Document:** [SubPhase_03_01_Overview.md](./SubPhase_03_01_Overview.md)

---

## Objective

Replace the Phase 01 stub in `backend/core_engine/tts_wrapper.py` with a fully functional TTS inference wrapper. The main function `generate_audio()` accepts text, voice ID, speed, and output path, runs the full pipeline (model load → tokenize → infer → normalize → save → measure duration), and returns a structured result dict.

---

## Instructions

### Step 1 — Replace the stub file

Overwrite the entire content of `backend/core_engine/tts_wrapper.py`. Import the model loader, audio utils, numpy, soundfile, os, and logging.

### Step 2 — Implement `generate_audio(text, voice_id, speed, output_path) → dict`

This is the main function — a pure function that accepts all parameters explicitly and returns a result dict.

**Parameters:**
- `text` (str): Text to convert to speech.
- `voice_id` (str, default `"af_bella"`): Kokoro voice ID.
- `speed` (float, default `1.0`): Speech speed multiplier.
- `output_path` (str): Absolute path where the `.wav` file will be saved.

**Success return:**
A dict with keys: `audio_path` (str), `duration` (float in seconds), `sample_rate` (int), and `success` (True).

**Error return:**
A dict with keys: `success` (False) and `error` (str with a human-readable message).

### Step 3 — Implement the pipeline flow inside `generate_audio()`

1. **Validate inputs:** Return error dict if `text` is empty/whitespace-only or `output_path` is None.
2. **Validate voice ID:** Call `validate_voice_id()` (Task 03.01.05) — falls back to default if invalid.
3. **Clamp speed:** Constrain to range 0.5–2.0.
4. **Get ONNX session:** Call `KokoroModelLoader.get_session()`. Catch `FileNotFoundError` and return error dict.
5. **Tokenize text:** Convert text to model input format (Task 03.01.04).
6. **Prepare input tensors:** Build the input dict with correct tensor names and shapes matching the model's expected format.
7. **Run inference:** Call `session.run(None, input_dict)` to get the raw float32 audio array.
8. **Normalize:** Call `normalize_audio(audio_array)` to peak-normalize to -1.0 dB.
9. **Save:** Call `save_audio_wav(audio_array, output_path, sample_rate)`.
10. **Calculate duration:** Call `get_audio_duration(output_path)`.
11. **Return success dict.**

### Step 4 — Wrap in try/except

The entire pipeline must be wrapped in a try/except block. Catch `FileNotFoundError` separately (for model-missing) and a generic `Exception` for any other failure. Always return a dict — never raise exceptions to callers. Log at ERROR level on failure with `exc_info=True`.

### Step 5 — Verify

Run `python manage.py test` to ensure nothing breaks. The wrapper is callable but full integration tests are in Task 03.01.10.

---

## Expected Output

```
backend/
└── core_engine/
    └── tts_wrapper.py          ← REPLACED (Phase 01 stub → full implementation)
```

---

## Validation

- [ ] `generate_audio()` returns a success dict with `audio_path`, `duration`, `sample_rate`, `success: True`.
- [ ] The generated `.wav` file exists at the specified path.
- [ ] Empty text returns `{"success": False, "error": "..."}`.
- [ ] Missing model returns `{"success": False, "error": "..."}` (no crash).
- [ ] Speed is clamped to 0.5–2.0.
- [ ] Re-generation overwrites the existing file cleanly.
- [ ] The function never raises exceptions — always returns a dict.

---

## Notes

- The wrapper is a **pure function** — it does NOT read from the database or update Django models. Database updates happen in SubPhase 03.02's API layer.
- The result dict pattern is intentional: callers check `result["success"]` instead of try/except. Error messages are structured and ready for API responses.
- The `output_path` must be provided by the caller — the wrapper does not construct paths autonomously. Use `construct_audio_path()` (Task 03.01.07) from the calling code.
- Log extensively: INFO for successful generations, ERROR for failures.
- The exact input tensor names and shapes depend on the Kokoro model version — they must be discovered at runtime using `session.get_inputs()`.

---

> **Parent:** [SubPhase_03_01_Overview.md](./SubPhase_03_01_Overview.md) (Layer 2)
> **Phase:** [Phase_03_Overview.md](../Phase_03_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_03_01_02_Create_Audio_Utils_Module.md](./Task_03_01_02_Create_Audio_Utils_Module.md)
> **Next Task:** [Task_03_01_04_Kokoro_Tokenization_Logic.md](./Task_03_01_04_Kokoro_Tokenization_Logic.md)
