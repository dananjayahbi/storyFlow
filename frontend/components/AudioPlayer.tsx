'use client';

import { useRef, useState, useEffect, useCallback } from 'react';
import { Play, Pause, Loader2, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Slider } from '@/components/ui/slider';
import { cn, formatTime } from '@/lib/utils';

interface AudioPlayerProps {
  /** Full URL to the .wav file (relative or absolute). */
  audioUrl: string;
  /** Duration in seconds from the database. */
  duration: number;
  /** Optional additional class names. */
  className?: string;
}

export function AudioPlayer({ audioUrl, duration, className }: AudioPlayerProps) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [isLoaded, setIsLoaded] = useState(false);
  const [hasError, setHasError] = useState(false);

  // Cache-busting URL to force re-fetch after regeneration
  const [cacheBuster, setCacheBuster] = useState(() => Date.now());

  const effectiveUrl = `${audioUrl}?t=${cacheBuster}`;

  // ── Reset when audioUrl changes (e.g. after regeneration) ──
  useEffect(() => {
    setCurrentTime(0);
    setIsPlaying(false);
    setIsLoaded(false);
    setHasError(false);
    setCacheBuster(Date.now());
  }, [audioUrl]);

  // ── Wire audio events ──
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const onTimeUpdate = () => setCurrentTime(audio.currentTime);
    const onLoadedMetadata = () => setIsLoaded(true);
    const onEnded = () => {
      setIsPlaying(false);
      setCurrentTime(0);
    };
    const onError = () => {
      setHasError(true);
      setIsPlaying(false);
    };

    audio.addEventListener('timeupdate', onTimeUpdate);
    audio.addEventListener('loadedmetadata', onLoadedMetadata);
    audio.addEventListener('ended', onEnded);
    audio.addEventListener('error', onError);

    return () => {
      audio.removeEventListener('timeupdate', onTimeUpdate);
      audio.removeEventListener('loadedmetadata', onLoadedMetadata);
      audio.removeEventListener('ended', onEnded);
      audio.removeEventListener('error', onError);
      // Cleanup on unmount
      audio.pause();
      audio.removeAttribute('src');
      audio.load();
    };
  }, [effectiveUrl]);

  // ── Play / Pause toggle ──
  const togglePlay = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;

    if (isPlaying) {
      audio.pause();
      setIsPlaying(false);
    } else {
      audio.play().catch(() => {
        // Browser autoplay policy blocked playback
        setIsPlaying(false);
      });
      setIsPlaying(true);
    }
  }, [isPlaying]);

  // ── Seek via Slider ──
  const handleSeek = useCallback((value: number[]) => {
    const audio = audioRef.current;
    if (!audio || !value.length) return;

    const newTime = value[0];
    audio.currentTime = newTime;
    setCurrentTime(newTime);
  }, []);

  // ── Error state ──
  if (hasError) {
    return (
      <div className={cn('flex items-center gap-2 text-sm text-destructive', className)}>
        <AlertCircle className="h-4 w-4" />
        <span>Audio unavailable</span>
      </div>
    );
  }

  // ── Loading state ──
  if (!isLoaded) {
    return (
      <div className={cn('flex items-center gap-2', className)}>
        {/* Hidden audio element to start loading metadata */}
        <audio ref={audioRef} src={effectiveUrl} preload="metadata" />
        <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
        <span className="text-xs text-muted-foreground">Loading audio…</span>
      </div>
    );
  }

  // ── Player UI ──
  return (
    <div className={cn('flex flex-col gap-1 sm:flex-row sm:items-center sm:gap-2', className)}>
      {/* Hidden audio element */}
      <audio ref={audioRef} src={effectiveUrl} preload="metadata" />

      {/* Top row: play button + slider */}
      <div className="flex items-center gap-2 w-full">
        {/* Play / Pause button — 44×44 touch target on mobile */}
        <Button
          variant="ghost"
          size="icon"
          className="h-11 w-11 shrink-0 sm:h-7 sm:w-7"
          onClick={togglePlay}
          aria-label={isPlaying ? 'Pause' : 'Play'}
        >
          {isPlaying ? (
            <Pause className="h-5 w-5 sm:h-4 sm:w-4" />
          ) : (
            <Play className="h-5 w-5 sm:h-4 sm:w-4" />
          )}
        </Button>

        {/* Seek slider */}
        <Slider
          value={[currentTime]}
          min={0}
          max={duration}
          step={0.1}
          onValueChange={handleSeek}
          className="flex-1 min-w-[120px]"
          aria-label="Audio seek"
        />

        {/* Time display — inline on sm+ */}
        <span className="hidden sm:inline shrink-0 text-xs tabular-nums text-muted-foreground">
          {formatTime(currentTime)} / {formatTime(duration)}
        </span>
      </div>

      {/* Time display — stacked below on mobile */}
      <span className="sm:hidden text-xs tabular-nums text-muted-foreground pl-13">
        {formatTime(currentTime)} / {formatTime(duration)}
      </span>
    </div>
  );
}
