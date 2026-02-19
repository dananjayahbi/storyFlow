# Task 03.01.09 — Update requirements.txt

> **Sub-Phase:** 03.01 — TTS Engine Integration
> **Phase:** Phase 03 — The Voice
> **Complexity:** Low
> **Dependencies:** None
> **Parent Document:** [SubPhase_03_01_Overview.md](./SubPhase_03_01_Overview.md)

---

## Objective

Add the three new Python dependencies required for TTS functionality — `onnxruntime`, `soundfile`, and `numpy` — to the backend's `requirements.txt` file.

---

## Instructions

### Step 1 — Append `onnxruntime>=1.17.0`

Add `onnxruntime` with a minimum version of `1.17.0`. Use a `>=` constraint rather than an exact pin to allow compatible updates. Note that `onnxruntime` and `onnxruntime-gpu` are mutually exclusive packages — only one may be installed at a time. Add a comment above the entry explaining this mutual exclusivity so future developers know to swap the package name if they have a CUDA-capable GPU.

### Step 2 — Append `soundfile>=0.12.1`

Add `soundfile` with a minimum version of `0.12.1`. This library provides the WAV read/write functionality. Note that `soundfile` depends on `libsndfile`, which is bundled in the pip package on Windows and macOS but may need a system-level install (`apt install libsndfile1`) on Linux. Add a brief comment noting this.

### Step 3 — Append `numpy>=1.26.0`

Add `numpy` with a minimum version of `1.26.0`. NumPy is used for audio array manipulation throughout the TTS pipeline. It may already be present as a transitive dependency of `onnxruntime`, but listing it explicitly ensures the version floor is enforced and makes the dependency visible.

### Step 4 — Preserve existing entries

Do not reorder, remove, or modify any existing entries in `requirements.txt`. Append the new entries at the end, optionally under a comment header like "TTS / Audio" to group them logically.

---

## Expected Output

```
backend/
└── requirements.txt            ← MODIFIED (3 packages appended)
```

---

## Validation

- [ ] `onnxruntime>=1.17.0` is present in `requirements.txt`.
- [ ] `soundfile>=0.12.1` is present in `requirements.txt`.
- [ ] `numpy>=1.26.0` is present in `requirements.txt`.
- [ ] All three use `>=` constraints, not exact pins.
- [ ] Existing entries are unchanged.
- [ ] `pip install -r requirements.txt` completes without conflicts.

---

## Notes

- This task is listed first in the execution order because other tasks depend on these packages being installed. The file edit itself is trivial, but it gates the rest of the sub-phase.
- If a developer already has `onnxruntime-gpu` installed, `pip install onnxruntime` will conflict. The comment in the file should make this clear.
- `numpy` is almost certainly already installed (Django and Pillow pull it in), but an explicit entry ensures the minimum version is met.

---

> **Parent:** [SubPhase_03_01_Overview.md](./SubPhase_03_01_Overview.md) (Layer 2)
> **Phase:** [Phase_03_Overview.md](../Phase_03_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_03_01_08_Model_Missing_Graceful_Degrade.md](./Task_03_01_08_Model_Missing_Graceful_Degrade.md)
> **Next Task:** [Task_03_01_10_Write_TTS_Unit_Tests.md](./Task_03_01_10_Write_TTS_Unit_Tests.md)
