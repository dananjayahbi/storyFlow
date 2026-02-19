# Task 02.03.14 — Write Frontend Component Tests

> **Sub-Phase:** 02.03 — Image Upload & Timeline Editor UI
> **Phase:** Phase 02 — The Logic
> **Complexity:** High
> **Dependencies:** Task 02.03.07 (Timeline Editor Page)
> **Parent Document:** [SubPhase_02_03_Overview.md](./SubPhase_02_03_Overview.md)

---

## Objective

Write comprehensive frontend tests for all new components and the Zustand store using React Testing Library, covering rendering, interactions, debounce, clipboard, and store state management.

---

## Instructions

### Step 1 — SegmentTextEditor Tests

Create tests in `frontend/__tests__/SegmentTextEditor.test.tsx` (or colocated `.test.tsx`).

```typescript
import { render, screen, fireEvent, act } from '@testing-library/react';
import { SegmentTextEditor } from '@/components/SegmentTextEditor';

jest.useFakeTimers();

describe('SegmentTextEditor', () => {
  const mockSave = jest.fn().mockResolvedValue(undefined);

  it('renders textarea with initial content', () => {
    render(<SegmentTextEditor segmentId={1} initialContent="Hello" isLocked={false} onSave={mockSave} />);
    expect(screen.getByDisplayValue('Hello')).toBeInTheDocument();
  });

  it('updates local state on input change', () => {
    render(<SegmentTextEditor segmentId={1} initialContent="" isLocked={false} onSave={mockSave} />);
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'New text' } });
    expect(screen.getByDisplayValue('New text')).toBeInTheDocument();
  });

  it('debounced save fires after 500ms of inactivity', async () => {
    render(<SegmentTextEditor segmentId={1} initialContent="" isLocked={false} onSave={mockSave} />);
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Typing...' } });
    expect(mockSave).not.toHaveBeenCalled();
    await act(async () => { jest.advanceTimersByTime(500); });
    expect(mockSave).toHaveBeenCalledWith(1, { text_content: 'Typing...' });
  });

  it('no save triggered if text has not changed', () => {
    render(<SegmentTextEditor segmentId={1} initialContent="Same" isLocked={false} onSave={mockSave} />);
    jest.advanceTimersByTime(1000);
    expect(mockSave).not.toHaveBeenCalled();
  });

  it('textarea is disabled when isLocked is true', () => {
    render(<SegmentTextEditor segmentId={1} initialContent="" isLocked={true} onSave={mockSave} />);
    expect(screen.getByRole('textbox')).toBeDisabled();
  });
});
```

### Step 2 — ImageUploader Tests

```typescript
describe('ImageUploader', () => {
  it('renders drop zone when no image');
  it('renders image preview when image exists');
  it('drop event triggers upload callback');
  it('click-to-browse triggers file input');
  it('rejects non-image files with error message');
  it('disables upload when locked');
});
```

- Mock `onUpload` and `onRemove` callbacks.
- Use `fireEvent.drop()` with a `DataTransfer` mock for drag-and-drop tests.
- Verify error messages appear for invalid file types.

### Step 3 — ImagePromptDisplay Tests

```typescript
describe('ImagePromptDisplay', () => {
  it('renders prompt text');
  it('copy button calls navigator.clipboard.writeText');
  it('shows "Copied!" feedback after click');
  it('empty prompt shows placeholder text');
});
```

- Mock `navigator.clipboard.writeText` globally:
  ```typescript
  Object.assign(navigator, {
    clipboard: { writeText: jest.fn().mockResolvedValue(undefined) },
  });
  ```

### Step 4 — SegmentCard Tests

```typescript
describe('SegmentCard', () => {
  it('renders all sub-components (text editor, image zone, prompt)');
  it('shows correct 1-based sequence number');
  it('lock toggle calls update callback with is_locked');
  it('delete button opens confirmation dialog');
});
```

- Pass a mock `Segment` object with all required fields.
- Verify sub-component rendering by checking for expected text/elements.

### Step 5 — Timeline Tests

```typescript
describe('Timeline', () => {
  it('renders correct number of SegmentCard components');
  it('shows empty state when no segments');
  it('cards are keyed by segment ID');
});
```

### Step 6 — Timeline Editor Page Tests

```typescript
describe('TimelineEditorPage', () => {
  it('fetches project on mount');
  it('shows loading state while fetching');
  it('renders all layout sections (header, sidebar, timeline, action bar)');
  it('disabled action buttons have correct tooltips');
});
```

- Mock `useProjectStore` to control state.
- Mock `useParams` from `next/navigation` to return an `id`.

### Step 7 — Zustand Store Tests

```typescript
import { useProjectStore } from '@/lib/stores';
import * as api from '@/lib/api';

jest.mock('@/lib/api');

describe('useProjectStore', () => {
  beforeEach(() => {
    useProjectStore.getState().reset(); // Fresh state per test
  });

  it('fetchProject populates state correctly');
  it('updateSegment performs optimistic update');
  it('updateSegment reverts on API error');
  it('deleteSegment removes segment from state');
  it('reset clears all state');
});
```

- Create a fresh store instance per test using `reset()` to avoid state leakage.
- Mock `api.ts` functions for test isolation.

---

## Expected Output

```
frontend/
└── __tests__/
    ├── SegmentTextEditor.test.tsx   ← NEW
    ├── ImageUploader.test.tsx       ← NEW
    ├── ImagePromptDisplay.test.tsx  ← NEW
    ├── SegmentCard.test.tsx         ← NEW
    ├── Timeline.test.tsx            ← NEW
    ├── TimelineEditorPage.test.tsx  ← NEW
    └── stores.test.ts               ← NEW
```

---

## Validation

- [ ] SegmentTextEditor — 5 tests pass (render, update, debounce, no-change skip, disabled when locked).
- [ ] ImageUploader — 6 tests pass (drop zone, preview, drop event, click-browse, reject invalid, locked).
- [ ] ImagePromptDisplay — 4 tests pass (render, copy, feedback, empty placeholder).
- [ ] SegmentCard — 4 tests pass (sub-components, sequence number, lock, delete dialog).
- [ ] Timeline — 3 tests pass (card count, empty state, keys).
- [ ] Timeline Editor Page — 4 tests pass (fetch, loading, layout, disabled buttons).
- [ ] Zustand Store — 5 tests pass (fetch, optimistic, rollback, delete, reset).
- [ ] All tests pass: `npm test` or `npx jest` exits with zero failures.

---

## Notes

- Use `jest.useFakeTimers()` for debounce tests — advance timers with `jest.advanceTimersByTime(500)`.
- Mock `navigator.clipboard.writeText` for clipboard tests.
- Mock `lib/api.ts` functions globally for Zustand store tests.
- For Zustand store tests, call `reset()` in `beforeEach` to prevent state leakage between tests.
- Wrap the component tree with `<TooltipProvider>` in tests that render components using Shadcn `Tooltip`.

---

> **Parent:** [SubPhase_02_03_Overview.md](./SubPhase_02_03_Overview.md) (Layer 2)
> **Phase:** [Phase_02_Overview.md](../Phase_02_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_02_03_13_Responsive_Layout_And_Styling.md](./Task_02_03_13_Responsive_Layout_And_Styling.md)
> **Next Task:** [Task_03_01_01](../../Phase_03_The_Voice/SubPhase_03_01_TTS_Engine_Integration/Task_03_01_01*.md) (first task of SubPhase 03.01)
