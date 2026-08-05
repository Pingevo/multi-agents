"""Tests for backend.ai_usage_hub — AI Usage Hub client (fire-and-forget HTTP push).

Seams under test (confirmed with user):
- log_ai_usage(entry) — public interface; tests inject _transport to observe calls
- env vars AI_USAGE_HUB_URL / AI_USAGE_HUB_TOKEN — guard the no-op path
"""
import os
import threading
import unittest
from unittest.mock import patch, MagicMock

import backend.ai_usage_hub as hub
from backend.ai_usage_hub import log_ai_usage


class _CaptureTransport:
    """Test double — records every call instead of doing HTTP."""
    def __init__(self):
        self.calls = []
        self.lock = threading.Lock()
    def __call__(self, url, json, headers, timeout):
        with self.lock:
            self.calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        return MagicMock(status_code=200, json=lambda: {"success": True})


class TestLogAiUsagePushesToHub(unittest.TestCase):
    def setUp(self):
        self.capture = _CaptureTransport()
        self._restore_env = {}
        self._restore_transport = hub._transport
        hub._transport = self.capture
        for k in ("AI_USAGE_HUB_URL", "AI_USAGE_HUB_TOKEN"):
            self._restore_env[k] = os.environ.get(k)
            os.environ[k] = f"placeholder_{k}"
        # Clear contextvars so each test starts clean
        hub.ai_user_ctx.set("")
        hub.ai_reference_ctx.set("")
        hub.ai_source_ctx.set("")

    def tearDown(self):
        hub._transport = self._restore_transport
        for k, v in self._restore_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_pushes_one_call_with_provider_when_minimal_entry(self):
        """Slice 1 red→green: minimal entry {provider} still reaches transport."""
        log_ai_usage({"provider": "openrouter"})
        self.assertEqual(len(self.capture.calls), 1)
        payload = self.capture.calls[0]["json"]
        self.assertEqual(payload["provider"], "openrouter")

    def test_passes_all_fields_through(self):
        """Every documented field survives the trip to the transport."""
        entry = {
            "provider": "openrouter",
            "model": "google/gemini-2.5-flash",
            "operation": "chat.completions",
            "source": "classifyPost",
            "user": "E1234 สมชาย",
            "reference": "project_id:9981",
            "request_id": "abc-123",
            "environment": "production",
            "prompt_tokens": 1200,
            "completion_tokens": 340,
            "units": {"images_processed": 3},
            "cost_usd": 0.00042,
            "cost_thb": 0.0153,
            "duration_ms": 850,
            "attempt": 1,
            "status": "success",
            "http_status": 200,
            "error_message": "rate limit exceeded",
            "raw_usage": {"x": 1},
            "metadata": {"channel_id": "9981"},
        }
        log_ai_usage(entry)
        payload = self.capture.calls[0]["json"]
        for k, v in entry.items():
            self.assertEqual(payload[k], v, f"field {k!r} mismatch")

    def test_defaults_provider_to_unknown_when_missing(self):
        """Spec says provider is mandatory — missing provider surfaces as
        "unknown" in the dashboard so missing-provider bugs are visible,
        not silently masked as "openrouter"."""
        log_ai_usage({"model": "x"})
        payload = self.capture.calls[0]["json"]
        self.assertEqual(payload["provider"], "unknown")

    def test_uses_contextvars_for_user_reference_source_when_not_passed(self):
        """When caller omits user/reference/source, fall back to contextvars."""
        hub.ai_user_ctx.set("system")
        hub.ai_reference_ctx.set("task:42")
        hub.ai_source_ctx.set("evaluatePersonDay")
        log_ai_usage({"provider": "openrouter"})
        payload = self.capture.calls[0]["json"]
        self.assertEqual(payload["user"], "system")
        self.assertEqual(payload["reference"], "task:42")
        self.assertEqual(payload["source"], "evaluatePersonDay")

    def test_explicit_entry_overrides_contextvars(self):
        """Explicit fields win over contextvar defaults."""
        hub.ai_user_ctx.set("system")
        log_ai_usage({"provider": "openrouter", "user": "Ping (admin)"})
        payload = self.capture.calls[0]["json"]
        self.assertEqual(payload["user"], "Ping (admin)")

    def test_sends_service_token_header(self):
        """Auth: x-service-token header carries the configured token."""
        os.environ["AI_USAGE_HUB_TOKEN"] = "svc_testtoken123"
        log_ai_usage({"provider": "openrouter"})
        headers = self.capture.calls[0]["headers"]
        self.assertEqual(headers["x-service-token"], "svc_testtoken123")
        self.assertEqual(headers["Content-Type"], "application/json")

    def test_posts_to_logs_endpoint(self):
        """URL = AI_USAGE_HUB_URL (trailing slash stripped) + /internal/ai-usage/logs."""
        os.environ["AI_USAGE_HUB_URL"] = "https://digital.in.th/"
        log_ai_usage({"provider": "openrouter"})
        self.assertEqual(self.capture.calls[0]["url"], "https://digital.in.th/internal/ai-usage/logs")

    def test_strips_none_fields_from_payload(self):
        """None fields should not be sent (Hub treats absent = unknown, None = invalid)."""
        log_ai_usage({"provider": "openrouter", "error_message": None, "model": "x"})
        payload = self.capture.calls[0]["json"]
        self.assertNotIn("error_message", payload)
        self.assertIn("model", payload)


class TestLogAiUsageNoOpAndSafety(unittest.TestCase):
    def setUp(self):
        self._restore_env = {}
        for k in ("AI_USAGE_HUB_URL", "AI_USAGE_HUB_TOKEN"):
            self._restore_env[k] = os.environ.get(k)

    def tearDown(self):
        for k, v in self._restore_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_noop_when_url_unset(self):
        """If AI_USAGE_HUB_URL is missing, do not attempt any HTTP."""
        os.environ.pop("AI_USAGE_HUB_URL", None)
        os.environ["AI_USAGE_HUB_TOKEN"] = "svc_x"
        transport = MagicMock()
        with patch.object(hub, "_transport", transport):
            log_ai_usage({"provider": "openrouter"})
        transport.assert_not_called()

    def test_noop_when_token_unset(self):
        """If AI_USAGE_HUB_TOKEN is missing, do not attempt any HTTP."""
        os.environ["AI_USAGE_HUB_URL"] = "https://digital.in.th"
        os.environ.pop("AI_USAGE_HUB_TOKEN", None)
        transport = MagicMock()
        with patch.object(hub, "_transport", transport):
            log_ai_usage({"provider": "openrouter"})
        transport.assert_not_called()

    def test_never_throws_when_transport_raises(self):
        """Fire-and-forget: a failing transport must not propagate."""
        os.environ["AI_USAGE_HUB_URL"] = "https://digital.in.th"
        os.environ["AI_USAGE_HUB_TOKEN"] = "svc_x"
        def boom(*a, **kw):
            raise ConnectionError("hub down")
        with patch.object(hub, "_transport", boom):
            # Must not raise
            log_ai_usage({"provider": "openrouter"})

    def test_never_throws_on_normal_call_without_env(self):
        """Belt-and-braces: even with no env at all, calling is safe."""
        os.environ.pop("AI_USAGE_HUB_URL", None)
        os.environ.pop("AI_USAGE_HUB_TOKEN", None)
        log_ai_usage({"provider": "openrouter", "model": "x"})


if __name__ == "__main__":
    unittest.main()
