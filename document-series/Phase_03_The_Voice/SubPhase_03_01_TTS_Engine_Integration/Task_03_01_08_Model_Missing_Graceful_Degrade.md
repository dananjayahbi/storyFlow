# Task 03.01.08 — Model-Missing Graceful Degradation

> **Sub-Phase:** 03.01 — TTS Engine Integration
> **Phase:** Phase 03 — The Voice
> **Complexity:** Medium
> **Dependencies:** Task 03.01.01 (Model Loader Singleton), Task 03.01.03 (TTS Wrapper)
> **Parent Document:** [SubPhase_03_01_Overview.md](./SubPhase_03_01_Overview.md)

---

## Objective

Ensure the entire application starts and operates normally even when the Kokoro ONNX model file is missing from the expected `models/` directory, providing clear user-facing messages about why TTS is unavailable and how to resolve the issue.

---

## Instructions

### Step 1 — Enhance `KokoroModelLoader` error handling

When `get_session()` is called and the model file (`models/kokoro-v0_19.onnx`) does not exist, raise a descriptive `FileNotFoundError`. The error message must include: the expected file path, the model file name, and a brief instruction telling the developer where to download the model and where to place it. This exception propagates up to the TTS wrapper.

### Step 2 — Catch and return error dict in `generate_audio()`

In `generate_audio()`, wrap the model session acquisition in a try/except block that catches `FileNotFoundError`. When caught, return the standard error dict format (with `"success": False` and an `"error"` string describing the missing model). Do not re-raise the exception — the function must never crash the calling code.

### Step 3 — Implement `is_model_available() → bool`

Add a lightweight method to `KokoroModelLoader` (or a module-level function) that checks whether the model file exists on disk without attempting to load it. This uses `os.path.exists()` or `pathlib.Path.exists()` on the expected path. This function allows callers (such as API views or the frontend status endpoint) to check model readiness without triggering a full load.

### Step 4 — Add optional Django startup warning

In the `core_engine` app's `apps.py` `ready()` method, optionally call `is_model_available()` and log a prominent warning (e.g., using `logging.warning`) if the model file is not found. This gives the developer immediate feedback in the console when starting the server. The warning must NOT raise an exception or prevent startup.

### Step 5 — Verify application startup without model

Confirm that `python manage.py runserver` starts successfully when the model file is absent. All endpoints (project CRUD, segment CRUD, image upload) must remain fully functional. Only TTS-specific calls should return error dicts.

---

## Expected Output

```
backend/
└── core_engine/
    ├── model_loader.py         ← MODIFIED (FileNotFoundError, is_model_available)
    ├── tts_wrapper.py          ← MODIFIED (catch FileNotFoundError in generate_audio)
    └── apps.py                 ← MODIFIED (optional startup warning)
```

---

## Validation

- [ ] `get_session()` raises `FileNotFoundError` with a helpful message when model is missing.
- [ ] `generate_audio()` returns `{"success": False, "error": "..."}` when model is missing — never raises.
- [ ] `is_model_available()` returns `False` when model file is absent and `True` when present.
- [ ] Django server starts successfully without the model file.
- [ ] Startup log shows a warning about the missing model (not an error or crash).
- [ ] All non-TTS endpoints remain fully functional when model is absent.

---

## Notes

- The model file is not committed to version control due to its size (~82M parameters). Developers must download it separately.
- The `is_model_available()` check is a file-existence check only — it does not validate the model's integrity or compatibility. A corrupt ONNX file would still return `True` but fail at load time, which `generate_audio()` handles via its error dict pattern.
- The startup warning should be visible but not alarming — the app is fully functional for all non-audio workflows (project management, segment editing, image handling).
- This graceful degradation pattern is critical for the development experience: a new contributor can clone the repo, install dependencies, and run the app immediately without needing the model file.

---

> **Parent:** [SubPhase_03_01_Overview.md](./SubPhase_03_01_Overview.md) (Layer 2)
> **Phase:** [Phase_03_Overview.md](../Phase_03_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_03_01_07_WAV_File_Storage_Logic.md](./Task_03_01_07_WAV_File_Storage_Logic.md)
> **Next Task:** [Task_03_01_09_Update_Requirements_Txt.md](./Task_03_01_09_Update_Requirements_Txt.md)
