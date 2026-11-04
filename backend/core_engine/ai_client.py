"""OpenAI-compatible chat client used by Script Craft.

StoryFlow is local-first, so this module deliberately has no third-party
dependency.  It talks to any OpenAI-compatible ``/chat/completions`` endpoint
(Ollama, LM Studio, llama.cpp server, vLLM, OpenAI, OpenRouter, ...).  The
endpoint is configured in Settings → AI Model and stored in GlobalSettings;
the model name and system prompt are stored per account.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any

from core_engine.image_prompt_rules import (
    merge_prompt_rules,
    sanitize_image_prompt,
)

DEFAULT_SYSTEM_PROMPT = (
    "You are Script Craft, the staff writer for StoryFlow, a channel that "
    "produces faceless narrative documentary videos. Write in a cinematic, "
    "authoritative documentary voice: vivid, factual, and paced for narration. "
    "Never invent statistics or quote fake sources; if a number is uncertain, "
    "describe it qualitatively. Each segment should be one coherent beat of "
    "the story, roughly 90-170 words, and must include a detailed cinematic "
    "image prompt for a text-to-image model. Keep the same visual style across "
    "the image prompts (lighting, palette, camera language)."
)

SCRIPT_FORMAT_INSTRUCTIONS = """Return ONLY a valid JSON object with this exact shape:

{
  "title": "A concise, compelling video title",
  "segments": [
    {
      "text_content": "Narration for one beat of the story.",
      "image_prompt": "A detailed cinematic image prompt for this beat."
    }
  ]
}

Rules:
- 8 to 16 segments unless the user explicitly asks for a different length.
- Every segment must contain both `text_content` and `image_prompt`.
- No markdown, no code fences, no commentary outside the JSON object.
- image_prompt must contain no text/letter/caption/signage/typography request,
  no split-screen/side-by-side/before-after comparison, and no aspect ratio or
  resolution.
"""


class AIClientError(Exception):
    """Raised when the AI endpoint cannot be reached or returns bad data."""


def _extract_json_object(text: str) -> dict[str, Any]:
    """Extract the first JSON object from an LLM reply."""
    if not text or not text.strip():
        raise AIClientError('The AI model returned an empty response.')

    cleaned = text.strip()
    # Remove ```json ... ``` fences if the model added them.
    fence = re.search(r'```(?:json)?\s*(.*?)```', cleaned, re.DOTALL | re.IGNORECASE)
    if fence:
        cleaned = fence.group(1).strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find('{')
        end = cleaned.rfind('}')
        if start == -1 or end <= start:
            raise AIClientError('The AI model did not return a JSON script.')
        try:
            parsed = json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError as exc:
            raise AIClientError(
                f'The AI model returned malformed JSON: {exc.msg}.'
            ) from exc

    if not isinstance(parsed, dict):
        raise AIClientError('The AI model returned JSON that is not an object.')
    return parsed


def normalize_script(payload: dict[str, Any], fallback_title: str = '') -> dict[str, Any]:
    """Validate and normalise a generated script to StoryFlow's import shape."""
    title = str(payload.get('title') or fallback_title or 'Untitled script').strip()
    raw_segments = payload.get('segments')
    if not isinstance(raw_segments, list) or not raw_segments:
        raise AIClientError('The generated script has no segments.')

    segments: list[dict[str, str]] = []
    for index, raw in enumerate(raw_segments, start=1):
        if isinstance(raw, str):
            text_content, image_prompt = raw, ''
        elif isinstance(raw, dict):
            text_content = (
                raw.get('text_content')
                or raw.get('text')
                or raw.get('narration')
                or ''
            )
            image_prompt = (
                raw.get('image_prompt')
                or raw.get('image')
                or raw.get('prompt')
                or ''
            )
        else:
            continue

        text_content = str(text_content).strip()
        if not text_content:
            continue
        segments.append({
            'text_content': text_content,
            'image_prompt': sanitize_image_prompt(str(image_prompt).strip()),
        })

    if not segments:
        raise AIClientError('The generated script contained no usable segments.')

    return {'title': title, 'segments': segments}


def _completion_url(base_url: str) -> str:
    if not base_url:
        raise AIClientError('No AI base URL configured. Set it in Settings → AI Model.')
    url = base_url.rstrip('/')
    if not url.endswith('/chat/completions'):
        url = f'{url}/chat/completions'
    return url


def _completion_headers(api_key: str) -> dict[str, str]:
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }
    if api_key:
        headers['Authorization'] = f'Bearer {api_key}'
    return headers


def _open_completion(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, Any]],
    temperature: float,
    timeout: int,
    stream: bool,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: str | None = None,
):
    if not model:
        raise AIClientError('No AI model configured. Set it in Settings → AI Model.')

    url = _completion_url(base_url)
    payload: dict[str, Any] = {
        'model': model,
        'messages': messages,
        'temperature': temperature,
        'stream': stream,
    }
    if tools:
        payload['tools'] = tools
        payload['tool_choice'] = tool_choice or 'auto'

    body = json.dumps(payload).encode('utf-8')
    request = urllib.request.Request(
        url,
        data=body,
        headers=_completion_headers(api_key),
        method='POST',
    )
    try:
        return url, urllib.request.urlopen(request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        detail = ''
        try:
            detail = exc.read().decode('utf-8', errors='replace')[:1000]
        except Exception:
            pass
        raise AIClientError(
            f'AI endpoint returned HTTP {exc.code}. {detail}'.strip()
        ) from exc
    except urllib.error.URLError as exc:
        raise AIClientError(
            f'Could not reach the AI endpoint at {url}: {exc.reason}'
        ) from exc


def _message_content(payload: dict[str, Any]) -> str:
    """Extract assistant text from a non-streamed completion payload."""
    try:
        content = payload['choices'][0]['message']['content']
    except (KeyError, IndexError, TypeError) as exc:
        raise AIClientError(
            'The AI endpoint response did not contain a chat completion.'
        ) from exc

    if isinstance(content, list):
        content = ''.join(
            block.get('text', '') if isinstance(block, dict) else str(block)
            for block in content
        )
    return str(content or '')


def chat_completion(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    temperature: float = 0.7,
    timeout: int = 180,
) -> str:
    """POST a chat completion and return the assistant message content."""
    url, response = _open_completion(
        base_url=base_url,
        api_key=api_key,
        model=model,
        messages=messages,
        temperature=temperature,
        timeout=timeout,
        stream=False,
    )
    try:
        payload = json.loads(response.read().decode('utf-8'))
    except (TimeoutError, json.JSONDecodeError) as exc:
        raise AIClientError(f'Invalid response from the AI endpoint: {exc}') from exc
    finally:
        response.close()

    return _message_content(payload)


def _iter_sse_payloads(response):
    """Yield decoded ``data:`` payloads from a server-sent event stream."""
    while True:
        raw_line = response.readline()
        if not raw_line:
            break
        line = raw_line.decode('utf-8', errors='replace').strip()
        if not line or line.startswith(':'):
            continue
        if not line.startswith('data:'):
            continue
        data = line[5:].strip()
        if data == '[DONE]':
            break
        if data:
            yield data


def _yield_full_completion(payload: dict[str, Any]):
    """Translate a non-streamed completion into streaming events."""
    try:
        choice = payload['choices'][0]
    except (KeyError, IndexError, TypeError) as exc:
        raise AIClientError(
            'The AI endpoint response did not contain a chat completion.'
        ) from exc

    message = choice.get('message') or {}
    thinking = (
        message.get('reasoning_content')
        or message.get('reasoning')
        or message.get('thinking')
    )
    if thinking:
        yield {'type': 'thinking', 'text': str(thinking)}

    content = message.get('content')
    if isinstance(content, list):
        content = ''.join(
            block.get('text', '') if isinstance(block, dict) else str(block)
            for block in content
        )
    if content:
        yield {'type': 'content', 'text': str(content)}

    for index, call in enumerate(message.get('tool_calls') or []):
        function = call.get('function') or {}
        yield {
            'type': 'tool_call',
            'index': index,
            'id': call.get('id') or '',
            'name': function.get('name') or '',
            'arguments': function.get('arguments') or '',
        }

    yield {'type': 'done', 'finish_reason': choice.get('finish_reason') or 'stop'}


def stream_chat_completion(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, Any]],
    temperature: float = 0.7,
    timeout: int = 180,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: str | None = None,
):
    """Stream a chat completion as small event dictionaries.

    Yields ``content``/``thinking`` deltas and ``tool_call`` deltas (with
    ``index``, ``id``, ``name`` and a partial ``arguments`` fragment).  Some
    OpenAI-compatible servers ignore ``stream`` and return a single JSON
    object; those responses are translated into the same events.
    """
    url, response = _open_completion(
        base_url=base_url,
        api_key=api_key,
        model=model,
        messages=messages,
        temperature=temperature,
        timeout=timeout,
        stream=True,
        tools=tools,
        tool_choice=tool_choice,
    )

    try:
        content_type = (response.headers.get('Content-Type') or '').lower()
        if 'text/event-stream' not in content_type:
            # The server returned a regular JSON completion.
            raw = response.read().decode('utf-8', errors='replace')
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise AIClientError(
                    f'Invalid response from the AI endpoint: {exc}'
                ) from exc
            yield from _yield_full_completion(payload)
            return

        for data in _iter_sse_payloads(response):
            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                # Providers occasionally send keep-alive pings or partial
                # frames; ignore anything that is not valid JSON.
                continue

            if isinstance(payload.get('error'), dict):
                raise AIClientError(
                    str(payload['error'].get('message') or payload['error'])
                )

            choices = payload.get('choices') or []
            if not choices:
                continue
            choice = choices[0]
            delta = choice.get('delta') or choice.get('message') or {}

            thinking = (
                delta.get('reasoning_content')
                or delta.get('reasoning')
                or delta.get('thinking')
            )
            if thinking:
                yield {'type': 'thinking', 'text': str(thinking)}

            content = delta.get('content')
            if isinstance(content, list):
                content = ''.join(
                    block.get('text', '') if isinstance(block, dict) else str(block)
                    for block in content
                )
            if content:
                yield {'type': 'content', 'text': str(content)}

            for index, call in enumerate(delta.get('tool_calls') or []):
                function = call.get('function') or {}
                yield {
                    'type': 'tool_call',
                    'index': call.get('index', index),
                    'id': call.get('id') or '',
                    'name': function.get('name') or '',
                    'arguments': function.get('arguments') or '',
                }

            if choice.get('finish_reason'):
                yield {
                    'type': 'done',
                    'finish_reason': choice.get('finish_reason'),
                }
    except (TimeoutError, OSError) as exc:
        raise AIClientError(f'Invalid response from the AI endpoint: {exc}') from exc
    finally:
        response.close()


def generate_script(
    *,
    pitch: str,
    history: list[dict[str, str]] | None = None,
    model: str,
    base_url: str,
    api_key: str = '',
    system_prompt: str = '',
    temperature: float = 0.7,
) -> dict[str, Any]:
    """Generate a complete script from a short pitch.

    Returns ``{'script': {...}, 'raw': '<assistant text>', 'model': model}``.
    """
    history = history or []
    system = merge_prompt_rules(
        (system_prompt or '').strip() or DEFAULT_SYSTEM_PROMPT
    )
    messages: list[dict[str, str]] = [
        {'role': 'system', 'content': system},
        {
            'role': 'system',
            'content': SCRIPT_FORMAT_INSTRUCTIONS,
        },
    ]
    for item in history:
        role = item.get('role') if isinstance(item, dict) else None
        content = item.get('content') if isinstance(item, dict) else None
        if role in ('user', 'assistant') and content:
            messages.append({'role': role, 'content': str(content)})

    messages.append({
        'role': 'user',
        'content': (
            'Write the script for this pitch:\n\n'
            f'{pitch.strip()}\n\n'
            'Remember: respond with the JSON object only.'
        ),
    })

    raw = chat_completion(
        base_url=base_url,
        api_key=api_key,
        model=model,
        messages=messages,
        temperature=temperature,
    )
    script = normalize_script(_extract_json_object(raw), fallback_title=pitch[:120])
    return {'script': script, 'raw': raw, 'model': model}
