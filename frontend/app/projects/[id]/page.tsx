'use client';

import { useEffect, useState } from 'react';
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
  ArrowLeft, Volume2, Film, Loader2, X, Plus, FileUp, Download, CheckCircle, AlertCircle,
  LayoutDashboard, Settings, Calendar, Layers, ChevronLeft, ChevronRight,
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
  const [mounted, setMounted] = useState(false);
  const {
    project, segments, isLoading, error,
    fetchProject, addSegment, importSegmentsToProject, updateSegment, deleteSegment,
    uploadImage, removeImage, reset,
    bulkGenerationProgress, generateAllAudio, cancelGeneration,
    // Render pipeline
    renderStatus, renderProgress, outputUrl,
    startRender, resetRenderState, downloadVideo,
  } = useProjectStore();

  const isGenerating = !!bulkGenerationProgress &&
    bulkGenerationProgress.status !== 'COMPLETED' &&
    bulkGenerationProgress.status !== 'FAILED';

  const bulkPercentage = bulkGenerationProgress
    ? Math.round((bulkGenerationProgress.completed / Math.max(bulkGenerationProgress.total, 1)) * 100)
    : 0;

  const isRendering = renderStatus === 'rendering' || renderStatus === 'validating';
  const renderPercentage = renderProgress?.percentage ?? 0;

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

  // Loading state
  if (isLoading) {
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
        {/* ── Left Sidebar — navigation + project info + settings ── */}
        <aside
          className={cn(
            'flex flex-col border-r bg-sidebar text-sidebar-foreground transition-all duration-200 ease-in-out shrink-0',
            mounted
              ? sidebarCollapsed ? 'w-14' : 'w-64'
              : 'w-64'
          )}
        >
          {/* Brand bar */}
          <div className={cn(
            'flex items-center h-14 border-b px-3 shrink-0',
            sidebarCollapsed ? 'justify-center' : 'gap-2.5'
          )}>
            <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary text-primary-foreground shrink-0">
              <Film className="h-4 w-4" />
            </div>
            {!sidebarCollapsed && (
              <span className="font-semibold text-sm tracking-tight truncate">
                StoryFlow
              </span>
            )}
          </div>

          {/* Navigation links */}
          <nav className="px-2 py-3 space-y-1">
            {[
              { label: 'Dashboard', href: '/', icon: LayoutDashboard },
              { label: 'Settings', href: '/settings', icon: Settings },
            ].map((item) => {
              const link = (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                    'text-sidebar-foreground/70 hover:bg-sidebar-accent/50 hover:text-sidebar-foreground',
                    sidebarCollapsed && 'justify-center px-2'
                  )}
                >
                  <item.icon className="h-4 w-4 shrink-0" />
                  {!sidebarCollapsed && <span>{item.label}</span>}
                </Link>
              );

              if (sidebarCollapsed) {
                return (
                  <Tooltip key={item.href} delayDuration={0}>
                    <TooltipTrigger asChild>{link}</TooltipTrigger>
                    <TooltipContent side="right" sideOffset={8}>
                      {item.label}
                    </TooltipContent>
                  </Tooltip>
                );
              }
              return link;
            })}
          </nav>

          <Separator className="mx-2" />

          {/* Project info section — only when expanded */}
          {!sidebarCollapsed && (
            <div className="px-4 py-3 space-y-3 overflow-y-auto flex-1">
              {/* Project name */}
              <div>
                <p className="text-[10px] uppercase tracking-widest text-sidebar-foreground/50 font-semibold mb-1">
                  Project
                </p>
                <p className="text-sm font-medium truncate">{project.title}</p>
              </div>

              {/* Status */}
              <div>
                <p className="text-[10px] uppercase tracking-widest text-sidebar-foreground/50 font-semibold mb-1">
                  Status
                </p>
                <Badge
                  variant="secondary"
                  className={cn('text-xs', statusStyles[project.status] || '')}
                >
                  {project.status.replace('_', ' ')}
                </Badge>
              </div>

              {/* Segment count */}
              <div className="flex items-center gap-2 text-sm">
                <Layers className="h-3.5 w-3.5 text-sidebar-foreground/50" />
                <span className="text-sidebar-foreground/80">
                  {segments.length} segment{segments.length !== 1 ? 's' : ''}
                </span>
              </div>

              {/* Created date */}
              <div className="flex items-center gap-2 text-sm">
                <Calendar className="h-3.5 w-3.5 text-sidebar-foreground/50" />
                <span className="text-sidebar-foreground/80">
                  {new Date(project.created_at).toLocaleDateString()}
                </span>
              </div>

              <Separator />

              {/* Global Settings */}
              <GlobalSettingsPanel />
            </div>
          )}

          {/* Collapse toggle at bottom */}
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
            <h1 className="text-sm font-semibold truncate">
              {project.title}
            </h1>
            <div className="flex items-center gap-2 shrink-0">
              <Button variant="ghost" size="sm" onClick={() => setShowImportDialog(true)}>
                <FileUp className="h-4 w-4 mr-1.5" />
                <span className="hidden sm:inline">Import</span>
              </Button>
              {renderStatus === 'completed' && outputUrl ? (
                <Button variant="ghost" size="sm" onClick={downloadVideo}>
                  <Download className="h-4 w-4 mr-1.5" />
                  <span className="hidden sm:inline">Download</span>
                </Button>
              ) : (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={startRender}
                  disabled={isRendering || segments.length === 0}
                >
                  {isRendering ? (
                    <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
                  ) : (
                    <Film className="h-4 w-4 mr-1.5" />
                  )}
                  <span className="hidden sm:inline">
                    {isRendering ? 'Rendering…' : 'Export'}
                  </span>
                </Button>
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
          <footer className="border-t bg-background px-4 sm:px-6 py-3 space-y-2 shrink-0">
            <div className="flex flex-wrap items-center gap-2 sm:gap-3">
              <Button
                size="sm"
                onClick={generateAllAudio}
                disabled={!!bulkGenerationProgress}
              >
                {isGenerating ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Volume2 className="h-4 w-4 mr-2" />
                )}
                {isGenerating ? 'Generating...' : 'Generate All Audio'}
              </Button>
              {isGenerating && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={cancelGeneration}
                >
                  <X className="h-4 w-4 mr-1" />
                  Cancel
                </Button>
              )}
              {/* ── Render / Export Video Button ── */}
              {renderStatus === 'completed' && outputUrl ? (
                <>
                  <Button size="sm" onClick={downloadVideo}>
                    <Download className="h-4 w-4 mr-2" />
                    Download Video
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={resetRenderState}
                  >
                    Re-render
                  </Button>
                </>
              ) : renderStatus === 'failed' ? (
                <>
                  <Button size="sm" variant="destructive" onClick={startRender}>
                    <AlertCircle className="h-4 w-4 mr-2" />
                    Retry Render
                  </Button>
                  <Button variant="outline" size="sm" onClick={resetRenderState}>
                    Dismiss
                  </Button>
                </>
              ) : (
                <Button
                  size="sm"
                  onClick={startRender}
                  disabled={isRendering || segments.length === 0}
                >
                  {isRendering ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <Film className="h-4 w-4 mr-2" />
                  )}
                  {isRendering ? 'Rendering…' : 'Export Video'}
                </Button>
              )}
            </div>
            {bulkGenerationProgress && (
              <div className="w-full space-y-1.5 overflow-hidden">
                {bulkGenerationProgress.status === 'COMPLETED' || bulkGenerationProgress.status === 'FAILED' ? (
                  <p
                    className={`text-sm font-medium ${
                      bulkGenerationProgress.failed > 0
                        ? 'text-amber-600 dark:text-amber-400'
                        : 'text-green-600 dark:text-green-400'
                    }`}
                  >
                    {bulkGenerationProgress.failed > 0
                      ? `Audio generation complete — ${bulkGenerationProgress.completed} succeeded, ${bulkGenerationProgress.failed} failed`
                      : `Audio generation complete — ${bulkGenerationProgress.completed} of ${bulkGenerationProgress.total} segments succeeded`}
                  </p>
                ) : (
                  <>
                    <p className="text-sm text-muted-foreground">
                      Generating audio… {bulkGenerationProgress.completed}/{bulkGenerationProgress.total} segments complete ({bulkPercentage}%)
                    </p>
                    <Progress value={bulkPercentage} className="w-full" />
                  </>
                )}
              </div>
            )}
            {/* ── Render Progress ── */}
            {isRendering && renderProgress && (
              <div className="w-full space-y-1.5 overflow-hidden">
                <p className="text-sm text-muted-foreground">
                  Rendering… segment {renderProgress.current_segment}/{renderProgress.total_segments} — {renderProgress.current_phase} ({renderPercentage}%)
                </p>
                <Progress value={renderPercentage} className="w-full" />
              </div>
            )}
            {isRendering && !renderProgress && (
              <div className="w-full">
                <p className="text-sm text-muted-foreground flex items-center gap-2">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  Preparing render pipeline…
                </p>
              </div>
            )}
            {renderStatus === 'completed' && outputUrl && (
              <div className="w-full">
                <p className="text-sm font-medium text-green-600 dark:text-green-400 flex items-center gap-2">
                  <CheckCircle className="h-3.5 w-3.5" />
                  Video rendered successfully — ready to download
                </p>
              </div>
            )}
            {renderStatus === 'failed' && (
              <div className="w-full">
                <p className="text-sm font-medium text-destructive flex items-center gap-2">
                  <AlertCircle className="h-3.5 w-3.5" />
                  Render failed — check that all segments have images and audio
                </p>
              </div>
            )}
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
