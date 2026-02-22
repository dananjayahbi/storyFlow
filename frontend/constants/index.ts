// ── Centralised Constants (Task 05.03.13) ──
//
// Pure data – no side-effects, no runtime imports beyond TS types.
// Every export uses `as const` or `Readonly<>` to prevent mutation.

import type { GlobalSettings } from '../types/settings';

// ─────────────────────────────────────────────────────────────────
// Step 1 — Available Voices
// ─────────────────────────────────────────────────────────────────

/** Voice entry shape used by constants (matches types/settings Voice). */
export interface VoiceEntry {
  /** Kokoro TTS voice identifier (e.g. "af_bella"). */
  id: string;
  /** Human-readable display name. */
  name: string;
  /** Language / locale tag. */
  language: string;
}

/**
 * All Kokoro TTS voices the system supports.
 *
 * Keep in sync with `VOICE_METADATA` in `backend/api/views.py`
 * and `VALID_VOICE_IDS` in `backend/core_engine/tts_wrapper.py`.
 */
export const AVAILABLE_VOICES: readonly VoiceEntry[] = [
  { id: 'af_bella',   name: 'Bella',   language: 'en-US' },
  { id: 'af_sarah',   name: 'Sarah',   language: 'en-US' },
  { id: 'af_nicole',  name: 'Nicole',  language: 'en-US' },
  { id: 'am_adam',    name: 'Adam',    language: 'en-US' },
  { id: 'am_michael', name: 'Michael', language: 'en-US' },
  { id: 'bf_emma',    name: 'Emma',    language: 'en-GB' },
  { id: 'bm_george',  name: 'George',  language: 'en-GB' },
] as const;

// ─────────────────────────────────────────────────────────────────
// Step 2 — Default Settings
// ─────────────────────────────────────────────────────────────────

/**
 * Factory defaults for every GlobalSettings field.
 *
 * Used when initialising settings for the first time or as
 * fallback values when a field is missing.
 */
export const DEFAULT_SETTINGS: Readonly<GlobalSettings> = {
  default_voice_id: 'af_bella',
  subtitle_font_family: 'Arial',
  subtitle_font_size: 48,
  subtitle_font_color: '#FFFFFF',
  subtitle_position: 'bottom',
  render_resolution: { width: 1920, height: 1080 },
  render_fps: 30,
  ken_burns_zoom_level: 1.2,
  transition_duration: 0.5,
} as const;

// ─────────────────────────────────────────────────────────────────
// Step 3 — Validation Rules
// ─────────────────────────────────────────────────────────────────

/** Resolution preset entry. */
export interface ResolutionPreset {
  label: string;
  width: number;
  height: number;
}

export const VALIDATION = {
  /** Subtitle font size range (px). */
  SUBTITLE_FONT_SIZE_MIN: 12,
  SUBTITLE_FONT_SIZE_MAX: 120,

  /** Ken Burns zoom level range (1.0 = no zoom). */
  KEN_BURNS_ZOOM_MIN: 1.0,
  KEN_BURNS_ZOOM_MAX: 2.0,

  /** Transition duration range (seconds). */
  TRANSITION_DURATION_MIN: 0.0,
  TRANSITION_DURATION_MAX: 2.0,

  /** Allowed output FPS values. */
  FPS_OPTIONS: [24, 30, 60] as const,

  /** Common resolution presets. */
  RESOLUTION_PRESETS: [
    { label: '720p',  width: 1280, height: 720 },
    { label: '1080p', width: 1920, height: 1080 },
    { label: '4K',    width: 3840, height: 2160 },
  ] as const satisfies readonly ResolutionPreset[],

  /** Maximum font file size in bytes (10 MB). */
  MAX_FONT_SIZE: 10 * 1024 * 1024,

  /** Allowed font file extensions. */
  ALLOWED_FONT_EXTENSIONS: ['.ttf', '.otf', '.woff', '.woff2'] as const,

  /** Regex for validating hex colour strings (#RGB or #RRGGBB). */
  HEX_COLOR_REGEX: /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/,
} as const;

// ─────────────────────────────────────────────────────────────────
// Step 4 — Toast Messages
// ─────────────────────────────────────────────────────────────────

export const TOAST_MESSAGES = {
  // Settings
  SETTINGS_SAVED: 'Settings saved successfully.',
  SETTINGS_SAVE_FAILED: 'Failed to save settings.',

  // Font
  FONT_UPLOADED: 'Font uploaded successfully.',
  FONT_UPLOAD_FAILED: 'Failed to upload font.',

  // Audio
  AUDIO_GENERATION_STARTED: 'Audio generation started.',
  AUDIO_GENERATION_COMPLETED: 'Audio generation completed.',
  AUDIO_GENERATION_FAILED: 'Audio generation failed.',

  // Render
  RENDER_STARTED: 'Video render started.',
  RENDER_COMPLETED: 'Video render completed.',
  RENDER_FAILED: 'Video render failed.',

  // Project
  PROJECT_CREATED: 'Project created successfully.',
  PROJECT_DELETED: 'Project deleted successfully.',
  PROJECT_IMPORT_SUCCESS: 'Project imported successfully.',
  PROJECT_IMPORT_FAILED: 'Failed to import project.',
} as const;

// ─────────────────────────────────────────────────────────────────
// Step 5 — Keyboard Shortcuts
// ─────────────────────────────────────────────────────────────────

/** Keyboard shortcut metadata (no action callback). */
export interface KeyboardShortcutEntry {
  /** Human-readable key combo (e.g. "Ctrl+Enter"). */
  combo: string;
  /** `KeyboardEvent.code` or `.key` value for programmatic matching. */
  key: string;
  /** Modifier flags. */
  ctrl?: boolean;
  shift?: boolean;
  alt?: boolean;
  /** What the shortcut does. */
  description: string;
  /** Display keys for the help dialog. */
  displayKeys: readonly string[];
}

export const KEYBOARD_SHORTCUTS: readonly KeyboardShortcutEntry[] = [
  {
    combo: 'Ctrl+Enter',
    key: 'Enter',
    ctrl: true,
    description: 'Generate audio for the current segment',
    displayKeys: ['Ctrl', 'Enter'],
  },
  {
    combo: 'Ctrl+Shift+Enter',
    key: 'Enter',
    ctrl: true,
    shift: true,
    description: 'Export / render the full video',
    displayKeys: ['Ctrl', 'Shift', 'Enter'],
  },
  {
    combo: 'Ctrl+S',
    key: 'KeyS',
    ctrl: true,
    description: 'Save global settings (when panel is open)',
    displayKeys: ['Ctrl', 'S'],
  },
  {
    combo: 'Escape',
    key: 'Escape',
    description: 'Close any open modal or panel',
    displayKeys: ['Esc'],
  },
  {
    combo: '?',
    key: '?',
    description: 'Open keyboard shortcuts help',
    displayKeys: ['?'],
  },
] as const;

// ─────────────────────────────────────────────────────────────────
// Step 6 — Render Constants
// ─────────────────────────────────────────────────────────────────

export const RENDER_CONSTANTS = {
  /** Interval between render-progress polling requests (ms). */
  POLLING_INTERVAL_MS: 2_000,

  /** Maximum time to poll before considering the render timed-out (ms). */
  MAX_POLLING_DURATION_MS: 600_000, // 10 minutes

  /** Default crossfade / transition duration between segments (s). */
  CROSSFADE_DURATION_S: 0.5,
} as const;
