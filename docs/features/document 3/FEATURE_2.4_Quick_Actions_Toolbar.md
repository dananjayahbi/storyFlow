# Feature 2.4 — Quick Actions Toolbar (Command Palette)

| Field | Value |
|---|---|
| **Feature ID** | 2.4 |
| **Title** | Quick Actions Toolbar (Command Palette) |
| **Status** | 🟡 Planned |
| **Priority** | High |
| **Complexity** | Medium |
| **Estimated Effort** | 2 days |
| **Dependencies** | `KeyboardShortcutProvider.tsx`, `useKeyboardShortcuts.ts`, project context via Zustand |
| **Output Files (NEW)** | `frontend/components/CommandPalette.tsx`, `frontend/constants/commandActions.ts` |
| **Files Modified** | `frontend/components/KeyboardShortcutProvider.tsx`, `frontend/app/layout.tsx` |

---

## 1. Document Overview

### 1.1 Problem Statement

Common actions in StoryFlow — such as triggering a render, generating audio, navigating to settings, or importing a story — are spread across several nested menus and page-specific buttons. There is currently no keyboard-first method of reaching these actions, which means power users must constantly switch from keyboard to mouse to perform routine operations. Locating a specific action in an unfamiliar project state is slow and requires prior knowledge of where each button lives in the interface.

### 1.2 Proposed Solution

Build a global command palette modal triggered by the `Ctrl+K` shortcut that provides a single, searchable access point for all high-value application actions registered centrally in an action registry.

- Create `CommandPalette.tsx`, a modal overlay component that renders centered on the viewport with a blurred dark backdrop, a text search input, and a scrollable list of matching action entries.
- Define a central action registry in `frontend/constants/commandActions.ts` as a typed array of action descriptor objects, each carrying an id, label, description, optional keyboard shortcut hint, context requirement, and a handler function reference.
- Register the following initial actions: "Generate All Audio", "Render Project", "Import Story", "Batch Import Stories", "Duplicate Project", "Open Settings", "Toggle Subtitle Preview", and "Go to Gallery".
- Implement real-time fuzzy filtering of the action list as the user types in the search input — match against both label and description text case-insensitively.
- Register `Ctrl+K` in `KeyboardShortcutProvider.tsx` to open the palette from anywhere in the application; `Escape` closes it; Arrow Up / Arrow Down navigate the highlighted entry; `Enter` fires the highlighted action's handler.
- Make the palette context-aware: actions tagged with `requiresProject: true` are hidden or shown as disabled when no project is currently open in the Zustand store.

### 1.3 Scope

| Category | Item |
|---|---|
| **In Scope** | `Ctrl+K` global shortcut to open palette |
| **In Scope** | Real-time fuzzy text search over action labels and descriptions |
| **In Scope** | Keyboard navigation and Enter-to-execute within the palette |
| **In Scope** | Context-aware action visibility based on whether a project is open |
| **Out of Scope** | Per-page dynamic action registration (static registry only in v1) |
| **Out of Scope** | Mouse-based drag reordering of palette results |
| **Out of Scope** | Persistent command history / recently used actions (future enhancement) |
| **Out of Scope** | Custom user-defined shortcuts for palette actions |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| `frontend/components/KeyboardShortcutProvider.tsx` | Global keyboard shortcut manager | Handles Ctrl+S, Ctrl+R; does not have Ctrl+K |
| `frontend/hooks/useKeyboardShortcuts.ts` | Custom hook for key binding logic | Exists; used by the provider above |
| `frontend/app/layout.tsx` | Root layout wrapping all pages | Renders `KeyboardShortcutProvider`; palette must also be rendered here |
| `frontend/constants/commandActions.ts` | New action registry file | Does not exist yet |
| `frontend/components/CommandPalette.tsx` | New palette modal component | Does not exist yet |

---

## 2. Flow Diagram

```
Any page in the application
        |
  User presses Ctrl+K
        |
        v
  KeyboardShortcutProvider intercepts
  → sets commandPaletteOpen = true (Zustand)
        |
        v
  CommandPalette modal renders
  (backdrop blur + centered panel)
        |
        v
  Search input auto-focused
  Full action list shown initially
        |
        v
  User types a query
        |
        v
  Fuzzy filter runs over commandActions
  (label + description match)
        |
        v
  Filtered list rendered with
  highlighted active entry
        |
   +-----------+-----------+
   |           |           |
 Arrow      Enter key    Escape key
  keys     (execute)     (close)
   |           |           |
   v           v           v
 Navigate   Handler()   Palette
 highlight  called      dismissed
            palette
            closed
```

---

## 3. Step-by-Step Instructions

### Step 3.1 — Create the Action Registry

File: `frontend/constants/commandActions.ts`
Export: `commandActions` array, `CommandAction` TypeScript interface

Define the `CommandAction` interface with fields: `id` (string), `label` (string), `description` (string), `shortcutHint` (optional string), `requiresProject` (boolean), and `handler` (function accepting a context object). Populate the array with eight initial actions. Handlers that require router navigation should accept a `router` object in the context argument. Handlers that require Zustand store methods should accept a `store` object. Keep the registry file free of direct component imports to avoid circular dependency issues — handlers receive everything they need via the context argument passed at call time.

### Step 3.2 — Create CommandPalette Component (Shell + Layout)

File: `frontend/components/CommandPalette.tsx`
Component: `CommandPalette`

Build the visual shell using a ShadCN `Dialog` set to full-width with `max-w-xl` and positioned near the top of the viewport (top-20 rather than centered vertically). Inside the dialog, place a `CommandInput` (or plain `Input` with autofocus) at the top, a scrollable `ul` list below it, and a narrow footer showing keyboard hint text ("↑↓ to navigate · Enter to run · Esc to close"). The component reads `commandPaletteOpen` from a Zustand UI slice and dispatches `closeCommandPalette` on close. Render all items from `commandActions`, filtered and sorted by relevance.

### Step 3.3 — Implement Fuzzy Filtering and Keyboard Navigation

File: `frontend/components/CommandPalette.tsx`
Logic: `filterActions`, `handleKeyDown`

Maintain a `query` state string updated by the search input. The `filterActions` function iterates over `commandActions`, lowercases query and each action's label and description, and returns entries where either field includes the query string (simple substring match is acceptable for v1 — a fuzzy library like `fuse.js` is optional). Maintain an `activeIndex` state integer for the highlighted row. The `handleKeyDown` listener on the dialog root handles ArrowUp (decrement index, clamp at 0), ArrowDown (increment index, clamp at filtered length minus 1), Enter (call the highlighted action's handler with a context object containing `router` and the Zustand store), and Escape (close palette).

### Step 3.4 — Register Ctrl+K in KeyboardShortcutProvider

File: `frontend/components/KeyboardShortcutProvider.tsx`
Function: existing shortcut registration block

Add a new entry to the existing shortcut map for the key combination `Ctrl+K`. When triggered, call `openCommandPalette()` from the Zustand UI slice. Ensure the default browser behavior for `Ctrl+K` (focus address bar in Firefox; link dialog in some editors) is prevented with `event.preventDefault()`. The palette must not open when the user is typing inside a text input or textarea — respect the existing guard logic already present in `useKeyboardShortcuts.ts`.

### Step 3.5 — Mount Palette in Root Layout and Add Zustand UI Slice

File: `frontend/app/layout.tsx` and `frontend/store/uiStore.ts` (or existing UI store slice)
Component: root layout children

Add `commandPaletteOpen`, `openCommandPalette`, and `closeCommandPalette` to the Zustand UI store slice (create the slice if it does not already exist, or append to the existing one). In `layout.tsx`, import and render `CommandPalette` as a sibling to `KeyboardShortcutProvider` so it is available on every page. Since `CommandPalette` reads its open state from Zustand, no prop threading is required.

---

## 4. Expected Outcome

1. Pressing `Ctrl+K` from any page in the application opens the command palette overlay without reloading or navigating away.
2. The palette renders a search input that is auto-focused, allowing the user to begin typing immediately.
3. Typing a partial query (for example, "ren") shows "Render Project" and any other matching actions in real time.
4. Arrow keys cycle through results; the currently active item is visually highlighted.
5. Pressing `Enter` on the highlighted action executes it and dismisses the palette.
6. Actions tagged `requiresProject: true` are hidden or visually disabled when no project is currently active in the store.
7. Pressing `Escape` or clicking outside the palette closes it without taking any action.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] `filterActions` with query "ren" returns actions whose label or description contains "ren" case-insensitively.
- [ ] `filterActions` with an empty query returns all actions.
- [ ] Actions with `requiresProject: true` are excluded from results when `currentProject` is null in the store.
- [ ] `handleKeyDown` with ArrowDown increments `activeIndex` and clamps at the filtered list length minus 1.
- [ ] `handleKeyDown` with Enter calls the highlighted action's handler exactly once.

### 5.2 Integration / Manual Tests

- [ ] Press `Ctrl+K` on the Dashboard page → palette opens with full action list visible.
- [ ] Press `Ctrl+K` while a text input is focused → palette does NOT open (shortcut guard is respected).
- [ ] Type "import" in the palette → "Import Story" and "Batch Import Stories" appear; "Render Project" does not.
- [ ] Click an action in the list with the mouse → action executes and palette closes.
- [ ] Open a project, then open the palette → project-scoped actions ("Render Project") are now visible and actionable.

### 5.3 Regression Tests

- [ ] Existing `Ctrl+S` and `Ctrl+R` shortcuts still function correctly and are not intercepted by the new `Ctrl+K` handler.
- [ ] The projects list page and project detail page render correctly with `CommandPalette` mounted in the root layout.
- [ ] Refreshing the page while the palette is open resets it to closed state (no hydration error from Zustand).

---

## 6. Notes for AI Agent

- Place the action registry in `frontend/constants/commandActions.ts` rather than inside the component to allow other parts of the application (tests, other components) to import it without pulling in React.
- Use ShadCN's `CommandDialog` primitive if available in the project's installed ShadCN version — it already bundles the overlay, input, and list with the correct keyboard behavior, which avoids reimplementing navigation from scratch.
- The context object passed to each action handler should be constructed inside `CommandPalette.tsx` at call time using `useRouter` and the Zustand store selectors available in that component — handlers must never import hooks themselves (hooks can only be called from components or other hooks).
- Keep `requiresProject` enforcement simple: check whether the Zustand project store's `currentProject` field is non-null; do not attempt per-action permission logic in v1.
- Test `Ctrl+K` across Chrome, Firefox, and Edge; Firefox maps `Ctrl+K` to the address bar by default and requires `preventDefault` to be called synchronously in the `keydown` handler to suppress it.
