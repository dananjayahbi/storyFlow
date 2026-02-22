// ── Settings API Service (Task 05.03.12) ──

import axios from 'axios';
import type { GlobalSettings, Voice } from '../types/settings';

/**
 * Axios instance pointing at the StoryFlow backend.
 * Mirrors the base config used by the existing project / segment API.
 */
const api = axios.create({
  baseURL: 'http://localhost:8000',
  headers: { 'Content-Type': 'application/json' },
});

// ── Settings CRUD ──

/**
 * Fetch the singleton GlobalSettings record.
 *
 * GET /api/settings/
 */
export async function getSettings(): Promise<GlobalSettings> {
  const { data } = await api.get<GlobalSettings>('/api/settings/');
  return data;
}

/**
 * Partially update the GlobalSettings record.
 * Only the fields present in `data` will be changed on the backend.
 *
 * PATCH /api/settings/
 */
export async function updateSettings(
  data: Partial<GlobalSettings>,
): Promise<GlobalSettings> {
  const response = await api.patch<GlobalSettings>('/api/settings/', data);
  return response.data;
}

// ── Voices ──

/**
 * List all available Kokoro TTS voices.
 *
 * GET /api/settings/voices/
 */
export async function getVoices(): Promise<Voice[]> {
  const { data } = await api.get<Voice[]>('/api/settings/voices/');
  return data;
}

// ── Font Upload ──

/**
 * Upload a custom subtitle font file (`.ttf` / `.otf`).
 * Returns the updated GlobalSettings with the new font family applied.
 *
 * POST /api/settings/font/upload/  (multipart/form-data)
 */
export async function uploadFont(file: File): Promise<GlobalSettings> {
  const formData = new FormData();
  formData.append('font_file', file);

  const { data } = await api.post<GlobalSettings>(
    '/api/settings/font/upload/',
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } },
  );
  return data;
}
