# Task 02.01.08 — Add TextArea Toggle UI

> **Sub-Phase:** 02.01 — Import & Parse Engine
> **Phase:** Phase 02 — The Logic
> **Complexity:** Low
> **Dependencies:** Task 02.01.07 (ImportDialog Component)
> **Parent Document:** [SubPhase_02_01_Overview.md](./SubPhase_02_01_Overview.md)

---

## Objective

Refine the ImportDialog's format toggle and textarea behavior for a polished user experience — adding format descriptions, auto-focus, character count, and a keyboard shortcut for submission.

---

## Instructions

### Step 1 — Add format description text

Below the format toggle buttons, add a descriptive helper text that changes based on the selected format:

- **JSON:** "Paste a JSON object with title and segments array."
- **Text:** "Paste text blocks separated by --- with Text: and Prompt: lines."

Use a `<p>` with `text-sm text-muted-foreground` Tailwind classes.

### Step 2 — Enhance format toggle visual distinction

Ensure the active format button has a clear visual difference:
- Active: `variant="default"` (filled background).
- Inactive: `variant="outline"` (border only).
- Buttons should be grouped with a small gap (`gap-2`).

### Step 3 — Set textarea minimum rows

Set the textarea `rows` attribute to at least **10** for comfortable editing of multi-segment content.

### Step 4 — Add character count indicator (optional)

Display a character count below the textarea's bottom-right corner:

```tsx
<p className="text-xs text-muted-foreground text-right">
  {content.length} characters
</p>
```

### Step 5 — Auto-focus textarea on dialog open

Use a `useEffect` to focus the textarea when the dialog opens:

```tsx
const textareaRef = useRef<HTMLTextAreaElement>(null);

useEffect(() => {
  if (open) {
    setTimeout(() => textareaRef.current?.focus(), 100);
  }
}, [open]);
```

The `setTimeout` is needed because the dialog animation must complete before focus can be set.

### Step 6 — Add Ctrl+Enter keyboard shortcut

Add an `onKeyDown` handler on the textarea that triggers submission on `Ctrl+Enter` (or `Cmd+Enter` on macOS):

```tsx
const handleKeyDown = (e: React.KeyboardEvent) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    e.preventDefault();
    if (!isSubmitting && content.trim()) {
      handleSubmit();
    }
  }
};
```

Attach to the textarea: `onKeyDown={handleKeyDown}`.

---

## Expected Output

```
frontend/
└── components/
    └── ImportDialog.tsx     ← MODIFIED (UX enhancements)
```

---

## Validation

- [ ] Format description text appears below the toggle and updates on format change.
- [ ] Active format button is visually distinct from the inactive one.
- [ ] Textarea has a minimum of 10 rows.
- [ ] Character count displays below the textarea.
- [ ] Textarea auto-focuses when the dialog opens.
- [ ] `Ctrl+Enter` / `Cmd+Enter` triggers submission (when content is non-empty and not already submitting).

---

## Notes

- This task is a UX refinement of Task 02.01.07's core functionality — it should be done after the ImportDialog is structurally complete.
- All changes are within the same `ImportDialog.tsx` file.

---

> **Parent:** [SubPhase_02_01_Overview.md](./SubPhase_02_01_Overview.md) (Layer 2)
> **Phase:** [Phase_02_Overview.md](../Phase_02_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_02_01_07_Build_ImportDialog_Component.md](./Task_02_01_07_Build_ImportDialog_Component.md)
> **Next Task:** [Task_02_01_09_Integrate_Dashboard_Import_Button.md](./Task_02_01_09_Integrate_Dashboard_Import_Button.md)
