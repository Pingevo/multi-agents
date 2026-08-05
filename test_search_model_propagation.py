"""Test: search_model set in orchestrator propagates to search_web.

Bug: Plan approval sets search_model=perplexity/sonar-pro (visible in
[DEBUG-MODELS] log), but search_web uses openrouter/free (visible in
[SearchTool] Searching log). The _search_model global isn't propagating
from orchestrator to search_web.

This test exercises the real propagation path:
  orchestrator._run_agents() sets _search_model = ai_search_model
  → search_web reads _search_model via _resolve_search_model()

If the global isn't shared between modules, this test goes red.
"""

import sys
sys.path.insert(0, '/Users/its-dev2/my-agent-app')

import backend.globals as g
from backend.tools.search import _resolve_search_model


class TestSearchModelPropagation:
    """Verify _search_model set via globals propagates to search_web's resolver."""

    def test_resolve_returns_search_model_when_set_in_globals(self):
        """If orchestrator sets g._search_model, _resolve_search_model must see it.

        This is the exact propagation that broke: orchestrator assigns
        _search_model = ai_search_model, but search_web reads its own
        imported copy. If they're not the same object, this fails.
        """
        # Simulate orchestrator setting the global
        original = g._search_model
        try:
            g._search_model = "perplexity/sonar-pro"
            # search_web's resolver should see this value
            result = _resolve_search_model(selected_model="", default_model="")
            assert result == "perplexity/sonar-pro", (
                f"Expected 'perplexity/sonar-pro' (set in globals), got {result!r}. "
                f"_search_model is not shared between orchestrator and search_web."
            )
        finally:
            g._search_model = original

    def test_search_web_module_global_matches_globals_module(self):
        """search_web's imported _search_model must be the same object as globals._search_model.

        Python gotcha: `from X import Y` copies the binding at import time.
        If search_web did `from backend.globals import _search_model`,
        later reassignment in globals won't be visible — UNLESS search_web
        uses `global _search_model` and reads it dynamically.
        """
        import backend.tools.search as sw
        # Set via the canonical globals module
        original = g._search_model
        try:
            g._search_model = "test-model-x"
            # search_web's _resolve_search_model reads its module-level _search_model
            # If propagation works, this returns "test-model-x"
            result = _resolve_search_model(selected_model="", default_model="")
            assert result == "test-model-x", (
                f"search_web did not see globals._search_model update. "
                f"globals._search_model={g._search_model!r}, resolver returned={result!r}"
            )
        finally:
            g._search_model = original
