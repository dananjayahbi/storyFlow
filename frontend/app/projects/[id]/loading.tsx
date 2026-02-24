import { Skeleton } from '@/components/ui/skeleton';

export default function TimelineEditorLoading() {
  return (
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
  );
}
