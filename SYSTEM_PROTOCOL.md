# SYSTEM_PROTOCOL: Agent Management Platform

## 0. Project Goal (North Star)

**สร้าง Multi-Agent Platform ที่ใช้ AI เป็นพนักงานจริง ไม่ใช่แค่แชทบอท**

โจทย์ตัวอย่าง: วางแผน Monthly Content — โพสวันละอย่าง 1 โพส, Short Video และ Artwork สัดส่วน 50:50 ต่อเดือน

วิสัยทัศน์: Platform เปรียบเสมือนบริษัท มีแบรนด์ ทีม และพนักงาน AI
- บริษัท (Platform) → แบรนด์ (Brand) → ทีม (Team) → พนักงาน (Agent)
- แต่ละแบรนด์มีทีมของตัวเอง ทีมในแบรนด์เดียวกันใช้ brand_context ร่วมกัน
- Agent แต่ละตัว = พนักงานจริง มี persona, expertise, memory — brand_context ดึงจาก Brand ของทีม
- Flow: ทำงาน → ส่งผล → User review → Feedback → ทำใหม่จนกว่าจะถูกใจ

หลักการ:
- **Reasoning over Workflow**: Agent คิด ตัดสินใจ ปรับตัวเองได้ ไม่ใช่ if-then-else ตายตัวเหมือน n8n
- **Multi-agent Collaboration**: แบ่งงานเป็น agent ต่าง role — Planner, Creator, Reviewer, Publisher — มี Quality Loop ตรวจสอบกันเอง
- **Agent as Employee**: Agent มี deep persona (personality, expertise, brand context, learnings) ไม่ใช่แค่ role + backstory บรรทัดเดียว
- **Iterative Workflow**: ไม่ใช่รวดเดียวจบ — ทำ → review → feedback → redo จนกว่า user จะพอใจ
- **OpenRouter เป็น API ตัวเดียว**: Text (chat/completions), Image (/api/v1/images), Video (/api/v1/videos) — ใช้ API key อันเดียว บิลเดียว
- **Self-hosted Orchestration**: ระบบคิด วางแผน ตรวจสอบ เป็นของเรา — ใช้ API ของคนอื่นแค่ส่วน generation
- **ใช้ได้จริง**: ต้องเชื่อม social media API สำหรับ auto-posting, ใช้ paid LLM (ไม่ใช่ free tier)

สิ่งที่ต้องสร้างเอง:
1. Multi-agent orchestration (CrewAI) — reasoning, delegation, quality loop
2. Frontend dashboard — ควบคุมและติดตาม agent
3. Social media API integration — auto-posting
4. Scheduling — รันตามเวลา (cron/scheduler)

สิ่งที่ใช้ API ของคนอื่น (ไม่สร้างเอง):
- LLM generation (OpenRouter)
- Image/Video generation (OpenRouter)
- Search (DuckDuckGo)

## 1. Architecture Overview

```
Frontend (Vite/React, port 5173)
  ↓ WebSocket + REST API
Backend (Chainlit, port 8000)
  ├── Core: Secretary, Orchestrator, Messenger, Scheduler
  ├── Agents: Registry, Factory, TaskStore, ChatStore, TeamRegistry, BrandRegistry
  ├── LLM: Manager, Discovery, Rotator, Selector
  ├── Media: GenerationManager (image/video/TTS/STT)
  └── Auth: System81AuthProvider, SessionManager, UserStore
  ↓
Auth API (FastAPI, port 8001)
  └── /api/auth/login, /verify, /logout, /login-url
```

### 3-Server Architecture
- **Vite dev server (port 5173)** — React frontend ที่ user เปิดใน browser
- **Chainlit backend (port 8000)** — WebSocket/API สำหรับ chat, tasks, agent management
- **FastAPI auth server (port 8001)** — REST API สำหรับ auth endpoints
- ดูคำสั่งรันทั้ง 3 servers ใน `DEV_SETUP.md`
- **ห้ามเปิด port 8000 ใน browser** — นั่นคือ Chainlit's own UI ไม่ใช่ React app

### System Design
- Agent Factory & Registry (Single Source of Truth)
- UI/UX: **Dashboard-first, Chat-second**. ไม่พ่น Log หรือ Debug ข้อมูลรกหน้าแชท
- Central Secretary: ต้องมี **AI Assessor** ประเมินความต้องการและถาม requirement ก่อนตัดสินใจ

## 2. UI/UX Rules (Retro Desktop)

Frontend เป็นแบบ **Windows 95 Retro Desktop**:
- **RetroDesktop** — หน้าจอหลัก มี desktop icons, taskbar, และ windows ที่เปิดได้
- **WindowManager** — จัดการ window position, z-index, focus, minimize/maximize
- **Taskbar** — แสดง running windows และ system tray
- **Windows**: ChatWindow, TasksWindow, AgentsWindow, HistoryWindow, NotificationsWindow, SettingsWindow, ScheduleWindow, AgentDetailWindow, BrandWindow

### Key Windows
- **ChatWindow** — Command center รับคำสั่ง, แสดง chat bubbles, plan cards, approval buttons
- **TasksWindow** — 3-panel: task list (ซ้าย), flow diagram (กลาง), result panel (ขวา) พร้อม tabs (Output/Review/Media/Info)
- **AgentsWindow** — Agent roster bar + agent detail window
- **HistoryWindow** — ประวัติการทำงานของ tasks

### Rules
- ห้ามใช้ `cl.Message` ในการอัปเดตสถานะงาน ให้ใช้การอัปเดต Custom Element บน Dashboard แทน
- ห้ามสร้าง Text Log รกรุงรังในแชท ทุก Task ต้องมี Slot ของตัวเองบน Dashboard
- Chat: ทำหน้าที่เป็น **Command Center** รับคำสั่งอย่างเดียว ไม่ใช่ที่แสดงผลการทำงานของ Agent

## 3. Intelligence & Requirement Gathering (AI Assessor)
- AI ประเมินความต้องการของ User ด้วยตนเอง ไม่บังคับหมวดหมู่ตายตัว
- ถ้าข้อมูลไม่ชัด: AI ถาม clarifying questions จนได้ requirement ที่ชัดเจน (วนลูปได้)
- ถ้าข้อมูลชัด: AI วิเคราะห์และเสนอ plan (กี่ agent, ทำอะไร, ใช้ tools อะไร)
- ทุก plan ต้องได้รับ approval จาก User ก่อน execute เสมอ
- คำถามทั่วไป/ขอข้อมูลระบบ: ตอบเลย ไม่ต้องสร้าง agent
- AI กำหนดจำนวน agent เอง ไม่จำกัด 1 ตัว
- AI เลือก tools เองจาก Tool Registry ทั้งหมด

## 3.5 Agent Persona (Deep Identity)

Agent = พนักงานจริง ต้องมี:

| Attribute | คำอธิบาย | ใช้ทุกงาน? |
|-----------|----------|-----------|
| `name` | `[Role] #N` เช่น Creative Writer #1 | YES |
| `role` | ตำแหน่ง | YES |
| `goal` | เป้าหมายหลัก | YES |
| `personality` | โทน, สไตล์การสื่อสาร, ภาษา | YES |
| `expertise` | สกิล/ความรู้ถาวร ไม่ลืม | YES |
| `brand_context` | ดึงจาก Brand ของทีม (derived — ไม่เก็บใน agent) | YES (derived) |
| `learnings` | บทเรียนสะสมจาก feedback | YES (last 5) |
| `tools` | เครื่องมือที่ใช้ได้ | YES |
| `model` | โมเดลที่ใช้ | YES |
| `team_id` | ทีมที่สังกัด | YES |

Naming: ใช้ `[Role] #N` ไม่ต้องชื่อแปลก ตัวเลข auto-increment ต่อ role

Memory: ยอมรับ context limit — แปลง learnings ที่ใช้บ่อยเป็น expertise ถ้าจำได้นานพอ

Quality: 2 ชั้น — agent ตรวจตัวเอง + manager ตรวจอีกชั้น

## 4. Brand & Team System

### Brand System
- **BrandRegistry**: จัดการแบรนด์ของ user แต่ละคน
- Brand = แบรนด์ที่ user ดูแล เก็บ `brand_context` (โทน, กลุ่มเป้าหมาย, guidelines, คำต้องห้าม) เป็น single source of truth
- 1 Brand มีได้หลายทีม (เช่น ทีม MKT, ทีม Admin ในแบรนด์เดียว)
- ทีมในแบรนด์เดียวกัน → ใช้ brand_context ร่วมกัน ไม่ drift
- ลบ Brand → ต้องจัดการทีมข้างใต้ก่อน
- UI: สร้างแบรนด์ก่อน → คลิกเข้าแบรนด์ → สร้าง/จัดการทีมในแบรนด์นั้น

### Team System
- **TeamRegistry**: จัดการทีม แต่ละทีมมี `brand_id` (บังคับ) + agents + manager
- ทีม = กลุ่ม agent ที่ทำงานด้วยกัน มี Manager agent คอย coordinate
- Manager agent: `allow_delegation=True`, ไม่มี tools, หน้าที่ delegate + synthesize results
- TeamCreateModal: ต้องเลือก Brand ก่อน → สร้างทีมพร้อม config manager (personality, expertise)
- แต่ละทีมมี settings เฉพาะ: review_iterations, max_retry, model selection
- brand_context ไม่เก็บในทีม — ดึงจาก Brand ที่สังกัด

## 5. Review Loop (Quality Control)

- หลัง agent ทำงานเสร็จ → Manager ตรวจสอบ output
- ถ้าไม่ผ่าน → ส่ง feedback กลับให้ agent ทำใหม่ (วนลูปได้หลายรอบ)
- `review_round` — รอบที่ตรวจปัจจุบัน
- `review_summary` — สรุปผลการตรวจ
- `review_feedback` — feedback ส่งกลับให้ agent
- `review_history` — ประวัติการตรวจทุกรอบ (round, status, summary, feedback, output_preview)
- ค่า `review_iterations` กำหนดจำนวนรอบสูงสุด (0 = unlimited)
- ถ้า review ครบรอบแล้วไม่ผ่าน → ส่งผลลัพธ์ล่าสุดให้ user พร้อมแจ้งว่าไม่ผ่าน review

## 6. Media Generation

- **MediaGenerationManager**: สร้าง image, video, TTS, STT ผ่าน OpenRouter API
- รองรับ: image generation, video generation, text-to-speech, speech-to-text, vision (image analysis)
- Generated media เก็บใน `data/users/{user_id}/generated/`
- Image approval flow: agent เสนอ prompt → user approve → generate → display result
- Message types: `image_approval` (approval card), `image_result` (generated media display)

## 7. LLM Management

- **LLMManager**: จัดการ LLM API calls ผ่าน OpenRouter
- **ModelDiscoveryService**: ดึงรายการ models จาก OpenRouter, ตรวจสอบ capabilities (vision, tools, context length)
- **ModelRotator**: สลับ model อัตโนมัติเมื่อเจอ rate limit หรือ error
- **ModelSelector**: เลือก model ตาม capability requirements (reasoning, creative, vision, etc.)
- **ModelCatalog**: รายการ models ที่รองรับ พร้อม pricing และ capabilities
- ทุก agent สามารถใช้ model คนละตัวได้
- Manager agent มี model เฉพาะของตัวเอง

## 8. Scheduler

- **Scheduler**: รัน recurring tasks ตาม schedule แบบ cron
- **ScheduledTaskStore**: เก็บ task definitions ที่ schedule ไว้ใน `data/users/{uid}/scheduled_tasks.json`
- รองรับ: daily, weekly, monthly intervals
- แต่ละ scheduled task มี: prompt, team_id, schedule config, enabled flag
- รันอัตโนมัติโดย background scheduler process

## 9. Agentic File I/O

- Universal input parsing: รับไฟล์ได้ทุกประเภท (image, PDF, audio, video, text, DOCX, XLSX, SVG)
- URL classification: YouTube, direct file, webpage
- แปลงไฟล์เป็น OpenRouter multimodal content blocks (image_url, file, input_audio, video_url)
- ตรวจสอบ model modality support ก่อนส่ง — ถ้าไม่รองรับ → fall back to text extraction
- SSRF protection, download size limits (50MB), text truncation (50K chars)
- CrewAI input files: ส่งไฟล์ตรงไป agent ผ่าน `input_files` parameter

## 10. Coding & Interaction Rules
- Code Clarity: โค้ดต้องอ่านง่าย ไม่ต้องคอมเมนต์ฟุ่มเฟือย แต่ต้องมี Documentation สรุป Logic
- Proactive Explainer: ก่อนเริ่มงานใหญ่ ต้องร่าง Diagram/Logic สรุปให้ User เห็นภาพก่อนเขียนโค้ดเสมอ
- No Over-Engineering: อย่าสร้าง Agent เองถ้า User ไม่ได้สั่ง ให้รอคำสั่งเสมอ

## 11. Operations Protocol
- เมื่อทำงาน feature/bugfix: อ่านไฟล์นี้เพื่อเข้าใจ architecture และ constraints
- เมื่อเจอปัญหา: ห้ามเดาสุ่ม ให้ตรวจสอบ Stack Trace และสรุปให้ User ฟังก่อนแก้
- เมื่อ User สั่งงานทั่วไป: ให้ตอบสนองในฐานะ Assistant ไม่ต้องพยายามสร้าง Agent ทุกกรณี

## 12. Mattpocock Skills (for feature/bugfix work)
Skills คือหลักการทำงาน ใช้ตามเงื่อนไข:

| Trigger | Skill | ทุกครั้ง? |
|---------|-------|-----------|
| เขียนโค้ดใหม่/ฟีเจอร์ใหม่ | `tdd` + `codebase-design` | YES |
| ลงมือ implement งาน | `implement` | YES |
| ส่งมอบงาน/แก้โค้ดเสร็จ | `code-review` | YES |
| เจอ bug หรือ output ผิด | `diagnosing-bugs` (ครบ 6 phases) | YES |
| เปลี่ยนคำศัพท์/concept | `domain-modeling` + อัปเดต `CONTEXT.md` | YES |
| สแกนปรับสถาปัตยกรรม | `improve-codebase-architecture` | ทุก few sprints |

- ห้ามข้ามขั้นตอน ห้ามเดาก่อนใช้ skill
- ข้าม skills ได้สำหรับงานเร่งด่วน (เปิดเว็บ, รัน server, ตอบคำถาม, แก้ config เล็กๆ)

## 13. Account System (Per-User Data Isolation)

### Architecture
- **AuthProvider** (pluggable interface): ปัจจุบันใช้ `System81AuthProvider` (OAuth ผ่าน Sellercenter System81)
- **UserStore**: เก็บ user profile ใน `data/users.json`
- **SessionManager**: สร้าง/verify session token เก็บใน `data/sessions.json` (TTL 7 วัน)
- **Per-user data**: แยกไฟล์ข้อมูลทุกประเภทตาม `data/users/{user_id}/`
  - `brand_registry.json` — brands ของ user นั้น
  - `agent_registry.json` — agents ของ user นั้น
  - `task_registry.json` — tasks ของ user นั้น
  - `chat_sessions.json` — chat history ของ user นั้น
  - `team_registry.json` — teams ของ user นั้น
  - `scheduled_tasks.json` — scheduled tasks ของ user นั้น
  - `history_log.json` — audit log ของ user นั้น
  - `generated/` — generated media ของ user นั้น

### System81 OAuth Flow
1. Frontend เรียก `/api/auth/login-url` → ได้ System81 login URL
2. User คลิก → redirect ไป System81 login page
3. System81 login สำเร็จ → redirect กลับมาพร้อม `?token=...`
4. Frontend ส่ง token ไป `/api/auth/login` → backend verify กับ System81 → สร้าง session token
5. Frontend เก็บ session token ใน localStorage แล้วส่งใน socket auth (`authToken`)
6. Backend `on_chat_start` อ่าน token → verify → ได้ `user_id` → สร้าง stores ด้วย `user_id`
7. ถ้าไม่มี token → dev mode ใช้ legacy paths (backward compatible)

### Pluggable Auth
คนที่มาเชื่อม SSO ขององค์กร แค่ implement `AuthProvider` ใหม่:
```python
class OAuthProvider(AuthProvider):     # Google/Azure AD
class LDAPProvider(AuthProvider):      # Active Directory
class SAMLProvider(AuthProvider):      # SAML SSO
```
ไม่ต้องแก้ code อื่นนอกจาก auth module

### API Endpoints (FastAPI, port 8001)
- `POST /api/auth/login` — login ด้วย System81 token หรือ username/password
- `POST /api/auth/verify` — verify session token
- `POST /api/auth/logout` — revoke session token
- `GET /api/auth/login-url` — ดึง System81 OAuth login URL

## 14. Market Parity Baseline (NON-NEGOTIABLE)

**หลักการ:** อะไรที่ AI chat / AI agent ในตลาด (Claude, ChatGPT, Gemini, Devin, Cursor, Replit Agent, etc.) ทำได้ ระบบเราต้องทำได้

เว็บของเรามีเพียงสมองจาก API Key ของ OpenRouter — แต่นั่นคือสมองเดียวกับที่ตลาดใช้
วิธีการสร้าง วิธีการแก้ไข มันต้องมีอยู่แล้ว ไม่มีอะไรที่ทำไม่ได้ นอกจากข้อจำกัดที่จำกัดไว้จริงๆ

### กฏ
- **ไม่ต้องถาม user ก่อนทำ parity feature** — ค้นหาว่าตลาดทำยังไง แล้วทำให้เหมือน
- **ไม่มี manual checklist** — checklist ไม่มีทางครบ ตลาดเปลี่ยนเร็ว และเราไม่รู้ทุก feature
- **Bug-driven parity**: เมื่อเจอ bug หรือ user อยาก feature → ค้นหาว่าตลาดทำยังไง → ทำให้เหมือน
- **หากตลาดทำได้ เราต้องทำได้** — ใช้ OpenRouter API เหมือนกัน ถ้าเขาทำได้ เราทำได้
- **ข้อจำกัดที่แท้จริง** = API rate limit, model capability, browser security sandbox — ไม่ใช่ "ไม่รู้ทำยังไง"

## 15. AI Usage Hub Logging (NON-NEGOTIABLE)

**หลักการ:** ทุกครั้งที่ระบบเรียก AI/scraping provider จริง (OpenRouter, Apify, 9arm, ฯลฯ) ต้องยิง log ไป AI Usage Hub ที่ `https://digital.in.th` — ไม่มี exception

### ทำไมต้องทำ
- ดูค่าใช้จ่าย/โทเคน/error rate แยกตาม user/model/provider แบบรวมศูนย์
- หัวหน้าดู dashboard ที่ `https://digital.in.th/ai-usage`
- OpenRouter เก็บ transaction log แค่ 31 วัน — log สดแม่นกว่าดึงย้อนหลัง

### กฎ
- **ทุก call site ต้อง log** — รวม error path ไม่ใช่แค่ success
- **`provider` บังคับ** — ส่งชัดทุกครั้ง ถ้าลืมจะกลายเป็น `"unknown"` ใน dashboard
- **`cost_usd` ต้องเป็นราคาจริง** — จาก `usage.cost` ของ OpenRouter ห้ามประมาณ
- **`metadata.analysis_type`** — แยกประเภทงาน (`chat`, `media`, `search`, `agent`) เพื่อ filter ใน dashboard
- **`user`/`reference`** — ตั้งใน contextvar ที่ entry point (`chat.py`) ไม่ใช่ส่งในแต่ละ call site
- **fire-and-forget** — log ต้องไม่ block หรือ throw error ถ้า Hub ล่ม
- **env var**: `AI_USAGE_HUB_URL`, `AI_USAGE_HUB_TOKEN`, `AI_USAGE_HUB_TIMEOUT` (ดู `.env.example`)

### ฟังก์ชันหลัก
- `backend/ai_usage_hub.py` → `log_ai_usage(entry: dict) -> None`
- ใช้ daemon thread, ไม่ throw, ไม่ block

### ถ้าเพิ่ม call site ใหม่
1. หลังได้ response จาก provider → เรียก `log_ai_usage({...})` ทันที
2. ใน `except` block → เรียก `log_ai_usage({...})` ด้วย `status="error"`
3. ส่ง `provider`, `model`, `operation`, `source`, `status`, `duration_ms`, `metadata` ครบ
4. ส่ง `cost_usd` จาก `usage.cost` ถ้ามี response
5. ส่ง `request_id` จาก `response.id` ถ้ามี
6. ส่ง `units` ถ้าไม่ใช่ token (เช่น `{"images_processed": 1}`)

### อย่าทำ
- ห้ามเขียน log ลงไฟล์ในเครื่อง (ลบ `credit_logger.py` ไปแล้ว)
- ห้ามประมาณราคาเอง
- ห้าม log แค่ success path

## 15. Secrets & Credentials Handling (NON-NEGOTIABLE)

**ห้ามอ่านค่า secret โดยตรงจาก `.env` หรือไฟล์ credential ใดๆ** — ไม่ว่าจะด้วย `cat`, `grep`, `read`, หรือคำสั่งอื่นใดที่แสดงค่าจริงออกมาใน context ของ agent

### สิ่งที่ห้ามทำ
- ห้าม `cat .env`, `grep KEY .env`, `read .env` หรือคำสั่งใดๆ ที่ทำให้ค่า secret ปรากฏใน output
- ห้าม print/log ค่า secret ออกมาใน terminal, chat, หรือไฟล์ log
- ห้าม copy ค่า secret ไปใส่ใน code, commit message, comment, หรือ documentation
- ห้ามส่งค่า secret ให้ user ดูใน chat — ถ้า user ถาม ให้บอกว่า "ห้ามแสดง secret ตามกฎ"

### วิธีที่ถูกต้อง
- **ใช้ผ่าน environment variable เท่านั้น** — ให้ code อ่านจาก `os.environ` หรือ `dotenv` ใน runtime ไม่ใช่ให้ agent อ่านเอง
- **ตรวจสอบการเชื่อมต่อผ่าน script** — เขียน script ที่โหลดค่าจาก env var แล้วทดสอบการเชื่อมต่อ โดย script แสดงผลแค่ "connected/not connected" ไม่เปิดเผยค่า secret
- **ถ้าต้อง debug auth** — ให้ script แสดงแค่สถานะ (success/fail) และ error message จาก library โดยไม่ echo ค่าที่ใช้
- **อ้างอิงชื่อ key ได้** — บอกได้ว่ามี key ชื่อ `MONGO_PASSWORD` อยู่ แต่ห้ามแสดงค่า

### ตัวอย่าง
```python
# ถูก — script โหลดจาก env เอง, แสดงแค่สถานะ
import os
from pymongo import MongoClient
client = MongoClient(host=os.environ["MONGO_HOST"], username=os.environ["MONGO_USER"], password=os.environ["MONGO_PASSWORD"])
try:
    client.admin.command("ping")
    print("MongoDB: connected")
except Exception as e:
    print(f"MongoDB: failed — {type(e).__name__}: {e}")
```

```bash
# ผิด — เปิดเผยค่า secret ใน output
grep MONGO_PASSWORD .env
cat .env
```

## 16. Assumption & Pivot Protocol (เมื่อความจริงเปลี่ยน แผนต้องตาม)

แผน (OST + milestone + issue) ทุกอันมี assumption ซ่อนอยู่ เมื่อค้นพบว่า assumption ผิด ต้องปรับแผนตามลำดับนี้ ห้ามข้าม:

### 16.1 ทุก OST Opportunity ต้องมี Assumption ชัด
- ใต้แต่ละ Opportunity ใน `OST.md` ต้องบอกว่า "สมมติฐานคืออะไร"
- เช่น: `# Assumption: สินค้าอยู่ใน MongoDB แล้ว (read-only)`
- ถ้าไม่มี assumption ชัด = planning fiction (วางแผนจากความเชื่อที่ไม่ได้เขียน)

### 16.2 เมื่อ Assumption พัง — Impact Analysis ก่อน, ปรับแผนทีหลัง
ก่อนแก้อะไร ต้องรู้ว่า assumption ที่พังกระทบอะไรบ้าง:

1. **ระบุ assumption ที่พัง** — เขียนชัดว่า assumption อะไร, ผิดเพราะอะไร, เรียนรู้อะไรใหม่
2. **ไล่หาทุก issue ที่ซ่อน assumption เดียวกัน** — ดูทุก milestone ไม่ใช่แค่ milestone ปัจจุบัน
   - เช่น: assumption "เก็บใน JSON" ซ่อนอยู่ใน #24, #31, #116, #132, ...
3. **บันทึก ADR** — บอก assumption ที่พัง + ทิศใหม่ + รายการ issue ที่กระทบ
4. **ตัดสินใจ scope ใหม่** — บางทีต้องสร้าง scope ที่ไม่เคยมีในแผน (เช่น "data persistence layer" ไม่เคยเป็น issue ของตัวเอง)
5. **ปรับ OST** — แก้ Opportunity ที่ assumption พัง + บอกว่า assumption เดิมผิดเพราะอะไร
6. **ปรับ issue**:
   - issue เดิม: mark "pivot" ใน body + บอก why (ห้ามลบ, ห้ามแก้จนเป็นเรื่องอื่น)
   - issue ใหม่: สร้างถ้าทิศเปลี่ยนเป็นเรื่องอื่น (1 issue = 1 concept)
   - issue อื่นที่กระทบ: เพิ่ม note ใน body ว่า "assumption X เปลี่ยน, ดู ADR-00XX"
7. **ปรับ milestone ถ้าจำเป็น** — ถ้าทิศใหม่ไม่ fit milestone เดิม หรือต้องสร้าง milestone ใหม่
8. **อัปเดต DEVELOPER_LOG** — บันทึก "signal ที่เรียนรู้" ไม่ใช่แค่ "decision ที่เปลี่ยน"

### 16.3 เมื่อไหนสร้าง milestone ใหม่ vs ใส่ใน milestone เดิม
- **สร้าง milestone ใหม่** เมื่อทิศใหม่:
  - เป็น foundation ที่กระทบหลาย milestone (เช่น data persistence กระทบ M6, M8, M9, M10, M11)
  - ไม่ fit ชื่อ/desc milestone เดิม
  - ทำให้ milestone เดิมบวมเกิน 3 เรื่องปน
- **ใส่ใน milestone เดิม** เมื่อ:
  - ทิศใหม่ยังเกี่ยวกับ milestone เดิม
  - ไม่กระทบ milestone อื่น
- ตั้งชื่อ milestone ใหม่ให้สื่อทิศใหม่ ไม่ใช่ตั้งชื่อสวยๆ

### 16.4 ห้ามทำ
- ห้ามลบ issue เดิมทิ้ง — ทำให้สูญเสียประวัติการตัดสินใจ
- ห้ามแก้ issue เดิมจนเป็นเรื่องอื่น — ใช้ issue ใหม่แทน (1 issue = 1 concept)
- ห้ามปรับแผนเงียบ — ต้องบันทึกใน ADR + DEVELOPER_LOG ทุกครั้ง
- ห้าม blame ตัวเอง/team — assumption ผิด = เรียนรู้ ไม่ใช่ความผิด
- ห้ามปรับแค่ issue ที่เจอโดยตรง — ต้องไล่หา issue อื่นที่ซ่อน assumption เดียวกัน

### 16.5 ตัวอย่าง (เคส MongoDB)
```
เดิม:
  OST Opp 7: สินค้าอยู่ใน MongoDB → ดึงข้อมูล
  #129: เชื่อม AI กับ MongoDB ดึงสินค้า
  Assumption (ซ่อน): MongoDB มีสินค้าอยู่แล้ว, เรามีสิทธิ์ read

ความจริงที่เจอ:
  MongoDB ว่างเปล่า + สิทธิ์ readWrite
  → assumption ผิด

Impact Analysis:
  assumption ที่พัง: "MongoDB มีสินค้า + เรามีสิทธิ์ read"
  assumption ซ่อนที่โผล่: "ทุก issue ที่เก็บ data สมมติว่าใช้ JSON"
  issue ที่กระทบ:
    - #129 (ดึงสินค้า) → pivot
    - #106 (Knowledge Store) → ลบ MongoDB connector ดึงสินค้า
    - #24, #31, #36, #116, #132 (เก็บ data) → อาจต้องย้ายไป MongoDB
  scope ใหม่ที่ไม่เคยมี: "data persistence layer" (ไม่เคยเป็น issue ของตัวเอง)

ปรับแผน:
  1. ADR 0006: "MongoDB = data storage ของเรา ไม่ใช่ดึงสินค้า" + บอก ADR-0003 (JSON) ถึงเวลาย้าย
  2. OST Opp 7: แก้ + บอกว่า assumption เดิมผิด
  3. #129: mark pivot (ไม่ลบ) + บอก why ใน body
  4. สร้าง milestone ใหม่ "M6.5: Data Persistence Migration" (foundation กระทบ M6/M8/M9/M10/M11)
  5. สร้าง issue ใหม่ใน M6.5: "data persistence layer (ย้าย JSON → MongoDB ทีละ store)"
  6. #106, #24, #31, ...: เพิ่ม note ว่า assumption เปลี่ยน, ดู ADR-0006
  7. M6 เดิม: ลด scope เหลือ Brand entity + Knowledge (พักสินค้า)
  8. DEVELOPER_LOG: บันทึก signal ที่เรียนรู้
```
