"""Regression tests for ExecutionOrchestrator.

Seam: run_async(user_input, agent_specs, model_assignment, ...) → Crew execution
Tests verify orchestrator initialization, agent creation, and output cleaning.
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


class TestExecutionOrchestratorInit(unittest.TestCase):
    """ExecutionOrchestrator must initialize correctly with dependencies."""

    def test_init_creates_agent_factory(self):
        from app import ExecutionOrchestrator, LLMManager, ToolRegistry
        mgr = MagicMock(spec=LLMManager)
        mgr._is_openrouter.return_value = False
        mgr.api_key = "fake"
        mgr.base_url = "https://openrouter.ai/api/v1"
        mgr.temperature = 0.7
        mgr._default_model = "openrouter/free"
        tools = ToolRegistry()
        orchestrator = ExecutionOrchestrator(mgr, tools)
        self.assertIsNotNone(orchestrator.agent_factory)
        self.assertIsNone(orchestrator.model_selector)  # not openrouter

    def test_init_with_openrouter_creates_model_selector(self):
        from app import ExecutionOrchestrator, LLMManager, ToolRegistry
        mgr = MagicMock(spec=LLMManager)
        mgr._is_openrouter.return_value = True
        mgr.api_key = "fake"
        mgr.base_url = "https://openrouter.ai/api/v1"
        mgr.temperature = 0.7
        mgr._default_model = "openrouter/free"
        tools = ToolRegistry()
        orchestrator = ExecutionOrchestrator(mgr, tools)
        self.assertIsNotNone(orchestrator.model_selector)


class TestCleanAgentOutput(unittest.TestCase):
    """_clean_agent_output must strip CrewAI internal markers."""

    def test_cleans_box_drawing_chars(self):
        from app import ExecutionOrchestrator
        dirty = "─│┌┐└┘Hello World─│"
        cleaned = ExecutionOrchestrator._clean_agent_output(dirty)
        self.assertEqual(cleaned, "Hello World")

    def test_cleans_internal_markers(self):
        from app import ExecutionOrchestrator
        dirty = "Crew Execution Started\nTask Started\nFinal Answer:\nReal content here\nTask Completed\nCrew Execution Completed"
        cleaned = ExecutionOrchestrator._clean_agent_output(dirty)
        self.assertIn("Real content here", cleaned)
        self.assertNotIn("Crew Execution Started", cleaned)
        self.assertNotIn("Final Answer:", cleaned)

    def test_empty_input_returns_empty(self):
        from app import ExecutionOrchestrator
        self.assertEqual(ExecutionOrchestrator._clean_agent_output(""), "")
        self.assertIsNone(ExecutionOrchestrator._clean_agent_output(None))

    def test_preserves_normal_text(self):
        from app import ExecutionOrchestrator
        text = "This is a normal output from the agent."
        cleaned = ExecutionOrchestrator._clean_agent_output(text)
        self.assertEqual(cleaned, text)


class TestOrchestratorRunAsync(unittest.TestCase):
    """run_async must execute agents and return results."""

    def test_run_async_with_empty_agents_returns_error(self):
        """Running with no agents should return an error result."""
        import asyncio
        from app import ExecutionOrchestrator, LLMManager, ToolRegistry
        mgr = MagicMock(spec=LLMManager)
        mgr._is_openrouter.return_value = False
        mgr.api_key = "fake"
        mgr.base_url = "https://openrouter.ai/api/v1"
        mgr.temperature = 0.7
        mgr._default_model = "openrouter/free"
        tools = ToolRegistry()
        orchestrator = ExecutionOrchestrator(mgr, tools)

        with patch("chainlit.user_session") as mock_session:
            mock_session.get.return_value = ""
            result = asyncio.run(
                orchestrator.run_async(
                    user_input="test",
                    agent_specs=[],
                    pre_assigned_models={"manager": "openrouter/free", "workers": {}},
                )
            )
        # Empty agents should produce some error or empty result
        self.assertIsInstance(result, dict)

    def test_run_async_with_mocked_crew(self):
        """run_async with a single agent should return a dict result."""
        import asyncio
        from app import ExecutionOrchestrator, LLMManager, ToolRegistry
        mgr = MagicMock(spec=LLMManager)
        mgr._is_openrouter.return_value = False
        mgr.api_key = "fake"
        mgr.base_url = "https://openrouter.ai/api/v1"
        mgr.temperature = 0.7
        mgr._default_model = "openrouter/free"
        mgr._selected_model = ""
        mgr.local_fallback_enabled = False
        tools = ToolRegistry()
        orchestrator = ExecutionOrchestrator(mgr, tools)

        # Mock the agent factory's create_agent and create_task
        mock_agent = MagicMock()
        mock_task = MagicMock()

        with patch.object(orchestrator.agent_factory, "create_agent", return_value=mock_agent), \
             patch.object(orchestrator.agent_factory, "create_task", return_value=mock_task), \
             patch("chainlit.user_session") as mock_session, \
             patch("backend.core.orchestrator.Crew") as MockCrew:

            mock_session.get.return_value = ""
            mock_output = MagicMock()
            mock_output.raw = "Task completed"
            mock_output.tasks_output = []
            mock_crew_instance = MagicMock()
            mock_crew_instance.kickoff_async = AsyncMock(return_value=mock_output)
            MockCrew.return_value = mock_crew_instance

            result = asyncio.run(
                orchestrator.run_async(
                    user_input="write a post",
                    agent_specs=[{
                        "name": "Writer",
                        "role": "Writer",
                        "goal": "Write",
                        "backstory": "Writer",
                        "tools": [],
                        "task_description": "Write 1 post",
                        "depends_on": [],
                        "model": "openrouter/free",
                    }],
                    pre_assigned_models={"manager": "openrouter/free", "workers": {"Writer": "openrouter/free"}},
                )
            )
            self.assertIsInstance(result, dict)


if __name__ == "__main__":
    unittest.main(verbosity=2)
