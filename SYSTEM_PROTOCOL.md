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
- Text/Chat, Image, Video, Web Search → OpenRouter API
- Text-to-Speech (TTS), Speech-to-Text (STT) → OpenRouter Audio API
- Vision (image analysis) → OpenRouter (model ที่รองรับ image input)
- Embeddings → OpenRouter (model ที่มี output_modalities=embeddings)
- ระบบค้นพบ model แบบไดนามิกจาก API — ห้าม hardcode

## 1. Project Philosophy
- User คือ Manager: ผู้ตัดสินใจสูงสุดคือ User ทุกฟีเจอร์ต้องผ่านการอนุมัติ
- System Design: Agent Factory & Registry (Single Source of Truth)
- UI/UX: **Dashboard-first, Chat-second**. ไม่พ่น Log หรือ Debug ข้อมูลรกหน้าแชท
- Central Secretary: ต้องมี **AI Assessor** ประเมินความต้องการและถาม requirement ก่อนตัดสินใจ

## 2. UI/UX Rules (Dashboard-First)
- Main View: ต้องเป็น **Agent Control Panel** ที่แสดง Task Slots, Plans, Agent Status แบบ Visual
- Sidebar: ต้องเป็น **Agent Console** ที่ค้างอยู่ตลอดเวลา มี Agent Table + ปุ่ม Action จัดการ Agent
- Chat: ทำหน้าที่เป็น **Command Center** รับคำสั่งอย่างเดียว ไม่ใช่ที่แสดงผลการทำงานของ Agent
- ห้ามใช้ `cl.Message` ในการอัปเดตสถานะงาน ให้ใช้การอัปเดต Custom Element บน Dashboard แทน
- ห้ามสร้าง Text Log รกรุงรังในแชท ทุก Task ต้องมี Slot ของตัวเองบน Dashboard

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

## 4. Coding & Interaction Rules
- Auto-Documentation: ทุกครั้งที่แก้ไขโค้ด ต้องอัปเดตไฟล์ `DEVELOPER_LOG.md` เสมอ
- Code Clarity: โค้ดต้องอ่านง่าย ไม่ต้องคอมเมนต์ฟุ่มเฟือย แต่ต้องมี Documentation สรุป Logic
- Proactive Explainer: ก่อนเริ่มงานใหญ่ ต้องร่าง Diagram/Logic สรุปให้ User เห็นภาพก่อนเขียนโค้ดเสมอ
- No Over-Engineering: อย่าสร้าง Agent เองถ้า User ไม่ได้สั่ง ให้รอคำสั่งเสมอ

## 5. Operations Protocol (Mandatory)
- เมื่อเริ่มต้นงานใหม่: ต้องอ่านไฟล์นี้เป็นลำดับแรก
- เมื่อเจอปัญหา: ห้ามเดาสุ่ม ให้ตรวจสอบ Stack Trace และสรุปให้ User ฟังก่อนแก้
- เมื่อ User สั่งงานทั่วไป: ให้ตอบสนองในฐานะ Assistant ไม่ต้องพยายามสร้าง Agent ทุกกรณี

## 6. Mattpocock Skills (MANDATORY — Non-negotiable)
Skills คือหลักการทำงาน ไม่ใช่ one-shot tools ต้องใช้ทุกครั้งตามเงื่อนไข:

| Trigger | Skill | ทุกครั้ง? |
|---------|-------|-----------|
| เขียนโค้ดใหม่/ฟีเจอร์ใหม่ | `tdd` + `codebase-design` | YES |
| ลงมือ implement งาน | `implement` | YES |
| ส่งมอบงาน/แก้โค้ดเสร็จ | `code-review` | YES |
| เจอ bug หรือ output ผิด | `diagnosing-bugs` (ครบ 6 phases) | YES |
| เปลี่ยนคำศัพท์/concept | `domain-modeling` + อัปเดต `CONTEXT.md` | YES |
| สแกนปรับสถาปัตยกรรม | `improve-codebase-architecture` | ทุก few sprints |

- ห้ามข้ามขั้นตอน ห้ามเดาก่อนใช้ skill
- ถ้าไม่แน่ใจว่าจะใช้ skill ไหน → อ่าน `SYSTEM_PROTOCOL.md` ก่อนเริ่มงาน

## 7. Maintenance
- ทุกครั้งที่ปิดโปรเจกต์หรือจบงาน: อัปเดต `DEVELOPER_LOG.md` ให้เป็นปัจจุบันที่สุด
