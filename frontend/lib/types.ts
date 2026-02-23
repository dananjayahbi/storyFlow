export interface Project {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  status: 'DRAFT' | 'PROCESSING' | 'COMPLETED' | 'FAILED';
  resolution_width: number;
  resolution_height: number;
  framerate: number;
  segment_count: number;
}

export interface Segment {
  id: string;
  project: string;
  sequence_index: number;
  text_content: string;
  image_prompt: string;
  image_file: string | null;
  audio_file: string | null;
  audio_duration: number | null;
  is_locked: boolean;
}

export interface GlobalSettings {
  default_voice_id: string;
  tts_speed: number;
  zoom_intensity: number;
  subtitle_font: string;
  subtitle_color: string;
  inter_segment_silence: number;
  subtitles_enabled: boolean;
}

export interface ProjectDetail extends Omit<Project, 'segment_count'> {
  output_path: string | null;
  segments: Segment[];
}

export interface CreateProjectPayload {
  title: string;
}

export interface ImportProjectRequest {
  format: 'json' | 'text';
  title: string;
  segments?: Array<{ text_content: string; image_prompt?: string }>;
  raw_text?: string;
}

export interface UpdateSegmentPayload {
  text_content?: string;
  image_prompt?: string;
  is_locked?: boolean;
}

export interface ReorderPayload {
  project_id: string;
  segment_order: string[];
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

// ── Audio Generation & Task Tracking ──

/** Per-segment audio generation state used by the Zustand store and UI components. */
export type AudioGenerationState =
  | { status: 'idle' }
  | { status: 'generating'; taskId?: string }
  | { status: 'completed' }
  | { status: 'failed'; error: string };

export type TaskStatus = 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED';

export interface TaskResponse {
  task_id: string;
  segment_id: string;
  status: TaskStatus;
  message: string;
}

export interface GenerateAllAudioOptions {
  skip_locked?: boolean;
  force_regenerate?: boolean;
}

export interface BulkTaskResponse {
  task_id: string;
  project_id: string;
  status: TaskStatus;
  total_segments: number;
  segments_to_process: number;
  message: string;
}

export interface TaskProgress {
  current: number;
  total: number;
  percentage: number;
  current_segment_id?: string;
}

export interface CompletedSegmentAudio {
  segment_id: string;
  audio_url: string;
  duration: number;
}

export interface TaskError {
  segment_id: string;
  error: string;
}

export interface TaskStatusResponse {
  task_id: string;
  status: TaskStatus;
  progress: TaskProgress;
  completed_segments: CompletedSegmentAudio[];
  errors: TaskError[];
}

export interface BulkGenerationProgress {
  task_id: string;
  status: TaskStatus;
  total: number;
  completed: number;
  failed: number;
  completed_segments: CompletedSegmentAudio[];
  errors: TaskError[];
}

// ── Render Pipeline ──

/** Render pipeline status for the project. */
export type RenderStatus = 'idle' | 'validating' | 'rendering' | 'completed' | 'failed';

/** Progress data returned by GET /api/projects/{id}/status/. */
export interface RenderProgress {
  current_segment: number;
  total_segments: number;
  percentage: number;
  current_phase: string;
}

/** Response from GET /api/projects/{id}/status/. */
export interface RenderStatusResponse {
  project_id: string;
  status: 'DRAFT' | 'PROCESSING' | 'COMPLETED' | 'FAILED';
  progress: RenderProgress | null;
  output_url: string | null;
}

// ── Gallery ──

/** A rendered video item returned by the Gallery API. */
export interface GalleryItem {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  resolution_width: number;
  resolution_height: number;
  framerate: number;
  segment_count: number;
  file_size: number;
  stream_url: string;
  download_url: string;
}
