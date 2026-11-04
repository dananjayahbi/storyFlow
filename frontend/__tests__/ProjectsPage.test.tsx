import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ProjectsPage from '@/app/facebook/projects/page';
import {
  getProjects,
  getSettings,
  updateSettings,
  uploadProjectThumbnail,
} from '@/lib/api';
import { TooltipProvider } from '@/components/ui/tooltip';
import type { Project } from '@/lib/types';

const pushMock = jest.fn();

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: pushMock, replace: jest.fn() }),
  usePathname: () => '/facebook/projects',
}));

jest.mock('@/lib/api', () => ({
  getProjects: jest.fn(),
  getSettings: jest.fn(),
  updateSettings: jest.fn(),
  deleteProject: jest.fn(),
  updateProject: jest.fn(),
  uploadProjectThumbnail: jest.fn(),
  removeProjectThumbnail: jest.fn(),
  createProject: jest.fn(),
  importProject: jest.fn(),
  importSegments: jest.fn(),
}));

const project: Project = {
  id: 'project-1',
  title: 'Cover Story',
  section: 'facebook',
  account: 'account-1',
  account_name: 'Default Account',
  created_at: '2026-01-01T00:00:00+00:00',
  updated_at: '2026-01-02T00:00:00+00:00',
  status: 'DRAFT',
  resolution_width: 1080,
  resolution_height: 1920,
  framerate: 30,
  segment_count: 4,
  thumbnail_url: null,
  manual_thumbnail_url: null,
  has_manual_thumbnail: false,
  thumbnail_source: null,
};

function renderPage() {
  return render(
    <TooltipProvider>
      <ProjectsPage />
    </TooltipProvider>,
  );
}

describe('ProjectsPage layouts', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (getProjects as jest.Mock).mockResolvedValue({
      count: 1,
      results: [project],
    });
    (getSettings as jest.Mock).mockResolvedValue({
      projects_view_mode: 'table',
    });
    (updateSettings as jest.Mock).mockResolvedValue({});
  });

  it('shows the project thumbnail as the first table column', async () => {
    (getProjects as jest.Mock).mockResolvedValue({
      count: 1,
      results: [
        {
          ...project,
          thumbnail_url: 'http://example.test/media/cover.png',
          thumbnail_source: 'segment',
        },
      ],
    });

    renderPage();

    await screen.findByText('Cover Story');
    expect(screen.getByText('Preview')).toBeInTheDocument();
    expect(
      screen.getByAltText('Cover Story thumbnail'),
    ).toHaveAttribute('src', 'http://example.test/media/cover.png');

    const headers = screen.getAllByRole('columnheader').map((cell) =>
      cell.textContent?.trim(),
    );
    expect(headers[0]).toBe('Preview');
  });

  it('renders the saved tile layout with an animated placeholder', async () => {
    (getSettings as jest.Mock).mockResolvedValue({
      projects_view_mode: 'tiles',
    });

    const { container } = renderPage();

    await screen.findByText('Cover Story');
    expect(screen.queryByText('Preview')).not.toBeInTheDocument();
    expect(
      screen.getByLabelText('Cover Story has no thumbnail yet'),
    ).toBeInTheDocument();
    expect(container.querySelector('.project-thumb-placeholder')).not.toBeNull();
    expect(container.querySelector('.grid')).not.toBeNull();
  });

  it('switches to tiles and persists the choice in the database', async () => {
    const user = userEvent.setup();
    renderPage();

    await screen.findByText('Cover Story');
    expect(screen.getByText('Preview')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /tiles/i }));

    await waitFor(() =>
      expect(updateSettings).toHaveBeenCalledWith({
        projects_view_mode: 'tiles',
      }),
    );
    expect(
      screen.getByLabelText('Cover Story has no thumbnail yet'),
    ).toBeInTheDocument();
  });

  it('uploads a manual thumbnail from the tile', async () => {
    (getSettings as jest.Mock).mockResolvedValue({
      projects_view_mode: 'tiles',
    });
    (uploadProjectThumbnail as jest.Mock).mockResolvedValue({
      ...project,
      thumbnail_url: 'http://example.test/media/thumbnail.png',
      manual_thumbnail_url: 'http://example.test/media/thumbnail.png',
      has_manual_thumbnail: true,
      thumbnail_source: 'manual',
    });

    renderPage();
    await screen.findByText('Cover Story');

    const file = new File(['image'], 'cover.png', { type: 'image/png' });
    const input = document.querySelector<HTMLInputElement>(
      'input[type="file"]',
    );
    expect(input).not.toBeNull();
    fireEvent.change(input as HTMLInputElement, {
      target: { files: [file] },
    });

    await waitFor(() =>
      expect(uploadProjectThumbnail).toHaveBeenCalledWith('project-1', file),
    );
    expect(
      await screen.findByAltText('Cover Story thumbnail'),
    ).toHaveAttribute('src', 'http://example.test/media/thumbnail.png');
  });
});
