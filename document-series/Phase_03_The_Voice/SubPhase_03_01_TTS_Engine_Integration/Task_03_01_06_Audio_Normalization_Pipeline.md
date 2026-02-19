# Task 03.01.06 — Audio Normalization Pipeline

> **Sub-Phase:** 03.01 — TTS Engine Integration
> **Phase:** Phase 03 — The Voice
> **Complexity:** Medium
> **Dependencies:** Task 03.01.02 (Audio Utils Module)
> **Parent Document:** [SubPhase_03_01_Overview.md](./SubPhase_03_01_Overview.md)

---

## Objective

Extend the audio normalization function in `audio_utils.py` with robust handling of edge cases and verified mathematical correctness, ensuring all TTS output is peak-normalized to −1.0 dB before writing to disk.

---

## Instructions

### Step 1 — Review and verify normalization math

The `normalize_audio()` function must scale the audio so the loudest sample reaches a target amplitude of approximately 0.8913 (which corresponds to −1.0 dB). The formula is: `target_amplitude = 10 ** (-1.0 / 20)`, yielding approximately 0.8913. The normalization factor is `target_amplitude / current_peak`, and every sample is multiplied by this factor.

### Step 2 — Handle the silence edge case

If the input array is all zeros (silence), there is no peak to normalize against — dividing by zero would produce `inf` or `nan`. In this case, return the array unchanged. Check by comparing the absolute-maximum against a near-zero threshold such as `1e-10`.

### Step 3 — Handle already-normalized audio

If the current peak already matches the target amplitude within a tight tolerance (e.g., `abs(current_peak - target_amplitude) < 1e-6`), return the array as-is to avoid unnecessary floating-point manipulation.

### Step 4 — Handle very quiet audio

Extremely quiet audio (peak far below the target) should normalize correctly via the standard formula. Verify that the function scales up without clipping — the math naturally handles this since the target is below 1.0.

### Step 5 — Handle clipping input

If the input contains samples whose absolute values exceed 1.0, the normalization should still work correctly. The formula naturally brings the peak down to 0.8913 regardless of whether the input exceeds 1.0.

### Step 6 — Preserve numpy dtype

The returned array must preserve the input's dtype. If the input is `float32`, the output must also be `float32`. Perform the multiplication in higher precision if needed, then cast back. This prevents subtle audio quality issues downstream.

### Step 7 — Do NOT modify the input in place

The function must return a new array. The caller's original array should remain unchanged. Use `array.copy()` or arithmetic that produces a new array rather than in-place operations like `*=`.

---

## Expected Output

```
backend/
└── core_engine/
    └── audio_utils.py          ← MODIFIED (normalization hardened)
```

---

## Validation

- [ ] Known input (e.g., array with peak 0.5) normalizes to peak ≈ 0.8913.
- [ ] All-zero (silence) input returns all zeros — no `inf` or `nan`.
- [ ] Already-normalized input (peak ≈ 0.8913) returns effectively identical array.
- [ ] Very quiet input (peak 0.001) scales up correctly.
- [ ] Clipping input (peak > 1.0) scales down to peak ≈ 0.8913.
- [ ] Output dtype matches input dtype (e.g., `float32` → `float32`).
- [ ] Original input array is not modified by the function.

---

## Notes

- The −1.0 dB target provides 1 dB of headroom, preventing DAC clipping on consumer devices and leaving room for minor variations during playback or transcoding.
- The normalization is "peak" normalization, not RMS normalization. Peak normalization is simpler, deterministic, and sufficient for speech audio.
- The `soundfile` library writes `float32` data natively, so keeping the dtype as `float32` avoids unnecessary conversions.
- This task is about hardening the function created in Task 03.01.02; it does not change the public API signature.

---

> **Parent:** [SubPhase_03_01_Overview.md](./SubPhase_03_01_Overview.md) (Layer 2)
> **Phase:** [Phase_03_Overview.md](../Phase_03_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_03_01_05_Voice_ID_Validation_Fallback.md](./Task_03_01_05_Voice_ID_Validation_Fallback.md)
> **Next Task:** [Task_03_01_07_WAV_File_Storage_Logic.md](./Task_03_01_07_WAV_File_Storage_Logic.md)
