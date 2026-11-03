"""Web search providers for the Script Craft agent.

DuckDuckGo (HTML endpoint) is the default and needs no configuration.  Brave
Search is optional and only used when the operator selects it and supplies an
API key.  Everything uses Python's standard library so StoryFlow keeps its
dependency-free promise.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from typing import Any

DUCKDUCKGO_URL = 'https://html.duckduckgo.com/html'
BRAVE_URL = 'https://api.search.brave.com/res/v1/web/search'
DEFAULT_REGION = 'wt-wt'
DEFAULT_MAX_RESULTS = 5

USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/124.0.0.0 Safari/537.36'
)


class SearchError(Exception):
    """Raised when the configured search provider cannot be queried."""


class _DuckDuckGoParser(HTMLParser):
    """Extract ``result__a`` / ``result__snippet`` anchors from DDG HTML."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.results: list[dict[str, Any]] = []
        self._current: dict[str, Any] | None = None
        self._capture: str | None = None

    def handle_starttag(self, tag, attrs):
        if tag != 'a':
            return
        attributes = dict(attrs)
        classes = (attributes.get('class') or '').split()
        if 'result__a' in classes:
            self._current = {
                'title': '',
                'url': _clean_duckduckgo_url(attributes.get('href') or ''),
                'snippet': '',
            }
            self._capture = 'title'
        elif 'result__snippet' in classes and self._current is not None:
            self._capture = 'snippet'

    def handle_data(self, data):
        if self._current is not None and self._capture:
            self._current[self._capture] += data

    def handle_endtag(self, tag):
        if tag != 'a' or self._current is None:
            return
        if self._capture == 'title':
            self._capture = None
        elif self._capture == 'snippet':
            self._capture = None
            self._finish_current()

    def close(self):
        super().close()
        self._finish_current()

    def _finish_current(self) -> None:
        if self._current is None:
            return
        result = {
            'title': self._current['title'].strip(),
            'url': self._current['url'],
            'snippet': re.sub(r'\s+', ' ', self._current['snippet']).strip(),
        }
        if result['title'] and result['url']:
            self.results.append(result)
        self._current = None


def _clean_duckduckgo_url(url: str) -> str:
    if url.startswith('//duckduckgo.com/l/?uddg='):
        encoded = url.split('uddg=', 1)[1].split('&', 1)[0]
        return urllib.parse.unquote(encoded)
    if url.startswith('//'):
        return f'https:{url}'
    return url


def _http_get(url: str, *, headers: dict[str, str], timeout: int) -> tuple[int, str]:
    request = urllib.request.Request(url, headers=headers, method='GET')
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode('utf-8', errors='replace')
    except urllib.error.HTTPError as exc:
        detail = ''
        try:
            detail = exc.read().decode('utf-8', errors='replace')[:500]
        except Exception:
            pass
        raise SearchError(
            f'Search provider returned HTTP {exc.code}. {detail}'.strip()
        ) from exc
    except urllib.error.URLError as exc:
        raise SearchError(f'Could not reach the search provider: {exc.reason}') from exc
    except (TimeoutError, OSError) as exc:
        raise SearchError(f'Search request failed: {exc}') from exc


def _http_post(
    url: str, *, data: dict[str, str], headers: dict[str, str], timeout: int
) -> tuple[int, str]:
    body = urllib.parse.urlencode(data).encode('utf-8')
    request = urllib.request.Request(url, data=body, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode('utf-8', errors='replace')
    except urllib.error.HTTPError as exc:
        detail = ''
        try:
            detail = exc.read().decode('utf-8', errors='replace')[:500]
        except Exception:
            pass
        raise SearchError(
            f'Search provider returned HTTP {exc.code}. {detail}'.strip()
        ) from exc
    except urllib.error.URLError as exc:
        raise SearchError(f'Could not reach the search provider: {exc.reason}') from exc
    except (TimeoutError, OSError) as exc:
        raise SearchError(f'Search request failed: {exc}') from exc


def _duckduckgo_search(
    query: str,
    *,
    region: str,
    max_results: int,
    timeout: int,
) -> list[dict[str, Any]]:
    status, html = _http_post(
        DUCKDUCKGO_URL,
        data={'q': query, 'kl': region or DEFAULT_REGION, 'kp': '1'},
        headers={
            'User-Agent': USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Referer': 'https://html.duckduckgo.com/',
        },
        timeout=timeout,
    )
    if status in (202, 403) or not html.strip():
        raise SearchError(
            'DuckDuckGo blocked this search request. Try again, or configure '
            'the optional Brave Search API in Settings → AI Model.'
        )

    parser = _DuckDuckGoParser()
    parser.feed(html)
    parser.close()
    return parser.results[:max_results]


def _brave_search(
    query: str,
    *,
    api_key: str,
    region: str,
    max_results: int,
    timeout: int,
) -> list[dict[str, Any]]:
    if not api_key.strip():
        raise SearchError(
            'Brave Search is selected but no API key is configured. Add one in '
            'Settings → AI Model.'
        )

    # Brave expects a two-letter country code; wt-wt means "no preference".
    country = (region or '').split('-')[0]
    params = {'q': query, 'count': str(max_results)}
    if len(country) == 2:
        params['country'] = country.upper()
    url = f'{BRAVE_URL}?{urllib.parse.urlencode(params)}'

    status, body = _http_get(
        url,
        headers={
            'Accept': 'application/json',
            'X-Subscription-Token': api_key.strip(),
            'User-Agent': 'StoryFlow/1.0',
        },
        timeout=timeout,
    )
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise SearchError('Brave Search returned an invalid response.') from exc

    raw_results = (payload.get('web') or {}).get('results') or []
    results: list[dict[str, Any]] = []
    for item in raw_results:
        title = str(item.get('title') or '').strip()
        link = str(item.get('url') or '').strip()
        description = str(item.get('description') or '')
        description = re.sub(r'<[^>]+>', '', description)
        description = re.sub(r'\s+', ' ', description).strip()
        if title and link:
            results.append({'title': title, 'url': link, 'snippet': description})
    return results[:max_results]


def search_web(
    query: str,
    *,
    provider: str = 'duckduckgo',
    brave_api_key: str = '',
    region: str = DEFAULT_REGION,
    max_results: int = DEFAULT_MAX_RESULTS,
    timeout: int = 20,
) -> list[dict[str, Any]]:
    """Search the web and return ``{title, url, snippet}`` results."""
    query = (query or '').strip()
    if not query:
        raise SearchError('A search query is required.')
    try:
        max_results = int(max_results)
    except (TypeError, ValueError):
        max_results = DEFAULT_MAX_RESULTS
    max_results = max(1, min(max_results, 10))

    if provider == 'brave':
        return _brave_search(
            query,
            api_key=brave_api_key,
            region=region,
            max_results=max_results,
            timeout=timeout,
        )
    if provider == 'duckduckgo':
        return _duckduckgo_search(
            query,
            region=region,
            max_results=max_results,
            timeout=timeout,
        )
    raise SearchError(f'Unknown search provider “{provider}”.')
