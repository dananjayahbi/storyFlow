'use client';

import { VolumeX, Loader2, Check, XCircle } from 'lucide-react';
import { cn, formatTime } from '@/lib/utils';
import type { AudioGenerationState } from '@/lib/types';

interface AudioStatusBadgeProps {
  /** URL of the audio file, or null if none. */
  audioFile: string | null;
  /** Duration in seconds, or null if unknown. */
  audioDuration: number | null;
  /** Current audio generation state from the Zustand store. */
  generationStatus: AudioGenerationState;
  /** Optional additional class names. */
  className?: string;
}

export function AudioStatusBadge({
  audioFile,
  audioDuration,
  generationStatus,
  className,
}: AudioStatusBadgeProps) {
  // ── Generating ──
  if (generationStatus.status === 'generating') {
    return (
      <span
        className={cn(
          'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium',
          'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400',
          className,
        )}
      >
        <Loader2 className="h-3 w-3 animate-spin" />
        Generating
      </span>
    );
  }

  // ── Failed ──
  if (generationStatus.status === 'failed') {
    return (
      <span
        className={cn(
          'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium',
          'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
          className,
        )}
        title={generationStatus.error}
      >
        <XCircle className="h-3 w-3" />
        Failed
      </span>
    );
  }

  // ── Ready (audio exists) ──
  if (audioFile) {
    return (
      <span
        className={cn(
          'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium',
          'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
          className,
        )}
      >
        <Check className="h-3 w-3" />
        {audioDuration != null ? formatTime(audioDuration) : 'Ready'}
      </span>
    );
  }

  // ── No Audio (default) ──
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium',
        'bg-muted text-muted-foreground',
        className,
      )}
    >
      <VolumeX className="h-3 w-3" />
      No Audio
    </span>
  );
}
