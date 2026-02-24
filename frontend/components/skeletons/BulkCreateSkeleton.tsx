import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';

export function BulkCreateSkeleton() {
  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <Skeleton className="h-7 w-36" />
          <Skeleton className="h-4 w-72 mt-2" />
        </div>
      </div>

      {/* Project selection card */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <Skeleton className="h-5 w-36" />
              <Skeleton className="h-4 w-56 mt-1" />
            </div>
            <Skeleton className="h-8 w-32 rounded-md" />
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <div className="p-4 space-y-3">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="flex items-center gap-4 px-4">
                <Skeleton className="size-4 rounded" />
                <Skeleton className="h-4 w-48" />
                <Skeleton className="h-5 w-16 rounded-full" />
                <Skeleton className="h-4 w-20 ml-auto" />
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
