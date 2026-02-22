import Link from 'next/link';
import { Card, CardContent, CardFooter } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel,
  AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import { Badge } from '@/components/ui/badge';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { Trash2, Film } from 'lucide-react';
import { deleteProject } from '@/lib/api';
import { Project } from '@/lib/types';

// ── Relative time utility (Step 7) ──

function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHr = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHr / 24);

  if (diffSec < 60) return 'Just now';
  if (diffMin < 60) return `${diffMin} minute${diffMin !== 1 ? 's' : ''} ago`;
  if (diffHr < 24) return `${diffHr} hour${diffHr !== 1 ? 's' : ''} ago`;
  if (diffDay === 1) return 'Yesterday';
  if (diffDay < 30) return `${diffDay} day${diffDay !== 1 ? 's' : ''} ago`;
  const diffMonth = Math.floor(diffDay / 30);
  if (diffMonth < 12) return `${diffMonth} month${diffMonth !== 1 ? 's' : ''} ago`;
  const diffYear = Math.floor(diffDay / 365);
  return `${diffYear} year${diffYear !== 1 ? 's' : ''} ago`;
}

function formatAbsoluteDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

// ── Status badge logic (Step 6) ──

type DerivedStatus = 'Draft' | 'In Progress' | 'Rendered' | 'Error';

function deriveBadge(status: Project['status']): {
  label: DerivedStatus;
  className: string;
} {
  switch (status) {
    case 'COMPLETED':
      return { label: 'Rendered', className: 'bg-green-500/15 text-green-700 dark:text-green-400 border-green-500/30' };
    case 'FAILED':
      return { label: 'Error', className: 'bg-destructive/15 text-destructive border-destructive/30' };
    case 'PROCESSING':
      return { label: 'In Progress', className: 'bg-amber-500/15 text-amber-700 dark:text-amber-400 border-amber-500/30 animate-pulse' };
    default:
      return { label: 'Draft', className: 'bg-muted text-muted-foreground border-border' };
  }
}

interface ProjectCardProps {
  project: Project;
  onDelete: (id: string) => void;
}

export function ProjectCard({ project, onDelete }: ProjectCardProps) {
  const hasSegments = project.segment_count > 0;
  const badge = deriveBadge(project.status);

  const handleDelete = async (e: React.MouseEvent) => {
    e.preventDefault();
    await deleteProject(String(project.id));
    onDelete(String(project.id));
  };

  return (
    <Link href={`/projects/${project.id}`}>
      <Card className={`overflow-hidden transition-all duration-200 ease-in-out hover:shadow-lg cursor-pointer ${
        hasSegments ? '' : 'opacity-75'
      }`}>
        {/* Cover Image Thumbnail (Step 5) */}
        <div className="relative aspect-video bg-gradient-to-br from-muted to-muted/60 flex items-center justify-center">
          <Film className="h-8 w-8 text-muted-foreground/40" />

          {/* Status Badge overlay (Step 6) */}
          <Badge
            variant="outline"
            className={`absolute top-2 right-2 text-[10px] px-1.5 py-0.5 ${badge.className}`}
          >
            {badge.label}
          </Badge>
        </div>

        {/* Card body */}
        <CardContent className="pt-4 pb-2">
          <div className="flex items-start justify-between gap-2">
            <h3 className="font-semibold text-base leading-tight line-clamp-1">
              {project.title}
            </h3>
            <div onClick={(e) => e.preventDefault()}>
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button variant="ghost" size="icon" className="h-7 w-7 shrink-0 text-destructive">
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>Delete Project</AlertDialogTitle>
                    <AlertDialogDescription>
                      Are you sure you want to delete &quot;{project.title}&quot;?
                      All segments and associated media will be permanently removed.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Cancel</AlertDialogCancel>
                    <AlertDialogAction
                      onClick={handleDelete}
                      className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                    >
                      Delete
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </div>
          </div>
          <p className={`text-sm mt-1 ${hasSegments ? 'text-foreground' : 'text-muted-foreground'}`}>
            {project.segment_count} segment{project.segment_count !== 1 ? 's' : ''}
          </p>
        </CardContent>

        <CardFooter className="flex items-center justify-between pb-4 pt-0">
          {/* Relative time with tooltip (Step 7) */}
          <Tooltip>
            <TooltipTrigger asChild>
              <p className="text-xs text-muted-foreground cursor-default">
                {formatRelativeTime(project.updated_at || project.created_at)}
              </p>
            </TooltipTrigger>
            <TooltipContent side="bottom">
              <p className="text-xs">{formatAbsoluteDate(project.updated_at || project.created_at)}</p>
            </TooltipContent>
          </Tooltip>

          {project.status === 'COMPLETED' && (
            <Button variant="outline" size="sm" className="text-xs h-7" asChild>
              <span>🎬 Watch</span>
            </Button>
          )}
        </CardFooter>
      </Card>
    </Link>
  );
}
