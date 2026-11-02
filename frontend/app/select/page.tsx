'use client';

import Link from 'next/link';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Film, Video } from 'lucide-react';
import { LogoutButton } from '@/components/LogoutButton';

const SECTIONS = [
  {
    title: 'Facebook Reels',
    description: 'Create and manage Facebook Reels projects.',
    href: '/facebook',
    section: 'facebook' as const,
    icon: Film,
  },
  {
    title: 'YouTube Videos',
    description: 'Create and manage YouTube video projects.',
    href: '/youtube',
    section: 'youtube' as const,
    icon: Video,
  },
];

export default function SelectionPage() {
  return (
    <div className="min-h-screen relative flex flex-col items-center justify-center bg-background p-6">
      <div className="absolute top-4 right-4">
        <LogoutButton />
      </div>
      <h1 className="text-3xl font-bold mb-2">Choose a Section</h1>
      <p className="text-muted-foreground mb-8">Select where you want to work.</p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 w-full max-w-3xl">
        {SECTIONS.map((section) => (
          <Link
            key={section.title}
            href={section.href}
            onClick={() => {
              try {
                sessionStorage.setItem('storyflow_section', section.section);
              } catch {
                // ignore
              }
            }}
          >
            <Card className="hover:bg-muted/50 transition-colors cursor-pointer h-full">
              <CardHeader>
                <div className="flex items-center gap-3">
                  <section.icon className="h-8 w-8" />
                  <CardTitle>{section.title}</CardTitle>
                </div>
                <CardDescription>{section.description}</CardDescription>
              </CardHeader>
              <CardContent />
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
