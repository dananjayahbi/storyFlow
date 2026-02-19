# Task 03.03.04 — Build AudioStatusBadge Component

> **Sub-Phase:** 03.03 — Audio Playback UI
> **Phase:** Phase 03 — The Voice
> **Complexity:** Low
> **Dependencies:** None
> **Parent Document:** [SubPhase_03_03_Overview.md](./SubPhase_03_03_Overview.md)

---

## Objective

Build a small visual badge displayed in the SegmentCard header that communicates the audio state of a segment at a glance.

---

## Instructions

### Step 1 — Create the component file

Create `frontend/components/AudioStatusBadge.tsx`. Define a props interface with `audioFile` (string or null), `audioDuration` (number or null), and `generationStatus` (AudioGenerationState from the Zustand store). Add optional `className` for styling overrides.

### Step 2 — Implement the "No Audio" variant

When `audioFile` is null and status is idle, render a gray badge with a muted speaker icon (🔇 or Lucide `VolumeX`) and the text "No Audio."

### Step 3 — Implement the "Generating" variant

When `generationStatus` indicates generating, render an amber badge with an hourglass icon (⏳ or Lucide `Loader2`) and the text "Generating." Use a subtle pulse or spin animation to convey activity.

### Step 4 — Implement the "Ready" variant

When `audioFile` exists and status is completed or idle, render a green badge with a check icon (✅ or Lucide `Check`) and the formatted duration (e.g., "0:42"). Use the same `formatTime` utility from AudioPlayer or a shared utility.

### Step 5 — Implement the "Failed" variant

When `generationStatus` indicates failed, render a red badge with an error icon (❌ or Lucide `XCircle`) and the text "Failed." Optionally include a tooltip showing the error message from the generation status object.

---

## Expected Output

```
frontend/
└── components/
    └── AudioStatusBadge.tsx ← CREATED
```

---

## Validation

- [ ] Gray badge with "No Audio" shown when no audio file and idle.
- [ ] Amber badge with "Generating" shown during generation.
- [ ] Green badge with formatted duration shown when audio is ready.
- [ ] Red badge with "Failed" shown on generation error.
- [ ] Badge is compact and fits within the SegmentCard header line.
- [ ] Component is purely presentational with no side effects.

---

## Notes

- This component is entirely presentational — it receives all data via props and renders the appropriate variant. It dispatches no actions and makes no API calls.
- The `formatTime` utility converts a duration in seconds to "M:SS" format. If not already shared from AudioPlayer, consider extracting it to a shared utility file (e.g., `lib/utils.ts`) for reuse.
- Badge styling should use Tailwind utility classes for background color, text color, padding, and border-radius to keep it lightweight and consistent with the Shadcn design system.

---

> **Parent:** [SubPhase_03_03_Overview.md](./SubPhase_03_03_Overview.md) (Layer 2)
> **Phase:** [Phase_03_Overview.md](../Phase_03_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_03_03_03_Build_GenerateAudioButton.md](./Task_03_03_03_Build_GenerateAudioButton.md)
> **Next Task:** [Task_03_03_05_Update_SegmentCard_Audio_Section.md](./Task_03_03_05_Update_SegmentCard_Audio_Section.md)
