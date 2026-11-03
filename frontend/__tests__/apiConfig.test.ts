import {
  DEFAULT_API_BASE_URL,
  apiUrl,
  getApiBaseUrl,
  normalizeApiBaseUrl,
} from '@/lib/apiConfig';

describe('apiConfig', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it('normalizes configured origins', () => {
    expect(normalizeApiBaseUrl(' http://localhost:8000/ ')).toBe(
      'http://localhost:8000'
    );
    expect(normalizeApiBaseUrl('http://localhost:8765///')).toBe(
      'http://localhost:8765'
    );
  });

  it('falls back to the documented development origin', () => {
    expect(normalizeApiBaseUrl('')).toBe(DEFAULT_API_BASE_URL);
    expect(normalizeApiBaseUrl(undefined)).toBe(DEFAULT_API_BASE_URL);
    expect(getApiBaseUrl()).toBe(DEFAULT_API_BASE_URL);
  });

  it('joins API-relative paths and leaves absolute URLs untouched', () => {
    expect(apiUrl('/api/health/')).toBe(`${DEFAULT_API_BASE_URL}/api/health/`);
    expect(apiUrl('api/accounts/')).toBe(`${DEFAULT_API_BASE_URL}/api/accounts/`);
    expect(apiUrl('https://example.com/x')).toBe('https://example.com/x');
  });
});
