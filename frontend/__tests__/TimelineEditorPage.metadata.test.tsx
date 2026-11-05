import { fireEvent, render, screen } from '@testing-library/react';

import TimelineEditorPage from '@/app/facebook/projects/[id]/page';
import { useProjectStore } from '@/lib/stores';
import type { ProjectDetail, Segment } from '@/lib/types';

jest.mock('sonner', () => ({
  toast: {
    success: jest.fn(),
    info: jest.fn(),
    warning: jest.fn(),
    error: jest.fn(),
  },
}));

let mockPathname = '/youtube/projects/42';

jest.mock('next/navigation', () => ({
  useParams: () => ({ id: '42' }),
  usePathname: () => mockPathname,
}));

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

const segment: Segment = {
  id: 'seg-1',
  project: '42',
  sequence_index: 0,
  text_content: 'Once upon a time',
  image_prompt: 'A fairy tale',
  image_file: '/media/YouTube/account/project/images/block.png',
  audio_file: null,
  audio_duration: null,
  is_locked: false,
};

const project: ProjectDetail = {
  id: '42',
  title: 'YouTube Story',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  status: 'DRAFT',
  resolution_width: 1920,
  resolution_height: 1080,
  framerate: 30,
  output_path: null,
  segments: [segment],
  default_voice_id: 'af_bella',
  tts_speed: 1,
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
  logo_opacity: 1,
  logo_margin: 20,
  outro_enabled: false,
  active_outro: null,
  bgm_enabled: false,
  active_bgm: null,
  bgm_gain_db: -18,
  bgm_ducking_db: -12,
  bgm_echo_percent: 0,
  bgm_crossfade_ms: 3000,
  tts_gain_db: 0,
  upscale_enabled: false,
  upscale_model: 'RealESRGAN_x4plus',
  upscale_denoise_strength: 0.5,
  thumbnails: [],
  thumbnail_system_prompt: '',
};

describe('TimelineEditorPage metadata management entry point', () => {
  beforeEach(() => {
    mockPathname = '/youtube/projects/42';
    useProjectStore.getState().reset();
    useProjectStore.setState({
      project,
      segments: [segment],
      isLoading: false,
      error: null,
      fetchProject: jest.fn(),
    });
    localStorage.clear();
  });

  it('shows Metadata management on the YouTube side and opens the modal', () => {
    render(<TimelineEditorPage />);

    const button = screen.getByRole('button', {
      name: /Metadata management/i,
    });
    fireEvent.click(button);

    expect(
      screen.getByText(/Draft a YouTube thumbnail prompt/i),
    ).toBeInTheDocument();
  });

  it('does not show Metadata management on the Facebook side', () => {
    mockPathname = '/facebook/projects/42';

    render(<TimelineEditorPage />);

    expect(
      screen.queryByRole('button', { name: /Metadata management/i }),
    ).not.toBeInTheDocument();
  });
});
