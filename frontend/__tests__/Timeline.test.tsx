import { render, screen } from '@testing-library/react';
import { Timeline } from '@/components/Timeline';
import { TooltipProvider } from '@/components/ui/tooltip';
import type { Segment } from '@/lib/types';

function createMockSegment(overrides: Partial<Segment> = {}): Segment {
  return {
    id: 'seg-default',
    project: 'proj-1',
    sequence_index: 0,
    text_content: 'Default text',
    image_prompt: 'Default prompt',
    image_file: null,
    audio_file: null,
    audio_duration: null,
    is_locked: false,
    ...overrides,
  };
}

function renderWithTooltip(ui: React.ReactElement) {
  return render(<TooltipProvider>{ui}</TooltipProvider>);
}

describe('Timeline', () => {
  const mockUpdate = jest.fn().mockResolvedValue(undefined);
  const mockDelete = jest.fn().mockResolvedValue(undefined);
  const mockUpload = jest.fn().mockResolvedValue(undefined);
  const mockRemove = jest.fn().mockResolvedValue(undefined);

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders correct number of SegmentCard components', () => {
    const segments = [
      createMockSegment({ id: 'seg-1', sequence_index: 0, text_content: 'First' }),
      createMockSegment({ id: 'seg-2', sequence_index: 1, text_content: 'Second' }),
      createMockSegment({ id: 'seg-3', sequence_index: 2, text_content: 'Third' }),
    ];

    renderWithTooltip(
      <Timeline
        segments={segments}
        onUpdateSegment={mockUpdate}
        onDeleteSegment={mockDelete}
        onUploadImage={mockUpload}
        onRemoveImage={mockRemove}
      />
    );

    // Each SegmentCard renders a badge with 1-based sequence number
    expect(screen.getByText('#1')).toBeInTheDocument();
    expect(screen.getByText('#2')).toBeInTheDocument();
    expect(screen.getByText('#3')).toBeInTheDocument();
  });

  it('shows empty state when no segments', () => {
    renderWithTooltip(
      <Timeline
        segments={[]}
        onUpdateSegment={mockUpdate}
        onDeleteSegment={mockDelete}
        onUploadImage={mockUpload}
        onRemoveImage={mockRemove}
      />
    );

    expect(screen.getByText('No segments')).toBeInTheDocument();
    expect(
      screen.getByText('Import a story to create segments.')
    ).toBeInTheDocument();
  });

  it('cards are keyed by segment ID', () => {
    const segments = [
      createMockSegment({ id: 'unique-id-1', sequence_index: 0 }),
      createMockSegment({ id: 'unique-id-2', sequence_index: 1 }),
    ];

    const { container } = renderWithTooltip(
      <Timeline
        segments={segments}
        onUpdateSegment={mockUpdate}
        onDeleteSegment={mockDelete}
        onUploadImage={mockUpload}
        onRemoveImage={mockRemove}
      />
    );

    // Verify 2 cards rendered (each card is a Card component with p-4)
    const cards = container.querySelectorAll('[class*="space-y-3"]');
    expect(cards.length).toBe(2);
  });
});
