import { useRef } from 'react';
import { createEvent, fireEvent, render, screen } from '@testing-library/react';
import {
  MediaKeyboardShortcutOptions,
  useMediaKeyboardShortcuts,
} from '@/lib/useMediaKeyboardShortcuts';

interface HarnessProps {
  options?: MediaKeyboardShortcutOptions;
  documentLevel?: boolean;
  video?: boolean;
}

function Harness({ options = {}, documentLevel = false, video = false }: HarnessProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mediaRef = useRef<HTMLMediaElement>(null);
  useMediaKeyboardShortcuts(documentLevel ? null : containerRef, mediaRef, options);
  return (
    <div ref={containerRef} tabIndex={0} data-testid="surface">
      <input data-testid="text" />
      <button data-testid="button">Button</button>
      {video ? (
        <video data-testid="media" ref={mediaRef as React.RefObject<HTMLVideoElement>} />
      ) : (
        <audio data-testid="media" ref={mediaRef as React.RefObject<HTMLAudioElement>} />
      )}
    </div>
  );
}

function getMedia(): HTMLMediaElement {
  return screen.getByTestId('media') as HTMLMediaElement;
}

function withDuration(media: HTMLMediaElement, duration: number) {
  Object.defineProperty(media, 'duration', {
    configurable: true,
    value: duration,
  });
}

describe('useMediaKeyboardShortcuts', () => {
  it('toggles playback with Space and K', () => {
    const onTogglePlay = jest.fn();
    render(<Harness options={{ onTogglePlay }} />);
    const surface = screen.getByTestId('surface');

    fireEvent.keyDown(surface, { key: ' ' });
    fireEvent.keyDown(surface, { key: 'k' });

    expect(onTogglePlay).toHaveBeenCalledTimes(2);
  });

  it('seeks backwards and forwards with arrows and J/L', () => {
    const onSkip = jest.fn();
    render(<Harness options={{ onSkip, seekStep: 5 }} />);
    const surface = screen.getByTestId('surface');

    fireEvent.keyDown(surface, { key: 'ArrowRight' });
    fireEvent.keyDown(surface, { key: 'ArrowLeft' });
    fireEvent.keyDown(surface, { key: 'ArrowRight', shiftKey: true });
    fireEvent.keyDown(surface, { key: 'j' });
    fireEvent.keyDown(surface, { key: 'L' });

    expect(onSkip).toHaveBeenNthCalledWith(1, 5);
    expect(onSkip).toHaveBeenNthCalledWith(2, -5);
    expect(onSkip).toHaveBeenNthCalledWith(3, 10);
    expect(onSkip).toHaveBeenNthCalledWith(4, -10);
    expect(onSkip).toHaveBeenNthCalledWith(5, 10);
  });

  it('changes volume with arrow up/down and clamps to 0..1', () => {
    const onVolumeChange = jest.fn();
    render(<Harness options={{ onVolumeChange, volumeStep: 0.25 }} />);
    const surface = screen.getByTestId('surface');
    getMedia().volume = 1;

    fireEvent.keyDown(surface, { key: 'ArrowUp' });
    fireEvent.keyDown(surface, { key: 'ArrowDown' });

    expect(onVolumeChange).toHaveBeenNthCalledWith(1, 1);
    expect(onVolumeChange).toHaveBeenNthCalledWith(2, 0.75);
  });

  it('mutes with M and seeks to start/end with Home/End', () => {
    const onToggleMute = jest.fn();
    const onSeekTo = jest.fn();
    render(<Harness options={{ onToggleMute, onSeekTo }} />);
    const surface = screen.getByTestId('surface');
    withDuration(getMedia(), 30);

    fireEvent.keyDown(surface, { key: 'm' });
    fireEvent.keyDown(surface, { key: 'Home' });
    fireEvent.keyDown(surface, { key: 'End' });

    expect(onToggleMute).toHaveBeenCalledTimes(1);
    expect(onSeekTo).toHaveBeenNthCalledWith(1, 0);
    expect(onSeekTo).toHaveBeenNthCalledWith(2, 30);
  });

  it('updates the media element directly when no callbacks are supplied', () => {
    render(<Harness />);
    const surface = screen.getByTestId('surface');
    const media = getMedia();
    withDuration(media, 30);
    media.currentTime = 10;

    fireEvent.keyDown(surface, { key: 'ArrowRight' });
    expect(media.currentTime).toBe(15);

    fireEvent.keyDown(surface, { key: 'ArrowLeft', shiftKey: true });
    expect(media.currentTime).toBe(5);
  });

  it('ignores typing fields and interactive controls for Space', () => {
    const onTogglePlay = jest.fn();
    render(<Harness options={{ onTogglePlay }} />);

    fireEvent.keyDown(screen.getByTestId('text'), { key: ' ' });
    fireEvent.keyDown(screen.getByTestId('button'), { key: ' ' });

    expect(onTogglePlay).not.toHaveBeenCalled();
  });

  it('does nothing while disabled', () => {
    const onTogglePlay = jest.fn();
    render(<Harness options={{ onTogglePlay, enabled: false }} />);

    fireEvent.keyDown(screen.getByTestId('surface'), { key: ' ' });

    expect(onTogglePlay).not.toHaveBeenCalled();
  });

  it('leaves unhandled keys alone', () => {
    render(<Harness />);
    const event = createEvent.keyDown(screen.getByTestId('surface'), {
      key: 'x',
    });

    fireEvent(screen.getByTestId('surface'), event);

    expect(event.defaultPrevented).toBe(false);
  });

  it('supports a document-level listener for modal players', () => {
    const onTogglePlay = jest.fn();
    render(<Harness options={{ onTogglePlay }} documentLevel />);

    fireEvent.keyDown(document, { key: ' ' });

    expect(onTogglePlay).toHaveBeenCalledTimes(1);
  });

  it('only toggles fullscreen for video and a supplied callback', () => {
    const onToggleFullscreen = jest.fn();
    render(
      <Harness video options={{ onToggleFullscreen }} />,
    );

    fireEvent.keyDown(screen.getByTestId('surface'), { key: 'f' });

    expect(onToggleFullscreen).toHaveBeenCalledTimes(1);
  });
});
