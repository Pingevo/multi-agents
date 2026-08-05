"""Test: Manager review prompt must contain current date (parity with agents).

Bug: Task B injected "Today's date" into agent backstory (factory.py) so
agents know what "today" is. But the Manager reviewer prompt
(_batch_manager_review in orchestrator.py) does NOT receive the date.
Manager then rejects valid data with 2026 dates as "future/hallucination"
because it doesn't know today is 2026.

This is the same bug as Task B but at the Manager reviewer side.

Seam: _build_manager_review_prompt(manager_persona, manager_goal, user_input,
      agents_data, retry_count, template_contracts, quality_criteria) -> str
Extracted from _batch_manager_review so the prompt can be tested without
making real LLM calls.
"""

import sys
from datetime import datetime
sys.path.insert(0, '/Users/its-dev2/my-agent-app')


class TestManagerReviewPromptDateInjection:
    """Verify Manager review prompt contains current date (parity with agent backstory)."""

    def _make_args(self):
        return {
            "manager_persona": "You are the Manager.",
            "manager_goal": "Review agent outputs for quality.",
            "user_input": "Find latest news",
            "agents_data": [
                {"idx": 0, "name": "Researcher", "role": "Analyst",
                 "goal": "Research news", "output": "News from August 2026"},
            ],
            "retry_count": 0,
            "template_contracts": "",
            "quality_criteria": "",
        }

    def test_prompt_contains_today_date_label(self):
        """Manager review prompt must contain 'Today's date' label."""
        from backend.core.orchestrator import _build_manager_review_prompt
        prompt = _build_manager_review_prompt(**self._make_args())
        assert "Today's date" in prompt, (
            "Manager review prompt must inject current date so Manager knows "
            "what 'today' is — otherwise it rejects valid 2026 data as 'future'. "
            f"Got: {prompt[:500]}"
        )

    def test_prompt_contains_current_year(self):
        """Manager review prompt must contain the current year."""
        from backend.core.orchestrator import _build_manager_review_prompt
        prompt = _build_manager_review_prompt(**self._make_args())
        current_year = str(datetime.now().year)
        assert current_year in prompt, (
            f"Manager review prompt must contain current year ({current_year}). "
            f"Got: {prompt[:500]}"
        )

    def test_date_appears_before_agent_outputs(self):
        """Date must appear before agent outputs so Manager reads it first."""
        from backend.core.orchestrator import _build_manager_review_prompt
        args = self._make_args()
        args["agents_data"] = [
            {"idx": 0, "name": "Researcher", "role": "Analyst",
             "goal": "Research", "output": "OUTPUT_MARKER_HERE"},
        ]
        prompt = _build_manager_review_prompt(**args)
        date_pos = prompt.find("Today's date")
        output_pos = prompt.find("OUTPUT_MARKER_HERE")
        assert date_pos != -1 and output_pos != -1
        assert date_pos < output_pos, (
            "Date must appear before agent outputs so Manager reads it first"
        )

    def test_date_present_with_multiple_agents(self):
        """Date injection must work when reviewing multiple agents."""
        from backend.core.orchestrator import _build_manager_review_prompt
        args = self._make_args()
        args["agents_data"] = [
            {"idx": 0, "name": "Writer", "role": "Author", "goal": "Write", "output": "content1"},
            {"idx": 1, "name": "Editor", "role": "Editor", "goal": "Edit", "output": "content2"},
        ]
        prompt = _build_manager_review_prompt(**args)
        assert "Today's date" in prompt
