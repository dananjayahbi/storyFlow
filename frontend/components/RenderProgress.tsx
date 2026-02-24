"use client";

import { useEffect, useRef } from "react";
import { Progress } from "@/components/ui/progress";
import { useProjectStore } from "@/lib/stores";
import { getRenderStatus } from "@/lib/api";

/**
 * RenderProgress — Multi-phase progress display during video rendering.
 *
 * Shows two separate progress sections:
 *   1. **Segment processing** (0–80 % overall) — Ken Burns + subtitle compositing
 *   2. **Export / encoding** (80–100 % overall) — video frames → audio → finalize
 *
 * Polls GET /api/projects/{id}/status/ every 3 seconds while the
 * project is in the PROCESSING state.
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
    if (renderStatus !== "rendering" || !project) return;

    const poll = async () => {
      try {
        const status = await getRenderStatus(project.id);
        useProjectStore.setState({ renderProgress: status.progress });

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

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [renderStatus, project]);

  if (renderStatus !== "rendering") return null;

  if (!renderProgress) {
    return (
      <div className="space-y-2 py-3">
        <Progress value={0} />
        <p className="text-sm text-muted-foreground">Starting render…</p>
      </div>
    );
  }

  const overallPct = renderProgress.percentage;
  const isExportPhase = overallPct >= 80;

  // Phase 1: Segment processing (overall 0–80 %) → mapped to 0–100 %
  const segmentPct = isExportPhase ? 100 : Math.round((overallPct / 80) * 100);

  // Phase 2: Export / encoding (overall 80–100 %) → mapped to 0–100 %
  const exportPct = isExportPhase
    ? Math.round(((overallPct - 80) / 20) * 100)
    : 0;

  return (
    <div className="space-y-4 py-3">
      {/* Phase 1 — Segment Processing */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between text-sm">
          <span className="font-medium">
            {isExportPhase ? "✓ Segments processed" : "Processing segments…"}
          </span>
          <span className="text-muted-foreground tabular-nums">
            {renderProgress.current_segment}/{renderProgress.total_segments}
            {!isExportPhase && ` (${segmentPct}%)`}
          </span>
        </div>
        <Progress value={segmentPct} />
        {!isExportPhase && renderProgress.current_phase && (
          <p className="text-xs text-muted-foreground">
            {renderProgress.current_phase}
          </p>
        )}
      </div>

      {/* Phase 2 — Export / Encoding */}
      {isExportPhase && (
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-sm">
            <span className="font-medium">
              {exportPct >= 100 ? "✓ Export complete" : "Exporting video…"}
            </span>
            <span className="text-muted-foreground tabular-nums">
              {exportPct}%
            </span>
          </div>
          <Progress value={exportPct} />
          <p className="text-xs text-muted-foreground">
            {renderProgress.current_phase}
          </p>
        </div>
      )}

      {/* Overall percentage */}
      <p className="text-xs text-muted-foreground text-right">
        Overall: {overallPct}%
      </p>
    </div>
  );
}
