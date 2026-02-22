'use client';

import { useState, useRef, useEffect } from 'react';
import Link from 'next/link';
import { testTTS, getVoices } from '@/lib/api';
import { AVAILABLE_VOICES, type Voice } from '@/lib/constants';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { ArrowLeft, Volume2, Loader2, Play, Square } from 'lucide-react';

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
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-3">
          <Button variant="outline" size="sm" asChild>
            <Link href="/">
              <ArrowLeft className="h-4 w-4 mr-1" />
              Back to Dashboard
            </Link>
          </Button>
          <h2 className="text-3xl font-bold">Settings</h2>
        </div>
      </div>

      {/* TTS Tester Section */}
      <div className="border rounded-lg p-6 max-w-3xl">
        <div className="flex items-center gap-2 mb-4">
          <Volume2 className="h-5 w-5" />
          <h3 className="text-xl font-semibold">TTS Audio Tester</h3>
        </div>
        <p className="text-sm text-muted-foreground mb-4">
          Test the text-to-speech engine by entering text below and generating audio.
          Use this to verify audio quality before generating for your story segments.
        </p>

        <Separator className="my-4" />

        <div className="space-y-4">
          {/* Voice selector */}
          <div>
            <label htmlFor="tts-voice" className="text-sm font-medium block mb-1">
              Voice
            </label>
            <select
              id="tts-voice"
              value={ttsVoice}
              onChange={(e) => setTtsVoice(e.target.value)}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            >
              {voices.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.name} ({v.gender}{v.accent ? `, ${v.accent}` : ''})
                </option>
              ))}
            </select>
          </div>

          {/* Speed control */}
          <div>
            <label htmlFor="tts-speed" className="text-sm font-medium block mb-1">
              Speed: {ttsSpeed.toFixed(1)}x
            </label>
            <div className="flex items-center gap-3">
              <span className="text-xs text-muted-foreground">0.5x</span>
              <input
                id="tts-speed"
                type="range"
                min="0.5"
                max="2.0"
                step="0.1"
                value={ttsSpeed}
                onChange={(e) => setTtsSpeed(parseFloat(e.target.value))}
                className="flex-1"
              />
              <span className="text-xs text-muted-foreground">2.0x</span>
            </div>
          </div>

          {/* Text input */}
          <div>
            <label htmlFor="tts-text" className="text-sm font-medium block mb-1">
              Text to Speak
            </label>
            <textarea
              id="tts-text"
              value={ttsText}
              onChange={(e) => setTtsText(e.target.value)}
              rows={5}
              placeholder="Enter text to convert to speech..."
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            />
            <p className="text-xs text-muted-foreground text-right mt-1">
              {ttsText.length} characters
            </p>
          </div>

          {/* Generate button */}
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
            <div className="mt-2">
              <audio controls src={audioUrl} className="w-full" />
            </div>
          )}

          {/* Error display */}
          {ttsError && (
            <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
              {ttsError}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
