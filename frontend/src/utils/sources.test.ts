import { describe, it, expect } from 'vitest';
import { extractSourceUrls } from './sources';

describe('extractSourceUrls', () => {
  it('returns empty array for empty/null/undefined input', () => {
    expect(extractSourceUrls('')).toEqual([]);
    expect(extractSourceUrls(null)).toEqual([]);
    expect(extractSourceUrls(undefined)).toEqual([]);
  });

  it('extracts Source: prefixed URLs (search prompt format)', () => {
    const text = 'Some summary.\n\nSources:\nSource: https://example.com/a\nSource: https://example.com/b';
    const urls = extractSourceUrls(text).map(c => c.url);
    expect(urls).toEqual(['https://example.com/a', 'https://example.com/b']);
  });

  it('extracts bare http(s) URLs', () => {
    const text = 'See https://foo.com/page for more. Also http://bar.org/x.';
    const urls = extractSourceUrls(text).map(c => c.url);
    expect(urls).toEqual(['https://foo.com/page', 'http://bar.org/x']);
  });

  it('dedupes URLs preserving first-seen order', () => {
    const text = 'https://dup.com/1 again https://dup.com/1 and https://uniq.com/2';
    const urls = extractSourceUrls(text).map(c => c.url);
    expect(urls).toEqual(['https://dup.com/1', 'https://uniq.com/2']);
  });

  it('strips trailing punctuation from URLs', () => {
    const text = 'Visit https://example.com/page, and https://other.com/end.';
    const urls = extractSourceUrls(text).map(c => c.url);
    expect(urls).toEqual(['https://example.com/page', 'https://other.com/end']);
  });

  it('label is the hostname without www.', () => {
    const chips = extractSourceUrls('https://www.example.com/path?x=1');
    expect(chips[0].label).toBe('example.com');
  });

  it('label truncates long hostnames with ellipsis', () => {
    const long = 'https://subdomain-very-long-name-here.example.com/x';
    const chips = extractSourceUrls(long);
    expect(chips[0].label.endsWith('…')).toBe(true);
    expect(chips[0].label.length).toBeLessThanOrEqual(28);
  });

  it('does not extract non-http schemes (mailto, ftp)', () => {
    const text = 'mailto:test@foo.com and ftp://files.example.com';
    expect(extractSourceUrls(text)).toEqual([]);
  });
});
