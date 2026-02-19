import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { SegmentCard } from '@/components/SegmentCard';
import { TooltipProvider } from '@/components/ui/tooltip';
import type { Segment } from '@/lib/types';

const mockSegment: Segment = {
  id: 'seg-abc-123',
  project: 'proj-1',
  sequence_index: 2,
  text_content: 'The hero enters the castle.',
  image_prompt: 'A medieval castle entrance',
  image_file: null,
  audio_file: null,
  audio_duration: null,
  is_locked: false,
};

function renderWithTooltip(ui: React.ReactElement) {
  return render(<TooltipProvider>{ui}</TooltipProvider>);
}

describe('SegmentCard', () => {
  const mockUpdate = jest.fn().mockResolvedValue(undefined);
  const mockDelete = jest.fn().mockResolvedValue(undefined);
  const mockUploadImage = jest.fn().mockResolvedValue(undefined);
  const mockRemoveImage = jest.fn().mockResolvedValue(undefined);

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders all sub-components (text editor, image zone, prompt)', () => {
    renderWithTooltip(
      <SegmentCard
        segment={mockSegment}
        onUpdate={mockUpdate}
        onDelete={mockDelete}
        onUploadImage={mockUploadImage}
        onRemoveImage={mockRemoveImage}
      />
    );
    // Text editor with segment content
    expect(
      screen.getByDisplayValue('The hero enters the castle.')
    ).toBeInTheDocument();
    // Image drop zone (no image set)
    expect(
      screen.getByText('Drop image here or click to browse')
    ).toBeInTheDocument();
    // Image prompt display
    expect(
      screen.getByText('A medieval castle entrance')
    ).toBeInTheDocument();
    // Audio placeholder
    expect(
      screen.getByText('🔊 Audio — Coming in Phase 03')
    ).toBeInTheDocument();
  });

  it('shows correct 1-based sequence number', () => {
    renderWithTooltip(
      <SegmentCard
        segment={mockSegment}
        onUpdate={mockUpdate}
        onDelete={mockDelete}
        onUploadImage={mockUploadImage}
        onRemoveImage={mockRemoveImage}
      />
    );
    // sequence_index is 2, so 1-based is #3
    expect(screen.getByText('#3')).toBeInTheDocument();
  });

  it('lock toggle calls update callback with is_locked', async () => {
    renderWithTooltip(
      <SegmentCard
        segment={mockSegment}
        onUpdate={mockUpdate}
        onDelete={mockDelete}
        onUploadImage={mockUploadImage}
        onRemoveImage={mockRemoveImage}
      />
    );
    // Find the lock button - it should show "Lock segment" tooltip trigger
    const lockButtons = screen.getAllByRole('button');
    // The first ghost button in the header should be the lock toggle
    const lockButton = lockButtons.find((btn) =>
      btn.querySelector('svg')
    );
    expect(lockButton).toBeDefined();
    fireEvent.click(lockButton!);
    expect(mockUpdate).toHaveBeenCalledWith('seg-abc-123', {
      is_locked: true,
    });
  });

  it('delete button opens confirmation dialog', async () => {
    renderWithTooltip(
      <SegmentCard
        segment={mockSegment}
        onUpdate={mockUpdate}
        onDelete={mockDelete}
        onUploadImage={mockUploadImage}
        onRemoveImage={mockRemoveImage}
      />
    );
    // Find the delete button (has text-destructive class)
    const deleteButton = screen.getAllByRole('button').find((btn) =>
      btn.classList.contains('text-destructive')
    );
    expect(deleteButton).toBeDefined();
    fireEvent.click(deleteButton!);
    // Confirmation dialog should appear
    await waitFor(() => {
      expect(screen.getByText('Delete Segment')).toBeInTheDocument();
      expect(
        screen.getByText(/Are you sure you want to delete Segment #3/)
      ).toBeInTheDocument();
    });
  });
});
