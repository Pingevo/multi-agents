"""Regression test: pre-execution model validation on plan approval.

Bug: When user approves a plan where agents use routing models (openrouter/free,
openrouter/auto), execution starts and fails with 502 or 404 errors. The user
has no chance to fix the model before execution.

Fix: On plan approval, validate all agent models. If any agent uses a routing
model, return a validation error to the user instead of starting execution.
"""

import unittest
import asyncio
import sys
import os
from unittest.mock import MagicMock, AsyncMock, patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault("OPENROUTER_API_KEY", "test-key-fake")


class TestValidatePlanModels(unittest.TestCase):
    """validate_plan_models must reject routing models for agents."""

    def test_rejects_openrouter_free_for_worker(self):
        """A worker with openrouter/free should fail validation."""
        from app import validate_plan_models

        agent_specs = [
            {"name": "Writer", "role": "Content Writer", "tools": [], "model": "openrouter/free"},
        ]
        errors = validate_plan_models(agent_specs)
        self.assertEqual(len(errors), 1)
        self.assertIn("Writer", errors[0])
        self.assertIn("openrouter/free", errors[0])

    def test_rejects_openrouter_auto_for_worker(self):
        """A worker with openrouter/auto should fail validation."""
        from app import validate_plan_models

        agent_specs = [
            {"name": "Writer", "role": "Content Writer", "tools": [], "model": "openrouter/auto"},
        ]
        errors = validate_plan_models(agent_specs)
        self.assertEqual(len(errors), 1)

    def test_rejects_routing_model_for_tool_agent(self):
        """A tool agent with routing model should fail with tool-specific message."""
        from app import validate_plan_models

        agent_specs = [
            {"name": "ImageGen", "role": "Image Generator", "tools": ["generate_image"], "model": "openrouter/free"},
        ]
        errors = validate_plan_models(agent_specs)
        self.assertEqual(len(errors), 1)
        self.assertIn("ImageGen", errors[0])

    def test_accepts_concrete_model(self):
        """A worker with a concrete model should pass validation."""
        from app import validate_plan_models

        agent_specs = [
            {"name": "Writer", "role": "Content Writer", "tools": [], "model": "meta-llama/llama-3.3-70b-instruct:free"},
        ]
        errors = validate_plan_models(agent_specs)
        self.assertEqual(len(errors), 0)

    def test_accepts_empty_model(self):
        """A worker with empty model (auto) should pass — system will resolve it."""
        from app import validate_plan_models

        agent_specs = [
            {"name": "Writer", "role": "Content Writer", "tools": [], "model": ""},
        ]
        errors = validate_plan_models(agent_specs)
        self.assertEqual(len(errors), 0)

    def test_multiple_errors(self):
        """Multiple agents with routing models should all be reported."""
        from app import validate_plan_models

        agent_specs = [
            {"name": "Writer", "role": "Content Writer", "tools": [], "model": "openrouter/free"},
            {"name": "ImageGen", "role": "Image Generator", "tools": ["generate_image"], "model": "openrouter/auto"},
        ]
        errors = validate_plan_models(agent_specs)
        self.assertEqual(len(errors), 2)

    def test_mixed_valid_and_invalid(self):
        """Only invalid models should be reported; valid ones pass silently."""
        from app import validate_plan_models

        agent_specs = [
            {"name": "Writer", "role": "Content Writer", "tools": [], "model": "meta-llama/llama-3.3-70b-instruct:free"},
            {"name": "ImageGen", "role": "Image Generator", "tools": ["generate_image"], "model": "openrouter/free"},
        ]
        errors = validate_plan_models(agent_specs)
        self.assertEqual(len(errors), 1)
        self.assertIn("ImageGen", errors[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
