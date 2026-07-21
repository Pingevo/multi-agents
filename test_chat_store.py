"""Regression tests for ChatStore session management.

Seam: create_session → add_message → get_session → rename → delete
Tests verify chat session lifecycle and message persistence.
"""

import os
import sys
import json
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("OPENROUTER_API_KEY", "test-key-fake")


class TestChatStoreCRUD(unittest.TestCase):
    """ChatStore must support full session lifecycle."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store_path = os.path.join(self.tmpdir, "test_chat.json")
        with open(self.store_path, "w") as f:
            json.dump([], f)

    def tearDown(self):
        if os.path.exists(self.store_path):
            os.unlink(self.store_path)
        os.rmdir(self.tmpdir)

    def _make_store(self):
        from backend.agents.chat_store import ChatStore
        return ChatStore(filepath=self.store_path)

    def test_create_session_returns_session_with_id(self):
        store = self._make_store()
        session = store.create_session("Test Chat")
        self.assertIn("id", session)
        self.assertEqual(session["title"], "Test Chat")
        self.assertEqual(session["messages"], [])

    def test_get_session_returns_correct_session(self):
        store = self._make_store()
        session = store.create_session("My Chat")
        found = store.get_session(session["id"])
        self.assertIsNotNone(found)
        self.assertEqual(found["title"], "My Chat")

    def test_get_session_returns_none_for_missing(self):
        store = self._make_store()
        self.assertIsNone(store.get_session("nonexistent"))

    def test_add_message_appends_to_session(self):
        store = self._make_store()
        session = store.create_session("Chat")
        store.add_message(session["id"], {"role": "user", "content": "Hello"})
        found = store.get_session(session["id"])
        self.assertEqual(len(found["messages"]), 1)
        self.assertEqual(found["messages"][0]["content"], "Hello")

    def test_add_message_auto_titles_from_first_user_message(self):
        store = self._make_store()
        session = store.create_session("New Chat")
        store.add_message(session["id"], {"role": "user", "content": "Create a content plan for coffee shop"})
        found = store.get_session(session["id"])
        self.assertNotEqual(found["title"], "New Chat")
        self.assertIn("Create a content plan", found["title"])

    def test_rename_session_updates_title(self):
        store = self._make_store()
        session = store.create_session("Old Title")
        result = store.rename_session(session["id"], "New Title")
        self.assertIsNotNone(result)
        self.assertEqual(result["title"], "New Title")

    def test_rename_session_returns_none_for_missing(self):
        store = self._make_store()
        self.assertIsNone(store.rename_session("nonexistent", "Title"))

    def test_delete_session_removes_from_store(self):
        store = self._make_store()
        session = store.create_session("To Delete")
        result = store.delete_session(session["id"])
        self.assertTrue(result)
        self.assertIsNone(store.get_session(session["id"]))

    def test_delete_session_returns_false_for_missing(self):
        store = self._make_store()
        self.assertFalse(store.delete_session("nonexistent"))

    def test_list_sessions_returns_sorted_by_updated(self):
        store = self._make_store()
        s1 = store.create_session("First")
        store.add_message(s1["id"], {"role": "user", "content": "Hi"})
        s2 = store.create_session("Second")
        store.add_message(s2["id"], {"role": "user", "content": "Hello"})
        sessions = store.list_sessions()
        # Most recently updated should be first
        self.assertEqual(sessions[0]["title"], "Second")

    def test_list_sessions_filters_by_team_id(self):
        store = self._make_store()
        store.create_session("Team A Chat", team_id="team-a")
        store.create_session("Team B Chat", team_id="team-b")
        store.create_session("No Team Chat")
        team_a = store.list_sessions(team_id="team-a")
        self.assertEqual(len(team_a), 1)
        self.assertEqual(team_a[0]["title"], "Team A Chat")

    def test_delete_sessions_by_team_removes_all(self):
        store = self._make_store()
        store.create_session("Chat 1", team_id="team-x")
        store.create_session("Chat 2", team_id="team-x")
        store.create_session("Other", team_id="team-y")
        deleted = store.delete_sessions_by_team("team-x")
        self.assertEqual(deleted, 2)
        self.assertEqual(len(store.list_sessions()), 1)

    def test_persists_to_disk(self):
        store = self._make_store()
        session = store.create_session("Persistent")
        store.add_message(session["id"], {"role": "user", "content": "Test"})
        # Create new store from same file
        store2 = self._make_store()
        sessions = store2.list_sessions()
        self.assertEqual(len(sessions), 1)
        self.assertEqual(len(sessions[0]["messages"]), 1)

    def test_save_and_load_canvas_state(self):
        store = self._make_store()
        session = store.create_session("Canvas Chat")
        canvas = {"nodes": [{"id": "1"}], "edges": []}
        store.save_canvas_state(session["id"], canvas)
        found = store.get_session(session["id"])
        self.assertIn("canvas_state", found)
        self.assertEqual(found["canvas_state"]["nodes"][0]["id"], "1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
