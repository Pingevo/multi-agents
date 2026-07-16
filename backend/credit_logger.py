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


def log_credit_snapshot(credits: dict | None, trigger: str = "poll"):
    """Append a credit snapshot to the JSONL log file — only when usage changes."""
    global _last_usage
    if not credits:
        return
    current_usage = credits.get("usage", 0)
    if _last_usage is not None and current_usage == _last_usage:
        return
    _last_usage = current_usage
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
    entry = {
        "timestamp": datetime.now().isoformat(),
        "model": model,
        "caller": caller,
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
        "cost": usage.get("cost", 0),
        "prompt_preview": prompt_preview[:200] if prompt_preview else "",
    }
    try:
        with open(LLM_CALL_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[LLMCallLog] Failed to write: {e}", flush=True)
