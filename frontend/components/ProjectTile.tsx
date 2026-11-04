'use client';

import { MoreVertical, Pencil, Trash2, Clock, ExternalLink } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { Project } from '@/lib/types';
import { ProjectThumbnail } from '@/components/ProjectThumbnail';
import { cn } from '@/lib/utils';

interface ProjectTileProps {
  project: Project;
  badge: { label: string; className: string };
  updatedLabel: string;
  updatedAbsolute: string;
  thumbnailBusy: boolean;
  onOpen: () => void;
  onRename: () => void;
  onRequestDelete: () => void;
  onThumbnailUpload: (file: File) => void;
  onThumbnailRemove: () => void;
}

/** Card/grid presentation of one project, used by the Projects page. */
export function ProjectTile({
  project,
  badge,
  updatedLabel,
  updatedAbsolute,
  thumbnailBusy,
  onOpen,
  onRename,
  onRequestDelete,
  onThumbnailUpload,
  onThumbnailRemove,
}: ProjectTileProps) {
  return (
    <Card
      className="group cursor-pointer gap-0 overflow-hidden py-0 transition-all hover:-translate-y-0.5 hover:shadow-md hover:ring-2 hover:ring-primary/30"
      onClick={onOpen}
    >
      <ProjectThumbnail
        project={project}
        className="aspect-video w-full"
        editable
        busy={thumbnailBusy}
        onUpload={onThumbnailUpload}
        onRemove={onThumbnailRemove}
      />

      <CardContent className="space-y-2.5 p-3">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <h3
              className="truncate text-sm font-semibold leading-tight"
              title={project.title}
            >
              {project.title}
            </h3>
            <p className="mt-1 text-[11px] text-muted-foreground">
              {project.segment_count} segment
              {project.segment_count === 1 ? '' : 's'}
            </p>
          </div>
          <Badge
            variant="outline"
            className={cn('shrink-0 text-[10px]', badge.className)}
          >
            {badge.label}
          </Badge>
        </div>

        <div className="flex items-center justify-between gap-2">
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="flex items-center gap-1 text-[11px] text-muted-foreground">
                <Clock className="size-3" />
                {updatedLabel}
              </span>
            </TooltipTrigger>
            <TooltipContent side="bottom">
              <p className="text-xs">{updatedAbsolute}</p>
            </TooltipContent>
          </Tooltip>

          <div
            className="flex items-center gap-0.5"
            onClick={(event) => event.stopPropagation()}
          >
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  className="size-7 text-muted-foreground hover:text-foreground"
                  onClick={onRename}
                  aria-label={`Rename ${project.title}`}
                >
                  <Pencil className="size-3.5" />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="bottom">Rename</TooltipContent>
            </Tooltip>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  className="size-7 text-muted-foreground"
                  aria-label={`More actions for ${project.title}`}
                >
                  <MoreVertical className="size-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={onOpen}>
                  <ExternalLink className="mr-2 size-3.5" />
                  Open project
                </DropdownMenuItem>
                <DropdownMenuItem onClick={onRename}>
                  <Pencil className="mr-2 size-3.5" />
                  Rename
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  onClick={onRequestDelete}
                  className="text-destructive focus:text-destructive"
                >
                  <Trash2 className="mr-2 size-3.5" />
                  Delete
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
