"""Integration tests with mocked OpenRouter API.

Tests the full LLM pipeline: LLMManager → FreeModelRotator → ModelSelector → CentralSecretary.
All HTTP calls to OpenRouter are mocked — no real API calls are made.
"""

import unittest
import asyncio
import json
import os
import sys
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("OPENROUTER_API_KEY", "test-key-fake")
os.environ.setdefault("LLM_PROVIDER", "openrouter")
os.environ.setdefault("LLM_API_KEY", "test-key-fake")
os.environ.setdefault("LLM_BASE_URL", "https://openrouter.ai/api/v1")
os.environ.setdefault("LOCAL_LLM_FALLBACK", "false")


def _mock_models_response():
    """Return a MagicMock that simulates OpenRouter /models endpoint."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "data": [
            {
                "id": "meta-llama/llama-3.3-70b-instruct:free",
                "context_length": 131072,
                "pricing": {"prompt": "0", "completion": "0"},
                "description": "Llama 3.3 70B Instruct (free)",
                "supported_parameters": ["tools", "temperature"],
                "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
            },
            {
                "id": "openai/gpt-oss-120b:free",
                "context_length": 131072,
                "pricing": {"prompt": "0", "completion": "0"},
                "description": "GPT-OSS 120B (free)",
                "supported_parameters": ["tools", "temperature"],
                "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
            },
            {
                "id": "meta-llama/llama-3.2-3b-instruct:free",
                "context_length": 131072,
                "pricing": {"prompt": "0", "completion": "0"},
                "description": "Llama 3.2 3B (free, small)",
                "supported_parameters": ["tools", "temperature"],
                "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
            },
        ]
    }
    return resp


def _mock_credits_response(credits: float = 10.0):
    """Return a MagicMock that simulates OpenRouter /credits endpoint."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "data": {
            "total_credits": credits,
            "limit": 100.0,
            "limit_remaining": 90.0,
            "usage": 10.0,
            "usage_daily": 1.0,
            "usage_monthly": 5.0,
            "is_free_tier": credits == 0,
        }
    }
    return resp


class TestLLMManagerTierDetection(unittest.TestCase):
    """LLMManager defaults to free routing model, no tier concept."""

    def test_default_model_is_free(self):
        from app import LLMManager
        mgr = LLMManager()
        self.assertEqual(mgr._default_model, "openrouter/free")

    def test_user_can_select_paid_model(self):
        from app import LLMManager
        mgr = LLMManager()
        mgr.set_selected_model("openrouter/auto")
        self.assertEqual(mgr._selected_model, "openrouter/auto")

    def test_user_can_select_free_model(self):
        from app import LLMManager
        mgr = LLMManager()
        mgr.set_selected_model("openrouter/free")
        self.assertEqual(mgr._selected_model, "openrouter/free")


class TestLLMManagerCallWithFallback(unittest.TestCase):
    """LLMManager.call_with_fallback tries primary model, falls back on error."""

    @patch("openai.OpenAI")
    def test_returns_primary_response_on_success(self, mock_openai):
        from app import LLMManager
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello from LLM"
        mock_response.usage = MagicMock()
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client
        mgr = LLMManager()
        result = mgr.call_with_fallback("test prompt")
        self.assertEqual(result, "Hello from LLM")

    @patch("openai.OpenAI")
    def test_raises_on_primary_failure_without_fallback(self, mock_openai):
        from app import LLMManager
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("502 Bad Gateway")
        mock_openai.return_value = mock_client
        mgr = LLMManager()
        mgr.local_fallback_enabled = False

        with self.assertRaises(RuntimeError) as ctx:
            mgr.call_with_fallback("test prompt")
        self.assertIn("502", str(ctx.exception))


class TestFreeModelRotatorIntegration(unittest.TestCase):
    """FreeModelRotator fetches and filters free models from OpenRouter."""

    def test_fetch_free_models_filters_small_and_non_chat(self):
        """Dynamic ranking returns only free models from the catalog (issue #125).

        No longer asserts specific slugs — OpenRouter retires free models
        over time. The contract is: all returned slugs have ':free' suffix
        and actually exist in the catalog.
        """
        from app import FreeModelRotator

        # Inject a realistic catalog so the test is deterministic (no HTTP)
        fake_catalog = type("FakeCatalog", (), {
            "get_models": lambda self: [
                {"id": "google/gemini-2.0-flash-exp:free", "context_length": 1048576, "architecture": {"input_modalities": ["text", "image"]}},
                {"id": "meta-llama/llama-3.3-70b-instruct:free", "context_length": 131072, "architecture": {"input_modalities": ["text"]}},
                {"id": "anthropic/claude-sonnet-5", "context_length": 200000, "architecture": {"input_modalities": ["text", "image"]}},
            ]
        })()
        rotator = FreeModelRotator(
            api_key="fake", base_url="https://openrouter.ai/api/v1",
            catalog=fake_catalog,
        )
        models = rotator.get_ranking()
        self.assertGreater(len(models), 0)
        self.assertTrue(all(":free" in m for m in models))
        # Paid models must NOT appear
        self.assertNotIn("anthropic/claude-sonnet-5", models)
        # Stale slugs (retired by OpenRouter) must NOT appear
        self.assertNotIn("deepseek/deepseek-r1:free", models)
        self.assertNotIn("openai/gpt-oss-120b:free", models)

    def test_call_rotates_on_failure(self):
        """FreeModelRotator.call should rotate to next model on failure."""
        from app import FreeModelRotator

        # Inject catalog so get_ranking() doesn't hit the network
        fake_catalog = type("FakeCatalog", (), {
            "get_models": lambda self: [
                {"id": "google/gemini-2.0-flash-exp:free", "context_length": 1048576, "architecture": {"input_modalities": ["text", "image"]}},
                {"id": "meta-llama/llama-3.3-70b-instruct:free", "context_length": 131072, "architecture": {"input_modalities": ["text"]}},
            ]
        })()
        rotator = FreeModelRotator(
            api_key="fake", base_url="https://openrouter.ai/api/v1",
            catalog=fake_catalog,
        )

        # Mock the OpenAI client to fail first, succeed second
        call_count = [0]
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello from model-b"
        mock_response.usage = MagicMock()

        def mock_create(**kwargs):
            call_count[0] += 1
            if call_count[0] <= 1:
                raise Exception("502 Bad Gateway")
            return mock_response

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = mock_create

        with patch("openai.OpenAI", return_value=mock_client):
            result = rotator.call("hi", max_attempts=3)
        self.assertEqual(result, "Hello from model-b")


class TestModelSelectorIntegration(unittest.TestCase):
    """ModelSelector uses rotator to get candidates and LLM to assign models."""

    @patch("backend.llm.manager.requests.get")
    def test_fetch_candidates_from_rotator(self, mock_get):
        from app import ModelSelector
        mock_rotator = MagicMock()
        mock_rotator.get_models.return_value = [
            "meta-llama/llama-3.3-70b-instruct:free",
            "openai/gpt-oss-120b:free",
        ]
        selector = ModelSelector(
            api_key="fake", base_url="https://openrouter.ai/api/v1", rotator=mock_rotator
        )
        candidates = selector._fetch_candidates()
        self.assertEqual(len(candidates), 2)
        for c in candidates:
            self.assertIn(":free", c["id"])
        mock_rotator.get_models.assert_called_once()

    @patch("backend.llm.manager.requests.get")
    def test_assign_models_returns_mapping(self, mock_get):
        from app import ModelSelector
        mock_rotator = MagicMock()
        mock_rotator.pick_smartest_model.return_value = "openai/gpt-oss-120b:free"
        selector = ModelSelector(
            api_key="fake", base_url="https://openrouter.ai/api/v1", rotator=mock_rotator
        )
        selector._candidates = [
            {"id": "openai/gpt-oss-120b:free", "context_length": 131072,
             "pricing": {"prompt": "0", "completion": "0"}, "description": "GPT-OSS 120B"},
            {"id": "meta-llama/llama-3.3-70b-instruct:free", "context_length": 131072,
             "pricing": {"prompt": "0", "completion": "0"}, "description": "Llama 3.3 70B"},
        ]

        llm_response = json.dumps({
            "manager": "openai/gpt-oss-120b:free",
            "workers": {"Writer": "meta-llama/llama-3.3-70b-instruct:free"},
        })
        mock_llm = MagicMock()
        mock_llm.call.return_value = llm_response

        with patch("app.LLM", return_value=mock_llm):
            result = selector.assign_models(
                [{"name": "Writer", "role": "Content Writer", "goal": "Write content",
                  "tools": [], "task_description": "Write 1 post"}],
                manager_goal="Create content plan",
            )

        self.assertEqual(result["manager"], "openai/gpt-oss-120b:free")
        self.assertEqual(result["workers"]["Writer"], "meta-llama/llama-3.3-70b-instruct:free")


class TestCentralSecretaryIntegration(unittest.TestCase):
    """CentralSecretary.assess_and_plan parses LLM JSON response into plan action."""

    def test_plan_response_with_agent(self):
        from app import CentralSecretary, LLMManager

        llm_mgr = MagicMock(spec=LLMManager)
        llm_mgr._selected_model = "openrouter/free"
        llm_mgr._default_model = "openrouter/auto"
        llm_mgr._is_openrouter = MagicMock(return_value=True)

        plan_response = json.dumps({
            "action": "plan",
            "summary": "Create 1 coffee shop post",
            "agents": [{
                "name": "Writer",
                "role": "Content Writer",
                "goal": "Write engaging content",
                "backstory": "Experienced copywriter",
                "tools": [],
                "task_description": "Write 1 engaging caption for a coffee shop post",
                "depends_on": [],
                "model": "openai/gpt-oss-120b:free",
            }],
            "manager_model": "openai/gpt-oss-120b:free",
            "image_model": "",
            "video_model": "",
            "search_model": "",
        })

        def stream(prompt, **kwargs):
            yield plan_response

        llm_mgr.call_streaming = stream
        llm_mgr.call_async = AsyncMock(return_value=plan_response)

        secretary = CentralSecretary(llm_mgr)
        result = asyncio.run(
            secretary.assess_and_plan(
                "สร้าง content plan สำหรับร้านกาแฟ 1 โพสต์",
                stream_callback=AsyncMock(),
            )
        )

        self.assertEqual(result["action"], "plan")
        self.assertEqual(len(result["agents"]), 1)
        self.assertEqual(result["agents"][0]["name"], "Writer")

    def test_chat_response_returns_message(self):
        from app import CentralSecretary, LLMManager

        llm_mgr = MagicMock(spec=LLMManager)
        llm_mgr._selected_model = "openrouter/free"
        llm_mgr._default_model = "openrouter/auto"
        llm_mgr._is_openrouter = MagicMock(return_value=True)

        chat_response = json.dumps({
            "action": "chat",
            "message": "สวัสดีครับ ผมช่วยอะไรได้บ้าง?",
        })

        def stream(prompt, **kwargs):
            yield chat_response

        llm_mgr.call_streaming = stream
        llm_mgr.call_async = AsyncMock(return_value=chat_response)

        secretary = CentralSecretary(llm_mgr)
        result = asyncio.run(
            secretary.assess_and_plan(
                "สวัสดี",
                stream_callback=AsyncMock(),
            )
        )

        self.assertEqual(result["action"], "chat")
        self.assertIn("สวัสดี", result["message"])

    def test_empty_stream_returns_error(self):
        from app import CentralSecretary, LLMManager

        llm_mgr = MagicMock(spec=LLMManager)
        llm_mgr._selected_model = "openrouter/free"
        llm_mgr._default_model = "openrouter/auto"
        llm_mgr._is_openrouter = MagicMock(return_value=True)

        def empty_stream(prompt, **kwargs):
            yield from ()

        llm_mgr.call_streaming = empty_stream
        llm_mgr.call_async = AsyncMock(return_value="")

        secretary = CentralSecretary(llm_mgr)
        result = asyncio.run(
            secretary.assess_and_plan(
                "สร้าง content plan",
                stream_callback=AsyncMock(),
            )
        )

        self.assertEqual(result["action"], "chat")
        self.assertIn("ว่างเปล่า", result["message"])

    def test_timeout_on_blocking_stream(self):
        from app import CentralSecretary, LLMManager

        llm_mgr = MagicMock(spec=LLMManager)
        llm_mgr._selected_model = "openrouter/free"
        llm_mgr._default_model = "openrouter/auto"
        llm_mgr._is_openrouter = MagicMock(return_value=True)

        def timeout_stream(prompt, **kwargs):
            raise TimeoutError("Request timed out")
            yield

        llm_mgr.call_streaming = timeout_stream
        llm_mgr.call_async = AsyncMock(return_value="")

        secretary = CentralSecretary(llm_mgr)
        result = asyncio.run(
            secretary.assess_and_plan(
                "test",
                stream_callback=AsyncMock(),
            )
        )

        self.assertEqual(result["action"], "chat")
        self.assertIn("ว่างเปล่า", result["message"])


class TestEndToEndPipeline(unittest.TestCase):
    """End-to-end: rotator fetches models → selector assigns → secretary plans."""

    @patch("backend.llm.manager.requests.get")
    def test_full_pipeline_produces_plan(self, mock_get):
        from app import FreeModelRotator, ModelSelector, CentralSecretary, LLMManager

        # Mock OpenRouter API: models + credits
        def mock_get_side_effect(url, **kwargs):
            if "/models" in url:
                return _mock_models_response()
            if "/credits" in url:
                return _mock_credits_response(credits=10.0)
            return MagicMock(status_code=404)

        mock_get.side_effect = mock_get_side_effect

        # 1. LLMManager defaults to free routing model
        mgr = LLMManager()
        self.assertEqual(mgr._default_model, "openrouter/free")

        # 2. FreeModelRotator returns dynamic ranking (injected catalog — no HTTP)
        fake_catalog = type("FakeCatalog", (), {
            "get_models": lambda self: [
                {"id": "google/gemini-2.0-flash-exp:free", "context_length": 1048576, "architecture": {"input_modalities": ["text", "image"]}},
                {"id": "meta-llama/llama-3.3-70b-instruct:free", "context_length": 131072, "architecture": {"input_modalities": ["text"]}},
                {"id": "openai/gpt-oss-120b:free", "context_length": 131072, "architecture": {"input_modalities": ["text"]}},
            ]
        })()
        rotator = FreeModelRotator(
            api_key="fake", base_url="https://openrouter.ai/api/v1",
            catalog=fake_catalog,
        )
        free_models = rotator.get_ranking()
        self.assertGreater(len(free_models), 0)
        self.assertTrue(all(":free" in m for m in free_models))

        # 3. ModelSelector assigns models using rotator
        selector = ModelSelector(
            api_key="fake", base_url="https://openrouter.ai/api/v1", rotator=rotator
        )

        llm_response = json.dumps({
            "manager": "openai/gpt-oss-120b:free",
            "workers": {"Writer": "meta-llama/llama-3.3-70b-instruct:free"},
        })
        mock_llm = MagicMock()
        mock_llm.call.return_value = llm_response

        with patch("app.LLM", return_value=mock_llm):
            assignment = selector.assign_models(
                [{"name": "Writer", "role": "Writer", "goal": "Write",
                  "tools": [], "task_description": "Write 1 post"}],
                manager_goal="Create content",
            )

        self.assertEqual(assignment["manager"], "openai/gpt-oss-120b:free")
        self.assertIn("Writer", assignment["workers"])

        # 4. CentralSecretary produces a plan
        llm_mgr = MagicMock(spec=LLMManager)
        llm_mgr._selected_model = "openrouter/free"
        llm_mgr._default_model = "openrouter/auto"
        llm_mgr._is_openrouter = MagicMock(return_value=True)

        plan_json = json.dumps({
            "action": "plan",
            "summary": "Create 1 post",
            "agents": [{
                "name": "Writer", "role": "Writer", "goal": "Write",
                "backstory": "Writer", "tools": [],
                "task_description": "Write 1 post",
                "depends_on": [], "model": "openai/gpt-oss-120b:free",
            }],
            "manager_model": "openai/gpt-oss-120b:free",
            "image_model": "", "video_model": "", "search_model": "",
        })

        def stream(prompt, **kwargs):
            yield plan_json

        llm_mgr.call_streaming = stream
        llm_mgr.call_async = AsyncMock(return_value=plan_json)

        secretary = CentralSecretary(llm_mgr)
        result = asyncio.run(
            secretary.assess_and_plan(
                "สร้าง content plan",
                stream_callback=AsyncMock(),
            )
        )

        self.assertEqual(result["action"], "plan")
        self.assertEqual(len(result["agents"]), 1)
        self.assertEqual(result["agents"][0]["name"], "Writer")


if __name__ == "__main__":
    unittest.main(verbosity=2)
