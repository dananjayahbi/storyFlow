// ── Settings Type Definitions (Task 05.03.12) ──

/**
 * Render resolution as a width/height pair.
 */
export interface RenderResolution {
  width: number;
  height: number;
}

/**
 * Global application settings — singleton record shared across all projects.
 *
 * Covers TTS defaults, subtitle styling, render parameters,
 * Ken Burns effect, and transition timing.
 */
export interface GlobalSettings {
  /** Default Kokoro TTS voice identifier (e.g. "af_bella"). */
  default_voice_id: string;

  /** Subtitle font family name (e.g. "Arial" or a custom uploaded font). */
  subtitle_font_family: string;

  /** Subtitle font size in pixels. */
  subtitle_font_size: number;

  /** Subtitle font color in hex format (e.g. "#FFFFFF"). */
  subtitle_font_color: string;

  /** Subtitle vertical position on the video frame. */
  subtitle_position: 'bottom' | 'center' | 'top';

  /** Output render resolution (width × height in pixels). */
  render_resolution: RenderResolution;

  /** Output render frames-per-second. */
  render_fps: number;

  /** Default Ken Burns zoom level (1.0 = no zoom). */
  ken_burns_zoom_level: number;

  /** Default transition duration between segments in seconds. */
  transition_duration: number;
}

/**
 * A Kokoro TTS voice available for audio generation.
 */
export interface Voice {
  /** Unique voice identifier used by the TTS engine (e.g. "af_bella"). */
  id: string;

  /** Human-readable display name (e.g. "Bella"). */
  name: string;

  /** Language / locale code (e.g. "en-US"). */
  language: string;

  /** Optional URL to a sample audio clip, or null if unavailable. */
  sample_url: string | null;
}
