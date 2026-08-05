"""Tests for LLMManager → log_ai_usage wiring (Slice 2).

Verifies that call_with_fallback pushes the right fields to the Hub,
including the error path that was previously unlogged.
"""
import unittest
import sys
import os
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("OPENROUTER_API_KEY", "test-key-fake")


def _make_usage(prompt=100, completion=50, cost=0.001):
    """Build a usage object that looks like OpenAI CompletionUsage."""
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


class TestCallWithFallbackLogging(unittest.TestCase):
    def setUp(self):
        from backend.llm.manager import LLMManager
        self.mgr = LLMManager.__new__(LLMManager)
        self.mgr._selected_model = ""
        self.mgr._default_model = "openrouter/free"
        self.mgr.provider = "openrouter"
        self.mgr.api_key = "test-key"
        self.mgr.base_url = "https://openrouter.ai/api/v1"
        self.mgr.temperature = 0.7
        self.mgr._rotator = None
        self.mgr.local_fallback_enabled = False
        self.mgr._fallback_until = 0.0
        self.mgr._fallback_cooldown = 60.0
        self.mgr._max_attempts = 4
        self.mgr.fallback_provider = "local"
        self.mgr.fallback_model = "qwen2.5:7b"
        self.mgr.fallback_base_url = "http://localhost:11434"
        self.mgr.fallback_api_key = "ollama"

    def _openai_client_returning(self, content="hello", usage=None):
        """Build a mock OpenAI client whose chat.completions.create returns content."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content=content))]
        mock_response.usage = usage or _make_usage()
        mock_client = MagicMock()
        mock_client.chat.completions.create = MagicMock(return_value=mock_response)
        return mock_client

    def test_success_path_logs_to_hub(self):
        """call_with_fallback success → log_ai_usage called with model, tokens, cost, status=success."""
        mock_client = self._openai_client_returning("hello world", _make_usage(100, 50, 0.002))
        with patch("openai.OpenAI", return_value=mock_client), \
             patch("backend.llm.manager.log_ai_usage") as mock_log:
            result = self.mgr.call_with_fallback("test prompt", caller="myCaller")
        self.assertEqual(result, "hello world")
        mock_log.assert_called_once()
        entry = mock_log.call_args[0][0]
        self.assertEqual(entry["provider"], "openrouter")
        self.assertEqual(entry["model"], "openrouter/free")
        self.assertEqual(entry["source"], "myCaller")
        self.assertEqual(entry["status"], "success")
        self.assertEqual(entry["prompt_tokens"], 100)
        self.assertEqual(entry["completion_tokens"], 50)
        self.assertEqual(entry["cost_usd"], 0.002)
        self.assertIn("duration_ms", entry)

    def test_error_path_logs_to_hub(self):
        """call_with_fallback error → log_ai_usage called with status=error and error_message."""
        mock_client = MagicMock()
        mock_client.chat.completions.create = MagicMock(side_effect=RuntimeError("502 Bad Gateway"))
        with patch("openai.OpenAI", return_value=mock_client), \
             patch("backend.llm.manager.log_ai_usage") as mock_log:
            with self.assertRaises(RuntimeError):
                self.mgr.call_with_fallback("test prompt", caller="myCaller")
        # Should have logged the error
        error_calls = [c for c in mock_log.call_args_list if c[0][0].get("status") == "error"]
        self.assertEqual(len(error_calls), 1, f"expected 1 error log, got {mock_log.call_args_list}")
        entry = error_calls[0][0][0]
        self.assertEqual(entry["provider"], "openrouter")
        self.assertEqual(entry["model"], "openrouter/free")
        self.assertEqual(entry["source"], "myCaller")
        self.assertEqual(entry["status"], "error")
        self.assertIn("502", entry["error_message"])

    def test_streaming_success_logs_to_hub(self):
        """call_streaming success → log_ai_usage called after stream completes."""
        # Build a mock stream that yields chunks then a usage chunk
        chunk1 = MagicMock(); chunk1.choices = [MagicMock(delta=MagicMock(content="chunk1"))]
        chunk1.usage = None
        chunk2 = MagicMock(); chunk2.choices = [MagicMock(delta=MagicMock(content="chunk2"))]
        chunk2.usage = None
        chunk_usage = MagicMock(); chunk_usage.choices = []
        chunk_usage.usage = _make_usage(200, 80, 0.003)
        mock_stream = iter([chunk1, chunk2, chunk_usage])
        mock_client = MagicMock()
        mock_client.chat.completions.create = MagicMock(return_value=mock_stream)
        with patch("openai.OpenAI", return_value=mock_client), \
             patch("backend.llm.manager.log_ai_usage") as mock_log:
            chunks = list(self.mgr.call_streaming("test prompt", caller="streamCaller"))
        self.assertEqual(chunks, ["chunk1", "chunk2"])
        mock_log.assert_called_once()
        entry = mock_log.call_args[0][0]
        self.assertEqual(entry["model"], "openrouter/free")
        self.assertEqual(entry["source"], "streamCaller")
        self.assertEqual(entry["status"], "success")
        self.assertEqual(entry["prompt_tokens"], 200)
        self.assertEqual(entry["completion_tokens"], 80)
        self.assertEqual(entry["cost_usd"], 0.003)


if __name__ == "__main__":
    unittest.main()
