import { render, screen } from '@testing-library/react';
import GalleryPage from '@/app/facebook/gallery/page';
import { getGalleryItems } from '@/lib/api';
import { TooltipProvider } from '@/components/ui/tooltip';
import type { GalleryItem } from '@/lib/types';

jest.mock('next/navigation', () => ({
  usePathname: () => '/facebook/gallery',
}));

const mockItem: GalleryItem = {
  id: 'video-1',
  title: 'First video',
  created_at: '2026-01-01T00:00:00+00:00',
  updated_at: '2026-01-01T00:00:00+00:00',
  resolution_width: 1080,
  resolution_height: 1440,
  framerate: 30,
  segment_count: 8,
  file_size: 12 * 1024 * 1024,
  stream_url: '/api/gallery/video-1/stream/',
  download_url: '/api/gallery/video-1/download/',
};

jest.mock('@/lib/api', () => ({
  getGalleryItems: jest.fn(),
  getStreamUrl: () => '/api/gallery/video-1/stream/',
  getDownloadUrl: () => '/api/gallery/video-1/download/',
}));

describe('GalleryPage layout', () => {
  beforeEach(() => {
    (getGalleryItems as jest.Mock).mockResolvedValue([mockItem]);
  });

  it('uses compact tiles with more columns on wide screens', async () => {
    const { container } = render(
      <TooltipProvider>
        <GalleryPage />
      </TooltipProvider>
    );
    await screen.findByText('First video');

    const grid = container.querySelector('.columns-2');
    expect(grid).not.toBeNull();
    expect(grid?.className).toContain('sm:columns-3');
    expect(grid?.className).toContain('lg:columns-4');
    expect(grid?.className).toContain('xl:columns-5');
    expect(grid?.className).toContain('2xl:columns-6');
    expect(grid?.className).not.toContain('lg:columns-3');
  });
});
