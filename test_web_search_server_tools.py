"""Test: OpenRouter web_search + web_fetch server tools are injected into agent LLM config."""

import pytest
from unittest.mock import patch, MagicMock
from backend.llm.manager import LLMManager


class TestWebSearchServerTools:
    """Verify that LLMManager injects openrouter:web_search and openrouter:web_fetch server tools."""

    def test_build_llm_includes_web_search_and_web_fetch(self):
        """When building an OpenRouter LLM, additional_params should include server tools."""
        manager = LLMManager()
        # Override to use OpenRouter provider
        manager.provider = "openrouter"
        manager.base_url = "https://openrouter.ai/api/v1"
        manager.api_key = "test-key"
        manager._default_model = "openrouter/free"

        with patch("chainlit.user_session") as mock_session:
            mock_session.get.return_value = None  # No attachment plugins
            llm = manager._build_llm("openrouter", "openrouter/free", "https://openrouter.ai/api/v1", "test-key")

        # Check additional_params contains server tools
        assert llm.additional_params is not None
        extra_body = llm.additional_params.get("extra_body", {})
        tools = extra_body.get("tools", [])
        tool_types = [t.get("type") for t in tools]
        assert "openrouter:web_search" in tool_types, f"web_search not in tools: {tool_types}"
        assert "openrouter:web_fetch" in tool_types, f"web_fetch not in tools: {tool_types}"

    def test_web_fetch_uses_free_engine(self):
        """web_fetch should use engine 'openrouter' (free) to avoid credit costs."""
        manager = LLMManager()
        manager.provider = "openrouter"
        manager.base_url = "https://openrouter.ai/api/v1"
        manager.api_key = "test-key"
        manager._default_model = "openrouter/free"

        with patch("chainlit.user_session") as mock_session:
            mock_session.get.return_value = None
            llm = manager._build_llm("openrouter", "openrouter/free", "https://openrouter.ai/api/v1", "test-key")

        extra_body = llm.additional_params.get("extra_body", {})
        tools = extra_body.get("tools", [])
        web_fetch_tool = [t for t in tools if t.get("type") == "openrouter:web_fetch"]
        assert len(web_fetch_tool) == 1
        assert web_fetch_tool[0].get("parameters", {}).get("engine") == "auto"

    def test_attachment_plugins_still_work_with_server_tools(self):
        """Server tools should be added alongside attachment plugins, not replacing them."""
        manager = LLMManager()
        manager.provider = "openrouter"
        manager.base_url = "https://openrouter.ai/api/v1"
        manager.api_key = "test-key"
        manager._default_model = "openrouter/free"

        mock_plugins = [{"id": "file-parser"}]
        with patch("chainlit.user_session") as mock_session:
            mock_session.get.return_value = mock_plugins
            llm = manager._build_llm("openrouter", "openrouter/free", "https://openrouter.ai/api/v1", "test-key")

        extra_body = llm.additional_params.get("extra_body", {})
        # Both plugins and tools should be present
        assert "plugins" in extra_body, "attachment plugins should still be present"
        assert "tools" in extra_body, "server tools should be added"
        tool_types = [t.get("type") for t in extra_body["tools"]]
        assert "openrouter:web_search" in tool_types


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
