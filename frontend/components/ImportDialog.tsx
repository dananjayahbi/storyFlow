'use client';

import { useState, useEffect, useRef } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { importProject } from '@/lib/api';
import { Project, ImportProjectRequest } from '@/lib/types';

interface ImportDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: (project: Project) => void;
}

const JSON_PLACEHOLDER = `{
  "title": "My Story",
  "segments": [
    {
      "text_content": "Your narration text...",
      "image_prompt": "Description of the image..."
    }
  ]
}`;

const TEXT_PLACEHOLDER = `Text: Your narration text for segment 1...
Prompt: Description of the image for segment 1...
---
Text: Your narration text for segment 2...
Prompt: Description of the image for segment 2...`;

export default function ImportDialog({ open, onOpenChange, onSuccess }: ImportDialogProps) {
  const [format, setFormat] = useState<'json' | 'text'>('json');
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errors, setErrors] = useState<Record<string, string[]> | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const mountedRef = useRef(true);

  // Track mount state for unmount safety
  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  // Reset state on dialog close
  useEffect(() => {
    if (!open) {
      setFormat('json');
      setTitle('');
      setContent('');
      setErrors(null);
      setIsSubmitting(false);
    }
  }, [open]);

  // Auto-focus textarea on dialog open
  useEffect(() => {
    if (open) {
      setTimeout(() => textareaRef.current?.focus(), 100);
    }
  }, [open]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      if (!isSubmitting && content.trim()) {
        handleSubmit();
      }
    }
  };

  const handleSubmit = async () => {
    setIsSubmitting(true);
    setErrors(null);

    try {
      const payload: ImportProjectRequest = {
        format,
        title: title.trim() || 'Untitled Project',
        ...(format === 'json'
          ? { segments: JSON.parse(content).segments }
          : { raw_text: content }),
      };

      // If JSON format and content has a title, use it
      if (format === 'json') {
        try {
          const parsed = JSON.parse(content);
          if (parsed.title && !title.trim()) {
            payload.title = parsed.title;
          }
          payload.segments = parsed.segments;
        } catch {
          if (mountedRef.current) {
            setErrors({ content: ['Invalid JSON format'] });
            setIsSubmitting(false);
          }
          return;
        }
      }

      const project = await importProject(payload);
      if (mountedRef.current) {
        onSuccess(project as unknown as Project);
        onOpenChange(false);
      }
    } catch (err: unknown) {
      if (mountedRef.current) {
        const error = err as { response?: { data?: Record<string, string[]> } };
        if (error.response?.data) {
          setErrors(error.response.data);
        } else {
          setErrors({ general: ['Import failed. Please try again.'] });
        }
      }
    } finally {
      if (mountedRef.current) {
        setIsSubmitting(false);
      }
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>Import Story</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          {/* Format Toggle */}
          <div className="flex gap-2">
            <Button
              type="button"
              variant={format === 'json' ? 'default' : 'outline'}
              onClick={() => setFormat('json')}
              className="flex-1"
            >
              JSON
            </Button>
            <Button
              type="button"
              variant={format === 'text' ? 'default' : 'outline'}
              onClick={() => setFormat('text')}
              className="flex-1"
            >
              Text
            </Button>
          </div>
          <p className="text-sm text-muted-foreground">
            {format === 'json'
              ? 'Paste a JSON object with title and segments array.'
              : 'Paste text blocks separated by --- with Text: and Prompt: lines.'}
          </p>

          {/* Title Input */}
          <div>
            <label htmlFor="import-title" className="text-sm font-medium">
              Project Title
            </label>
            <Input
              id="import-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Optional — will use JSON title or default"
              className="mt-1"
            />
          </div>

          {/* Content Textarea */}
          <div>
            <label htmlFor="import-content" className="text-sm font-medium">
              Content
            </label>
            <textarea
              id="import-content"
              ref={textareaRef}
              value={content}
              onChange={(e) => setContent(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={format === 'json' ? JSON_PLACEHOLDER : TEXT_PLACEHOLDER}
              rows={10}
              className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            />
            <p className="text-xs text-muted-foreground text-right">
              {content.length} characters
            </p>
          </div>

          {/* Error Display */}
          {errors && (
            <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive overflow-y-auto max-h-32">
              {Object.entries(errors).map(([key, messages]) => (
                <div key={key}>
                  {messages.map((msg, i) => (
                    <p key={i}>{key !== 'general' ? `${key}: ` : ''}{msg}</p>
                  ))}
                </div>
              ))}
            </div>
          )}
        </div>

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </Button>
          <Button
            type="button"
            onClick={handleSubmit}
            disabled={isSubmitting || content.trim() === ''}
          >
            {isSubmitting ? 'Importing...' : 'Import'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
