# Task 01.01.06 — Initialize Next.js Project

## Metadata

| Field                    | Value                                                                                  |
| ------------------------ | -------------------------------------------------------------------------------------- |
| **Sub-Phase**            | SubPhase 01.01 — Project Initialization & Tooling Setup                                |
| **Phase**                | Phase 01 — The Skeleton                                                                |
| **Document Type**        | Layer 3 — Task Document                                                                |
| **Estimated Complexity** | Medium                                                                                 |
| **Dependencies**         | None — frontend initialization is independent of backend tasks                         |
| **Parent Document**      | [SubPhase_01_01_Overview.md](SubPhase_01_01_Overview.md) (Layer 2, §5.6)               |

---

## Objective

Scaffold the Next.js frontend project inside `/frontend` using `create-next-app` with TypeScript (strict mode), App Router, Tailwind CSS, and ESLint enabled. The `/app` directory must be at the project root (no `/src` directory). After this task, the Next.js development server starts successfully on `http://localhost:3000`.

---

## Instructions

### Step 1: Run `create-next-app`

From the project root directory, run:

```bash
npx create-next-app@latest frontend --typescript --tailwind --eslint --app --src-dir=false --import-alias="@/*"
```

**Flag breakdown:**

| Flag                   | Purpose                                                     |
| ---------------------- | ----------------------------------------------------------- |
| `frontend`             | Directory name for the project                              |
| `--typescript`         | Enable TypeScript with strict mode                          |
| `--tailwind`           | Pre-configure Tailwind CSS                                  |
| `--eslint`             | Include ESLint configuration                                |
| `--app`                | Use the App Router (not Pages Router)                       |
| `--src-dir=false`      | Place `/app` at the project root, NOT inside `/src`         |
| `--import-alias="@/*"` | Set `@/` as the import alias for the project root           |

> **Critical:** The `--src-dir=false` flag is essential. Without it (or if set to `true`), the project creates `frontend/src/app/` instead of `frontend/app/`. This breaks all file path references in the StoryFlow documentation.

If `npx` prompts to install `create-next-app`, accept the prompt.

---

### Step 2: Verify the Generated Structure

After the command completes, confirm the following directory structure:

```
frontend/
├── app/
│   ├── favicon.ico
│   ├── globals.css
│   ├── layout.tsx
│   └── page.tsx
├── public/
│   ├── next.svg          (or similar default assets)
│   └── vercel.svg
├── .eslintrc.json         (or eslint.config.mjs)
├── .gitignore
├── next.config.ts
├── next-env.d.ts
├── package.json
├── package-lock.json
├── postcss.config.mjs
├── tailwind.config.ts
├── tsconfig.json
└── README.md
```

> **Key check:** `app/` must be directly inside `frontend/`, NOT inside `frontend/src/`.

---

### Step 3: Verify TypeScript Strict Mode

Open `frontend/tsconfig.json` and verify that `"strict": true` is set in the `compilerOptions`:

```json
{
  "compilerOptions": {
    "strict": true,
    ...
  }
}
```

If `"strict"` is missing or set to `false`, add or change it to `true`. This is a project requirement — all TypeScript must compile under strict mode.

---

### Step 4: Verify the Development Server

```bash
cd frontend
npm run dev
```

**Expected output:**

```
   ▲ Next.js 16.x.x
   - Local:        http://localhost:3000
   ...
 ✓ Ready in Xs
```

Open `http://localhost:3000` in a browser — the default Next.js welcome page should display.

Press `Ctrl+C` to stop the server after verification.

---

### Step 5: Verify TypeScript Compilation

Run the TypeScript compiler in check mode:

```bash
npx tsc --noEmit
```

This should complete with **zero errors**. If there are errors, they must be resolved before continuing.

---

## Expected Output

After completing this task:

```
/storyflow_root
├── /backend          (from Tasks 01–05)
└── /frontend         ← NEW
    ├── app/
    │   ├── favicon.ico
    │   ├── globals.css
    │   ├── layout.tsx
    │   └── page.tsx
    ├── public/
    ├── package.json
    ├── package-lock.json
    ├── tsconfig.json       (strict: true)
    ├── tailwind.config.ts
    ├── postcss.config.mjs
    ├── next.config.ts
    └── .eslintrc.json
```

The Next.js development server starts and serves the default welcome page on port 3000. TypeScript strict mode is enabled. Tailwind CSS is pre-configured (further verified in Task 01.01.07).

---

## Validation

- [ ] `frontend/` directory exists at the project root.
- [ ] `frontend/app/layout.tsx` exists (NOT `frontend/src/app/layout.tsx`).
- [ ] `frontend/app/page.tsx` exists.
- [ ] `frontend/tsconfig.json` contains `"strict": true`.
- [ ] `frontend/tailwind.config.ts` exists.
- [ ] `frontend/package.json` exists with Next.js as a dependency.
- [ ] `npm run dev` starts without errors on `http://localhost:3000`.
- [ ] The default Next.js welcome page loads in a browser.
- [ ] `npx tsc --noEmit` completes with zero errors.
- [ ] No `src/` directory exists inside `frontend/`.

---

## Notes

- **Package manager consistency:** If `npm` is used for `create-next-app`, continue using `npm` for all subsequent frontend commands throughout the project. Do not mix `npm` and `pnpm` — pick one.
- The `--import-alias="@/*"` flag configures path aliases so that imports can use `@/components/...`, `@/lib/...`, etc. This is defined in both `tsconfig.json` (paths) and Next.js configuration.
- The default `page.tsx` and `layout.tsx` files will be replaced with custom content in SubPhase 01.03. For now, leave them as auto-generated defaults.
- `create-next-app` also generates a `frontend/.gitignore` specific to Next.js. This complements (does not replace) the root `.gitignore` created in [Task 01.01.10](Task_01_01_10_Create_Gitignore.md).
- Next.js 16+ may have slightly different default file names or structures compared to earlier versions. The important invariants are: App Router is used, TypeScript is strict, Tailwind is configured, and no `/src` directory.

---

> **Parent:** [SubPhase_01_01_Overview.md](SubPhase_01_01_Overview.md) (Layer 2)
> **Phase:** [Phase_01_Overview.md](../Phase_01_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_01_01_05_Configure_Django_Settings.md](Task_01_01_05_Configure_Django_Settings.md)
> **Next Task:** [Task_01_01_07_Configure_Tailwind_CSS.md](Task_01_01_07_Configure_Tailwind_CSS.md)
