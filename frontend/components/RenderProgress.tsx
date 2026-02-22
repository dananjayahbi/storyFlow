"use client";

import { useEffect, useRef } from "react";
import { Progress } from "@/components/ui/progress";
import { useProjectStore } from "@/lib/stores";
import { getRenderStatus } from "@/lib/api";

/**
 * RenderProgress — Real-time progress bar during video rendering.
 *
 * Polls GET /api/projects/{id}/status/ every 3 seconds while the
 * project is in the PROCESSING state.  Automatically stops when
 * rendering completes or fails and disappears from the UI.
 */
export default function RenderProgress() {
  const {
    project,
    renderStatus,
    renderProgress,
  } = useProjectStore();

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Polling effect ──
  useEffect(() => {
    // Only poll while rendering
    if (renderStatus !== "rendering" || !project) return;

    const poll = async () => {
      try {
        const status = await getRenderStatus(project.id);

        // Update Zustand store with latest progress
        useProjectStore.setState({ renderProgress: status.progress });

        // Terminal states — stop polling
        if (status.status === "COMPLETED") {
          useProjectStore.setState({
            renderStatus: "completed",
            renderProgress: status.progress,
            outputUrl: status.output_url,
          });
          if (intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
          }
        } else if (status.status === "FAILED") {
          useProjectStore.setState({
            renderStatus: "failed",
            renderProgress: status.progress,
            outputUrl: null,
          });
          if (intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
          }
        }
      } catch {
        // Transient error — continue polling
      }
    };

    intervalRef.current = setInterval(poll, 3000);

    // Cleanup on unmount or when renderStatus changes
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [renderStatus, project]);

  // ── Don't render when not PROCESSING ──
  if (renderStatus !== "rendering") return null;

  // ── Starting state — before first poll response ──
  if (!renderProgress) {
    return (
      <div className="space-y-2 py-3">
        <Progress value={0} />
        <p className="text-sm text-muted-foreground">Starting render…</p>
      </div>
    );
  }

  // ── Active progress ──
  return (
    <div className="space-y-2 py-3">
      <Progress value={renderProgress.percentage} />
      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>
          Segment {renderProgress.current_segment} of{" "}
          {renderProgress.total_segments} ({renderProgress.percentage}%)
        </span>
        <span className="text-xs">{renderProgress.current_phase}</span>
      </div>
    </div>
  );
}
