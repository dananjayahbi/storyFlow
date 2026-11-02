'use client';

import Link from 'next/link';
import { Button } from '@/components/ui/button';

export default function YouTubePage() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-background p-6 gap-4">
      <h1 className="text-3xl font-bold">YouTube Videos</h1>
      <p className="text-muted-foreground">YouTube Videos workspace.</p>
      <Button asChild>
        <Link href="/projects">Go to Projects</Link>
      </Button>
    </div>
  );
}
