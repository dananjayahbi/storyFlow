# Feature 1.3 — Multi-Select Segments

| Field | Value |
|---|---|
| **Feature ID** | 1.3 |
| **Title** | Multi-Select Segments |
| **Status** | 🟡 Planned |
| **Priority** | High |
| **Complexity** | Medium |
| **Estimated Effort** | 5–7 days |
| **Dependencies** | Segment list rendered and owned inside `frontend/app/projects/[id]/page.tsx`; `Segment` model has `is_locked` field on backend; `KeyboardShortcutProvider.tsx` shortcut registry is functional; ShadCN Button and Tooltip components available |
| **Output Files (NEW)** | `frontend/store/selectionStore.ts`, `frontend/components/BulkActionToolbar.tsx` |
| **Files Modified** | `frontend/components/SegmentCard.tsx`, `frontend/components/Timeline.tsx`, `frontend/components/KeyboardShortcutProvider.tsx`, `backend/api/views.py`, `backend/api/urls.py`, `backend/api/serializers.py` |

---

## 1. Document Overview

### 1.1 Problem Statement

StoryFlow currently restricts all segment operations to single-segment granularity, which means every action a creator wants to perform must be executed one card at a time regardless of how many cards need the same treatment. A creator working on a 30-segment video project who wants to regenerate audio for every segment after switching the project voice must click the regenerate button 30 individual times. A creator who wants to delete the last ten segments to restructure the ending of their video must individually confirm ten delete operations in sequence. A creator who wants to lock the first five segments to protect already-approved content while still editing the rest must toggle the lock icon five times with no way to operate on the group at once. This is not merely an inconvenience; on large projects the time cost is significant enough that creators may avoid making correct structural decisions simply to avoid the repetitive clicking involved in implementing them. The problem is especially acute for AI-generated story outlines, which StoryFlow's typical user receives as a 20-to-40-segment first draft that almost always requires substantial structural editing before production. There is currently no selection state tracked anywhere in the frontend data model, no visual affordance on segment cards for indicating which are selected, and no toolbar surface that exposes batch operations on a group of segments. The feature is standard in virtually every list-based content editing interface and its absence makes StoryFlow feel unfinished compared to professional timeline and script editing tools.

### 1.2 Proposed Solution

Introduce a first-class multi-selection system composed of three interlocking pieces: a dedicated Zustand `selectionStore` to manage which segment IDs are currently selected, a modified click-interaction model on `SegmentCard` that respects standard Ctrl+Click and Shift+Click modifier conventions, and a new floating `BulkActionToolbar` component that appears at the bottom of the viewport whenever the selection set is non-empty. Selection state is kept entirely separate from segment data state so that selecting and deselecting segments is zero-cost and triggers no API calls by itself. API calls are triggered only when the user actively invokes one of the bulk action buttons in the toolbar.

Key design decisions for this implementation:

- The selection store holds a `Set<string>` of selected segment IDs rather than an index array, which gives O(1) membership tests, automatic deduplication, and a simple equality check via set size.
- A separate `anchorId` field in the store tracks the segment that was last activated without the Shift key held, allowing Shift+Click to calculate a correct contiguous range even after previous Ctrl+Click toggles have built up a non-contiguous selection.
- The range selection model is exclusive: Shift+Click replaces the selection with the contiguous range between the anchor and the clicked segment, rather than unioning the range with the existing selection. This matches the behaviour of most file manager and list applications.
- Selection state is ephemeral: it is never persisted to the server, never included in undo/redo history snapshots, and is cleared on navigation away from the project page.
- The `BulkActionToolbar` component is rendered as a React portal targeting `document.body` to ensure it floats above all scrollable content, regardless of the segment list length or nested overflow containers.
- Two new backend endpoints are required: a bulk delete endpoint and a bulk patch (lock/unlock) endpoint. Both must validate that all requested segment IDs belong to the given project before executing any database operations.
- The Escape key clears the current selection without performing any action, and Ctrl+A selects all segments in the project. Both are registered as named shortcuts in the existing `KeyboardShortcutProvider`.
- The "Regenerate Audio for Selected" button is included in the toolbar as a visible placeholder button for the current iteration but is rendered in a disabled state since bulk audio regeneration is a separate async-job feature not implemented in this iteration.

### 1.3 Scope

| Area | In Scope |
|---|---|
| Ctrl+Click (or Cmd+Click on macOS) to toggle individual segment selection | ✅ Yes |
| Shift+Click to extend selection as a contiguous range from the anchor to the target | ✅ Yes |
| Ctrl+A to select all segments in the current project | ✅ Yes |
| Escape to clear the current selection with no data operation | ✅ Yes |
| Bulk delete selected segments via a new backend endpoint | ✅ Yes |
| Bulk lock and unlock selected segments via a new backend endpoint | ✅ Yes |
| Move selected segments up or down one position in sequence order | ✅ Yes |
| Visual selected state on segment cards (border highlight and checkbox icon) | ✅ Yes |

| Area | Out of Scope |
|---|---|
| Bulk audio regeneration (separate async job feature, placeholder button only) | ❌ Out of scope for this document |
| Rubber-band drag-to-select with a mouse selection rectangle | ❌ Out of scope — modifier-key interaction only |
| Selection persistence across browser refreshes or page navigations | ❌ Out of scope — ephemeral in-memory only |
| Cross-project segment copying or moving | ❌ Out of scope |
| Touch / mobile multi-select via long-press or swipe gesture | ❌ Out of scope for this iteration |
| Moving a selected group to an arbitrary target position (only up/down one step) | ❌ Out of scope |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| `frontend/store/selectionStore.ts` | New Zustand store managing `selectedSegmentIds` Set, `anchorId`, and selection action functions | Does not exist — must be created |
| `frontend/components/BulkActionToolbar.tsx` | New floating bulk-action toolbar that renders via React portal when selection is non-empty | Does not exist — must be created |
| `frontend/components/SegmentCard.tsx` | Individual segment card; needs click-handler modifier logic and selected visual state applied | Exists — needs modifications to click handling and visual layer |
| `frontend/components/Timeline.tsx` | Renders all segment cards; needs to mount `BulkActionToolbar` and pass ordered segment IDs to cards | Exists — needs minor modifications |
| `frontend/components/KeyboardShortcutProvider.tsx` | Shortcut registry; needs Ctrl+A and Escape registered with appropriate guards | Exists — needs two new shortcut entries |
| `backend/api/views.py` | Django REST views; needs two new view classes for bulk delete and bulk lock/unlock | Exists — needs new view classes added |
| `backend/api/urls.py` | URL router for the API; needs routes for both new bulk views | Exists — needs two new URL patterns |
| `backend/api/serializers.py` | DRF serialisers; needs a new request-validation serialiser for bulk-action bodies | Exists — needs one new serialiser class |

### 1.5 Guiding Principles and Architecture Notes

Four core principles govern how the multi-select system integrates with StoryFlow's existing frontend architecture.

**Principle 1 — Selection state is separated from segment data state by design**

Storing selection in a dedicated `selectionStore` rather than as a boolean field inside each segment object means that selecting and deselecting segments is a zero-latency operation that never triggers any API activity. If selection were embedded in segment objects, every toggle would cause the entire segment list to re-render and potentially trigger unwanted server synchronisation side-effects.

**Principle 2 — Selection is ephemeral and never written to the server**

Segment selection is a client-facing interaction affordance, not a piece of business data. Persisting selection to the backend would impose unnecessary API overhead and create confusing multi-tab behaviour where selecting a segment in one browser tab would highlight it in all other tabs viewing the same project. Ephemeral in-memory selection avoids all of these complications.

**Principle 3 — The anchor ID range model follows universal operating system conventions**

Windows Explorer, macOS Finder, Linux file managers, most email clients, and most IDE file trees all implement Shift+Click range selection by extending from a fixed anchor point to the clicked item. Using this universally familiar model means creators will find the interaction predictable without reading any documentation, reducing the feature's onboarding friction to zero.

**Principle 4 — Bulk endpoints are thin and write-only from the frontend's perspective**

The backend bulk endpoints perform the database operation and return a success status. The frontend is entirely responsible for reconciling local state after a successful bulk operation. This clean boundary prevents the backend from needing to understand the frontend's rendering model or selection concept, and keeps the Django views small, focused, and testable independently of any frontend state.

---

## 2. Flow Diagram

  ┌──────────────────────────────────────────────────────────┐
  │              PROJECT PAGE INITIAL STATE                  │
  │                                                          │
  │   selectionStore.selectedSegmentIds = Set{}              │
  │   selectionStore.anchorId = null                         │
  │   selectionStore.selectionCount = 0                      │
  │   BulkActionToolbar: not rendered (count === 0)          │
  └────────────────────────┬─────────────────────────────────┘
                           │
  ─ ─ ─ ─ ─ ─ PLAIN CLICK on segment card (no modifier) ─ ─ ─
                           │
                           ▼
      clearSelection()   then   toggleSelection(id)
      anchorId = id
      selectedIds = Set{ id }
      BulkActionToolbar renders: "1 selected"
      Card highlights with blue ring + checkbox icon

  ─ ─ ─ ─ ─ ─ CTRL+CLICK on a second segment card ─ ─ ─ ─ ─ ─
                           │
                           ▼
      toggleSelection(id2)   (no clearSelection)
      anchorId = id2
      selectedIds = Set{ id, id2 }
      BulkActionToolbar: "2 selected"
      Second card highlights; first remains highlighted

  ─ ─ ─ ─ ─ ─ SHIFT+CLICK on a third card ─ ─ ─ ─ ─ ─ ─ ─ ─
                           │
                           ▼
      selectRange(anchorId=id2, clickedId=id3, orderedIds[])
      Slice indices from ordered array: find idx(id2), idx(id3)
      Select all IDs in slice [min..max] inclusive
      selectedIds = Set{ all cards from id2 to id3 in order }
      BulkActionToolbar count badge updates

  ─ ─ ─ ─ ─ ─ CTRL+A keyboard shortcut ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
                           │
                           ▼
      selectAll(orderedSegmentIds)
      selectedIds = Set{ all segment IDs }
      BulkActionToolbar: "N selected" (full count)

  ─ ─ ─ ─ ─ ─ USER CLICKS "Delete Selected" ─ ─ ─ ─ ─ ─ ─ ─ ─
                           │
                           ▼
      if count > 3: show confirmation dialog
                           │
                           ▼
      DELETE /api/projects/{id}/segments/bulk/
      body: { ids: [...selectedIds] }
                           │
                           ▼
      Backend: validate IDs belong to project → delete → 204
                           │
                           ▼
      Filter local segment list to remove deleted IDs
      clearSelection()
      BulkActionToolbar disappears

  ─ ─ ─ ─ ─ ─ ESCAPE key or Clear button ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
                           │
                           ▼
      clearSelection()
      selectedIds = Set{}   anchorId = null
      All cards return to unselected visual state
      BulkActionToolbar unmounts (count === 0)

The diagram above traces the complete selection state lifecycle: from initial page load through Ctrl+Click toggles, Shift+Click range extensions, Ctrl+A full selection, bulk action dispatch, and finally Escape clearance.

---

## 3. Step-by-Step Instructions

### Step 3.1 — Create `selectionStore.ts`

**File path:** `frontend/store/selectionStore.ts`

Create a new file in the `frontend/store/` directory. Define a TypeScript interface `SelectionState` containing the fields `selectedSegmentIds` typed as `Set<string>`, `anchorId` typed as `string | null`, and the following action function signatures: `toggleSelection(id: string): void`, `selectRange(fromId: string, toId: string, orderedIds: string[]): void`, `selectAll(orderedIds: string[]): void`, and `clearSelection(): void`. Also expose a computed getter `selectionCount` returning `selectedSegmentIds.size`. Export a `useSelectionStore` hook using Zustand's `create<SelectionState>()` factory, following the same pattern used in `settingsStore.ts`. Implement `toggleSelection` so that it creates a new Set from the existing one (never mutating in place), adds the ID if absent or deletes it if present, and then updates `anchorId` to this ID. Implement `selectRange` by receiving the fully ordered segment ID array, finding the indices of `fromId` and `toId` within it, taking the inclusive slice between the lower and higher index regardless of which argument is lower, and replacing `selectedSegmentIds` with a new Set built from that slice. Implement `selectAll` by replacing `selectedSegmentIds` with a new Set built from the entire `orderedIds` array. Implement `clearSelection` by resetting `selectedSegmentIds` to an empty Set and `anchorId` to null. Because Zustand's shallow equality check does not detect mutations inside a Set, always assign a brand-new Set instance rather than calling `.add()` or `.delete()` on the existing reference.

### Step 3.2 — Modify `SegmentCard.tsx` for Multi-Select Click Handling

**File path:** `frontend/components/SegmentCard.tsx`

Open the existing component and read its current click-handling behaviour. The card root container element (likely a `div`) needs an enriched `onClick` handler that inspects the `MouseEvent` for keyboard modifier flags. Add the following conditional logic inside the handler: if `event.ctrlKey` or `event.metaKey` is true (Meta covers the Command key on macOS), call `toggleSelection(segment.id)` and `event.preventDefault()` to suppress any browser text-selection side-effects. If `event.shiftKey` is true, call `selectRange(anchorId, segment.id, orderedSegmentIds)` where `orderedSegmentIds` is the complete ordered array passed as a new prop from the parent `Timeline`; also call `event.preventDefault()`. If neither modifier is held and the click target is not a nested interactive element (guard against clicks on buttons, the text editor, or audio controls propagating up), call `clearSelection()` followed by `toggleSelection(segment.id)`. Read `selectedSegmentIds` and `anchorId` from `useSelectionStore` at the top of the component. Derive an `isSelected` boolean as `selectedSegmentIds.has(segment.id)`. Apply conditional Tailwind classes to the card root using `isSelected`: add a coloured ring (`ring-2 ring-blue-500`) and a subtle background tint when selected or restore the default border when not. In the top-left corner of the card, render a ShadCN `Checkbox` component with a `checked` value equal to `isSelected` and `readOnly` set to true to display selection state visually without taking additional click events.

### Step 3.3 — Create `BulkActionToolbar.tsx`

**File path:** `frontend/components/BulkActionToolbar.tsx`

Create a new component file. At the top of the component body, read `selectedSegmentIds`, `selectionCount`, and `clearSelection` from `useSelectionStore`. If `selectionCount === 0`, return null immediately so the component renders nothing when no segments are selected. When `selectionCount > 0`, use `ReactDOM.createPortal` to render the toolbar's JSX into `document.body`, ensuring the toolbar floats above all scrollable and overflow-clipped containers in the page layout. Inside the portal, render a fixed-position container anchored to the bottom-centre of the viewport using Tailwind utility classes such as `fixed bottom-6 left-1/2 -translate-x-1/2 z-50`. Inside this container, render a horizontal pill-shaped panel with a light shadow and backdrop blur for visual separation from the segment list behind it. The panel should contain the following controls from left to right: a count badge reading "N selected" styled as a small rounded label; a "Delete Selected" ShadCN `Button` with the destructive colour variant; a "Lock" `Button`; an "Unlock" `Button`; a "Move Up" `Button` with an upward chevron icon; a "Move Down" `Button` with a downward chevron icon; a disabled "Regenerate Audio" `Button` (placeholder for the future async job feature, rendered with a tooltip explaining it is coming soon); and a close/X `Button` on the far right that calls `clearSelection()`. All primary action buttons receive their handler functions as props passed from the project page. On narrow viewports, collapse the text labels and display only icon buttons using responsive Tailwind classes.

### Step 3.4 — Add Bulk Action Handlers in the Project Page

**File path:** `frontend/app/projects/[id]/page.tsx`

Add three groups of bulk action handlers in the project page scope and pass them down to `BulkActionToolbar` as props. The first handler, `handleBulkDelete`, reads the current `selectedSegmentIds` Set from `useSelectionStore`, converts it to an array of ID strings, and — if the count exceeds three — shows a ShadCN `AlertDialog` confirmation before proceeding. On confirmation (or immediately if count is three or fewer), it sends a single DELETE request to `/api/projects/{id}/segments/bulk/` with the ID array in the request body, awaits the 204 response, filters the local segment list state to remove the deleted IDs, and then calls `clearSelection()`. The second handler, `handleBulkLock`, accepts a boolean `locked` argument and sends a PATCH to `/api/projects/{id}/segments/bulk/` with the body containing the selected IDs and the target `is_locked` value. On success it updates the `is_locked` field of each affected segment in the local state and calls `clearSelection()`. The third handler pair, `handleBulkMoveUp` and `handleBulkMoveDown`, reads the selected IDs, finds their current `sequence_index` values, shifts each by plus or minus one, checks for boundary constraints to prevent moving the first segment further up or the last segment further down, and fires PATCH requests for the changed indices. Pass the ordered segment ID array as a prop to `Timeline` and through `Timeline` to each `SegmentCard` so the `selectRange` action has access to the correct sequence order at all times.

### Step 3.5 — Add Bulk Endpoints to the Django Backend

**File paths:** `backend/api/views.py`, `backend/api/urls.py`, `backend/api/serializers.py`

In `serializers.py`, add a new DRF serialiser class named `BulkSegmentActionSerializer`. This serialiser validates a request body containing an `ids` field defined as a `ListField` of the segment primary key type (integer or UUID depending on the current model) and an optional `is_locked` boolean field used only for the PATCH variant. In `views.py`, add a new class-based view `BulkSegmentActionView` that handles `DELETE` and `PATCH` HTTP methods at the same URL. The `delete` method receives the project primary key from the URL kwargs, validates the request body through `BulkSegmentActionSerializer`, queries for `Segment` objects matching both the provided IDs and the given project to prevent cross-project operations, deletes the matched records, and returns a 204 response with no body. The `patch` method performs the same ownership validation query, updates the `is_locked` field on all matched segments using a bulk `queryset.update()` call for efficiency, and returns a 200 response with the serialised updated segments. In `urls.py`, register the new view at the path `projects/<int:project_pk>/segments/bulk/` and ensure this URL pattern appears before any `<int:pk>/` wildcard pattern in the same router to prevent the literal string "bulk" from being interpreted as an integer primary key value.

### Step 3.6 — Register Keyboard Shortcuts for Selection Control

**File path:** `frontend/components/KeyboardShortcutProvider.tsx`

Open the keyboard provider and add two new entries to the shortcut registration block. The first maps Ctrl+A to a `handleSelectAll` callback: this callback retrieves the current ordered segment ID array from the project page context or a provided prop and calls `selectionStore.selectAll(orderedIds)`. Include `event.preventDefault()` inside this handler to prevent the browser from activating its native Select All text-selection behaviour across the entire page. The second entry maps the Escape key to `selectionStore.clearSelection()`, but includes a guard to check that no modal dialog is currently mounted and that `document.activeElement` is neither a native input nor a textarea — if either condition is true the Escape handler returns early to allow the native focus behaviour to process the keypress instead. Add both new shortcut names to the comment block at the top of the provider file where existing shortcuts are documented, including their intended effect and the guard conditions under which they are suppressed.

---

## 4. Expected Outcome

1. Users can Ctrl+Click any number of non-adjacent segment cards and each clicked card acquires a visible highlighted border and a checked checkbox icon confirming it is part of the active selection.
2. Shift+Click extends the current selection as a contiguous range from the most recent non-Shift click anchor card to the newly clicked card, inclusive of all cards in between regardless of how many there are.
3. The `BulkActionToolbar` floats at the bottom centre of the viewport and becomes visible the moment any segment is selected, displaying a live-updated count badge that always reflects the exact number of currently selected segments.
4. Pressing Ctrl+A on the project page selects all segments simultaneously and the toolbar count badge updates to match the total project segment count.
5. Pressing Escape or clicking the toolbar's Clear button immediately deselects all segments with no API call and no unintended data change, returning every card to its unselected appearance and dismissing the toolbar.
6. Clicking "Delete Selected" in the toolbar fires a single bulk DELETE request targeting all selected segment IDs at once, rather than a sequential series of individual delete requests, and the Timeline updates to remove all deleted cards in one render cycle.
7. Clicking "Lock Selected" or "Unlock Selected" fires a single bulk PATCH request and all affected segment cards update their locked icons in the same render cycle.
8. The "Move Up" and "Move Down" buttons correctly reorder the selected segments by one step in the specified direction without affecting any unselected segment's position or content.
9. Plain (no modifier) single clicks on a segment card continue to behave exactly as they did before this feature — they focus the card for editing and do not permanently break any existing interaction.
10. The backend bulk endpoints correctly reject any request body containing segment IDs that do not belong to the specified project, returning an appropriate HTTP error code and message.
11. Adding selection affordances (checkbox icons and ring styles) to `SegmentCard` does not visually interfere with any of its existing interactive elements: the text editor, audio player, image uploader, or individual action buttons.
12. The `BulkActionToolbar` rendered via React portal always appears above all other page elements regardless of z-index stacking contexts within the segment list scroll container.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] `selectionStore.toggleSelection` called with an ID not in the set adds it and sets `selectionCount` to 1; calling it again with the same ID removes it and sets `selectionCount` back to 0.
- [ ] `selectionStore.toggleSelection` correctly updates `anchorId` to the toggled ID on each call, regardless of whether the ID was added or removed from the selection.
- [ ] `selectionStore.selectRange` with `fromId` before `toId` in the ordered array selects all IDs in the inclusive slice between them and no IDs outside that range.
- [ ] `selectionStore.selectRange` with `fromId` after `toId` in the ordered array (reversed order) still produces the same correct inclusive slice, confirming order-independence of the range arguments.
- [ ] `selectionStore.selectAll` called with an array of 15 IDs results in `selectionCount === 15` and `selectedSegmentIds.has(id)` returning true for every one of the 15 provided IDs.
- [ ] `selectionStore.clearSelection` resets `selectedSegmentIds` to an empty Set and `anchorId` to null, verified immediately after a `selectAll` call with a non-empty array.
- [ ] `BulkSegmentActionSerializer` on the backend returns a validation error when the `ids` field is absent from the request body.
- [ ] `BulkSegmentActionView.delete` on the backend returns 403 or 404 when any ID in the request body belongs to a different project than the one in the URL path.

### 5.2 Integration / Manual Tests

- [ ] Ctrl+Click three non-adjacent segment cards and confirm all three display the selected visual state (blue ring and checked checkbox) and the toolbar shows "3 selected".
- [ ] After building a three-card selection with Ctrl+Click, Shift+Click a card that is five positions below the last Ctrl+clicked card and confirm the selection extends as a contiguous range of five or more cards from the anchor to the target.
- [ ] With two cards selected, click "Delete Selected" in the floating toolbar, confirm the network inspector shows exactly one DELETE request (not two), and confirm both cards are removed from the Timeline in the same render.
- [ ] With four cards selected, click "Lock Selected" and verify all four cards display the locked icon and one PATCH request appears in the network inspector with all four IDs in the payload.
- [ ] Press Ctrl+A on a project with 22 segments and confirm all 22 cards are highlighted and the toolbar shows "22 selected".
- [ ] Press Escape immediately after pressing Ctrl+A and confirm all cards return to unselected state and the toolbar disappears, with no network activity in the inspector.
- [ ] Click the text editor inside a selected card and confirm the card remains selected (the text click propagated to the input rather than the card background and did not trigger a deselection).
- [ ] Navigate away from the project editing page after building a multi-segment selection, then return — confirm no segments are highlighted on return and the toolbar is not visible.

### 5.3 Regression Tests

- [ ] Single-click on a segment card with no modifier keys still produces the correct focus or expand behaviour that existed before this feature, without any unintended selection side-effects on adjacent cards.
- [ ] The individual delete button on a single `SegmentCard` still functions correctly and deletes only that one segment, regardless of whether other segments are simultaneously selected.
- [ ] The existing Ctrl+S save shortcut and any other registered shortcuts in `KeyboardShortcutProvider.tsx` continue to fire without interference from the new Ctrl+A and Escape handlers.
- [ ] The drag-and-drop reorder interaction in `Timeline.tsx` still works correctly and the click-modifier logic added to `SegmentCard.tsx` does not intercept or prevent drag events from initialising.
- [ ] A single-segment project renders the segment card correctly with the new selection affordances visible, and clicking the card selects it without causing any layout shift or error.

---

## 6. Notes for AI Agent

- Create `selectionStore.ts` before touching any component files and verify it imports and type-checks cleanly. Component-level TypeScript errors caused by a missing or malformed store type are slow to diagnose and may produce misleading cascading errors in `SegmentCard` and `Timeline`.

- Zustand's default shallow equality comparison does not detect changes inside a mutable Set object. If you call `.add()` or `.delete()` on the existing `selectedSegmentIds` Set reference without replacing it with a new Set, the store subscription will not notify consumers and the UI will not update. Always construct and assign a brand-new Set on every state update.

- The `selectRange` function depends on receiving the fully ordered segment ID array at call time rather than reading it from internal store state. This is intentional: keeping the ordered list out of the selection store avoids duplicating segment sequence data in two places that could desynchronise when segments are reordered. Pass `orderedSegmentIds` as a prop from `Timeline` to each `SegmentCard` so it is always available when the click handler fires.

- Use `ReactDOM.createPortal(jsx, document.body)` inside `BulkActionToolbar` to render the toolbar directly as a child of the document body. Without the portal, the toolbar's `fixed` positioning will be broken if any ancestor element in the `Timeline` or project page layout has a CSS `transform`, `filter`, or `will-change` property applied, which is very common in animated or scrollable list containers.

- When adding the route for `BulkSegmentActionView` in `urls.py`, place the `bulk/` URL pattern before any pattern with a `<int:pk>` or `<uuid:pk>` wildcard capture. Django URL resolution evaluates patterns in order and if a wildcard pattern appears first it will attempt to cast the literal string "bulk" to an integer or UUID, raising a 404 or a value-conversion error before the bulk view is ever reached.

- The confirmation dialog for bulk delete should only appear when the count of selected segments exceeds three, not for every delete. Showing a confirmation for a two-card delete is unnecessarily disruptive and reduces the productivity benefit of the feature. Three cards is a reasonable threshold at which the risk of accidental mass deletion justifies the extra confirmation step.

- For the "Move Up" and "Move Down" bulk actions, guard against boundary cases where selected segments include the first segment (cannot move up) or the last segment (cannot move down). Display a disabled state on the button or a toast message rather than silently swapping to incorrect positions or generating a PATCH with conflicting sequence indices.

- Before implementing the backend bulk endpoints, verify whether `drf-nested-routers` or a similar package is already installed in the Django project. If nested routing is used, the bulk URL must be registered correctly within the nested router namespace to receive the `project_pk` URL kwarg. If nested routing is not used, the project primary key must be included explicitly in the URL pattern and extracted from `self.kwargs` in the view.

---

## 7. Implementation Order and Effort Breakdown

### 7.1 Recommended Build Sequence

The six implementation steps for multi-select span both the frontend store layer and the Django backend and must be completed in a specific dependency order to avoid import errors and integration surprises.

**Phase 1 — Selection store foundation (Day 1)**

The store is the only file with zero dependencies on any other new code and must be created first.

- Create `frontend/store/selectionStore.ts`. Implement `toggleSelection`, `selectRange`, `selectAll`, and `clearSelection` following the immutable-Set pattern.
- Confirm `selectionCount` reactively reflects `selectedSegmentIds.size` after each action.
- Write unit tests for all four actions and for the `selectRange` forward and backward range cases.
- Run TypeScript compilation to confirm the new store exports are type-correct before touching any component.

**Phase 2 — Backend bulk endpoints (Day 2)**

Implement the backend endpoints in parallel with frontend store work to minimise integration delays.

- Add `BulkSegmentActionSerializer` to `backend/api/serializers.py` with `ids` (list) and optional `is_locked` (boolean) fields.
- Add `BulkSegmentActionView` with `delete` and `patch` methods to `backend/api/views.py`, including project ownership validation for all IDs on both methods.
- Register the `bulk/` URL in `backend/api/urls.py` before any wildcard segment route.
- Test the DELETE endpoint using the Django shell or curl with real segment IDs from a test project.
- Test the PATCH endpoint and confirm `is_locked` is updated in the database.
- Test the cross-project ownership reject case by sending IDs from a different project.

**Phase 3 — SegmentCard multi-select click affordances (Days 2–3)**

With the store ready, add the interaction layer to the existing card component.

- Pass `orderedSegmentIds` as a new prop from `Timeline.tsx` through to each `SegmentCard`.
- Add the modifier-key inspection logic to the card's `onClick` handler for the three cases: Ctrl+Click toggle, Shift+Click range, and plain click.
- Derive `isSelected` and apply the conditional Tailwind ring and background tint classes.
- Add the read-only ShadCN `Checkbox` in the card's top-left corner.
- Manual-test all three click variants in a running browser before proceeding.

**Phase 4 — BulkActionToolbar component (Day 3–4)**

- Create `frontend/components/BulkActionToolbar.tsx` with the React portal pattern targeting `document.body`.
- Build the pill-shaped panel with all button controls and the live count badge.
- Wire `clearSelection` to the Close/X button; test that the toolbar mounts and unmounts correctly as `selectionCount` changes.
- Pass bulk action handler props from the project page down to the toolbar and confirm wiring is complete.

**Phase 5 — Bulk action handlers and API integration (Days 4–5)**

- Implement `handleBulkDelete` with the optional confirmation dialog for selections above three items.
- Implement `handleBulkLock` and `handleBulkMoveUp` / `handleBulkMoveDown` with boundary guards.
- Connect each handler to its corresponding toolbar button prop.
- Test the full end-to-end path for each action: selection → toolbar click → network request → DOM update.

**Phase 6 — Keyboard shortcuts and accessibility (Day 5)**

- Register Ctrl+A → `handleSelectAll` in `KeyboardShortcutProvider.tsx` with `event.preventDefault()` guard.
- Register Escape → `clearSelection` with the modal-open and active-element guards.
- Verify neither shortcut conflicts with existing Ctrl+S or other registered actions.
- Test that the `BulkActionToolbar` is keyboard-accessible: users should be able to tab to each toolbar button and activate it with the Enter key.

### 7.2 Dependency Map

| Implementation Component | Requires | Blocks |
|---|---|---|
| `selectionStore.ts` | Nothing | All component changes and bulk handlers |
| Backend bulk endpoints | Existing `Segment` model and project auth | Bulk action handlers in the frontend |
| SegmentCard click affordances | `selectionStore.ts` | BulkActionToolbar visibility and count accuracy |
| `BulkActionToolbar.tsx` | `selectionStore.ts` | Bulk action handler wiring |
| Bulk action handlers in page | Backend endpoints, `selectionStore.ts` | BulkActionToolbar fully functional |
| Keyboard shortcuts | `selectionStore.ts` | Nothing further |

### 7.3 Per-Step Effort Estimates

| Step | Optimistic | Realistic | Pessimistic | Primary Risk Factor |
|---|---|---|---|---|
| `selectionStore.ts` | 1.5 hrs | 2 hrs | 3 hrs | Zustand Set immutability pattern getting it right first time |
| Backend bulk endpoints | 2 hrs | 4 hrs | 7 hrs | Unknown router setup and ownership query complexity |
| SegmentCard click affordances | 2 hrs | 3.5 hrs | 6 hrs | Existing card click handler and event propagation complexity |
| `BulkActionToolbar.tsx` | 2 hrs | 4 hrs | 6 hrs | React portal + responsive icon-only layout at narrow widths |
| Bulk action handlers | 3 hrs | 5 hrs | 8 hrs | Four handlers with boundary guards and API error handling |
| Keyboard shortcuts | 1 hr | 1.5 hrs | 2.5 hrs | Guard conditions for modal state and focused input elements |

### 7.4 Risk Register

| Risk | Likelihood | Impact | Mitigation Strategy |
|---|---|---|---|
| Zustand Set mutation not triggering re-render due to shallow equality | High | High | Always construct a new Set instance on every state update; unit-test re-render fires after toggle |
| `BulkActionToolbar` `fixed` positioning broken by CSS `transform` on an ancestor | Medium | High | Use `ReactDOM.createPortal` targeting `document.body` unconditionally |
| Backend `bulk/` URL shadowed by a `<pk>` wildcard, producing 404 or type error | Medium | High | Place `bulk/` pattern before all `<pk>` patterns in the URL configuration file |
| `selectRange` produces incorrect slice when `fromId` and `toId` order is reversed | Medium | Medium | Test both forward and backward argument order in dedicated unit tests |
| SegmentCard plain click causes browser text selection in the narration textarea | Low | Medium | Call `event.preventDefault()` on Ctrl+Click and Shift+Click only; leave plain-click unmodified |
| Bulk delete fires without confirmation on large accidental selections | Low | Critical | Show ShadCN `AlertDialog` when the selected count exceeds three before dispatching the DELETE request |
| BulkActionToolbar renders but obscures the last segment card with no scroll affordance | Low | Low | Add bottom padding to the Timeline scroll container equal to the toolbar height when `selectionCount > 0` |

### 7.5 Definition of Done

The multi-select feature is considered fully complete when every one of the following conditions is simultaneously true without exception:

- All 8 unit tests in section 5.1 pass in CI without any skipped or conditionally-passing assertions.
- All 8 integration/manual tests in section 5.2 produce the exact described result in a real browser with DevTools open.
- All 5 regression tests in section 5.3 confirm that existing single-segment behaviour is completely unaffected.
- Running `tsc --noEmit` on the entire `frontend/` directory produces zero new TypeScript errors.
- The `BulkActionToolbar` is completely invisible when no segments are selected and immediately appears when any card is clicked.
- The count badge in `BulkActionToolbar` accurately reflects the selection size after every Ctrl+Click, Shift+Click, Ctrl+A, and individual toggle action.
- The backend bulk DELETE endpoint returns 204 and the correct segments are absent from subsequent GET requests to the segments list.
- The backend bulk PATCH endpoint returns 200 and the `is_locked` field is correctly updated in the database for all targeted segments.
- Ctrl+A and Escape shortcuts operate correctly without conflicting with any existing shortcut registrations.
- The `BulkActionToolbar` remains visible above all page content regardless of how far the user scrolls within the segment list.

### 7.6 Rollout Considerations and Known Limitations

Before marking this feature as shipped, the following additional considerations should be reviewed with the team:

**Accessibility**
The Ctrl+Click and Shift+Click modifiers are inherently mouse-dependent interactions. To ensure the feature is usable without a pointer device, review whether keyboard-only segment selection (via arrow keys and Space bar) is needed as a follow-up task. The current specification does not define keyboard-only selection because it is a broader scope than multi-select alone, but it should not be forgotten.

**Mobile and touch support**
Ctrl+Click and Shift+Click are desktop-only affordances. On touch devices, a long-press gesture is the conventional equivalent of entering multi-select mode. This feature specification does not cover touch input. If StoryFlow is used on tablets, a separate touch selection story will be required.

**Performance on large projects**
When a project has 50 or more segments, selecting all with Ctrl+A and then performing a bulk delete issues a single backend DELETE request but triggers a full re-render of the segment list and a full re-fetch of the project data. On slower connections this will be perceptible. A loading state on the bulk delete button during the API round-trip is recommended even if it is not strictly required by this specification.

**Undo interaction**
This feature does not define how multi-segment bulk delete or bulk lock interacts with the undo/redo system described in Feature 1.2. The relationship between the two systems should be scoped in a follow-up document before either feature is considered stable.
