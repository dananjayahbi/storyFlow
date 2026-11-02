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
            'image_prompt': str(image_prompt).strip(),
        })

    if not segments:
        raise AIClientError('The generated script contained no usable segments.')

    return {'title': title, 'segments': segments}


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
    if not base_url:
        raise AIClientError('No AI base URL configured. Set it in Settings → AI Model.')
    if not model:
        raise AIClientError('No AI model configured. Set it in Settings → AI Model.')

    url = base_url.rstrip('/')
    if not url.endswith('/chat/completions'):
        url = f'{url}/chat/completions'

    body = json.dumps({
        'model': model,
        'messages': messages,
        'temperature': temperature,
        'stream': False,
    }).encode('utf-8')

    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }
    if api_key:
        headers['Authorization'] = f'Bearer {api_key}'

    request = urllib.request.Request(url, data=body, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode('utf-8'))
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
    except (TimeoutError, json.JSONDecodeError) as exc:
        raise AIClientError(f'Invalid response from the AI endpoint: {exc}') from exc

    try:
        content = payload['choices'][0]['message']['content']
    except (KeyError, IndexError, TypeError) as exc:
        raise AIClientError(
            'The AI endpoint response did not contain a chat completion.'
        ) from exc

    if isinstance(content, list):
        # Some providers return content blocks instead of a plain string.
        content = ''.join(
            block.get('text', '') if isinstance(block, dict) else str(block)
            for block in content
        )
    return str(content)


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
    system = (system_prompt or '').strip() or DEFAULT_SYSTEM_PROMPT
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
