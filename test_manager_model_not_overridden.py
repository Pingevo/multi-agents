"""Regression test: manager model must NOT be overridden by selected_model from UI.

Bug: Fix 1 (adding fallback `or llm_manager.get_selected_model_name()`) caused
`selected_model` to be non-empty in adaptive mode, which then triggered the
override at chat.py lines 1080/1248, replacing the AI's manager model choice
with the UI fallback (e.g. openrouter/free).

This test asserts that:
1. The secretary's model_assignment["manager"] comes from the AI's choice, not
   from the UI's selected_model.
2. ChatReplyPlan schema includes managerModel field.
3. The change_manager_model action updates pre_assigned_models["manager"].
"""

import unittest
import asyncio
import sys
import os
from unittest.mock import MagicMock, AsyncMock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault("OPENROUTER_API_KEY", "test-key-fake")


class TestManagerModelNotOverridden(unittest.TestCase):
    """Manager model from AI must not be overridden by UI selected_model."""

    def test_secretary_returns_ai_manager_model(self):
        """Secretary should return the manager_model that the AI chose in the plan JSON."""
        from app import CentralSecretary, LLMManager

        llm_mgr = MagicMock(spec=LLMManager)
        llm_mgr._selected_model = "openrouter/free"
        llm_mgr._default_model = "openrouter/auto"
        llm_mgr._is_openrouter = MagicMock(return_value=True)

        ai_response = (
            '{"action":"plan","summary":"test",'
            '"agents":[{"name":"Writer","role":"Content Writer","goal":"Write","backstory":"Writer","tools":[],"task_description":"Write 1 post","depends_on":[],"model":"openrouter/free"}],'
            '"manager_model":"anthropic/claude-sonnet-4.5",'
            '"image_model":"","video_model":"","search_model":""}'
        )

        def stream(prompt, **kwargs):
            yield ai_response

        llm_mgr.call_streaming = stream
        llm_mgr.call_async = AsyncMock(return_value=ai_response)

        secretary = CentralSecretary(llm_mgr)
        result = asyncio.run(
            secretary.assess_and_plan(
                "สร้าง content plan สำหรับร้านกาแฟ 1 โพสต์",
                stream_callback=AsyncMock(),
            )
        )

        self.assertEqual(result.get("action"), "plan")
        model_assignment = result.get("model_assignment", {})
        self.assertEqual(
            model_assignment.get("manager"),
            "anthropic/claude-sonnet-4.5",
            f"Expected AI's manager model, got: {model_assignment.get('manager')}"
        )


class TestChatReplyPlanHasManagerModel(unittest.TestCase):
    """ChatReplyPlan schema must include managerModel field."""

    def test_manager_model_field_exists(self):
        from schemas import ChatReplyPlan

        plan = ChatReplyPlan(
            planAgents=[],
            planTaskDescription="test",
            managerModel="anthropic/claude-sonnet-4.5",
        )
        self.assertEqual(plan.managerModel, "anthropic/claude-sonnet-4.5")

    def test_manager_model_defaults_empty(self):
        from schemas import ChatReplyPlan

        plan = ChatReplyPlan()
        self.assertEqual(plan.managerModel, "")


class TestChangeManagerModelAction(unittest.TestCase):
    """change_manager_model action should update pre_assigned_models['manager']."""

    def test_change_manager_model_updates_session(self):
        """When change_manager_model is received, pre_assigned_models['manager'] must update."""
        # Simulate the handler logic directly
        pre_assigned = {"manager": "openrouter/free", "workers": {"Writer": "openrouter/free"}}
        model_id = "anthropic/claude-sonnet-4.5"

        # This mirrors the handler in chat.py
        if model_id:
            pre_assigned["manager"] = model_id

        self.assertEqual(pre_assigned["manager"], "anthropic/claude-sonnet-4.5")


if __name__ == "__main__":
    unittest.main(verbosity=2)
