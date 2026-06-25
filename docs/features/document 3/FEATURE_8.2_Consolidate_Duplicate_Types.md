# Feature 8.2 — Consolidate Duplicate TypeScript Type Definitions

| Field | Value |
|---|---|
| Feature ID | 8.2 |
| Title | Consolidate Duplicate TypeScript Type Definitions |
| Status | 🟡 Planned |
| Priority | Medium |
| Complexity | Low |
| Estimated Effort | 0.5–1 day |
| Dependencies | None |
| Output Files (NEW) | None (refactor only) |
| Files Modified | frontend/lib/types.ts, frontend/types/settings.ts, frontend/components/VoiceSelector.tsx, frontend/components/SubtitlePreview.tsx, frontend/app/settings/page.tsx, frontend/store/settingsStore.ts |

---

## 1. Document Overview

### 1.1 Problem Statement

The StoryFlow frontend defines the `GlobalSettings` interface — along with several related
settings-specific child interfaces — in two completely separate files: `frontend/types/settings.ts`
and `frontend/lib/types.ts`.
These definitions were authored independently at different stages of the project, and over time
they have diverged in ways that are structurally subtle but practically harmful, because TypeScript
treats them as distinct, incompatible types even though both are intended to represent the exact
same domain concept.
`frontend/types/settings.ts` uses snake_case field names such as `subtitle_color`, `voice_id`,
and `output_resolution` because those names were copied directly from the Django REST serializer
output, while `frontend/lib/types.ts` uses camelCase names like `subtitleColor`, `voiceId`, and
`outputResolution` in an attempt to follow JavaScript naming conventions.

Because TypeScript structural typing evaluates field name as part of the type shape, an object
typed as `GlobalSettings` from `lib/types.ts` is not assignable to a parameter typed as
`GlobalSettings` from `types/settings.ts`, even though both represent the same settings domain
model — the compiler will flag an assignment error or, more dangerously, silently accept the
assignment if the two interfaces happen to share a common subset of fields while the mismatched
fields become `undefined` at runtime without any error.
A component that reads `settings.subtitleColor` on a `GlobalSettings` object whose fields are
actually named with snake_case will receive `undefined` silently at render time, causing the
subtitle preview to render with no color applied rather than the configured value, and no console
error or TypeScript diagnostic will point to the cause.
This category of bug is particularly difficult to diagnose because the symptoms — a blank or
default-styled subtitle — look identical to a missing API response rather than a field naming
mismatch, and developers frequently waste time investigating the network layer before discovering
the root cause in the type definition layer.

---

### 1.2 Proposed Solution

The right approach is to designate `frontend/lib/types.ts` as the single canonical location for
all shared frontend type definitions, adopt snake_case as the authoritative field naming convention
for the `GlobalSettings` interface — because the Django REST Framework serializer outputs snake_case
and the frontend ultimately consumes that format — then convert `frontend/types/settings.ts` into
a thin re-export barrel file so that existing imports from that path do not immediately break
during the transition period.
Running `tsc --noEmit` before and after the migration provides a measurable baseline for comparing
the error count and confirming that no net new errors were introduced by the changes.
The re-export barrel approach is a deliberate transitional choice that decouples the type
consolidation from the import path migration, allowing the two concerns to be addressed
independently in separate follow-up tasks without leaving the codebase in an inconsistent state.

- Run `tsc --noEmit` across the full `frontend/` directory before making any changes and record
  the complete list of existing type errors as a baseline; this establishes a reference point so
  that errors introduced by the migration can be distinguished from pre-existing issues.

- Open both `frontend/types/settings.ts` and `frontend/lib/types.ts` simultaneously and produce
  a side-by-side field-by-field comparison of every interface they define, noting field names,
  TypeScript types, optional vs required markers, and any JSDoc comments associated with fields
  that should be preserved in the merged version.

- For each field in the mapping, select the snake_case name as authoritative if the field
  corresponds to a value that arrives from the Django REST API (since it will be received as
  snake_case from the network response); for frontend-only computed or ephemeral fields that
  have no backend equivalent, also convert to snake_case for consistency within the file.

- Rewrite `frontend/lib/types.ts` with the merged, authoritative set of interfaces using fully
  consistent snake_case field names, preserve all JSDoc comments from either source, then replace
  the entire body of `frontend/types/settings.ts` with TypeScript `export type` re-export
  statements pointing to each interface in `lib/types.ts`.

- Run `tsc --noEmit` again and compare the error output to the pre-migration baseline; open
  each file containing a new error and update the field name accesses from camelCase to the newly
  authoritative snake_case names, resolving all new errors before marking the task complete.

---

### 1.3 Scope

| In Scope | Out of Scope |
|---|---|
| Merging `GlobalSettings` and related interfaces from both files into `lib/types.ts` | Redesigning the Django backend serializer field names |
| Converting `types/settings.ts` to a barrel re-export file | Adding new type definitions beyond what currently exists |
| Adopting snake_case as the authoritative naming convention in `lib/types.ts` | Migrating Python type hints in `backend/` to match frontend types |
| Running `tsc --noEmit` comparisons to surface and fix type errors | Changing the Django API response structure or adding new endpoints |
| Updating imports in components that directly reference type fields by name | Modifying test fixture data shapes beyond what is required to pass tests |

---

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| frontend/lib/types.ts | Canonical type destination; currently camelCase GlobalSettings | Active; will hold merged snake_case definitions after migration |
| frontend/types/settings.ts | Older snake_case type file; to become a re-export barrel | Active; will be reduced to re-export statements pointing to lib/types.ts |
| frontend/store/settingsStore.ts | Zustand settings store; imports GlobalSettings type | May reference camelCase fields that will change after migration |
| frontend/app/settings/page.tsx | Settings page component; renders all GlobalSettings fields | Form field bindings will need updating for any renamed fields |
| frontend/api/settingsApi.ts | Settings API layer; maps network response to GlobalSettings | Directly receives snake_case from backend; alignment simplifies mapping |
| backend/api/serializers.py | Django REST serializer defining authoritative field names | Reference only for naming decisions; must not be modified in this task |

---

## 2. Flow Diagram

The following ASCII diagram shows the type resolution graph before and after consolidation.

    ─────────── BEFORE CONSOLIDATION ────────────────────────────────────────────
    lib/types.ts          ──── defines GlobalSettings (camelCase fields)
                               { voiceId, subtitleColor, outputResolution }
    types/settings.ts     ──── defines GlobalSettings (snake_case fields)
                               { voice_id, subtitle_color, output_resolution }
    settingsStore.ts      ──── imports from one path (camelCase GlobalSettings)
    settings/page.tsx     ──── imports from different path (snake_case GlobalSettings)
    settingsApi.ts        ──── receives snake_case from API; assigns to camelCase type
                               [ TypeScript sees two incompatible GlobalSettings types ]

    ─────────── AFTER CONSOLIDATION ─────────────────────────────────────────────
    lib/types.ts          ──── defines GlobalSettings (snake_case, authoritative)
                               { voice_id, subtitle_color, output_resolution }
    types/settings.ts     ──── re-exports GlobalSettings from lib/types.ts (barrel only)
    settingsStore.ts      ──── imports from lib/types.ts (single canonical definition)
    settings/page.tsx     ──── imports via either path; both resolve to same type
    settingsApi.ts        ──── receives snake_case from API; assigns to snake_case type
                               [ One GlobalSettings; all consumers share same structure ]

---

## 3. Step-by-Step Instructions

### Step 3.1 — Establish the Pre-Migration Type Error Baseline

Navigate to the `frontend/` directory and run the TypeScript compiler with `tsc --noEmit` to
generate a full list of all current type errors in the project before any file is modified.
Save the complete output — including file paths, line numbers, and error messages — to a local
scratch file or terminal buffer that can be referenced throughout the migration process.
This baseline is essential because the field name changes in the migration will introduce new
type errors in all consumer files that access renamed fields, and without the baseline it is
impossible to know whether a given error was pre-existing or newly introduced by the refactoring.
Count the total number of errors in the baseline so that progress can be quantified by
comparing the count after each step.

---

### Step 3.2 — Produce the Field Comparison Table

Open `frontend/types/settings.ts` and `frontend/lib/types.ts` side by side, either in two
editor splits or by reading both files sequentially and noting their contents.
For every interface defined in either file, produce a mapping table with columns for the
field name in `types/settings.ts`, the equivalent field name in `lib/types.ts`, the TypeScript
type from each definition, and a column noting whether the field is the same across both files
or differs in name, type, or optionality.
Pay special attention to the `GlobalSettings` interface in each file, as it is the most widely
consumed type and the most likely source of the runtime bugs described in the problem statement.
Note which fields appear only in one file with no equivalent in the other, because those fields
require a merge decision rather than a simple renaming.

---

### Step 3.3 — Rewrite lib/types.ts and Convert types/settings.ts to a Barrel

Using the comparison table from Step 3.2 as the definitive guide, rewrite the `GlobalSettings`
interface and all related interfaces in `frontend/lib/types.ts` so that every field uses
snake_case naming consistent with the Django REST serializer output format.
For any field that previously existed only in `lib/types.ts` under a camelCase name and has no
backend equivalent, rename it to snake_case and add a comment clarifying that it is a
frontend-only ephemeral field not present in the API response.
After completing the rewrite of `lib/types.ts`, open `frontend/types/settings.ts` and replace
its entire contents with `export type` re-export statements for each interface, pointing to the
definitions now in `lib/types.ts`, so that all existing import statements pointing to
`types/settings.ts` continue to resolve without requiring any import path changes in
consumer files during this task.

---

### Step 3.4 — Fix All New Type Errors in Consumer Files

Run `tsc --noEmit` again and compare the full error output to the pre-migration baseline.
For every error that appears in the new output but was not present in the baseline, open
the file containing the error and update the property access expression to use the correct
snake_case field name as defined in the newly merged `lib/types.ts`.
Work through the errors one file at a time rather than jumping between files, because fixing
all errors in a single file at once is more efficient and allows the TypeScript language server
to refresh its understanding of that file before moving on.
After resolving all new errors, run `tsc --noEmit` one final time and confirm that the error
count is equal to or less than the baseline, establishing a quantitative proof that the
consolidation has not introduced any net new type regressions.

---

## 4. Expected Outcome

1. Exactly one location in the `frontend/` codebase defines the authoritative `GlobalSettings`
   interface, and that location is `frontend/lib/types.ts`, making it unambiguous for any
   developer where to look when they need to understand the structure of a settings object or
   add a new field to the settings domain model.

2. All field names in `GlobalSettings` and its related types use snake_case naming that matches
   the Django REST Framework serializer output without transformation, eliminating the entire
   category of runtime bugs caused by reading a camelCase key on an object whose fields are
   stored under snake_case keys — a silent `undefined` access that produces incorrect UI state
   without any observable error.

3. The file `frontend/types/settings.ts` still physically exists and still correctly resolves all
   imports that reference it, because it now re-exports every type from `lib/types.ts`; this
   means the barrel approach provides a zero-disruption migration pathway for consumer files
   that can be updated to point directly to `lib/types.ts` in a future follow-up task.

4. The TypeScript compiler reports zero new errors compared to the pre-migration baseline,
   providing a measurable, quantitative confirmation that the consolidation is complete and
   that the merged type definitions are correctly consumed by all impacted components, stores,
   and API layer files across the frontend project.

5. The `frontend/api/settingsApi.ts` file now types the network response object directly as
   `GlobalSettings` from `lib/types.ts` without requiring any field-name transformation layer,
   because the API response arrives as snake_case from Django and the type definition now uses
   snake_case — making the data flow from backend to frontend state fully transparent and
   eliminating an entire category of potential mapping bugs.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] A unit test imports `GlobalSettings` from both `@/lib/types` and `@/types/settings` and
      performs a structural comparison confirming they resolve to the same type definition,
      verifying that the barrel re-export is wired correctly with no structural divergence.
- [ ] A unit test for the settings API layer creates a mock API response object with snake_case
      fields and confirms that it can be assigned to `GlobalSettings` without a TypeScript
      cast or transformation, verifying direct type compatibility with the backend format.
- [ ] A unit test for the settings page component renders the component with a `GlobalSettings`
      prop using snake_case field names and confirms that all expected form fields are populated
      with the correct values from those fields.
- [ ] A unit test confirms that the Zustand settings store initializes its state from a
      `GlobalSettings` object typed against the merged `lib/types.ts` definition without errors,
      verifying store-type compatibility after the snake_case migration.

---

### 5.2 Integration / Manual Tests

- [ ] Load the settings page in the running application and verify that all form fields are
      pre-populated with correct values from the backend response, confirming that snake_case
      field names are read correctly by the form rendering logic.
- [ ] Change a subtitle style setting in the UI and save it; reload the settings page and
      verify that the saved value is correctly round-tripped through the API and displayed
      in the form on reload.
- [ ] Open the subtitle preview component after changing settings and verify that the preview
      correctly reflects the current subtitle color and font settings, confirming that the
      component now reads the correct snake_case field names from the store.
- [ ] Check the browser console for any `undefined` property access warnings that might
      indicate a field name mismatch that was not caught by the TypeScript compiler and is
      manifesting as a silent runtime issue.

---

### 5.3 Regression Tests

- [ ] Run `tsc --noEmit` across the full frontend project and confirm the error count is equal
      to or less than the pre-migration baseline count established in Step 3.1.
- [ ] Run the complete Jest test suite and confirm that all previously passing tests continue
      to pass, with no new failures introduced by field name changes in the type definitions.
- [ ] Perform a text search across all `frontend/` TypeScript files for camelCase field accesses
      on `GlobalSettings`-typed variables (`voiceId`, `subtitleColor`, `outputResolution`) and
      confirm that no direct property accesses using those camelCase names remain.

---

## 6. Notes for AI Agent

- The re-export barrel approach for `frontend/types/settings.ts` is intentionally transitional —
  it allows this task to focus entirely on normalizing the type definitions without requiring
  a simultaneous mass update of all import paths across the codebase; a separate follow-up
  task should eventually update all consumer imports to point directly to `lib/types.ts`.

- When selecting snake_case as the authoritative naming convention, the deciding factor is
  the Django REST serializer output — any field that appears in an API response arrives as
  snake_case, and aligning the frontend type to match means zero field-name translation is
  needed anywhere between the network response parsing step and the component rendering step.

- The TypeScript `export type` keyword should be used rather than `export` alone when creating
  re-export statements in `types/settings.ts`, because `export type` is type-only and generates
  no JavaScript runtime artifact, which is the semantically correct choice for a file that
  exists solely to forward type definitions from another location.

- The file `backend/api/serializers.py` is the authoritative source of truth for field naming
  decisions in this task — when there is doubt about which name to use, opening the serializer
  and reading the field names declared there provides the definitive answer; the serializer
  must not be modified as part of this task.

---

## 6.1 Migration Safety Notes

- After Step 3.1 (baseline measurement), confirm the TypeScript version in `frontend/package.json`
  before interpreting the error count; TypeScript version differences affect which errors are
  reported under strict mode, so comparing error counts across TypeScript version changes would
  produce misleading results that complicate the migration assessment.

- After Step 3.3 (rewriting `lib/types.ts`), immediately check whether any other file inside
  `frontend/lib/` imports from `lib/types.ts` and references field names that have just been
  renamed to snake_case; library files with incorrect field references will produce errors that
  cascade into every file that imports those library modules, amplifying the apparent error count.

- If the type error count after Step 3.4 is significantly higher than the baseline, suspect
  that a field used extensively throughout the application was renamed without updating all
  call sites; in this case, use `tsc --noEmit` output to find the most-referenced erroring
  field name and update all its occurrences before addressing less-common fields.

- When the barrel re-export file approach is eventually removed in a future follow-up task,
  the migration from `types/settings` to `lib/types` import paths must be performed atomically
  in a single commit that updates all consumer files simultaneously, to avoid a transient state
  where some files import from the barrel and others from the canonical source.

---

*Document created for StoryFlow project — Phase 8 Frontend Refactoring series.*
*Target directory: e:\My_GitHub_Repos\storyFlow\docs\features\document 3\*
*Stack: Next.js (app router) + TypeScript + Zustand*
*Last updated: 2026-03-10*
