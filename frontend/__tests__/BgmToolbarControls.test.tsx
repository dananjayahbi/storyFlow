import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { BgmToolbarControls } from '@/components/BgmToolbarControls';
import { BgmGenerationProgress } from '@/components/BgmGenerationProgress';
import { useBgmStore, useProjectStore } from '@/lib/stores';
import * as api from '@/lib/api';
import type { BgmClip, ProjectDetail, TaskStatusResponse } from '@/lib/types';

jest.mock('@/lib/api');
jest.mock('sonner', () => ({
  toast: { success: jest.fn(), error: jest.fn(), info: jest.fn() },
}));

const mockApi = api as jest.Mocked<typeof api>;

const clip = {
  id: 'clip-1',
  name: 'Ocean theme',
  source: 'generated',
} as unknown as BgmClip;

const engine = {
  engine: 'musicgen',
  model: 'facebook/musicgen-small',
  installed: true,
  torch_installed: true,
  torch_version: '2.6.0',
  cuda_available: true,
  device: 'cuda',
  available: true,
  python: '3.11',
  reason: null,
  sample_rate: 32000,
  continuation_tail_seconds: 3,
  crossfade_ms: 3000,
} as const;

const project = {
  id: '42',
  title: 'Ocean',
  bgm_enabled: true,
  active_bgm: null,
} as unknown as ProjectDetail;

const done: TaskStatusResponse = {
  task_id: 'task-1',
  status: 'COMPLETED',
  progress: {
    current: 1,
    total: 1,
    percentage: 100,
    description: 'Soundtrack ready',
    generated_clip_id: 'clip-1',
  },
  completed_segments: [],
  errors: [],
};

describe('BgmToolbarControls', () => {
  beforeEach(() => {
    useBgmStore.getState().reset();
    useProjectStore.setState({
      fetchProject: jest.fn().mockResolvedValue(undefined),
    });
    jest.clearAllMocks();
    mockApi.getBgmClips.mockResolvedValue([clip]);
    mockApi.getMusicEngineStatus.mockResolvedValue(engine);
  });

  it('renders nothing when background music is disabled', () => {
    render(<BgmToolbarControls project={{ ...project, bgm_enabled: false }} />);
    expect(screen.queryByText('Generate with MusicGen')).not.toBeInTheDocument();
  });

  it('shows the track picker and MusicGen button when enabled', async () => {
    render(<BgmToolbarControls project={project} />);

    expect(screen.getByText('Generate with MusicGen')).toBeInTheDocument();
    expect(screen.getByTitle('Background music track')).toBeInTheDocument();
    await waitFor(() => expect(mockApi.getBgmClips).toHaveBeenCalled());
  });

  it('queues a soundtrack and shows detailed progress', async () => {
    let release: (status: TaskStatusResponse) => void = () => {};
    mockApi.generateBgmSoundtrack.mockResolvedValue({
      task_id: 'task-1',
      status: 'PROCESSING',
      engine: 'musicgen',
      model: 'facebook/musicgen-small',
      project_id: '42',
      account_id: 'account-1',
      segments: 4,
      estimated_duration: 16,
      attach_to_project: true,
      message: 'queued',
    });
    mockApi.pollTaskStatus.mockImplementation(
      (_id, onProgress) =>
        new Promise<TaskStatusResponse>((resolve) => {
          onProgress({
            ...done,
            status: 'PROCESSING',
            progress: {
              current: 2,
              total: 4,
              percentage: 48,
              description: 'Generated music 2/4',
            },
          });
          release = resolve;
        })
    );

    render(
      <>
        <BgmToolbarControls project={project} />
        <BgmGenerationProgress />
      </>
    );
    fireEvent.click(screen.getByText('Generate with MusicGen'));

    await waitFor(() =>
      expect(screen.getByText('Generated music 2/4')).toBeInTheDocument()
    );
    expect(screen.getByText('48%')).toBeInTheDocument();
    expect(screen.getByText('(2/4)')).toBeInTheDocument();

    release(done);
    await waitFor(() =>
      expect(
        screen.getByText('Soundtrack generated and attached to this project')
      ).toBeInTheDocument()
    );
  });

  it('renders a compact detailed progress bar', () => {
    useBgmStore.setState({
      generating: true,
      message: 'Encoding soundtrack to MP3…',
      progress: { current: 4, total: 4, percentage: 95 },
    });

    render(<BgmGenerationProgress />);

    expect(screen.getByText('Encoding soundtrack to MP3…')).toBeInTheDocument();
    expect(screen.getByText('95%')).toBeInTheDocument();
    expect(screen.getByText('(4/4)')).toBeInTheDocument();
  });
});
