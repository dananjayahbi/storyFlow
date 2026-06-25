# Feature 8.1 — Consolidate Duplicate Zustand Settings Stores

| Field | Value |
|---|---|
| Feature ID | 8.1 |
| Title | Consolidate Duplicate Zustand Settings Stores |
| Status | 🟡 Planned |
| Priority | Medium |
| Complexity | Low |
| Estimated Effort | 0.5–1 day |
| Dependencies | None |
| Output Files (NEW) | None (refactor only) |
| Files Modified | frontend/lib/stores.ts, frontend/store/settingsStore.ts, frontend/components/VoiceSelector.tsx, frontend/components/SubtitlePreview.tsx, frontend/app/settings/page.tsx, frontend/types/settings.ts |

---

## 1. Document Overview

### 1.1 Problem Statement

The StoryFlow frontend currently maintains two separate Zustand stores that both export an
identifier named `useSettingsStore` — one located at `frontend/lib/stores.ts` and another
at `frontend/store/settingsStore.ts`.
These stores were created at different times and by different contributors, and their internal
state shapes have drifted apart in ways that cause real, observable bugs at runtime rather
than compile-time errors.
The older store at `lib/stores.ts` uses snake_case field names such as `voice_id` and
`subtitle_color` reflecting the Django REST API response format directly, while the newer
store at `store/settingsStore.ts` uses camelCase names such as `voiceId` and `subtitleColor`
following TypeScript naming conventions.

This divergence means that two components importing `useSettingsStore` from different paths
receive state objects with structurally incompatible shapes at runtime.
A mutation dispatched to the store at `store/settingsStore.ts` has absolutely no effect on
components subscribed to `lib/stores.ts`, because these are two completely independent reactive
trees holding duplicate — but not shared — state.
A developer attempting to debug why a settings change on the settings page has no effect on
the voice selector will spend significant time before realizing the two components are reading
from entirely different stores.

TypeScript does not catch this class of error automatically because both export statements use
the exact same function name `useSettingsStore`, and the only distinguishing factor between
them is the import path in each consuming component file.
Since TypeScript resolves each import independently and the resulting function signatures are
identical, the compiler cannot warn that two separate reactive store instances exist — the bug
is wholly invisible to the type system and only becomes apparent during manual testing or
through a careful audit of import statements across the codebase.

---

### 1.2 Proposed Solution

The correct fix is to designate `frontend/store/settingsStore.ts` as the single canonical
settings store for the entire frontend application.
Any unique state fields present in `frontend/lib/stores.ts` but absent from the canonical
store must be identified and merged into the canonical store's type definitions and initial
state before any imports are changed, ensuring no data loss occurs during migration.
Once the canonical store contains a complete superset of all settings-related state, every
component and utility that imports from the deprecated path must be updated to use the canonical
path, after which the deprecated file can be permanently deleted.

- Grep the entire `frontend/` directory recursively for the string `lib/stores` to produce
  a definitive, complete list of every file path and line number where the deprecated store
  is imported; include both `@/lib/stores` alias forms and relative path forms like `../lib/stores`
  in the search pattern to capture all possible import styles.

- Open `frontend/lib/stores.ts` and enumerate every state property and every action defined
  in the Zustand `create` call, recording each field name, its TypeScript type, and its
  initial value; then perform the same enumeration for `frontend/store/settingsStore.ts` and
  build a field-by-field comparison table documenting exact equivalents, renamed equivalents
  (snake_case vs camelCase), and truly unique-to-deprecated fields with no equivalent.

- Merge any state properties and actions that are unique to `frontend/lib/stores.ts` into
  `frontend/store/settingsStore.ts`, converting all field names to camelCase for consistency
  with the existing canonical store convention, and update the store's TypeScript interface to
  declare the new fields so that consumers receive full type checking coverage.

- Update every import statement identified in the grep audit to replace the deprecated import
  path with `@/store/settingsStore`, and in the same pass change any field access expressions
  that use the old snake_case names (such as `settings.voice_id`) to the new camelCase equivalents
  (such as `settings.voiceId`) to prevent silent runtime undefined reads.

- Delete `frontend/lib/stores.ts` after verifying that `tsc --noEmit` across the entire
  `frontend/` directory reports zero errors and the full Jest test suite passes without regressions,
  committing the deletion separately from the import updates to keep the git history clear.

---

### 1.3 Scope

| In Scope | Out of Scope |
|---|---|
| Merging state fields from `lib/stores.ts` into `store/settingsStore.ts` | Redesigning the settings store state shape from scratch |
| Updating all import paths that reference `lib/stores` | Migrating other unrelated stores such as the project store |
| Deleting `frontend/lib/stores.ts` after full migration | Adding entirely new settings fields or business logic |
| Resolving camelCase vs snake_case field naming in the canonical store | Changing how settings values are persisted to the backend |
| Verifying no circular imports are introduced during the merge | Modifying Django REST serializer field names to match |

---

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| frontend/lib/stores.ts | Deprecated settings store; snake_case state shape | Active but must be deleted after migration completes |
| frontend/store/settingsStore.ts | Canonical settings store; camelCase state shape | Active; missing some fields present in the deprecated store |
| frontend/components/VoiceSelector.tsx | Voice selection UI; subscribes to settings store | Likely importing from deprecated or inconsistent path |
| frontend/components/SubtitlePreview.tsx | Subtitle preview UI; reads subtitle style settings | May be reading snake_case fields from deprecated store |
| frontend/app/settings/page.tsx | Full settings page; reads and writes all settings | Must be confirmed to import from canonical store after migration |
| frontend/types/settings.ts | TypeScript type definitions for settings state | May need field name updates to reflect camelCase merge |

---

## 2. Flow Diagram

The following ASCII diagram illustrates the store import graph before and after the migration.

    ─────────── BEFORE MIGRATION ───────────────────────────────────────────────
    VoiceSelector.tsx      ──────────────────────► lib/stores.ts
                                                    (voice_id, subtitle_color)
    SubtitlePreview.tsx    ──────────────────────► lib/stores.ts
                                                    (two independent instances)
    app/settings/page.tsx  ──────────────────────► store/settingsStore.ts
                                                    (voiceId, subtitleColor)
    [ State changes in settingsStore do NOT propagate to lib/stores consumers ]

    ─────────── AFTER MIGRATION ─────────────────────────────────────────────────
    VoiceSelector.tsx      ──┐
                             │
    SubtitlePreview.tsx    ──┼──────────────────► store/settingsStore.ts
                             │                    (voiceId, subtitleColor)
    app/settings/page.tsx  ──┘                    [ SINGLE SOURCE OF TRUTH ]

    lib/stores.ts ─────────────── PERMANENTLY DELETED ──────────────────────────
    [ All imports resolve to one store; state changes are universally reactive ]

---

## 3. Step-by-Step Instructions

### Step 3.1 — Audit All Import Sites

Open a terminal at `frontend/` and run a recursive text search for the string `lib/stores`
across all TypeScript and TSX files using grep or a similar tool.
Record every file path and line number returned by the search, because this list is the
complete definition of scope — every entry in the list is a file that must be edited before
the deprecated store can be deleted.
Also search for the relative import form `../lib/stores` and `../../lib/stores` separately,
because some files may use relative paths instead of the `@/` alias, and those would not
appear in a search limited to the alias form.
Do not begin any edits until the full list is confirmed, because working from an incomplete
audit risks leaving orphaned imports in files that were missed, causing build failures that
are confusing to diagnose after the fact.

---

### Step 3.2 — Merge Unique Fields into the Canonical Store

Open `frontend/lib/stores.ts` and list every state property and action in the Zustand
`create` call, noting the exact field name, TypeScript type annotation, and initial value
for each one.
Repeat the same enumeration for `frontend/store/settingsStore.ts` and build a side-by-side
comparison to identify which fields are present only in the deprecated store with no
equivalent in the canonical store.
For each unique field, add it to the canonical store's state interface using camelCase naming,
assign it an appropriate initial value consistent with the existing initial state pattern,
and add a corresponding setter action following the naming convention already used in
`store/settingsStore.ts`.
Run `tsc --noEmit` on just `store/settingsStore.ts` after each field addition to catch type
errors immediately at their source rather than accumulating them into a large batch.

---

### Step 3.3 — Update All Identified Import Statements

Work through the list of files identified in Step 3.1 in order, and in each file change
the import statement that currently references the deprecated store path to instead reference
`@/store/settingsStore`.
Inside the same file, search for every property access on the store state that uses a
snake_case field name originating from the deprecated store, and rename each access to
the corresponding camelCase field name now present in the canonical store.
Pay special attention to destructuring patterns such as `const { voice_id } = useSettingsStore()`
which must be updated to `const { voiceId } = useSettingsStore()` along with every downstream
usage of the `voice_id` variable within that component's render logic.
After saving each file, verify that the TypeScript language server in VS Code shows zero
type errors in that file before moving to the next one in the list.

---

### Step 3.4 — Delete the Deprecated File and Confirm Clean Build

After all files in the audit list have been updated, delete the file `frontend/lib/stores.ts`
from the repository using a standard file deletion command in the terminal.
Run `tsc --noEmit` across the entire `frontend/` directory and confirm that the compiler
output shows zero errors — any remaining reference to the deleted file will surface as a
module-not-found error that must be resolved before proceeding.
Run the full Jest test suite with `npm test` and confirm that every test that was passing
before the migration is still passing, with no new failures introduced by the import path
or field name changes.
Stage the deletion of `lib/stores.ts` as a separate git commit distinct from the import
update commits so that the deletion is clearly visible in the pull request diff and can
be reviewed independently.

---

## 4. Expected Outcome

1. There is exactly one file in the `frontend/` directory that exports `useSettingsStore`,
   and that file is `frontend/store/settingsStore.ts`, making it structurally impossible for
   any future contributor to accidentally create a split-brain state scenario by importing
   a settings store hook from an alternative location.

2. All components that previously read settings state — including `VoiceSelector.tsx`,
   `SubtitlePreview.tsx`, and `app/settings/page.tsx` — now share a single reactive Zustand
   store instance, so a value written through any one component's setter action is immediately
   observed by all other subscribed components on the next render cycle without any additional
   synchronization logic.

3. Field names across all settings-related state reads, writes, and destructuring patterns in
   the frontend codebase are consistently camelCase, eliminating the entire class of silent
   runtime bugs caused by reading a snake_case key on a JavaScript object that stores its
   values under camelCase keys, which returns `undefined` without an error.

4. The TypeScript compiler run in strict mode across the full `frontend/` directory reports
   zero errors related to settings store field access, store import paths, or state type
   mismatches, providing high confidence that the migration is complete and correct.

5. The file `frontend/lib/stores.ts` no longer exists anywhere in the repository's working
   tree, meaning the root cause of the duplication has been eliminated and any future attempt
   to recreate a second settings store would require an explicit, reviewable decision visible
   in a pull request diff.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] A unit test confirms that `useSettingsStore` imported from `@/store/settingsStore` returns
      a store object containing all previously available fields from both the old and new store
      shapes, verifying that no fields were lost during the merge.
- [ ] A unit test for `VoiceSelector.tsx` confirms that the component correctly reads the `voiceId`
      field from the canonical store and renders the expected voice label in the UI without
      any undefined-related rendering errors.
- [ ] A unit test for `SubtitlePreview.tsx` confirms that the component correctly reads the
      `subtitleColor` field from the canonical store and applies it to the preview container's
      rendered style attribute.
- [ ] A unit test confirms that dispatching a setter action on the canonical store updates the
      state value and that a component subscribed via `useSettingsStore` re-renders with the
      new value, demonstrating live reactivity after the migration.

---

### 5.2 Integration / Manual Tests

- [ ] Navigate to the settings page in the running development application and change the voice
      selection to a different value; verify that every other component on the page that displays
      the current voice selection also updates immediately to reflect the change.
- [ ] Navigate to the settings page and update the subtitle color, then open the subtitle preview
      component in the same session and confirm it reflects the correct updated color value
      without requiring a page reload or manual refresh.
- [ ] Open the Zustand DevTools browser extension and navigate to multiple pages that use
      the settings store; confirm that exactly one store instance named `useSettingsStore`
      appears in the store inspector throughout the session.
- [ ] Perform a complete settings save and reload flow — save settings, reload the page, and
      verify that the stored values are correctly re-hydrated into the single canonical store
      and displayed in all consuming components.

---

### 5.3 Regression Tests

- [ ] Run the full Jest test suite and confirm that the total number of passing tests is equal
      to or greater than the count recorded in the pre-migration baseline, with no new failures.
- [ ] Run `tsc --noEmit` across the entire `frontend/` directory and confirm the output contains
      zero errors, establishing that the migration has not introduced any new type regressions.
- [ ] Perform a grep search across all tracked files in the repository for the path `lib/stores`
      and confirm zero matches, verifying complete removal of all references to the deleted file.

---

## 6. Notes for AI Agent

- Begin every session on this task by re-running the import audit grep, because other developers
  may have added new imports to `lib/stores.ts` since the last session; working from a stale
  audit list is a common source of missed files that only reveal themselves as build failures
  after the deprecated file is deleted and the missing import becomes a hard error.

- When merging new fields into `store/settingsStore.ts`, pay careful attention to whether the
  `useSettingsStore.getState()` static accessor pattern is used anywhere in the codebase outside
  of React components — this non-reactive access pattern is common in API utility functions and
  event handlers, and those call sites will not surface as JSX type errors but will silently
  return `undefined` if they access a field that was renamed during the migration.

- Circular import risk: if `store/settingsStore.ts` imports type definitions from `lib/types.ts`,
  and `lib/types.ts` previously imported anything from `lib/stores.ts`, then deleting
  `lib/stores.ts` will break `lib/types.ts` — check both directions of the import graph between
  these files and resolve any such dependency before deleting the deprecated store.

- The three most impacted components are `VoiceSelector.tsx`, `SubtitlePreview.tsx`, and
  `app/settings/page.tsx`; prioritize manually testing these three components after each change
  to catch integration issues early, because they collectively cover the full settings read and
  write surface area of the application.

---

## 6.1 Migration Safety Notes

- Before making any file edits, verify the current git working tree is completely clean by
  running `git status`; all pending work should be committed or stashed so that the migration
  diff is isolated and reviewable on its own without unrelated changes mixed in.

- After completing the field merge in Step 3.2 and before touching any consumer files,
  run `tsc --noEmit` specifically targeting `store/settingsStore.ts` to confirm that the
  merged interface compiles correctly; a type error in the store file itself will cascade into
  false errors in every consuming component, making the root cause harder to identify.

- If any step introduces a TypeScript error that cannot be resolved within one focused session,
  use `git stash` to preserve the partially-completed work and return to the pre-migration
  clean state; attempting to continue with unresolved type errors across multiple files creates
  compounding confusion that is significantly harder to untangle than a clean restart.

- The final deletion of `frontend/lib/stores.ts` should be committed in a standalone commit
  with the message clearly identifying it as a cleanup step following the import migration;
  this makes the git log interpretable and allows the deletion to be reverted independently
  if a downstream issue is discovered after merge without requiring a revert of the entire
  migration.

---

*Document created for StoryFlow project — Phase 8 Frontend Refactoring series.*
*Target directory: e:\My_GitHub_Repos\storyFlow\docs\features\document 3\*
*Stack: Next.js (app router) + TypeScript + Zustand*
*Last updated: 2026-03-10*
