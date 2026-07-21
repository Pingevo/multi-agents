"""Regression tests for TaskStore task lifecycle.

Seam: add_task → update_task → get_task → list → delete
Tests verify task CRUD, status transitions, and team/session filtering.
Catches UUID generation bugs (e.g. uuid.uuid4()[:8] TypeError).
"""

import os
import sys
import json
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("OPENROUTER_API_KEY", "test-key-fake")

from backend.agents.task_store import TaskStore


class TestTaskStoreCRUD(unittest.TestCase):
    """TaskStore must support full task lifecycle."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store_path = os.path.join(self.tmpdir, "test_tasks.json")
        with open(self.store_path, "w") as f:
            json.dump([], f)

    def tearDown(self):
        if os.path.exists(self.store_path):
            os.unlink(self.store_path)
        os.rmdir(self.tmpdir)

    def _make_store(self):
        return TaskStore(filepath=self.store_path)

    def test_add_task_generates_id(self):
        """add_task must auto-generate a valid ID when none provided."""
        store = self._make_store()
        task = store.add_task({"input": "test task", "team_id": "t1"})
        self.assertIn("id", task)
        self.assertTrue(task["id"].startswith("task_"))
        self.assertEqual(task["status"], "draft")
        self.assertIn("created_at", task)

    def test_add_task_preserves_existing_id(self):
        """add_task must not overwrite a pre-set ID."""
        store = self._make_store()
        task = store.add_task({"id": "custom_123", "input": "test"})
        self.assertEqual(task["id"], "custom_123")

    def test_add_task_uuid_does_not_crash(self):
        """Regression: uuid.uuid4()[:8] raised TypeError — must use .hex[:8]."""
        store = self._make_store()
        # This should not raise
        for _ in range(10):
            task = store.add_task({"input": "uuid test"})
            self.assertTrue(len(task["id"]) > 5)

    def test_get_task(self):
        store = self._make_store()
        t = store.add_task({"input": "find me"})
        found = store.get_task(t["id"])
        self.assertIsNotNone(found)
        self.assertEqual(found["input"], "find me")
        self.assertIsNone(store.get_task("nonexistent"))

    def test_update_task(self):
        store = self._make_store()
        t = store.add_task({"input": "test"})
        updated = store.update_task(t["id"], status="running", progress=50)
        self.assertEqual(updated["status"], "running")
        self.assertEqual(updated["progress"], 50)
        # done status should set done_at
        store.update_task(t["id"], status="done")
        self.assertIn("done_at", store.get_task(t["id"]))

    def test_update_task_nonexistent(self):
        store = self._make_store()
        result = store.update_task("nope", status="done")
        self.assertIsNone(result)

    def test_delete_task(self):
        store = self._make_store()
        t = store.add_task({"input": "delete me"})
        self.assertTrue(store.delete_task(t["id"]))
        self.assertIsNone(store.get_task(t["id"]))
        self.assertFalse(store.delete_task(t["id"]))

    def test_list_tasks(self):
        store = self._make_store()
        store.add_task({"input": "t1"})
        store.add_task({"input": "t2"})
        self.assertEqual(len(store.list_tasks()), 2)

    def test_get_tasks_by_team(self):
        store = self._make_store()
        store.add_task({"input": "a", "team_id": "team_a"})
        store.add_task({"input": "b", "team_id": "team_b"})
        store.add_task({"input": "c", "team_id": "team_a"})
        self.assertEqual(len(store.get_tasks_by_team("team_a")), 2)
        self.assertEqual(len(store.get_tasks_by_team("team_b")), 1)
        self.assertEqual(len(store.get_tasks_by_team("team_c")), 0)

    def test_get_tasks_by_session(self):
        store = self._make_store()
        store.add_task({"input": "a", "session_id": "s1"})
        store.add_task({"input": "b", "session_id": "s2"})
        self.assertEqual(len(store.get_tasks_by_session("s1")), 1)
        self.assertEqual(len(store.get_tasks_by_session("s2")), 1)

    def test_delete_tasks_by_team(self):
        store = self._make_store()
        store.add_task({"input": "a", "team_id": "team_a"})
        store.add_task({"input": "b", "team_id": "team_a"})
        store.add_task({"input": "c", "team_id": "team_b"})
        deleted = store.delete_tasks_by_team("team_a")
        self.assertEqual(deleted, 2)
        self.assertEqual(len(store.list_tasks()), 1)

    def test_delete_tasks_by_session(self):
        store = self._make_store()
        store.add_task({"input": "a", "session_id": "s1"})
        store.add_task({"input": "b", "session_id": "s1"})
        store.add_task({"input": "c", "session_id": "s2"})
        deleted = store.delete_tasks_by_session("s1")
        self.assertEqual(deleted, 2)
        self.assertEqual(len(store.list_tasks()), 1)

    def test_detach_tasks_by_session(self):
        store = self._make_store()
        store.add_task({"input": "a", "session_id": "s1", "status": "done"})
        store.add_task({"input": "b", "session_id": "s1", "status": "running"})
        store.add_task({"input": "c", "session_id": "s2"})
        detached = store.detach_tasks_by_session("s1")
        self.assertEqual(detached, 2)
        # Tasks still exist but session_id is None
        self.assertEqual(len(store.list_tasks()), 3)
        self.assertEqual(len(store.get_tasks_by_session("s1")), 0)
        self.assertEqual(len(store.get_tasks_by_session("s2")), 1)

    def test_clear_all(self):
        store = self._make_store()
        store.add_task({"input": "a"})
        store.add_task({"input": "b"})
        store.clear_all()
        self.assertEqual(len(store.list_tasks()), 0)

    def test_persistence_across_instances(self):
        """TaskStore must persist to disk and reload correctly."""
        store1 = self._make_store()
        store1.add_task({"input": "persist me"})
        store2 = self._make_store()
        self.assertEqual(len(store2.list_tasks()), 1)
        self.assertEqual(store2.list_tasks()[0]["input"], "persist me")


if __name__ == "__main__":
    unittest.main()
