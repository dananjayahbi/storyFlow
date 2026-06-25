# Feature 2.5 — Estimated Total Video Duration

| Field | Value |
|---|---|
| **Feature ID** | 2.5 |
| **Title** | Estimated Total Video Duration |
| **Status** | 🟡 Planned |
| **Priority** | Medium |
| **Complexity** | Low |
| **Estimated Effort** | 1 day |
| **Dependencies** | Segment data in Zustand store, project settings (TTS speed, transition duration, outro) |
| **Output Files (NEW)** | None |
| **Files Modified** | `frontend/components/Timeline.tsx` |

---

## 1. Document Overview

### 1.1 Problem Statement

StoryFlow users have no way to know the approximate duration of their video without performing a full render, which can take several minutes. Platform constraints — TikTok short clips at 60 seconds, TikTok premium at 3 minutes, YouTube Shorts at 60 seconds — make it critically important to know video length before investing render time. Without a pre-render estimate, users routinely discover after a long render that their video overshoots the target platform limit and must edit and re-render.

### 1.2 Proposed Solution

Calculate and display a live estimated total duration in the project header bar, derived entirely from client-side segment data already loaded in the Zustand store.

- Compute the estimated total as a sum of four components: the segment audio durations (using the actual stored duration value if audio has been generated, or a word-count estimate if not), the transition/crossfade time between segments, the inter-segment silence padding, and the optional outro clip duration.
- For segments without generated audio, estimate duration using the formula: word count divided by 150 words-per-minute (standard TTS rate) multiplied by 60 seconds, then divided by the project-level TTS speed multiplier. Display these estimates with a tilde prefix ("~") to signal approximation.
- Label the display "exact" (no tilde) when every segment in the project has a confirmed generated audio duration, making the estimate fully reliable.
- Add a color-coded platform indicator beside the duration: green when below 60 seconds, amber when between 60 seconds and 3 minutes, and red when over 3 minutes. Show a tooltip on hover that names the specific platform limits exceeded.
- Update the display reactively whenever any segment is added, removed, reordered, or has its text changed — this is driven naturally by the Zustand store subscription already used by the Timeline component.

### 1.3 Scope

| Category | Item |
|---|---|
| **In Scope** | Client-side duration calculation from Zustand segment data |
| **In Scope** | Word-count-based fallback estimate for segments without generated audio |
| **In Scope** | Platform warning indicator with three color states and a tooltip |
| **In Scope** | Real-time reactive update on segment data changes |
| **Out of Scope** | Backend duration calculation or storage of the estimate |
| **Out of Scope** | Per-segment duration display (only the project total is shown in this feature) |
| **Out of Scope** | Custom platform limit configuration by the user |
| **Out of Scope** | Music track duration contribution to the estimate |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| `frontend/components/Timeline.tsx` | Main project editor timeline component | Has segment list; header section does not show duration |
| `frontend/store/projectStore.ts` | Zustand store holding segments and project settings | Exposes `segments`, `projectSettings` (tts_speed, crossfade_duration, silence_duration, outro_enabled, outro_duration) |
| `frontend/types/project.ts` | TypeScript types for `Segment`, `ProjectSettings` | `Segment` has `duration` (number or null), `text_content` |
| `frontend/lib/utils.ts` | Shared utility functions | Has general helpers; no duration utilities currently |

---

## 2. Flow Diagram

```
Zustand store: segments[] + projectSettings
        |
        | (reactive selector — updates on any segment change)
        v
  calculateEstimatedDuration(segments, settings)
        |
        +---> for each segment:
        |       if segment.duration != null
        |         use segment.duration (exact)
        |       else
        |         wordCount = countWords(segment.text_content)
        |         estimate = (wordCount / 150 / settings.tts_speed) * 60
        |
        +---> transitions = crossfade_duration * max(0, segmentCount - 1)
        |
        +---> silences = silence_duration * segmentCount
        |
        +---> outro = outro_enabled ? outro_duration : 0
        |
        v
  totalSeconds = sum(segmentDurations) + transitions + silences + outro
  isExact = every segment has a stored duration
        |
        v
  DurationDisplay component in Timeline header
        |
     +------+------+
     |      |      |
   < 60s  60–180s  > 180s
   green  amber    red
     |      |      |
     v      v      v
  ✅ "~Xs" ⚠️ "~Xm Ys" 🚫 "~Xm Ys"
        |
        v
  Tooltip on indicator:
  "TikTok: 60s max — Xs over"
```

---

## 3. Step-by-Step Instructions

### Step 3.1 — Add Duration Calculation Utility

File: `frontend/lib/utils.ts`
Function: `calculateEstimatedDuration`

Add a pure function that accepts an array of `Segment` objects and a `ProjectSettings` object and returns an object containing `totalSeconds` (number), `isExact` (boolean), and `formattedDisplay` (string). Inside the function, map each segment to a seconds value — use `segment.duration` if it is a non-null number, otherwise compute `(wordCount / 150 / ttsSpeed) * 60` where `wordCount` is derived by splitting `text_content` on whitespace. Sum the segment values, then add `crossfade_duration * Math.max(0, segments.length - 1)`, `silence_duration * segments.length`, and `outro_duration` (if `outro_enabled` is true). Set `isExact` to true only when every segment had a non-null `duration`. Format the display string as "Xm Ys" for totals over 60 seconds or "Xs" for totals under 60 seconds, prepending a tilde when `isExact` is false.

### Step 3.2 — Add Platform Warning Logic

File: `frontend/lib/utils.ts`
Function: `getPlatformWarning`

Add a second utility function that accepts `totalSeconds` (number) and returns an object with `level` ("green" | "amber" | "red"), `icon` ("✅" | "⚠️" | "🚫"), and `tooltipText` (string). Green means under 60 seconds; amber means 60 to 179 seconds; red means 180 seconds or over. Build the tooltip text to name which platforms are affected — for example at 75 seconds the tooltip reads "TikTok Short limit (60s) exceeded by 15s — fits TikTok Premium (3min) and YouTube long-form". Keep the logic as a simple chain of comparisons; no external dependency is required.

### Step 3.3 — Create DurationBadge Sub-Component

File: `frontend/components/Timeline.tsx`
Component: `DurationBadge` (local, non-exported)

Define a small functional component directly in `Timeline.tsx` above the main export. It accepts `totalSeconds`, `isExact`, and `formattedDisplay` as props, calls `getPlatformWarning(totalSeconds)` internally, and renders a single `span` containing the icon, the formatted duration string, and a ShadCN `Tooltip` wrapping the icon that shows the tooltip text on hover. Apply a Tailwind text color class based on `level`: `text-green-500`, `text-amber-500`, or `text-red-500`.

### Step 3.4 — Integrate into Timeline Header

File: `frontend/components/Timeline.tsx`
Component: main `Timeline` export, header section

In the Timeline component's header bar, add a selector that reads `segments` and `projectSettings` from the Zustand project store. Call `calculateEstimatedDuration(segments, projectSettings)` to get the result object. Place `DurationBadge` in the header beside the project title or the existing action buttons — a right-aligned position in the header flex container works well. Pass the three calculated values as props. Because the calculation is a pure function called during render from a reactive Zustand selector, no `useEffect` or manual subscription is needed; updates are automatic whenever the store changes.

### Step 3.5 — Handle Edge Cases

File: `frontend/components/Timeline.tsx` and `frontend/lib/utils.ts`

Ensure the following edge cases do not cause errors or misleading output. An empty `segments` array should return `totalSeconds = 0` (plus outro if enabled) and display "0s". A segment with empty or whitespace-only `text_content` should produce a word count of zero (no division errors). A null or undefined `projectSettings` should be guarded with sensible defaults — `tts_speed = 1.0`, `crossfade_duration = 0`, `silence_duration = 0`, `outro_enabled = false`. Segments with `duration = 0` (a valid value for a very short clip) should be treated as exact values, not as missing.

---

## 4. Expected Outcome

1. The Timeline header bar displays a live estimated total duration shown as "~1m 23s" when some segments lack generated audio, or "1m 23s" (no tilde) when all segments have confirmed audio durations.
2. A color-coded icon immediately to the left of the duration text indicates platform compliance: green for under 60s, amber for 60s–3min, red for over 3 minutes.
3. Hovering the icon shows a tooltip explaining which platform limits are affected and by how much.
4. Adding a new segment causes the display to update immediately with an updated estimate.
5. Deleting a segment causes the display to decrease immediately.
6. Editing a segment's text (which invalidates any cached audio duration) switches the relevant segment's contribution back to the word-count estimate and re-adds the tilde prefix if it was previously exact.
7. No backend requests are made; the entire calculation is performed on already-loaded data in the Zustand store.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] `calculateEstimatedDuration` with all segments having `duration` values returns `isExact = true` and `totalSeconds` equal to the correct arithmetic sum including transitions, silences, and outro.
- [ ] `calculateEstimatedDuration` with one null-duration segment returns `isExact = false` and a tilde-prefixed `formattedDisplay`.
- [ ] `calculateEstimatedDuration` with an empty segments array returns `totalSeconds = 0` (or `outro_duration` if outro is enabled).
- [ ] `getPlatformWarning` returns `level = "green"` for 45 seconds, `level = "amber"` for 90 seconds, and `level = "red"` for 200 seconds.
- [ ] Word count estimation correctly handles multi-space, tab, and newline-separated words without producing NaN or Infinity.

### 5.2 Integration / Manual Tests

- [ ] Open a project with 3 segments all having generated audio → header shows exact duration with no tilde and green indicator (assuming total under 60s).
- [ ] Add a new unsaved segment with the text "Hello world this is a test" → duration display updates immediately with a tilde estimate.
- [ ] Enable outro in project settings → outro duration is added to the displayed total immediately.
- [ ] Edit an existing segment's text to a much longer passage → estimated duration increases in real time.
- [ ] Increase TTS speed multiplier in project settings → estimated duration for un-generated segments decreases accordingly.

### 5.3 Regression Tests

- [ ] The Timeline component renders correctly for projects that have zero segments (no crash, shows "~0s" or "0s").
- [ ] Existing Timeline functionality (segment reorder, delete, edit) is unaffected by the added duration badge in the header.
- [ ] The Timeline still renders when `projectSettings` is partially missing or returns default values (no undefined access errors).

---

## 6. Notes for AI Agent

- Implement `calculateEstimatedDuration` and `getPlatformWarning` as pure functions in `lib/utils.ts` — pure functions are straightforward to unit test in isolation without needing to mock React or Zustand.
- Do not use `useMemo` for the duration calculation unless profiling shows a real performance problem; the calculation is O(n) over segments and re-running it on every render is negligible for typical story lengths of 5–30 segments.
- The tilde prefix convention ("~Xs" vs "Xs") clearly communicates to the user that the value is an estimate — preserve this distinction in `formattedDisplay` and do not collapse it into a single display mode.
- ShadCN's `Tooltip` component wrapping just the icon (not the whole badge) gives a clean UX — the duration number is always readable, and the platform explanation is available on demand.
- Verify that the `Segment` TypeScript type in `frontend/types/project.ts` actually has a `duration` field typed as `number | null`; if the field is named differently (e.g., `audio_duration`), adjust the utility function accordingly before implementing.
