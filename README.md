# Dynamic Agent Management Platform

แพลตฟอร์มสร้าง AI Agent อัตโนมัติ — ผู้ใช้พิมพ์คำสั่ง → AI ประเมินและสร้างแผน → ผู้ใช้อนุมัติ → Agent หลายตัวทำงานร่วมกัน → ส่งผลลัพธ์กลับ

## เริ่มต้นอย่างรวดเร็ว

> **อ่านภาพรวมโปรเจคก่อน** → เปิด [docs/project-overview.html](docs/project-overview.html) ในเบราว์เซอร์ (มีไดอะแกรม คำอธิบายทุกโมดูล และ checklist)

### สถาปัตยกรรม

| ชั้น | เทคโนโลยี | พอร์ต |
|------|-----------|-------|
| Frontend | React + TypeScript + TailwindCSS (Vite) | 5173 |
| Backend | Python + Chainlit + CrewAI | 8000 |
| External | OpenRouter (LLM), System81 (OAuth) | — |

- สื่อสารผ่าน **WebSocket (JSON)**
- เก็บข้อมูลใน **JSON files** (ไม่มี database)
- มี 2 UI: **Modern** และ **Retro (Win95)**

### รันเซิร์ฟเวอร์

```bash
# Backend (port 8000)
source venv/bin/activate
PYTHONPATH=/Users/its-dev2/my-agent-app chainlit run app.py --host 0.0.0.0 --port 8000

# Frontend (port 5173) — เปิดในเบราว์เซอร์ที่นี่
cd frontend && npm run dev
```

หรือใช้ `./ctl.sh start` / `./ctl.sh stop`

### โครงสร้างหลัก

```
app.py                    → HTTP endpoints (login, upload, media)
backend/
├── handlers/chat.py      → รับ message, ตัดสินใจ, สั่งทำงาน
├── core/                 → Secretary, Orchestrator, Messenger, Scheduler
├── agents/               → Registry, Factory, Stores (JSON)
├── llm/                  → Manager, Rotator, Selector, Catalog
├── tools/                → Search, Media, Audio, Browser, Document, Web
├── attachment/           → Processor, Security, URL
├── auth/                 → System81 OAuth, DevLogin, Session
└── media/manager.py      → สร้างสื่อผ่าน OpenRouter
frontend/src/
├── App.tsx               → Socket.IO + state management
├── components/           → Modern UI + Retro UI (Win95)
└── context/              → PlatformContext, AuthContext
docs/
├── project-overview.html → ภาพรวมโปรเจคแบบละเอียด (เปิดในเบราว์เซอร์)
└── adr/                  → Architecture Decision Records
```

### เอกสาร

- [docs/project-overview.html](docs/project-overview.html) — ภาพรวมโปรเจคแบบละเอียด (7 sections + ไดอะแกรม)
- [CONTEXT.md](CONTEXT.md) — คำศัพท์และ domain glossary
- [docs/adr/](docs/adr/) — Architecture Decision Records
