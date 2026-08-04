"""Test: search_web uses selected_model (not openrouter/free) as fallback.

Bug: When user doesn't set ai_search_model, search_web falls back to
openrouter/free which is slow (48-65s per call) and violates SYSTEM_PROTOCOL
rule "ใช้ paid LLM (ไม่ใช่ free tier)".

Business rule (per SYSTEM_PROTOCOL.md line 22 + user decision):
- search_model resolution order:
  1. ai_search_model (user-selected search model from plan approval)
  2. selected_model (user's top-bar model selection)
  3. _default_model (LLMManager default)
- openrouter/free must NOT be the fallback when selected_model is set

Also: Secretary prompt must NOT mark search_model as "deprecated" — it is
REQUIRED when plan uses search_web, same as image_model for generate_image.
"""

import sys
sys.path.insert(0, '/Users/its-dev2/my-agent-app')

from backend.tools.search import _resolve_search_model
from backend.globals import _search_model


class TestSearchModelFallback:
    """Verify search_web falls back to selected_model, not openrouter/free."""

    def test_uses_ai_search_model_when_set(self, monkeypatch):
        """When ai_search_model is set, it takes priority."""
        monkeypatch.setattr("backend.tools.search._search_model", "perplexity/sonar")
        result = _resolve_search_model(selected_model="anthropic/claude-sonnet-5")
        assert result == "perplexity/sonar"

    def test_falls_back_to_selected_model_when_ai_search_empty(self, monkeypatch):
        """When ai_search_model is empty, use selected_model (top bar), NOT openrouter/free."""
        monkeypatch.setattr("backend.tools.search._search_model", "")
        result = _resolve_search_model(selected_model="anthropic/claude-sonnet-5")
        assert result == "anthropic/claude-sonnet-5"
        assert result != "openrouter/free"

    def test_does_not_use_openrouter_free_when_selected_set(self, monkeypatch):
        """Critical: must never fall to openrouter/free when selected_model is set."""
        monkeypatch.setattr("backend.tools.search._search_model", "")
        result = _resolve_search_model(selected_model="openai/gpt-4o-mini")
        assert "free" not in result.lower()

    def test_falls_back_to_default_when_both_empty(self, monkeypatch):
        """When both ai_search_model and selected_model are empty, use _default_model."""
        monkeypatch.setattr("backend.tools.search._search_model", "")
        # _default_model is read from LLMManager; we test the resolution logic
        # by passing default_model explicitly
        result = _resolve_search_model(selected_model="", default_model="openrouter/free")
        # Last resort fallback is openrouter/free (only when nothing else available)
        assert result == "openrouter/free"


class TestSecretaryPromptSearchModel:
    """Verify Secretary prompt treats search_model as REQUIRED, not deprecated."""

    def test_prompt_does_not_say_deprecated_for_search_model(self):
        """The Secretary prompt must NOT mark search_model as 'deprecated'."""
        from backend.core.secretary import _build_plan_schema_section
        schema = _build_plan_schema_section()
        assert "deprecated" not in schema.lower(), (
            f"search_model should not be marked deprecated. Got: {schema}"
        )

    def test_prompt_says_required_for_search_model(self):
        """The Secretary prompt should mark search_model as REQUIRED when using search_web."""
        from backend.core.secretary import _build_plan_schema_section
        schema = _build_plan_schema_section()
        # search_model line should mention REQUIRED (like image_model)
        assert "search_model" in schema
        assert "REQUIRED" in schema or "required" in schema.lower(), (
            f"search_model should be marked REQUIRED. Got: {schema}"
        )

    def test_instruction_mentions_search_web_to_search_model(self):
        """The instruction should map search_web → search_model (like generate_image → image_model)."""
        from backend.core.secretary import _build_design_rules_section
        rules = _build_design_rules_section()
        assert "search_web" in rules
        assert "search_model" in rules
