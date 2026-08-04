"""Feedback loop: measure search_web timing.

Hypothesis: 16 search calls × ~30s each = 8 minutes, plus synthesis = 15 min total.
This script measures a single search_web call to verify.
"""
import time
import sys
sys.path.insert(0, '/Users/its-dev2/my-agent-app')

from backend.globals import _search_model, _thread_local
from backend.tools.search import _check_search_call_limit

# Disable limit for this test
_thread_local.max_search_calls = 0
_thread_local.search_call_count = 0

# Use the search_web tool directly (it's a CrewAI @tool, call via .func or direct)
from crewai.tools import tool as crewai_tool

# search_web is decorated with @tool, access the underlying function
import backend.tools.search as search_module
# The @tool decorator wraps the function; we need to call the underlying
# Actually CrewAI @tool creates a Tool object, but the original function
# is accessible. Let's just call _call_openrouter_web_search directly.

from backend.tools.search import _call_openrouter_web_search
from backend.llm.manager import LLMManager

mgr = LLMManager()
search_model = "openrouter/free"

queries = [
    "Arsenal latest news March 2026",
    "Arsenal fixtures results March 2026",
    "Arsenal transfers January 2026",
]

print("=" * 60)
print("Search Web Timing Test")
print("=" * 60)

total = 0
for i, q in enumerate(queries, 1):
    print(f"\n[Search #{i}] query={q!r}", flush=True)
    start = time.time()
    try:
        result = _call_openrouter_web_search(mgr, search_model, q)
        elapsed = time.time() - start
        total += elapsed
        print(f"[Search #{i}] DONE in {elapsed:.1f}s, {len(result)} chars", flush=True)
    except Exception as e:
        elapsed = time.time() - start
        total += elapsed
        print(f"[Search #{i}] FAILED in {elapsed:.1f}s: {e}", flush=True)

print(f"\n{'=' * 60}")
print(f"SUMMARY: {len(queries)} searches took {total:.1f}s total")
print(f"Average: {total/len(queries):.1f}s per search")
print(f"Projected 16 searches: {total/len(queries) * 16:.1f}s = {total/len(queries) * 16 / 60:.1f} min")
print(f"{'=' * 60}")
