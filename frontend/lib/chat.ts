import { ensureApiBaseUrl } from './apiConfig';
import type { ChatSelection } from './types';
import type { Section } from './section';

/** Shape emitted by the Script Craft SSE endpoint. */
export interface ChatStreamEnvelope {
  event: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data: any;
}

export interface StreamChatOptions {
  sessionId: string;
  message: string;
  section: Section;
  accountId: string | null;
  selection?: ChatSelection | null;
  signal?: AbortSignal;
  onEvent: (envelope: ChatStreamEnvelope) => void;
}

/**
 * Split a raw SSE buffer into complete frames.
 *
 * Exported for unit tests; `streamChatSession` uses the same parser.
 */
export function parseSSEFrames(buffer: string): {
  frames: ChatStreamEnvelope[];
  rest: string;
} {
  const normalised = buffer.replace(/\r\n/g, '\n');
  const frames: ChatStreamEnvelope[] = [];
  let rest = normalised;
  let separator = rest.indexOf('\n\n');

  while (separator !== -1) {
    const rawFrame = rest.slice(0, separator);
    rest = rest.slice(separator + 2);
    separator = rest.indexOf('\n\n');

    if (!rawFrame.trim()) continue;
    let event = 'message';
    const dataLines: string[] = [];

    for (const line of rawFrame.split('\n')) {
      if (line.startsWith('event:')) {
        event = line.slice(6).trim();
      } else if (line.startsWith('data:')) {
        dataLines.push(line.slice(5).trimStart());
      }
    }

    const rawData = dataLines.join('\n');
    if (!rawData) continue;
    try {
      frames.push({ event, data: JSON.parse(rawData) });
    } catch {
      // Ignore malformed frames instead of killing the whole stream.
    }
  }

  return { frames, rest };
}

/** Stream one agent turn. Returns when the server closes the stream. */
export async function streamChatSession({
  sessionId,
  message,
  section,
  accountId,
  selection,
  signal,
  onEvent,
}: StreamChatOptions): Promise<void> {
  const base = (await ensureApiBaseUrl()).replace(/\/$/, '');
  const params = new URLSearchParams({ section });
  if (accountId) params.set('account', accountId);

  const response = await fetch(
    `${base}/api/chat/sessions/${sessionId}/stream/?${params.toString()}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        ...(selection ? { selection } : {}),
      }),
      signal,
    }
  );

  if (!response.ok) {
    let detail = `The agent request failed (HTTP ${response.status}).`;
    try {
      const payload = await response.json();
      detail = payload?.error || detail;
    } catch {
      // Keep the generic message.
    }
    throw new Error(detail);
  }

  if (!response.body) {
    throw new Error('Streaming is not supported by this browser.');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const parsed = parseSSEFrames(buffer);
    buffer = parsed.rest;
    for (const frame of parsed.frames) {
      onEvent(frame);
    }
  }

  buffer += decoder.decode();
  const parsed = parseSSEFrames(buffer);
  for (const frame of parsed.frames) {
    onEvent(frame);
  }
}
