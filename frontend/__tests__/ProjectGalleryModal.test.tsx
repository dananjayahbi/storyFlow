import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TooltipProvider } from '@/components/ui/tooltip';
import { ProjectGalleryModal } from '@/components/ProjectGalleryModal';
import {
  getGalleryItems,
  updateGalleryItemStatus,
} from '@/lib/api';
import type { GalleryItem } from '@/lib/types';

const mockItem: GalleryItem = {
  id: 'video-1',
  project_id: 'project-1',
  project_title: 'First video',
  title: 'First video',
  status: 'rendered',
  status_label: 'Rendered',
  created_at: '2026-01-01T00:00:00+00:00',
  updated_at: '2026-01-01T00:00:00+00:00',
  published_at: null,
  resolution_width: 1080,
  resolution_height: 1440,
  framerate: 30,
  segment_count: 8,
  file_size: 12 * 1024 * 1024,
  duration: 42,
  stream_url: '/api/gallery/video-1/stream/',
  download_url: '/api/gallery/video-1/download/',
};

jest.mock('@/lib/api', () => ({
  getGalleryItems: jest.fn(),
  getStreamUrl: (id: string) => `/api/gallery/${id}/stream/`,
  getDownloadUrl: (id: string) => `/api/gallery/${id}/download/`,
  updateGalleryItemStatus: jest.fn(),
  bulkUpdateGalleryStatus: jest.fn(),
  deleteGalleryItem: jest.fn(),
  bulkDeleteGalleryItems: jest.fn(),
}));

function renderModal() {
  return render(
    <TooltipProvider>
      <ProjectGalleryModal
        open
        onOpenChange={() => {}}
        projectId="project-1"
        projectTitle="First video"
      />
    </TooltipProvider>,
  );
}

describe('ProjectGalleryModal', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (getGalleryItems as jest.Mock).mockResolvedValue([mockItem]);
    (updateGalleryItemStatus as jest.Mock).mockResolvedValue({
      ...mockItem,
      status: 'published',
    });
  });

  it('opens the player popup when a rendering is clicked', async () => {
    const user = userEvent.setup();
    renderModal();

    await screen.findByText('First video');
    expect(document.querySelectorAll('[role="dialog"]')).toHaveLength(1);
    expect(document.querySelectorAll('video')).toHaveLength(1);

    await user.click(screen.getByText('First video'));

    const dialogs = Array.from(document.querySelectorAll('[role="dialog"]'));
    expect(dialogs).toHaveLength(2);
    const player = dialogs[dialogs.length - 1];
    expect(
      player.querySelector('video')?.getAttribute('src'),
    ).toContain('/api/gallery/video-1/stream/');
  });

  it('updates the status of one rendering from the player popup', async () => {
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    renderModal();

    await user.click(await screen.findByText('First video'));
    const dialogs = Array.from(document.querySelectorAll('[role="dialog"]'));
    const player = dialogs[dialogs.length - 1];

    await user.click(within(player as HTMLElement).getByRole('button', { name: /rendered/i }));
    await user.click(screen.getByRole('menuitem', { name: /published/i }));

    expect(updateGalleryItemStatus).toHaveBeenCalledWith(
      'video-1',
      'published',
    );
  });
});
