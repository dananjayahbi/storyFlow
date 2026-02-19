# Task 03.03.13 — Responsive Audio Layout

> **Sub-Phase:** 03.03 — Audio Playback UI
> **Phase:** Phase 03 — The Voice
> **Complexity:** Medium
> **Dependencies:** Task 03.03.02 (AudioPlayer), Task 03.03.03 (GenerateAudioButton), Task 03.03.05 (SegmentCard Audio Section), Task 03.03.07 (Footer Progress Bar)
> **Parent Document:** [SubPhase_03_03_Overview.md](./SubPhase_03_03_Overview.md)

---

## Objective

Ensure all audio-related UI components render correctly and remain usable across mobile, tablet, and desktop viewport widths.

---

## Instructions

### Step 1 — Audit AudioPlayer at narrow widths

Open `frontend/components/AudioPlayer.tsx` and test the layout at 320px viewport width. On narrow screens, the time display (current time / duration) should stack below the slider rather than sitting inline. Use a Tailwind responsive breakpoint (e.g., `sm:`) to switch between stacked and inline layouts. The play/pause button should remain fixed-width, and the slider should use `flex-1` to fill available horizontal space.

### Step 2 — Audit GenerateAudioButton at narrow widths

Open `frontend/components/GenerateAudioButton.tsx` and verify that the button text wraps naturally at narrow widths. The button should use `w-full` or a similar Tailwind utility on narrow screens so it spans the full width of the audio section, then revert to auto-width on wider screens.

### Step 3 — Audit SegmentCard audio section overflow

In `frontend/components/SegmentCard.tsx`, ensure the audio section container has `overflow-hidden` to prevent the slider or any other audio element from overflowing the card boundary. Test with long error messages in the failed state to confirm they truncate or wrap gracefully.

### Step 4 — Audit footer progress bar

In `frontend/app/projects/[id]/page.tsx`, confirm the Shadcn Progress component spans `w-full` within the footer area. The progress label text should wrap naturally below the bar on narrow screens. Test at 320px and 768px widths.

### Step 5 — Test at three breakpoints

Verify the full audio UI at three representative viewport widths:
- 320px (mobile): All elements stack vertically, buttons are full-width, slider remains usable with touch.
- 768px (tablet): Elements begin to display inline where appropriate, adequate spacing.
- 1024px+ (desktop): Full inline layouts, comfortable spacing, no wasted space.

### Step 6 — Ensure touch target sizes

On narrow viewports, verify that the play/pause button, slider thumb, and Generate Audio button meet minimum touch target sizes (at least 44×44 CSS pixels) for comfortable mobile interaction. Adjust padding or sizing as needed.

---

## Expected Output

```
frontend/
├── components/
│   ├── AudioPlayer.tsx ← MODIFIED (responsive adjustments)
│   ├── GenerateAudioButton.tsx ← MODIFIED (responsive adjustments)
│   └── SegmentCard.tsx ← MODIFIED (overflow handling)
└── app/
    └── projects/
        └── [id]/
            └── page.tsx ← MODIFIED (footer bar responsive)
```

---

## Validation

- [ ] AudioPlayer time display stacks below slider on narrow screens.
- [ ] Slider uses `flex-1` and fills available width.
- [ ] GenerateAudioButton is full-width on mobile, auto-width on desktop.
- [ ] Audio section has `overflow-hidden` on SegmentCard.
- [ ] Long error messages truncate or wrap without overflow.
- [ ] Footer progress bar spans full width at all breakpoints.
- [ ] Progress label wraps naturally on narrow screens.
- [ ] Layout is correct at 320px, 768px, and 1024px+.
- [ ] Touch targets meet 44×44px minimum on mobile.
- [ ] No horizontal scrolling caused by audio components.

---

## Notes

- This task does not introduce new functionality — it is a responsive polish pass over the components built in earlier tasks. All changes should be Tailwind CSS adjustments only (responsive prefixes, flexbox utilities, overflow handling).
- Tailwind CSS 4 responsive prefixes follow the mobile-first convention: base styles apply to mobile, and `sm:`, `md:`, `lg:` prefixes add overrides for larger screens.
- The Shadcn Slider component renders an HTML range input internally. Ensure the slider container is not constrained by a fixed width that would make it unusable on mobile. A minimum width of around 120px is a reasonable floor.
- Touch interaction on the slider may require testing on an actual mobile device or using browser DevTools' device emulation mode.

---

> **Parent:** [SubPhase_03_03_Overview.md](./SubPhase_03_03_Overview.md) (Layer 2)
> **Phase:** [Phase_03_Overview.md](../Phase_03_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_03_03_12_Text_Changed_Audio_Stale_Warning.md](./Task_03_03_12_Text_Changed_Audio_Stale_Warning.md)
> **Next Task:** [Task_03_03_14_Write_Frontend_Component_Tests.md](./Task_03_03_14_Write_Frontend_Component_Tests.md)
