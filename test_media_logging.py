"""Tests for MediaGenerationManager → log_ai_usage wiring (Slice 4).

Covers image, video, TTS, STT, vision — all 5 OpenRouter endpoints that
previously had no Hub logging (image/video had partial log_llm_call, TTS/STT/
vision had none).
"""
import unittest
import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("OPENROUTER_API_KEY", "test-key-fake")


class _FakeResp:
    def __init__(self, status=200, json_data=None, content=b"", headers=None):
        self.status_code = status
        self._json = json_data or {}
        self.content = content
        self.text = str(json_data)
        self.headers = headers or {}
    def json(self):
        return self._json


class TestMediaLogging(unittest.TestCase):
    def setUp(self):
        from backend.media.manager import MediaGenerationManager
        llm = MagicMock()
        llm.api_key = "test-key"
        llm.base_url = "https://openrouter.ai/api/v1"
        self.mgr = MediaGenerationManager.__new__(MediaGenerationManager)
        self.mgr.openrouter_key = "test-key"
        self.mgr.openrouter_base = "https://openrouter.ai/api/v1"
        self.mgr.image_model = "google/gemini-2.5-flash-image"
        self.mgr.video_model = "google/veo-3"
        self.mgr.tts_model = "openai/tts-1"
        self.mgr.stt_model = "openai/whisper-1"
        self.mgr.vision_model = "google/gemini-2.5-flash"
        self.mgr.gen_dir = "/tmp/test_media"
        self.mgr.base_url = "/api/media/generated"
        import os as _os
        _os.makedirs(self.mgr.gen_dir, exist_ok=True)

    def test_image_success_logs_cost(self):
        """Image generation success → log_ai_usage with cost_usd from response."""
        resp = _FakeResp(200, {
            "cost": 0.05,
            "data": [{"b64_json": "iVBORw0KGgo=", "media_type": "image/png"}],
        })
        with patch("backend.media.manager.requests.post", return_value=resp), \
             patch("backend.media.manager.log_ai_usage") as mock_log:
            self.mgr.generate_image("a cat")
        mock_log.assert_called_once()
        entry = mock_log.call_args[0][0]
        self.assertEqual(entry["provider"], "openrouter")
        self.assertEqual(entry["model"], "google/gemini-2.5-flash-image")
        self.assertEqual(entry["operation"], "image.generate")
        self.assertEqual(entry["source"], "generate_image")
        self.assertEqual(entry["status"], "success")
        self.assertEqual(entry["cost_usd"], 0.05)

    def test_image_error_logs_error(self):
        """Image generation error → log_ai_usage with status=error."""
        resp = _FakeResp(402, {"error": "insufficient credits"})
        with patch("backend.media.manager.requests.post", return_value=resp), \
             patch("backend.media.manager.log_ai_usage") as mock_log:
            result = self.mgr.generate_image("a cat")
        self.assertTrue(result.startswith("Error:"))
        mock_log.assert_called_once()
        entry = mock_log.call_args[0][0]
        self.assertEqual(entry["status"], "error")
        self.assertEqual(entry["http_status"], 402)
        self.assertIn("insufficient credits", entry["error_message"])

    def test_tts_success_logs(self):
        """TTS success → log_ai_usage called (previously unlogged)."""
        resp = _FakeResp(200, content=b"audio-bytes")
        with patch("backend.media.manager.requests.post", return_value=resp), \
             patch("backend.media.manager.log_ai_usage") as mock_log:
            self.mgr.generate_tts("hello world")
        mock_log.assert_called_once()
        entry = mock_log.call_args[0][0]
        self.assertEqual(entry["operation"], "audio.speech")
        self.assertEqual(entry["source"], "generate_tts")
        self.assertEqual(entry["status"], "success")

    def test_vision_success_logs(self):
        """Vision success → log_ai_usage called (previously unlogged)."""
        resp = _FakeResp(200, {
            "usage": {"prompt_tokens": 50, "completion_tokens": 20, "cost": 0.001},
            "choices": [{"message": {"content": "it's a cat"}}],
        })
        with patch("backend.media.manager.requests.post", return_value=resp), \
             patch("backend.media.manager.log_ai_usage") as mock_log:
            self.mgr.generate_vision("https://example.com/cat.png", "what is this?")
        mock_log.assert_called_once()
        entry = mock_log.call_args[0][0]
        self.assertEqual(entry["operation"], "chat.completions")
        self.assertEqual(entry["source"], "generate_vision")
        self.assertEqual(entry["cost_usd"], 0.001)


if __name__ == "__main__":
    unittest.main()
