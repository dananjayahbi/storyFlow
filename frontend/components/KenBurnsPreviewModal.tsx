'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Pause, Play, RotateCcw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle,
} from '@/components/ui/dialog';
import { getApiBaseUrl } from '@/lib/apiConfig';
import { animationLabel, describeKenBurnsConfig } from '@/lib/kenBurns';
import {
  buildKenBurnsPreviewPlan,
  computePreparedFrame,
  previewTransform,
  sampleKenBurnsPreview,
} from '@/lib/kenBurnsPreview';
import type { ImageFocusArea, KenBurnsConfig } from '@/lib/types';

/** Used when the block has no TTS audio yet, so the speed is only a guess. */
export const DEFAULT_PREVIEW_DURATION = 5;

interface KenBurnsPreviewModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Image URL path exactly as stored on the segment. */
  image: string | null;
  config?: KenBurnsConfig | null;
  focusX?: number;
  focusY?: number;
  focusArea?: ImageFocusArea | null;
  focusAreas?: ImageFocusArea[] | null;
  frameWidth: number;
  frameHeight: number;
  zoomIntensity: number;
  segmentIndex: number;
  /** Block audio duration in seconds; null/0 means the TTS is missing. */
  duration?: number | null;
  segmentLabel?: string;
}

export function KenBurnsPreviewModal({
  open,
  onOpenChange,
  image,
  config = null,
  focusX = 0.5,
  focusY = 0.5,
  focusArea = null,
  focusAreas = null,
  frameWidth,
  frameHeight,
  zoomIntensity,
  segmentIndex,
  duration = null,
  segmentLabel,
}: KenBurnsPreviewModalProps) {
  const [naturalSize, setNaturalSize] = useState<{
    width: number;
    height: number;
  } | null>(null);
  const [progress, setProgress] = useState(0);
  const [playing, setPlaying] = useState(false);
  const elapsedRef = useRef(0);

  const estimatedDuration = !duration || duration <= 0;
  const previewDuration = estimatedDuration
    ? DEFAULT_PREVIEW_DURATION
    : Number(duration);

  const imageUrl = useMemo(() => {
    if (!image) return null;
    return image.startsWith('http') ? image : `${getApiBaseUrl()}${image}`;
  }, [image]);

  const prepared = useMemo(
    () =>
      computePreparedFrame(
        naturalSize?.width ?? 0,
        naturalSize?.height ?? 0,
        frameWidth,
        frameHeight,
        zoomIntensity,
      ),
    [naturalSize, frameWidth, frameHeight, zoomIntensity],
  );

  const plan = useMemo(
    () =>
      buildKenBurnsPreviewPlan({
        config,
        duration: previewDuration,
        segmentIndex,
        prepared,
        outputWidth: frameWidth,
        outputHeight: frameHeight,
        zoomIntensity,
        focusArea,
        focusAreas,
      }),
    [
      config,
      previewDuration,
      segmentIndex,
      prepared,
      frameWidth,
      frameHeight,
      zoomIntensity,
      focusArea,
      focusAreas,
    ],
  );

  // Restart when the modal opens so every visit shows the full move.
  // Deferred to the next frame because the state reset is a side effect of
  // the dialog opening, not of rendering.
  useEffect(() => {
    if (!open) return;
    elapsedRef.current = 0;
    const raf = requestAnimationFrame(() => {
      setProgress(0);
      setPlaying(true);
    });
    return () => cancelAnimationFrame(raf);
  }, [open]);

  // Drive the preview from the same clock and easing the renderer uses.
  useEffect(() => {
    if (!open || !playing) return;
    let raf = 0;
    let last = performance.now();
    const tick = (now: number) => {
      const delta = Math.max(0, (now - last) / 1000);
      last = now;
      const next = Math.min(previewDuration, elapsedRef.current + delta);
      elapsedRef.current = next;
      setProgress(previewDuration > 0 ? next / previewDuration : 1);
      if (next >= previewDuration) {
        setPlaying(false);
        return;
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [open, playing, previewDuration]);

  const restart = useCallback(() => {
    elapsedRef.current = 0;
    setProgress(0);
    setPlaying(true);
  }, []);

  const togglePlay = useCallback(() => {
    if (playing) {
      setPlaying(false);
      return;
    }
    if (elapsedRef.current >= previewDuration - 0.001) {
      elapsedRef.current = 0;
      setProgress(0);
    }
    setPlaying(true);
  }, [playing, previewDuration]);

  const seek = useCallback(
    (value: number) => {
      const next = Math.max(0, Math.min(previewDuration, value));
      elapsedRef.current = next;
      setProgress(previewDuration > 0 ? next / previewDuration : 0);
      setPlaying(false);
    },
    [previewDuration],
  );

  const frame = sampleKenBurnsPreview(plan, progress * previewDuration);
  const { transform } = previewTransform(frame);
  const currentSeconds = progress * previewDuration;

  const summary =
    plan.source === 'manual' && config
      ? describeKenBurnsConfig(config)
      : 'Automatic planner — a deterministic pan or zoom chosen for this block.';

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            Ken Burns preview
            {segmentLabel && (
              <Badge variant="secondary">{segmentLabel}</Badge>
            )}
          </DialogTitle>
          <DialogDescription>
            The exact motion path, easing and framing used by the renderer.
          </DialogDescription>
        </DialogHeader>

        {imageUrl ? (
          <div className="space-y-3">
            <div
              className="relative w-full overflow-hidden rounded-md border bg-black"
              style={{ aspectRatio: `${frameWidth} / ${frameHeight}` }}
              role="img"
              aria-label="Ken Burns animation preview"
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={imageUrl}
                alt=""
                draggable={false}
                onLoad={(event) => {
                  const target = event.currentTarget;
                  if (target.naturalWidth && target.naturalHeight) {
                    setNaturalSize({
                      width: target.naturalWidth,
                      height: target.naturalHeight,
                    });
                  }
                }}
                className="absolute inset-0 h-full w-full select-none object-cover"
                style={{
                  objectPosition: `${focusX * 100}% ${focusY * 100}%`,
                  transform,
                  transformOrigin: 'center',
                  willChange: 'transform',
                }}
              />
            </div>

            <div className="flex items-center gap-3">
              <Button
                type="button"
                size="icon"
                variant="secondary"
                className="h-8 w-8 shrink-0"
                onClick={togglePlay}
                aria-label={playing ? 'Pause preview' : 'Play preview'}
                title={playing ? 'Pause preview' : 'Play preview'}
              >
                {playing ? (
                  <Pause className="h-4 w-4" />
                ) : (
                  <Play className="h-4 w-4" />
                )}
              </Button>
              <Button
                type="button"
                size="icon"
                variant="ghost"
                className="h-8 w-8 shrink-0"
                onClick={restart}
                aria-label="Restart preview"
                title="Restart preview"
              >
                <RotateCcw className="h-4 w-4" />
              </Button>
              <input
                type="range"
                min={0}
                max={previewDuration}
                step={0.01}
                value={currentSeconds}
                onChange={(event) => seek(Number(event.target.value))}
                className="h-1.5 flex-1 cursor-pointer accent-primary"
                aria-label="Preview position"
              />
              <span className="w-24 shrink-0 text-right text-[11px] tabular-nums text-muted-foreground">
                {currentSeconds.toFixed(1)}s / {previewDuration.toFixed(1)}s
              </span>
            </div>

            <div className="space-y-1 rounded-md border bg-muted/20 px-3 py-2">
              <div className="flex items-center gap-2 text-xs font-medium">
                <span>{plan.source === 'manual' && config
                  ? animationLabel(config.animation)
                  : 'Automatic'}</span>
                <Badge variant="outline" className="h-4 px-1.5 text-[10px]">
                  {plan.motion.replace(/_/g, ' ')}
                </Badge>
              </div>
              <p className="text-[11px] text-muted-foreground">{summary}</p>
              {estimatedDuration && (
                <p className="text-[11px] text-amber-600 dark:text-amber-400">
                  No TTS audio yet — this preview uses a{' '}
                  {DEFAULT_PREVIEW_DURATION} s estimate. Generate the audio to
                  preview the final speed.
                </p>
              )}
            </div>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            Upload an image to preview its Ken Burns animation.
          </p>
        )}
      </DialogContent>
    </Dialog>
  );
}
