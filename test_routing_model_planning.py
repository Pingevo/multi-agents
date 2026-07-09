"""Regression test: empty streaming responses must not hang the system.

Bug: When the planning LLM returns HTTP 200 with an empty SSE stream, the
streaming loop has no total timeout, so the UI hangs forever and no error
reaches the user. The user may be using any model (including openrouter/free),
which sometimes works and sometimes returns an empty stream.

This test asserts that:
1. assess_and_plan returns a user-facing error when the stream is empty.
2. assess_and_plan does not hang on an empty stream — completes within seconds.
3. Normal planning responses are parsed correctly.
"""

import unittest
import asyncio
import sys
import os
import time
from unittest.mock import MagicMock, AsyncMock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Required env for LLMManager
os.environ.setdefault("OPENROUTER_API_KEY", "test-key-fake")


class TestEmptyStreamReturnsError(unittest.TestCase):
    """Empty streaming response must return error, not hang."""

    def test_empty_stream_returns_error_within_timeout(self):
        """If the LLM returns an empty stream, assess_and_plan must return an error
        within a bounded time (not hang forever)."""
        from app import CentralSecretary, LLMManager

        llm_mgr = MagicMock(spec=LLMManager)
        llm_mgr._selected_model = "openrouter/free"  # user may use any model
        llm_mgr._default_model = "openrouter/auto"
        llm_mgr.tier = "free"

        # Simulate empty stream: yields nothing, returns immediately
        def empty_stream(prompt):
            yield from ()  # empty generator

        llm_mgr.call_streaming = empty_stream
        llm_mgr.call_async = AsyncMock(return_value="")

        secretary = CentralSecretary(llm_mgr)

        start = time.time()
        result = asyncio.get_event_loop().run_until_complete(
            secretary.assess_and_plan(
                "สร้าง content plan สำหรับร้านกาแฟ 1 โพสต์",
                stream_callback=AsyncMock(),
            )
        )
        elapsed = time.time() - start

        # Must complete within 10 seconds (not hang)
        self.assertLess(elapsed, 10.0, "assess_and_plan hung on empty stream")
        # Must return an error message
        self.assertEqual(result.get("action"), "chat")
        self.assertIn("ว่างเปล่า", result.get("message", ""))

    def test_timeout_returns_error(self):
        """If the LLM stream never yields chunks, assess_and_plan must timeout and
        return an error instead of hanging forever."""
        from app import CentralSecretary, LLMManager
        import threading

        llm_mgr = MagicMock(spec=LLMManager)
        llm_mgr._selected_model = "openrouter/free"
        llm_mgr._default_model = "openrouter/auto"
        llm_mgr.tier = "free"

        # Simulate a stream that blocks forever
        def blocking_stream(prompt):
            while True:
                threading.Event().wait(1)

        llm_mgr.call_streaming = blocking_stream
        llm_mgr.call_async = AsyncMock(return_value="")

        secretary = CentralSecretary(llm_mgr)

        start = time.time()
        result = asyncio.get_event_loop().run_until_complete(
            secretary.assess_and_plan(
                "สร้าง content plan สำหรับร้านกาแฟ 1 โพสต์",
                stream_callback=AsyncMock(),
            )
        )
        elapsed = time.time() - start

        # Must complete within 35 seconds (30s timeout + buffer)
        self.assertLess(elapsed, 35.0, "assess_and_plan did not timeout")
        self.assertEqual(result.get("action"), "chat")
        self.assertTrue(
            "ว่างเปล่า" in result.get("message", ""),
            result.get("message", "")
        )


class TestNormalResponseParsed(unittest.TestCase):
    """Non-empty responses should be parsed normally."""

    def test_valid_json_response_returns_plan(self):
        """A normal JSON response should be parsed into a plan action."""
        from app import CentralSecretary, LLMManager

        llm_mgr = MagicMock(spec=LLMManager)
        llm_mgr._selected_model = "openrouter/free"
        llm_mgr._default_model = "openrouter/auto"
        llm_mgr.tier = "free"

        valid_response = (
            '{"action":"plan","summary":"test","agents":[],'
            '"model_assignment":{"manager":"openrouter/free","workers":{}},'
            '"image_model":"","video_model":"","search_model":""}'
        )

        def non_empty_stream(prompt):
            yield valid_response

        llm_mgr.call_streaming = non_empty_stream
        llm_mgr.call_async = AsyncMock(return_value=valid_response)

        secretary = CentralSecretary(llm_mgr)

        result = asyncio.get_event_loop().run_until_complete(
            secretary.assess_and_plan(
                "สร้าง content plan สำหรับร้านกาแฟ 1 โพสต์",
                stream_callback=AsyncMock(),
            )
        )

        self.assertEqual(result.get("action"), "plan")


if __name__ == "__main__":
    unittest.main(verbosity=2)
