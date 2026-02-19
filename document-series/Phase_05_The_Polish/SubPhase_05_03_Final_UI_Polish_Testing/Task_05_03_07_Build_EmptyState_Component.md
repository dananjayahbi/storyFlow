# Task 05.03.07 — Build EmptyState Component

## Layer 3 Task Document

---

| **Field**              | **Value**                                                                                      |
| ---------------------- | ---------------------------------------------------------------------------------------------- |
| **Task ID**            | 05.03.07                                                                                       |
| **Task Name**          | Build EmptyState Component                                                                     |
| **Sub-Phase**          | 05.03 — Final UI Polish & Testing                                                              |
| **Phase**              | Phase 05 — The Polish                                                                          |
| **Layer**              | Layer 3 (Task Document)                                                                        |
| **Status**             | Not Started                                                                                    |
| **Estimated Complexity** | Low                                                                                          |
| **Parent Document**    | [SubPhase_05_03_Overview.md](./SubPhase_05_03_Overview.md) (Layer 2)                           |
| **Dependencies**       | None (reusable UI component — independent of other tasks)                                      |
| **Output Files**       | `frontend/components/EmptyState.tsx` (NEW), multiple page components (MODIFIED)                |

---

## Objective

Build a reusable empty state component that displays a friendly message when lists or sections have no content, and integrate it into all locations across the application that can be empty.

---

## Instructions

### Step 1 — Create the EmptyState Component

Create `frontend/components/EmptyState.tsx` accepting the following props: `icon` (a Lucide React icon component), `title` (heading string), `description` (explanatory text string), and optionally `actionLabel` (button text) and `onAction` (button click handler). The component renders a vertically centered layout with the icon displayed large in muted color, the title as a semibold heading, the description in muted text, and an optional CTA button below.

### Step 2 — Style the Component

Use a centered flexbox column layout with generous vertical padding (around `py-16`). The icon should be large (e.g., `h-12 w-12`) in `text-muted-foreground` color. The title should be `text-lg font-semibold`. The description should be `text-muted-foreground` with a max width constraint to prevent overly wide text. The optional button uses the standard Shadcn/UI `Button` component.

### Step 3 — Integrate Into the Dashboard

Replace the current empty project list display on the dashboard page with the `EmptyState` component using: FolderPlus icon, title "No projects yet", description "Create your first story to get started!", actionLabel "+ New Project", and `onAction` that triggers the project creation flow.

### Step 4 — Integrate Into the Project Detail Page

When a project has no segments (before import), replace the blank area with: FileText icon, title "No segments", description "Import a story to create segments."

### Step 5 — Integrate Into Segment Contexts

For segments without audio: Volume2 icon, title "No audio generated", description "Click 'Generate Audio' to create narration." For segments without an image: Image icon, title "No image uploaded", description "Upload an image for this segment." For projects without a rendered video: Video icon, title "No video yet", description "Click 'Export Video' to render your story."

---

## Expected Output

A reusable `EmptyState.tsx` component integrated into the dashboard, project detail page, and segment-level displays, replacing blank areas with informative, actionable empty state messages.

---

## Validation

- [ ] EmptyState component renders with icon, title, description, and optional CTA button.
- [ ] Dashboard shows the EmptyState when no projects exist.
- [ ] Project detail shows EmptyState when no segments exist.
- [ ] CTA buttons trigger the correct actions (e.g., create project, import story).
- [ ] EmptyState without a CTA button renders correctly (icon + text only).
- [ ] Visual styling is centered, uses muted colors, and looks polished.

---

## Notes

- The EmptyState component is stateless — no internal state, no API calls. It is purely presentational.
- The Lucide React icons (FolderPlus, FileText, Volume2, Image, Video) are already available as part of the Shadcn/UI dependency chain.
- Each integration replaces a previously blank or minimal "No items" text area, significantly improving the user experience by providing context and guidance.

---

> **Parent:** [SubPhase_05_03_Overview.md](./SubPhase_05_03_Overview.md) (Layer 2)
> **Phase:** [Phase_05_Overview.md](../Phase_05_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
