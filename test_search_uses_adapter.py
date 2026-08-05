"""Test: search.py delegates to SearchAdapter (P0.2 consolidation).

After consolidation, _resolve_search_model in search.py should be a thin
wrapper that delegates to SearchAdapter.resolve_search_model — not a
separate implementation reading _globals._search_model directly.

This locks in the deepening: the adapter is the single decision point,
search.py is a caller, not a duplicate implementation.
"""
import sys
sys.path.insert(0, '/Users/its-dev2/my-agent-app')

import backend.globals as g
from backend.tools.search import _resolve_search_model


class TestSearchDelegatesToAdapter:
    """Verify _resolve_search_model delegates to SearchAdapter.resolve_search_model."""

    def test_resolve_uses_adapter_when_global_set(self):
        """When _globals._search_model is set, resolver returns it (via adapter)."""
        original = g._search_model
        try:
            g._search_model = "perplexity/sonar-pro"
            result = _resolve_search_model(selected_model="", default_model="")
            assert result == "perplexity/sonar-pro"
        finally:
            g._search_model = original

    def test_resolve_falls_back_through_adapter(self):
        """Fallback chain works the same after delegation."""
        original = g._search_model
        try:
            g._search_model = ""
            result = _resolve_search_model(
                selected_model="anthropic/claude-sonnet-5",
                default_model="openrouter/free",
            )
            assert result == "anthropic/claude-sonnet-5"
        finally:
            g._search_model = original
