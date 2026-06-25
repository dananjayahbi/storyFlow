# Feature 3.4 — Image Fit Preview (Crop Overlay)

| Field | Value |
|---|---|
| Feature ID | 3.4 |
| Title | Image Fit Preview — Ken Burns Crop Overlay |
| Status | 🟡 Planned |
| Priority | High |
| Complexity | Medium |
| Estimated Effort | 3–5 days |
| Dependencies | Project `resolution_width`, `resolution_height`, `zoom_intensity` fields must be populated |
| Output Files (NEW) | `frontend/components/ImageFitPreview.tsx` |
| Files Modified | `frontend/components/ImageUploader.tsx`, `frontend/components/SegmentCard.tsx`, `frontend/app/projects/[id]/page.tsx` |

---

## 1. Document Overview

### 1.1 Problem Statement

When a user uploads an image to a segment in the StoryFlow editor, the image is displayed in the `ImageUploader` component at its full natural dimensions with no indication of how it will be cropped during the final render. The Ken Burns animation engine in `ken_burns.py` computes a start and end crop rectangle based on the project's output resolution and zoom intensity settings. A user uploading a wide landscape photograph for a 9:16 portrait project has no way to see which narrow vertical slice of that image will actually appear in the video. This mismatch between the editor preview and the rendered output causes frequent re-renders and wasted time, especially with multi-minute projects. Without a visual crop guide, users cannot confidently position their images or verify that the subject matter sits within the visible animation zone.

### 1.2 Proposed Solution

Introduce an `ImageFitPreview` component that renders a translucent overlay on top of the displayed image, showing two crop rectangles — one representing the Ken Burns start frame and one representing the end frame. The overlay is calculated entirely on the client side using JavaScript math against the project's known resolution and zoom settings. No backend requests are required for this feature.

Key implementation points:

- Create `frontend/components/ImageFitPreview.tsx` as a self-contained presentational component that accepts the image element dimensions, target aspect ratio, and zoom intensity as props.
- Compute the start crop box as a rectangle occupying the full image width scaled to the target aspect ratio (zoom factor of approximately 1.0).
- Compute the end crop box as a smaller centered rectangle using the project's `zoom_intensity` field to derive the zoom factor (typically in the range 1.08–1.12).
- Render the start crop box with a solid indigo border at two pixels, and add a small "Start" label badge in the top-left corner of the rectangle.
- Render the end crop box with a dashed emerald border at two pixels, and add a small "End" label badge to distinguish it from the start box.
- Implement a "Show Crop Overlay" toggle button that appears on hover over the image in `ImageUploader.tsx`. A single click freezes the overlay visible; a second click dismisses it.
- Pass project resolution and zoom intensity down from the project page through `SegmentCard` into `ImageUploader` as additional props so the crop math is always in sync with the project configuration.
- Ensure the overlay boxes recompute whenever the displayed image dimensions change — for example, when the browser window is resized.

### 1.3 Scope

| Category | Item |
|---|---|
| In Scope | Client-side crop overlay rendering in the segment editor |
| In Scope | Start and end Ken Burns viewport visualization using project settings |
| In Scope | Hover-activated toggle button to show or hide the overlay |
| In Scope | Responsive recomputation when image display size changes |
| Out of Scope | Backend API changes — no server calls are needed |
| Out of Scope | Interactive dragging or repositioning of the crop boxes |
| Out of Scope | Overlay for the audio waveform or subtitle timing editors |
| Out of Scope | Exporting or saving the overlay as a reference image |

### 1.4 Key Files Reference

| File | Role |
|---|---|
| `frontend/components/ImageUploader.tsx` | Hosts the image display and will receive the overlay toggle button; passes image dimensions to the preview component |
| `frontend/components/ImageFitPreview.tsx` | New component — renders the two crop rectangle overlays as absolutely positioned divs |
| `frontend/components/SegmentCard.tsx` | Parent of `ImageUploader`; must be updated to pass `resolutionWidth`, `resolutionHeight`, and `zoomIntensity` props down |
| `frontend/app/projects/[id]/page.tsx` | Project page that loads the project object; provides resolution and zoom settings to segment cards |
| `backend/core_engine/ken_burns.py` | Reference for understanding how zoom factor is derived from `zoom_intensity` — not modified by this feature |
| `frontend/store/` | Zustand store — may be used to read project settings in the component tree without deep prop drilling |
| `frontend/types/` | TypeScript type definitions — may require a new `CropOverlayProps` type or extension of `ProjectSettings` |

---

## 2. Flow Diagram

```
User opens project page (resolution_width, resolution_height, zoom_intensity loaded)
        |
        v
SegmentCard renders for each segment
        |
        v
ImageUploader receives image + project resolution props
        |
        v
User hovers over image
        |
        v
"Show Crop Overlay" button appears (absolute positioned, top-right corner)
        |
        v
User clicks toggle button
        |
        v
ImageFitPreview component mounts over the image
        |
        +-----------> Compute targetAspectRatio = resolutionWidth / resolutionHeight
        |
        +-----------> Compute startCropWidth = displayedImageWidth (zoom ~1.0)
        |              startCropHeight = startCropWidth / targetAspectRatio
        |
        +-----------> Compute endZoomFactor from zoom_intensity (e.g. 1.0 + intensity * 0.12)
        |              endCropWidth = startCropWidth / endZoomFactor
        |              endCropHeight = endCropWidth / targetAspectRatio
        |
        +-----------> Center both boxes horizontally and vertically over the image
        |
        v
Render: solid indigo border box (Start) + dashed emerald border box (End)
        |
        v
User clicks toggle again → overlay hidden
```

---

## 3. Step-by-Step Instructions

### Step 1 — Extend project props through the component tree

File: `frontend/app/projects/[id]/page.tsx`
Function/Component: Project page render function
What to change: When mapping over segments to render `SegmentCard` components, pass `resolutionWidth`, `resolutionHeight`, and `zoomIntensity` as additional props sourced from the loaded project object. Ensure these values are read from the project API response and are typed correctly. If they are possibly undefined, provide sensible default fallbacks (for example 1920 width, 1080 height, and 0.5 intensity).

### Step 2 — Forward crop props in SegmentCard

File: `frontend/components/SegmentCard.tsx`
Function/Component: `SegmentCard` component props interface and JSX return
What to change: Add `resolutionWidth: number`, `resolutionHeight: number`, and `zoomIntensity: number` to the `SegmentCardProps` interface. Forward all three values as props when rendering the `ImageUploader` component inside the card. No other logic changes are required in this file.

### Step 3 — Add hover toggle state to ImageUploader

File: `frontend/components/ImageUploader.tsx`
Function/Component: `ImageUploader` component
What to change: Accept the three new resolution and zoom props. Add a boolean state variable `overlayVisible` (default false). On the wrapper div containing the image, add `onMouseEnter` and `onMouseLeave` handlers to show and hide a "Show Crop Overlay" button. The button's click handler toggles `overlayVisible`. When `overlayVisible` is true, render the `ImageFitPreview` component directly after the image element inside the same relative-positioned wrapper.

### Step 4 — Create the ImageFitPreview component

File: `frontend/components/ImageFitPreview.tsx`
Function/Component: New `ImageFitPreview` functional component
What to change: Create the file from scratch. Accept props for `imageWidth`, `imageHeight`, `resolutionWidth`, `resolutionHeight`, and `zoomIntensity`. Compute `targetAspectRatio`, `startCropWidth`, `startCropHeight`, `endZoomFactor`, `endCropWidth`, and `endCropHeight` as plain numeric computations. Derive pixel offsets to horizontally and vertically center each crop box. Render two absolutely positioned divs — the first with a solid indigo border and a "Start" badge, the second with a dashed emerald border and an "End" badge. The component's root element should be a `position: absolute` full-bleed div that does not intercept mouse events (set `pointer-events: none` so the toggle button remains clickable).

### Step 5 — Measure displayed image dimensions

File: `frontend/components/ImageUploader.tsx`
Function/Component: `ImageUploader` component
What to change: Attach a `ref` to the image element and use a `ResizeObserver` (or a `useEffect` with `getBoundingClientRect`) to read the rendered width and height of the image element after it loads. Store these as state variables `displayedWidth` and `displayedHeight`. Pass them into `ImageFitPreview` as `imageWidth` and `imageHeight`. Re-measure whenever the image `src` changes or the window resizes.

### Step 6 — TypeScript types and TailwindCSS polish

File: `frontend/types/` (new or existing type file as appropriate)
Function/Component: Type definitions
What to change: Define a `CropOverlayProps` interface with the five numeric fields. Ensure all components have accurate TypeScript prop types. Apply TailwindCSS utility classes for the overlay button styling — use `opacity-0 group-hover:opacity-100 transition-opacity` pattern on the button so it fades in on hover. Add `rounded-sm text-xs font-semibold px-1` classes to the Start and End badge labels within `ImageFitPreview`.

---

## 4. Expected Outcome

1. When a user opens any project and views a segment's image in the editor, hovering over the image reveals a "Show Crop Overlay" button in the top-right corner.
2. Clicking the button freezes the overlay visible — two colored rectangles appear on top of the image marking the start and end Ken Burns viewport boundaries.
3. The solid indigo rectangle (labeled "Start") correctly represents the initial frame the animation begins from, spanning the full width of the image scaled to the output aspect ratio.
4. The dashed emerald rectangle (labeled "End") is visibly smaller and centered, representing the zoomed-in end frame derived from the project's zoom intensity setting.
5. For a landscape image in a portrait project, the two boxes are visually taller than they are wide and clearly indicate the narrow vertical strip of the photo that will appear in the final video.
6. The overlay boxes update immediately when the user switches to a different project with different resolution settings — no page reload required.
7. The overlay can be dismissed by clicking the toggle button a second time, returning the image to its normal unobstructed display.
8. No network requests are triggered by the overlay feature — it operates entirely from data already present in the loaded project state.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] `ImageFitPreview` unit test: given a 1920×1080 landscape image with a 9:16 target ratio and 0.5 zoom intensity, the start crop height equals the full image width divided by 0.5625 and the end crop box is smaller than the start.
- [ ] `ImageFitPreview` unit test: given a square image and a 1:1 target ratio, both crop boxes are square and the end box is centered within the start box.
- [ ] `ImageFitPreview` unit test: zoom intensity of 0.0 should produce start and end boxes of equal size (no zoom change).
- [ ] `ImageUploader` unit test: the overlay toggle button is not rendered when `overlayVisible` is false and no hover event has occurred.
- [ ] `ImageUploader` unit test: clicking the toggle button sets `overlayVisible` to true; clicking it again sets it back to false.

### 5.2 Integration / Manual Tests

- [ ] Open a project with 1920×1080 resolution — verify the indigo Start box spans the full image width and the emerald End box is inset and centered.
- [ ] Open a project with 1080×1920 (portrait) resolution and upload a wide landscape photo — verify both boxes appear as tall narrow rectangles, confirming the portrait crop zone.
- [ ] Resize the browser window while the overlay is active — verify both boxes recompute to match the new displayed image size within one second.
- [ ] Verify the overlay boxes do not interfere with the image upload controls — clicking the file picker or drag-and-drop zone while overlay is visible still works correctly.
- [ ] Switch between two segments in the same project — confirm the overlay state resets and the button reappears cleanly on each segment's image.
- [ ] Verify the feature degrades gracefully: if `resolutionWidth` or `resolutionHeight` is missing, fall back to 16:9 defaults and log a console warning rather than crashing.

### 5.3 Regression Tests

- [ ] Existing image upload functionality in `ImageUploader.tsx` is unaffected — files can still be selected, previewed, and cleared after this feature is added.
- [ ] `SegmentCard` renders correctly when `resolutionWidth`, `resolutionHeight`, and `zoomIntensity` are all undefined (backward compatibility with any cached or legacy project data).
- [ ] The project page loads and renders all segments within the same performance budget as before — no noticeable slowdown introduced by the resize observer or overlay math.

---

## 6. Notes for AI Agent

- The crop math must mirror the logic in `backend/core_engine/ken_burns.py` as closely as possible. Read that file before implementing the client-side formula to ensure the "End" crop box reflects the actual rendered output precisely.
- Do not use any inline style objects that conflict with TailwindCSS purge — use Tailwind utility classes wherever possible, reserving calculated pixel values (top, left, width, height) for the crop box positioning only, applied as CSS custom properties or inline style width/height.
- The `pointer-events: none` rule on the `ImageFitPreview` root is critical — if it is omitted, the overlay will block the file input click event and the upload button will stop working.
- Consider whether the project settings should be read from the Zustand store directly inside `ImageFitPreview` rather than passed as props — either approach is acceptable, but the store approach reduces the prop drilling chain and is preferred if the store already holds the active project.
- All numeric crop calculations should be wrapped in a dedicated pure utility function (for example `computeKenBurnsCropBoxes`) placed in `frontend/lib/` so it can be unit-tested independently from the React component.

---

*Document created: 2026-03-10 | Feature area: Frontend / Editor UX | Phase 03 — The Polish*
