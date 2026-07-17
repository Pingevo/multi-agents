"""Utility functions used across the backend."""

import os
import re


def _sanitize_error(e) -> str:
    """Sanitize error messages to prevent API key leakage in logs."""
    msg = str(e)
    msg = re.sub(r'sk-or-[A-Za-z0-9\-_]+', 'sk-or-***', msg)
    msg = re.sub(r'Bearer [A-Za-z0-9\-_]+', 'Bearer ***', msg)
    msg = re.sub(r'api_key=[A-Za-z0-9\-_]+', 'api_key=***', msg)
    msg = re.sub(r'key=[A-Za-z0-9\-_]+', 'key=***', msg)
    return msg[:500]


def _debug(*args, **kwargs):
    """Print only when DEBUG_MODE=true."""
    if os.getenv("DEBUG_MODE", "false").lower() == "true":
        print(*args, **kwargs)


_URL_REGEX = re.compile(r'https://[^\s<>"\')\]]+')


def extract_urls(text: str) -> list[str]:
    """Extract all URLs from text using urlextract."""
    if not text:
        return []
    from backend.attachment.url import find_urls_in_text
    return find_urls_in_text(text)
