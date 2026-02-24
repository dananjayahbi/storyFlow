'use client';

import { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import { Slider } from '@/components/ui/slider';
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Film, Monitor, Smartphone, Square } from 'lucide-react';
import { VALIDATION } from '@/lib/constants';

// ── Props ──────────────────────────────────────────────────────────
interface RenderSettingsFormProps {
  /** Current zoom intensity value (1.0 – 2.0). */
  zoomIntensity: number;
  /** Current render width. */
  renderWidth: number;
  /** Current render height. */
  renderHeight: number;
  /** Current render FPS. */
  renderFps: number;
  /** Called with partial settings update to persist changes. */
  onChange: (data: { zoom_intensity?: number; render_width?: number; render_height?: number; render_fps?: number }) => Promise<void>;
}

// ── Helpers ────────────────────────────────────────────────────────

/** Build a unique key from width × height for Select value matching. */
function resolutionKey(w: number, h: number): string {
  return `${w}x${h}`;
}

/** Category icons */
const categoryIcons = {
  landscape: Monitor,
  portrait: Smartphone,
  square: Square,
} as const;

const categoryLabels = {
  landscape: 'Landscape',
  portrait: 'Portrait',
  square: 'Square',
} as const;

// ── Component ──────────────────────────────────────────────────────

/**
 * Render settings form with an interactive zoom‐intensity slider
 * and resolution selector supporting multiple aspect ratios.
 */
/** Available FPS options. */
const FPS_OPTIONS = [24, 30, 60] as const;

export function RenderSettingsForm({
  zoomIntensity,
  renderWidth,
  renderHeight,
  renderFps,
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

  // ── Resolution selector handler ──
  const handleResolutionChange = useCallback(
    (value: string) => {
      const [w, h] = value.split('x').map(Number);
      if (w && h) {
        onChange({ render_width: w, render_height: h });
      }
    },
    [onChange],
  );

  // Group presets by category
  const groupedPresets = useMemo(() => {
    const groups: Record<string, typeof VALIDATION.RESOLUTION_PRESETS[number][]> = {};
    for (const preset of VALIDATION.RESOLUTION_PRESETS) {
      if (!groups[preset.category]) groups[preset.category] = [];
      groups[preset.category].push(preset);
    }
    return groups;
  }, []);

  // Current resolution key
  const currentKey = resolutionKey(renderWidth, renderHeight);

  // Find current preset label for display
  const currentPreset = VALIDATION.RESOLUTION_PRESETS.find(
    (p) => p.width === renderWidth && p.height === renderHeight
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

      {/* ── Resolution Selector ── */}
      <div className="space-y-1.5">
        <label className="text-xs text-muted-foreground font-medium">
          Resolution
        </label>
        <Select value={currentKey} onValueChange={handleResolutionChange}>
          <SelectTrigger className="h-9 text-sm">
            <SelectValue placeholder="Select resolution">
              {currentPreset
                ? `${currentPreset.label} (${currentPreset.aspect})`
                : `${renderWidth} × ${renderHeight}`}
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            {(['landscape', 'portrait', 'square'] as const).map((cat) => {
              const presets = groupedPresets[cat];
              if (!presets?.length) return null;
              const Icon = categoryIcons[cat];
              return (
                <SelectGroup key={cat}>
                  <SelectLabel className="flex items-center gap-1.5 text-xs">
                    <Icon className="h-3 w-3" />
                    {categoryLabels[cat]}
                  </SelectLabel>
                  {presets.map((p) => (
                    <SelectItem
                      key={resolutionKey(p.width, p.height)}
                      value={resolutionKey(p.width, p.height)}
                    >
                      <span className="flex items-center justify-between gap-3 w-full">
                        <span>{p.label}</span>
                        <span className="text-muted-foreground text-xs">
                          {p.width}×{p.height} · {p.aspect}
                        </span>
                      </span>
                    </SelectItem>
                  ))}
                </SelectGroup>
              );
            })}
          </SelectContent>
        </Select>
        <p className="text-[10px] text-muted-foreground">
          Choose aspect ratio for your target platform
        </p>
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

      {/* ── Framerate Selector ── */}
      <div className="space-y-1.5">
        <label className="text-xs text-muted-foreground font-medium">
          Framerate
        </label>
        <Select
          value={String(renderFps)}
          onValueChange={(value) => onChange({ render_fps: Number(value) })}
        >
          <SelectTrigger className="h-9 text-sm">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {FPS_OPTIONS.map((f) => (
              <SelectItem key={f} value={String(f)}>
                {f} fps{f === 60 ? ' (smooth)' : f === 24 ? ' (cinematic)' : ''}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}
