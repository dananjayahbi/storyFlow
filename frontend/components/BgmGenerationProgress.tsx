'use client';

import { AlertCircle, CheckCircle2, Loader2 } from 'lucide-react';
import { Progress } from '@/components/ui/progress';
import { useBgmStore } from '@/lib/stores';
import { cn } from '@/lib/utils';

/**
 * Detailed MusicGen progress for the project toolbar and settings panel.
 *
 * Mirrors the TTS bulk-generation meter: a stage description, the current
 * segment count, an integer percentage and a progress bar.  Both surfaces read
 * the same store, so the bar is identical wherever it is rendered.
 */
export function BgmGenerationProgress({ className }: { className?: string }) {
  const generating = useBgmStore((state) => state.generating);
  const progress = useBgmStore((state) => state.progress);
  const message = useBgmStore((state) => state.message);
  const error = useBgmStore((state) => state.error);
  const lastClipId = useBgmStore((state) => state.lastClipId);

  if (!generating && !error && !lastClipId) return null;

  if (!generating) {
    if (error) {
      return (
        <p
          className={cn(
            'flex items-center gap-1.5 text-xs font-medium text-destructive',
            className
          )}
        >
          <AlertCircle className="h-3 w-3 shrink-0" />
          <span className="truncate">Music: {error}</span>
        </p>
      );
    }

    return (
      <p
        className={cn(
          'flex items-center gap-1.5 text-xs font-medium text-green-600 dark:text-green-400',
          className
        )}
      >
        <CheckCircle2 className="h-3 w-3 shrink-0" />
        Soundtrack generated and attached to this project
      </p>
    );
  }

  const percentage = Math.max(
    0,
    Math.min(100, Math.round(progress?.percentage ?? 0))
  );
  const current = progress?.current ?? 0;
  const total = progress?.total ?? 0;
  const description =
    message || progress?.description || 'Generating background music…';

  return (
    <div className={cn('space-y-1', className)}>
      <div className="flex items-center justify-between gap-3">
        <p className="flex min-w-0 items-center gap-1.5 text-xs text-muted-foreground">
          <Loader2 className="h-3 w-3 shrink-0 animate-spin" />
          <span className="truncate">{description}</span>
          {total > 0 && (
            <span className="shrink-0 text-[10px] tabular-nums">
              ({current}/{total})
            </span>
          )}
        </p>
        <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
          {percentage}%
        </span>
      </div>
      <Progress value={percentage} className="h-1.5" />
    </div>
  );
}
