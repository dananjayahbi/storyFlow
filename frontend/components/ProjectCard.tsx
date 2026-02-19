import Link from 'next/link';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel,
  AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import { Trash2 } from 'lucide-react';
import { deleteProject } from '@/lib/api';
import { Project } from '@/lib/types';

interface ProjectCardProps {
  project: Project;
  onDelete: (id: string) => void;
}

const statusVariant: Record<Project['status'], 'default' | 'secondary' | 'destructive' | 'outline'> = {
  DRAFT: 'secondary',
  PROCESSING: 'outline',
  COMPLETED: 'default',
  FAILED: 'destructive',
};

export function ProjectCard({ project, onDelete }: ProjectCardProps) {
  const hasSegments = project.segment_count > 0;

  const handleDelete = async (e: React.MouseEvent) => {
    e.preventDefault();
    await deleteProject(String(project.id));
    onDelete(String(project.id));
  };

  return (
    <Link href={`/projects/${project.id}`}>
      <Card className={`hover:shadow-lg transition-shadow cursor-pointer ${
        hasSegments ? '' : 'opacity-75'
      }`}>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg">{project.title}</CardTitle>
            <div className="flex items-center gap-1">
              <Badge variant={statusVariant[project.status]}>
                {project.status}
              </Badge>
              <div onClick={(e) => e.preventDefault()}>
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive">
                      <Trash2 className="h-4 w-4" />
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
          </div>
        </CardHeader>
        <CardContent>
          <p className={`text-sm ${hasSegments ? 'text-foreground' : 'text-muted-foreground'}`}>
            {project.segment_count} segment{project.segment_count !== 1 ? 's' : ''}
          </p>
        </CardContent>
        <CardFooter>
          <p className="text-xs text-muted-foreground">
            Created {new Date(project.created_at).toLocaleDateString('en-US', {
              year: 'numeric',
              month: 'short',
              day: 'numeric',
            })}
          </p>
        </CardFooter>
      </Card>
    </Link>
  );
}
