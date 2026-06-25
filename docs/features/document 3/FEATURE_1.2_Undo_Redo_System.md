# Feature 1.2 — Undo/Redo System

| Field | Value |
|---|---|
| **Feature ID** | 1.2 |
| **Title** | Undo/Redo System |
| **Status** | 🟡 Planned |
| **Priority** | High |
| **Complexity** | Medium |
| **Estimated Effort** | 4–6 days |
| **Dependencies** | Zustand store pattern established in `settingsStore.ts`; project page state hook must expose segment list as a single serialisable object; no optimistic-UI conflicts with existing PATCH calls |
| **Output Files (NEW)** | `frontend/store/historyStore.ts`, `frontend/lib/snapshotUtils.ts` |
| **Files Modified** | `frontend/components/KeyboardShortcutProvider.tsx`, `frontend/app/projects/[id]/page.tsx`, `frontend/components/Timeline.tsx`, `frontend/hooks/useKeyboardShortcuts.ts`, `frontend/components/SegmentCard.tsx` |

---

## 1. Document Overview

### 1.1 Problem Statement

StoryFlow currently operates on a fully immediate-commit editing model in which every change a creator makes is instantly persisted to the Django REST backend with no intermediate buffer and no mechanism for reversal. Once a narration text edit is submitted, a segment is deleted, an image is replaced, or a reorder is confirmed, the previous state is permanently discarded with no recovery path available to the user under any circumstances. This is most dangerous during segment deletion: a user who accidentally clicks the delete button on the wrong card permanently loses that segment's narration text, image assignment, and all associated metadata immediately, with no confirmation gate and no retrieval mechanism. The problem compounds on medium-to-large projects containing 20 or more segments, where a creator may be rearranging multiple segments to restructure a narrative arc — a single misplaced drag-and-drop or accidental click can silently corrupt the intended sequence order without the user noticing until further downstream in the editing workflow. Undo functionality is one of the most universally expected features in any content creation tool, present in word processors, image editors, code editors, video editors, and spreadsheet applications alike; its absence from StoryFlow creates a significant confidence gap that actively discourages experimentation. A creator who wants to try an alternative phrasing for a segment but cannot undo the change will typically avoid making the edit at all, reducing the quality of the final output. Professional creators evaluating StoryFlow against competitor tools will immediately identify the missing undo system as a reliability concern. Restoring confidence in the editing experience requires a durable, transparent undo/redo system that feels natural and imposes no visible latency on normal editing operations.

### 1.2 Proposed Solution

Introduce a client-side command history system built as a dedicated Zustand store named `historyStore`. Rather than reimplementing the browser's native undo stack or intercepting low-level DOM events, the system operates at the application state snapshot level: before any mutating action is dispatched to the server, the current project editing state is deep-cloned and pushed onto an immutable `past` array. After a series of undos, a corresponding `future` array retains the superseded states so that redo can walk forward through the same sequence. When the user invokes undo, the system pops the most-recent snapshot from `past`, applies it to the live project state, and fires the same PATCH API calls that any normal edit would use — undo is architecturally transparent to the Django backend. The system integrates with the existing `KeyboardShortcutProvider` and also exposes toolbar buttons in `Timeline.tsx` for pointer-based interaction.

Key implementation decisions:

- Snapshots are defined as plain serialisable JavaScript objects containing a typed array of segment descriptor fields and a small set of project-level settings; no class instances, DOM nodes, React refs, or binary file objects are included.
- The history stack is hard-capped at 50 entries; when the cap is exceeded, the oldest entry is automatically discarded so that memory consumption remains bounded regardless of session length.
- Text-change snapshots use a 500 millisecond debounce on the text-field blur event so that rapid successive keystrokes do not each generate their own history entry; only the stable committed state is recorded as one snapshot.
- Performing any new mutating action after a series of undos clears the entire `future` array, enforcing the standard linear-history model that users universally recognise from other editors.
- Undo and redo operations set an `isSyncing` flag on the history store during the server round-trip to prevent stacking further undo calls while a prior undo's API writes are still resolving.
- The history stack is project-scoped and is cleared on both page mount and page unmount to ensure that stale snapshots from one project never appear when a different project is opened in the same browser session.
- Two computed boolean getters — `canUndo` (derived from `past.length > 0`) and `canRedo` (from `future.length > 0`) — drive the disabled state of the toolbar buttons and the event guards in the keyboard handler.
- The entire implementation lives in the frontend; no Django migration, no new API endpoint, and no backend schema change is needed.

### 1.3 Scope

| Area | In Scope |
|---|---|
| Narration text edits, captured on blur after a 500 ms debounce | ✅ Yes |
| Segment delete operations, snapshot taken immediately before deletion fires | ✅ Yes |
| Drag-and-drop segment reorder, snapshot taken before the reorder is committed | ✅ Yes |
| Image upload and replacement, snapshot taken before the new image URL is committed | ✅ Yes |
| Project-level voice or settings values stored in the project page state | ✅ Yes |
| Ctrl+Z (undo) and Ctrl+Shift+Z (redo) keyboard shortcuts | ✅ Yes |
| Undo and Redo toolbar buttons in Timeline with reactive disabled state | ✅ Yes |
| Automatic history clearing on project page mount and unmount | ✅ Yes |

| Area | Out of Scope |
|---|---|
| Undo of audio regeneration, which is a backend async job without a synchronous state counterpart | ❌ Out of scope for this feature |
| Undo of project-level deletion from the dashboard page | ❌ Out of scope — a confirmation dialog handles destructive intent there |
| Persisting history across browser refreshes using localStorage or IndexedDB | ❌ Out of scope — history is in-memory for this iteration |
| Collaborative multi-user history merging or operational transform | ❌ Out of scope — StoryFlow is single-user per project editing session |
| Fine-grained character-by-character text undo within the textarea (native browser behaviour) | ❌ Out of scope — the native textarea undo is not suppressed |
| A visual history panel listing all past operations by name | ❌ Out of scope — may be addressed in a later enhancement |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| `frontend/store/historyStore.ts` | New Zustand store with `past[]`, `present`, `future[]`, `isSyncing`, and `pushState` / `undo` / `redo` / `clearHistory` actions | Does not exist — must be created |
| `frontend/lib/snapshotUtils.ts` | New utility module with `deepCloneSnapshot` and `buildSnapshotFromState` helper functions | Does not exist — must be created |
| `frontend/store/settingsStore.ts` | Reference implementation for the Zustand `create<T>()` and typed interface pattern used across the project | Exists and working — use as a style guide |
| `frontend/components/KeyboardShortcutProvider.tsx` | Wraps the entire application; registers named shortcut actions; currently handles Ctrl+S, Ctrl+R, and three others | Exists — requires two new shortcut registrations and `preventDefault` calls |
| `frontend/hooks/useKeyboardShortcuts.ts` | Custom hook that maps key combos to action strings and invokes registered callbacks | Exists — may require updated union type for the new action names |
| `frontend/app/projects/[id]/page.tsx` | Project editing page; owns or proxies the segment list state and all mutating handlers | Exists — each mutating handler needs a snapshot push inserted before the API call |
| `frontend/components/Timeline.tsx` | Renders the ordered list of segment cards and a top-level project toolbar | Exists — needs an Undo button and a Redo button added to the toolbar |
| `frontend/components/SegmentCard.tsx` | Individual segment card; fires text-change, delete, and image-upload events to parent | Exists — text blur handler needs to trigger the debounced snapshot capture |

### 1.5 Guiding Principles and Architecture Notes

Four core principles govern how the history system integrates with StoryFlow's existing architecture without introducing tight couplings or requiring backend changes.

**Principle 1 — The store is a passive container**

The history store holds and retrieves snapshots but never directly modifies project state. The project page retains sole ownership of the segment array and all API dispatch responsibilities. This separation keeps the store independently testable in isolation and prevents history management from becoming entangled with the data layer or with React rendering cycles.

**Principle 2 — Undo is transparent to the backend**

The Django REST API does not and should not distinguish between a PATCH dispatched by a user typing in a text field and a PATCH dispatched by an undo operation restoring a prior snapshot. Both use the same endpoint and the same payload format. This transparency means no parallel undo-record system is needed on the backend, and the entire feature stays within the frontend boundary with no Django migration required.

**Principle 3 — Snapshot granularity is action-based, not character-based**

One snapshot corresponds to one logical user action: finishing a text edit, deleting a segment, completing a reorder, or confirming an image replacement. Recording one snapshot per keystroke would exhaust the 50-entry budget within seconds of typing. The debounce on the text-change handler ensures that each typing session appears in the history stack as a single discrete undoable step rather than dozens of micro-states.

**Principle 4 — History does not cross project boundaries**

Clearing the history store on both mount and unmount ensures that a creator who navigates between two projects never accidentally undoes an edit that belonged to the previously opened project. Cross-project history leakage would be deeply disorienting and could result in unintended data overwrites in the wrong project with no obvious indication of what went wrong.

---

## 2. Flow Diagram

  ┌───────────────────────────────────────────────────────┐
  │               PROJECT PAGE INITIAL LOAD               │
  │                                                       │
  │   historyStore.clearHistory()  ←  called on mount     │
  │   past = []    future = []    isSyncing = false        │
  │   canUndo = false   canRedo = false                    │
  └────────────────────────┬──────────────────────────────┘
                           │
                           ▼
    User performs a mutating action
    (text blur / delete / reorder / image upload)
                           │
                           ▼
      buildSnapshotFromState(currentState)
        → strips non-serialisable fields
        → sorts segments by sequence_index
        → returns typed ProjectSnapshot
                           │
                           ▼
      deepCloneSnapshot(snapshot)  →  clone
                           │
                    ┌──────┴──────────────────────────────┐
                    │    historyStore.pushState(clone)     │
                    │                                      │
                    │    if past.length >= 50:             │
                    │       past.shift()  (drop oldest)    │
                    │    past.push(clone)                  │
                    │    future = []  (clear redo stack)   │
                    └──────┬──────────────────────────────┘
                           │
                           ▼
      Execute mutation  →  PATCH API call dispatched
                           │
                           ▼
      UI reflects new present state
      canUndo = true    canRedo = false
      Undo button: ENABLED   Redo button: DISABLED

  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─

  User presses Ctrl+Z  (or clicks toolbar Undo button)
                           │
                           ▼
      Guard: canUndo && !isSyncing?   NO → return early
                           │
                           ▼
      isSyncing = true
      restoredSnapshot = past.pop()
      future.push( deepClone(currentPresentState) )
                           │
                           ▼
      applySnapshot(restoredSnapshot)
        → diff each segment field vs current state
        → PATCH only changed segment fields
        → await Promise.all( patchPromises )
                           │
                           ▼
      isSyncing = false
      UI reflects restored state
      canUndo = past.length > 0
      canRedo = true   (Redo button: ENABLED)

  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─

  User presses Ctrl+Shift+Z  (or clicks toolbar Redo button)
                           │
                           ▼
      Guard: canRedo && !isSyncing?   NO → return early
                           │
                           ▼
      isSyncing = true
      restoredSnapshot = future.pop()
      past.push( deepClone(currentPresentState) )
                           │
                           ▼
      applySnapshot(restoredSnapshot)  →  PATCH + await
                           │
                           ▼
      isSyncing = false
      UI reflects re-applied state
      canUndo = true    canRedo = future.length > 0

  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─

  User navigates away from project page
                           │
                           ▼
      historyStore.clearHistory()  ←  called on unmount
      past = []    future = []

---

## 3. Step-by-Step Instructions

### Step 3.1 — Create `historyStore.ts`

**File path:** `frontend/store/historyStore.ts`

Create a new file in the `frontend/store/` directory. Begin by defining a TypeScript interface named `ProjectSnapshot` that describes the minimal serialisable shape of the project editing state: an array of segment descriptor objects each containing the fields `id` (string), `sequence_index` (number), `text_content` (string), `is_locked` (boolean), and `image_reference` (string or null). Next define a second interface `HistoryState` with the following fields: `past` typed as `ProjectSnapshot[]`, `future` typed as `ProjectSnapshot[]`, `isSyncing` typed as boolean, and four action functions with the signatures `pushState(snapshot: ProjectSnapshot): void`, `undo(): ProjectSnapshot | null`, `redo(): ProjectSnapshot | null`, and `clearHistory(): void`. In the Zustand `create<HistoryState>()` call, implement `pushState` so that it appends the incoming snapshot to `past`, resets `future` to an empty array, and enforces the 50-entry cap by calling `past.shift()` whenever `past.length` would exceed 50 after the push. Implement `undo` to pop the last entry from `past` and return it, returning null if `past` is empty. Implement `redo` symmetrically on `future`. Implement `clearHistory` to set both arrays to empty and `isSyncing` to false. Export two derived boolean values `canUndo` and `canRedo` as computed selectors based on the array lengths.

### Step 3.2 — Create `snapshotUtils.ts`

**File path:** `frontend/lib/snapshotUtils.ts`

Create a new utility file in the `frontend/lib/` directory. Expose a function `deepCloneSnapshot` that accepts any serialisable value and returns a fully independent deep copy. Use `structuredClone` as the primary implementation, which is natively available in modern browsers and Node.js 17 and above and handles nested objects, arrays, and dates correctly without any external dependencies. Wrap the `structuredClone` call in a try/catch block that falls back to `JSON.parse(JSON.stringify(input))` for older runtimes such as test environments running on Node.js 16, ensuring the utility does not throw in non-browser contexts. Expose a second function `buildSnapshotFromState` that accepts the raw project page state — typically a segment array plus any project-level settings values that are part of the editable view — and returns a typed `ProjectSnapshot` object ready to be cloned and pushed. Inside this function, explicitly map only the whitelisted serialisable fields (`id`, `sequence_index`, `text_content`, `is_locked`, `image_reference`) from each segment object, discarding any fields that are not part of the snapshot contract such as event callbacks, loading flags, error states, React refs, or File/Blob instances. Sort the output segment array by `sequence_index` before returning, so that snapshots are always in a canonical order regardless of how the in-memory state array is ordered.

### Step 3.3 — Insert Snapshot Captures Before Each Mutation

**File path:** `frontend/app/projects/[id]/page.tsx`

Open the project page or its companion state hook and locate every function that performs a state mutation followed by an API write. The functions to target are: the narration text-change commit handler (fired on focus-out or after a debounce), the segment delete handler, the drag-and-drop reorder completion handler, and the image upload success callback. For each handler, insert a snapshot capture as the very first statement of the function body: call `buildSnapshotFromState(currentState)` to construct a snapshot of the pre-mutation state and then immediately call `historyStore.pushState(snapshot)` before any async logic or state update runs. The narration text-change handler requires special treatment because it fires on every keystroke: wrap the snapshot capture in a 500 millisecond debounce so that only the stable committed state at the end of a typing pause is recorded. The debounce timer should be reset on each keystroke and the snapshot push should happen when the timer fires, meaning the snapshot captures the state immediately before the first character of the current typing burst was entered. After the snapshot insertion, leave all existing API call logic and state-update logic in each handler completely unchanged.

### Step 3.4 — Implement `applySnapshot` Restoration Logic

**File path:** `frontend/app/projects/[id]/page.tsx`

Add a new async function named `applySnapshot` in the project page scope. This function accepts a `ProjectSnapshot` and is called internally by both `handleUndo` and `handleRedo`. Its first action is to set `historyStore.isSyncing = true` to lock further undo operations during the network round-trip. It then retrieves the current live segment list from the project page state and performs a field-by-field comparison between each segment in the restored snapshot and its counterpart in the live state (matched by `id`). Only segments that differ in at least one field are included in the PATCH batch. The function constructs one PATCH promise per changed segment, targeting the Django endpoint for that individual segment and including only the fields that differ in the payload. It calls `Promise.all` on all PATCH promises and, once every request resolves, updates the project page's local state with the restored snapshot's segment array. The state update must be atomic — either all changes apply or none — by first awaiting the full `Promise.all` before touching the local state array. Wrap the entire operation in a try/finally block where the `finally` clause sets `historyStore.isSyncing = false` regardless of success or failure. If a PATCH request rejects, display a non-blocking toast notification but do not roll back the local state update that has already been applied.

### Step 3.5 — Add `handleUndo` and `handleRedo` Functions

**File path:** `frontend/app/projects/[id]/page.tsx`

Define two new public functions: `handleUndo` and `handleRedo`. The `handleUndo` function reads `canUndo` and `isSyncing` from `useHistoryStore` at the call site, returning early with no visible effect if either condition blocks the operation. It then takes a deep clone of the current present state and calls `historyStore.undo()` to retrieve the most recently pushed snapshot. It passes the retrieved snapshot to `applySnapshot` and awaits the result. The `handleRedo` function mirrors this exactly: it checks `canRedo` and `isSyncing`, clones current state, calls `historyStore.redo()` for the snapshot, and calls `applySnapshot`. Both functions should be wrapped in `useCallback` with an appropriate dependency array to avoid triggering unnecessary re-renders when passed as props to the Timeline toolbar or the keyboard provider. Both functions should be exported from the project page component scope so they can be used by any component in the project editing subtree.

### Step 3.6 — Register Keyboard Shortcuts

**File path:** `frontend/components/KeyboardShortcutProvider.tsx`

Open the keyboard provider component and locate the section where shortcut key bindings are registered. Add a new binding entry for Ctrl+Z that calls `handleUndo` and calls `event.preventDefault()` before invoking the handler, to prevent the browser's native document undo behaviour from firing and competing with the custom history system. Add a second binding for Ctrl+Shift+Z that calls `handleRedo` with the same `event.preventDefault()` guard. Add two additional guards to both handlers: first, check that `document.activeElement` is not a native input or textarea element before processing, so that the user's normal character-level undo inside a text field is not hijacked; second, check `historyStore.isSyncing` and short-circuit if a sync is already in progress to prevent unbounded undo stacking during slow network conditions. Update the documentation comment block at the top of the provider file where existing shortcuts are listed to include the two new entries with a short description of each.

### Step 3.7 — Add Toolbar Buttons and Clear History on Unmount

**File path:** `frontend/components/Timeline.tsx` and `frontend/app/projects/[id]/page.tsx`

In `Timeline.tsx`, locate the toolbar section at the top of the component. Import `useHistoryStore` and read `canUndo` and `canRedo` from it. Add two ShadCN `Button` components positioned as an adjacent pair in the toolbar: one labelled "Undo" with an undo-arrow icon, and one labelled "Redo" with a redo-arrow icon. Wire each button's `onClick` to the corresponding `handleUndo` and `handleRedo` props passed down from the project page. Set the `disabled` prop of the Undo button to `!canUndo` and the Redo button to `!canRedo`. Wrap each button in a ShadCN `Tooltip` that displays the keyboard shortcut hint in parentheses. In `page.tsx`, add a `useEffect` that returns a cleanup function calling `historyStore.clearHistory()` to wipe the history when the user navigates away. Add a second call to `clearHistory()` at the top of the component body (outside any effect) or inside a mount-only `useEffect` to ensure the store starts clean every time the project page is entered.

---

## 4. Expected Outcome

1. Users can press Ctrl+Z at any point during a project editing session to revert the most recently committed change, with the restored content becoming immediately visible in every affected segment card.
2. The restored state is synchronised to the Django backend via PATCH calls within the same operation, so the server always reflects the same state the UI is showing.
3. Users can press Ctrl+Shift+Z to reapply any previously undone operation, stepping forward through the redo history stack until the most recent edit is reached.
4. The Undo toolbar button is visually enabled when history is available and visually disabled when the `past` array is empty; the same applies symmetrically to the Redo button.
5. Tooltips on the toolbar buttons hint the keyboard shortcuts so that users who click the buttons discover the keyboard equivalents naturally.
6. Rapid typing in a narration text field generates a single history entry per pause rather than one per keystroke, keeping the 50-slot history budget from being consumed by minor incremental edits.
7. Segment delete, image replace, and drag-and-drop reorder are all individually undoable and appear as discrete steps when stepping back through history with repeated Ctrl+Z presses.
8. The history stack silently enforces its 50-entry limit by dropping the oldest entry; the user is never shown an error for exceeding the limit, and the Undo button simply disables when no earlier snapshots remain.
9. Navigating away from a project and opening a different project starts with a fully empty history — no snapshots from the previous project appear in the new session.
10. Any new edit made after undoing one or more operations clears the redo stack instantly and disables the Redo button, preventing branching history confusion.
11. During an undo or redo sync operation, a loading indicator is visible in the toolbar area and further undo/redo keyboard events are silently ignored until the sync completes.
12. No new Django migration files, no new API endpoints, and no changes to the backend `Segment` model or its serialiser are required by this feature.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] `historyStore.pushState` appends the snapshot to `past` as the last element and simultaneously clears `future` to an empty array, verified by inspecting both arrays after the call.
- [ ] `historyStore.undo` returns the last element that was pushed to `past`, removes it from the array, and does not modify `future` or any other store field during the retrieval step itself.
- [ ] `historyStore.redo` returns the last element of `future`, removes it from the array, and leaves `past` unchanged during the retrieval step.
- [ ] `canUndo` is false when `past` is empty and becomes true immediately after a single `pushState` call, confirming reactive derivation from the array length.
- [ ] `canRedo` is false when `future` is empty and becomes true after an `undo` call that moves an entry into `future`.
- [ ] After exactly 51 consecutive `pushState` calls with distinct snapshot values, `past.length` is exactly 50 and the snapshot from the first call is no longer in the array.
- [ ] `deepCloneSnapshot` returns a value that is deeply equal to the input (all fields match) yet shares zero object references — mutating a nested field in the clone must not change the corresponding field in the original.
- [ ] `clearHistory` called on a store with 48 entries in `past` and 2 entries in `future` resets both arrays to empty and `isSyncing` to false without throwing any error.

### 5.2 Integration / Manual Tests

- [ ] Type a new sentence into a segment narration field, wait longer than 500 ms, then press Ctrl+Z — the original pre-edit text reappears in the field and the network inspector shows a PATCH request carrying the restored text value.
- [ ] Delete a segment card, then press Ctrl+Z — the segment card reappears in the Timeline at its original position with its sequence index, narration text, and image reference all intact.
- [ ] Drag a segment from position 2 to position 8 in the Timeline, then press Ctrl+Z — the segment returns to position 2 and all other segments return to their prior positions.
- [ ] Perform four sequential edit operations of different types (text, reorder, delete, image), then press Ctrl+Z four times, verifying that each press restores exactly one operation in reverse chronological order.
- [ ] After four undos, press Ctrl+Shift+Z four times — the state advances forward through each operation and returns correctly to the most recent state as it was before the undos.
- [ ] Click the Undo toolbar button with a pointer device — the behaviour is identical to pressing Ctrl+Z in all observable ways including network activity.
- [ ] Perform a new text edit after two undos, confirm the Redo button disables immediately and Ctrl+Shift+Z has no effect.
- [ ] Navigate away from the project page and return — confirm both toolbar buttons are disabled on arrival with an empty history store.

### 5.3 Regression Tests

- [ ] The existing Ctrl+S save shortcut continues to fire its handler correctly and does not conflict with the new Ctrl+Z registration in any browser tested.
- [ ] The text editor's existing API debounce for normal non-undo edits still triggers PATCH requests within the expected time window on edits that are not followed by an undo.
- [ ] The single-segment delete button on an individual `SegmentCard` still removes only that segment correctly when pressed on a project with an empty history store.
- [ ] Settings changes managed by `settingsStore.ts` that are unrelated to the project segment list do not interact with `historyStore` and are neither snapshotted nor reversed by undo operations.
- [ ] Timeline rendering performance with 30 segments is not visibly degraded by the presence of the new `useHistoryStore` hook subscription anywhere in the component tree.

---

## 6. Notes for AI Agent

- Always create `historyStore.ts` and `snapshotUtils.ts` first and verify they compile cleanly before modifying any component or page file. Downstream TypeScript errors caused by an incomplete store type are significantly harder to trace than missing-file errors.

- The `ProjectSnapshot` type contract must be locked before implementing `buildSnapshotFromState` or `applySnapshot`. Any mismatch between the fields captured in a snapshot and the fields expected by `applySnapshot` will produce silent data corruption — segments may appear to restore correctly at first glance but have stale locked states or wrong sequence indices.

- Never include audio file binaries, `File` API objects, `Blob` instances, or base64-encoded image strings in the snapshot. Attempting `structuredClone` on a `File` or `Blob` will either throw a `DataCloneError` or return an empty object depending on the browser. Only string URL references (or null) should represent image and audio associations.

- The debounce on the text-change snapshot capture must fire at the leading edge of each new typing burst, capturing the pre-edit state before any character is appended. A trailing-edge debounce would capture the state after the first character has been added, meaning undo would restore a partially-edited state rather than the clean state before the user began typing.

- When `applySnapshot` constructs the PATCH batch, compare fields individually per segment rather than serialising and string-comparing entire snapshot objects. On a 30-segment project, only one or two segments typically differ between adjacent snapshots, so sending one targeted PATCH per changed field is far more efficient than sending 30 full-segment PATCHes.

- Test the 50-entry cap with an explicit off-by-one unit test using exactly 50 pushes (no overflow), exactly 51 pushes (first overflow drop), and exactly 52 pushes (two items dropped). Off-by-one errors in array-cap logic are the single most common source of bugs in ring-buffer implementations and are not caught by casual manual testing.

- Register the Ctrl+Z keyboard handler with a modifier-key guard that requires exactly and only the Ctrl key — no Shift, Meta, or Alt modifiers. Without this guard, Ctrl+Shift+Z would match both the Redo handler and a misconfigured Undo handler simultaneously, causing them to cancel each other in some shortcut frameworks.

- If the project page uses optimistic UI patterns where the local state is updated immediately before the PATCH response arrives from the server, take the snapshot from the last server-confirmed state rather than the optimistically-updated local state. Snapshotting after an optimistic update means undo would restore a state the server may have rejected, creating a divergence between frontend and backend that is very difficult to diagnose.

---

## 7. Implementation Order and Effort Breakdown

### 7.1 Recommended Build Sequence

The seven implementation steps must be completed in a specific dependency order. Building UI components before the underlying store or utility module is ready produces import errors and misleading TypeScript cascades. The recommended order by phase is:

**Phase 1 — Foundation utilities (Day 1)**

These two files have zero dependencies on any other new code and must exist before any consumer is written.

- Create `frontend/lib/snapshotUtils.ts` and implement `deepCloneSnapshot` with the `structuredClone` primary path and `JSON.parse` fallback.
- Implement `buildSnapshotFromState` with a strict whitelist of serialisable field names, sorting the output by `sequence_index`.
- Write unit tests covering clone independence, whitelist enforcement, and sort order before continuing.
- Create `frontend/store/historyStore.ts` and implement all four actions with the 50-entry cap and the `canUndo` / `canRedo` computed getters.
- Write unit tests for `pushState`, `undo`, `redo`, `clearHistory`, and the cap logic at boundaries 49, 50, 51, and 52 pushes.

**Phase 2 — State integration in the project page (Days 2–3)**

Intercept mutating handlers without changing their core logic flow.

- Identify all four target handlers in `page.tsx`: text-change commit, segment delete, drag-drop reorder, and image upload completion.
- Insert `buildSnapshotFromState` and `historyStore.pushState` as the first two statements of each handler, wrapping the text-change version in a 500 ms leading-edge debounce.
- Implement `applySnapshot` with per-segment field-level diff, `Promise.all` for parallel PATCH dispatch, and the `isSyncing` flag inside a `try/finally` block.
- Implement `handleUndo` and `handleRedo` as thin wrappers that call the guard checks and delegate to `applySnapshot`.

**Phase 3 — Timeline toolbar (Day 3–4)**

Surface the undo and redo controls visually before wiring keyboard events.

- Add the Undo `Button` and Redo `Button` as an adjacent pair in the `Timeline.tsx` toolbar, wired to `handleUndo` and `handleRedo` props.
- Bind the `disabled` prop of each button to `canUndo` and `canRedo` from `useHistoryStore`.
- Wrap each button in a ShadCN `Tooltip` showing the keyboard shortcut text.
- Test both buttons with mouse clicks in a running browser instance, confirming network activity and UI state changes.

**Phase 4 — Keyboard shortcut registration (Day 4)**

Add shortcuts only after confirming the underlying functions work correctly from the toolbar.

- Register Ctrl+Z → `handleUndo` with `event.preventDefault()` and the `document.activeElement` guard.
- Register Ctrl+Shift+Z → `handleRedo` with `event.preventDefault()` and the same `activeElement` guard.
- Add the `isSyncing` early-return guard to both handlers to prevent keyboard-mashing during sync.
- Verify all five previously registered shortcuts still function without interference.

**Phase 5 — Lifecycle management and polish (Days 5–6)**

- Add `clearHistory()` to the `useEffect` unmount cleanup return function in `page.tsx`.
- Add a second `clearHistory()` in a mount-only `useEffect` to reset state after hot-reloads during development.
- Add a toolbar loading indicator that is visible while `isSyncing` is true.
- Add a non-blocking toast notification path in `applySnapshot` for PATCH failures.
- Write the leading-edge debounce edge-case test and the mid-undo new-edit redo-clearing test.

### 7.2 Dependency Map

| Step | Must Precede | Depends On |
|---|---|---|
| `snapshotUtils.ts` | `historyStore.ts`, snapshot inserts in page | Nothing |
| `historyStore.ts` | Snapshot inserts, `applySnapshot`, and both handle functions | `snapshotUtils.ts` |
| Snapshot inserts in `page.tsx` handlers | `applySnapshot` integration | `historyStore.ts` |
| `applySnapshot` function | `handleUndo` and `handleRedo` functions | Snapshot inserts in page |
| `handleUndo` and `handleRedo` | Toolbar buttons and keyboard shortcuts | `applySnapshot` |
| Toolbar buttons in `Timeline.tsx` | Nothing further | `handleUndo`, `handleRedo`, `canUndo`, `canRedo` |
| Keyboard shortcuts in provider | Nothing further | `handleUndo`, `handleRedo` |

### 7.3 Per-Step Effort Estimates

| Step | Optimistic | Realistic | Pessimistic | Primary Risk Factor |
|---|---|---|---|---|
| `snapshotUtils.ts` | 1.5 hrs | 2.5 hrs | 4 hrs | Discovering non-serialisable fields in page state late |
| `historyStore.ts` | 1.5 hrs | 2.5 hrs | 4 hrs | Off-by-one in 50-item cap slice logic |
| Snapshot inserts in page | 2 hrs | 4 hrs | 7 hrs | Unknown complexity of existing handler structure |
| `applySnapshot` function | 3 hrs | 5 hrs | 9 hrs | Per-field diff and PATCH failure handling combinations |
| `handleUndo` and `handleRedo` | 0.5 hrs | 1 hr | 1.5 hrs | Minimal risk — thin wrappers with guards only |
| Keyboard shortcuts | 1 hr | 1.5 hrs | 2.5 hrs | Modifier-key guard correctness across OS variants |
| Toolbar buttons and tooltips | 1.5 hrs | 2 hrs | 3.5 hrs | ShadCN Tooltip exact API usage |
| Lifecycle cleanup and polish | 0.5 hrs | 1 hr | 2 hrs | Identifying correct useEffect dependency array |

### 7.4 Risk Register

| Risk | Likelihood | Impact | Mitigation Strategy |
|---|---|---|---|
| Snapshot contains a `File` or `Blob`, causing `structuredClone` to throw `DataCloneError` | Medium | Critical | Enforce a strict whitelist of serialisable fields in `buildSnapshotFromState` |
| Debounce fires on trailing edge, snapshot captures post-edit state instead of pre-edit | Medium | High | Explicitly configure and test leading-edge debounce behaviour with a 600 ms wait |
| `isSyncing` not cleared after a PATCH failure, permanently blocking all future undo | Medium | Critical | Wrap all sync logic in `try/finally`; write a unit test that simulates a PATCH rejection mid-undo |
| Off-by-one in the 50-entry cap allows the 51st snapshot to persist in memory | Medium | Low | Write explicit unit test with push counts of 49, 50, 51, and 52 in sequence |
| Ctrl+Z shortcut hijacks native character-level undo inside a textarea field | Low | Medium | Guard against firing when `document.activeElement` is an input or textarea element |
| `applySnapshot` sends full-segment PATCHes to all 30 segments instead of only changed ones | Low | Medium | Implement per-segment field-level diff before constructing the PATCH batch |

### 7.5 Definition of Done

The undo/redo feature is considered fully complete when every one of the following conditions holds without exception:

- All 8 unit tests in section 5.1 pass in CI without any skipped assertions or `todo` markers.
- All 8 integration/manual tests in section 5.2 produce the exact described result when executed in Chrome with the DevTools Network panel open.
- All 5 regression tests in section 5.3 confirm zero change in observable behaviour for existing features.
- Running `tsc --noEmit` on the entire `frontend/` directory produces zero new TypeScript errors.
- The Undo and Redo toolbar buttons are both visible and correctly positioned as an adjacent pair in the project editing toolbar.
- Both toolbar buttons render a ShadCN tooltip on hover displaying the human-readable keyboard shortcut hint.
- Pressing Ctrl+Z exactly 60 times on a project with 50 snapshots in history stops at the 50th step, disables the Undo button, and throws no errors.
- Opening two different projects in the same browser session without refreshing produces fully empty history (both buttons disabled) on each project page load.
