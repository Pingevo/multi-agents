"""Test: search_web uses OpenRouter server tool (openrouter:web_search) not deprecated plugin.

Bug (Task A — search parity): OpenRouter deprecated `plugins: [{id: "web"}]` in
favor of `tools: [{type: "openrouter:web_search", parameters: {...}}]`. If we
don't migrate, search breaks when OpenRouter removes plugin support.

Market standard (Claude/ChatGPT/Gemini): server-side web search tool where the
model decides when to search (not forced every call).

Business rules:
- Request body must use `tools` array, NOT `plugins` array
- Tool type must be "openrouter:web_search"
- Parameters (engine, max_results, max_total_results, search_context_size)
  must come from config (agent spec), not hardcoded literals (No Hardcode rule)
- Defaults applied when config omits a field

Seam: _build_web_search_tool(search_config) -> dict  (pure, no HTTP)
"""

import sys
sys.path.insert(0, '/Users/its-dev2/my-agent-app')


class TestBuildWebSearchTool:
    """Verify _build_web_search_tool produces the server-tool format, not plugin format."""

    def test_returns_openrouter_web_search_type(self):
        """Tool object must have type='openrouter:web_search' (server tool, not plugin)."""
        from backend.tools.search import _build_web_search_tool
        tool = _build_web_search_tool()
        assert tool["type"] == "openrouter:web_search"

    def test_has_parameters_key(self):
        """Server tool accepts optional 'parameters' for engine/max_results/etc."""
        from backend.tools.search import _build_web_search_tool
        tool = _build_web_search_tool()
        assert "parameters" in tool

    def test_default_engine_is_auto(self):
        """Default engine should be 'auto' (OpenRouter default: native or Exa fallback)."""
        from backend.tools.search import _build_web_search_tool
        tool = _build_web_search_tool()
        assert tool["parameters"]["engine"] == "auto"

    def test_default_max_results_is_positive(self):
        """Default max_results must be > 0 so search returns results."""
        from backend.tools.search import _build_web_search_tool
        tool = _build_web_search_tool()
        assert tool["parameters"]["max_results"] > 0

    def test_custom_config_overrides_defaults(self):
        """Agent spec config (engine, max_results) must override defaults (No Hardcode)."""
        from backend.tools.search import _build_web_search_tool
        tool = _build_web_search_tool({
            "engine": "exa",
            "max_results": 10,
        })
        assert tool["parameters"]["engine"] == "exa"
        assert tool["parameters"]["max_results"] == 10

    def test_partial_config_keeps_other_defaults(self):
        """If config sets only engine, max_results should still get its default."""
        from backend.tools.search import _build_web_search_tool
        tool = _build_web_search_tool({"engine": "perplexity"})
        assert tool["parameters"]["engine"] == "perplexity"
        assert "max_results" in tool["parameters"]
        assert tool["parameters"]["max_results"] > 0

    def test_no_plugins_key_in_tool(self):
        """The returned object must NOT contain a 'plugins' key (deprecated format)."""
        from backend.tools.search import _build_web_search_tool
        tool = _build_web_search_tool()
        assert "plugins" not in tool
        assert "id" not in tool  # plugin format used {"id": "web"}


class TestCallUsesServerTool:
    """Verify _call_openrouter_web_search sends 'tools' not 'plugins' in the request body."""

    def test_request_body_uses_tools_not_plugins(self, monkeypatch):
        """The HTTP request body must include 'tools' and must NOT include 'plugins'."""
        import backend.tools.search as search_mod

        captured = {}

        class FakeResp:
            def raise_for_status(self):
                pass

            def json(self):
                return {"choices": [{"message": {"content": "ok"}}]}

        def fake_post(url, headers=None, json=None, timeout=None):
            captured["json"] = json
            return FakeResp()

        monkeypatch.setattr(search_mod.requests, "post", fake_post)
        monkeypatch.setattr(search_mod, "_build_web_search_tool",
                            lambda config=None: {"type": "openrouter:web_search",
                                                 "parameters": {"engine": "auto", "max_results": 5}})

        class FakeLLMMgr:
            base_url = "https://openrouter.ai/api/v1"
            api_key = "fake-key"

        search_mod._call_openrouter_web_search(FakeLLMMgr(), "openai/gpt-4o-mini", "test query")

        body = captured["json"]
        assert "tools" in body, "Request body must use 'tools' (server tool format)"
        assert "plugins" not in body, "Request body must NOT use deprecated 'plugins'"
        assert body["tools"][0]["type"] == "openrouter:web_search"
