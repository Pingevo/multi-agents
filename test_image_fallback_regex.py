"""Regression tests for image fallback regex extraction.

Tests that the regex patterns in chat.py correctly extract image prompts
from various agent output formats.
"""

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("OPENROUTER_API_KEY", "test-key-fake")


class TestImageFallbackRegex(unittest.TestCase):
    """The fallback regex patterns must extract prompts from agent output."""

    def _extract_prompt(self, output_text: str) -> str | None:
        """Replicate the fallback regex chain from chat.py."""
        img_match = re.search(r'```\s*\n([A-Za-z][^`]{20,})\n```', output_text)
        if not img_match:
            img_match = re.search(r'Prompt[:\s]+([A-Za-z][^\n]{20,})', output_text)
        if not img_match:
            img_match = re.search(r'[Ii]mage [Pp]rompt[:\s]+([A-Za-z][^\n]{20,})', output_text)
        if not img_match:
            img_match = re.search(r'"([A-Z][^"]{30,})"', output_text)
        if not img_match:
            img_match = re.search(r'\*\*([A-Z][^*]{30,})\*\*', output_text)
        if not img_match:
            img_match = re.search(r'generate_image\([^)]*"([^"]{20,})"', output_text)
        if img_match:
            return img_match.group(1).strip()
        return None

    def test_code_block_prompt(self):
        output = "Here is the prompt:\n```\nA beautiful sunset over the ocean with golden light\n```"
        result = self._extract_prompt(output)
        self.assertIsNotNone(result)
        self.assertIn("sunset", result.lower())

    def test_prompt_prefix(self):
        output = "Prompt: A modern product poster for iPhone charger with clean design"
        result = self._extract_prompt(output)
        self.assertIsNotNone(result)
        self.assertIn("product poster", result.lower())

    def test_image_prompt_prefix(self):
        output = "Image prompt: A sleek smartphone on a white background with soft shadows"
        result = self._extract_prompt(output)
        self.assertIsNotNone(result)
        self.assertIn("smartphone", result.lower())

    def test_quoted_prompt(self):
        output = 'The agent suggested "A professional advertisement poster for a tech gadget with vibrant colors" as the prompt.'
        result = self._extract_prompt(output)
        self.assertIsNotNone(result)
        self.assertIn("advertisement", result.lower())

    def test_bold_prompt(self):
        output = "**A stunning product photography shot of a wireless charger on marble surface**"
        result = self._extract_prompt(output)
        self.assertIsNotNone(result)
        self.assertIn("product photography", result.lower())

    def test_generate_image_call(self):
        output = 'The agent called generate_image("A futuristic city skyline at night with neon lights")'
        result = self._extract_prompt(output)
        self.assertIsNotNone(result)
        self.assertIn("city skyline", result.lower())

    def test_no_match_returns_none(self):
        output = "The agent completed the task successfully but did not provide any image prompt."
        result = self._extract_prompt(output)
        self.assertIsNone(result)

    def test_empty_output_returns_none(self):
        result = self._extract_prompt("")
        self.assertIsNone(result)

    def test_short_prompt_no_match(self):
        """Prompts shorter than 20 chars should not match (minimum length filter)."""
        output = "Prompt: too short"
        result = self._extract_prompt(output)
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
