#!/usr/bin/env python3
"""Create 9 GitHub milestones for the Agentic AI Workforce Platform roadmap.

M1-M5: closed (work completed)
M6-M9: open (future work)
"""

import json
import os
import urllib.request
import urllib.error

REPO = "Pingevo/multi-agents"
TOKEN = os.environ.get("GITHUB_TOKEN", "")

def api_call(method, path, data=None):
    """Make a GitHub API call."""
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
        print(f"  ERROR {e.code}: {e.read().decode()[:200]}")
        return None

# Milestone definitions
milestones = [
    {"title": "M1: Foundation & Core Infrastructure", "state": "closed", "description": "Chainlit + FastAPI Backend, CrewAI Multi-Agent Framework, Multimodal Attachment Pipeline, Model Discovery, React Frontend, Agent Tuning, Account System, Feedback Loop, Unit Tests (July 9-10)"},
    {"title": "M2: Multi-Agent Orchestration & Team System", "state": "closed", "description": "Team-Based UI Redesign, System81 OAuth Login, ModelPicker, Credit Usage Optimization, OpenRouter Server Tools, browse_web Tool, Manager Review + Storyboard UI (July 13-17)"},
    {"title": "M3: Retro UI, CI/CD & Production Hardening", "state": "closed", "description": "Retro Windows UI (WindowManager, Desktop, Taskbar), CI/CD Pipeline, Full System Tests, Cross-Session Notifications, Team Isolation, Agent Tuning, Manager Review Bug Fixes (July 18-24)"},
    {"title": "M4: Enterprise Security & Data Isolation", "state": "closed", "description": "Per-user JSON Stores, Per-user Media/Attachment Storage, Secure Media Serving Endpoint, Frontend withMediaToken helper, StaticFiles cleanup (July 29)"},
    {"title": "M5: Universal Multi-Modal AI", "state": "closed", "description": "Agentic File I/O (PPTX, ZIP/TAR, Code files), Multi-Modal Generation (TTS, STT, Vision), Type-Aware UI Rendering, Approval Flow for all media types, Retro Theme Migration (July 29)"},
    {"title": "M6: Continuous Learning & Optimization", "state": "open", "description": "Trust Score per agent, Model-level trust, Manager review intensity based on trust, Auto-tune from reject patterns, Conversation memory window, Permanent quality_criteria, Cost-trust correlation, Error pattern persistence, Learning Dashboard UI (Priority 1: Output must be perfect first)"},
    {"title": "M7: Company Knowledge Base", "state": "open", "description": "Knowledge Store with 5 data source connectors (MongoDB, REST API, URL, File, Manual text), Knowledge Management UI, query_knowledge_base CrewAI tool, Team-level Brand Context (Priority 2: AI must know the company)"},
    {"title": "M8: The Autonomous Workforce", "state": "open", "description": "Scheduled Tasks UI, Task Templates UI, Backend Scheduler integration + context-blind fix, Content Calendar, Competitor Intelligence, End-to-End Automation Loop (Priority 3: AI works autonomously)"},
    {"title": "M9: External Platform Connections", "state": "open", "description": "Credential Manager, Integration Framework (plug-in architecture), Social Media Adapters (Facebook, Instagram, TikTok, X, LinkedIn), E-commerce Adapters (Shopee, Lazada, Shopify, SellerCenter), External Action Tools, Generic Approval Flow, Connection Settings UI + Sales Analytics (Priority 4: AI connects to external platforms — social + e-commerce combined)"},
]

print("=== Creating 9 Milestones ===")
created = {}
for i, ms in enumerate(milestones):
    print(f"  Creating: {ms['title']} ({ms['state']})...")
    result = api_call("POST", "milestones", ms)
    if result:
        created[i + 1] = result["number"]
        print(f"    -> milestone #{result['number']}")
    else:
        print(f"    -> FAILED")

print(f"\nCreated {len(created)}/9 milestones")
print("Milestone mapping:")
for k, v in created.items():
    print(f"  M{k} -> GitHub milestone #{v}")

# Save mapping for next steps
with open("/tmp/milestone_map.json", "w") as f:
    json.dump(created, f)

print("\nSaved mapping to /tmp/milestone_map.json")
