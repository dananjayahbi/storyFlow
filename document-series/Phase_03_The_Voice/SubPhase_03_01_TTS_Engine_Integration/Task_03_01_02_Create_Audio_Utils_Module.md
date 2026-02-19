# Task 03.01.02 — Create Audio Utils Module

> **Sub-Phase:** 03.01 — TTS Engine Integration
> **Phase:** Phase 03 — The Voice
> **Complexity:** Medium
> **Dependencies:** Task 03.01.09 (requirements.txt)
> **Parent Document:** [SubPhase_03_01_Overview.md](./SubPhase_03_01_Overview.md)

---

## Objective

Create a standalone utility module `backend/core_engine/audio_utils.py` with pure functions for peak normalization, WAV file saving, duration calculation, and audio file validation.

---

## Instructions

### Step 1 — Create the module file

Create `backend/core_engine/audio_utils.py`. Import `numpy`, `soundfile`, `os`, and `logging`.

### Step 2 — Implement `normalize_audio(audio_array, target_db=-1.0)`

Peak-normalize a 1D float32 numpy array to the target dB level.

- Calculate the peak absolute value of the array.
- If peak is zero (silence), return the array unchanged to avoid division by zero.
- Compute the target amplitude: `10 ** (target_db / 20)` — for -1.0 dB this equals approximately 0.8913.
- Scale the array: `audio * (target_amplitude / peak)`.
- Return a **new** array — do NOT modify the input in-place.

### Step 3 — Implement `get_audio_duration(file_path)`

Return the duration of a `.wav` file in seconds as a float.

- Check `os.path.exists()` — raise `FileNotFoundError` if missing.
- Use `soundfile.info(file_path).duration` to read the duration.

### Step 4 — Implement `validate_audio_file(file_path)`

Check if a `.wav` file is valid and readable. Return `True` if `soundfile.info()` succeeds and reports a positive duration and sample rate. Return `False` for any exception, missing file, or corrupt data.

### Step 5 — Implement `save_audio_wav(audio_array, output_path, sample_rate)`

Save a float32 audio array as a `.wav` file.

- Create parent directories with `os.makedirs(os.path.dirname(output_path), exist_ok=True)`.
- Write the file using `soundfile.write(output_path, audio_array, sample_rate)`.
- Return the `output_path` for chaining convenience.

---

## Expected Output

```
backend/
└── core_engine/
    └── audio_utils.py          ← NEW
```

---

## Validation

- [ ] `normalize_audio()` scales peak to -1.0 dB (≈ 0.8913 amplitude).
- [ ] `normalize_audio()` handles silence (all-zero array) without error.
- [ ] `normalize_audio()` returns a new array (does not modify input).
- [ ] `get_audio_duration()` returns correct duration for a known `.wav` file.
- [ ] `get_audio_duration()` raises `FileNotFoundError` for missing files.
- [ ] `validate_audio_file()` returns `True` for valid `.wav`, `False` for corrupt/missing.
- [ ] `save_audio_wav()` creates the file and auto-creates parent directories.

---

## Notes

- All functions are pure utilities — no Django imports, no model access, no side effects beyond file I/O.
- Functions should be testable in isolation using synthetic numpy arrays.
- Use `soundfile` (not Python's built-in `wave` module) for float32 support and a simpler API.
- The normalization target of -1.0 dB provides headroom below 0 dBFS, preventing clipping.

---

> **Parent:** [SubPhase_03_01_Overview.md](./SubPhase_03_01_Overview.md) (Layer 2)
> **Phase:** [Phase_03_Overview.md](../Phase_03_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_03_01_01_Create_Model_Loader_Singleton.md](./Task_03_01_01_Create_Model_Loader_Singleton.md)
> **Next Task:** [Task_03_01_03_Implement_TTS_Wrapper.md](./Task_03_01_03_Implement_TTS_Wrapper.md)
