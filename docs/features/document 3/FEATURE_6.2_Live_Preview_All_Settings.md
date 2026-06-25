# Feature 6.2 — Live Preview for All Settings

| Field | Value |
|---|---|
| Feature ID | 6.2 |
| Title | Live Preview for All Settings |
| Status | 🟡 Planned |
| Priority | High |
| Complexity | Medium |
| Estimated Effort | 3 days |
| Dependencies | Existing SubtitlePreview component; settingsStore must be fully wired; fonts served from backend or public directory |
| Output Files (NEW) | `frontend/components/SettingsLivePreview.tsx`; `frontend/components/KenBurnsPreview.tsx`; `frontend/components/TransitionPreview.tsx` |
| Files Modified | `frontend/app/settings/page.tsx`, `frontend/components/SubtitlePreview.tsx`, `frontend/store/settingsStore.ts` |

---

## 1. Document Overview

### 1.1 Problem Statement

StoryFlow's settings page currently provides a subtitle preview and a logo preview, but every other visual setting — Ken Burns zoom intensity, transition type and duration, and font selection — has no live feedback mechanism whatsoever. A creator who sets the Ken Burns intensity to 0.3 versus 0.8 will experience dramatically different levels of video motion, but discerning the difference requires waiting for a full video render to complete, which can take minutes. Similarly, changing the subtitle font from "Roboto" to "Impact" or "Cinzel" requires a full render cycle before the creator can judge whether the font matches their intended brand. This round-trip render feedback loop dramatically slows down the visual configuration workflow and discourages experimentation with settings values.

### 1.2 Proposed Solution

Extend the settings page with a unified live preview panel that reacts to slider and dropdown changes in real time using CSS animations and dynamically loaded fonts, eliminating the need for backend video rendering just to preview a visual change.

- Create a new `SettingsLivePreview.tsx` component that renders a fixed 640×360 preview panel embedded in the settings page sidebar, styled to match standard video aspect ratio with overflow hidden and a dark background representing a typical video frame.
- Build a `KenBurnsPreview.tsx` sub-component that applies a CSS keyframe animation to a background image div; the animation's scale range is computed from the current `zoom_intensity` Zustand value so that moving the slider from 0.1 to 1.0 visibly changes how aggressively the image zooms during the 3-second looped animation.
- Build a `TransitionPreview.tsx` sub-component that overlays two placeholder image divs and animates an opacity crossfade between them over a duration set by the `transition_duration` setting, giving a direct visual representation of how long and how smooth the scene transition will feel.
- Implement font preview by injecting a `<style>` tag at render time declaring a `@font-face` rule for the currently selected font; a sample subtitle line renders in the selected font over the Ken Burns background, updating in real time as the font dropdown value changes.
- The preview auto-plays on a loop using CSS `animation: infinite`; any settings change triggers an animation restart by incrementing a React `key` prop on the top-level preview container, forcing a clean re-mount with the new values.
- All preview animations are client-side only — no backend calls are made during live preview interaction, keeping the response latency under 50ms.

### 1.3 Scope

| Dimension | In Scope |
|---|---|
| Ken Burns preview | CSS scale animation driven by zoom_intensity slider value |
| Transition preview | CSS opacity crossfade driven by transition_duration value |
| Font preview | Real-time subtitle text rendered in selected font via @font-face |
| Preview panel layout | 640×360 panel embedded in settings page layout |

| Dimension | Out of Scope |
|---|---|
| Audio preview | Playing TTS voice samples is covered in Feature 5.x (TTS) |
| Color/gradient background preview | Not a current GlobalSettings field |
| Full segment video playback | Full preview rendering is a separate video player feature |
| Mobile-responsive preview panel | Preview targets desktop settings layout only |

### 1.4 Key Files Reference

| File | Role in This Feature |
|---|---|
| `frontend/components/SettingsLivePreview.tsx` | Root preview container, composes sub-components, manages animation key |
| `frontend/components/KenBurnsPreview.tsx` | CSS zoom animation driven by zoom_intensity from settingsStore |
| `frontend/components/TransitionPreview.tsx` | CSS crossfade animation driven by transition_duration from settingsStore |
| `frontend/app/settings/page.tsx` | Embed SettingsLivePreview in a sticky sidebar column layout |
| `frontend/store/settingsStore.ts` | All animation-driving values (zoom_intensity, transition_duration, subtitle_font) read from here |

---

## 2. Flow Diagram

```
Settings Page renders two-column layout
  Left: settings form fields
  Right: SettingsLivePreview panel (640x360)
         |
         v
  User moves zoom_intensity slider → 0.6
         |
         v
  settingsStore.zoom_intensity updates to 0.6
         |
         v
  KenBurnsPreview reads new value → recomputes scale end
  scale: 1.0 → 1.09  (1.0 + 0.6 * 0.15)
         |
         v
  Preview container key increments → animation restarts
         |
         v
  CSS @keyframes zoom plays from scale(1.0) → scale(1.09)
  3-second loop, ease-in-out
         |
         v
  User also changes font dropdown → "Impact"
         |
         v
  FontPreview injects @font-face style tag for Impact.ttf
  Sample subtitle text re-renders in Impact font
         |
         v
  User clicks "Save Settings" → stored to backend only on save
```

---

## 3. Step-by-Step Instructions

### Step 1 — Create SettingsLivePreview.tsx root component

File: `frontend/components/SettingsLivePreview.tsx` (new file)

Create the root preview container as a React functional component. It should render a 640×360 div with `overflow-hidden`, a dark background, and `relative` positioning. Inside, compose `KenBurnsPreview`, `TransitionPreview`, and a subtitle overlay `<p>` element showing sample text. Maintain a `previewKey` state integer; expose a `triggerRestart` function that increments it and pass it as the `key` prop to each sub-component so that settings changes cause all animations to restart cleanly. Subscribe to the necessary values from `settingsStore` using `useSettingsStore` selectors.

### Step 2 — Create KenBurnsPreview.tsx with CSS animation

File: `frontend/components/KenBurnsPreview.tsx` (new file)

The component receives `zoomIntensity` and `durationSeconds` as props. Compute the CSS animation end scale as `1.0 + zoomIntensity * 0.15` and construct an inline `@keyframes` rule string that starts at `scale(1.0)` and ends at the computed scale. Inject this as a `<style>` tag inside the component using a unique animation name tied to the current props values to avoid CSS namespace collisions. Render a full-width, full-height div with a placeholder landscape background image and apply the generated keyframe animation with `animation-fill-mode: both`, `animation-iteration-count: infinite`, and `animation-timing-function: ease-in-out`.

### Step 3 — Create TransitionPreview.tsx with crossfade animation

File: `frontend/components/TransitionPreview.tsx` (new file)

The component receives `transitionDuration` as a prop and renders two overlapping `absolute`-positioned full-size background image divs — one showing a warm-toned placeholder image and one showing a cool-toned placeholder — stacked with `z-index`. Inject a `<style>` tag defining a `@keyframes` crossfade that transitions the top div's opacity from 1 to 0 and back over the provided duration. Wire the animation duration directly to the `transitionDuration` prop value in seconds. The animation loops infinitely so the user can watch the crossfade effect without interaction. Use two visually distinct placeholder images from `frontend/public/` so the transition is clearly visible.

### Step 4 — Embed live preview panel in settings page layout

File: `frontend/app/settings/page.tsx`

Restructure the settings page layout to a two-column grid using Tailwind `grid grid-cols-3 gap-6`. The left two columns contain the existing settings form sections. The rightmost column contains `SettingsLivePreview` wrapped in a `sticky top-4` container so the preview stays visible as the user scrolls through the settings form. Add a small toolbar beneath the preview panel showing the current zoom scale, transition duration, and active font name as readable labels. Subscribe to `settingsStore` change events and pass a `onSettingsChange` callback that triggers `triggerRestart` on the preview component using a `useRef` forwarded ref.

---

## 4. Expected Outcome

- The settings page renders a 640×360 live preview panel in a sticky right column that remains visible while scrolling through all settings sections.
- Moving the Ken Burns intensity slider from minimum to maximum produces visibly different zoom motion in the preview panel within 50ms of the slider interaction.
- Changing the transition duration slider directly alters how long the crossfade animation takes, giving immediate tactile feedback on timing.
- Switching fonts in the font dropdown instantly re-renders the sample subtitle text in the newly selected font without any page reload or backend call.
- All preview animations loop continuously and restart cleanly whenever a relevant setting value changes, with no stale animation states.
- When the user saves settings, no additional preview restart or reload is triggered — the preview continues running with the current values.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] `KenBurnsPreview` component renders with correct computed end scale when given `zoomIntensity=0.5`: expected scale should be `1.075`.
- [ ] `TransitionPreview` component applies the correct CSS animation duration value derived from the `transitionDuration` prop in the inline style tag.
- [ ] `SettingsLivePreview` increments `previewKey` exactly once per prop change event and passes it correctly as the `key` prop to sub-components.
- [ ] Font preview injects a `@font-face` style tag containing the correct `font-family` name and `src` URL matching the selected font filename.

### 5.2 Integration / Manual Tests

- [ ] Set zoom_intensity to 0.1 and observe a subtle, slow zoom in the preview; set it to 1.0 and observe a dramatic, fast zoom — confirm visible difference matches expectations.
- [ ] Set transition_duration to 0.5 seconds and observe a quick snap crossfade; set it to 3.0 seconds and observe a slow, cinematic crossfade — confirm the visual timing matches the numeric value.
- [ ] Select three different fonts from the dropdown in sequence and verify the subtitle sample text in the preview re-renders in each font without any flicker or layout shift.
- [ ] Scroll down through all settings sections and verify the preview panel remains visible and sticky in the right column throughout.
- [ ] Confirm that no network requests are made to the backend while manipulating any preview-driving slider or dropdown before clicking Save.

### 5.3 Regression Tests

- [ ] Existing SubtitlePreview component continues to function correctly and is not visually disrupted by the addition of the SettingsLivePreview panel in the page layout.
- [ ] The settings page Save button still correctly persists all field values to the backend and returns a success toast — no regression from layout restructure.
- [ ] settingsStore values are not inadvertently reset or overwritten by the preview component's read-only subscriptions.

---

## 6. Notes for AI Agent

- The inline `@keyframes` injection approach requires generating a unique animation name per render cycle (e.g., `kenBurns_${zoomIntensity * 100}`) to prevent the browser from caching stale keyframe values from a previous render — this is critical for the live-update behavior to work correctly.
- Placeholder images for the preview should be included in `frontend/public/preview/` as static landscape images approximately 640×360px; they do not need to be actual project assets — generic nature or gradient images are fine.
- The font `src` URL in the dynamically injected `@font-face` style tag should point to `frontend/public/fonts/` paths (relative URL starting with `/fonts/`) to avoid CORS issues, assuming fonts are served as Next.js static files rather than from the Django backend.
- Do not subscribe to all settingsStore fields in `SettingsLivePreview` — use narrow selectors for only the three fields that drive animations (zoom_intensity, transition_duration, subtitle_font) to prevent unnecessary re-renders when unrelated settings fields are updated.
