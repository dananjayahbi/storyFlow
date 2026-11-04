'use client';

import { useState, useRef, useEffect } from 'react';
import {
  testTTS,
  getVoices,
  getAIConfig,
  updateAIConfig,
  updateSettings as updateAccountSettings,
} from '@/lib/api';
import type { AIConfig } from '@/lib/types';
import { AVAILABLE_VOICES, type Voice } from '@/lib/constants';
import { useSettingsStore as useLogoStore } from '@/lib/stores';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { Slider } from '@/components/ui/slider';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Volume2, Loader2, Play, Square, Type, Save, Image as ImageIcon,
  Trash2, Upload, Film, Cpu, Mic, AlertTriangle, CheckCircle2, Wand2,
  SlidersHorizontal, BookOpen,
} from 'lucide-react';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { useSettingsStore } from '@/store/settingsStore';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
import { SettingsSkeleton } from '@/components/skeletons';
import { SettingsMixPanel } from '@/components/SettingsMixPanel';
import { StoryTemplateModal } from '@/components/StoryTemplateModal';
import { mediaUrl } from '@/lib/apiConfig';

type SettingsTab =
  | 'tester'
  | 'engines'
  | 'voices'
  | 'subtitles'
  | 'logos'
  | 'outros'
  | 'mix'
  | 'template'
  | 'ai';

const SETTINGS_TABS: Array<{
  id: SettingsTab;
  label: string;
  description: string;
  icon: React.ElementType;
}> = [
  {
    id: 'tester',
    label: 'Audio Tester',
    description: 'Try voices before rendering',
    icon: Volume2,
  },
  {
    id: 'engines',
    label: 'TTS Engines',
    description: 'Kokoro & Qwen status',
    icon: Cpu,
  },
  {
    id: 'voices',
    label: 'Voice References',
    description: 'Clips for voice cloning',
    icon: Mic,
  },
  {
    id: 'subtitles',
    label: 'Subtitles',
    description: 'Font, size and position',
    icon: Type,
  },
  {
    id: 'logos',
    label: 'Logos',
    description: 'Watermarks for renders',
    icon: ImageIcon,
  },
  {
    id: 'outros',
    label: 'Outros',
    description: 'Clips appended at the end',
    icon: Film,
  },
  {
    id: 'mix',
    label: 'Audio Mix',
    description: 'Music, echo & demo tune',
    icon: SlidersHorizontal,
  },
  {
    id: 'template',
    label: 'Story Template',
    description: 'JSON import reference',
    icon: BookOpen,
  },
  {
    id: 'ai',
    label: 'AI Model',
    description: 'Script Craft model & prompt',
    icon: Wand2,
  },
];

const SETTINGS_TAB_STORAGE_KEY = 'storyflow.settings.tab';

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<SettingsTab>('tester');

  // Keep the selected tab across reloads. This matters for the Audio Mix
  // playground: a background job keeps running, and reloading should return
  // the operator to the progress panel instead of the default Audio Tester.
  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(SETTINGS_TAB_STORAGE_KEY);
      if (saved && SETTINGS_TABS.some((tab) => tab.id === saved)) {
        setActiveTab(saved as SettingsTab);
      }
    } catch {
      // localStorage may be unavailable in private/restricted contexts.
    }
  }, []);

  const selectTab = (tab: SettingsTab) => {
    setActiveTab(tab);
    try {
      window.localStorage.setItem(SETTINGS_TAB_STORAGE_KEY, tab);
    } catch {
      // Ignore storage failures; tab switching still works for this session.
    }
  };
  // TTS Tester state
  const [ttsText, setTtsText] = useState('Hello! This is a test of the StoryFlow text to speech engine.');
  const [ttsVoice, setTtsVoice] = useState('af_bella');
  const [ttsSpeed, setTtsSpeed] = useState(1.0);
  const [isGenerating, setIsGenerating] = useState(false);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [ttsError, setTtsError] = useState<string | null>(null);
  const [voices, setVoices] = useState<Voice[]>([]);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // TTS engine selection state (Kokoro default, Qwen optional)
  const [ttsEngine, setTtsEngine] = useState<'kokoro' | 'qwen'>('kokoro');
  const [qwenMode, setQwenMode] = useState<'custom_voice' | 'clone'>('custom_voice');
  const [qwenSpeaker, setQwenSpeaker] = useState('Aiden');
  const [qwenLanguage, setQwenLanguage] = useState('English');
  const [qwenInstruct, setQwenInstruct] = useState('');
  const [qwenMaxTokens, setQwenMaxTokens] = useState(1024);
  const [voiceReferenceId, setVoiceReferenceId] = useState<string>('');
  const [xVectorOnly, setXVectorOnly] = useState(true);
  const [isSavingTtsEngine, setIsSavingTtsEngine] = useState(false);
  const voiceRefInputRef = useRef<HTMLInputElement>(null);

  // Subtitle settings state
  const { settings, fetchSettings, saveSettings } = useSettingsStore();
  const [subtitleFontSize, setSubtitleFontSize] = useState(48);
  const [subtitlePosition, setSubtitlePosition] = useState<'bottom' | 'center' | 'top'>('bottom');
  const [subtitleFontColor, setSubtitleFontColor] = useState('#FFFFFF');
  const [isSavingSubtitles, setIsSavingSubtitles] = useState(false);
  const [subtitleSaveMsg, setSubtitleSaveMsg] = useState<string | null>(null);

  // Script Craft AI configuration (per account, with shared endpoint config)
  const [aiConfig, setAiConfig] = useState<AIConfig | null>(null);
  const [aiModel, setAiModel] = useState('');
  const [aiSystemPrompt, setAiSystemPrompt] = useState('');
  const [aiBaseUrl, setAiBaseUrl] = useState('http://localhost:11434/v1');
  const [aiApiKey, setAiApiKey] = useState('');
  const [aiTemperature, setAiTemperature] = useState(0.7);
  const [aiApplyToAll, setAiApplyToAll] = useState(false);
  const [searchEnabled, setSearchEnabled] = useState(true);
  const [searchProvider, setSearchProvider] = useState<'duckduckgo' | 'brave'>(
    'duckduckgo'
  );
  const [searchBraveApiKey, setSearchBraveApiKey] = useState('');
  const [searchRegion, setSearchRegion] = useState('wt-wt');
  const [isSavingAI, setIsSavingAI] = useState(false);
  const [aiConfirmOpen, setAiConfirmOpen] = useState(false);

  // Logo management state
  const {
    logos,
    isLogosLoading,
    isLogoUploading,
    fetchLogos,
    uploadLogo,
    deleteLogo,
    outroVideos,
    isOutrosLoading,
    isOutroUploading,
    fetchOutroVideos,
    uploadOutroVideo,
    deleteOutroVideo,
    ttsEngines,
    isTtsEnginesLoading,
    fetchTtsEngines,
    unloadQwen,
    voiceReferences,
    isVoiceReferencesLoading,
    isVoiceReferenceUploading,
    fetchVoiceReferences,
    uploadVoiceReference,
    updateVoiceReference,
    deleteVoiceReference,
  } = useLogoStore();
  const logoInputRef = useRef<HTMLInputElement>(null);
  const outroInputRef = useRef<HTMLInputElement>(null);

  // Derived engine capability info
  const kokoroEngine = ttsEngines.find((e) => e.id === 'kokoro');
  const qwenEngine = ttsEngines.find((e) => e.id === 'qwen');
  const qwenSpeakers = qwenEngine?.speakers ?? {};
  const qwenLanguages = qwenEngine?.languages ?? ['English'];

  // Fetch settings on mount
  useEffect(() => {
    fetchSettings();
    fetchLogos();
    fetchOutroVideos();
    fetchTtsEngines();
    fetchVoiceReferences();
  }, [
    fetchSettings, fetchLogos, fetchOutroVideos,
    fetchTtsEngines, fetchVoiceReferences,
  ]);

  // Load the account-specific Script Craft AI configuration.
  useEffect(() => {
    getAIConfig()
      .then((config) => {
        setAiConfig(config);
        setAiModel(config.model || config.default_model || '');
        setAiSystemPrompt(config.system_prompt || '');
        setAiBaseUrl(config.base_url || 'http://localhost:11434/v1');
        setAiApiKey(config.api_key || '');
        setAiTemperature(config.temperature ?? 0.7);
        setAiApplyToAll(config.apply_to_all ?? false);
        setSearchEnabled(config.search_enabled ?? true);
        setSearchProvider(config.search_provider ?? 'duckduckgo');
        setSearchBraveApiKey(config.search_brave_api_key || '');
        setSearchRegion(config.search_region || 'wt-wt');
      })
      .catch(() => {
        // The AI tab surfaces its own error state.
      });
  }, []);

  const saveAISettings = async () => {
    setIsSavingAI(true);
    try {
      const updated = await updateAIConfig({
        model: aiModel.trim(),
        system_prompt: aiSystemPrompt,
        base_url: aiBaseUrl.trim(),
        api_key: aiApiKey.trim(),
        temperature: aiTemperature,
        apply_to_all: aiApplyToAll,
        search_enabled: searchEnabled,
        search_provider: searchProvider,
        search_brave_api_key: searchBraveApiKey.trim(),
        search_region: searchRegion.trim() || 'wt-wt',
      });
      setAiConfig(updated);
      setAiModel(updated.model || updated.default_model || '');
      setAiApplyToAll(updated.apply_to_all);
      setSearchEnabled(updated.search_enabled);
      setSearchProvider(updated.search_provider);
      setSearchBraveApiKey(updated.search_brave_api_key || '');
      setSearchRegion(updated.search_region || 'wt-wt');
      toast.success(
        updated.apply_to_all
          ? 'AI model applied to every account'
          : 'AI settings saved for this account'
      );
    } catch {
      toast.error('Failed to save AI settings');
    } finally {
      setIsSavingAI(false);
    }
  };

  const requestSaveAI = () => {
    if (!aiModel.trim()) {
      toast.error('Choose an AI model before saving.');
      return;
    }
    if (aiApplyToAll) {
      setAiConfirmOpen(true);
      return;
    }
    saveAISettings();
  };

  // Sync local state when settings load
  useEffect(() => {
    if (settings) {
      setSubtitleFontSize(settings.subtitle_font_size ?? 48);
      setSubtitlePosition(settings.subtitle_position ?? 'bottom');
      setSubtitleFontColor(settings.subtitle_font_color ?? '#FFFFFF');
      setTtsEngine(settings.tts_engine ?? 'kokoro');
      setQwenMode(settings.qwen_mode ?? 'custom_voice');
      setQwenSpeaker(settings.qwen_speaker ?? 'Aiden');
      setQwenLanguage(settings.qwen_language ?? 'English');
      setQwenInstruct(settings.qwen_instruct ?? '');
      setQwenMaxTokens(settings.qwen_max_new_tokens ?? 1024);
      setVoiceReferenceId(settings.active_voice_reference ?? '');
      setXVectorOnly(settings.qwen_clone_x_vector_only ?? true);
    }
  }, [settings]);

  // Load available voices
  useEffect(() => {
    getVoices()
      .then((data) => setVoices(data))
      .catch(() => {
        setVoices(AVAILABLE_VOICES);
      });
  }, []);

  // Cleanup audio URL on unmount
  useEffect(() => {
    return () => {
      if (audioUrl) URL.revokeObjectURL(audioUrl);
    };
  }, [audioUrl]);

  const handleGenerateAudio = async () => {
    if (!ttsText.trim()) return;

    setIsGenerating(true);
    setTtsError(null);

    // Stop current audio if playing
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
      setIsPlaying(false);
    }

    // Revoke old URL
    if (audioUrl) {
      URL.revokeObjectURL(audioUrl);
      setAudioUrl(null);
    }

    try {
      const blob = await testTTS(ttsText, {
        engine: ttsEngine,
        voice: ttsVoice,
        speed: ttsSpeed,
        mode: qwenMode,
        speaker: qwenSpeaker,
        language: qwenLanguage,
        instruct: qwenInstruct,
        max_new_tokens: qwenMaxTokens,
        voice_reference_id: voiceReferenceId || null,
        x_vector_only: xVectorOnly,
      });

      // Check if the response is actually an error JSON
      if (blob.type === 'application/json') {
        const text = await blob.text();
        const err = JSON.parse(text);
        setTtsError(err.error || 'TTS generation failed');
        return;
      }

      const url = URL.createObjectURL(blob);
      setAudioUrl(url);
    } catch (err: unknown) {
      const error = err as { response?: { data?: Blob } };
      if (error.response?.data) {
        try {
          const text = await error.response.data.text();
          const parsed = JSON.parse(text);
          setTtsError(parsed.error || 'TTS generation failed');
        } catch {
          setTtsError('TTS generation failed. Check the backend server.');
        }
      } else {
        setTtsError('TTS generation failed. Check the backend server.');
      }
    } finally {
      setIsGenerating(false);
    }
  };

  const handleSaveTtsEngine = async () => {
    setIsSavingTtsEngine(true);
    try {
      await updateAccountSettings({ tts_engine: ttsEngine });
      await fetchSettings();
      toast.success(
        `Default TTS model saved: ${ttsEngine === 'qwen' ? 'Qwen3-TTS' : 'Kokoro'}`,
      );
    } catch {
      toast.error('Failed to save the default TTS model');
    } finally {
      setIsSavingTtsEngine(false);
    }
  };

  const handlePlayAudio = () => {
    if (!audioUrl) return;

    if (isPlaying && audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
      setIsPlaying(false);
      return;
    }

    const audio = new Audio(audioUrl);
    audioRef.current = audio;
    audio.onended = () => {
      setIsPlaying(false);
      audioRef.current = null;
    };
    audio.onerror = () => {
      setIsPlaying(false);
      audioRef.current = null;
      setTtsError('Failed to play audio');
    };
    audio.play();
    setIsPlaying(true);
  };

  // Show skeleton while initial settings are loading
  const isInitialLoading = !settings && !voices.length;

  if (isInitialLoading) {
    return <SettingsSkeleton />;
  }

  return (
    <div className="mx-auto w-full max-w-6xl">
      {/* Page header */}
      <div className="mb-6 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Settings</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Configure voices, rendering defaults and AI for this account. Each
            account can keep different values.
          </p>
        </div>
        <span className="text-xs text-muted-foreground rounded-full border px-3 py-1 self-start sm:self-auto">
          Saved for the selected account
        </span>
      </div>

      <div className="grid items-start gap-6 lg:grid-cols-[236px_minmax(0,1fr)]">
        {/* Settings section rail */}
        <aside className="lg:sticky lg:top-6">
          <nav className="flex gap-1 overflow-x-auto rounded-xl border bg-card p-1.5 lg:flex-col lg:overflow-visible">
            {SETTINGS_TABS.map((tab) => {
              const Icon = tab.icon;
              const active = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => selectTab(tab.id)}
                  className={cn(
                    'group flex shrink-0 items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-colors lg:w-full',
                    active
                      ? 'bg-primary/10 text-primary'
                      : 'text-muted-foreground hover:bg-muted/60 hover:text-foreground',
                  )}
                >
                  <span
                    className={cn(
                      'flex h-8 w-8 shrink-0 items-center justify-center rounded-md border transition-colors',
                      active
                        ? 'border-primary/30 bg-primary/10'
                        : 'border-border bg-background group-hover:border-primary/20',
                    )}
                  >
                    <Icon className="h-4 w-4" />
                  </span>
                  <span className="min-w-0">
                    <span className="block text-sm font-medium whitespace-nowrap">
                      {tab.label}
                    </span>
                    <span className="hidden text-[11px] text-muted-foreground lg:block">
                      {tab.description}
                    </span>
                  </span>
                </button>
              );
            })}
          </nav>
          <div className="mt-4 hidden rounded-xl border border-dashed bg-muted/20 p-4 lg:block">
            <p className="text-xs font-medium">Local-first</p>
            <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
              Models, voices and rendered media never leave this machine.
            </p>
          </div>
        </aside>

        {/* Active settings panel */}
        <div className="min-w-0">
      {/* TTS Tester Card */}
      {activeTab === 'tester' && (
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/10">
              <Volume2 className="h-4 w-4 text-primary" />
            </div>
            <div>
              <CardTitle className="text-lg">TTS Audio Tester</CardTitle>
              <CardDescription>
                Test voice settings with custom text before applying to your project.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-5">
          {/* Engine selector */}
          <div className="space-y-2">
            <label htmlFor="tts-engine" className="text-sm font-medium">
              Engine
            </label>
            <select
              id="tts-engine"
              value={ttsEngine}
              onChange={(e) => setTtsEngine(e.target.value as 'kokoro' | 'qwen')}
              className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              <option value="kokoro" disabled={kokoroEngine ? !kokoroEngine.available : false}>
                Kokoro — fast draft (default)
              </option>
              <option value="qwen" disabled={qwenEngine ? !qwenEngine.available : false}>
                Qwen3-TTS — GPU{qwenEngine && !qwenEngine.available ? ' (unavailable)' : ''}
              </option>
            </select>
            <p className="text-xs text-muted-foreground">
              {ttsEngine === 'kokoro'
                ? 'Lightweight CPU engine. Build a full draft video quickly, then regenerate with Qwen.'
                : qwenEngine?.available
                  ? `GPU: ${qwenEngine.device}. Only one checkpoint is resident at a time.`
                  : qwenEngine?.error || 'Qwen requires a CUDA GPU and the dedicated Python 3.11 environment.'}
            </p>
          </div>

          {ttsEngine === 'kokoro' ? (
            <>
              {/* Kokoro voice selector */}
              <div className="space-y-2">
                <label htmlFor="tts-voice" className="text-sm font-medium">
                  Voice
                </label>
                <select
                  id="tts-voice"
                  value={ttsVoice}
                  onChange={(e) => setTtsVoice(e.target.value)}
                  className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                >
                  {voices.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.name} ({v.gender}{v.accent ? `, ${v.accent}` : ''})
                    </option>
                  ))}
                </select>
              </div>

              {/* Speed control — using Slider */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-sm font-medium">Speed</label>
                  <span className="text-sm font-medium tabular-nums text-muted-foreground">
                    {ttsSpeed.toFixed(1)}x
                  </span>
                </div>
                <Slider
                  value={[ttsSpeed]}
                  min={0.5}
                  max={2.0}
                  step={0.1}
                  onValueChange={(values) => setTtsSpeed(values[0])}
                />
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">0.5x</span>
                  <span className="text-xs text-muted-foreground">2.0x</span>
                </div>
              </div>
            </>
          ) : (
            <>
              {/* Qwen mode */}
              <div className="space-y-2">
                <label htmlFor="qwen-mode" className="text-sm font-medium">
                  Voice mode
                </label>
                <select
                  id="qwen-mode"
                  value={qwenMode}
                  onChange={(e) => setQwenMode(e.target.value as 'custom_voice' | 'clone')}
                  className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm"
                >
                  <option value="custom_voice">Preset voice</option>
                  <option value="clone">Voice cloning (reference clip)</option>
                </select>
              </div>

              {qwenMode === 'custom_voice' ? (
                <div className="space-y-2">
                  <label htmlFor="qwen-speaker" className="text-sm font-medium">
                    Speaker
                  </label>
                  <select
                    id="qwen-speaker"
                    value={qwenSpeaker}
                    onChange={(e) => setQwenSpeaker(e.target.value)}
                    className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm"
                  >
                    {Object.entries(qwenSpeakers).map(([id, label]) => (
                      <option key={id} value={id}>{label}</option>
                    ))}
                  </select>
                </div>
              ) : (
                <div className="space-y-2">
                  <label htmlFor="qwen-reference" className="text-sm font-medium">
                    Reference voice
                  </label>
                  <select
                    id="qwen-reference"
                    value={voiceReferenceId}
                    onChange={(e) => setVoiceReferenceId(e.target.value)}
                    className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm"
                  >
                    <option value="">Select a reference clip…</option>
                    {voiceReferences.map((ref) => (
                      <option key={ref.id} value={ref.id}>
                        {ref.name}{ref.duration ? ` (${ref.duration.toFixed(1)}s)` : ''}
                      </option>
                    ))}
                  </select>
                  <label className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer">
                    <input
                      type="checkbox"
                      checked={xVectorOnly}
                      onChange={(e) => setXVectorOnly(e.target.checked)}
                      className="h-3.5 w-3.5 accent-primary"
                    />
                    Speaker-embedding only (no transcript needed)
                  </label>
                </div>
              )}

              <div className="space-y-2">
                <label htmlFor="qwen-language" className="text-sm font-medium">
                  Language
                </label>
                <select
                  id="qwen-language"
                  value={qwenLanguage}
                  onChange={(e) => setQwenLanguage(e.target.value)}
                  className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm"
                >
                  {qwenLanguages.map((lang) => (
                    <option key={lang} value={lang}>{lang}</option>
                  ))}
                </select>
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-sm font-medium">Max new tokens</label>
                  <span className="text-sm font-medium tabular-nums text-muted-foreground">
                    {qwenMaxTokens}
                  </span>
                </div>
                <Slider
                  value={[qwenMaxTokens]}
                  min={256}
                  max={2048}
                  step={128}
                  onValueChange={(values) => setQwenMaxTokens(values[0])}
                />
                <p className="text-xs text-muted-foreground">
                  ~40 s of speech at 1024. Raise only if you have VRAM headroom.
                </p>
              </div>

              <div className="space-y-2">
                <label htmlFor="qwen-instruct" className="text-sm font-medium">
                  Style instruction <span className="text-muted-foreground">(optional)</span>
                </label>
                <textarea
                  id="qwen-instruct"
                  value={qwenInstruct}
                  onChange={(e) => setQwenInstruct(e.target.value)}
                  rows={2}
                  placeholder="e.g. calm documentary narration"
                  className="flex min-h-14 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm resize-y"
                />
                <p className="text-xs text-muted-foreground">
                  Ignored by the 0.6B checkpoint; supported by the 1.7B build.
                </p>
              </div>
            </>
          )}

          <Separator />

          {/* Text input */}
          <div className="space-y-2">
            <label htmlFor="tts-text" className="text-sm font-medium">
              Text to Speak
            </label>
            <textarea
              id="tts-text"
              value={ttsText}
              onChange={(e) => setTtsText(e.target.value)}
              rows={5}
              placeholder="Enter text to convert to speech..."
              className="flex min-h-20 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring resize-y"
            />
            <p className="text-xs text-muted-foreground text-right">
              {ttsText.length} characters
            </p>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-3">
            <Button
              onClick={handleGenerateAudio}
              disabled={isGenerating || !ttsText.trim()}
            >
              {isGenerating ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Generating...
                </>
              ) : (
                <>
                  <Volume2 className="h-4 w-4 mr-2" />
                  Generate Audio
                </>
              )}
            </Button>

            <Button
              variant="outline"
              onClick={() => void handleSaveTtsEngine()}
              disabled={isSavingTtsEngine}
              title="Use this engine for new audio on every project in this account"
            >
              {isSavingTtsEngine ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Save className="h-4 w-4 mr-2" />
              )}
              Save as default
            </Button>

            {audioUrl && (
              <Button
                variant="outline"
                onClick={handlePlayAudio}
              >
                {isPlaying ? (
                  <>
                    <Square className="h-4 w-4 mr-2" />
                    Stop
                  </>
                ) : (
                  <>
                    <Play className="h-4 w-4 mr-2" />
                    Play
                  </>
                )}
              </Button>
            )}
          </div>

          {/* Audio player */}
          {audioUrl && (
            <div className="rounded-md bg-muted/50 p-3">
              <audio controls src={audioUrl} className="w-full" />
            </div>
          )}

          {/* Error display */}
          {ttsError && (
            <div className="rounded-md bg-destructive/10 border border-destructive/20 p-3 text-sm text-destructive">
              {ttsError}
            </div>
          )}
        </CardContent>
      </Card>
      )}

      {/* ── TTS Engine Status Card ── */}
      {activeTab === 'engines' && (
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/10">
              <Cpu className="h-4 w-4 text-primary" />
            </div>
            <div>
              <CardTitle className="text-lg">TTS Engines</CardTitle>
              <CardDescription>
                Kokoro is the default. Qwen3-TTS is optional, GPU-only, and supports voice cloning.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="space-y-2 rounded-lg border bg-muted/20 p-3">
            <label htmlFor="default-tts-engine" className="text-sm font-medium">
              Default TTS model for this account
            </label>
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
              <select
                id="default-tts-engine"
                value={ttsEngine}
                onChange={(e) =>
                  setTtsEngine(e.target.value as 'kokoro' | 'qwen')
                }
                className="flex h-9 flex-1 rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                <option
                  value="kokoro"
                  disabled={kokoroEngine ? !kokoroEngine.available : false}
                >
                  Kokoro — fast draft (default)
                </option>
                <option
                  value="qwen"
                  disabled={qwenEngine ? !qwenEngine.available : false}
                >
                  Qwen3-TTS — GPU
                  {qwenEngine && !qwenEngine.available ? ' (unavailable)' : ''}
                </option>
              </select>
              <Button
                onClick={() => void handleSaveTtsEngine()}
                disabled={isSavingTtsEngine}
              >
                {isSavingTtsEngine ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Save className="mr-2 h-4 w-4" />
                )}
                Save model
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              Saving updates every existing project on this account. Generate
              the audio again to use the newly selected engine.
            </p>
          </div>

          {isTtsEnginesLoading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> Checking engines…
            </div>
          ) : (
            ttsEngines.map((engine) => (
              <div
                key={engine.id}
                className="flex items-start gap-3 border rounded-lg p-3"
              >
                <div className="mt-0.5">
                  {engine.available ? (
                    <CheckCircle2 className="h-4 w-4 text-green-600" />
                  ) : (
                    <AlertTriangle className="h-4 w-4 text-amber-500" />
                  )}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="text-sm font-medium">{engine.label}</p>
                    {engine.supports_cloning && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-primary/10 text-primary">
                        voice cloning
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {engine.available ? engine.device : (engine.error || 'Unavailable')}
                  </p>
                  {engine.description && (
                    <p className="text-xs text-muted-foreground mt-1">{engine.description}</p>
                  )}
                </div>
                {engine.id === 'qwen' && engine.available && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-7 text-xs shrink-0"
                    onClick={async () => {
                      try {
                        const message = await unloadQwen();
                        toast.success(message);
                      } catch {
                        toast.error('Could not unload Qwen');
                      }
                    }}
                  >
                    Unload VRAM
                  </Button>
                )}
              </div>
            ))
          )}
        </CardContent>
      </Card>
      )}

      {/* ── Voice References Card (Qwen cloning) ── */}
      {activeTab === 'voices' && (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Mic className="h-5 w-5" />
            Voice References
          </CardTitle>
          <CardDescription>
            Upload clean 3–10 second speech clips. Qwen can clone any of them when generating audio.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <input
              ref={voiceRefInputRef}
              type="file"
              accept=".wav,.mp3,.m4a,.mp4,.flac,.ogg,.opus,.webm,audio/*"
              className="hidden"
              onChange={async (e) => {
                const file = e.target.files?.[0];
                if (!file) return;
                if (file.size > 25 * 1024 * 1024) {
                  toast.error('Reference clips must be under 25 MB');
                  return;
                }
                try {
                  await uploadVoiceReference(file);
                  toast.success('Voice reference uploaded');
                } catch {
                  toast.error('Failed to upload voice reference');
                }
                if (voiceRefInputRef.current) voiceRefInputRef.current.value = '';
              }}
            />
            <Button
              variant="outline"
              onClick={() => voiceRefInputRef.current?.click()}
              disabled={isVoiceReferenceUploading}
            >
              {isVoiceReferenceUploading ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Uploading…
                </>
              ) : (
                <>
                  <Upload className="h-4 w-4 mr-2" />
                  Upload Reference Clip
                </>
              )}
            </Button>
            <p className="text-xs text-muted-foreground mt-1">
              WAV/MP3/M4A/FLAC. 3–10s of one speaker, minimal background noise. Max 25 MB.
            </p>
          </div>

          <Separator />

          {isVoiceReferencesLoading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading references…
            </div>
          ) : voiceReferences.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No reference clips yet. Upload one to enable Qwen voice cloning.
            </p>
          ) : (
            <div className="space-y-3">
              {voiceReferences.map((ref) => (
                <div key={ref.id} className="border rounded-lg p-3 space-y-2 group">
                  <div className="flex items-center gap-3">
                    <Mic className="h-4 w-4 text-muted-foreground shrink-0" />
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium truncate">{ref.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {ref.duration ? `${ref.duration.toFixed(1)}s · ` : ''}
                        Uploaded {new Date(ref.uploaded_at).toLocaleDateString()}
                      </p>
                    </div>
                    {ref.audio_url && (
                      <audio controls src={mediaUrl(ref.audio_url) ?? undefined} className="h-8 max-w-[180px]" />
                    )}
                    <Button
                      size="sm"
                      variant="destructive"
                      className="h-7 w-7 p-0 shrink-0"
                      onClick={async () => {
                        try {
                          await deleteVoiceReference(ref.id);
                          toast.success('Voice reference deleted');
                        } catch {
                          toast.error('Failed to delete voice reference');
                        }
                      }}
                    >
                      <Trash2 className="h-3 w-3" />
                    </Button>
                  </div>
                  <div className="pl-7">
                    <label className="text-[10px] uppercase tracking-wider text-muted-foreground">
                      Reference transcript (optional, improves cloning accuracy)
                    </label>
                    <textarea
                      defaultValue={ref.transcript}
                      rows={2}
                      placeholder="Exact words spoken in the clip…"
                      className="mt-1 w-full rounded-md border border-input bg-background px-2 py-1.5 text-xs resize-y"
                      onBlur={async (e) => {
                        if (e.target.value === ref.transcript) return;
                        try {
                          await updateVoiceReference(ref.id, { transcript: e.target.value });
                          toast.success('Transcript saved');
                        } catch {
                          toast.error('Failed to save transcript');
                        }
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
      )}

      {/* Subtitle Settings Card */}
      {activeTab === 'subtitles' && (
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/10">
              <Type className="h-4 w-4 text-primary" />
            </div>
            <div>
              <CardTitle className="text-lg">Subtitle Settings</CardTitle>
              <CardDescription>
                Adjust subtitle appearance for rendered videos.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-5">
          {/* Font Size */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium">Font Size</label>
              <span className="text-sm font-medium tabular-nums text-muted-foreground">
                {subtitleFontSize}px
              </span>
            </div>
            <Slider
              value={[subtitleFontSize]}
              min={12}
              max={120}
              step={1}
              onValueChange={(values) => setSubtitleFontSize(values[0])}
            />
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">12px</span>
              <span className="text-xs text-muted-foreground">120px</span>
            </div>
          </div>

          {/* Position */}
          <div className="space-y-2">
            <label htmlFor="subtitle-position" className="text-sm font-medium">
              Position
            </label>
            <select
              id="subtitle-position"
              value={subtitlePosition}
              onChange={(e) => setSubtitlePosition(e.target.value as 'bottom' | 'center' | 'top')}
              className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              <option value="bottom">Bottom</option>
              <option value="center">Center</option>
              <option value="top">Top</option>
            </select>
          </div>

          {/* Font Color */}
          <div className="space-y-2">
            <label className="text-sm font-medium">Font Color</label>
            <div className="flex items-center gap-3">
              <input
                type="color"
                value={subtitleFontColor}
                onChange={(e) => setSubtitleFontColor(e.target.value)}
                className="h-9 w-12 rounded-md border border-input bg-background p-1 cursor-pointer"
              />
              <input
                type="text"
                value={subtitleFontColor}
                onChange={(e) => {
                  const val = e.target.value;
                  if (/^#[0-9A-Fa-f]{0,6}$/.test(val)) setSubtitleFontColor(val);
                }}
                maxLength={7}
                className="flex h-9 w-28 rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm font-mono transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              />
            </div>
          </div>

          <Separator />

          {/* Save */}
          <div className="flex items-center gap-3">
            <Button
              onClick={async () => {
                setIsSavingSubtitles(true);
                setSubtitleSaveMsg(null);
                try {
                  await saveSettings({
                    subtitle_font_size: subtitleFontSize,
                    subtitle_position: subtitlePosition,
                    subtitle_font_color: subtitleFontColor,
                  });
                  setSubtitleSaveMsg('Saved successfully');
                  setTimeout(() => setSubtitleSaveMsg(null), 3000);
                } catch {
                  setSubtitleSaveMsg('Failed to save');
                } finally {
                  setIsSavingSubtitles(false);
                }
              }}
              disabled={isSavingSubtitles}
            >
              {isSavingSubtitles ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Save className="h-4 w-4 mr-2" />
                  Save Subtitle Settings
                </>
              )}
            </Button>

            {subtitleSaveMsg && (
              <span className={`text-sm ${subtitleSaveMsg.includes('Failed') ? 'text-destructive' : 'text-green-600'}`}>
                {subtitleSaveMsg}
              </span>
            )}
          </div>
        </CardContent>
      </Card>
      )}

      {/* ── Logo Management Card ── */}
      {activeTab === 'logos' && (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ImageIcon className="h-5 w-5" />
            Logo Management
          </CardTitle>
          <CardDescription>
            Upload logos to burn into your rendered videos as watermarks.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Upload Button */}
          <div>
            <input
              ref={logoInputRef}
              type="file"
              accept=".png,.webp,.jpg,.jpeg"
              className="hidden"
              onChange={async (e) => {
                const file = e.target.files?.[0];
                if (!file) return;

                // Validate size
                if (file.size > 5 * 1024 * 1024) {
                  toast.error('Logo file must be under 5 MB');
                  return;
                }

                try {
                  await uploadLogo(file);
                  toast.success('Logo uploaded successfully');
                } catch {
                  toast.error('Failed to upload logo');
                }

                // Reset input
                if (logoInputRef.current) logoInputRef.current.value = '';
              }}
            />
            <Button
              variant="outline"
              onClick={() => logoInputRef.current?.click()}
              disabled={isLogoUploading}
            >
              {isLogoUploading ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Uploading…
                </>
              ) : (
                <>
                  <Upload className="h-4 w-4 mr-2" />
                  Upload Logo
                </>
              )}
            </Button>
            <p className="text-xs text-muted-foreground mt-1">
              PNG recommended for transparency. Max 5 MB.
            </p>
          </div>

          <Separator />

          {/* Logo Grid */}
          {isLogosLoading ? (
            <div className="flex items-center gap-2 text-muted-foreground text-sm">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading logos…
            </div>
          ) : logos.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No logos uploaded yet. Upload a logo to use as a video watermark.
            </p>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
              {logos.map((logo) => (
                <div
                  key={logo.id}
                  className="relative group border rounded-lg p-2 flex flex-col items-center gap-2"
                >
                  <div className="w-full aspect-square bg-muted/30 rounded flex items-center justify-center overflow-hidden">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={mediaUrl(logo.file) ?? undefined}
                      alt={logo.name}
                      className="max-w-full max-h-full object-contain"
                    />
                  </div>
                  <span className="text-xs text-muted-foreground truncate w-full text-center">
                    {logo.name}
                  </span>
                  <Button
                    size="sm"
                    variant="destructive"
                    className="absolute top-1 right-1 h-7 w-7 p-0 opacity-0 group-hover:opacity-100 transition-opacity"
                    onClick={async () => {
                      try {
                        await deleteLogo(logo.id);
                        toast.success('Logo deleted');
                      } catch {
                        toast.error('Failed to delete logo');
                      }
                    }}
                  >
                    <Trash2 className="h-3 w-3" />
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
      )}

      {/* ── Outro Video Management Card ── */}
      {activeTab === 'outros' && (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Film className="h-5 w-5" />
            Outro Video Management
          </CardTitle>
          <CardDescription>
            Upload outro/logo animation videos to append at the end of rendered videos.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Upload Button */}
          <div>
            <input
              ref={outroInputRef}
              type="file"
              accept=".mp4,.mov,.webm,.avi,.mkv"
              className="hidden"
              onChange={async (e) => {
                const file = e.target.files?.[0];
                if (!file) return;
                if (file.size > 100 * 1024 * 1024) {
                  toast.error('Outro video file must be under 100 MB');
                  return;
                }
                try {
                  await uploadOutroVideo(file);
                  toast.success('Outro video uploaded successfully');
                } catch {
                  toast.error('Failed to upload outro video');
                }
                if (outroInputRef.current) outroInputRef.current.value = '';
              }}
            />
            <Button
              variant="outline"
              onClick={() => outroInputRef.current?.click()}
              disabled={isOutroUploading}
            >
              {isOutroUploading ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Uploading…
                </>
              ) : (
                <>
                  <Upload className="h-4 w-4 mr-2" />
                  Upload Outro Video
                </>
              )}
            </Button>
            <p className="text-xs text-muted-foreground mt-1">
              MP4 recommended. Max 100 MB.
            </p>
          </div>

          <Separator />

          {/* Outro Videos List */}
          {isOutrosLoading ? (
            <div className="flex items-center gap-2 text-muted-foreground text-sm">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading outro videos…
            </div>
          ) : outroVideos.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No outro videos uploaded yet. Upload a video to append at the end of your renders.
            </p>
          ) : (
            <div className="space-y-2">
              {outroVideos.map((outro) => (
                <div
                  key={outro.id}
                  className="flex items-center justify-between gap-3 border rounded-lg p-3 group"
                >
                  <div className="flex items-center gap-3 min-w-0 flex-1">
                    <Film className="h-5 w-5 text-muted-foreground flex-shrink-0" />
                    <div className="min-w-0">
                      <p className="text-sm font-medium truncate">
                        {outro.name}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        Uploaded {new Date(outro.uploaded_at).toLocaleDateString()}
                      </p>
                    </div>
                  </div>
                  <Button
                    size="sm"
                    variant="destructive"
                    className="h-8 w-8 p-0 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0"
                    onClick={async () => {
                      try {
                        await deleteOutroVideo(outro.id);
                        toast.success('Outro video deleted');
                      } catch {
                        toast.error('Failed to delete outro video');
                      }
                    }}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
      )}
      {/* ── Audio Mix + demo playground ── */}
      {activeTab === 'mix' && <SettingsMixPanel />}

      {/* ── Story Template reference (moved from the project Details tab) ── */}
      {activeTab === 'template' && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BookOpen className="h-5 w-5" />
              Story Template
            </CardTitle>
            <CardDescription>
              The JSON structure used by Import Segments. Open the reference to
              copy the template or a complete example story.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <StoryTemplateModal
              trigger={
                <Button variant="outline">
                  <BookOpen className="mr-2 h-4 w-4" />
                  Open Story Template
                </Button>
              }
            />
            <p className="text-xs text-muted-foreground">
              Each segment needs narration text and an image prompt. Import the
              JSON with the Import Segments button in a project.
            </p>
          </CardContent>
        </Card>
      )}

      {/* ── Script Craft AI Configuration ── */}
      {activeTab === 'ai' && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Wand2 className="h-5 w-5" />
              Script Craft AI Model
            </CardTitle>
            <CardDescription>
              Configure the AI agent that writes scripts for this account. The
              model and system prompt are account-specific; the endpoint is
              shared by the whole app.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="space-y-2">
              <label htmlFor="ai-base-url" className="text-sm font-medium">
                API base URL
              </label>
              <input
                id="ai-base-url"
                value={aiBaseUrl}
                onChange={(event) => setAiBaseUrl(event.target.value)}
                placeholder="http://localhost:11434/v1"
                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm"
              />
              <p className="text-xs text-muted-foreground">
                Any OpenAI-compatible endpoint: Ollama, LM Studio, llama.cpp,
                vLLM, OpenAI, OpenRouter…
              </p>
            </div>

            <div className="space-y-2">
              <label htmlFor="ai-api-key" className="text-sm font-medium">
                API key <span className="text-muted-foreground">(optional)</span>
              </label>
              <input
                id="ai-api-key"
                type="password"
                value={aiApiKey}
                onChange={(event) => setAiApiKey(event.target.value)}
                placeholder="Not needed for local servers"
                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm"
              />
            </div>

            <Separator />

            <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_160px]">
              <div className="space-y-2">
                <label htmlFor="ai-model" className="text-sm font-medium">
                  Model for this account
                </label>
                <input
                  id="ai-model"
                  value={aiModel}
                  onChange={(event) => setAiModel(event.target.value)}
                  placeholder="e.g. llama3.1:8b or gpt-4o-mini"
                  className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm"
                />
                {aiConfig?.default_model && (
                  <p className="text-xs text-muted-foreground">
                    Workspace default: {aiConfig.default_model}
                  </p>
                )}
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label htmlFor="ai-temperature" className="text-sm font-medium">
                    Temperature
                  </label>
                  <span className="text-sm tabular-nums text-muted-foreground">
                    {aiTemperature.toFixed(1)}
                  </span>
                </div>
                <Slider
                  id="ai-temperature"
                  value={[aiTemperature]}
                  min={0}
                  max={1.5}
                  step={0.1}
                  onValueChange={(values) => setAiTemperature(values[0])}
                />
              </div>
            </div>

            <div className="space-y-2">
              <label htmlFor="ai-system-prompt" className="text-sm font-medium">
                System prompt
              </label>
              <textarea
                id="ai-system-prompt"
                value={aiSystemPrompt}
                onChange={(event) => setAiSystemPrompt(event.target.value)}
                rows={6}
                placeholder="Describe the voice, style and rules for this account's scripts. Leave blank to use the StoryFlow documentary default."
                className="flex min-h-28 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm resize-y"
              />
              <p className="text-xs text-muted-foreground">
                The agent always appends the required JSON output format, so the
                generated script can be parsed and saved to the library.
              </p>
            </div>

            <Separator />

            <div className="space-y-4">
              <div>
                <h3 className="text-sm font-semibold">Web search</h3>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  Lets the agent research facts, dates and statistics while
                  writing. It cites the sources it used.
                </p>
              </div>

              <div className="flex items-start gap-3 rounded-lg border p-3">
                <input
                  id="search-enabled"
                  type="checkbox"
                  checked={searchEnabled}
                  onChange={(event) => setSearchEnabled(event.target.checked)}
                  className="mt-0.5 h-4 w-4 accent-primary"
                />
                <div>
                  <label htmlFor="search-enabled" className="text-sm font-medium">
                    Enable web search
                  </label>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    On by default. When disabled the agent uses only its own
                    knowledge and the conversation.
                  </p>
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <label htmlFor="search-provider" className="text-sm font-medium">
                    Search provider
                  </label>
                  <select
                    id="search-provider"
                    value={searchProvider}
                    onChange={(event) =>
                      setSearchProvider(event.target.value as 'duckduckgo' | 'brave')
                    }
                    disabled={!searchEnabled}
                    className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:opacity-50"
                  >
                    <option value="duckduckgo">DuckDuckGo — no key needed (default)</option>
                    <option value="brave">Brave Search — API key required</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <label htmlFor="search-region" className="text-sm font-medium">
                    Region
                  </label>
                  <input
                    id="search-region"
                    value={searchRegion}
                    onChange={(event) => setSearchRegion(event.target.value)}
                    disabled={!searchEnabled}
                    placeholder="wt-wt"
                    className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm disabled:opacity-50"
                  />
                  <p className="text-xs text-muted-foreground">
                    e.g. us-en, gb-en, de-de. <code>wt-wt</code> means no
                    preference.
                  </p>
                </div>
              </div>

              {searchProvider === 'brave' && (
                <div className="space-y-2">
                  <label
                    htmlFor="search-brave-key"
                    className="text-sm font-medium"
                  >
                    Brave Search API key
                  </label>
                  <input
                    id="search-brave-key"
                    type="password"
                    value={searchBraveApiKey}
                    onChange={(event) => setSearchBraveApiKey(event.target.value)}
                    disabled={!searchEnabled}
                    placeholder="Paste your Brave Search subscription token"
                    className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm disabled:opacity-50"
                  />
                  <p className="text-xs text-muted-foreground">
                    Stored locally with the endpoint settings. Brave is only
                    used when selected above.
                  </p>
                </div>
              )}

              {searchEnabled && searchProvider === 'brave' && !searchBraveApiKey.trim() && (
                <p className="text-xs text-amber-600 dark:text-amber-400">
                  Add a Brave API key before saving, otherwise web search will
                  fail.
                </p>
              )}
            </div>

            <Separator />

            <div className="flex items-start gap-3 rounded-lg border p-3">
              <input
                id="ai-apply-all"
                type="checkbox"
                checked={aiApplyToAll}
                onChange={(event) => setAiApplyToAll(event.target.checked)}
                className="mt-0.5 h-4 w-4 accent-primary"
              />
              <div>
                <label htmlFor="ai-apply-all" className="text-sm font-medium">
                  Use this model for all accounts
                </label>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  Off by default. When enabled and saved, every Facebook and
                  YouTube account is switched to this model. You will be asked
                  to confirm because existing per-account models are replaced.
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <Button onClick={requestSaveAI} disabled={isSavingAI}>
                {isSavingAI ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Saving…
                  </>
                ) : (
                  <>
                    <Save className="mr-2 h-4 w-4" />
                    Save AI Settings
                  </>
                )}
              </Button>
              {aiApplyToAll && (
                <span className="text-xs text-amber-600 dark:text-amber-400">
                  Saving will overwrite every account&apos;s AI model.
                </span>
              )}
            </div>
          </CardContent>
        </Card>
      )}
        </div>
      </div>

      <AlertDialog open={aiConfirmOpen} onOpenChange={setAiConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Replace the model on every account?</AlertDialogTitle>
            <AlertDialogDescription>
              Saving with “Use this model for all accounts” enabled will set the
              AI model of every Facebook page and YouTube channel to
              <strong> {aiModel || 'the selected model'}</strong>. Any
              account-specific model choices will be replaced. System prompts
              are left untouched.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={saveAISettings}>
              Apply to all accounts
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
