import { sectionFromPathname, sectionPath, scopedHref } from '@/lib/section';

describe('section helpers', () => {
  it('resolves the youtube section from its URL prefix', () => {
    expect(sectionFromPathname('/youtube')).toBe('youtube');
    expect(sectionFromPathname('/youtube/projects/abc')).toBe('youtube');
  });

  it('defaults every other path to facebook', () => {
    expect(sectionFromPathname('/facebook')).toBe('facebook');
    expect(sectionFromPathname('/facebook/gallery')).toBe('facebook');
    expect(sectionFromPathname('/select')).toBe('facebook');
    expect(sectionFromPathname(undefined)).toBe('facebook');
  });

  it('builds section-scoped paths', () => {
    expect(sectionPath('facebook')).toBe('/facebook');
    expect(sectionPath('youtube', '/projects')).toBe('/youtube/projects');
    expect(sectionPath('youtube', 'projects')).toBe('/youtube/projects');
    expect(sectionPath('facebook', '/')).toBe('/facebook');
  });

  it('prefixes legacy root paths with the active section', () => {
    expect(scopedHref('/youtube/projects', '/projects/123')).toBe(
      '/youtube/projects/123'
    );
    expect(scopedHref('/facebook/gallery', '/settings')).toBe(
      '/facebook/settings'
    );
  });
});
