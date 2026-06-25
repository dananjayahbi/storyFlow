# Feature 1.6 — Segment Duration Display

| Field | Value |
|---|---|
| **Feature ID** | 1.6 |
| **Title** | Segment Duration Display |
| **Status** | 🟡 Planned |
| **Priority** | Medium |
| **Complexity** | Low |
| **Estimated Effort** | 1 day |
| **Dependencies** | None |
| **Output Files (NEW)** | None |
| **Files Modified** | `frontend/components/SegmentCard.tsx`, `frontend/components/Timeline.tsx` |

---

## 1. Document Overview

### 1.1 Problem Statement

Users currently have no way to gauge video length before committing to a full TTS generation pass. Audio duration is only shown after it has already been generated, meaning a creator must render all audio in a project to discover the total runtime. For projects with 20 or more segments this represents a significant time cost for what is effectively just a planning check. There is no feedback mechanism in the editing UI that connects text volume to expected output length.

### 1.2 Proposed Solution

Introduce a lightweight, purely client-side duration estimate that uses word count and TTS speed to compute an approximate audio length for each segment. The estimate is derived from an industry-standard average reading rate of approximately 150 words per minute at 1.0× playback speed, adjusted proportionally when the user has selected a faster or slower speed. Once actual audio has been generated and the backend provides a real `duration` value, that measured figure replaces the estimate automatically.

Key implementation points:

- Compute word count from `text_content` by splitting on whitespace in the component render function.
- Apply the formula: estimated seconds equals word count divided by the product of 150 and the TTS speed multiplier.
- Display estimated durations formatted as "~3.2s" (tilde prefix + one decimal) in gray italic text inside `SegmentCard.tsx`.
- Display measured (actual) durations formatted as "3.2s" (no tilde) in normal weight text — the visual contrast makes the distinction obvious without a tooltip.
- Aggregate estimates and actuals in `Timeline.tsx` to show a project-level total in the toolbar.
- Include transition overhead in the total: 0.5 seconds per inter-segment transition and the outro duration if one is enabled.
- Format totals longer than 60 seconds as "~Xm Ys" rather than a raw second count.
- No backend changes, no new API calls — this is entirely a rendering concern.

### 1.3 Scope

| Category | Item |
|---|---|
| **In Scope** | Per-segment estimated duration label in `SegmentCard.tsx` |
| **In Scope** | Per-segment actual duration label (replacing estimate when `duration` field is present) |
| **In Scope** | Project total duration estimate in the `Timeline.tsx` toolbar |
| **In Scope** | Transition and outro duration included in project total |
| **Out of Scope** | Backend changes of any kind |
| **Out of Scope** | Duration-based pricing, quota warnings, or export gating |
| **Out of Scope** | Per-word or per-sentence granularity (segment-level only) |
| **Out of Scope** | Reading-speed customisation beyond the existing TTS speed setting |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| `frontend/components/SegmentCard.tsx` | Renders one segment: text, image, audio player, voice controls | Audio duration shown only after generation; no estimate |
| `frontend/components/Timeline.tsx` | Renders the full ordered segment list with toolbar actions | No duration summary in toolbar |
| `frontend/store/settingsStore.ts` | Zustand store for global settings including TTS speed | Contains `ttsSpeed` field used for generation |
| `frontend/app/projects/[id]/page.tsx` | Project detail page; holds segment array state | Passes segment data as props to `Timeline` and `SegmentCard` |

---

## 2. Flow Diagram

```
User edits text_content in SegmentCard
         │
         ▼
  SegmentCard reads text_content
         │
         ▼
  word_count = split on whitespace → count
         │
         ▼
  tts_speed pulled from settingsStore
         │
         ▼
  estimated_seconds = word_count / (150 × tts_speed)
         │
         ├── segment.duration is null?
         │        │
         │        ▼
         │   Show "~X.Xs" (gray italic)
         │
         └── segment.duration is set?
                  │
                  ▼
             Show "X.Xs" (normal weight)

Timeline collects all per-segment values
         │
         ▼
  total = Σ(estimated or actual) + 0.5 × transitions + outro
         │
         ▼
  Format as "~Xm Ys" or "~Xs"
         │
         ▼
  Display in Timeline toolbar
```

---

## 3. Step-by-Step Instructions

### Step 3.1 — Add a duration utility function near the top of SegmentCard.tsx

File: `frontend/components/SegmentCard.tsx`

Locate the import section at the top of the file. Immediately after the last import statement, define a plain helper function called `computeEstimatedSeconds`. It should accept a `textContent` string and a `ttsSpeed` number. Inside, split `textContent` on one or more whitespace characters to get an array, filter out empty strings to avoid inflating the count, then return the array length divided by the product of 150 and `ttsSpeed`. Guard against zero or negative speed values by defaulting to 1.0. This function does not touch any React state and does not require memoisation for a project of this scale.

### Step 3.2 — Read ttsSpeed from the settings store inside SegmentCard

File: `frontend/components/SegmentCard.tsx`

Locate the component function body where other Zustand store values are already selected. Add a selector to pull `ttsSpeed` from `useSettingsStore`. If the individual segment also carries its own speed override (check the segment object shape — there may be a `tts_speed` property), prefer the segment-level value and fall back to the global store value. Store the resolved speed in a local constant called `resolvedSpeed`.

### Step 3.3 — Render the duration label in SegmentCard

File: `frontend/components/SegmentCard.tsx`

Locate the section in the JSX where the audio player controls are rendered (look for the audio element or the play/pause button). Directly below or alongside those controls, add a small inline element to display the duration. Use a conditional: if `segment.duration` is truthy, render the measured value formatted to one decimal place with no tilde prefix, styled with normal font weight and the project's default text colour. If `segment.duration` is falsy, call `computeEstimatedSeconds` with `segment.text_content` and `resolvedSpeed`, format the result to one decimal place, prepend a tilde character, and render in gray italic. Wrap the label in a span with an accessible `title` attribute explaining the distinction between estimate and measured value.

### Step 3.4 — Compute and display the project total in Timeline

File: `frontend/components/Timeline.tsx`

Locate the toolbar render section — the bar that sits above the segment list and contains action buttons. Before the return statement, derive a total duration value by reducing over the segments array: for each segment, use `segment.duration` if present, otherwise apply the same word-count formula using the segment's own tts speed or the global store value. After the reduction, add the transition overhead by multiplying 0.5 by the number of inter-segment gaps (which is `segments.length - 1` when there is at least one segment). If an outro is enabled (check the project settings object for an `outro_enabled` flag or equivalent), add the outro duration or a sensible default of 5 seconds. Format the final number using a formatting helper: if total is 60 seconds or more, express as minutes and seconds; otherwise express as a raw second count. In both cases prefix with a tilde if any estimated segment was used, or omit the tilde when all durations are measured actuals.

### Step 3.5 — Add a format helper for minutes/seconds

File: `frontend/components/Timeline.tsx`

Immediately after imports, define a small pure function called `formatDuration` that accepts a number of seconds and a boolean flag indicating whether any value is an estimate. If the seconds value is 60 or greater, divide by 60 to get minutes, compute the remainder seconds, and return a string in the form "~Xm Ys" (with tilde if estimated) or "Xm Ys" (without tilde if all measured). If the value is below 60, return "~Xs" or "Xs" accordingly, formatted to one decimal place. Place the formatted string in a span in the toolbar alongside a label such as "Est. Total:" or "Total Duration:".

---

## 4. Expected Outcome

1. Every `SegmentCard` component shows a duration label immediately upon render, even before any audio has been generated.
2. The label reads "~X.Xs" in gray italic for segments with no generated audio, making the estimated nature immediately apparent.
3. After audio generation the label updates to "X.Xs" in normal weight text because the backend now returns a real `duration` value — no page reload required if the state update propagates correctly.
4. The Timeline toolbar displays a total project duration that sums all per-segment values and accounts for transitions and the outro.
5. The total duration uses minutes-and-seconds format for projects 60 seconds or longer, keeping the display compact.
6. The tilde prefix on the total disappears once every segment has real measured audio, signalling that the total is now exact.
7. No extra network requests are made; the feature is entirely derived from existing segment data already in memory.
8. The change is visually non-intrusive — users who do not care about duration can ignore the label entirely.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] `computeEstimatedSeconds("Hello world", 1.0)` returns a value equal to 2 divided by 150, within floating-point tolerance.
- [ ] `computeEstimatedSeconds` correctly applies a 1.5× speed: result should be two-thirds of the 1.0× result for the same text.
- [ ] `computeEstimatedSeconds` handles an empty string without throwing and returns 0.
- [ ] `formatDuration(90, true)` returns "~1m 30s".
- [ ] `formatDuration(45.3, false)` returns "45.3s" without a tilde.
- [ ] `formatDuration(60, false)` returns "1m 0s".

### 5.2 Integration / Manual Tests

- [ ] Open a project with five segments; verify that each `SegmentCard` displays a gray italic estimate before audio generation.
- [ ] Generate audio for one segment; verify that its label changes to a non-italic measured value and the total in the toolbar updates accordingly.
- [ ] Change the global TTS speed in settings; verify that all un-generated segment estimates immediately recalculate without a page reload.
- [ ] Create a segment with zero words (blank text); verify the label shows "~0.0s" and does not crash.
- [ ] Enable the outro and verify the Timeline total includes the outro duration.
- [ ] Open a project where all segments have generated audio; verify no tilde appears on any label or on the total.

### 5.3 Regression Tests

- [ ] Verify that generating audio for a segment still works as before and the resulting `duration` value is stored and displayed correctly.
- [ ] Confirm that editing segment text updates the word count and recalculates the estimate in real time without triggering an unnecessary API call.
- [ ] Confirm the Timeline toolbar renders correctly on projects with a single segment (zero transition overhead).

---

## 6. Notes for AI Agent

- The 150 words-per-minute constant should be defined as a named constant at the top of the relevant file rather than as a magic number inline, making it trivial to adjust later.
- The `ttsSpeed` value from the store represents a multiplier (e.g., 0.75, 1.0, 1.25). Be careful not to apply it as a percentage; it is already a decimal factor.
- When checking whether a duration is "measured" vs "estimated", treat any non-null, non-zero positive number from `segment.duration` as measured. A value of exactly 0 may indicate the audio exists but has zero length, which should be handled as a special case rather than triggering the estimate path.
- The outro duration field name in the project settings object should be confirmed against the actual Django serializer response before implementing the Timeline total — look at what `GET /api/projects/{id}/` returns for the outro configuration.
- This feature intentionally avoids any backend work; if a future feature adds a `word_count` field to the Segment model for search or analytics purposes, the frontend estimate can be replaced with that server-side value without changing the display logic.
