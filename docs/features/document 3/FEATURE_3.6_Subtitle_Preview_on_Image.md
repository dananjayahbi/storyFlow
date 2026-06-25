# Feature 3.6 — Subtitle Preview on Image

| Field | Value |
|---|---|
| Feature ID | 3.6 |
| Title | Subtitle Overlay Preview on Segment Image |
| Status | 🟡 Planned |
| Priority | High |
| Complexity | Low |
| Estimated Effort | 1 day |
| Dependencies | segment.image_url populated, project.subtitle_settings JSONField available |
| Output Files (NEW) | None |
| Files Modified | frontend/components/SubtitlePreview.tsx, frontend/app/projects/[id]/page.tsx |

---

## 1. Document Overview

### 1.1 Problem Statement

The current `SubtitlePreview.tsx` component renders subtitle text against a hardcoded dark gray background that has no relationship to the actual content of the segment. When a creator writes or edits subtitle text, they see white letters floating on a neutral dark box — which tells them nothing about whether those subtitles are readable over the real video frame. For example, a segment whose image is a bright overcast sky will have white subtitle text that completely disappears against the pale background, yet the preview makes it look perfectly legible. This gap between the preview and the rendered video output causes readability problems to go unnoticed until the full video is rendered, which wastes significant processing time. The preview needs to use the actual segment image as its background so that subtitle legibility can be assessed in context before any rendering job is triggered.

---

### 1.2 Proposed Solution

The solution requires no backend changes — it is entirely a CSS and React update to the subtitle preview area. The core idea is to make the preview container display position `relative`, set the segment image as a CSS `background-image` with `cover` sizing and `center` positioning, lock the container to the project's aspect ratio, and absolutely position the subtitle text over the image exactly where the video renderer will place it. An optional toggle button beneath the preview lets users switch between the real-image background and the original dark background when they want the neutral view.

Key elements of the proposed solution:

- Update `SubtitlePreview.tsx` to accept `imageUrl` (string or null), `subtitleSettings` (object), and `aspectRatio` (string such as "16/9") as props in addition to the existing `text` prop.
- When `imageUrl` is a non-empty string, set it as the CSS `background-image` of the preview container; apply `background-size: cover` and `background-position: center` so it fills the container exactly as the video frame would.
- Set the container's aspect ratio using the CSS `aspect-ratio` property derived from the project's `resolution_width` and `resolution_height` fields so the preview box is geometrically identical to the video output frame.
- Position the subtitle text using absolute positioning: anchored to the bottom of the container at the same percentage offset used by the video renderer, horizontally centered with `left: 50%` and `transform: translateX(-50%)`.
- Read font size, font family, text color, text shadow, and stroke settings from `project.subtitle_settings` and apply them directly as inline styles on the subtitle text element so that the preview reflects the real render output as closely as possible.
- If `imageUrl` is null or empty, fall back silently to the existing dark background — no error state needed, just a CSS class swap.
- Add a small "Preview on Image / Preview on Dark" toggle button beneath the preview container that switches a local boolean state, allowing creators to compare both views without losing any data.

---

### 1.3 Scope

| In Scope | Out of Scope |
|---|---|
| CSS background-image overlay using segment image | Backend API changes or new endpoints |
| Aspect ratio locking via CSS aspect-ratio property | Rendering or exporting a preview as an image file |
| Subtitle positioning matching video renderer output | Animating subtitles or showing multiple lines in sequence |
| Reading subtitle_settings for font, color, shadow | Per-word highlight or karaoke-style preview |
| Dark background fallback when no image exists | Adding new subtitle_settings fields to the backend model |
| Toggle button for Image vs Dark background view | Full video playback preview in the browser |
| Passing imageUrl and subtitleSettings as new props | Changes to the video_renderer.py or subtitle_engine.py |

---

### 1.4 Key Files Reference

| File | Role in This Feature |
|---|---|
| frontend/components/SubtitlePreview.tsx | PRIMARY CHANGE — receives image and settings props; applies CSS overlay |
| frontend/app/projects/[id]/page.tsx | MODIFIED — passes segment.image_url and project.subtitle_settings down as props |
| frontend/components/SegmentCard.tsx | Possible secondary change location if SubtitlePreview is embedded here |
| frontend/types/ (project and segment types) | Read-only reference — confirm shapes of subtitle_settings and image_url |
| backend/api/models.py | Read-only reference — confirms subtitle_settings JSONField structure |
| backend/api/serializers.py | Read-only reference — confirms resolution_width and resolution_height fields are serialised |

---

## 2. Flow Diagram

```
User opens Project Page
         |
         v
Project data loaded: resolution_width, resolution_height, subtitle_settings fetched
         |
         v
Segment data loaded: each segment has image_url (string or null)
         |
         v
SegmentCard / SubtitlePreview receives props:
  text, imageUrl, subtitleSettings, aspectRatio
         |
         +----- imageUrl is null or "" ------> Use dark background CSS class (current behavior)
         |
         v
Preview container styled:
  position: relative
  aspect-ratio: (resolution_width / resolution_height)
  background-image: url(image_url)
  background-size: cover
  background-position: center
         |
         v
Subtitle text element styled (absolute position):
  bottom: subtitleSettings.position_y_percent (or default 10%)
  left: 50%, transform: translateX(-50%)
  font-size: subtitleSettings.font_size
  color: subtitleSettings.color
  text-shadow: subtitleSettings.shadow
  font-family: subtitleSettings.font_family
         |
         v
User sees subtitle text overlaid on real image
         |
         v
Toggle button clicked
         |
         +----- "Preview on Dark" ------> Swap to dark background CSS class
         |
         +----- "Preview on Image" ----> Restore image background CSS class
```

---

## 3. Step-by-Step Instructions

### Step 1 — Audit SubtitlePreview.tsx and Identify Prop Gaps

Open `frontend/components/SubtitlePreview.tsx` and read the current component definition fully. Note exactly which props it currently accepts and how it renders the preview container and text. Identify the CSS classes or inline styles responsible for the dark background so you know what to conditionally replace. Also note where the subtitle text element sits in the JSX hierarchy — this is the element that will receive the absolute positioning styles. Cross-reference with `SegmentCard.tsx` to understand whether `SubtitlePreview` is embedded inside `SegmentCard` or used standalone in the project page. This audit determines the exact prop-drilling path needed to pass `imageUrl` and `subtitleSettings` from the project page down to `SubtitlePreview`.

### Step 2 — Extend the SubtitlePreview Props Interface

Add three new optional props to the `SubtitlePreview` component's TypeScript interface: `imageUrl` (string or null, default null), `subtitleSettings` (an inline type or imported type representing the project's subtitle settings object, default an empty object), and `aspectRatio` (string in CSS fraction format derived from width/height, default "16/9"). Marking them optional ensures that any existing usage of `SubtitlePreview` that does not yet pass these props will not produce TypeScript errors during the migration period. Once all call sites have been updated to pass the new props, they can be made required in a follow-up cleanup.

### Step 3 — Update the Preview Container and Subtitle Text Styles

In the JSX of `SubtitlePreview.tsx`, locate the outer container div. Introduce a local boolean state variable `previewOnImage` with an initial value of `true`. When `previewOnImage` is true AND `imageUrl` is a non-empty string, apply the following styles to the container: set `position` to `relative`, set `aspectRatio` to the value from props, set `backgroundImage` to `url(imageUrl)`, set `backgroundSize` to `cover`, and set `backgroundPosition` to `center`. When `previewOnImage` is false OR `imageUrl` is empty, retain the original dark background class. For the subtitle text element, when image preview mode is active, set `position` to `absolute`, set `bottom` to the percentage offset from `subtitleSettings.position_y` (fall back to ten percent if missing), horizontally center it, and apply font size, color, font family, and text shadow from `subtitleSettings`. All of these are confined to inline style objects or conditional TailwindCSS classes — no new CSS files are needed.

### Step 4 — Add the Preview Mode Toggle Button

Immediately below the preview container div (not inside it, to avoid z-index complications), add a small button element. When `previewOnImage` is true, it reads "Switch to Dark Preview". When false, it reads "Switch to Image Preview". Clicking it flips the `previewOnImage` boolean state. Style it as a minimal secondary button using the existing ShadCN button variant conventions already used elsewhere in the project — do not introduce a new button style. The button should only be rendered when `imageUrl` is a non-empty string; if there is no image, the toggle is meaningless and should be hidden to avoid confusing the user with a button that does nothing.

### Step 5 — Pass Props from the Project Page

Open `frontend/app/projects/[id]/page.tsx`. Locate where `SubtitlePreview` is instantiated (or where `SegmentCard` is instantiated if `SubtitlePreview` is nested there). Thread the following values down to the component: `segment.image_url` as `imageUrl`, `project.subtitle_settings` as `subtitleSettings`, and a computed `aspectRatio` string built from `project.resolution_width` and `project.resolution_height` (for example, "16/9" when the dimensions are 1920 by 1080). The `aspectRatio` computation should live in a small helper function or a `useMemo` call inside the project page to avoid recomputing it on every render. Verify the TypeScript types align at every level of the prop-drilling chain and that no type assertions are needed — if the segment type does not yet declare `image_url` as `string | null`, update the type definition accordingly.

---

## 4. Expected Outcome

Upon successful implementation, the following changes should be observable in the StoryFlow frontend:

- Opening a segment's subtitle editor or preview area shows the subtitle text overlaid directly on the segment's actual image background, correctly scaled to the project's aspect ratio.
- The subtitle text position, font size, color, and shadow in the preview visually match the rendered video output, eliminating the guesswork about readability that the dark preview introduced.
- Segments with a bright image (sky, white background, snow scene) make white subtitle text visibly hard to read in the preview — exactly as intended, since this surfaces a problem before the costly render step.
- Segments without a generated image (image_url is null) continue to display the existing dark background preview without any errors or visual regressions.
- A "Switch to Dark Preview / Switch to Image Preview" toggle button appears beneath the preview when an image is present, allowing creators to flip between both views for comparison.
- The aspect ratio container matches the project's configured output resolution ratio, so the relative position of the subtitle text in the preview accurately corresponds to its position in the final video frame.
- No backend API calls are added or modified — the feature is fully client-side and introduces zero additional network requests.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] SubtitlePreview renders a `background-image` style on the container when `imageUrl` is a non-empty string and `previewOnImage` is true.
- [ ] SubtitlePreview does not render `background-image` style when `imageUrl` is null, regardless of `previewOnImage` state.
- [ ] SubtitlePreview applies the correct `font-size` and `color` inline styles from `subtitleSettings` to the subtitle text element.
- [ ] The toggle button is not rendered when `imageUrl` is null or empty.
- [ ] Clicking the toggle button changes `previewOnImage` state and switches the container between image and dark background rendering.

### 5.2 Integration and Manual Tests

- [ ] Open a segment that has both a generated image and subtitle text — confirm the subtitle text appears correctly overlaid on the image in the preview.
- [ ] Open a segment with a bright white or pastel image and observe that white subtitle text is visibly hard to read, confirming the preview correctly represents the readability problem.
- [ ] Click "Switch to Dark Preview" and confirm the image background disappears and the dark background returns without any layout shift or text content change.
- [ ] Open a segment without a generated image — confirm no errors, no toggle button, and the dark background renders as before.
- [ ] Change `subtitle_settings` (font size or color) in the project settings and confirm the preview updates to reflect the new settings immediately.
- [ ] Test with three different aspect ratios (16:9, 9:16, 1:1) — confirm the preview container resizes correctly for each.

### 5.3 Regression Tests

- [ ] Existing segments that do not pass `imageUrl` to `SubtitlePreview` continue to render a dark background without TypeScript or runtime errors.
- [ ] The project page still loads and passes the full TypeScript compiler check (`tsc --noEmit`) after the prop additions.
- [ ] SegmentCard layout (all controls, spacing, buttons) is unchanged when the subtitle preview area is in both image-mode and dark-mode.

---

## 6. Notes for AI Agent

- The CSS `aspect-ratio` property is supported in all modern browsers but may cause layout inconsistencies in older Safari versions — if needed, a `padding-top` percentage fallback can be used as a `before` pseudo-element trick, though for an internal tool this level of compatibility concern is likely unnecessary.
- When setting `background-image` via inline React styles, use `backgroundImage: \`url(${imageUrl})\`` in the style object — not `background-image` (kebab-case is not valid in React inline styles).
- The `position: absolute` on the subtitle text element requires the parent container to explicitly have `position: relative` — confirm this is applied to the outermost preview container, not a wrapper further up the tree.
- If `project.subtitle_settings` is typed as `Record<string, unknown>` in the frontend types, define a proper `SubtitleSettings` interface (font_size as number, color as string, font_family as string, shadow as string, position_y as number) and use it throughout — this prevents silent type errors when reading individual fields.
- The toggle state (`previewOnImage`) should be local to `SubtitlePreview` using `useState` — it does not need to be lifted to the Zustand store because it is purely a display preference scoped to the preview component and does not affect any other part of the UI.
