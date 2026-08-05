"""Regression tests for date injection in agent backstory.

Bug: Agent rejected valid box office data as "future information" because
it didn't know the current date. Market standard (Claude/ChatGPT/Gemini)
injects current date into the system prompt automatically.

Seam: AgentFactory._build_agent_backstory(spec) → must contain current date
"""

import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("OPENROUTER_API_KEY", "test-key-fake")


class TestDateInjection(unittest.TestCase):
    """_build_agent_backstory must inject current date so agents know 'today'."""

    def _make_factory(self):
        from backend.agents.factory import AgentFactory
        # _build_agent_backstory doesn't use llm_manager or tool_registry
        return AgentFactory(llm_manager=None, tool_registry=None)

    def test_backstory_contains_current_date(self):
        factory = self._make_factory()
        spec = {"name": "Researcher", "role": "Box Office Analyst", "goal": "Research"}
        backstory = factory._build_agent_backstory(spec)
        today = datetime.now()
        # Must contain today's date in a human-readable form
        self.assertIn(str(today.year), backstory,
                      "Agent backstory must contain current year so it knows what 'today' is")

    def test_backstory_contains_today_keyword(self):
        """Agent must see an explicit 'Today's date' label, not just a year number
        that could appear in other context (e.g. a movie release year)."""
        factory = self._make_factory()
        spec = {"name": "Researcher", "role": "Analyst", "goal": "Research"}
        backstory = factory._build_agent_backstory(spec)
        self.assertIn("Today's date", backstory,
                      "Backstory must label the date explicitly as 'Today's date'")

    def test_date_appears_in_full_backstory_with_other_fields(self):
        """Date injection must not break when other persona fields are present."""
        factory = self._make_factory()
        spec = {
            "name": "Researcher",
            "role": "Box Office Analyst",
            "goal": "Research box office data",
            "backstory": "You are an expert in box office numbers.",
            "personality": {"tone": "professional", "language": "English"},
            "expertise": ["data analysis", "web search"],
        }
        backstory = factory._build_agent_backstory(spec)
        self.assertIn("Today's date", backstory)
        self.assertIn("Box Office Analyst", backstory)
        self.assertIn("data analysis", backstory)


if __name__ == "__main__":
    unittest.main()
