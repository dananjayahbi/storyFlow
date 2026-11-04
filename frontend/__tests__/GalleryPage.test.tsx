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
  getStreamUrl: () => '/api/gallery/video-1/stream/',
  getDownloadUrl: () => '/api/gallery/video-1/download/',
}));

describe('GalleryPage layout', () => {
  beforeEach(() => {
    (getGalleryItems as jest.Mock).mockResolvedValue([mockItem]);
  });

  function renderPage() {
    return render(
      <TooltipProvider>
        <GalleryPage />
      </TooltipProvider>
    );
  }

  it('uses compact tiles with more columns on wide screens', async () => {
    const { container } = renderPage();
    await screen.findByText('First video');

    const grid = container.querySelector('.columns-2');
    expect(grid).not.toBeNull();
    expect(grid?.className).toContain('sm:columns-3');
    expect(grid?.className).toContain('lg:columns-4');
    expect(grid?.className).toContain('xl:columns-5');
    expect(grid?.className).toContain('2xl:columns-6');
    expect(grid?.className).not.toContain('lg:columns-3');
  });

  it('keeps the filter section compact and on one row', async () => {
    renderPage();
    await screen.findByText('First video');

    const search = screen.getByPlaceholderText(/search video or project/i);
    expect(search).toHaveClass('h-8');

    const filterCard = search.closest('[data-slot="card"]');
    expect(filterCard).toHaveClass('py-0');
    expect(filterCard).toHaveClass('gap-0');

    const content = filterCard?.querySelector('[data-slot="card-content"]');
    expect(content).toHaveClass('p-2');
    expect(content).not.toHaveClass('space-y-3');

    // Only the filter row is rendered while nothing is selected.
    expect(content?.children).toHaveLength(1);
    expect(content?.firstElementChild).toHaveClass('flex-wrap');

    // All filter selects follow the same compact height.
    filterCard
      ?.querySelectorAll('[data-slot="select-trigger"]')
      .forEach((trigger) => expect(trigger).toHaveClass('h-8'));
  });
});
