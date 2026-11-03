'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { Upload, X, Move, LocateFixed } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

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
  onFocusChange?: (segmentId: string, focus: { x: number; y: number }) => Promise<void>;
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

export function ImageUploader({
  segmentId, currentImage, isLocked,
  frameWidth = 1920, frameHeight = 1080, focusX = 0.5, focusY = 0.5,
  onFocusChange, onUpload, onRemove,
}: ImageUploaderProps) {
  const [isDraggingFile, setIsDraggingFile] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isPanning, setIsPanning] = useState(false);
  const [focus, setFocus] = useState({ x: focusX, y: focusY });
  const dragCounterRef = useRef(0);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const frameRef = useRef<HTMLDivElement>(null);
  const imageRef = useRef<HTMLImageElement>(null);
  const dragRef = useRef<DragState | null>(null);
  const focusRef = useRef(focus);

  useEffect(() => {
    focusRef.current = focus;
  }, [focus]);

  const imageUrl = currentImage
    ? (currentImage.startsWith('http') ? currentImage : `${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8765'}${currentImage}`)
    : null;

  // Keep the local pan in sync when the segment/project changes.
  useEffect(() => {
    setFocus({ x: focusX, y: focusY });
  }, [focusX, focusY, segmentId, currentImage]);

  useEffect(() => {
    // New image or aspect ratio → any in-flight drag is stale.
    dragRef.current = null;
    setIsPanning(false);
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

  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (isLocked) return;
    e.preventDefault();
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

  const endPan = (e: React.PointerEvent<HTMLDivElement>) => {
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
            onPointerUp={endPan}
            onPointerCancel={endPan}
            style={{ aspectRatio: `${frameWidth || 16} / ${frameHeight || 9}`, touchAction: 'none' }}
            className={cn(
              'relative w-full overflow-hidden rounded-md border bg-muted select-none',
              !isLocked && 'cursor-grab',
              isPanning && 'cursor-grabbing',
            )}
            title={isLocked ? 'Unlock the segment to reposition the image' : 'Drag to reposition the image inside the render frame'}
            aria-label={`Render frame ${frameWidth}×${frameHeight}. Drag to reposition the image.`}
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

            {!isLocked && (
              <div className="absolute left-2 bottom-2 flex items-center gap-1 rounded bg-black/55 px-1.5 py-0.5 text-[10px] text-white/90 opacity-0 transition-opacity group-hover:opacity-100">
                <Move className="h-3 w-3" />
                <span>Drag to reposition</span>
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
