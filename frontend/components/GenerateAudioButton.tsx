'use client';

import { Mic, Lock, Loader2, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { AudioGenerationState } from '@/lib/types';

interface GenerateAudioButtonProps {
  /** UUID of the segment. */
  segmentId: string;
  /** Whether the segment is locked. */
  isLocked: boolean;
  /** Current audio generation state from the Zustand store. */
  generationStatus: AudioGenerationState;
  /** Callback to trigger (or retry) audio generation. */
  onGenerate: () => void;
  /** Optional additional class names. */
  className?: string;
}

export function GenerateAudioButton({
  segmentId: _segmentId,
  isLocked,
  generationStatus,
  onGenerate,
  className,
}: GenerateAudioButtonProps) {
  // ── Locked state ──
  if (isLocked) {
    return (
      <div className={cn('w-full sm:w-auto', className)}>
        <Button
          variant="outline"
          size="sm"
          disabled
          title="Unlock segment to generate audio"
          aria-label="Generate Audio (locked)"
          className="w-full sm:w-auto min-h-[44px] sm:min-h-0"
        >
          <Lock className="mr-2 h-4 w-4" />
          Generate Audio
        </Button>
      </div>
    );
  }

  // ── Generating state ──
  if (generationStatus.status === 'generating') {
    return (
      <div className={cn('w-full sm:w-auto', className)}>
        <Button variant="outline" size="sm" disabled className="w-full sm:w-auto min-h-[44px] sm:min-h-0">
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          Generating…
        </Button>
      </div>
    );
  }

  // ── Failed state ──
  if (generationStatus.status === 'failed') {
    return (
      <div className={cn('flex flex-col sm:flex-row sm:items-center gap-2', className)}>
        <span className="text-sm text-destructive break-words">
          {generationStatus.error}
        </span>
        <Button variant="outline" size="sm" onClick={onGenerate} className="w-full sm:w-auto min-h-[44px] sm:min-h-0">
          <RefreshCw className="mr-2 h-4 w-4" />
          Retry
        </Button>
      </div>
    );
  }

  // ── Idle state (default) ──
  return (
    <div className={cn('w-full sm:w-auto', className)}>
      <Button variant="outline" size="sm" onClick={onGenerate} className="w-full sm:w-auto min-h-[44px] sm:min-h-0">
        <Mic className="mr-2 h-4 w-4" />
        Generate Audio
      </Button>
    </div>
  );
}
