import Link from 'next/link';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Project } from '@/lib/types';

interface ProjectCardProps {
  project: Project;
}

const statusVariant: Record<Project['status'], 'default' | 'secondary' | 'destructive' | 'outline'> = {
  DRAFT: 'secondary',
  PROCESSING: 'outline',
  COMPLETED: 'default',
  FAILED: 'destructive',
};

export function ProjectCard({ project }: ProjectCardProps) {
  return (
    <Link href={`/projects/${project.id}`}>
      <Card className="hover:shadow-lg transition-shadow cursor-pointer">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg">{project.title}</CardTitle>
            <Badge variant={statusVariant[project.status]}>
              {project.status}
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
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
