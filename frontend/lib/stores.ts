import { create } from 'zustand';
import {
  getProject,
  getSegments,
  getSegment,
  updateSegment as apiUpdateSegment,
  deleteSegment as apiDeleteSegment,
  uploadSegmentImage,
  removeSegmentImage,
  reorderSegments as apiReorderSegments,
  generateSegmentAudio,
  generateAllAudio as apiGenerateAllAudio,
  getTaskStatus,
  pollTaskStatus,
  startRender as apiStartRender,
  getRenderStatus as apiGetRenderStatus,
} from './api';
import type {
  ProjectDetail,
  Segment,
  UpdateSegmentPayload,
  AudioGenerationState,
  BulkGenerationProgress,
  RenderStatus,
  RenderProgress,
} from './types';

interface ProjectStore {
  // State
  project: ProjectDetail | null;
  segments: Segment[];
  isLoading: boolean;
  error: string | null;

  /** Task ID for single-segment or bulk generation polling. */
  audioTaskId: string | null;

  /** Per-segment audio generation status map (segmentId → state). */
  audioGenerationStatus: Record<string, AudioGenerationState>;

  /** Bulk generation progress (null when idle). */
  bulkGenerationProgress: BulkGenerationProgress | null;

  /** Session-only Set of segment IDs whose text was edited after audio generation. */
  staleAudioSegments: Set<string>;

  // ── Render Pipeline State ──

  /** TaskManager task ID from the render endpoint. */
  renderTaskId: string | null;

  /** Current render status for the active project. */
  renderStatus: RenderStatus;

  /** Progress data during rendering. */
  renderProgress: RenderProgress | null;

  /** Backend-provided URL for the rendered video. */
  outputUrl: string | null;

  // Actions
  fetchProject: (id: string) => Promise<void>;
  updateSegment: (id: string, data: UpdateSegmentPayload) => Promise<void>;
  deleteSegment: (id: string) => Promise<void>;
  reorderSegments: (newOrder: string[]) => Promise<void>;
  uploadImage: (segmentId: string, file: File) => Promise<void>;
  removeImage: (segmentId: string) => Promise<void>;

  /** Trigger audio generation for a single segment. */
  generateAudio: (segmentId: string) => Promise<void>;

  /** Trigger audio generation for all unlocked segments. */
  generateAllAudio: () => Promise<void>;

  /** Cancel bulk audio generation polling (client-side only). */
  cancelGeneration: () => void;

  /** Refresh a single segment's data from the server. */
  refreshSegmentAudio: (segmentId: string) => Promise<void>;

  /** Update a specific segment's audio generation status. */
  setSegmentAudioStatus: (segmentId: string, status: AudioGenerationState) => void;

  /** Reset bulk generation progress to null. */
  clearBulkProgress: () => void;

  /** Mark a segment's audio as stale (text edited after audio generated). */
  markAudioStale: (segmentId: string) => void;

  /** Clear the stale audio flag for a segment. */
  clearAudioStale: (segmentId: string) => void;

  // ── Render Pipeline Actions ──

  /** Trigger video rendering via the backend. */
  startRender: () => Promise<void>;

  /** Poll render status and update progress. */
  pollRenderStatus: () => void;

  /** Reset all render-related state and cancel polling. */
  resetRenderState: () => void;

  /** Download the rendered video file. */
  downloadVideo: () => void;

  reset: () => void;
}

// Module-level variable for cancellable bulk polling
let bulkPollingTimer: ReturnType<typeof setInterval> | null = null;

// Module-level variable for cancellable render polling
let renderPollingTimer: ReturnType<typeof setTimeout> | null = null;

export const useProjectStore = create<ProjectStore>()((set, get) => ({
  project: null,
  segments: [],
  isLoading: false,
  error: null,
  audioTaskId: null,
  audioGenerationStatus: {} as Record<string, AudioGenerationState>,
  bulkGenerationProgress: null,
  staleAudioSegments: new Set<string>(),
  renderTaskId: null,
  renderStatus: 'idle' as RenderStatus,
  renderProgress: null,
  outputUrl: null,

  fetchProject: async (id) => {
    set({ isLoading: true, error: null });
    try {
      const project = await getProject(id);
      const segments = await getSegments(id);
      set({ project, segments, isLoading: false });

      // Detect render state from project status
      if (project.status === 'PROCESSING') {
        set({ renderStatus: 'rendering' as RenderStatus });
        get().pollRenderStatus();
      } else if (project.status === 'COMPLETED' && project.output_path) {
        const backendBase = process.env.NEXT_PUBLIC_API_URL?.replace('/api', '') || 'http://localhost:8000';
        set({
          renderStatus: 'completed' as RenderStatus,
          outputUrl: `/media/${project.output_path}`,
        });
      }
    } catch {
      set({ error: 'Failed to load project', isLoading: false });
    }
  },

  updateSegment: async (id, data) => {
    // If text_content is changing on a segment that has audio, mark as stale
    if ('text_content' in data) {
      const seg = get().segments.find((s) => s.id === id);
      if (seg?.audio_file) {
        get().markAudioStale(id);
      }
    }
    // Optimistic update — save previous state for rollback
    const previousSegments = get().segments;
    set((state) => ({
      segments: state.segments.map((s) =>
        s.id === id ? { ...s, ...data } : s
      ),
    }));
    try {
      const updated = await apiUpdateSegment(id, data);
      set((state) => ({
        segments: state.segments.map((s) =>
          s.id === id ? updated : s
        ),
      }));
    } catch {
      // Rollback on failure
      set({ segments: previousSegments, error: 'Failed to update segment' });
    }
  },

  deleteSegment: async (id) => {
    // Pessimistic — wait for API success
    try {
      await apiDeleteSegment(id);
      set((state) => ({
        segments: state.segments.filter((s) => s.id !== id),
      }));
    } catch {
      set({ error: 'Failed to delete segment' });
    }
  },

  reorderSegments: async (newOrder) => {
    const { project } = get();
    if (!project) return;
    try {
      await apiReorderSegments(String(project.id), newOrder);
      set((state) => ({
        segments: newOrder.map((id, index) => {
          const seg = state.segments.find((s) => s.id === id);
          return seg ? { ...seg, sequence_index: index } : seg!;
        }),
      }));
    } catch {
      set({ error: 'Failed to reorder segments' });
    }
  },

  uploadImage: async (segmentId, file) => {
    // Pessimistic — wait for response
    try {
      const result = await uploadSegmentImage(segmentId, file);
      set((state) => ({
        segments: state.segments.map((s) =>
          s.id === segmentId ? { ...s, image_file: result.image_file } : s
        ),
      }));
    } catch {
      set({ error: 'Failed to upload image' });
    }
  },

  removeImage: async (segmentId) => {
    try {
      await removeSegmentImage(segmentId);
      set((state) => ({
        segments: state.segments.map((s) =>
          s.id === segmentId ? { ...s, image_file: null } : s
        ),
      }));
    } catch {
      set({ error: 'Failed to remove image' });
    }
  },

  // ── Render Pipeline Actions ──

  startRender: async () => {
    const { project } = get();
    if (!project) return;

    set({ renderStatus: 'validating' as RenderStatus, renderProgress: null, outputUrl: null, renderTaskId: null });

    try {
      const result = await apiStartRender(project.id);
      set({
        renderStatus: 'rendering' as RenderStatus,
        renderTaskId: result.task_id,
      });

      // Begin polling for progress
      get().pollRenderStatus();
    } catch (err: unknown) {
      // Axios errors carry a response object
      const axiosErr = err as { response?: { status?: number; data?: Record<string, unknown> } };
      const status = axiosErr?.response?.status;

      if (status === 400) {
        // Validation error — set back to idle and surface error
        const errorData = axiosErr?.response?.data;
        const message = errorData?.message || errorData?.error || 'Validation failed';
        set({ renderStatus: 'idle' as RenderStatus, error: String(message) });
      } else if (status === 409) {
        // Already rendering — set to rendering and start polling
        set({ renderStatus: 'rendering' as RenderStatus });
        get().pollRenderStatus();
      } else {
        const message = err instanceof Error ? err.message : 'Failed to start render';
        set({ renderStatus: 'failed' as RenderStatus, error: message });
      }
    }
  },

  pollRenderStatus: () => {
    const { project } = get();
    if (!project) return;

    const poll = async () => {
      const { renderStatus } = get();
      if (renderStatus !== 'rendering') return;

      try {
        const status = await apiGetRenderStatus(project.id);

        if (status.status === 'COMPLETED') {
          set({
            renderStatus: 'completed' as RenderStatus,
            renderProgress: status.progress,
            outputUrl: status.output_url,
          });
          renderPollingTimer = null;
          return;
        }

        if (status.status === 'FAILED') {
          set({
            renderStatus: 'failed' as RenderStatus,
            renderProgress: status.progress,
            outputUrl: null,
          });
          renderPollingTimer = null;
          return;
        }

        // Still processing — update progress and poll again
        set({ renderProgress: status.progress });
        renderPollingTimer = setTimeout(poll, 3000);
      } catch {
        // Transient error — try again
        renderPollingTimer = setTimeout(poll, 3000);
      }
    };

    // Start polling after a short delay to let the backend begin
    renderPollingTimer = setTimeout(poll, 1000);
  },

  resetRenderState: () => {
    if (renderPollingTimer) {
      clearTimeout(renderPollingTimer);
      renderPollingTimer = null;
    }
    set({
      renderTaskId: null,
      renderStatus: 'idle' as RenderStatus,
      renderProgress: null,
      outputUrl: null,
    });
  },

  downloadVideo: () => {
    const { outputUrl } = get();
    if (!outputUrl) return;

    // Cross-origin download via fetch → blob → object URL
    const backendBase = process.env.NEXT_PUBLIC_API_URL?.replace('/api', '') || 'http://localhost:8000';
    const fullUrl = `${backendBase}${outputUrl}`;

    fetch(fullUrl)
      .then((res) => res.blob())
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'final.mp4';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      })
      .catch(() => {
        set({ error: 'Failed to download video' });
      });
  },

  reset: () => {
    if (bulkPollingTimer) {
      clearInterval(bulkPollingTimer);
      bulkPollingTimer = null;
    }
    if (renderPollingTimer) {
      clearTimeout(renderPollingTimer);
      renderPollingTimer = null;
    }
    set({
      project: null, segments: [], isLoading: false, error: null,
      audioTaskId: null,
      audioGenerationStatus: {},
      bulkGenerationProgress: null,
      staleAudioSegments: new Set<string>(),
      renderTaskId: null,
      renderStatus: 'idle' as RenderStatus,
      renderProgress: null,
      outputUrl: null,
    });
  },

  generateAudio: async (segmentId) => {
    const { setSegmentAudioStatus, refreshSegmentAudio, clearAudioStale } = get();
    // Clear any stale warning and set generating state
    clearAudioStale(segmentId);
    setSegmentAudioStatus(segmentId, { status: 'generating' as const });
    try {
      // Fire the API call (returns task_id)
      const taskResponse = await generateSegmentAudio(segmentId);
      // Store task ID and update status with taskId
      set({ audioTaskId: taskResponse.task_id });
      setSegmentAudioStatus(segmentId, { status: 'generating' as const, taskId: taskResponse.task_id });

      // Poll until completion (retry-tolerant)
      const finalStatus = await pollTaskStatus(taskResponse.task_id, () => {});

      set({ audioTaskId: null });

      if (finalStatus.status === 'COMPLETED') {
        setSegmentAudioStatus(segmentId, { status: 'completed' as const });
        await refreshSegmentAudio(segmentId);
      } else {
        // FAILED
        const errorMsg = finalStatus.errors?.length
          ? finalStatus.errors[0].error
          : 'Audio generation failed';
        setSegmentAudioStatus(segmentId, { status: 'failed' as const, error: errorMsg });
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Audio generation failed';
      set({ audioTaskId: null });
      setSegmentAudioStatus(segmentId, { status: 'failed' as const, error: message });
    }
  },

  generateAllAudio: async () => {
    const { project, setSegmentAudioStatus, refreshSegmentAudio } = get();
    if (!project) return;

    try {
      const bulkResponse = await apiGenerateAllAudio(project.id);
      // Seed initial progress state
      set({
        audioTaskId: bulkResponse.task_id,
        bulkGenerationProgress: {
          task_id: bulkResponse.task_id,
          status: bulkResponse.status,
          total: bulkResponse.segments_to_process,
          completed: 0,
          failed: 0,
          completed_segments: [],
          errors: [],
        },
      });

      // Track which segments have already been processed to avoid duplicates
      const handledSegments = new Set<string>();
      let consecutiveFailures = 0;

      // Start cancellable polling loop
      await new Promise<void>((resolve, reject) => {
        bulkPollingTimer = setInterval(async () => {
          try {
            const taskStatus = await getTaskStatus(bulkResponse.task_id);
            consecutiveFailures = 0; // Reset on successful poll

            // Process newly completed segments
            for (const seg of taskStatus.completed_segments) {
              if (!handledSegments.has(seg.segment_id)) {
                handledSegments.add(seg.segment_id);
                setSegmentAudioStatus(seg.segment_id, { status: 'completed' as const });
                refreshSegmentAudio(seg.segment_id);
              }
            }

            // Process newly failed segments
            for (const err of taskStatus.errors) {
              if (!handledSegments.has(err.segment_id)) {
                handledSegments.add(err.segment_id);
                setSegmentAudioStatus(err.segment_id, { status: 'failed' as const, error: err.error });
              }
            }

            // Update bulk progress incrementally
            set({
              bulkGenerationProgress: {
                task_id: taskStatus.task_id,
                status: taskStatus.status,
                total: taskStatus.progress.total,
                completed: taskStatus.completed_segments.length,
                failed: taskStatus.errors.length,
                completed_segments: taskStatus.completed_segments,
                errors: taskStatus.errors,
              },
            });

            if (taskStatus.status === 'COMPLETED' || taskStatus.status === 'FAILED') {
              if (bulkPollingTimer) {
                clearInterval(bulkPollingTimer);
                bulkPollingTimer = null;
              }
              set({ audioTaskId: null });

              if (taskStatus.status === 'FAILED' && taskStatus.errors.length > 0) {
                set({ error: `Bulk audio generation completed with ${taskStatus.errors.length} error(s)` });
              }
              // Clear progress after a brief delay for UI feedback
              setTimeout(() => set({ bulkGenerationProgress: null }), 3000);
              resolve();
            }
          } catch {
            consecutiveFailures++;
            if (consecutiveFailures >= 3) {
              if (bulkPollingTimer) {
                clearInterval(bulkPollingTimer);
                bulkPollingTimer = null;
              }
              set({ audioTaskId: null });
              reject(new Error('Lost connection to server'));
            }
            // Otherwise continue polling (transient failure)
          }
        }, 2000);
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Bulk audio generation failed';
      set({ error: message, bulkGenerationProgress: null, audioTaskId: null });
    }
  },

  cancelGeneration: () => {
    if (bulkPollingTimer) {
      clearInterval(bulkPollingTimer);
      bulkPollingTimer = null;
    }
    // Reset any segments still in 'generating' status back to 'idle'
    set((state) => {
      const updatedStatus = { ...state.audioGenerationStatus };
      for (const [id, s] of Object.entries(updatedStatus)) {
        if (s.status === 'generating') {
          updatedStatus[id] = { status: 'idle' };
        }
      }
      return {
        bulkGenerationProgress: null,
        audioTaskId: null,
        audioGenerationStatus: updatedStatus,
      };
    });
  },

  refreshSegmentAudio: async (segmentId) => {
    try {
      const updated = await getSegment(segmentId);
      set((state) => {
        const existing = state.segments.find((s) => s.id === segmentId);
        // Bail out if segment not found or audio data hasn't changed —
        // avoids creating a new array reference and triggering downstream re-renders.
        if (
          !existing ||
          (existing.audio_file === updated.audio_file &&
           existing.audio_duration === updated.audio_duration)
        ) {
          return {};
        }
        // Immutable update: only the matching segment object is replaced.
        // React.memo on SegmentCard ensures non-updated cards skip re-render.
        return {
          segments: state.segments.map((s) =>
            s.id === segmentId ? updated : s
          ),
        };
      });
    } catch {
      set({ error: 'Failed to refresh segment audio' });
    }
  },

  setSegmentAudioStatus: (segmentId, status) => {
    set((state) => ({
      audioGenerationStatus: {
        ...state.audioGenerationStatus,
        [segmentId]: status,
      },
    }));
  },

  markAudioStale: (segmentId) => {
    set((state) => {
      const next = new Set(state.staleAudioSegments);
      next.add(segmentId);
      return { staleAudioSegments: next };
    });
  },

  clearAudioStale: (segmentId) => {
    set((state) => {
      if (!state.staleAudioSegments.has(segmentId)) return {};
      const next = new Set(state.staleAudioSegments);
      next.delete(segmentId);
      return { staleAudioSegments: next };
    });
  },

  clearBulkProgress: () => {
    set({ bulkGenerationProgress: null });
  },
}));
