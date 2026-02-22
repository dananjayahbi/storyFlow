// ── Settings Zustand Store (Task 05.03.12) ──

import { create } from 'zustand';
import type { GlobalSettings, Voice } from '../types/settings';
import * as settingsApi from '../api/settingsApi';

// ── Store shape ──

interface SettingsState {
  /** Current global settings (null until the first fetch completes). */
  settings: GlobalSettings | null;

  /** Available Kokoro TTS voices. */
  voices: Voice[];

  /** True while any settings request is in-flight. */
  loading: boolean;

  /** Most recent error message, or null when there is no error. */
  error: string | null;

  // ── Actions ──

  /** Fetch the singleton GlobalSettings from the backend. */
  fetchSettings: () => Promise<void>;

  /** Partially update settings and refresh local state with the response. */
  saveSettings: (data: Partial<GlobalSettings>) => Promise<void>;

  /** Fetch the list of available TTS voices. */
  fetchVoices: () => Promise<void>;

  /** Upload a custom subtitle font and update settings with the result. */
  uploadFont: (file: File) => Promise<void>;
}

// ── Store implementation ──

export const useSettingsStore = create<SettingsState>()((set) => ({
  settings: null,
  voices: [],
  loading: false,
  error: null,

  fetchSettings: async () => {
    set({ loading: true, error: null });
    try {
      const settings = await settingsApi.getSettings();
      set({ settings, loading: false });
    } catch {
      set({ error: 'Failed to load settings', loading: false });
    }
  },

  saveSettings: async (data) => {
    set({ error: null });
    try {
      const updated = await settingsApi.updateSettings(data);
      set({ settings: updated });
    } catch {
      set({ error: 'Failed to save settings' });
    }
  },

  fetchVoices: async () => {
    set({ error: null });
    try {
      const voices = await settingsApi.getVoices();
      set({ voices });
    } catch {
      set({ error: 'Failed to load voices' });
    }
  },

  uploadFont: async (file) => {
    set({ error: null });
    try {
      const updated = await settingsApi.uploadFont(file);
      set({ settings: updated });
    } catch {
      set({ error: 'Failed to upload font' });
    }
  },
}));
