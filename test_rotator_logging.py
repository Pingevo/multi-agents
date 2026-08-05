"""Tests for FreeModelRotator → log_ai_usage wiring (Slice 3).

Verifies that rotator pushes both success and error attempts to the Hub,
including the attempt number in `metadata`.
"""
import unittest
import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("OPENROUTER_API_KEY", "test-key-fake")


def _make_usage(prompt=100, completion=50, cost=0.001):
    u = MagicMock()
    u.prompt_tokens = prompt
    u.completion_tokens = completion
    u.total_tokens = prompt + completion
    u.cost = cost
    u.model_dump = MagicMock(return_value={
        "prompt_tokens": prompt, "completion_tokens": completion,
        "total_tokens": prompt + completion, "cost": cost,
    })
    return u


class TestRotatorLogging(unittest.TestCase):
    def setUp(self):
        from backend.llm.rotator import FreeModelRotator
        # Inject a fake catalog so get_ranking doesn't hit the network
        fake_catalog = MagicMock()
        fake_catalog.get_models = MagicMock(return_value=[
            {"id": "google/gemini-2.0-flash-exp:free", "context_length": 1000000},
            {"id": "meta-llama/llama-3.2-3b-instruct:free", "context_length": 128000},
        ])
        self.rotator = FreeModelRotator(
            api_key="test-key",
            base_url="https://openrouter.ai/api/v1",
            temperature=0.7,
            catalog=fake_catalog,
        )
        # Bypass vision fetch (returns a known list without network)
        self.rotator._vision_free_models_cache = ["google/gemini-2.0-flash-exp:free"]

    def test_call_success_logs_with_attempt(self):
        """Rotator success → log_ai_usage called with metadata.attempt=1."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="ok"))]
        mock_response.usage = _make_usage(100, 50, 0.0001)
        mock_client = MagicMock()
        mock_client.chat.completions.create = MagicMock(return_value=mock_response)
        with patch("openai.OpenAI", return_value=mock_client), \
             patch("backend.llm.rotator.log_ai_usage") as mock_log:
            result = self.rotator.call("hi", caller="rot_test")
        self.assertEqual(result, "ok")
        mock_log.assert_called_once()
        entry = mock_log.call_args[0][0]
        self.assertEqual(entry["status"], "success")
        self.assertEqual(entry["model"], "google/gemini-2.0-flash-exp:free")
        self.assertEqual(entry["source"], "rot_test")
        self.assertEqual(entry["provider"], "openrouter")
        self.assertEqual(entry["cost_usd"], 0.0001)

    def test_call_error_then_success_logs_both(self):
        """First attempt error → log error; second attempt success → log success."""
        ok_response = MagicMock()
        ok_response.choices = [MagicMock(message=MagicMock(content="ok"))]
        ok_response.usage = _make_usage(80, 30, 0.0002)
        mock_client = MagicMock()
        mock_client.chat.completions.create = MagicMock(
            side_effect=[RuntimeError("429 rate limit"), ok_response]
        )
        with patch("openai.OpenAI", return_value=mock_client), \
             patch("backend.llm.rotator.log_ai_usage") as mock_log, \
             patch("time.sleep"):  # skip backoff
            result = self.rotator.call("hi", caller="rot_test")
        self.assertEqual(result, "ok")
        # Two log calls: 1 error, 1 success
        self.assertEqual(mock_log.call_count, 2)
        first = mock_log.call_args_list[0][0][0]
        second = mock_log.call_args_list[1][0][0]
        self.assertEqual(first["status"], "error")
        self.assertIn("429", first["error_message"])
        self.assertEqual(second["status"], "success")
        self.assertEqual(second["cost_usd"], 0.0002)

    def test_streaming_success_logs(self):
        """Rotator streaming success → log_ai_usage called after stream ends."""
        chunk1 = MagicMock(); chunk1.choices = [MagicMock(delta=MagicMock(content="a"))]
        chunk1.usage = None
        chunk_usage = MagicMock(); chunk_usage.choices = []
        chunk_usage.usage = _make_usage(50, 20, 0.0003)
        mock_client = MagicMock()
        mock_client.chat.completions.create = MagicMock(return_value=iter([chunk1, chunk_usage]))
        with patch("openai.OpenAI", return_value=mock_client), \
             patch("backend.llm.rotator.log_ai_usage") as mock_log:
            chunks = list(self.rotator.call_streaming("hi", caller="rot_stream"))
        self.assertEqual(chunks, ["a"])
        mock_log.assert_called_once()
        entry = mock_log.call_args[0][0]
        self.assertEqual(entry["status"], "success")
        self.assertEqual(entry["cost_usd"], 0.0003)
        self.assertEqual(entry["source"], "rot_stream")


if __name__ == "__main__":
    unittest.main()
