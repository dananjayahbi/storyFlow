export interface Account {
  id: string;
  name: string;
  section: 'facebook' | 'youtube';
  description: string;
  project_count: number;
  gallery_count: number;
  created_at: string;
  updated_at: string;
}

export interface Project {
  id: string;
  title: string;
  section?: 'facebook' | 'youtube';
  account?: string | null;
  account_name?: string | null;
  created_at: string;
  updated_at: string;
  status: 'DRAFT' | 'PROCESSING' | 'COMPLETED' | 'FAILED';
  resolution_width: number;
  resolution_height: number;
  framerate: number;
  segment_count: number;
  /** Number of rendered gallery assets linked to this project. */
  rendering_count?: number;
  /** Ready-to-use cover URL: active thumbnail, manual thumbnail, else segment. */
  thumbnail_url?: string | null;
  /** URL of the manually uploaded cover, when one exists. */
  manual_thumbnail_url?: string | null;
  has_manual_thumbnail?: boolean;
  /** URL of the active Metadata management thumbnail, when one exists. */
  active_thumbnail_url?: string | null;
  has_active_thumbnail?: boolean;
  /** Where `thumbnail_url` came from. */
  thumbnail_source?: 'active' | 'manual' | 'segment' | null;
}

/** One uploaded YouTube thumbnail candidate from Metadata management. */
export interface ProjectThumbnail {
  id: string;
  url: string | null;
  prompt: string;
  is_active: boolean;
  created_at: string;
}

/** Gating state for YouTube thumbnail generation. */
export interface ThumbnailReadiness {
  script_ready: boolean;
  images_ready: boolean;
  ready: boolean;
  segment_count: number;
  text_segment_count: number;
  image_count: number;
  required_images: number;
  min_reference_images: number;
}

/** One project's render preflight result from /api/projects/render-readiness/. */
export interface ProjectRenderReadiness {
  project_id: string;
  title: string;
  status: Project['status'];
  segment_count: number;
  /** Status allows a render (DRAFT, COMPLETED or FAILED). */
  renderable: boolean;
  /** Backend render validation passed (files exist on disk). */
  ready: boolean;
  is_processing: boolean;
  missing_images: string[];
  missing_audio: string[];
  message: string;
}

/** Extended project data returned by the detail endpoint. */
export interface LatestRendering {
  id: string;
  created_at: string;
  status: RenderingStatus;
  status_label: string;
  duration: number | null;
  /** Wall-clock seconds spent in the video render pipeline. */
  render_time_seconds: number | null;
}

export interface ProjectDetail extends Omit<Project, 'segment_count'> {
  output_path: string | null;
  segments: Segment[];
  rendering_count?: number;
  /** Newest render, including how long it took to generate. */
  latest_rendering?: LatestRendering | null;
  /** Uploaded thumbnail candidates; one may be active. */
  thumbnails?: ProjectThumbnail[];
  /** Backend-computed gating for thumbnail prompt generation. */
  thumbnail_readiness?: ThumbnailReadiness;
  /** Editable system prompt for thumbnail prompt generation (empty = default). */
  thumbnail_system_prompt?: string;
  /** Editable system prompts for upload-ready title/description generation. */
  title_system_prompt?: string;
  description_system_prompt?: string;
  /** Saved upload-ready YouTube metadata (separate from the project title). */
  upload_title?: string;
  upload_description?: string;
  /** Selected video compositor: v1 (stable) or v2 (parallel). */
  render_pipeline?: 'v1' | 'v2';

  // ── Per-project settings ──
  default_voice_id: string;
  tts_speed: number;
  /** Optional project-specific system prompt for TTS script rewriting. */
  tts_system_prompt?: string;
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
  bgm_enabled: boolean;
  active_bgm: string | null;
  bgm_gain_db: number;
  bgm_ducking_db: number;
  bgm_echo_percent: number;
  bgm_crossfade_ms: number;
  tts_gain_db: number;
  upscale_enabled: boolean;
  upscale_model: 'RealESRGAN_x4plus' | 'RealESRGAN_x2plus' | 'RealESRGAN_x4plus_anime_6B';
  upscale_denoise_strength: number;
  /** Write-only: re-apply the resolution defaults to this project. */
  reset_settings?: boolean;
}

/** Normalised rectangle inside the rendered image frame (0..1). */
export interface ImageFocusArea {
  x: number;
  y: number;
  w: number;
  h: number;
}

/** Normalised point inside the rendered image frame (0..1). */
export interface KenBurnsPoint {
  x: number;
  y: number;
}

/**
 * Animation presets available in the per-segment manual Ken Burns editor.
 * Each preset has its own settings:
 * - `pan` uses start/end points (or a drawn area) and a constant crop.
 * - `zoom_in` / `zoom_out` use a focal point and zoom strength.
 * - `pan_zoom` combines the start/end path with a push-in.
 */
export type KenBurnsAnimation = 'pan' | 'zoom_in' | 'zoom_out' | 'pan_zoom';

/** How a pan path is defined: two points or a drawn rectangle. */
export type KenBurnsPanMode = 'points' | 'area';

/**
 * Per-segment manual Ken Burns override.  When `enabled` is false the
 * automatic planner keeps choosing the animation exactly as before.
 */
export interface KenBurnsConfig {
  enabled: boolean;
  animation: KenBurnsAnimation;
  pan_mode: KenBurnsPanMode;
  /** Pan start point (normalised to the visible render frame). */
  start: KenBurnsPoint;
  /** Pan end point (normalised to the visible render frame). */
  end: KenBurnsPoint;
  /** Centre of a zoom animation. */
  focal_point: KenBurnsPoint;
  /** Optional rectangle used when `pan_mode` is `area`. */
  area: ImageFocusArea | null;
  /** Visual zoom multiplier relative to the full frame (1.0 = no zoom). */
  zoom: number;
}

export interface Segment {
  id: string;
  project: string;
  sequence_index: number;
  text_content: string;
  /** Optional spoken version generated for the TTS engine. */
  tts_text?: string;
  image_prompt: string;
  image_file: string | null;
  audio_file: string | null;
  audio_duration: number | null;
  /** Measured sentence spans used for audio-accurate subtitles. */
  audio_timings?: {
    version?: number;
    method?: string;
    total?: number;
    sentences?: Array<{
      text: string;
      start: number;
      duration: number;
      end: number;
    }>;
  } | null;
  /** Which engine produced the current audio ('kokoro' | 'qwen' | ''). */
  audio_engine?: 'kokoro' | 'qwen' | '';
  is_locked: boolean;
  /** Normalised horizontal frame position inside the image (0..1). */
  image_focus_x?: number;
  /** Normalised vertical frame position inside the image (0..1). */
  image_focus_y?: number;
  /** Optional subject rectangle kept inside the Ken Burns frame. */
  image_focus_area?: ImageFocusArea | null;
  /** List form for compatibility; only the first (single) area is used. */
  image_focus_areas?: ImageFocusArea[] | null;
  /** Optional manual Ken Burns override (disabled = automatic planner). */
  ken_burns_config?: KenBurnsConfig | null;
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
  ken_burns_zoom?: number;
  transition_duration?: number;
  subtitle_font_family?: string;
  subtitle_font_color?: string;
  custom_font_file?: string | null;
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
  bgm_gain_db: number;
  bgm_ducking_db: number;
  bgm_echo_percent: number;
  tts_gain_db: number;
  upscale_enabled: boolean;
  upscale_model: 'RealESRGAN_x4plus' | 'RealESRGAN_x2plus' | 'RealESRGAN_x4plus_anime_6B';
  upscale_denoise_strength: number;
  /** Projects page layout, persisted per account in the database. */
  projects_view_mode: 'table' | 'tiles';
}

/**
 * Resolution-specific defaults used to seed a new project's settings.
 * A profile without a stored row reports the account settings as its
 * effective values with ``is_customized: false``.
 */
export interface ProjectSettingsProfile
  extends Omit<
    GlobalSettings,
    | 'render_width'
    | 'render_height'
    | 'render_fps'
    | 'projects_view_mode'
    | 'ken_burns_zoom'
    | 'transition_duration'
    | 'subtitle_font_family'
    | 'subtitle_font_color'
  > {
  id: string | null;
  resolution_width: number;
  resolution_height: number;
  framerate: number;
  ken_burns_zoom: number;
  transition_duration: number;
  subtitle_font_family: string;
  subtitle_font_color: string;
  is_customized: boolean;
  created_at?: string | null;
  updated_at?: string | null;
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
  account?: string;
  /** Chosen in the create dialog; pulls that resolution's default profile. */
  resolution_width?: number;
  resolution_height?: number;
}

export interface ImportProjectRequest {
  format: 'json' | 'text';
  title: string;
  section?: 'facebook' | 'youtube';
  account?: string;
  segments?: Array<{ text_content: string; image_prompt?: string }>;
  raw_text?: string;
}

export interface UpdateSegmentPayload {
  text_content?: string;
  tts_text?: string;
  image_prompt?: string;
  is_locked?: boolean;
  image_focus_x?: number;
  image_focus_y?: number;
  image_focus_area?: ImageFocusArea | null;
  image_focus_areas?: ImageFocusArea[];
  ken_burns_config?: KenBurnsConfig;
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

export type TaskStatus = 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED' | 'CANCELLED';

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
  description?: string;
  /** MusicGen task results. */
  generated_clip_id?: string;
  output_url?: string;
  duration?: number;
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
  /** Wall-clock seconds the completed render took, when known. */
  render_time_seconds?: number | null;
}

/** Response from GET /api/projects/{id}/status/. */
export interface RenderStatusResponse {
  project_id: string;
  status: 'DRAFT' | 'PROCESSING' | 'COMPLETED' | 'FAILED';
  progress: RenderProgress | null;
  output_url: string | null;
}

// ── Script Craft & Script Library ──

export interface ScriptSegment {
  text_content: string;
  image_prompt: string;
}

export interface ScriptContent {
  title: string;
  segments: ScriptSegment[];
}

/** A script saved to an account's Script Library. */
export interface Script {
  id: string;
  account: string;
  section: 'facebook' | 'youtube';
  title: string;
  pitch: string;
  content: ScriptContent;
  model_used: string;
  segment_count: number;
  created_at: string;
  updated_at: string;
}

export interface ScriptGenerateResponse {
  reply: string;
  script: ScriptContent;
  model: string;
  segment_count: number;
}

export interface ScriptChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

/** A tool activity chip shown under an assistant message. */
export interface ChatToolEvent {
  name: string;
  status: 'started' | 'completed' | string;
  label?: string;
}

/** One message in a persisted Script Craft conversation. */
export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  thinking?: string;
  tools?: ChatToolEvent[];
  question?: string;
  options?: string[];
  steering?: boolean;
  stopped?: boolean;
  created_at: string;
}

/** One script page inside a chat session's "book". */
export interface ChatScriptPage {
  id: string;
  title: string;
  pitch: string;
  content: ScriptContent;
  model: string;
  created_at: string;
  updated_at: string;
}

/** A persisted Script Craft chat session. */
export interface ChatSession {
  id: string;
  account: string;
  section: 'facebook' | 'youtube';
  title: string;
  summary: string;
  messages: ChatMessage[];
  scripts: ChatScriptPage[];
  pending_steer: string;
  stop_requested: boolean;
  compacted_at: string | null;
  message_count: number;
  script_count: number;
  last_message: string;
  created_at: string;
  updated_at: string;
}

/** The block the user selected before sending a message. */
export interface ChatSelection {
  script_id: string;
  segment_index: number;
}

export interface ChatCompactResponse {
  summary: string;
  compacted_at: string | null;
  message_count: number;
}

/** Per-account Script Craft AI configuration. */
export interface AIConfig {
  model: string;
  system_prompt: string;
  default_model: string;
  base_url: string;
  api_key: string;
  temperature: number;
  apply_to_all: boolean;
  search_enabled: boolean;
  search_provider: 'duckduckgo' | 'brave';
  search_brave_api_key: string;
  search_region: string;
}

// ── BGM Library ──

/** A background-music track (always stored as MP3). */
export interface BgmClip {
  id: string;
  account: string;
  account_name: string;
  section: 'facebook' | 'youtube';
  name: string;
  file: string;
  file_url: string;
  is_shared: boolean;
  /** 'uploaded' or 'generated' (MusicGen). */
  source: 'uploaded' | 'generated';
  project: string | null;
  generation_metadata: MusicGenerationMetadata;
  original_name: string;
  original_format: string;
  duration: number | null;
  file_size: number;
  can_edit: boolean;
  created_at: string;
  updated_at: string;
}

// ── Audio Mix playground (Settings page) ──

export interface PlaygroundBlock {
  index: number;
  text_content: string;
  image_url: string | null;
  has_audio: boolean;
  audio_duration: number | null;
}

export interface PlaygroundState {
  project_id: string;
  title: string;
  status: 'DRAFT' | 'PROCESSING' | 'COMPLETED' | 'FAILED';
  /** Background job currently running: BASE (TTS + video) or MIX. */
  job: 'BASE' | 'MIX' | '';
  output_url: string | null;
  /** Cache-busting mtime for the rendered demo video. */
  output_version: number | null;
  /** Cached video rendered once with TTS, no subtitles and no music. */
  base_video_url: string | null;
  base_video_version: number | null;
  has_base_video: boolean;
  /** True when the base video can be re-mixed without regenerating it. */
  can_remix: boolean;
  bgm_clip: string | null;
  /** What the last apply/generate used: MusicGen, a library clip, or none. */
  music_source: 'generated' | 'library' | 'none';
  music_clip_name: string | null;
  /** A MusicGen soundtrack exists and matches the current script. */
  generated_music_ready: boolean;
  /** A soundtrack exists but the script/durations changed since it was made. */
  generated_music_stale: boolean;
  music_fingerprint: string;
  blocks: PlaygroundBlock[];
  task_status: 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED' | 'CANCELLED' | null;
  progress: number | null;
  progress_description: string | null;
  cancel_requested: boolean;
}

/** Metadata stored on a MusicGen-generated BGM clip. */
export interface MusicGenerationMetadata {
  engine?: string;
  model?: string;
  generated?: boolean;
  bpm?: number;
  root_key?: string;
  mode?: string;
  anchor?: string;
  style?: string;
  prompts?: string[];
  segment_count?: number;
  total_duration?: number;
}

export interface MusicEngineStatus {
  engine: 'musicgen';
  backend?: 'transformers' | 'audiocraft' | 'unavailable';
  model: string;
  model_dir?: string | null;
  installed: boolean;
  torch_installed: boolean;
  torch_version: string | null;
  transformers_version?: string | null;
  cuda_available: boolean;
  device: 'cuda' | 'cpu' | null;
  available: boolean;
  python: string;
  gpu?: string | null;
  vram_total_gb?: number | null;
  vram_free_gb?: number | null;
  weights_verified?: boolean | null;
  reason: string | null;
  sample_rate: number;
  continuation_tail_seconds: number;
  crossfade_ms: number;
}

export interface GenerateSoundtrackPayload {
  project?: string;
  segments?: Array<{
    text_content: string;
    image_prompt?: string;
    duration: number;
  }>;
  name?: string;
  bpm?: number;
  root_key?: string;
  mode?: 'major' | 'minor';
  style?: string;
  attach?: boolean;
}

export interface GenerateSoundtrackResponse {
  task_id: string;
  status: TaskStatus;
  engine: 'musicgen';
  model: string;
  project_id: string | null;
  account_id: string;
  segments: number;
  estimated_duration: number;
  attach_to_project: boolean;
  message: string;
}

// ── Gallery ──

/** Publishing workflow state of one rendered gallery asset. */
export type RenderingStatus = 'rendered' | 'ready_to_publish' | 'published';

/**
 * One rendered video asset returned by the Gallery API.  A project can have
 * many renderings; each one has its own file, status and metadata.
 */
export interface GalleryItem {
  /** Rendering id (the project id for assets rendered before this feature). */
  id: string;
  project_id: string;
  project_title: string;
  title: string;
  status: RenderingStatus;
  status_label: string;
  /** True for the project's current hero video. */
  is_primary?: boolean;
  created_at: string;
  updated_at: string;
  published_at: string | null;
  resolution_width: number;
  resolution_height: number;
  framerate: number;
  segment_count: number;
  file_size: number;
  duration: number | null;
  /** Wall-clock seconds spent rendering this video, when known. */
  render_time_seconds?: number | null;
  /**
   * The owning project's configured cover, using the same fallback as the
   * Projects page (active thumbnail → manual cover → first segment image).
   */
  thumbnail_url?: string | null;
  /** Which source produced `thumbnail_url`. */
  thumbnail_source?: 'active' | 'manual' | 'segment' | null;
  stream_url: string;
  download_url: string;
}
