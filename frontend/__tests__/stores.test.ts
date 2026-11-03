import { useProjectStore } from '@/lib/stores';
import * as api from '@/lib/api';
import type { ProjectDetail, Segment } from '@/lib/types';

jest.mock('@/lib/api');

const mockApi = api as jest.Mocked<typeof api>;

const mockProject: ProjectDetail = {
  id: '1',
  title: 'Test Project',
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
  bgm_echo_percent: 0,
  bgm_crossfade_ms: 3000,
  tts_gain_db: 0,
  upscale_enabled: false,
  upscale_model: 'RealESRGAN_x4plus',
  upscale_denoise_strength: 0.5,
};

const mockSegments: Segment[] = [
  {
    id: 'seg-1',
    project: '1',
    sequence_index: 0,
    text_content: 'First segment',
    image_prompt: 'First prompt',
    image_file: null,
    audio_file: null,
    audio_duration: null,
    is_locked: false,
  },
  {
    id: 'seg-2',
    project: '1',
    sequence_index: 1,
    text_content: 'Second segment',
    image_prompt: 'Second prompt',
    image_file: null,
    audio_file: null,
    audio_duration: null,
    is_locked: false,
  },
];

describe('useProjectStore', () => {
  beforeEach(() => {
    useProjectStore.getState().reset();
    jest.clearAllMocks();
  });

  it('fetchProject populates state correctly', async () => {
    mockApi.getProject.mockResolvedValue(mockProject);
    mockApi.getSegments.mockResolvedValue(mockSegments);

    await useProjectStore.getState().fetchProject('1');

    const state = useProjectStore.getState();
    expect(state.project).toEqual(mockProject);
    expect(state.segments).toEqual(mockSegments);
    expect(state.isLoading).toBe(false);
    expect(state.error).toBeNull();
  });

  it('updateSegment performs optimistic update', async () => {
    // Pre-populate state
    useProjectStore.setState({ segments: mockSegments });

    const updatedSegment: Segment = {
      ...mockSegments[0],
      text_content: 'Updated text',
    };
    mockApi.updateSegment.mockResolvedValue(updatedSegment);

    const updatePromise = useProjectStore
      .getState()
      .updateSegment('seg-1', { text_content: 'Updated text' });

    // Optimistic update should apply immediately before API resolves
    const intermediateState = useProjectStore.getState();
    expect(intermediateState.segments[0].text_content).toBe('Updated text');

    await updatePromise;

    // After API resolves, state should reflect the API response
    const finalState = useProjectStore.getState();
    expect(finalState.segments[0].text_content).toBe('Updated text');
  });

  it('updateSegment reverts on API error', async () => {
    // Pre-populate state
    useProjectStore.setState({ segments: [...mockSegments] });

    mockApi.updateSegment.mockRejectedValue(new Error('API Error'));

    await useProjectStore
      .getState()
      .updateSegment('seg-1', { text_content: 'Bad update' });

    const state = useProjectStore.getState();
    // Should revert to original text
    expect(state.segments[0].text_content).toBe('First segment');
    expect(state.error).toBe('Failed to update segment');
  });

  it('deleteSegment removes segment from state', async () => {
    useProjectStore.setState({ segments: [...mockSegments] });
    mockApi.deleteSegment.mockResolvedValue(undefined);

    await useProjectStore.getState().deleteSegment('seg-1');

    const state = useProjectStore.getState();
    expect(state.segments).toHaveLength(1);
    expect(state.segments[0].id).toBe('seg-2');
  });

  it('reset clears all state', () => {
    useProjectStore.setState({
      project: mockProject,
      segments: mockSegments,
      isLoading: true,
      error: 'Some error',
    });

    useProjectStore.getState().reset();

    const state = useProjectStore.getState();
    expect(state.project).toBeNull();
    expect(state.segments).toEqual([]);
    expect(state.isLoading).toBe(false);
    expect(state.error).toBeNull();
  });
});
