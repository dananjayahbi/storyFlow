'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  AlertTriangle,
  BookMarked,
  Loader2,
  MessageSquare,
  RefreshCw,
  Save,
  Send,
  Sparkles,
  Wand2,
} from 'lucide-react';
import { toast } from 'sonner';
import {
  generateScript,
  getAIConfig,
  saveScript,
} from '@/lib/api';
import type {
  AIConfig,
  ScriptChatMessage,
  ScriptContent,
} from '@/lib/types';
import { sectionFromPathname, sectionPath } from '@/lib/section';
import { withAccount } from '@/lib/account';
import { useAccountId } from '@/lib/useAccountId';
import { ScriptViewer } from '@/components/ScriptViewer';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';

function errorMessage(err: unknown): string {
  const axiosErr = err as {
    response?: { data?: { error?: string } };
    message?: string;
  };
  return (
    axiosErr?.response?.data?.error ||
    axiosErr?.message ||
    'The AI model could not generate a script.'
  );
}

export function ScriptCraftPage() {
  const pathname = usePathname();
  const section = sectionFromPathname(pathname);
  const accountId = useAccountId(section);
  const accountHref = (path: string) =>
    accountId ? withAccount(path, accountId) : path;

  const [pitch, setPitch] = useState('');
  const [messages, setMessages] = useState<ScriptChatMessage[]>([
    {
      role: 'assistant',
      content:
        'Tell me what you need — for example: “A documentary video script about World War 2, about 20 minutes long.” I will draft it here and show the script on the right.',
    },
  ]);
  const [script, setScript] = useState<ScriptContent | null>(null);
  const [lastPitch, setLastPitch] = useState('');
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [aiConfig, setAiConfig] = useState<AIConfig | null>(null);
  const [modelUsed, setModelUsed] = useState('');
  const chatEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    getAIConfig()
      .then(setAiConfig)
      .catch(() => setAiConfig(null));
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, generating]);

  const activeModel = useMemo(
    () => aiConfig?.model || aiConfig?.default_model || '',
    [aiConfig]
  );

  const handleGenerate = async () => {
    const value = pitch.trim();
    if (!value || generating) return;

    const history = messages.slice(-12);
    setMessages((prev) => [...prev, { role: 'user', content: value }]);
    setPitch('');
    setGenerating(true);
    setSaved(false);

    try {
      const result = await generateScript(value, history);
      setScript(result.script);
      setLastPitch(value);
      setModelUsed(result.model);
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: result.reply },
      ]);
    } catch (err) {
      const message = errorMessage(err);
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: `I could not write that script: ${message}` },
      ]);
      toast.error(message);
    } finally {
      setGenerating(false);
    }
  };

  const handleSave = async () => {
    if (!script || saving) return;
    setSaving(true);
    try {
      await saveScript({
        title: script.title,
        pitch: lastPitch,
        content: script,
        model_used: modelUsed,
      });
      setSaved(true);
      toast.success('Script saved to the Script Library');
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const startOver = () => {
    setScript(null);
    setSaved(false);
    setLastPitch('');
    setPitch('');
    setMessages([
      {
        role: 'assistant',
        content: 'Fresh page. What should this script be about?',
      },
    ]);
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight">
            <Wand2 className="h-6 w-6 text-primary" />
            Script Craft
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Describe the pitch. The account&apos;s AI agent writes the script,
            ready to save to your library.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {activeModel ? (
            <Badge variant="outline" className="gap-1.5">
              <Sparkles className="h-3 w-3" />
              {activeModel}
            </Badge>
          ) : (
            <Badge variant="outline" className="gap-1.5 text-amber-600">
              <AlertTriangle className="h-3 w-3" />
              No model configured
            </Badge>
          )}
          <Button variant="outline" size="sm" asChild>
            <Link href={accountHref(sectionPath(section, '/script-library'))}>
              <BookMarked className="mr-2 h-4 w-4" />
              Script Library
            </Link>
          </Button>
        </div>
      </div>

      {!activeModel && aiConfig !== null && (
        <div className="flex items-start gap-3 rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-sm">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />
          <div>
            <p className="font-medium">Choose an AI model first</p>
            <p className="mt-1 text-muted-foreground">
              Open{' '}
              <Link
                href={accountHref(sectionPath(section, '/settings'))}
                className="font-medium text-primary underline-offset-4 hover:underline"
              >
                Settings → AI Model
              </Link>{' '}
              to configure the endpoint, model and this account&apos;s system
              prompt.
            </p>
          </div>
        </div>
      )}

      <div className="grid items-start gap-5 lg:grid-cols-[minmax(320px,0.85fr)_minmax(0,1.4fr)]">
        {/* ── Chat ── */}
        <Card className="lg:sticky lg:top-4">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <MessageSquare className="h-4 w-4 text-primary" />
              Chat with your writer
            </CardTitle>
            <CardDescription>
              Brief the agent, refine the idea, then review the draft.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="max-h-[46vh] space-y-3 overflow-y-auto pr-1">
              {messages.map((message, index) => (
                <div
                  key={index}
                  className={
                    message.role === 'user'
                      ? 'ml-8 rounded-2xl rounded-br-sm bg-primary px-3.5 py-2.5 text-sm text-primary-foreground'
                      : 'mr-8 rounded-2xl rounded-bl-sm bg-muted px-3.5 py-2.5 text-sm'
                  }
                >
                  {message.content}
                </div>
              ))}
              {generating && (
                <div className="mr-8 flex items-center gap-2 rounded-2xl rounded-bl-sm bg-muted px-3.5 py-2.5 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Writing the script…
                </div>
              )}
              <div ref={chatEndRef} />
            </div>

            <Separator />

            <div className="space-y-2">
              <Textarea
                value={pitch}
                onChange={(event) => setPitch(event.target.value)}
                rows={4}
                placeholder="e.g. A 20-minute documentary script about the hidden dangers of the Amazon River"
                className="resize-none"
                onKeyDown={(event) => {
                  if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
                    event.preventDefault();
                    handleGenerate();
                  }
                }}
              />
              <div className="flex items-center justify-between gap-2">
                <span className="text-[11px] text-muted-foreground">
                  Ctrl/⌘ + Enter to generate
                </span>
                <Button
                  onClick={handleGenerate}
                  disabled={generating || !pitch.trim()}
                  size="sm"
                >
                  {generating ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Send className="mr-2 h-4 w-4" />
                  )}
                  Generate
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* ── Script output ── */}
        <Card>
          <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3 space-y-0 pb-3">
            <div>
              <CardTitle className="text-base">Script draft</CardTitle>
              <CardDescription>
                Parsed from the agent&apos;s JSON into a readable storyboard.
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              {script && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={startOver}
                  disabled={generating}
                >
                  <RefreshCw className="mr-2 h-4 w-4" />
                  New
                </Button>
              )}
              <Button
                size="sm"
                onClick={handleSave}
                disabled={!script || saving || saved}
              >
                {saving ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Save className="mr-2 h-4 w-4" />
                )}
                {saved ? 'Saved' : 'Save to Library'}
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {script ? (
              <ScriptViewer script={script} />
            ) : (
              <div className="flex flex-col items-center justify-center py-20 text-center text-muted-foreground">
                <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10">
                  <Wand2 className="h-7 w-7 text-primary" />
                </div>
                <p className="text-base font-medium text-foreground">
                  Your script will appear here
                </p>
                <p className="mt-1 max-w-sm text-sm">
                  Send a pitch in the chat. The agent returns structured
                  segments with narration and cinematic image prompts.
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
