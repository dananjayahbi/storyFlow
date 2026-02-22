'use client';

import { useEffect } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { useProjectStore } from '@/lib/stores';
import { Timeline } from '@/components/Timeline';
import { GlobalSettingsPanel } from '@/components/GlobalSettingsPanel';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import { Progress } from '@/components/ui/progress';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { ArrowLeft, Volume2, Film, Loader2, X } from 'lucide-react';

export default function TimelineEditorPage() {
  const params = useParams();
  const id = params.id as string;
  const {
    project, segments, isLoading, error,
    fetchProject, updateSegment, deleteSegment,
    uploadImage, removeImage, reset,
    bulkGenerationProgress, generateAllAudio, cancelGeneration,
  } = useProjectStore();

  const isGenerating = !!bulkGenerationProgress &&
    bulkGenerationProgress.status !== 'COMPLETED' &&
    bulkGenerationProgress.status !== 'FAILED';

  const bulkPercentage = bulkGenerationProgress
    ? Math.round((bulkGenerationProgress.completed / Math.max(bulkGenerationProgress.total, 1)) * 100)
    : 0;

  useEffect(() => {
    fetchProject(id);
    return () => {
      cancelGeneration();
      reset();
    };
  }, [id, fetchProject, cancelGeneration, reset]);

  // Loading state
  if (isLoading) {
    return (
      <div className="flex flex-col h-screen bg-background">
        <header className="border-b p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
          <Skeleton className="h-8 w-48 sm:w-64" />
          <Skeleton className="h-9 w-40" />
        </header>
        <div className="flex flex-col lg:flex-row flex-1 overflow-hidden">
          <aside className="lg:w-64 lg:border-r border-b lg:border-b-0 p-4 flex-shrink-0">
            <div className="flex flex-row lg:flex-col gap-4 lg:gap-4 flex-wrap">
              <Skeleton className="h-6 w-40" />
              <Skeleton className="h-5 w-20" />
              <Skeleton className="h-5 w-32" />
              <Skeleton className="h-5 w-36" />
            </div>
          </aside>
          <main className="flex-1 p-4 space-y-4">
            <Skeleton className="h-48 w-full" />
            <Skeleton className="h-48 w-full" />
            <Skeleton className="h-48 w-full" />
          </main>
        </div>
      </div>
    );
  }

  // Error state
  if (error || !project) {
    return (
      <div className="flex flex-col items-center justify-center h-screen gap-4 bg-background px-4">
        <p className="text-lg text-destructive">{error || 'Project not found'}</p>
        <div className="flex gap-2">
          <Button onClick={() => fetchProject(id)}>Retry</Button>
          <Button variant="outline" asChild>
            <Link href="/">Back to Dashboard</Link>
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen bg-background text-foreground">
      {/* Header */}
      <header className="border-b p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
        <div className="flex items-center gap-3 min-w-0">
          <h1 className="text-lg sm:text-xl font-bold truncate">
            StoryFlow — {project.title}
          </h1>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <Button variant="outline" size="sm" asChild>
            <Link href="/">
              <ArrowLeft className="h-4 w-4 mr-1" />
              <span className="hidden sm:inline">Back to Dashboard</span>
              <span className="sm:hidden">Back</span>
            </Link>
          </Button>
          <Button variant="outline" size="sm" disabled>
            Export
          </Button>
        </div>
      </header>

      {/* Main content */}
      <div className="flex flex-col lg:flex-row flex-1 overflow-hidden">
        {/* Left sidebar — project info + settings */}
        <div className="lg:border-r border-b lg:border-b-0 flex-shrink-0 lg:w-64 overflow-y-auto">
          {/* Project info */}
          <div className="p-4">
            <div className="flex flex-row lg:flex-col gap-4 lg:gap-4 flex-wrap">
              <div className="min-w-0">
                <p className="text-sm text-muted-foreground">Project</p>
                <p className="font-medium truncate">{project.title}</p>
              </div>
              <Separator className="hidden lg:block" />
              <div>
                <p className="text-sm text-muted-foreground">Status</p>
                <Badge variant="secondary" className="mt-1">
                  {project.status}
                </Badge>
              </div>
              <Separator className="hidden lg:block" />
              <div>
                <p className="text-sm text-muted-foreground">Segments</p>
                <p className="font-medium">{segments.length}</p>
              </div>
              <Separator className="hidden lg:block" />
              <div>
                <p className="text-sm text-muted-foreground">Created</p>
                <p className="font-medium">
                  {new Date(project.created_at).toLocaleDateString()}
                </p>
              </div>
            </div>
          </div>

          <Separator />

          {/* Global Settings Panel */}
          <GlobalSettingsPanel />
        </div>

        {/* Center panel */}
        <main className="flex-1 overflow-auto">
          <Timeline
            segments={segments}
            onUpdateSegment={updateSegment}
            onDeleteSegment={deleteSegment}
            onUploadImage={uploadImage}
            onRemoveImage={removeImage}
          />
        </main>
      </div>

      {/* Action bar */}
      <footer className="border-t p-3 sm:p-4 space-y-2">
        <div className="flex flex-wrap items-center gap-2 sm:gap-4">
          <Button
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
          <Tooltip>
            <TooltipTrigger asChild>
              <span>
                <Button disabled>
                  <Film className="h-4 w-4 mr-2" />
                  Export Video
                </Button>
              </span>
            </TooltipTrigger>
            <TooltipContent>Coming in Phase 04</TooltipContent>
          </Tooltip>
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
      </footer>
    </div>
  );
}
