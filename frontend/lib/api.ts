import axios from 'axios';
import {
  Account,
  Project,
  ProjectDetail,
  ProjectRenderReadiness,
  Segment,
  CreateProjectPayload,
  ImportProjectRequest,
  UpdateSegmentPayload,
  PaginatedResponse,
  TaskResponse,
  BulkTaskResponse,
  GenerateAllAudioOptions,
  TaskStatusResponse,
  GlobalSettings,
  ProjectSettingsProfile,
  GalleryItem,
  RenderingStatus,
  Logo,
  OutroVideo,
  VoiceReference,
  TtsEnginesResponse,
  GenerateAudioOptions,
  Script,
  ScriptContent,
  ScriptGenerateResponse,
  ScriptChatMessage,
  AIConfig,
  ChatSession,
  ChatCompactResponse,
  BgmClip,
  MusicEngineStatus,
  GenerateSoundtrackPayload,
  GenerateSoundtrackResponse,
  PlaygroundState,
} from './types';
import { Voice } from './constants';
import { getCurrentSection, type Section } from './section';
import { getCurrentAccountId } from './account';
import { ensureApiBaseUrl, getApiBaseUrl } from './apiConfig';

const api = axios.create({
  baseURL: getApiBaseUrl(),
});

// Every request is scoped to the workspace encoded in the current URL.
// This prevents the Facebook side from ever listing or mutating YouTube data
// (and vice versa) even if a component forgets to pass the section.
api.interceptors.request.use(async (config) => {
  // Resolve the backend origin once (configurable via NEXT_PUBLIC_API_URL,
  // otherwise auto-discovered from /api/health/).  This keeps every page —
  // including accounts — pointed at the server that is actually running.
  config.baseURL = await ensureApiBaseUrl();
  const section = getCurrentSection();
  config.params = { ...(config.params ?? {}) };
  if (!config.params.section) {
    config.params.section = section;
  }

  // Account isolation: when an account is selected, every request carries it
  // so projects, segments, gallery items and uploads stay inside that account.
  const account = getCurrentAccountId(section);
  if (account && !config.params.account) {
    config.params.account = account;
  }
  return config;
});

// ── Accounts ──

export async function getAccounts(
  section?: Section
): Promise<PaginatedResponse<Account>> {
  const response = await api.get<PaginatedResponse<Account>>('/api/accounts/', {
    params: section ? { section } : undefined,
  });
  return response.data;
}

export interface AccountPayload {
  name: string;
  section?: Section;
  description?: string;
}

export async function createAccount(payload: AccountPayload): Promise<Account> {
  const response = await api.post<Account>('/api/accounts/', payload);
  return response.data;
}

export async function updateAccount(
  id: string,
  data: Partial<AccountPayload>
): Promise<Account> {
  const response = await api.patch<Account>(`/api/accounts/${id}/`, data);
  return response.data;
}

export async function deleteAccount(id: string): Promise<void> {
  await api.delete(`/api/accounts/${id}/`);
}

export async function getProjects(section?: Section): Promise<PaginatedResponse<Project>> {
  const response = await api.get<PaginatedResponse<Project>>('/api/projects/', {
    params: section ? { section } : undefined,
  });
  return response.data;
}

export async function getProject(id: string): Promise<ProjectDetail> {
  const response = await api.get<ProjectDetail>(`/api/projects/${id}/`);
  return response.data;
}

/**
 * Bulk Create preflight. Runs the backend's real render validation for every
 * project in the selected account, including checking asset files on disk.
 */
export async function getProjectRenderReadiness(
  section?: Section,
): Promise<ProjectRenderReadiness[]> {
  const response = await api.get<{ results: ProjectRenderReadiness[] }>(
    '/api/projects/render-readiness/',
    { params: section ? { section } : undefined },
  );
  return response.data.results;
}

export async function createProject(payload: CreateProjectPayload): Promise<Project> {
  const response = await api.post<Project>('/api/projects/', payload);
  return response.data;
}

export async function updateProject(
  id: string,
  data: Partial<Omit<ProjectDetail, 'id' | 'created_at' | 'updated_at' | 'segments' | 'custom_font_file'>>,
): Promise<ProjectDetail> {
  const response = await api.patch<ProjectDetail>(`/api/projects/${id}/`, data);
  return response.data;
}

/** Upload a manual cover image for a project (multipart PATCH). */
export async function uploadProjectThumbnail(
  id: string,
  file: File,
): Promise<ProjectDetail> {
  const formData = new FormData();
  formData.append('thumbnail', file);
  const { data } = await api.patch<ProjectDetail>(
    `/api/projects/${id}/`,
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } },
  );
  return data;
}

/** Remove the manual cover; the first segment image becomes the thumbnail. */
export async function removeProjectThumbnail(
  id: string,
): Promise<ProjectDetail> {
  const { data } = await api.patch<ProjectDetail>(`/api/projects/${id}/`, {
    thumbnail: null,
  });
  return data;
}

export async function importProject(payload: ImportProjectRequest): Promise<ProjectDetail> {
  const response = await api.post<ProjectDetail>('/api/projects/import/', payload);
  return response.data;
}

export async function importSegments(
  projectId: string,
  payload: { format: 'json' | 'text'; segments?: Array<{ text_content: string; image_prompt?: string }>; raw_text?: string }
): Promise<Segment[]> {
  const response = await api.post<Segment[]>(`/api/projects/${projectId}/import-segments/`, payload);
  return response.data;
}

export async function getSegments(projectId: string): Promise<Segment[]> {
  const response = await api.get<PaginatedResponse<Segment>>(`/api/segments/?project=${projectId}`);
  return response.data.results;
}

export async function createSegment(
  projectId: string,
  data: { text_content?: string; image_prompt?: string } = {}
): Promise<Segment> {
  const response = await api.post<Segment>('/api/segments/', {
    project: projectId,
    ...data,
  });
  return response.data;
}

export async function getSegment(id: string): Promise<Segment> {
  const response = await api.get<Segment>(`/api/segments/${id}/`);
  return response.data;
}

export async function updateSegment(
  id: string,
  data: UpdateSegmentPayload
): Promise<Segment> {
  const response = await api.patch<Segment>(`/api/segments/${id}/`, data);
  return response.data;
}

export async function deleteSegment(id: string): Promise<void> {
  await api.delete(`/api/segments/${id}/`);
}

export async function uploadSegmentImage(
  id: string,
  file: File
): Promise<{ id: string; image_file: string; message: string }> {
  const formData = new FormData();
  formData.append('image', file);
  const response = await api.post(`/api/segments/${id}/upload-image/`, formData);
  return response.data;
}

export async function removeSegmentImage(
  id: string
): Promise<{ id: string; image_file: null; message: string }> {
  const response = await api.delete(`/api/segments/${id}/remove-image/`);
  return response.data;
}

export async function removeSegmentAudio(
  id: string
): Promise<{ id: string; audio_file: null; audio_duration: null; message: string }> {
  const response = await api.delete(`/api/segments/${id}/remove-audio/`);
  return response.data;
}

export async function reorderSegments(
  projectId: string,
  segmentOrder: string[]
): Promise<void> {
  await api.post('/api/segments/reorder/', {
    project_id: projectId,
    segment_order: segmentOrder,
  });
}

export async function deleteProject(id: string): Promise<void> {
  await api.delete(`/api/projects/${id}/`);
}

// ── Audio Generation & Task Tracking ──

export async function generateSegmentAudio(
  segmentId: string,
  options: GenerateAudioOptions = {}
): Promise<TaskResponse> {
  const response = await api.post<TaskResponse>(
    `/api/segments/${segmentId}/generate-audio/`,
    options
  );
  return response.data;
}

export async function generateAllAudio(
  projectId: string,
  options: GenerateAllAudioOptions = {}
): Promise<BulkTaskResponse> {
  const body = {
    skip_locked: options.skip_locked ?? true,
    force_regenerate: options.force_regenerate ?? false,
    ...(options.engine ? { engine: options.engine } : {}),
    ...(options.voice_reference_id
      ? { voice_reference_id: options.voice_reference_id }
      : {}),
  };
  const response = await api.post<BulkTaskResponse>(
    `/api/projects/${projectId}/generate-all-audio/`,
    body
  );
  return response.data;
}

export async function getTaskStatus(
  taskId: string
): Promise<TaskStatusResponse> {
  const response = await api.get<TaskStatusResponse>(
    `/api/tasks/${taskId}/status/`
  );
  return response.data;
}

export async function pollTaskStatus(
  taskId: string,
  onProgress: (status: TaskStatusResponse) => void,
  intervalMs: number = 2000,
  maxRetries: number = 3
): Promise<TaskStatusResponse> {
  return new Promise<TaskStatusResponse>((resolve, reject) => {
    let consecutiveFailures = 0;
    const timer = setInterval(async () => {
      try {
        const taskStatus = await getTaskStatus(taskId);
        consecutiveFailures = 0; // Reset on successful poll
        onProgress(taskStatus);

        if (
          taskStatus.status === 'COMPLETED' ||
          taskStatus.status === 'FAILED'
        ) {
          clearInterval(timer);
          resolve(taskStatus);
        }
      } catch {
        consecutiveFailures++;
        if (consecutiveFailures >= maxRetries) {
          clearInterval(timer);
          reject(new Error('Lost connection to server'));
        }
        // Otherwise continue polling (transient failure)
      }
    }, intervalMs);
  });
}

// ── Render Pipeline ──

export async function startRender(
  projectId: string
): Promise<{ task_id: string; project_id: string; status: string; total_segments: number; message: string }> {
  const { data } = await api.post(`/api/projects/${projectId}/render/`);
  return data;
}

export async function getRenderStatus(
  projectId: string
): Promise<import('./types').RenderStatusResponse> {
  const { data } = await api.get(`/api/projects/${projectId}/status/`);
  return data;
}

export async function cancelRender(
  projectId: string
): Promise<{ project_id: string; status: string; message: string }> {
  const { data } = await api.post(`/api/projects/${projectId}/cancel-render/`);
  return data;
}

// ── Global Settings ──

export async function getSettings(): Promise<GlobalSettings> {
  const { data } = await api.get<GlobalSettings>('/api/settings/');
  return data;
}

export async function updateSettings(
  data: Partial<GlobalSettings>
): Promise<GlobalSettings> {
  const response = await api.patch<GlobalSettings>('/api/settings/', data);
  return response.data;
}

// ── Resolution-specific project defaults ──

export async function getProjectSettingsDefaults(): Promise<ProjectSettingsProfile[]> {
  const { data } = await api.get<{ results: ProjectSettingsProfile[] }>(
    '/api/settings/project-defaults/'
  );
  return data.results;
}

export async function updateProjectSettingsDefault(
  width: number,
  height: number,
  payload: Partial<ProjectSettingsProfile>,
): Promise<ProjectSettingsProfile> {
  const { data } = await api.patch<ProjectSettingsProfile>(
    `/api/settings/project-defaults/${width}x${height}/`,
    payload,
  );
  return data;
}

export async function resetProjectSettingsDefault(
  width: number,
  height: number,
): Promise<ProjectSettingsProfile> {
  const { data } = await api.delete<ProjectSettingsProfile>(
    `/api/settings/project-defaults/${width}x${height}/`,
  );
  return data;
}

/** Re-apply this project's resolution defaults without touching others. */
export async function resetProjectSettings(id: string): Promise<ProjectDetail> {
  const { data } = await api.post<ProjectDetail>(
    `/api/projects/${id}/reset-settings/`,
  );
  return data;
}

// ── Available Voices (Task 05.03.02) ──

export async function getVoices(): Promise<Voice[]> {
  const { data } = await api.get<Voice[]>('/api/settings/voices/');
  return data;
}

// ── TTS engines (Kokoro default + optional Qwen GPU) ──

export async function getTtsEngines(): Promise<TtsEnginesResponse> {
  const { data } = await api.get<TtsEnginesResponse>('/api/settings/tts-engines/');
  return data;
}

export async function unloadQwenEngine(): Promise<{ ok: boolean; message?: string }> {
  const { data } = await api.post('/api/settings/tts-engines/qwen/unload/');
  return data;
}

// ── Voice references (Qwen cloning) ──

export async function getVoiceReferences(): Promise<VoiceReference[]> {
  const { data } = await api.get<VoiceReference[]>('/api/settings/voice-references/');
  return data;
}

export async function uploadVoiceReference(
  file: File,
  name?: string,
  transcript?: string
): Promise<VoiceReference> {
  const formData = new FormData();
  formData.append('file', file);
  if (name) formData.append('name', name);
  if (transcript) formData.append('transcript', transcript);
  const { data } = await api.post<VoiceReference>(
    '/api/settings/voice-references/',
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } }
  );
  return data;
}

export async function updateVoiceReference(
  id: string,
  data: { name?: string; transcript?: string }
): Promise<VoiceReference> {
  const response = await api.patch<VoiceReference>(
    `/api/settings/voice-references/${id}/`,
    data
  );
  return response.data;
}

export async function deleteVoiceReference(id: string): Promise<void> {
  await api.delete(`/api/settings/voice-references/${id}/`);
}

// ── Font Upload (Task 05.03.03) ──

export async function uploadFont(
  file: File
): Promise<{ subtitle_font: string; message: string }> {
  const formData = new FormData();
  formData.append('font', file);
  const { data } = await api.post('/api/settings/font/upload/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

// ── TTS Test ──

export interface TestTTSOptions {
  voice?: string;
  speed?: number;
  engine?: 'kokoro' | 'qwen';
  mode?: 'custom_voice' | 'clone';
  speaker?: string;
  language?: string;
  instruct?: string;
  max_new_tokens?: number;
  voice_reference_id?: string | null;
  x_vector_only?: boolean;
}

export async function testTTS(
  text: string,
  options: TestTTSOptions = {}
): Promise<Blob> {
  const response = await api.post(
    '/api/settings/tts-test/',
    { text, ...options },
    { responseType: 'blob' }
  );
  return response.data;
}

// ── Script Craft & Script Library ──

export async function generateScript(
  pitch: string,
  history: ScriptChatMessage[] = []
): Promise<ScriptGenerateResponse> {
  const { data } = await api.post<ScriptGenerateResponse>(
    '/api/script-craft/generate/',
    { pitch, history }
  );
  return data;
}

export async function getScripts(): Promise<Script[]> {
  const { data } = await api.get<PaginatedResponse<Script> | Script[]>(
    '/api/scripts/'
  );
  return Array.isArray(data) ? data : data.results;
}

export async function saveScript(payload: {
  title: string;
  pitch?: string;
  content: ScriptContent;
  model_used?: string;
}): Promise<Script> {
  const { data } = await api.post<Script>('/api/scripts/', payload);
  return data;
}

export async function updateScript(
  id: string,
  payload: Partial<Pick<Script, 'title' | 'pitch' | 'content'>>
): Promise<Script> {
  const { data } = await api.patch<Script>(`/api/scripts/${id}/`, payload);
  return data;
}

export async function deleteScript(id: string): Promise<void> {
  await api.delete(`/api/scripts/${id}/`);
}

// ── Script Craft AI configuration ──

export async function getAIConfig(): Promise<AIConfig> {
  const { data } = await api.get<AIConfig>('/api/settings/ai/');
  return data;
}

export async function updateAIConfig(
  payload: Partial<AIConfig>
): Promise<AIConfig> {
  const { data } = await api.patch<AIConfig>('/api/settings/ai/', payload);
  return data;
}

// ── Script Craft chat sessions ──

export async function getChatSessions(): Promise<ChatSession[]> {
  const { data } = await api.get<{ results: ChatSession[] } | ChatSession[]>(
    '/api/chat/sessions/'
  );
  return Array.isArray(data) ? data : data.results;
}

export async function createChatSession(
  title = ''
): Promise<ChatSession> {
  const { data } = await api.post<ChatSession>('/api/chat/sessions/', {
    title,
  });
  return data;
}

export async function getChatSession(id: string): Promise<ChatSession> {
  const { data } = await api.get<ChatSession>(`/api/chat/sessions/${id}/`);
  return data;
}

export async function updateChatSession(
  id: string,
  payload: { title?: string }
): Promise<ChatSession> {
  const { data } = await api.patch<ChatSession>(
    `/api/chat/sessions/${id}/`,
    payload
  );
  return data;
}

export async function deleteChatSession(id: string): Promise<void> {
  await api.delete(`/api/chat/sessions/${id}/`);
}

export async function steerChatSession(
  id: string,
  message: string
): Promise<{ ok: boolean; pending_steer: string }> {
  const { data } = await api.post<{ ok: boolean; pending_steer: string }>(
    `/api/chat/sessions/${id}/steer/`,
    { message }
  );
  return data;
}

export async function stopChatSession(
  id: string
): Promise<{ ok: boolean; stop_requested: boolean }> {
  const { data } = await api.post<{ ok: boolean; stop_requested: boolean }>(
    `/api/chat/sessions/${id}/stop/`
  );
  return data;
}

export async function compactChatSession(
  id: string
): Promise<ChatCompactResponse> {
  const { data } = await api.post<ChatCompactResponse>(
    `/api/chat/sessions/${id}/compact/`
  );
  return data;
}

// ── BGM Library ──

export async function getBgmClips(): Promise<BgmClip[]> {
  const { data } = await api.get<PaginatedResponse<BgmClip> | BgmClip[]>(
    '/api/bgm/'
  );
  return Array.isArray(data) ? data : data.results;
}

export async function uploadBgmClip(
  file: File,
  options: { name?: string; isShared?: boolean } = {}
): Promise<BgmClip> {
  const formData = new FormData();
  formData.append('file', file);
  if (options.name) formData.append('name', options.name);
  formData.append('is_shared', options.isShared ? 'true' : 'false');
  const { data } = await api.post<BgmClip>('/api/bgm/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export async function updateBgmClip(
  id: string,
  payload: { name?: string; is_shared?: boolean }
): Promise<BgmClip> {
  const { data } = await api.patch<BgmClip>(`/api/bgm/${id}/`, payload);
  return data;
}

export async function deleteBgmClip(id: string): Promise<void> {
  await api.delete(`/api/bgm/${id}/`);
}

export async function getMusicEngineStatus(): Promise<MusicEngineStatus> {
  const { data } = await api.get<MusicEngineStatus>('/api/bgm/engine-status/');
  return data;
}

export async function generateBgmSoundtrack(
  payload: GenerateSoundtrackPayload
): Promise<GenerateSoundtrackResponse> {
  const { data } = await api.post<GenerateSoundtrackResponse>(
    '/api/bgm/generate/',
    payload
  );
  return data;
}

// ── Audio Mix playground (Settings page) ──

export async function getPlayground(): Promise<PlaygroundState> {
  const { data } = await api.get<PlaygroundState>('/api/settings/playground/');
  return data;
}

export async function savePlayground(payload: {
  blocks: { text_content: string }[];
  bgm_clip?: string | null;
}): Promise<PlaygroundState> {
  const { data } = await api.put<PlaygroundState>(
    '/api/settings/playground/',
    payload
  );
  return data;
}

export async function uploadPlaygroundImage(
  index: number,
  file: File
): Promise<{ index: number; image_url: string }> {
  const formData = new FormData();
  formData.append('image', file);
  const { data } = await api.post(
    `/api/settings/playground/blocks/${index}/image/`,
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } }
  );
  return data;
}

export async function removePlaygroundImage(
  index: number
): Promise<{ index: number; image_url: null }> {
  const { data } = await api.delete(
    `/api/settings/playground/blocks/${index}/image/`
  );
  return data;
}

export async function generatePlayground(payload: {
  bgm_clip?: string | null;
  music_source?: 'generated' | 'library' | 'none';
  regenerate_music?: boolean;
} = {}): Promise<{
  task_id: string;
  project_id: string;
  status: string;
  message: string;
}> {
  const { data } = await api.post('/api/settings/playground/generate/', payload);
  return data;
}

export async function applyPlaygroundBgm(payload: {
  bgm_clip?: string | null;
  music_source?: 'generated' | 'library' | 'none';
  regenerate_music?: boolean;
} = {}): Promise<{
  task_id: string;
  project_id: string;
  status: string;
  music_source?: 'generated' | 'library' | 'none';
  generate_music?: boolean;
  message: string;
}> {
  const { data } = await api.post('/api/settings/playground/apply/', payload);
  return data;
}

export async function cancelPlayground(): Promise<PlaygroundState & { message: string }> {
  const { data } = await api.post<PlaygroundState & { message: string }>(
    '/api/settings/playground/cancel/'
  );
  return data;
}

// ── Gallery ──

export interface GalleryQuery {
  /** Only assets linked to this project. */
  project?: string;
  /** One or more publishing statuses. */
  status?: RenderingStatus[];
  /** Search in asset/project title. */
  q?: string;
  sort?: 'newest' | 'oldest';
}

export async function getGalleryItems(
  section?: Section,
  query: GalleryQuery = {},
): Promise<GalleryItem[]> {
  const { data } = await api.get<GalleryItem[]>('/api/gallery/', {
    params: {
      ...(section ? { section } : {}),
      ...(query.project ? { project: query.project } : {}),
      ...(query.status?.length ? { status: query.status.join(',') } : {}),
      ...(query.q ? { q: query.q } : {}),
      ...(query.sort ? { sort: query.sort } : {}),
    },
  });
  return data;
}

export async function updateGalleryItemStatus(
  id: string,
  status: RenderingStatus,
): Promise<GalleryItem> {
  const { data } = await api.patch<GalleryItem>(`/api/gallery/${id}/`, {
    status,
  });
  return data;
}

export async function bulkUpdateGalleryStatus(
  ids: string[],
  status: RenderingStatus,
): Promise<{ updated: number; status: RenderingStatus; ids: string[] }> {
  const { data } = await api.post('/api/gallery/bulk-status/', { ids, status });
  return data;
}

export async function deleteGalleryItem(id: string): Promise<void> {
  await api.delete(`/api/gallery/${id}/`);
}

export async function bulkDeleteGalleryItems(
  ids: string[],
): Promise<{ deleted: number; ids: string[] }> {
  const { data } = await api.post('/api/gallery/bulk-delete/', { ids });
  return data;
}

export function getStreamUrl(
  renderingId: string,
  section: Section = getCurrentSection(),
): string {
  const base = getApiBaseUrl();
  const account = getCurrentAccountId(section);
  const params = new URLSearchParams({ section });
  if (account) params.set('account', account);
  return `${base}/api/gallery/${renderingId}/stream/?${params.toString()}`;
}

export function getDownloadUrl(
  renderingId: string,
  section: Section = getCurrentSection(),
): string {
  const base = getApiBaseUrl();
  const account = getCurrentAccountId(section);
  const params = new URLSearchParams({ section });
  if (account) params.set('account', account);
  return `${base}/api/gallery/${renderingId}/download/?${params.toString()}`;
}

export function getSegmentAudioDownloadUrl(
  segmentId: string,
  format: 'wav' | 'mp3' = 'wav',
  section: Section = getCurrentSection()
): string {
  const base = getApiBaseUrl();
  const account = getCurrentAccountId(section);
  const params = new URLSearchParams({ audio_format: format, section });
  if (account) params.set('account', account);
  return `${base}/api/segments/${segmentId}/download-audio/?${params.toString()}`;
}

// ── Logos ──

export async function getLogos(): Promise<Logo[]> {
  const { data } = await api.get<Logo[]>('/api/settings/logos/');
  return data;
}

export async function uploadLogo(file: File): Promise<Logo> {
  const formData = new FormData();
  formData.append('file', file);
  const { data } = await api.post<Logo>('/api/settings/logos/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export async function deleteLogo(logoId: string): Promise<void> {
  await api.delete(`/api/settings/logos/${logoId}/`);
}

// ── Outro Videos ──

export async function getOutroVideos(): Promise<OutroVideo[]> {
  const { data } = await api.get<OutroVideo[]>('/api/settings/outros/');
  return data;
}

export async function uploadOutroVideo(file: File): Promise<OutroVideo> {
  const formData = new FormData();
  formData.append('file', file);
  const { data } = await api.post<OutroVideo>('/api/settings/outros/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export async function deleteOutroVideo(outroId: string): Promise<void> {
  await api.delete(`/api/settings/outros/${outroId}/`);
}

export default api;
