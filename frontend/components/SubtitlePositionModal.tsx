'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Slider } from '@/components/ui/slider';
import { GripHorizontal, RotateCcw } from 'lucide-react';

// ── Props ──────────────────────────────────────────────────────────
interface SubtitlePositionModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Current Y position in pixels (top-edge at render resolution), or null for preset. */
  yPosition: number | null;
  /** Preset position keyword — used as fallback when yPosition is null. */
  presetPosition: 'bottom' | 'center' | 'top';
  /** Render resolution width. */
  renderWidth: number;
  /** Render resolution height. */
  renderHeight: number;
  /** Subtitle font size in pixels. */
  fontSize: number;
  /** Subtitle color for the preview bar. */
  subtitleColor: string;
  /** Called with the new Y position (top-edge pixels from top at render res). */
  onSave: (yPosition: number | null) => Promise<void>;
}

// ── Constants ──────────────────────────────────────────────────────
const VERT_MARGIN_RATIO = 0.08; // matches subtitle_engine.py
const STROKE_WIDTH = 2;         // matches subtitle_engine.py DEFAULT_STROKE_WIDTH
const MAX_PREVIEW_WIDTH = 520;
const MAX_PREVIEW_HEIGHT = 380; // cap to prevent overflow on tall resolutions

/**
 * Compute the approximate rendered subtitle block height (pixels at
 * render resolution).  Mirrors the backend calculation in both
 * ``subtitle_engine.py`` and ``fast_compositor.py``:
 *   pad_px = max(stroke_width * 4, font_size // 4, 12)
 *   text_h ≈ font_size + 2 * pad_px
 */
function estimateSubtitleBlockH(fontSize: number): number {
  const padPx = Math.max(STROKE_WIDTH * 4, Math.floor(fontSize / 4), 12);
  return fontSize + 2 * padPx;
}

/**
 * Calculate the default TOP-EDGE Y position for a preset keyword.
 * The saved subtitle_y_position represents the TOP EDGE of the subtitle
 * block.  This matches precisely what the backend uses as ``y_pos``,
 * eliminating any dependency on the actual rendered clip height.
 */
function presetToTopY(
  preset: 'bottom' | 'center' | 'top',
  renderHeight: number,
  subtitleBlockHeight: number,
): number {
  const margin = Math.round(renderHeight * VERT_MARGIN_RATIO);
  switch (preset) {
    case 'top':
      return margin;
    case 'center':
      return Math.round((renderHeight - subtitleBlockHeight) / 2);
    case 'bottom':
    default:
      return renderHeight - subtitleBlockHeight - margin;
  }
}

// ── Component ──────────────────────────────────────────────────────

export function SubtitlePositionModal({
  open,
  onOpenChange,
  yPosition,
  presetPosition,
  renderWidth,
  renderHeight,
  fontSize,
  subtitleColor,
  onSave,
}: SubtitlePositionModalProps) {
  // Estimate subtitle block height to match backend rendering
  const subtitleBlockH = estimateSubtitleBlockH(fontSize);
  // Maximum top-edge Y so the subtitle stays fully inside the frame
  const maxTopY = Math.max(0, renderHeight - subtitleBlockH);

  // localY = TOP-EDGE of the subtitle in render-space pixels.
  // This is exactly what the backend uses as y_pos — no conversion needed.
  const initialY =
    yPosition !== null && yPosition !== undefined
      ? yPosition
      : presetToTopY(presetPosition, renderHeight, subtitleBlockH);

  const [localY, setLocalY] = useState(initialY);
  const [isSaving, setIsSaving] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const isDragging = useRef(false);

  // Re-sync when modal opens or external value changes
  useEffect(() => {
    if (open) {
      const y =
        yPosition !== null && yPosition !== undefined
          ? yPosition
          : presetToTopY(presetPosition, renderHeight, subtitleBlockH);
      setLocalY(y);
    }
  }, [open, yPosition, presetPosition, renderHeight, subtitleBlockH]);

  // ── Compute scale to fit preview in modal ──
  // Scale down so both width ≤ MAX_PREVIEW_WIDTH and height ≤ MAX_PREVIEW_HEIGHT
  const scaleW = MAX_PREVIEW_WIDTH / renderWidth;
  const scaleH = MAX_PREVIEW_HEIGHT / renderHeight;
  const scale = Math.min(scaleW, scaleH, 1); // never scale up
  const previewWidth = Math.round(renderWidth * scale);
  const previewHeight = Math.round(renderHeight * scale);
  const scaledSubH = Math.max(6, Math.round(subtitleBlockH * scale));

  // Convert render-space top-edge Y → preview-space top for CSS (trivial scaling)
  const topYToPreviewTop = (topY: number) => Math.round(topY * scale);

  // Clamp a render-space top-edge Y within valid range
  const clampTopY = (y: number) => Math.max(0, Math.min(y, maxTopY));

  // Convert a preview-space pointer Y to a render-space top-edge Y.
  // The pointer represents the CENTER of the subtitle for intuitive positioning.
  const pointerToTopY = (previewPointerY: number) => {
    const renderPointerY = previewPointerY / scale;
    return clampTopY(Math.round(renderPointerY - subtitleBlockH / 2));
  };

  // ── Drag handlers ──
  const handlePointerDown = useCallback(
    (e: React.PointerEvent) => {
      isDragging.current = true;
      (e.target as HTMLElement).setPointerCapture(e.pointerId);
    },
    [],
  );

  const handlePointerMove = useCallback(
    (e: React.PointerEvent) => {
      if (!isDragging.current || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const relativeY = e.clientY - rect.top;
      setLocalY(pointerToTopY(relativeY));
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [scale, subtitleBlockH, maxTopY],
  );

  const handlePointerUp = useCallback(() => {
    isDragging.current = false;
  }, []);

  // ── Click to reposition ──
  const handleContainerClick = useCallback(
    (e: React.MouseEvent) => {
      if (!containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const relativeY = e.clientY - rect.top;
      setLocalY(pointerToTopY(relativeY));
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [scale, subtitleBlockH, maxTopY],
  );

  // ── Save handler ──
  const handleSave = async () => {
    setIsSaving(true);
    try {
      await onSave(localY);
      onOpenChange(false);
    } finally {
      setIsSaving(false);
    }
  };

  // ── Reset to preset ──
  const handleReset = async () => {
    const defaultY = presetToTopY(presetPosition, renderHeight, subtitleBlockH);
    setLocalY(defaultY);
    // Also persist null to clear manual override
    setIsSaving(true);
    try {
      await onSave(null);
      onOpenChange(false);
    } finally {
      setIsSaving(false);
    }
  };

  // Top-edge in preview pixels for CSS positioning
  const previewTopY = topYToPreviewTop(localY);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[640px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Adjust Subtitle Position</DialogTitle>
          <DialogDescription>
            Drag the subtitle bar or click anywhere on the preview to set the
            vertical position. Resolution: {renderWidth} × {renderHeight}
          </DialogDescription>
        </DialogHeader>

        {/* ── Resolution Placeholder ── */}
        <div className="flex flex-col items-center gap-3 py-2">
          <div
            ref={containerRef}
            className="relative rounded-md overflow-hidden border border-border cursor-crosshair select-none"
            style={{
              width: previewWidth,
              height: previewHeight,
              background: 'linear-gradient(180deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)',
            }}
            onClick={handleContainerClick}
          >
            {/* Grid lines for visual reference */}
            {[0.25, 0.5, 0.75].map((ratio) => (
              <div
                key={ratio}
                className="absolute left-0 right-0 border-t border-dashed border-white/10"
                style={{ top: `${ratio * 100}%` }}
              />
            ))}

            {/* Resolution label */}
            <div className="absolute top-2 left-2 text-[10px] text-white/30 font-mono select-none pointer-events-none">
              {renderWidth}×{renderHeight}
            </div>

            {/* Placeholder image area hint */}
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
              <span className="text-white/15 text-sm font-medium">Video Frame</span>
            </div>

            {/* ── Draggable Subtitle Bar ── */}
            <div
              className="absolute left-1/2 -translate-x-1/2 cursor-grab active:cursor-grabbing"
              style={{
                top: previewTopY,
                width: '90%',
                touchAction: 'none',
              }}
              onPointerDown={handlePointerDown}
              onPointerMove={handlePointerMove}
              onPointerUp={handlePointerUp}
            >
              {/* Grip icon — positioned above the text via negative translate,
                  so it doesn't shift the subtitle text position */}
              <div className="flex justify-center -translate-y-full pb-0.5 pointer-events-none">
                <GripHorizontal className="w-4 h-4 text-white/50" />
              </div>
              {/* Subtitle text preview — top edge aligns exactly with previewTopY.
                  Uses fixed height to match the scaled block height precisely,
                  so visual placement matches actual rendering. */}
              <div
                className="w-full text-center flex items-center justify-center rounded-sm overflow-hidden"
                style={{
                  backgroundColor: 'rgba(0, 0, 0, 0.6)',
                  height: scaledSubH,
                }}
              >
                <span
                  className="font-bold leading-none select-none truncate px-2"
                  style={{
                    fontSize: Math.max(8, Math.round(scaledSubH * 0.45)),
                    color: subtitleColor || '#FFFFFF',
                    textShadow: [
                      '1px 1px 2px rgba(0,0,0,0.9)',
                      '-1px -1px 2px rgba(0,0,0,0.9)',
                      '1px -1px 2px rgba(0,0,0,0.9)',
                      '-1px 1px 2px rgba(0,0,0,0.9)',
                    ].join(', '),
                  }}
                >
                  The quick brown fox jumps over
                </span>
              </div>
            </div>
          </div>

          {/* ── Y-Position Slider ── */}
          <div className="w-full max-w-[520px] space-y-1.5">
            <div className="flex items-center justify-between">
              <label className="text-xs text-muted-foreground font-medium">
                Y Position (top edge): {localY}px
              </label>
              <Button
                variant="ghost"
                size="sm"
                className="h-6 px-2 text-xs gap-1"
                onClick={handleReset}
                disabled={isSaving}
              >
                <RotateCcw className="w-3 h-3" />
                Reset to {presetPosition}
              </Button>
            </div>
            <Slider
              value={[localY]}
              min={0}
              max={maxTopY}
              step={1}
              onValueChange={(v) => setLocalY(v[0])}
            />
            <div className="flex justify-between text-[10px] text-muted-foreground/60">
              <span>0 (top)</span>
              <span>{maxTopY} (bottom)</span>
            </div>
          </div>
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isSaving}
          >
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={isSaving}>
            {isSaving ? 'Saving…' : 'Save Position'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
