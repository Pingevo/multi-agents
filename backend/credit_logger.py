"""LLM call logger — logs every LLM API call with cost, model, agent, and user prompt.

This is the single source of truth for credit usage analysis.
Every LLM call (planning, agent execution, manager review, synthesis, streaming)
is logged here, so total credit usage = sum of all cost fields.
"""
import json
import os
from datetime import datetime

LLM_CALL_LOG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "llm-call-log.jsonl")


def _get_user_prompt() -> str:
    """Get user_prompt from contextvars (cross-thread) or _thread_local fallback."""
    try:
        from backend.globals import user_prompt_ctx
        val = user_prompt_ctx.get("")
        if val:
            return val
    except ImportError:
        pass
    try:
        from backend.globals import _thread_local
        return getattr(_thread_local, "user_prompt", "")
    except ImportError:
        return ""


def log_llm_call(
    model: str,
    usage: dict | None,
    caller: str = "",
    prompt_preview: str = "",
    user_prompt: str = "",
):
    """Log a single LLM API call with token usage and cost.

    Args:
        model: The model ID used (e.g. 'openrouter/free', 'google/gemini-3.5-flash')
        usage: The usage dict from OpenRouter response (prompt_tokens, completion_tokens, total_tokens, cost)
        caller: Which part of the system made the call (e.g. 'assess_and_plan', 'agent:Writer#1')
        prompt_preview: First 200 chars of the prompt for reference
        user_prompt: The original user message that triggered this call (auto-filled from _thread_local)
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
    # Auto-populate user_prompt from _thread_local if not provided
    if not user_prompt:
        user_prompt = _get_user_prompt()
    entry = {
        "timestamp": datetime.now().isoformat(),
        "model": model,
        "caller": caller,
        "user_prompt": user_prompt[:200] if user_prompt else "",
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
