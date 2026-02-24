'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { useSettingsStore } from '@/lib/stores';
import { Slider } from '@/components/ui/slider';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { VoiceSelector } from '@/components/VoiceSelector';
import { SubtitleSettingsForm } from '@/components/SubtitleSettingsForm';
import { RenderSettingsForm } from '@/components/RenderSettingsForm';
import { LogoWatermarkModal } from '@/components/LogoWatermarkModal';
import {
  Settings,
  ChevronDown,
  ChevronRight,
  Volume2,
  RefreshCw,
  Timer,
  Captions,
  Stamp,
} from 'lucide-react';
import { toast } from 'sonner';

// ── LocalStorage key for collapsed state persistence ──
const COLLAPSED_KEY = 'storyflow-settings-collapsed';

function getInitialCollapsed(): boolean {
  if (typeof window === 'undefined') return false;
  try {
    return localStorage.getItem(COLLAPSED_KEY) === 'true';
  } catch {
    return false;
  }
}

export function GlobalSettingsPanel() {
  const {
    globalSettings,
    isSettingsLoading,
    settingsError,
    fetchSettings,
    updateSettings,
  } = useSettingsStore();

  const [isCollapsed, setIsCollapsed] = useState(getInitialCollapsed);

  // Debounce timer ref for TTS speed slider
  const speedTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Debounce timer ref for inter-segment silence slider
  const silenceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Local slider value for responsive UI (updated immediately, saved after debounce)
  const [localSpeed, setLocalSpeed] = useState<number | null>(null);
  const [localSilence, setLocalSilence] = useState<number | null>(null);

  // Logo watermark modal state
  const [isLogoModalOpen, setIsLogoModalOpen] = useState(false);

  // Fetch settings on mount
  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  // Sync local slider value when globalSettings loads/changes
  useEffect(() => {
    if (globalSettings) {
      setLocalSpeed(globalSettings.tts_speed);
      setLocalSilence(globalSettings.inter_segment_silence);
    }
  }, [globalSettings]);

  // Persist collapsed state to localStorage
  const toggleCollapsed = useCallback(() => {
    setIsCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(COLLAPSED_KEY, String(next));
      } catch {
        // localStorage unavailable — no-op
      }
      return next;
    });
  }, []);

  // Shared handler: wraps updateSettings with toast feedback
  const handleSettingChange = useCallback(
    async (data: Parameters<typeof updateSettings>[0]) => {
      try {
        await updateSettings(data);
        toast.success('Settings saved successfully');
      } catch {
        toast.error('Failed to save settings');
      }
    },
    [updateSettings]
  );

  // ── TTS Speed slider with debounce ──
  const handleSpeedChange = useCallback(
    (values: number[]) => {
      const value = values[0];
      setLocalSpeed(value);

      if (speedTimerRef.current) {
        clearTimeout(speedTimerRef.current);
      }
      speedTimerRef.current = setTimeout(() => {
        handleSettingChange({ tts_speed: value });
      }, 300);
    },
    [handleSettingChange]
  );

  // ── Inter-segment silence slider with debounce ──
  const handleSilenceChange = useCallback(
    (values: number[]) => {
      const value = values[0];
      setLocalSilence(value);

      if (silenceTimerRef.current) {
        clearTimeout(silenceTimerRef.current);
      }
      silenceTimerRef.current = setTimeout(() => {
        handleSettingChange({ inter_segment_silence: value });
      }, 300);
    },
    [handleSettingChange]
  );

  // Cleanup debounce timer on unmount
  useEffect(() => {
    return () => {
      if (speedTimerRef.current) clearTimeout(speedTimerRef.current);
      if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
    };
  }, []);

  // ── Loading skeleton ──
  if (isSettingsLoading) {
    return (
      <div className="p-4">
        <div className="flex items-center gap-2 mb-4">
          <Skeleton className="h-5 w-5" />
          <Skeleton className="h-5 w-24" />
        </div>
        <div className="space-y-6">
          <div className="space-y-3">
            <Skeleton className="h-4 w-20" />
            <Skeleton className="h-9 w-full" />
            <Skeleton className="h-4 w-16" />
            <Skeleton className="h-6 w-full" />
          </div>
          <Skeleton className="h-px w-full" />
          <div className="space-y-3">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-6 w-full" />
          </div>
          <Skeleton className="h-px w-full" />
          <div className="space-y-3">
            <Skeleton className="h-4 w-20" />
            <Skeleton className="h-9 w-full" />
            <Skeleton className="h-9 w-full" />
          </div>
        </div>
      </div>
    );
  }

  // ── Error state ──
  if (settingsError || !globalSettings) {
    return (
      <div className="p-4">
        <div className="flex items-center gap-2 mb-4">
          <Settings className="h-5 w-5 text-muted-foreground" />
          <span className="font-medium text-sm">Settings</span>
        </div>
        <p className="text-sm text-destructive mb-3">
          {settingsError || 'Failed to load settings'}
        </p>
        <Button size="sm" variant="outline" onClick={fetchSettings}>
          <RefreshCw className="h-4 w-4 mr-1" />
          Retry
        </Button>
      </div>
    );
  }

  return (
    <div className="p-4">
      {/* ── Collapsible Header ── */}
      <button
        onClick={toggleCollapsed}
        className="flex items-center gap-2 w-full text-left mb-4 hover:opacity-80 transition-opacity"
      >
        <Settings className="h-5 w-5 text-muted-foreground" />
        <span className="font-medium text-sm flex-1">Settings</span>
        {isCollapsed ? (
          <ChevronRight className="h-4 w-4 text-muted-foreground" />
        ) : (
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        )}
      </button>

      {/* ── Expanded Panel Body ── */}
      {!isCollapsed && (
        <div className="space-y-6">
          {/* ── Voice Settings Section ── */}
          <section>
            {/* Voice Selector (Task 05.03.02) */}
            <VoiceSelector
              value={globalSettings.default_voice_id}
              onChange={handleSettingChange}
            />

            {/* TTS Speed Slider */}
            <div className="space-y-1.5 mt-3">
              <div className="flex items-center justify-between">
                <label className="text-xs text-muted-foreground">
                  TTS Speed
                </label>
                <span className="text-xs font-medium tabular-nums">
                  {(localSpeed ?? globalSettings.tts_speed).toFixed(1)}x
                </span>
              </div>
              <Slider
                value={[localSpeed ?? globalSettings.tts_speed]}
                min={0.5}
                max={2.0}
                step={0.1}
                onValueChange={handleSpeedChange}
              />
            </div>
          </section>

          <Separator />

          {/* ── Timing Settings Section ── */}
          <section>
            <div className="flex items-center gap-1.5 mb-3">
              <Timer className="h-4 w-4 text-muted-foreground" />
              <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Timing
              </h3>
            </div>

            {/* Inter-segment Silence Slider */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="text-xs text-muted-foreground">
                  Pause Between Segments
                </label>
                <span className="text-xs font-medium tabular-nums">
                  {(localSilence ?? globalSettings.inter_segment_silence).toFixed(1)}s
                </span>
              </div>
              <Slider
                value={[localSilence ?? globalSettings.inter_segment_silence]}
                min={0}
                max={3.0}
                step={0.1}
                onValueChange={handleSilenceChange}
              />
              <p className="text-[10px] text-muted-foreground">
                Silence gap between narration segments in the final video
              </p>
            </div>
          </section>

          <Separator />

          {/* ── Render Settings Section (Task 05.03.05) ── */}
          <section>
            <RenderSettingsForm
              zoomIntensity={globalSettings.zoom_intensity}
              renderWidth={globalSettings.render_width ?? 1920}
              renderHeight={globalSettings.render_height ?? 1080}
              renderFps={globalSettings.render_fps ?? 30}
              onChange={handleSettingChange}
            />
          </section>

          <Separator />

          {/* ── Logo Watermark Section ── */}
          <section>
            <div className="flex items-center gap-1.5 mb-3">
              <Stamp className="h-4 w-4 text-muted-foreground" />
              <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex-1">
                Watermark
              </h3>
              <label className="flex items-center gap-2 cursor-pointer">
                <span className="text-xs text-muted-foreground">
                  {globalSettings.logo_enabled ? 'On' : 'Off'}
                </span>
                <input
                  type="checkbox"
                  checked={globalSettings.logo_enabled ?? false}
                  onChange={(e) =>
                    handleSettingChange({ logo_enabled: e.target.checked })
                  }
                  className="h-4 w-4 rounded border-muted-foreground accent-primary cursor-pointer"
                />
              </label>
            </div>

            <Button
              variant="outline"
              size="sm"
              className="w-full"
              onClick={() => setIsLogoModalOpen(true)}
            >
              <Stamp className="h-4 w-4 mr-2" />
              Configure Watermark
            </Button>

            {globalSettings.logo_enabled && globalSettings.active_logo && (
              <p className="text-[10px] text-muted-foreground mt-1.5">
                Logo will be placed at{' '}
                <span className="font-medium">
                  {globalSettings.logo_position?.replace('-', ' ') ?? 'bottom right'}
                </span>{' '}
                with {Math.round((globalSettings.logo_opacity ?? 1) * 100)}% opacity
              </p>
            )}

            <LogoWatermarkModal
              open={isLogoModalOpen}
              onOpenChange={setIsLogoModalOpen}
              renderWidth={globalSettings.render_width ?? 1920}
              renderHeight={globalSettings.render_height ?? 1080}
            />
          </section>

          <Separator />

          {/* ── Subtitle Settings Section (Task 05.03.03) ── */}
          <section>
            {/* Subtitles enabled toggle */}
            <div className="flex items-center gap-1.5 mb-3">
              <Captions className="h-4 w-4 text-muted-foreground" />
              <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex-1">
                Subtitles
              </h3>
              <label className="flex items-center gap-2 cursor-pointer">
                <span className="text-xs text-muted-foreground">
                  {globalSettings.subtitles_enabled ? 'On' : 'Off'}
                </span>
                <input
                  type="checkbox"
                  checked={globalSettings.subtitles_enabled}
                  onChange={(e) =>
                    handleSettingChange({ subtitles_enabled: e.target.checked })
                  }
                  className="h-4 w-4 rounded border-muted-foreground accent-primary cursor-pointer"
                />
              </label>
            </div>

            {globalSettings.subtitles_enabled && (
              <SubtitleSettingsForm
                font={globalSettings.subtitle_font}
                color={globalSettings.subtitle_color}
                fontSize={globalSettings.subtitle_font_size ?? 48}
                position={globalSettings.subtitle_position ?? 'bottom'}
                onChange={handleSettingChange}
              />
            )}
          </section>
        </div>
      )}
    </div>
  );
}
