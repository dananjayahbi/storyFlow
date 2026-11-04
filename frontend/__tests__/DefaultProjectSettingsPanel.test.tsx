import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DefaultProjectSettingsPanel } from '@/components/DefaultProjectSettingsPanel';
import {
  getProjectSettingsDefaults,
  resetProjectSettingsDefault,
  updateProjectSettingsDefault,
} from '@/lib/api';
import type { ProjectSettingsProfile } from '@/lib/types';

jest.mock('@/lib/api', () => ({
  getProjectSettingsDefaults: jest.fn(),
  updateProjectSettingsDefault: jest.fn(),
  resetProjectSettingsDefault: jest.fn(),
}));

jest.mock('@/lib/stores', () => ({
  useSettingsStore: () => ({
    availableVoices: [
      { id: 'af_bella', name: 'Bella', language: 'en-US', sample_url: null },
    ],
    fetchVoices: jest.fn(),
    ttsEngines: [{ id: 'qwen', label: 'Qwen', available: false, device: '', supports_cloning: true }],
    fetchTtsEngines: jest.fn(),
    logos: [],
    fetchLogos: jest.fn(),
    outroVideos: [],
    fetchOutroVideos: jest.fn(),
  }),
}));

function profile(
  width: number,
  height: number,
  overrides: Partial<ProjectSettingsProfile> = {},
): ProjectSettingsProfile {
  return {
    id: null,
    resolution_width: width,
    resolution_height: height,
    is_customized: false,
    default_voice_id: 'af_bella',
    tts_speed: 1,
    tts_engine: 'kokoro',
    qwen_mode: 'custom_voice',
    qwen_speaker: 'Aiden',
    qwen_language: 'English',
    qwen_instruct: '',
    qwen_max_new_tokens: 1024,
    qwen_clone_x_vector_only: true,
    active_voice_reference: null,
    subtitle_font_family: 'Arial',
    subtitle_font_size: 48,
    subtitle_font_color: '#FFFFFF',
    subtitle_position: 'bottom',
    subtitle_y_position: null,
    subtitle_font: '',
    subtitle_color: '#FFFFFF',
    subtitles_enabled: true,
    custom_font_file: null,
    framerate: 30,
    ken_burns_zoom: 1.2,
    transition_duration: 0.5,
    zoom_intensity: 1.3,
    inter_segment_silence: 0.3,
    logo_enabled: false,
    active_logo: null,
    logo_scale: 0.15,
    logo_position: 'bottom-right',
    logo_opacity: 1,
    logo_margin: 20,
    outro_enabled: false,
    active_outro: null,
    bgm_gain_db: -18,
    bgm_ducking_db: -12,
    bgm_echo_percent: 0,
    tts_gain_db: 0,
    upscale_enabled: false,
    upscale_model: 'RealESRGAN_x4plus',
    upscale_denoise_strength: 0.5,
    ...overrides,
  };
}

describe('DefaultProjectSettingsPanel', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (getProjectSettingsDefaults as jest.Mock).mockResolvedValue([
      profile(720, 1280, { is_customized: true, subtitle_font_size: 70 }),
      profile(1920, 1080),
    ]);
    (updateProjectSettingsDefault as jest.Mock).mockImplementation(
      (width: number, height: number, payload: Partial<ProjectSettingsProfile>) =>
        Promise.resolve(profile(width, height, { ...payload, is_customized: true })),
    );
    (resetProjectSettingsDefault as jest.Mock).mockImplementation(
      (width: number, height: number) => Promise.resolve(profile(width, height)),
    );
  });

  it('shows the per-resolution profile and saves edits for that resolution', async () => {
    const user = userEvent.setup();
    render(<DefaultProjectSettingsPanel />);

    await screen.findByText('Default Project Settings');
    expect(screen.getByText(/Custom defaults are active/)).toBeInTheDocument();

    const sizeSlider = screen.getAllByRole('slider')[1];
    sizeSlider.focus();
    await user.keyboard('{ArrowRight}');

    await user.click(screen.getByRole('button', { name: /Save defaults for 720 × 1280/ }));

    await waitFor(() => {
      expect(updateProjectSettingsDefault).toHaveBeenCalledWith(
        720,
        1280,
        expect.objectContaining({ subtitle_font_size: 71 }),
      );
    });
  });

  it('reverts a customised resolution to the account defaults', async () => {
    const user = userEvent.setup();
    render(<DefaultProjectSettingsPanel />);

    await screen.findByText('Default Project Settings');
    await user.click(screen.getByRole('button', { name: /Use account defaults/ }));

    await waitFor(() => {
      expect(resetProjectSettingsDefault).toHaveBeenCalledWith(720, 1280);
    });
    expect(
      await screen.findByText(/projects fall back to the account settings/),
    ).toBeInTheDocument();
  });
});
