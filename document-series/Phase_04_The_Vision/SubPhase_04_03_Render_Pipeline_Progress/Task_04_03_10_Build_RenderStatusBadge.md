# Task 04.03.10 — Build RenderStatusBadge

## Metadata

| Field         | Value                                                                |
| ------------- | -------------------------------------------------------------------- |
| **Task ID**   | 04.03.10                                                             |
| **Task Name** | Build RenderStatusBadge                                              |
| **Sub-Phase** | 04.03 — Render Pipeline & Progress API                               |
| **Phase**     | Phase 04 — The Vision: Video Rendering Engine                        |
| **Complexity**| Medium                                                               |
| **Dependencies** | None (purely presentational)                                      |
| **Parent**    | [SubPhase_04_03_Overview.md](./SubPhase_04_03_Overview.md)           |

---

## Objective

Build a small presentational component that renders a color-coded badge reflecting the project's current render status. The badge uses the Shadcn Badge component with four distinct visual variants corresponding to DRAFT, PROCESSING, COMPLETED, and FAILED states. It is used in multiple locations: the project detail page header and the dashboard project cards.

---

## Instructions

### Step 1 — Create the Component File

Create a new file at frontend/components/RenderStatusBadge.tsx. This can be a server component since it is purely presentational with no client-side interactivity — it receives the status as a prop and renders accordingly. However, if it is imported by a client component, it becomes a client component implicitly, which is also acceptable.

### Step 2 — Define the Props Interface

Define a TypeScript interface for the component props. The only required prop is status, typed as a union of the four allowed string literals: "DRAFT", "PROCESSING", "COMPLETED", and "FAILED". Optionally accept a className prop for layout customization by the parent.

### Step 3 — Map Status to Visual Variants

Create a mapping from each status value to its visual properties:

- DRAFT: Use a gray/neutral badge variant. Display the text "Draft" with a pencil emoji (📝).
- PROCESSING: Use a yellow/warning badge variant. Display the text "Rendering" with a gear emoji (⚙️). Apply Tailwind's animate-pulse class to create a subtle pulsing animation indicating active processing.
- COMPLETED: Use a green/success badge variant. Display the text "Completed" with a checkmark emoji (✅).
- FAILED: Use a red/destructive badge variant. Display the text "Failed" with an X emoji (❌).

### Step 4 — Render the Badge

Render the Shadcn Badge component with the appropriate variant, text, and emoji based on the status prop. Apply the optional className prop using Tailwind's cn utility for merging class strings.

### Step 5 — Handle Unknown Status

Include a fallback for any status value that does not match the four expected values. Render a default gray badge with the raw status string. This defensive coding handles edge cases where the backend sends an unexpected status value.

---

## Expected Output

A new file frontend/components/RenderStatusBadge.tsx that renders a color-coded Shadcn Badge based on the project's render status. The component is used in the project header and dashboard cards.

---

## Validation

- [ ] RenderStatusBadge.tsx exists with a typed status prop.
- [ ] DRAFT renders a gray badge with "Draft 📝".
- [ ] PROCESSING renders a yellow badge with "Rendering ⚙️" and pulse animation.
- [ ] COMPLETED renders a green badge with "Completed ✅".
- [ ] FAILED renders a red badge with "Failed ❌".
- [ ] Accepts an optional className prop for layout customization.
- [ ] Handles unknown status values with a fallback.

---

## Notes

- This is a purely presentational component with no side effects, state, or API calls. It simply transforms a status string into a visual indicator.
- The pulse animation on the PROCESSING badge provides a subtle visual cue that something is actively happening, without being distracting.
- The emoji characters are used instead of icon components to keep the badge compact and avoid additional icon library imports for this simple use case.
- The component is intentionally simple and reusable — it receives status as a prop rather than reading from the Zustand store, making it usable in both the project detail page (where store data is available) and the dashboard cards (where status comes from the API list response).

---

> **Parent:** [SubPhase_04_03_Overview.md](./SubPhase_04_03_Overview.md) (Layer 2)
> **Phase:** [Phase_04_Overview.md](../Phase_04_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
