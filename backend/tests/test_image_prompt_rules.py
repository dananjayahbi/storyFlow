"""Tests for image-prompt rules (Issue #28)."""

from django.test import SimpleTestCase

from api.parsers import JSONParser, TextParser
from core_engine import ai_client, chat_agent
from core_engine.image_prompt_rules import (
    IMAGE_PROMPT_RULES,
    merge_prompt_rules,
    sanitize_image_prompt,
)


class ImagePromptSanitizerTests(SimpleTestCase):
    def test_removes_aspect_ratio_and_resolution(self):
        cleaned = sanitize_image_prompt(
            'A storm over the sea, 16:9 aspect ratio, 1920x1080 resolution, '
            'cinematic lighting.'
        )
        self.assertNotIn('16:9', cleaned)
        self.assertNotIn('1920', cleaned)
        self.assertNotIn('aspect ratio', cleaned.lower())
        self.assertIn('cinematic lighting', cleaned)

    def test_removes_comparison_compositions(self):
        cleaned = sanitize_image_prompt(
            'A split-screen comparison of a city before and after the flood, '
            'side-by-side panels, dramatic sky.'
        )
        lowered = cleaned.lower()
        self.assertNotIn('split-screen', lowered)
        self.assertNotIn('side-by-side', lowered)
        self.assertNotIn('before and after', lowered)
        self.assertNotIn('comparison', lowered)
        self.assertIn('dramatic sky', cleaned)

    def test_removes_text_instructions_and_quotes(self):
        cleaned = sanitize_image_prompt(
            'An astronaut with the words "WE ARE NOT ALONE" on the helmet, '
            'a caption reading MISSION ONE, bold typography, Mars landscape.'
        )
        lowered = cleaned.lower()
        self.assertNotIn('we are not alone', lowered)
        self.assertNotIn('caption', lowered)
        self.assertNotIn('typography', lowered)
        self.assertNotIn('words', lowered)
        self.assertIn('Mars landscape', cleaned)

    def test_removes_negative_text_instructions_too(self):
        cleaned = sanitize_image_prompt(
            'A quiet library with no text and without any captions, warm light.'
        )
        self.assertNotIn('text', cleaned.lower())
        self.assertNotIn('caption', cleaned.lower())
        self.assertIn('warm light', cleaned)

    def test_keeps_ordinary_visual_prompt(self):
        prompt = (
            'A lone lighthouse on a rocky cliff at dusk, cold blue palette, '
            'low camera angle, volumetric fog.'
        )
        self.assertEqual(sanitize_image_prompt(prompt), prompt)

    def test_prompt_rules_are_available_to_every_script_path(self):
        self.assertIn('Never request text', IMAGE_PROMPT_RULES)
        merged = merge_prompt_rules('You are a writer.')
        self.assertIn('You are a writer.', merged)
        self.assertIn('Never request a comparison image', merged)
        self.assertIn('aspect ratio', ai_client.SCRIPT_FORMAT_INSTRUCTIONS)
        self.assertIn('Image prompt rules', chat_agent.AGENT_INSTRUCTIONS)


class ImagePromptNormalizationTests(SimpleTestCase):
    def test_normalize_script_sanitizes_image_prompts(self):
        result = ai_client.normalize_script({
            'title': 'Mars',
            'segments': [{
                'text_content': 'Narration.',
                'image_prompt': (
                    'A rover on Mars, vertical 9:16, with text reading HELLO, '
                    'side by side comparison with Earth.'
                ),
            }],
        })
        prompt = result['segments'][0]['image_prompt']
        self.assertNotIn('9:16', prompt)
        self.assertNotIn('HELLO', prompt)
        self.assertNotIn('side by side', prompt.lower())

    def test_chat_rewrite_sanitizes_image_prompt(self):
        scripts = [{
            'id': 's1',
            'title': 'Chat script',
            'content': {'title': 'Chat script', 'segments': [
                {'text_content': 'Old text', 'image_prompt': 'Old prompt'},
            ]},
        }]
        updated, _events = chat_agent._rewrite_segment(
            scripts,
            {
                'script_id': 's1',
                'segment_index': 1,
                'text_content': 'New text',
                'image_prompt': (
                    'A castle, 4:3, title card reading THE KING, '
                    'before-and-after comparison.'
                ),
            },
        )
        self.assertIsNotNone(updated)
        prompt = updated['content']['segments'][0]['image_prompt']
        self.assertNotIn('4:3', prompt)
        self.assertNotIn('THE KING', prompt)
        self.assertNotIn('before-and-after', prompt.lower())


class ImportParserImagePromptTests(SimpleTestCase):
    def test_json_import_sanitizes_image_prompt(self):
        parsed = JSONParser().parse({
            'title': 'Import',
            'segments': [{
                'text_content': 'Text',
                'image_prompt': 'A map, 16:9, with the words ROUTE 66.',
            }],
        })
        prompt = parsed['segments'][0]['image_prompt']
        self.assertNotIn('16:9', prompt)
        self.assertNotIn('ROUTE 66', prompt)

    def test_text_import_sanitizes_image_prompt(self):
        parsed = TextParser().parse(
            'Import',
            'Text: A line.\nPrompt: A forest, side-by-side comparison, 9:16.\n',
        )
        prompt = parsed['segments'][0]['image_prompt']
        self.assertNotIn('side-by-side', prompt.lower())
        self.assertNotIn('9:16', prompt)
