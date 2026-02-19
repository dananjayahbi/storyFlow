# Task 03.03.12 — Text Changed Audio Stale Warning

> **Sub-Phase:** 03.03 — Audio Playback UI
> **Phase:** Phase 03 — The Voice
> **Complexity:** Low
> **Dependencies:** Task 03.03.05 (SegmentCard Audio Section)
> **Parent Document:** [SubPhase_03_03_Overview.md](./SubPhase_03_03_Overview.md)

---

## Objective

Display a subtle amber warning in the SegmentCard when the segment's text has been edited after audio was generated, alerting the user that the audio may no longer match the text.

---

## Instructions

### Step 1 — Choose a staleness detection approach

Implement a session-only staleness mechanism using the Zustand store. Add a `staleAudioSegments` Set (of segment IDs) to the store. This Set tracks which segments have had their text edited after audio was generated. The Set is not persisted — it resets on page reload, which is acceptable because the warning is a convenience indicator, not a data integrity mechanism.

### Step 2 — Mark audio as stale on text edit

In the text editing logic within `SegmentCard.tsx` (or in the Zustand store's text update action), check if the segment has an existing `audio_file`. If it does and the text has changed, add the segment's ID to the `staleAudioSegments` Set.

### Step 3 — Render the stale warning

In the audio section of the SegmentCard, check if the segment's ID is in `staleAudioSegments`. If so, render a small amber warning bar below the AudioPlayer with the text: "Text changed — audio may be out of sync." Include a Lucide `AlertTriangle` icon for visual emphasis.

### Step 4 — Add a "Regenerate" shortcut link

Within the warning bar, include a clickable "Regenerate" text link that triggers the same `generateAudio(segmentId)` action. This provides a one-click path from the warning to resolving the staleness.

### Step 5 — Clear staleness on regeneration

When audio is regenerated for a segment (either via the Regenerate Audio menu item, the inline Regenerate link, or the GenerateAudioButton), remove the segment's ID from the `staleAudioSegments` Set. This clears the warning.

### Step 6 — Ensure session-only behavior

Confirm that the `staleAudioSegments` Set is initialized as empty on store creation and is not persisted to any storage. On page reload, all staleness indicators reset. This is intentional — the server does not track text-audio sync status.

---

## Expected Output

```
frontend/
├── lib/
│   └── stores.ts ← MODIFIED (staleAudioSegments Set + actions)
└── components/
    └── SegmentCard.tsx ← MODIFIED (stale warning rendering)
```

---

## Validation

- [ ] Editing text on a segment with existing audio adds the segment to staleAudioSegments.
- [ ] Amber warning bar appears below AudioPlayer for stale segments.
- [ ] Warning text reads "Text changed — audio may be out of sync."
- [ ] "Regenerate" link in the warning triggers `generateAudio(segmentId)`.
- [ ] Warning clears after successful audio regeneration.
- [ ] Warning does not appear for segments without audio.
- [ ] `staleAudioSegments` resets to empty on page reload.
- [ ] No TypeScript errors.

---

## Notes

- This is a UX convenience feature, not a data integrity mechanism. The audio file on disk may or may not match the current text — the warning simply reminds the user to regenerate if they care about sync.
- An alternative approach would be to compare timestamps (text `updated_at` vs. audio file creation time) on the server side. However, this adds backend complexity that is not warranted for Phase 03. The session-only approach is simpler and sufficient.
- The stale warning should not appear during active generation. If the segment is currently generating, the GenerateAudioButton's spinner is a sufficient visual indicator.

---

> **Parent:** [SubPhase_03_03_Overview.md](./SubPhase_03_03_Overview.md) (Layer 2)
> **Phase:** [Phase_03_Overview.md](../Phase_03_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_03_03_11_Add_Regenerate_Audio_Option.md](./Task_03_03_11_Add_Regenerate_Audio_Option.md)
> **Next Task:** [Task_03_03_13_Responsive_Audio_Layout.md](./Task_03_03_13_Responsive_Audio_Layout.md)
