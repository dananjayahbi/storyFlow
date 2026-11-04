'use client';

import { useEffect } from 'react';
import { Loader2, Music, Wand2 } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useBgmStore } from '@/lib/stores';
import type { ProjectDetail, Segment } from '@/lib/types';

/**
 * Background-music track picker + MusicGen trigger, shown beside the main
 * "Generate All Audio" action whenever the project has BG music enabled.
 *
 * MusicGen needs the measured duration of every narration block, so the
 * trigger stays disabled until all TTS audio has been generated.
 */
export function BgmToolbarControls({
  project,
  segments = [],
}: {
  project: ProjectDetail;
  segments?: Segment[];
}) {
  const clips = useBgmStore((state) => state.clips);
  const engine = useBgmStore((state) => state.engine);
  const engineLoaded = useBgmStore((state) => state.engineLoaded);
  const generating = useBgmStore((state) => state.generating);
  const ensureLoaded = useBgmStore((state) => state.ensureLoaded);
  const generate = useBgmStore((state) => state.generate);
  const setActiveTrack = useBgmStore((state) => state.setActiveTrack);

  const missingTts = segments.filter(
    (segment) => !segment.audio_file || !segment.audio_duration
  );
  const ttsReady = segments.length > 0 && missingTts.length === 0;

  useEffect(() => {
    if (project.bgm_enabled) void ensureLoaded(project.id);
  }, [project.id, project.bgm_enabled, ensureLoaded]);

  if (!project.bgm_enabled) return null;

  const handleSelect = async (value: string) => {
    try {
      await setActiveTrack(value === 'none' ? null : value);
      toast.success('Background music updated');
    } catch {
      toast.error('Failed to update background music');
    }
  };

  const handleGenerate = async () => {
    const result = await generate(
      project.id,
      `${project.title} — Generated Soundtrack`
    );
    if (result.ok) {
      toast.success('Soundtrack generated and attached to this project');
    } else if (result.error) {
      toast.error(result.error);
    }
  };

  const unavailableReason =
    engineLoaded && !engine?.available
      ? engine?.reason || 'MusicGen is unavailable'
      : undefined;

  const missingTtsReason = !ttsReady
    ? segments.length === 0
      ? 'Add at least one narration block before generating music'
      : `Generate TTS audio for every block first (${missingTts.length} remaining)`
    : undefined;

  return (
    <div className="flex items-center gap-2">
      <Music className="hidden h-3.5 w-3.5 text-muted-foreground sm:block" />
      <Select
        value={project.active_bgm ?? 'none'}
        onValueChange={(value) => void handleSelect(value)}
      >
        <SelectTrigger
          className="h-8 w-[150px] text-xs"
          title="Background music track"
        >
          <SelectValue placeholder="BG music…" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="none">No BG music</SelectItem>
          {clips.map((clip) => (
            <SelectItem key={clip.id} value={clip.id}>
              {clip.name}
              {clip.source === 'generated' ? ' · generated' : ''}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Button
        size="sm"
        variant="outline"
        className="h-8 text-xs"
        onClick={() => void handleGenerate()}
        disabled={
          generating ||
          !ttsReady ||
          (engineLoaded && !engine?.available)
        }
        title={
          unavailableReason ||
          missingTtsReason ||
          'Generate a continuous MusicGen soundtrack from this script'
        }
      >
        {generating ? (
          <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
        ) : (
          <Wand2 className="mr-1.5 h-3.5 w-3.5" />
        )}
        {generating ? 'Generating…' : 'Generate with MusicGen'}
      </Button>
    </div>
  );
}
