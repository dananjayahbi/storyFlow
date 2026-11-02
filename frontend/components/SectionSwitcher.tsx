'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { sectionFromPathname, sectionPath } from '@/lib/section';

export function SectionSwitcher() {
  const pathname = usePathname();
  const section = sectionFromPathname(pathname);

  // Preserve the current sub-page when switching sections. A dashboard
  // (/facebook or /youtube) stays a dashboard; sub-pages keep their path.
  const rawRest = pathname.replace(/^\/(facebook|youtube)/, '');
  const rest = rawRest === '' || rawRest === '/' ? '' : rawRest;

  return (
    <div className="flex items-center gap-2">
      <Button asChild variant={section === 'facebook' ? 'default' : 'outline'} size="sm">
        <Link href={sectionPath('facebook', rest)}>Facebook</Link>
      </Button>
      <Button asChild variant={section === 'youtube' ? 'default' : 'outline'} size="sm">
        <Link href={sectionPath('youtube', rest)}>YouTube</Link>
      </Button>
    </div>
  );
}
