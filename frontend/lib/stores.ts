import { create } from 'zustand';
import {
  getProject,
  getSegments,
  updateSegment as apiUpdateSegment,
  deleteSegment as apiDeleteSegment,
  uploadSegmentImage,
  removeSegmentImage,
  reorderSegments as apiReorderSegments,
} from './api';
import type { ProjectDetail, Segment, UpdateSegmentPayload } from './types';

interface ProjectStore {
  // State
  project: ProjectDetail | null;
  segments: Segment[];
  isLoading: boolean;
  error: string | null;

  // Actions
  fetchProject: (id: string) => Promise<void>;
  updateSegment: (id: string, data: UpdateSegmentPayload) => Promise<void>;
  deleteSegment: (id: string) => Promise<void>;
  reorderSegments: (newOrder: string[]) => Promise<void>;
  uploadImage: (segmentId: string, file: File) => Promise<void>;
  removeImage: (segmentId: string) => Promise<void>;
  reset: () => void;
}

export const useProjectStore = create<ProjectStore>()((set, get) => ({
  project: null,
  segments: [],
  isLoading: false,
  error: null,

  fetchProject: async (id) => {
    set({ isLoading: true, error: null });
    try {
      const project = await getProject(id);
      const segments = await getSegments(id);
      set({ project, segments, isLoading: false });
    } catch {
      set({ error: 'Failed to load project', isLoading: false });
    }
  },

  updateSegment: async (id, data) => {
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

  reset: () => set({ project: null, segments: [], isLoading: false, error: null }),
}));
