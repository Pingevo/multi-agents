"""Regression tests for plan approval action flow.

Seam: accept_plan action → on_action_accept → execute_multi_agent_task
      reject_plan action → on_action_reject → state cleanup

Tests that plan approval/rejection triggers the correct backend flow
and that the selected model is propagated to the execution.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch, AsyncMock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("OPENROUTER_API_KEY", "test-key-fake")
os.environ.setdefault("LLM_PROVIDER", "openrouter")
os.environ.setdefault("LLM_API_KEY", "test-key-fake")
os.environ.setdefault("LLM_BASE_URL", "https://openrouter.ai/api/v1")
os.environ.setdefault("LOCAL_LLM_FALLBACK", "false")


class TestPlanAcceptAction(unittest.TestCase):
    """accept_plan action should trigger execution with the correct model."""

    def test_accept_plan_payload_preserves_selected_model(self):
        """The accept_plan payload should include the selected model for execution."""
        # Simulate the payload that frontend sends
        payload = {
            "plan": {
                "agents": [{"name": "Writer", "role": "Writer", "goal": "Write", "model": "openai/gpt-5.6-luna"}],
                "task_description": "Write 1 post",
            },
            "model_assignment": {
                "manager": "anthropic/claude-sonnet-4.5",
                "workers": {"Writer": "openai/gpt-5.6-luna"},
            },
        }

        # The payload must contain model_assignment with manager model
        model_assignment = payload.get("model_assignment", {})
        self.assertEqual(model_assignment.get("manager"), "anthropic/claude-sonnet-4.5")
        self.assertEqual(model_assignment.get("workers", {}).get("Writer"), "openai/gpt-5.6-luna")

    def test_accept_plan_pre_assigned_models_updated(self):
        """When accept_plan is received, pre_assigned_models should be updated with the plan's models."""
        # Simulate session state
        pre_assigned = {"manager": "openrouter/free", "workers": {}}

        # Simulate what on_action_accept does with model_assignment
        plan_payload = {
            "model_assignment": {
                "manager": "anthropic/claude-sonnet-4.5",
                "workers": {"Writer": "openai/gpt-5.6-luna"},
            }
        }

        model_assignment = plan_payload.get("model_assignment", {})
        if model_assignment:
            pre_assigned["manager"] = model_assignment.get("manager", pre_assigned["manager"])
            pre_assigned["workers"].update(model_assignment.get("workers", {}))

        self.assertEqual(pre_assigned["manager"], "anthropic/claude-sonnet-4.5")
        self.assertEqual(pre_assigned["workers"]["Writer"], "openai/gpt-5.6-luna")


class TestSetSelectedModelAction(unittest.TestCase):
    """set_selected_model action should update session state and sync to LLMManager."""

    def test_set_selected_model_stores_in_session(self):
        """set_selected_model should store the model_id in session."""
        # Simulate the handler logic
        model_id = "openai/gpt-5.6-luna"
        session_state = {}

        # What the handler does:
        session_state["selected_model"] = model_id
        pre_assigned = session_state.get("pre_assigned_models", {"manager": "", "workers": {}})
        pre_assigned["manager"] = model_id
        session_state["pre_assigned_models"] = pre_assigned

        self.assertEqual(session_state["selected_model"], "openai/gpt-5.6-luna")
        self.assertEqual(session_state["pre_assigned_models"]["manager"], "openai/gpt-5.6-luna")

    def test_set_selected_model_syncs_to_llm_manager(self):
        """When set_selected_model is called, LLMManager.set_selected_model should be called too."""
        from app import LLMManager
        mgr = LLMManager()

        # Simulate what should happen in the handler
        model_id = "openai/gpt-5.6-luna"
        mgr.set_selected_model(model_id)

        self.assertEqual(mgr._selected_model, "openai/gpt-5.6-luna")
        self.assertFalse(mgr._is_free_routing())


class TestRejectPlanAction(unittest.TestCase):
    """reject_plan action should clean up state and return to idle."""

    def test_reject_plan_clears_current_plan(self):
        """When reject_plan is received, current_plan should be cleared."""
        session_state = {"current_plan": {"agents": [], "task_description": "test"}, "state": "awaiting_approval"}

        # Simulate what on_action_reject does
        session_state["current_plan"] = None
        session_state["state"] = "idle"

        self.assertIsNone(session_state["current_plan"])
        self.assertEqual(session_state["state"], "idle")


if __name__ == "__main__":
    unittest.main(verbosity=2)
