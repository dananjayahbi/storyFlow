import { readFileSync } from 'fs';
import { join } from 'path';

const FILES = [
  'app/facebook/dashboard/page.tsx',
  'app/facebook/projects/[id]/page.tsx',
];

const MOJIBAKE = /[\u00c2\u00c3\u00e2\u00f0\ufffd]/;

describe('UTF-8 text encoding', () => {
  test.each(FILES)('%s contains no mojibake characters', (relative) => {
    const text = readFileSync(join(__dirname, '..', relative), 'utf8');
    const badLines = text
      .split(/\r?\n/)
      .map((line, index) => ({ line, index: index + 1 }))
      .filter(({ line }) => MOJIBAKE.test(line));

    expect(badLines).toEqual([]);
  });

  test('user-facing project strings use real punctuation', () => {
    const text = readFileSync(
      join(__dirname, '..', 'app/facebook/projects/[id]/page.tsx'),
      'utf8'
    );
    expect(text).toContain('Render complete — ready to download');
    expect(text).toContain('Generating…');
    expect(text).not.toContain('â€”');
  });
});
