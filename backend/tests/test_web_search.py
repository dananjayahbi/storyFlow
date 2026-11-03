"""Web search providers and search-settings tests."""

import json
from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APITestCase

from api.models import Account, GlobalSettings
from core_engine import chat_agent, web_search

AI_SETTINGS_URL = '/api/settings/ai/'

DUCKDUCKGO_HTML = """
<html><body>
<div class="result results_links results_links_deep web-result">
  <div class="links_main links_deep result__body">
    <h2 class="result__title">
      <a rel="nofollow" class="result__a"
         href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Focean&amp;rut=abc">
        The Hidden <b>Ocean</b>
      </a>
    </h2>
    <a class="result__snippet" href="https://example.com/ocean">
      A <b>deep</b> dive into the sea.
    </a>
  </div>
</div>
<div class="result results_links results_links_deep web-result">
  <h2 class="result__title">
    <a rel="nofollow" class="result__a" href="https://example.org/second">
      Second result
    </a>
  </h2>
  <a class="result__snippet" href="https://example.org/second">Another snippet.</a>
</div>
</body></html>
"""


class DuckDuckGoSearchTests(APITestCase):
    def test_parses_titles_urls_and_snippets(self):
        with patch(
            'core_engine.web_search._http_post',
            return_value=(200, DUCKDUCKGO_HTML),
        ) as mocked:
            results = web_search.search_web(
                'hidden ocean', provider='duckduckgo', region='us-en', max_results=5
            )

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['title'], 'The Hidden Ocean')
        self.assertEqual(results[0]['url'], 'https://example.com/ocean')
        self.assertEqual(results[0]['snippet'], 'A deep dive into the sea.')
        self.assertEqual(results[1]['url'], 'https://example.org/second')
        kwargs = mocked.call_args.kwargs
        self.assertEqual(kwargs['data']['q'], 'hidden ocean')
        self.assertEqual(kwargs['data']['kl'], 'us-en')

    def test_blocked_response_raises_a_helpful_error(self):
        with patch('core_engine.web_search._http_post', return_value=(202, '')):
            with self.assertRaises(web_search.SearchError) as raised:
                web_search.search_web('anything')
        self.assertIn('Brave', str(raised.exception))

    def test_empty_query_is_rejected(self):
        with self.assertRaises(web_search.SearchError):
            web_search.search_web('   ')


class BraveSearchTests(APITestCase):
    def test_requires_an_api_key(self):
        with self.assertRaises(web_search.SearchError):
            web_search.search_web('ocean', provider='brave', brave_api_key='')

    def test_parses_brave_results_and_strips_html(self):
        payload = {
            'web': {
                'results': [
                    {
                        'title': 'Ocean facts',
                        'url': 'https://example.com/facts',
                        'description': 'The <strong>deep</strong> sea.',
                    }
                ]
            }
        }
        with patch(
            'core_engine.web_search._http_get',
            return_value=(200, json.dumps(payload)),
        ) as mocked:
            results = web_search.search_web(
                'ocean facts',
                provider='brave',
                brave_api_key='secret',
                region='us-en',
            )

        self.assertEqual(results, [{
            'title': 'Ocean facts',
            'url': 'https://example.com/facts',
            'snippet': 'The deep sea.',
        }])
        headers = mocked.call_args.kwargs['headers']
        self.assertEqual(headers['X-Subscription-Token'], 'secret')
        self.assertIn('country=US', mocked.call_args.args[0])


class WebSearchToolTests(APITestCase):
    def test_tool_returns_results_and_a_chip_label(self):
        with patch(
            'core_engine.web_search.search_web',
            return_value=[{'title': 'A', 'url': 'https://a.test', 'snippet': 'S'}],
        ):
            outcome = chat_agent.execute_tool(
                'web_search',
                {'query': 'ocean facts'},
                [],
                search_config={
                    'enabled': True,
                    'provider': 'duckduckgo',
                    'brave_api_key': '',
                    'region': 'wt-wt',
                },
            )

        self.assertEqual(outcome['result']['results'][0]['title'], 'A')
        self.assertEqual(outcome['events'][0]['type'], 'tool')
        self.assertIn('Searched the web', outcome['events'][0]['label'])

    def test_disabled_search_is_reported_without_network_access(self):
        outcome = chat_agent.execute_tool(
            'web_search',
            {'query': 'ocean'},
            [],
            search_config={'enabled': False},
        )
        self.assertIn('disabled', outcome['result']['error'])


class SearchSettingsTests(APITestCase):
    def setUp(self):
        GlobalSettings.load()
        self.account = Account.objects.create(name='Writer', section='facebook')

    def _url(self):
        return f'{AI_SETTINGS_URL}?section=facebook&account={self.account.id}'

    def test_defaults_to_duckduckgo_enabled(self):
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['search_enabled'])
        self.assertEqual(response.data['search_provider'], 'duckduckgo')
        self.assertEqual(response.data['search_region'], 'wt-wt')

    def test_saves_brave_configuration(self):
        response = self.client.patch(
            self._url(),
            {
                'search_enabled': True,
                'search_provider': 'brave',
                'search_brave_api_key': 'brave-key',
                'search_region': 'gb-en',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['search_provider'], 'brave')
        self.assertEqual(response.data['search_brave_api_key'], 'brave-key')
        self.assertEqual(response.data['search_region'], 'gb-en')

    def test_rejects_unknown_provider(self):
        response = self.client.patch(
            self._url(),
            {'search_provider': 'google'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
