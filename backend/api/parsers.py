import re


class ParseError(Exception):
    """Raised when import data cannot be parsed into the normalized format."""

    def __init__(self, message: str, details: str | None = None):
        self.message = message
        self.details = details
        super().__init__(self.message)


class JSONParser:
    """Parses a JSON import payload into the normalized data format."""

    def parse(self, data: dict) -> dict:
        # 1. Extract and validate title
        title = data.get('title', '').strip()
        if not title:
            raise ParseError("Missing or empty title")

        # 2. Extract and validate segments list
        segments = data.get('segments')
        if not isinstance(segments, list) or len(segments) == 0:
            raise ParseError("Missing or empty segments array")

        # 3. Build normalized segments
        normalized_segments = []
        for i, segment in enumerate(segments):
            if not isinstance(segment, dict):
                raise ParseError(
                    "Invalid segment format",
                    details=f"Segment at index {i} is not an object"
                )

            text_content = segment.get('text_content', '').strip()
            if not text_content:
                raise ParseError(
                    "Missing text_content",
                    details=f"Segment at index {i} is missing text_content"
                )

            image_prompt = segment.get('image_prompt', '')
            if not isinstance(image_prompt, str):
                image_prompt = str(image_prompt)

            normalized_segments.append({
                'text_content': text_content,
                'image_prompt': image_prompt.strip(),
                'sequence_index': i,
            })

        # 4. Return normalized format
        return {
            'title': title,
            'segments': normalized_segments,
        }


class TextParser:
    """Parses a text-based import payload into the normalized data format.

    Text format:
        Text: Narration content for segment 1...
        Prompt: Image description for segment 1...
        ---
        Text: Narration content for segment 2...
        Prompt: Image description for segment 2...
    """

    def parse(self, title: str, raw_text: str) -> dict:
        # 1. Validate title
        title = title.strip() if title else ''
        if not title:
            raise ParseError("Missing or empty title")

        # 2. Validate raw_text
        if not raw_text or not raw_text.strip():
            raise ParseError("Missing or empty raw_text")

        # 3. Split by --- delimiter (three or more hyphens on their own line)
        blocks = re.split(r'\n-{3,}\n', raw_text)

        # 4. Process each block
        normalized_segments = []
        block_number = 0

        for block in blocks:
            block = block.strip()
            if not block:
                continue  # Skip empty blocks

            block_number += 1

            # 5. Extract Text: and Prompt: lines using string operations
            text_lines = []
            prompt_lines = []

            for line in block.split('\n'):
                stripped = line.strip()
                lower = stripped.lower()

                if lower.startswith('text:'):
                    text_lines.append(stripped[5:].strip())
                elif lower.startswith('prompt:'):
                    prompt_lines.append(stripped[7:].strip())
                # Lines not matching Text: or Prompt: are silently ignored

            # 6. Validate: block must have at least one Text: line
            if not text_lines:
                raise ParseError(
                    "Text parsing failed",
                    details=f"Could not parse segment at block {block_number}"
                )

            # 7. Build normalized segment
            text_content = ' '.join(text_lines)  # Concatenate multiple Text: lines
            image_prompt = ' '.join(prompt_lines) if prompt_lines else ''

            if not text_content.strip():
                raise ParseError(
                    "Empty text content",
                    details=f"Block {block_number} has empty Text: value"
                )

            normalized_segments.append({
                'text_content': text_content,
                'image_prompt': image_prompt,
                'sequence_index': len(normalized_segments),  # 0-based
            })

        # 8. Must have at least one parsed segment
        if not normalized_segments:
            raise ParseError("No parseable segments found in text")

        return {
            'title': title,
            'segments': normalized_segments,
        }
