"""Headless browser tool — render JS and extract full content from any URL.

Uses Playwright + playwright-stealth with real Chrome (channel='chrome') for
maximum anti-bot evasion. Falls back to bundled Chromium if Chrome is not installed.
"""

import asyncio
import json
import re

from crewai.tools import tool

try:
    import nest_asyncio
    nest_asyncio.apply()
except ImportError:
    pass


async def _extract_content(page) -> str:
    """Extract page title, body text, and JSON-LD structured data."""
    parts = []

    # Page title
    try:
        title = await page.title()
        if title:
            parts.append(f"Title: {title}\n")
    except Exception:
        pass

    # Body text
    try:
        body_text = await page.inner_text("body")
        if body_text:
            parts.append(body_text.strip())
    except Exception:
        pass

    # JSON-LD structured data (product info, reviews, etc.)
    try:
        ld_json = await page.eval_on_selector_all(
            'script[type="application/ld+json"]',
            'els => els.map(e => e.textContent).join("\\n")'
        )
        if ld_json and ld_json.strip():
            for block in ld_json.split("\n"):
                block = block.strip()
                if not block:
                    continue
                try:
                    data = json.loads(block)
                    parts.append(f"\n[Structured Data]\n{json.dumps(data, ensure_ascii=False, indent=2)[:3000]}")
                except (json.JSONDecodeError, ValueError):
                    pass
    except Exception:
        pass

    return "\n".join(parts) if parts else ""


async def _browse_async(url: str, timeout_ms: int = 20000) -> str:
    """Async implementation using Playwright."""
    from playwright.async_api import async_playwright
    try:
        from playwright_stealth import stealth_async
    except ImportError:
        stealth_async = None

    async with async_playwright() as p:
        # Try real Chrome first, fall back to bundled Chromium
        browser = None
        for channel in ["chrome", None]:
            try:
                launch_kwargs = {"headless": True}
                if channel:
                    launch_kwargs["channel"] = channel
                browser = await p.chromium.launch(**launch_kwargs)
                break
            except Exception:
                continue
        if browser is None:
            return "Error: Could not launch any browser (Chrome or Chromium)"

        try:
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            )
            page = await context.new_page()

            if stealth_async:
                await stealth_async(page)

            await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            # Wait for network idle (JS rendering)
            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass

            content = await _extract_content(page)
            if not content:
                content = "No readable content found at this URL."

            # Truncate to prevent context window bloat
            max_chars = 12000
            if len(content) > max_chars:
                content = content[:max_chars] + "\n\n[... content truncated]"

            return content
        finally:
            await browser.close()


@tool
def browse_web(url: str) -> str:
    """Open a URL with a real headless browser (Chrome) to render JavaScript and extract full page content.

    Use this tool for JavaScript-heavy websites (SPAs, e-commerce, dynamic content)
    where web_fetch returns empty or incomplete results.
    Examples: Shopee, Lazada, Amazon, YouTube, news sites with dynamic loading.

    Returns the visible text content, page title, and any structured data (JSON-LD) found on the page.
    """
    if not url or not url.strip():
        return "Error: Empty URL provided"

    url_clean = url.strip()
    if not (url_clean.startswith("http://") or url_clean.startswith("https://")):
        return f"Error: URL must start with http:// or https:// — got: {url_clean}"

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Inside an existing event loop (CrewAI context) — use nest_asyncio
            return loop.run_until_complete(_browse_async(url_clean))
        else:
            return asyncio.run(_browse_async(url_clean))
    except RuntimeError:
        # No running loop — safe to use asyncio.run
        return asyncio.run(_browse_async(url_clean))
    except Exception as e:
        from backend.utils import _sanitize_error
        return f"Error browsing URL: {_sanitize_error(e)}"
