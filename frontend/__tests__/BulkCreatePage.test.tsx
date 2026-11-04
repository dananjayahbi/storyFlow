import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import BulkCreatePage from '@/app/facebook/bulk-create/page';
import { getProjectRenderReadiness, getRenderStatus } from '@/lib/api';
import { TooltipProvider } from '@/components/ui/tooltip';
import type { ProjectRenderReadiness } from '@/lib/types';

jest.mock('next/navigation', () => ({
  usePathname: () => '/facebook/bulk-create',
}));

jest.mock('@/lib/useAccountId', () => ({
  useAccountId: () => 'account-1',
}));

jest.mock('@/lib/api', () => ({
  getProjectRenderReadiness: jest.fn(),
  startRender: jest.fn(),
  getRenderStatus: jest.fn(),
  cancelRender: jest.fn(),
}));

function readiness(
  id: string,
  title: string,
  overrides: Partial<ProjectRenderReadiness> = {},
): ProjectRenderReadiness {
  return {
    project_id: id,
    title,
    status: 'DRAFT',
    segment_count: 3,
    renderable: true,
    ready: true,
    is_processing: false,
    missing_images: [],
    missing_audio: [],
    message: '',
    ...overrides,
  };
}

const results = [
  readiness('ready-id', 'Ready project'),
  readiness('missing-id', 'Missing media', {
    ready: false,
    missing_images: ['seg-1'],
    missing_audio: ['seg-2', 'seg-3'],
    message: '2 segment(s) missing image files; 3 segment(s) missing audio files.',
  }),
  readiness('processing-id', 'Rendering project', {
    status: 'PROCESSING',
    renderable: false,
    ready: false,
    is_processing: true,
  }),
  readiness('done-id', 'Published project', { status: 'COMPLETED' }),
  readiness('locked-id', 'Processing status only', {
    status: 'PROCESSING',
    renderable: false,
    ready: false,
    is_processing: true,
  }),
];

function renderPage() {
  return render(
    <TooltipProvider>
      <BulkCreatePage />
    </TooltipProvider>,
  );
}

describe('BulkCreatePage readiness', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (getProjectRenderReadiness as jest.Mock).mockResolvedValue(results);
    (getRenderStatus as jest.Mock).mockResolvedValue({ status: 'COMPLETED' });
  });

  it('uses the backend render preflight for every project', async () => {
    renderPage();

    await screen.findByText('Ready project');

    expect(getProjectRenderReadiness).toHaveBeenCalledWith('facebook');
    expect(screen.getByText('(2 ready of 5)')).toBeInTheDocument();
    expect(screen.getAllByText('Ready').length).toBe(2);
    expect(screen.getByText('Not Ready')).toBeInTheDocument();
    expect(screen.getAllByText('Rendering').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Already rendering')).toHaveLength(2);
  });

  it('links to projects with the active account preserved', async () => {
    renderPage();

    const link = await screen.findByRole('link', { name: 'Ready project' });
    expect(link).toHaveAttribute(
      'href',
      '/facebook/projects/ready-id?account=account-1',
    );
  });

  it('only allows ready projects to be selected and rendered', async () => {
    const user = userEvent.setup();
    renderPage();

    await screen.findByText('Ready project');
    const missing = screen.getByRole('checkbox', {
      name: 'Select Missing media',
    });
    expect(missing).toBeDisabled();

    await user.click(
      screen.getByRole('checkbox', { name: 'Select Ready project' }),
    );
    expect(
      screen.getByRole('button', { name: /render 1 project/i }),
    ).toBeInTheDocument();
  });

  it('shows an error when the preflight request fails', async () => {
    (getProjectRenderReadiness as jest.Mock).mockRejectedValue(
      new Error('offline'),
    );

    renderPage();

    expect(
      await screen.findByText('Failed to load render readiness. Please try again.'),
    ).toBeInTheDocument();
  });
});
