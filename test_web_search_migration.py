"""Test: SearchAdapter uses OpenRouter server tool (openrouter:web_search) not
deprecated plugin, AND picks web_search_options for perplexity models.

Bug (Task A — search parity): OpenRouter deprecated `plugins: [{id: "web"}]` in
favor of `tools: [{type: "openrouter:web_search", parameters: {...}}]`. If we
don't migrate, search breaks when OpenRouter removes plugin support.

Bug (P0.2 — perplexity 404): perplexity models don't accept `tools` — they use
built-in search via top-level `web_search_options`. Sending `tools` to perplexity
returns 404 "No endpoints found that support tool use".

Market standard (Claude/ChatGPT/Gemini): server-side web search tool where the
model decides when to search (not forced every call).
Perplexity standard: built-in search via web_search_options.

Business rules:
- tools-capable model request body must use `tools` array, NOT `plugins`
- perplexity model request body must use `web_search_options`, NOT `tools`
- Tool type must be "openrouter:web_search"
- Parameters (engine, max_results, max_total_results, search_context_size)
  must come from config (agent spec), not hardcoded literals (No Hardcode rule)
- Defaults applied when config omits a field

Seam: SearchAdapter._build_request_body(query, model, search_config) -> dict
      (pure, no HTTP — verified via _build_tools_param and _build_web_search_options)
"""

import sys
sys.path.insert(0, '/Users/its-dev2/my-agent-app')

from backend.tools.search_adapter import SearchAdapter


class _FakeDiscovery:
    def __init__(self, catalog: dict[str, list[str]]):
        self._catalog = catalog

    def get_supported_parameters(self, model_id: str) -> list[str]:
        return self._catalog.get(model_id, [])


_CATALOG = {
    "openai/gpt-4o-mini": ["tools", "temperature"],
    "perplexity/sonar-pro": ["web_search_options", "temperature"],
}


def _adapter() -> SearchAdapter:
    return SearchAdapter(llm_manager=None, discovery=_FakeDiscovery(_CATALOG))


class TestBuildToolsParam:
    """Verify _build_tools_param produces the server-tool format, not plugin format."""

    def test_returns_openrouter_web_search_type(self):
        """Tool object must have type='openrouter:web_search' (server tool, not plugin)."""
        tool = _adapter()._build_tools_param()
        assert tool["type"] == "openrouter:web_search"

    def test_has_parameters_key(self):
        """Server tool accepts optional 'parameters' for engine/max_results/etc."""
        tool = _adapter()._build_tools_param()
        assert "parameters" in tool

    def test_default_engine_is_auto(self):
        """Default engine should be 'auto' (OpenRouter default: native or Exa fallback)."""
        tool = _adapter()._build_tools_param()
        assert tool["parameters"]["engine"] == "auto"

    def test_default_max_results_is_positive(self):
        """Default max_results must be > 0 so search returns results."""
        tool = _adapter()._build_tools_param()
        assert tool["parameters"]["max_results"] > 0

    def test_custom_config_overrides_defaults(self):
        """Agent spec config (engine, max_results) must override defaults (No Hardcode)."""
        tool = _adapter()._build_tools_param({
            "engine": "exa",
            "max_results": 10,
        })
        assert tool["parameters"]["engine"] == "exa"
        assert tool["parameters"]["max_results"] == 10

    def test_partial_config_keeps_other_defaults(self):
        """If config sets only engine, max_results should still get its default."""
        tool = _adapter()._build_tools_param({"engine": "perplexity"})
        assert tool["parameters"]["engine"] == "perplexity"
        assert "max_results" in tool["parameters"]
        assert tool["parameters"]["max_results"] > 0

    def test_no_plugins_key_in_tool(self):
        """The returned object must NOT contain a 'plugins' key (deprecated format)."""
        tool = _adapter()._build_tools_param()
        assert "plugins" not in tool
        assert "id" not in tool  # plugin format used {"id": "web"}


class TestBuildRequestBodyToolsFormat:
    """Verify _build_request_body uses 'tools' (not 'plugins') for tools-capable models."""

    def test_tools_capable_model_uses_tools_array(self):
        """Claude/GPT models must get 'tools' in the request body."""
        body = _adapter()._build_request_body("test query", "openai/gpt-4o-mini")
        assert "tools" in body, "tools-capable model must use 'tools' (server tool format)"
        assert "plugins" not in body, "Request body must NOT use deprecated 'plugins'"
        assert body["tools"][0]["type"] == "openrouter:web_search"

    def test_tools_capable_model_no_web_search_options(self):
        """Claude/GPT models must NOT get web_search_options (that's perplexity-only)."""
        body = _adapter()._build_request_body("test query", "openai/gpt-4o-mini")
        assert "web_search_options" not in body


class TestBuildRequestBodyPerplexityFormat:
    """Verify _build_request_body uses 'web_search_options' for perplexity models.

    This is the P0.2 bug fix: perplexity + tools → 404. Must use web_search_options.
    """

    def test_perplexity_model_uses_web_search_options(self):
        """Perplexity models must get 'web_search_options', NOT 'tools'."""
        body = _adapter()._build_request_body("test query", "perplexity/sonar-pro")
        assert "web_search_options" in body, (
            "perplexity model must use 'web_search_options' (built-in search)"
        )
        assert "tools" not in body, (
            "perplexity model must NOT get 'tools' — that causes 404 error"
        )

    def test_perplexity_web_search_options_has_context_size(self):
        """web_search_options must include search_context_size (default 'high')."""
        body = _adapter()._build_request_body("test query", "perplexity/sonar-pro")
        opts = body["web_search_options"]
        assert opts["search_context_size"] == "high"

    def test_perplexity_custom_context_size_from_config(self):
        """search_context_size must come from config (No Hardcode)."""
        body = _adapter()._build_request_body(
            "test query", "perplexity/sonar-pro",
            search_config={"search_context_size": "low"},
        )
        assert body["web_search_options"]["search_context_size"] == "low"

    def test_perplexity_no_plugins_key(self):
        """Perplexity request body must NOT contain 'plugins' (deprecated)."""
        body = _adapter()._build_request_body("test query", "perplexity/sonar-pro")
        assert "plugins" not in body
