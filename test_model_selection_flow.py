"""Regression tests for model selection flow.

Seam: set_selected_model(model_id) → _selected_model → call_with_fallback uses it.

Tests that the model selected by the user is the one actually used by the LLM,
not the default openrouter/free.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("OPENROUTER_API_KEY", "test-key-fake")
os.environ.setdefault("LLM_PROVIDER", "openrouter")
os.environ.setdefault("LLM_API_KEY", "test-key-fake")
os.environ.setdefault("LLM_BASE_URL", "https://openrouter.ai/api/v1")
os.environ.setdefault("LOCAL_LLM_FALLBACK", "false")


class TestModelSelectionFlow(unittest.TestCase):
    """When user selects a model, LLMManager must use it, not the default."""

    def test_set_selected_model_updates_internal_state(self):
        """set_selected_model should update _selected_model."""
        from app import LLMManager
        mgr = LLMManager()
        mgr.set_selected_model("anthropic/claude-sonnet-4.5")
        self.assertEqual(mgr._selected_model, "anthropic/claude-sonnet-4.5")

    def test_selected_model_overrides_default_in_routing(self):
        """_is_free_routing should return False when a non-free model is selected."""
        from app import LLMManager
        mgr = LLMManager()
        mgr.set_selected_model("anthropic/claude-sonnet-4.5")
        self.assertFalse(mgr._is_free_routing())

    def test_selected_model_used_in_call_with_fallback(self):
        """call_with_fallback should use _selected_model, not _default_model."""
        from app import LLMManager
        mgr = LLMManager()
        mgr.set_selected_model("anthropic/claude-sonnet-4.5")

        captured_model = []

        def mock_create(**kwargs):
            captured_model.append(kwargs.get("model", ""))
            mock_resp = MagicMock()
            mock_resp.choices = [MagicMock()]
            mock_resp.choices[0].message.content = "Response from selected model"
            mock_resp.usage = MagicMock()
            return mock_resp

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = mock_create

        with patch("openai.OpenAI", return_value=mock_client):
            result = mgr.call_with_fallback("test prompt")

        self.assertEqual(result, "Response from selected model")
        self.assertEqual(captured_model[0], "anthropic/claude-sonnet-4.5")

    def test_default_model_used_when_no_selection(self):
        """call_with_fallback should use _default_model when no model is selected."""
        from app import LLMManager
        mgr = LLMManager()
        # Don't set selected model — should default to openrouter/free
        self.assertEqual(mgr._selected_model, "")

        captured_model = []

        def mock_create(**kwargs):
            captured_model.append(kwargs.get("model", ""))
            mock_resp = MagicMock()
            mock_resp.choices = [MagicMock()]
            mock_resp.choices[0].message.content = "Response from default"
            mock_resp.usage = MagicMock()
            return mock_resp

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = mock_create

        with patch("openai.OpenAI", return_value=mock_client):
            result = mgr.call_with_fallback("test prompt")

        self.assertEqual(result, "Response from default")
        self.assertEqual(captured_model[0], "openrouter/free")

    def test_get_selected_model_name_returns_selected(self):
        """get_selected_model_name should return _selected_model."""
        from app import LLMManager
        mgr = LLMManager()
        mgr.set_selected_model("openai/gpt-5.6-luna")
        name = mgr.get_selected_model_name()
        self.assertEqual(name, "openai/gpt-5.6-luna")


class TestPlanApprovalModelPropagation(unittest.TestCase):
    """When a plan includes manager_model, it must propagate to model_assignment."""

    def test_plan_with_manager_model_propagates_to_assignment(self):
        """assess_and_plan should use manager_model from AI response in model_assignment."""
        import asyncio
        import json
        from app import CentralSecretary, LLMManager
        from unittest.mock import AsyncMock

        llm_mgr = MagicMock(spec=LLMManager)
        llm_mgr._selected_model = "openrouter/free"
        llm_mgr._default_model = "openrouter/free"
        llm_mgr._is_openrouter = MagicMock(return_value=True)

        plan_response = json.dumps({
            "action": "plan",
            "summary": "Test plan",
            "agents": [{
                "name": "Writer",
                "role": "Writer",
                "goal": "Write",
                "backstory": "Writer",
                "tools": [],
                "task_description": "Write 1 post",
                "depends_on": [],
                "model": "openai/gpt-5.6-luna",
            }],
            "manager_model": "anthropic/claude-sonnet-4.5",
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
                "สร้าง content plan",
                stream_callback=AsyncMock(),
            )
        )

        self.assertEqual(result["action"], "plan")
        model_assignment = result.get("model_assignment", {})
        self.assertEqual(
            model_assignment.get("manager"),
            "anthropic/claude-sonnet-4.5",
            "manager_model from AI response must propagate to model_assignment"
        )
        self.assertEqual(
            model_assignment.get("workers", {}).get("Writer"),
            "openai/gpt-5.6-luna",
        )

    def test_plan_without_manager_model_defaults_to_free(self):
        """If AI doesn't specify manager_model, should default to openrouter/free."""
        import asyncio
        import json
        from app import CentralSecretary, LLMManager
        from unittest.mock import AsyncMock

        llm_mgr = MagicMock(spec=LLMManager)
        llm_mgr._selected_model = "openrouter/free"
        llm_mgr._default_model = "openrouter/free"
        llm_mgr._is_openrouter = MagicMock(return_value=True)

        plan_response = json.dumps({
            "action": "plan",
            "summary": "Test plan",
            "agents": [{
                "name": "Writer",
                "role": "Writer",
                "goal": "Write",
                "backstory": "Writer",
                "tools": [],
                "task_description": "Write 1 post",
                "depends_on": [],
                "model": "",
            }],
        })

        def stream(prompt, **kwargs):
            yield plan_response

        llm_mgr.call_streaming = stream
        llm_mgr.call_async = AsyncMock(return_value=plan_response)

        secretary = CentralSecretary(llm_mgr)
        result = asyncio.run(
            secretary.assess_and_plan(
                "สร้าง content plan",
                stream_callback=AsyncMock(),
            )
        )

        self.assertEqual(result["action"], "plan")
        model_assignment = result.get("model_assignment", {})
        self.assertEqual(model_assignment.get("manager"), "openrouter/free")


class TestModelCatalogMessenger(unittest.TestCase):
    """Model catalog must include the selected model in the response."""

    def test_reply_model_catalog_includes_selected_model(self):
        """reply_model_catalog should send the selected_model to frontend."""
        import asyncio
        from app import StateMessenger
        from unittest.mock import AsyncMock, MagicMock

        mock_task_store = MagicMock()
        mock_task_store.list_tasks.return_value = []
        mock_chat_store = MagicMock()
        mock_chat_store.list_sessions.return_value = []

        messenger = StateMessenger(task_store=mock_task_store, chat_store=mock_chat_store)

        mock_msg = MagicMock()
        mock_msg.send = AsyncMock()

        with patch("chainlit.Message", return_value=mock_msg):
            asyncio.run(
                messenger.reply_model_catalog(
                    recommended={"openai": [{"id": "openai/gpt-5.6-luna", "name": "GPT 5.6 Luna"}]},
                    search_results=[],
                    selected_model="openai/gpt-5.6-luna",
                )
            )

        mock_msg.send.assert_called_once()


if __name__ == "__main__":
    unittest.main(verbosity=2)
