'use client';

import { useState, useRef, useEffect } from 'react';
import { testTTS, getVoices } from '@/lib/api';
import { AVAILABLE_VOICES, type Voice } from '@/lib/constants';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { Slider } from '@/components/ui/slider';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Volume2, Loader2, Play, Square } from 'lucide-react';

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
    </div>
  );
}
