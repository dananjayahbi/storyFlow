# Task 02.01.10 — Write Frontend Import Tests

> **Sub-Phase:** 02.01 — Import & Parse Engine
> **Phase:** Phase 02 — The Logic
> **Complexity:** Medium
> **Dependencies:** Task 02.01.09 (Dashboard Integration complete)
> **Parent Document:** [SubPhase_02_01_Overview.md](./SubPhase_02_01_Overview.md)

---

## Objective

Write frontend tests for the `ImportDialog` component and the dashboard import integration, verifying rendering, user interactions, form submission, and error handling.

---

## Instructions

### Step 1 — Create the test file

Create a test file for `ImportDialog`. Use the project's testing convention — either colocated (e.g., `frontend/components/__tests__/ImportDialog.test.tsx`) or in a top-level `__tests__/` directory.

### Step 2 — ImportDialog component tests

```typescript
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ImportDialog from '@/components/ImportDialog';
import * as api from '@/lib/api';

// Mock the API module
jest.mock('@/lib/api');
const mockImportProject = api.importProject as jest.MockedFunction<typeof api.importProject>;

describe('ImportDialog', () => {
  const mockOnOpenChange = jest.fn();
  const mockOnSuccess = jest.fn();

  const defaultProps = {
    open: true,
    onOpenChange: mockOnOpenChange,
    onSuccess: mockOnSuccess,
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('renders correctly when open', () => {
    render(<ImportDialog {...defaultProps} />);
    expect(screen.getByText('Import Story')).toBeInTheDocument();
    expect(screen.getByText('JSON')).toBeInTheDocument();
    expect(screen.getByText('Text')).toBeInTheDocument();
  });

  test('format toggle switches between JSON and Text', () => {
    render(<ImportDialog {...defaultProps} />);
    const textButton = screen.getByText('Text');
    fireEvent.click(textButton);
    // Verify placeholder updates (text format placeholder content)
    expect(screen.getByPlaceholderText(/Text:/)).toBeInTheDocument();
  });

  test('Import button is disabled when textarea is empty', () => {
    render(<ImportDialog {...defaultProps} />);
    const importButton = screen.getByRole('button', { name: /import/i });
    expect(importButton).toBeDisabled();
  });

  test('Import button is disabled while submitting', async () => {
    mockImportProject.mockImplementation(() => new Promise(() => {})); // Never resolves
    render(<ImportDialog {...defaultProps} />);
    // Type content into textarea
    const textarea = screen.getByRole('textbox', { name: /content/i });
    fireEvent.change(textarea, { target: { value: '{"title":"T","segments":[]}' } });
    const importButton = screen.getByRole('button', { name: /import/i });
    fireEvent.click(importButton);
    await waitFor(() => expect(importButton).toBeDisabled());
  });

  test('successful submission calls onSuccess and closes dialog', async () => {
    const mockProject = { id: 1, title: 'Imported', status: 'DRAFT', segments: [] };
    mockImportProject.mockResolvedValue(mockProject as any);
    render(<ImportDialog {...defaultProps} />);
    // Fill content
    const textarea = screen.getByRole('textbox', { name: /content/i });
    fireEvent.change(textarea, { target: { value: '{"title":"T","segments":[{"text_content":"A","image_prompt":"B"}]}' } });
    fireEvent.click(screen.getByRole('button', { name: /import/i }));
    await waitFor(() => {
      expect(mockOnSuccess).toHaveBeenCalledWith(mockProject);
      expect(mockOnOpenChange).toHaveBeenCalledWith(false);
    });
  });

  test('displays errors when API returns 400', async () => {
    mockImportProject.mockRejectedValue({
      response: { data: { error: 'Validation failed', details: { title: ['Required'] } } },
    });
    render(<ImportDialog {...defaultProps} />);
    const textarea = screen.getByRole('textbox', { name: /content/i });
    fireEvent.change(textarea, { target: { value: 'invalid' } });
    fireEvent.click(screen.getByRole('button', { name: /import/i }));
    await waitFor(() => expect(screen.getByText(/Validation failed|Required/)).toBeInTheDocument());
  });

  test('Cancel closes the dialog', () => {
    render(<ImportDialog {...defaultProps} />);
    fireEvent.click(screen.getByRole('button', { name: /cancel/i }));
    expect(mockOnOpenChange).toHaveBeenCalledWith(false);
  });
});
```

### Step 3 — Dashboard integration tests

```typescript
describe('Dashboard Import Integration', () => {
  test('renders Import Story button', () => {
    render(<DashboardPage />);
    expect(screen.getByText('Import Story')).toBeInTheDocument();
  });

  test('clicking Import Story opens ImportDialog', () => {
    render(<DashboardPage />);
    fireEvent.click(screen.getByText('Import Story'));
    expect(screen.getByText('Import Story')).toBeInTheDocument(); // Dialog title
  });
});
```

### Step 4 — Run tests

```bash
cd frontend
npm test
```

---

## Expected Output

```
frontend/
└── components/
    └── __tests__/
        └── ImportDialog.test.tsx    ← NEW (or colocated pattern)
```

---

## Validation

- [ ] ImportDialog renders correctly when `open={true}`.
- [ ] Format toggle switches between JSON and Text.
- [ ] Placeholder text updates when format changes.
- [ ] "Import" button is disabled when textarea is empty.
- [ ] "Import" button is disabled while submitting.
- [ ] Successful submission calls `onSuccess` and closes dialog.
- [ ] Error display when API returns 400.
- [ ] "Cancel" closes the dialog.
- [ ] Dashboard page renders "Import Story" button.
- [ ] Clicking "Import Story" opens the ImportDialog.
- [ ] All tests pass with `npm test`.

---

## Notes

- Mock the Axios API client (`jest.mock('@/lib/api')`) for test isolation — no real API calls.
- Focus on behavior, not implementation details (don't test internal state directly).
- Adapt selectors (e.g., `getByRole`, `getByText`, `getByPlaceholderText`) to match the actual rendered output of the component.
- If using Vitest instead of Jest, adjust mock syntax accordingly.

---

> **Parent:** [SubPhase_02_01_Overview.md](./SubPhase_02_01_Overview.md) (Layer 2)
> **Phase:** [Phase_02_Overview.md](../Phase_02_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_02_01_09_Integrate_Dashboard_Import_Button.md](./Task_02_01_09_Integrate_Dashboard_Import_Button.md)
> **Next Task:** [Task_02_01_11_Error_Handling_And_Edge_Cases.md](./Task_02_01_11_Error_Handling_And_Edge_Cases.md)
