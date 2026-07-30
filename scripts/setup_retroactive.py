#!/usr/bin/env python3
"""Create 28 retroactive issues for M1-M3 and close them immediately.

M1: 10 retroactive issues
M2: 10 retroactive issues
M3: 8 retroactive issues
"""

import json
import os
import urllib.request
import urllib.error
import time

REPO = "Pingevo/multi-agents"
TOKEN = os.environ.get("GITHUB_TOKEN", "")

def api_call(method, path, data=None):
    url = f"https://api.github.com/repos/{REPO}/{path}"
    headers = {
        "Authorization": f"token {TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
    }
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()[:300]
        print(f"  ERROR {e.code}: {err_body}")
        return None

# Load milestone mapping
with open("/tmp/milestone_map.json") as f:
    ms_map = json.load(f)

# Retroactive issues definition: (milestone_number, title)
retroactive = [
    # M1: Foundation (10 issues)
    (ms_map["1"], "[Retroactive] ตั้งค่า Chainlit + FastAPI Backend พร้อม Socket.IO Real-time Communication"),
    (ms_map["1"], "[Retroactive] สร้าง CrewAI Multi-Agent Framework เชื่อมต่อ OpenRouter LLM API"),
    (ms_map["1"], "[Retroactive] สร้าง Multimodal Attachment Pipeline (Image/PDF/Audio/Video/DOCX/XLSX/SVG)"),
    (ms_map["1"], "[Retroactive] สร้าง URL Processing Pipeline พร้อม SSRF Protection + YouTube Extraction"),
    (ms_map["1"], "[Retroactive] สร้าง Model Discovery Service + Model Selector + Free Model Rotator"),
    (ms_map["1"], "[Retroactive] สร้าง React Frontend (Vite) — ChatPanel, CanvasArea, ModelPicker, Storyboard"),
    (ms_map["1"], "[Retroactive] สร้าง Agent Tuning — Deep Persona Schema (personality, expertise, brand_context)"),
    (ms_map["1"], "[Retroactive] สร้าง Account System — Pluggable Auth + Password Verification + Login UI"),
    (ms_map["1"], "[Retroactive] สร้าง Agent Feedback Loop + Auto-Learning System"),
    (ms_map["1"], "[Retroactive] เขียน Unit Tests 53 ตัว (Attachment Processing + Plan Model Validation)"),

    # M2: Orchestration & Team (10 issues)
    (ms_map["2"], "[Retroactive] สร้าง Team-Based UI Redesign — Backend Teams + Frontend Team Pages"),
    (ms_map["2"], "[Retroactive] สร้าง System81 OAuth Login สำหรับ SellerCenter Integration"),
    (ms_map["2"], "[Retroactive] สร้าง ModelPicker Component เต็มรูปแบบ (แทน Dropdown)"),
    (ms_map["2"], "[Retroactive] สร้าง Credit Usage Optimization + Per-Request Credit Logging"),
    (ms_map["2"], "[Retroactive] สร้าง OpenRouter Server Tools (แทน legacy search_web/scrape_web)"),
    (ms_map["2"], "[Retroactive] สร้าง browse_web Tool ด้วย Playwright Headless Browser"),
    (ms_map["2"], "[Retroactive] สร้าง contextvars Propagation สำหรับ user_prompt ข้าม Thread"),
    (ms_map["2"], "[Retroactive] สร้าง LLM Call Logger สำหรับ Credit Usage Analysis"),
    (ms_map["2"], "[Retroactive] สร้าง Manager Review + Storyboard UI สำหรับ Agent Output Display"),
    (ms_map["2"], "[Retroactive] แก้ Chat Mode: ป้องกัน Planning, รองรับ Multimodal, จัดการ Attachments"),

    # M3: Retro UI & Hardening (8 issues)
    (ms_map["3"], "[Retroactive] สร้าง CI/CD Pipeline (GitHub Actions + Pre-commit Hooks)"),
    (ms_map["3"], "[Retroactive] สร้าง Full System Automated Tests (E2E Playwright + Unit + Regression)"),
    (ms_map["3"], "[Retroactive] สร้าง Cross-Session Notifications พร้อม Click-to-Navigate"),
    (ms_map["3"], "[Retroactive] สร้าง Frontend SPA Serving + CORS Fix"),
    (ms_map["3"], "[Retroactive] สร้าง Team Isolation — กรอง tasks/agents/notifications ตาม team_id"),
    (ms_map["3"], "[Retroactive] สร้าง Comprehensive Agent Tuning — 6 New Fields + Auto-Tune on Approve"),
    (ms_map["3"], "[Retroactive] แก้ Manager Review Bugs — Progress Card, Stale Tasks, Stop/Restart State"),
    (ms_map["3"], "[Retroactive] สร้าง Real-Time History Broadcast — log_history ส่งไป Frontend ทันที"),
]

print(f"=== Creating {len(retroactive)} Retroactive Issues ===")
created_issues = []
for i, (ms_num, title) in enumerate(retroactive, 1):
    print(f"  [{i}/{len(retroactive)}] Creating: {title[:60]}...")
    result = api_call("POST", "issues", {"title": title, "milestone": ms_num})
    if result:
        issue_num = result["number"]
        created_issues.append(issue_num)
        print(f"    -> issue #{issue_num} (milestone #{ms_num})")
        # Close immediately
        close_result = api_call("PATCH", f"issues/{issue_num}", {"state": "closed"})
        if close_result:
            print(f"    -> closed")
        else:
            print(f"    -> FAILED to close")
    else:
        print(f"    -> FAILED")
    time.sleep(0.5)  # Rate limiting

print(f"\nCreated and closed {len(created_issues)}/{len(retroactive)} retroactive issues")
print(f"Issue numbers: {created_issues}")
