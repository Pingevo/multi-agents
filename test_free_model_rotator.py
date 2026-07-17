"""Tests for FreeModelRotator — verifies hardcoded ranking, rotation, and fallback behavior."""

import unittest
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class TestFreeModelRotatorRanking(unittest.TestCase):
    """Seam: get_ranking() returns hardcoded free model list in order."""

    def test_returns_hardcoded_ranking(self):
        from app import FreeModelRotator
        rotator = FreeModelRotator(api_key="fake", base_url="https://openrouter.ai/api/v1")
        ranking = rotator.get_ranking()

        self.assertIn("deepseek/deepseek-r1:free", ranking)
        self.assertIn("meta-llama/llama-3.3-70b-instruct:free", ranking)
        self.assertEqual(ranking[0], "deepseek/deepseek-r1:free")
        self.assertEqual(ranking[-1], "meta-llama/llama-3.2-3b-instruct:free")

    def test_ranking_is_a_copy(self):
        from app import FreeModelRotator
        rotator = FreeModelRotator(api_key="fake", base_url="https://openrouter.ai/api/v1")
        r1 = rotator.get_ranking()
        r1.append("fake/model:free")
        r2 = rotator.get_ranking()
        self.assertNotIn("fake/model:free", r2)


class TestFreeModelRotatorCall(unittest.TestCase):
    """Seam: call(prompt, max_attempts) rotates through free models on failure."""

    def test_returns_first_success(self):
        from app import FreeModelRotator
        rotator = FreeModelRotator(api_key="fake", base_url="https://openrouter.ai/api/v1")

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
        rotator = FreeModelRotator(api_key="fake", base_url="https://openrouter.ai/api/v1")

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
        rotator = FreeModelRotator(api_key="fake", base_url="https://openrouter.ai/api/v1")

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


if __name__ == "__main__":
    unittest.main()
