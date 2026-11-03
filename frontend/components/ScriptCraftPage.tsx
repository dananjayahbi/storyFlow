'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  AlertTriangle,
  BookMarked,
  BookOpen,
  Brain,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  History,
  Loader2,
  MessageSquare,
  Plus,
  RefreshCw,
  Save,
  Send,
  Sparkles,
  Square,
  Wand2,
} from 'lucide-react';
import { toast } from 'sonner';
import {
  compactChatSession,
  createChatSession,
  getAIConfig,
  getChatSession,
  getChatSessions,
  saveScript,
  steerChatSession,
  stopChatSession,
} from '@/lib/api';
import {
  streamChatSession,
  type ChatStreamEnvelope,
} from '@/lib/chat';
import type {
  AIConfig,
  ChatMessage,
  ChatScriptPage,
  ChatSelection,
  ChatSession,
  ChatToolEvent,
  ScriptContent,
} from '@/lib/types';
import { sectionFromPathname, sectionPath } from '@/lib/section';
import { withAccount } from '@/lib/account';
import { useAccountId } from '@/lib/useAccountId';
import { ScriptViewer } from '@/components/ScriptViewer';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { Textarea } from '@/components/ui/textarea';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  DropdownMenuItem,
} from '@/components/ui/dropdown-menu';
import { cn } from '@/lib/utils';

function errorMessage(err: unknown): string {
  const axiosErr = err as {
    response?: { data?: { error?: string } };
    message?: string;
  };
  return (
    axiosErr?.response?.data?.error ||
    axiosErr?.message ||
    'The AI agent could not complete that request.'
  );
}

function newId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

interface DraftMessage {
  content: string;
  thinking: string;
  tools: ChatToolEvent[];
}

const SLASH_COMMANDS = [
  {
    command: '/compact',
    label: 'Compact session',
    description: 'Summarise earlier turns to free up context.',
  },
  {
    command: '/new',
    label: 'New chat',
    description: 'Start a fresh session with an empty book.',
  },
  {
    command: '/stop',
    label: 'Stop agent',
    description: 'Interrupt the response that is streaming now.',
  },
  {
    command: '/scripts',
    label: 'List book pages',
    description: 'Show every script in this session.',
  },
  {
    command: '/help',
    label: 'Show help',
    description: 'List the available chat commands.',
  },
];

const SESSION_KEY_PREFIX = 'storyflow-scriptcraft-session';

export function ScriptCraftPage() {
  const pathname = usePathname();
  const section = sectionFromPathname(pathname);
  const accountId = useAccountId(section);
  const accountHref = (path: string) =>
    accountId ? withAccount(path, accountId) : path;

  const [session, setSession] = useState<ChatSession | null>(null);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [loadingSession, setLoadingSession] = useState(true);
  const [input, setInput] = useState('');
  const [draft, setDraft] = useState<DraftMessage | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [steeringQueued, setSteeringQueued] = useState(false);
  const [selectedPageId, setSelectedPageId] = useState<string | null>(null);
  const [selectedSegment, setSelectedSegment] = useState<number | null>(null);
  const [savedPages, setSavedPages] = useState<Record<string, boolean>>({});
  const [savingPage, setSavingPage] = useState<string | null>(null);
  const [aiConfig, setAiConfig] = useState<AIConfig | null>(null);

  const chatEndRef = useRef<HTMLDivElement | null>(null);
  const composerRef = useRef<HTMLTextAreaElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const activeSessionRef = useRef<string | null>(null);

  const activeModel = useMemo(
    () => aiConfig?.model || aiConfig?.default_model || '',
    [aiConfig]
  );

  const pages = useMemo(() => session?.scripts ?? [], [session?.scripts]);
  const activePage: ChatScriptPage | null = useMemo(() => {
    if (pages.length === 0) return null;
    return (
      pages.find((page) => page.id === selectedPageId) ||
      pages[pages.length - 1]
    );
  }, [pages, selectedPageId]);

  useEffect(() => {
    getAIConfig()
      .then(setAiConfig)
      .catch(() => setAiConfig(null));
  }, []);

  useEffect(() => {
    activeSessionRef.current = session?.id ?? null;
  }, [session?.id]);

  const refreshSession = useCallback(async (id: string) => {
    try {
      const fresh = await getChatSession(id);
      if (activeSessionRef.current === id) {
        setSession(fresh);
      }
      setSessions((prev) =>
        prev.map((item) => (item.id === id ? fresh : item))
      );
    } catch {
      // The session may have been deleted elsewhere; leave the current view.
    }
  }, []);

  const loadSessionList = useCallback(
    async (preferredId?: string | null) => {
      if (!accountId) return;
      setLoadingSession(true);
      try {
        let list = await getChatSessions();
        let target: ChatSession | null = null;

        if (list.length === 0) {
          target = await createChatSession('');
          list = [target];
        } else {
          const stored =
            preferredId ||
            window.localStorage.getItem(`${SESSION_KEY_PREFIX}-${accountId}`);
          target =
            list.find((item) => item.id === stored) ||
            list[0];
        }

        const detail = await getChatSession(target.id);
        setSessions(list);
        setSession(detail);
        setSelectedPageId(
          detail.scripts.length ? detail.scripts[detail.scripts.length - 1].id : null
        );
        setSelectedSegment(null);
        window.localStorage.setItem(
          `${SESSION_KEY_PREFIX}-${accountId}`,
          detail.id
        );
      } catch (err) {
        toast.error(errorMessage(err));
      } finally {
        setLoadingSession(false);
      }
    },
    [accountId]
  );

  useEffect(() => {
    if (!accountId) return;
    void loadSessionList();
    // `section` changes imply a different account scope as well.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accountId, section]);

  useEffect(() => {
    const node = chatEndRef.current;
    // jsdom (and some embedded browsers) do not implement scrollIntoView.
    if (node && typeof node.scrollIntoView === 'function') {
      node.scrollIntoView({ behavior: 'smooth' });
    }
  }, [session?.messages, draft, streaming]);

  const selectSession = useCallback(
    async (id: string) => {
      if (!accountId || id === session?.id) return;
      if (streaming) {
        abortRef.current?.abort();
        setStreaming(false);
        setDraft(null);
      }
      try {
        const detail = await getChatSession(id);
        setSession(detail);
        setSelectedPageId(
          detail.scripts.length ? detail.scripts[detail.scripts.length - 1].id : null
        );
        setSelectedSegment(null);
        setSteeringQueued(false);
        window.localStorage.setItem(
          `${SESSION_KEY_PREFIX}-${accountId}`,
          detail.id
        );
      } catch (err) {
        toast.error(errorMessage(err));
      }
    },
    [accountId, session?.id, streaming]
  );

  const startNewChat = useCallback(async () => {
    setStreaming(false);
    abortRef.current?.abort();
    setDraft(null);
    try {
      const created = await createChatSession('');
      setSessions((prev) => [created, ...prev]);
      setSession(created);
      setSelectedPageId(null);
      setSelectedSegment(null);
      setSteeringQueued(false);
      setInput('');
      if (accountId) {
        window.localStorage.setItem(
          `${SESSION_KEY_PREFIX}-${accountId}`,
          created.id
        );
      }
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }, [accountId]);

  const applyEvent = useCallback(({ event, data }: ChatStreamEnvelope) => {
    if (event === 'token') {
      setDraft((prev) => ({
        content: (prev?.content || '') + (data?.text || ''),
        thinking: prev?.thinking || '',
        tools: prev?.tools || [],
      }));
      return;
    }

    if (event === 'thinking') {
      setDraft((prev) => ({
        content: prev?.content || '',
        thinking: (prev?.thinking || '') + (data?.text || ''),
        tools: prev?.tools || [],
      }));
      return;
    }

    if (event === 'tool') {
      setDraft((prev) => {
        const current = prev || { content: '', thinking: '', tools: [] };
        const tools = [...current.tools];
        if (data?.status === 'started') {
          tools.push({
            name: data.name || 'tool',
            status: 'started',
            label: data.label,
          });
        } else {
          const existing = tools.findIndex(
            (tool) => tool.name === data?.name && tool.status === 'started'
          );
          const completed = {
            name: data?.name || 'tool',
            status: 'completed',
            label: data?.label,
          };
          if (existing >= 0) tools[existing] = completed;
          else tools.push(completed);
        }
        return { ...current, tools };
      });
      return;
    }

    if (event === 'message') {
      const message = data?.message as ChatMessage | undefined;
      if (!message?.id) return;
      setSession((prev) => {
        if (!prev) return prev;
        if (prev.messages.some((item) => item.id === message.id)) return prev;
        return { ...prev, messages: [...prev.messages, message] };
      });
      setDraft(null);
      return;
    }

    if (event === 'script') {
      const script = data?.script as ChatScriptPage | undefined;
      const list = (data?.scripts as ChatScriptPage[]) || [];
      setSession((prev) => {
        if (!prev) return prev;
        const scripts = list.length ? list : prev.scripts;
        return { ...prev, scripts };
      });
      if (script?.id) {
        if (data?.action === 'created') {
          setSelectedPageId(script.id);
          setSelectedSegment(null);
        }
      }
      return;
    }

    if (event === 'steer') {
      const message = data?.message as ChatMessage | undefined;
      setSteeringQueued(false);
      if (message?.id) {
        setSession((prev) => {
          if (!prev) return prev;
          if (prev.messages.some((item) => item.id === message.id)) return prev;
          return { ...prev, messages: [...prev.messages, message] };
        });
      }
      return;
    }

    if (event === 'error') {
      toast.error(data?.error || 'The agent stream failed.');
      return;
    }
  }, []);

  const runStream = useCallback(
    async (text: string, selection: ChatSelection | null) => {
      if (!session) return;
      const sessionId = session.id;
      const controller = new AbortController();
      abortRef.current = controller;
      setStreaming(true);
      setSteeringQueued(false);
      setDraft({ content: '', thinking: '', tools: [] });

      const optimistic: ChatMessage = {
        id: `local-${newId()}`,
        role: 'user',
        content: text,
        created_at: new Date().toISOString(),
      };
      setSession((prev) =>
        prev ? { ...prev, messages: [...prev.messages, optimistic] } : prev
      );

      try {
        await streamChatSession({
          sessionId,
          message: text,
          section,
          accountId,
          selection,
          signal: controller.signal,
          onEvent: applyEvent,
        });
      } catch (err) {
        if ((err as Error)?.name !== 'AbortError') {
          toast.error(errorMessage(err));
        }
      } finally {
        setStreaming(false);
        setDraft(null);
        abortRef.current = null;
        // The server persists the turn; pull the canonical copy (title,
        // message ids, tool metadata) once the stream is finished.
        await refreshSession(sessionId);
        if (accountId) {
          window.localStorage.setItem(
            `${SESSION_KEY_PREFIX}-${accountId}`,
            sessionId
          );
        }
      }
    },
    [accountId, applyEvent, refreshSession, section, session]
  );

  const sendMessage = useCallback(
    async (raw: string, explicitSelection?: ChatSelection | null) => {
      const text = raw.trim();
      if (!text || !session || streaming) return;

      const selection: ChatSelection | null =
        explicitSelection ??
        (activePage && selectedSegment != null
          ? { script_id: activePage.id, segment_index: selectedSegment + 1 }
          : null);

      setInput('');
      setSelectedSegment(null);
      await runStream(text, selection);
    },
    [activePage, runStream, selectedSegment, session, streaming]
  );

  const handleStop = useCallback(async () => {
    if (!session) return;
    try {
      await stopChatSession(session.id);
    } catch {
      // Aborting the fetch is the fallback.
    }
    abortRef.current?.abort();
    setStreaming(false);
    setDraft(null);
    toast.info('Stopped the agent.');
    // Give the server generator a moment to persist the partial message.
    window.setTimeout(() => {
      void refreshSession(session.id);
    }, 600);
  }, [refreshSession, session]);

  const handleSteer = useCallback(async () => {
    const text = input.trim();
    if (!text || !session) return;
    try {
      await steerChatSession(session.id, text);
      setInput('');
      setSteeringQueued(true);
      toast.success('Steering message sent.');
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }, [input, session]);

  const handleCompact = useCallback(async () => {
    if (!session) return;
    try {
      const result = await compactChatSession(session.id);
      toast.success(
        `Compacted ${result.message_count} message${
          result.message_count === 1 ? '' : 's'
        } into a summary.`
      );
      await refreshSession(session.id);
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }, [refreshSession, session]);

  const runSlashCommand = useCallback(
    async (raw: string) => {
      const [command] = raw.trim().split(/\s+/);
      setInput('');
      if (command === '/compact') {
        await handleCompact();
        return;
      }
      if (command === '/new') {
        await startNewChat();
        return;
      }
      if (command === '/stop') {
        await handleStop();
        return;
      }
      if (command === '/scripts') {
        const list = pages.length
          ? pages
              .map((page, index) => `${index + 1}. ${page.title}`)
              .join('\n')
          : 'The book is empty. Ask me for a new script.';
        setSession((prev) =>
          prev
            ? {
                ...prev,
                messages: [
                  ...prev.messages,
                  {
                    id: `local-${newId()}`,
                    role: 'assistant',
                    content: `Script pages in this session:\n${list}`,
                    created_at: new Date().toISOString(),
                  },
                ],
              }
            : prev
        );
        return;
      }
      if (command === '/help') {
        setSession((prev) =>
          prev
            ? {
                ...prev,
                messages: [
                  ...prev.messages,
                  {
                    id: `local-${newId()}`,
                    role: 'assistant',
                    content: [
                      'Chat commands:',
                      ...SLASH_COMMANDS.map(
                        (item) => `${item.command} — ${item.description}`
                      ),
                      '',
                      'Tip: click a block in the book, then type an instruction to rewrite just that block.',
                    ].join('\n'),
                    created_at: new Date().toISOString(),
                  },
                ],
              }
            : prev
        );
        return;
      }
      await sendMessage(raw);
    },
    [handleCompact, handleStop, pages, sendMessage, startNewChat]
  );

  const handleSubmit = useCallback(async () => {
    if (streaming) {
      await handleSteer();
      return;
    }
    const text = input.trim();
    if (!text) return;
    if (text.startsWith('/')) {
      await runSlashCommand(text);
      return;
    }
    await sendMessage(text);
  }, [handleSteer, input, runSlashCommand, sendMessage, streaming]);

  const handleRewriteSegment = useCallback(
    async (index: number) => {
      if (!activePage) return;
      setSelectedSegment(index);
      await sendMessage(
        `Rewrite segment ${index + 1} with a fresh take. Keep the rest of the script unchanged.`,
        { script_id: activePage.id, segment_index: index + 1 }
      );
    },
    [activePage, sendMessage]
  );

  const handleSavePage = useCallback(
    async (page: ChatScriptPage) => {
      if (savingPage) return;
      setSavingPage(page.id);
      try {
        await saveScript({
          title: page.title,
          pitch: page.pitch,
          content: page.content as ScriptContent,
          model_used: page.model,
        });
        setSavedPages((prev) => ({ ...prev, [page.id]: true }));
        toast.success(`Saved “${page.title}” to the Script Library`);
      } catch (err) {
        toast.error(errorMessage(err));
      } finally {
        setSavingPage(null);
      }
    },
    [savingPage]
  );

  const pageIndex = activePage
    ? pages.findIndex((page) => page.id === activePage.id)
    : -1;

  const commandMatches =
    input.startsWith('/') && !input.includes(' ')
      ? SLASH_COMMANDS.filter((item) => item.command.startsWith(input))
      : [];

  if (!accountId || loadingSession) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center text-sm text-muted-foreground">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        Loading your writer…
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight">
            <Wand2 className="h-6 w-6 text-primary" />
            Script Craft
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Chat with the agent, steer it while it writes, and keep every script
            in this session as pages in the book.
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
          {session?.compacted_at && (
            <Badge variant="secondary" className="gap-1.5">
              <RefreshCw className="h-3 w-3" />
              Compacted
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

      <div className="grid items-start gap-5 lg:grid-cols-[minmax(340px,0.9fr)_minmax(0,1.25fr)]">
        {/* ── Chat column ── */}
        <Card className="lg:sticky lg:top-4">
          <CardHeader className="pb-3">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <CardTitle className="flex items-center gap-2 text-base">
                  <MessageSquare className="h-4 w-4 text-primary" />
                  Chat with your writer
                </CardTitle>
                <CardDescription className="mt-1 truncate">
                  {session?.title || 'New chat'}
                </CardDescription>
              </div>
              <div className="flex shrink-0 items-center gap-1">
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="outline" size="sm">
                      <History className="mr-1.5 h-4 w-4" />
                      History
                      <ChevronDown className="ml-1 h-3.5 w-3.5" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-72">
                    <DropdownMenuLabel>Recent chats</DropdownMenuLabel>
                    <DropdownMenuSeparator />
                    {sessions.length === 0 && (
                      <div className="px-2 py-3 text-xs text-muted-foreground">
                        No chats yet.
                      </div>
                    )}
                    {sessions.map((item) => (
                      <DropdownMenuItem
                        key={item.id}
                        onSelect={() => void selectSession(item.id)}
                        className="flex flex-col items-start gap-0.5"
                      >
                        <span className="flex w-full items-center gap-2">
                          <span className="truncate font-medium">
                            {item.title || 'Untitled chat'}
                          </span>
                          {item.id === session?.id && (
                            <Check className="ml-auto h-3.5 w-3.5 text-primary" />
                          )}
                        </span>
                        <span className="w-full truncate text-xs text-muted-foreground">
                          {item.last_message || `${item.script_count} page(s)`}
                        </span>
                      </DropdownMenuItem>
                    ))}
                  </DropdownMenuContent>
                </DropdownMenu>
                <Button
                  variant="outline"
                  size="icon"
                  className="h-8 w-8"
                  onClick={() => void startNewChat()}
                  title="New chat"
                >
                  <Plus className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="max-h-[52vh] space-y-3 overflow-y-auto pr-1">
              {session?.messages.length === 0 && !draft && (
                <div className="rounded-2xl rounded-bl-sm bg-muted px-3.5 py-2.5 text-sm">
                  Tell me what to write — a pitch, a length, and any style you
                  want. I can ask questions, and you can steer me while I work.
                </div>
              )}

              {session?.messages.map((message) => (
                <ChatBubble key={message.id} message={message} onAnswer={sendMessage} />
              ))}

              {draft && (
                <div className="mr-8 space-y-2 rounded-2xl rounded-bl-sm bg-muted px-3.5 py-2.5 text-sm">
                  {draft.thinking && (
                    <details className="group">
                      <summary className="flex cursor-pointer list-none items-center gap-1.5 text-xs font-medium text-muted-foreground">
                        <Brain className="h-3.5 w-3.5" />
                        Thinking
                        <ChevronDown className="h-3 w-3 transition group-open:rotate-180" />
                      </summary>
                      <p className="mt-2 whitespace-pre-line border-l-2 border-primary/30 pl-3 text-xs italic text-muted-foreground">
                        {draft.thinking}
                      </p>
                    </details>
                  )}
                  {draft.tools.length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                      {draft.tools.map((tool, index) => (
                        <ToolChip key={`${tool.name}-${index}`} tool={tool} />
                      ))}
                    </div>
                  )}
                  {draft.content ? (
                    <p className="whitespace-pre-line">{draft.content}</p>
                  ) : (
                    !draft.thinking && (
                      <span className="flex items-center gap-2 text-muted-foreground">
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Thinking…
                      </span>
                    )
                  )}
                </div>
              )}

              {steeringQueued && (
                <div className="ml-8 rounded-2xl rounded-br-sm border border-dashed px-3.5 py-2 text-xs text-muted-foreground">
                  Steering queued — the agent will apply it after the current
                  chunk.
                </div>
              )}

              <div ref={chatEndRef} />
            </div>

            <Separator />

            <div className="space-y-2">
              {selectedSegment != null && activePage && (
                <div className="flex items-center justify-between gap-2 rounded-md border border-primary/30 bg-primary/5 px-2.5 py-1.5 text-xs">
                  <span>
                    Segment {selectedSegment + 1} of “{activePage.title}” selected
                  </span>
                  <button
                    type="button"
                    className="text-muted-foreground hover:text-foreground"
                    onClick={() => setSelectedSegment(null)}
                  >
                    Clear
                  </button>
                </div>
              )}

              {commandMatches.length > 0 && (
                <div className="overflow-hidden rounded-md border bg-popover shadow-sm">
                  {commandMatches.map((item) => (
                    <button
                      key={item.command}
                      type="button"
                      className="flex w-full flex-col items-start gap-0.5 px-3 py-2 text-left text-xs hover:bg-accent"
                      onClick={() => void runSlashCommand(item.command)}
                    >
                      <span className="font-medium">
                        {item.command}{' '}
                        <span className="text-muted-foreground">
                          — {item.label}
                        </span>
                      </span>
                      <span className="text-muted-foreground">
                        {item.description}
                      </span>
                    </button>
                  ))}
                </div>
              )}

              <Textarea
                ref={composerRef}
                value={input}
                onChange={(event) => setInput(event.target.value)}
                rows={3}
                placeholder={
                  streaming
                    ? 'Steer the agent while it writes…'
                    : 'e.g. A 20-minute documentary script about the hidden dangers of the Amazon River'
                }
                className="resize-none"
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault();
                    void handleSubmit();
                  }
                }}
              />
              <div className="flex items-center justify-between gap-2">
                <span className="text-[11px] text-muted-foreground">
                  Enter to send · Shift + Enter for a new line · “/” for commands
                </span>
                <div className="flex items-center gap-2">
                  {streaming && (
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => void handleStop()}
                    >
                      <Square className="mr-2 h-3.5 w-3.5" />
                      Stop
                    </Button>
                  )}
                  <Button
                    onClick={() => void handleSubmit()}
                    disabled={!input.trim()}
                    size="sm"
                  >
                    {streaming ? (
                      <Sparkles className="mr-2 h-4 w-4" />
                    ) : (
                      <Send className="mr-2 h-4 w-4" />
                    )}
                    {streaming ? 'Steer' : 'Send'}
                  </Button>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* ── Book ── */}
        <Card>
          <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3 space-y-0 pb-3">
            <div>
              <CardTitle className="flex items-center gap-2 text-base">
                <BookOpen className="h-4 w-4 text-primary" />
                Script book
                {pages.length > 0 && (
                  <Badge variant="secondary" className="ml-1">
                    {pages.length} page{pages.length === 1 ? '' : 's'}
                  </Badge>
                )}
              </CardTitle>
              <CardDescription>
                Every script created in this chat lives here. Select a block to
                rewrite it.
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              {pages.length > 1 && (
                <>
                  <Button
                    variant="outline"
                    size="icon"
                    className="h-8 w-8"
                    disabled={pageIndex <= 0}
                    onClick={() =>
                      setSelectedPageId(pages[Math.max(0, pageIndex - 1)]?.id)
                    }
                    title="Previous page"
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </Button>
                  <span className="text-xs text-muted-foreground">
                    {pageIndex + 1} / {pages.length}
                  </span>
                  <Button
                    variant="outline"
                    size="icon"
                    className="h-8 w-8"
                    disabled={pageIndex >= pages.length - 1}
                    onClick={() =>
                      setSelectedPageId(
                        pages[Math.min(pages.length - 1, pageIndex + 1)]?.id
                      )
                    }
                    title="Next page"
                  >
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </>
              )}
              <Button
                size="sm"
                onClick={() => activePage && void handleSavePage(activePage)}
                disabled={!activePage || savingPage === activePage?.id}
              >
                {savingPage === activePage?.id ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Save className="mr-2 h-4 w-4" />
                )}
                {activePage && savedPages[activePage.id]
                  ? 'Saved'
                  : 'Save to Library'}
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {pages.length > 1 && (
              <div className="mb-4 flex gap-1.5 overflow-x-auto pb-1">
                {pages.map((page, index) => (
                  <button
                    key={page.id}
                    type="button"
                    onClick={() => {
                      setSelectedPageId(page.id);
                      setSelectedSegment(null);
                    }}
                    className={cn(
                      'shrink-0 rounded-md border px-2.5 py-1.5 text-xs transition',
                      page.id === activePage?.id
                        ? 'border-primary bg-primary/10 text-primary'
                        : 'text-muted-foreground hover:border-primary/40 hover:text-foreground'
                    )}
                    title={page.title}
                  >
                    <span className="mr-1 font-semibold">{index + 1}.</span>
                    <span className="max-w-[9rem] truncate align-bottom">
                      {page.title}
                    </span>
                  </button>
                ))}
              </div>
            )}

            {activePage ? (
              <ScriptViewer
                script={activePage.content}
                selectable
                selectedIndex={selectedSegment}
                onSelectSegment={(index) =>
                  setSelectedSegment((prev) => (prev === index ? null : index))
                }
                onRewriteSegment={(index) => void handleRewriteSegment(index)}
              />
            ) : (
              <div className="flex flex-col items-center justify-center py-20 text-center text-muted-foreground">
                <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10">
                  <Wand2 className="h-7 w-7 text-primary" />
                </div>
                <p className="text-base font-medium text-foreground">
                  Your book is empty
                </p>
                <p className="mt-1 max-w-sm text-sm">
                  Ask the agent for a script. Every new script becomes another
                  page, and the agent can read all of them when you ask follow-up
                  questions.
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function ToolChip({ tool }: { tool: ChatToolEvent }) {
  const pending = tool.status === 'started';
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px]',
        pending
          ? 'border-primary/30 bg-primary/5 text-primary'
          : 'text-muted-foreground'
      )}
    >
      {pending ? (
        <Loader2 className="h-2.5 w-2.5 animate-spin" />
      ) : (
        <Check className="h-2.5 w-2.5" />
      )}
      {tool.label || tool.name}
    </span>
  );
}

function ChatBubble({
  message,
  onAnswer,
}: {
  message: ChatMessage;
  onAnswer: (answer: string) => void;
}) {
  const isUser = message.role === 'user';

  if (isUser) {
    return (
      <div className="ml-8 rounded-2xl rounded-br-sm bg-primary px-3.5 py-2.5 text-sm text-primary-foreground">
        {message.steering && (
          <span className="mb-1 block text-[10px] font-semibold uppercase tracking-wider opacity-80">
            Steering
          </span>
        )}
        <p className="whitespace-pre-line">{message.content}</p>
      </div>
    );
  }

  return (
    <div className="mr-8 space-y-2 rounded-2xl rounded-bl-sm bg-muted px-3.5 py-2.5 text-sm">
      {message.thinking && (
        <details className="group">
          <summary className="flex cursor-pointer list-none items-center gap-1.5 text-xs font-medium text-muted-foreground">
            <Brain className="h-3.5 w-3.5" />
            Thinking
            <ChevronDown className="h-3 w-3 transition group-open:rotate-180" />
          </summary>
          <p className="mt-2 whitespace-pre-line border-l-2 border-primary/30 pl-3 text-xs italic text-muted-foreground">
            {message.thinking}
          </p>
        </details>
      )}

      {message.tools && message.tools.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {message.tools.map((tool, index) => (
            <ToolChip key={`${tool.name}-${index}`} tool={tool} />
          ))}
        </div>
      )}

      {message.content && (
        <p className="whitespace-pre-line">{message.content}</p>
      )}

      {message.stopped && (
        <p className="text-[11px] uppercase tracking-wider text-muted-foreground">
          Stopped
        </p>
      )}

      {message.question && (
        <div className="space-y-2 rounded-lg border border-primary/30 bg-background p-3">
          <p className="text-xs font-medium text-primary">
            The agent needs your input
          </p>
          {message.options && message.options.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {message.options.map((option) => (
                <Button
                  key={option}
                  size="sm"
                  variant="outline"
                  className="h-7 text-xs"
                  onClick={() => onAnswer(option)}
                >
                  {option}
                </Button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
