'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  applyPlaygroundBgm,
  cancelPlayground,
  getBgmClips,
  getMusicEngineStatus,
  getPlayground,
  getSettings,
  savePlayground,
  generatePlayground,
  updateSettings,
  uploadPlaygroundImage,
  removePlaygroundImage,
} from '@/lib/api';
import type { BgmClip, MusicEngineStatus, PlaygroundState } from '@/lib/types';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Slider } from '@/components/ui/slider';
import { Separator } from '@/components/ui/separator';
import { Progress } from '@/components/ui/progress';
import { toast } from 'sonner';
import {
  Loader2, Music, Save, Sparkles, Upload, Trash2, Volume2,
  Waves, Mic2, RefreshCw, Film, Square, Wand2,
} from 'lucide-react';
import { mediaUrl } from '@/lib/apiConfig';

const POLL_INTERVAL_MS = 2000;
const MUSIC_SOURCE_KEY = 'storyflow.playground.music-source';

type MusicSource = 'generated' | 'library' | 'none';

function storedMusicSource(): MusicSource {
  if (typeof window === 'undefined') return 'generated';
  const raw = localStorage.getItem(MUSIC_SOURCE_KEY);
  return raw === 'library' || raw === 'none' || raw === 'generated'
    ? raw
    : 'generated';
}

function apiErrorMessage(error: unknown, fallback: string): string {
  const detail = (
    error as { response?: { data?: { error?: string } } }
  )?.response?.data?.error;
  return detail || fallback;
}

function formatDb(value: number): string {
  return `${value > 0 ? '+' : ''}${value.toFixed(0)} dB`;
}

export function SettingsMixPanel() {
  // ── Account audio-mix settings ─────────────────────────────────────
  const [bgmGain, setBgmGain] = useState(-18);
  const [bgmDucking, setBgmDucking] = useState(-12);
  const [bgmEcho, setBgmEcho] = useState(0);
  const [ttsGain, setTtsGain] = useState(0);
  const [isLoadingSettings, setIsLoadingSettings] = useState(true);
  const [isSavingSettings, setIsSavingSettings] = useState(false);

  // ── Playground ─────────────────────────────────────────────────────
  const [playground, setPlayground] = useState<PlaygroundState | null>(null);
  const [drafts, setDrafts] = useState<string[]>(['', '', '']);
  const [clips, setClips] = useState<BgmClip[]>([]);
  const [selectedClip, setSelectedClip] = useState('');
  const [musicSource, setMusicSource] = useState<MusicSource>('generated');
  const [regenerateMusic, setRegenerateMusic] = useState(false);
  const [musicEngine, setMusicEngine] = useState<MusicEngineStatus | null>(null);
  const [isLoadingPlayground, setIsLoadingPlayground] = useState(true);
  const [isSavingPlayground, setIsSavingPlayground] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isApplying, setIsApplying] = useState(false);
  const [isStopping, setIsStopping] = useState(false);
  const [isUploadingIndex, setIsUploadingIndex] = useState<number | null>(null);
  const fileInputs = useRef<Array<HTMLInputElement | null>>([]);

  const loadPlayground = useCallback(async () => {
    try {
      const state = await getPlayground();
      setPlayground(state);
      setDrafts(state.blocks.map((block) => block.text_content));
      setSelectedClip(state.bgm_clip ?? '');
      setIsGenerating(state.status === 'PROCESSING');
      if (state.status !== 'PROCESSING') setIsStopping(false);
      setIsLoadingPlayground(false);
      return state;
    } catch {
      setIsLoadingPlayground(false);
      toast.error('Failed to load the demo playground');
      return null;
    }
  }, []);

  useEffect(() => {
    setMusicSource(storedMusicSource());
  }, []);

  useEffect(() => {
    getSettings()
      .then((settings) => {
        setBgmGain(settings.bgm_gain_db ?? -18);
        setBgmDucking(settings.bgm_ducking_db ?? -12);
        setBgmEcho(settings.bgm_echo_percent ?? 0);
        setTtsGain(settings.tts_gain_db ?? 0);
      })
      .catch(() => toast.error('Failed to load Audio Mix settings'))
      .finally(() => setIsLoadingSettings(false));

    void loadPlayground();
    getBgmClips()
      .then(setClips)
      .catch(() => setClips([]));
    getMusicEngineStatus()
      .then(setMusicEngine)
      .catch(() => setMusicEngine(null));

  }, [loadPlayground]);

  // Poll while a demo job is running. The state lives in the database, so
  // reloading this page re-attaches to the job instead of interrupting it.
  // Use an interval (not a single timeout) so polling keeps going until the
  // backend reports a terminal status.
  useEffect(() => {
    if (!isGenerating) return;
    const interval = setInterval(async () => {
      const state = await loadPlayground();
      if (state && state.status !== 'PROCESSING') {
        setIsGenerating(false);
        setIsStopping(false);
        if (isStopping) {
          toast.success('Demo generation stopped');
        } else if (state.status === 'COMPLETED') {
          toast.success('Demo video ready');
        } else if (state.status === 'FAILED') {
          toast.error('Demo generation failed. Check the backend log.');
        }
      }
    }, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [isGenerating, isStopping, loadPlayground]);

  const saveMixSettings = useCallback(async () => {
    setIsSavingSettings(true);
    try {
      await updateSettings({
        bgm_gain_db: bgmGain,
        bgm_ducking_db: bgmDucking,
        bgm_echo_percent: bgmEcho,
        tts_gain_db: ttsGain,
      });
      toast.success('Audio Mix settings saved for this account');
    } catch {
      toast.error('Failed to save Audio Mix settings');
      throw new Error('save failed');
    } finally {
      setIsSavingSettings(false);
    }
  }, [bgmGain, bgmDucking, bgmEcho, ttsGain]);

  const saveBlocks = useCallback(async (silent = false) => {
    setIsSavingPlayground(true);
    try {
      const state = await savePlayground({
        blocks: drafts.map((text_content) => ({ text_content })),
      });
      setPlayground(state);
      setDrafts(state.blocks.map((block) => block.text_content));
      if (!silent) toast.success('Demo blocks saved');
      return state;
    } catch {
      toast.error('Failed to save demo blocks');
      throw new Error('save failed');
    } finally {
      setIsSavingPlayground(false);
    }
  }, [drafts]);

  const handleUpload = async (index: number, file: File) => {
    setIsUploadingIndex(index);
    try {
      await uploadPlaygroundImage(index, file);
      const state = await loadPlayground();
      if (state) {
        setDrafts(state.blocks.map((block) => block.text_content));
      }
      toast.success(`Block ${index + 1} image uploaded`);
    } catch {
      toast.error('Failed to upload image');
    } finally {
      setIsUploadingIndex(null);
      const input = fileInputs.current[index];
      if (input) input.value = '';
    }
  };

  const handleRemoveImage = async (index: number) => {
    setIsUploadingIndex(index);
    try {
      await removePlaygroundImage(index);
      await loadPlayground();
      toast.success(`Block ${index + 1} image removed`);
    } catch {
      toast.error('Failed to remove image');
    } finally {
      setIsUploadingIndex(null);
    }
  };

  const handleMusicSourceChange = (value: MusicSource) => {
    setMusicSource(value);
    try {
      localStorage.setItem(MUSIC_SOURCE_KEY, value);
    } catch {
      // Ignore storage failures (private mode); the current session still works.
    }
  };

  const handleGenerate = async () => {
    setIsGenerating(true);
    try {
      // Persist the current tuning and block text first so the demo always
      // reflects exactly what the sliders show. The base video is rendered
      // without subtitles or music; press Apply Background Music afterwards
      // to compose the soundtrack.
      await saveMixSettings();
      await saveBlocks(true);
      await generatePlayground({ music_source: 'none' });
      toast.success('Rendering the demo video without background music…');
      await loadPlayground();
    } catch (error) {
      setIsGenerating(false);
      toast.error(apiErrorMessage(error, 'Could not start the demo render'));
    }
  };

  const handleApplyBgm = async () => {
    setIsApplying(true);
    try {
      // Only the audio track is re-mixed; the generated video stays untouched.
      await saveMixSettings();
      await saveBlocks(true);
      await applyPlaygroundBgm({
        music_source: musicSource,
        bgm_clip: musicSource === 'library' ? selectedClip || null : undefined,
        regenerate_music:
          musicSource === 'generated' ? regenerateMusic : false,
      });
      const composeNew = musicSource === 'generated' && regenerateMusic;
      setRegenerateMusic(false);
      toast.success(
        musicSource === 'generated'
          ? composeNew
            ? 'Composing a new MusicGen soundtrack and applying it to the demo…'
            : 'Applying the generated soundtrack to the demo video…'
          : 'Applying background music to the existing demo video',
      );
      setIsGenerating(true);
      await loadPlayground();
      // A freshly generated soundtrack is added to the BGM Library.
      getBgmClips().then(setClips).catch(() => {});
    } catch (error) {
      toast.error(
        apiErrorMessage(error, 'Could not apply the background music'),
      );
    } finally {
      // The job continues in the background; status polling takes over.
      setIsApplying(false);
    }
  };

  const handleStop = async () => {
    setIsStopping(true);
    try {
      const state = await cancelPlayground();
      setPlayground(state);
      toast.success(state.message ?? 'Stopping the demo job…');
    } catch {
      setIsStopping(false);
      toast.error('Could not stop the demo job');
    }
  };

  if (isLoadingSettings || isLoadingPlayground) {
    return (
      <Card>
        <CardContent className="flex items-center gap-2 py-8 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading Audio Mix tools…
        </CardContent>
      </Card>
    );
  }

  const rawOutput = mediaUrl(playground?.output_url ?? null);
  const shownOutput = rawOutput
    ? `${rawOutput}${rawOutput.includes('?') ? '&' : '?'}v=${
        playground?.output_version ?? 0
      }`
    : null;
  const hasRunningJob = playground?.status === 'PROCESSING';
  const isBusy = isGenerating || isApplying || hasRunningJob;
  const canRemix = Boolean(playground?.can_remix) && !isBusy;
  const musicUnavailable = musicEngine !== null && !musicEngine.available;
  const canApplyMusic =
    canRemix &&
    !(
      musicSource === 'generated' &&
      musicUnavailable &&
      (!playground?.generated_music_ready || regenerateMusic)
    );
  const jobLabel =
    playground?.job === 'BASE'
      ? 'Narrating blocks and rendering the base video'
      : playground?.job === 'MIX'
        ? 'Preparing and applying background music'
        : 'Working';

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <Waves className="h-5 w-5 text-primary" />
            Audio Mix
          </CardTitle>
          <CardDescription>
            These values apply to every project on this account the next time
            audio is mixed, and to the demo below. They are stored per account.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="grid gap-6 sm:grid-cols-2">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium flex items-center gap-1.5">
                  <Music className="h-4 w-4 text-muted-foreground" />
                  Base music level
                </label>
                <span className="text-sm tabular-nums text-muted-foreground">
                  {formatDb(bgmGain)}
                </span>
              </div>
              <Slider
                value={[bgmGain]}
                min={-40}
                max={0}
                step={1}
                onValueChange={(values) => setBgmGain(values[0])}
              />
              <p className="text-xs text-muted-foreground">
                How loud the background bed sits under the narration.
              </p>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium flex items-center gap-1.5">
                  <Mic2 className="h-4 w-4 text-muted-foreground" />
                  TTS voice volume
                </label>
                <span className="text-sm tabular-nums text-muted-foreground">
                  {formatDb(ttsGain)}
                </span>
              </div>
              <Slider
                value={[ttsGain]}
                min={-24}
                max={12}
                step={1}
                onValueChange={(values) => setTtsGain(values[0])}
              />
              <p className="text-xs text-muted-foreground">
                Raises or lowers the narration against the music.
              </p>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium flex items-center gap-1.5">
                  <Volume2 className="h-4 w-4 text-muted-foreground" />
                  Voice-over ducking
                </label>
                <span className="text-sm tabular-nums text-muted-foreground">
                  {formatDb(bgmDucking)}
                </span>
              </div>
              <Slider
                value={[bgmDucking]}
                min={-30}
                max={0}
                step={1}
                onValueChange={(values) => setBgmDucking(values[0])}
              />
              <p className="text-xs text-muted-foreground">
                How much the music drops while the voice is speaking.
              </p>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium flex items-center gap-1.5">
                  <Waves className="h-4 w-4 text-muted-foreground" />
                  Echo
                </label>
                <span className="text-sm tabular-nums text-muted-foreground">
                  {bgmEcho.toFixed(0)}%
                </span>
              </div>
              <Slider
                value={[bgmEcho]}
                min={0}
                max={100}
                step={1}
                onValueChange={(values) => setBgmEcho(values[0])}
              />
              <p className="text-xs text-muted-foreground">
                Adds a short reflected tail to the background music only.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Button onClick={() => void saveMixSettings()} disabled={isSavingSettings}>
              {isSavingSettings ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Save className="mr-2 h-4 w-4" />
              )}
              Save Mix Settings
            </Button>
            <p className="text-xs text-muted-foreground">
              Saving also updates every existing project on this account.
            </p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <Sparkles className="h-5 w-5 text-primary" />
            Demo Playground
          </CardTitle>
          <CardDescription>
            Three blocks with an uploaded image and a script. Generate the TTS
            and base video once, then press <strong>Apply Background Music</strong>
            {' '}— MusicGen composes a soundtrack for this script and mixes it
            into the existing video without re-rendering it. Jobs keep running
            if you reload this page.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="space-y-2">
            <label className="text-sm font-medium">Background music</label>
            <select
              value={musicSource}
              onChange={(event) =>
                handleMusicSourceChange(event.target.value as MusicSource)
              }
              className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm"
            >
              <option value="generated">
                Generate with MusicGen (default)
              </option>
              <option value="library">Use a track from the BGM Library</option>
              <option value="none">No background music</option>
            </select>

            {musicSource === 'generated' && (
              <div className="space-y-2 rounded-md border bg-muted/20 p-3">
                <p className="flex items-start gap-2 text-xs text-muted-foreground">
                  <Wand2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" />
                  <span>
                    {musicUnavailable && !playground?.generated_music_ready
                      ? `MusicGen is unavailable: ${
                          musicEngine?.reason ?? 'check the backend setup'
                        }`
                      : playground?.generated_music_ready
                        ? 'A generated soundtrack is ready for this demo. Applying re-uses it so slider changes stay fast.'
                        : playground?.generated_music_stale
                          ? 'The script changed since the last soundtrack. Applying composes a new one.'
                          : 'Applying will compose a soundtrack for this script with MusicGen, then mix it into the existing video.'}
                  </span>
                </p>
                <label className="flex items-center gap-2 text-xs text-muted-foreground">
                  <input
                    type="checkbox"
                    checked={regenerateMusic}
                    onChange={(event) =>
                      setRegenerateMusic(event.target.checked)
                    }
                    className="h-3.5 w-3.5 rounded border-input"
                  />
                  Compose a new soundtrack now (slower)
                </label>
              </div>
            )}

            {musicSource === 'library' && (
              <>
                <select
                  value={selectedClip}
                  onChange={(event) => setSelectedClip(event.target.value)}
                  className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm"
                >
                  <option value="">No background music</option>
                  {clips.map((clip) => (
                    <option key={clip.id} value={clip.id}>
                      {clip.name}
                      {clip.source === 'generated' ? ' · generated' : ''}
                    </option>
                  ))}
                </select>
                <p className="text-xs text-muted-foreground">
                  Pick any track from the account BGM Library or a shared track.
                </p>
              </>
            )}
          </div>

          <Separator />

          <div className="grid gap-4 lg:grid-cols-3">
            {drafts.map((text, index) => {
              const block = playground?.blocks.find((item) => item.index === index);
              const imageUrl = mediaUrl(block?.image_url ?? null);
              return (
                <div key={index} className="space-y-2 rounded-lg border p-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Block {index + 1}</span>
                    <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
                      {block?.has_audio ? 'narrated' : 'no audio yet'}
                    </span>
                  </div>

                  <div className="relative aspect-video overflow-hidden rounded-md border bg-muted/20">
                    {imageUrl ? (
                      <>
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={imageUrl}
                          alt={`Block ${index + 1}`}
                          className="h-full w-full object-cover"
                        />
                        <Button
                          type="button"
                          variant="destructive"
                          size="icon"
                          className="absolute right-1 top-1 h-6 w-6"
                          onClick={() => void handleRemoveImage(index)}
                          disabled={isUploadingIndex === index}
                        >
                          <Trash2 className="h-3 w-3" />
                        </Button>
                      </>
                    ) : (
                      <button
                        type="button"
                        onClick={() => fileInputs.current[index]?.click()}
                        className="flex h-full w-full flex-col items-center justify-center gap-1 text-xs text-muted-foreground hover:bg-muted/40"
                      >
                        {isUploadingIndex === index ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Upload className="h-4 w-4" />
                        )}
                        Upload image
                      </button>
                    )}
                  </div>
                  <input
                    ref={(element) => {
                      fileInputs.current[index] = element;
                    }}
                    type="file"
                    accept="image/png,image/jpeg,image/webp,image/gif"
                    className="hidden"
                    onChange={(event) => {
                      const file = event.target.files?.[0];
                      if (file) void handleUpload(index, file);
                    }}
                  />

                  <textarea
                    value={text}
                    onChange={(event) => {
                      const next = [...drafts];
                      next[index] = event.target.value;
                      setDrafts(next);
                    }}
                    rows={5}
                    placeholder={`Script text for block ${index + 1}…`}
                    className="w-full resize-y rounded-md border border-input bg-background px-2 py-1.5 text-xs"
                  />
                </div>
              );
            })}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="outline"
              onClick={() => void saveBlocks()}
              disabled={isSavingPlayground || isBusy}
            >
              {isSavingPlayground ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Save className="mr-2 h-4 w-4" />
              )}
              Save Blocks
            </Button>
            <Button onClick={() => void handleGenerate()} disabled={isBusy}>
              {isBusy && playground?.job === 'BASE' ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Film className="mr-2 h-4 w-4" />
              )}
              Generate TTS + Video
            </Button>
            <Button
              variant="outline"
              onClick={() => void handleApplyBgm()}
              disabled={!canApplyMusic}
              title={
                !canRemix
                  ? 'Generate the demo video first'
                  : musicSource === 'generated' && musicUnavailable
                    ? musicEngine?.reason ?? 'MusicGen is unavailable'
                    : musicSource === 'generated'
                      ? 'Compose a MusicGen soundtrack for this script and mix it into the existing video'
                      : 'Apply the selected track and Audio Mix values to the existing video'
              }
            >
              {isBusy && playground?.job === 'MIX' ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : musicSource === 'generated' ? (
                <Wand2 className="mr-2 h-4 w-4" />
              ) : (
                <Music className="mr-2 h-4 w-4" />
              )}
              Apply Background Music
            </Button>
            {hasRunningJob && (
              <Button
                variant="destructive"
                onClick={() => void handleStop()}
                disabled={isStopping || playground?.cancel_requested}
              >
                {isStopping || playground?.cancel_requested ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Square className="mr-2 h-4 w-4" />
                )}
                {isStopping || playground?.cancel_requested
                  ? 'Stopping…'
                  : 'Stop'}
              </Button>
            )}
            <Button variant="ghost" onClick={() => void loadPlayground()}>
              <RefreshCw className="mr-2 h-4 w-4" />
              Refresh
            </Button>
            <span className="text-xs text-muted-foreground">
              Regenerating TTS + Video replaces the base without music; applying
              background music composes/re-uses a soundtrack and only re-mixes
              the existing base.
            </span>
          </div>

          {hasRunningJob && (
            <div className="space-y-2 rounded-md border bg-muted/20 p-3">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                {jobLabel}
                {playground?.progress_description
                  ? ` — ${playground.progress_description}`
                  : '…'}
              </div>
              <Progress value={playground?.progress ?? undefined} className="h-1.5" />
              <p className="text-[11px] text-muted-foreground">
                This runs in the background. You can reload the page and the
                job will continue.
              </p>
            </div>
          )}

          {shownOutput && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-medium">Latest demo</h3>
                <a
                  href={shownOutput}
                  download
                  className="text-xs text-primary hover:underline"
                >
                  Download
                </a>
              </div>
              <video
                key={shownOutput}
                src={shownOutput}
                controls
                className="w-full rounded-lg border bg-black"
              />
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
