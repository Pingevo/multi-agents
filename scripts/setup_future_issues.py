#!/usr/bin/env python3
"""Create 18 future issues for M6-M9.

M6: 1 future issue (Learning Dashboard UI)
M7: 4 future issues (Knowledge Base)
M8: 6 future issues (Autonomous Workforce)
M9: 7 future issues (External Connections)
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

# Future issues: (milestone_key, title, labels, body)
future_issues = [
    # M6: Continuous Learning (1 issue)
    (ms_map["6"],
     "[Feature] Learning Dashboard UI — หน้าจอแสดง Trust Score และ Learning Analytics",
     ["enhancement"],
     "สร้างหน้าจอใน retro UI สำหรับดู trust score ของแต่ละ agent\n\n- แสดง trust score ของแต่ละ agent และ model\n- แสดงประวัติการเรียนรู้ ความผิดพลาดที่แก้แล้ว ความก้าวหน้า\n- เชื่อมกับ credit analytics (Issue #35)\n- แสดง cost-trust correlation\n\n**Milestone:** M6 — Continuous Learning & Optimization\n**Priority:** 1 — Output ต้อง perfect ก่อน"),

    # M7: Company Knowledge Base (4 issues)
    (ms_map["7"],
     "[Architecture] Knowledge Store + Data Source Connectors — ที่เก็บข้อมูลบริษัทระดับ team",
     ["enhancement"],
     "สร้าง `KnowledgeStore` class (per-user/per-team isolation)\n\nรองรับ 5 แหล่งข้อมูล:\n- MongoDB connector (ดึงข้อมูลสินค้า/แบรนด์จาก MongoDB ที่บริษัทใช้)\n- REST API connector (ดึงข้อมูลจาก API ใดๆ ที่บริษัทมี)\n- URL ingestion (อ่านข้อมูลจากลิงก์ — ใช้ browse_web/scrape_web ที่มี)\n- File ingestion (อัปโหลด PDF, DOCX, XLSX, images — ใช้ attachment pipeline ที่มี)\n- Text/Manual entry (พิมพ์ข้อมูลโดยตรง)\n\nแต่ละแหล่งข้อมูลมี connector แยก ใช้ interface เดียวกัน (plug-in architecture)\nข้อมูลถูก normalize + index ในที่เก็บกลาง\n\n**Milestone:** M7 — Company Knowledge Base\n**Priority:** 2 — AI ต้องรู้จักบริษัท"),

    (ms_map["7"],
     "[Feature] Knowledge Management UI — หน้าจอจัดการ Knowledge Base",
     ["enhancement"],
     "สร้างหน้าจอใน retro UI (KnowledgeWindow ใหม่)\n\n- เพิ่ม/ลบ/แก้ไข knowledge items\n- แสดงรายการตามประเภท (สินค้า, แบรนด์, ลูกค้า, เอกสาร)\n- ค้นหา + filter\n- รองรับการเชื่อมต่อ MongoDB, API, URL, File upload\n\n**Milestone:** M7 — Company Knowledge Base"),

    (ms_map["7"],
     "[Tool] query_knowledge_base — CrewAI tool สำหรับค้นหาข้อมูลบริษัท",
     ["enhancement"],
     "สร้าง tool ใหม่ใน `backend/tools/knowledge.py`\n\n- Agent ใช้ค้นหาข้อมูลสินค้า แบรนด์ ลูกค้า ได้ระหว่างทำงาน\n- ลงทะเบียนใน `ToolRegistry` และ `CapabilityRegistry`\n- รองรับการ query จาก Knowledge Store ที่เชื่อมกับ MongoDB/API/URL/File\n\n**Milestone:** M7 — Company Knowledge Base"),

    (ms_map["7"],
     "[Architecture] Team-level Brand Context — ย้ายจาก agent ไป team",
     ["enhancement"],
     "ขยาย `TeamRegistry` ให้มี field `brand_context` และ `knowledge_base_id`\n\n- Agent ดึง brand_context จาก team แทนที่จะเก็บเอง\n- รองรับ issue #33 ที่เปิดอยู่\n- เชื่อมกับ Knowledge Store จาก M7\n\n**Milestone:** M7 — Company Knowledge Base\n**Related:** #33"),

    # M8: Autonomous Workforce (6 issues)
    (ms_map["8"],
     "[Feature] Scheduled Tasks UI — หน้าจอตั้งเวลาให้ AI ทำงานอัตโนมัติ",
     ["enhancement"],
     "สร้างหน้าจอเต็มใน ScheduleWindow (แทน placeholder 20 บรรทัดปัจจุบัน)\n\n- สร้าง/แก้ไข/ลบ/เปิด-ปิด scheduled tasks\n- รองรับ one-time และ recurring (รายวัน/รายสัปดาห์/รายเดือน)\n- เชื่อมกับ `ScheduledTaskStore` และ `BackgroundScheduler`\n\n**Milestone:** M8 — Autonomous Workforce\n**Priority:** 3 — AI ทำงานอัตโนมัติ"),

    (ms_map["8"],
     "[Feature] Task Templates UI — ระบบเซฟรูปแบบคำสั่งประจำ (One-click execution)",
     ["enhancement"],
     "สร้างหน้าจอสำหรับบันทึก/โหลด task templates\n\n- เชื่อมกับ `TaskTemplateStore`\n- User บันทึกคำสั่ง + agent config เป็น template → เรียกใช้ซ้ำได้ในคลิกเดียว\n- รองรับ issue #37 (ผูก Task Template กับ agent config ที่พิสูจน์แล้ว)\n\n**Milestone:** M8 — Autonomous Workforce"),

    (ms_map["8"],
     "[Integration] เชื่อม Backend Scheduler กับ Frontend + แก้ context-blind bug",
     ["enhancement", "bug"],
     "สร้าง API endpoints สำหรับ CRUD scheduled tasks\n\n- สร้าง WebSocket events สำหรับ real-time schedule status\n- แก้ BackgroundScheduler context-blind bug (Issue #39) — ไม่ส่ง user_id, team_id, conversation history\n\n**Milestone:** M8 — Autonomous Workforce\n**Related:** #39"),

    (ms_map["8"],
     "[Feature] Content Calendar — AI วางแผนคอนเทนต์เป็นปฏิทิน",
     ["enhancement"],
     "AI วางแผนคอนเทนต์รายสัปดาห์/รายเดือน โดยอัตโนมัติ\n\n- แสดงเป็นปฏิทินใน retro UI (CalendarWindow ใหม่)\n- แต่ละวันมี task ที่ AI จะทำอัตโนมัติ (สร้างคอนเทนต์ + ใช้ Knowledge Base)\n- User สามารถ approve/edit/skip แต่ละ task ในปฏิทินได้\n- เชื่อมกับ Scheduled Tasks และ Knowledge Base (M7)\n\n**Milestone:** M8 — Autonomous Workforce"),

    (ms_map["8"],
     "[Feature] Competitor Intelligence — AI ติดตามคู่แข่งอัตโนมัติ",
     ["enhancement"],
     "AI ใช้ browse_web/search_web ติดตามราคา สินค้าใหม่ กลยุทธ์คอนเทนต์ของคู่แข่ง\n\n- สร้างรายงานสรุปสัปดาห์/เดือน\n- แนะนำการปรับกลยุทธ์ตามข้อมูลคู่แข่ง\n- สามารถตั้งเวลาให้รันอัตโนมัติได้ (เชื่อมกับ Scheduled Tasks)\n\n**Milestone:** M8 — Autonomous Workforce"),

    (ms_map["8"],
     "[Feature] End-to-End Automation Loop — สั่งงานทิ้งไว้ ระบบรันเอง",
     ["enhancement"],
     "เชื่อม Scheduled Tasks + Task Templates + Knowledge Base + Notifications\n\n- User ตั้งเวลา → ระบบรันอัตโนมัติ → ใช้ Knowledge Base → สร้างคอนเทนต์ → ส่ง Notification\n- นี่คือ \"ปุ่มกด\" ที่ทำให้ AI เป็นพนักงานจริง (ก่อนเชื่อม external platforms)\n- ทุกผลลัพธ์ที่ส่งผลกระทบภายนอกต้องผ่าน approval\n\n**Milestone:** M8 — Autonomous Workforce"),

    # M9: External Platform Connections (7 issues)
    (ms_map["9"],
     "[Architecture] Credential Manager — ที่เก็บ encrypted API keys/tokens",
     ["enhancement"],
     "สร้าง `CredentialStore` (encrypted, per-user isolation)\n\n- เก็บ OAuth tokens, API keys ของ external services\n- API endpoints สำหรับ add/remove/list credentials\n- รองรับทั้ง social media และ e-commerce platforms\n\n**Milestone:** M9 — External Platform Connections\n**Priority:** 4 — เชื่อมต่อภายนอก (social + e-commerce รวมกัน)"),

    (ms_map["9"],
     "[Architecture] Integration Framework — plug-in สำหรับ external platform",
     ["enhancement"],
     "สร้าง `IntegrationBase` interface สำหรับ external platform ทุกประเภท\n\nMethods: authenticate(), post(), get_metrics(), delete_post(), list_products(), update_product(), get_orders(), reply_customer()\n\n- `IntegrationRegistry` สำหรับ register/list integrations\n- สถาปัตยกรรมแบบ plug-in — เพิ่ม platform ใหม่ได้โดยไม่ต้องแก้ core\n- ใช้สำหรับทั้ง social media และ e-commerce\n\n**Milestone:** M9 — External Platform Connections"),

    (ms_map["9"],
     "[Feature] Social Media Adapters — Facebook, Instagram, TikTok, X, LinkedIn",
     ["enhancement"],
     "สร้าง adapter 5 ตัว แต่ละตัว implement IntegrationBase\n\n- Facebook/Instagram: Graph API\n- TikTok: Content Posting API\n- X (Twitter): API v2\n- LinkedIn: Marketing API\n\n**Milestone:** M9 — External Platform Connections\n**Note:** User ยังไม่มี API keys — ออกแบบ framework ไว้ล่วงหน้า"),

    (ms_map["9"],
     "[Feature] E-commerce Adapters — Shopee, Lazada, Shopify, SellerCenter",
     ["enhancement"],
     "สร้าง adapter 4 ตัว แต่ละตัว implement IntegrationBase\n\n- Shopee: Open Platform API\n- Lazada: Open Platform API\n- Shopify: Admin API\n- SellerCenter: System81 API (ขยายจาก OAuth ที่มีอยู่)\n\n**Milestone:** M9 — External Platform Connections\n**Note:** User ยังไม่มี API keys — ออกแบบ framework ไว้ล่วงหน้า"),

    (ms_map["9"],
     "[Tool] External Action Tools — post_to_social, list_products, update_product, get_orders, reply_customer",
     ["enhancement"],
     "สร้าง tools ใน `backend/tools/external.py`\n\n- ทุก tool ส่ง approval card ก่อนทำจริง (เหมือน image approval flow)\n- ลงทะเบียนใน `ToolRegistry` และ `CapabilityRegistry`\n- รองรับทั้ง social media posting และ e-commerce operations\n\n**Milestone:** M9 — External Platform Connections"),

    (ms_map["9"],
     "[Feature] External Action Approval Flow — ขยาย approval สำหรับการกระทำภายนอก",
     ["enhancement"],
     "ขยาย ImageApprovalCard → เป็น GenericActionApprovalCard\n\n- รองรับ: social media posting, e-commerce updates, customer replies\n- User ต้อง approve ทุกการกระทำที่ส่งผลกระทบภายนอกระบบ (ตาม requirement ของ user)\n- แสดง preview ของ action ก่อน approve\n\n**Milestone:** M9 — External Platform Connections"),

    (ms_map["9"],
     "[Feature] Connection Settings UI + Sales Analytics Dashboard",
     ["enhancement"],
     "ขยาย SettingsWindow ให้มี external connection management\n\n- แสดงสถานะการเชื่อมต่อแต่ละ platform + OAuth flow\n- แสดง connected accounts พร้อม disconnect button\n- สร้างหน้าจอ Sales Analytics ใน retro UI (ยอดขาย สินค้าขายดี แนวโน้ม)\n\n**Milestone:** M9 — External Platform Connections"),
]

print(f"=== Creating {len(future_issues)} Future Issues ===")
created = []
for i, (ms_num, title, labels, body) in enumerate(future_issues, 1):
    print(f"  [{i}/{len(future_issues)}] Creating: {title[:60]}...")
    result = api_call("POST", "issues", {
        "title": title,
        "milestone": ms_num,
        "labels": labels,
        "body": body,
    })
    if result:
        issue_num = result["number"]
        created.append(issue_num)
        print(f"    -> issue #{issue_num} (milestone #{ms_num})")
    else:
        print(f"    -> FAILED")
    time.sleep(0.5)

print(f"\nCreated {len(created)}/{len(future_issues)} future issues")
print(f"Issue numbers: {created}")
