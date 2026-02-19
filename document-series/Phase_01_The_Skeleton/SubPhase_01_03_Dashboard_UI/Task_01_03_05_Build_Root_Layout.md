# Task 01.03.05 — Build Root Layout

## Metadata

| Field                    | Value                                                                   |
| ------------------------ | ----------------------------------------------------------------------- |
| **Sub-Phase**            | SubPhase 01.03 — Dashboard UI & Basic API                               |
| **Phase**                | Phase 01 — The Skeleton                                                 |
| **Document Type**        | Layer 3 — Task Document                                                 |
| **Estimated Complexity** | Low                                                                     |
| **Dependencies**         | None                                                                    |
| **Parent Document**      | [SubPhase_01_03_Overview.md](SubPhase_01_03_Overview.md) (Layer 2, §5.5)|

---

## Objective

Customize the root layout with StoryFlow branding, font configuration, metadata, and a persistent header with responsive container styling.

---

## Instructions

### Step 1: Update `app/layout.tsx`

Open `frontend/app/layout.tsx` and replace with:

```tsx
import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'StoryFlow',
  description: 'Semi-Automated Narrative Video Engine',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <header className="border-b bg-background">
          <div className="container mx-auto px-4 py-4">
            <h1 className="text-2xl font-bold">StoryFlow</h1>
          </div>
        </header>
        <main className="container mx-auto px-4 py-8">
          {children}
        </main>
      </body>
    </html>
  );
}
```

---

## Expected Output

```
frontend/app/layout.tsx   ← MODIFIED
```

---

## Validation

- [ ] `<html lang="en">` is set.
- [ ] Inter font is loaded from `next/font/google`.
- [ ] Metadata includes `title: 'StoryFlow'` and `description`.
- [ ] A `<header>` with "StoryFlow" title is rendered on every page.
- [ ] `{children}` is wrapped in a `<main>` with container, padding, and max-width.
- [ ] `globals.css` is imported (for Tailwind base styles).

---

## Notes

- The header is persistent across all pages. Individual pages render inside `{children}`.
- The "Create Project" button is NOT in the layout — it belongs to the dashboard page specifically.
- The `Inter` font can be swapped for any other Google Font. It's a popular choice for clean UI typography.
- If the Next.js scaffold already has a layout, modify it rather than creating from scratch. Preserve any existing Tailwind/Shadcn CSS imports.

---

> **Parent:** [SubPhase_01_03_Overview.md](SubPhase_01_03_Overview.md) (Layer 2)
> **Previous Task:** [Task_01_03_04_Define_TypeScript_Interfaces.md](Task_01_03_04_Define_TypeScript_Interfaces.md)
> **Next Task:** [Task_01_03_06_Build_Dashboard_Page.md](Task_01_03_06_Build_Dashboard_Page.md)
