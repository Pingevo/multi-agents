#!/usr/bin/env python3
"""Update 76 existing GitHub issues with milestone assignments.

Issue-to-milestone mapping based on the roadmap plan.
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

# Issue-to-milestone mapping: issue_number -> milestone_key
issue_mapping = {}

# M1: Foundation (5 issues)
for n in [1, 2, 3, 4, 5]:
    issue_mapping[n] = ms_map["1"]

# M2: Orchestration & Team (1 issue)
issue_mapping[6] = ms_map["2"]

# M3: Retro UI & Hardening (19 issues)
for n in [7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 30, 76]:
    issue_mapping[n] = ms_map["3"]

# M4: Security & Data Isolation (17 issues)
for n in [40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56]:
    issue_mapping[n] = ms_map["4"]

# M5: Multi-Modal AI (19 issues)
for n in [57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75]:
    issue_mapping[n] = ms_map["5"]

# M6: Continuous Learning (12 issues)
for n in [24, 25, 26, 27, 28, 29, 31, 32, 35, 36, 37, 38]:
    issue_mapping[n] = ms_map["6"]

# M7: Company Knowledge Base (2 issues)
for n in [33, 34]:
    issue_mapping[n] = ms_map["7"]

# M8: Autonomous Workforce (1 issue)
issue_mapping[39] = ms_map["8"]

# M9: External Connections (0 existing issues)

print(f"Total issues to update: {len(issue_mapping)}")
assert len(issue_mapping) == 76, f"Expected 76, got {len(issue_mapping)}"

print(f"\n=== Updating {len(issue_mapping)} Existing Issues ===")
success = 0
failed = 0
for i, (issue_num, ms_num) in enumerate(sorted(issue_mapping.items()), 1):
    print(f"  [{i}/{len(issue_mapping)}] Issue #{issue_num} -> milestone #{ms_num}...", end=" ")
    result = api_call("PATCH", f"issues/{issue_num}", {"milestone": ms_num})
    if result:
        print("OK")
        success += 1
    else:
        print("FAILED")
        failed += 1
    time.sleep(0.3)  # Rate limiting

print(f"\nDone: {success} success, {failed} failed")
