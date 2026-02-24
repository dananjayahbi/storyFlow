'use client';

import { useEffect, useState, useRef, useCallback } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { useProjectStore } from '@/lib/stores';
import { Timeline } from '@/components/Timeline';
import { GlobalSettingsPanel } from '@/components/GlobalSettingsPanel';
import ImportDialog from '@/components/ImportDialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import { Progress } from '@/components/ui/progress';
import { Tooltip, TooltipProvider, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import {
  ArrowLeft, Volume2, Film, Loader2, X, FileUp, Download, CheckCircle, AlertCircle,
  Settings, ChevronLeft, ChevronRight, Info, Sliders, Home, Layers, Calendar,
} from 'lucide-react';
import { cn } from '@/lib/utils';

// ── Sidebar collapsed state persistence ──
const EDITOR_SIDEBAR_KEY = 'storyflow-editor-sidebar-collapsed';

function getEditorSidebarCollapsed(): boolean {
  if (typeof window === 'undefined') return false;
  try {
    return localStorage.getItem(EDITOR_SIDEBAR_KEY) === 'true';
  } catch {
    return false;
  }
}

export default function TimelineEditorPage() {
  const params = useParams();
  const id = params.id as string;
  const [showImportDialog, setShowImportDialog] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [sidebarTab, setSidebarTab] = useState<'info' | 'settings'>('info');
  const [mounted, setMounted] = useState(false);
  const {
    project, segments, isLoading, error,
    fetchProject, addSegment, importSegmentsToProject, updateSegment, deleteSegment,
    uploadImage, removeImage, reset,
    bulkGenerationProgress, generateAllAudio, cancelGeneration,
    // Render pipeline
    renderStatus, renderProgress, outputUrl,
    startRender, resetRenderState, cancelRender, downloadVideo,
  } = useProjectStore();

  const isGenerating = !!bulkGenerationProgress &&
    bulkGenerationProgress.status !== 'COMPLETED' &&
    bulkGenerationProgress.status !== 'FAILED';

  const bulkPercentage = bulkGenerationProgress
    ? Math.round((bulkGenerationProgress.completed / Math.max(bulkGenerationProgress.total, 1)) * 100)
    : 0;

  const isRendering = renderStatus === 'rendering' || renderStatus === 'validating';
  const renderPercentage = renderProgress?.percentage ?? 0;

  // ── Smooth progress interpolation ──
  // Smoothly animate between polled render percentage values instead of
  // jumping discretely. Uses requestAnimationFrame to increment the
  // displayed value toward the actual target at ~1% per 50ms.
  const [smoothRenderPct, setSmoothRenderPct] = useState(0);
  const smoothRef = useRef<number | null>(null);
  const targetPctRef = useRef(0);

  useEffect(() => {
    targetPctRef.current = renderPercentage;
  }, [renderPercentage]);

  useEffect(() => {
    if (!isRendering) {
      setSmoothRenderPct(0);
      if (smoothRef.current) cancelAnimationFrame(smoothRef.current);
      return;
    }

    const tick = () => {
      setSmoothRenderPct((prev) => {
        const target = targetPctRef.current;
        if (prev >= target) return prev;
        // Advance ~1% per frame, capped at target
        const step = Math.max(0.3, (target - prev) * 0.08);
        return Math.min(prev + step, target);
      });
      smoothRef.current = requestAnimationFrame(tick);
    };

    smoothRef.current = requestAnimationFrame(tick);
    return () => {
      if (smoothRef.current) cancelAnimationFrame(smoothRef.current);
    };
  }, [isRendering]);

  // Also smooth the bulk audio generation percentage
  const [smoothBulkPct, setSmoothBulkPct] = useState(0);
  const smoothBulkRef = useRef<number | null>(null);
  const targetBulkRef = useRef(0);

  useEffect(() => {
    targetBulkRef.current = bulkPercentage;
  }, [bulkPercentage]);

  useEffect(() => {
    if (!isGenerating) {
      setSmoothBulkPct(0);
      if (smoothBulkRef.current) cancelAnimationFrame(smoothBulkRef.current);
      return;
    }

    const tick = () => {
      setSmoothBulkPct((prev) => {
        const target = targetBulkRef.current;
        if (prev >= target) return prev;
        const step = Math.max(0.3, (target - prev) * 0.08);
        return Math.min(prev + step, target);
      });
      smoothBulkRef.current = requestAnimationFrame(tick);
    };

    smoothBulkRef.current = requestAnimationFrame(tick);
    return () => {
      if (smoothBulkRef.current) cancelAnimationFrame(smoothBulkRef.current);
    };
  }, [isGenerating]);

  // Hydrate sidebar state
  useEffect(() => {
    setSidebarCollapsed(getEditorSidebarCollapsed());
    setMounted(true);
  }, []);

  const toggleSidebar = () => {
    setSidebarCollapsed((prev) => {
      const next = !prev;
      try { localStorage.setItem(EDITOR_SIDEBAR_KEY, String(next)); } catch { /* no-op */ }
      return next;
    });
  };

  useEffect(() => {
    fetchProject(id);
    return () => {
      cancelGeneration();
      resetRenderState();
      reset();
    };
  }, [id, fetchProject, cancelGeneration, resetRenderState, reset]);

  // Loading state — also treat initial state (no project yet, no error) as loading
  if (isLoading || (!project && !error)) {
    return (
      <TooltipProvider>
        <div className="flex h-screen bg-background">
          {/* Skeleton sidebar */}
          <aside className="w-56 border-r bg-sidebar shrink-0 p-4 space-y-4">
            <Skeleton className="h-8 w-8 rounded-lg" />
            <Skeleton className="h-6 w-40" />
            <Skeleton className="h-5 w-20" />
            <Skeleton className="h-5 w-32" />
            <Skeleton className="h-px w-full" />
            <Skeleton className="h-5 w-24" />
            <Skeleton className="h-9 w-full" />
          </aside>
          {/* Skeleton content */}
          <div className="flex-1 flex flex-col">
            <header className="h-14 border-b px-6 flex items-center">
              <Skeleton className="h-6 w-48" />
            </header>
            <main className="flex-1 p-6 space-y-4">
              <Skeleton className="h-48 w-full" />
              <Skeleton className="h-48 w-full" />
            </main>
          </div>
        </div>
      </TooltipProvider>
    );
  }

  // Error state
  if (error || !project) {
    return (
      <div className="flex flex-col items-center justify-center h-screen gap-4 bg-background px-4">
        <div className="flex items-center justify-center w-12 h-12 rounded-full bg-destructive/10">
          <X className="h-6 w-6 text-destructive" />
        </div>
        <p className="text-lg font-medium text-foreground">{error || 'Project not found'}</p>
        <div className="flex gap-2">
          <Button onClick={() => fetchProject(id)}>Retry</Button>
          <Button variant="outline" asChild>
            <Link href="/">
              <ArrowLeft className="h-4 w-4 mr-1" />
              Back to Dashboard
            </Link>
          </Button>
        </div>
      </div>
    );
  }

  // ── Status badge styling ──
  const statusStyles: Record<string, string> = {
    DRAFT: 'bg-muted text-muted-foreground',
    IN_PROGRESS: 'bg-blue-500/10 text-blue-600 dark:text-blue-400',
    RENDERING: 'bg-amber-500/10 text-amber-600 dark:text-amber-400',
    COMPLETED: 'bg-green-500/10 text-green-600 dark:text-green-400',
    ERROR: 'bg-destructive/10 text-destructive',
  };

  return (
    <TooltipProvider>
      <div className="flex h-screen bg-background text-foreground">
        {/* ── Left Sidebar — modern tabbed layout ── */}
        <aside
          className={cn(
            'flex flex-col border-r bg-sidebar text-sidebar-foreground transition-all duration-200 ease-in-out shrink-0',
            mounted
              ? sidebarCollapsed ? 'w-14' : 'w-72'
              : 'w-72'
          )}
        >
          {/* ── Brand + Project header ── */}
          <div className={cn(
            'flex items-center h-14 border-b px-3 shrink-0',
            sidebarCollapsed ? 'justify-center' : 'gap-2.5'
          )}>
            <Link href="/" className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary text-primary-foreground shrink-0 hover:bg-primary/90 transition-colors">
              <Film className="h-4 w-4" />
            </Link>
            {!sidebarCollapsed && (
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold truncate">{project.title}</p>
                <div className="flex items-center gap-1.5">
                  <Badge
                    variant="secondary"
                    className={cn('text-[10px] px-1.5 py-0 h-4', statusStyles[project.status] || '')}
                  >
                    {project.status.replace('_', ' ')}
                  </Badge>
                  <span className="text-[10px] text-sidebar-foreground/50">
                    · {segments.length} seg{segments.length !== 1 ? 's' : ''}
                  </span>
                </div>
              </div>
            )}
          </div>

          {/* ── Tab Switcher (when expanded) ── */}
          {!sidebarCollapsed && (
            <div className="flex border-b shrink-0">
              <button
                onClick={() => setSidebarTab('info')}
                className={cn(
                  'flex-1 flex items-center justify-center gap-2 py-2.5 text-xs font-medium transition-colors border-b-2',
                  sidebarTab === 'info'
                    ? 'border-primary text-primary'
                    : 'border-transparent text-sidebar-foreground/50 hover:text-sidebar-foreground/80'
                )}
              >
                <Info className="h-3.5 w-3.5" />
                Details
              </button>
              <button
                onClick={() => setSidebarTab('settings')}
                className={cn(
                  'flex-1 flex items-center justify-center gap-2 py-2.5 text-xs font-medium transition-colors border-b-2',
                  sidebarTab === 'settings'
                    ? 'border-primary text-primary'
                    : 'border-transparent text-sidebar-foreground/50 hover:text-sidebar-foreground/80'
                )}
              >
                <Sliders className="h-3.5 w-3.5" />
                Settings
              </button>
            </div>
          )}

          {/* ── Collapsed icon tabs ── */}
          {sidebarCollapsed && (
            <div className="px-2 py-2 space-y-1">
              <Tooltip delayDuration={0}>
                <TooltipTrigger asChild>
                  <button
                    onClick={() => { setSidebarCollapsed(false); setSidebarTab('info'); }}
                    className={cn(
                      'flex items-center justify-center w-full rounded-md p-2 transition-colors',
                      'text-sidebar-foreground/60 hover:bg-sidebar-accent/50 hover:text-sidebar-foreground'
                    )}
                  >
                    <Info className="h-4 w-4" />
                  </button>
                </TooltipTrigger>
                <TooltipContent side="right" sideOffset={8}>Project Details</TooltipContent>
              </Tooltip>
              <Tooltip delayDuration={0}>
                <TooltipTrigger asChild>
                  <button
                    onClick={() => { setSidebarCollapsed(false); setSidebarTab('settings'); }}
                    className={cn(
                      'flex items-center justify-center w-full rounded-md p-2 transition-colors',
                      'text-sidebar-foreground/60 hover:bg-sidebar-accent/50 hover:text-sidebar-foreground'
                    )}
                  >
                    <Sliders className="h-4 w-4" />
                  </button>
                </TooltipTrigger>
                <TooltipContent side="right" sideOffset={8}>Settings</TooltipContent>
              </Tooltip>
            </div>
          )}

          {/* ── Tab Content ── */}
          {!sidebarCollapsed && (
            <div className="flex-1 overflow-y-auto">
              {sidebarTab === 'info' ? (
                /* ── Info Tab ── */
                <div className="p-4 space-y-4">
                  {/* Project details cards */}
                  <div className="space-y-3">
                    <div className="rounded-lg border bg-card/50 p-3 space-y-2.5">
                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <Layers className="h-3.5 w-3.5" />
                        <span>Segments</span>
                        <span className="ml-auto font-medium text-foreground">{segments.length}</span>
                      </div>
                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <Calendar className="h-3.5 w-3.5" />
                        <span>Created</span>
                        <span className="ml-auto font-medium text-foreground">
                          {new Date(project.created_at).toLocaleDateString()}
                        </span>
                      </div>
                      {project.updated_at && (
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                          <Calendar className="h-3.5 w-3.5" />
                          <span>Updated</span>
                          <span className="ml-auto font-medium text-foreground">
                            {new Date(project.updated_at).toLocaleDateString()}
                          </span>
                        </div>
                      )}
                    </div>
                  </div>

                  <Separator />

                  {/* Quick Actions */}
                  <div>
                    <p className="text-[10px] uppercase tracking-widest text-sidebar-foreground/50 font-semibold mb-2">
                      Quick Actions
                    </p>
                    <div className="space-y-1.5">
                      <Button
                        variant="outline"
                        size="sm"
                        className="w-full justify-start text-xs"
                        onClick={() => setShowImportDialog(true)}
                      >
                        <FileUp className="h-3.5 w-3.5 mr-2" />
                        Import Segments
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        className="w-full justify-start text-xs"
                        onClick={generateAllAudio}
                        disabled={!!bulkGenerationProgress}
                      >
                        {isGenerating ? (
                          <Loader2 className="h-3.5 w-3.5 mr-2 animate-spin" />
                        ) : (
                          <Volume2 className="h-3.5 w-3.5 mr-2" />
                        )}
                        {isGenerating ? 'Generating…' : 'Generate All Audio'}
                      </Button>
                    </div>
                  </div>

                  <Separator />

                  {/* Navigation */}
                  <div>
                    <p className="text-[10px] uppercase tracking-widest text-sidebar-foreground/50 font-semibold mb-2">
                      Navigate
                    </p>
                    <div className="space-y-1">
                      <Link
                        href="/"
                        className="flex items-center gap-2.5 rounded-md px-2.5 py-2 text-xs font-medium text-sidebar-foreground/70 hover:bg-sidebar-accent/50 hover:text-sidebar-foreground transition-colors"
                      >
                        <Home className="h-3.5 w-3.5" />
                        Dashboard
                      </Link>
                      <Link
                        href="/settings"
                        className="flex items-center gap-2.5 rounded-md px-2.5 py-2 text-xs font-medium text-sidebar-foreground/70 hover:bg-sidebar-accent/50 hover:text-sidebar-foreground transition-colors"
                      >
                        <Settings className="h-3.5 w-3.5" />
                        Global Settings
                      </Link>
                    </div>
                  </div>
                </div>
              ) : (
                /* ── Settings Tab ── */
                <div className="py-2">
                  <GlobalSettingsPanel />
                </div>
              )}
            </div>
          )}

          {/* ── Collapse toggle at bottom ── */}
          <div className="border-t px-2 py-2 shrink-0">
            <Tooltip delayDuration={0}>
              <TooltipTrigger asChild>
                <button
                  onClick={toggleSidebar}
                  className={cn(
                    'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium w-full transition-colors',
                    'text-sidebar-foreground/60 hover:bg-sidebar-accent/50 hover:text-sidebar-foreground',
                    sidebarCollapsed && 'justify-center px-2'
                  )}
                >
                  {sidebarCollapsed ? (
                    <ChevronRight className="h-4 w-4 shrink-0" />
                  ) : (
                    <>
                      <ChevronLeft className="h-4 w-4 shrink-0" />
                      <span>Collapse</span>
                    </>
                  )}
                </button>
              </TooltipTrigger>
              <TooltipContent side="right" sideOffset={8}>
                {sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              </TooltipContent>
            </Tooltip>
          </div>
        </aside>

        {/* ── Right content area ── */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* ── Top Bar ── */}
          <header className="flex items-center justify-between h-14 border-b bg-background px-4 sm:px-6 shrink-0">
            <div className="flex items-center gap-3 min-w-0">
              <Button variant="ghost" size="icon" className="h-8 w-8 shrink-0 sm:hidden" asChild>
                <Link href="/"><ArrowLeft className="h-4 w-4" /></Link>
              </Button>
              <h1 className="text-sm font-semibold truncate">
                {project.title}
              </h1>
              <Badge
                variant="secondary"
                className={cn('text-[10px] px-1.5 py-0 h-4 shrink-0 hidden sm:inline-flex', statusStyles[project.status] || '')}
              >
                {project.status.replace('_', ' ')}
              </Badge>
            </div>
            <div className="flex items-center gap-1 shrink-0">
              <Tooltip delayDuration={0}>
                <TooltipTrigger asChild>
                  <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setShowImportDialog(true)}>
                    <FileUp className="h-4 w-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Import Segments</TooltipContent>
              </Tooltip>
              {renderStatus === 'completed' && outputUrl ? (
                <Tooltip delayDuration={0}>
                  <TooltipTrigger asChild>
                    <Button variant="ghost" size="icon" className="h-8 w-8" onClick={downloadVideo}>
                      <Download className="h-4 w-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>Download Video</TooltipContent>
                </Tooltip>
              ) : (
                <Tooltip delayDuration={0}>
                  <TooltipTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      onClick={startRender}
                      disabled={isRendering || segments.length === 0}
                    >
                      {isRendering ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Film className="h-4 w-4" />
                      )}
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>{isRendering ? 'Rendering…' : 'Export Video'}</TooltipContent>
                </Tooltip>
              )}
            </div>
          </header>

          {/* ── Timeline Content ── */}
          <main className="flex-1 overflow-auto">
            <Timeline
              segments={segments}
              onAddSegment={async () => { await addSegment(); }}
              onUpdateSegment={updateSegment}
              onDeleteSegment={deleteSegment}
              onUploadImage={uploadImage}
              onRemoveImage={removeImage}
            />
          </main>

          {/* ── Action Bar ── */}
          <footer className="border-t bg-background shrink-0">
            {/* Progress / Status indicators (only when active) */}
            {(bulkGenerationProgress || isRendering || renderStatus === 'completed' || renderStatus === 'failed') && (
              <div className="px-4 sm:px-6 pt-2.5 pb-1 space-y-1.5">
                {/* Audio generation progress */}
                {bulkGenerationProgress && (
                  <div className="space-y-1">
                    {bulkGenerationProgress.status === 'COMPLETED' || bulkGenerationProgress.status === 'FAILED' ? (
                      <p className={cn(
                        'text-xs font-medium flex items-center gap-1.5',
                        bulkGenerationProgress.failed > 0
                          ? 'text-amber-600 dark:text-amber-400'
                          : 'text-green-600 dark:text-green-400'
                      )}>
                        <CheckCircle className="h-3 w-3" />
                        {bulkGenerationProgress.failed > 0
                          ? `Audio: ${bulkGenerationProgress.completed} done, ${bulkGenerationProgress.failed} failed`
                          : `Audio: ${bulkGenerationProgress.completed}/${bulkGenerationProgress.total} complete`}
                      </p>
                    ) : (
                      <div className="flex items-center gap-3">
                        <p className="text-xs text-muted-foreground whitespace-nowrap">
                          Audio {bulkGenerationProgress.completed}/{bulkGenerationProgress.total}
                        </p>
                        <Progress value={Math.round(smoothBulkPct)} className="flex-1 h-1.5" />
                        <span className="text-xs tabular-nums text-muted-foreground">{Math.round(smoothBulkPct)}%</span>
                      </div>
                    )}
                  </div>
                )}

                {/* Render progress */}
                {isRendering && renderProgress && (
                  <div className="flex items-center gap-3">
                    <p className="text-xs text-muted-foreground whitespace-nowrap">
                      Render {renderProgress.current_segment}/{renderProgress.total_segments}
                    </p>
                    <Progress value={Math.round(smoothRenderPct)} className="flex-1 h-1.5" />
                    <span className="text-xs tabular-nums text-muted-foreground">{Math.round(smoothRenderPct)}%</span>
                  </div>
                )}
                {isRendering && !renderProgress && (
                  <p className="text-xs text-muted-foreground flex items-center gap-1.5">
                    <Loader2 className="h-3 w-3 animate-spin" />
                    Preparing render pipeline…
                  </p>
                )}

                {/* Completed / Failed banners */}
                {renderStatus === 'completed' && outputUrl && (
                  <p className="text-xs font-medium text-green-600 dark:text-green-400 flex items-center gap-1.5">
                    <CheckCircle className="h-3 w-3" />
                    Render complete — ready to download
                  </p>
                )}
                {renderStatus === 'failed' && (
                  <p className="text-xs font-medium text-destructive flex items-center gap-1.5">
                    <AlertCircle className="h-3 w-3" />
                    Render failed — check segments have images &amp; audio
                  </p>
                )}
              </div>
            )}

            {/* Action buttons row */}
            <div className="flex items-center justify-between px-4 sm:px-6 py-2">
              {/* Left: Audio actions */}
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={generateAllAudio}
                  disabled={!!bulkGenerationProgress}
                  className="h-8 text-xs"
                >
                  {isGenerating ? (
                    <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                  ) : (
                    <Volume2 className="h-3.5 w-3.5 mr-1.5" />
                  )}
                  {isGenerating ? 'Generating…' : 'Generate All Audio'}
                </Button>
                {isGenerating && (
                  <Button variant="ghost" size="sm" onClick={cancelGeneration} className="h-8 text-xs px-2">
                    <X className="h-3.5 w-3.5" />
                  </Button>
                )}
              </div>

              {/* Center: segment count */}
              <span className="text-[10px] text-muted-foreground tabular-nums hidden sm:block">
                {segments.length} segment{segments.length !== 1 ? 's' : ''}
              </span>

              {/* Right: Render / Export actions */}
              <div className="flex items-center gap-2">
                {renderStatus === 'completed' && outputUrl ? (
                  <>
                    <Button size="sm" onClick={downloadVideo} className="h-8 text-xs">
                      <Download className="h-3.5 w-3.5 mr-1.5" />
                      Download
                    </Button>
                    <Button variant="ghost" size="sm" onClick={resetRenderState} className="h-8 text-xs px-2">
                      Re-render
                    </Button>
                  </>
                ) : renderStatus === 'failed' ? (
                  <>
                    <Button size="sm" variant="destructive" onClick={startRender} className="h-8 text-xs">
                      <AlertCircle className="h-3.5 w-3.5 mr-1.5" />
                      Retry
                    </Button>
                    <Button variant="ghost" size="sm" onClick={resetRenderState} className="h-8 text-xs px-2">
                      Dismiss
                    </Button>
                  </>
                ) : (
                  <>
                    <Button
                      size="sm"
                      onClick={startRender}
                      disabled={isRendering || segments.length === 0}
                      className="h-8 text-xs"
                    >
                      {isRendering ? (
                        <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                      ) : (
                        <Film className="h-3.5 w-3.5 mr-1.5" />
                      )}
                      {isRendering ? 'Rendering…' : 'Export'}
                    </Button>
                    {isRendering && (
                      <Button variant="ghost" size="sm" onClick={cancelRender} className="h-8 text-xs px-2">
                        <X className="h-3.5 w-3.5" />
                      </Button>
                    )}
                  </>
                )}
              </div>
            </div>
          </footer>
        </div>

        {/* Import Segments Dialog */}
        <ImportDialog
          open={showImportDialog}
          onOpenChange={setShowImportDialog}
          projectId={id}
          onSuccess={() => {}}
          onSegmentsImported={(segments) => {
            useProjectStore.setState({ segments });
          }}
        />
      </div>
    </TooltipProvider>
  );
}
