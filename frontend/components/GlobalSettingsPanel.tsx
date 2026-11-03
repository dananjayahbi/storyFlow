'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { useSettingsStore, useProjectStore, useBgmStore } from '@/lib/stores';
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
import { BgmGenerationProgress } from '@/components/BgmGenerationProgress';
import {
  Settings,
  ChevronDown,
  ChevronRight,
  Timer,
  Captions,
  Stamp,
  Film,
  Sparkles,
  Music,
  Loader2,
  Wand2,
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
    project,
    isLoading: isProjectLoading,
    updateProjectSettings,
  } = useProjectStore();
  const {
    outroVideos, fetchOutroVideos, logos, fetchLogos,
    ttsEngines, fetchTtsEngines, voiceReferences, fetchVoiceReferences,
  } = useSettingsStore();
  const {
    clips: bgmClips,
    engine: musicEngine,
    generating: generatingMusic,
    ensureLoaded: ensureBgmLoaded,
    refreshClips: refreshBgmClips,
    generate: generateMusic,
    setActiveTrack,
  } = useBgmStore();

  // Start expanded to keep server/client markup identical, then restore the
  // persisted choice after hydration.
  const [isCollapsed, setIsCollapsed] = useState(false);

  // Debounce timer ref for TTS speed slider
  const speedTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Debounce timer ref for inter-segment silence slider
  const silenceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Debounce timer ref for upscale denoise slider
  const denoiseTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Local slider value for responsive UI (updated immediately, saved after debounce)
  const [localSpeed, setLocalSpeed] = useState<number | null>(null);
  const [localSilence, setLocalSilence] = useState<number | null>(null);
  const [localDenoise, setLocalDenoise] = useState<number | null>(null);

  // Background-music library + MusicGen state lives in the shared BGM store
  // so the timeline toolbar and this panel stay in sync.

  // Logo watermark modal state
  const [isLogoModalOpen, setIsLogoModalOpen] = useState(false);

  // Fetch global assets on mount (project is already loaded by the page)
  useEffect(() => {
    fetchOutroVideos();
    fetchLogos();
    fetchTtsEngines();
    fetchVoiceReferences();
  }, [fetchOutroVideos, fetchLogos, fetchTtsEngines, fetchVoiceReferences]);

  // Load the account's music library and the MusicGen runtime status. The
  // store deduplicates this across the settings panel and the timeline
  // toolbar, so both surfaces show the same clips and progress.
  useEffect(() => {
    if (project) void ensureBgmLoaded(project.id);
  }, [project, ensureBgmLoaded]);

  // Derived Qwen capability info
  const qwenEngine = ttsEngines.find((e) => e.id === 'qwen');
  const qwenSpeakers = qwenEngine?.speakers ?? {};
  const qwenLanguages = qwenEngine?.languages ?? ['English'];

  // Restore the persisted collapsed state after the first client render.
  useEffect(() => {
    setIsCollapsed(getInitialCollapsed());
  }, []);

  // Sync local slider value when project loads/changes
  useEffect(() => {
    if (project) {
      setLocalSpeed(project.tts_speed);
      setLocalSilence(project.inter_segment_silence);
      setLocalDenoise(project.upscale_denoise_strength);
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

  // ── Upscale denoise strength slider with debounce ──
  const handleDenoiseChange = useCallback(
    (values: number[]) => {
      const value = values[0];
      setLocalDenoise(value);

      if (denoiseTimerRef.current) {
        clearTimeout(denoiseTimerRef.current);
      }
      denoiseTimerRef.current = setTimeout(() => {
        handleSettingChange({ upscale_denoise_strength: value });
      }, 300);
    },
    [handleSettingChange]
  );

  // ── Background-music level sliders are configured on the Settings page
  //    (Audio Mix).  The project panel keeps only the track + generation
  //    controls so the same account-wide mix applies to every render.

  const handleBgmTrackChange = useCallback(
    async (value: string) => {
      try {
        await setActiveTrack(value === 'none' ? null : value);
        toast.success('Settings saved');
      } catch {
        toast.error('Failed to save settings');
      }
    },
    [setActiveTrack]
  );

  const handleGenerateMusic = useCallback(async () => {
    if (!project) return;
    const result = await generateMusic(
      project.id,
      `${project.title} — Generated Soundtrack`
    );
    if (result.ok) {
      toast.success('Soundtrack generated and attached to this project');
    } else if (result.error) {
      toast.error(result.error);
    }
  }, [project, generateMusic]);

  // Cleanup debounce timer on unmount
  useEffect(() => {
    return () => {
      if (speedTimerRef.current) clearTimeout(speedTimerRef.current);
      if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
      if (denoiseTimerRef.current) clearTimeout(denoiseTimerRef.current);
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
          {/* ── Voice / TTS Engine Section ── */}
          <section>
            {/* Engine selector: Kokoro draft vs Qwen final */}
            <div className="space-y-1.5">
              <label className="text-xs text-muted-foreground">TTS Engine</label>
              <Select
                value={project.tts_engine ?? 'kokoro'}
                onValueChange={(val) =>
                  handleSettingChange({ tts_engine: val as 'kokoro' | 'qwen' })
                }
              >
                <SelectTrigger className="w-full h-8 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="kokoro">Kokoro — fast draft</SelectItem>
                  <SelectItem value="qwen" disabled={!qwenEngine?.available}>
                    Qwen3-TTS — GPU final
                  </SelectItem>
                </SelectContent>
              </Select>
              <p className="text-[10px] text-muted-foreground">
                {(project.tts_engine ?? 'kokoro') === 'kokoro'
                  ? 'Build the full draft video quickly, then switch to Qwen and regenerate the audio.'
                  : qwenEngine?.available
                    ? `Heavy GPU engine${qwenEngine.device ? ` (${qwenEngine.device})` : ''}. Generates the final narration.`
                    : qwenEngine?.error || 'Qwen is unavailable. See Settings → TTS Engines.'}
              </p>
            </div>

            {(project.tts_engine ?? 'kokoro') === 'qwen' ? (
              <div className="space-y-2.5 mt-3">
                {/* Qwen mode */}
                <div className="space-y-1.5">
                  <label className="text-xs text-muted-foreground">Voice mode</label>
                  <Select
                    value={project.qwen_mode ?? 'custom_voice'}
                    onValueChange={(val) =>
                      handleSettingChange({
                        qwen_mode: val as 'custom_voice' | 'clone',
                      })
                    }
                  >
                    <SelectTrigger className="w-full h-8 text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="custom_voice">Preset voice</SelectItem>
                      <SelectItem value="clone">Voice cloning</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                {(project.qwen_mode ?? 'custom_voice') === 'custom_voice' ? (
                  <div className="space-y-1.5">
                    <label className="text-xs text-muted-foreground">Speaker</label>
                    <Select
                      value={project.qwen_speaker ?? 'Aiden'}
                      onValueChange={(val) => handleSettingChange({ qwen_speaker: val })}
                    >
                      <SelectTrigger className="w-full h-8 text-xs">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {Object.entries(qwenSpeakers).map(([id, label]) => (
                          <SelectItem key={id} value={id}>{label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                ) : (
                  <div className="space-y-1.5">
                    <label className="text-xs text-muted-foreground">Reference voice</label>
                    <Select
                      value={project.active_voice_reference ?? ''}
                      onValueChange={(val) =>
                        handleSettingChange({ active_voice_reference: val || null })
                      }
                    >
                      <SelectTrigger className="w-full h-8 text-xs">
                        <SelectValue placeholder="Select reference…" />
                      </SelectTrigger>
                      <SelectContent>
                        {voiceReferences.map((ref) => (
                          <SelectItem key={ref.id} value={ref.id}>{ref.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    {voiceReferences.length === 0 && (
                      <p className="text-[10px] text-muted-foreground">
                        No reference clips. Upload one in Settings → Voice References.
                      </p>
                    )}
                  </div>
                )}

                <div className="space-y-1.5">
                  <label className="text-xs text-muted-foreground">Language</label>
                  <Select
                    value={project.qwen_language ?? 'English'}
                    onValueChange={(val) => handleSettingChange({ qwen_language: val })}
                  >
                    <SelectTrigger className="w-full h-8 text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {qwenLanguages.map((lang) => (
                        <SelectItem key={lang} value={lang}>{lang}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
            ) : (
              <div className="mt-3">
                {/* Kokoro Voice Selector (Task 05.03.02) */}
                <VoiceSelector
                  value={project.default_voice_id}
                  onChange={handleSettingChange}
                />
              </div>
            )}

            {/* TTS Speed Slider (applies to both engines) */}
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

          {/* ── Background Music (uploads + MusicGen) ── */}
          <section>
            <div className="flex items-center gap-1.5 mb-3">
              <Music className="h-4 w-4 text-muted-foreground" />
              <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex-1">
                Background Music
              </h3>
              <label className="flex items-center gap-2 cursor-pointer">
                <span className="text-xs text-muted-foreground">
                  {project.bgm_enabled ? 'On' : 'Off'}
                </span>
                <input
                  type="checkbox"
                  checked={project.bgm_enabled ?? false}
                  onChange={(e) =>
                    handleSettingChange({ bgm_enabled: e.target.checked })
                  }
                  className="h-4 w-4 rounded border-muted-foreground accent-primary cursor-pointer"
                />
              </label>
            </div>

            {project.bgm_enabled && (
              <div className="space-y-3">
                <div className="space-y-1.5">
                  <label className="text-xs text-muted-foreground">
                    Music track
                  </label>
                  <Select
                    value={project.active_bgm ?? 'none'}
                    onValueChange={(value) => void handleBgmTrackChange(value)}
                  >
                    <SelectTrigger className="w-full h-8 text-xs">
                      <SelectValue placeholder="Select a track…" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">No track selected</SelectItem>
                      {bgmClips.map((clip) => (
                        <SelectItem key={clip.id} value={clip.id}>
                          {clip.name}
                          {clip.source === 'generated' ? ' · generated' : ''}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => void handleGenerateMusic()}
                    disabled={generatingMusic || !musicEngine?.available}
                    title={
                      musicEngine?.available
                        ? 'Generate a continuous MusicGen soundtrack from this script'
                        : musicEngine?.reason || 'MusicGen is unavailable'
                    }
                  >
                    {generatingMusic ? (
                      <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Wand2 className="mr-2 h-3.5 w-3.5" />
                    )}
                    {generatingMusic ? 'Generating…' : 'Generate with MusicGen'}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => void refreshBgmClips()}
                  >
                    Refresh tracks
                  </Button>
                </div>

                {generatingMusic && <BgmGenerationProgress />}
                {musicEngine?.available && musicEngine.gpu && (
                  <p className="text-[10px] text-muted-foreground">
                    {musicEngine.gpu}
                    {musicEngine.vram_free_gb != null
                      ? ` · ${musicEngine.vram_free_gb.toFixed(1)} GB VRAM free`
                      : ''}
                    {musicEngine.backend === 'transformers'
                      ? ' · Transformers / CUDA'
                      : ''}
                    {musicEngine.weights_verified ? ' · weights verified' : ''}
                  </p>
                )}
                {musicEngine && !musicEngine.available && (
                  <p className="rounded-md border border-amber-500/30 bg-amber-500/10 p-2 text-[10px] text-amber-700 dark:text-amber-300">
                    {musicEngine.reason}
                  </p>
                )}

                <p className="text-[10px] leading-relaxed text-muted-foreground">
                  Music level, echo and voice-over ducking are account-wide
                  settings. Adjust them in{' '}
                  <span className="font-medium text-foreground">
                    Settings → Audio Mix
                  </span>{' '}
                  and preview the result in the demo playground.
                </p>
              </div>
            )}
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

          {/* ── Image Upscale (GAN) Section ── */}
          <section>
            <div className="flex items-center gap-1.5 mb-3">
              <Sparkles className="h-4 w-4 text-muted-foreground" />
              <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex-1">
                Image Upscale
              </h3>
              <label className="flex items-center gap-2 cursor-pointer">
                <span className="text-xs text-muted-foreground">
                  {project.upscale_enabled ? 'On' : 'Off'}
                </span>
                <input
                  type="checkbox"
                  checked={project.upscale_enabled ?? false}
                  onChange={(e) =>
                    handleSettingChange({ upscale_enabled: e.target.checked })
                  }
                  className="h-4 w-4 rounded border-muted-foreground accent-primary cursor-pointer"
                />
              </label>
            </div>

            {project.upscale_enabled && (
              <div className="space-y-3">
                {/* Model Selector */}
                <div className="space-y-1.5">
                  <label className="text-xs text-muted-foreground">
                    GAN Model
                  </label>
                  <Select
                    value={project.upscale_model ?? 'RealESRGAN_x4plus'}
                    onValueChange={(val) =>
                      handleSettingChange({ upscale_model: val as 'RealESRGAN_x4plus' | 'RealESRGAN_x2plus' | 'RealESRGAN_x4plus_anime_6B' })
                    }
                  >
                    <SelectTrigger className="w-full h-8 text-xs">
                      <SelectValue placeholder="Select model…" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="RealESRGAN_x4plus">
                        Real-ESRGAN x4 (General)
                      </SelectItem>
                      <SelectItem value="RealESRGAN_x2plus">
                        Real-ESRGAN x2 (General)
                      </SelectItem>
                      <SelectItem value="RealESRGAN_x4plus_anime_6B">
                        Real-ESRGAN x4 (Anime)
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                {/* Denoise Strength Slider */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-xs text-muted-foreground">
                      Denoise Strength
                    </label>
                    <span className="text-xs font-medium tabular-nums">
                      {((localDenoise ?? project.upscale_denoise_strength) * 100).toFixed(0)}%
                    </span>
                  </div>
                  <Slider
                    value={[localDenoise ?? project.upscale_denoise_strength]}
                    min={0}
                    max={1.0}
                    step={0.05}
                    onValueChange={handleDenoiseChange}
                  />
                  <p className="text-[10px] text-muted-foreground">
                    Higher values remove more noise but may lose details
                  </p>
                </div>

                <p className="text-[10px] text-muted-foreground">
                  Images will be upscaled using the selected GAN model before rendering.
                  This improves quality for low-resolution source images.
                </p>
              </div>
            )}
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
