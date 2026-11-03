import { render, screen, waitFor } from '@testing-library/react';
import { TooltipProvider } from '@/components/ui/tooltip';
import TimelineEditorPage from '@/app/facebook/projects/[id]/page';
import { useProjectStore } from '@/lib/stores';
import type { ProjectDetail, Segment } from '@/lib/types';

// Mock next/navigation
jest.mock('next/navigation', () => ({
  useParams: () => ({ id: '42' }),
  usePathname: () => '/facebook/projects/42',
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
  default_voice_id: 'af_bella',
  tts_speed: 1.0,
  subtitle_font_family: 'Arial',
  subtitle_font_size: 48,
  subtitle_font_color: '#FFFFFF',
  subtitle_position: 'bottom',
  subtitle_y_position: null,
  subtitle_font: '',
  subtitle_color: '#FFFFFF',
  subtitles_enabled: true,
  custom_font_file: null,
  zoom_intensity: 1.3,
  ken_burns_zoom: 1.2,
  transition_duration: 0.5,
  inter_segment_silence: 0.3,
  logo_enabled: false,
  active_logo: null,
  logo_scale: 0.15,
  logo_position: 'bottom-right',
  logo_opacity: 1.0,
  logo_margin: 20,
  outro_enabled: false,
  active_outro: null,
  bgm_enabled: false,
  active_bgm: null,
  bgm_gain_db: -18,
  bgm_ducking_db: -12,
  bgm_crossfade_ms: 3000,
  upscale_enabled: false,
  upscale_model: 'RealESRGAN_x4plus',
  upscale_denoise_strength: 0.5,
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
    // The page fetches the project on mount. Keep that a no-op by default so
    // tests that seed the store directly keep their fixture state.
    useProjectStore.setState({ fetchProject: jest.fn() });
    localStorage.clear();
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
    expect(screen.getAllByText('DRAFT').length).toBeGreaterThan(0);

    // Navigation link — sidebar has Dashboard link
    expect(
      screen.getAllByRole('link', { name: /dashboard/i }).length
    ).toBeGreaterThan(0);

    // Timeline content (segment text)
    expect(screen.getByDisplayValue('Once upon a time')).toBeInTheDocument();

    // Action bar buttons (also duplicated in the sidebar)
    expect(screen.getAllByText('Generate All Audio').length).toBeGreaterThan(0);
    expect(screen.getByText('Export')).toBeInTheDocument();
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
      expect(screen.getAllByText('Generate All Audio').length).toBeGreaterThan(0);
    });

    // Generate All Audio button is now enabled (activated in Phase 03)
    const generateButtons = screen.getAllByText('Generate All Audio');
    const generateButton = generateButtons[generateButtons.length - 1].closest('button');
    const exportButton = screen.getByText('Export').closest('button');
    expect(generateButton).toBeEnabled();
    expect(exportButton).toBeDisabled();
  });
});
