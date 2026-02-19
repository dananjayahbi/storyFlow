# Task 03.03.01 — Install New Shadcn Components

> **Sub-Phase:** 03.03 — Audio Playback UI
> **Phase:** Phase 03 — The Voice
> **Complexity:** Low
> **Dependencies:** None
> **Parent Document:** [SubPhase_03_03_Overview.md](./SubPhase_03_03_Overview.md)

---

## Objective

Install the Shadcn `Progress` and `Slider` UI components required by the audio playback interface.

---

## Instructions

### Step 1 — Install the `progress` component

Navigate to the `frontend/` directory and run `npx shadcn@latest add progress`. This auto-generates `components/ui/progress.tsx` with the Radix UI `Progress` primitive styled with Tailwind CSS.

### Step 2 — Install the `slider` component

Run `npx shadcn@latest add slider`. This auto-generates `components/ui/slider.tsx` with the Radix UI `Slider` primitive styled with Tailwind CSS.

### Step 3 — Verify file creation

Confirm both files exist under `components/ui/`. Open each file briefly to verify the imports and exports are correct.

### Step 4 — Verify TypeScript compilation

Run `npx tsc --noEmit` to ensure the new components compile without errors and integrate with the existing project configuration.

---

## Expected Output

```
frontend/
└── components/
    └── ui/
        ├── progress.tsx        ← CREATED (Shadcn auto-generated)
        └── slider.tsx          ← CREATED (Shadcn auto-generated)
```

---

## Validation

- [ ] `components/ui/progress.tsx` exists and exports a `Progress` component.
- [ ] `components/ui/slider.tsx` exists and exports a `Slider` component.
- [ ] `npx tsc --noEmit` passes with zero errors.

---

## Notes

- These are the only new Shadcn components needed for Phase 03. All other Shadcn components (Button, Card, Dialog, Badge, etc.) were installed during Phases 01–02.
- `Progress` is used for the footer bulk generation progress bar (Task 03.03.07).
- `Slider` is used for the audio seek/scrub bar in the `AudioPlayer` component (Task 03.03.02).

---

> **Parent:** [SubPhase_03_03_Overview.md](./SubPhase_03_03_Overview.md) (Layer 2)
> **Phase:** [Phase_03_Overview.md](../Phase_03_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Next Task:** [Task_03_03_02_Build_AudioPlayer_Component.md](./Task_03_03_02_Build_AudioPlayer_Component.md)
