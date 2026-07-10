"""Search tool using OpenRouter AI-selected search model."""

from crewai.tools import tool
from crewai import LLM
from backend.globals import _progress_callback, _search_model
from backend.utils import _sanitize_error
from backend.llm.manager import LLMManager


@tool
def search_web(query: str) -> str:
    """Search the web for current information using OpenRouter (AI-selected search model)."""
    global _progress_callback, _search_model
    if _progress_callback:
        _progress_callback(50, "🔍 กำลังค้นหาข้อมูลจากเว็บ...")

    if not query or not query.strip():
        return "กรุณาระบุคำค้นหา"

    llm_mgr = LLMManager()
    search_model = _search_model or llm_mgr._default_model or "openrouter/free"
    is_free = ":free" in search_model or search_model == "openrouter/free"
    if not is_free:
        print(f"[SearchTool] WARNING: using PAID search model: {search_model!r}", flush=True)

    try:
        llm = LLM(
            model=f"openrouter/{search_model}" if not search_model.startswith("openrouter/") else search_model,
            base_url=llm_mgr.base_url,
            api_key=llm_mgr.api_key,
            temperature=0.3,
            max_retries=0,
        )
        result = llm.call(f"Search the web for: {query}\n\nProvide factual, up-to-date information with sources if possible.")
        if _progress_callback:
            _progress_callback(80, "🧠 กำลังประมวลผลข้อมูล...")
        return result
    except Exception as e:
        return f"เกิดข้อผิดพลาดระหว่างค้นหา: {_sanitize_error(e)} กรุณาลองใหม่อีกครั้ง"
