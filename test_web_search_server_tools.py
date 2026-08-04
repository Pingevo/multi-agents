"""Test: web search and scraping tools are registered in ToolRegistry alongside media tools."""

import pytest
from backend.agents.tool_registry import ToolRegistry


class TestWebSearchToolsRegistered:
    """Verify that search_web and scrape_web are registered in ToolRegistry alongside other tools."""

    def test_search_web_is_registered(self):
        """search_web should be in the tool registry."""
        registry = ToolRegistry()
        tool_names = registry.list_tools()
        assert "search_web" in tool_names, f"search_web not found in registry: {tool_names}"

    def test_scrape_web_is_registered(self):
        """scrape_web should be in the tool registry."""
        registry = ToolRegistry()
        tool_names = registry.list_tools()
        assert "scrape_web" in tool_names, f"scrape_web not found in registry: {tool_names}"

    def test_media_tools_still_registered_alongside_search(self):
        """generate_image and generate_document should still be registered alongside search tools."""
        registry = ToolRegistry()
        tool_names = registry.list_tools()
        assert "generate_image" in tool_names, "generate_image missing from registry"
        assert "generate_document" in tool_names, "generate_document missing from registry"
        assert "browse_web" in tool_names, "browse_web missing from registry"

    def test_all_tools_coexist(self):
        """All expected tools should be registered simultaneously."""
        registry = ToolRegistry()
        tool_names = set(registry.list_tools())
        expected = {"generate_image", "generate_video", "text_to_speech", "transcribe_audio",
                    "analyze_image", "generate_document", "browse_web", "search_web", "scrape_web"}
        missing = expected - tool_names
        assert not missing, f"Missing tools from registry: {missing}"




class TestUrlExtraction:
    """Verify URL extraction from user messages."""

    def test_extract_urls_from_text(self):
        """Should extract https:// URLs from user message text."""
        from backend.utils import extract_urls
        text = "Check this out https://example.com/article and also https://test.org/page"
        urls = extract_urls(text)
        assert "https://example.com/article" in urls
        assert "https://test.org/page" in urls

    def test_no_urls_returns_empty(self):
        """Should return empty list when no URLs in text."""
        from backend.utils import extract_urls
        text = "Just a regular message without URLs"
        urls = extract_urls(text)
        assert urls == []

    def test_url_with_query_params(self):
        """Should extract URLs with query parameters."""
        from backend.utils import extract_urls
        text = "See https://example.com/page?id=123&ref=abc"
        urls = extract_urls(text)
        assert len(urls) == 1
        assert "https://example.com/page?id=123&ref=abc" in urls
