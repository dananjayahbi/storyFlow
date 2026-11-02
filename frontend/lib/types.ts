export interface Project {
  id: string;
  title: string;
  section?: 'facebook' | 'youtube';
  created_at: string;
  updated_at: string;
  status: 'DRAFT' | 'PROCESSING' | 'COMPLETED' | 'FAILED';
  resolution_width: number;
  resolution_height: number;
  framerate: number;
  segment_count: number;
}

/** Extended project data returned by the detail endpoint. */
export interface ProjectDetail extends Omit<Project, 'segment_count'> {
  output_path: string | null;
  segments: Segment[];

  // ── Per-project settings ──
  default_voice_id: string;
  tts_speed: number;
  tts_engine?: 'kokoro' | 'qwen';
  qwen_mode?: 'custom_voice' | 'clone';
  qwen_speaker?: string;
  qwen_language?: string;
  qwen_instruct?: string;
  qwen_max_new_tokens?: number;
  qwen_clone_x_vector_only?: boolean;
  active_voice_reference?: string | null;
  subtitle_font_family: string;
  subtitle_font_size: number;
  subtitle_font_color: string;
  subtitle_position: 'bottom' | 'center' | 'top';
  subtitle_y_position: number | null;
  subtitle_font: string;
  subtitle_color: string;
  subtitles_enabled: boolean;
  custom_font_file: string | null;
  zoom_intensity: number;
  ken_burns_zoom: number;
  transition_duration: number;
  inter_segment_silence: number;
  logo_enabled: boolean;
  active_logo: string | null;
  logo_scale: number;
  logo_position: 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right';
  logo_opacity: number;
  logo_margin: number;
  outro_enabled: boolean;
  active_outro: string | null;
  upscale_enabled: boolean;
  upscale_model: 'RealESRGAN_x4plus' | 'RealESRGAN_x2plus' | 'RealESRGAN_x4plus_anime_6B';
  upscale_denoise_strength: number;
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
  /** Which engine produced the current audio ('kokoro' | 'qwen' | ''). */
  audio_engine?: 'kokoro' | 'qwen' | '';
  is_locked: boolean;
}

export interface GlobalSettings {
  default_voice_id: string;
  tts_speed: number;
  tts_engine: 'kokoro' | 'qwen';
  qwen_mode: 'custom_voice' | 'clone';
  qwen_speaker: string;
  qwen_language: string;
  qwen_instruct: string;
  qwen_max_new_tokens: number;
  qwen_clone_x_vector_only: boolean;
  active_voice_reference: string | null;
  zoom_intensity: number;
  subtitle_font: string;
  subtitle_color: string;
  subtitle_font_size: number;
  subtitle_position: 'bottom' | 'center' | 'top';
  subtitle_y_position: number | null;  // Manual vertical position override (pixels from top at render res)
  inter_segment_silence: number;
  subtitles_enabled: boolean;
  render_width: number;
  render_height: number;
  render_fps: number;
  logo_enabled: boolean;
  active_logo: string | null;  // Logo UUID or null
  logo_scale: number;
  logo_position: 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right';
  logo_opacity: number;
  logo_margin: number;
  outro_enabled: boolean;
  active_outro: string | null;  // OutroVideo UUID or null
  upscale_enabled: boolean;
  upscale_model: 'RealESRGAN_x4plus' | 'RealESRGAN_x2plus' | 'RealESRGAN_x4plus_anime_6B';
  upscale_denoise_strength: number;
}

export interface Logo {
  id: string;
  name: string;
  file: string;      // URL path to the logo image
  uploaded_at: string;
}

export interface OutroVideo {
  id: string;
  name: string;
  file: string;      // URL path to the outro video
  uploaded_at: string;
}

/** A reference clip used by Qwen3-TTS zero-shot voice cloning. */
export interface VoiceReference {
  id: string;
  name: string;
  file: string;
  file_url: string | null;
  audio_url: string | null;
  transcript: string;
  duration: number | null;
  uploaded_at: string;
}

/** Capability/status entry for one TTS engine. */
export interface TtsEngineInfo {
  id: 'kokoro' | 'qwen';
  label: string;
  available: boolean;
  installed?: boolean;
  device: string;
  cuda?: boolean;
  python?: string | null;
  supports_cloning: boolean;
  error?: string | null;
  description?: string;
  speakers?: Record<string, string>;
  languages?: string[];
  modes?: Array<{ id: 'custom_voice' | 'clone'; label: string }>;
}

export interface TtsEnginesResponse {
  default_engine: 'kokoro';
  engines: TtsEngineInfo[];
}

/** Optional per-request TTS overrides for audio generation. */
export interface GenerateAudioOptions {
  engine?: 'kokoro' | 'qwen';
  voice_reference_id?: string | null;
}

export interface CreateProjectPayload {
  title: string;
  section?: 'facebook' | 'youtube';
}

export interface ImportProjectRequest {
  format: 'json' | 'text';
  title: string;
  section?: 'facebook' | 'youtube';
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
  engine?: 'kokoro' | 'qwen';
  message: string;
}

export interface GenerateAllAudioOptions {
  skip_locked?: boolean;
  force_regenerate?: boolean;
  engine?: 'kokoro' | 'qwen';
  voice_reference_id?: string | null;
}

export interface BulkTaskResponse {
  task_id?: string;
  project_id: string;
  status: TaskStatus;
  engine?: 'kokoro' | 'qwen';
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
