"""Metadata management prompts for the YouTube workspace.

The YouTube side can draft a detailed text-to-image prompt for a video
thumbnail from the project's script, selected storyboard images and a few
external references (screenshots, PDFs, notes).  The operator then generates
the actual image manually with that prompt and uploads the chosen result.

This module keeps the prompt contract and the readiness rules out of the API
layer so they can be unit tested without an AI endpoint.  It also contains the
small amount of multimodal plumbing needed by the local OpenAI-compatible
client (base64 image parts and document text extraction).
"""

from __future__ import annotations

import base64
import io
import os
from typing import Any

from core_engine import ai_client

#: Artwork the prompt engineer should follow.  The operator can replace this
#: per project from the Metadata management dialog.
DEFAULT_THUMBNAIL_SYSTEM_PROMPT = """You are a senior YouTube thumbnail art director for a faceless documentary channel. Your job is to write one production-ready text-to-image prompt that a human can paste into an image generator.

Use the supplied script, the selected storyboard images and any external style references to choose ONE pivotal, high-stakes moment that would make a viewer stop scrolling.

Rules:
- Return only the prompt. No introduction, no markdown, no quotation marks, no commentary.
- Describe a single 16:9 landscape composition suitable for a YouTube thumbnail.
- Specify the main subject, expression or action, foreground/background separation, camera angle, lens, lighting, palette, mood and level of detail.
- Keep the visual style consistent with the provided storyboard and reference images.
- Make the subject readable at small sizes: strong silhouette, clear focal point, dramatic contrast.
- Do not request on-image text, captions, logos or watermarks unless the user's message explicitly asks for text.
- Do not mention split screens, side-by-side comparisons, borders or UI elements.
- Do not invent historical details that are absent from the script.
"""

DEFAULT_TITLE_SYSTEM_PROMPT = """You are a YouTube SEO title strategist for a faceless documentary channel. Write the single best upload-ready title for the supplied script.

Rules:
- Return only the title. No introduction, no markdown, no quotation marks, no prefix like "Title:".
- Aim for 60-95 characters; never exceed 100 characters.
- Front-load the primary search keyword or the most concrete subject.
- Create honest curiosity or tension. Never invent facts, numbers or claims that are not in the script.
- Prefer specific nouns and active phrasing over vague hype.
- Do not add hashtags, emoji, channel names or episode numbers unless the user asks.
- Use title case or sentence case consistently and keep it readable at a glance.
"""

DEFAULT_DESCRIPTION_SYSTEM_PROMPT = """You are a YouTube SEO copywriter for a faceless documentary channel. Write one upload-ready video description for the supplied script.

Rules:
- Return only the description. No introduction, no markdown code fences, no prefix like "Description:".
- Open with a strong two-line hook that naturally includes the primary keyword.
- Follow with 2-4 short paragraphs that summarise the story, cover the main search phrases and make the viewer want to watch.
- Include relevant keywords naturally; never keyword-stuff or repeat a phrase unnaturally.
- Do not invent sources, statistics, quotes, dates or claims that are not supported by the script.
- Add a short call to action (subscribe / watch next) only if it fits naturally.
- End with 3-6 relevant hashtags on one line, each starting with #.
- Do not include timestamps unless the user explicitly asks for chapters.
"""

#: Minimum number of reference images (from the storyboard) required before a
#: prompt can be drafted.  The task requires at least two.
MIN_BLOCK_REFERENCE_IMAGES = 2

#: How many storyboard images are selected by default in the UI.
DEFAULT_BLOCK_REFERENCE_IMAGES = 5

#: Character budget for the serialised script and each document.
MAX_SCRIPT_CHARS = 12000
MAX_DOCUMENT_CHARS = 4000

REFERENCE_DOCUMENT_EXTENSIONS = {'.pdf', '.txt', '.md', '.csv', '.json'}


def thumbnail_readiness(project) -> dict[str, Any]:
    """Return the gating state for thumbnail generation.

    The feature unlocks only after the script exists and at least half of the
    project's blocks have an image.  ``required_images`` is inclusive (ceil)
    so a ten-block project needs five images and a nine-block project needs
    five as well.
    """
    segments = list(project.segments.all().order_by('sequence_index'))
    total = len(segments)
    with_text = sum(1 for segment in segments if (segment.text_content or '').strip())
    with_images = sum(1 for segment in segments if segment.image_file)
    required_images = (total + 1) // 2 if total else 0

    script_ready = total > 0 and with_text > 0
    images_ready = required_images > 0 and with_images >= required_images
    return {
        'script_ready': script_ready,
        'images_ready': images_ready,
        'ready': script_ready and images_ready,
        'segment_count': total,
        'text_segment_count': with_text,
        'image_count': with_images,
        'required_images': required_images,
        'min_reference_images': MIN_BLOCK_REFERENCE_IMAGES,
    }


def image_to_data_url(source, max_side: int = 1024) -> str:
    """Return a compact JPEG data URL for a stored or uploaded image.

    Storyboard frames are often 2K-4K renders; re-encoding them keeps the
    multimodal request small enough for local models while preserving the
    composition and colour cues the prompt engineer needs.
    """
    from PIL import Image

    if hasattr(source, 'path'):
        image = Image.open(source.path)
    else:
        source.seek(0)
        image = Image.open(source)

    if image.mode not in ('RGB', 'L'):
        image = image.convert('RGB')
    elif image.mode == 'L':
        image = image.convert('RGB')

    image.thumbnail((max_side, max_side))
    buffer = io.BytesIO()
    image.save(buffer, format='JPEG', quality=85, optimize=True)
    encoded = base64.b64encode(buffer.getvalue()).decode('ascii')
    return f'data:image/jpeg;base64,{encoded}'


def read_reference_document(uploaded_file, limit: int = MAX_DOCUMENT_CHARS) -> str:
    """Extract plain text from an uploaded PDF/TXT/Markdown reference.

    ``pypdf`` is optional: when it is missing a PDF still counts as an
    uploaded reference, but the prompt notes that its text could not be
    extracted instead of failing the whole request.
    """
    name = getattr(uploaded_file, 'name', 'reference')
    extension = os.path.splitext(name)[1].lower()

    if extension == '.pdf':
        try:
            from pypdf import PdfReader
        except ImportError:
            return (
                f'[{name}: PDF text extraction is unavailable in this '
                'installation (install pypdf to include its contents).]'
            )
        try:
            reader = PdfReader(uploaded_file)
            text = '\n'.join(
                (page.extract_text() or '') for page in reader.pages
            )
        except Exception as exc:  # pragma: no cover - corrupt PDFs
            return f'[{name}: could not read PDF ({exc}).]'
        finally:
            try:
                uploaded_file.seek(0)
            except Exception:
                pass
    else:
        raw = uploaded_file.read()
        try:
            uploaded_file.seek(0)
        except Exception:
            pass
        text = raw.decode('utf-8', errors='replace')

    text = text.strip()
    if len(text) > limit:
        text = text[:limit].rstrip() + '\n…'
    return text


def build_script_reference(project, segments) -> str:
    """Serialise the script into a compact reference block."""
    parts = [f'Project title: {project.title}']
    for segment in segments:
        text = (segment.text_content or '').strip()
        prompt = (segment.image_prompt or '').strip()
        parts.append(f'Block {segment.sequence_index + 1}: {text}')
        if prompt:
            parts.append(f'  Visual direction: {prompt}')
    joined = '\n'.join(parts)
    if len(joined) > MAX_SCRIPT_CHARS:
        joined = joined[:MAX_SCRIPT_CHARS].rstrip() + '\n…'
    return joined


def clean_generated_prompt(text: str) -> str:
    """Remove common wrappers an LLM adds around a prompt."""
    cleaned = (text or '').strip()
    if cleaned.startswith('```'):
        lines = cleaned.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip().startswith('```'):
            lines = lines[:-1]
        cleaned = '\n'.join(lines).strip()
    for prefix in (
        'Thumbnail prompt:',
        'Image prompt:',
        'Prompt:',
        'Here is the prompt:',
        'Here’s the prompt:',
        "Here's the prompt:",
    ):
        if cleaned.lower().startswith(prefix.lower()):
            cleaned = cleaned[len(prefix):].strip()
            break
    # Models often wrap the whole answer in matching quotes.
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in ('"', "'"):
        cleaned = cleaned[1:-1].strip()
    return cleaned


def clean_generated_title(text: str) -> str:
    """Normalise a generated title into one clean line."""
    cleaned = (text or '').strip()
    if cleaned.startswith('```'):
        lines = cleaned.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip().startswith('```'):
            lines = lines[:-1]
        cleaned = '\n'.join(lines).strip()

    for line in cleaned.splitlines():
        line = line.strip().lstrip('#').strip()
        if not line:
            continue
        for prefix in ('Title:', 'YouTube title:', 'Upload title:', 'Here is the title:'):
            if line.lower().startswith(prefix.lower()):
                line = line[len(prefix):].strip()
        if len(line) >= 2 and line[0] == line[-1] and line[0] in ('"', "'"):
            line = line[1:-1].strip()
        return ' '.join(line.split())
    return ''


def clean_generated_description(text: str) -> str:
    """Normalise a generated description without destroying its structure."""
    cleaned = (text or '').strip()
    if cleaned.startswith('```'):
        lines = cleaned.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip().startswith('```'):
            lines = lines[:-1]
        cleaned = '\n'.join(lines).strip()

    for prefix in (
        'Description:',
        'YouTube description:',
        'Upload description:',
        'Here is the description:',
        'Here’s the description:',
        "Here's the description:",
    ):
        if cleaned.lower().startswith(prefix.lower()):
            cleaned = cleaned[len(prefix):].strip()
            break
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in ('"', "'"):
        cleaned = cleaned[1:-1].strip()
    # Keep paragraph breaks but never return a wall of blank lines.
    lines = [line.rstrip() for line in cleaned.splitlines()]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    output = []
    blank = False
    for line in lines:
        if line:
            output.append(line)
            blank = False
        elif not blank:
            output.append('')
            blank = True
    return '\n'.join(output).strip()


def _text_metadata_messages(
    *,
    project,
    segments,
    system_prompt: str,
    fallback_system_prompt: str,
    user_message: str,
    task_instruction: str,
    thumbnail_prompt: str = '',
) -> list[dict[str, Any]]:
    """Build the text-only messages shared by title and description drafts."""
    system = (system_prompt or '').strip() or fallback_system_prompt
    sections = [
        f'Working project title: {project.title}',
        'Script reference:\n' + build_script_reference(project, segments),
    ]
    if (thumbnail_prompt or '').strip():
        sections.append(
            'Thumbnail prompt already drafted for this video:\n'
            + thumbnail_prompt.strip()
        )
    instruction = (user_message or '').strip() or task_instruction
    sections.append(instruction)
    return [
        {'role': 'system', 'content': system},
        {'role': 'user', 'content': '\n\n'.join(sections)},
    ]


def generate_title(
    *,
    project,
    segments,
    system_prompt: str = '',
    user_message: str = '',
    thumbnail_prompt: str = '',
    model: str,
    base_url: str,
    api_key: str = '',
    temperature: float = 0.7,
    timeout: int = 180,
) -> dict[str, Any]:
    """Ask the configured LLM for one upload-ready YouTube title."""
    messages = _text_metadata_messages(
        project=project,
        segments=segments,
        system_prompt=system_prompt,
        fallback_system_prompt=DEFAULT_TITLE_SYSTEM_PROMPT,
        user_message=user_message,
        task_instruction=(
            'Write the best upload-ready YouTube title for this video now. '
            'Return only the title.'
        ),
        thumbnail_prompt=thumbnail_prompt,
    )
    raw = ai_client.chat_completion(
        base_url=base_url,
        api_key=api_key,
        model=model,
        messages=messages,
        temperature=temperature,
        timeout=timeout,
    )
    title = clean_generated_title(raw)
    if not title:
        raise ai_client.AIClientError('The AI model returned an empty title.')
    return {'title': title[:255], 'raw': raw, 'model': model}


def generate_description(
    *,
    project,
    segments,
    system_prompt: str = '',
    user_message: str = '',
    thumbnail_prompt: str = '',
    model: str,
    base_url: str,
    api_key: str = '',
    temperature: float = 0.7,
    timeout: int = 240,
) -> dict[str, Any]:
    """Ask the configured LLM for one SEO-finetuned YouTube description."""
    messages = _text_metadata_messages(
        project=project,
        segments=segments,
        system_prompt=system_prompt,
        fallback_system_prompt=DEFAULT_DESCRIPTION_SYSTEM_PROMPT,
        user_message=user_message,
        task_instruction=(
            'Write the upload-ready YouTube description for this video now. '
            'Return only the description.'
        ),
        thumbnail_prompt=thumbnail_prompt,
    )
    raw = ai_client.chat_completion(
        base_url=base_url,
        api_key=api_key,
        model=model,
        messages=messages,
        temperature=temperature,
        timeout=timeout,
    )
    description = clean_generated_description(raw)
    if not description:
        raise ai_client.AIClientError(
            'The AI model returned an empty description.'
        )
    return {'description': description, 'raw': raw, 'model': model}


def build_thumbnail_messages(
    *,
    project,
    segments,
    selected_segments,
    system_prompt: str,
    user_message: str,
    external_images=None,
    documents=None,
) -> list[dict[str, Any]]:
    """Build the multimodal chat messages for a thumbnail prompt draft."""
    system = (system_prompt or '').strip() or DEFAULT_THUMBNAIL_SYSTEM_PROMPT
    external_images = external_images or []
    documents = documents or []

    parts: list[dict[str, Any]] = [
        {
            'type': 'text',
            'text': (
                'Use the following script as the story reference. Choose one '
                'moment that will make the strongest thumbnail.\n\n'
                f'{build_script_reference(project, segments)}'
            ),
        }
    ]

    for segment in selected_segments:
        text = (segment.text_content or '').strip()
        prompt = (segment.image_prompt or '').strip()
        label = (
            f'Storyboard image from block {segment.sequence_index + 1}.'
            + (f'\nNarration: {text[:600]}' if text else '')
            + (f'\nVisual direction: {prompt[:600]}' if prompt else '')
        )
        parts.append({'type': 'text', 'text': label})
        try:
            parts.append({
                'type': 'image_url',
                'image_url': {'url': image_to_data_url(segment.image_file)},
            })
        except Exception:
            parts.append({
                'type': 'text',
                'text': (
                    f'(The image for block {segment.sequence_index + 1} could '
                    'not be read; rely on its text instead.)'
                ),
            })

    for index, uploaded in enumerate(external_images, start=1):
        name = getattr(uploaded, 'name', f'reference-{index}')
        parts.append({
            'type': 'text',
            'text': f'External style reference image {index}: {name}.',
        })
        try:
            parts.append({
                'type': 'image_url',
                'image_url': {'url': image_to_data_url(uploaded)},
            })
        except Exception:
            parts.append({
                'type': 'text',
                'text': f'(External reference {name} could not be read.)',
            })

    document_blocks = []
    for index, uploaded in enumerate(documents, start=1):
        name = getattr(uploaded, 'name', f'document-{index}')
        text = read_reference_document(uploaded)
        if text:
            document_blocks.append(f'--- {name} ---\n{text}')
    if document_blocks:
        parts.append({
            'type': 'text',
            'text': (
                'Additional reference notes supplied by the operator:\n\n'
                + '\n\n'.join(document_blocks)
            ),
        })

    instruction = (user_message or '').strip() or (
        'Create the thumbnail prompt now. Follow the reference images and '
        'the story, and return only the prompt text.'
    )
    parts.append({'type': 'text', 'text': instruction})

    return [
        {'role': 'system', 'content': system},
        {'role': 'user', 'content': parts},
    ]


def generate_thumbnail_prompt(
    *,
    project,
    segments,
    selected_segments,
    system_prompt: str,
    user_message: str,
    external_images=None,
    documents=None,
    model: str,
    base_url: str,
    api_key: str = '',
    temperature: float = 0.7,
    timeout: int = 240,
) -> dict[str, Any]:
    """Ask the configured LLM for a thumbnail prompt and clean the reply."""
    messages = build_thumbnail_messages(
        project=project,
        segments=segments,
        selected_segments=selected_segments,
        system_prompt=system_prompt,
        user_message=user_message,
        external_images=external_images,
        documents=documents,
    )
    raw = ai_client.chat_completion(
        base_url=base_url,
        api_key=api_key,
        model=model,
        messages=messages,
        temperature=temperature,
        timeout=timeout,
    )
    prompt = clean_generated_prompt(raw)
    if not prompt:
        raise ai_client.AIClientError(
            'The AI model returned an empty thumbnail prompt.'
        )
    return {'prompt': prompt, 'raw': raw, 'model': model}
