'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { useSettingsStore, useProjectStore } from '@/lib/stores';
import { Slider } from '@/components/ui/slider';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { VoiceSelector } from '@/components/VoiceSelector';
import { SubtitleSettingsForm } from '@/components/SubtitleSettingsForm';
import { RenderSettingsForm } from '@/components/RenderSettingsForm';
import { LogoWatermarkModal } from '@/components/LogoWatermarkModal';
import {
  Settings,
  ChevronDown,
  ChevronRight,
  Timer,
  Captions,
  Stamp,
  Film,
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
  const { project, isLoading: isProjectLoading, updateProjectSettings } = useProjectStore();
  const { outroVideos, fetchOutroVideos, logos, fetchLogos } = useSettingsStore();

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

  // Fetch global assets on mount (project is already loaded by the page)
  useEffect(() => {
    fetchOutroVideos();
    fetchLogos();
  }, [fetchOutroVideos, fetchLogos]);

  // Sync local slider value when project loads/changes
  useEffect(() => {
    if (project) {
      setLocalSpeed(project.tts_speed);
      setLocalSilence(project.inter_segment_silence);
    }
  }, [project]);

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

  // Shared handler: wraps updateProjectSettings with toast feedback
  const handleSettingChange = useCallback(
    async (data: Parameters<typeof updateProjectSettings>[0]) => {
      try {
        await updateProjectSettings(data);
        toast.success('Settings saved');
      } catch {
        toast.error('Failed to save settings');
      }
    },
    [updateProjectSettings]
  );

  // Wrapper for RenderSettingsForm that maps render_* field names to ProjectDetail field names
  const handleRenderSettingChange = useCallback(
    async (data: { zoom_intensity?: number; render_width?: number; render_height?: number; render_fps?: number }) => {
      const mapped: Parameters<typeof updateProjectSettings>[0] = {};
      if (data.zoom_intensity !== undefined) mapped.zoom_intensity = data.zoom_intensity;
      if (data.render_width !== undefined) mapped.resolution_width = data.render_width;
      if (data.render_height !== undefined) mapped.resolution_height = data.render_height;
      if (data.render_fps !== undefined) mapped.framerate = data.render_fps;
      await handleSettingChange(mapped);
    },
    [handleSettingChange]
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
  if (isProjectLoading) {
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
  if (!project) {
    return (
      <div className="p-4">
        <div className="flex items-center gap-2 mb-4">
          <Settings className="h-5 w-5 text-muted-foreground" />
          <span className="font-medium text-sm">Settings</span>
        </div>
        <p className="text-sm text-muted-foreground mb-3">
          No project loaded
        </p>
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
              value={project.default_voice_id}
              onChange={handleSettingChange}
            />

            {/* TTS Speed Slider */}
            <div className="space-y-1.5 mt-3">
              <div className="flex items-center justify-between">
                <label className="text-xs text-muted-foreground">
                  TTS Speed
                </label>
                <span className="text-xs font-medium tabular-nums">
                  {(localSpeed ?? project.tts_speed).toFixed(1)}x
                </span>
              </div>
              <Slider
                value={[localSpeed ?? project.tts_speed]}
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
                  {(localSilence ?? project.inter_segment_silence).toFixed(1)}s
                </span>
              </div>
              <Slider
                value={[localSilence ?? project.inter_segment_silence]}
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
              zoomIntensity={project.zoom_intensity}
              renderWidth={project.resolution_width ?? 1920}
              renderHeight={project.resolution_height ?? 1080}
              renderFps={project.framerate ?? 30}
              onChange={handleRenderSettingChange}
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
                  {project.logo_enabled ? 'On' : 'Off'}
                </span>
                <input
                  type="checkbox"
                  checked={project.logo_enabled ?? false}
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

            {project.logo_enabled && project.active_logo && (
              <p className="text-[10px] text-muted-foreground mt-1.5">
                Logo will be placed at{' '}
                <span className="font-medium">
                  {project.logo_position?.replace('-', ' ') ?? 'bottom right'}
                </span>{' '}
                with {Math.round((project.logo_opacity ?? 1) * 100)}% opacity
              </p>
            )}

            <LogoWatermarkModal
              open={isLogoModalOpen}
              onOpenChange={setIsLogoModalOpen}
              renderWidth={project.resolution_width ?? 1920}
              renderHeight={project.resolution_height ?? 1080}
            />
          </section>

          <Separator />

          {/* ── Outro Video Section ── */}
          <section>
            <div className="flex items-center gap-1.5 mb-3">
              <Film className="h-4 w-4 text-muted-foreground" />
              <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex-1">
                Outro Video
              </h3>
              <label className="flex items-center gap-2 cursor-pointer">
                <span className="text-xs text-muted-foreground">
                  {project.outro_enabled ? 'On' : 'Off'}
                </span>
                <input
                  type="checkbox"
                  checked={project.outro_enabled ?? false}
                  onChange={(e) =>
                    handleSettingChange({ outro_enabled: e.target.checked })
                  }
                  className="h-4 w-4 rounded border-muted-foreground accent-primary cursor-pointer"
                />
              </label>
            </div>

            {project.outro_enabled && (
              <div className="space-y-2">
                <Select
                  value={project.active_outro ?? ''}
                  onValueChange={(val) =>
                    handleSettingChange({ active_outro: val || null })
                  }
                >
                  <SelectTrigger className="w-full h-8 text-xs">
                    <SelectValue placeholder="Select outro video…" />
                  </SelectTrigger>
                  <SelectContent>
                    {outroVideos.map((o) => (
                      <SelectItem key={o.id} value={o.id}>
                        {o.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {outroVideos.length === 0 && (
                  <p className="text-[10px] text-muted-foreground">
                    No outro videos uploaded. Go to Settings page to upload.
                  </p>
                )}
                {project.active_outro && (
                  <p className="text-[10px] text-muted-foreground">
                    Selected video will be appended with a smooth crossfade.
                  </p>
                )}
              </div>
            )}
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
                  {project.subtitles_enabled ? 'On' : 'Off'}
                </span>
                <input
                  type="checkbox"
                  checked={project.subtitles_enabled}
                  onChange={(e) =>
                    handleSettingChange({ subtitles_enabled: e.target.checked })
                  }
                  className="h-4 w-4 rounded border-muted-foreground accent-primary cursor-pointer"
                />
              </label>
            </div>

            {project.subtitles_enabled && (
              <SubtitleSettingsForm
                font={project.subtitle_font}
                color={project.subtitle_color}
                fontSize={project.subtitle_font_size ?? 48}
                position={project.subtitle_position ?? 'bottom'}
                yPosition={project.subtitle_y_position ?? null}
                renderWidth={project.resolution_width ?? 1920}
                renderHeight={project.resolution_height ?? 1080}
                onChange={handleSettingChange}
              />
            )}
          </section>
        </div>
      )}
    </div>
  );
}
