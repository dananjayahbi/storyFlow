import axios from 'axios';
import {
  Project,
  ProjectDetail,
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
  GalleryItem,
  Logo,
  OutroVideo,
} from './types';
import { Voice } from './constants';

const api = axios.create({
  baseURL: 'http://localhost:8000',
});

export async function getProjects(): Promise<PaginatedResponse<Project>> {
  const response = await api.get<PaginatedResponse<Project>>('/api/projects/');
  return response.data;
}

export async function getProject(id: string): Promise<ProjectDetail> {
  const response = await api.get<ProjectDetail>(`/api/projects/${id}/`);
  return response.data;
}

export async function createProject(payload: CreateProjectPayload): Promise<Project> {
  const response = await api.post<Project>('/api/projects/', payload);
  return response.data;
}

export async function updateProject(id: string, data: Partial<Pick<Project, 'title' | 'status'>>): Promise<Project> {
  const response = await api.patch<Project>(`/api/projects/${id}/`, data);
  return response.data;
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
  segmentId: string
): Promise<TaskResponse> {
  const response = await api.post<TaskResponse>(
    `/api/segments/${segmentId}/generate-audio/`
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

// ── Available Voices (Task 05.03.02) ──

export async function getVoices(): Promise<Voice[]> {
  const { data } = await api.get<Voice[]>('/api/settings/voices/');
  return data;
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

export async function testTTS(
  text: string,
  voice?: string,
  speed?: number
): Promise<Blob> {
  const response = await api.post(
    '/api/settings/tts-test/',
    { text, voice, speed },
    { responseType: 'blob' }
  );
  return response.data;
}

// ── Gallery ──

export async function getGalleryItems(): Promise<GalleryItem[]> {
  const { data } = await api.get<GalleryItem[]>('/api/gallery/');
  return data;
}

export function getStreamUrl(projectId: string): string {
  const base = api.defaults.baseURL || 'http://localhost:8000';
  return `${base}/api/gallery/${projectId}/stream/`;
}

export function getDownloadUrl(projectId: string): string {
  const base = api.defaults.baseURL || 'http://localhost:8000';
  return `${base}/api/gallery/${projectId}/download/`;
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
