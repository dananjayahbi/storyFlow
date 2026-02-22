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

// ── Validation constants (Task 05.03.03) ──────────────────────────

export const VALIDATION = {
  /** Allowed font file extensions for subtitle fonts. */
  ALLOWED_FONT_EXTENSIONS: ['.ttf', '.otf'] as const,

  /** Maximum font file size in bytes (10 MB). */
  MAX_FONT_SIZE: 10 * 1024 * 1024,

  /** Regex for validating hex color strings (#RGB or #RRGGBB). */
  HEX_COLOR_REGEX: /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/,
} as const;
