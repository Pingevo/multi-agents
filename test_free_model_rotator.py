"""Tests for FreeModelRotator — verifies dynamic ranking, rotation, and fallback behavior.

Updated 2026-08-05 (issue #125): ranking is now fetched dynamically from the
OpenRouter catalog (No Hardcode) instead of a hardcoded list. Tests inject a
fake catalog so they don't hit the network and don't break when OpenRouter
retires free slugs.
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class _FakeCatalog:
    """Fake OpenRouter /models response for testing (no HTTP)."""
    def __init__(self, models):
        self._models = models

    def get_models(self):
        return self._models


# Realistic free models that currently exist in OpenRouter (verified 2026-08-05)
_FAKE_FREE_CATALOG = [
    {"id": "google/gemini-2.0-flash-exp:free", "context_length": 1048576, "architecture": {"input_modalities": ["text", "image"]}},
    {"id": "meta-llama/llama-3.3-70b-instruct:free", "context_length": 131072, "architecture": {"input_modalities": ["text"]}},
    {"id": "meta-llama/llama-3.2-3b-instruct:free", "context_length": 131072, "architecture": {"input_modalities": ["text"]}},
]


class TestFreeModelRotatorRanking(unittest.TestCase):
    """Seam: get_ranking() returns dynamic free model list, smartest first."""

    def test_returns_dynamic_ranking_from_catalog(self):
        from app import FreeModelRotator
        rotator = FreeModelRotator(
            api_key="fake", base_url="https://openrouter.ai/api/v1",
            catalog=_FakeCatalog(_FAKE_FREE_CATALOG),
        )
        ranking = rotator.get_ranking()

        # All returned slugs must be free models from the catalog
        self.assertIn("google/gemini-2.0-flash-exp:free", ranking)
        self.assertIn("meta-llama/llama-3.3-70b-instruct:free", ranking)
        # Smartest (largest context) first
        self.assertEqual(ranking[0], "google/gemini-2.0-flash-exp:free")

    def test_ranking_excludes_stale_slugs(self):
        """Stale slugs that OpenRouter retired (deepseek-r1:free, gpt-oss-120b:free)
        must NOT appear — they would 404 (issue #125)."""
        from app import FreeModelRotator
        rotator = FreeModelRotator(
            api_key="fake", base_url="https://openrouter.ai/api/v1",
            catalog=_FakeCatalog(_FAKE_FREE_CATALOG),
        )
        ranking = rotator.get_ranking()
        self.assertNotIn("deepseek/deepseek-r1:free", ranking)
        self.assertNotIn("openai/gpt-oss-120b:free", ranking)

    def test_ranking_is_a_copy(self):
        from app import FreeModelRotator
        rotator = FreeModelRotator(
            api_key="fake", base_url="https://openrouter.ai/api/v1",
            catalog=_FakeCatalog(_FAKE_FREE_CATALOG),
        )
        r1 = rotator.get_ranking()
        r1.append("fake/model:free")
        r2 = rotator.get_ranking()
        self.assertNotIn("fake/model:free", r2)


class TestFreeModelRotatorCall(unittest.TestCase):
    """Seam: call(prompt, max_attempts) rotates through free models on failure."""

    def test_returns_first_success(self):
        from app import FreeModelRotator
        rotator = FreeModelRotator(
            api_key="fake", base_url="https://openrouter.ai/api/v1",
            catalog=_FakeCatalog(_FAKE_FREE_CATALOG),
        )

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Hello"))]
        mock_response.usage = MagicMock()

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch("openai.OpenAI", return_value=mock_client):
            with patch("time.sleep"):
                result = rotator.call("hi", max_attempts=3)

        self.assertEqual(result, "Hello")

    def test_rotates_on_failure(self):
        from app import FreeModelRotator
        rotator = FreeModelRotator(
            api_key="fake", base_url="https://openrouter.ai/api/v1",
            catalog=_FakeCatalog(_FAKE_FREE_CATALOG),
        )

        call_count = [0]
        def mock_create(**kwargs):
            call_count[0] += 1
            if call_count[0] <= 1:
                raise Exception("502 Bad Gateway")
            mock_resp = MagicMock()
            mock_resp.choices = [MagicMock(message=MagicMock(content="Hello from model-b"))]
            mock_resp.usage = MagicMock()
            return mock_resp

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = mock_create

        with patch("openai.OpenAI", return_value=mock_client):
            with patch("time.sleep"):
                result = rotator.call("hi", max_attempts=3)

        self.assertEqual(result, "Hello from model-b")
        self.assertGreaterEqual(call_count[0], 2)

    def test_raises_after_all_attempts_fail(self):
        from app import FreeModelRotator
        rotator = FreeModelRotator(
            api_key="fake", base_url="https://openrouter.ai/api/v1",
            catalog=_FakeCatalog(_FAKE_FREE_CATALOG),
        )

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("502 Bad Gateway")

        with patch("openai.OpenAI", return_value=mock_client):
            with patch("time.sleep"):
                with self.assertRaises(RuntimeError) as ctx:
                    rotator.call("hi", max_attempts=3)

        self.assertIn("attempts failed", str(ctx.exception))


class TestFreeModelRotatorBuildCrewaiLLM(unittest.TestCase):
    """Seam: build_crewai_llm() returns a CrewAI LLM for a specific free model."""

    def test_builds_llm_with_correct_model(self):
        from app import FreeModelRotator
        rotator = FreeModelRotator(api_key="fake", base_url="https://openrouter.ai/api/v1")

        llm = rotator.build_crewai_llm("meta-llama/llama-3.3-70b-instruct:free")
        self.assertIn("meta-llama/llama-3.3-70b-instruct:free", llm.model)


class TestFreeModelRotatorVisionBlocklist(unittest.TestCase):
    """Seam: _fetch_vision_free_models() must exclude blocklisted models and sort preferred first."""

    def _make_api_response(self, model_ids):
        """Build a mock OpenRouter /models API response."""
        return {
            "data": [
                {
                    "id": mid,
                    "architecture": {"input_modalities": ["text", "image"]},
                }
                for mid in model_ids
            ]
        }

    def test_blocklisted_models_excluded(self):
        """Content safety / moderation models must not appear in vision model list."""
        from app import FreeModelRotator
        rotator = FreeModelRotator(api_key="fake", base_url="https://openrouter.ai/api/v1")

        models = [
            "nvidia/nemotron-3.5-content-safety:free",
            "nvidia/nemotron-nano-12b-v2-vl:free",
            "google/gemini-2.0-flash-exp:free",
            "qwen/qwen2.5-vl-72b-instruct:free",
        ]
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = self._make_api_response(models)

        with patch("requests.get", return_value=mock_resp):
            result = rotator._fetch_vision_free_models()

        self.assertNotIn("nvidia/nemotron-3.5-content-safety:free", result)
        self.assertNotIn("nvidia/nemotron-nano-12b-v2-vl:free", result)
        self.assertIn("google/gemini-2.0-flash-exp:free", result)
        self.assertIn("qwen/qwen2.5-vl-72b-instruct:free", result)

    def test_preferred_models_sorted_first(self):
        """Preferred models should appear before non-preferred in the list."""
        from app import FreeModelRotator
        rotator = FreeModelRotator(api_key="fake", base_url="https://openrouter.ai/api/v1")

        models = [
            "random/unknown-vision:free",
            "google/gemini-2.0-flash-exp:free",
            "another/random-vl:free",
            "qwen/qwen2.5-vl-72b-instruct:free",
        ]
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = self._make_api_response(models)

        with patch("requests.get", return_value=mock_resp):
            result = rotator._fetch_vision_free_models()

        # Preferred models should come first
        preferred_indices = [i for i, m in enumerate(result) if m in FreeModelRotator._VISION_PREFERRED]
        non_preferred_indices = [i for i, m in enumerate(result) if m not in FreeModelRotator._VISION_PREFERRED]
        if preferred_indices and non_preferred_indices:
            self.assertLess(max(preferred_indices), min(non_preferred_indices))

    def test_empty_api_response_returns_empty(self):
        """If API returns no vision models, result should be empty list."""
        from app import FreeModelRotator
        rotator = FreeModelRotator(api_key="fake", base_url="https://openrouter.ai/api/v1")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": []}

        with patch("requests.get", return_value=mock_resp):
            result = rotator._fetch_vision_free_models()

        self.assertEqual(result, [])

    def test_api_error_uses_fallback(self):
        """If API request fails, fallback list should be used."""
        from app import FreeModelRotator
        rotator = FreeModelRotator(api_key="fake", base_url="https://openrouter.ai/api/v1")

        with patch("requests.get", side_effect=Exception("Connection error")):
            result = rotator._fetch_vision_free_models()

        self.assertEqual(result, ["google/gemini-2.0-flash-exp:free"])


if __name__ == "__main__":
    unittest.main()
