import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Separator } from '@/components/ui/separator';

function SkeletonSettingsCard({ rows = 3 }: { rows?: number }) {
  return (
    <Card>
      <CardHeader>
        <Skeleton className="h-5 w-40" />
        <Skeleton className="h-4 w-64 mt-1" />
      </CardHeader>
      <CardContent className="space-y-4">
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="space-y-2">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-9 w-full rounded-md" />
          </div>
        ))}
        <Skeleton className="h-9 w-24 rounded-md mt-2" />
      </CardContent>
    </Card>
  );
}

export function SettingsSkeleton() {
  return (
    <div>
      {/* Header */}
      <div className="mb-6">
        <Skeleton className="h-7 w-28" />
        <Skeleton className="h-4 w-64 mt-2" />
      </div>

      <div className="space-y-6 max-w-2xl">
        {/* TTS Test Card */}
        <SkeletonSettingsCard rows={4} />

        <Separator />

        {/* Subtitle Settings Card */}
        <SkeletonSettingsCard rows={3} />

        <Separator />

        {/* Logo Management Card */}
        <Card>
          <CardHeader>
            <Skeleton className="h-5 w-36" />
            <Skeleton className="h-4 w-56 mt-1" />
          </CardHeader>
          <CardContent>
            <Skeleton className="h-9 w-32 rounded-md mb-4" />
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="aspect-video w-full rounded-md" />
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
