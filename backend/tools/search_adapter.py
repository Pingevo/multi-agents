"""SearchAdapter — single decision point for web search format selection.

Consolidates the search-format decision logic that was previously spread
across 4 points (secretary, chat.py, orchestrator, search.py). The adapter
hides capability detection + format selection + HTTP execution behind a
small interface (deep module per codebase-design vocabulary).

Bug fixed: perplexity/sonar-pro + tools:[openrouter:web_search] → 404.
Perplexity models have built-in search (web_search_options) and do NOT
accept the openrouter:web_search server tool. The adapter detects this
via ModelDiscoveryService catalog (supported_parameters field) and picks
the correct request format per model.
"""

import time
import requests
from backend.ai_usage_hub import log_ai_usage
from backend.globals import DEFAULT_SEARCH_ENGINE, DEFAULT_SEARCH_MAX_RESULTS


class SearchAdapter:
    """Deep module: small interface hiding capability check + format + HTTP.

    Interface:
        supports_server_tool(model) -> bool
            True  = model accepts `tools` (server tool format)
            False = model uses built-in search (web_search_options format)
        search(query, model, search_config) -> str
            Execute web search, picking the correct format per model.

    Implementation:
        - Uses ModelDiscoveryService to read supported_parameters from catalog
        - Fallback to prefix heuristic when model not in catalog
        - Format selection (tools vs web_search_options) in _build_request_body
        - HTTP execution in search()
    """

    def __init__(self, llm_manager=None, discovery=None):
        # llm_manager: needed for search() HTTP calls (base_url, api_key)
        # discovery: ModelDiscoveryService instance — injectable for tests
        #            (None = caller will set before calling search())
        self._llm_manager = llm_manager
        self._discovery = discovery

    def supports_server_tool(self, model: str) -> bool:
        """Check whether a model accepts the openrouter:web_search server tool.

        Decision logic:
        1. Query ModelDiscoveryService catalog for supported_parameters
        2. "tools" in params        → True  (server tool format)
        3. "web_search" in params
           (without "tools")        → False (built-in search, e.g. perplexity)
        4. Not in catalog           → prefix heuristic fallback:
           - "perplexity/" prefix   → False (known built-in search family)
           - empty / openrouter/    → True  (router or unknown, let API decide)
           - other unknown          → True  (default to server tool)
        """
        if not model:
            return True  # empty = unknown, let API decide

        params = self._lookup_params(model)
        if params:
            # Catalog hit — authoritative decision
            if "tools" in params:
                return True
            if "web_search" in params:
                return False  # built-in search, no server tool
            # Has params but neither tools nor web_search — default to True
            return True

        # Catalog miss — prefix heuristic fallback
        if model.startswith("perplexity/"):
            return False
        return True  # unknown non-perplexity → let API decide

    def _lookup_params(self, model: str) -> list[str]:
        """Read supported_parameters from discovery service. Empty list if unavailable."""
        if self._discovery is None:
            return []
        try:
            return self._discovery.get_supported_parameters(model)
        except Exception:
            return []

    def _build_tools_param(self, search_config: dict | None = None) -> dict:
        """Build the openrouter:web_search server-tool object for the `tools` array.

        Parameters come from search_config (agent spec field) with defaults
        from globals (No Hardcode rule). Pure function — no HTTP.
        """
        cfg = search_config or {}
        parameters = {
            "engine": cfg.get("engine", DEFAULT_SEARCH_ENGINE),
            "max_results": cfg.get("max_results", DEFAULT_SEARCH_MAX_RESULTS),
        }
        # Optional parameters — only include when config provides them
        for opt_key in ("max_total_results", "search_context_size", "max_uses",
                        "max_characters", "allowed_domains", "excluded_domains"):
            if opt_key in cfg and cfg[opt_key] is not None:
                parameters[opt_key] = cfg[opt_key]
        return {"type": "openrouter:web_search", "parameters": parameters}

    def _build_web_search_options(self, search_config: dict | None = None) -> dict:
        """Build the web_search_options object for perplexity built-in search.

        Perplexity models accept a top-level `web_search_options` parameter
        instead of the `tools` array. Only search_context_size is forwarded
        (the main knob for built-in search); engine/max_results are not
        applicable — perplexity uses its own Sonar engine.
        """
        cfg = search_config or {}
        opts = {}
        # search_context_size: low/medium/high — default "high" for thorough search
        opts["search_context_size"] = cfg.get("search_context_size", "high")
        return opts

    def _build_request_body(self, query: str, model: str,
                            search_config: dict | None = None) -> dict:
        """Build the OpenRouter chat/completions request body.

        Picks the search format based on model capability:
        - tools-capable (Claude/GPT/Gemini) → `tools: [openrouter:web_search]`
        - built-in search (Perplexity)      → `web_search_options: {...}`

        Pure function — no HTTP. Extracted so tests can verify the format
        selection without making network calls.
        """
        search_prompt = (
            f"Search the web for: {query}\n\n"
            "Provide factual, up-to-date information.\n"
            "CRITICAL: You MUST include source URLs for every claim you make.\n"
            "List each source URL on a separate line prefixed with 'Source: '.\n"
            "If you cannot find reliable sources for a claim, explicitly state "
            "'No reliable source found' instead of fabricating information.\n"
            "Do NOT invent URLs or make up sources.\n"
            "Format your response as:\n"
            "1. A summary of findings (with inline citations)\n"
            "2. A 'Sources:' section listing all URLs used"
        )
        body = {
            "model": model,
            "messages": [{"role": "user", "content": search_prompt}],
            "temperature": 0.3,
        }
        if self.supports_server_tool(model):
            body["tools"] = [self._build_tools_param(search_config)]
        else:
            body["web_search_options"] = self._build_web_search_options(search_config)
        return body

    def search(self, query: str, model: str, search_config: dict | None = None) -> str:
        """Execute a web search via OpenRouter, picking the correct format per model.

        Returns the content string from the chat completion response.
        Raises on HTTP errors (caller handles fallback).
        """
        if self._llm_manager is None:
            raise RuntimeError("SearchAdapter.search requires llm_manager")
        body = self._build_request_body(query, model, search_config)
        started_at = time.time()
        try:
            resp = requests.post(
                f"{self._llm_manager.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._llm_manager.api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=60,
            )
            resp.raise_for_status()
        except Exception as e:
            http_status = getattr(resp, "status_code", None) if 'resp' in dir() else None
            log_ai_usage({
                "provider": "openrouter",
                "model": model,
                "operation": "chat.completions",
                "source": "search_web",
                "status": "error",
                "http_status": http_status,
                "error_message": str(e),
                "duration_ms": int((time.time() - started_at) * 1000),
                "metadata": {"analysis_type": "search"},
            })
            raise
        data = resp.json()
        usage = data.get("usage", {})
        log_ai_usage({
            "provider": "openrouter",
            "model": model,
            "operation": "chat.completions",
            "source": "search_web",
            "status": "success",
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "cost_usd": usage.get("cost"),
            "duration_ms": int((time.time() - started_at) * 1000),
            "raw_usage": usage,
            "request_id": data.get("id"),
            "metadata": {"analysis_type": "search"},
        })
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return content

