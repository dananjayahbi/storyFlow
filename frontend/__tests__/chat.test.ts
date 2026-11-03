import { parseSSEFrames } from '@/lib/chat';

describe('parseSSEFrames', () => {
  it('parses named events with JSON data', () => {
    const { frames, rest } = parseSSEFrames(
      'event: token\ndata: {"text":"Hello"}\n\n' +
        'event: done\ndata: {"stopped":false}\n\n'
    );

    expect(rest).toBe('');
    expect(frames).toEqual([
      { event: 'token', data: { text: 'Hello' } },
      { event: 'done', data: { stopped: false } },
    ]);
  });

  it('keeps an incomplete frame for the next chunk', () => {
    const first = parseSSEFrames('event: thinking\ndata: {"text":"Plan');
    expect(first.frames).toEqual([]);
    expect(first.rest).toContain('"Plan');

    const second = parseSSEFrames(
      `${first.rest}"}\n\nevent: token\ndata: {"text":"Hi"}\n\n`
    );
    expect(second.frames).toEqual([
      { event: 'thinking', data: { text: 'Plan' } },
      { event: 'token', data: { text: 'Hi' } },
    ]);
  });

  it('handles CRLF frames and ignores malformed JSON', () => {
    const { frames } = parseSSEFrames(
      'event: token\r\ndata: {"text":"ok"}\r\n\r\n' +
        'event: bad\r\ndata: {oops}\r\n\r\n'
    );
    expect(frames).toEqual([{ event: 'token', data: { text: 'ok' } }]);
  });
});
