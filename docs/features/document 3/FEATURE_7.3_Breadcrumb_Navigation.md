# Feature 7.3 — Breadcrumb Navigation

| Field | Value |
|---|---|
| Feature ID | 7.3 |
| Title | Breadcrumb Navigation |
| Status | 🟡 Planned |
| Priority | Medium |
| Complexity | Low |
| Estimated Effort | 1 day |
| Dependencies | None |
| Output Files (NEW) | `frontend/components/Breadcrumb.tsx` |
| Files Modified | `frontend/app/layout.tsx`, `frontend/store/settingsStore.ts`, `frontend/app/projects/[id]/page.tsx` |

---

## 1. Document Overview

### 1.1 Problem Statement

The StoryFlow frontend uses a left sidebar with navigation links, but no breadcrumb trail is shown at the top of any page to communicate the user's current location within the app hierarchy. A creator who opens a project editor across multiple browser tabs has no visual confirmation of which project they are viewing without actively reading the page title or the full URL bar. When a user navigates from the timeline editor into a nested sub-view such as the render history panel, all sense of hierarchical position is lost since the sidebar does not update to reflect depth. The browser's back button is the only recovery mechanism, but it does not always reproduce the intended navigation path after a hard page refresh or direct URL visit.

### 1.2 Proposed Solution

A new `Breadcrumb` component is introduced and mounted once in the root layout, ensuring it appears universally above all page content without changes to individual page files. The component reads the current URL path using Next.js's `usePathname()` hook and maps each segment to a human-readable label. Dynamic segments such as project IDs are resolved to the project's actual name by reading from the global Zustand settings store. The breadcrumb renders as a horizontal list of clickable links where every item except the current page is navigable.

- Create `frontend/components/Breadcrumb.tsx` as a client component that reads `usePathname()` and builds a label-and-href pair array
- Map known path segments to labels: `/` → "Home", `/projects` → "Projects", a numeric project ID segment → the current project name from `settingsStore.currentProject.name`
- Render each non-last item as a Next.js `<Link>` component pointing to the accumulated path for that level
- Render the last item (current page) as a plain `<span>` with bold text and no hover or click behavior
- Use a `›` chevron separator character between each item in the trail, wrapped in a non-interactive `<span aria-hidden="true">`
- On mobile screens narrower than 640px (Tailwind `sm:` breakpoint), collapse all items except the last two and replace collapsed items with a `...` indicator
- Mount `<Breadcrumb />` inside `frontend/app/layout.tsx` above the main `{children}` render, separated by a subtle horizontal rule
- Ensure `currentProject` is written to `settingsStore` when the project page loads, so the breadcrumb name resolves correctly on hard refresh

### 1.3 Scope

| In Scope | Out of Scope |
|---|---|
| Breadcrumb displayed on all main app pages | Animated breadcrumb transitions or collapse animations |
| Dynamic resolution of project ID to project name | Third-party breadcrumb library integration |
| Mobile collapse to last two visible levels | Breadcrumb inside modal or dialog overlays |
| Integration directly into root `layout.tsx` | Per-segment icons or emoji in breadcrumb items |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| `frontend/app/layout.tsx` | Root layout wrapping all pages | No breadcrumb component — sidebar + main content only |
| `frontend/components/Sidebar.tsx` | Left sidebar with navigation links | Static links; no active-page or hierarchy indicator |
| `frontend/store/settingsStore.ts` | Zustand global state store | Has `currentProject` field with `id` and `name` |
| `frontend/app/projects/[id]/page.tsx` | Project detail / timeline editor page | Loads project data; must call `setCurrentProject` after data loads |
| `frontend/components/Breadcrumb.tsx` | NEW — breadcrumb trail component | Does not exist yet; must be created |

---

## 2. Flow Diagram

```
User visits URL: /projects/42
        │
        ▼
Breadcrumb mounts in layout.tsx
        │
        ▼
usePathname() → "/projects/42"
        │
        ▼
Split by "/" → ["projects", "42"]
        │
     ┌──┴────────────────────────────────┐
     ▼                                   ▼
Segment "projects"              Segment "42"
Label: "Projects"               isNumeric? Yes
href: "/projects"               → settingsStore.currentProject.name
                                → "The Lost City"
                                → href: "/projects/42"
     │                                   │
     └──────────────────────────────────►│◄── Last item → no link
                                         ▼
Rendered breadcrumb bar:
  Home  ›  Projects  ›  The Lost City
 (link)    (link)         (bold span)

Mobile < 640px:
  ...  ›  Projects  ›  The Lost City
```

---

## 3. Step-by-Step Instructions

### Step 3.1 — Create the Breadcrumb Component File

Create a new file at `frontend/components/Breadcrumb.tsx`. Mark it as a client component by adding `"use client"` as the first line. Import `usePathname` from `next/navigation` and `Link` from `next/link`. Import `useSettingsStore` from the project's canonical Zustand store path. Define a `LABELS` constant map inside the file: it maps known string segments to their display names, for example `"projects"` maps to `"Projects"`, `"settings"` maps to `"Settings"`, and `"library"` maps to `"Library"`. This handles all known static segments. Define the `Breadcrumb` component as the default export.

### Step 3.2 — Build the Breadcrumb Item Array

Inside the `Breadcrumb` function body, call `usePathname()` to obtain the pathname string. Split it by `"/"` and filter out empty strings. Derive the `currentProject` from the Zustand store. Build a `crumbs` array by iterating over the segments: for each index, set `href` to the path joined from `"/"` plus all segments up to and including the current index. Set the `label` using the `LABELS` map if the segment is a known key; if the segment passes `Number.isFinite(Number(segment))`, use `currentProject?.name ?? "Project"` as the label. Prepend a "Home" item with `href: "/"` pointing to the app root.

### Step 3.3 — Render the Trail with Separators

Return a `<nav aria-label="Breadcrumb">` element. Inside it, render an `<ol className="flex items-center gap-1 text-sm flex-wrap">`. Map over the `crumbs` array. For each item that is NOT the last, render an `<li>` containing a `<Link>` with muted text color and hover underline styling. After each non-last item, render a `<li aria-hidden="true">` containing the `›` character in muted text. For the last item in the array (the current page), render an `<li>` with a `<span>` using `font-semibold` and the primary text color, without a link. Wrap the entire nav in a `<div className="px-4 py-2 border-b border-border">`.

### Step 3.4 — Add Mobile Collapse Behavior

Before the render return, add a computed variable `visibleCrumbs`. On desktop (cannot detect in SSR — use a CSS visibility approach instead): in the `<ol>`, apply `hidden sm:flex` to all items before the second-to-last item. Add a separate mobile-only `<li className="sm:hidden">` containing `...` as a non-interactive span. This means on mobile, only the last two full crumb items (plus `...`) are visible. Add a `<li className="sm:hidden" aria-hidden="true">›</li>` separator before the second-to-last visible item on mobile as well. Confirm behavior by testing the component at both desktop (≥ 640px) and mobile (< 640px) viewport widths.

### Step 3.5 — Mount in Root Layout and Update Store

Open `frontend/app/layout.tsx`. Import the `Breadcrumb` component. Inside the JSX, in the main content area wrapper just before `{children}`, add `<Breadcrumb />`. This makes the breadcrumb appear on every page automatically. Then open `frontend/store/settingsStore.ts` and confirm the store has a `setCurrentProject` action that accepts a `{id: number, name: string}` object. If the action is missing, add it. Open `frontend/app/projects/[id]/page.tsx` and locate the `useEffect` where the project API call is made. After the project data resolves, call `setCurrentProject({ id: project.id, name: project.name })` so the store is always populated with the currently loaded project name when the breadcrumb tries to resolve it.

---

## 4. Expected Outcome

1. A breadcrumb trail appears at the top of every page across the entire app, consistently positioned above all page content.
2. On the project list page (`/projects`), the trail reads `Home › Projects` with both items as clickable links.
3. On the timeline editor for "The Lost City" (`/projects/42`), the trail reads `Home › Projects › The Lost City` with the last item as non-interactive bold text.
4. Clicking any non-last breadcrumb item navigates the user to the correct ancestor route.
5. On a mobile viewport below 640px, the breadcrumb collapses to `... › Projects › The Lost City` to prevent layout overflow.
6. When a user loads a project page directly via a bookmarked URL, the project name resolves correctly after the page data loads (may briefly show "Project" as a placeholder before the API response).
7. The breadcrumb adds no layout disruption to existing pages — all existing sidebar and content render correctly with the new component present.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] `Breadcrumb` renders `Home › Projects` when pathname is `/projects`
- [ ] `Breadcrumb` renders `Home › Projects › The Lost City` when pathname is `/projects/42` and `currentProject.name` is "The Lost City"
- [ ] The last breadcrumb item renders as a `<span>` element with no `href` attribute
- [ ] The mobile `...` item is present in the DOM and is marked with `sm:hidden` class
- [ ] When `currentProject` is `null`, the dynamic ID segment renders as the fallback label "Project"

### 5.2 Integration / Manual Tests

- [ ] Navigate to `/projects` in browser — breadcrumb shows `Home › Projects`
- [ ] Click a project card — page navigates and breadcrumb updates to show project name
- [ ] Click `Home` in the breadcrumb — navigates to the app home/dashboard
- [ ] Click `Projects` in the breadcrumb while on the editor — navigates back to the project list
- [ ] Load the editor page directly via URL — breadcrumb shows correct project name after data loads
- [ ] Resize browser below 640px — breadcrumb collapses to last two items with `...`

### 5.3 Regression Tests

- [ ] All existing page layouts render correctly with the breadcrumb inserted in root layout
- [ ] Sidebar navigation links continue to function; no layout shift observed
- [ ] TypeScript compilation (`tsc --noEmit`) reports zero new errors after adding the component

---

## 6. Notes for AI Agent

- Use `usePathname()` from `next/navigation` (the App Router API). Do NOT use `useRouter().pathname` — that is the Pages Router API and does not work in the app directory.
- Mark the component with `"use client"` at top because `usePathname()` is a client-side hook and cannot be used in Server Components.
- Detect a dynamic project ID segment by testing `Number.isFinite(Number(segment))` — if the result is `true`, treat it as a project ID that needs name resolution.
- If `currentProject` is not yet loaded (null or undefined), render a skeleton placeholder (e.g., a `div` with `w-20 h-4 bg-muted animate-pulse rounded`) in place of the project name to prevent a blank breadcrumb during loading.
- Test the breadcrumb carefully on the settings page and any page that does not involve a project — numeric-looking route params must not accidentally trigger the project-name resolution branch for non-project routes.
