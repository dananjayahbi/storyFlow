import fs from 'fs';
import path from 'path';

const appRoot = path.join(process.cwd(), 'app');
const componentsRoot = path.join(process.cwd(), 'components');

function routeFiles(root: string): string[] {
  const found: string[] = [];
  const walk = (dir: string) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(full);
      } else if (entry.name === 'page.tsx' || entry.name === 'loading.tsx') {
        found.push(path.relative(root, full).replace(/\\/g, '/'));
      }
    }
  };
  walk(root);
  return found.sort();
}

function componentFiles(root: string): string[] {
  const found: string[] = [];
  const walk = (dir: string) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      if (entry.isDirectory()) {
        if (entry.name === '__tests__') continue;
        walk(path.join(dir, entry.name));
      } else if (entry.name.endsWith('.tsx') || entry.name.endsWith('.ts')) {
        found.push(path.join(dir, entry.name));
      }
    }
  };
  walk(root);
  return found;
}

describe('Facebook / YouTube domain parity', () => {
  it('exposes exactly the same routes on both sides', () => {
    const facebook = routeFiles(path.join(appRoot, 'facebook'));
    const youtube = routeFiles(path.join(appRoot, 'youtube'));
    expect(youtube).toEqual(facebook);
  });

  it('reuses the Facebook implementation for every YouTube page', () => {
    const youtubeRoot = path.join(appRoot, 'youtube');
    for (const route of routeFiles(youtubeRoot)) {
      if (!route.endsWith('page.tsx')) continue;
      const source = fs.readFileSync(path.join(youtubeRoot, route), 'utf8');
      expect({ route, reusesFacebook: source.includes('@/app/facebook') }).toEqual({
        route,
        reusesFacebook: true,
      });
    }
  });

  it('keeps shared components free of hardcoded domain links', () => {
    for (const file of componentFiles(componentsRoot)) {
      const source = fs.readFileSync(file, 'utf8');
      expect({ file, facebookUrl: /\/facebook\//.test(source) }).toEqual({
        file,
        facebookUrl: false,
      });
      expect({ file, youtubeUrl: /\/youtube\//.test(source) }).toEqual({
        file,
        youtubeUrl: false,
      });
    }
  });
});
