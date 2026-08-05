"""Test: FreeModelRotator fetches free model slugs dynamically (No Hardcode).

Bug (issue #125): _FREE_MODEL_RANKING is hardcoded with stale slugs that
OpenRouter has retired (deepseek-r1:free, llama-3.3-70b:free, etc. — all 404).
Per No Hardcode rule, the ranking must be fetched dynamically from the
OpenRouter catalog, filtering for models with ':free' suffix that actually
exist.

Seam: FreeModelRotator.get_ranking() -> list[str]
- Injected with a fake catalog (no HTTP)
- Returns only models with ':free' suffix that exist in the catalog
- Sorted by capability (e.g. context_length desc) so smartest is first
- Falls back to empty list if catalog unavailable (caller handles)
"""
import sys
sys.path.insert(0, '/Users/its-dev2/my-agent-app')

from backend.llm.rotator import FreeModelRotator


class _FakeCatalog:
    """Fake OpenRouter /models endpoint response."""
    def __init__(self, models: list[dict]):
        self._models = models

    def get_models(self) -> list[dict]:
        return self._models


# Realistic catalog: mix of free + paid, with context_length for ranking
_FAKE_CATALOG = [
    # Free models (should appear in ranking)
    {"id": "google/gemini-2.0-flash-exp:free", "context_length": 1048576, "architecture": {"input_modalities": ["text", "image"]}},
    {"id": "meta-llama/llama-3.3-70b-instruct:free", "context_length": 131072, "architecture": {"input_modalities": ["text"]}},
    {"id": "qwen/qwen3-coder:free", "context_length": 131072, "architecture": {"input_modalities": ["text"]}},
    # Paid models (should NOT appear in free ranking)
    {"id": "anthropic/claude-sonnet-5", "context_length": 200000, "architecture": {"input_modalities": ["text", "image"]}},
    {"id": "openai/gpt-5", "context_length": 200000, "architecture": {"input_modalities": ["text", "image"]}},
    # Stale slug that no longer exists — must NOT appear
    # (we don't include it in the fake catalog, simulating OpenRouter having retired it)
]


class TestDynamicRanking:
    """Verify get_ranking() returns only free models that exist in the catalog."""

    def test_ranking_returns_only_free_models(self):
        """All returned slugs must have ':free' suffix."""
        rotator = FreeModelRotator(
            api_key="fake", base_url="http://fake",
            catalog=_FakeCatalog(_FAKE_CATALOG),
        )
        ranking = rotator.get_ranking()
        assert all(":free" in m for m in ranking), (
            f"Non-free model in ranking: {ranking}"
        )

    def test_ranking_excludes_paid_models(self):
        """Paid models (claude-sonnet-5, gpt-5) must NOT appear."""
        rotator = FreeModelRotator(
            api_key="fake", base_url="http://fake",
            catalog=_FakeCatalog(_FAKE_CATALOG),
        )
        ranking = rotator.get_ranking()
        assert "anthropic/claude-sonnet-5" not in ranking
        assert "openai/gpt-5" not in ranking

    def test_ranking_excludes_stale_slugs(self):
        """Stale slugs (deepseek-r1:free, gpt-oss-120b:free) that OpenRouter
        retired must NOT appear — they would 404."""
        rotator = FreeModelRotator(
            api_key="fake", base_url="http://fake",
            catalog=_FakeCatalog(_FAKE_CATALOG),
        )
        ranking = rotator.get_ranking()
        # These are not in the fake catalog (simulating retirement)
        assert "deepseek/deepseek-r1:free" not in ranking
        assert "openai/gpt-oss-120b:free" not in ranking

    def test_ranking_sorted_by_context_length_desc(self):
        """Smartest model (largest context) should be first."""
        rotator = FreeModelRotator(
            api_key="fake", base_url="http://fake",
            catalog=_FakeCatalog(_FAKE_CATALOG),
        )
        ranking = rotator.get_ranking()
        # gemini-2.0-flash-exp:free has 1048576 context — should be first
        assert ranking[0] == "google/gemini-2.0-flash-exp:free", (
            f"Expected gemini-2.0-flash-exp:free first (largest context), got {ranking[0]}"
        )

    def test_ranking_empty_when_catalog_empty(self):
        """No free models in catalog → empty ranking (caller handles)."""
        rotator = FreeModelRotator(
            api_key="fake", base_url="http://fake",
            catalog=_FakeCatalog([]),
        )
        ranking = rotator.get_ranking()
        assert ranking == []
