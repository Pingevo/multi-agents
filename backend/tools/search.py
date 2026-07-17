"""Search tool using OpenRouter AI-selected search model."""

from crewai.tools import tool
from crewai import LLM
from backend.globals import _progress_callback, _search_model
from backend.utils import _sanitize_error
from backend.llm.manager import LLMManager


@tool
def search_web(query: str) -> str:
    """Search the web for current information using OpenRouter (AI-selected search model).

    Returns factual information with source URLs. Always cite sources.
    """
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
        search_prompt = (
            f"Search the web for: {query}\n\n"
            "Provide factual, up-to-date information.\n"
            "CRITICAL: You MUST include source URLs for every claim you make.\n"
            "List each source URL on a separate line prefixed with 'Source: '.\n"
            "If you cannot find reliable sources for a claim, explicitly state "
            "'No reliable source found' instead of fabricating information.\n"
            "Do NOT invent URLs or make up sources.\n"
            "Format your response as:\n"
            "1. A summary of findings (with inline citations)\n"
            "2. A 'Sources:' section listing all URLs used"
        )
        print(f"[SearchTool] Searching: query={query!r}, model={search_model!r}", flush=True)
        result = llm.call(search_prompt)
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
                llm = LLM(
                    model=fallback_model,
                    base_url=llm_mgr.base_url,
                    api_key=llm_mgr.api_key,
                    temperature=0.3,
                    max_retries=0,
                )
                result = llm.call(search_prompt)
                if "Source:" not in result and "Sources:" not in result and "http" not in result:
                    result += "\n\n⚠️ No source URLs were returned by the search model. Treat this information as unverified."
                print(f"[SearchTool] Fallback success: {len(result)} chars returned", flush=True)
                return result
            except Exception as e2:
                err2 = _sanitize_error(e2)
                print(f"[SearchTool] Fallback also failed: {err2}", flush=True)
        return f"เกิดข้อผิดพลาดระหว่างค้นหา (model={search_model}): {err_detail}\nกรุณาดำเนินการต่อโดยใช้ข้อมูลที่มีอยู่และระบุว่าไม่สามารถค้นหาเว็บได้"

