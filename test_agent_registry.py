"""Regression tests for AgentRegistry CRUD operations.

Seam: add_agent → list_agents → get_by_id → update_agent → delete_agent
Tests verify the full lifecycle of agent registration.
"""

import os
import sys
import json
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("OPENROUTER_API_KEY", "test-key-fake")


class TestAgentRegistryCRUD(unittest.TestCase):
    """AgentRegistry must support full CRUD lifecycle."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.registry_path = os.path.join(self.tmpdir, "test_agents.json")
        with open(self.registry_path, "w") as f:
            json.dump([], f)

    def tearDown(self):
        if os.path.exists(self.registry_path):
            os.unlink(self.registry_path)
        os.rmdir(self.tmpdir)

    def _make_registry(self):
        from backend.agents.registry import AgentRegistry
        return AgentRegistry(filepath=self.registry_path)

    def test_add_agent_creates_with_id_and_status(self):
        reg = self._make_registry()
        agent = reg.add_agent({"name": "Writer", "role": "Content Writer", "goal": "Write content"})
        self.assertIn("id", agent)
        self.assertEqual(agent["name"], "Writer")
        self.assertEqual(agent["role"], "Content Writer")
        self.assertEqual(agent["status"], "Idle")

    def test_add_agent_auto_names_by_role(self):
        reg = self._make_registry()
        agent = reg.add_agent({"role": "Researcher", "goal": "Research"})
        self.assertIn("Researcher", agent["name"])
        self.assertIn("#1", agent["name"])

    def test_list_agents_returns_all(self):
        reg = self._make_registry()
        reg.add_agent({"name": "A", "role": "Writer", "goal": "Write"})
        reg.add_agent({"name": "B", "role": "Editor", "goal": "Edit"})
        agents = reg.list_agents()
        self.assertEqual(len(agents), 2)

    def test_get_by_id_returns_correct_agent(self):
        reg = self._make_registry()
        agent = reg.add_agent({"name": "Finder", "role": "Writer", "goal": "Write"})
        found = reg.get_by_id(agent["id"])
        self.assertIsNotNone(found)
        self.assertEqual(found["name"], "Finder")

    def test_get_by_id_returns_none_for_missing(self):
        reg = self._make_registry()
        self.assertIsNone(reg.get_by_id("nonexistent"))

    def test_update_agent_modifies_fields(self):
        reg = self._make_registry()
        agent = reg.add_agent({"name": "Writer", "role": "Writer", "goal": "Write"})
        result = reg.update_agent(agent["id"], {"goal": "Write better content"})
        self.assertTrue(result)
        updated = reg.get_by_id(agent["id"])
        self.assertEqual(updated["goal"], "Write better content")

    def test_update_agent_returns_false_for_missing(self):
        reg = self._make_registry()
        self.assertFalse(reg.update_agent("nonexistent", {"goal": "test"}))

    def test_delete_agent_removes_from_registry(self):
        reg = self._make_registry()
        agent = reg.add_agent({"name": "Temp", "role": "Writer", "goal": "Write"})
        result = reg.delete_agent(agent["id"])
        self.assertTrue(result)
        self.assertIsNone(reg.get_by_id(agent["id"]))

    def test_delete_agent_returns_false_for_missing(self):
        reg = self._make_registry()
        self.assertFalse(reg.delete_agent("nonexistent"))

    def test_update_status_changes_status(self):
        reg = self._make_registry()
        agent = reg.add_agent({"name": "Worker", "role": "Writer", "goal": "Write"})
        result = reg.update_status(agent["id"], "Busy")
        self.assertTrue(result)
        updated = reg.get_by_id(agent["id"])
        self.assertEqual(updated["status"], "Busy")
        self.assertIsNotNone(updated["last_used_at"])

    def test_find_by_name_returns_agent(self):
        reg = self._make_registry()
        reg.add_agent({"name": "Creative Writer", "role": "Writer", "goal": "Write"})
        found = reg.find_by_name("Creative Writer")
        self.assertIsNotNone(found)
        self.assertEqual(found["name"], "Creative Writer")

    def test_find_by_name_case_insensitive(self):
        reg = self._make_registry()
        reg.add_agent({"name": "Writer Pro", "role": "Writer", "goal": "Write"})
        found = reg.find_by_name("writer pro")
        self.assertIsNotNone(found)

    def test_find_by_name_returns_none_for_missing(self):
        reg = self._make_registry()
        self.assertIsNone(reg.find_by_name("Ghost"))

    def test_find_idle_agent_by_role(self):
        reg = self._make_registry()
        reg.add_agent({"name": "Writer A", "role": "Content Writer", "goal": "Write", "tools": []})
        found = reg.find_idle_agent("Content Writer", [])
        self.assertIsNotNone(found)
        self.assertEqual(found["name"], "Writer A")

    def test_find_idle_agent_by_tools(self):
        reg = self._make_registry()
        reg.add_agent({"name": "Researcher", "role": "Research", "goal": "Research", "tools": ["search_web"]})
        found = reg.find_idle_agent("Other Role", ["search_web"])
        self.assertIsNotNone(found)
        self.assertEqual(found["name"], "Researcher")

    def test_to_spec_converts_agent_for_factory(self):
        reg = self._make_registry()
        agent = reg.add_agent({"name": "Spec Agent", "role": "Writer", "goal": "Write", "tools": ["search_web"]})
        spec = reg.to_spec(agent)
        self.assertEqual(spec["name"], "Spec Agent")
        self.assertEqual(spec["role"], "Writer")
        self.assertEqual(spec["tools"], ["search_web"])
        self.assertEqual(spec["id"], agent["id"])

    def test_add_learning_appends_and_caps_at_10(self):
        reg = self._make_registry()
        agent = reg.add_agent({"name": "Learner", "role": "Writer", "goal": "Write"})
        for i in range(15):
            reg.add_learning(agent["id"], {"text": f"Learning {i}"})
        updated = reg.get_by_id(agent["id"])
        self.assertEqual(len(updated["learnings"]), 10)
        self.assertEqual(updated["learnings"][-1]["text"], "Learning 14")

    def test_persists_to_disk(self):
        reg = self._make_registry()
        reg.add_agent({"name": "Persistent", "role": "Writer", "goal": "Write"})
        # Create new registry instance from same file
        reg2 = self._make_registry()
        agents = reg2.list_agents()
        self.assertEqual(len(agents), 1)
        self.assertEqual(agents[0]["name"], "Persistent")


if __name__ == "__main__":
    unittest.main(verbosity=2)
