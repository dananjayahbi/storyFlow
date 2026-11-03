'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { Upload, X, Move, LocateFixed, Scan, Focus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { getApiBaseUrl } from '@/lib/apiConfig';
import type { ImageFocusArea } from '@/lib/types';

interface ImageUploaderProps {
  segmentId: string;
  currentImage: string | null;
  isLocked: boolean;
  /** Render frame width in pixels (project resolution). */
  frameWidth?: number;
  /** Render frame height in pixels (project resolution). */
  frameHeight?: number;
  /** Normalised horizontal frame position inside the image (0..1). */
  focusX?: number;
  /** Normalised vertical frame position inside the image (0..1). */
  focusY?: number;
  /** Optional marked subject area inside the frame. */
  focusArea?: ImageFocusArea | null;
  onFocusChange?: (segmentId: string, focus: { x: number; y: number }) => Promise<void>;
  onFocusAreaChange?: (segmentId: string, area: ImageFocusArea | null) => Promise<void>;
  onUpload: (segmentId: string, file: File) => Promise<void>;
  onRemove: (segmentId: string) => Promise<void>;
}

const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
const MAX_SIZE = 20 * 1024 * 1024; // 20MB
const MAX_FRAME_HEIGHT = 420;

function clamp01(value: number): number {
  return Math.max(0, Math.min(1, value));
}

interface DragState {
  pointerId: number;
  startClientX: number;
  startClientY: number;
  startFocusX: number;
  startFocusY: number;
  overflowX: number;
  overflowY: number;
}

interface SelectionState {
  pointerId: number;
  startX: number;
  startY: number;
  currentX: number;
  currentY: number;
}

const MIN_FOCUS_AREA = 0.03;

export function ImageUploader({
  segmentId, currentImage, isLocked,
  frameWidth = 1920, frameHeight = 1080, focusX = 0.5, focusY = 0.5,
  focusArea = null,
  onFocusChange, onFocusAreaChange, onUpload, onRemove,
}: ImageUploaderProps) {
  const [isDraggingFile, setIsDraggingFile] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isPanning, setIsPanning] = useState(false);
  const [isMarking, setIsMarking] = useState(false);
  const [selection, setSelection] = useState<ImageFocusArea | null>(null);
  const [focus, setFocus] = useState({ x: focusX, y: focusY });
  const [area, setArea] = useState<ImageFocusArea | null>(focusArea);
  const dragCounterRef = useRef(0);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const frameRef = useRef<HTMLDivElement>(null);
  const imageRef = useRef<HTMLImageElement>(null);
  const dragRef = useRef<DragState | null>(null);
  const selectionRef = useRef<SelectionState | null>(null);
  const focusRef = useRef(focus);

  useEffect(() => {
    focusRef.current = focus;
  }, [focus]);

  const imageUrl = currentImage
    ? (currentImage.startsWith('http') ? currentImage : `${getApiBaseUrl()}${currentImage}`)
    : null;

  // Keep the local pan in sync when the segment/project changes.
  useEffect(() => {
    setFocus({ x: focusX, y: focusY });
  }, [focusX, focusY, segmentId, currentImage]);

  useEffect(() => {
    setArea(focusArea ?? null);
  }, [focusArea, segmentId, currentImage]);

  useEffect(() => {
    // New image or aspect ratio → any in-flight drag is stale.
    dragRef.current = null;
    selectionRef.current = null;
    setSelection(null);
    setIsPanning(false);
    setIsMarking(false);
  }, [currentImage, frameWidth, frameHeight]);

  const handleFile = async (file: File) => {
    if (!ALLOWED_TYPES.includes(file.type)) {
      setError('Only JPEG, PNG, and WebP images are allowed.');
      return;
    }
    if (file.size > MAX_SIZE) {
      setError('Image must be under 20MB.');
      return;
    }
    setError(null);
    setIsUploading(true);
    try {
      await onUpload(segmentId, file);
    } finally {
      setIsUploading(false);
    }
  };

  const onDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    if (isLocked) return;
    dragCounterRef.current++;
    setIsDraggingFile(true);
  };

  const onDragOver = (e: React.DragEvent) => {
    e.preventDefault(); // REQUIRED — without this, onDrop won't fire
  };

  const onDragLeave = () => {
    dragCounterRef.current--;
    if (dragCounterRef.current === 0) setIsDraggingFile(false);
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    dragCounterRef.current = 0;
    setIsDraggingFile(false);
    if (isLocked) return;
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  const handleZoneClick = () => {
    if (isLocked) return;
    fileInputRef.current?.click();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleZoneClick();
    }
  };

  const handleRemove = async () => {
    if (isLocked) return;
    await onRemove(segmentId);
  };

  // ── Pan / reposition inside the frame ──────────────────────────────
  const computeOverflow = useCallback(() => {
    const frame = frameRef.current;
    const image = imageRef.current;
    if (!frame || !image || !image.naturalWidth || !image.naturalHeight) {
      return { overflowX: 0, overflowY: 0 };
    }
    const cw = frame.clientWidth;
    const ch = frame.clientHeight;
    const scale = Math.max(cw / image.naturalWidth, ch / image.naturalHeight);
    return {
      overflowX: Math.max(0, image.naturalWidth * scale - cw),
      overflowY: Math.max(0, image.naturalHeight * scale - ch),
    };
  }, []);

  const framePoint = (e: React.PointerEvent<HTMLDivElement>): { x: number; y: number } => {
    const rect = e.currentTarget.getBoundingClientRect();
    if (!rect.width || !rect.height) return { x: 0.5, y: 0.5 };
    return {
      x: clamp01((e.clientX - rect.left) / rect.width),
      y: clamp01((e.clientY - rect.top) / rect.height),
    };
  };

  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (isLocked) return;
    e.preventDefault();

    // Focus-area marking takes precedence over image panning.
    if (isMarking) {
      const point = framePoint(e);
      selectionRef.current = {
        pointerId: e.pointerId,
        startX: point.x,
        startY: point.y,
        currentX: point.x,
        currentY: point.y,
      };
      setSelection({ x: point.x, y: point.y, w: 0, h: 0 });
      e.currentTarget.setPointerCapture(e.pointerId);
      return;
    }

    const { overflowX, overflowY } = computeOverflow();
    if (overflowX < 1 && overflowY < 1) return;
    dragRef.current = {
      pointerId: e.pointerId,
      startClientX: e.clientX,
      startClientY: e.clientY,
      startFocusX: focusRef.current.x,
      startFocusY: focusRef.current.y,
      overflowX,
      overflowY,
    };
    setIsPanning(true);
    e.currentTarget.setPointerCapture(e.pointerId);
  };

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    const selecting = selectionRef.current;
    if (selecting && selecting.pointerId === e.pointerId) {
      const point = framePoint(e);
      selecting.currentX = point.x;
      selecting.currentY = point.y;
      const x = Math.min(selecting.startX, point.x);
      const y = Math.min(selecting.startY, point.y);
      setSelection({
        x,
        y,
        w: Math.abs(point.x - selecting.startX),
        h: Math.abs(point.y - selecting.startY),
      });
      return;
    }

    const drag = dragRef.current;
    if (!drag || drag.pointerId !== e.pointerId) return;
    const dx = e.clientX - drag.startClientX;
    const dy = e.clientY - drag.startClientY;
    const next = {
      x: drag.overflowX >= 1
        ? clamp01(drag.startFocusX - dx / drag.overflowX)
        : drag.startFocusX,
      y: drag.overflowY >= 1
        ? clamp01(drag.startFocusY - dy / drag.overflowY)
        : drag.startFocusY,
    };
    setFocus(next);
  };

  const finishPointer = (e: React.PointerEvent<HTMLDivElement>) => {
    const selecting = selectionRef.current;
    if (selecting && selecting.pointerId === e.pointerId) {
      selectionRef.current = null;
      if (e.currentTarget.hasPointerCapture(e.pointerId)) {
        e.currentTarget.releasePointerCapture(e.pointerId);
      }
      const x = Math.min(selecting.startX, selecting.currentX);
      const y = Math.min(selecting.startY, selecting.currentY);
      const w = Math.min(Math.abs(selecting.currentX - selecting.startX), 1 - x);
      const h = Math.min(Math.abs(selecting.currentY - selecting.startY), 1 - y);
      setSelection(null);

      if (w >= MIN_FOCUS_AREA && h >= MIN_FOCUS_AREA) {
        const next = {
          x: Number(x.toFixed(4)),
          y: Number(y.toFixed(4)),
          w: Number(w.toFixed(4)),
          h: Number(h.toFixed(4)),
        };
        setArea(next);
        setIsMarking(false);
        if (onFocusAreaChange) {
          onFocusAreaChange(segmentId, next).catch(() => {
            setError('Failed to save the focus area.');
          });
        }
      } else {
        setError('Draw a larger area to mark the focus.');
      }
      return;
    }

    const drag = dragRef.current;
    if (!drag || drag.pointerId !== e.pointerId) return;
    dragRef.current = null;
    setIsPanning(false);
    if (e.currentTarget.hasPointerCapture(e.pointerId)) {
      e.currentTarget.releasePointerCapture(e.pointerId);
    }

    const latest = focusRef.current;
    const changed = Math.abs(latest.x - focusX) > 0.001
      || Math.abs(latest.y - focusY) > 0.001;
    if (changed && onFocusChange) {
      onFocusChange(segmentId, latest).catch(() => {
        setError('Failed to save image position.');
      });
    }
  };

  const resetFocus = () => {
    if (isLocked) return;
    setFocus({ x: 0.5, y: 0.5 });
    if (onFocusChange) {
      onFocusChange(segmentId, { x: 0.5, y: 0.5 }).catch(() => {
        setError('Failed to save image position.');
      });
    }
  };

  const clearFocusArea = () => {
    if (isLocked) return;
    setArea(null);
    setIsMarking(false);
    setSelection(null);
    if (onFocusAreaChange) {
      onFocusAreaChange(segmentId, null).catch(() => {
        setError('Failed to clear the focus area.');
      });
    }
  };

  const toggleMarking = () => {
    if (isLocked) return;
    setError(null);
    setIsMarking((previous) => !previous);
    setSelection(null);
    selectionRef.current = null;
  };

  const shownArea = selection ?? area;

  // State B — Image uploaded: show the render frame with draggable pan
  if (imageUrl) {
    const aspect = frameWidth > 0 && frameHeight > 0
      ? frameWidth / frameHeight
      : 16 / 9;
    const isRepositioned = Math.abs(focus.x - 0.5) > 0.001
      || Math.abs(focus.y - 0.5) > 0.001;

    return (
      <div className="space-y-1">
        <div className="relative group mx-auto w-full" style={{ maxWidth: `${Math.round(MAX_FRAME_HEIGHT * aspect)}px` }}>
          <div
            ref={frameRef}
            onPointerDown={handlePointerDown}
            onPointerMove={handlePointerMove}
            onPointerUp={finishPointer}
            onPointerCancel={finishPointer}
            style={{ aspectRatio: `${frameWidth || 16} / ${frameHeight || 9}`, touchAction: 'none' }}
            className={cn(
              'relative w-full overflow-hidden rounded-md border bg-muted select-none',
              !isLocked && !isMarking && 'cursor-grab',
              isPanning && 'cursor-grabbing',
              isMarking && 'cursor-crosshair',
            )}
            title={
              isLocked
                ? 'Unlock the segment to edit the image'
                : isMarking
                  ? 'Drag to mark the Ken Burns focus area'
                  : 'Drag to reposition the image inside the render frame'
            }
            aria-label={`Render frame ${frameWidth}×${frameHeight}. ${isMarking ? 'Drag to mark the Ken Burns focus area.' : 'Drag to reposition the image.'}`}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              ref={imageRef}
              src={imageUrl}
              alt="Segment image cropped to the render frame"
              draggable={false}
              className="absolute inset-0 h-full w-full object-cover pointer-events-none"
              style={{ objectPosition: `${focus.x * 100}% ${focus.y * 100}%` }}
            />

            {/* Frame crop guides */}
            <div className="pointer-events-none absolute inset-0 ring-1 ring-inset ring-white/20" />

            {/* Marked Ken Burns focus area (or the live selection) */}
            {shownArea && shownArea.w > 0 && shownArea.h > 0 && (
              <div
                className={cn(
                  'pointer-events-none absolute border-2',
                  isMarking ? 'border-amber-300 bg-amber-300/20' : 'border-primary bg-primary/20',
                )}
                style={{
                  left: `${shownArea.x * 100}%`,
                  top: `${shownArea.y * 100}%`,
                  width: `${shownArea.w * 100}%`,
                  height: `${shownArea.h * 100}%`,
                  boxShadow: '0 0 0 9999px rgba(0,0,0,0.45)',
                }}
              >
                <span className="absolute -top-5 left-0 rounded bg-primary px-1.5 py-0.5 text-[10px] font-medium text-primary-foreground whitespace-nowrap">
                  {isMarking ? 'Drawing focus…' : 'Ken Burns focus'}
                </span>
              </div>
            )}

            {!isLocked && (
              <div
                className="absolute left-2 top-2 flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100"
                onPointerDown={(event) => event.stopPropagation()}
              >
                <Button
                  type="button"
                  variant={isMarking ? 'default' : 'secondary'}
                  size="icon"
                  className="h-7 w-7"
                  onClick={toggleMarking}
                  aria-label={isMarking ? 'Cancel focus area marking' : 'Mark Ken Burns focus area'}
                  title={isMarking ? 'Cancel focus area marking' : 'Mark the subject area Ken Burns should keep in view'}
                >
                  <Scan className="h-3.5 w-3.5" />
                </Button>
                {area && (
                  <Button
                    type="button"
                    variant="secondary"
                    size="icon"
                    className="h-7 w-7"
                    onClick={clearFocusArea}
                    aria-label="Clear focus area"
                    title="Clear focus area"
                  >
                    <Focus className="h-3.5 w-3.5" />
                  </Button>
                )}
              </div>
            )}

            {!isLocked && (
              <div className="absolute left-2 bottom-2 flex items-center gap-1 rounded bg-black/55 px-1.5 py-0.5 text-[10px] text-white/90 opacity-0 transition-opacity group-hover:opacity-100">
                <Move className="h-3 w-3" />
                <span>{isMarking ? 'Drag to mark focus' : 'Drag to reposition'}</span>
              </div>
            )}
            {isRepositioned && !isLocked && (
              <Button
                type="button"
                variant="secondary"
                size="icon"
                className="absolute right-2 bottom-2 h-7 w-7 opacity-0 transition-opacity group-hover:opacity-100"
                onClick={resetFocus}
                aria-label="Center image in frame"
                title="Center image in frame"
              >
                <LocateFixed className="h-3.5 w-3.5" />
              </Button>
            )}
          </div>
          {!isLocked && (
            <Button
              variant="destructive"
              size="icon"
              className="absolute top-2 right-2 h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity"
              onClick={handleRemove}
              aria-label="Remove image"
            >
              <X className="h-4 w-4" />
            </Button>
          )}
        </div>
        {error && (
          <p className="text-xs text-destructive">{error}</p>
        )}
      </div>
    );
  }

  // State A — No image: show drop zone
  return (
    <div className="space-y-1">
      <div
        role="button"
        tabIndex={isLocked ? -1 : 0}
        onClick={handleZoneClick}
        onKeyDown={handleKeyDown}
        onDragEnter={onDragEnter}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        className={`flex flex-col items-center justify-center h-32 md:h-40 border-2 border-dashed rounded-md cursor-pointer transition-colors ${
          isLocked
            ? 'opacity-50 cursor-not-allowed border-muted'
            : isDraggingFile
              ? 'border-primary bg-primary/5'
              : 'border-muted-foreground/25 hover:border-primary/50'
        }`}
      >
        {isUploading ? (
          <p className="text-sm text-muted-foreground">Uploading...</p>
        ) : (
          <>
            <Upload className="h-8 w-8 text-muted-foreground mb-2" />
            <p className="text-sm text-muted-foreground">
              Drop image here or click to browse
            </p>
          </>
        )}
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handleFile(file);
        }}
      />

      {error && (
        <p className="text-xs text-destructive">{error}</p>
      )}
    </div>
  );
}
