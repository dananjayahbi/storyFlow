# Task 01.01.08 — Initialize Shadcn/UI

## Metadata

| Field                    | Value                                                                                  |
| ------------------------ | -------------------------------------------------------------------------------------- |
| **Sub-Phase**            | SubPhase 01.01 — Project Initialization & Tooling Setup                                |
| **Phase**                | Phase 01 — The Skeleton                                                                |
| **Document Type**        | Layer 3 — Task Document                                                                |
| **Estimated Complexity** | Low                                                                                    |
| **Dependencies**         | [Task_01_01_07](Task_01_01_07_Configure_Tailwind_CSS.md) — Tailwind CSS must be configured |
| **Parent Document**      | [SubPhase_01_01_Overview.md](SubPhase_01_01_Overview.md) (Layer 2, §5.8)               |

---

## Objective

Initialize Shadcn/UI in the frontend project, install the base set of UI components (button, card, dialog, input, badge), and install Axios as the HTTP client dependency.

---

## Instructions

### Step 1: Initialize Shadcn/UI

From the `frontend/` directory, run:

```bash
cd frontend
npx shadcn-ui@latest init
```

When prompted, select the following configuration:

| Prompt                    | Selection          |
| ------------------------- | ------------------ |
| Style                     | Default            |
| Base color                | Slate (or Neutral) |
| CSS variables             | Yes                |
| Components directory      | `components/ui`    |
| Utilities                 | `lib/utils.ts`     |

> **Note:** Prompt wording may vary between Shadcn/UI versions. Choose the option closest to each specification above.

---

### Step 2: Install Base Components

Install the five base components needed for SubPhase 01.03:

```bash
npx shadcn-ui@latest add button card dialog input badge
```

This copies the component source files directly into `frontend/components/ui/`. They are NOT npm dependencies — they are local files that can be customized.

---

### Step 3: Install Axios

```bash
npm install axios
```

Axios will be used as the HTTP client for frontend-to-backend API communication. The actual API client module (`lib/api.ts`) is built in SubPhase 01.03 — Axios is only installed as a dependency here.

---

### Step 4: Verify Generated Files

Confirm the following files exist:

| File                                  | Created By           | Purpose                                      |
| ------------------------------------- | -------------------- | -------------------------------------------- |
| `frontend/components.json`           | `shadcn-ui init`     | Shadcn/UI project configuration              |
| `frontend/lib/utils.ts`              | `shadcn-ui init`     | `cn()` helper (merges Tailwind class names)  |
| `frontend/components/ui/button.tsx`   | `shadcn-ui add`      | Button component                             |
| `frontend/components/ui/card.tsx`     | `shadcn-ui add`      | Card component (with header, content, footer)|
| `frontend/components/ui/dialog.tsx`   | `shadcn-ui add`      | Dialog/modal component                       |
| `frontend/components/ui/input.tsx`    | `shadcn-ui add`      | Text input component                         |
| `frontend/components/ui/badge.tsx`    | `shadcn-ui add`      | Badge/label component                        |

Verify that `frontend/lib/utils.ts` contains the `cn()` function:

```typescript
import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
```

---

### Step 5: Verify Axios in `package.json`

Open `frontend/package.json` and confirm `axios` appears in the `dependencies` section:

```json
{
  "dependencies": {
    "axios": "^1.x.x",
    ...
  }
}
```

---

## Expected Output

```
frontend/
├── app/
├── components/
│   └── ui/              ← NEW
│       ├── button.tsx
│       ├── card.tsx
│       ├── dialog.tsx
│       ├── input.tsx
│       └── badge.tsx
├── lib/
│   └── utils.ts         ← NEW
├── components.json      ← NEW
├── package.json         ← MODIFIED (axios added)
└── ...
```

---

## Validation

- [ ] `frontend/components.json` exists and is properly configured.
- [ ] `frontend/lib/utils.ts` exists with the `cn()` helper function.
- [ ] `frontend/components/ui/button.tsx` exists.
- [ ] `frontend/components/ui/card.tsx` exists.
- [ ] `frontend/components/ui/dialog.tsx` exists.
- [ ] `frontend/components/ui/input.tsx` exists.
- [ ] `frontend/components/ui/badge.tsx` exists.
- [ ] `axios` is listed in `frontend/package.json` dependencies.
- [ ] `npm run dev` still starts without errors after these additions.
- [ ] `npx tsc --noEmit` completes with zero TypeScript errors.

---

## Notes

- Shadcn/UI copies component source code into the project — they are local files, not installed npm packages. This means they can be freely customized without affecting any upstream dependency.
- The `cn()` helper from `lib/utils.ts` is used throughout Shadcn/UI components and in custom components to conditionally merge Tailwind class names.
- Additional Shadcn/UI components (e.g., `toast`, `slider`, `select`) will be installed in later phases as needed. Only the base five are installed now.
- Axios is installed but NOT used yet. The API client module (`lib/api.ts`) that wraps Axios is built in SubPhase 01.03.

---

> **Parent:** [SubPhase_01_01_Overview.md](SubPhase_01_01_Overview.md) (Layer 2)
> **Previous Task:** [Task_01_01_07_Configure_Tailwind_CSS.md](Task_01_01_07_Configure_Tailwind_CSS.md)
> **Next Task:** [Task_01_01_09_Configure_CORS.md](Task_01_01_09_Configure_CORS.md)
