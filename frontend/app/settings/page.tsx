'use client';

import { useState, useRef, useEffect } from 'react';
import { testTTS, getVoices } from '@/lib/api';
import { AVAILABLE_VOICES, type Voice } from '@/lib/constants';
import { useSettingsStore as useLogoStore } from '@/lib/stores';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { Slider } from '@/components/ui/slider';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Volume2, Loader2, Play, Square, Type, Save, Image as ImageIcon, Trash2, Upload, Film } from 'lucide-react';
import { useSettingsStore } from '@/store/settingsStore';
import { toast } from 'sonner';
import { SettingsSkeleton } from '@/components/skeletons';

export default function SettingsPage() {
  // TTS Tester state
  const [ttsText, setTtsText] = useState('Hello! This is a test of the StoryFlow text to speech engine.');
  const [ttsVoice, setTtsVoice] = useState('af_bella');
  const [ttsSpeed, setTtsSpeed] = useState(1.0);
  const [isGenerating, setIsGenerating] = useState(false);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [ttsError, setTtsError] = useState<string | null>(null);
  const [voices, setVoices] = useState<Voice[]>([]);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Subtitle settings state
  const { settings, fetchSettings, saveSettings } = useSettingsStore();
  const [subtitleFontSize, setSubtitleFontSize] = useState(48);
  const [subtitlePosition, setSubtitlePosition] = useState<'bottom' | 'center' | 'top'>('bottom');
  const [subtitleFontColor, setSubtitleFontColor] = useState('#FFFFFF');
  const [isSavingSubtitles, setIsSavingSubtitles] = useState(false);
  const [subtitleSaveMsg, setSubtitleSaveMsg] = useState<string | null>(null);

  // Logo management state
  const {
    logos,
    isLogosLoading,
    isLogoUploading,
    fetchLogos,
    uploadLogo,
    deleteLogo,
    outroVideos,
    isOutrosLoading,
    isOutroUploading,
    fetchOutroVideos,
    uploadOutroVideo,
    deleteOutroVideo,
  } = useLogoStore();
  const logoInputRef = useRef<HTMLInputElement>(null);
  const outroInputRef = useRef<HTMLInputElement>(null);

  // Fetch settings on mount
  useEffect(() => {
    fetchSettings();
    fetchLogos();
    fetchOutroVideos();
  }, [fetchSettings, fetchLogos, fetchOutroVideos]);

  // Sync local state when settings load
  useEffect(() => {
    if (settings) {
      setSubtitleFontSize(settings.subtitle_font_size ?? 48);
      setSubtitlePosition(settings.subtitle_position ?? 'bottom');
      setSubtitleFontColor(settings.subtitle_font_color ?? '#FFFFFF');
    }
  }, [settings]);

  // Load available voices
  useEffect(() => {
    getVoices()
      .then((data) => setVoices(data))
      .catch(() => {
        setVoices(AVAILABLE_VOICES);
      });
  }, []);

  // Cleanup audio URL on unmount
  useEffect(() => {
    return () => {
      if (audioUrl) URL.revokeObjectURL(audioUrl);
    };
  }, [audioUrl]);

  const handleGenerateAudio = async () => {
    if (!ttsText.trim()) return;

    setIsGenerating(true);
    setTtsError(null);

    // Stop current audio if playing
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
      setIsPlaying(false);
    }

    // Revoke old URL
    if (audioUrl) {
      URL.revokeObjectURL(audioUrl);
      setAudioUrl(null);
    }

    try {
      const blob = await testTTS(ttsText, ttsVoice, ttsSpeed);

      // Check if the response is actually an error JSON
      if (blob.type === 'application/json') {
        const text = await blob.text();
        const err = JSON.parse(text);
        setTtsError(err.error || 'TTS generation failed');
        return;
      }

      const url = URL.createObjectURL(blob);
      setAudioUrl(url);
    } catch (err: unknown) {
      const error = err as { response?: { data?: Blob } };
      if (error.response?.data) {
        try {
          const text = await error.response.data.text();
          const parsed = JSON.parse(text);
          setTtsError(parsed.error || 'TTS generation failed');
        } catch {
          setTtsError('TTS generation failed. Check the backend server.');
        }
      } else {
        setTtsError('TTS generation failed. Check the backend server.');
      }
    } finally {
      setIsGenerating(false);
    }
  };

  const handlePlayAudio = () => {
    if (!audioUrl) return;

    if (isPlaying && audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
      setIsPlaying(false);
      return;
    }

    const audio = new Audio(audioUrl);
    audioRef.current = audio;
    audio.onended = () => {
      setIsPlaying(false);
      audioRef.current = null;
    };
    audio.onerror = () => {
      setIsPlaying(false);
      audioRef.current = null;
      setTtsError('Failed to play audio');
    };
    audio.play();
    setIsPlaying(true);
  };

  // Show skeleton while initial settings are loading
  const isInitialLoading = !settings && !voices.length;

  if (isInitialLoading) {
    return <SettingsSkeleton />;
  }

  return (
    <div className="max-w-3xl">
      {/* Page header */}
      <div className="mb-6">
        <h2 className="text-2xl font-bold tracking-tight">Settings</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Configure and test TTS audio before generating for your story segments.
        </p>
      </div>

      {/* TTS Tester Card */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/10">
              <Volume2 className="h-4 w-4 text-primary" />
            </div>
            <div>
              <CardTitle className="text-lg">TTS Audio Tester</CardTitle>
              <CardDescription>
                Test voice settings with custom text before applying to your project.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-5">
          {/* Voice selector */}
          <div className="space-y-2">
            <label htmlFor="tts-voice" className="text-sm font-medium">
              Voice
            </label>
            <select
              id="tts-voice"
              value={ttsVoice}
              onChange={(e) => setTtsVoice(e.target.value)}
              className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              {voices.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.name} ({v.gender}{v.accent ? `, ${v.accent}` : ''})
                </option>
              ))}
            </select>
          </div>

          {/* Speed control — using Slider */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium">Speed</label>
              <span className="text-sm font-medium tabular-nums text-muted-foreground">
                {ttsSpeed.toFixed(1)}x
              </span>
            </div>
            <Slider
              value={[ttsSpeed]}
              min={0.5}
              max={2.0}
              step={0.1}
              onValueChange={(values) => setTtsSpeed(values[0])}
            />
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">0.5x</span>
              <span className="text-xs text-muted-foreground">2.0x</span>
            </div>
          </div>

          <Separator />

          {/* Text input */}
          <div className="space-y-2">
            <label htmlFor="tts-text" className="text-sm font-medium">
              Text to Speak
            </label>
            <textarea
              id="tts-text"
              value={ttsText}
              onChange={(e) => setTtsText(e.target.value)}
              rows={5}
              placeholder="Enter text to convert to speech..."
              className="flex min-h-20 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring resize-y"
            />
            <p className="text-xs text-muted-foreground text-right">
              {ttsText.length} characters
            </p>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-3">
            <Button
              onClick={handleGenerateAudio}
              disabled={isGenerating || !ttsText.trim()}
            >
              {isGenerating ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Generating...
                </>
              ) : (
                <>
                  <Volume2 className="h-4 w-4 mr-2" />
                  Generate Audio
                </>
              )}
            </Button>

            {audioUrl && (
              <Button
                variant="outline"
                onClick={handlePlayAudio}
              >
                {isPlaying ? (
                  <>
                    <Square className="h-4 w-4 mr-2" />
                    Stop
                  </>
                ) : (
                  <>
                    <Play className="h-4 w-4 mr-2" />
                    Play
                  </>
                )}
              </Button>
            )}
          </div>

          {/* Audio player */}
          {audioUrl && (
            <div className="rounded-md bg-muted/50 p-3">
              <audio controls src={audioUrl} className="w-full" />
            </div>
          )}

          {/* Error display */}
          {ttsError && (
            <div className="rounded-md bg-destructive/10 border border-destructive/20 p-3 text-sm text-destructive">
              {ttsError}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Subtitle Settings Card */}
      <Card className="mt-6">
        <CardHeader>
          <div className="flex items-center gap-2">
            <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/10">
              <Type className="h-4 w-4 text-primary" />
            </div>
            <div>
              <CardTitle className="text-lg">Subtitle Settings</CardTitle>
              <CardDescription>
                Adjust subtitle appearance for rendered videos.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-5">
          {/* Font Size */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium">Font Size</label>
              <span className="text-sm font-medium tabular-nums text-muted-foreground">
                {subtitleFontSize}px
              </span>
            </div>
            <Slider
              value={[subtitleFontSize]}
              min={12}
              max={120}
              step={1}
              onValueChange={(values) => setSubtitleFontSize(values[0])}
            />
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">12px</span>
              <span className="text-xs text-muted-foreground">120px</span>
            </div>
          </div>

          {/* Position */}
          <div className="space-y-2">
            <label htmlFor="subtitle-position" className="text-sm font-medium">
              Position
            </label>
            <select
              id="subtitle-position"
              value={subtitlePosition}
              onChange={(e) => setSubtitlePosition(e.target.value as 'bottom' | 'center' | 'top')}
              className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              <option value="bottom">Bottom</option>
              <option value="center">Center</option>
              <option value="top">Top</option>
            </select>
          </div>

          {/* Font Color */}
          <div className="space-y-2">
            <label className="text-sm font-medium">Font Color</label>
            <div className="flex items-center gap-3">
              <input
                type="color"
                value={subtitleFontColor}
                onChange={(e) => setSubtitleFontColor(e.target.value)}
                className="h-9 w-12 rounded-md border border-input bg-background p-1 cursor-pointer"
              />
              <input
                type="text"
                value={subtitleFontColor}
                onChange={(e) => {
                  const val = e.target.value;
                  if (/^#[0-9A-Fa-f]{0,6}$/.test(val)) setSubtitleFontColor(val);
                }}
                maxLength={7}
                className="flex h-9 w-28 rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm font-mono transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              />
            </div>
          </div>

          <Separator />

          {/* Save */}
          <div className="flex items-center gap-3">
            <Button
              onClick={async () => {
                setIsSavingSubtitles(true);
                setSubtitleSaveMsg(null);
                try {
                  await saveSettings({
                    subtitle_font_size: subtitleFontSize,
                    subtitle_position: subtitlePosition,
                    subtitle_font_color: subtitleFontColor,
                  });
                  setSubtitleSaveMsg('Saved successfully');
                  setTimeout(() => setSubtitleSaveMsg(null), 3000);
                } catch {
                  setSubtitleSaveMsg('Failed to save');
                } finally {
                  setIsSavingSubtitles(false);
                }
              }}
              disabled={isSavingSubtitles}
            >
              {isSavingSubtitles ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Save className="h-4 w-4 mr-2" />
                  Save Subtitle Settings
                </>
              )}
            </Button>

            {subtitleSaveMsg && (
              <span className={`text-sm ${subtitleSaveMsg.includes('Failed') ? 'text-destructive' : 'text-green-600'}`}>
                {subtitleSaveMsg}
              </span>
            )}
          </div>
        </CardContent>
      </Card>

      {/* ── Logo Management Card ── */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ImageIcon className="h-5 w-5" />
            Logo Management
          </CardTitle>
          <CardDescription>
            Upload logos to burn into your rendered videos as watermarks.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Upload Button */}
          <div>
            <input
              ref={logoInputRef}
              type="file"
              accept=".png,.webp,.jpg,.jpeg"
              className="hidden"
              onChange={async (e) => {
                const file = e.target.files?.[0];
                if (!file) return;

                // Validate size
                if (file.size > 5 * 1024 * 1024) {
                  toast.error('Logo file must be under 5 MB');
                  return;
                }

                try {
                  await uploadLogo(file);
                  toast.success('Logo uploaded successfully');
                } catch {
                  toast.error('Failed to upload logo');
                }

                // Reset input
                if (logoInputRef.current) logoInputRef.current.value = '';
              }}
            />
            <Button
              variant="outline"
              onClick={() => logoInputRef.current?.click()}
              disabled={isLogoUploading}
            >
              {isLogoUploading ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Uploading…
                </>
              ) : (
                <>
                  <Upload className="h-4 w-4 mr-2" />
                  Upload Logo
                </>
              )}
            </Button>
            <p className="text-xs text-muted-foreground mt-1">
              PNG recommended for transparency. Max 5 MB.
            </p>
          </div>

          <Separator />

          {/* Logo Grid */}
          {isLogosLoading ? (
            <div className="flex items-center gap-2 text-muted-foreground text-sm">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading logos…
            </div>
          ) : logos.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No logos uploaded yet. Upload a logo to use as a video watermark.
            </p>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
              {logos.map((logo) => (
                <div
                  key={logo.id}
                  className="relative group border rounded-lg p-2 flex flex-col items-center gap-2"
                >
                  <div className="w-full aspect-square bg-muted/30 rounded flex items-center justify-center overflow-hidden">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={`http://localhost:8000${logo.file}`}
                      alt={logo.name}
                      className="max-w-full max-h-full object-contain"
                    />
                  </div>
                  <span className="text-xs text-muted-foreground truncate w-full text-center">
                    {logo.name}
                  </span>
                  <Button
                    size="sm"
                    variant="destructive"
                    className="absolute top-1 right-1 h-7 w-7 p-0 opacity-0 group-hover:opacity-100 transition-opacity"
                    onClick={async () => {
                      try {
                        await deleteLogo(logo.id);
                        toast.success('Logo deleted');
                      } catch {
                        toast.error('Failed to delete logo');
                      }
                    }}
                  >
                    <Trash2 className="h-3 w-3" />
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* ── Outro Video Management Card ── */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Film className="h-5 w-5" />
            Outro Video Management
          </CardTitle>
          <CardDescription>
            Upload outro/logo animation videos to append at the end of rendered videos.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Upload Button */}
          <div>
            <input
              ref={outroInputRef}
              type="file"
              accept=".mp4,.mov,.webm,.avi,.mkv"
              className="hidden"
              onChange={async (e) => {
                const file = e.target.files?.[0];
                if (!file) return;
                if (file.size > 100 * 1024 * 1024) {
                  toast.error('Outro video file must be under 100 MB');
                  return;
                }
                try {
                  await uploadOutroVideo(file);
                  toast.success('Outro video uploaded successfully');
                } catch {
                  toast.error('Failed to upload outro video');
                }
                if (outroInputRef.current) outroInputRef.current.value = '';
              }}
            />
            <Button
              variant="outline"
              onClick={() => outroInputRef.current?.click()}
              disabled={isOutroUploading}
            >
              {isOutroUploading ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Uploading…
                </>
              ) : (
                <>
                  <Upload className="h-4 w-4 mr-2" />
                  Upload Outro Video
                </>
              )}
            </Button>
            <p className="text-xs text-muted-foreground mt-1">
              MP4 recommended. Max 100 MB.
            </p>
          </div>

          <Separator />

          {/* Outro Videos List */}
          {isOutrosLoading ? (
            <div className="flex items-center gap-2 text-muted-foreground text-sm">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading outro videos…
            </div>
          ) : outroVideos.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No outro videos uploaded yet. Upload a video to append at the end of your renders.
            </p>
          ) : (
            <div className="space-y-2">
              {outroVideos.map((outro) => (
                <div
                  key={outro.id}
                  className="flex items-center justify-between gap-3 border rounded-lg p-3 group"
                >
                  <div className="flex items-center gap-3 min-w-0 flex-1">
                    <Film className="h-5 w-5 text-muted-foreground flex-shrink-0" />
                    <div className="min-w-0">
                      <p className="text-sm font-medium truncate">
                        {outro.name}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        Uploaded {new Date(outro.uploaded_at).toLocaleDateString()}
                      </p>
                    </div>
                  </div>
                  <Button
                    size="sm"
                    variant="destructive"
                    className="h-8 w-8 p-0 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0"
                    onClick={async () => {
                      try {
                        await deleteOutroVideo(outro.id);
                        toast.success('Outro video deleted');
                      } catch {
                        toast.error('Failed to delete outro video');
                      }
                    }}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
