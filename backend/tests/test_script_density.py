"""Script Craft block-density contract (Feature update #11)."""

from django.test import SimpleTestCase

from core_engine import ai_client, chat_agent


class ScriptDensityTests(SimpleTestCase):
    def test_default_prompts_request_doubled_shorter_blocks(self):
        self.assertIn('20 to 30 segments', ai_client.SCRIPT_FORMAT_INSTRUCTIONS)
        self.assertIn('45-85 words', ai_client.SCRIPT_FORMAT_INSTRUCTIONS)
        self.assertIn('one coherent beat', ai_client.DEFAULT_SYSTEM_PROMPT)
        self.assertIn('45-85 words', ai_client.DEFAULT_SYSTEM_PROMPT)
        self.assertNotIn('8 to 16 segments', ai_client.SCRIPT_FORMAT_INSTRUCTIONS)
        self.assertNotIn('90-170', ai_client.DEFAULT_SYSTEM_PROMPT)

    def test_chat_agent_prompt_and_tool_schema_match(self):
        self.assertIn('20 to 30 segments', chat_agent.AGENT_INSTRUCTIONS)
        self.assertIn('45-85 words', chat_agent.AGENT_INSTRUCTIONS)
        self.assertNotIn('8 to 16 segments', chat_agent.AGENT_INSTRUCTIONS)
        self.assertNotIn('90-170', chat_agent.AGENT_INSTRUCTIONS)

        tools = {
            item['function']['name']: item['function']
            for item in chat_agent.TOOL_DEFINITIONS
        }
        for name in ('create_script', 'update_script'):
            segments = tools[name]['parameters']['properties']['segments']
            self.assertIn('20-30 short blocks', segments['description'])
            text = segments['items']['properties']['text_content']
            self.assertIn('45-85 words', text['description'])

    def test_chat_messages_carry_the_density_rules(self):
        messages = chat_agent.build_messages(
            system_prompt='',
            summary='',
            transcript=[],
            scripts=[],
            user_text='Write a new documentary script.',
        )
        system = messages[0]['content']
        self.assertIn('20 to 30 segments', system)
        self.assertIn('45-85 words', system)
