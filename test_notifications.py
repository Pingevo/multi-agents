"""Unit tests for ChatStore.get_all_notifications() — cross-session notification aggregation."""

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta

from backend.agents.chat_store import ChatStore


class TestGetAllNotifications(unittest.TestCase):
    """Tests for ChatStore.get_all_notifications()."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        self.tmp.write('[]')
        self.tmp.close()
        self.store = ChatStore(filepath=self.tmp.name)

    def tearDown(self):
        os.unlink(self.tmp.name)

    def _add_msg(self, session_id: str, msg_type: str, extra: dict = None, ts: str = None):
        """Helper to add a message to a session."""
        msg = {"messageType": msg_type, "timestamp": ts or datetime.now().isoformat()}
        if extra:
            msg.update(extra)
        self.store.add_message(session_id, msg)

    def test_aggregates_across_multiple_sessions(self):
        """Should collect notifications from all sessions."""
        s1 = self.store.create_session("Session 1")
        s2 = self.store.create_session("Session 2")

        self._add_msg(s1["id"], "plan", {"planStatus": "pending", "planTaskDescription": "Task A"})
        self._add_msg(s2["id"], "image_approval", {"approvalStatus": "pending", "imagePrompt": "cat"})

        notifs = self.store.get_all_notifications()
        self.assertEqual(len(notifs), 2)
        session_ids = {n["sessionId"] for n in notifs}
        self.assertEqual(session_ids, {s1["id"], s2["id"]})

    def test_filters_non_notification_types(self):
        """Should only include plan, image_approval, agent_review, tuning_proposal."""
        s1 = self.store.create_session("Session 1")
        self._add_msg(s1["id"], "text", {"content": "hello"})
        self._add_msg(s1["id"], "plan", {"planStatus": "pending"})
        self._add_msg(s1["id"], "progress", {"progressPercent": 50})

        notifs = self.store.get_all_notifications()
        self.assertEqual(len(notifs), 1)
        self.assertEqual(notifs[0]["messageType"], "plan")

    def test_filters_old_messages_15_days(self):
        """Should exclude messages older than 15 days."""
        s1 = self.store.create_session("Session 1")
        old_ts = (datetime.now() - timedelta(days=20)).isoformat()
        recent_ts = datetime.now().isoformat()

        self._add_msg(s1["id"], "plan", {"planStatus": "approved"}, ts=old_ts)
        self._add_msg(s1["id"], "plan", {"planStatus": "pending"}, ts=recent_ts)

        notifs = self.store.get_all_notifications()
        self.assertEqual(len(notifs), 1)
        self.assertEqual(notifs[0]["planStatus"], "pending")

    def test_includes_session_metadata(self):
        """Each notification should include sessionId and sessionTitle."""
        s1 = self.store.create_session("My Chat")
        self._add_msg(s1["id"], "plan", {"planStatus": "pending"})

        notifs = self.store.get_all_notifications()
        self.assertEqual(len(notifs), 1)
        self.assertEqual(notifs[0]["sessionId"], s1["id"])
        self.assertEqual(notifs[0]["sessionTitle"], "My Chat")

    def test_filters_by_team_id(self):
        """Should filter notifications by team_id when provided."""
        s1 = self.store.create_session("Team A Chat", team_id="team-a")
        s2 = self.store.create_session("Team B Chat", team_id="team-b")

        self._add_msg(s1["id"], "plan", {"planStatus": "pending"})
        self._add_msg(s2["id"], "plan", {"planStatus": "pending"})

        notifs = self.store.get_all_notifications(team_id="team-a")
        self.assertEqual(len(notifs), 1)
        self.assertEqual(notifs[0]["sessionId"], s1["id"])

    def test_sorted_by_timestamp_descending(self):
        """Notifications should be sorted by timestamp descending (newest first)."""
        s1 = self.store.create_session("Session 1")
        old_ts = (datetime.now() - timedelta(days=5)).isoformat()
        new_ts = datetime.now().isoformat()

        self._add_msg(s1["id"], "plan", {"planStatus": "approved"}, ts=old_ts)
        self._add_msg(s1["id"], "plan", {"planStatus": "pending"}, ts=new_ts)

        notifs = self.store.get_all_notifications()
        self.assertEqual(len(notifs), 2)
        self.assertGreaterEqual(notifs[0]["timestamp"], notifs[1]["timestamp"])

    def test_empty_store_returns_empty_list(self):
        """Should return empty list when no sessions exist."""
        notifs = self.store.get_all_notifications()
        self.assertEqual(notifs, [])

    def test_all_notification_types_included(self):
        """All four notification types should be included."""
        s1 = self.store.create_session("Session 1")
        self._add_msg(s1["id"], "plan", {"planStatus": "pending"})
        self._add_msg(s1["id"], "image_approval", {"approvalStatus": "pending"})
        self._add_msg(s1["id"], "agent_review", {"reviewStatus": "pending"})
        self._add_msg(s1["id"], "tuning_proposal", {"tuningStatus": None})

        notifs = self.store.get_all_notifications()
        types = {n["messageType"] for n in notifs}
        self.assertEqual(types, {"plan", "image_approval", "agent_review", "tuning_proposal"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
