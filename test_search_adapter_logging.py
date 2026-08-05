"""Tests for SearchAdapter → log_ai_usage wiring (Slice 5).

SearchAdapter previously had NO logging at all. This slice adds Hub push
for both success and error paths.
"""
import unittest
import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("OPENROUTER_API_KEY", "test-key-fake")


class _FakeResp:
    def __init__(self, status=200, json_data=None):
        self.status_code = status
        self._json = json_data or {}
        self.text = str(json_data)
    def json(self):
        return self._json
    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class TestSearchAdapterLogging(unittest.TestCase):
    def setUp(self):
        from backend.tools.search_adapter import SearchAdapter
        llm = MagicMock()
        llm.base_url = "https://openrouter.ai/api/v1"
        llm.api_key = "test-key"
        self.adapter = SearchAdapter(llm_manager=llm, discovery=MagicMock())

    def test_search_success_logs(self):
        """Search success → log_ai_usage called with cost from response usage."""
        resp = _FakeResp(200, {
            "choices": [{"message": {"content": "search results here"}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "cost": 0.0002},
        })
        with patch("backend.tools.search_adapter.requests.post", return_value=resp), \
             patch("backend.tools.search_adapter.log_ai_usage") as mock_log:
            result = self.adapter.search("test query", "perplexity/sonar-pro")
        self.assertEqual(result, "search results here")
        mock_log.assert_called_once()
        entry = mock_log.call_args[0][0]
        self.assertEqual(entry["provider"], "openrouter")
        self.assertEqual(entry["model"], "perplexity/sonar-pro")
        self.assertEqual(entry["operation"], "chat.completions")
        self.assertEqual(entry["source"], "search_web")
        self.assertEqual(entry["status"], "success")
        self.assertEqual(entry["cost_usd"], 0.0002)

    def test_search_error_logs(self):
        """Search error → log_ai_usage called with status=error."""
        resp = _FakeResp(500, {"error": "server error"})
        with patch("backend.tools.search_adapter.requests.post", return_value=resp), \
             patch("backend.tools.search_adapter.log_ai_usage") as mock_log:
            with self.assertRaises(RuntimeError):
                self.adapter.search("test query", "perplexity/sonar-pro")
        mock_log.assert_called_once()
        entry = mock_log.call_args[0][0]
        self.assertEqual(entry["status"], "error")
        self.assertEqual(entry["http_status"], 500)


if __name__ == "__main__":
    unittest.main()
