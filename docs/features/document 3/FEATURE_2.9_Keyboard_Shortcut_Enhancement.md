# Feature 2.9 — Keyboard Shortcut Enhancement

| Field | Value |
|---|---|
| Feature ID | 2.9 |
| Title | Keyboard Shortcut Enhancement for Mouse-Free Editing |
| Status | 🟡 Planned |
| Priority | High |
| Complexity | Low |
| Estimated Effort | 2 days |
| Dependencies | Feature 2.2 (Segment CRUD API), Feature 2.3 (Audio Player), `is_locked` field on Segment model |
| Output Files (NEW) | `frontend/components/KeyboardShortcutReference.tsx`, `frontend/components/DeleteSegmentPopover.tsx` |
| Files Modified | `frontend/hooks/useKeyboardShortcuts.ts`, `frontend/app/projects/[id]/page.tsx`, `frontend/components/SegmentCard.tsx`, `frontend/components/Timeline.tsx` |

---

## 1. Document Overview

### 1.1 Problem Statement

Every segment action in StoryFlow currently requires a mouse click: creating a segment, duplicating it, deleting it, locking it, and playing its audio preview all demand a hand-off from keyboard to mouse. A power user editing a 30-segment video must move the mouse dozens of times per session, losing several minutes of productive flow per project across a typical production week. The existing five keyboard shortcuts handle only global navigation and do not extend to the segment editing workflow where the majority of editing time is spent. For StoryFlow to serve content creators as a professional production tool, mouse-free segment editing must be a first-class capability.

### 1.2 Proposed Solution

Extend `useKeyboardShortcuts.ts` to support a comprehensive set of segment-oriented shortcuts driven by a `focusedSegmentId` state variable held in the project page. All segment-specific shortcuts (D, Del, L, Space) operate on the currently focused segment, while navigation shortcuts (↑, ↓, 1–9) move focus between segments. A lightweight confirmation popover handles destructive actions. A reference card accessible via `?` provides discoverable documentation inline.

- Introduce `focusedSegmentId` as a string (or null) piece of React state owned by the project page, passed down to `Timeline` and each `SegmentCard` as a prop; the focused card receives a distinct visual ring (`ring-2 ring-blue-500`) so the user always knows which segment is active.
- `N` key calls the existing `createSegment()` API action and appends a new blank segment immediately after the focused one (or at the end if none is focused).
- `D` key calls a `duplicateSegment(focusedSegmentId)` handler that clones the segment's text content and voice settings via a POST to `api/segments/<id>/duplicate/`, does not copy audio or image files, and sets focus to the newly created clone.
- `Del` key renders a `DeleteSegmentPopover` positioned near the focused segment card with a "Delete segment? Confirm" prompt; the delete API call only fires on explicit confirmation, preventing accidental deletion.
- `↑` and `↓` move focus to the previous or next segment in the ordered list; the newly focused card scrolls into view using the browser's `scrollIntoView` method.
- `Space` calls `.play()` or `.pause()` on the `HTMLAudioElement` ref attached to the focused segment's audio player, toggling playback without any mouse interaction.
- `L` sends a `PATCH /api/segments/<id>/` request with `{ is_locked: !currentLocked }` and updates the Zustand segment slice optimistically.
- `1`–`9` move focus directly to the segment at that 1-based index in the visible segment list.
- `Escape` clears `focusedSegmentId` to null and closes any open popovers.
- `?` opens the `KeyboardShortcutReference` modal, which renders the complete shortcut table for in-app discoverability.

### 1.3 Scope

| # | In Scope | Out of Scope |
|---|---|---|
| 1 | All 10 new shortcuts listed above plus the existing 5 | Custom user-remappable keybindings |
| 2 | Visual focus ring on the active SegmentCard | Drag-and-drop reordering via keyboard |
| 3 | In-app KeyboardShortcutReference modal opened via `?` | Global OS-level shortcut registration |
| 4 | Delete confirmation popover to prevent accidental deletion | Undo/redo stack for deleted segments |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| `frontend/hooks/useKeyboardShortcuts.ts` | Registers keydown listeners; dispatches actions for 5 existing shortcuts | Functional; needs expansion for 10 new bindings |
| `frontend/components/KeyboardShortcutProvider.tsx` | Wraps the app; instantiates `useKeyboardShortcuts` at root level | Functional; may need project-page context for segment shortcuts |
| `frontend/components/SegmentCard.tsx` | Renders one segment: text editor, audio player, image, voice selector | Has no focused/unfocused visual states; needs `isFocused` prop |
| `frontend/components/Timeline.tsx` | Renders the ordered list of SegmentCards | Passes segment data; does not manage focus state |
| `frontend/app/projects/[id]/page.tsx` | Project editing page; owns segment list state | Owns Zustand selectors; needs `focusedSegmentId` state added |

---

## 2. Flow Diagram

```
User presses a key while project page is focused
        |
        v
useKeyboardShortcuts keydown handler fires
        |
        v
Is a text input or textarea currently focused?
   YES  |              NO
        |               |
   Ignore event         v
                 Match key against shortcut map
                        |
           _____________|_______________
          |         |         |         |
          v         v         v         v
       N key     ↑ / ↓    Del key    1–9 key
       Create   Move      Open        Jump
      segment   focus   Confirm     to index
         |      prev/    Popover         |
         v      next         |           v
    API POST      |      User confirms  focusedSegmentId
    appends       v      → DELETE API   set to index - 1
    new seg   scrollIntoView  |
         |    called on    Segment
         v    new focus    removed
     Focus       |         from list
    set to        |
    new seg       |
                  v
          Space / L / D key
          Acts on focusedSegmentId
          → play/pause audio ref
          → PATCH is_locked toggle
          → POST duplicate endpoint
```

---

## 3. Step-by-Step Instructions

### Step 3.1 — Add focusedSegmentId State to the Project Page

**File:** `frontend/app/projects/[id]/page.tsx`
**Function:** Page component (top-level)

- Declare `const [focusedSegmentId, setFocusedSegmentId] = useState<string | null>(null)` near the other state declarations at the top of the component.
- Pass `focusedSegmentId` and `setFocusedSegmentId` down to the `Timeline` component as props so that clicking a segment card can also set focus programmatically from the mouse (the two input methods should share the same focus concept).
- Attach a `useEffect` that listens for clicks anywhere on the page background (outside a segment card) and calls `setFocusedSegmentId(null)` to clear focus when the user deselects by clicking empty space.
- Export the `focusedSegmentId` value through a module-level React context (`FocusedSegmentContext`) so that `useKeyboardShortcuts` can read it without prop-drilling through intermediate components.

### Step 3.2 — Extend the useKeyboardShortcuts Hook

**File:** `frontend/hooks/useKeyboardShortcuts.ts`
**Function:** `useKeyboardShortcuts`

- Import the `FocusedSegmentContext` and read `focusedSegmentId` and `setFocusedSegmentId` from it at the top of the hook.
- Inside the existing `keydown` event handler, skip all segment-specific logic if `document.activeElement` is an `INPUT`, `TEXTAREA`, or `SELECT` element — this prevents shortcuts from firing while the user is typing segment text.
- Add cases for `n` (create), `d` (duplicate), `Delete` (open confirm popover), `ArrowUp` / `ArrowDown` (move focus), `' '` (Space — toggle audio), `l` (lock), `1`–`9` (jump to index), `Escape` (clear focus), and `?` (open reference modal).
- For the `1`–`9` jump, read the current ordered segment list from the Zustand store and call `setFocusedSegmentId(segments[key - 1]?.id ?? null)`.

### Step 3.3 — Update SegmentCard for Focus Visual State

**File:** `frontend/components/SegmentCard.tsx`
**Function:** `SegmentCard` component

- Add an `isFocused: boolean` prop to the component's props interface.
- Apply `ring-2 ring-blue-500 ring-offset-2` Tailwind classes to the card's outermost container element conditionally when `isFocused` is true, alongside the existing border/shadow classes.
- Attach a `ref` to the card's outermost `div` and expose it via `useImperativeHandle` (or forward a ref from the Timeline parent) so that the `↑`/`↓` handler can call `ref.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' })` when focus moves.
- Attach the audio element's ref to a variable accessible from the Timeline/page level so the `Space` shortcut handler can call `.play()` / `.pause()` directly on the `HTMLAudioElement`.

### Step 3.4 — Build the DeleteSegmentPopover Component

**File:** `frontend/components/DeleteSegmentPopover.tsx`
**Function:** `DeleteSegmentPopover` (new component)

- Accept props: `isOpen` (boolean), `onConfirm` (callback), `onCancel` (callback), and `segmentIndex` (number, for display in the message).
- Use ShadCN `Popover` + `PopoverContent` to render a small card with the message "Delete segment [N]?" and two buttons: "Confirm" (red destructive variant) and "Cancel" (ghost variant).
- `onConfirm` triggers the `deleteSegment(focusedSegmentId)` API call, closes the popover, and moves focus to the previous segment if one exists.
- `onCancel` closes the popover and returns focus to the segment card without any state mutation; `Escape` key also calls `onCancel` via its own keydown case in `useKeyboardShortcuts`.

### Step 3.5 — Build the KeyboardShortcutReference Modal

**File:** `frontend/components/KeyboardShortcutReference.tsx`
**Function:** `KeyboardShortcutReference` (new component)

- Accept a single `isOpen` / `onClose` prop pair; render using a ShadCN `Dialog` with a scrollable content area.
- Inside the dialog, render a two-column table with headers "Key" and "Action" listing all 15 shortcuts (5 existing plus the 10 new ones) in logical groups: Navigation, Segment Actions, Playback, and Global.
- The `?` key handler in `useKeyboardShortcuts` sets an `isShortcutReferenceOpen` boolean in local state to true; the `Escape` key (and the dialog's own close button) sets it back to false.
- Include a footer note: "Shortcuts are disabled while a text input is focused" so users understand why shortcuts occasionally appear to not respond.

---

## 4. Expected Outcome

1. Pressing `N` on the project page creates a new blank segment appended after the currently focused segment and immediately moves keyboard focus to the new card.
2. Pressing `D` duplicates the focused segment's text and voice settings, calls the duplicate API endpoint, and shifts focus to the clone — no audio or image files are copied.
3. Pressing `Del` opens a small confirmation popover adjacent to the focused card; the segment is only deleted after explicit confirmation, preventing accidental data loss.
4. Pressing `↑` or `↓` moves the blue focus ring to the previous or next segment and smoothly scrolls the card into the visible viewport area.
5. Pressing `Space` toggles audio playback on the focused segment's audio player without requiring the user to locate and click the play button with the mouse.
6. Pressing `L` optimistically toggles the `is_locked` visual indicator on the focused segment and persists the change via a PATCH request.
7. Pressing `1` through `9` immediately focuses the segment at that 1-based position, enabling instant jumps to known segment indices in long timelines.
8. Pressing `?` opens the in-app keyboard shortcut reference card listing all 15 shortcuts, making the feature self-documenting and discoverable without external documentation.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] `useKeyboardShortcuts` fires the `createSegment` action exactly once when `N` is pressed and no text input is active.
- [ ] `useKeyboardShortcuts` does NOT fire any segment action when a `textarea` element is focused and the user presses `D`.
- [ ] Focus moves to `segments[2]` (index 2) when `3` is pressed with a segment list of at least 3 items.
- [ ] `DeleteSegmentPopover` renders the correct segment index in its confirmation message and calls `onConfirm` when the Confirm button is clicked.
- [ ] Pressing `Escape` while the popover is open calls `onCancel` and does not trigger a segment deletion.
- [ ] `SegmentCard` applies `ring-2 ring-blue-500` classes when `isFocused` is true and removes them when `isFocused` is false.

### 5.2 Integration / Manual Tests

- [ ] Tab through the project page settings the browser's native focus indicator; confirm keyboard shortcuts activate correctly when the page body (not an input) holds focus.
- [ ] Press `D` on a segment with text "Hello world" and voice "en-US"; verify the duplicate card appears below with identical text and voice but no audio file attached.
- [ ] Press `Del`, then click "Cancel" in the popover; verify the segment count is unchanged and the blue ring remains on the original card.
- [ ] Press `Space` while a segment with an audio file is focused; verify audio begins playing and a second press pauses it.
- [ ] Press `?`; verify the shortcut reference dialog opens and lists all 15 shortcuts in a readable table; press `Escape` to close.
- [ ] Press `↓` on the last segment; verify focus does not wrap around to the first segment (boundary condition — should stay on last).

### 5.3 Regression Tests

- [ ] All 5 existing keyboard shortcuts (documented in current `useKeyboardShortcuts.ts`) continue to work exactly as before after the expansion.
- [ ] The text editor inside `SegmentCard` still accepts all keyboard input — letters, numbers, Delete, Space — without being intercepted by the shortcut handler.
- [ ] Clicking a segment card with the mouse still sets `focusedSegmentId` correctly, and subsequent keyboard shortcuts operate on the mouse-clicked card.

---

## 6. Notes for AI Agent

- The most critical guard in `useKeyboardShortcuts` is the early-return check for `document.activeElement` being an editable element. Every shortcut that uses letter keys (`N`, `D`, `L`) or `Space` / `Delete` must be gated behind this check — these are common typing keys and will break text editing if the guard is missing or incomplete.
- `focusedSegmentId` must live in the project page's React state (or a dedicated Zustand slice), not inside `useKeyboardShortcuts` itself, because multiple components — Timeline, SegmentCard, and the shortcut hook — all need to read and write the same value. A React context is the cleanest solution for sharing it without prop-drilling four levels deep.
- The `HTMLAudioElement` ref for each segment needs to be stored in a ref map keyed by segment ID (e.g., `useRef<Record<string, HTMLAudioElement | null>>({})`); this allows the Space shortcut handler to look up the correct element in O(1) regardless of which segment is focused.
- The `1`–`9` shortcut must be implemented by detecting `event.key` values `'1'` through `'9'` as strings, not as `event.keyCode` numbers, to remain consistent with the rest of the shortcut handler and to avoid issues with numeric keypad vs top-row key differences on some layouts.
- When implementing the `duplicate` endpoint on the backend, confirm that the serialiser explicitly excludes `audio_file` and `image_file` fields from the clone so the backend does not attempt to copy binary assets — only `text`, `voice_id`, `voice_speed`, `subtitle_text`, and `order` should carry over.
