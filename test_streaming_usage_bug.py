"""Regression test: all streaming methods must call log_ai_usage even when
the stream omits usage_data.

Bug: 3 streaming methods had `if usage_data:` guards without an `else` clause.
When a model's stream doesn't include usage (some models do this), log_ai_usage
was silently skipped on success — meaning the call never reached the dashboard.

Fixed methods:
1. LLMManager.call_streaming
2. LLMManager.call_with_multimodal_streaming
3. FreeModelRotator.call_streaming

Each test mocks the OpenAI client to return a stream WITHOUT usage, then
asserts log_ai_usage was still called.
"""
import os
import unittest
from unittest.mock import MagicMock, patch


def _make_chunk(content=None, usage=None, chunk_id=None):
    """Build a fake stream chunk."""
    chunk = MagicMock()
    chunk.usage = usage
    chunk.id = chunk_id
    chunk.choices = [MagicMock()]
    chunk.choices[0].delta.content = content
    return chunk


class TestLLMManagerStreamingNoUsage(unittest.TestCase):
    def setUp(self):
        os.environ["LLM_PROVIDER"] = "openrouter"
        os.environ["LLM_BASE_URL"] = "https://openrouter.ai/api/v1"
        os.environ["LLM_API_KEY"] = "sk-fake"
        os.environ["AI_USAGE_HUB_URL"] = "https://digital.in.th"
        os.environ["AI_USAGE_HUB_TOKEN"] = "svc_" + "0" * 64

    def test_call_streaming_logs_without_usage(self):
        from backend.llm.manager import LLMManager
        mgr = LLMManager()
        fake_stream = [_make_chunk(content="hello", chunk_id="chatcmpl-1"), _make_chunk()]

        with patch("backend.llm.manager.log_ai_usage") as mock_log, \
             patch("openai.OpenAI") as mock_openai:
            mock_openai.return_value.chat.completions.create.return_value = iter(fake_stream)
            list(mgr.call_streaming("test", caller="test"))

        self.assertEqual(mock_log.call_count, 1, "log_ai_usage not called when stream omits usage")

    def test_call_with_multimodal_streaming_logs_without_usage(self):
        from backend.llm.manager import LLMManager
        mgr = LLMManager()
        fake_stream = [_make_chunk(content="hello", chunk_id="chatcmpl-1"), _make_chunk()]

        with patch("backend.llm.manager.log_ai_usage") as mock_log, \
             patch("openai.OpenAI") as mock_openai:
            mock_openai.return_value.chat.completions.create.return_value = iter(fake_stream)
            list(mgr.call_with_multimodal_streaming("test", [{"type": "text", "text": "hi"}], caller="test"))

        self.assertEqual(mock_log.call_count, 1, "log_ai_usage not called when multimodal stream omits usage")


class TestRotatorStreamingNoUsage(unittest.TestCase):
    def setUp(self):
        os.environ["LLM_PROVIDER"] = "openrouter"
        os.environ["LLM_BASE_URL"] = "https://openrouter.ai/api/v1"
        os.environ["LLM_API_KEY"] = "sk-fake"
        os.environ["AI_USAGE_HUB_URL"] = "https://digital.in.th"
        os.environ["AI_USAGE_HUB_TOKEN"] = "svc_" + "0" * 64

    def test_rotator_call_streaming_logs_without_usage(self):
        from backend.llm.rotator import FreeModelRotator
        rotator = FreeModelRotator(api_key="sk-fake", base_url="https://openrouter.ai/api/v1")
        fake_stream = [_make_chunk(content="hello", chunk_id="chatcmpl-1"), _make_chunk()]

        with patch("backend.llm.rotator.log_ai_usage") as mock_log, \
             patch("openai.OpenAI") as mock_openai:
            mock_openai.return_value.chat.completions.create.return_value = iter(fake_stream)
            list(rotator.call_streaming("test", caller="test"))

        self.assertEqual(mock_log.call_count, 1, "log_ai_usage not called when rotator stream omits usage")


if __name__ == "__main__":
    unittest.main(verbosity=2)
