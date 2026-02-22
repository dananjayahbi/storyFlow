'use client';

import { useEffect } from 'react';
import { useSettingsStore } from '@/lib/stores';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Mic } from 'lucide-react';
import { toast } from 'sonner';

// ── Props ──────────────────────────────────────────────────────────
interface VoiceSelectorProps {
  /** Currently selected voice ID (e.g. "af_bella"). */
  value: string;
  /** Called with a partial settings update when the user picks a voice. */
  onChange: (data: { default_voice_id: string }) => Promise<void>;
}

// ── Helpers ────────────────────────────────────────────────────────

/** Build a user-friendly display label such as "Bella (Female)" or
 *  "Emma (British Female)". */
function formatVoiceLabel(name: string, gender: string, accent?: string): string {
  if (accent) {
    return `${name} (${accent} ${gender})`;
  }
  return `${name} (${gender})`;
}

// ── Component ──────────────────────────────────────────────────────

export function VoiceSelector({ value, onChange }: VoiceSelectorProps) {
  const { availableVoices, isVoicesLoading, fetchVoices } = useSettingsStore();

  // Fetch the voice list on mount
  useEffect(() => {
    if (availableVoices.length === 0) {
      fetchVoices();
    }
  }, [availableVoices.length, fetchVoices]);

  // ── Handler: voice selection changed ──
  const handleChange = async (selectedId: string) => {
    if (selectedId === value) return; // no-op if same voice
    try {
      await onChange({ default_voice_id: selectedId });
      toast.warning(
        'Voice changed. Re-generate audio to hear the new voice.'
      );
    } catch {
      // onChange already shows an error toast via GlobalSettingsPanel
    }
  };

  return (
    <div className="space-y-2">
      {/* ── Section Label ── */}
      <div className="flex items-center gap-1.5">
        <Mic className="h-4 w-4 text-muted-foreground" />
        <label className="text-xs text-muted-foreground font-medium">
          Voice
        </label>
      </div>

      {/* ── Select Dropdown ── */}
      <Select
        value={value}
        onValueChange={handleChange}
        disabled={isVoicesLoading}
      >
        <SelectTrigger className="w-full">
          <SelectValue
            placeholder={isVoicesLoading ? 'Loading voices...' : 'Select a voice'}
          />
        </SelectTrigger>

        <SelectContent>
          {availableVoices.map((voice) => (
            <SelectItem key={voice.id} value={voice.id}>
              {formatVoiceLabel(voice.name, voice.gender, voice.accent)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
