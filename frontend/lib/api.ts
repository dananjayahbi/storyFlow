import axios from 'axios';
import { Project, ProjectDetail, Segment, CreateProjectPayload, ImportProjectRequest, UpdateSegmentPayload, PaginatedResponse } from './types';

const api = axios.create({
  baseURL: 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
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

export async function importProject(payload: ImportProjectRequest): Promise<ProjectDetail> {
  const response = await api.post<ProjectDetail>('/api/projects/import/', payload);
  return response.data;
}

export async function getSegments(projectId: string): Promise<Segment[]> {
  const response = await api.get<Segment[]>(`/api/segments/?project=${projectId}`);
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

export default api;
