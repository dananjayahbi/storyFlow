# Task 02.03.12 — Install New Shadcn Components

> **Sub-Phase:** 02.03 — Image Upload & Timeline Editor UI
> **Phase:** Phase 02 — The Logic
> **Complexity:** Low
> **Dependencies:** None (should be done FIRST)
> **Parent Document:** [SubPhase_02_03_Overview.md](./SubPhase_02_03_Overview.md)

---

## Objective

Install all new Shadcn/UI components required for this sub-phase and configure the root layout with `<Toaster />` and `<TooltipProvider />`.

---

## Instructions

### Step 1 — Install Shadcn components

```bash
cd frontend
npx shadcn@latest add textarea tooltip dropdown-menu scroll-area separator alert-dialog toast
```

### Step 2 — Verify installation

Confirm the following files exist in `frontend/components/ui/`:

| File                    | Purpose                                   |
| ----------------------- | ----------------------------------------- |
| `textarea.tsx`          | Inline text editing (SegmentTextEditor)   |
| `tooltip.tsx`           | Hover tooltips for action buttons         |
| `dropdown-menu.tsx`     | Context menus for actions                 |
| `scroll-area.tsx`       | Vertical scrollable segment list          |
| `separator.tsx`         | Visual dividers between sections          |
| `alert-dialog.tsx`      | Confirmation dialogs for destructive actions |
| `toast.tsx`             | Brief notifications ("Copied!", "Saved!") |
| `toaster.tsx`           | Toast provider component                  |
| `use-toast.ts`          | Toast hook                                |

### Step 3 — Add Toaster to root layout

In `frontend/app/layout.tsx`, add the `<Toaster />` component:

```tsx
import { Toaster } from "@/components/ui/toaster";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        {children}
        <Toaster />
      </body>
    </html>
  );
}
```

### Step 4 — Add TooltipProvider to root layout

The Shadcn `Tooltip` component requires a `<TooltipProvider>` wrapper:

```tsx
import { TooltipProvider } from "@/components/ui/tooltip";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <TooltipProvider>
          {children}
        </TooltipProvider>
        <Toaster />
      </body>
    </html>
  );
}
```

### Step 5 — Verify TypeScript compilation

```bash
cd frontend
npx tsc --noEmit
```

---

## Expected Output

```
frontend/
├── app/
│   └── layout.tsx              ← MODIFIED (Toaster + TooltipProvider added)
└── components/
    └── ui/
        ├── textarea.tsx        ← NEW (Shadcn)
        ├── tooltip.tsx         ← NEW (Shadcn)
        ├── dropdown-menu.tsx   ← NEW (Shadcn)
        ├── scroll-area.tsx     ← NEW (Shadcn)
        ├── separator.tsx       ← NEW (Shadcn)
        ├── alert-dialog.tsx    ← NEW (Shadcn)
        ├── toast.tsx           ← NEW (Shadcn)
        ├── toaster.tsx         ← NEW (Shadcn)
        └── use-toast.ts        ← NEW (Shadcn)
```

---

## Validation

- [ ] All 7 Shadcn components installed (+ toaster + use-toast).
- [ ] `<Toaster />` added to root layout.
- [ ] `<TooltipProvider>` wraps `{children}` in root layout.
- [ ] `npx tsc --noEmit` passes with zero errors.
- [ ] No new npm packages installed beyond Shadcn-generated components.

---

## Notes

- This task should be done **FIRST** before any component work that uses these Shadcn components.
- The Toast system requires both the `toast` component and the `<Toaster />` provider — without `<Toaster />`, toast calls silently fail.
- The `useToast` hook must be used within a React component — it cannot be called from a Zustand store directly. Pass toast callbacks as parameters if needed.

---

> **Parent:** [SubPhase_02_03_Overview.md](./SubPhase_02_03_Overview.md) (Layer 2)
> **Phase:** [Phase_02_Overview.md](../Phase_02_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_02_03_11_Add_Project_Delete_To_Dashboard.md](./Task_02_03_11_Add_Project_Delete_To_Dashboard.md)
> **Next Task:** [Task_02_03_13_Responsive_Layout_And_Styling.md](./Task_02_03_13_Responsive_Layout_And_Styling.md)
