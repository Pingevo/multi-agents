"""Web scraping tool — fetch and extract text content from URLs."""

import re
from crewai.tools import tool
from backend.globals import _progress_callback


@tool
def scrape_web(url: str) -> str:
    """Fetch and extract text content from a web page URL.

    Call this tool when you need to read content from a specific URL —
    articles, blog posts, product pages, documentation, etc.
    Returns the extracted text content (HTML tags removed, main text only).
    """
    global _progress_callback
    if not url or not url.strip():
        return "Error: Empty URL for scraping"

    url_clean = url.strip()
    if not (url_clean.startswith("http://") or url_clean.startswith("https://")):
        return f"Error: URL must start with http:// or https:// — got: {url_clean}"

    if _progress_callback:
        _progress_callback(30, "🌐 กำลังดึงเนื้อหาจากเว็บไซต์...")

    try:
        import urllib.request
        req = urllib.request.Request(
            url_clean,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9,th;q=0.8",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
            # Try common encodings
            for enc in ("utf-8", "utf-8-sig", "tis-620", "latin-1"):
                try:
                    html = raw.decode(enc)
                    break
                except (UnicodeDecodeError, LookupError):
                    continue
            else:
                html = raw.decode("utf-8", errors="replace")

        if _progress_callback:
            _progress_callback(70, "📝 กำลังประมวลผลเนื้อหา...")

        # Remove script/style blocks
        html = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', ' ', html)
        # Decode common HTML entities
        text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"').replace('&#39;', "'")
        # Collapse whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        # Truncate to reasonable length
        max_chars = 8000
        if len(text) > max_chars:
            text = text[:max_chars] + "\n\n[... content truncated]"

        if not text:
            return "No readable text content found at this URL."

        return text

    except Exception as e:
        from backend.utils import _sanitize_error
        return f"Error scraping URL: {_sanitize_error(e)}"
