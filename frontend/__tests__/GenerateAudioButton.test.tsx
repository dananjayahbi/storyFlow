import { render, screen, fireEvent } from '@testing-library/react';
import { GenerateAudioButton } from '@/components/GenerateAudioButton';
import type { AudioGenerationState } from '@/lib/types';

describe('GenerateAudioButton', () => {
  const defaultProps = {
    segmentId: 'seg-1',
    isLocked: false,
    onGenerate: jest.fn(),
  };

  beforeEach(() => jest.clearAllMocks());

  // ── Idle state ──
  it('renders "Generate Audio" button with mic icon when idle and unlocked', () => {
    const status: AudioGenerationState = { status: 'idle' };
    render(<GenerateAudioButton {...defaultProps} generationStatus={status} />);

    const btn = screen.getByRole('button', { name: /generate audio/i });
    expect(btn).toBeEnabled();
  });

  it('clicking the idle button calls onGenerate', () => {
    const status: AudioGenerationState = { status: 'idle' };
    render(<GenerateAudioButton {...defaultProps} generationStatus={status} />);

    fireEvent.click(screen.getByRole('button', { name: /generate audio/i }));
    expect(defaultProps.onGenerate).toHaveBeenCalledTimes(1);
  });

  // ── Locked state ──
  it('renders disabled button with lock icon when locked', () => {
    const status: AudioGenerationState = { status: 'idle' };
    render(<GenerateAudioButton {...defaultProps} isLocked generationStatus={status} />);

    const btn = screen.getByRole('button', { name: /generate audio \(locked\)/i });
    expect(btn).toBeDisabled();
  });

  it('locked button does not respond to clicks', () => {
    const status: AudioGenerationState = { status: 'idle' };
    render(<GenerateAudioButton {...defaultProps} isLocked generationStatus={status} />);

    fireEvent.click(screen.getByRole('button', { name: /generate audio \(locked\)/i }));
    expect(defaultProps.onGenerate).not.toHaveBeenCalled();
  });

  // ── Generating state ──
  it('renders disabled button with "Generating…" when generating', () => {
    const status: AudioGenerationState = { status: 'generating' };
    render(<GenerateAudioButton {...defaultProps} generationStatus={status} />);

    const btn = screen.getByRole('button', { name: /generating/i });
    expect(btn).toBeDisabled();
  });

  it('generating button does not respond to clicks', () => {
    const status: AudioGenerationState = { status: 'generating' };
    render(<GenerateAudioButton {...defaultProps} generationStatus={status} />);

    fireEvent.click(screen.getByRole('button', { name: /generating/i }));
    expect(defaultProps.onGenerate).not.toHaveBeenCalled();
  });

  // ── Failed state ──
  it('renders error message and "Retry" button when failed', () => {
    const status: AudioGenerationState = { status: 'failed', error: 'TTS engine error' };
    render(<GenerateAudioButton {...defaultProps} generationStatus={status} />);

    expect(screen.getByText('TTS engine error')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /retry/i })).toBeEnabled();
  });

  it('clicking "Retry" calls onGenerate', () => {
    const status: AudioGenerationState = { status: 'failed', error: 'oops' };
    render(<GenerateAudioButton {...defaultProps} generationStatus={status} />);

    fireEvent.click(screen.getByRole('button', { name: /retry/i }));
    expect(defaultProps.onGenerate).toHaveBeenCalledTimes(1);
  });
});
