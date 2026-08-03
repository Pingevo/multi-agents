# SYSTEM_PROTOCOL: Agent Management Platform

## 0. Project Goal (North Star)

**สร้าง Multi-Agent Platform ที่ใช้ AI เป็นพนักงานจริง ไม่ใช่แค่แชทบอท**

โจทย์ตัวอย่าง: วางแผน Monthly Content — โพสวันละอย่าง 1 โพส, Short Video และ Artwork สัดส่วน 50:50 ต่อเดือน

วิสัยทัศน์: Platform เปรียบเสมือนบริษัท มีทีม แบรนด์ และพนักงาน AI
- บริษัท (Platform) → ทีม (Team) → แบรนด์ (Brand) → พนักงาน (Agent)
- แต่ละทีมดูแลแบรนด์ของตัวเอง มีฐานความรู้เฉพาะ
- Agent แต่ละตัว = พนักงานจริง มี persona, expertise, brand context, memory
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
  ├── Agents: Registry, Factory, TaskStore, ChatStore, TeamRegistry
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
- **Windows**: ChatWindow, TasksWindow, AgentsWindow, HistoryWindow, NotificationsWindow, SettingsWindow, ScheduleWindow, AgentDetailWindow

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
| `brand_context` | แบรนด์ที่ดูแล + guidelines + target audience | YES |
| `learnings` | บทเรียนสะสมจาก feedback | YES (last 5) |
| `tools` | เครื่องมือที่ใช้ได้ | YES |
| `model` | โมเดลที่ใช้ | YES |
| `team_id` | ทีมที่สังกัด | YES |

Naming: ใช้ `[Role] #N` ไม่ต้องชื่อแปลก ตัวเลข auto-increment ต่อ role

Memory: ยอมรับ context limit — แปลง learnings ที่ใช้บ่อยเป็น expertise ถ้าจำได้นานพอ

Quality: 2 ชั้น — agent ตรวจตัวเอง + manager ตรวจอีกชั้น

## 4. Team System

- **TeamRegistry**: จัดการทีม แต่ละทีมมี agents และ manager
- ทีม = กลุ่ม agent ที่ทำงานด้วยกัน มี Manager agent คอย coordinate
- Manager agent: `allow_delegation=True`, ไม่มี tools, หน้าที่ delegate + synthesize results
- TeamCreateModal: สร้างทีมพร้อม config manager (personality, expertise, brand_context)
- แต่ละทีมมี settings เฉพาะ: review_iterations, max_retry, model selection

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
