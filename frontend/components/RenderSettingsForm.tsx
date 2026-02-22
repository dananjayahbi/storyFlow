'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import { Slider } from '@/components/ui/slider';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { Film, Info } from 'lucide-react';

// ── Props ──────────────────────────────────────────────────────────
interface RenderSettingsFormProps {
  /** Current zoom intensity value (1.0 – 2.0). */
  zoomIntensity: number;
  /** Called with partial settings update to persist changes. */
  onChange: (data: { zoom_intensity: number }) => Promise<void>;
}

// ── Component ──────────────────────────────────────────────────────

/**
 * Render settings form with an interactive zoom‐intensity slider
 * and read-only resolution / framerate displays.
 */
export function RenderSettingsForm({
  zoomIntensity,
  onChange,
}: RenderSettingsFormProps) {
  // ── Local slider state for responsive UI ──
  const [localZoom, setLocalZoom] = useState(zoomIntensity);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Sync local value when prop changes (e.g. after fetch)
  useEffect(() => {
    setLocalZoom(zoomIntensity);
  }, [zoomIntensity]);

  // Cleanup debounce timer on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  // ── Debounced slider handler ──
  const handleZoomChange = useCallback(
    (values: number[]) => {
      const value = values[0];
      setLocalZoom(value);

      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => {
        onChange({ zoom_intensity: value });
      }, 300);
    },
    [onChange],
  );

  return (
    <div className="space-y-4">
      {/* ── Section Header ── */}
      <div className="flex items-center gap-1.5">
        <Film className="h-4 w-4 text-muted-foreground" />
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Render Settings
        </h3>
      </div>

      {/* ── Zoom Intensity Slider ── */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <label className="text-xs text-muted-foreground font-medium">
            Zoom Intensity
          </label>
          <span className="text-xs font-medium tabular-nums">
            {localZoom.toFixed(1)}x
          </span>
        </div>
        <Slider
          value={[localZoom]}
          min={1.0}
          max={2.0}
          step={0.1}
          onValueChange={handleZoomChange}
        />
      </div>

      {/* ── Resolution (read-only) ── */}
      <div className="space-y-1">
        <div className="flex items-center gap-1">
          <label className="text-xs text-muted-foreground font-medium">
            Resolution
          </label>
          <TooltipProvider delayDuration={200}>
            <Tooltip>
              <TooltipTrigger asChild>
                <Info className="h-3 w-3 text-muted-foreground/60 cursor-help" />
              </TooltipTrigger>
              <TooltipContent side="top" className="text-xs max-w-[200px]">
                Resolution is not configurable in v1.0
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
        <p className="text-sm text-muted-foreground/70 select-none">
          1920 × 1080 (1080p)
        </p>
      </div>

      {/* ── Framerate (read-only) ── */}
      <div className="space-y-1">
        <label className="text-xs text-muted-foreground font-medium">
          Framerate
        </label>
        <p className="text-sm text-muted-foreground/70 select-none">30 fps</p>
      </div>
    </div>
  );
}
