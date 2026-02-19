# Task 01.01.07 — Configure Tailwind CSS

## Metadata

| Field                    | Value                                                                                  |
| ------------------------ | -------------------------------------------------------------------------------------- |
| **Sub-Phase**            | SubPhase 01.01 — Project Initialization & Tooling Setup                                |
| **Phase**                | Phase 01 — The Skeleton                                                                |
| **Document Type**        | Layer 3 — Task Document                                                                |
| **Estimated Complexity** | Low                                                                                    |
| **Dependencies**         | [Task_01_01_06](Task_01_01_06_Initialize_NextJS_Project.md) — Next.js project must exist |
| **Parent Document**      | [SubPhase_01_01_Overview.md](SubPhase_01_01_Overview.md) (Layer 2, §5.7)               |

---

## Objective

Verify and configure Tailwind CSS 4 so that utility classes are properly scoped to the project's component directories and render correctly in the browser.

---

## Instructions

### Step 1: Verify `tailwind.config.ts` Content Array

Open `frontend/tailwind.config.ts` and ensure the `content` array includes all directories where Tailwind classes will be used:

```typescript
content: [
  './app/**/*.{js,ts,jsx,tsx,mdx}',
  './components/**/*.{js,ts,jsx,tsx,mdx}',
  './lib/**/*.{js,ts,jsx,tsx,mdx}',
]
```

If `./components/**` or `./lib/**` are missing, add them. These directories will contain Shadcn/UI components and utility files that use Tailwind classes.

> **Note:** Tailwind CSS 4 may use a different configuration format than v3 (e.g., CSS-based configuration via `@import` instead of a JS/TS config file). If `create-next-app` generated a v4-style setup, follow the v4 configuration approach while ensuring all three directories are covered.

---

### Step 2: Verify `globals.css` Tailwind Directives

Open `frontend/app/globals.css` and verify it includes the Tailwind base directives:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

For Tailwind CSS 4, this may instead use:

```css
@import "tailwindcss";
```

Either format is acceptable as long as Tailwind's base styles, component layer, and utilities layer are all loaded.

---

### Step 3: Test Tailwind Rendering

Start the dev server and verify Tailwind classes render correctly:

```bash
cd frontend
npm run dev
```

Open `http://localhost:3000` in a browser and inspect the page with browser DevTools. Verify that:
- Tailwind's CSS reset is applied (e.g., `margin: 0` on `body`).
- Tailwind utility classes (e.g., `text-blue-500`, `p-4`, `flex`) produce the expected styles.

---

## Expected Output

No new files are created. The existing `tailwind.config.ts` and `globals.css` are verified (and adjusted if needed) to ensure proper Tailwind CSS coverage across all project directories.

---

## Validation

- [ ] `frontend/tailwind.config.ts` exists and includes `./app/**`, `./components/**`, and `./lib/**` in its content array.
- [ ] `frontend/app/globals.css` contains Tailwind directives (`@tailwind base/components/utilities` or `@import "tailwindcss"`).
- [ ] Tailwind utility classes render correctly in the browser (verified via DevTools).
- [ ] No CSS compilation errors appear in the terminal when running `npm run dev`.

---

## Notes

- This task is primarily a **verification task**. If `create-next-app` was run with `--tailwind`, most configuration should already be correct. The main risk is a missing `content` path for `./components/**` or `./lib/**`.
- Tailwind CSS 4 introduced significant configuration changes from v3. The exact format depends on which version `create-next-app` installs. Follow whichever format the generated project uses — do NOT mix v3 and v4 configuration styles.

---

> **Parent:** [SubPhase_01_01_Overview.md](SubPhase_01_01_Overview.md) (Layer 2)
> **Previous Task:** [Task_01_01_06_Initialize_NextJS_Project.md](Task_01_01_06_Initialize_NextJS_Project.md)
> **Next Task:** [Task_01_01_08_Initialize_Shadcn_UI.md](Task_01_01_08_Initialize_Shadcn_UI.md)
