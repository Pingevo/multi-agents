"""Tests for FreeModelRotator — verifies free model fetching, rotation, and fallback behavior."""

import unittest
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class TestFreeModelRotatorFetch(unittest.TestCase):
    """Seam: _fetch_free_models() filters :free models from OpenRouter API response."""

    def test_returns_only_free_models(self):
        from app import FreeModelRotator
        rotator = FreeModelRotator(api_key="fake", base_url="https://openrouter.ai/api/v1")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"id": "meta-llama/llama-3.3-70b-instruct:free"},
                {"id": "openai/gpt-4"},
                {"id": "qwen/qwen3-coder:free"},
                {"id": "google/gemini-pro"},
            ]
        }

        with patch("app.requests.get", return_value=mock_response):
            models = rotator._fetch_free_models()

        self.assertIn("meta-llama/llama-3.3-70b-instruct:free", models)
        self.assertIn("qwen/qwen3-coder:free", models)
        self.assertNotIn("openai/gpt-4", models)
        self.assertNotIn("google/gemini-pro", models)

    def test_filters_out_small_models(self):
        from app import FreeModelRotator
        rotator = FreeModelRotator(api_key="fake", base_url="https://openrouter.ai/api/v1")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"id": "meta-llama/llama-3.3-70b-instruct:free"},
                {"id": "meta-llama/llama-3.2-3b-instruct:free"},
                {"id": "liquid/lfm-2.5-1.2b-instruct:free"},
                {"id": "nvidia/nemotron-nano-9b-v2:free"},
                {"id": "cohere/north-mini-code:free"},
                {"id": "poolside/laguna-xs-2.1:free"},
                {"id": "openai/gpt-oss-120b:free"},
                {"id": "qwen/qwen3-coder:free"},
                {"id": "nousresearch/hermes-3-llama-3.1-405b:free"},
            ]
        }

        with patch("app.requests.get", return_value=mock_response):
            models = rotator._fetch_free_models()

        self.assertIn("meta-llama/llama-3.3-70b-instruct:free", models)
        self.assertIn("openai/gpt-oss-120b:free", models)
        self.assertIn("nousresearch/hermes-3-llama-3.1-405b:free", models)
        self.assertNotIn("meta-llama/llama-3.2-3b-instruct:free", models)
        self.assertNotIn("liquid/lfm-2.5-1.2b-instruct:free", models)
        self.assertNotIn("nvidia/nemotron-nano-9b-v2:free", models)
        self.assertNotIn("cohere/north-mini-code:free", models)
        self.assertNotIn("poolside/laguna-xs-2.1:free", models)

    def test_filters_out_non_chat_models(self):
        from app import FreeModelRotator
        rotator = FreeModelRotator(api_key="fake", base_url="https://openrouter.ai/api/v1")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"id": "nvidia/nemotron-3.5-content-safety:free"},
                {"id": "meta-llama/llama-3.3-70b-instruct:free"},
                {"id": "some-model-guard:free"},
                {"id": "openai/gpt-oss-120b:free"},
            ]
        }

        with patch("app.requests.get", return_value=mock_response):
            models = rotator._fetch_free_models()

        self.assertIn("meta-llama/llama-3.3-70b-instruct:free", models)
        self.assertIn("openai/gpt-oss-120b:free", models)
        self.assertNotIn("nvidia/nemotron-3.5-content-safety:free", models)
        self.assertNotIn("some-model-guard:free", models)

    def test_returns_empty_on_api_error(self):
        from app import FreeModelRotator
        rotator = FreeModelRotator(api_key="fake", base_url="https://openrouter.ai/api/v1")

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"error": "unauthorized"}

        with patch("app.requests.get", return_value=mock_response):
            models = rotator._fetch_free_models()

        self.assertEqual(models, [])


class TestFreeModelRotatorCall(unittest.TestCase):
    """Seam: call(prompt, max_attempts) rotates through free models on failure."""

    def test_returns_first_success(self):
        from app import FreeModelRotator
        rotator = FreeModelRotator(api_key="fake", base_url="https://openrouter.ai/api/v1")
        rotator._models = ["model-a:free", "model-b:free"]

        mock_llm = MagicMock()
        mock_llm.call.return_value = "Hello from model-a"

        with patch("app.LLM", return_value=mock_llm):
            result = rotator.call("hi", max_attempts=3)

        self.assertEqual(result, "Hello from model-a")

    def test_rotates_on_failure(self):
        from app import FreeModelRotator
        rotator = FreeModelRotator(api_key="fake", base_url="https://openrouter.ai/api/v1")
        rotator._models = ["model-a:free", "model-b:free"]

        call_count = [0]
        def mock_call(prompt):
            call_count[0] += 1
            if call_count[0] <= 1:
                raise Exception("502 Bad Gateway")
            return "Hello from model-b"

        mock_llm = MagicMock()
        mock_llm.call.side_effect = mock_call

        with patch("app.LLM", return_value=mock_llm):
            with patch("time.sleep"):  # no real sleeping in tests
                result = rotator.call("hi", max_attempts=3)

        self.assertEqual(result, "Hello from model-b")
        self.assertGreaterEqual(call_count[0], 2)

    def test_raises_after_all_attempts_fail(self):
        from app import FreeModelRotator
        rotator = FreeModelRotator(api_key="fake", base_url="https://openrouter.ai/api/v1")
        rotator._models = ["model-a:free", "model-b:free"]

        mock_llm = MagicMock()
        mock_llm.call.side_effect = Exception("502 Bad Gateway")

        with patch("app.LLM", return_value=mock_llm):
            with patch("time.sleep"):
                with self.assertRaises(RuntimeError) as ctx:
                    rotator.call("hi", max_attempts=3)

        self.assertIn("3 attempts failed", str(ctx.exception))

    def test_raises_when_no_models_available(self):
        from app import FreeModelRotator
        rotator = FreeModelRotator(api_key="fake", base_url="https://openrouter.ai/api/v1")
        rotator._models = []

        with self.assertRaises(RuntimeError) as ctx:
            rotator.call("hi", max_attempts=3)

        self.assertIn("No free models", str(ctx.exception))


class TestFreeModelRotatorPickModel(unittest.TestCase):
    """Seam: pick_model() returns a random model from the cached list."""

    def test_returns_model_from_list(self):
        from app import FreeModelRotator
        rotator = FreeModelRotator(api_key="fake", base_url="https://openrouter.ai/api/v1")
        rotator._models = ["model-a:free", "model-b:free", "model-c:free"]

        picked = rotator.pick_model()
        self.assertIn(picked, rotator._models)

    def test_returns_empty_when_no_models(self):
        from app import FreeModelRotator
        rotator = FreeModelRotator(api_key="fake", base_url="https://openrouter.ai/api/v1")
        rotator._models = []

        self.assertEqual(rotator.pick_model(), "")

    def test_pick_smartest_returns_largest_model(self):
        from app import FreeModelRotator
        rotator = FreeModelRotator(api_key="fake", base_url="https://openrouter.ai/api/v1")
        rotator._models = [
            "meta-llama/llama-3.3-70b-instruct:free",
            "openai/gpt-oss-20b:free",
            "nousresearch/hermes-3-llama-3.1-405b:free",
            "qwen/qwen3-coder:free",
        ]

        picked = rotator.pick_smartest_model()
        self.assertEqual(picked, "nousresearch/hermes-3-llama-3.1-405b:free")

    def test_pick_smartest_empty_when_no_models(self):
        from app import FreeModelRotator
        rotator = FreeModelRotator(api_key="fake", base_url="https://openrouter.ai/api/v1")
        rotator._models = []

        self.assertEqual(rotator.pick_smartest_model(), "")


if __name__ == "__main__":
    unittest.main()
