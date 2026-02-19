import { render, screen, fireEvent, act } from '@testing-library/react';
import { SegmentTextEditor } from '@/components/SegmentTextEditor';

jest.useFakeTimers();

describe('SegmentTextEditor', () => {
  const mockSave = jest.fn().mockResolvedValue(undefined);

  beforeEach(() => {
    jest.clearAllMocks();
  });

  afterEach(() => {
    jest.runOnlyPendingTimers();
  });

  it('renders textarea with initial content', () => {
    render(
      <SegmentTextEditor
        segmentId="seg-1"
        initialContent="Hello"
        isLocked={false}
        onSave={mockSave}
      />
    );
    expect(screen.getByDisplayValue('Hello')).toBeInTheDocument();
  });

  it('updates local state on input change', () => {
    render(
      <SegmentTextEditor
        segmentId="seg-1"
        initialContent=""
        isLocked={false}
        onSave={mockSave}
      />
    );
    fireEvent.change(screen.getByRole('textbox'), {
      target: { value: 'New text' },
    });
    expect(screen.getByDisplayValue('New text')).toBeInTheDocument();
  });

  it('debounced save fires after 500ms of inactivity', async () => {
    render(
      <SegmentTextEditor
        segmentId="seg-1"
        initialContent=""
        isLocked={false}
        onSave={mockSave}
      />
    );
    fireEvent.change(screen.getByRole('textbox'), {
      target: { value: 'Typing...' },
    });
    expect(mockSave).not.toHaveBeenCalled();
    await act(async () => {
      jest.advanceTimersByTime(500);
    });
    expect(mockSave).toHaveBeenCalledWith('seg-1', {
      text_content: 'Typing...',
    });
  });

  it('no save triggered if text has not changed', () => {
    render(
      <SegmentTextEditor
        segmentId="seg-1"
        initialContent="Same"
        isLocked={false}
        onSave={mockSave}
      />
    );
    jest.advanceTimersByTime(1000);
    expect(mockSave).not.toHaveBeenCalled();
  });

  it('textarea is disabled when isLocked is true', () => {
    render(
      <SegmentTextEditor
        segmentId="seg-1"
        initialContent=""
        isLocked={true}
        onSave={mockSave}
      />
    );
    expect(screen.getByRole('textbox')).toBeDisabled();
  });
});
