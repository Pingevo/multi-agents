"""Feedback loop for diagnosing slow Manager synthesis.

Bug: Manager synthesis takes 15 minutes (should be seconds).
This script measures the actual time of a synthesis LLM call with
different context sizes, to isolate whether the slowness is:
- context size (50K chars)
- model (openrouter/free)
- retry loop
- or something else

Run: venv/bin/python test_synth_timing.py
"""
import time
import sys
sys.path.insert(0, '/Users/its-dev2/my-agent-app')

from backend.llm.manager import LLMManager


def make_synthesis_prompt(size_chars: int) -> str:
    """Build a synthesis prompt of approximately size_chars."""
    base = (
        "User request: อยากรู้สถานการณ์ปัจจุบันของทีมอาร์เซนอล\n\n"
        "You are an experienced team manager.\n"
        "Your team has completed their tasks.\n"
        "Below are the outputs from each team member:\n\n"
    )
    # Fill with realistic-looking search results
    filler = (
        "--- นักวิเคราะห์ข่าวฟุตบอล #1 (นักข่าวกีฬา) ---\n"
        "Arsenal latest news: Martin Odegaard and Leandro Trossard missed Arsenal's trip "
        "to Germany but are now in contention to be included in the squad. "
        "Ben White has returned to the defensive line, while Jurrien Timber remains sidelined. "
        "Source: https://www.arsenal.com/news/team-news-white-starts-against-leverkusen\n"
        "On March 14, 2026, Arsenal defeated Everton 2-0 at the Emirates Stadium. "
        "Viktor Gyokeres scored in the 89th minute. Max Dowman (16 years old) scored in stoppage time. "
        "Source: https://www.arsenal.com/fixture/arsenal/2026-Mar-14/arsenal-2-0-everton-match-report\n"
    )
    target = size_chars - len(base) - 200
    repeats = max(1, target // len(filler))
    prompt = base + (filler * repeats) + "\nSummarize the team's deliverables briefly.\n"
    return prompt[:size_chars]


def time_synthesis_call(prompt: str, model: str, label: str) -> float:
    """Time a single synthesis LLM call. Returns elapsed seconds."""
    print(f"\n[{label}] model={model}, prompt={len(prompt)} chars", flush=True)
    mgr = LLMManager()
    llm = mgr.build_llm_for_model(model)
    start = time.time()
    try:
        result = llm.call(prompt)
        elapsed = time.time() - start
        result_len = len(str(result))
        print(f"[{label}] DONE in {elapsed:.1f}s, result={result_len} chars", flush=True)
        print(f"[{label}] result preview: {str(result)[:200]}", flush=True)
        return elapsed
    except Exception as e:
        elapsed = time.time() - start
        print(f"[{label}] FAILED in {elapsed:.1f}s: {e}", flush=True)
        return elapsed


if __name__ == "__main__":
    print("=" * 70)
    print("Manager Synthesis Timing Diagnosis")
    print("=" * 70)

    # Test 1: Small context (1K chars) with free model
    p1 = make_synthesis_prompt(1000)
    t1 = time_synthesis_call(p1, "openrouter/free", "small-1K-free")

    # Test 2: Medium context (10K chars) with free model
    p2 = make_synthesis_prompt(10000)
    t2 = time_synthesis_call(p2, "openrouter/free", "medium-10K-free")

    # Test 3: Large context (50K chars) with free model — simulates the bug
    p3 = make_synthesis_prompt(50000)
    t3 = time_synthesis_call(p3, "openrouter/free", "large-50K-free")

    # Test 4: Large context (50K chars) with paid model (if user has credits)
    t4 = time_synthesis_call(p3, "anthropic/claude-sonnet-5", "large-50K-paid")

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  1K chars,  free model:  {t1:.1f}s")
    print(f"  10K chars, free model:  {t2:.1f}s")
    print(f"  50K chars, free model:  {t3:.1f}s  <-- simulates bug")
    print(f"  50K chars, paid model:  {t4:.1f}s")
    print()
    if t3 > 60:
        print("  DIAGNOSIS: 50K context + free model = slow (>60s)")
        print("  → Likely cause: free model is slow OR context too large")
    if t4 < t3 / 3:
        print("  DIAGNOSIS: Paid model much faster → free model is the bottleneck")
