'use client';

import { useState } from 'react';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { Button } from '@/components/ui/button';
import { ClipboardCopy, Check } from 'lucide-react';

interface ImagePromptDisplayProps {
  prompt: string;
}

export function ImagePromptDisplay({ prompt }: ImagePromptDisplayProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(prompt);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!prompt) {
    return (
      <div className="rounded-md bg-muted p-3">
        <p className="text-sm font-medium text-muted-foreground">Image Prompt</p>
        <p className="text-sm italic text-muted-foreground">No image prompt</p>
      </div>
    );
  }

  return (
    <div className="rounded-md bg-muted p-3 space-y-2">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium">Image Prompt</p>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="ghost" size="icon" onClick={handleCopy}>
              {copied ? <Check className="h-4 w-4" /> : <ClipboardCopy className="h-4 w-4" />}
            </Button>
          </TooltipTrigger>
          <TooltipContent>
            {copied ? 'Copied!' : 'Copy prompt to clipboard'}
          </TooltipContent>
        </Tooltip>
      </div>
      <p className="text-sm font-mono">{prompt}</p>
    </div>
  );
}
