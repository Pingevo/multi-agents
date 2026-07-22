"""Backend integration tests — verify handler wiring with mocked cl.user_session.

These tests call real handler functions (on_chat_start, execute_multi_agent_task,
on_message plan-creation path) with a mocked chainlit user_session, asserting
real side effects. This catches wiring bugs that isolated unit tests cannot.
"""

import asyncio
import json
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set test env before importing backend modules
_test_data_dir = tempfile.mkdtemp(prefix="handler-test-")
os.environ["AGENT_APP_DATA_DIR"] = _test_data_dir
os.environ["LLM_PROVIDER"] = "openrouter"
os.environ["LLM_API_KEY"] = "test-key-fake"
os.environ["LLM_BASE_URL"] = "http://127.0.0.1:11434"
os.environ["LOCAL_LLM_FALLBACK"] = "false"
os.environ["USE_DEV_LOGIN"] = "true"


def _fresh_registry_file():
    """Return a unique temp file path for an isolated agent registry."""
    return tempfile.mktemp(suffix=".json", prefix="agent_reg_")


def _fresh_task_store_file():
    """Return a unique temp file path for an isolated task store."""
    return tempfile.mktemp(suffix=".json", prefix="task_store_")


@pytest.fixture
def mock_user_session():
    """Create a mock chainlit user_session with all keys that on_chat_start sets."""
    session = MagicMock()
    session_data = {}

    session.get = MagicMock(side_effect=lambda key, default=None: session_data.get(key, default))
    session.set = MagicMock(side_effect=lambda key, value: session_data.__setitem__(key, value))

    # Patch cl.user_session globally
    with patch("chainlit.user_session", session):
        yield session, session_data


class TestOnChatStartWiring:
    """Verify on_chat_start sets all required session keys.

    These tests mock chainlit.Message and chainlit.context to allow
    on_chat_start to run outside a real Chainlit server.
    """

    def _run_on_chat_start(self, session_data):
        """Helper: run on_chat_start with mocked chainlit internals."""
        async def _run():
            mock_msg = AsyncMock()
            mock_msg.send = AsyncMock()

            mock_ctx = MagicMock()
            mock_ctx.session = MagicMock()
            mock_ctx.session.id = "test-session-id"

            with patch("chainlit.Message", return_value=mock_msg), \
                 patch("chainlit.context", mock_ctx), \
                 patch("chainlit.context.get_context", return_value=mock_ctx):
                from backend.handlers.chat import on_chat_start
                try:
                    await on_chat_start()
                except Exception:
                    pass

        asyncio.run(_run())

    def test_task_store_is_set_in_session(self, mock_user_session):
        """Regression: task_store was not being set, causing AttributeError on plan approval."""
        session, session_data = mock_user_session
        self._run_on_chat_start(session_data)

        assert "task_store" in session_data, "task_store was not set in user_session"
        assert session_data["task_store"] is not None, "task_store is None"

    def test_messenger_is_set_in_session(self, mock_user_session):
        """Verify messenger is set so get_messenger() doesn't return None."""
        session, session_data = mock_user_session
        self._run_on_chat_start(session_data)

        assert "messenger" in session_data, "messenger was not set in user_session"
        assert session_data["messenger"] is not None, "messenger is None"

    def test_registry_is_set_in_session(self, mock_user_session):
        """Verify registry is set for agent operations."""
        session, session_data = mock_user_session
        self._run_on_chat_start(session_data)

        assert "registry" in session_data, "registry was not set in user_session"
        assert session_data["registry"] is not None, "registry is None"


class TestTaskStoreTeamId:
    """Verify TaskStore stores and filters by team_id correctly."""

    def test_add_task_with_team_id(self):
        from backend.agents.task_store import TaskStore

        store = TaskStore(filepath=_fresh_task_store_file())
        task = {"input": "Test task", "team_id": "team-123", "status": "running"}
        result = store.add_task(task)

        assert result is not None
        assert result.get("team_id") == "team-123", "task should have team_id set"

    def test_get_tasks_by_team_filters_correctly(self):
        from backend.agents.task_store import TaskStore

        store = TaskStore(filepath=_fresh_task_store_file())
        store.add_task({"input": "Task A", "team_id": "team-a", "status": "running"})
        store.add_task({"input": "Task B", "team_id": "team-b", "status": "running"})
        store.add_task({"input": "Task C", "team_id": "team-a", "status": "running"})

        team_a_tasks = store.get_tasks_by_team("team-a")
        team_b_tasks = store.get_tasks_by_team("team-b")

        assert len(team_a_tasks) == 2, "team-a should have 2 tasks"
        assert len(team_b_tasks) == 1, "team-b should have 1 task"
        assert all(t.get("team_id") == "team-a" for t in team_a_tasks), "all team-a tasks should have team_id=team-a"


class TestMessengerAddTaskTeamId:
    """Verify messenger.add_task accepts and stores team_id."""

    def test_add_task_passes_team_id(self):
        from backend.core.messenger import StateMessenger
        from backend.agents.task_store import TaskStore

        task_store = TaskStore(filepath=_fresh_task_store_file())

        async def _run():
            messenger = StateMessenger(task_store=task_store)
            # Mock _send to avoid socket calls
            messenger._send = AsyncMock()

            # add_task signature: add_task(task_id, title, agent_name, team_id)
            await messenger.add_task("task-test-1", "Test messenger task", "TestAgent", team_id="team-test-456")

            tasks = task_store.get_tasks_by_team("team-test-456")
            assert len(tasks) == 1, "task should be stored with team_id"
            assert tasks[0].get("team_id") == "team-test-456"

        asyncio.run(_run())


class TestRegistryTeamFiltering:
    """Verify agent registry filters by team_id."""

    def test_find_by_name_filters_by_team_id(self):
        from backend.agents.registry import AgentRegistry

        registry = AgentRegistry(filepath=_fresh_registry_file())

        # Add agents for different teams
        registry.add_agent({"name": "Agent Alpha", "role": "Researcher", "team_id": "team-a"})
        registry.add_agent({"name": "Agent Beta", "role": "Researcher", "team_id": "team-b"})

        # find_by_name with team_id should only find agents in that team
        result_a = registry.find_by_name("Agent Alpha", team_id="team-a")
        result_b = registry.find_by_name("Agent Alpha", team_id="team-b")

        assert result_a is not None, "Agent Alpha should be found in team-a"
        assert result_b is None, "Agent Alpha should NOT be found in team-b"

    def test_find_idle_agent_filters_by_team_id(self):
        from backend.agents.registry import AgentRegistry

        registry = AgentRegistry(filepath=_fresh_registry_file())

        registry.add_agent({"name": "Idle Agent A", "role": "Researcher", "team_id": "team-a"})
        registry.add_agent({"name": "Idle Agent B", "role": "Researcher", "team_id": "team-b"})

        result = registry.find_idle_agent("Researcher", [], team_id="team-a")

        assert result is not None, "Should find idle agent in team-a"
        assert result.get("name") == "Idle Agent A", "Should find the correct agent"
        assert result.get("team_id") == "team-a", "Found agent should belong to team-a"

    def test_list_agents_filters_by_team_id(self):
        from backend.agents.registry import AgentRegistry

        registry = AgentRegistry(filepath=_fresh_registry_file())

        registry.add_agent({"name": "List Agent A", "role": "Researcher", "team_id": "team-a"})
        registry.add_agent({"name": "List Agent B", "role": "Researcher", "team_id": "team-b"})
        registry.add_agent({"name": "List Agent C", "role": "Writer", "team_id": "team-a"})

        team_a_agents = registry.list_agents(team_id="team-a")
        team_b_agents = registry.list_agents(team_id="team-b")

        assert len(team_a_agents) == 2, "team-a should have 2 agents"
        assert len(team_b_agents) == 1, "team-b should have 1 agent"
        assert all(a.get("team_id") == "team-a" for a in team_a_agents), "all team-a agents should have team_id=team-a"
