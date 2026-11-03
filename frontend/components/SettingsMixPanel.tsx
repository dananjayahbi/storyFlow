'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  getBgmClips,
  getPlayground,
  getSettings,
  savePlayground,
  generatePlayground,
  updateSettings,
  uploadPlaygroundImage,
  removePlaygroundImage,
} from '@/lib/api';
import type { BgmClip, PlaygroundState } from '@/lib/types';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Slider } from '@/components/ui/slider';
import { Separator } from '@/components/ui/separator';
import { Progress } from '@/components/ui/progress';
import { toast } from 'sonner';
import {
  Loader2, Music, Save, Sparkles, Upload, Trash2, Volume2,
  Waves, Mic2, RefreshCw, Film,
} from 'lucide-react';

const API_BASE = 'http://localhost:8765';
const POLL_INTERVAL_MS = 2000;

function mediaUrl(path: string | null): string | null {
  if (!path) return null;
  if (path.startsWith('http://') || path.startsWith('https://')) return path;
  return `${API_BASE}${path.startsWith('/') ? '' : '/'}${path}`;
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
  const [isLoadingPlayground, setIsLoadingPlayground] = useState(true);
  const [isSavingPlayground, setIsSavingPlayground] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isUploadingIndex, setIsUploadingIndex] = useState<number | null>(null);
  const fileInputs = useRef<Array<HTMLInputElement | null>>([]);
  const pollTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const loadPlayground = useCallback(async () => {
    try {
      const state = await getPlayground();
      setPlayground(state);
      setDrafts(state.blocks.map((block) => block.text_content));
      setSelectedClip(state.bgm_clip ?? '');
      setIsGenerating(state.status === 'PROCESSING');
      setIsLoadingPlayground(false);
      return state;
    } catch {
      setIsLoadingPlayground(false);
      toast.error('Failed to load the demo playground');
      return null;
    }
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

    return () => {
      if (pollTimer.current) clearTimeout(pollTimer.current);
    };
  }, [loadPlayground]);

  // Poll while a demo render is running so the preview appears as soon as it
  // finishes. The backend replaces the previous output in place.
  useEffect(() => {
    if (!isGenerating) return;
    pollTimer.current = setTimeout(async () => {
      const state = await loadPlayground();
      if (state && state.status !== 'PROCESSING') {
        setIsGenerating(false);
        if (state.status === 'COMPLETED') {
          toast.success('Demo video ready');
        } else if (state.status === 'FAILED') {
          toast.error('Demo generation failed. Check the backend log.');
        }
      }
    }, POLL_INTERVAL_MS);
    return () => {
      if (pollTimer.current) clearTimeout(pollTimer.current);
    };
  }, [isGenerating, loadPlayground, playground?.status]);

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

  const saveBlocks = useCallback(async () => {
    setIsSavingPlayground(true);
    try {
      const state = await savePlayground({
        blocks: drafts.map((text_content) => ({ text_content })),
        bgm_clip: selectedClip || null,
      });
      setPlayground(state);
      setDrafts(state.blocks.map((block) => block.text_content));
      toast.success('Demo blocks saved');
      return state;
    } catch {
      toast.error('Failed to save demo blocks');
      throw new Error('save failed');
    } finally {
      setIsSavingPlayground(false);
    }
  }, [drafts, selectedClip]);

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

  const handleGenerate = async () => {
    setIsGenerating(true);
    try {
      // Persist the current tuning and block text first so the demo always
      // reflects exactly what the sliders show.
      await saveMixSettings();
      await saveBlocks();
      await generatePlayground({
        bgm_clip: selectedClip || null,
      });
      toast.success('Demo generation started');
      await loadPlayground();
    } catch {
      setIsGenerating(false);
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

  const shownOutput = mediaUrl(playground?.output_url ?? null);
  const isBusy = isGenerating || playground?.status === 'PROCESSING';

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
            Three blocks with an uploaded image and a script. Generate the demo
            as often as you like; each run replaces the previous video.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="space-y-2">
            <label className="text-sm font-medium">Background track</label>
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
              {isBusy ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Film className="mr-2 h-4 w-4" />
              )}
              {isBusy ? 'Generating demo…' : 'Generate Demo Video'}
            </Button>
            <Button
              variant="ghost"
              onClick={() => void loadPlayground()}
              disabled={isBusy}
            >
              <RefreshCw className="mr-2 h-4 w-4" />
              Refresh
            </Button>
            <span className="text-xs text-muted-foreground">
              Each run replaces the previous demo video.
            </span>
          </div>

          {isBusy && (
            <div className="space-y-2 rounded-md border bg-muted/20 p-3">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                Generating narration and rendering the demo…
              </div>
              <Progress value={undefined} className="h-1.5" />
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
