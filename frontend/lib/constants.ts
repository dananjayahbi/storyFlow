// ===================================================================
// Shared Constants (Task 05.03.02 + 05.03.03)
// ===================================================================

/** A single Kokoro TTS voice entry. */
export interface Voice {
  id: string;
  name: string;
  gender: string;
  accent?: string;
}

/**
 * Hardcoded fallback voice list.
 *
 * Used when `GET /api/settings/voices/` is unreachable (network error,
 * backend down, etc.).  Must stay in sync with
 * `VOICE_METADATA` in `backend/api/views.py` and
 * `VALID_VOICE_IDS` in `backend/core_engine/tts_wrapper.py`.
 */
export const AVAILABLE_VOICES: Voice[] = [
  { id: 'af_bella',   name: 'Bella',   gender: 'Female' },
  { id: 'af_sarah',   name: 'Sarah',   gender: 'Female' },
  { id: 'af_nicole',  name: 'Nicole',  gender: 'Female' },
  { id: 'am_adam',    name: 'Adam',    gender: 'Male' },
  { id: 'am_michael', name: 'Michael', gender: 'Male' },
  { id: 'bf_emma',    name: 'Emma',    gender: 'Female', accent: 'British' },
  { id: 'bm_george',  name: 'George',  gender: 'Male',   accent: 'British' },
];

// ── Resolution preset type ────────────────────────────────────────

/** Resolution preset entry. */
export interface ResolutionPreset {
  label: string;
  width: number;
  height: number;
  aspect: string;
  category: 'landscape' | 'portrait' | 'square';
}

// ── Validation constants (Task 05.03.03) ──────────────────────────

export const VALIDATION = {
  /** Allowed font file extensions for subtitle fonts. */
  ALLOWED_FONT_EXTENSIONS: ['.ttf', '.otf'] as const,

  /** Maximum font file size in bytes (10 MB). */
  MAX_FONT_SIZE: 10 * 1024 * 1024,

  /** Regex for validating hex color strings (#RGB or #RRGGBB). */
  HEX_COLOR_REGEX: /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/,

  /** Subtitle font size range (px). */
  SUBTITLE_FONT_SIZE_MIN: 12,
  SUBTITLE_FONT_SIZE_MAX: 120,

  /** Common resolution presets for different platforms. */
  RESOLUTION_PRESETS: [
    // 16:9 Landscape — YouTube, standard widescreen
    { label: '720p',           width: 1280, height: 720,  aspect: '16:9', category: 'landscape' },
    { label: '1080p',          width: 1920, height: 1080, aspect: '16:9', category: 'landscape' },
    { label: '4K',             width: 3840, height: 2160, aspect: '16:9', category: 'landscape' },
    // 9:16 Portrait — TikTok, Reels, Shorts
    { label: '720p Portrait',  width: 720,  height: 1280, aspect: '9:16', category: 'portrait' },
    { label: '1080p Portrait', width: 1080, height: 1920, aspect: '9:16', category: 'portrait' },
    // 1:1 Square — Instagram / Facebook post
    { label: '720p Square',    width: 720,  height: 720,  aspect: '1:1',  category: 'square' },
    { label: '1080p Square',   width: 1080, height: 1080, aspect: '1:1',  category: 'square' },
    // 4:5 Portrait — Instagram / Facebook feed
    { label: '1080 × 1350',    width: 1080, height: 1350, aspect: '4:5',  category: 'portrait' },
    // 4:3 Landscape — Classic
    { label: '1440 × 1080',    width: 1440, height: 1080, aspect: '4:3',  category: 'landscape' },
    // 3:4 Portrait
    { label: '1080 × 1440',    width: 1080, height: 1440, aspect: '3:4',  category: 'portrait' },
  ] as const satisfies readonly ResolutionPreset[],
} as const;
