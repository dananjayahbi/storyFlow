"""Script Craft streaming chat, history and agent-tool tests."""

import io
import json
from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import Account, ChatSession, GlobalSettings
from core_engine import ai_client, chat_agent

SESSIONS_URL = '/api/chat/sessions/'

SAMPLE_SCRIPT = {
    'title': 'The Hidden Ocean',
    'segments': [
        {'text_content': 'The sea is deeper than we imagine.', 'image_prompt': 'Cinematic ocean'},
        {'text_content': 'Light dies a hundred meters down.', 'image_prompt': 'Dark water'},
    ],
}


class ChatSessionApiTests(APITestCase):
    def setUp(self):
        GlobalSettings.load()
        self.fb = Account.objects.create(name='Page One', section='facebook')
        self.fb_other = Account.objects.create(name='Page Two', section='facebook')
        self.yt = Account.objects.create(name='Channel One', section='youtube')

    def _url(self, account, suffix=''):
        return f'{SESSIONS_URL}{suffix}?section={account.section}&account={account.id}'

    def test_requires_account(self):
        response = self.client.get(f'{SESSIONS_URL}?section=facebook')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_and_list_are_account_scoped(self):
        created = self.client.post(
            self._url(self.fb), {'title': 'Ocean chat'}, format='json'
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(created.data['title'], 'Ocean chat')

        other = self.client.post(
            self._url(self.fb_other), {'title': 'Other chat'}, format='json'
        )
        self.assertEqual(other.status_code, status.HTTP_201_CREATED)

        listing = self.client.get(self._url(self.fb))
        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [item['title'] for item in listing.data['results']], ['Ocean chat']
        )

    def test_detail_is_account_and_section_scoped(self):
        session = ChatSession.objects.create(
            account=self.fb, section='facebook', title='Private'
        )
        response = self.client.get(
            f'{SESSIONS_URL}{session.id}/?section=youtube&account={self.yt.id}'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_rename_and_delete(self):
        session = ChatSession.objects.create(
            account=self.fb, section='facebook', title='Old'
        )
        renamed = self.client.patch(
            self._url(self.fb, f'{session.id}/'),
            {'title': 'New'},
            format='json',
        )
        self.assertEqual(renamed.status_code, status.HTTP_200_OK)
        self.assertEqual(renamed.data['title'], 'New')

        deleted = self.client.delete(self._url(self.fb, f'{session.id}/'))
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ChatSession.objects.filter(pk=session.pk).exists())

    def test_steer_and_stop_flags(self):
        session = ChatSession.objects.create(
            account=self.fb, section='facebook'
        )
        steer = self.client.post(
            self._url(self.fb, f'{session.id}/steer/'),
            {'message': 'Make it darker'},
            format='json',
        )
        self.assertEqual(steer.status_code, status.HTTP_200_OK)
        session.refresh_from_db()
        self.assertEqual(session.pending_steer, 'Make it darker')

        stop = self.client.post(self._url(self.fb, f'{session.id}/stop/'))
        self.assertEqual(stop.status_code, status.HTTP_200_OK)
        session.refresh_from_db()
        self.assertTrue(session.stop_requested)


class ChatStreamTests(APITestCase):
    def setUp(self):
        GlobalSettings.load()
        self.account = Account.objects.create(name='Writer', section='facebook')
        self.account.ai_model = 'test-model'
        self.account.save(update_fields=['ai_model'])
        self.session = ChatSession.objects.create(
            account=self.account, section='facebook'
        )

    def _url(self, suffix):
        return (
            f'{SESSIONS_URL}{self.session.id}/{suffix}'
            f'?section=facebook&account={self.account.id}'
        )

    def test_stream_requires_configured_model(self):
        self.account.ai_model = ''
        self.account.save(update_fields=['ai_model'])
        response = self.client.post(
            self._url('stream/'), {'message': 'Hello'}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_stream_persists_messages_and_scripts(self):
        def fake_turn(**kwargs):
            yield {'type': 'thinking', 'text': 'Planning the page.'}
            yield {'type': 'token', 'text': 'Writing it now.'}
            script = {
                'id': 'page-1',
                'title': SAMPLE_SCRIPT['title'],
                'pitch': 'ocean',
                'content': SAMPLE_SCRIPT,
                'model': 'test-model',
                'created_at': '2026-01-01T00:00:00+00:00',
                'updated_at': '2026-01-01T00:00:00+00:00',
            }
            yield {'type': 'script', 'action': 'created', 'script': script}
            yield {
                'type': 'message',
                'message': {
                    'id': 'assistant-1',
                    'role': 'assistant',
                    'content': 'Writing it now.',
                    'thinking': 'Planning the page.',
                    'tools': [{'name': 'create_script', 'status': 'completed'}],
                    'created_at': '2026-01-01T00:00:00+00:00',
                },
            }
            yield {'type': 'done', 'stopped': False, 'scripts': [script]}

        with patch('core_engine.chat_agent.run_agent_turn', side_effect=fake_turn):
            response = self.client.post(
                self._url('stream/'),
                {'message': 'Write about the ocean'},
                format='json',
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            body = b''.join(response.streaming_content).decode('utf-8')

        self.assertIn('event: thinking', body)
        self.assertIn('event: token', body)
        self.assertIn('event: script', body)
        self.assertIn('event: done', body)

        self.session.refresh_from_db()
        self.assertEqual(self.session.title, 'Write about the ocean')
        self.assertEqual(len(self.session.scripts), 1)
        roles = [message['role'] for message in self.session.messages]
        self.assertEqual(roles, ['user', 'assistant'])
        self.assertEqual(self.session.messages[0]['content'], 'Write about the ocean')
        self.assertIn('Planning the page.', self.session.messages[1]['thinking'])

    def test_stream_error_event_is_forwarded(self):
        def failing_turn(**kwargs):
            yield {'type': 'error', 'error': 'endpoint down'}

        with patch('core_engine.chat_agent.run_agent_turn', side_effect=failing_turn):
            response = self.client.post(
                self._url('stream/'), {'message': 'Hello'}, format='json'
            )
            body = b''.join(response.streaming_content).decode('utf-8')

        self.assertIn('event: error', body)
        self.assertIn('endpoint down', body)

    def test_compact_summarises_and_marks_cutoff(self):
        self.session.messages = [
            {
                'id': 'm1',
                'role': 'user',
                'content': 'Write an ocean script',
                'created_at': '2026-01-01T00:00:00+00:00',
            },
            {
                'id': 'm2',
                'role': 'assistant',
                'content': 'Done',
                'created_at': '2026-01-01T00:00:01+00:00',
            },
        ]
        self.session.save(update_fields=['messages'])

        with patch(
            'core_engine.ai_client.chat_completion',
            return_value='The user wants an ocean script.',
        ) as mocked:
            response = self.client.post(self._url('compact/'), {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mocked.assert_called_once()
        self.session.refresh_from_db()
        self.assertEqual(self.session.summary, 'The user wants an ocean script.')
        self.assertIsNotNone(self.session.compacted_at)


class ChatAgentToolTests(SimpleTestCase):
    def test_create_script_adds_a_page(self):
        scripts = []
        result = chat_agent.execute_tool(
            'create_script',
            {'title': 'Ocean', 'segments': SAMPLE_SCRIPT['segments']},
            scripts,
            model='test-model',
        )
        self.assertEqual(result['result']['status'], 'created')
        self.assertEqual(len(scripts), 1)
        self.assertEqual(scripts[0]['content']['segments'][0]['text_content'],
                         SAMPLE_SCRIPT['segments'][0]['text_content'])
        self.assertTrue(any(e['type'] == 'script' for e in result['events']))

    def test_rewrite_segment_changes_only_that_block(self):
        scripts = [{
            'id': 'page-1',
            'title': 'Ocean',
            'content': json.loads(json.dumps(SAMPLE_SCRIPT)),
            'updated_at': '',
        }]
        result = chat_agent.execute_tool(
            'rewrite_segment',
            {
                'script_id': 'page-1',
                'segment_index': 2,
                'text_content': 'A new second beat.',
                'image_prompt': 'A new image.',
            },
            scripts,
        )
        self.assertEqual(result['result']['status'], 'rewritten')
        segments = scripts[0]['content']['segments']
        self.assertEqual(segments[0]['text_content'], SAMPLE_SCRIPT['segments'][0]['text_content'])
        self.assertEqual(segments[1]['text_content'], 'A new second beat.')

    def test_read_and_list_expose_every_page(self):
        scripts = [
            {'id': 'a', 'title': 'One', 'content': {'title': 'One', 'segments': [{'text_content': 'x'}]}},
            {'id': 'b', 'title': 'Two', 'content': {'title': 'Two', 'segments': [{'text_content': 'y'}]}},
        ]
        listing = chat_agent.execute_tool('list_scripts', {}, scripts)
        self.assertEqual(len(listing['result']['scripts']), 2)
        read = chat_agent.execute_tool('read_script', {'script_id': 'b'}, scripts)
        self.assertEqual(read['result']['segments'][0]['text_content'], 'y')

    def test_build_messages_includes_selection_context(self):
        messages = chat_agent.build_messages(
            system_prompt='',
            summary='Summary text',
            transcript=[{'role': 'user', 'content': 'Earlier'}],
            scripts=[{'id': 'page-1', 'title': 'Ocean', 'content': SAMPLE_SCRIPT}],
            user_text='Redo this block',
            selection={'script_id': 'page-1', 'segment_index': 2},
        )
        joined = '\n'.join(message['content'] for message in messages if message['role'] == 'system')
        self.assertIn('Summary text', joined)
        self.assertIn('segment 2', joined)
        self.assertEqual(messages[-1]['content'], 'Redo this block')

    def test_run_agent_turn_executes_tool_calls_then_replies(self):
        calls = {'count': 0}

        def fake_stream(**kwargs):
            calls['count'] += 1
            if calls['count'] == 1:
                yield {'type': 'thinking', 'text': 'Let me write.'}
                yield {
                    'type': 'tool_call',
                    'index': 0,
                    'id': 'call_1',
                    'name': 'create_script',
                    'arguments': json.dumps({
                        'title': 'Ocean',
                        'segments': SAMPLE_SCRIPT['segments'],
                    }),
                }
                yield {'type': 'done', 'finish_reason': 'tool_calls'}
            else:
                yield {'type': 'content', 'text': 'Added the ocean page.'}
                yield {'type': 'done', 'finish_reason': 'stop'}

        scripts = []
        with patch('core_engine.ai_client.stream_chat_completion', side_effect=fake_stream):
            events = list(chat_agent.run_agent_turn(
                base_url='http://localhost:11434/v1',
                api_key='',
                model='test-model',
                temperature=0.7,
                system_prompt='',
                summary='',
                transcript=[],
                scripts=scripts,
                user_text='Write about the ocean',
            ))

        self.assertEqual(len(scripts), 1)
        kinds = [event['type'] for event in events]
        self.assertIn('script', kinds)
        self.assertIn('tool', kinds)
        self.assertIn('token', kinds)
        self.assertIn('done', kinds)

    def test_run_agent_turn_keeps_thinking_from_every_round(self):
        calls = {'count': 0}

        def fake_stream(**kwargs):
            calls['count'] += 1
            if calls['count'] == 1:
                yield {'type': 'thinking', 'text': 'First thought. '}
                yield {
                    'type': 'tool_call',
                    'index': 0,
                    'id': 'call_1',
                    'name': 'create_script',
                    'arguments': json.dumps({
                        'title': 'Ocean',
                        'segments': SAMPLE_SCRIPT['segments'],
                    }),
                }
                yield {'type': 'done', 'finish_reason': 'tool_calls'}
            else:
                yield {'type': 'thinking', 'text': 'Second thought.'}
                yield {'type': 'content', 'text': 'Added the ocean page.'}
                yield {'type': 'done', 'finish_reason': 'stop'}

        with patch('core_engine.ai_client.stream_chat_completion', side_effect=fake_stream):
            events = list(chat_agent.run_agent_turn(
                base_url='http://localhost:11434/v1',
                api_key='',
                model='test-model',
                temperature=0.7,
                system_prompt='',
                summary='',
                transcript=[],
                scripts=[],
                user_text='Write about the ocean',
            ))

        final = [
            event['message'] for event in events
            if event['type'] == 'message' and event['message'].get('content')
        ][-1]
        self.assertIn('First thought.', final['thinking'])
        self.assertIn('Second thought.', final['thinking'])

    def test_ask_user_stops_the_turn_with_a_question(self):
        def fake_stream(**kwargs):
            yield {
                'type': 'tool_call',
                'index': 0,
                'id': 'call_q',
                'name': 'ask_user',
                'arguments': json.dumps({
                    'question': 'How long should it be?',
                    'options': ['10 minutes', '20 minutes'],
                }),
            }
            yield {'type': 'done', 'finish_reason': 'tool_calls'}

        with patch('core_engine.ai_client.stream_chat_completion', side_effect=fake_stream):
            events = list(chat_agent.run_agent_turn(
                base_url='http://localhost:11434/v1',
                api_key='',
                model='test-model',
                temperature=0.7,
                system_prompt='',
                summary='',
                transcript=[],
                scripts=[],
                user_text='Make a script',
            ))

        kinds = [event['type'] for event in events]
        self.assertIn('question', kinds)
        done = [event for event in events if event['type'] == 'done'][-1]
        self.assertTrue(done['waiting_for_user'])


class AIStreamingClientTests(SimpleTestCase):
    class FakeResponse:
        def __init__(self, body, content_type='text/event-stream'):
            self._stream = io.BytesIO(body.encode('utf-8'))
            self.headers = {'Content-Type': content_type}

        def readline(self):
            return self._stream.readline()

        def read(self):
            return self._stream.read()

        def close(self):
            pass

    def test_parses_content_thinking_and_tool_deltas(self):
        chunks = [
            'data: {"choices":[{"delta":{"reasoning_content":"Think "}}]}\n\n',
            'data: {"choices":[{"delta":{"content":"Hello "}}]}\n\n',
            'data: {"choices":[{"delta":{"content":"world"}}]}\n\n',
            'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_1",'
            '"function":{"name":"create_script","arguments":"{\\"title\\":\\"X\\"}"}}]}}]}\n\n',
            'data: [DONE]\n\n',
        ]
        fake = self.FakeResponse(''.join(chunks))
        with patch('urllib.request.urlopen', return_value=fake):
            events = list(ai_client.stream_chat_completion(
                base_url='http://localhost:11434/v1',
                api_key='',
                model='test-model',
                messages=[{'role': 'user', 'content': 'hi'}],
            ))

        self.assertEqual(events[0], {'type': 'thinking', 'text': 'Think '})
        self.assertEqual(''.join(e['text'] for e in events if e['type'] == 'content'),
                         'Hello world')
        tool = [e for e in events if e['type'] == 'tool_call'][0]
        self.assertEqual(tool['name'], 'create_script')

    def test_non_streaming_json_response_is_translated(self):
        payload = json.dumps({
            'choices': [{
                'message': {
                    'content': 'Plain reply',
                    'tool_calls': [{
                        'id': 'call_1',
                        'function': {'name': 'list_scripts', 'arguments': '{}'},
                    }],
                },
                'finish_reason': 'stop',
            }]
        })
        fake = self.FakeResponse(payload, content_type='application/json')
        with patch('urllib.request.urlopen', return_value=fake):
            events = list(ai_client.stream_chat_completion(
                base_url='http://localhost:11434/v1',
                api_key='',
                model='test-model',
                messages=[{'role': 'user', 'content': 'hi'}],
            ))

        self.assertIn({'type': 'content', 'text': 'Plain reply'}, events)
        self.assertTrue(any(e['type'] == 'tool_call' for e in events))
