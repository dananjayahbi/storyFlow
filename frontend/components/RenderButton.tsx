"use client";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useProjectStore } from "@/lib/stores";

/**
 * RenderButton — Primary action button for triggering video rendering.
 *
 * Adapts its appearance and behaviour based on the current render state:
 *  • Ready (blue)       — "Export Video", calls startRender
 *  • Not Ready (gray)   — disabled, tooltip lists missing assets
 *  • Rendering (spinner)— disabled during processing
 *  • Completed (green)  — "Download Video" + re-render dropdown
 *  • Failed (red)       — "Retry Render", calls startRender
 */
export default function RenderButton() {
  const {
    segments,
    renderStatus,
    startRender,
    downloadVideo,
  } = useProjectStore();

  // ── Client-side readiness check ──
  const missingImages = segments.filter((s) => !s.image_file).length;
  const missingAudio = segments.filter((s) => !s.audio_file).length;
  const isReady = segments.length > 0 && missingImages === 0 && missingAudio === 0;

  // Build tooltip message for the not-ready state
  const tooltipParts: string[] = [];
  if (segments.length === 0) {
    tooltipParts.push("No segments in project");
  } else {
    if (missingImages > 0) tooltipParts.push(`${missingImages} segment(s) need images`);
    if (missingAudio > 0) tooltipParts.push(`${missingAudio} segment(s) need audio`);
  }
  const tooltipMessage = tooltipParts.join(". ");

  // ── Rendering / Validating state ──
  if (renderStatus === "validating" || renderStatus === "rendering") {
    return (
      <Button disabled className="gap-2">
        <svg
          className="size-4 animate-spin"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
          />
        </svg>
        Rendering…
      </Button>
    );
  }

  // ── Completed state ──
  if (renderStatus === "completed") {
    return (
      <div className="flex items-center gap-0.5">
        <Button
          className="rounded-r-none bg-green-600 hover:bg-green-700 text-white"
          onClick={() => downloadVideo()}
        >
          ⬇️ Download Video
        </Button>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              className="rounded-l-none border-l border-green-800 bg-green-600 hover:bg-green-700 text-white px-2"
              aria-label="More render options"
            >
              <svg
                className="size-4"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => startRender()}>
              🔄 Re-Render
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    );
  }

  // ── Failed state ──
  if (renderStatus === "failed") {
    return (
      <Button variant="destructive" onClick={() => startRender()}>
        🔁 Retry Render
      </Button>
    );
  }

  // ── Idle state: ready or not ready ──
  if (!isReady) {
    return (
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <span tabIndex={0}>
              <Button disabled>
                🎬 Export Video
              </Button>
            </span>
          </TooltipTrigger>
          <TooltipContent>
            <p>{tooltipMessage}</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
  }

  // Ready — blue primary button
  return (
    <Button onClick={() => startRender()}>
      🎬 Export Video
    </Button>
  );
}
