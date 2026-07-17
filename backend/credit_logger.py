"""Automatic credit usage logger for OpenRouter."""
import json
import os
from datetime import datetime

CREDIT_LOG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "credit-usage-log.jsonl")
LLM_CALL_LOG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "llm-call-log.jsonl")


def _load_last_usage() -> float | None:
    """Read the last usage value from the log file to survive restarts."""
    try:
        with open(CREDIT_LOG_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if lines:
            last = json.loads(lines[-1])
            return last.get("usage")
    except (FileNotFoundError, json.JSONDecodeError, IndexError):
        pass
    return None


_last_usage = _load_last_usage()
_last_limit_remaining: float | None = None
_last_log_time: float | None = None
_pending_cost = 0.0


def get_pending_cost() -> float:
    """Return accumulated cost since last credit snapshot."""
    return _pending_cost


def reset_pending_cost():
    """Reset pending cost after OpenRouter has updated (credit snapshot written)."""
    global _pending_cost
    _pending_cost = 0.0


def log_credit_snapshot(credits: dict | None, trigger: str = "poll"):
    """Append a credit snapshot to the JSONL log file — only when usage meaningfully changes."""
    global _last_usage, _last_limit_remaining, _last_log_time
    if not credits:
        return
    current_usage = credits.get("usage", 0)
    current_remaining = credits.get("limit_remaining")
    now = datetime.now().timestamp()
    # Dedup: round usage to 2 decimal places to ignore minor oscillations
    usage_rounded = round(current_usage, 2)
    last_rounded = round(_last_usage, 2) if _last_usage is not None else None
    if last_rounded is not None and usage_rounded == last_rounded:
        return
    # Cooldown: at least 30 seconds between log entries
    if _last_log_time is not None and (now - _last_log_time) < 30:
        return
    _last_usage = current_usage
    _last_limit_remaining = current_remaining
    _last_log_time = now
    reset_pending_cost()
    entry = {
        "timestamp": datetime.now().isoformat(),
        "trigger": trigger,
        "limit": credits.get("limit"),
        "limit_remaining": credits.get("limit_remaining"),
        "usage": current_usage,
        "usage_daily": credits.get("usage_daily", 0),
        "usage_weekly": credits.get("usage_weekly", 0),
        "usage_monthly": credits.get("usage_monthly", 0),
        "is_free_tier": credits.get("is_free_tier", True),
    }
    try:
        with open(CREDIT_LOG_PATH, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[CreditLog] Failed to write: {e}", flush=True)


def log_llm_call(
    model: str,
    usage: dict | None,
    caller: str = "",
    prompt_preview: str = "",
):
    """Log a single LLM API call with token usage and cost for billing purposes.

    Args:
        model: The model ID used (e.g. 'openrouter/free', 'google/gemini-3.5-flash')
        usage: The usage dict from OpenRouter response (prompt_tokens, completion_tokens, total_tokens, cost)
        caller: Which part of the system made the call (e.g. 'assess_and_plan', 'agent:Writer#1')
        prompt_preview: First 200 chars of the prompt for reference
    """
    if not usage:
        return
    # Convert Pydantic object (e.g. CompletionUsage) to dict if needed
    if hasattr(usage, "model_dump"):
        usage = usage.model_dump()
    elif not isinstance(usage, dict):
        usage = {
            "prompt_tokens": getattr(usage, "prompt_tokens", 0),
            "completion_tokens": getattr(usage, "completion_tokens", 0),
            "total_tokens": getattr(usage, "total_tokens", 0),
            "cost": getattr(usage, "cost", 0),
        }
    cost = usage.get("cost", 0)
    global _pending_cost
    _pending_cost += cost
    entry = {
        "timestamp": datetime.now().isoformat(),
        "model": model,
        "caller": caller,
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
        "cost": cost,
        "prompt_preview": prompt_preview[:200] if prompt_preview else "",
    }
    try:
        with open(LLM_CALL_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[LLMCallLog] Failed to write: {e}", flush=True)
