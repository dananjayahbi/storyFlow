# Task 03.01.01 — Create Model Loader Singleton

> **Sub-Phase:** 03.01 — TTS Engine Integration
> **Phase:** Phase 03 — The Voice
> **Complexity:** High
> **Dependencies:** Task 03.01.09 (requirements.txt)
> **Parent Document:** [SubPhase_03_01_Overview.md](./SubPhase_03_01_Overview.md)

---

## Objective

Implement a thread-safe singleton class `KokoroModelLoader` in `backend/core_engine/model_loader.py` that lazily loads the Kokoro-82M ONNX model exactly once and reuses the ONNX Runtime `InferenceSession` for all subsequent inference calls.

---

## Instructions

### Step 1 — Create the module file

Create `backend/core_engine/model_loader.py` with a module-level logger.

### Step 2 — Define the `KokoroModelLoader` class

Implement a class with class-level attributes for the session (`_session = None`), a threading lock (`_lock = threading.Lock()`), and the resolved model path.

### Step 3 — Implement `get_session()` with double-checked locking

The `get_session()` class method must:
1. Check if `_session` is already loaded (fast path — no lock needed).
2. If not, acquire the lock.
3. Inside the lock, check again (`_session is None`) to handle the race condition where another thread loaded it between step 1 and acquiring the lock.
4. Call the private `_load_model()` method if still `None`.
5. Return `_session`.

### Step 4 — Implement `_load_model()`

This private class method:
1. Resolves the model file path using `_resolve_model_path()`.
2. Checks `os.path.exists()` — raises `FileNotFoundError` with actionable instructions if missing.
3. Creates an `onnxruntime.InferenceSession` with the model file.
4. Stores the session in `cls._session`.
5. Logs an INFO message confirming the model was loaded.

### Step 5 — Implement `_resolve_model_path()`

Construct the absolute path to `kokoro-v0_19.onnx` relative to the project root. Use `django.conf.settings.BASE_DIR` to navigate to the `/models/` directory at the project root (parent of the backend directory).

### Step 6 — Implement `is_model_available()`

A lightweight class method that returns `True`/`False` based solely on `os.path.exists()` — it does NOT load the model.

### Step 7 — Implement `get_model_info()`

A debugging utility that calls `get_session()`, then inspects and returns the model's input/output tensor metadata (name, shape, type for each input and output).

---

## Expected Output

```
backend/
└── core_engine/
    └── model_loader.py         ← NEW
```

---

## Validation

- [ ] `get_session()` returns an ONNX `InferenceSession` object.
- [ ] Subsequent calls return the same session object (singleton behavior).
- [ ] `is_model_available()` returns `True` when file exists, `False` when missing.
- [ ] `get_session()` raises `FileNotFoundError` with download instructions when model is missing.
- [ ] Thread safety: concurrent calls do not double-load or crash.
- [ ] `get_model_info()` returns input/output tensor metadata.
- [ ] Model loads lazily — NOT at Django startup.

---

## Notes

- The double-checked locking pattern is critical for thread safety: the outer check avoids lock contention on the hot path; the inner check prevents race conditions.
- Lazy initialization means the app starts fast and non-TTS features work even without the model file.
- ONNX Runtime automatically uses CUDA if `onnxruntime-gpu` is installed — no code change needed.
- The model is ~82M parameters — loading into RAM is fine for local use.

---

> **Parent:** [SubPhase_03_01_Overview.md](./SubPhase_03_01_Overview.md) (Layer 2)
> **Phase:** [Phase_03_Overview.md](../Phase_03_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** None (first task of SubPhase 03.01)
> **Next Task:** [Task_03_01_02_Create_Audio_Utils_Module.md](./Task_03_01_02_Create_Audio_Utils_Module.md)
