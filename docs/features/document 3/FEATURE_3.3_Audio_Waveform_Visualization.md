# Feature 3.3 — Audio Waveform Visualization

| Field | Value |
|---|---|
| Feature ID | 3.3 |
| Title | Audio Waveform Visualization per Segment |
| Status | 🟡 Planned |
| Priority | Medium |
| Complexity | Medium |
| Estimated Effort | 2 days |
| Dependencies | WaveSurfer.js (npm install wavesurfer.js), segment audio_url populated |
| Output Files (NEW) | frontend/components/AudioWaveform.tsx |
| Files Modified | frontend/components/SegmentCard.tsx, frontend/store/settingsStore.ts |

---

## 1. Document Overview

### 1.1 Problem Statement

Currently every segment in StoryFlow provides only a basic HTML audio element with a play/pause button to let users listen to generated TTS audio. This gives zero visual information about the underlying audio signal — a user cannot see where speech begins, where it ends, whether there is unwanted silence at the head or tail of the clip, or whether the audio was generated at all versus resulting in an empty file. When a project contains twenty or more segments, scrubbing through each clip individually to check for pacing and silence issues is tedious and error-prone. A visual waveform representation would allow a creator to glance at a segment and immediately assess whether the audio is healthy, too short, or padded with excessive silence before even pressing play.

---

### 1.2 Proposed Solution

The solution is to replace the bare audio element in each SegmentCard with a purpose-built AudioWaveform component that uses WaveSurfer.js to decode and display the audio signal as a colored waveform bar. WaveSurfer decodes audio data directly in the browser using the Web Audio API and renders the waveform to an HTML canvas element contained inside a `div`. The component handles its own lifecycle — mounting, decoding, playing, pausing, and destroying the WaveSurfer instance — so the consuming SegmentCard remains clean.

Key elements of the proposed solution:

- Install the WaveSurfer.js package as a production dependency using npm so that the waveform renderer is available across the frontend build.
- Create a new standalone component `AudioWaveform.tsx` that accepts `audioUrl` as a required string prop and an optional `isPlaying` boolean prop for external play control.
- On component mount and whenever `audioUrl` changes, the component initialises a WaveSurfer instance attached to a stable `div` ref, applying consistent visual options: waveColor `#4F46E5`, progressColor `#818CF8`, height 48 pixels, normalize enabled, and WebAudio backend.
- While WaveSurfer is loading and decoding the audio file, show a full-width gray skeleton bar of the same 48-pixel height so the layout does not shift.
- Expose a play/pause button beneath the waveform bar (or overlaid at the left) that calls `wavesurfer.playPause()`, and display a remaining-time counter that updates via the `audioprocess` event callback.
- Replace the existing inline audio element and its play/pause button inside SegmentCard with the AudioWaveform component, rendering it only when `segment.audio_url` is a non-empty string.
- Because WaveSurfer depends on browser-only Web APIs (AudioContext, Canvas), the component must be imported dynamically with `ssr: false` to prevent SSR failures in Next.js.
- Add an "Enable Waveforms" boolean toggle to the global settings store (`settingsStore.ts`) so that users with many segments can disable waveform rendering to conserve CPU and memory, falling back to the plain audio element.

---

### 1.3 Scope

| In Scope | Out of Scope |
|---|---|
| AudioWaveform component creation | Server-side audio analysis or pre-generated waveform data |
| WaveSurfer.js installation and configuration | Editing or trimming audio from within the waveform |
| SegmentCard integration with audio_url guard | Custom waveform color themes per project |
| Loading skeleton while decoding | Exporting waveform images to video frames |
| Enable/Disable toggle in settings store | Multi-track mixing or layered waveforms |
| Remaining-time counter display | Waveform zoom or scrolling for long clips |
| Dynamic import to prevent SSR errors | Backend changes of any kind |

---

### 1.4 Key Files Reference

| File | Role in This Feature |
|---|---|
| frontend/components/AudioWaveform.tsx | NEW — hosts WaveSurfer instance, waveform canvas, play/pause, timer |
| frontend/components/SegmentCard.tsx | MODIFIED — imports AudioWaveform; replaces audio element; passes audio_url |
| frontend/store/settingsStore.ts | MODIFIED — add enableWaveforms boolean field and toggle action |
| frontend/app/projects/[id]/page.tsx | Read-only reference — confirms how segment data flows down to SegmentCard |
| frontend/types/ (segment type files) | Read-only reference — confirm audio_url type is string or null |
| package.json (frontend) | MODIFIED — records wavesurfer.js as a new dependency after install |

---

## 2. Flow Diagram

```
User opens Project Page
         |
         v
SegmentCard receives segment prop (audio_url may be null or a URL string)
         |
         +----- audio_url is null --------> Show "No Audio" placeholder text
         |
         v
settingsStore.enableWaveforms check
         |
         +----- enableWaveforms = false ---> Render plain HTML audio element (fallback)
         |
         v
Dynamic import: AudioWaveform loaded (ssr: false)
         |
         v
AudioWaveform mounts: WaveSurfer.create() called with div ref + visual options
         |
         v
WaveSurfer begins fetching + decoding audio_url
         |
         +----- decoding in progress ------> Gray skeleton bar (height: 48px) shown
         |
         v
WaveSurfer 'ready' event fires: waveform canvas rendered
         |
         v
User clicks Play/Pause button --> wavesurfer.playPause()
         |
         v
'audioprocess' event fires continuously --> Remaining-time counter updates
         |
         v
audio_url prop changes (re-generation) --> WaveSurfer.destroy() then re-init
```

---

## 3. Step-by-Step Instructions

### Step 1 — Install WaveSurfer.js

Navigate into the `frontend` directory in your terminal. Run the standard npm install command for the `wavesurfer.js` package without any version pin so that the latest stable release is installed. After installation confirms success, verify that `wavesurfer.js` appears in the `dependencies` section of `frontend/package.json`. Do not install any WaveSurfer plugins at this stage — the core package is sufficient for basic waveform display, play/pause, and time tracking. Commit the updated `package.json` and `package-lock.json` together.

### Step 2 — Create AudioWaveform.tsx

Create the file `frontend/components/AudioWaveform.tsx`. This component accepts `audioUrl` (string) and an optional `className` prop. Inside the component, declare a `div` ref that will serve as the WaveSurfer container, a boolean state for `isLoading` (initially true), a boolean state for `isPlaying` (initially false), and a number state for `currentTime`. On mount, call `WaveSurfer.create` targeting the div ref with the visual configuration described in the solution section above. Subscribe to the `ready` event to set `isLoading` to false. Subscribe to `audioprocess` to update `currentTime`. Subscribe to `finish` to set `isPlaying` to false. In the cleanup function returned from the effect, call `wavesurfer.destroy()` to prevent memory leaks when the component unmounts or when `audioUrl` changes. Render a wrapper div, the WaveSurfer container div (always in the DOM but hidden while loading), the skeleton bar (shown only while loading), the play/pause toggle button, and the time display.

### Step 3 — Update SegmentCard.tsx

Open `frontend/components/SegmentCard.tsx`. Locate the section that renders the audio element and its play/pause controls. Remove the inline audio element and its associated state and handlers. Import `settingsStore` and read the `enableWaveforms` flag. Import `AudioWaveform` using Next.js `dynamic` with `{ ssr: false }` — this must be a module-level import, not inside the render function, to avoid re-creating the dynamic import on every render. In the JSX, add a guard: if `segment.audio_url` is falsy, render a short muted "No audio generated" label. If `segment.audio_url` is set and `enableWaveforms` is true, render `AudioWaveform` with the `audioUrl` prop. If `segment.audio_url` is set but `enableWaveforms` is false, render the plain HTML audio element as before. This ensures backward compatibility for users on lower-powered machines.

### Step 4 — Add the Enable Waveforms Toggle to settingsStore

Open `frontend/store/settingsStore.ts`. Add a new boolean field `enableWaveforms` to the store state, defaulting to `true`. Add a corresponding action `toggleWaveforms` that flips the boolean. If the store is already persisted to localStorage via Zustand's `persist` middleware, the new field will automatically be saved and restored between sessions. If persistence is not yet in place for the settings store, add `persist` wrapping around the store definition so that the user's waveform preference survives page reloads. Expose the toggle in a visible settings area — either through an existing project-settings panel or, if none exists, as a small "⚡ Waveforms: ON/OFF" chip in the project page header area.

### Step 5 — Validate Memory and Performance

After integrating the component, open a project with at least ten segments and observe browser DevTools Memory panel. Ensure that destroying and re-creating WaveSurfer instances (by navigating away and back) does not cause the memory baseline to grow unboundedly — each destroy call must release the AudioContext. Test that toggling `enableWaveforms` off and on changes the rendered output without a hard page reload. Test that when `audio_url` changes (because the user regenerates TTS for a segment), the old waveform is destroyed and a new one is initialized cleanly. Confirm no `WaveSurfer` console errors appear in production mode (some versions emit deprecation warnings that should be suppressed or handled).

---

## 4. Expected Outcome

Upon successful implementation, the following observable changes should be present in the StoryFlow frontend:

- Every SegmentCard with a non-null `audio_url` displays a color-coded horizontal waveform bar at 48-pixel height in place of the plain audio element.
- The waveform fills with an indigo progress color as playback advances, giving a clear visual indicator of position within the clip.
- A remaining-time counter displayed next to the waveform updates continuously during playback, showing how many seconds remain.
- While the waveform is decoding (typically under one second for short TTS clips), a gray shimmer or solid gray skeleton bar of identical dimensions occupies the space so there is no layout shift.
- Segments where the waveform is nearly flat or shows a very short spike immediately reveal silence-heavy or empty audio clips without the user needing to listen.
- Users on lower-end machines or projects with thirty-plus segments can disable waveform rendering entirely via the settings toggle, reverting to the plain audio element without losing any other functionality.
- Re-generating audio for a segment (which updates `audio_url`) causes the waveform to destroy and reinitialise automatically, reflecting the new audio without requiring a page reload.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] AudioWaveform renders a loading skeleton when `isLoading` is true and waveform container is not yet visible.
- [ ] AudioWaveform renders the WaveSurfer container div once `isLoading` becomes false on the `ready` event.
- [ ] SegmentCard renders the "No audio generated" label when `segment.audio_url` is null or empty string.
- [ ] SegmentCard renders the plain audio element (not AudioWaveform) when `settingsStore.enableWaveforms` is false.
- [ ] `toggleWaveforms` action in settingsStore correctly flips the boolean value between true and false.

### 5.2 Integration and Manual Tests

- [ ] Open a project with at least five segments that have audio; confirm all five waveforms render without errors in the browser console.
- [ ] Click play on a waveform and confirm the progress color advances left to right and the time counter decrements.
- [ ] Toggle "Enable Waveforms" off and confirm all SegmentCards switch to plain audio elements immediately without a reload.
- [ ] Regenerate TTS audio for one segment and confirm the waveform reinitialises with the new audio clip automatically.
- [ ] Open DevTools Memory panel, reload with ten segments, and confirm no unbounded memory growth after opening and closing several segments.
- [ ] Confirm the page passes Next.js build (`next build`) without SSR errors related to `window` or `AudioContext`.

### 5.3 Regression Tests

- [ ] Segments without audio still display all other SegmentCard controls (text editor, voice selector, regenerate button) without layout issues.
- [ ] The project page still loads correctly and renders all segments when `wavesurfer.js` is unavailable or throws on init (graceful degradation to plain audio).
- [ ] Existing SegmentCard snapshot tests (if any) are updated to reflect the new conditional render logic without breaking CI.

---

## 6. Notes for AI Agent

- WaveSurfer.js v7+ changed its API significantly from v6 — when implementing, check which major version is installed and use the corresponding constructor and event names; do not mix v6 and v7 patterns.
- The `dynamic` import must be declared at the module level of `SegmentCard.tsx`, not inside a render or callback function — placing it inside a function causes Next.js to re-evaluate the dynamic import on every render cycle, which defeats lazy loading.
- When subscribing to WaveSurfer events inside a useEffect, always return a cleanup function that calls `wavesurfer.destroy()` — failing to do so when ten or more segments are mounted simultaneously will exhaust the browser's AudioContext limit (typically six concurrent contexts).
- The `audioUrl` prop passed to `AudioWaveform` should be the full absolute URL as stored in `segment.audio_url` — if the backend returns a relative path, prefix it with the API base URL in SegmentCard before passing it down.
- If the remote audio URL does not include CORS headers (Access-Control-Allow-Origin), WaveSurfer's WebAudio backend will fail silently — ensure the Django backend or media server sends appropriate CORS headers for audio files.
