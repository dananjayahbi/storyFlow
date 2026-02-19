# Task 02.03.13 — Responsive Layout and Styling

> **Sub-Phase:** 02.03 — Image Upload & Timeline Editor UI
> **Phase:** Phase 02 — The Logic
> **Complexity:** Medium
> **Dependencies:** Task 02.03.07 (Timeline Editor Page)
> **Parent Document:** [SubPhase_02_03_Overview.md](./SubPhase_02_03_Overview.md)

---

## Objective

Ensure the Timeline Editor and all components are properly styled and responsive across desktop, tablet, and mobile breakpoints, with consistent spacing, dark-mode-ready colors, loading states, and empty states.

---

## Instructions

### Step 1 — Timeline Editor page breakpoints

| Breakpoint             | Layout                                                     |
| ---------------------- | ---------------------------------------------------------- |
| Desktop (≥1024px)      | Sidebar (250px) + Center panel (fluid) side-by-side        |
| Tablet (768px–1023px)  | Sidebar collapses to a top bar, center panel full width    |
| Mobile (<768px)        | Single column, sidebar info becomes collapsible section    |

Use Tailwind responsive prefixes: `lg:` for sidebar side-by-side, `md:` for tablet, default for mobile.

```tsx
<div className="flex flex-col lg:flex-row flex-1 overflow-hidden">
  <aside className="lg:w-64 lg:border-r border-b lg:border-b-0 p-4 flex-shrink-0">
    ...
  </aside>
  <main className="flex-1 overflow-auto">
    <Timeline ... />
  </main>
</div>
```

### Step 2 — SegmentCard responsiveness

- Desktop: Image zone and prompt side by side (`flex-row`).
- Mobile: Image zone and prompt stacked vertically (`flex-col`).

```tsx
<div className="flex flex-col md:flex-row gap-4">
  <div className="md:w-2/5"><ImageUploader ... /></div>
  <div className="md:w-3/5"><ImagePromptDisplay ... /></div>
</div>
```

### Step 3 — Consistent spacing

- Between cards: `space-y-4`.
- Inside cards: `p-4`.
- Between sections within a card: `space-y-3`.
- Use Tailwind's design tokens consistently.

### Step 4 — Dark mode readiness

Use Shadcn/Tailwind semantic colors — **not** hardcoded colors:

| Use This                 | NOT This        |
| ------------------------ | --------------- |
| `bg-background`         | `bg-white`      |
| `text-foreground`       | `text-black`    |
| `bg-muted`              | `bg-gray-100`   |
| `text-muted-foreground` | `text-gray-500`  |
| `border`                | `border-gray-200`|
| `bg-destructive`        | `bg-red-500`    |

### Step 5 — Loading states

- **Page loading:** Skeleton loaders (pulsing placeholder blocks) mimicking the layout structure.
- **Segment save:** "Saving..." text indicator (from SegmentTextEditor).
- **Image upload:** "Uploading..." text or spinner (from ImageUploader).
- **Delete:** Brief loading state on the confirm button.

### Step 6 — Empty states

- **No segments:** "Import a story to get started" with action link back to dashboard.
- **No image:** Drop zone with clear dashed border and upload icon.

### Step 7 — Action bar styling

- Fixed at bottom of the page.
- Disabled buttons: `opacity-50 cursor-not-allowed`.
- Tooltips explain why buttons are disabled ("Coming in Phase 03" / "Coming in Phase 04").

### Step 8 — Test at common breakpoints

Verify layout at: 375px (mobile), 768px (tablet), 1024px (laptop), 1440px (desktop).

---

## Expected Output

```
frontend/
├── app/
│   └── projects/[id]/page.tsx  ← MODIFIED (responsive classes)
└── components/
    ├── SegmentCard.tsx         ← MODIFIED (responsive image/prompt layout)
    ├── Timeline.tsx            ← MODIFIED (responsive adjustments)
    └── ImageUploader.tsx       ← MODIFIED (responsive sizing)
```

---

## Validation

- [ ] Desktop: Sidebar + center panel side-by-side.
- [ ] Tablet: Sidebar collapses to top bar.
- [ ] Mobile: Single-column layout.
- [ ] SegmentCard image/prompt stacks vertically on mobile.
- [ ] All colors use Tailwind semantic tokens (dark-mode ready).
- [ ] Loading skeletons show during data fetch.
- [ ] Empty state message shown when no segments.
- [ ] Disabled action buttons have reduced opacity and tooltips.
- [ ] No custom CSS files — Tailwind utilities only.

---

## Notes

- Use Tailwind's responsive prefixes: `sm:`, `md:`, `lg:`.
- Do NOT use any CSS frameworks beyond Tailwind — Shadcn/UI handles component styling.
- Do NOT implement virtual scrolling in Phase 02 — keep it simple. Use `React.memo` on `SegmentCard` for performance.

---

> **Parent:** [SubPhase_02_03_Overview.md](./SubPhase_02_03_Overview.md) (Layer 2)
> **Phase:** [Phase_02_Overview.md](../Phase_02_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_02_03_12_Install_New_Shadcn_Components.md](./Task_02_03_12_Install_New_Shadcn_Components.md)
> **Next Task:** [Task_02_03_14_Write_Frontend_Component_Tests.md](./Task_02_03_14_Write_Frontend_Component_Tests.md)
