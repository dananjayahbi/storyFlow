"use client";

import { useRef, useState, useCallback } from "react";
import { useProjectStore } from "@/lib/stores";
import { Button } from "@/components/ui/button";

/**
 * Formats seconds into MM:SS display string.
 */
function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

/**
 * VideoPreview — displays the rendered video with playback controls,
 * metadata (duration), and a cross-origin-safe download button.
 * Only renders when outputUrl is available (non-empty string).
 */
export default function VideoPreview() {
  const { outputUrl, downloadVideo } = useProjectStore();

  const videoRef = useRef<HTMLVideoElement>(null);
  const [duration, setDuration] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);

  // Build full video URL with cache-busting timestamp
  const backendBase =
    process.env.NEXT_PUBLIC_API_URL?.replace("/api", "") ||
    "http://localhost:8000";
  const videoSrc = outputUrl
    ? `${backendBase}${outputUrl}?t=${Date.now()}`
    : "";

  const handleLoadedMetadata = useCallback(() => {
    if (videoRef.current) {
      setDuration(videoRef.current.duration);
    }
    setIsLoading(false);
    setHasError(false);
  }, []);

  const handleError = useCallback(() => {
    setIsLoading(false);
    setHasError(true);
  }, []);

  const handleLoadStart = useCallback(() => {
    setIsLoading(true);
    setHasError(false);
  }, []);

  // Only render when outputUrl is available
  if (!outputUrl) {
    return null;
  }

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold">Video Preview</h3>

      {/* Loading placeholder */}
      {isLoading && !hasError && (
        <div className="flex items-center justify-center rounded-lg border bg-muted/50 aspect-video">
          <div className="text-center space-y-2">
            <div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full mx-auto" />
            <p className="text-sm text-muted-foreground">Loading video...</p>
          </div>
        </div>
      )}

      {/* Error state */}
      {hasError && (
        <div className="flex items-center justify-center rounded-lg border border-destructive bg-destructive/10 aspect-video">
          <div className="text-center space-y-2 px-4">
            <p className="text-sm font-medium text-destructive">
              Failed to load video
            </p>
            <p className="text-xs text-muted-foreground">
              The video file may have been deleted. Try re-rendering the
              project.
            </p>
          </div>
        </div>
      )}

      {/* HTML5 Video Element */}
      <video
        ref={videoRef}
        controls
        className={`w-full rounded-lg ${isLoading || hasError ? "hidden" : ""}`}
        onLoadedMetadata={handleLoadedMetadata}
        onError={handleError}
        onLoadStart={handleLoadStart}
      >
        <source src={videoSrc} type="video/mp4" />
        Your browser does not support the video tag.
      </video>

      {/* Metadata & Download */}
      {!hasError && (
        <div className="flex items-center justify-between">
          <div className="text-sm text-muted-foreground">
            {duration !== null && (
              <span>Duration: {formatDuration(duration)}</span>
            )}
          </div>
          <Button onClick={downloadVideo} variant="outline" size="sm">
            ⬇️ Download Video
          </Button>
        </div>
      )}
    </div>
  );
}
