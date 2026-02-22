import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import { TooltipProvider } from '@/components/ui/tooltip';
import { ToastProvider } from '@/components/ToastProvider';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import './globals.css';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'StoryFlow',
  description: 'Semi-Automated Narrative Video Engine',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <header className="border-b bg-background">
          <div className="container mx-auto px-4 py-4">
            <h1 className="text-2xl font-bold">StoryFlow</h1>
          </div>
        </header>
        <main className="container mx-auto px-4 py-8">
          <TooltipProvider>
            <ErrorBoundary>
              {children}
            </ErrorBoundary>
          </TooltipProvider>
        </main>
        <ToastProvider />
      </body>
    </html>
  );
}
