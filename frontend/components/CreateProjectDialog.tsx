'use client';

import { useMemo, useState } from 'react';
import { createProject } from '@/lib/api';
import { getCurrentSection } from '@/lib/section';
import { VALIDATION } from '@/lib/constants';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';

interface CreateProjectDialogProps {
  onProjectCreated: () => void;
}

const DEFAULT_RESOLUTION = { width: 1920, height: 1080 };

export function CreateProjectDialog({ onProjectCreated }: CreateProjectDialogProps) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState('');
  const [resolution, setResolution] = useState(
    `${DEFAULT_RESOLUTION.width}x${DEFAULT_RESOLUTION.height}`,
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const presets = useMemo(() => {
    const groups: Record<string, typeof VALIDATION.RESOLUTION_PRESETS[number][]> = {};
    for (const preset of VALIDATION.RESOLUTION_PRESETS) {
      if (!groups[preset.category]) groups[preset.category] = [];
      groups[preset.category].push(preset);
    }
    return groups;
  }, []);

  const handleSubmit = async () => {
    if (!title.trim()) return;

    try {
      setLoading(true);
      setError(null);
      const section = getCurrentSection();
      const [width, height] = resolution.split('x').map(Number);
      await createProject({
        title: title.trim(),
        section,
        resolution_width: width,
        resolution_height: height,
      });
      setTitle('');
      setOpen(false);
      onProjectCreated();
    } catch (err) {
      setError('Failed to create project. Please try again.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button data-create-project-trigger>Create Project</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create New Project</DialogTitle>
          <DialogDescription>
            Pick a title and resolution. The project starts with that
            resolution&apos;s default settings.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <Input
            placeholder="Project title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && title.trim()) {
                handleSubmit();
              }
            }}
            disabled={loading}
          />

          <div className="space-y-2">
            <label htmlFor="create-project-resolution" className="text-sm font-medium">
              Resolution
            </label>
            <select
              id="create-project-resolution"
              value={resolution}
              onChange={(e) => setResolution(e.target.value)}
              disabled={loading}
              className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm"
            >
              {Object.entries(presets).map(([category, items]) => (
                <optgroup key={category} label={category}>
                  {items.map((preset) => (
                    <option
                      key={`${preset.width}x${preset.height}`}
                      value={`${preset.width}x${preset.height}`}
                    >
                      {preset.label} · {preset.width}×{preset.height} · {preset.aspect}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
            <p className="text-xs text-muted-foreground">
              Defaults are managed under Settings → Default Project Settings.
            </p>
          </div>

          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}
        </div>
        <DialogFooter>
          <Button
            onClick={handleSubmit}
            disabled={!title.trim() || loading}
          >
            {loading ? 'Creating...' : 'Create'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
