'use client';

import { useRef, useState, useEffect, useCallback } from 'react';
import { Play, Pause, Loader2, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Slider } from '@/components/ui/slider';
import { cn, formatTime } from '@/lib/utils';
import { getApiBaseUrl } from '@/lib/apiConfig';

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
  const isSeekingRef = useRef(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [isLoaded, setIsLoaded] = useState(false);
  const [hasError, setHasError] = useState(false);
  // Use the DB duration when available and fall back to the decoded metadata
  // (BGM tracks may not have a stored duration yet).
  const [resolvedDuration, setResolvedDuration] = useState(duration);

  // Cache-busting URL to force re-fetch after regeneration. Start at 0 so
  // server and client markup match; the effect below fills in the timestamp.
  const [cacheBuster, setCacheBuster] = useState(0);

  // audioUrl may be a relative path ("/media/...") served by Django or an absolute URL.
  // Prepend the backend base URL only if it's not already absolute (same pattern as ImageUploader).
  const backendBase = getApiBaseUrl();
  const resolvedUrl = audioUrl.startsWith('http') ? audioUrl : `${backendBase}${audioUrl}`;
  const effectiveUrl = `${resolvedUrl}?t=${cacheBuster}`;

  // ── Reset when audioUrl changes (e.g. after regeneration) ──
  /* eslint-disable react-hooks/set-state-in-effect -- synchronise the player with a new audio source */
  useEffect(() => {
    setCurrentTime(0);
    setIsPlaying(false);
    setIsLoaded(false);
    setHasError(false);
    setResolvedDuration(duration);
    setCacheBuster(Date.now());
  }, [audioUrl, duration]);
  /* eslint-enable react-hooks/set-state-in-effect */

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

  // Radix fires onValueChange continuously while dragging. Update the visual
  // position only; the actual media seek happens once on pointer/key commit.
  const handleSeekPreview = useCallback((value: number[]) => {
    if (!value.length) return;
    isSeekingRef.current = true;
    setCurrentTime(value[0]);
  }, []);

  const handleSeekCommit = useCallback((value: number[]) => {
    const audio = audioRef.current;
    if (!audio || !value.length) return;
    const newTime = Math.max(0, value[0]);
    try {
      audio.currentTime = newTime;
    } catch {
      // Metadata may not be available yet; the seeked/loadedmetadata events
      // will reconcile the display as soon as the browser is ready.
    }
    setCurrentTime(newTime);
    isSeekingRef.current = false;
  }, []);

  // ── Media element event handlers ──
  const handleLoadedMetadata = useCallback(() => {
    const audio = audioRef.current;
    setIsLoaded(true);
    if (audio && Number.isFinite(audio.duration) && audio.duration > 0) {
      setResolvedDuration(audio.duration);
    }
  }, []);

  const handleTimeUpdate = useCallback(() => {
    const audio = audioRef.current;
    if (!audio || isSeekingRef.current) return;
    setCurrentTime(audio.currentTime);
  }, []);

  const handleSeeked = useCallback(() => {
    const audio = audioRef.current;
    isSeekingRef.current = false;
    if (audio) setCurrentTime(audio.currentTime);
  }, []);

  const handleEnded = useCallback(() => {
    setIsPlaying(false);
    setCurrentTime(0);
  }, []);

  const handleError = useCallback(() => {
    setHasError(true);
    setIsPlaying(false);
  }, []);

  return (
    <div className={cn('flex flex-col gap-1 sm:flex-row sm:items-center sm:gap-2', className)}>
      {/* The <audio> element is always mounted so React never swaps the
          element (and its media session) while loading or after an error. */}
      <audio
        ref={audioRef}
        src={effectiveUrl}
        preload="auto"
        onLoadedMetadata={handleLoadedMetadata}
        onTimeUpdate={handleTimeUpdate}
        onSeeked={handleSeeked}
        onEnded={handleEnded}
        onError={handleError}
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
      />

      {hasError ? (
        <div className="flex items-center gap-2 text-sm text-destructive">
          <AlertCircle className="h-4 w-4" />
          <span>Audio unavailable</span>
        </div>
      ) : !isLoaded ? (
        <div className="flex items-center gap-2">
          <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
          <span className="text-xs text-muted-foreground">Loading audio…</span>
        </div>
      ) : (
        <>
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
              max={resolvedDuration || 0}
              step={0.1}
              onValueChange={handleSeekPreview}
              onValueCommit={handleSeekCommit}
              className="flex-1 min-w-[120px]"
              aria-label="Audio seek"
            />

            {/* Time display — inline on sm+ with a stable width so the
                slider's right edge never shifts as digits change. */}
            <span className="hidden sm:inline min-w-[84px] shrink-0 text-right text-xs tabular-nums text-muted-foreground">
              {formatTime(currentTime)} / {formatTime(resolvedDuration)}
            </span>
          </div>

          {/* Time display — stacked below on mobile */}
          <span className="sm:hidden text-xs tabular-nums text-muted-foreground pl-13">
            {formatTime(currentTime)} / {formatTime(resolvedDuration)}
          </span>
        </>
      )}
    </div>
  );
}
