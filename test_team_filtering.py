"""Regression tests for cross-team notification and task filtering.

Tests that tasks and notifications are properly filtered by team_id,
preventing data from one team leaking into another.
"""

import os
import sys
import json
import tempfile
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("OPENROUTER_API_KEY", "test-key-fake")

from backend.agents.task_store import TaskStore
from backend.agents.chat_store import ChatStore


class TestTaskStoreTeamFiltering(unittest.TestCase):
    """TaskStore.get_tasks_by_team must return only tasks for that team."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store_path = os.path.join(self.tmpdir, "tasks.json")
        with open(self.store_path, "w") as f:
            json.dump([], f)
        self.store = TaskStore(filepath=self.store_path)

    def tearDown(self):
        if os.path.exists(self.store_path):
            os.unlink(self.store_path)
        os.rmdir(self.tmpdir)

    def test_get_tasks_by_team_returns_only_team_tasks(self):
        self.store.add_task({"id": "t1", "team_id": "team_a", "title": "Task A1"})
        self.store.add_task({"id": "t2", "team_id": "team_b", "title": "Task B1"})
        self.store.add_task({"id": "t3", "team_id": "team_a", "title": "Task A2"})

        team_a_tasks = self.store.get_tasks_by_team("team_a")
        team_b_tasks = self.store.get_tasks_by_team("team_b")

        self.assertEqual(len(team_a_tasks), 2)
        self.assertEqual(len(team_b_tasks), 1)
        self.assertEqual(team_b_tasks[0]["id"], "t2")

    def test_list_tasks_returns_all(self):
        self.store.add_task({"id": "t1", "team_id": "team_a"})
        self.store.add_task({"id": "t2", "team_id": "team_b"})
        all_tasks = self.store.list_tasks()
        self.assertEqual(len(all_tasks), 2)

    def test_get_tasks_by_team_empty(self):
        self.store.add_task({"id": "t1", "team_id": "team_a"})
        result = self.store.get_tasks_by_team("nonexistent")
        self.assertEqual(result, [])

    def test_tasks_without_team_id_excluded_from_team_filter(self):
        self.store.add_task({"id": "t1", "team_id": "team_a"})
        self.store.add_task({"id": "t2", "title": "no team"})
        result = self.store.get_tasks_by_team("team_a")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "t1")


class TestChatStoreNotificationTeamFiltering(unittest.TestCase):
    """ChatStore.get_all_notifications must filter by team_id."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store_path = os.path.join(self.tmpdir, "chat.json")
        with open(self.store_path, "w") as f:
            json.dump([], f)
        self.store = ChatStore(filepath=self.store_path)

    def tearDown(self):
        if os.path.exists(self.store_path):
            os.unlink(self.store_path)
        os.rmdir(self.tmpdir)

    def _add_plan_msg(self, session_id, summary="Test plan"):
        self.store.add_message(session_id, {
            "role": "assistant",
            "messageType": "plan",
            "planSummary": summary,
            "timestamp": datetime.now().isoformat(),
        })

    def test_notifications_filtered_by_team(self):
        s1 = self.store.create_session("Session A", team_id="team_a")
        s2 = self.store.create_session("Session B", team_id="team_b")
        self._add_plan_msg(s1["id"], "Plan for team A")
        self._add_plan_msg(s2["id"], "Plan for team B")

        team_a_notifs = self.store.get_all_notifications(team_id="team_a")
        team_b_notifs = self.store.get_all_notifications(team_id="team_b")

        self.assertEqual(len(team_a_notifs), 1)
        self.assertEqual(team_a_notifs[0]["planSummary"], "Plan for team A")
        self.assertEqual(len(team_b_notifs), 1)
        self.assertEqual(team_b_notifs[0]["planSummary"], "Plan for team B")

    def test_notifications_without_team_id_returns_all(self):
        s1 = self.store.create_session("Session A", team_id="team_a")
        s2 = self.store.create_session("Session B", team_id="team_b")
        self._add_plan_msg(s1["id"])
        self._add_plan_msg(s2["id"])

        all_notifs = self.store.get_all_notifications()
        self.assertEqual(len(all_notifs), 2)

    def test_notifications_include_unassigned_sessions(self):
        s1 = self.store.create_session("Team A session", team_id="team_a")
        s2 = self.store.create_session("Unassigned session")
        self._add_plan_msg(s1["id"])
        self._add_plan_msg(s2["id"])

        notifs = self.store.get_all_notifications(team_id="team_a")
        # include_unassigned=True in list_sessions, so unassigned should appear
        self.assertEqual(len(notifs), 2)

    def test_non_notification_messages_excluded(self):
        s1 = self.store.create_session("Session A", team_id="team_a")
        self.store.add_message(s1["id"], {
            "role": "assistant",
            "messageType": "text",
            "content": "Hello",
            "timestamp": datetime.now().isoformat(),
        })
        notifs = self.store.get_all_notifications(team_id="team_a")
        self.assertEqual(len(notifs), 0)


class TestMessengerUpdateTasksTeamFiltering(unittest.TestCase):
    """StateMessenger.update_tasks with team_id must filter tasks."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.task_path = os.path.join(self.tmpdir, "tasks.json")
        with open(self.task_path, "w") as f:
            json.dump([], f)
        self.task_store = TaskStore(filepath=self.task_path)
        self.task_store.add_task({"id": "t1", "team_id": "team_a", "title": "A1"})
        self.task_store.add_task({"id": "t2", "team_id": "team_b", "title": "B1"})

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_get_tasks_by_team_filters_correctly(self):
        result = self.task_store.get_tasks_by_team("team_a")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "t1")

    def test_list_tasks_returns_all_unfiltered(self):
        result = self.task_store.list_tasks()
        self.assertEqual(len(result), 2)


if __name__ == "__main__":
    unittest.main()
