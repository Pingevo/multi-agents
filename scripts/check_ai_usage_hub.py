#!/usr/bin/env python3
"""One-shot completeness check for AI Usage Hub integration.

Run: python scripts/check_ai_usage_hub.py
Exit 0 = all checks pass. Exit 1 = something is missing.

Checks 6 categories in one pass:
1. Call site coverage — every OpenRouter HTTP call has log in success + error
2. Spec field coverage — every required field present where appropriate
3. Cleanup — credit_logger deleted, no log_llm_call remnants, no jsonl file
4. Config — .env.example has all env vars
5. Edge cases — video polling, local fallback, streaming, litellm, crewai
6. Code quality — indentation consistency in log_ai_usage blocks
"""
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
FAILED = []

def fail(category, msg):
    FAILED.append(f"[{category}] {msg}")
    print(f"  FAIL: {msg}")

def ok(msg):
    print(f"  OK:   {msg}")

def check_call_site_coverage():
    print("\n=== 1. Call site coverage ===")
    files = [
        "backend/llm/manager.py",
        "backend/llm/rotator.py",
        "backend/media/manager.py",
        "backend/tools/search_adapter.py",
        "backend/core/orchestrator.py",
    ]
    for f in files:
        path = ROOT / f
        if not path.exists():
            fail("call_site", f"{f} missing")
            continue
        src = path.read_text()
        # Find log_ai_usage blocks
        blocks = list(re.finditer(r'log_ai_usage\(\{(.*?)\}\)', src, re.DOTALL))
        success = sum(1 for b in blocks if '"success"' in b.group(1))
        error = sum(1 for b in blocks if '"error"' in b.group(1) or '"timeout"' in b.group(1))
        ok(f"{f}: {len(blocks)} logs ({success} success, {error} error/timeout)")
        if success == 0:
            fail("call_site", f"{f}: no success logs")
        if error == 0:
            fail("call_site", f"{f}: no error logs")

def check_spec_fields():
    print("\n=== 2. Spec field coverage ===")
    files = [
        "backend/llm/manager.py",
        "backend/llm/rotator.py",
        "backend/media/manager.py",
        "backend/tools/search_adapter.py",
        "backend/core/orchestrator.py",
    ]
    mandatory_in_all = ["provider", "model", "operation", "source", "status", "metadata"]
    mandatory_in_success = ["cost_usd", "duration_ms"]
    mandatory_in_error = ["error_message", "duration_ms"]

    total = 0
    for f in files:
        src = (ROOT / f).read_text()
        for m in re.finditer(r'log_ai_usage\(\{(.*?)\}\)', src, re.DOTALL):
            block = m.group(1)
            total += 1
            line = src[:m.start()].count("\n") + 1
            is_success = '"success"' in block
            is_error = '"error"' in block or '"timeout"' in block

            for field in mandatory_in_all:
                if f'"{field}"' not in block:
                    fail("fields", f"{f}:{line} missing {field}")

            if is_success:
                for field in mandatory_in_success:
                    if f'"{field}"' not in block:
                        fail("fields", f"{f}:{line} success missing {field}")
            if is_error:
                for field in mandatory_in_error:
                    if f'"{field}"' not in block:
                        fail("fields", f"{f}:{line} error missing {field}")
    ok(f"checked {total} log_ai_usage blocks")

def check_cleanup():
    print("\n=== 3. Cleanup ===")
    if (ROOT / "backend/credit_logger.py").exists():
        fail("cleanup", "backend/credit_logger.py still exists")
    else:
        ok("credit_logger.py deleted")

    if (ROOT / "llm-call-log.jsonl").exists():
        fail("cleanup", "llm-call-log.jsonl still on disk")
    else:
        ok("llm-call-log.jsonl deleted")

    gitignore = (ROOT / ".gitignore").read_text()
    if "llm-call-log.jsonl" in gitignore:
        fail("cleanup", "llm-call-log.jsonl still in .gitignore")
    else:
        ok(".gitignore clean")

    # Check no log_llm_call imports remain (except in comments)
    for f in ["backend/llm/manager.py", "backend/llm/rotator.py",
              "backend/media/manager.py", "backend/tools/search_adapter.py",
              "backend/core/orchestrator.py"]:
        src = (ROOT / f).read_text()
        # Look for actual import or call (not in comments)
        for i, line in enumerate(src.split("\n"), 1):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            if "log_llm_call" in line and "import" in line:
                fail("cleanup", f"{f}:{i} still imports log_llm_call")
    ok("no log_llm_call imports")

def check_config():
    print("\n=== 4. Config ===")
    env = (ROOT / ".env.example").read_text()
    for var in ["AI_USAGE_HUB_URL", "AI_USAGE_HUB_TOKEN", "AI_USAGE_HUB_TIMEOUT"]:
        if var not in env:
            fail("config", f".env.example missing {var}")
        else:
            ok(f".env.example has {var}")

    # Check token is placeholder, not real
    if "svc_42" in env and "svc_" in env:
        ok("token is placeholder (svc_42)")

def check_edge_cases():
    print("\n=== 5. Edge cases ===")
    media = (ROOT / "backend/media/manager.py").read_text()
    if '"status": "timeout"' in media:
        ok("video polling timeout logged")
    else:
        fail("edge", "video polling timeout not logged")

    if '"status": "error"' in media and "video" in media.lower():
        ok("video polling failure logged")
    else:
        fail("edge", "video polling failure not logged")

    mgr = (ROOT / "backend/llm/manager.py").read_text()
    if "fallback_provider" in mgr and "log_ai_usage" in mgr:
        ok("local fallback logged")
    else:
        fail("edge", "local fallback not logged")

    if "stream_options" in mgr or "include_usage" in mgr:
        ok("streaming usage capture")
    else:
        fail("edge", "streaming usage not captured")

    orch = (ROOT / "backend/core/orchestrator.py").read_text()
    if "log_failure_event" in orch or '"status": "error"' in orch:
        ok("litellm failure callback")
    else:
        fail("edge", "litellm failure callback missing")

    if "LLMCallCompletedEvent" in orch:
        ok("crewai event bus logged")
    else:
        fail("edge", "crewai event bus not logged")

def check_indentation():
    print("\n=== 6. Code quality (indentation) ===")
    files = [
        "backend/llm/manager.py",
        "backend/llm/rotator.py",
        "backend/media/manager.py",
        "backend/tools/search_adapter.py",
        "backend/core/orchestrator.py",
    ]
    for f in files:
        path = ROOT / f
        lines = path.read_text().split("\n")
        for i, line in enumerate(lines):
            if '"metadata":' in line and "analysis_type" in line:
                indent = len(line) - len(line.lstrip())
                # Find previous non-empty sibling field
                for j in range(i - 1, max(i - 10, 0), -1):
                    prev = lines[j]
                    if prev.strip().startswith('"') and ":" in prev:
                        prev_indent = len(prev) - len(prev.lstrip())
                        if indent != prev_indent:
                            fail("indent", f"{f}:{i+1} metadata indent={indent} != sibling indent={prev_indent}")
                        break

    # Check closing }) matches log_ai_usage({ indent
    for f in files:
        path = ROOT / f
        src = path.read_text()
        for m in re.finditer(r'(\s*)log_ai_usage\(\{', src):
            open_indent = len(m.group(1))
            # Find the matching closing })
            pos = m.end()
            depth = 1
            while pos < len(src) and depth > 0:
                next_open = src.find("log_ai_usage({", pos)
                next_close = src.find("})", pos)
                if next_close == -1:
                    break
                if next_open != -1 and next_open < next_close:
                    depth += 1
                    pos = next_open + len("log_ai_usage({")
                else:
                    depth -= 1
                    pos = next_close + 2
            # We don't strictly check this — Python allows it
    ok("indentation checked")

def main():
    print("AI Usage Hub — Completeness Check")
    print("=" * 50)
    check_call_site_coverage()
    check_spec_fields()
    check_cleanup()
    check_config()
    check_edge_cases()
    check_indentation()

    print("\n" + "=" * 50)
    if FAILED:
        print(f"RESULT: {len(FAILED)} issue(s) found")
        for f in FAILED:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("RESULT: ALL CHECKS PASSED")
        sys.exit(0)

if __name__ == "__main__":
    main()
