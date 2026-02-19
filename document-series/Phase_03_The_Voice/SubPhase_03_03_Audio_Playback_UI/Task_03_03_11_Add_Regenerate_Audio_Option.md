# Task 03.03.11 — Add Regenerate Audio Option

> **Sub-Phase:** 03.03 — Audio Playback UI
> **Phase:** Phase 03 — The Voice
> **Complexity:** Low
> **Dependencies:** Task 03.03.05 (SegmentCard Audio Section), Task 03.03.08 (Zustand Audio State)
> **Parent Document:** [SubPhase_03_03_Overview.md](./SubPhase_03_03_Overview.md)

---

## Objective

Add a "Regenerate Audio" option to the SegmentCard's existing dropdown menu, allowing users to re-generate audio for a segment that already has an audio file.

---

## Instructions

### Step 1 — Locate the SegmentCard dropdown menu

Open `frontend/components/SegmentCard.tsx` and find the existing dropdown menu (added in Phase 02) that contains segment actions such as delete and lock/unlock.

### Step 2 — Add the "Regenerate Audio" menu item

Add a new menu item labeled "Regenerate Audio" with a refresh icon (Lucide `RefreshCw`). Position it logically among the existing actions — after the lock/unlock action is a natural placement.

### Step 3 — Conditionally display the option

Only show the "Regenerate Audio" option when the segment already has an `audio_file`. If no audio has been generated yet, the option should not appear in the menu — the user should use the GenerateAudioButton instead.

### Step 4 — Disable when locked

If the segment is locked, the "Regenerate Audio" option should be disabled (grayed out) with a tooltip or visual cue indicating that the segment must be unlocked first.

### Step 5 — Wire to the generateAudio action

On click, call the Zustand store's `generateAudio(segmentId)` action — the same action used by the GenerateAudioButton. This triggers the standard flow: set status to generating → call API → poll → update. The AudioPlayer disappears during generation (replaced by GenerateAudioButton in generating state) and reappears with the new audio file on completion.

---

## Expected Output

```
frontend/
└── components/
    └── SegmentCard.tsx ← MODIFIED
```

---

## Validation

- [ ] "Regenerate Audio" option appears in the dropdown when audio_file exists.
- [ ] Option does NOT appear when no audio has been generated.
- [ ] Option is disabled (grayed out) when segment is locked.
- [ ] Clicking triggers the `generateAudio(segmentId)` Zustand action.
- [ ] AudioPlayer disappears during regeneration, GenerateAudioButton appears with spinner.
- [ ] New audio file loads in AudioPlayer after regeneration completes.
- [ ] Cache-busted URL ensures the browser does not serve stale audio.

---

## Notes

- Regeneration uses the exact same code path as initial generation. The backend TTS endpoint overwrites the existing audio file, and the frontend refreshes the segment data to get the updated `audio_file` URL.
- The cache-busting query parameter (appended by AudioPlayer as described in Task 03.03.02) ensures that the browser fetches the new audio file rather than serving the previous version from cache.
- This option is intentionally simple — no confirmation dialog is needed because audio regeneration is non-destructive to other data (text, images, order are all preserved).

---

> **Parent:** [SubPhase_03_03_Overview.md](./SubPhase_03_03_Overview.md) (Layer 2)
> **Phase:** [Phase_03_Overview.md](../Phase_03_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_03_03_10_Real_Time_Segment_Updates.md](./Task_03_03_10_Real_Time_Segment_Updates.md)
> **Next Task:** [Task_03_03_12_Text_Changed_Audio_Stale_Warning.md](./Task_03_03_12_Text_Changed_Audio_Stale_Warning.md)
