'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { sectionFromPathname, sectionPath } from '@/lib/section';

export function SectionSwitcher() {
  const pathname = usePathname();
  const section = sectionFromPathname(pathname);

  // Switching sides always lands on that side's account picker. Accounts are
  // side-specific, so carrying a Facebook account id into YouTube would be
  // meaningless (and is rejected by the API).
  return (
    <div className="flex items-center gap-1 rounded-lg border border-sidebar-border/60 p-0.5">
      <Button
        asChild
        variant={section === 'facebook' ? 'secondary' : 'ghost'}
        size="sm"
        className="h-7 px-2.5 text-xs"
      >
        <Link href={sectionPath('facebook')}>Facebook</Link>
      </Button>
      <Button
        asChild
        variant={section === 'youtube' ? 'secondary' : 'ghost'}
        size="sm"
        className="h-7 px-2.5 text-xs"
      >
        <Link href={sectionPath('youtube')}>YouTube</Link>
      </Button>
    </div>
  );
}
