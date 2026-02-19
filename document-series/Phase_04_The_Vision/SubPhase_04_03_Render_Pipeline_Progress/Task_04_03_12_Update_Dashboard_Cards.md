# Task 04.03.12 — Update Dashboard Cards

## Metadata

| Field         | Value                                                                |
| ------------- | -------------------------------------------------------------------- |
| **Task ID**   | 04.03.12                                                             |
| **Task Name** | Update Dashboard Cards                                               |
| **Sub-Phase** | 04.03 — Render Pipeline & Progress API                               |
| **Phase**     | Phase 04 — The Vision: Video Rendering Engine                        |
| **Complexity**| Low                                                                  |
| **Dependencies** | Task 04.03.10 (RenderStatusBadge component)                      |
| **Parent**    | [SubPhase_04_03_Overview.md](./SubPhase_04_03_Overview.md)           |

---

## Objective

Update the ProjectCard component on the dashboard to display the render status badge and add a "Watch" quick-action link for projects with completed videos. These additions provide at-a-glance visibility into each project's render state directly from the dashboard, without requiring the user to navigate into the project detail page.

---

## Instructions

### Step 1 — Import RenderStatusBadge

In the existing ProjectCard.tsx component file, import the RenderStatusBadge component created in Task 04.03.10.

### Step 2 — Add the Status Badge to the Card Layout

Place the RenderStatusBadge in the card's header area, alongside the project title. Pass the project's status field as the status prop. Position the badge to the right of the title using Tailwind flex utilities (e.g., flex row with items-center and justify-between) so the title and badge sit on the same line.

### Step 3 — Add the "Watch" Quick-Action

For projects with status "COMPLETED", add a "Watch" quick-action button or link to the card's footer area alongside existing actions (like the "Open" button). The Watch action navigates the user to the project detail page, where the VideoPreview component will display the rendered video. Use Next.js router push to navigate to the project detail route.

### Step 4 — Conditional Rendering

Only render the "Watch" action when the project status is COMPLETED. For other statuses, the existing card layout remains unchanged. This prevents showing a "Watch" button for projects that have not yet been rendered.

---

## Expected Output

The ProjectCard component on the dashboard now displays a RenderStatusBadge for each project and shows a "Watch" quick-action for projects with completed videos.

---

## Validation

- [ ] RenderStatusBadge appears in the project card header.
- [ ] Badge correctly reflects DRAFT, PROCESSING, COMPLETED, and FAILED statuses.
- [ ] "Watch" action appears only for COMPLETED projects.
- [ ] "Watch" action navigates to the project detail page.
- [ ] Existing card layout and actions are preserved.

---

## Notes

- This is a minor enhancement to an existing component. The primary changes are importing and rendering the badge, plus adding a conditional action link.
- The "Watch" action navigates to the project detail page rather than opening the video directly, because the VideoPreview component (with playback controls, metadata, and download) is already part of the detail page layout.
- The status data comes from the project list API response, which already includes the status field from the Phase 01 model definition. No additional API calls are needed.

---

> **Parent:** [SubPhase_04_03_Overview.md](./SubPhase_04_03_Overview.md) (Layer 2)
> **Phase:** [Phase_04_Overview.md](../Phase_04_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
