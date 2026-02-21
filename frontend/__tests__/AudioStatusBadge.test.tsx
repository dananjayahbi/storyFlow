import { render, screen } from '@testing-library/react';
import { AudioStatusBadge } from '@/components/AudioStatusBadge';
import type { AudioGenerationState } from '@/lib/types';

describe('AudioStatusBadge', () => {
  // ── No Audio (idle, no file) ──
  it('renders gray "No Audio" badge when no audio file and status is idle', () => {
    const status: AudioGenerationState = { status: 'idle' };
    render(
      <AudioStatusBadge audioFile={null} audioDuration={null} generationStatus={status} />,
    );

    expect(screen.getByText('No Audio')).toBeInTheDocument();
  });

  // ── Generating ──
  it('renders amber "Generating" badge when status is generating', () => {
    const status: AudioGenerationState = { status: 'generating' };
    render(
      <AudioStatusBadge audioFile={null} audioDuration={null} generationStatus={status} />,
    );

    expect(screen.getByText('Generating')).toBeInTheDocument();
  });

  // ── Ready with duration ──
  it('renders green badge with formatted duration when audio file exists', () => {
    const status: AudioGenerationState = { status: 'completed' };
    render(
      <AudioStatusBadge
        audioFile="/media/audio.wav"
        audioDuration={65}
        generationStatus={status}
      />,
    );

    expect(screen.getByText('1:05')).toBeInTheDocument();
  });

  // ── Ready without duration ──
  it('renders "Ready" text when audio file exists but duration is null', () => {
    const status: AudioGenerationState = { status: 'completed' };
    render(
      <AudioStatusBadge
        audioFile="/media/audio.wav"
        audioDuration={null}
        generationStatus={status}
      />,
    );

    expect(screen.getByText('Ready')).toBeInTheDocument();
  });

  // ── Failed ──
  it('renders red "Failed" badge when status is failed', () => {
    const status: AudioGenerationState = { status: 'failed', error: 'Engine crashed' };
    render(
      <AudioStatusBadge audioFile={null} audioDuration={null} generationStatus={status} />,
    );

    expect(screen.getByText('Failed')).toBeInTheDocument();
  });
});
