'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  getProjectSettingsDefaults,
  resetProjectSettingsDefault,
  updateProjectSettingsDefault,
} from '@/lib/api';
import type { ProjectSettingsProfile } from '@/lib/types';
import { useSettingsStore } from '@/lib/stores';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Slider } from '@/components/ui/slider';
import {
  AlertTriangle,
  Captions,
  CheckCircle2,
  Film,
  Image as ImageIcon,
  Layers,
  Loader2,
  Music,
  RotateCcw,
  Save,
  SlidersHorizontal,
  Volume2,
} from 'lucide-react';
import { toast } from 'sonner';

const FPS_OPTIONS = [24, 30, 60] as const;

const LOGO_POSITIONS = [
  { value: 'top-left', label: 'Top left' },
  { value: 'top-right', label: 'Top right' },
  { value: 'bottom-left', label: 'Bottom left' },
  { value: 'bottom-right', label: 'Bottom right' },
] as const;

const UPSCALE_MODELS = [
  { value: 'RealESRGAN_x4plus', label: 'Real-ESRGAN x4 (General)' },
  { value: 'RealESRGAN_x2plus', label: 'Real-ESRGAN x2 (General)' },
  { value: 'RealESRGAN_x4plus_anime_6B', label: 'Real-ESRGAN x4 (Anime)' },
] as const;

function resolutionKey(width: number, height: number): string {
  return `${width}x${height}`;
}

function profileLabel(profile: ProjectSettingsProfile): string {
  return `${profile.resolution_width} × ${profile.resolution_height}`;
}

function editablePayload(profile: ProjectSettingsProfile) {
  return {
    default_voice_id: profile.default_voice_id,
    tts_speed: profile.tts_speed,
    tts_engine: profile.tts_engine,
    subtitle_font_size: profile.subtitle_font_size,
    subtitle_font_color: profile.subtitle_font_color,
    subtitle_position: profile.subtitle_position,
    subtitles_enabled: profile.subtitles_enabled,
    framerate: profile.framerate,
    ken_burns_zoom: profile.ken_burns_zoom,
    transition_duration: profile.transition_duration,
    inter_segment_silence: profile.inter_segment_silence,
    logo_enabled: profile.logo_enabled,
    active_logo: profile.active_logo ?? null,
    logo_scale: profile.logo_scale,
    logo_position: profile.logo_position,
    logo_opacity: profile.logo_opacity,
    logo_margin: profile.logo_margin,
    outro_enabled: profile.outro_enabled,
    active_outro: profile.active_outro ?? null,
    upscale_enabled: profile.upscale_enabled,
    upscale_model: profile.upscale_model,
    upscale_denoise_strength: profile.upscale_denoise_strength,
    bgm_gain_db: profile.bgm_gain_db,
    bgm_ducking_db: profile.bgm_ducking_db,
    bgm_echo_percent: profile.bgm_echo_percent,
    tts_gain_db: profile.tts_gain_db,
  };
}

export function DefaultProjectSettingsPanel() {
  const {
    availableVoices,
    fetchVoices,
    ttsEngines,
    fetchTtsEngines,
    logos,
    fetchLogos,
    outroVideos,
    fetchOutroVideos,
  } = useSettingsStore();

  const [profiles, setProfiles] = useState<ProjectSettingsProfile[]>([]);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [draft, setDraft] = useState<ProjectSettingsProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isResetting, setIsResetting] = useState(false);

  useEffect(() => {
    fetchVoices();
    fetchTtsEngines();
    fetchLogos();
    fetchOutroVideos();
  }, [fetchVoices, fetchTtsEngines, fetchLogos, fetchOutroVideos]);

  useEffect(() => {
    let cancelled = false;
    getProjectSettingsDefaults()
      .then((results) => {
        if (cancelled) return;
        setProfiles(results);
        const first = results[0];
        if (first) {
          setSelectedKey(resolutionKey(first.resolution_width, first.resolution_height));
          setDraft(first);
        }
      })
      .catch(() => toast.error('Failed to load project defaults'))
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const selected = useMemo(
    () => profiles.find(
      (profile) =>
        resolutionKey(profile.resolution_width, profile.resolution_height) === selectedKey,
    ) ?? null,
    [profiles, selectedKey],
  );

  const selectResolution = useCallback(
    (key: string) => {
      setSelectedKey(key);
      const next = profiles.find(
        (profile) => resolutionKey(profile.resolution_width, profile.resolution_height) === key,
      );
      setDraft(next ?? null);
    },
    [profiles],
  );

  const setField = useCallback(
    <K extends keyof ProjectSettingsProfile>(field: K, value: ProjectSettingsProfile[K]) => {
      setDraft((current) => (current ? { ...current, [field]: value } : current));
    },
    [],
  );

  const replaceProfile = useCallback((updated: ProjectSettingsProfile) => {
    setProfiles((current) =>
      current.map((profile) =>
        profile.resolution_width === updated.resolution_width &&
        profile.resolution_height === updated.resolution_height
          ? updated
          : profile,
      ),
    );
    setDraft(updated);
    setSelectedKey(resolutionKey(updated.resolution_width, updated.resolution_height));
  }, []);

  const saveDefaults = useCallback(async () => {
    if (!draft) return;
    setIsSaving(true);
    try {
      const updated = await updateProjectSettingsDefault(
        draft.resolution_width,
        draft.resolution_height,
        editablePayload(draft),
      );
      replaceProfile(updated);
      toast.success(`Defaults saved for ${profileLabel(updated)}`);
    } catch {
      toast.error('Failed to save project defaults');
    } finally {
      setIsSaving(false);
    }
  }, [draft, replaceProfile]);

  const resetDefaults = useCallback(async () => {
    if (!draft) return;
    setIsResetting(true);
    try {
      const updated = await resetProjectSettingsDefault(
        draft.resolution_width,
        draft.resolution_height,
      );
      replaceProfile(updated);
      toast.success(
        `Reverted ${profileLabel(updated)} to the account defaults`,
      );
    } catch {
      toast.error('Failed to reset project defaults');
    } finally {
      setIsResetting(false);
    }
  }, [draft, replaceProfile]);

  if (isLoading || !draft || !selected) {
    return (
      <Card>
        <CardContent className="flex items-center gap-2 py-10 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading project defaults…
        </CardContent>
      </Card>
    );
  }

  const qwenEngine = ttsEngines.find((engine) => engine.id === 'qwen');
  const qwenAvailable = qwenEngine ? qwenEngine.available : false;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
              <Layers className="h-4 w-4 text-primary" />
            </div>
            <div>
              <CardTitle className="text-lg">Default Project Settings</CardTitle>
              <CardDescription>
                Pre-define the settings each new project starts with for every
                available resolution.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="rounded-lg border bg-muted/20 p-3 text-xs leading-relaxed text-muted-foreground">
            These are <strong>defaults for new projects</strong>. A project
            copies the matching profile when it is created or when its
            resolution changes, then keeps its own editable snapshot. Editing
            one project never changes another project or these defaults.
          </div>

          <div className="space-y-2">
            <label htmlFor="default-profile-resolution" className="text-sm font-medium">
              Resolution
            </label>
            <select
              id="default-profile-resolution"
              value={selectedKey ?? ''}
              onChange={(event) => selectResolution(event.target.value)}
              className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm"
            >
              {profiles.map((profile) => (
                <option
                  key={resolutionKey(profile.resolution_width, profile.resolution_height)}
                  value={resolutionKey(profile.resolution_width, profile.resolution_height)}
                >
                  {profileLabel(profile)}
                  {profile.is_customized ? ' — custom defaults' : ' — account fallback'}
                </option>
              ))}
            </select>
            <div className="flex items-center gap-2">
              {selected.is_customized ? (
                <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-600 dark:text-emerald-400">
                  <CheckCircle2 className="h-3 w-3" />
                  Custom defaults are active for this resolution
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 text-[11px] font-medium text-amber-600 dark:text-amber-400">
                  <AlertTriangle className="h-3 w-3" />
                  Not customised yet — projects fall back to the account settings
                </span>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* TTS */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Volume2 className="h-4 w-4" />
            Voice &amp; TTS
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <label className="text-sm font-medium">TTS engine</label>
              <select
                value={draft.tts_engine}
                onChange={(event) => setField('tts_engine', event.target.value as 'kokoro' | 'qwen')}
                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm"
              >
                <option value="kokoro">Kokoro — fast draft</option>
                <option value="qwen" disabled={!qwenAvailable}>
                  Qwen3-TTS — GPU{qwenAvailable ? '' : ' (unavailable)'}
                </option>
              </select>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Kokoro voice</label>
              <select
                value={draft.default_voice_id}
                onChange={(event) => setField('default_voice_id', event.target.value)}
                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm"
              >
                {(availableVoices.length ? availableVoices : [{ id: draft.default_voice_id, name: draft.default_voice_id, language: '', sample_url: null }]).map((voice) => (
                  <option key={voice.id} value={voice.id}>
                    {voice.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium">Speech speed</label>
              <span className="text-sm font-medium tabular-nums text-muted-foreground">
                {draft.tts_speed.toFixed(1)}x
              </span>
            </div>
            <Slider
              value={[draft.tts_speed]}
              min={0.5}
              max={2.0}
              step={0.1}
              onValueChange={(values) => setField('tts_speed', values[0])}
            />
          </div>
        </CardContent>
      </Card>

      {/* Subtitles */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Captions className="h-4 w-4" />
            Subtitles
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={draft.subtitles_enabled}
              onChange={(event) => setField('subtitles_enabled', event.target.checked)}
              className="h-4 w-4 accent-primary"
            />
            Burn subtitles into rendered videos
          </label>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium">Font size</label>
                <span className="text-sm tabular-nums text-muted-foreground">
                  {draft.subtitle_font_size}px
                </span>
              </div>
              <Slider
                value={[draft.subtitle_font_size]}
                min={12}
                max={120}
                step={1}
                onValueChange={(values) => setField('subtitle_font_size', values[0])}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Position</label>
              <select
                value={draft.subtitle_position}
                onChange={(event) =>
                  setField('subtitle_position', event.target.value as 'bottom' | 'center' | 'top')
                }
                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm"
              >
                <option value="bottom">Bottom</option>
                <option value="center">Center</option>
                <option value="top">Top</option>
              </select>
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">Font color</label>
            <div className="flex items-center gap-3">
              <input
                type="color"
                value={draft.subtitle_font_color}
                onChange={(event) => setField('subtitle_font_color', event.target.value)}
                className="h-9 w-12 cursor-pointer rounded-md border border-input bg-background p-1"
              />
              <span className="font-mono text-sm">{draft.subtitle_font_color}</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Render */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <SlidersHorizontal className="h-4 w-4" />
            Render &amp; Motion
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <label className="text-sm font-medium">Framerate</label>
              <select
                value={String(draft.framerate)}
                onChange={(event) => setField('framerate', Number(event.target.value))}
                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm"
              >
                {FPS_OPTIONS.map((fps) => (
                  <option key={fps} value={fps}>{fps} fps</option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium">Inter-segment silence</label>
                <span className="text-sm tabular-nums text-muted-foreground">
                  {draft.inter_segment_silence.toFixed(1)}s
                </span>
              </div>
              <Slider
                value={[draft.inter_segment_silence]}
                min={0}
                max={5}
                step={0.1}
                onValueChange={(values) => setField('inter_segment_silence', values[0])}
              />
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium">Ken Burns zoom</label>
              <span className="text-sm tabular-nums text-muted-foreground">
                {draft.ken_burns_zoom.toFixed(1)}x
              </span>
            </div>
            <Slider
              value={[draft.ken_burns_zoom]}
              min={1.0}
              max={2.0}
              step={0.1}
              onValueChange={(values) => setField('ken_burns_zoom', values[0])}
            />
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium">Transition duration</label>
              <span className="text-sm tabular-nums text-muted-foreground">
                {draft.transition_duration.toFixed(1)}s
              </span>
            </div>
            <Slider
              value={[draft.transition_duration]}
              min={0}
              max={2}
              step={0.1}
              onValueChange={(values) => setField('transition_duration', values[0])}
            />
          </div>
        </CardContent>
      </Card>

      {/* Logo */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <ImageIcon className="h-4 w-4" />
            Logo watermark
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={draft.logo_enabled}
              onChange={(event) => setField('logo_enabled', event.target.checked)}
              className="h-4 w-4 accent-primary"
            />
            Enable logo watermark by default
          </label>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <label className="text-sm font-medium">Logo</label>
              <select
                value={draft.active_logo ?? ''}
                onChange={(event) => setField('active_logo', event.target.value || null)}
                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm"
              >
                <option value="">No logo</option>
                {logos.map((logo) => (
                  <option key={logo.id} value={logo.id}>{logo.name}</option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Position</label>
              <select
                value={draft.logo_position}
                onChange={(event) =>
                  setField(
                    'logo_position',
                    event.target.value as ProjectSettingsProfile['logo_position'],
                  )
                }
                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm"
              >
                {LOGO_POSITIONS.map((position) => (
                  <option key={position.value} value={position.value}>{position.label}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium">Scale</label>
                <span className="text-sm tabular-nums text-muted-foreground">
                  {Math.round(draft.logo_scale * 100)}%
                </span>
              </div>
              <Slider
                value={[draft.logo_scale]}
                min={0.05}
                max={0.5}
                step={0.01}
                onValueChange={(values) => setField('logo_scale', values[0])}
              />
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium">Opacity</label>
                <span className="text-sm tabular-nums text-muted-foreground">
                  {Math.round(draft.logo_opacity * 100)}%
                </span>
              </div>
              <Slider
                value={[draft.logo_opacity]}
                min={0}
                max={1}
                step={0.05}
                onValueChange={(values) => setField('logo_opacity', values[0])}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Outro + upscale */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Film className="h-4 w-4" />
            Outro &amp; Upscaling
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={draft.outro_enabled}
                  onChange={(event) => setField('outro_enabled', event.target.checked)}
                  className="h-4 w-4 accent-primary"
                />
                Append an outro video
              </label>
              <select
                value={draft.active_outro ?? ''}
                onChange={(event) => setField('active_outro', event.target.value || null)}
                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm"
              >
                <option value="">No outro</option>
                {outroVideos.map((outro) => (
                  <option key={outro.id} value={outro.id}>{outro.name}</option>
                ))}
              </select>
            </div>

            <div className="space-y-2">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={draft.upscale_enabled}
                  onChange={(event) => setField('upscale_enabled', event.target.checked)}
                  className="h-4 w-4 accent-primary"
                />
                Upscale source images
              </label>
              <select
                value={draft.upscale_model}
                onChange={(event) =>
                  setField(
                    'upscale_model',
                    event.target.value as ProjectSettingsProfile['upscale_model'],
                  )
                }
                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm"
              >
                {UPSCALE_MODELS.map((model) => (
                  <option key={model.value} value={model.value}>{model.label}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium">Upscale denoise strength</label>
              <span className="text-sm tabular-nums text-muted-foreground">
                {draft.upscale_denoise_strength.toFixed(2)}
              </span>
            </div>
            <Slider
              value={[draft.upscale_denoise_strength]}
              min={0}
              max={1}
              step={0.05}
              onValueChange={(values) => setField('upscale_denoise_strength', values[0])}
            />
          </div>
        </CardContent>
      </Card>

      {/* Audio mix */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Music className="h-4 w-4" />
            Audio mix
          </CardTitle>
          <CardDescription>
            Initial music and narration levels for projects created at this
            resolution.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-5 sm:grid-cols-2">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium">Music gain</label>
              <span className="text-sm tabular-nums text-muted-foreground">
                {draft.bgm_gain_db.toFixed(0)} dB
              </span>
            </div>
            <Slider
              value={[draft.bgm_gain_db]}
              min={-60}
              max={0}
              step={1}
              onValueChange={(values) => setField('bgm_gain_db', values[0])}
            />
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium">Ducking</label>
              <span className="text-sm tabular-nums text-muted-foreground">
                {draft.bgm_ducking_db.toFixed(0)} dB
              </span>
            </div>
            <Slider
              value={[draft.bgm_ducking_db]}
              min={-30}
              max={0}
              step={1}
              onValueChange={(values) => setField('bgm_ducking_db', values[0])}
            />
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium">Echo</label>
              <span className="text-sm tabular-nums text-muted-foreground">
                {draft.bgm_echo_percent.toFixed(0)}%
              </span>
            </div>
            <Slider
              value={[draft.bgm_echo_percent]}
              min={0}
              max={100}
              step={1}
              onValueChange={(values) => setField('bgm_echo_percent', values[0])}
            />
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium">Narration gain</label>
              <span className="text-sm tabular-nums text-muted-foreground">
                {draft.tts_gain_db.toFixed(0)} dB
              </span>
            </div>
            <Slider
              value={[draft.tts_gain_db]}
              min={-24}
              max={12}
              step={1}
              onValueChange={(values) => setField('tts_gain_db', values[0])}
            />
          </div>
        </CardContent>
      </Card>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <Button onClick={saveDefaults} disabled={isSaving || isResetting}>
          {isSaving ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Save className="mr-2 h-4 w-4" />
          )}
          Save defaults for {profileLabel(draft)}
        </Button>
        <Button
          variant="outline"
          onClick={resetDefaults}
          disabled={isSaving || isResetting || !selected.is_customized}
        >
          {isResetting ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <RotateCcw className="mr-2 h-4 w-4" />
          )}
          Use account defaults
        </Button>
        <span className="text-xs text-muted-foreground">
          Saving creates a custom profile for this resolution only.
        </span>
      </div>
    </div>
  );
}
