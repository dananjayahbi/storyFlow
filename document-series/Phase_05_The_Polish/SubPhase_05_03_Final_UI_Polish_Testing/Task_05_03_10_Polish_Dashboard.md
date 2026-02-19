# Task 05.03.10 — Polish Dashboard

## Layer 3 Task Document

---

| **Field**              | **Value**                                                                                      |
| ---------------------- | ---------------------------------------------------------------------------------------------- |
| **Task ID**            | 05.03.10                                                                                       |
| **Task Name**          | Polish Dashboard                                                                               |
| **Sub-Phase**          | 05.03 — Final UI Polish & Testing                                                              |
| **Phase**              | Phase 05 — The Polish                                                                          |
| **Layer**              | Layer 3 (Task Document)                                                                        |
| **Status**             | Not Started                                                                                    |
| **Estimated Complexity** | Medium                                                                                       |
| **Parent Document**    | [SubPhase_05_03_Overview.md](./SubPhase_05_03_Overview.md) (Layer 2)                           |
| **Dependencies**       | Task 05.03.07 (EmptyState for empty dashboard), Task 05.03.06 (ToastProvider for action toasts)|
| **Output Files**       | `frontend/components/Dashboard.tsx` (MODIFIED)                                                 |

---

## Objective

Upgrade the project Dashboard from a functional list into a polished, production-quality project management interface with a responsive card grid layout, sort controls, search/filter capabilities, loading skeleton states, cover image thumbnails, status badges, and relative time display.

---

## Instructions

### Step 1 — Convert to Responsive Card Grid

Replace the existing project listing with a responsive card grid layout. Use Tailwind CSS grid utilities with responsive breakpoints: a single column on mobile (default), two columns on medium screens (`md:grid-cols-2`), and three columns on large screens (`lg:grid-cols-3`). Each project card should have consistent height, a subtle border, rounded corners, and a hover shadow elevation effect. The grid should fill available space and handle edge cases like a single project or an odd number of projects gracefully.

### Step 2 — Add Sort Controls

Add a sort control bar above the card grid with two sort options: sort by creation date (newest first as default, with toggle to oldest first) and sort by title (alphabetical A–Z and Z–A). Implement sorting as a client-side operation on the already-fetched project list from the Zustand store. Use a dropdown select or a set of toggle buttons for the sort mode. Persist the selected sort preference in component state (no need to persist across page reloads).

### Step 3 — Add Search and Filter Bar

Add a text input search bar alongside the sort controls that filters the displayed projects by title. The filter should be case-insensitive and apply in real-time as the user types (no submit button needed). When the search term matches no projects, display the EmptyState component with an appropriate "No matching projects" message rather than an empty grid. Include a small clear button (X icon) inside the search input to reset the filter.

### Step 4 — Add Loading Skeleton States

When the project list is being fetched from the backend (initial page load or refresh), display a grid of skeleton placeholder cards instead of a blank space or spinner. Each skeleton card should match the dimensions of a real project card and use `animate-pulse` on rectangular placeholder blocks for the title, description snippet, status badge, and timestamp areas. Show the same number of skeleton cards as the grid column count (e.g., three skeletons on large screens, two on medium) to fill the first row.

### Step 5 — Add Cover Image Thumbnails

Each project card should display a small cover image thumbnail at the top of the card. If the project has a rendered video with a generated thumbnail, use that. If not, display a gradient placeholder or a muted-color rectangle with a Film/Video icon centered inside it. The thumbnail area should have a fixed aspect ratio (16:9 recommended) and use `object-cover` to prevent distortion. This visual element provides instant recognition when scanning the dashboard.

### Step 6 — Add Status Badges

Display a small status badge on each project card indicating the project's current state: "Draft" (muted/gray), "In Progress" (amber/yellow), "Rendered" (green/success), "Error" (red/destructive). The badge should be positioned in the top-right corner of the card overlapping the thumbnail area, or inline below the title. Derive the status from the project's segment states — if all segments are rendered, the project is "Rendered"; if any segment has an error, the project is "Error"; if any segment is processing, "In Progress"; otherwise, "Draft".

### Step 7 — Add Relative Time Display

Display the project's last-modified timestamp as a relative time string ("2 minutes ago", "3 hours ago", "Yesterday", "5 days ago") rather than an absolute date. Implement a simple relative time formatting utility function or use a lightweight library. Update the displayed time on component mount — it does not need to live-update while the page is open. Show the absolute date as a tooltip on hover for precision.

---

## Expected Output

A polished Dashboard component with a responsive card grid, sort controls (date/title), a search/filter bar with real-time filtering, loading skeletons during data fetch, cover image thumbnails (real or placeholder), status badges derived from segment states, and relative time display for last-modified timestamps.

---

## Validation

- [ ] Card grid is responsive: 1 column on mobile, 2 on medium, 3 on large screens.
- [ ] Sort by date (newest/oldest) and by title (A–Z / Z–A) works correctly.
- [ ] Search bar filters projects by title in real-time, case-insensitive.
- [ ] Empty search results show the EmptyState component.
- [ ] Loading skeletons appear during initial data fetch.
- [ ] Skeleton cards match real card dimensions and use `animate-pulse`.
- [ ] Cover image thumbnails display for projects with rendered output.
- [ ] Placeholder thumbnails display for projects without rendered output.
- [ ] Status badges correctly reflect project state (Draft, In Progress, Rendered, Error).
- [ ] Relative time display shows human-readable timestamps ("2 hours ago").
- [ ] Hover tooltip on relative time shows absolute date.

---

## Notes

- The Dashboard is the first thing users see when they open StoryFlow. Visual polish here sets the tone for the entire application experience.
- Sort and search are client-side operations only — the backend returns all projects in a single API call. This is acceptable because StoryFlow is a local single-user application and the project count will remain small (typically under 50).
- The status badge logic is a derived computation. It should not be stored in the database; instead, compute it on the fly from the segment states. Consider extracting this into a utility function for testability.

---

> **Parent:** [SubPhase_05_03_Overview.md](./SubPhase_05_03_Overview.md) (Layer 2)
> **Phase:** [Phase_05_Overview.md](../Phase_05_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
