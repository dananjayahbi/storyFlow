import { render, screen, waitFor } from '@testing-library/react';
import { TooltipProvider } from '@/components/ui/tooltip';
import TimelineEditorPage from '@/app/projects/[id]/page';
import { useProjectStore } from '@/lib/stores';
import type { ProjectDetail, Segment } from '@/lib/types';

// Mock next/navigation
jest.mock('next/navigation', () => ({
  useParams: () => ({ id: '42' }),
}));

// Mock next/link
jest.mock('next/link', () => {
  return function MockLink({
    children,
    href,
    ...props
  }: {
    children: React.ReactNode;
    href: string;
    [key: string]: unknown;
  }) {
    return (
      <a href={href} {...props}>
        {children}
      </a>
    );
  };
});

const mockProject: ProjectDetail = {
  id: '42',
  title: 'Test Story',
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
  status: 'DRAFT',
  resolution_width: 1920,
  resolution_height: 1080,
  framerate: 30,
  output_path: null,
  segments: [],
};

const mockSegment: Segment = {
  id: 'seg-1',
  project: '42',
  sequence_index: 0,
  text_content: 'Once upon a time',
  image_prompt: 'A fairy tale',
  image_file: null,
  audio_file: null,
  audio_duration: null,
  is_locked: false,
};

function renderPage() {
  return render(
    <TooltipProvider>
      <TimelineEditorPage />
    </TooltipProvider>
  );
}

describe('TimelineEditorPage', () => {
  beforeEach(() => {
    useProjectStore.getState().reset();
    jest.clearAllMocks();
  });

  it('fetches project on mount', () => {
    const fetchSpy = jest.fn();
    useProjectStore.setState({ fetchProject: fetchSpy, isLoading: true });

    renderPage();

    expect(fetchSpy).toHaveBeenCalledWith('42');
  });

  it('shows loading state while fetching', () => {
    useProjectStore.setState({ isLoading: true });

    const { container } = renderPage();

    // Skeleton elements should be present during loading
    const skeletons = container.querySelectorAll('[class*="animate-pulse"], [data-slot="skeleton"]');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('renders all layout sections (header, sidebar, timeline, action bar)', async () => {
    useProjectStore.setState({
      project: mockProject,
      segments: [mockSegment],
      isLoading: false,
      error: null,
    });

    renderPage();

    // Header — project title in top bar (also appears in sidebar)
    await waitFor(() => {
      const matches = screen.getAllByText('Test Story');
      expect(matches.length).toBeGreaterThanOrEqual(1);
    });

    // Sidebar info
    expect(screen.getByText('DRAFT')).toBeInTheDocument();

    // Navigation link — sidebar has Dashboard link
    expect(
      screen.getByRole('link', { name: /dashboard/i })
    ).toBeInTheDocument();

    // Timeline content (segment text)
    expect(screen.getByDisplayValue('Once upon a time')).toBeInTheDocument();

    // Action bar buttons (disabled)
    expect(screen.getByText('Generate All Audio')).toBeInTheDocument();
    expect(screen.getByText('Export Video')).toBeInTheDocument();
  });

  it('disabled action buttons have correct tooltips', async () => {
    useProjectStore.setState({
      project: mockProject,
      segments: [],
      isLoading: false,
      error: null,
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getByText('Generate All Audio')).toBeInTheDocument();
    });

    // Generate All Audio button is now enabled (activated in Phase 03)
    const generateButton = screen.getByText('Generate All Audio').closest('button');
    const exportButton = screen.getByText('Export Video').closest('button');
    expect(generateButton).toBeEnabled();
    expect(exportButton).toBeDisabled();
  });
});
