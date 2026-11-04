"""Tool-using, streaming Script Craft agent.

The agent is transport-agnostic: :func:`run_agent_turn` consumes the streaming
events produced by :mod:`core_engine.ai_client` and yields higher-level events
that the Django view forwards to the browser as server-sent events.

Tools let the model:

* ask the human a clarifying question (``ask_user``),
* inspect every script page in the session (``list_scripts``, ``read_script``),
* create a new page (``create_script``),
* replace a whole page (``update_script``),
* rewrite one selected block (``rewrite_segment``).

Everything is standard-library only so StoryFlow stays dependency-free.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Iterator

from core_engine import ai_client
from core_engine.image_prompt_rules import sanitize_image_prompt

AGENT_INSTRUCTIONS = """You are Script Craft, the staff writer and writing partner
inside StoryFlow. You talk to the channel owner in a chat while the scripts you
produce appear as pages in a book on the right side of the screen.

How you work:
- Keep chat replies short and conversational. Never paste a whole script into
  the chat; the script itself belongs to the book panel.
- Use the tools for every script change. Do not print raw JSON unless the user
  explicitly asks to see it.
- `create_script` adds a NEW page to the book. Use it whenever the user asks
  for a new script, even if earlier scripts already exist in this session.
- `update_script` replaces an existing page. `rewrite_segment` replaces exactly
  one block of an existing page.
- `list_scripts` and `read_script` give you access to every page created in
  this session, including pages written earlier in the conversation. Read them
  before editing or when the user refers to an earlier script.
- If you need a decision, a missing fact, or the user's approval, call
  `ask_user`. Never invent facts to avoid asking.
- When the user selects a block and asks for changes, call `rewrite_segment`
  with that script id and segment number.
- If the user steers you while you are answering, follow the new instruction
  immediately and acknowledge it briefly.
- Use `web_search` for current facts, names, dates and statistics you are not
  certain about. Cite the source titles or URLs briefly. If search is disabled
  or fails, say so instead of inventing facts.

Script rules:
- 8 to 16 segments unless the user asks for a different length.
- Every segment needs `text_content` (90-170 words of narration) and
  `image_prompt` (a detailed cinematic text-to-image prompt).
- Keep lighting, palette and camera language consistent across image prompts.
- Give each script a concise, compelling title.

Image prompt rules:
- Describe only visual subjects, lighting, palette and camera language.
- Never request text of any kind: no words, letters, numbers, captions,
  subtitles, title cards, labels, signage with writing, typography, logos or
  watermarks.
- Never request a comparison image: no split-screen, side-by-side, diptych,
  before-and-after, two-panel or "X vs Y" composition. One single scene only.
- Never mention an aspect ratio, frame size, resolution or orientation
  (16:9, 9:16, 4:3, 1:1, vertical, landscape, widescreen, --ar ...).
- Do not quote text that should appear inside the image.
"""

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        'type': 'function',
        'function': {
            'name': 'create_script',
            'description': (
                'Create a new script page in this chat session. Call this '
                'whenever the user asks for a new script. The page appears in '
                'the book on the right.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'title': {'type': 'string'},
                    'pitch': {'type': 'string'},
                    'segments': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'text_content': {'type': 'string'},
                                'image_prompt': {
                                    'type': 'string',
                                    'description': (
                                        'Cinematic visual prompt. No text, '
                                        'captions, typography or signage; no '
                                        'comparison/split-screen composition; '
                                        'no aspect ratio or resolution.'
                                    ),
                                },
                            },
                            'required': ['text_content'],
                        },
                    },
                },
                'required': ['title', 'segments'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'update_script',
            'description': 'Replace the title and/or segments of an existing script page.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'script_id': {'type': 'string'},
                    'title': {'type': 'string'},
                    'segments': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'text_content': {'type': 'string'},
                                'image_prompt': {
                                    'type': 'string',
                                    'description': (
                                        'Cinematic visual prompt. No text, '
                                        'captions, typography or signage; no '
                                        'comparison/split-screen composition; '
                                        'no aspect ratio or resolution.'
                                    ),
                                },
                            },
                            'required': ['text_content'],
                        },
                    },
                },
                'required': ['script_id'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'rewrite_segment',
            'description': (
                'Rewrite exactly one block (segment) of an existing script. '
                'Use this when the user selected a block or asks to redo one '
                'specific part.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'script_id': {'type': 'string'},
                    'segment_index': {
                        'type': 'integer',
                        'description': '1-based segment number.',
                    },
                    'text_content': {'type': 'string'},
                    'image_prompt': {
                        'type': 'string',
                        'description': (
                            'Cinematic visual prompt. No text, captions, '
                            'typography or signage; no comparison/split-screen '
                            'composition; no aspect ratio or resolution.'
                        ),
                    },
                },
                'required': ['script_id', 'segment_index', 'text_content'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'list_scripts',
            'description': 'List every script page in this session with ids and segment counts.',
            'parameters': {'type': 'object', 'properties': {}},
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'read_script',
            'description': 'Read the full content of one script page, including every segment.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'script_id': {'type': 'string'},
                },
                'required': ['script_id'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'web_search',
            'description': (
                'Search the web for current facts, sources, dates, names or '
                'statistics. Use this before making factual claims you are not '
                'certain about. Mention the sources briefly in your reply.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'query': {'type': 'string'},
                    'max_results': {
                        'type': 'integer',
                        'description': 'How many results to read (1-10).',
                    },
                },
                'required': ['query'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'ask_user',
            'description': (
                'Ask the human a clarifying question and wait for the answer. '
                'Use this for choices, missing facts, or approval before a '
                'large rewrite.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'question': {'type': 'string'},
                    'options': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'description': 'Optional quick-reply choices.',
                    },
                },
                'required': ['question'],
            },
        },
    },
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _jsonable(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return str(value)


def _parse_arguments(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _find_script(scripts: list[dict], args: dict) -> dict | None:
    wanted = str(args.get('script_id') or args.get('id') or '').strip()
    if wanted:
        for script in scripts:
            if str(script.get('id')) == wanted:
                return script
        # Accept a page number or title as a fallback.
        try:
            index = int(wanted) - 1
        except (TypeError, ValueError):
            index = -1
        if 0 <= index < len(scripts):
            return scripts[index]
        for script in scripts:
            if str(script.get('title', '')).strip().lower() == wanted.lower():
                return script
    page = args.get('page') or args.get('index')
    if page is not None:
        try:
            index = int(page) - 1
        except (TypeError, ValueError):
            index = -1
        if 0 <= index < len(scripts):
            return scripts[index]
    if scripts:
        return scripts[-1]
    return None


def _script_summary(script: dict) -> dict[str, Any]:
    content = script.get('content') or {}
    return {
        'id': script.get('id'),
        'index': None,  # filled by caller when useful
        'title': content.get('title') or script.get('title') or 'Untitled script',
        'segment_count': len(content.get('segments') or []),
        'updated_at': script.get('updated_at'),
    }


def _script_index(scripts: list[dict]) -> list[dict[str, Any]]:
    index = []
    for position, script in enumerate(scripts, start=1):
        item = _script_summary(script)
        item['index'] = position
        index.append(item)
    return index


def _normalise_script_payload(args: dict[str, Any]) -> dict[str, Any]:
    payload = args.get('script') if isinstance(args.get('script'), dict) else args
    segments = payload.get('segments')
    if isinstance(segments, str):
        try:
            segments = json.loads(segments)
        except json.JSONDecodeError:
            segments = []
    return ai_client.normalize_script(
        {
            'title': payload.get('title') or args.get('title') or '',
            'segments': segments or [],
        },
        fallback_title=str(args.get('pitch') or '')[:120],
    )


def _create_script(
    scripts: list[dict], args: dict[str, Any], model: str
) -> tuple[dict, list[dict]]:
    content = _normalise_script_payload(args)
    now = _now_iso()
    script = {
        'id': uuid.uuid4().hex,
        'title': content['title'],
        'pitch': str(args.get('pitch') or '').strip(),
        'content': content,
        'model': model,
        'created_at': now,
        'updated_at': now,
    }
    scripts.append(script)
    return script, [{'type': 'script', 'action': 'created', 'script': script}]


def _update_script(scripts: list[dict], args: dict[str, Any]) -> tuple[dict | None, list[dict]]:
    script = _find_script(scripts, args)
    if script is None:
        return None, []
    old_content = script.get('content') or {}
    merged = dict(old_content)
    if args.get('title'):
        merged['title'] = str(args['title']).strip()
    if args.get('segments') is not None:
        content = _normalise_script_payload(args)
        merged['title'] = content['title'] or merged.get('title')
        merged['segments'] = content['segments']
    script['content'] = merged
    script['title'] = merged.get('title') or script.get('title') or 'Untitled script'
    script['updated_at'] = _now_iso()
    return script, [{'type': 'script', 'action': 'updated', 'script': script}]


def _rewrite_segment(scripts: list[dict], args: dict[str, Any]) -> tuple[dict | None, list[dict]]:
    script = _find_script(scripts, args)
    if script is None:
        return None, []
    content = script.get('content') or {}
    segments = list(content.get('segments') or [])
    try:
        index = int(args.get('segment_index') or args.get('index') or 0) - 1
    except (TypeError, ValueError):
        index = -1
    if not (0 <= index < len(segments)):
        return None, []

    old = segments[index] if isinstance(segments[index], dict) else {}
    text_content = str(args.get('text_content') or '').strip()
    if not text_content:
        return None, []
    segments[index] = {
        'text_content': text_content,
        'image_prompt': sanitize_image_prompt(
            str(args.get('image_prompt', old.get('image_prompt', ''))).strip()
        ),
    }
    content['segments'] = segments
    script['content'] = content
    script['updated_at'] = _now_iso()
    return script, [
        {
            'type': 'script',
            'action': 'rewritten',
            'script': script,
            'segment_index': index + 1,
        }
    ]


def execute_tool(
    name: str,
    args: dict[str, Any],
    scripts: list[dict],
    *,
    model: str = '',
    search_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute one agent tool and return result, events and stop flag."""

    if name == 'web_search':
        query = str(args.get('query') or '').strip()
        if not query:
            return {
                'result': {'error': 'A search query is required.'},
                'events': [],
                'stop': False,
            }
        config = search_config or {}
        if not config.get('enabled', True):
            return {
                'result': {
                    'error': (
                        'Web search is disabled. Enable it in Settings → AI Model.'
                    )
                },
                'events': [],
                'stop': False,
            }

        try:
            from core_engine import web_search

            results = web_search.search_web(
                query,
                provider=str(config.get('provider') or 'duckduckgo'),
                brave_api_key=str(config.get('brave_api_key') or ''),
                region=str(config.get('region') or 'wt-wt'),
                max_results=int(args.get('max_results') or 5),
            )
        except Exception as exc:
            return {
                'result': {'error': str(exc) or 'The web search failed.'},
                'events': [{
                    'type': 'tool',
                    'name': name,
                    'status': 'completed',
                    'label': f'Web search failed: {str(exc)[:80]}',
                }],
                'stop': False,
            }

        return {
            'result': {'query': query, 'results': results},
            'events': [{
                'type': 'tool',
                'name': name,
                'status': 'completed',
                'label': f'Searched the web for “{query[:60]}”',
            }],
            'stop': False,
        }

    if name == 'ask_user':
        question = str(args.get('question') or '').strip()
        options = args.get('options') if isinstance(args.get('options'), list) else []
        options = [str(option)[:120] for option in options[:6]]
        message = {
            'id': uuid.uuid4().hex,
            'role': 'assistant',
            'content': question or 'Could you tell me a little more?',
            'thinking': '',
            'tools': [],
            'question': question or 'Could you tell me a little more?',
            'options': options,
            'stopped': False,
            'created_at': _now_iso(),
        }
        return {
            'result': {'status': 'waiting_for_user'},
            'events': [
                {'type': 'tool', 'name': name, 'status': 'completed', 'label': 'Asked you a question'},
                {'type': 'message', 'message': message},
                {
                    'type': 'question',
                    'question': message['question'],
                    'options': options,
                    'message': message,
                },
            ],
            'stop': True,
        }

    if name == 'list_scripts':
        return {
            'result': {'scripts': _script_index(scripts)},
            'events': [{
                'type': 'tool',
                'name': name,
                'status': 'completed',
                'label': f'Read the book index ({len(scripts)} page{"s" if len(scripts) != 1 else ""})',
            }],
            'stop': False,
        }

    if name == 'read_script':
        script = _find_script(scripts, args)
        if script is None:
            return {
                'result': {'error': 'No matching script page.'},
                'events': [],
                'stop': False,
            }
        content = script.get('content') or {}
        return {
            'result': {
                'id': script.get('id'),
                'title': content.get('title') or script.get('title'),
                'segments': content.get('segments') or [],
            },
            'events': [{
                'type': 'tool',
                'name': name,
                'status': 'completed',
                'label': f'Read “{content.get("title") or script.get("title") or "script"}”',
            }],
            'stop': False,
        }

    if name == 'create_script':
        script, events = _create_script(scripts, args, model)
        summary = _script_summary(script)
        summary['index'] = len(scripts)
        return {
            'result': {
                'status': 'created',
                'script': summary,
                'message': 'The new page is now visible to the user.',
            },
            'events': [{
                'type': 'tool',
                'name': name,
                'status': 'completed',
                'label': f'Wrote page {len(scripts)}: “{summary["title"]}”',
            }, *events],
            'stop': False,
        }

    if name == 'update_script':
        script, events = _update_script(scripts, args)
        if script is None:
            return {
                'result': {'error': 'No matching script page.'},
                'events': [],
                'stop': False,
            }
        return {
            'result': {
                'status': 'updated',
                'script': _script_summary(script),
            },
            'events': [{
                'type': 'tool',
                'name': name,
                'status': 'completed',
                'label': f'Updated “{script.get("title") or "script"}”',
            }, *events],
            'stop': False,
        }

    if name == 'rewrite_segment':
        script, events = _rewrite_segment(scripts, args)
        if script is None:
            return {
                'result': {'error': 'That page or segment number does not exist.'},
                'events': [],
                'stop': False,
            }
        segment_index = events[0].get('segment_index')
        return {
            'result': {
                'status': 'rewritten',
                'script': _script_summary(script),
                'segment_index': segment_index,
            },
            'events': [{
                'type': 'tool',
                'name': name,
                'status': 'completed',
                'label': f'Rewrote segment {segment_index}',
            }, *events],
            'stop': False,
        }

    return {
        'result': {'error': f'Unknown tool “{name}”.'},
        'events': [],
        'stop': False,
    }


def build_messages(
    *,
    system_prompt: str,
    summary: str,
    transcript: list[dict],
    scripts: list[dict],
    user_text: str,
    selection: dict | None = None,
) -> list[dict[str, Any]]:
    """Build the OpenAI message list for one turn."""
    base = (system_prompt or '').strip() or ai_client.DEFAULT_SYSTEM_PROMPT
    messages: list[dict[str, Any]] = [
        {'role': 'system', 'content': f'{base}\n\n{AGENT_INSTRUCTIONS}'},
    ]

    if summary:
        messages.append({
            'role': 'system',
            'content': (
                'Summary of the earlier conversation (already compacted):\n'
                f'{summary}'
            ),
        })

    if scripts:
        index_lines = [
            f'{item["index"]}. id={item["id"]} — {item["title"]} '
            f'({item["segment_count"]} segments)'
            for item in _script_index(scripts)
        ]
        messages.append({
            'role': 'system',
            'content': (
                'Script pages currently in this session\'s book:\n'
                + '\n'.join(index_lines)
                + '\nUse read_script to read any page before editing it.'
            ),
        })

    for item in transcript[-40:]:
        role = item.get('role')
        content = str(item.get('content') or '').strip()
        if role in ('user', 'assistant') and content:
            messages.append({'role': role, 'content': content})

    if selection:
        try:
            segment_index = int(selection.get('segment_index') or 0)
        except (TypeError, ValueError):
            segment_index = 0
        script_id = str(selection.get('script_id') or '')
        if segment_index > 0 and script_id:
            script = _find_script(scripts, {'script_id': script_id})
            title = (script or {}).get('title') or 'script'
            messages.append({
                'role': 'system',
                'content': (
                    f'The user selected segment {segment_index} of “{title}” '
                    f'(script_id={script_id}). If the request is about that '
                    'block, call rewrite_segment with that script_id and '
                    'segment_index. Keep the rest of the script unchanged.'
                ),
            })

    messages.append({'role': 'user', 'content': user_text})
    return messages


def _try_local_tool_fallback(
    content: str,
    scripts: list[dict],
    model: str,
    search_config: dict[str, Any] | None = None,
):
    """Handle models without native tool support.

    Some local models ignore the tools parameter and print a JSON object.  If
    it looks like a script, create the page for them; if it looks like a tool
    call, execute it.
    """
    try:
        payload = ai_client._extract_json_object(content)
    except ai_client.AIClientError:
        return None

    if isinstance(payload.get('segments'), list):
        fake_args = {
            'title': payload.get('title') or '',
            'segments': payload.get('segments'),
        }
        return execute_tool(
            'create_script',
            fake_args,
            scripts,
            model=model,
            search_config=search_config,
        )

    if isinstance(payload.get('name'), str):
        args = payload.get('arguments') or payload.get('args') or {}
        if isinstance(args, str):
            args = _parse_arguments(args)
        return execute_tool(
            str(payload['name']),
            args,
            scripts,
            model=model,
            search_config=search_config,
        )

    return None


def _poll_interval() -> float:
    # A DB read every 0.6 s is cheap on SQLite and keeps the stop/steer
    # latency well under a second.
    return 0.6


def run_agent_turn(
    *,
    base_url: str,
    api_key: str,
    model: str,
    temperature: float,
    system_prompt: str,
    summary: str,
    transcript: list[dict],
    scripts: list[dict],
    user_text: str,
    selection: dict | None = None,
    search_config: dict[str, Any] | None = None,
    should_stop: Callable[[], bool] | None = None,
    take_steer: Callable[[], str | None] | None = None,
    max_tool_rounds: int = 8,
) -> Iterator[dict[str, Any]]:
    """Run one chat turn, yielding UI-friendly streaming events."""
    messages = build_messages(
        system_prompt=system_prompt,
        summary=summary,
        transcript=transcript,
        scripts=scripts,
        user_text=user_text,
        selection=selection,
    )

    all_tools: list[dict[str, Any]] = []
    all_thinking_parts: list[str] = []

    for round_index in range(max_tool_rounds):
        content_parts: list[str] = []
        thinking_parts: list[str] = []
        tool_calls: dict[int, dict[str, str]] = {}
        steer_text: str | None = None
        stopped = False
        last_poll = time.monotonic()

        try:
            stream = ai_client.stream_chat_completion(
                base_url=base_url,
                api_key=api_key,
                model=model,
                messages=messages,
                temperature=temperature,
                tools=TOOL_DEFINITIONS,
            )
            for delta in stream:
                now = time.monotonic()
                if now - last_poll >= _poll_interval():
                    last_poll = now
                    if should_stop and should_stop():
                        stopped = True
                        break
                    if take_steer and steer_text is None:
                        steer_text = take_steer()

                delta_type = delta.get('type')
                if delta_type == 'thinking':
                    text = delta.get('text') or ''
                    thinking_parts.append(text)
                    yield {'type': 'thinking', 'text': text}
                elif delta_type == 'content':
                    text = delta.get('text') or ''
                    content_parts.append(text)
                    yield {'type': 'token', 'text': text}
                elif delta_type == 'tool_call':
                    index = int(delta.get('index') or 0)
                    entry = tool_calls.setdefault(
                        index, {'id': '', 'name': '', 'arguments': ''}
                    )
                    if delta.get('id'):
                        entry['id'] = str(delta['id'])
                    if delta.get('name'):
                        if not entry['name'] or delta['name'] not in entry['name']:
                            entry['name'] += str(delta['name'])
                    if delta.get('arguments'):
                        entry['arguments'] += str(delta['arguments'])
        except ai_client.AIClientError as exc:
            yield {'type': 'error', 'error': str(exc)}
            return

        content = ''.join(content_parts)
        thinking = ''.join(thinking_parts)
        if thinking:
            all_thinking_parts.append(thinking)

        if stopped:
            yield {
                'type': 'message',
                'message': _assistant_message(
                    content, ''.join(all_thinking_parts), tools=all_tools,
                    stopped=True,
                ),
            }
            yield {'type': 'done', 'stopped': True}
            return

        if tool_calls:
            calls = []
            for index in sorted(tool_calls):
                entry = tool_calls[index]
                calls.append({
                    'id': entry['id'] or f'call_{round_index}_{index}',
                    'name': entry['name'].strip(),
                    'arguments': entry['arguments'],
                })

            assistant_tool_message = {
                'role': 'assistant',
                'content': content,
                'tool_calls': [
                    {
                        'id': call['id'],
                        'type': 'function',
                        'function': {
                            'name': call['name'],
                            'arguments': call['arguments'] or '{}',
                        },
                    }
                    for call in calls
                ],
            }
            messages.append(assistant_tool_message)

            tool_notes: list[dict[str, Any]] = []
            question_message: dict | None = None
            for call in calls:
                args = _parse_arguments(call['arguments'])
                yield {
                    'type': 'tool',
                    'name': call['name'],
                    'status': 'started',
                    'label': _tool_start_label(call['name'], args),
                }
                outcome = execute_tool(
                    call['name'],
                    args,
                    scripts,
                    model=model,
                    search_config=search_config,
                )
                for event in outcome['events']:
                    if event.get('type') == 'message':
                        event['message']['tools'] = list(all_tools)
                        question_message = event['message']
                    yield event
                    if event.get('type') == 'tool':
                        note = {
                            'name': event.get('name'),
                            'status': event.get('status'),
                            'label': event.get('label'),
                        }
                        tool_notes.append(note)
                        all_tools.append(note)
                    if event.get('type') == 'question':
                        # The question message already carries the text.
                        question_message = event.get('message')
                messages.append({
                    'role': 'tool',
                    'tool_call_id': call['id'],
                    'content': json.dumps(_jsonable(outcome['result'])),
                })
                if outcome['stop']:
                    if question_message is not None:
                        yield question_message_event(question_message)
                    yield {'type': 'done', 'stopped': False, 'waiting_for_user': True}
                    return

            if content.strip():
                # Keep a short preamble visible in the chat.
                message = _assistant_message(content, thinking, tools=tool_notes)
                yield {'type': 'message', 'message': message}

            if steer_text:
                yield {'type': 'steer', 'text': steer_text, 'created_at': _now_iso()}
                messages.append({'role': 'user', 'content': steer_text})
                steer_note = {
                    'name': 'steer',
                    'status': 'completed',
                    'label': 'Applied your steering update',
                }
                all_tools.append(steer_note)
                yield {'type': 'tool', **steer_note}

            # Loop again so the model can summarise the tool result.
            continue

        # No tool call: try a text fallback for models without tool support.
        fallback = _try_local_tool_fallback(
            content, scripts, model, search_config
        )
        if fallback is not None:
            for event in fallback['events']:
                yield event
            clean = _fallback_ack(content)
            message = _assistant_message(
                clean, ''.join(all_thinking_parts), tools=all_tools
            )
            yield {'type': 'message', 'message': message}
            if fallback.get('stop'):
                yield {'type': 'done', 'stopped': False, 'waiting_for_user': True}
                return
            yield {'type': 'done', 'stopped': False}
            return

        message = _assistant_message(
            content, ''.join(all_thinking_parts), tools=all_tools
        )
        yield {'type': 'message', 'message': message}

        if steer_text:
            yield {'type': 'steer', 'text': steer_text, 'created_at': _now_iso()}
            messages.append({'role': 'assistant', 'content': content})
            messages.append({'role': 'user', 'content': steer_text})
            continue

        if not content.strip() and not thinking.strip():
            # Some providers return an empty final chunk; avoid an empty bubble.
            yield {'type': 'done', 'stopped': False}
            return

        yield {'type': 'done', 'stopped': False}
        return

    yield {
        'type': 'message',
        'message': _assistant_message(
            'I reached the tool-call limit for one turn. Ask me to continue '
            'and I will pick up from here.',
            '',
            tools=[],
        ),
    }
    yield {'type': 'done', 'stopped': False}


def question_message_event(message: dict) -> dict[str, Any]:
    return {
        'type': 'question',
        'question': message.get('question') or message.get('content'),
        'options': message.get('options') or [],
        'message': message,
    }


def _fallback_ack(content: str) -> str:
    if content.strip() and not content.strip().startswith('{'):
        return content.strip()
    return 'I added that script to the book.'


def _assistant_message(
    content: str,
    thinking: str,
    *,
    tools: list[dict] | None = None,
    stopped: bool = False,
) -> dict[str, Any]:
    return {
        'id': uuid.uuid4().hex,
        'role': 'assistant',
        'content': content,
        'thinking': thinking,
        'tools': tools or [],
        'stopped': stopped,
        'created_at': _now_iso(),
    }


def _tool_start_label(name: str, args: dict) -> str:
    labels = {
        'create_script': 'Writing a new script page',
        'update_script': 'Updating a script page',
        'rewrite_segment': 'Rewriting a segment',
        'list_scripts': 'Checking the book',
        'read_script': 'Reading a script page',
        'web_search': 'Searching the web',
        'ask_user': 'Thinking of a question',
    }
    return labels.get(name, f'Running {name}')
