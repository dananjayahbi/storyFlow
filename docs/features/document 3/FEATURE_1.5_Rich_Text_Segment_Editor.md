# Feature 1.5 — Rich Text Segment Editor

| Field | Value |
|---|---|
| **Feature ID** | 1.5 |
| **Title** | Rich Text Segment Editor |
| **Status** | 🟡 Planned |
| **Priority** | Medium |
| **Complexity** | Low–Medium |
| **Estimated Effort** | 3–5 days |
| **Dependencies** | None (standalone); integrates with Feature 3.4 Pronunciation Dictionary and Feature 5.3 Narration Pacing Analysis when those are built |
| **Output Files (NEW)** | None |
| **Files Modified** | `frontend/components/SegmentTextEditor.tsx`, `frontend/components/SegmentCard.tsx` |

---

## 1. Document Overview

### 1.1 Problem Statement

The current segment text input in StoryFlow is a plain `<textarea>` with no supplemental information displayed alongside it, providing creators with zero real-time feedback about the size, density, or audio implications of the text they are entering. Creators have no way to know in advance how many words a segment contains, how long its characters string is, or how long the generated TTS audio for that text will approximately run. For a project targeting a 60-second short-form video distributed across 20–30 segments, this absence of metadata means the creator can only discover that a segment is fatally too long or too short — perhaps a 90-word passage that will generate 36 seconds of audio, far overrunning a single cut — after waiting for the TTS engine to process it and reviewing the output.

At that point, the creator faces significant re-editing work: return to the segment, shorten the text, regenerate the audio, and re-check the duration — potentially repeating this loop several times per offending segment across an entire project. This feedback loop is expensive in both time and in TTS API credits (or compute time for local models). A professional authoring tool should surface this information preemptively, during text entry, so that creators can self-correct in real time before committing to generation.

Beyond duration, the plain textarea also gives no signal about TTS input quality thresholds. Very long strings (above roughly 500 characters) often produce subtly degraded intonation and unnatural pacing in neural TTS models, because the model's attention mechanism loses confidence over long input windows. Creators have no way to know when they have crossed this threshold without domain expertise. A simple color-coded character count warning removes this expert knowledge requirement entirely and makes the quality guidance implicit in the tool's interface.

### 1.2 Proposed Solution

Augment `SegmentTextEditor.tsx` with a lightweight real-time metadata overlay rendered directly below the textarea. This approach requires no third-party rich text library and no changes to the underlying textarea mechanics — it is purely additive UI. The overlay displays four categories of information computed in real time on every keystroke:

- **Character count** displayed with soft color-coded warnings that change from neutral to amber at 300 characters and from amber to red at 500 characters, reflecting the approximate thresholds where TTS intonation quality begins to degrade on long inputs.
- **Word count** derived from splitting the trimmed text on whitespace boundaries, giving creators an immediate sense of narration density without requiring any manual counting.
- **Estimated TTS duration** computed in real time from word count and the segment's `tts_speed` multiplier using the formula `(wordCount / (BASE_WPM * ttsSpeed)) * 60`, where `BASE_WPM = 150` represents a neutral voice speaking rate at 1.0× speed. The estimate updates on every keystroke and is displayed in seconds, making it practical to aim for specific segment durations without generating audio first.
- **Color-coded duration warnings** that shift from neutral to amber when the estimate exceeds 15 seconds, and from amber to red when it exceeds 30 seconds, aligning with the widely-cited 30-second guideline for individual visual cuts on short-form social platforms.
- **Documented extension points** for two future features: Feature 3.4's SSML pronunciation dictionary word highlighting (an overlay `<div>` pattern over the textarea) and Feature 5.3's narration pacing analysis badge (a WPM label derived from actual generated `duration`). Both are documented here as named integration targets but not implemented — they live as comment blocks in the component.

The solution deliberately avoids introducing any third-party rich text editor library (TipTap, Slate, Quill, CodeMirror, or similar). The current data model stores plain text strings and the Kokoro TTS engine receives plain text. Replacing the textarea with a `contenteditable`-based editor would add significant bundle weight, introduce complex event handling differences across browsers, and create a mismatch between the component output and the backend model's field type. All metadata value in this feature comes from the overlay panel beneath the textarea, not from formatting capabilities of the editing surface.

### 1.3 Scope

| Dimension | In Scope |
|---|---|
| Real-time character count below the textarea | ✅ Yes |
| Real-time word count below the textarea | ✅ Yes |
| Estimated TTS duration computed from word count and tts_speed | ✅ Yes |
| Color-coded warnings for overly long text (amber and red thresholds) | ✅ Yes |
| Warning when estimated duration exceeds 30 seconds | ✅ Yes |
| Extension point documented for SSML word highlight overlay | ✅ Yes (design only, not implemented) |

| Dimension | Out of Scope |
|---|---|
| SSML or pronunciation dictionary highlighting (deferred to Feature 3.4) | ❌ Not yet |
| Narration pacing badge (deferred to Feature 5.3) | ❌ Not yet |
| Markdown or rich text formatting support | ❌ No |
| Persisting word count or character count to the database | ❌ No |
| Per-project configurable WPM rate setting | ❌ Not in this feature |
| Mobile-specific layout for the metadata overlay | ❌ Not in this feature |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| `frontend/components/SegmentTextEditor.tsx` | Primary textarea for segment text; save-on-change/blur | Plain textarea; no metadata; no character/word count |
| `frontend/components/SegmentCard.tsx` | Container card; provides voice selector and other controls | Holds `tts_speed` value from segment data; does not pass it to SegmentTextEditor |
| `frontend/types/segment.ts` (or inline type) | TypeScript interface for the Segment data shape | Has `text_content`, `tts_speed`, `voice_id`, `audio_file`, `duration`, `is_locked` |
| `frontend/store/projectStore.ts` (or equivalent) | Zustand store for project and segment state | Holds segments array; no derived metadata computed |
| `frontend/app/projects/[id]/page.tsx` | Project detail page; renders Timeline and passes segment data | Passes full segment objects to child components |
| `frontend/lib/segmentUtils.ts` (or inline) | Utility functions for segment operations | May not exist yet; candidate location for estimation logic |

---

## 2. Flow Diagram

    METADATA COMPUTATION PIPELINE
    ==============================

    [ User types a character in the textarea ]
                   |
                   | onChange fires
                   v
    [ Local text state updates synchronously ]
                   |
                   v
    [ On every render, compute derived values: ]

      characterCount  = text.length

      trimmedText     = text.trim()
      words           = trimmedText === "" ? [] : trimmedText.split(/\s+/)
      wordCount       = words.length

      estimatedSecs   = wordCount === 0
                        ? 0
                        : (wordCount / (BASE_WPM * ttsSpeed)) * 60
                   |
      +------------+-------------+--------------+
      |                          |              |
      v                          v              v
    [ charColor ]           [ wordColor ]  [ durColor ]
      text.length < 300:       always          estimatedSecs < 15:
        text-muted              muted             text-muted
      300 – 500:                                15 – 30:
        text-amber-500                            text-amber-500
      > 500:                                    > 30:
        text-red-500                              text-red-500
      |
      +------------+-------------+--------------+
                   |
                   v
    [ Metadata row renders below the textarea ]

      text.length === 0 → row hidden (no zeros shown)
      text.length  > 0  → row visible:
        [ {charCount} chars ]  [ {wordCount} words ]  [ ~{estimatedSecs}s ]


    TTSESPEED PROP FLOW
    ====================

    SegmentCard
    (holds segment.tts_speed; renders voice selector)
                   |
                   | passes ttsSpeed = segment.tts_speed ?? 1.0
                   v
    SegmentTextEditor
    (receives ttsSpeed: number = 1.0)
                   |
                   | uses in duration formula on every render
                   v
    estimatedSecs = (wordCount / (BASE_WPM * ttsSpeed)) * 60


    FUTURE EXTENSION POINTS (deferred, not implemented here)
    =========================================================

    Feature 3.4 — SSML Word Highlight Overlay
    ------------------------------------------
    Positioned <div> rendered at same size / position as textarea
    Matching font family, size, line-height metrics
    Z-index: above textarea background, below textarea text
    pointer-events: none (clicks pass through to textarea)
    Colored <span> elements under pronunciation-dict matched words

    Feature 5.3 — Narration Pacing Badge
    -------------------------------------
    Renders only when segment.duration is non-null
    actualWPM = (wordCount / segment.duration) * 60
    Color-coded label: Slow / Normal / Fast / Too Fast
    Replaces estimated duration badge when real duration available

---

## 3. Step-by-Step Instructions

### Step 3.1 — Add ttsSpeed Prop to SegmentTextEditor

**File:** `frontend/components/SegmentTextEditor.tsx`

Extend the component's TypeScript props interface to include a `ttsSpeed` optional prop of type `number` with a default value of `1.0`. This prop represents the TTS playback speed multiplier stored on the backend Segment model as `tts_speed` (a FloatField that defaults to 1.0 in the database schema). It will be consumed exclusively by the duration estimation formula in Step 3.3 and has no effect on how text is saved to the API or how the textarea renders its content.

Mark the prop as optional with the TypeScript syntax `ttsSpeed?: number` in the props type and apply the default at the destructuring site: `({ text, onChange, ttsSpeed = 1.0, ...rest })`. This ensures that all existing call sites — including any unit tests that render the component in isolation — continue to compile and run without change. A missing `ttsSpeed` prop simply means the duration estimate uses the 1.0× baseline, which is the most conservative and informative fallback.

Add a one-line JSDoc comment above the prop declaration: something like "@prop ttsSpeed — multiplier used only for estimated duration display; does not affect TTS generation or saving behavior." This prevents future developers from mistakenly removing the prop thinking it serves no purpose.

### Step 3.2 — Pass ttsSpeed from SegmentCard to SegmentTextEditor

**File:** `frontend/components/SegmentCard.tsx`

Locate the line in `SegmentCard` where `SegmentTextEditor` is rendered. `SegmentCard` already has access to the full segment object (or its individual fields) because it renders the voice selector dropdown and the TTS speed slider, both of which require `voice_id` and `tts_speed`. Extract `tts_speed` from the segment props and pass it to `SegmentTextEditor` as the `ttsSpeed` prop.

Wrap the value with a nullish coalescing fallback before passing it: `ttsSpeed={segment.tts_speed ?? 1.0}`. This guard is essential because the Django model defines `tts_speed` as a FloatField that may be null in some edge-case database rows — particularly for segments created by early versions of the app or through direct database imports without the field populated. Passing `null` or `undefined` to `SegmentTextEditor` would produce `NaN` in the duration formula, resulting in a broken display.

This is the only change required in `SegmentCard.tsx` for this entire feature. Verify that the `tts_speed` value updates correctly when the user adjusts the speed slider — since `SegmentCard` should already receive updated segment data from local state on slider change, this should work without any additional wiring.

### Step 3.3 — Implement Metadata Computation in SegmentTextEditor

**File:** `frontend/components/SegmentTextEditor.tsx`

Declare a named constant `BASE_WPM = 150` at the module level (outside the component function) to represent the baseline words-per-minute speaking rate of the Kokoro TTS voice at 1.0× speed. Placing it at module level — not inline as a magic number inside the formula — makes it trivially easy to recalibrate later against real TTS output measurements.

Inside the component, immediately after the existing `text` state declaration, compute three derived values on every render. These computations are lightweight enough that wrapping them in `useMemo` is optional, but they can be memoized with `[text, ttsSpeed]` as dependencies if performance profiling on a large Timeline shows unnecessary rerender overhead:

**Character count:** `text.length`. Include all characters: spaces, punctuation, digits. Do not trim before counting — creators sometimes deliberately include spacing that affects TTS rhythm, and an accurate character count requires counting the raw string.

**Word count:** `text.trim().split(/\s+/).filter(Boolean).length`. The `.trim()` removes leading and trailing whitespace before the split so that a leading space does not produce a phantom empty element at index 0. The `/\s+/` regex splits on one or more consecutive whitespace characters, covering multiple spaces, tabs, and newlines that creators might paste in from external documents. The `.filter(Boolean)` provides a final safety net, removing any empty strings that could survive on edge-case inputs. When `text.trim()` is an empty string, the entire expression returns 0 correctly.

**Estimated seconds:** When `wordCount` is 0, return 0 directly. Otherwise compute `(wordCount / (BASE_WPM * ttsSpeed)) * 60` and round to one decimal place using `Math.round(result * 10) / 10`. The formula models speaking rate as inversely proportional to speed: at `ttsSpeed = 2.0`, a 150-word segment takes 30 seconds rather than 60, which is the correct real-world behavior for speed-multiplied TTS.

### Step 3.4 — Determine Warning Colors for Each Metric

**File:** `frontend/components/SegmentTextEditor.tsx`

For each metric badge, determine the Tailwind color utility class to apply based on threshold comparisons. Encapsulate each decision as a small helper expression — either an inline ternary chain or a tiny pure function scoped to the component file:

**Character count color:** Below 300 characters, apply `text-muted-foreground` (the standard ShadCN/UI muted token). From 300 to 500 characters inclusive, apply `text-amber-500`. Above 500 characters, apply `text-red-500`. The 300 and 500 thresholds are empirically derived from the point at which neural TTS models — including Kokoro — begin to show measurable degradation in intonation naturalness and pause placement on long input strings. These numbers are estimates and may be tuned after real-world testing.

**Estimated duration color:** Below 15 seconds, apply `text-muted-foreground`. Between 15 and 30 seconds inclusive, apply `text-amber-500` to signal that the segment is getting long for a single visual cut. Above 30 seconds, apply `text-red-500`. The 30-second boundary reflects the maximum recommended duration for a single visual cut in short-form social video — a cut longer than 30 seconds loses viewer attention on TikTok, Instagram Reels, and YouTube Shorts. The 15-second amber threshold provides an early warning that the creator is approaching this boundary.

**Word count color:** Always `text-muted-foreground`. Word count carries no quality warning threshold at this time — it is informational only.

### Step 3.5 — Render the Metadata Row Below the Textarea

**File:** `frontend/components/SegmentTextEditor.tsx`

Directly beneath the existing `<textarea>` element in the JSX output, add a `<div>` container for the metadata row. The container should use Tailwind flex layout (`flex flex-row items-center gap-3`) with a small font size (`text-xs`) to keep it compact and visually subordinate to the editing surface. It must not introduce any extra margin or padding that shifts the textarea's vertical position relative to the rest of the `SegmentCard` — use a tight top padding like `pt-1`.

Conditionally render the entire metadata row: when `text.length === 0`, render nothing (or a single non-distracting placeholder like a short horizontal rule or just empty space). Displaying "0 chars, 0 words, ~0.0s" on an empty textarea adds visual noise and could mislead creators into thinking the metadata is broken.

When `text.length > 0`, render three child `<span>` elements inside the container:

- **Character badge:** Display `{characterCount} chars` with the color class from the character count threshold logic. Example rendered text: "342 chars" displayed in amber when over the first threshold.
- **Word badge:** Display `{wordCount} words` always in `text-muted-foreground`. Example: "67 words".
- **Duration badge:** Display `~{estimatedSecs}s` with the color class from the duration threshold logic. Example: "~26.8s" in amber, "~34.2s" in red.

Separate the three spans using the `gap-3` spacing from the parent container or with a thin muted-color separator character if preferred. Do not use ShadCN `Badge` components for these items — they add border, background, and padding that makes the metadata row too prominent relative to the textarea. Plain styled `<span>` elements achieve the correct visual weight.

### Step 3.6 — Document Extension Points for Future Features

**File:** `frontend/components/SegmentTextEditor.tsx`

Add two clearly marked comment blocks in precise locations within the component. These comments are not decorative — they are the specification handed to the future AI agent or developer who will implement Features 3.4 and 5.3. Each comment must be specific and actionable, not vague.

The first comment block should appear just before the metadata row `<div>` (between the closing `</textarea>` tag and the opening of the metadata row container). It should explain Feature 3.4's SSML word highlight overlay in enough detail for an implementer to begin without reading the original feature document: "EXTENSION POINT — Feature 3.4 (Pronunciation Dictionary). Add a `<div>` here with `position: absolute`, matching the textarea's computed `width`, `height`, `font-family`, `font-size`, `line-height`, and `padding`. Set `pointer-events: none` and `overflow: hidden` on the overlay so all user interactions pass through to the textarea below. Inside the overlay, render the full text content as invisible (transparent color) text with `<span>` elements wrapping each word that matches a pronunciation dictionary entry. Apply a colored underline or background to those spans as the visual highlight. Wire visibility to a `showHighlights` prop that will be added in Feature 3.4."

The second comment block should appear just after the duration estimate `<span>`, immediately before the closing `</div>` of the metadata container.
It should describe Feature 5.3’s pacing badge: "EXTENSION POINT — Feature 5.3 (Narration Pacing Analysis).
When `segment.duration` is a non-null number (meaning TTS has already been generated for this segment),
replace the estimated duration badge above with a real pacing badge:
compute `actualWPM = (wordCount / segment.duration) * 60`,
classify as Slow (< 100 WPM), Normal (100–180 WPM), Fast (180–240 WPM), or Too Fast (> 240 WPM),
and render a color-coded label.
Accept `duration` as an optional prop of type `number | null` in the component’s props interface.
Only render this badge when `duration !== null`; otherwise fall through to the estimated duration display already in place."

### Step 3.7 — Cross-Browser and Edge-Case Validation

**File:** `frontend/components/SegmentTextEditor.tsx` (validation only; no code changes required)

Before marking this feature complete, execute a cross-browser spot-check of metadata row rendering and behavior
across the three browsers most used by StoryFlow creators: Chrome (latest stable), Firefox (latest stable), and Safari on macOS.
The metadata row uses only CSS flex layout and Tailwind utilities, so significant rendering differences are unlikely.
However, the `onChange` event wiring on the textarea has subtle cross-browser variations in how it fires during IME composition
(Chinese Pinyin, Japanese IME input, Korean Hangul)
that may cause the character count to briefly show intermediate composition characters that are not part of the final committed input.
This is cosmetic only, but should be noted in a QA findings comment if observed.

On iOS Safari in particular, `selectionStart` on a textarea may return `null` before the user has first tapped the field.
If Feature 1.4 (Segment Split & Merge) is developed in parallel and its cursor-tracking handler is already present on the same textarea,
ensure the cursor-change logic includes a defensive nullish fallback when reading `selectionStart`.
This prevents a `null` comparison TypeError from contaminating the word count computation in this feature.

Validate the word count computation against a set of edge-case input strings that are likely to appear in real story content:
- Strings with em-dashes used as sentence punctuation: “word—word” counts as one token (correct; em-dash is not whitespace).
- Strings with numeric values and units: “10,000 viewers” counts as two tokens: ’10,000’ and ‘viewers’ (correct).
- Multi-paragraph text pasted from a word processor, which may include carriage-return plus newline (`\r\n`) pairs.
  Confirm that `/\s+/` handles `\r\n` correctly or add explicit `\r` to the split pattern if not.
- A string consisting entirely of punctuation with no whitespace: should return 1 word token, not 0.

Verify that conditional hiding of the metadata row (`text.length === 0`) removes the `<div>` from the DOM entirely
rather than hiding it with CSS visibility or opacity.
Use browser DevTools to confirm the node is absent from the accessibility tree when the textarea is empty.
Hidden-but-present nodes are still read by screen readers, which would produce a confusing announcement
of “zero chars, zero words, zero seconds” for every new empty segment card in the Timeline.

---

## 4. Expected Outcome

1. Every segment's text editor displays a real-time character count below the textarea, updating on every keystroke with no perceptible lag, so creators can monitor text length while they type.
2. Every segment's text editor displays a real-time word count below the textarea, correctly derived from whitespace-delimited token splitting and robust to multiple consecutive spaces, leading whitespace, and pasted multi-line text.
3. Every segment's text editor displays an estimated TTS duration in seconds below the textarea, giving creators a predictive signal about generated audio length before the TTS engine is invoked.
4. The character count badge turns amber at 301 characters and red above 500 characters, providing a graduated visual signal that the segment text is approaching lengths associated with TTS quality degradation.
5. The estimated duration badge turns amber at 15.1 seconds and red above 30 seconds, aligning with the practical upper limit for a single visual cut in short-form social video content.
6. A segment with `tts_speed = 1.5` shows a shorter estimated duration than the same text content with `tts_speed = 1.0`, correctly reflecting the inverse relationship between speed multiplier and time.
7. A segment with `tts_speed = 0.8` (slower than baseline) shows a longer estimated duration, demonstrating that the formula works symmetrically in both directions.
8. When the textarea is empty, the metadata row is completely hidden — no zeros, no dashes, no placeholder text — presenting a clean uncluttered state for new segments.
9. The word count correctly returns zero for a string containing only whitespace, and correctly counts compound-hyphenated words and apostrophized contractions as single tokens because they contain no whitespace separator.
10. The component continues to save text to the backend on blur exactly as before, and the `onBlur` handler fires at identical timing to the pre-feature behavior — the metadata row is purely a visual addition and introduces no side effects on the save lifecycle.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] `computeWordCount("Hello world")` returns `2`
- [ ] `computeWordCount("  Hello   world  ")` returns `2` (whitespace-robust)
- [ ] `computeWordCount("")` returns `0`
- [ ] `computeEstimatedDuration(wordCount=150, ttsSpeed=1.0)` returns `60.0` seconds (150 words at 150 WPM = 60s)
- [ ] `computeEstimatedDuration(wordCount=150, ttsSpeed=1.5)` returns `40.0` seconds
- [ ] `computeEstimatedDuration(wordCount=0, ttsSpeed=1.0)` returns `0`
- [ ] Character color class is `text-amber-500` for `charCount=350`
- [ ] Character color class is `text-red-500` for `charCount=600`
- [ ] Duration color class is `text-muted-foreground` for `estimatedSecs=10`
- [ ] Duration color class is `text-amber-500` for `estimatedSecs=20`
- [ ] Duration color class is `text-red-500` for `estimatedSecs=35`
- [ ] Metadata row `<div>` is not rendered at all when `text === ""`
- [ ] Metadata row `<div>` is visible when `text.length > 0`

### 5.2 Integration / Manual Tests

- [ ] Type a 50-word paragraph into a segment; verify all three metadata badges update in real time with correct values
- [ ] Change the segment's `tts_speed` via the voice speed slider; verify the estimated duration badge updates to reflect the new speed
- [ ] Type until character count exceeds 300; verify badge turns amber without any page flicker or layout shift
- [ ] Continue typing past 500 characters; verify badge turns red
- [ ] Type a 100-word segment at `tts_speed = 1.0`; verify estimated duration is approximately 40 seconds and the badge is red
- [ ] Clear the textarea completely; verify the metadata row hides or shows the empty state indicator
- [ ] Verify that textual saving behavior (PATCH called on blur) is completely unaffected by the metadata row addition
- [ ] Open the component in a narrow viewport; verify the metadata row wraps or scrolls correctly without breaking the textarea layout
- [ ] Paste multi-paragraph text (with `\r\n` line endings) from a word processor; verify word count is correct
- [ ] Open DevTools on an empty segment card; confirm the metadata row `<div>` is absent from the DOM entirely

### 5.3 Regression Tests

- [ ] Existing `onBlur` save-to-API behavior still fires correctly after adding the metadata row
- [ ] `SegmentCard` renders without TypeScript errors when `tts_speed` is `null` in the segment data (nullish coalescing fallback)
- [ ] `SegmentTextEditor` renders without errors when `ttsSpeed` prop is not passed at all (optional prop default)
- [ ] No bundle size regressions from introducing a third-party rich text library — confirm no such library was accidentally added
- [ ] The feature interoperates cleanly with Feature 1.4 (Split & Merge) — metadata row shows correctly on both new cards after a split
- [ ] Changing `tts_speed` via the voice speed slider immediately updates the estimated duration badge without a page reload
- [ ] A segment whose `tts_speed` was null in the database shows the correct fallback of 1.0× in the duration estimate

---

## 6. Notes for AI Agent

- **No library imports are needed or permitted for this feature.**
  The requirements are fully satisfied with native React state, JavaScript string methods, and Tailwind classes.
  Do not add TipTap, Quill, Slate, CodeMirror, or any `contenteditable`-based solution.
  These libraries are large relative to the feature's actual scope.
  They introduce complex event-handling differences from native `<textarea>` elements.
  They require migrating the data model from a plain string to a structured document.
  That data model migration is a backend concern and is entirely out of scope for this feature.
  The native textarea approach is simpler, faster to implement, and zero added bundle size.

- **BASE_WPM = 150 is a calibration starting point, not ground truth.**
  The Kokoro ONNX model used by this project may speak at a different rate than 150 WPM at 1.0× speed.
  The actual rate depends on the voice identity, phoneme density, and natural pause insertion by the model.
  After the first set of real TTS outputs are generated for a test project, measure actual `duration` values.
  Compare actual durations against estimates from this formula across at least 20 representative segments.
  Adjust `BASE_WPM` to minimize the mean absolute error across that sample.
  Place the constant at the top of `SegmentTextEditor.tsx` as a named export, not buried inline.
  This makes it easy to tune without hunting through component logic.

- **The extension point comments are NOT optional.**
  They are the specification handoff for Feature 3.4 and Feature 5.3.
  A future AI agent implementing those features will locate them by searching the codebase for the comment strings.
  If the comments are absent, the agent may add the overlay or pacing badge in incorrect locations.
  That would require rework and could introduce layout regressions in the segment card.
  Place both comments precisely as specified in Step 3.6.
  Use the exact format `// EXTENSION POINT — Feature X.Y` so they are uniquely grep-findable.

- **Performance: keep the metadata row lean.**
  The Timeline may render 30 to 50 `SegmentCard` components simultaneously on a long project.
  Each card contains one `SegmentTextEditor`, which now renders a metadata row below the textarea.
  Total additional DOM nodes: three `<span>` elements per card — negligible render cost.
  Do NOT wrap these spans in `<Tooltip>`, `<Badge>`, `<Popover>`, or any ShadCN/UI component.
  ShadCN interactive components rerender internally on hover and focus events.
  Multiplied across 30–50 cards, that creates unnecessary rerender chains during mouse movement.
  Plain `<span>` nodes with Tailwind color classes are exactly sufficient for this use case.

- **The `ttsSpeed` nullish coalescing guard in SegmentCard is mandatory, not optional.**
  The backend's `tts_speed` field defaults to 1.0 for segments created through the normal UI flow.
  However, segments created via direct API calls, database migrations, or test fixtures may have null values.
  Without the `?? 1.0` fallback, a null `tts_speed` reaches the formula as `null`.
  The JavaScript expression `(wordCount / (BASE_WPM * null)) * 60` evaluates to `NaN`.
  The metadata row would render `NaN chars / NaN words / ~NaNs`, which is confusing and unprofessional.
  Always pass the guarded value: `ttsSpeed={segment.tts_speed ?? 1.0}` in `SegmentCard`.

- **Word count splitting: use `/\s+/` with `.filter(Boolean)` after `.trim()`.**
  Do not use `.split(' ')` — it creates empty string tokens for consecutive spaces.
  Do not use `.match(/\b\w+\b/g)` — word-boundary matching has Unicode edge cases with non-ASCII characters.
  Do not estimate word count from character count and an assumed average word length — it is inaccurate.
  The `.trim().split(/\s+/).filter(Boolean)` pattern handles spaces, tabs, newlines, and carriage returns.
  It is O(n) in string length and adds negligible compute overhead even on the maximum 500-character input.
  This pattern is established in the StoryFlow test suite; other approaches will fail existing tests.

- **TypeScript strict mode compliance is non-negotiable.**
  The `ttsSpeed?: number` optional prop type implies the value may be `undefined` at the call site.
  The component's internal default handles this through destructuring default assignment.
  Run `tsc --noEmit` in the `frontend/` directory after every change to catch type regressions early.
  Do not suppress type errors with `as any` or `// @ts-ignore` — resolve the root type issue instead.
  Ensure that `computeEstimatedDuration` is typed as `(wordCount: number, ttsSpeed: number) => number`.
  Export the function alongside the component so unit tests can import and test it in isolation.

- **Do not show the duration estimate while TTS generation is actively in progress.**
  If the segment has a `generatingAudio: true` indicator in local or server state, hide the estimate badge.
  The juxtaposition of an estimated duration beside a live generation spinner is visually contradictory.
  When actual `duration` becomes available after generation completes, the Feature 5.3 extension point takes over.
  The real pacing badge derived from actual `duration` supersedes the estimate automatically.
  Until Feature 5.3 is implemented, the estimate is only meaningful and should only display in the pre-generation state.

- **Implement in this strict order to isolate regressions at each step.**
  Step 1: Add `ttsSpeed?: number` prop to `SegmentTextEditor`; confirm all existing call sites compile.
  Step 2: Pass `tts_speed ?? 1.0` from `SegmentCard` down into `SegmentTextEditor`.
  Step 3: Declare `BASE_WPM = 150` at the module top; derive `characterCount`, `wordCount`, `estimatedSecs`.
  Step 4: Add color-threshold logic for character count (amber at 300, red at 500).
  Step 5: Add color-threshold logic for estimated duration (amber at 15s, red at 30s).
  Step 6: Render the metadata row as a conditional `<div>` hidden when `text.length === 0`.
  Step 7: Add the two extension point comment blocks in exact positions specified in Step 3.6.
  Step 8: Run unit tests from the verification checklist; run cross-browser smoke-check from Step 3.7.
