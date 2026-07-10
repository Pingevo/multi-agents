"""Tests for ModelSelector — LLM-driven model assignment per agent."""

import unittest
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class TestModelSelectorFetchCandidates(unittest.TestCase):
    """Seam: _fetch_candidates() pulls FREE models from rotator (not OpenRouter API)."""

    def test_returns_free_models_from_rotator(self):
        from app import ModelSelector
        mock_rotator = MagicMock()
        mock_rotator.get_models.return_value = [
            "meta-llama/llama-3.3-70b-instruct:free",
            "openai/gpt-oss-120b:free",
        ]
        selector = ModelSelector(api_key="fake", base_url="https://openrouter.ai/api/v1", rotator=mock_rotator)

        candidates = selector._fetch_candidates()

        self.assertEqual(len(candidates), 2)
        self.assertIn("id", candidates[0])
        self.assertIn("context_length", candidates[0])
        # All candidates must be free models
        for c in candidates:
            self.assertIn(":free", c["id"])
        mock_rotator.get_models.assert_called_once()

    def test_fetches_from_api_without_rotator(self):
        """Without rotator, _fetch_candidates fetches tool-capable models from OpenRouter API."""
        from app import ModelSelector
        selector = ModelSelector(api_key="fake", base_url="https://openrouter.ai/api/v1")

        # Mock _fetch_all_models to avoid real API call
        selector._fetch_all_models = MagicMock(return_value=[
            {"id": "model-a", "supported_parameters": ["tools"], "context_length": 131072,
             "pricing": {"prompt": "0", "completion": "0"}, "description": "Model A"},
            {"id": "model-b", "supported_parameters": [], "context_length": 8192,
             "pricing": {"prompt": "0", "completion": "0"}, "description": "Model B"},
        ])

        candidates = selector._fetch_candidates()

        # Only tool-capable models should be returned
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["id"], "model-a")


class TestModelSelectorAssignModels(unittest.TestCase):
    """Seam: assign_models(agent_specs) returns {manager: id, workers: {name: id}}."""

    def test_returns_valid_mapping_from_llm(self):
        from app import ModelSelector
        mock_rotator = MagicMock()
        mock_rotator.pick_smartest_model.return_value = "openai/gpt-oss-120b:free"
        selector = ModelSelector(api_key="fake", base_url="https://openrouter.ai/api/v1", rotator=mock_rotator)
        selector._candidates = [
            {"id": "meta-llama/llama-3.3-70b-instruct:free", "context_length": 131072},
            {"id": "openai/gpt-oss-120b:free", "context_length": 131072},
            {"id": "qwen/qwen3-coder:free", "context_length": 131072},
        ]

        llm_response = '{"manager": "openai/gpt-oss-120b:free", "workers": {"Coder": "qwen/qwen3-coder:free", "Writer": "meta-llama/llama-3.3-70b-instruct:free"}}'

        mock_llm = MagicMock()
        mock_llm.call.return_value = llm_response

        with patch("app.LLM", return_value=mock_llm):
            result = selector.assign_models(
                agent_specs=[
                    {"name": "Coder", "role": "Code Writer", "task_description": "Write code"},
                    {"name": "Writer", "role": "Content Writer", "task_description": "Write content"},
                ],
                manager_goal="Coordinate the team",
            )

        self.assertEqual(result["manager"], "openai/gpt-oss-120b:free")
        self.assertEqual(result["workers"]["Coder"], "qwen/qwen3-coder:free")
        self.assertEqual(result["workers"]["Writer"], "meta-llama/llama-3.3-70b-instruct:free")
        mock_rotator.pick_smartest_model.assert_called_once()

    def test_invalid_model_id_falls_back_to_smartest(self):
        from app import ModelSelector
        mock_rotator = MagicMock()
        mock_rotator.pick_smartest_model.return_value = "openai/gpt-oss-120b:free"
        selector = ModelSelector(api_key="fake", base_url="https://openrouter.ai/api/v1", rotator=mock_rotator)
        selector._candidates = [
            {"id": "meta-llama/llama-3.3-70b-instruct:free", "context_length": 131072},
            {"id": "openai/gpt-oss-120b:free", "context_length": 131072},
        ]

        llm_response = '{"manager": "nonexistent/model:free", "workers": {"Coder": "also-fake/model:free"}}'

        mock_llm = MagicMock()
        mock_llm.call.return_value = llm_response

        with patch("app.LLM", return_value=mock_llm):
            result = selector.assign_models(
                agent_specs=[{"name": "Coder", "role": "Coder", "task_description": "Code"}],
                manager_goal="Manage",
            )

        # Manager should get smartest model (not random)
        self.assertEqual(result["manager"], "openai/gpt-oss-120b:free")
        # Worker should get a valid model (smartest available after manager)
        valid_ids = {c["id"] for c in selector._candidates}
        self.assertIn(result["workers"]["Coder"], valid_ids)

    def test_llm_call_fails_falls_back_to_smartest(self):
        from app import ModelSelector
        mock_rotator = MagicMock()
        mock_rotator.pick_smartest_model.return_value = "openai/gpt-oss-120b:free"
        selector = ModelSelector(api_key="fake", base_url="https://openrouter.ai/api/v1", rotator=mock_rotator)
        selector._candidates = [
            {"id": "meta-llama/llama-3.3-70b-instruct:free", "context_length": 131072},
            {"id": "openai/gpt-oss-120b:free", "context_length": 131072},
        ]

        mock_llm = MagicMock()
        mock_llm.call.side_effect = Exception("API down")

        with patch("app.LLM", return_value=mock_llm):
            result = selector.assign_models(
                agent_specs=[{"name": "Coder", "role": "Coder", "task_description": "Code"}],
                manager_goal="Manage",
            )

        # Manager should get smartest model
        self.assertEqual(result["manager"], "openai/gpt-oss-120b:free")
        # Worker should get a valid model
        valid_ids = {c["id"] for c in selector._candidates}
        self.assertIn(result["workers"]["Coder"], valid_ids)

    def test_manager_always_assigned_from_candidates(self):
        from app import ModelSelector
        mock_rotator = MagicMock()
        mock_rotator.pick_smartest_model.return_value = "openai/gpt-oss-120b:free"
        selector = ModelSelector(api_key="fake", base_url="https://openrouter.ai/api/v1", rotator=mock_rotator)
        selector._candidates = [
            {"id": "meta-llama/llama-3.3-70b-instruct:free", "context_length": 131072},
            {"id": "openai/gpt-oss-120b:free", "context_length": 131072},
            {"id": "qwen/qwen3-coder:free", "context_length": 131072},
        ]

        llm_response = '{"manager": "openai/gpt-oss-120b:free", "workers": {}}'

        mock_llm = MagicMock()
        mock_llm.call.return_value = llm_response

        with patch("app.LLM", return_value=mock_llm):
            result = selector.assign_models(
                agent_specs=[],
                manager_goal="Manage",
            )

        valid_ids = {c["id"] for c in selector._candidates}
        self.assertIn(result["manager"], valid_ids)


if __name__ == "__main__":
    unittest.main()
