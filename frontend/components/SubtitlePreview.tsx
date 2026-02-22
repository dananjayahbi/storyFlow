'use client';

import { VALIDATION } from '@/lib/constants';

// ── Props ──────────────────────────────────────────────────────────
interface SubtitlePreviewProps {
  /** Current font path string (used for display context only). */
  font: string;
  /** Current subtitle color hex string. */
  color: string;
}

// ── Component ──────────────────────────────────────────────────────

/**
 * Live preview box showing sample subtitle text styled with
 * the current font and color settings. Simulates a dark video
 * frame with bottom-center subtitle placement.
 */
export function SubtitlePreview({ color }: SubtitlePreviewProps) {
  // Resolve a safe color — fall back to white when the value is invalid
  const resolvedColor = VALIDATION.HEX_COLOR_REGEX.test(color)
    ? color
    : '#FFFFFF';

  return (
    <div className="space-y-1.5">
      {/* ── Label ── */}
      <p className="text-xs text-muted-foreground font-medium">Preview</p>

      {/* ── Video-frame simulation ── */}
      <div
        className="relative w-full rounded-md overflow-hidden bg-zinc-900 border border-border"
        style={{ height: 120, maxWidth: 260 }}
      >
        {/* Subtle gradient to mimic a dim scene */}
        <div className="absolute inset-0 bg-gradient-to-b from-zinc-800/30 to-zinc-900" />

        {/* ── Subtitle text — bottom-center ── */}
        <span
          className="absolute inset-x-0 bottom-3 text-center px-3 leading-snug select-none"
          style={{
            color: resolvedColor,
            fontFamily:
              '"Arial Black", "Helvetica Neue", ui-sans-serif, system-ui, sans-serif',
            fontWeight: 800,
            fontSize: '0.8rem',
            /*
             * Multi-directional text shadow simulating the stroke/outline
             * used in actual MoviePy subtitle rendering.
             */
            textShadow: [
              '1px 1px 2px rgba(0,0,0,0.9)',
              '-1px -1px 2px rgba(0,0,0,0.9)',
              '1px -1px 2px rgba(0,0,0,0.9)',
              '-1px 1px 2px rgba(0,0,0,0.9)',
              '0px 1px 2px rgba(0,0,0,0.9)',
              '0px -1px 2px rgba(0,0,0,0.9)',
              '1px 0px 2px rgba(0,0,0,0.9)',
              '-1px 0px 2px rgba(0,0,0,0.9)',
            ].join(', '),
          }}
        >
          The quick brown fox jumps over
        </span>
      </div>
    </div>
  );
}
