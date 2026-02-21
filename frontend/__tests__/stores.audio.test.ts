import { useProjectStore } from '@/lib/stores';
import * as api from '@/lib/api';
import type { Segment } from '@/lib/types';

jest.mock('@/lib/api');
const mockApi = api as jest.Mocked<typeof api>;

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
    audio_file: '/media/audio/seg-2.wav',
    audio_duration: 3.5,
    is_locked: false,
  },
];

describe('Zustand Audio Actions', () => {
  beforeEach(() => {
    useProjectStore.getState().reset();
    jest.clearAllMocks();
  });

  // ── setSegmentAudioStatus ──
  it('setSegmentAudioStatus updates the correct segment status', () => {
    useProjectStore.getState().setSegmentAudioStatus('seg-1', { status: 'generating' });

    const state = useProjectStore.getState();
    expect(state.audioGenerationStatus['seg-1']).toEqual({ status: 'generating' });
    expect(state.audioGenerationStatus['seg-2']).toBeUndefined();
  });

  // ── clearBulkProgress ──
  it('clearBulkProgress resets bulkGenerationProgress to null', () => {
    useProjectStore.setState({
      bulkGenerationProgress: {
        task_id: 'task-1',
        status: 'PROCESSING',
        total: 5,
        completed: 2,
        failed: 0,
        completed_segments: [],
        errors: [],
      },
    });

    useProjectStore.getState().clearBulkProgress();

    expect(useProjectStore.getState().bulkGenerationProgress).toBeNull();
  });

  // ── generateAudio ──
  it('generateAudio sets generating status and calls API', async () => {
    useProjectStore.setState({ segments: [...mockSegments] });

    mockApi.generateSegmentAudio.mockResolvedValue({
      task_id: 'task-abc',
      segment_id: 'seg-1',
      status: 'PENDING' as const,
      message: 'Audio generation queued',
    });
    mockApi.pollTaskStatus.mockResolvedValue({
      task_id: 'task-abc',
      status: 'COMPLETED' as const,
      progress: { current: 1, total: 1, percentage: 100 },
      completed_segments: [{ segment_id: 'seg-1', audio_url: '/media/audio/seg-1.wav', duration: 4.2 }],
      errors: [],
    });
    mockApi.getSegment.mockResolvedValue({
      ...mockSegments[0],
      audio_file: '/media/audio/seg-1.wav',
      audio_duration: 4.2,
    });

    const promise = useProjectStore.getState().generateAudio('seg-1');

    // Should immediately be in generating status
    expect(useProjectStore.getState().audioGenerationStatus['seg-1']?.status).toBe('generating');

    await promise;

    // After completion
    expect(useProjectStore.getState().audioGenerationStatus['seg-1']?.status).toBe('completed');
    expect(mockApi.generateSegmentAudio).toHaveBeenCalledWith('seg-1');
  });

  it('generateAudio sets failed status on API error', async () => {
    useProjectStore.setState({ segments: [...mockSegments] });

    mockApi.generateSegmentAudio.mockRejectedValue(new Error('Network error'));

    await useProjectStore.getState().generateAudio('seg-1');

    const status = useProjectStore.getState().audioGenerationStatus['seg-1'];
    expect(status?.status).toBe('failed');
    expect(status && 'error' in status ? status.error : '').toBe('Network error');
  });

  // ── cancelGeneration ──
  it('cancelGeneration resets generating segments to idle', () => {
    useProjectStore.setState({
      audioGenerationStatus: {
        'seg-1': { status: 'generating' },
        'seg-2': { status: 'completed' },
      },
      audioTaskId: 'task-xyz',
      bulkGenerationProgress: {
        task_id: 'task-xyz',
        status: 'PROCESSING',
        total: 2,
        completed: 1,
        failed: 0,
        completed_segments: [],
        errors: [],
      },
    });

    useProjectStore.getState().cancelGeneration();

    const state = useProjectStore.getState();
    expect(state.audioGenerationStatus['seg-1']).toEqual({ status: 'idle' });
    expect(state.audioGenerationStatus['seg-2']).toEqual({ status: 'completed' });
    expect(state.bulkGenerationProgress).toBeNull();
    expect(state.audioTaskId).toBeNull();
  });

  // ── refreshSegmentAudio ──
  it('refreshSegmentAudio fetches updated segment data', async () => {
    useProjectStore.setState({ segments: [...mockSegments] });

    const updatedSeg: Segment = {
      ...mockSegments[0],
      audio_file: '/media/audio/seg-1-new.wav',
      audio_duration: 6.0,
    };
    mockApi.getSegment.mockResolvedValue(updatedSeg);

    await useProjectStore.getState().refreshSegmentAudio('seg-1');

    const state = useProjectStore.getState();
    const seg = state.segments.find((s) => s.id === 'seg-1');
    expect(seg?.audio_file).toBe('/media/audio/seg-1-new.wav');
    expect(seg?.audio_duration).toBe(6.0);
  });

  it('refreshSegmentAudio bails out if audio data has not changed', async () => {
    useProjectStore.setState({ segments: [...mockSegments] });

    // Return same data — should not create a new segments array
    mockApi.getSegment.mockResolvedValue({ ...mockSegments[0] });

    const segsBefore = useProjectStore.getState().segments;
    await useProjectStore.getState().refreshSegmentAudio('seg-1');
    const segsAfter = useProjectStore.getState().segments;

    // Same reference = no unnecessary re-render
    expect(segsBefore).toBe(segsAfter);
  });

  // ── staleAudioSegments ──
  it('markAudioStale adds segment ID to staleAudioSegments Set', () => {
    useProjectStore.getState().markAudioStale('seg-1');

    expect(useProjectStore.getState().staleAudioSegments.has('seg-1')).toBe(true);
    expect(useProjectStore.getState().staleAudioSegments.has('seg-2')).toBe(false);
  });

  it('clearAudioStale removes segment ID from staleAudioSegments Set', () => {
    useProjectStore.getState().markAudioStale('seg-1');
    useProjectStore.getState().markAudioStale('seg-2');
    useProjectStore.getState().clearAudioStale('seg-1');

    expect(useProjectStore.getState().staleAudioSegments.has('seg-1')).toBe(false);
    expect(useProjectStore.getState().staleAudioSegments.has('seg-2')).toBe(true);
  });

  it('clearAudioStale is a no-op when segment is not stale', () => {
    const setBefore = useProjectStore.getState().staleAudioSegments;
    useProjectStore.getState().clearAudioStale('nonexistent');
    const setAfter = useProjectStore.getState().staleAudioSegments;

    // Same reference — no unnecessary state change
    expect(setBefore).toBe(setAfter);
  });

  it('updateSegment marks audio stale when text changes on segment with audio', async () => {
    useProjectStore.setState({ segments: [...mockSegments] });

    const updatedSeg = { ...mockSegments[1], text_content: 'Changed text' };
    mockApi.updateSegment.mockResolvedValue(updatedSeg);

    // seg-2 has audio_file, so changing text_content should mark it stale
    await useProjectStore.getState().updateSegment('seg-2', { text_content: 'Changed text' });

    expect(useProjectStore.getState().staleAudioSegments.has('seg-2')).toBe(true);
  });

  it('updateSegment does NOT mark stale when segment has no audio', async () => {
    useProjectStore.setState({ segments: [...mockSegments] });

    const updatedSeg = { ...mockSegments[0], text_content: 'Changed text' };
    mockApi.updateSegment.mockResolvedValue(updatedSeg);

    // seg-1 has no audio_file, so changing text should NOT mark stale
    await useProjectStore.getState().updateSegment('seg-1', { text_content: 'Changed text' });

    expect(useProjectStore.getState().staleAudioSegments.has('seg-1')).toBe(false);
  });

  it('generateAudio clears stale flag for the segment', async () => {
    useProjectStore.setState({ segments: [...mockSegments] });
    useProjectStore.getState().markAudioStale('seg-1');

    mockApi.generateSegmentAudio.mockResolvedValue({
      task_id: 'task-clear',
      segment_id: 'seg-1',
      status: 'PENDING' as const,
      message: 'Audio generation queued',
    });
    mockApi.pollTaskStatus.mockResolvedValue({
      task_id: 'task-clear',
      status: 'COMPLETED' as const,
      progress: { current: 1, total: 1, percentage: 100 },
      completed_segments: [{ segment_id: 'seg-1', audio_url: '/media/audio/seg-1.wav', duration: 3.0 }],
      errors: [],
    });
    mockApi.getSegment.mockResolvedValue({
      ...mockSegments[0],
      audio_file: '/media/audio/seg-1.wav',
      audio_duration: 3.0,
    });

    await useProjectStore.getState().generateAudio('seg-1');

    expect(useProjectStore.getState().staleAudioSegments.has('seg-1')).toBe(false);
  });

  it('reset clears staleAudioSegments', () => {
    useProjectStore.getState().markAudioStale('seg-1');
    useProjectStore.getState().markAudioStale('seg-2');

    useProjectStore.getState().reset();

    expect(useProjectStore.getState().staleAudioSegments.size).toBe(0);
  });
});
