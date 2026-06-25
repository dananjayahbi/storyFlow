# Feature 1.3 — Safe Zone Overlays

| Field | Value |
|---|---|
| Feature ID | 1.3 |
| Title | Safe Zone Overlays |
| Status | 🟡 Planned |
| Priority | Medium |
| Complexity | Low |
| Estimated Effort | 1–2 days |
| Dependencies | Feature 1.1 (Platform Preset Profiles — provides target_platform on Project model) |
| Output Files (NEW) | frontend/constants/safeZones.ts, frontend/components/SafeZoneOverlay.tsx |
| Files Modified | frontend/app/projects/[id]/page.tsx, frontend/components/SegmentCard.tsx |

---

## 1. Document Overview

### 1.1 Problem Statement

Different social media platforms overlay their own UI elements — navigation bars, share buttons, caption regions, username handles, and engagement widgets — on top of substantial portions of the video frame, permanently obscuring content that the creator placed in those regions.
On TikTok specifically, the bottom approximately fifteen percent of the video frame is consistently covered by the platform's own caption text, profile avatar, user handle, song title, and interaction buttons, meaning any subtitle text or important visual subject that the creator placed near the bottom of the frame will be hidden from viewers without any warning.
On YouTube Shorts, Instagram Reels, and similar short-form surfaces, the bottom ten to twelve percent and various edge areas are similarly obstructed by native UI layers, and these overlap zones differ between platforms in their exact dimensions and shapes.
Currently StoryFlow has no mechanism to warn creators during the editing phase that their subtitles, lower-third labels, or key visual subjects are positioned in regions that will be hidden by the destination platform's own interface, meaning creators only discover the problem after publishing and receiving viewer feedback.

### 1.2 Proposed Solution

The Safe Zone Overlays feature adds a visual guide system to the image preview area within the project editor, allowing creators to toggle a set of semi-transparent colored overlays that highlight exactly which screen regions each platform's native UI will cover. The overlays are rendered purely in the browser as absolutely-positioned CSS elements layered over the image preview, and they have absolutely zero effect on the actual rendered MP4 output — they are presentation aids only. The system reads the current project's `target_platform` value and automatically selects the correct safe zone dimensions without requiring the creator to manually configure anything. When no platform is selected, the system falls back to showing a conservative generic safe zone that represents the intersection of the strictest restrictions across all supported platforms, giving a universally safe content area. Each overlay zone includes a short text label explaining what platform UI element occupies that region, helping creators understand not just that the area is dangerous but specifically why it should be avoided.

- A new TypeScript constants file maps each platform key to an object defining the unsafe percentage margins on each edge — top, bottom, left, and right — of the video frame.
- A new `SafeZoneOverlay` React component accepts the platform key and a boolean visibility toggle as props, and renders absolutely-positioned semi-transparent divs over the parent image container.
- Each overlay div is styled with a red fill at thirty percent opacity and a solid red border to distinguish it clearly from the underlying image content.
- Short italic text labels are rendered inside each overlay region, naming the platform UI element that occupies the zone, using a small font size and reduced opacity so they inform without dominating.
- A toggle button is added to the project editor toolbar or image preview area header, allowing the creator to show or hide the overlays with a single click.
- The toggle state is stored in local React component state and is NOT persisted to the backend — it is a session-level view preference, not a project setting.
- A fallback "generic safe zone" overlay is rendered as a centered eighty-percent bounding box when no platform is selected, representing the conservative intersection of all platform safe areas.

### 1.3 Scope

| Category | Item |
|---|---|
| In Scope | Creating the `safeZones.ts` constants file with per-platform overlay dimensions for all eight platforms |
| In Scope | Building the `SafeZoneOverlay.tsx` component that renders the CSS overlays on top of the image preview |
| In Scope | Adding the toggle button to the project editor and wiring it to show/hide the overlay component |
| In Scope | Rendering text labels inside each overlay zone describing the covering platform UI element |
| Out of Scope | Modifying the rendered video output in any way based on safe zone data |
| Out of Scope | Automatically repositioning or cropping subtitle text to avoid unsafe zones |
| Out of Scope | Persisting the safe zone toggle state to the database or across browser sessions |
| Out of Scope | Rendering safe zone overlays in the segment thumbnail grid view on the project list page |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| frontend/app/projects/[id]/page.tsx | Project editor page containing the image preview area and toolbar | Exists; has image preview but no overlay toggle or overlay rendering |
| frontend/components/SegmentCard.tsx | Individual segment card component that renders segment image thumbnails | Exists; renders image but has no overlay layer support |
| frontend/constants/safeZones.ts | Maps platform keys to unsafe margin percentages (top, bottom, left, right) | Does not exist yet — must be created as part of this feature |
| frontend/components/SafeZoneOverlay.tsx | React component rendering the colored overlay divs with text labels | Does not exist yet — must be created as part of this feature |
| frontend/constants/platformPresets.ts | Provides the PlatformKey type shared between preset and safe zone constants | Must exist (created in Feature 1.1); SafeZoneOverlay imports PlatformKey from here |

---

## 2. Flow Diagram

    Project editor page loads
                |
                v
    Page reads project.target_platform from API response
    (e.g., "tiktok")
                |
                v
    SafeZoneOverlay component receives:
      - platformKey = "tiktok"
      - visible = false (default toggle state)
                |
         User clicks "Show Safe Zones" button
                |
                v
    Toggle state flips to true in React local state
                |
                v
    SafeZoneOverlay renders with visible=true
                |
                v
    Component reads SAFE_ZONES["tiktok"]
    --> { top: 3, bottom: 15, left: 5, right: 5 }
                |
                v
    Four absolutely-positioned divs rendered over image:
      Top div    -->  height: 3%  of frame, red 30% opacity
      Bottom div -->  height: 15% of frame, red 30% opacity
      Left div   -->  width: 5%   of frame, red 30% opacity
      Right div  -->  width: 5%   of frame, red 30% opacity
                |
                v
    Each div renders label text:
      Bottom: "TikTok: captions + buttons area"
      Left:   "TikTok: side chrome"
                |
                v
    User clicks "Hide Safe Zones" button
                |
                v
    Toggle state flips back to false
    Overlay divs unmounted / set to display:none

---

## 3. Step-by-Step Instructions

### Step 1 — Create the Safe Zones Constants File

Create a new file at `frontend/constants/safeZones.ts` — this file should be a pure data module with no React imports, no side-effect code, and no dynamic logic.
Begin by importing the `PlatformKey` type from `frontend/constants/platformPresets.ts` so that the safe zone map benefits from the same union type that the platform preset system already uses, ensuring that both constant registries remain synchronized on the list of valid platform keys.
Define and export an interface named `SafeZone` with four numeric properties: `top`, `bottom`, `left`, and `right`, each representing the percentage of the frame's total height or width that the corresponding platform UI element covers along that edge.
Define and export a `SAFE_ZONES` constant typed as a `Partial<Record<PlatformKey, SafeZone>>` and populate it with entries for all eight platforms using these values: TikTok — bottom 15, left 5, right 5, top 3; YouTube Shorts — bottom 10, top 5, left 0, right 0; Instagram Reel — bottom 12, top 3, left 2, right 2; Instagram Post — bottom 8, top 2, left 0, right 0; YouTube — bottom 5, top 2, left 0, right 0; Facebook — bottom 5, top 2, left 0, right 0; Twitter/X — bottom 6, top 3, left 0, right 0; LinkedIn — bottom 5, top 2, left 0, right 0.
Also export a `GENERIC_SAFE_ZONE` constant representing the conservative fallback used when no platform is selected — define this as a centered box by setting all four edges to 15 percent, which represents the intersection of the strictest platform restrictions.
Finally, export a `SAFE_ZONE_LABELS` constant typed as `Record<string, Partial<Record<"top" | "bottom" | "left" | "right", string>>>` mapping each platform key and edge to a short description of what UI element covers that edge, for example `{ tiktok: { bottom: "TikTok: captions, handle, buttons", left: "TikTok: side chrome" } }`.

### Step 2 — Build the SafeZoneOverlay Component

Create a new file at `frontend/components/SafeZoneOverlay.tsx`.
Define the component's props interface with three fields: `platformKey` typed as `PlatformKey` or an empty string, `visible` typed as boolean, and `containerWidth` and `containerHeight` typed as numbers representing the pixel dimensions of the image preview container, which are needed to compute absolute pixel positions from percentage values.
Inside the component, begin by looking up the active safe zone data: if `platformKey` is a non-empty string and is present in `SAFE_ZONES`, use the platform-specific entry; if `platformKey` is empty or not found, fall back to `GENERIC_SAFE_ZONE`.
Compute the pixel values for each edge by multiplying the container dimension by the percentage divided by one hundred — for example, `bottomHeight = containerHeight * safeZone.bottom / 100`.
Render a wrapping `div` styled with `position: absolute`, `inset: 0`, `pointer-events: none`, and `z-index: 10` so that the overlay sits on top of the image without blocking user interaction with any underlying controls, and conditionally render this wrapper only when the `visible` prop is true.
Inside the wrapper, render up to four child `div` elements — one per edge with a non-zero value — each styled with `position: absolute`, a `backgroundColor` of `rgba(220, 20, 20, 0.30)`, a `border` in solid red at one pixel, and an appropriate combination of `top`, `bottom`, `left`, `right`, `width`, and `height` style properties derived from the computed pixel values.
Inside each overlay div, render a small `span` element that displays the corresponding label from `SAFE_ZONE_LABELS` using a font size of eleven pixels, italic style, white color, and an opacity of 0.85, positioned at the inner edge of the overlay so it reads clearly against the red background.

### Step 3 — Integrate the Overlay into the Project Editor Page

Open `frontend/app/projects/[id]/page.tsx` and locate the section of the component that renders the image preview area for the currently selected segment.
Add two new pieces of local state to the component: a boolean `showSafeZones` initialized to `false`, and a `containerRef` using `useRef<HTMLDivElement>(null)` attached to the image preview container div so that the container's current pixel dimensions can be read via `containerRef.current.getBoundingClientRect()`.
Add a toolbar button or an icon-button labeled "Safe Zones" near the image preview header row; this button should toggle `showSafeZones` between true and false on each click, and visually indicate its active state by changing its background or border styling when the overlay is currently shown.
Wrap the existing `img` element inside a `div` that has `position: relative` and the `containerRef` attached, then place the `SafeZoneOverlay` component as a sibling after the `img` inside that wrapper, passing `platformKey={project.target_platform}`, `visible={showSafeZones}`, and the container dimensions derived from the ref.
Add a short informational tooltip or subtitle text near the toggle button that reads "Shows which regions each platform's UI will cover on published videos" so first-time users immediately understand the feature's purpose without needing to consult documentation.

### Step 4 — Handle Resize and Dynamic Container Dimensions

The `SafeZoneOverlay` component needs accurate container dimensions to convert percentage safe zone values into correct pixel positions, and the container dimensions can change if the user resizes their browser window or the editor panel is resized.
In `frontend/app/projects/[id]/page.tsx`, add a `ResizeObserver` within a `useEffect` hook that observes the image preview container referenced by `containerRef` and updates a `[containerWidth, setContainerWidth]` and `[containerHeight, setContainerHeight]` state pair whenever the container size changes.
Pass the current `containerWidth` and `containerHeight` values from state down to the `SafeZoneOverlay` component as props so that the overlay's pixel calculations always reflect the most recent layout.
Inside the `useEffect` that creates the `ResizeObserver`, return a cleanup function that calls `resizeObserver.disconnect()` to prevent memory leaks when the project editor component unmounts.
Read the initial dimensions inside a `useLayoutEffect` that runs after the first render so that the overlay is positioned correctly even before any resize event fires, avoiding a flash of incorrectly-placed overlays on initial page load.

### Step 5 — Connect Safe Zones to the SegmentCard Thumbnail View

Open `frontend/components/SegmentCard.tsx` and review the current structure of the component — it renders a thumbnail image of the segment along with text content and control buttons.
Add an optional boolean prop named `showSafeZones` and an optional `platformKey` prop to the `SegmentCard` component's props interface, both defaulting to false and empty string respectively, so that the component remains fully backward compatible when called without these props from any context outside the project editor.
When both `showSafeZones` is true and `platformKey` is non-empty, wrap the thumbnail image in a `position: relative` container and render a simplified version of the `SafeZoneOverlay` component as an overlay; use a reduced z-index so it does not interfere with the segment card's hover controls.
In `frontend/app/projects/[id]/page.tsx`, pass the current `showSafeZones` boolean and `project.target_platform` down to each `SegmentCard` instance rendered in the segment list so that the safe zone state propagates consistently to both the large single-image preview and the segment thumbnail strip.
Add a brief comment in the `SegmentCard` component clarifying that the safe zone overlay is purely cosmetic and has no connection to the rendered video output, so future developers never attempt to wire this component to the render pipeline.

---

## 4. Expected Outcome

1. When a creator opens the project editor for a TikTok-targeted project and clicks the "Safe Zones" button, red semi-transparent bands immediately appear over the bottom fifteen percent and side five percent of the image preview, clearly showing the platform's danger zones.
2. Each overlay band displays a short italic label such as "TikTok: captions, handle, buttons" so the creator understands which platform UI element is responsible for the restriction without needing any external reference.
3. Clicking the "Safe Zones" button a second time immediately hides all overlay elements and returns the image preview to its original unobstructed state.
4. For projects with no platform selected, clicking the toggle shows a single conservative eighty-percent centered bounding box in a neutral color, communicating the universally safe content region without asserting any platform-specific information.
5. The rendered MP4 output file for any project is completely unchanged regardless of whether the safe zone toggle was enabled or disabled during editing, confirming that the feature is a non-destructive visual guide only.
6. The safe zone overlays scale correctly when the browser window is resized or when the editor panel layout changes, always covering the correct proportional regions of the image preview without positional drift.
7. The `SegmentCard` thumbnail strip also reflects the safe zone overlay when the toggle is active, giving creators an inline view of which segments have critical content placed in dangerous zones without requiring them to open each segment preview individually.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] Test that `SAFE_ZONES` in `safeZones.ts` contains valid entries for all eight platform keys and that every populated entry has at least a `bottom` value greater than zero.
- [ ] Test that `SafeZoneOverlay` renders no overlay divs when the `visible` prop is false, regardless of what `platformKey` is provided.
- [ ] Test that `SafeZoneOverlay` renders exactly the correct number of non-zero-edge overlay divs for the "tiktok" platform key (bottom, left, right, and top edges are all non-zero for TikTok).
- [ ] Test that when `platformKey` is an empty string, the component falls back to rendering the `GENERIC_SAFE_ZONE` overlay instead of throwing an undefined access error.
- [ ] Test that the `GENERIC_SAFE_ZONE` constant has equal values on all four edges and that all four values are greater than ten percent, confirming it represents a meaningfully conservative restriction.

### 5.2 Integration / Manual Tests

- [ ] Open a project with target_platform set to "tiktok", click the Safe Zones toggle, and visually verify that the bottom overlay covers approximately the lower fifteen percent of the image preview area at the expected red opacity.
- [ ] Open a project with target_platform set to "youtube", toggle safe zones on, and verify that only a thin bottom band and an even thinner top band appear — confirming that the platform-specific values differ visibly from TikTok.
- [ ] Open a project with no target_platform set, toggle safe zones on, and verify that the generic centered bounding box appears as a border around roughly the inner eighty percent of the image area.
- [ ] Resize the browser window while safe zones are enabled and verify that the overlay bands reposition and rescale to continue covering the correct proportional regions of the image preview.
- [ ] Trigger a render on a project where safe zones were toggled on during editing and confirm that the output video file has no red overlay artifacts burned into it.
- [ ] Enable safe zones in the project editor and scroll through the segment list to confirm that all SegmentCard thumbnails also display the overlay consistently, and that disabling the toggle removes overlays from all cards simultaneously.

### 5.3 Regression Tests

- [ ] Confirm that the project editor page loads and renders without any JavaScript errors or console warnings for projects where `target_platform` is null, undefined, or an empty string arriving from the API response.
- [ ] Confirm that none of the existing backend API endpoints are impacted by this feature, since it is entirely a frontend-only change — all existing API response shapes should remain identical.
- [ ] Confirm that the `SegmentCard` component continues to function correctly in any context where it is rendered without the `showSafeZones` and `platformKey` props, including in any test fixtures or Storybook stories that instantiate it with only its pre-existing props.

---

## 6. Notes for AI Agent

- The overlay divs must carry `pointer-events: none` in their inline styles or Tailwind class to prevent them from accidentally intercepting mouse clicks intended for the image preview or segment card controls beneath them; forgetting this is the single most common usability bug with absolutely-positioned overlays and leads to confusing reports where buttons appear clickable but do not respond.
- Percentage values in `SAFE_ZONES` describe the unsafe margin as a fraction of the total frame dimension, not the safe region; when computing pixel positions, `bottomHeight = containerHeight * safeZone.bottom / 100` gives the height of the bottom danger strip, and the bottom danger div should be positioned with `bottom: 0` and `height: bottomHeight` — a common inversion error is to instead compute `top = containerHeight - bottomHeight` and render from the top, which produces the same visual result but is semantically confusing.
- The `ResizeObserver` added to track the image preview container must be cleaned up inside the `useEffect` return callback; failing to do so will cause a memory leak warning in development and potential issues in long-running browser sessions where the project editor is opened and closed many times without a full page refresh.
- When building the `SafeZoneOverlay` component, avoid computing the pixel dimensions inside the component itself using a `ref` internal to the overlay — instead, receive the dimensions as props from the parent, because the image preview container's ref lives in the parent `page.tsx` component, and having two observers for the same container would be wasteful.
- Safe zone values for social media platforms change periodically as platforms update their UI; add a comment in `safeZones.ts` specifying the approximate date these values were last verified so future maintainers know when a re-check against current platform documentation is warranted.
