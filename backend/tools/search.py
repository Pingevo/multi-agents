"""Search tool using OpenRouter AI-selected search model."""

from crewai.tools import tool
from backend.globals import _progress_callback, _thread_local
import backend.globals as _globals
from backend.utils import _sanitize_error
from backend.llm.manager import LLMManager
from backend.tools.search_adapter import SearchAdapter


def _get_search_config() -> dict:
    """Read search_config from _thread_local (set by orchestrator from agent spec).

    Falls back to empty dict (→ defaults) when not set. Mirrors the
    max_search_calls pattern for per-agent, parallel-safe config.
    """
    return getattr(_thread_local, "search_config", {}) or {}


def _build_search_adapter(llm_mgr: LLMManager) -> SearchAdapter:
    """Build a SearchAdapter wired to llm_mgr + ModelDiscoveryService.

    The discovery service is constructed lazily from llm_mgr's config so the
    adapter can check model capabilities (tools vs web_search_options) without
    the caller knowing about catalog internals.
    """
    discovery = None
    try:
        from backend.llm.discovery import ModelDiscoveryService
        discovery = ModelDiscoveryService(
            base_url=llm_mgr.base_url, api_key=llm_mgr.api_key,
        )
    except Exception:
        pass  # adapter falls back to prefix heuristic when discovery unavailable
    return SearchAdapter(llm_manager=llm_mgr, discovery=discovery)


def _call_openrouter_web_search(llm_mgr: LLMManager, model: str, query: str) -> str:
    """Call OpenRouter chat completions for web search, picking the format per model.

    Delegates to SearchAdapter which checks model capability via
    ModelDiscoveryService and sends `tools` (server tool) for tools-capable
    models or `web_search_options` for perplexity built-in search models.
    Fixes the perplexity 404 bug (P0.2).
    """
    adapter = _build_search_adapter(llm_mgr)
    return adapter.search(query, model, search_config=_get_search_config())


def _check_search_call_limit() -> str | None:
    """Check per-agent search call limit. Returns refusal message if limit reached, None if allowed.

    Reads _thread_local.max_search_calls (0 = unlimited) and increments
    _thread_local.search_call_count. This is extracted so tests can verify
    the limit logic without making real HTTP calls.
    """
    max_search_calls = getattr(_thread_local, "max_search_calls", 0) or 0
    if max_search_calls <= 0:
        return None  # unlimited
    count = getattr(_thread_local, "search_call_count", 0) or 0
    if count >= max_search_calls:
        print(f"[SearchTool] Limit reached: {count}/{max_search_calls} — refusing further search", flush=True)
        return (
            f"⚠️ ค้นหาครบ {max_search_calls} ครั้งแล้วตามขีดจำกัดของ agent "
            f"(max_search_calls={max_search_calls}) "
            "กรุณาสรุปผลจากข้อมูลที่ค้นพบแล้ว และระบุว่าอาจมีข้อมูลเพิ่มเติมที่ไม่ได้ค้น"
        )
    _thread_local.search_call_count = count + 1
    print(f"[SearchTool] Call {count + 1}/{max_search_calls}", flush=True)
    return None


def _resolve_search_model(selected_model: str = "", default_model: str = "") -> str:
    """Resolve which model search_web should use.

    Delegates to SearchAdapter.resolve_search_model — the single decision point
    (P0.2 consolidation per ADR-0004). The ai_search_model is read from
    _globals._search_model (set by orchestrator from cl.user_session).

    Resolution order (per SYSTEM_PROTOCOL.md "ใช้ paid LLM (ไม่ใช่ free tier)"):
    1. ai_search_model (user-selected search model from plan approval)
    2. selected_model (user's top-bar model selection)
    3. default_model (LLMManager._default_model)
    4. "openrouter/free" (last resort, only when nothing else available)

    Thin wrapper — keeps the legacy test seam (test_search_model_fallback.py,
    test_search_model_propagation.py) while concentrating the resolution
    logic in the adapter.
    """
    # Read dynamically from globals module — `from X import Y` would copy the
    # binding at import time, so reassignment in orchestrator (global _search_model)
    # wouldn't be visible here. This is the Python module-rebinding gotcha.
    ai_search_model = _globals._search_model or ""
    return SearchAdapter().resolve_search_model(
        ai_search_model=ai_search_model,
        selected_model=selected_model,
        default_model=default_model,
    )


@tool
def search_web(query: str) -> str:
    """Search the web for current information using OpenRouter (AI-selected search model).

    Returns factual information with source URLs. Always cite sources.
    """
    global _progress_callback
    if _progress_callback:
        _progress_callback(50, "🔍 กำลังค้นหาข้อมูลจากเว็บ...")

    if not query or not query.strip():
        return "กรุณาระบุคำค้นหา"

    # Per-agent search call limit (config-driven via agent spec max_search_calls)
    limit_msg = _check_search_call_limit()
    if limit_msg:
        return limit_msg

    llm_mgr = LLMManager()
    # Resolve search model: ai_search_model → selected_model → default → free (last resort)
    # Per SYSTEM_PROTOCOL: prefer paid model over free tier
    import chainlit as cl
    _selected = ""
    try:
        _selected = cl.user_session.get("selected_model") or ""
    except Exception:
        pass  # no chainlit context (e.g. in tests)
    search_model = _resolve_search_model(
        selected_model=_selected,
        default_model=llm_mgr._default_model,
    )
    is_free = ":free" in search_model or search_model == "openrouter/free"
    if not is_free:
        print(f"[SearchTool] WARNING: using PAID search model: {search_model!r}", flush=True)

    try:
        print(f"[SearchTool] Searching: query={query!r}, model={search_model!r}", flush=True)
        result = _call_openrouter_web_search(llm_mgr, search_model, query)
        if _progress_callback:
            _progress_callback(80, "🧠 กำลังประมวลผลข้อมูล...")
        if "Source:" not in result and "Sources:" not in result and "http" not in result:
            result += "\n\n⚠️ No source URLs were returned by the search model. Treat this information as unverified."
        print(f"[SearchTool] Success: {len(result)} chars returned", flush=True)
        return result
    except Exception as e:
        err_detail = _sanitize_error(e)
        print(f"[SearchTool] ERROR with model={search_model!r}: {err_detail}", flush=True)
        # Retry with fallback free model
        if search_model != "openrouter/free":
            try:
                fallback_model = "openrouter/free"
                print(f"[SearchTool] Retrying with fallback model={fallback_model!r}", flush=True)
                result = _call_openrouter_web_search(llm_mgr, fallback_model, query)
                if "Source:" not in result and "Sources:" not in result and "http" not in result:
                    result += "\n\n⚠️ No source URLs were returned by the search model. Treat this information as unverified."
                print(f"[SearchTool] Fallback success: {len(result)} chars returned", flush=True)
                return result
            except Exception as e2:
                err2 = _sanitize_error(e2)
                print(f"[SearchTool] Fallback also failed: {err2}", flush=True)
        return f"เกิดข้อผิดพลาดระหว่างค้นหา (model={search_model}): {err_detail}\nกรุณาดำเนินการต่อโดยใช้ข้อมูลที่มีอยู่และระบุว่าไม่สามารถค้นหาเว็บได้"

