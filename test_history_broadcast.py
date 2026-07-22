"""Regression tests for real-time history broadcasting.

Seam: log_history → history_store.add_entry → _broadcast_history → reply_history
Tests verify that log_history persists entries and schedules a broadcast.
"""

import os
import sys
import json
import tempfile
import asyncio
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("OPENROUTER_API_KEY", "test-key-fake")

from backend.agents.history_store import HistoryStore


class TestHistoryStoreEntry(unittest.TestCase):
    """HistoryStore.add_entry must persist entries correctly."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store_path = os.path.join(self.tmpdir, "history_log.json")
        with open(self.store_path, "w") as f:
            json.dump([], f)

    def tearDown(self):
        if os.path.exists(self.store_path):
            os.unlink(self.store_path)
        os.rmdir(self.tmpdir)

    def test_add_entry_creates_new_task_log(self):
        store = HistoryStore.__new__(HistoryStore)
        store.filepath = self.store_path
        store.logs = []
        store._load = lambda: None
        entry = store.add_entry("task-1", "Test Task", "Manager", "สร้าง plan")
        self.assertEqual(entry["actor"], "Manager")
        self.assertEqual(entry["action"], "สร้าง plan")
        self.assertEqual(len(store.logs), 1)
        self.assertEqual(store.logs[0]["task_id"], "task-1")
        self.assertEqual(len(store.logs[0]["entries"]), 1)

    def test_add_entry_appends_to_existing_task(self):
        store = HistoryStore.__new__(HistoryStore)
        store.filepath = self.store_path
        store.logs = []
        store._load = lambda: None
        store.add_entry("task-1", "Test Task", "User", "สั่งงาน")
        store.add_entry("task-1", "Test Task", "Manager", "รับคำสั่ง")
        self.assertEqual(len(store.logs), 1)
        self.assertEqual(len(store.logs[0]["entries"]), 2)
        self.assertEqual(store.logs[0]["entries"][1]["actor"], "Manager")

    def test_list_history_returns_recent(self):
        store = HistoryStore.__new__(HistoryStore)
        store.filepath = self.store_path
        store.logs = []
        store._load = lambda: None
        for i in range(5):
            store.add_entry(f"task-{i}", f"Task {i}", "Agent", f"action {i}")
        result = store.list_history(3)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[-1]["task_id"], "task-4")


class TestLogHistoryBroadcast(unittest.TestCase):
    """log_history must schedule a broadcast after adding entry."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store_path = os.path.join(self.tmpdir, "history_log.json")
        with open(self.store_path, "w") as f:
            json.dump([], f)

    def tearDown(self):
        if os.path.exists(self.store_path):
            os.unlink(self.store_path)
        os.rmdir(self.tmpdir)

    def _make_messenger(self):
        """Create a StateMessenger with a temp history_store, no cl dependency."""
        from backend.core.messenger import StateMessenger
        ms = StateMessenger.__new__(StateMessenger)
        ms.history_store = HistoryStore.__new__(HistoryStore)
        ms.history_store.filepath = self.store_path
        ms.history_store.logs = []
        ms.history_store._load = lambda: None
        ms._main_loop = None
        ms.current_session_id = None
        return ms

    def test_log_history_calls_add_entry(self):
        ms = self._make_messenger()
        with patch.object(ms.history_store, "add_entry") as mock_add:
            ms.log_history("task-1", "Test", "Manager", "สร้าง plan")
            mock_add.assert_called_once_with("task-1", "Test", "Manager", "สร้าง plan", "")

    def test_log_history_schedules_broadcast_in_async_context(self):
        ms = self._make_messenger()

        async def run_test():
            with patch.object(ms, "reply_history", new_callable=AsyncMock) as mock_reply:
                ms.log_history("task-1", "Test", "Manager", "สร้าง plan")
                await asyncio.sleep(0.01)
                mock_reply.assert_awaited_once()

        asyncio.run(run_test())

    def test_log_history_schedules_broadcast_from_thread(self):
        ms = self._make_messenger()

        loop = asyncio.new_event_loop()

        async def reply_mock():
            pass

        async def run_test():
            ms._main_loop = asyncio.get_event_loop()
            with patch.object(ms, "reply_history", new_callable=AsyncMock) as mock_reply:
                ms.log_history("task-1", "Test", "Manager", "สร้าง plan")
                await asyncio.sleep(0.05)
                mock_reply.assert_awaited_once()

        loop.run_until_complete(run_test())
        loop.close()

    def test_log_history_no_broadcast_when_no_loop(self):
        ms = self._make_messenger()
        ms._main_loop = None
        with patch.object(ms, "reply_history") as mock_reply:
            ms.log_history("task-1", "Test", "Manager", "สร้าง plan")
            mock_reply.assert_not_called()


class AsyncMock:
    """Simple async mock that tracks calls."""
    def __init__(self):
        self.awaited = False
        self.await_count = 0

    async def __call__(self, *args, **kwargs):
        self.awaited = True
        self.await_count += 1

    def assert_awaited_once(self):
        assert self.awaited and self.await_count == 1, f"Expected 1 await, got {self.await_count}"

    def assert_not_called(self):
        assert not self.awaited, "Expected no calls"


if __name__ == "__main__":
    unittest.main()
