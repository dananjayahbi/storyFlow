import { create } from 'zustand';
import {
  getProject,
  getSegments,
  getSegment,
  createSegment as apiCreateSegment,
  importSegments as apiImportSegments,
  updateSegment as apiUpdateSegment,
  deleteSegment as apiDeleteSegment,
  uploadSegmentImage,
  removeSegmentImage,
  removeSegmentAudio,
  reorderSegments as apiReorderSegments,
  generateSegmentAudio,
  generateAllAudio as apiGenerateAllAudio,
  getTaskStatus,
  pollTaskStatus,
  updateProject as apiUpdateProject,
  startRender as apiStartRender,
  getRenderStatus as apiGetRenderStatus,
  cancelRender as apiCancelRender,
  getSettings as apiGetSettings,
  updateSettings as apiUpdateSettings,
  getVoices as apiGetVoices,
  uploadFont as apiUploadFont,
  getLogos as apiGetLogos,
  uploadLogo as apiUploadLogo,
  deleteLogo as apiDeleteLogo,
  getOutroVideos as apiGetOutroVideos,
  uploadOutroVideo as apiUploadOutroVideo,
  deleteOutroVideo as apiDeleteOutroVideo,
  getTtsEngines as apiGetTtsEngines,
  unloadQwenEngine as apiUnloadQwenEngine,
  getVoiceReferences as apiGetVoiceReferences,
  uploadVoiceReference as apiUploadVoiceReference,
  updateVoiceReference as apiUpdateVoiceReference,
  deleteVoiceReference as apiDeleteVoiceReference,
  getBgmClips,
  getMusicEngineStatus,
  generateBgmSoundtrack,
} from './api';
import type {
  ProjectDetail,
  Segment,
  UpdateSegmentPayload,
  AudioGenerationState,
  BulkGenerationProgress,
  RenderStatus,
  RenderProgress,
  GlobalSettings,
  Logo,
  OutroVideo,
  VoiceReference,
  TtsEngineInfo,
  GenerateAudioOptions,
  GenerateAllAudioOptions,
  BgmClip,
  MusicEngineStatus,
  TaskProgress,
} from './types';
import { type Voice, AVAILABLE_VOICES } from './constants';

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

  /** Human-readable bulk generation error (e.g. Qwen unavailable). */
  bulkError: string | null;

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
  addSegment: (data?: { text_content?: string; image_prompt?: string }) => Promise<void>;
  importSegmentsToProject: (payload: { format: 'json' | 'text'; segments?: Array<{ text_content: string; image_prompt?: string }>; raw_text?: string }) => Promise<void>;
  updateSegment: (id: string, data: UpdateSegmentPayload) => Promise<void>;
  deleteSegment: (id: string) => Promise<void>;
  reorderSegments: (newOrder: string[]) => Promise<void>;
  uploadImage: (segmentId: string, file: File) => Promise<void>;
  removeImage: (segmentId: string) => Promise<void>;
  removeAudio: (segmentId: string) => Promise<void>;

  /** Trigger audio generation for a single segment. */
  generateAudio: (segmentId: string, options?: GenerateAudioOptions) => Promise<void>;

  /** Trigger audio generation for all unlocked segments. */
  generateAllAudio: (options?: GenerateAllAudioOptions) => Promise<void>;

  /** Cancel bulk audio generation polling (client-side only). */
  cancelGeneration: () => void;

  /** Refresh a single segment's data from the server. */
  refreshSegmentAudio: (segmentId: string) => Promise<void>;

  /** Update a specific segment's audio generation status. */
  setSegmentAudioStatus: (segmentId: string, status: AudioGenerationState) => void;

  /** Reset bulk generation progress to null. */
  clearBulkProgress: () => void;

  /** Clear the bulk generation error banner. */
  clearBulkError: () => void;

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

  /** Cancel an in-progress render. */
  cancelRender: () => Promise<void>;

  /** Download the rendered video file. */
  downloadVideo: () => void;

  /** Rename the current project. */
  renameProject: (newTitle: string) => Promise<void>;

  /** Update per-project settings (optimistic). */
  updateProjectSettings: (data: Partial<ProjectDetail>) => Promise<void>;

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
  bulkError: null,
  staleAudioSegments: new Set<string>(),
  renderTaskId: null,
  renderStatus: 'idle' as RenderStatus,
  renderProgress: null,
  outputUrl: null,

  renameProject: async (newTitle) => {
    const project = get().project;
    if (!project) return;
    const updated = await apiUpdateProject(String(project.id), { title: newTitle });
    set({ project: { ...project, title: updated.title } });
  },

  updateProjectSettings: async (data) => {
    const project = get().project;
    if (!project) return;
    const previous = project;
    // Optimistic update
    set({ project: { ...project, ...data } });
    try {
      const updated = await apiUpdateProject(String(project.id), data);
      set({ project: { ...project, ...updated } });
    } catch {
      // Rollback on failure
      set({ project: previous });
      throw new Error('Failed to save project settings');
    }
  },

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
        const backendBase = process.env.NEXT_PUBLIC_API_URL?.replace('/api', '') || 'http://localhost:8765';
        set({
          renderStatus: 'completed' as RenderStatus,
          outputUrl: `/media/${project.output_path}`,
        });
      }
    } catch {
      set({ error: 'Failed to load project', isLoading: false });
    }
  },

  addSegment: async (data) => {
    const project = get().project;
    if (!project) return;
    try {
      const newSegment = await apiCreateSegment(project.id, data);
      set((state) => ({
        segments: [...state.segments, newSegment],
      }));
    } catch {
      // Let the caller handle errors via toast
      throw new Error('Failed to add segment');
    }
  },

  importSegmentsToProject: async (payload) => {
    const project = get().project;
    if (!project) return;
    try {
      const allSegments = await apiImportSegments(project.id, payload);
      set({ segments: allSegments });
    } catch {
      throw new Error('Failed to import segments');
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

  removeAudio: async (segmentId) => {
    try {
      await removeSegmentAudio(segmentId);
      set((state) => ({
        segments: state.segments.map((s) =>
          s.id === segmentId ? { ...s, audio_file: null, audio_duration: null } : s
        ),
        // Clear any audio generation status for this segment
        audioGenerationStatus: {
          ...state.audioGenerationStatus,
          [segmentId]: { status: 'idle' as const },
        },
      }));
      // Also clear the stale flag if set
      get().clearAudioStale(segmentId);
    } catch {
      set({ error: 'Failed to remove audio' });
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
        renderPollingTimer = setTimeout(poll, 2000);
      } catch {
        // Transient error — try again
        renderPollingTimer = setTimeout(poll, 2000);
      }
    };

    // Start polling quickly
    renderPollingTimer = setTimeout(poll, 500);
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

  cancelRender: async () => {
    const { project, renderStatus: rs } = get();
    if (!project) return;
    if (rs !== 'rendering' && rs !== 'validating') return;

    try {
      await apiCancelRender(project.id);
    } catch {
      // Ignore errors — we still reset locally
    }

    // Stop polling and reset
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
    const backendBase = process.env.NEXT_PUBLIC_API_URL?.replace('/api', '') || 'http://localhost:8765';
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
      bulkError: null,
      staleAudioSegments: new Set<string>(),
      renderTaskId: null,
      renderStatus: 'idle' as RenderStatus,
      renderProgress: null,
      outputUrl: null,
    });
  },

  generateAudio: async (segmentId, options = {}) => {
    const { setSegmentAudioStatus, refreshSegmentAudio, clearAudioStale } = get();
    // Clear any stale warning and set generating state
    clearAudioStale(segmentId);
    setSegmentAudioStatus(segmentId, { status: 'generating' as const });
    try {
      // Fire the API call (returns task_id)
      const taskResponse = await generateSegmentAudio(segmentId, options);
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

  generateAllAudio: async (options = {}) => {
    const { project, setSegmentAudioStatus, refreshSegmentAudio } = get();
    if (!project) return;

    set({ bulkError: null });

    try {
      const bulkResponse = await apiGenerateAllAudio(project.id, options);

      // The backend returns 200 without a task when there is nothing to do
      // (e.g. every segment already uses the requested engine).
      if (!bulkResponse.task_id) {
        set({
          audioTaskId: null,
          bulkGenerationProgress: null,
          bulkError: bulkResponse.message || 'Nothing to generate.',
        });
        return;
      }

      const taskId = bulkResponse.task_id;

      // Seed initial progress state
      set({
        audioTaskId: taskId,
        bulkGenerationProgress: {
          task_id: taskId,
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
            const taskStatus = await getTaskStatus(taskId);
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
                set({
                  bulkError: `Bulk audio generation completed with ${taskStatus.errors.length} error(s)`,
                });
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
      const axiosErr = err as {
        response?: { data?: { error?: string; message?: string } };
      };
      const message =
        axiosErr?.response?.data?.error ||
        axiosErr?.response?.data?.message ||
        (err instanceof Error ? err.message : 'Bulk audio generation failed');
      set({
        bulkError: message,
        bulkGenerationProgress: null,
        audioTaskId: null,
      });
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

  clearBulkError: () => {
    set({ bulkError: null });
  },
}));

// ===================================================================
// Settings Store (Task 05.03.01 + 05.03.02 + 05.03.03)
// ===================================================================

interface SettingsStore {
  /** Current global settings (null until fetched). */
  globalSettings: GlobalSettings | null;

  /** True while the initial GET is in-flight. */
  isSettingsLoading: boolean;

  /** Error message if fetch or update failed. */
  settingsError: string | null;

  /** Fetch settings from GET /api/settings/. */
  fetchSettings: () => Promise<void>;

  /** Partial-update settings via PATCH /api/settings/. */
  updateSettings: (data: Partial<GlobalSettings>) => Promise<void>;

  /** List of available Kokoro TTS voices. */
  availableVoices: Voice[];

  /** True while the voices list is being fetched. */
  isVoicesLoading: boolean;

  /** Fetch voices from GET /api/settings/voices/, falls back to hardcoded list. */
  fetchVoices: () => Promise<void>;

  /** True while a font file is being uploaded. */
  isFontUploading: boolean;

  /** Upload a custom subtitle font via POST /api/settings/font/upload/. */
  uploadFont: (file: File) => Promise<void>;

  /** List of uploaded logos. */
  logos: Logo[];

  /** True while logos are loading. */
  isLogosLoading: boolean;

  /** True while a logo is being uploaded. */
  isLogoUploading: boolean;

  /** Fetch all uploaded logos. */
  fetchLogos: () => Promise<void>;

  /** Upload a new logo file. */
  uploadLogo: (file: File) => Promise<Logo>;

  /** Delete a logo by ID. */
  deleteLogo: (logoId: string) => Promise<void>;

  /** List of uploaded outro videos. */
  outroVideos: OutroVideo[];

  /** True while outro videos are loading. */
  isOutrosLoading: boolean;

  /** True while an outro video is being uploaded. */
  isOutroUploading: boolean;

  /** Fetch all uploaded outro videos. */
  fetchOutroVideos: () => Promise<void>;

  /** Upload a new outro video file. */
  uploadOutroVideo: (file: File) => Promise<OutroVideo>;

  /** Delete an outro video by ID. */
  deleteOutroVideo: (outroId: string) => Promise<void>;

  // ── TTS engines + Qwen voice references ──

  /** Capability/status of Kokoro and Qwen. */
  ttsEngines: TtsEngineInfo[];

  /** True while engine status is loading. */
  isTtsEnginesLoading: boolean;

  /** Fetch engine capabilities from GET /api/settings/tts-engines/. */
  fetchTtsEngines: () => Promise<void>;

  /** Unload the Qwen checkpoint (frees VRAM). */
  unloadQwen: () => Promise<string>;

  /** Uploaded reference clips for Qwen voice cloning. */
  voiceReferences: VoiceReference[];

  /** True while references are loading. */
  isVoiceReferencesLoading: boolean;

  /** True while a reference clip is uploading. */
  isVoiceReferenceUploading: boolean;

  /** Fetch all voice references. */
  fetchVoiceReferences: () => Promise<void>;

  /** Upload a reference clip (optionally with a name/transcript). */
  uploadVoiceReference: (file: File, name?: string, transcript?: string) => Promise<VoiceReference>;

  /** Rename/retranscribe a reference clip. */
  updateVoiceReference: (id: string, data: { name?: string; transcript?: string }) => Promise<void>;

  /** Delete a reference clip. */
  deleteVoiceReference: (id: string) => Promise<void>;
}

export const useSettingsStore = create<SettingsStore>()((set, get) => ({
  globalSettings: null,
  isSettingsLoading: false,
  settingsError: null,
  availableVoices: [],
  isVoicesLoading: false,
  isFontUploading: false,
  logos: [],
  isLogosLoading: false,
  isLogoUploading: false,
  outroVideos: [],
  isOutrosLoading: false,
  isOutroUploading: false,
  ttsEngines: [],
  isTtsEnginesLoading: false,
  voiceReferences: [],
  isVoiceReferencesLoading: false,
  isVoiceReferenceUploading: false,

  fetchSettings: async () => {
    set({ isSettingsLoading: true, settingsError: null });
    try {
      const settings = await apiGetSettings();
      set({ globalSettings: settings, isSettingsLoading: false });
    } catch {
      set({
        settingsError: 'Failed to load settings',
        isSettingsLoading: false,
      });
    }
  },

  updateSettings: async (data) => {
    const previous = get().globalSettings;

    // Optimistic update
    if (previous) {
      set({ globalSettings: { ...previous, ...data } });
    }

    try {
      const updated = await apiUpdateSettings(data);
      set({ globalSettings: updated, settingsError: null });
    } catch {
      // Rollback on failure
      set({
        globalSettings: previous,
        settingsError: 'Failed to save settings',
      });
      throw new Error('Failed to save settings');
    }
  },

  fetchVoices: async () => {
    set({ isVoicesLoading: true });
    try {
      const voices = await apiGetVoices();
      set({ availableVoices: voices, isVoicesLoading: false });
    } catch {
      // Fall back to hardcoded list on API failure
      console.warn(
        '[useSettingsStore] Failed to fetch voices from API — using fallback list'
      );
      set({ availableVoices: AVAILABLE_VOICES, isVoicesLoading: false });
    }
  },

  uploadFont: async (file) => {
    set({ isFontUploading: true });
    try {
      const result = await apiUploadFont(file);
      // Update the globalSettings with the new font path
      const prev = get().globalSettings;
      if (prev) {
        set({
          globalSettings: { ...prev, subtitle_font: result.subtitle_font },
          isFontUploading: false,
        });
      } else {
        set({ isFontUploading: false });
      }
    } catch {
      set({ isFontUploading: false });
      throw new Error('Failed to upload font');
    }
  },

  fetchLogos: async () => {
    set({ isLogosLoading: true });
    try {
      const logos = await apiGetLogos();
      set({ logos, isLogosLoading: false });
    } catch {
      set({ isLogosLoading: false });
    }
  },

  uploadLogo: async (file) => {
    set({ isLogoUploading: true });
    try {
      const logo = await apiUploadLogo(file);
      set((state) => ({
        logos: [logo, ...state.logos],
        isLogoUploading: false,
      }));
      return logo;
    } catch {
      set({ isLogoUploading: false });
      throw new Error('Failed to upload logo');
    }
  },

  deleteLogo: async (logoId) => {
    try {
      await apiDeleteLogo(logoId);
      set((state) => ({
        logos: state.logos.filter((l) => l.id !== logoId),
      }));
      // If this was the active logo, disable it
      const gs = get().globalSettings;
      if (gs && gs.active_logo === logoId) {
        set({
          globalSettings: { ...gs, active_logo: null, logo_enabled: false },
        });
      }
    } catch {
      throw new Error('Failed to delete logo');
    }
  },

  fetchOutroVideos: async () => {
    set({ isOutrosLoading: true });
    try {
      const outroVideos = await apiGetOutroVideos();
      set({ outroVideos, isOutrosLoading: false });
    } catch {
      set({ isOutrosLoading: false });
    }
  },

  uploadOutroVideo: async (file) => {
    set({ isOutroUploading: true });
    try {
      const outro = await apiUploadOutroVideo(file);
      set((state) => ({
        outroVideos: [outro, ...state.outroVideos],
        isOutroUploading: false,
      }));
      return outro;
    } catch {
      set({ isOutroUploading: false });
      throw new Error('Failed to upload outro video');
    }
  },

  deleteOutroVideo: async (outroId) => {
    try {
      await apiDeleteOutroVideo(outroId);
      set((state) => ({
        outroVideos: state.outroVideos.filter((o) => o.id !== outroId),
      }));
      // If this was the active outro, disable it
      const gs = get().globalSettings;
      if (gs && gs.active_outro === outroId) {
        set({
          globalSettings: { ...gs, active_outro: null, outro_enabled: false },
        });
      }
    } catch {
      throw new Error('Failed to delete outro video');
    }
  },

  // ── TTS engines ──

  fetchTtsEngines: async () => {
    set({ isTtsEnginesLoading: true });
    try {
      const response = await apiGetTtsEngines();
      set({ ttsEngines: response.engines, isTtsEnginesLoading: false });
    } catch {
      set({ isTtsEnginesLoading: false });
    }
  },

  unloadQwen: async () => {
    const result = await apiUnloadQwenEngine();
    if (!result.ok) throw new Error(result.message || 'Could not unload Qwen');
    return result.message || 'Qwen unloaded — VRAM freed.';
  },

  // ── Voice references ──

  fetchVoiceReferences: async () => {
    set({ isVoiceReferencesLoading: true });
    try {
      const voiceReferences = await apiGetVoiceReferences();
      set({ voiceReferences, isVoiceReferencesLoading: false });
    } catch {
      set({ isVoiceReferencesLoading: false });
    }
  },

  uploadVoiceReference: async (file, name, transcript) => {
    set({ isVoiceReferenceUploading: true });
    try {
      const reference = await apiUploadVoiceReference(file, name, transcript);
      set((state) => ({
        voiceReferences: [reference, ...state.voiceReferences],
        isVoiceReferenceUploading: false,
      }));
      return reference;
    } catch {
      set({ isVoiceReferenceUploading: false });
      throw new Error('Failed to upload voice reference');
    }
  },

  updateVoiceReference: async (id, data) => {
    const updated = await apiUpdateVoiceReference(id, data);
    set((state) => ({
      voiceReferences: state.voiceReferences.map((ref) =>
        ref.id === id ? updated : ref
      ),
    }));
  },

  deleteVoiceReference: async (id) => {
    await apiDeleteVoiceReference(id);
    set((state) => ({
      voiceReferences: state.voiceReferences.filter((ref) => ref.id !== id),
    }));

    // Detach from global settings if it was active
    const gs = get().globalSettings;
    if (gs && gs.active_voice_reference === id) {
      set({ globalSettings: { ...gs, active_voice_reference: null } });
    }
  },
}));

// ── Background music (library + MusicGen generation) ─────────────────────

interface BgmStore {
  projectId: string | null;
  clips: BgmClip[];
  clipsLoaded: boolean;
  engine: MusicEngineStatus | null;
  engineLoaded: boolean;
  generating: boolean;
  progress: TaskProgress | null;
  message: string | null;
  error: string | null;
  lastClipId: string | null;
  ensureLoaded: (projectId: string) => Promise<void>;
  refreshClips: () => Promise<void>;
  refreshEngine: () => Promise<void>;
  generate: (
    projectId: string,
    title: string
  ) => Promise<{ ok: boolean; clipId?: string | null; error?: string }>;
  setActiveTrack: (clipId: string | null) => Promise<void>;
  reset: () => void;
}

const initialBgmState = {
  projectId: null as string | null,
  clips: [] as BgmClip[],
  clipsLoaded: false,
  engine: null as MusicEngineStatus | null,
  engineLoaded: false,
  generating: false,
  progress: null as TaskProgress | null,
  message: null as string | null,
  error: null as string | null,
  lastClipId: null as string | null,
};

export const useBgmStore = create<BgmStore>()((set, get) => ({
  ...initialBgmState,

  ensureLoaded: async (projectId) => {
    if (get().projectId !== projectId) {
      set({ ...initialBgmState, projectId });
    }
    const pending: Promise<void>[] = [];
    if (!get().clipsLoaded) pending.push(get().refreshClips());
    if (!get().engineLoaded) pending.push(get().refreshEngine());
    await Promise.all(pending);
  },

  refreshClips: async () => {
    try {
      const clips = await getBgmClips();
      set({ clips, clipsLoaded: true });
    } catch {
      set({ clipsLoaded: true });
    }
  },

  refreshEngine: async () => {
    try {
      const engine = await getMusicEngineStatus();
      set({ engine, engineLoaded: true });
    } catch {
      set({ engine: null, engineLoaded: true });
    }
  },

  generate: async (projectId, title) => {
    if (get().generating) {
      return { ok: false, error: 'A soundtrack is already being generated.' };
    }

    const queued: TaskProgress = {
      current: 0,
      total: 0,
      percentage: 0,
      description: 'Queuing MusicGen…',
    };
    set({
      generating: true,
      error: null,
      message: queued.description,
      progress: queued,
      lastClipId: null,
    });

    try {
      const response = await generateBgmSoundtrack({
        project: projectId,
        name: title,
      });
      const finalStatus = await pollTaskStatus(response.task_id, (status) => {
        set({
          progress: status.progress,
          message: status.progress?.description || 'Generating music…',
        });
      });

      if (finalStatus.status === 'COMPLETED') {
        const clipId = finalStatus.progress?.generated_clip_id ?? null;
        set({
          generating: false,
          message: null,
          error: null,
          lastClipId: clipId,
          progress: {
            ...finalStatus.progress,
            percentage: 100,
            description: 'Soundtrack ready',
          },
        });
        await get().refreshClips();
        await useProjectStore.getState().fetchProject(projectId);
        return { ok: true, clipId };
      }

      const detail =
        finalStatus.errors?.[0]?.error || 'Music generation failed';
      set({ generating: false, error: detail, message: detail });
      return { ok: false, error: detail };
    } catch (err) {
      const detail =
        (err as { response?: { data?: { error?: string } } })?.response?.data
          ?.error || 'Music generation failed';
      set({ generating: false, error: detail, message: detail });
      return { ok: false, error: detail };
    }
  },

  setActiveTrack: async (clipId) => {
    await useProjectStore
      .getState()
      .updateProjectSettings({ active_bgm: clipId });
  },

  reset: () => set({ ...initialBgmState }),
}));
