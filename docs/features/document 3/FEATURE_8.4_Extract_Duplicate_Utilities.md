# Feature 8.4 — Extract Duplicate Utility Functions into Shared Module

| Field | Value |
|---|---|
| Feature ID | 8.4 |
| Title | Extract Duplicate Utility Functions into Shared Module |
| Status | 🟡 Planned |
| Priority | Medium |
| Complexity | Low |
| Estimated Effort | 0.5–1 day |
| Dependencies | None |
| Output Files (NEW) | None (refactor only) |
| Files Modified | frontend/lib/utils.ts, frontend/components/ProjectCard.tsx, frontend/components/RenderHistoryItem.tsx, frontend/app/dashboard/page.tsx |

---

## 1. Document Overview

### 1.1 Problem Statement

Three or more component files in the StoryFlow frontend — at minimum
`frontend/components/ProjectCard.tsx`, `frontend/components/RenderHistoryItem.tsx`, and
`frontend/app/dashboard/page.tsx` — each contain their own inline definition of a function
named `formatRelativeTime` that converts a `Date` object into a human-readable relative
time string such as "2 hours ago" or "3 days ago".
These three implementations were individually written or copy-pasted at different points in
the project's history and have since drifted apart in their output format: one returns the
full English description "2 hours ago", another returns an abbreviated form "2h ago", and
a third may use a different threshold for switching between "just now", minutes, hours, and
days — meaning the same render job's completion timestamp is displayed in three visually
different formats depending on which component happens to be rendering it.

The bug-fix maintenance burden is severe: if the product team decides the relative time format
should change — for example to always show absolute dates for anything older than 7 days — a
developer must locate and update all three implementations independently.
Under time pressure, developers frequently update the most visible implementation and overlook
the others, so the application ends up in a permanently inconsistent state where the "new"
format applies on the dashboard and the "old" format persists in the render history and
project card views until the inconsistency is noticed and reported again.
When a fourth developer adds an entirely new component that needs to display a relative
timestamp — for example a notifications panel — they copy the function from a random existing
component, perpetuating the inconsistency with yet another slightly different implementation
that will diverge further over time.

---

### 1.2 Proposed Solution

The correct approach is to perform a systematic discovery of all duplicate utility function
definitions across `frontend/components/` and `frontend/app/`, identify the canonical
implementation of each function — preferring completeness, correctness, and output format
quality — move that implementation into `frontend/lib/utils.ts`, update every component that
previously defined the function inline to import it from `@/lib/utils` instead, and delete
the inline definitions so that exactly one authoritative copy remains in the codebase.
Unit tests written for the canonical implementations in `lib/utils.ts` provide a regression
net for future changes and serve as executable documentation of the expected output format.
Once the consolidation is complete, any developer who needs relative time formatting in a
new component simply imports the function from `@/lib/utils` rather than writing or copying
a new implementation.

- Run a recursive grep search across `frontend/components/` and `frontend/app/` for the pattern
  `const formatRelativeTime` and `function formatRelativeTime` separately to discover every
  file that contains an inline function definition, and record the full body of each definition
  so that the implementations can be compared for completeness and correctness.

- Perform the same discovery for the other three suspected duplicate utility functions:
  search for `formatDuration`, `formatFileSize`, and `truncateText` (and their equivalent
  `const` arrow function assignment forms) to build a complete inventory of all inline utility
  function definitions across all component and page files.

- For each discovered utility function, read all found implementations side by side, select
  or synthesize the most correct and complete version accounting for edge cases like future
  dates, zero values, and very large numbers, then write that canonical version into
  `frontend/lib/utils.ts` with explicit TypeScript parameter and return type annotations.

- Update the import section of each component file that previously contained an inline
  definition, adding an import of the relevant function name from `@/lib/utils`, then delete
  the inline function body from the component file, leaving only the import statement and
  the call site that uses the function.

- Write unit tests in the frontend test suite for each of the four canonical utility functions
  in `lib/utils.ts`, covering at least a normal input, a boundary input, and an edge case
  input for each function, providing a stable regression baseline for future modifications.

---

### 1.3 Scope

| In Scope | Out of Scope |
|---|---|
| Discovering all inline definitions of the four named utility functions | Adding new utility functions not already present in some form |
| Consolidating canonical implementations into `frontend/lib/utils.ts` | Changing output formats beyond standardizing to one existing format |
| Updating component import sections to use `@/lib/utils` | Modifying component rendering layout or business logic |
| Deleting inline function bodies from component files after import update | Extracting non-utility component logic into shared modules |
| Writing unit tests for the four canonical implementations | Setting up a new test framework or adding testing infrastructure |

---

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| frontend/lib/utils.ts | Shared utility module; canonical destination for all utilities | Partially populated; may already contain some utilities from scaffolding |
| frontend/components/ProjectCard.tsx | Project list card; displays project creation/update timestamps | Contains inline `formatRelativeTime` with abbreviated output format |
| frontend/components/RenderHistoryItem.tsx | Render history item; displays render completion time | Contains inline `formatRelativeTime` with spelled-out output format |
| frontend/app/dashboard/page.tsx | Main dashboard; displays mixed project and render history data | May contain a third inline `formatRelativeTime` definition |
| frontend/__tests__/ | Jest test directory for frontend unit and component tests | May not yet contain tests for utility functions in `lib/utils.ts` |
| frontend/tsconfig.json | TypeScript configuration defining path aliases | Defines `@/*` pointing to `frontend/`; must resolve `@/lib/utils` |

---

## 2. Flow Diagram

The following ASCII diagram shows the before and after state of utility function ownership.

    ─────────── BEFORE EXTRACTION ───────────────────────────────────────────────
    ProjectCard.tsx ───── defines formatRelativeTime() locally
                          output: "2h ago"  (abbreviated)
    RenderHistoryItem.tsx ─ defines formatRelativeTime() locally
                          output: "2 hours ago"  (spelled out)
    app/dashboard/page.tsx ─ defines formatRelativeTime() locally
                          output: unknown format  (may differ again)
    [ Bug fix requires 3 edits; 4th component will copy from random location ]

    ─────────── AFTER EXTRACTION ────────────────────────────────────────────────
    lib/utils.ts ─────────── defines formatRelativeTime(date: Date): string
                             defines formatDuration(seconds: number): string
                             defines formatFileSize(bytes: number): string
                             defines truncateText(text: string, max: number): string
                             [ Single authoritative source for all four functions ]

    ProjectCard.tsx ───────── imports from @/lib/utils  (no local definition)
    RenderHistoryItem.tsx ─── imports from @/lib/utils  (no local definition)
    app/dashboard/page.tsx ── imports from @/lib/utils  (no local definition)
    [ Bug fix requires 1 edit; new components simply add one import line ]

---

## 3. Step-by-Step Instructions

### Step 3.1 — Discover All Duplicate Definitions by Function Name

Navigate to the `frontend/` directory and run recursive grep searches for the definition
patterns of each of the four utility functions: search for `formatRelativeTime`,
`formatDuration`, `formatFileSize`, and `truncateText` using patterns that match both the
`function` keyword declaration form and the `const arrowName =` assignment form.
For each function name, record every file path and line number where a definition is found,
then read the full body of each definition and note the differences in output format,
threshold values, edge-case handling, and TypeScript type annotations between the implementations.
Do not limit the search to `components/` only — also search `app/`, `hooks/`, and `lib/`
to ensure no existing partial migration has already placed a version in `lib/utils.ts` that
is subtly different from the versions in the component files and would cause output divergence
if naively treated as the canonical implementation.
Complete the full discovery phase before making any edits.

---

### Step 3.2 — Write Canonical Implementations into lib/utils.ts

Using the discovery results from Step 3.1 as the source material, evaluate all versions of
each function and select or synthesize the best implementation — prioritizing the most complete
edge-case coverage, the clearest output format, and the most accurate TypeScript type signature.
For `formatRelativeTime`, choose the spelled-out English format with thresholds at 1 minute,
1 hour, 1 day, and 7 days, falling back to an absolute date string format for older timestamps.
For `formatFileSize`, ensure the implementation handles zero bytes, handles values larger than
1 gigabyte without overflow, and uses the IEC binary prefix convention (kilobytes as 1024 bytes).
For `formatDuration`, ensure the result represents hours, minutes, and seconds correctly for
inputs longer than 3600 seconds, and for `truncateText` ensure the function appends an ellipsis
character only when truncation actually occurs and not for strings shorter than the limit.
Write each canonical function into `frontend/lib/utils.ts` with the `export` keyword and
explicit TypeScript parameter and return type annotations.

---

### Step 3.3 — Update Component Import Sections and Remove Inline Definitions

Work through each component file identified in Step 3.1 that contains an inline utility
function definition, starting with the files that contain definitions for the most functions
to maximize momentum early in the process.
For each file, add one or more import statements at the top of the file to import the relevant
canonical utility functions from `@/lib/utils`, following the existing import ordering
convention in the file.
After adding the import, identify the inline function body within the component file — including
the full `const functionName = (params): ReturnType => { ... }` block or `function` declaration
— and delete it entirely.
After the deletion, confirm that the component file compiles without errors by checking for
TypeScript diagnostics in VS Code or running `tsc --noEmit` on that individual file, since
any call site that previously relied on the inline definition now depends on the imported
function having the same parameter signature.

---

### Step 3.4 — Standardize and Verify Output Consistency

After all component files have been updated to import from `@/lib/utils`, start the Next.js
development server and navigate to the dashboard page, the render history view, and the
project cards view.
Inspect the relative time strings displayed for several timestamps on each page and verify
that all displayed strings use the exact same format — the same unit abbreviation style, the
same threshold for switching between "just now" and a minute count, and the same fallback
format for older timestamps.
If any inconsistency is visible, trace it to the source by checking whether a component was
missed during the discovery grep in Step 3.1, because a missed component would still have its
inline definition in place and would produce output in its old format independent of the
canonical implementation.
Once visual output consistency is confirmed, run the full Jest test suite to verify that no
existing component rendering tests have been broken by the import path changes.

---

## 4. Expected Outcome

1. The string `const formatRelativeTime` and `function formatRelativeTime` appear exactly once
   each in a grep search of the entire `frontend/` directory, and that single occurrence is
   located in `frontend/lib/utils.ts`, confirming that all previously duplicate inline
   definitions have been removed without exception.

2. Every component on the dashboard page and in the render history views displays timestamps
   in the identical textual format — both in unit style and threshold behavior — eliminating
   the visual inconsistency that previously caused the same data point to appear differently
   depending on which component happened to be rendering it.

3. A single modification to the `formatRelativeTime` function body in `frontend/lib/utils.ts`
   is sufficient to change how relative times are displayed everywhere in the application
   simultaneously, removing the operational risk of inconsistent multi-site patches that
   previously required knowing all three (or more) locations of the function definition.

4. Unit tests in the frontend test suite cover each of the four canonical utility functions
   in `lib/utils.ts` with at least three test cases each — a normal input, a boundary input,
   and an edge case — providing a stable regression net and serving as executable documentation
   of the expected output format that new contributors can read to understand the function.

5. The total number of lines of code across the four most-affected component files is measurably
   reduced compared to the pre-migration state because the inline function bodies that averaged
   fifteen to twenty-five lines each have been replaced with single import statements, leaving
   each component file focused exclusively on its own rendering and event-handling logic.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] A unit test for `formatRelativeTime` in `lib/utils.ts` confirms that a `Date` object
      representing exactly one hour ago returns the canonical human-readable string in the
      chosen output format without any undefined behavior or error.
- [ ] A unit test for `formatRelativeTime` confirms that a date more than 30 days in the past
      returns an absolute date string rather than a relative description, verifying that the
      threshold-based fallback logic is implemented correctly.
- [ ] A unit test for `formatFileSize` confirms that an input of 1,048,576 bytes returns
      the canonical string representing one megabyte, and that an input of zero bytes returns
      a meaningful non-error representation such as "0 B" rather than throwing or returning "NaN".
- [ ] A unit test for `formatDuration` confirms that 3,661 seconds returns a string correctly
      representing one hour, one minute, and one second in the chosen canonical format, and
      that zero seconds returns a meaningful empty or "0s" representation.

---

### 5.2 Integration / Manual Tests

- [ ] Navigate to the dashboard page in the running application and compare the timestamp
      format shown on at least three `ProjectCard` components; confirm that all three use
      the exact same output format with no visible variation in style, unit, or threshold.
- [ ] Navigate to the render history view and compare the timestamp format shown on at least
      two `RenderHistoryItem` components; confirm that the format matches the `ProjectCard`
      format exactly, proving that both consume the same canonical `formatRelativeTime`.
- [ ] Open the browser developer tools console and search the JavaScript source for
      `formatRelativeTime` to confirm that the function definition appears only once in the
      entire bundled client JavaScript output.
- [ ] Verify in the browser console on the dashboard page that no `undefined`, `NaN`, or
      empty string timestamp values are rendered for any project or render history item,
      confirming that the canonical implementation handles all data shapes present in the
      application's real data.

---

### 5.3 Regression Tests

- [ ] Run the complete Jest test suite and confirm that all previously passing component tests
      for `ProjectCard`, `RenderHistoryItem`, and the dashboard page continue to pass after
      the import path changes and inline definition removals.
- [ ] Run `tsc --noEmit` across the full frontend project and confirm zero type errors,
      verifying that every call site's argument types are compatible with the canonical function
      signatures declared in `lib/utils.ts`.
- [ ] Run grep searches for `const formatRelativeTime`, `const formatDuration`,
      `const formatFileSize`, and `const truncateText` across all `frontend/components/` and
      `frontend/app/` files and confirm that all results are zero matches, verifying that no
      inline definitions remain in any component or page file.

---

## 6. Notes for AI Agent

- The grep patterns used for discovery in Step 3.1 must specifically target function definition
  syntax rather than function call syntax — searching for `formatRelativeTime` alone will return
  every call site in addition to every definition site, making the results noisy and error-prone;
  using the more specific pattern `const formatRelativeTime =` or `function formatRelativeTime`
  will return only definition locations, which is the correct target for the discovery audit.

- When synthesizing the canonical `formatRelativeTime` implementation, adopt the spelled-out
  English format "2 hours ago" rather than the abbreviated "2h ago" as the default, because
  spelled-out formats are more accessible to screen readers, more internationally legible, and
  more consistent with the natural language quality expected in a story-focused application.

- Never import from a Zustand store, a React context, or any other stateful module inside
  `lib/utils.ts` — the utility functions in this file must be pure functions that depend only
  on their explicit input arguments and standard JavaScript and TypeScript globals, because
  importing stateful modules into a shared utility file creates circular dependency risks and
  makes the functions non-testable in isolation.

- If `frontend/lib/utils.ts` already contains a `cn` function (class name combiner, typically
  generated by Shadcn UI setup), that function must be preserved exactly as-is when adding new
  utility functions to the file; the `cn` function is likely used by dozens of UI components
  throughout the project and any accidental modification or removal would cause widespread
  styling failures across the entire component library.

---

## 6.1 Migration Safety Notes

- Before deleting any inline function body from a component file, read the call site in that
  same file to confirm the argument being passed matches the expected parameter type of the
  canonical implementation — for example, if the component calls `formatRelativeTime(project.createdAt)`
  and `createdAt` is a string rather than a `Date`, the call site must be updated to convert
  the string to a `Date` before the function will accept it under the canonical typed signature.

- After updating each individual component file, run `tsc --noEmit` before moving to the next
  file rather than waiting until all files are updated; catching type errors file by file as they
  are introduced makes each error trivially traceable to the specific change that caused it,
  whereas accumulating errors across multiple files creates a large batch that is harder to
  attribute and resolve.

- If a test for a component is structured around mocking the inline function definition that
  was present in the component file itself (for example by using `jest.spyOn` on a module-level
  constant), that mock will break after the inline definition is removed; such tests must be
  updated to mock the `@/lib/utils` module export instead, which is a cleaner and more
  idiomatic test pattern.

- At any point during the migration, the codebase is in a valid state as long as each individual
  file is internally consistent — meaning a component that has already had its inline definition
  replaced by an import still works correctly, and a component that has not yet been updated
  still works correctly with its original inline definition; the only invalid intermediate state
  is a file missing both its inline definition and its import statement, which would be a
  hard compilation error immediately visible in the TypeScript language server.

---

*Document created for StoryFlow project — Phase 8 Frontend Refactoring series.*
*Target directory: e:\My_GitHub_Repos\storyFlow\docs\features\document 3\*
*Stack: Next.js (app router) + TypeScript + Zustand*
*Last updated: 2026-03-10*
