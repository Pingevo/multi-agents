// extractSourceUrls — pull source URLs out of agent output text so they can
// render as clickable chips (parity with Claude/ChatGPT/Perplexity source lists).
//
// The search prompt (backend/tools/search_adapter.py) asks the model to format
// sources as `Source: <url>` lines and a trailing `Sources:` section. We also
// catch bare http(s) URLs so non-search output (e.g. browse_web summaries) is
// covered too. Dedupes by URL, preserves first-seen order.

export interface SourceChip {
  url: string;
  label: string; // host — short, fits a chip
}

const URL_RE = /https?:\/\/[^\s<>"')\]]+/gi;

// Hostnames worth stripping to a tidier label (www. prefix, common mobile/m subdomains).
function hostLabel(url: string): string {
  try {
    const u = new URL(url);
    let h = u.hostname.replace(/^www\./, '');
    if (h.length > 28) h = h.slice(0, 25) + '…';
    return h;
  } catch {
    // Not a parseable URL — fall back to a truncated raw string
    return url.length > 28 ? url.slice(0, 25) + '…' : url;
  }
}

export function extractSourceUrls(text: string | undefined | null): SourceChip[] {
  if (!text) return [];
  const seen = new Set<string>();
  const out: SourceChip[] = [];
  for (const raw of text.matchAll(URL_RE)) {
    const url = raw[0].replace(/[.,;:)]+$/, ''); // trim trailing punctuation
    if (seen.has(url)) continue;
    seen.add(url);
    out.push({ url, label: hostLabel(url) });
  }
  return out;
}
