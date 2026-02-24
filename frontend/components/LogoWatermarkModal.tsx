'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import { useSettingsStore } from '@/lib/stores';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Slider } from '@/components/ui/slider';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Loader2, Check, ImageOff } from 'lucide-react';
import { toast } from 'sonner';

// ── Props ──────────────────────────────────────────────────────────
interface LogoWatermarkModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Current render resolution for preview aspect ratio. */
  renderWidth: number;
  renderHeight: number;
}

// ── Position labels ────────────────────────────────────────────────
const POSITION_OPTIONS = [
  { value: 'top-left', label: 'Top Left' },
  { value: 'top-right', label: 'Top Right' },
  { value: 'bottom-left', label: 'Bottom Left' },
  { value: 'bottom-right', label: 'Bottom Right' },
] as const;

// ── Component ──────────────────────────────────────────────────────

export function LogoWatermarkModal({
  open,
  onOpenChange,
  renderWidth,
  renderHeight,
}: LogoWatermarkModalProps) {
  const {
    logos,
    isLogosLoading,
    fetchLogos,
    globalSettings,
    updateSettings,
  } = useSettingsStore();

  // Local state for the modal controls
  const [selectedLogoId, setSelectedLogoId] = useState<string | null>(null);
  const [scale, setScale] = useState(0.15);
  const [position, setPosition] = useState<string>('bottom-right');
  const [opacity, setOpacity] = useState(1.0);
  const [margin, setMargin] = useState(20);
  const [isSaving, setIsSaving] = useState(false);

  // Load logos and sync state when modal opens
  useEffect(() => {
    if (open) {
      fetchLogos();
      if (globalSettings) {
        setSelectedLogoId(globalSettings.active_logo ?? null);
        setScale(globalSettings.logo_scale ?? 0.15);
        setPosition(globalSettings.logo_position ?? 'bottom-right');
        setOpacity(globalSettings.logo_opacity ?? 1.0);
        setMargin(globalSettings.logo_margin ?? 20);
      }
    }
  }, [open, fetchLogos, globalSettings]);

  // Find the selected logo object
  const selectedLogo = useMemo(
    () => logos.find((l) => l.id === selectedLogoId) ?? null,
    [logos, selectedLogoId],
  );

  // Preview dimensions (fit within 320px wide)
  const previewMaxW = 320;
  const aspectRatio = renderWidth / renderHeight;
  const previewW = aspectRatio >= 1 ? previewMaxW : Math.round(previewMaxW * aspectRatio);
  const previewH = aspectRatio >= 1 ? Math.round(previewMaxW / aspectRatio) : previewMaxW;

  // Logo preview size and position
  const logoPreviewW = Math.round(previewW * scale);
  const marginPx = Math.round((margin / renderWidth) * previewW);

  const logoStyle = useMemo(() => {
    const style: React.CSSProperties = {
      width: logoPreviewW,
      opacity,
      position: 'absolute',
    };

    if (position === 'top-left') {
      style.top = marginPx;
      style.left = marginPx;
    } else if (position === 'top-right') {
      style.top = marginPx;
      style.right = marginPx;
    } else if (position === 'bottom-left') {
      style.bottom = marginPx;
      style.left = marginPx;
    } else {
      style.bottom = marginPx;
      style.right = marginPx;
    }

    return style;
  }, [logoPreviewW, opacity, position, marginPx]);

  // Save handler
  const handleSave = useCallback(async () => {
    setIsSaving(true);
    try {
      await updateSettings({
        logo_enabled: !!selectedLogoId,
        active_logo: selectedLogoId,
        logo_scale: scale,
        logo_position: position as 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right',
        logo_opacity: opacity,
        logo_margin: margin,
      });
      toast.success('Logo watermark settings saved');
      onOpenChange(false);
    } catch {
      toast.error('Failed to save logo settings');
    } finally {
      setIsSaving(false);
    }
  }, [selectedLogoId, scale, position, opacity, margin, updateSettings, onOpenChange]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle>Logo Watermark</DialogTitle>
          <DialogDescription>
            Select a logo and adjust its size, position, and opacity for the video output.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-5 pt-2">
          {/* ── Logo Selector ── */}
          <div className="space-y-2">
            <label className="text-sm font-medium">Select Logo</label>
            {isLogosLoading ? (
              <div className="flex items-center gap-2 text-muted-foreground text-sm">
                <Loader2 className="h-4 w-4 animate-spin" />
                Loading…
              </div>
            ) : logos.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No logos uploaded. Go to Settings → Logo Management to upload logos.
              </p>
            ) : (
              <div className="grid grid-cols-4 gap-2">
                {/* None option */}
                <button
                  onClick={() => setSelectedLogoId(null)}
                  className={`border rounded-lg p-2 flex flex-col items-center gap-1 transition-colors ${
                    selectedLogoId === null
                      ? 'border-primary bg-primary/5'
                      : 'border-muted hover:border-muted-foreground/30'
                  }`}
                >
                  <div className="w-full aspect-square rounded flex items-center justify-center bg-muted/30">
                    <ImageOff className="h-6 w-6 text-muted-foreground/50" />
                  </div>
                  <span className="text-[10px] text-muted-foreground">None</span>
                </button>

                {logos.map((logo) => (
                  <button
                    key={logo.id}
                    onClick={() => setSelectedLogoId(logo.id)}
                    className={`relative border rounded-lg p-2 flex flex-col items-center gap-1 transition-colors ${
                      selectedLogoId === logo.id
                        ? 'border-primary bg-primary/5'
                        : 'border-muted hover:border-muted-foreground/30'
                    }`}
                  >
                    <div className="w-full aspect-square rounded flex items-center justify-center overflow-hidden bg-muted/30">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={`http://localhost:8000${logo.file}`}
                        alt={logo.name}
                        className="max-w-full max-h-full object-contain"
                      />
                    </div>
                    <span className="text-[10px] text-muted-foreground truncate w-full text-center">
                      {logo.name}
                    </span>
                    {selectedLogoId === logo.id && (
                      <Check className="absolute top-1 right-1 h-3 w-3 text-primary" />
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* ── Controls (only show if a logo is selected) ── */}
          {selectedLogoId && (
            <>
              {/* Scale Slider */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label className="text-sm font-medium">Size</label>
                  <span className="text-xs font-medium tabular-nums">
                    {Math.round(scale * 100)}%
                  </span>
                </div>
                <Slider
                  value={[scale]}
                  min={0.05}
                  max={0.50}
                  step={0.01}
                  onValueChange={(v) => setScale(v[0])}
                />
              </div>

              {/* Position */}
              <div className="space-y-1.5">
                <label className="text-sm font-medium">Position</label>
                <Select value={position} onValueChange={setPosition}>
                  <SelectTrigger className="h-9">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {POSITION_OPTIONS.map((opt) => (
                      <SelectItem key={opt.value} value={opt.value}>
                        {opt.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Opacity Slider */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label className="text-sm font-medium">Opacity</label>
                  <span className="text-xs font-medium tabular-nums">
                    {Math.round(opacity * 100)}%
                  </span>
                </div>
                <Slider
                  value={[opacity]}
                  min={0.1}
                  max={1.0}
                  step={0.05}
                  onValueChange={(v) => setOpacity(v[0])}
                />
              </div>

              {/* Margin Slider */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label className="text-sm font-medium">Margin</label>
                  <span className="text-xs font-medium tabular-nums">
                    {margin}px
                  </span>
                </div>
                <Slider
                  value={[margin]}
                  min={0}
                  max={100}
                  step={5}
                  onValueChange={(v) => setMargin(v[0])}
                />
              </div>

              {/* ── Live Preview ── */}
              <div className="space-y-1.5">
                <label className="text-sm font-medium">Preview</label>
                <div
                  className="relative bg-muted/50 border rounded-lg mx-auto overflow-hidden"
                  style={{ width: previewW, height: previewH }}
                >
                  {/* Resolution label */}
                  <span className="absolute top-1 left-1 text-[9px] text-muted-foreground/60">
                    {renderWidth}×{renderHeight}
                  </span>

                  {/* Logo preview */}
                  {selectedLogo && (
                    /* eslint-disable-next-line @next/next/no-img-element */
                    <img
                      src={`http://localhost:8000${selectedLogo.file}`}
                      alt="Logo preview"
                      style={logoStyle}
                      className="pointer-events-none"
                    />
                  )}
                </div>
              </div>
            </>
          )}

          {/* ── Save / Cancel ── */}
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button onClick={handleSave} disabled={isSaving}>
              {isSaving ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Saving…
                </>
              ) : (
                'Save'
              )}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
