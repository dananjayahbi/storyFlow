import { render, screen } from '@testing-library/react';
import DashboardPage from '@/app/facebook/dashboard/page';
import { getProjects, getGalleryItems } from '@/lib/api';
import type { GalleryItem, Project } from '@/lib/types';

jest.mock('next/navigation', () => ({
  usePathname: () => '/facebook/dashboard',
}));

jest.mock('@/lib/useAccountId', () => ({
  useAccountId: () => 'account-1',
}));

jest.mock('@/lib/api', () => ({
  getProjects: jest.fn(),
  getGalleryItems: jest.fn(),
}));

const project: Project = {
  id: 'project-1',
  title: 'Launch Story',
  section: 'facebook',
  account: 'account-1',
  created_at: '2026-01-01T00:00:00+00:00',
  updated_at: '2026-01-02T00:00:00+00:00',
  status: 'COMPLETED',
  resolution_width: 1080,
  resolution_height: 1920,
  framerate: 30,
  segment_count: 5,
};

function publishedItem(id: string): GalleryItem {
  return {
    id,
    project_id: 'project-1',
    project_title: 'Launch Story',
    title: `Published ${id}`,
    status: 'published',
    status_label: 'Published',
    created_at: '2026-01-01T00:00:00+00:00',
    updated_at: '2026-01-02T00:00:00+00:00',
    published_at: new Date().toISOString(),
    resolution_width: 1080,
    resolution_height: 1920,
    framerate: 30,
    segment_count: 5,
    file_size: 1024,
    duration: 30,
    stream_url: `/api/gallery/${id}/stream/`,
    download_url: `/api/gallery/${id}/download/`,
  };
}

describe('DashboardPage publishing KPI and chart', () => {
  beforeEach(() => {
    (getProjects as jest.Mock).mockResolvedValue({
      count: 1,
      results: [project],
    });
    (getGalleryItems as jest.Mock).mockResolvedValue([
      publishedItem('one'),
      publishedItem('two'),
    ]);
  });

  it('shows the published KPI and the publishing chart', async () => {
    render(<DashboardPage />);

    await screen.findByText('Published');

    expect(getGalleryItems).toHaveBeenCalledWith('facebook', {
      status: ['published'],
    });
    expect(screen.getByText('Live from the gallery')).toBeInTheDocument();
    expect(screen.getByText('Published videos')).toBeInTheDocument();
    expect(screen.getByText('2 published')).toBeInTheDocument();
  });

  it('still renders the dashboard when the gallery request fails', async () => {
    (getGalleryItems as jest.Mock).mockRejectedValue(new Error('offline'));

    render(<DashboardPage />);

    await screen.findByText('Launch Story');
    expect(screen.getByText('Published')).toBeInTheDocument();
    expect(screen.getByText('0 published')).toBeInTheDocument();
  });
});
