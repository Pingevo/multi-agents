"""AI Usage Hub client — fire-and-forget HTTP push to https://digital.in.th.

Single source of truth for logging every AI/scraping provider call to the
central AI Usage Hub. Replaces the old local-only `credit_logger.log_llm_call`.

Interface (one function, one dict):
    log_ai_usage(entry: dict) -> None

Invariants (what callers can rely on):
1. Never raises — fire-and-forget. A failing Hub must not break the main flow.
2. If AI_USAGE_HUB_URL or AI_USAGE_HUB_TOKEN is unset → silent no-op (with
   a one-time console warning so missing config is visible, not silent).
3. If `provider` is missing → defaults to "unknown" (spec says mandatory;
   surfacing as "unknown" makes missing-provider bugs visible in the
   dashboard instead of silently masking them as "openrouter").
4. `cost_usd` is passed through unchanged — never estimated here.
5. HTTP push runs in a daemon thread with a 5s timeout — does not block caller.
6. contextvars (`ai_user_ctx`, `ai_reference_ctx`, `ai_source_ctx`) supply
   defaults for `user`, `reference`, `source` when the caller omits them.
   Explicit fields in `entry` always win over contextvars.

Env vars:
- AI_USAGE_HUB_URL   e.g. https://digital.in.th
- AI_USAGE_HUB_TOKEN e.g. svc_<64 hex>  (issued by sellcenter team)
"""
import contextvars
import os
import threading


# ============================================================
# Contextvars — set by chat handler / orchestrator, read as defaults
# ============================================================
ai_user_ctx: contextvars.ContextVar = contextvars.ContextVar("ai_usage_user", default="")
ai_reference_ctx: contextvars.ContextVar = contextvars.ContextVar("ai_usage_reference", default="")
ai_source_ctx: contextvars.ContextVar = contextvars.ContextVar("ai_usage_source", default="")

# Internal handle used by tests to swap the HTTP transport without monkeypatching
# the network. Default points to a thin requests.post wrapper.
_transport = None  # set below after defining _default_transport


def _default_transport(url, json, headers, timeout):
    """Default HTTP transport — thin wrapper over requests.post."""
    import requests
    return requests.post(url, json=json, headers=headers, timeout=timeout)


_transport = _default_transport


def _normalize_entry(entry: dict) -> dict:
    """Apply defaults and strip None fields so the Hub never sees nulls.

    - provider default = "unknown" (spec says mandatory; callers MUST set it.
      Default surfaces missing-provider bugs in the dashboard instead of
      silently masking them as "openrouter".)
    - user / reference / source pulled from contextvars when absent in entry
    - None-valued fields removed (Hub treats absent = unknown; None = invalid)
    """
    payload = dict(entry)  # shallow copy — caller's dict stays untouched
    payload.setdefault("provider", "unknown")
    if "user" not in payload or not payload.get("user"):
        cv = ai_user_ctx.get("")
        if cv:
            payload["user"] = cv
    if "reference" not in payload or not payload.get("reference"):
        cv = ai_reference_ctx.get("")
        if cv:
            payload["reference"] = cv
    if "source" not in payload or not payload.get("source"):
        cv = ai_source_ctx.get("")
        if cv:
            payload["source"] = cv
    # Drop None values — Hub treats absent as "unknown", None as malformed
    return {k: v for k, v in payload.items() if v is not None}


def log_ai_usage(entry: dict) -> None:
    """Push one AI-usage event to the Hub. Fire-and-forget — never raises.

    See module docstring for invariants. `entry` keys match the Hub API doc
    (provider, model, operation, source, user, reference, request_id,
    environment, prompt_tokens, completion_tokens, units, cost_usd, cost_thb,
    duration_ms, attempt, status, http_status, error_message, raw_usage,
    metadata).
    """
    try:
        url = os.environ.get("AI_USAGE_HUB_URL")
        token = os.environ.get("AI_USAGE_HUB_TOKEN")
        if not url or not token:
            if not getattr(log_ai_usage, "_warned", False):
                print("[ai-usage-hub] AI_USAGE_HUB_URL or AI_USAGE_HUB_TOKEN not set — logs will NOT be sent to Hub. Set them in .env to enable.", flush=True)
                log_ai_usage._warned = True
            return  # not configured — silent no-op (per Hub doc example code)

        payload = _normalize_entry(entry)
        headers = {"Content-Type": "application/json", "x-service-token": token}
        full_url = url.rstrip("/") + "/internal/ai-usage/logs"

        # Daemon thread — caller never waits, never sees the exception
        t = threading.Thread(
            target=_safe_post,
            args=(full_url, payload, headers),
            daemon=True,
        )
        t.start()
    except Exception:
        # Belt-and-braces: even normalization must not break the caller
        pass


def _safe_post(url: str, payload: dict, headers: dict) -> None:
    """Run the transport in a try/except so thread death stays silent."""
    try:
        timeout = float(os.environ.get("AI_USAGE_HUB_TIMEOUT", "5"))
        resp = _transport(url, json=payload, headers=headers, timeout=timeout)
        if resp.status_code >= 400:
            print(f"[ai-usage-hub] push failed: HTTP {resp.status_code} — {resp.text[:200]}", flush=True)
    except Exception as e:
        # Fire-and-forget: Hub down, network error, etc. — log and swallow.
        print(f"[ai-usage-hub] push error: {e}", flush=True)
