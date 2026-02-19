# Task 04.01.06 — Duration Synchronization

> **Sub-Phase:** 04.01 — Basic Video Assembly
> **Phase:** Phase 04 — The Vision
> **Complexity:** Medium
> **Dependencies:** Task 04.01.05 (AudioClip ImageClip Pairing)
> **Parent Document:** [SubPhase_04_01_Overview.md](./SubPhase_04_01_Overview.md)

---

## Objective

Ensure that each image clip displays for exactly the same duration as its corresponding audio clip, achieving perfect audio-visual synchronization throughout the entire video.

---

## Instructions

### Step 1 — Use audio clip duration as the authority

Within the per-segment loop, set the image clip's duration using the audio clip's actual `.duration` property — NOT the `segment.audio_duration` value stored in the database. The audio clip's duration is the authoritative value as read directly from the file by MoviePy/FFmpeg, eliminating any floating-point rounding differences that may exist in the database field.

### Step 2 — Cross-validate against database duration

Optionally log a warning if the absolute difference between `audio_clip.duration` and `segment.audio_duration` exceeds 0.1 seconds (100ms). A discrepancy larger than this suggests a data inconsistency that should be investigated but does not block rendering.

### Step 3 — Handle zero or negative duration

If `audio_clip.duration` is zero or negative, skip this segment with a logged warning rather than crashing the entire render. A zero-duration clip would cause MoviePy errors downstream. Log the segment ID and sequence index for debugging.

### Step 4 — Handle extremely long duration

If `audio_clip.duration` exceeds 60 seconds for a single segment, log a warning (this likely indicates a content issue — an unusually long narration) but proceed with rendering. This is informational only.

### Step 5 — Document the synchronization rule

The synchronization rule is absolute: **image clip duration = audio clip duration**. This ensures that when clips are concatenated, each segment's narration plays exactly while its image is displayed. This same timing is reused by Phase 05's subtitle overlay for frame-accurate text display.

---

## Expected Output

```
backend/
└── core_engine/
    └── video_renderer.py ← MODIFIED (duration sync within render loop)
```

---

## Validation

- [ ] Image clip duration is set from `audio_clip.duration`, not `segment.audio_duration`.
- [ ] Warning logged if database duration differs from file duration by > 0.1s.
- [ ] Zero/negative duration segments are skipped with a warning.
- [ ] Extremely long segments (> 60s) are logged as warnings but rendered.
- [ ] Final video total duration equals sum of all audio clip durations.
- [ ] No audio-visual desynchronization in the output video.

---

## Notes

- MoviePy's `set_duration()` creates a clip that holds the static image for the specified number of seconds. For static images (no Ken Burns), every frame within that duration is identical.
- The choice to use `audio_clip.duration` over `segment.audio_duration` is a deliberate design decision. The database value may have been rounded during storage, while the file-based value is exact to MoviePy's internal precision.
- When Ken Burns effects are added in SubPhase 04.02, the duration synchronization remains identical — the duration source is always the audio clip. The only change is that the image clip will have per-frame transformations instead of static display.

---

> **Parent:** [SubPhase_04_01_Overview.md](./SubPhase_04_01_Overview.md) (Layer 2)
> **Phase:** [Phase_04_Overview.md](../Phase_04_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_04_01_05_AudioClip_ImageClip_Pairing.md](./Task_04_01_05_AudioClip_ImageClip_Pairing.md)
> **Next Task:** [Task_04_01_07_Clip_Concatenation.md](./Task_04_01_07_Clip_Concatenation.md)
