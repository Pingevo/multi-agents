"""Test H1: Is openrouter/free the bottleneck for search_web?

Compare search timing: free model vs paid model.
"""
import time
import sys
sys.path.insert(0, '/Users/its-dev2/my-agent-app')

from backend.tools.search import _call_openrouter_web_search
from backend.llm.manager import LLMManager

mgr = LLMManager()
query = "Arsenal latest news March 2026"

print("=" * 60)
print("H1 Test: free vs paid search model")
print("=" * 60)

# Test with free model
print(f"\n[free] query={query!r}", flush=True)
start = time.time()
try:
    r1 = _call_openrouter_web_search(mgr, "openrouter/free", query)
    t1 = time.time() - start
    print(f"[free] DONE in {t1:.1f}s, {len(r1)} chars", flush=True)
except Exception as e:
    t1 = time.time() - start
    print(f"[free] FAILED in {t1:.1f}s: {e}", flush=True)

# Test with paid model (perplexity sonar - designed for search)
print(f"\n[paid-perplexity] query={query!r}", flush=True)
start = time.time()
try:
    r2 = _call_openrouter_web_search(mgr, "perplexity/sonar", query)
    t2 = time.time() - start
    print(f"[paid-perplexity] DONE in {t2:.1f}s, {len(r2)} chars", flush=True)
except Exception as e:
    t2 = time.time() - start
    print(f"[paid-perplexity] FAILED in {t2:.1f}s: {e}", flush=True)

# Test with another paid model
print(f"\n[paid-gpt4o-mini] query={query!r}", flush=True)
start = time.time()
try:
    r3 = _call_openrouter_web_search(mgr, "openai/gpt-4o-mini", query)
    t3 = time.time() - start
    print(f"[paid-gpt4o-mini] DONE in {t3:.1f}s, {len(r3)} chars", flush=True)
except Exception as e:
    t3 = time.time() - start
    print(f"[paid-gpt4o-mini] FAILED in {t3:.1f}s: {e}", flush=True)

print(f"\n{'=' * 60}")
print(f"SUMMARY:")
print(f"  free (openrouter/free):     {t1:.1f}s")
print(f"  paid (perplexity/sonar):    {t2:.1f}s")
print(f"  paid (gpt-4o-mini):         {t3:.1f}s")
print(f"{'=' * 60}")
