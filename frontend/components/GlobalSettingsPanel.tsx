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
import {
  Settings,
  ChevronDown,
  ChevronRight,
  Volume2,
  RefreshCw,
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

  // Local slider value for responsive UI (updated immediately, saved after debounce)
  const [localSpeed, setLocalSpeed] = useState<number | null>(null);

  // Fetch settings on mount
  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  // Sync local slider value when globalSettings loads/changes
  useEffect(() => {
    if (globalSettings) {
      setLocalSpeed(globalSettings.tts_speed);
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

  // Cleanup debounce timer on unmount
  useEffect(() => {
    return () => {
      if (speedTimerRef.current) clearTimeout(speedTimerRef.current);
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
            <div className="flex items-center gap-1.5 mb-3">
              <Volume2 className="h-4 w-4 text-muted-foreground" />
              <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Voice
              </h3>
            </div>

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

          {/* ── Render Settings Section (Task 05.03.05) ── */}
          <section>
            <RenderSettingsForm
              zoomIntensity={globalSettings.zoom_intensity}
              onChange={handleSettingChange}
            />
          </section>

          <Separator />

          {/* ── Subtitle Settings Section (Task 05.03.03) ── */}
          <section>
            <SubtitleSettingsForm
              font={globalSettings.subtitle_font}
              color={globalSettings.subtitle_color}
              onChange={handleSettingChange}
            />
          </section>
        </div>
      )}
    </div>
  );
}
