'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import {
  Upload, X, Move, LocateFixed, Scan, Focus, Crosshair, Play, RotateCcw, Eye,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import { Slider } from '@/components/ui/slider';
import { cn } from '@/lib/utils';
import { getApiBaseUrl } from '@/lib/apiConfig';
import {
  DEFAULT_KEN_BURNS_CONFIG,
  KEN_BURNS_ANIMATION_OPTIONS,
  KEN_BURNS_PAN_MODE_OPTIONS,
  animationLabel,
  animationUsesPan,
  animationUsesZoom,
  describeKenBurnsConfig,
  resolveKenBurnsConfig,
} from '@/lib/kenBurns';
import type { ImageFocusArea, KenBurnsConfig } from '@/lib/types';

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
  /** Legacy list form; only the first entry is used. */
  focusAreas?: ImageFocusArea[] | null;
  onFocusChange?: (segmentId: string, focus: { x: number; y: number }) => Promise<void>;
  /** Legacy single-area callback (used when no list callback is supplied). */
  onFocusAreaChange?: (segmentId: string, area: ImageFocusArea | null) => Promise<void>;
  onFocusAreasChange?: (segmentId: string, areas: ImageFocusArea[]) => Promise<void>;
  /** Optional per-segment manual Ken Burns override. */
  kenBurnsConfig?: KenBurnsConfig | null;
  onKenBurnsConfigChange?: (
    segmentId: string,
    config: KenBurnsConfig,
  ) => Promise<void>;
  /** Opens the modal that plays the animation exactly as the renderer will. */
  onRequestKenBurnsPreview?: () => void;
  onUpload: (segmentId: string, file: File) => Promise<void>;
  onRemove: (segmentId: string) => Promise<void>;
}

/** Which point/area the manual Ken Burns tool is currently picking. */
type KenBurnsTool = 'start' | 'end' | 'focal' | 'area' | null;

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
  focusArea = null, focusAreas = null,
  kenBurnsConfig = null, onKenBurnsConfigChange, onRequestKenBurnsPreview,
  onFocusChange, onFocusAreaChange, onFocusAreasChange, onUpload, onRemove,
}: ImageUploaderProps) {
  const [isDraggingFile, setIsDraggingFile] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isPanning, setIsPanning] = useState(false);
  const [isMarking, setIsMarking] = useState(false);
  const [selection, setSelection] = useState<ImageFocusArea | null>(null);
  const [focus, setFocus] = useState({ x: focusX, y: focusY });
  // Only one highlighted rectangle is supported per image.  Legacy projects
  // may still store a list; the first entry is shown and the rest are ignored.
  const initialArea = focusAreas?.[0] ?? focusArea ?? null;
  const [area, setArea] = useState<ImageFocusArea | null>(initialArea);
  // Manual Ken Burns editor state.  The stored config is mirrored locally so
  // dragging the tools feels instant; every change is also persisted.
  const [kbConfig, setKbConfig] = useState<KenBurnsConfig>(
    () => resolveKenBurnsConfig(kenBurnsConfig),
  );
  const [kbTool, setKbTool] = useState<KenBurnsTool>(null);
  const selectionModeRef = useRef<'focus' | 'kb' | null>(null);
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
    setArea(focusAreas?.[0] ?? focusArea ?? null);
  }, [focusAreas, focusArea, segmentId, currentImage]);

  useEffect(() => {
    setKbConfig(resolveKenBurnsConfig(kenBurnsConfig));
  }, [kenBurnsConfig, segmentId, currentImage]);

  useEffect(() => {
    // New image or aspect ratio → any in-flight drag is stale.
    dragRef.current = null;
    selectionRef.current = null;
    selectionModeRef.current = null;
    setSelection(null);
    setIsPanning(false);
    setIsMarking(false);
    setKbTool(null);
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

  const emitArea = (next: ImageFocusArea | null) => {
    setArea(next);
    if (onFocusAreasChange) {
      onFocusAreasChange(segmentId, next ? [next] : []).catch(() => {
        setError('Failed to save the focus area.');
      });
    } else if (onFocusAreaChange) {
      onFocusAreaChange(segmentId, next).catch(() => {
        setError('Failed to save the focus area.');
      });
    }
  };

  const emitKenBurns = (next: KenBurnsConfig) => {
    setKbConfig(next);
    if (onKenBurnsConfigChange) {
      onKenBurnsConfigChange(segmentId, next).catch(() => {
        setError('Failed to save the Ken Burns animation.');
      });
    }
  };

  const updateKenBurns = (patch: Partial<KenBurnsConfig>) => {
    emitKenBurns({ ...kbConfig, ...patch });
  };

  const resetKenBurns = () => {
    setKbTool(null);
    emitKenBurns({
      ...DEFAULT_KEN_BURNS_CONFIG,
      enabled: false,
    });
  };

  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (isLocked) return;
    e.preventDefault();

    // Manual Ken Burns tools take precedence: a click places the requested
    // point, or starts drawing the pan area rectangle.
    if (kbConfig.enabled && kbTool) {
      const point = framePoint(e);
      if (kbTool === 'start' || kbTool === 'end' || kbTool === 'focal') {
        const rounded = {
          x: Number(point.x.toFixed(4)),
          y: Number(point.y.toFixed(4)),
        };
        const key = kbTool === 'focal' ? 'focal_point' : kbTool;
        emitKenBurns({ ...kbConfig, [key]: rounded });
        setKbTool(null);
        return;
      }
      if (kbTool === 'area') {
        selectionModeRef.current = 'kb';
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
    }

    // Focus-area marking takes precedence over image panning.
    if (isMarking) {
      const point = framePoint(e);
      selectionModeRef.current = 'focus';
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
      const mode = selectionModeRef.current;
      selectionModeRef.current = null;
      setSelection(null);

      if (w >= MIN_FOCUS_AREA && h >= MIN_FOCUS_AREA) {
        const next = {
          x: Number(x.toFixed(4)),
          y: Number(y.toFixed(4)),
          w: Number(w.toFixed(4)),
          h: Number(h.toFixed(4)),
        };
        if (mode === 'kb') {
          setKbTool(null);
          emitKenBurns({
            ...kbConfig,
            pan_mode: 'area',
            area: next,
          });
        } else {
          setIsMarking(false);
          // Drawing again replaces the existing rectangle.
          emitArea(next);
        }
      } else {
        setError(
          mode === 'kb'
            ? 'Draw a larger area for the pan.'
            : 'Draw a larger area to mark the focus.',
        );
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
    setIsMarking(false);
    setSelection(null);
    emitArea(null);
  };

  const toggleMarking = () => {
    if (isLocked) return;
    setError(null);
    setIsMarking((previous) => !previous);
    setSelection(null);
    selectionRef.current = null;
  };

  const shownArea = selection;

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
              !isLocked && !isMarking && !kbTool && 'cursor-grab',
              isPanning && 'cursor-grabbing',
              (isMarking || kbTool) && 'cursor-crosshair',
            )}
            title={
              isLocked
                ? 'Unlock the segment to edit the image'
                : kbTool
                  ? kbTool === 'area'
                    ? 'Drag to draw the pan area'
                    : 'Click to place the Ken Burns point'
                  : isMarking
                    ? 'Drag to mark the Ken Burns focus area'
                    : 'Drag to reposition the image inside the render frame'
            }
            aria-label={`Render frame ${frameWidth}×${frameHeight}. ${
              kbTool
                ? 'Click to place the Ken Burns point.'
                : isMarking
                  ? 'Drag to mark the Ken Burns focus area.'
                  : 'Drag to reposition the image.'
            }`}
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

            {/* Marked Ken Burns focus area (one per image) */}
            {area && (
              <div
                className="pointer-events-none absolute border-2 border-primary bg-primary/15"
                style={{
                  left: `${area.x * 100}%`,
                  top: `${area.y * 100}%`,
                  width: `${area.w * 100}%`,
                  height: `${area.h * 100}%`,
                }}
              >
                <span className="absolute -top-5 left-0 rounded bg-primary px-1.5 py-0.5 text-[10px] font-medium text-primary-foreground whitespace-nowrap">
                  Ken Burns focus
                </span>
              </div>
            )}

            {/* Manual Ken Burns overlays */}
            {kbConfig.enabled && animationUsesPan(kbConfig.animation) && (
              <>
                {kbConfig.pan_mode === 'points' && (
                  <>
                    <svg
                      className="pointer-events-none absolute inset-0 h-full w-full text-primary"
                      viewBox="0 0 100 100"
                      preserveAspectRatio="none"
                      aria-hidden="true"
                    >
                      <line
                        x1={kbConfig.start.x * 100}
                        y1={kbConfig.start.y * 100}
                        x2={kbConfig.end.x * 100}
                        y2={kbConfig.end.y * 100}
                        stroke="currentColor"
                        strokeWidth={1.5}
                        strokeDasharray="4 3"
                        vectorEffect="non-scaling-stroke"
                      />
                    </svg>
                    {([
                      ['start', kbConfig.start, 'A', 'Pan start point'],
                      ['end', kbConfig.end, 'B', 'Pan end point'],
                    ] as const).map(([key, point, label, title]) => (
                      <div
                        key={key}
                        className="pointer-events-none absolute flex h-5 w-5 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border-2 border-white bg-primary text-[9px] font-bold text-primary-foreground shadow"
                        style={{
                          left: `${point.x * 100}%`,
                          top: `${point.y * 100}%`,
                        }}
                        title={`${title} (${Math.round(point.x * 100)}%, ${Math.round(point.y * 100)}%)`}
                      >
                        {label}
                      </div>
                    ))}
                  </>
                )}
                {kbConfig.pan_mode === 'area' && kbConfig.area && (
                  <div
                    className="pointer-events-none absolute border-2 border-dashed border-primary bg-primary/5"
                    style={{
                      left: `${kbConfig.area.x * 100}%`,
                      top: `${kbConfig.area.y * 100}%`,
                      width: `${kbConfig.area.w * 100}%`,
                      height: `${kbConfig.area.h * 100}%`,
                    }}
                  >
                    <span className="absolute -top-5 left-0 whitespace-nowrap rounded bg-primary px-1.5 py-0.5 text-[10px] font-medium text-primary-foreground">
                      Pan area
                    </span>
                  </div>
                )}
              </>
            )}

            {kbConfig.enabled && animationUsesZoom(kbConfig.animation) && (
              <div
                className="pointer-events-none absolute -translate-x-1/2 -translate-y-1/2"
                style={{
                  left: `${kbConfig.focal_point.x * 100}%`,
                  top: `${kbConfig.focal_point.y * 100}%`,
                }}
                title={`Zoom focal point (${Math.round(kbConfig.focal_point.x * 100)}%, ${Math.round(kbConfig.focal_point.y * 100)}%)`}
              >
                <span className="absolute -inset-3 rounded-full border border-primary/70" />
                <span className="absolute left-1/2 top-1/2 h-1.5 w-1.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-primary ring-2 ring-white" />
                <Crosshair className="h-5 w-5 text-primary drop-shadow" />
              </div>
            )}

            {/* Live selection while marking a new area */}
            {shownArea && shownArea.w > 0 && shownArea.h > 0 && (
              <div
                className="pointer-events-none absolute border-2 border-amber-300 bg-amber-300/20"
                style={{
                  left: `${shownArea.x * 100}%`,
                  top: `${shownArea.y * 100}%`,
                  width: `${shownArea.w * 100}%`,
                  height: `${shownArea.h * 100}%`,
                  boxShadow: '0 0 0 9999px rgba(0,0,0,0.45)',
                }}
              >
                <span className="absolute -top-5 left-0 rounded bg-primary px-1.5 py-0.5 text-[10px] font-medium text-primary-foreground whitespace-nowrap">
                  Drawing focus…
                </span>
              </div>
            )}

            {kbConfig.enabled && kbTool && (
              <div
                className="absolute left-1/2 top-2 z-10 flex -translate-x-1/2 items-center gap-1.5 rounded-full bg-black/70 px-2.5 py-1 text-[10px] text-white shadow"
                onPointerDown={(event) => event.stopPropagation()}
              >
                <Crosshair className="h-3 w-3" />
                <span>
                  {kbTool === 'area'
                    ? 'Drag to draw the pan area'
                    : kbTool === 'focal'
                      ? 'Click to place the zoom focal point'
                      : kbTool === 'start'
                        ? 'Click to place the pan start point'
                        : 'Click to place the pan end point'}
                </span>
                <button
                  type="button"
                  className="ml-1 rounded px-1 text-white/80 hover:bg-white/20 hover:text-white"
                  onClick={() => setKbTool(null)}
                >
                  Cancel
                </button>
              </div>
            )}

            {!isLocked && !kbConfig.enabled && (
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
                    title="Clear the focus area"
                  >
                    <Focus className="h-3.5 w-3.5" />
                  </Button>
                )}
              </div>
            )}

            {!isLocked && (
              <div className="absolute left-2 bottom-2 flex items-center gap-1 rounded bg-black/55 px-1.5 py-0.5 text-[10px] text-white/90 opacity-0 transition-opacity group-hover:opacity-100">
                <Move className="h-3 w-3" />
                <span>
                  {kbTool
                    ? 'Click to place point'
                    : isMarking
                      ? 'Drag to mark focus'
                      : 'Drag to reposition'}
                </span>
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
        {/* Manual Ken Burns controls */}
        <div className="space-y-2 rounded-md border bg-muted/20 p-2">
          <div className="flex items-center justify-between gap-2">
            <label className="flex cursor-pointer items-center gap-2 text-[11px] font-medium">
              <Checkbox
                checked={kbConfig.enabled}
                disabled={isLocked}
                onCheckedChange={(checked) => {
                  setKbTool(null);
                  emitKenBurns({ ...kbConfig, enabled: checked === true });
                }}
                aria-label="Manual Ken Burns"
              />
              Manual Ken Burns
            </label>
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] text-muted-foreground">
                {kbConfig.enabled
                  ? animationLabel(kbConfig.animation)
                  : 'Automatic'}
              </span>
              {onRequestKenBurnsPreview && (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="h-6 gap-1 px-2 text-[10px]"
                  onClick={onRequestKenBurnsPreview}
                  aria-label="Preview Ken Burns animation"
                  title="Preview the animation exactly as it will render"
                >
                  <Eye className="h-3 w-3" />
                  Preview
                </Button>
              )}
            </div>
          </div>
          <p className="text-[10px] text-muted-foreground">
            {describeKenBurnsConfig(kbConfig)}
          </p>

          {kbConfig.enabled && (
            <div className="space-y-2">
              <Select
                value={kbConfig.animation}
                disabled={isLocked}
                onValueChange={(value) => {
                  setKbTool(null);
                  emitKenBurns({
                    ...kbConfig,
                    animation: value as KenBurnsConfig['animation'],
                  });
                }}
              >
                <SelectTrigger
                  size="sm"
                  className="h-8 w-full text-xs"
                  aria-label="Ken Burns animation"
                >
                  <SelectValue placeholder="Choose animation" />
                </SelectTrigger>
                <SelectContent>
                  {KEN_BURNS_ANIMATION_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      <div className="flex flex-col">
                        <span>{option.label}</span>
                        <span className="text-[10px] text-muted-foreground">
                          {option.description}
                        </span>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              {animationUsesPan(kbConfig.animation) && (
                <div className="space-y-1.5">
                  <div className="flex gap-1">
                    {KEN_BURNS_PAN_MODE_OPTIONS.map((option) => (
                      <Button
                        key={option.value}
                        type="button"
                        size="sm"
                        variant={
                          kbConfig.pan_mode === option.value
                            ? 'default'
                            : 'outline'
                        }
                        className="h-7 flex-1 px-2 text-[10px]"
                        disabled={isLocked}
                        onClick={() => {
                          setKbTool(null);
                          emitKenBurns({
                            ...kbConfig,
                            pan_mode: option.value,
                          });
                        }}
                      >
                        {option.label}
                      </Button>
                    ))}
                  </div>
                  {kbConfig.pan_mode === 'points' ? (
                    <div className="flex gap-1">
                      <Button
                        type="button"
                        size="sm"
                        variant={kbTool === 'start' ? 'default' : 'outline'}
                        className="h-7 flex-1 px-2 text-[10px]"
                        disabled={isLocked}
                        onClick={() => setKbTool(kbTool === 'start' ? null : 'start')}
                      >
                        <Play className="mr-1 h-3 w-3" />
                        Set start
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant={kbTool === 'end' ? 'default' : 'outline'}
                        className="h-7 flex-1 px-2 text-[10px]"
                        disabled={isLocked}
                        onClick={() => setKbTool(kbTool === 'end' ? null : 'end')}
                      >
                        <Play className="mr-1 h-3 w-3 rotate-180" />
                        Set end
                      </Button>
                    </div>
                  ) : (
                    <div className="flex gap-1">
                      <Button
                        type="button"
                        size="sm"
                        variant={kbTool === 'area' ? 'default' : 'outline'}
                        className="h-7 flex-1 px-2 text-[10px]"
                        disabled={isLocked}
                        onClick={() => setKbTool(kbTool === 'area' ? null : 'area')}
                      >
                        <Scan className="mr-1 h-3 w-3" />
                        {kbConfig.area ? 'Redraw pan area' : 'Draw pan area'}
                      </Button>
                      {kbConfig.area && (
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          className="h-7 px-2 text-[10px]"
                          disabled={isLocked}
                          onClick={() => {
                            setKbTool(null);
                            emitKenBurns({ ...kbConfig, area: null });
                          }}
                        >
                          Clear
                        </Button>
                      )}
                    </div>
                  )}
                </div>
              )}

              {animationUsesZoom(kbConfig.animation) && (
                <div className="space-y-1.5">
                  {kbConfig.animation !== 'pan_zoom' && (
                    <Button
                      type="button"
                      size="sm"
                      variant={kbTool === 'focal' ? 'default' : 'outline'}
                      className="h-7 w-full px-2 text-[10px]"
                      disabled={isLocked}
                      onClick={() => setKbTool(kbTool === 'focal' ? null : 'focal')}
                    >
                      <Crosshair className="mr-1 h-3 w-3" />
                      Set focal point
                    </Button>
                  )}
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] text-muted-foreground">Zoom</span>
                    <Slider
                      min={1}
                      max={2}
                      step={0.05}
                      value={[kbConfig.zoom]}
                      disabled={isLocked}
                      onValueChange={(values) =>
                        updateKenBurns({ zoom: values[0] ?? 1.25 })
                      }
                      aria-label="Ken Burns zoom strength"
                    />
                    <span className="w-9 text-right text-[10px] tabular-nums text-muted-foreground">
                      {kbConfig.zoom.toFixed(2)}x
                    </span>
                  </div>
                </div>
              )}

              <div className="flex items-start justify-between gap-2">
                <p className="text-[10px] text-amber-600 dark:text-amber-400">
                  Generate the TTS first — the animation speed adapts to the
                  narration duration.
                </p>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  className="h-6 shrink-0 px-1.5 text-[10px]"
                  disabled={isLocked}
                  onClick={resetKenBurns}
                >
                  <RotateCcw className="mr-1 h-3 w-3" />
                  Auto
                </Button>
              </div>
            </div>
          )}
        </div>

        {!isLocked && !kbConfig.enabled && area && (
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-1">
              <span className="inline-flex items-center gap-1 rounded border bg-muted/40 px-1.5 py-0.5 text-[10px] text-muted-foreground">
                Focus area
                <button
                  type="button"
                  onClick={clearFocusArea}
                  className="rounded p-0.5 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                  aria-label="Remove focus area"
                  title="Remove focus area"
                >
                  <X className="h-2.5 w-2.5" />
                </button>
              </span>
            </div>
            <p className="text-[10px] text-muted-foreground">
              Ken Burns keeps this area in frame (up to 10% may leave the
              edge) and adapts the pan or zoom speed to the space around it.
            </p>
          </div>
        )}
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
