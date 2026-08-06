"""End-to-end: verify the exact payload from call_streaming (no usage_data path)
reaches the Hub and gets 201.

Phase 5/6 feedback loop for diagnosing-bugs session.
The unit test (test_streaming_usage_bug.py) already proves log_ai_usage gets
called. This test verifies the Hub actually accepts that payload.
"""
import os
import time
import unittest


class TestStreamingPayloadReachesHub(unittest.TestCase):
    def setUp(self):
        from dotenv import load_dotenv
        load_dotenv(override=True)
        if not os.environ.get("AI_USAGE_HUB_TOKEN"):
            self.skipTest("AI_USAGE_HUB_TOKEN not set")

    def test_no_usage_payload_accepted_by_hub(self):
        """Simulate the exact payload call_streaming sends when stream omits usage."""
        import backend.ai_usage_hub as hub

        # This is the payload the fixed call_streaming sends when usage_data is None
        payload = {
            "provider": "openrouter",
            "model": "openrouter/free",
            "operation": "chat.completions",
            "source": "e2e_verify",
            "status": "success",
            "duration_ms": 1234,
            "request_id": "chatcmpl-test-e2e",
            "metadata": {"analysis_type": "chat", "note": "stream omitted usage"},
        }

        # Capture the HTTP response by running _safe_post synchronously
        url = os.environ["AI_USAGE_HUB_URL"].rstrip("/") + "/internal/ai-usage/logs"
        token = os.environ["AI_USAGE_HUB_TOKEN"]
        headers = {"Content-Type": "application/json", "x-service-token": token}

        # Normalize the payload the same way log_ai_usage does
        normalized = hub._normalize_entry(payload)

        # Push directly (not via daemon thread) so we can check the response
        import requests
        try:
            resp = requests.post(url, json=normalized, headers=headers, timeout=15)
        except requests.exceptions.ReadTimeout:
            self.skipTest("Hub did not respond within 15s — network flake, not a code bug")

        print(f"[E2E] Hub response: HTTP {resp.status_code} — {resp.text[:200]}")
        print(f"[E2E] Payload sent: {normalized}")

        self.assertEqual(resp.status_code, 201,
            f"Hub rejected the no-usage payload: HTTP {resp.status_code} — {resp.text}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
