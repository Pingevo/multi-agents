"""Test: SearchAdapter.supports_server_tool — capability detection per model.

Bug: perplexity/sonar-pro + tools:[openrouter:web_search] → 404
"No endpoints found that support tool use"

Perplexity models have built-in search (web_search_options) — they don't
accept the openrouter:web_search server tool. SearchAdapter must detect
this via ModelDiscoveryService catalog and report which format to use.

Seam (approved by user): SearchAdapter.supports_server_tool(model) -> bool
- Pure function, no HTTP
- ModelDiscoveryService injected with fake catalog in tests
- True  = model supports `tools` (server tool format)
- False = model uses built-in search (web_search_options format)
"""

import sys
sys.path.insert(0, '/Users/its-dev2/my-agent-app')

from backend.tools.search_adapter import SearchAdapter


class _FakeDiscovery:
    """Minimal fake ModelDiscoveryService for testing.

    Returns canned supported_parameters per model ID, mimicking the real
    OpenRouter catalog structure. No HTTP, no network.
    """

    def __init__(self, catalog: dict[str, list[str]]):
        # catalog: {model_id: supported_parameters_list}
        self._catalog = catalog

    def get_supported_parameters(self, model_id: str) -> list[str]:
        return self._catalog.get(model_id, [])


# Catalog mimicking real OpenRouter model metadata
# - tools-capable models: have "tools" in supported_parameters
# - perplexity models: have "web_search_options" (current OpenRouter param name)
#   but NOT "tools" (built-in search)
# - openrouter/free: not in catalog (router, skipped by discover_all)
_FAKE_CATALOG = {
    "anthropic/claude-sonnet-5": ["tools", "temperature", "max_tokens"],
    "openai/gpt-5.6-luna": ["tools", "temperature", "max_tokens"],
    "google/gemini-3.5-flash": ["tools", "temperature", "max_tokens"],
    "x-ai/grok-4.5": ["tools", "temperature", "max_tokens"],
    "perplexity/sonar-pro": ["web_search_options", "temperature", "max_tokens"],
    "perplexity/sonar": ["web_search_options", "temperature"],
    "perplexity/sonar-reasoning-pro": ["web_search_options", "reasoning", "temperature"],
    "perplexity/sonar-deep-research": ["web_search_options", "reasoning", "temperature"],
    "perplexity/sonar-pro-search": ["web_search_options", "temperature"],
}


def _make_adapter() -> SearchAdapter:
    """Build a SearchAdapter with the fake catalog (no network)."""
    return SearchAdapter(llm_manager=None, discovery=_FakeDiscovery(_FAKE_CATALOG))


class TestSupportsServerTool:
    """Verify supports_server_tool correctly identifies which models
    accept the openrouter:web_search server tool (Seam 1 — approved)."""

    # Models that SHOULD support server tool (have "tools" in params)
    def test_claude_supports_server_tool(self):
        adapter = _make_adapter()
        assert adapter.supports_server_tool("anthropic/claude-sonnet-5") is True

    def test_gpt_supports_server_tool(self):
        adapter = _make_adapter()
        assert adapter.supports_server_tool("openai/gpt-5.6-luna") is True

    def test_gemini_supports_server_tool(self):
        adapter = _make_adapter()
        assert adapter.supports_server_tool("google/gemini-3.5-flash") is True

    def test_grok_supports_server_tool(self):
        adapter = _make_adapter()
        assert adapter.supports_server_tool("x-ai/grok-4.5") is True

    # Models that should NOT get server tool (built-in search, no "tools")
    def test_perplexity_sonar_pro_no_server_tool(self):
        """The exact bug: sonar-pro has built-in search, must skip server tool."""
        adapter = _make_adapter()
        assert adapter.supports_server_tool("perplexity/sonar-pro") is False

    def test_perplexity_sonar_no_server_tool(self):
        adapter = _make_adapter()
        assert adapter.supports_server_tool("perplexity/sonar") is False

    def test_perplexity_sonar_reasoning_pro_no_server_tool(self):
        adapter = _make_adapter()
        assert adapter.supports_server_tool("perplexity/sonar-reasoning-pro") is False

    def test_perplexity_sonar_deep_research_no_server_tool(self):
        adapter = _make_adapter()
        assert adapter.supports_server_tool("perplexity/sonar-deep-research") is False

    def test_perplexity_sonar_pro_search_no_server_tool(self):
        adapter = _make_adapter()
        assert adapter.supports_server_tool("perplexity/sonar-pro-search") is False

    # Edge cases — fallback when model not in catalog
    def test_empty_model_returns_true(self):
        """Empty model = unknown, default to including tool (let API decide)."""
        adapter = _make_adapter()
        assert adapter.supports_server_tool("") is True

    def test_free_model_returns_true(self):
        """openrouter/free is a router, not in catalog — supports tool."""
        adapter = _make_adapter()
        assert adapter.supports_server_tool("openrouter/free") is True

    def test_unknown_non_perplexity_model_returns_true(self):
        """Unknown model without perplexity prefix — default to tool (let API decide)."""
        adapter = _make_adapter()
        assert adapter.supports_server_tool("some-unknown-vendor/model-x") is True

    def test_unknown_perplexity_model_returns_false(self):
        """Unknown perplexity model not in catalog — prefix heuristic says no tool."""
        adapter = _make_adapter()
        assert adapter.supports_server_tool("perplexity/new-sonar-variant") is False
