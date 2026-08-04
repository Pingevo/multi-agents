# Search Parity — Handoff Doc

> **วิธีใช้**: ใน new Devin session พิมพ์ `@` แล้วเลือกไฟล์นี้ แล้ว copy-paste prompt ของ task ที่จะทำ

## ภาพรวม

ระบบ search ของเราต้องทำได้เหมือนตลาด (Claude/ChatGPT/Gemini) ตามกฏ Market Parity Baseline ใน `SYSTEM_PROTOCOL.md` section 14

หลังจากสำรวจตลาด + ตรวจโค้ดเรา พบ 10 ข้อที่ต้องทำ แบ่งเป็น 4 tasks:

| Task | ข้อที่ครอบคลุม | ขนาด | สถานะ |
|------|---------------|------|------|
| **B. Date injection** | #10 | เล็ก | ✅ DONE (commit `41756f6`) |
| **A. Migration plugin → server tool** | #1, #2, #3, #7, #8, #9 | กลาง/เสี่ยง | ⏳ TODO |
| **C. Prompt: read full pages** | #5 | เล็ก | ⏳ TODO |
| **D. Frontend: source chips** | #6 | กลาง | ⏳ TODO |

## ลำดับที่แนะนำ

1. ~~Task B — date injection~~ ✅ เสร็จ
2. **Task A — migration** (เร่งด่วน เพราะ OpenRouter ถอด plugin เก่า)
3. **Task C — prompt** (เล็ก ทำหลัง A)
4. **Task D — frontend** (แยก ทำทีหลังได้)

## รายละเอียดแต่ละ Task

### Task A: Migration plugin → server tool (เร่งด่วน)

**ทำไม**: OpenRouter ประกาศ `plugins: [{id: "web"}]` เป็น deprecated ให้ใช้ `tools: [{type: "openrouter:web_search"}]` แทน ถ้าไม่ migrate ระบบ search พังเมื่อ OpenRouter ถอดรองรับ

**ไฟล์หลัก**: `backend/tools/search.py` บรรทัด 30-47 (ฟังก์ชัน `_call_openrouter_web_search`)

**สิ่งที่ต้องเปลี่ยน**:
- `plugins: [{"id": "web", "max_results": 5}]` → `tools: [{"type": "openrouter:web_search", "parameters": {...}}]`
- เพิ่ม parameters: `engine`, `max_results`, `max_total_results`, `search_context_size`
- ปล่อยให้ model ตัดสินใจว่าจะค้นเมื่อไหร่ (server tool ทำได้ แต่ plugin บังคับค้นทุกครั้ง)

**อ้างอิงตลาด**:
- OpenRouter docs: https://openrouter.ai/docs/guides/features/server-tools/web-search
- ChatGPT 8.2 queries/prompt, Claude 5.4, Gemini 6.8 (multi-query reformulation)
- ตลาดใช้ engine ต่างกัน: ChatGPT=Bing, Claude=Brave, Gemini=Google, Perplexity=Sonar

**กฏที่เกี่ยวข้อง**:
- Market Parity Baseline (NON-NEGOTIABLE) — ตลาดทำได้ เราต้องทำได้
- No Hardcode — engine/max_results ต้องเป็น config ไม่ใช่ค่าคงที่ (ใช้ agent spec field)

**ความเสี่ยง**: สูง — ถ้าพารามิเตอร์ผิด ค้นไม่ได้เลย ต้องเทสสุด

---

### Task C: Prompt — read full pages

**ทำไม**: ตลาดอ่าน passage จากหน้าจริงก่อน synthesize เราได้แค่ summary จาก plugin → ข้อมูลตื้น

**ไฟล์หลัก**: `backend/core/secretary.py` (prompt section)

**สิ่งที่ต้องเปลี่ยน**:
- เพิ่มใน secretary prompt: "ถ้า search_web ส่ง URL กลับมา ให้ agent เรียก browse_web อ่านหน้าจริงก่อน synthesize"
- มี `browse_web` (Playwright) และ `scrape_web` (urllib) อยู่แล้วใน `tool_registry.py`

**ความเสี่ยง**: ต่ำ — เปลี่ยนแค่ prompt

---

### Task D: Frontend — source chips

**ทำไม**: ตลาดแสดง source chips คลิกได้ เราฝัง URL ใน text → UX ต่างกว่า

**ไฟล์หลัก**:
- `frontend/src/components/retro/ChatWindow.tsx`
- `frontend/src/schemas/messages.ts`

**สิ่งที่ต้องเปลี่ยน**:
- แยก source URLs จาก search result
- แสดงเป็น chips คลิกได้ (เปิดใน tab ใหม่)
- อาจต้องเพิ่ม field ใน message schema

**ความเสี่ยง**: กลาง — frontend change

## กฏที่ต้องยึดในทุก task

1. **Market Parity Baseline** (SYSTEM_PROTOCOL.md section 14) — ตลาดทำได้ เราต้องทำได้ ไม่ต้องถาม user
2. **No Hardcode** (global_rules.md) — ค่าที่อาจเปลี่ยนต้องเป็น config
3. **TDD** — red before green, one slice at a time
4. **code-review** — mandatory หลัง code changes
5. **DEVELOPER_LOG.md** — update ทุกครั้งที่แก้โค้ด

## ไฟล์ที่เกี่ยวข้องทั้งหมด

- `backend/tools/search.py` — search_web tool (Task A)
- `backend/tools/browser.py` — browse_web (Playwright)
- `backend/tools/web.py` — scrape_web (urllib)
- `backend/agents/tool_registry.py` — tool registration
- `backend/core/secretary.py` — secretary prompt (Task C)
- `backend/agents/factory.py` — agent factory (Task B done here)
- `frontend/src/components/retro/ChatWindow.tsx` — chat UI (Task D)
- `frontend/src/schemas/messages.ts` — message schema (Task D)
- `SYSTEM_PROTOCOL.md` section 14 — Market Parity rule
- `DEVELOPER_LOG.md` — log ทุกการเปลี่ยนแปลง
