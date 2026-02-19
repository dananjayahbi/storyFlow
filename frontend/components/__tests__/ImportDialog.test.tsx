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
    const importButton = screen.getByRole('button', { name: /^Import$/i });
    expect(importButton).toBeDisabled();
  });

  test('Import button is disabled while submitting', async () => {
    mockImportProject.mockImplementation(() => new Promise(() => {})); // Never resolves
    render(<ImportDialog {...defaultProps} />);
    // Type content into textarea
    const textarea = screen.getByPlaceholderText(/segments/i);
    fireEvent.change(textarea, { target: { value: '{"title":"T","segments":[]}' } });
    const importButton = screen.getByRole('button', { name: /^Import$/i });
    fireEvent.click(importButton);
    await waitFor(() => expect(importButton).toBeDisabled());
  });

  test('successful submission calls onSuccess and closes dialog', async () => {
    const mockProject = { id: '1', title: 'Imported', status: 'DRAFT', segments: [] };
    mockImportProject.mockResolvedValue(mockProject as any);
    render(<ImportDialog {...defaultProps} />);
    // Fill content
    const textarea = screen.getByPlaceholderText(/segments/i);
    fireEvent.change(textarea, { target: { value: '{"title":"T","segments":[{"text_content":"A","image_prompt":"B"}]}' } });
    fireEvent.click(screen.getByRole('button', { name: /^Import$/i }));
    await waitFor(() => {
      expect(mockOnSuccess).toHaveBeenCalledWith(mockProject);
      expect(mockOnOpenChange).toHaveBeenCalledWith(false);
    });
  });

  test('displays errors when API returns 400', async () => {
    mockImportProject.mockRejectedValue({
      response: { data: { error: ['Validation failed'] } },
    });
    render(<ImportDialog {...defaultProps} />);
    const textarea = screen.getByPlaceholderText(/segments/i);
    fireEvent.change(textarea, { target: { value: '{"title":"T","segments":[]}' } });
    fireEvent.click(screen.getByRole('button', { name: /^Import$/i }));
    await waitFor(() => expect(screen.getByText(/Validation failed/)).toBeInTheDocument());
  });

  test('Cancel closes the dialog', () => {
    render(<ImportDialog {...defaultProps} />);
    fireEvent.click(screen.getByRole('button', { name: /cancel/i }));
    expect(mockOnOpenChange).toHaveBeenCalledWith(false);
  });
});
