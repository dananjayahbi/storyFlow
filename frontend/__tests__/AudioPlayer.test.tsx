import { render, screen, fireEvent, act } from '@testing-library/react';
import { AudioPlayer } from '@/components/AudioPlayer';
import { formatTime } from '@/lib/utils';

// ── Stub HTMLMediaElement methods that jsdom doesn't implement ──
let playSpy: jest.SpyInstance;
let pauseSpy: jest.SpyInstance;
let loadSpy: jest.SpyInstance;

beforeEach(() => {
  playSpy = jest
    .spyOn(window.HTMLMediaElement.prototype, 'play')
    .mockImplementation(() => Promise.resolve());
  pauseSpy = jest
    .spyOn(window.HTMLMediaElement.prototype, 'pause')
    .mockImplementation(() => {});
  loadSpy = jest
    .spyOn(window.HTMLMediaElement.prototype, 'load')
    .mockImplementation(() => {});
});

afterEach(() => {
  jest.restoreAllMocks();
});

/** Helper to get the underlying <audio> element from the DOM */
function getAudioEl(): HTMLAudioElement {
  return document.querySelector('audio')!;
}

/** Fire a native event on the audio element so React's effect listeners hear it */
function fireAudioEvent(eventName: string) {
  const audio = getAudioEl();
  act(() => {
    audio.dispatchEvent(new Event(eventName));
  });
}

describe('formatTime utility', () => {
  it('formats 0 seconds', () => expect(formatTime(0)).toBe('0:00'));
  it('formats 59 seconds', () => expect(formatTime(59)).toBe('0:59'));
  it('formats 60 seconds', () => expect(formatTime(60)).toBe('1:00'));
  it('formats 600 seconds', () => expect(formatTime(600)).toBe('10:00'));
  it('formats NaN', () => expect(formatTime(NaN)).toBe('0:00'));
  it('formats negative', () => expect(formatTime(-5)).toBe('0:00'));
  it('formats fractional', () => expect(formatTime(65.7)).toBe('1:05'));
});

describe('AudioPlayer', () => {
  it('shows loading state before audio metadata is loaded', () => {
    render(<AudioPlayer audioUrl="/test.wav" duration={10} />);
    expect(screen.getByText('Loading audio…')).toBeInTheDocument();
  });

  it('renders play button, slider, and time display once loaded', () => {
    render(<AudioPlayer audioUrl="/test.wav" duration={10} />);

    // Simulate metadata loaded
    fireAudioEvent('loadedmetadata');

    expect(screen.getByRole('button', { name: 'Play' })).toBeInTheDocument();
    expect(screen.getByLabelText('Audio seek')).toBeInTheDocument();
    expect(screen.getByRole('slider')).toBeInTheDocument();
    // Time display (duplicated for responsive: desktop + mobile)
    expect(screen.getAllByText(/0:00/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/0:10/).length).toBeGreaterThanOrEqual(1);
  });

  it('clicking play calls audio.play and shows pause button', async () => {
    render(<AudioPlayer audioUrl="/test.wav" duration={10} />);

    fireAudioEvent('loadedmetadata');

    const playButton = screen.getByRole('button', { name: 'Play' });
    await act(async () => {
      fireEvent.click(playButton);
    });

    expect(playSpy).toHaveBeenCalled();
    expect(screen.getByRole('button', { name: 'Pause' })).toBeInTheDocument();
  });

  it('clicking pause calls audio.pause and shows play button', async () => {
    render(<AudioPlayer audioUrl="/test.wav" duration={10} />);

    fireAudioEvent('loadedmetadata');

    // Play first
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Play' }));
    });

    // Now pause
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Pause' }));
    });

    expect(pauseSpy).toHaveBeenCalled();
    expect(screen.getByRole('button', { name: 'Play' })).toBeInTheDocument();
  });

  it('handles audio error events gracefully', () => {
    render(<AudioPlayer audioUrl="/bad.wav" duration={10} />);

    fireAudioEvent('error');

    expect(screen.getByText('Audio unavailable')).toBeInTheDocument();
  });

  it('resets when audioUrl prop changes', () => {
    const { rerender } = render(<AudioPlayer audioUrl="/v1.wav" duration={10} />);

    fireAudioEvent('loadedmetadata');

    // Re-render with new URL
    rerender(<AudioPlayer audioUrl="/v2.wav" duration={15} />);
    // Should go back to loading
    expect(screen.getByText('Loading audio…')).toBeInTheDocument();
  });
});
