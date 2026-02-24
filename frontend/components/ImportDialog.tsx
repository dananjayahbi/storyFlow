'use client';

import { useState, useEffect, useRef } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { importProject, importSegments, updateProject } from '@/lib/api';
import { Project, ImportProjectRequest, Segment } from '@/lib/types';

interface ImportDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: (project: Project) => void;
  /** When provided, imports segments into an existing project instead of creating a new one. */
  projectId?: string;
  /** Called when segments are imported into an existing project. */
  onSegmentsImported?: (segments: Segment[]) => void;
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

export default function ImportDialog({ open, onOpenChange, onSuccess, projectId, onSegmentsImported }: ImportDialogProps) {
  const [format, setFormat] = useState<'json' | 'text'>('json');
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errors, setErrors] = useState<Record<string, string[]> | null>(null);
  const [detectedTitle, setDetectedTitle] = useState<string | null>(null);
  const [useImportedTitle, setUseImportedTitle] = useState(true);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const mountedRef = useRef(true);

  const isAppendMode = !!projectId;

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
      setDetectedTitle(null);
      setUseImportedTitle(true);
    }
  }, [open]);

  // Detect title from JSON content (for append mode)
  useEffect(() => {
    if (!isAppendMode || format !== 'json' || !content.trim()) {
      setDetectedTitle(null);
      return;
    }
    try {
      const parsed = JSON.parse(content);
      if (parsed.title && typeof parsed.title === 'string' && parsed.title.trim()) {
        setDetectedTitle(parsed.title.trim());
      } else {
        setDetectedTitle(null);
      }
    } catch {
      setDetectedTitle(null);
    }
  }, [content, format, isAppendMode]);

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
      // Parse JSON content first if needed
      let segments: Array<{ text_content: string; image_prompt?: string }> | undefined;
      let rawText: string | undefined;

      if (format === 'json') {
        try {
          const parsed = JSON.parse(content);
          segments = parsed.segments;
          // For new project mode, extract title from JSON if not provided
          if (!isAppendMode && parsed.title && !title.trim()) {
            // will be used below
          }
        } catch {
          if (mountedRef.current) {
            setErrors({ content: ['Invalid JSON format'] });
            setIsSubmitting(false);
          }
          return;
        }
      } else {
        rawText = content;
      }

      if (isAppendMode) {
        // Import segments into existing project
        const importPayload = {
          format,
          ...(format === 'json' ? { segments } : { raw_text: rawText }),
        };
        const allSegments = await importSegments(projectId, importPayload);

        // Optionally rename the project with the imported story title
        if (detectedTitle && useImportedTitle) {
          try {
            await updateProject(projectId, { title: detectedTitle });
          } catch {
            // Non-critical — segments were imported successfully
          }
        }

        if (mountedRef.current) {
          onSegmentsImported?.(allSegments);
          onOpenChange(false);
        }
      } else {
        // Create new project (original behavior)
        const parsed = format === 'json' ? JSON.parse(content) : null;
        const payload: ImportProjectRequest = {
          format,
          title: title.trim() || (parsed?.title) || 'Untitled Project',
          ...(format === 'json' ? { segments } : { raw_text: rawText }),
        };

        const project = await importProject(payload);
        if (mountedRef.current) {
          onSuccess(project as unknown as Project);
          onOpenChange(false);
        }
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
          <DialogTitle>{isAppendMode ? 'Import Segments' : 'Import Story'}</DialogTitle>
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

          {/* Title Input — hidden when importing into an existing project */}
          {!isAppendMode && (
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
          )}

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

          {/* Rename option when importing into existing project */}
          {isAppendMode && detectedTitle && (
            <label className="flex items-start gap-2.5 rounded-md border bg-muted/50 px-3 py-2.5 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={useImportedTitle}
                onChange={(e) => setUseImportedTitle(e.target.checked)}
                className="h-4 w-4 mt-0.5 rounded border-muted-foreground accent-primary cursor-pointer"
              />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium">
                  Rename project to &ldquo;{detectedTitle}&rdquo;
                </p>
                <p className="text-xs text-muted-foreground">
                  Update the project title with the imported story title
                </p>
              </div>
            </label>
          )}

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
