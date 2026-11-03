import { useBgmStore, useProjectStore } from '@/lib/stores';
import * as api from '@/lib/api';
import type { BgmClip, ProjectDetail, TaskStatusResponse } from '@/lib/types';

jest.mock('@/lib/api');

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

function completedTask(
  progress: TaskStatusResponse['progress']
): TaskStatusResponse {
  return {
    task_id: 'task-1',
    status: 'COMPLETED',
    progress,
    completed_segments: [],
    errors: [],
  };
}

describe('useBgmStore', () => {
  beforeEach(() => {
    useBgmStore.getState().reset();
    useProjectStore.setState({
      project,
      fetchProject: jest.fn().mockResolvedValue(undefined),
    });
    jest.clearAllMocks();
  });

  it('loads clips and engine once per project', async () => {
    mockApi.getBgmClips.mockResolvedValue([clip]);
    mockApi.getMusicEngineStatus.mockResolvedValue(engine);

    await useBgmStore.getState().ensureLoaded('42');
    await useBgmStore.getState().ensureLoaded('42');

    expect(mockApi.getBgmClips).toHaveBeenCalledTimes(1);
    expect(mockApi.getMusicEngineStatus).toHaveBeenCalledTimes(1);
    expect(useBgmStore.getState().clips).toEqual([clip]);
    expect(useBgmStore.getState().engine).toEqual(engine);
  });

  it('publishes detailed progress while generating', async () => {
    let observed: number[] = [];
    mockApi.generateBgmSoundtrack.mockResolvedValue({
      task_id: 'task-1',
      status: 'PROCESSING',
      engine: 'musicgen',
      model: 'facebook/musicgen-small',
      project_id: '42',
      account_id: 'account-1',
      segments: 3,
      estimated_duration: 12,
      attach_to_project: true,
      message: 'queued',
    });
    mockApi.pollTaskStatus.mockImplementation(async (_id, onProgress) => {
      onProgress(completedTask({
        current: 1,
        total: 3,
        percentage: 33,
        description: 'Generated music 1/3',
      }));
      observed = [useBgmStore.getState().progress?.percentage ?? -1];
      return completedTask({
        current: 3,
        total: 3,
        percentage: 90,
        description: 'Generated music 3/3',
        generated_clip_id: 'clip-1',
      });
    });
    mockApi.getBgmClips.mockResolvedValue([clip]);

    const result = await useBgmStore.getState().generate('42', 'Ocean');

    expect(result).toEqual({ ok: true, clipId: 'clip-1' });
    expect(observed).toEqual([33]);
    expect(useBgmStore.getState().generating).toBe(false);
    expect(useBgmStore.getState().progress?.percentage).toBe(100);
    expect(useProjectStore.getState().fetchProject).toHaveBeenCalledWith('42');
  });

  it('surfaces the worker error when generation fails', async () => {
    mockApi.generateBgmSoundtrack.mockResolvedValue({
      task_id: 'task-1',
      status: 'PROCESSING',
      engine: 'musicgen',
      model: 'facebook/musicgen-small',
      project_id: '42',
      account_id: 'account-1',
      segments: 1,
      estimated_duration: 4,
      attach_to_project: true,
      message: 'queued',
    });
    mockApi.pollTaskStatus.mockResolvedValue({
      ...completedTask({
        current: 0,
        total: 1,
        percentage: 5,
        description: 'Loading MusicGen…',
      }),
      status: 'FAILED',
      errors: [{ segment_id: '', error: 'weights are corrupt' }],
    });

    const result = await useBgmStore.getState().generate('42', 'Ocean');

    expect(result.ok).toBe(false);
    expect(result.error).toBe('weights are corrupt');
    expect(useBgmStore.getState().generating).toBe(false);
    expect(useBgmStore.getState().error).toBe('weights are corrupt');
  });

  it('persists the selected track through project settings', async () => {
    const updateProjectSettings = jest.fn().mockResolvedValue(undefined);
    useProjectStore.setState({ updateProjectSettings });

    await useBgmStore.getState().setActiveTrack('clip-1');
    await useBgmStore.getState().setActiveTrack(null);

    expect(updateProjectSettings).toHaveBeenNthCalledWith(1, {
      active_bgm: 'clip-1',
    });
    expect(updateProjectSettings).toHaveBeenNthCalledWith(2, {
      active_bgm: null,
    });
  });
});
