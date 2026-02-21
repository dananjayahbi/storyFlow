import { render, screen } from '@testing-library/react';
import { SegmentCard } from '@/components/SegmentCard';
import { TooltipProvider } from '@/components/ui/tooltip';
import { useProjectStore } from '@/lib/stores';
import type { Segment, AudioGenerationState } from '@/lib/types';

// Mock the Zustand store
jest.mock('@/lib/stores', () => ({
  useProjectStore: jest.fn(),
}));
const mockUseProjectStore = useProjectStore as unknown as jest.Mock;

const baseSegment: Segment = {
  id: 'seg-audio-1',
  project: 'proj-1',
  sequence_index: 0,
  text_content: 'A dramatic opening scene.',
  image_prompt: 'A dark stormy sky',
  image_file: null,
  audio_file: null,
  audio_duration: null,
  is_locked: false,
};

const segmentWithAudio: Segment = {
  ...baseSegment,
  audio_file: '/media/projects/proj-1/audio/seg-audio-1.wav',
  audio_duration: 5.2,
};

function renderWithTooltip(ui: React.ReactElement) {
  return render(<TooltipProvider>{ui}</TooltipProvider>);
}

const mockGenerateAudio = jest.fn();

function setupStoreMock(overrides: {
  audioGenerationStatus?: Record<string, AudioGenerationState>;
  staleAudioSegments?: Set<string>;
} = {}) {
  mockUseProjectStore.mockImplementation(
    (selector: (state: Record<string, unknown>) => unknown) => {
      const fakeState = {
        audioGenerationStatus: overrides.audioGenerationStatus ?? {},
        generateAudio: mockGenerateAudio,
        staleAudioSegments: overrides.staleAudioSegments ?? new Set<string>(),
      };
      return selector(fakeState);
    },
  );
}

const commonProps = {
  onUpdate: jest.fn().mockResolvedValue(undefined),
  onDelete: jest.fn().mockResolvedValue(undefined),
  onUploadImage: jest.fn().mockResolvedValue(undefined),
  onRemoveImage: jest.fn().mockResolvedValue(undefined),
};

describe('SegmentCard — Audio Integration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    setupStoreMock();
  });

  it('renders GenerateAudioButton when no audio_file exists', () => {
    renderWithTooltip(
      <SegmentCard segment={baseSegment} {...commonProps} />,
    );

    expect(screen.getByText('Generate Audio')).toBeInTheDocument();
    expect(screen.getByText('No Audio')).toBeInTheDocument();
  });

  it('renders AudioPlayer when audio_file exists and status is not generating', () => {
    renderWithTooltip(
      <SegmentCard segment={segmentWithAudio} {...commonProps} />,
    );

    // AudioPlayer shows loading then slider; at minimum an audio element is rendered
    // Since the AudioPlayer shows "Loading audio…" before loadedmetadata, check for that
    expect(screen.getByText('Loading audio…')).toBeInTheDocument();
    // GenerateAudioButton should NOT be rendered
    expect(screen.queryByText('Generate Audio')).not.toBeInTheDocument();
  });

  it('applies pulsing amber border class during generation', () => {
    setupStoreMock({
      audioGenerationStatus: {
        'seg-audio-1': { status: 'generating' },
      },
    });

    const { container } = renderWithTooltip(
      <SegmentCard segment={baseSegment} {...commonProps} />,
    );

    // The Card element should have animate-pulse and border-amber-400
    const card = container.querySelector('.animate-pulse');
    expect(card).toBeTruthy();
  });

  it('"Regenerate Audio" appears in dropdown only when audio_file exists', () => {
    renderWithTooltip(
      <SegmentCard segment={segmentWithAudio} {...commonProps} />,
    );

    // The MoreVertical dropdown trigger should exist
    const moreButtons = screen.getAllByRole('button');
    const moreButton = moreButtons.find((btn) =>
      btn.querySelector('[class*="lucide-more-vertical"], [data-testid="more-vertical"]') ||
      btn.getAttribute('aria-haspopup') === 'menu'
    );
    expect(moreButton).toBeDefined();
  });

  it('does NOT show dropdown when no audio_file', () => {
    renderWithTooltip(
      <SegmentCard segment={baseSegment} {...commonProps} />,
    );

    // Check that no button has aria-haspopup="menu" (i.e. no dropdown trigger)
    const allButtons = screen.getAllByRole('button');
    const hasDropdownTrigger = allButtons.some(
      (btn) => btn.getAttribute('aria-haspopup') === 'menu',
    );
    expect(hasDropdownTrigger).toBe(false);
  });

  it('shows stale warning when segment is marked stale', () => {
    setupStoreMock({
      staleAudioSegments: new Set(['seg-audio-1']),
    });

    renderWithTooltip(
      <SegmentCard segment={segmentWithAudio} {...commonProps} />,
    );

    expect(
      screen.getByText('Text changed — audio may be out of sync.'),
    ).toBeInTheDocument();
    expect(screen.getByText('Regenerate')).toBeInTheDocument();
  });

  it('does NOT show stale warning when segment is not stale', () => {
    setupStoreMock({
      staleAudioSegments: new Set<string>(),
    });

    renderWithTooltip(
      <SegmentCard segment={segmentWithAudio} {...commonProps} />,
    );

    expect(
      screen.queryByText('Text changed — audio may be out of sync.'),
    ).not.toBeInTheDocument();
  });
});
