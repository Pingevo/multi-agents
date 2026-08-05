"""Test: SearchAdapter.resolve_search_model — single resolution point.

Consolidates the 4 scattered decision points (P0.2 per ADR-0004 / HANDOFF):
1. Secretary (plan phase) — sets search_model in plan JSON
2. chat.py — stores in cl.user_session("ai_search_model")
3. orchestrator.py — writes to _globals._search_model
4. search.py _resolve_search_model — reads from _globals._search_model

The adapter becomes the single resolution point. Resolution order:
1. ai_search_model (user-selected from plan approval)
2. selected_model (top-bar model selection)
3. default_model (LLMManager default)
4. "openrouter/free" (last resort)

Seam: SearchAdapter.resolve_search_model(ai_search_model, selected_model, default_model) -> str
Pure function, no globals, no HTTP — fully testable through the interface.
"""
import sys
sys.path.insert(0, '/Users/its-dev2/my-agent-app')

from backend.tools.search_adapter import SearchAdapter


def _make_adapter() -> SearchAdapter:
    """Adapter with no llm_manager (resolve_search_model doesn't need it)."""
    return SearchAdapter(llm_manager=None, discovery=None)


class TestResolveSearchModel:
    """Verify resolution order: ai_search_model > selected_model > default > free."""

    def test_ai_search_model_takes_priority(self):
        adapter = _make_adapter()
        result = adapter.resolve_search_model(
            ai_search_model="perplexity/sonar",
            selected_model="anthropic/claude-sonnet-5",
            default_model="openrouter/free",
        )
        assert result == "perplexity/sonar"

    def test_selected_model_when_ai_search_empty(self):
        adapter = _make_adapter()
        result = adapter.resolve_search_model(
            ai_search_model="",
            selected_model="anthropic/claude-sonnet-5",
            default_model="openrouter/free",
        )
        assert result == "anthropic/claude-sonnet-5"
        assert result != "openrouter/free"

    def test_default_model_when_both_empty(self):
        adapter = _make_adapter()
        result = adapter.resolve_search_model(
            ai_search_model="",
            selected_model="",
            default_model="openai/gpt-4o-mini",
        )
        assert result == "openai/gpt-4o-mini"

    def test_free_as_last_resort(self):
        adapter = _make_adapter()
        result = adapter.resolve_search_model(
            ai_search_model="",
            selected_model="",
            default_model="",
        )
        assert result == "openrouter/free"

    def test_no_free_when_selected_set(self):
        """Critical: must never fall to openrouter/free when selected_model is set."""
        adapter = _make_adapter()
        result = adapter.resolve_search_model(
            ai_search_model="",
            selected_model="openai/gpt-4o-mini",
            default_model="",
        )
        assert "free" not in result.lower()
