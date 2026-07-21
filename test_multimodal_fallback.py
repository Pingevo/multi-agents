"""Tests for multimodal fallback: openrouter/free → rotator vision models.

When openrouter/free returns empty or fails on multimodal input (image/PDF),
the LLMManager should fall back to the FreeModelRotator's vision-capable models.
"""

import unittest
import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("OPENROUTER_API_KEY", "test-key-fake")


class TestCallWithImageFallback(unittest.TestCase):
    """_call_with_image should try openrouter/free first, then rotator on empty/error."""

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

    def test_falls_back_to_rotator_on_empty_response(self):
        """When openrouter/free returns empty content, should call rotator.call_with_image."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content=""))]
        mock_response.usage = MagicMock()

        rotator = MagicMock()
        rotator.call_with_image = MagicMock(return_value="vision result from rotator")

        with patch("openai.OpenAI") as mock_openai_class, \
             patch.object(self.mgr, "_get_rotator", return_value=rotator), \
             patch("backend.llm.manager.log_llm_call"):
            mock_client = MagicMock()
            mock_client.chat.completions.create = MagicMock(return_value=mock_response)
            mock_openai_class.return_value = mock_client

            result = self.mgr._call_with_image("describe this", "data:image/png;base64,abc")

            self.assertEqual(result, "vision result from rotator")
            rotator.call_with_image.assert_called_once()

    def test_falls_back_to_rotator_on_exception(self):
        """When openrouter/free raises an error, should call rotator.call_with_image."""
        rotator = MagicMock()
        rotator.call_with_image = MagicMock(return_value="vision result from rotator")

        with patch("openai.OpenAI") as mock_openai_class, \
             patch.object(self.mgr, "_get_rotator", return_value=rotator), \
             patch("backend.llm.manager.log_llm_call"):
            mock_client = MagicMock()
            mock_client.chat.completions.create = MagicMock(side_effect=RuntimeError("model error"))
            mock_openai_class.return_value = mock_client

            result = self.mgr._call_with_image("describe this", "data:image/png;base64,abc")

            self.assertEqual(result, "vision result from rotator")
            rotator.call_with_image.assert_called_once()

    def test_returns_content_when_non_empty(self):
        """When openrouter/free returns non-empty content, should NOT call rotator."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="good response"))]
        mock_response.usage = MagicMock()

        rotator = MagicMock()

        with patch("openai.OpenAI") as mock_openai_class, \
             patch.object(self.mgr, "_get_rotator", return_value=rotator), \
             patch("backend.llm.manager.log_llm_call"):
            mock_client = MagicMock()
            mock_client.chat.completions.create = MagicMock(return_value=mock_response)
            mock_openai_class.return_value = mock_client

            result = self.mgr._call_with_image("describe this", "data:image/png;base64,abc")

            self.assertEqual(result, "good response")
            rotator.call_with_image.assert_not_called()

    def test_no_rotator_when_not_free_routing(self):
        """When model is NOT openrouter/free, should raise instead of using rotator."""
        self.mgr._selected_model = "anthropic/claude-sonnet-5"
        self.mgr._default_model = ""

        with patch("openai.OpenAI") as mock_openai_class, \
             patch("backend.llm.manager.log_llm_call"):
            mock_client = MagicMock()
            mock_client.chat.completions.create = MagicMock(side_effect=RuntimeError("model error"))
            mock_openai_class.return_value = mock_client

            with self.assertRaises(RuntimeError):
                self.mgr._call_with_image("describe this", "data:image/png;base64,abc")


class TestCallWithMultimodalFallback(unittest.TestCase):
    """_call_with_multimodal should try openrouter/free first, then rotator on empty/error."""

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

    def test_falls_back_to_rotator_on_empty_response(self):
        """When openrouter/free returns empty content, should call rotator.call_with_multimodal."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content=""))]
        mock_response.usage = MagicMock()

        rotator = MagicMock()
        rotator.call_with_multimodal = MagicMock(return_value="multimodal result")

        content_blocks = [{"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}}]

        with patch("openai.OpenAI") as mock_openai_class, \
             patch.object(self.mgr, "_get_rotator", return_value=rotator), \
             patch("backend.llm.manager.log_llm_call"):
            mock_client = MagicMock()
            mock_client.chat.completions.create = MagicMock(return_value=mock_response)
            mock_openai_class.return_value = mock_client

            result = self.mgr._call_with_multimodal("analyze this", content_blocks)

            self.assertEqual(result, "multimodal result")
            rotator.call_with_multimodal.assert_called_once()

    def test_falls_back_to_rotator_on_exception(self):
        """When openrouter/free raises an error, should call rotator.call_with_multimodal."""
        rotator = MagicMock()
        rotator.call_with_multimodal = MagicMock(return_value="multimodal result")

        content_blocks = [{"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}}]

        with patch("openai.OpenAI") as mock_openai_class, \
             patch.object(self.mgr, "_get_rotator", return_value=rotator), \
             patch("backend.llm.manager.log_llm_call"):
            mock_client = MagicMock()
            mock_client.chat.completions.create = MagicMock(side_effect=RuntimeError("model error"))
            mock_openai_class.return_value = mock_client

            result = self.mgr._call_with_multimodal("analyze this", content_blocks)

            self.assertEqual(result, "multimodal result")
            rotator.call_with_multimodal.assert_called_once()

    def test_returns_content_when_non_empty(self):
        """When openrouter/free returns non-empty content, should NOT call rotator."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="good multimodal response"))]
        mock_response.usage = MagicMock()

        rotator = MagicMock()

        content_blocks = [{"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}}]

        with patch("openai.OpenAI") as mock_openai_class, \
             patch.object(self.mgr, "_get_rotator", return_value=rotator), \
             patch("backend.llm.manager.log_llm_call"):
            mock_client = MagicMock()
            mock_client.chat.completions.create = MagicMock(return_value=mock_response)
            mock_openai_class.return_value = mock_client

            result = self.mgr._call_with_multimodal("analyze this", content_blocks)

            self.assertEqual(result, "good multimodal response")
            rotator.call_with_multimodal.assert_not_called()


class TestRotatorVisionMethods(unittest.TestCase):
    """FreeModelRotator should have call_with_image and call_with_multimodal methods."""

    def test_rotator_has_call_with_image(self):
        from backend.llm.rotator import FreeModelRotator
        rotator = FreeModelRotator(api_key="test", base_url="https://openrouter.ai/api/v1")
        self.assertTrue(hasattr(rotator, "call_with_image"))

    def test_rotator_has_call_with_multimodal(self):
        from backend.llm.rotator import FreeModelRotator
        rotator = FreeModelRotator(api_key="test", base_url="https://openrouter.ai/api/v1")
        self.assertTrue(hasattr(rotator, "call_with_multimodal"))

    def test_rotator_has_fetch_vision_free_models(self):
        from backend.llm.rotator import FreeModelRotator
        rotator = FreeModelRotator(api_key="test", base_url="https://openrouter.ai/api/v1")
        self.assertTrue(hasattr(rotator, "_fetch_vision_free_models"))

    def test_fetch_vision_free_models_uses_api(self):
        """_fetch_vision_free_models should query OpenRouter API and filter by input_modalities."""
        from backend.llm.rotator import FreeModelRotator
        rotator = FreeModelRotator(api_key="test", base_url="https://openrouter.ai/api/v1")

        mock_api_response = {
            "data": [
                {"id": "google/gemini-2.0-flash-exp:free", "architecture": {"input_modalities": ["text", "image"]}},
                {"id": "meta-llama/llama-3.3-70b:free", "architecture": {"input_modalities": ["text"]}},
                {"id": "openrouter/free", "architecture": {"input_modalities": ["text", "image"]}},
                {"id": "qwen/qwen-vision:free", "architecture": {"input_modalities": ["text", "image"]}},
            ]
        }

        with patch("backend.llm.rotator.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_api_response
            mock_get.return_value = mock_resp

            result = rotator._fetch_vision_free_models()

            # Should include free models with image input, excluding openrouter/ routing models
            self.assertIn("google/gemini-2.0-flash-exp:free", result)
            self.assertIn("qwen/qwen-vision:free", result)
            self.assertNotIn("meta-llama/llama-3.3-70b:free", result)
            self.assertNotIn("openrouter/free", result)

    def test_fetch_vision_free_models_fallback_on_api_error(self):
        """If API fails, should fall back to a known vision model."""
        from backend.llm.rotator import FreeModelRotator
        rotator = FreeModelRotator(api_key="test", base_url="https://openrouter.ai/api/v1")

        with patch("backend.llm.rotator.requests.get", side_effect=Exception("network error")):
            result = rotator._fetch_vision_free_models()
            self.assertTrue(len(result) > 0, "Should have fallback model when API fails")


if __name__ == "__main__":
    unittest.main(verbosity=2)
