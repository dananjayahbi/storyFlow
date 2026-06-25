# Feature 1.4 — Segment Split & Merge

| Field | Value |
|---|---|
| **Feature ID** | 1.4 |
| **Title** | Segment Split & Merge |
| **Status** | 🟡 Planned |
| **Priority** | High |
| **Complexity** | Medium |
| **Estimated Effort** | 4–6 days |
| **Dependencies** | Feature 1.2 (Undo/Redo, optional integration), existing segment CRUD endpoints |
| **Output Files (NEW)** | None (optional: backend reorder endpoint in `api/views.py` + `api/urls.py`) |
| **Files Modified** | `frontend/components/SegmentCard.tsx`, `frontend/components/SegmentTextEditor.tsx`, `frontend/app/projects/[id]/page.tsx` (or equivalent hook file), `backend/api/views.py`, `backend/api/urls.py` |

---

## 1. Document Overview

### 1.1 Problem Statement

StoryFlow currently allows creators to add blank segments or delete existing ones, but there is no mechanism for surgically restructuring narrative content once it has been entered into the text fields. A creator who pastes a full story paragraph into a single segment — perhaps 200 words of narration describing an establishing shot — cannot break it into multiple visual cuts without performing several error-prone manual steps: creating a new blank segment, memorizing the intended cursor position in the original text, carefully cutting and re-entering the fragments by hand, and then manually re-adjusting the `sequence_index` values of all subsequent segments to restore the correct playback order. This process is slow, fragile, and introduces a meaningful risk of text loss or index corruption, particularly on projects with 20 or more segments where a single misordered index goes unnoticed until the final rendered video reveals the problem.

The inverse problem is equally obstructive. A creator who over-segmented a scene — for instance, splitting a single line of dialogue across two segments where one cohesive moment would serve the story better — must manually concatenate the two text fields, copy the combined result back into the correct textarea, delete the now-redundant segment, and verify that all remaining indices are still correct and gapless. Neither operation is remotely consistent with the iterative, low-friction drafting experience a professional story authoring tool should provide.

Beyond immediate editing friction, the absence of these two operations imposes a structural constraint on how creators approach StoryFlow: they must mentally pre-plan the exact segment breakdown of their script before entering any text, because restructuring after the fact is so costly. A tool that embraces exploratory drafting — type freely first, refine the cuts second — requires native split and merge operations to be genuinely useful at a professional level.

### 1.2 Proposed Solution

Introduce two complementary editing actions directly on the `SegmentCard` component: a **Split Here** action that divides a single segment into two at the current text cursor position, and a **Merge with Next** action that combines two consecutive segments into one. Both actions are destructive operations that modify sequence indices, so they must trigger a full resequence of the project's segments after execution. Both actions also invalidate any previously generated TTS audio on the affected segments, since the text content changes. The broad approach is:

- Add a contextual **Split Here** button inside or alongside `SegmentTextEditor` that becomes active only when the user's cursor rests at an interior position — strictly greater than index 0 and strictly less than the full `text_content` length. Splitting at either extreme would produce an empty segment on one side, which is invalid and must be prevented on both the client and the server.
- Wire `onKeyUp`, `onClick`, and `onSelect` event handlers to the underlying textarea in `SegmentTextEditor` so the component continuously reports the current `selectionStart` value to `SegmentCard` via an `onCursorChange` callback prop. This ensures that wherever the user's cursor happens to be when they click Split Here, the position is always up-to-date without requiring the user to explicitly mark anything.
- Add a **Merge with Next** button to the `SegmentCard` action bar, rendered disabled and visually grayed out for the final segment in the timeline since there is no subsequent segment to merge with. Pass an `isLast` boolean prop from the Timeline down to each card to drive this disabled state.
- Implement a resequence utility — either a frontend-side function that fires sequential PATCH calls to update each segment's `sequence_index` in sorted order, or a dedicated backend endpoint `POST /api/projects/{id}/reorder-segments/` that accepts an ordered array of segment IDs and updates indices atomically inside a single database transaction. The backend endpoint is strongly preferred for consistency and is the target recommendation in this document.
- After either operation, optimistically set `audio_file = null` in local React state before the API calls complete, then refresh the full segments list from the server to ensure client and server are in sync. Stale audio state must not persist after any operation that alters `text_content`.
- Both operations should maintain an `isOperationInFlight` boolean flag in local state that disables all split and merge buttons during pending network requests, preventing race conditions from rapid double-clicks or impatient rapid key sequences.

### 1.3 Scope

| Dimension | In Scope |
|---|---|
| Split a segment at cursor position into two segments | ✅ Yes |
| Merge the current segment with the immediately following segment | ✅ Yes |
| Recompute all `sequence_index` values after split or merge | ✅ Yes |
| Clear `audio_file` on affected segments after split/merge | ✅ Yes |
| New segment created by split inherits `voice_id` and `tts_speed` | ✅ Yes |
| Merged segment retains the first segment's `image_file` | ✅ Yes |

| Dimension | Out of Scope |
|---|---|
| Splitting a segment at multiple points simultaneously | ❌ No |
| Merging non-adjacent segments (only adjacent allowed) | ❌ No |
| Preserving audio by trimming/splicing audio files on split | ❌ No |
| Drag-to-select text range for partial merge/extract | ❌ No |
| Visual animation of the split/merge transition in the Timeline | ❌ No |
| Undo/redo integration (deferred, see Feature 1.2) | ❌ Not in this feature |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| `frontend/components/SegmentCard.tsx` | Renders one segment card with action buttons | Has delete, lock, duplicate buttons; no split/merge buttons |
| `frontend/components/SegmentTextEditor.tsx` | Textarea input for segment text; saves on change/blur | Plain textarea; does not expose cursor position to parent |
| `frontend/app/projects/[id]/page.tsx` | Project detail page; holds segments array in React state | Has handlers for add, delete, patch segment; no reorder logic |
| `frontend/hooks/useProjectSegments.ts` (or inline) | Custom hook managing segments state and API calls | Manages basic CRUD; no split/merge handlers |
| `backend/api/views.py` | Django views for segment CRUD and project endpoints | Has CRUD views; no reorder-segments endpoint |
| `backend/api/urls.py` | URL routing for API endpoints | Has segment CRUD routes; no reorder route |
| `backend/api/models.py` | Segment model definition | Has `sequence_index`, `text_content`, `audio_file`, `voice_id`, `tts_speed` |
| `backend/api/serializers.py` | DRF serializers for Segment model | Serializes all fields; handles partial PATCH |

---

## 2. Flow Diagram

    SPLIT OPERATION — Data Flow
    ============================

    [ User clicks or types in SegmentTextEditor ]
                  |
                  | onKeyUp / onClick / onSelect fires
                  v
    [ SegmentTextEditor calls onCursorChange(selectionStart) ]
                  |
                  v
    [ SegmentCard stores cursorPosition in local React state ]
                  |
                  | guard: cursor > 0 AND cursor < text.length ?
                  |
          YES ----+---- NO
          |               |
          v               v
    [ Split button    [ Split button
      ENABLED ]         DISABLED ]
          |
          | user clicks
          v
    [ onSplitSegment(segmentId, cursorPosition) called on project page ]
          |
          v
    [ isOperationInFlight = true; all split/merge buttons disabled ]
          |
          v
    [ Compute: before_text = text.substring(0, cursorPosition) ]
    [ Compute: after_text  = text.substring(cursorPosition)    ]
          |
          +---------------------------+
          |                           |
          v                           v
    [ PATCH current segment ]   [ POST new segment ]
      text_content=before_text    text_content=after_text
      audio_file=null             sequence_index=current+0.5
                                  voice_id=parent.voice_id
                                  tts_speed=parent.tts_speed
                                  audio_file=null
          |                           |
          +---------------------------+
                       |
                       v
    [ POST /api/projects/{id}/reorder-segments/ ]
      body: { ordered_ids: [id0, id1, id2, ...] }
      backend assigns sequence_index = 0, 1, 2, ...
                       |
                       v
    [ GET /api/projects/{id}/segments/ — refresh list ]
                       |
                       v
    [ React state updated; Timeline re-renders ]
    [ Two cards appear where one was; both show Audio Not Generated ]
                       |
                       v
    [ isOperationInFlight = false; buttons re-enabled ]


    MERGE OPERATION — Data Flow
    ============================

    [ User clicks "Merge with Next" on segment N ]
                  |
                  | guard: isLast === false ?
                  |
          YES ----+---- NO
          |               |
          v               v
    [ handler fires ]  [ button is disabled;
                         no action taken    ]
          |
          v
    [ isOperationInFlight = true ]
          |
          v
    [ Read segmentN.text and segmentN1.text from local state ]
    [ combined = segmentN.text + " " + segmentN1.text          ]
          |
          +---------------------------+
          |                           |
          v                           v
    [ PATCH segment N ]         [ DELETE segment N+1 ]
      text_content=combined       DELETE /api/.../segments/{N+1.id}/
      audio_file=null
      image_file=keep existing
          |                           |
          +---------------------------+
                       |
                       v
    [ POST /api/projects/{id}/reorder-segments/ ]
                       |
                       v
    [ GET segments — refresh; Timeline re-renders ]
    [ N+1 card gone; N card shows combined text + Audio Not Generated ]
                       |
                       v
    [ isOperationInFlight = false ]

---

## 3. Step-by-Step Instructions

### Step 3.1 — Expose Cursor Position from SegmentTextEditor

**File:** `frontend/components/SegmentTextEditor.tsx`

Extend the component's TypeScript props interface to include an optional `onCursorChange` callback prop that accepts a single `number` argument representing the current cursor offset within the textarea string. This prop must have a default value of a no-op function so that all existing call sites of `SegmentTextEditor` that do not supply the prop continue to compile and run without any modification — this is a strictly additive, non-breaking change.

Wire three event handlers to the native textarea element to ensure position is always current: `onClick` (captures mouse clicks that reposition the cursor without typing), `onKeyUp` (captures keyboard movements — arrow keys, Home, End, Page Up, Page Down, and regular character input keys), and `onSelect` (captures text selection gestures that also reposition the cursor anchor). In all three handlers, read `event.target.selectionStart` and call the `onCursorChange` prop with that integer value. Always prefer `selectionStart` over `selectionEnd` — for a split operation, the start of any selection is the more intuitive and consistent anchor point.

Do not add any logic around debouncing. Cursor position tracking is a microsecond operation and must be synchronous so that `SegmentCard` always has an up-to-date value ready when the user clicks Split Here. Add a brief JSDoc comment above the prop in the interface explaining its purpose and noting that it is consumed only by the split feature — future readers should understand that removing it would break Feature 1.4.

### Step 3.2 — Add Split Button to SegmentCard

**File:** `frontend/components/SegmentCard.tsx`

Declare two pieces of local React state inside `SegmentCard`: `cursorPosition` (number, initialized to 0) and `isOperationInFlight` (boolean, initialized to false). Pass an `onCursorChange` callback to the child `SegmentTextEditor` that updates `cursorPosition` whenever the cursor moves.

Derive a computed boolean `isSplitEnabled` that is true only when all three of the following conditions hold simultaneously: `cursorPosition` is strictly greater than zero, `cursorPosition` is strictly less than the current `text_content.length`, and `isOperationInFlight` is false. This triple guard prevents invalid operations and concurrent requests.

Render a dedicated "Restructure" action group in the segment card, visually separated from the primary actions (delete, lock, duplicate) by a divider. Inside this group, place a "Split Here" button using a scissors icon and an indigo or slate color scheme — the neutral palette signals a structural editing action rather than a destructive one. Set `disabled={!isSplitEnabled}` on the button. When clicked, call the `onSplitSegment(segmentId, cursorPosition)` handler prop from the parent and immediately set `isOperationInFlight = true` to prevent further clicks until the operation resolves.

### Step 3.3 — Add Merge with Next Button to SegmentCard

**File:** `frontend/components/SegmentCard.tsx`

Add a "Merge with Next" button inside the same "Restructure" action group introduced in Step 3.2, immediately beside the Split Here button. The button requires an `isLast` boolean prop supplied by the parent Timeline. When `isLast` is true, or when `isOperationInFlight` is true, the button must be visually disabled and non-interactive — render it with reduced opacity and the `disabled` HTML attribute set.

When clicked (and both conditions permit), the button invokes an `onMergeWithNext(segmentId)` handler prop received from the parent project page. No merge logic of any kind belongs inside `SegmentCard` — the card's sole responsibilities for this action are rendering the button, enforcing the guard conditions, and forwarding the call to the handler. All computation, API calls, and state management live in the project page or its custom hook.

Use a combine or converging-arrows icon as the button's visual indicator. The label text "Merge ↓" or "Merge with Next" both clearly communicate the downward merge direction. Keep the label concise — the Restructure group will be visually compact. After invoking `onMergeWithNext`, set `isOperationInFlight = true` in the same way the Split button does, gating both buttons until the operation resolves.

### Step 3.4 — Implement Split and Merge Handlers in Project Page

**File:** `frontend/app/projects/[id]/page.tsx` (or the custom segments hook)

Implement `handleSplitSegment(segmentId: number, cursorPosition: number)` as an async function. Begin by reading the target segment from local state and extracting `text_content`, `voice_id`, `tts_speed`, and `sequence_index`. Compute `before_text = text_content.substring(0, cursorPosition)` and `after_text = text_content.substring(cursorPosition)`. Validate that neither half is empty or purely whitespace before proceeding — if either is invalid, show a user-facing toast error and return early without making any API calls.

Fire the first API call: `PATCH /api/projects/{projectId}/segments/{segmentId}/` with body `{ text_content: before_text, audio_file: null }`. Await its completion. If this PATCH fails, display an error toast and return — no further operations should proceed after a failed first call, leaving both segments in the last known good state.

Fire the second API call: `POST /api/projects/{projectId}/segments/` with body `{ text_content: after_text, sequence_index: currentSegmentIndex + 0.5, voice_id, tts_speed, audio_file: null }`. Await its completion. If this POST fails, display an error toast advising the user to reload the page, because the original segment's text has already been reduced to `before_text` and `after_text` data is now orphaned in memory only.

If both calls succeed, invoke the resequence utility (Step 3.5), then call `GET /api/projects/{projectId}/segments/` to refresh the full segment list into local state. Resolve the `isOperationInFlight` flag in both the success and the failure code paths.

Implement `handleMergeWithNext(segmentId: number)` similarly: find the current segment and the next segment by sorting local state by `sequence_index` and taking the element one position later. Compute `combined_text` as a trimmed join. PATCH the current segment first; if it succeeds, DELETE the next segment. If either call fails, show a toast. After success, resequence and refresh.

### Step 3.5 — Implement Resequence Utility

**File:** `frontend/app/projects/[id]/page.tsx` or `frontend/lib/segmentUtils.ts`

After every split and every merge, all `sequence_index` values must be normalized to clean, consecutive integers starting from zero. The intermediate fractional index (e.g., 0.5) introduced during a split is a temporary placement device — it must never remain in the database after the operation completes, because downstream features that sort by `sequence_index` will behave incorrectly if the field contains non-integer values.

Approach A — Frontend-driven: After the split or merge API calls complete, sort all segments from local state by `sequence_index`, then fire a series of `PATCH /api/projects/{projectId}/segments/{id}/` calls — one per segment — each updating `sequence_index` to its position in the sorted array (0, 1, 2...). This approach requires N additional network requests for a project with N segments and does not guarantee atomicity, but it requires no new backend code and is sufficient for projects with fewer than 50 segments.

Approach B — Backend reorder endpoint (recommended): Implement `POST /api/projects/{projectId}/reorder-segments/` in the Django backend (see Step 3.6). Once implemented, the frontend resequence utility reduces to a single API call that passes the full sorted list of segment IDs. The backend assigns integer indices atomically inside a database transaction, guaranteeing consistency even if the request fails partway through. Use Approach B as the default target for this feature; document Approach A as a fallback if the backend endpoint cannot be delivered within the sprint.

The resequence utility function itself should be a small, pure function that accepts the current sorted segments array and returns an ordered list of IDs — the actual API calls are its caller's responsibility. This makes the utility easy to unit-test in isolation.

### Step 3.6 — Backend Reorder Endpoint

**File:** `backend/api/views.py` and `backend/api/urls.py`

In `views.py`, create a new API view — either a function-based view decorated with `@api_view(['POST'])` or a class-based `APIView` with a `post` method — mapped to the URL `projects/<int:project_id>/reorder-segments/`. The view must be protected by the same authentication and project-ownership checks used by the existing segment CRUD views; a user must not be able to resequence segments for a project they do not own.

The request body must be a JSON object with a single key `ordered_ids` containing an array of integer segment primary keys in the desired final order, from first (index 0) to last. The view performs three validation steps before writing to the database: (1) verify that every ID in `ordered_ids` exists and belongs to the specified `project_id`; (2) verify that the array length exactly matches the total number of segments belonging to that project — no IDs may be missing or duplicated; (3) verify the project itself exists and return HTTP 404 otherwise. If any validation step fails, return HTTP 400 with a descriptive error message.

On successful validation, open a database `transaction.atomic()` block and iterate through `ordered_ids` using `enumerate(ordered_ids, start=0)`, calling `Segment.objects.filter(id=seg_id).update(sequence_index=i)` for each. Commit the transaction. Return HTTP 200 with the full updated segment list serialized by the standard `SegmentSerializer`. In `urls.py`, register the new URL pattern adjacent to the existing segment CRUD routes, following the existing naming conventions in that file.

### Step 3.7 — Update Timeline to Pass isLast and Handler Props

**File:** `frontend/components/Timeline.tsx`

Before this feature, the Timeline maps over the segments array and renders each `SegmentCard` with segment data, but without any inter-card relational information. After this feature, it must supply two additional pieces of information to each card: whether the card is the last in the sorted order, and how to invoke the split and merge operations.

First, verify whether the Timeline already sorts segments by `sequence_index` before mapping. If it does not, add the sort — all downstream rendering and the `isLast` computation depend on the segments being in the correct order. Once sorted, compute `isLast = (index === sortedSegments.length - 1)` inside the map callback and pass it as a prop to `SegmentCard`.

Second, the `onSplitSegment` and `onMergeWithNext` handler functions live in the project page but must reach `SegmentCard`.
For a two-level component hierarchy (project page → Timeline → SegmentCard), prop-threading through the Timeline is the simplest and most readable approach:
the project page passes both handlers to `Timeline` as props, and the Timeline passes them onward to each `SegmentCard`.
If the project later grows to deeper hierarchies, replacing this prop-chain with a React context is a valid refactor — but it is unnecessary at this stage of the project.
Add both handler functions to the Timeline’s props interface and document their expected signatures clearly.

### Step 3.8 — Keyboard Accessibility and Error-State Communication

**Files:** All modified frontend files

Creators who rely on keyboard navigation must be able to reach and activate both the Split Here and Merge with Next buttons without a mouse.
Verify that pressing Tab within a `SegmentCard` moves focus through action buttons in a predictable order that includes both Restructure buttons.
The Split Here button must carry a descriptive `aria-label` — for example, "Split segment at cursor position" — rather than relying solely on the visible button label,
because screen-reader users need context that a specific cursor position is being used as the split point.

The disabled state of each button must communicate its reason to assistive technology.
When the Split button is disabled because the cursor is at position 0, add an `aria-describedby` reference pointing to a short hidden element reading "Position your cursor in the text first."
When disabled because the text is empty, the referenced element should say "No text to split yet."
The Merge with Next button requires special treatment when disabled due to `isLast`:
use `aria-disabled="true"` rather than the native HTML `disabled` attribute,
because native `disabled` removes the element from the Tab order entirely,
preventing screen-reader users from ever discovering the button exists.

For error communication, every failed API call during a split or merge must produce a specific, actionable toast notification.
A failed PATCH on the existing segment: "Could not update segment text — please try again."
A PATCH-succeeded but POST-failed split: "Segment was shortened but the second segment could not be created. Reload the page to restore a consistent state."
A PATCH-succeeded but DELETE-failed merge: "Segment text was updated but the duplicate could not be removed. Reload the page and delete it manually."
All toast notifications must include `role="alert"` so they are announced by screen readers without requiring focus.

After a successful split or merge and the Timeline re-render, keyboard focus must move programmatically to a predictable element.
When the Timeline refreshes its DOM after a state update, the element that previously held focus is destroyed.
Re-focus the first resulting segment card (the `before_text` card after a split, or the retained card after a merge) using a `useEffect` that fires after the list refresh resolves.
Without this, keyboard users are left with focus in an indeterminate location after every restructure operation.

---

## 4. Expected Outcome

1. A creator can position their cursor at any interior point within a segment's text field and click "Split Here" to immediately produce two consecutive segment cards in the Timeline, with the text precisely divided at the cursor offset — no manual copy-paste required.
2. The new segment produced by a split automatically inherits the parent segment's `voice_id` and `tts_speed` settings, so the creator can generate TTS for the new segment immediately without re-selecting voice options from scratch.
3. Both segments resulting from a split show the "Audio not generated" indicator immediately after the operation, even if the original segment had a valid generated audio file — stale audio is never associated with changed text.
4. A creator can click "Merge with Next" on any segment that is not the final one in the project to combine its text and the following segment's text into a single cohesive segment, eliminating unnecessary cuts in a single click.
5. The merged segment automatically retains the first segment's `image_file` as its visual, providing a deterministic and logical default — the leading visual cut survives the merge.
6. The merged segment immediately shows "Audio not generated" after the operation, correctly reflecting that the new combined text has never been sent to the TTS engine.
7. After every split and every merge, all `sequence_index` values in the database are clean, consecutive integers starting from zero — no fractional values (like 0.5) or gaps (like 0, 1, 3) are ever left persisted.
8. The "Merge with Next" button is visually disabled and non-interactive on the final segment card at all times, because there is no subsequent segment to merge with.
9. The "Split Here" button is disabled whenever the cursor rests at position 0 or at the full text length, ensuring neither half of a potential split would be an empty string.
10. All restructure buttons enter a disabled state during in-flight API requests and only re-enable after the complete operation — including resequence and list refresh — has resolved, preventing race conditions from double-clicks.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] `splitTextAtCursor("Hello world", 5)` returns `["Hello", " world"]` correctly
- [ ] `splitTextAtCursor("Hello", 0)` is treated as an invalid split and the button is disabled
- [ ] `splitTextAtCursor("Hello", 5)` is treated as an invalid split (cursor at end) and the button is disabled
- [ ] `mergeTexts("Hello", "world")` returns `"Hello world"` with correct single space separator
- [ ] `resequenceSegments([{id:1, seq:0}, {id:2, seq:0.5}, {id:3, seq:1}])` returns correct `[0,1,2]` index mapping
- [ ] `SegmentCard` renders Split button disabled when `cursorPosition === 0`
- [ ] `SegmentCard` renders Merge button disabled when `isLast === true`
- [ ] `onCursorChange` callback fires correctly on `onKeyUp` and `onClick` events in `SegmentTextEditor`
- [ ] `SegmentCard` renders with `isOperationInFlight = true` and both Split and Merge buttons show as disabled simultaneously
- [ ] `mergeTexts("  Hello  ", "  world  ")` returns `"Hello world"` with whitespace trimmed at the join boundary
- [ ] `resequenceIds` correctly handles an already-integer sequence `[0,1,2]` without mutation errors
- [ ] TypeScript compilation passes with `--strict` on all modified files; no implicit `any` or unhandled `null` warnings

### 5.2 Integration / Manual Tests

- [ ] Split a segment mid-sentence; verify two new cards appear in the Timeline in correct order
- [ ] Verify split: first card has text up to cursor, second card has text from cursor onward
- [ ] Verify split: second new card shows "Audio not generated", first card also shows "Audio not generated"
- [ ] Split a segment whose parent had generated audio; confirm `audio_file` is null on both resulting segments
- [ ] Merge two segments; verify single card appears with concatenated text and a single space between them
- [ ] Verify merge: retained card keeps first segment's image, second segment's image is discarded
- [ ] After split then merge, verify `sequence_index` values are sequential integers: 0, 1, 2...
- [ ] Rapidly click "Split Here" twice; verify the second click is ignored while first request is in flight
- [ ] After merge, verify that TTS speed slider and voice selector on the merged card reflect the first segment's original settings, not the deleted second segment's
- [ ] Verify that focus moves to the first resulting segment card after a split completes and the Timeline re-renders
- [ ] Simulate a failed POST during split by killing the network; verify the toast message contains specific partial-state language, not a generic error

### 5.3 Regression Tests

- [ ] Existing delete segment still works correctly after this feature is merged
- [ ] Existing duplicate segment still works correctly; duplicated card gets correct `sequence_index`
- [ ] Existing lock/unlock segment toggle is unaffected
- [ ] Adding a blank segment via the "Add Segment" button still appends at the end with the correct next `sequence_index`
- [ ] Segment card renders correctly with no `onSplitSegment` or `onMergeWithNext` prop (optional props with no-op defaults)
- [ ] Backend reorder endpoint correctly handles a project with only one segment (array of length 1 assigns `sequence_index = 0`)
- [ ] Backend reorder endpoint returns 400 if `ordered_ids` contains an ID that belongs to a different project
- [ ] Backend reorder endpoint returns 400 if `ordered_ids` has fewer IDs than the project's actual segment count

---

## 6. Notes for AI Agent

- **Implement in this strict order:**
  Step 1: Expose cursor position from `SegmentTextEditor` via the `onCursorChange` prop.
  Step 2: Add local cursor state and the `isSplitEnabled` guard to `SegmentCard`.
  Step 3: Add the Merge button with the `isLast` prop; test disabled state on last card.
  Step 4: Write handler stubs in the project page that `console.log` arguments without API calls.
  Step 5: Verify the correct `segmentId` and `cursorPosition` reach each handler stub.
  Step 6: Implement the backend reorder endpoint; test it independently with a REST client.
  Step 7: Replace handler stubs with real PATCH / POST / DELETE API calls.
  Step 8: Wire the Timeline `isLast` and handler props.
  This order ensures each layer is individually testable before the next is connected.

- **Resequence is not optional.**
  Skipping the resequence step after a split leaves a fractional `sequence_index` (e.g., 0.5) permanently in the database.
  Any feature that sorts by `sequence_index` — the video renderer, the Timeline display, the export pipeline — will behave incorrectly with fractional values.
  Any feature that computes `sequence_index + 1` to find the next segment will skip a gap and fail.
  Always call resequence after both the split and merge operations complete successfully.

- **The `+0.5` index is a transient placeholder only.**
  It allows the newly created segment to sort immediately after its parent before the resequence normalizes everything.
  Always guarantee the resequence call executes after both PATCH and POST calls succeed.
  Never treat the `+0.5` value as a valid finished state in any part of the codebase.
  If the resequence call itself fails, display an error and advise the user to reload the page.

- **Cursor position: always use `selectionStart`, never `selectionEnd`.**
  When the user has text selected (highlighted), `selectionStart` and `selectionEnd` differ.
  `selectionStart` is the anchor of the selection — the position where the selection begins.
  `selectionEnd` is the focus — where the selection ends.
  For a split, the anchor is the more intuitive and predictable split point.
  Using `selectionEnd` would silently split at the wrong position whenever any text is selected.

- **Empty-segment guard must exist on both ends.**
  Frontend validation: the `isSplitEnabled` derived boolean stops the request from being sent.
  Backend validation: reject a PATCH with empty or whitespace-only `text_content` with a 400 response.
  Both layers are required; do not rely on only one.
  An empty-segment guard prevents a segment with no text from ever reaching the TTS engine,
  which can produce undefined behavior or an empty audio file depending on the TTS backend.

- **Merge direction is intentionally limited to “Next” only.**
  A creator who wants to merge segment N with N-1 can do so by clicking “Merge with Next” on segment N-1.
  Implementing “Merge with Previous” would double the edge-case surface area.
  Boundary conditions, button placement decisions, and disabled states all multiply.
  Defer until there is explicit user research showing the “Previous” direction is meaningfully preferred.

- **API call ordering for split is failure-mode critical.**
  Always PATCH the existing segment first, then POST the new one.
  If the PATCH succeeds and the POST fails: the user sees a shortened segment, which is recoverable by reloading.
  If the POST were fired first and succeeded before a failed PATCH: the user has a ghost segment with duplicate text.
  Always choose the failure mode that is easier to explain and resolve.

- **Audio clearing must be optimistic.**
  Set `audio_file = null` in the local state update before the first API call begins, not after the last one succeeds.
  This prevents the UI from briefly showing a stale “Audio ready” badge on a segment whose text has already changed.
  The brief window while network requests are pending is long enough for a user to read the badge and be confused.

- **Keyboard accessibility is not optional.**
  Both buttons must be reachable via Tab key and activatable via Enter or Space.
  The Merge button must use `aria-disabled` (not native `disabled`) on the last segment.
  Native `disabled` removes the element from the Tab order, making it invisible to keyboard users.
  Run a keyboard-only walkthrough of the full split and merge flow before marking the PR ready for review.

- **Post-operation focus management prevents accessibility regressions.**
  After a split or merge, the Timeline re-renders and the previously focused DOM node is destroyed.
  Programmatically re-focus the relevant card after the React update cycle completes.
  Use a `useEffect` with a ref to the first resulting card, triggered after the segment list refresh.
  Without this, every keyboard user must navigate the entire page from the beginning after each restructure operation.
  This is a short implementation — typically 4–6 lines — but prevents a significant class of accessibility failures.
