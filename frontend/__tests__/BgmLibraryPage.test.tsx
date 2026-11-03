import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { BgmLibraryPage } from '@/components/BgmLibraryPage';
import type { BgmClip } from '@/lib/types';

jest.mock('next/navigation', () => ({
  usePathname: () => '/facebook/bgm-library',
}));

jest.mock('@/lib/useAccountId', () => ({
  useAccountId: () => 'account-1',
}));

jest.mock('sonner', () => ({
  toast: { success: jest.fn(), error: jest.fn(), info: jest.fn() },
}));

jest.mock('@/components/AudioPlayer', () => ({
  AudioPlayer: ({ audioUrl }: { audioUrl: string }) => (
    <div data-testid="audio-player">{audioUrl}</div>
  ),
}));

const apiMock = {
  getBgmClips: jest.fn(),
  uploadBgmClip: jest.fn(),
  updateBgmClip: jest.fn(),
  deleteBgmClip: jest.fn(),
};

jest.mock('@/lib/api', () => ({
  getBgmClips: (...args: unknown[]) => apiMock.getBgmClips(...args),
  uploadBgmClip: (...args: unknown[]) => apiMock.uploadBgmClip(...args),
  updateBgmClip: (...args: unknown[]) => apiMock.updateBgmClip(...args),
  deleteBgmClip: (...args: unknown[]) => apiMock.deleteBgmClip(...args),
}));

function clip(overrides: Partial<BgmClip>): BgmClip {
  return {
    id: 'clip-1',
    account: 'account-1',
    account_name: 'Page One',
    section: 'facebook',
    name: 'Ocean drone',
    file: 'bgm/facebook/account-1/ocean.mp3',
    file_url: '/media/bgm/facebook/account-1/ocean.mp3',
    is_shared: false,
    source: 'uploaded',
    project: null,
    generation_metadata: {},
    original_name: 'ocean.wav',
    original_format: 'wav',
    duration: 95,
    file_size: 3 * 1024 * 1024,
    can_edit: true,
    created_at: '2026-01-01T00:00:00+00:00',
    updated_at: '2026-01-01T00:00:00+00:00',
    ...overrides,
  };
}

describe('BgmLibraryPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    apiMock.getBgmClips.mockResolvedValue([
      clip({}),
      clip({
        id: 'clip-2',
        account: 'account-2',
        account_name: 'Page Two',
        name: 'Shared strings',
        is_shared: true,
        can_edit: false,
      }),
    ]);
  });

  it('lists own and shared tracks with the inbuilt player', async () => {
    render(<BgmLibraryPage />);

    expect(await screen.findByText('Ocean drone')).toBeInTheDocument();
    expect(screen.getByText('Shared strings')).toBeInTheDocument();
    expect(screen.getByText('Shared')).toBeInTheDocument();
    expect(screen.getByText(/Shared by Page Two/)).toBeInTheDocument();
    expect(screen.getAllByTestId('audio-player')).toHaveLength(2);
  });

  it('uploads a selected audio file', async () => {
    apiMock.uploadBgmClip.mockResolvedValue(
      clip({ id: 'clip-3', name: 'New track' })
    );
    render(<BgmLibraryPage />);
    await screen.findByText('Ocean drone');

    const fileInput = screen.getByLabelText('Audio file') as HTMLInputElement;
    const file = new File(['audio'], 'new-track.wav', { type: 'audio/wav' });
    fireEvent.change(fileInput, { target: { files: [file] } });
    fireEvent.click(screen.getByRole('button', { name: /Upload & convert/i }));

    await waitFor(() => {
      expect(apiMock.uploadBgmClip).toHaveBeenCalledWith(
        file,
        expect.objectContaining({ name: 'new-track', isShared: false })
      );
    });
    expect(await screen.findByText('New track')).toBeInTheDocument();
  });

  it('toggles sharing for an owned track', async () => {
    apiMock.updateBgmClip.mockResolvedValue(
      clip({ is_shared: true })
    );
    render(<BgmLibraryPage />);
    await screen.findByText('Ocean drone');

    const shareButtons = screen.getAllByRole('button', { name: /^Share$/i });
    fireEvent.click(shareButtons[0]);

    await waitFor(() => {
      expect(apiMock.updateBgmClip).toHaveBeenCalledWith('clip-1', {
        is_shared: true,
      });
    });
  });
});
