# Search Parity — Handoff Doc

> **วิธีใช้**: ใน new Devin session พิมพ์ `@` แล้วเลือกไฟล์นี้ แล้ว copy-paste prompt ของ task ที่จะทำ

## ภาพรวม

ระบบ search ของเราต้องทำได้เหมือนตลาด (Claude/ChatGPT/Gemini) ตามกฏ Market Parity Baseline ใน `SYSTEM_PROTOCOL.md` section 14

หลังจากสำรวจตลาด + ตรวจโค้ดเรา พบ 10 ข้อที่ต้องทำ แบ่งเป็น 4 tasks:

| Task | ข้อที่ครอบคลุม | ขนาด | สถานะ |
|------|---------------|------|------|
| **B. Date injection** | #10 | เล็ก | ✅ DONE (commit `41756f6`) |
| **A. Migration plugin → server tool** | #1, #2, #3, #7, #8, #9 | กลาง/เสี่ยง | ✅ DONE — code + bug fixes (search_model propagation, web_search_options adapter) + manual test ผ่าน 2026-08-05 (Perplexity ไม่ 404, source URLs คลิกได้, review loop ทำงาน) |
| **C. Prompt: read full pages** | #5 | เล็ก | ⏳ TODO — อาจไม่จำเป็น: Perplexity ส่ง passage ละเอียดพอแล้ว (manual test ได้ตัวเลข box office ละเอียด) |
| **D. Frontend: source chips** | #6 | กลาง | ⏳ TODO — URL คลิกได้ใน result แล้ว แต่ยังไม่ใช่ chip แบบตลาด |

## ลำดับที่แนะนำ

1. ~~Task B — date injection~~ ✅ เสร็จ
2. ~~Task A — migration~~ ✅ เสร็จ
3. **Task C — prompt** (เล็ก ทำหลัง A) — อาจ skip ถ้า Perplexity passage เพียงพอ
4. **Task D — frontend** (แยก ทำทีหลังได้)

## สถานะ issue บน GitHub

- ✅ #125 — FreeModelRotator stale slugs — CLOSED 2026-08-05 (session 11) — dynamic catalog fetch
- ⏳ #126 — Manager LLM flaky JSON parse — open (P1, ต้อง capture full response ก่อน)

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

---

# Architecture Debt — ทำหลัง Task C/D เสร็จ

> **วิธีใช้**: หลัง HANDOFF tasks ครบ ใช้ `/improve-codebase-architecture` skill ทำ refactor ตามรายการนี้
> ลำดับความสำคัญ sort ตาม "bugs we've hit" → "will hit" → "code smell"

## ทำไมต้องแก้ architecture ก่อนทำ feature ต่อ

บัค 2 ตัวที่เจอตอน manual test Task A ไม่ใช่บัคจาก Task A — เป็น **architecture debt** ที่ซ่อนอยู่:

1. **Bug search_model ไม่ propagate** — เกิดจาก Python module-rebinding gotcha (`from X import Y` คัดลอก binding)
2. **Bug perplexity 404** — เกิดจาก decision logic กระจาย ไม่มีจุดเดียวที่ตัดสินใจว่า model ไหนรองรับ `tools`

ถ้าไม่แก้ architecture จะเจอบัคแบบนี้ซ้ำทุกครั้งที่เพิ่ม feature ใหม่

## ลำดับการแก้ (priority)

### P0 — Bugs we've hit (แก้ก่อน)

#### P0.1 Module-level globals เป็น shared state (anti-pattern)

**ไฟล์**: `backend/globals.py`, `backend/core/orchestrator.py`, `backend/tools/search.py`, `backend/tools/media.py`, `backend/tools/audio.py`, `backend/tools/document.py`, `backend/tools/web.py`

**ปัญหาปัจจุบัน**:
- `_progress_callback`, `_media_gen_manager`, `_media_tool_results`, `_thread_local`, `_search_model` เป็น module-level mutable globals
- ใช้ 2 pattern ผสมกัน: `from backend.globals import X` (คัดลอก binding) กับ `import backend.globals as g; g.X` (dynamic)
- Python gotcha: `from X import Y` คัดลอก binding ตอน import ครั้งเดียว → reassign ใน module อื่นไม่ส่งผล
- บัค search_model เกิดจาก pattern นี้ (แก้ชั่วคราวแล้วด้วย dynamic read/write ผ่าน `_globals`)

**จุดที่ใช้**:
| Global | ผู้เขียน | ผู้อ่าน |
|--------|---------|---------|
| `_search_model` | orchestrator.py:406, 1520 | search.py:125 |
| `_progress_callback` | orchestrator.py:385, 1518 | search.py, media.py, audio.py, document.py, web.py |
| `_media_gen_manager` | orchestrator.py:386, 1519 | media.py, audio.py |
| `_media_tool_results` | orchestrator.py:387 | media.py, audio.py, document.py |
| `_thread_local` | orchestrator.py:511-522 | search.py, media.py, audio.py, factory.py |

**ทางแก้**: แทนที่ globals ด้วย **dependency injection** — ส่ง context object ผ่าน function parameter แทนการอ่านจาก global

**Deletion test**: ถ้าลบ globals ออก ความซับซ้อนจะ concentrate ที่ call sites (ต้องส่ง context ทุกฟังก์ชัน) — แต่นั่นคือสิ่งที่ถูกต้อง เพราะทำให้ dependency ชัดเจน

---

#### P0.2 Decision logic กระจาย — ไม่มีจุดเดียวที่ตัดสินใจ — ✅ DONE (session 10)

**สถานะ**: SearchAdapter สร้างแล้วใน `backend/tools/search_adapter.py` — แก้บัค perplexity 404
โดยเลือก `tools` (server tool) หรือ `web_search_options` (perplexity built-in) อัตโนมัติ
ผ่าน `ModelDiscoveryService.get_supported_parameters()`. 364 tests pass, 0 regressions.

**Session 10 amendment**: 
- แก้ bug ใน `supports_server_tool` ที่เช็ค `"web_search"` (ชื่อเก่า) แทน `"web_search_options"` (ชื่อปัจจุบัน) — ทำให้ Perplexity ทุกตัว return True ผิด และเกิด 404 อีก (bug เดียวกับที่ ADR-0004 หมายจะแก้)
- เพิ่ม `SearchAdapter.resolve_search_model()` เป็น single resolution point — รวม 4 จุดตัดสินใจเข้าเป็น 1 deep module + 1 thin wrapper ใน search.py
- แก้ test data ใน `test_search_adapter.py` + `test_web_search_migration.py` ที่ใช้ `"web_search"` ใน fake catalog (เหตุที่ bug หลุดรอดมา)
- ADR-0004 มี amendment section บันทึกการเปลี่ยนแปลง

**คงเหลือ**: `_globals._search_model` ยังอยู่ (P0.1 จะแทนด้วย DI) — wrapper ใน search.py ยังอ่านจาก global แต่ logic อยู่ใน adapter หมดแล้ว

**ไฟล์**: `backend/tools/search.py:47-85`, `backend/llm/selector.py:39`, `backend/llm/discovery.py:72`, `backend/core/secretary.py:610-620`, `backend/handlers/chat.py:2753-2760`, `backend/core/orchestrator.py:398-431`

**ปัญหาปัจจุบัน** — 4 จุดตัดสินใจ search model:
1. Secretary (plan phase) — เลือก search_model ใน plan JSON
2. chat.py — เก็บใน `cl.user_session("ai_search_model")`
3. orchestrator.py — อ่านจาก session → เขียนลง `_globals._search_model`
4. search.py `_resolve_search_model` — อ่านจาก `_globals._search_model` + fallback chain

**ปัญหาเพิ่มเติม — ไม่มีการตรวจ model capability**:
- `_call_openrouter_web_search` ส่ง `tools: [{type: "openrouter:web_search"}]` ให้ทุก model
- Perplexity models (5 ตัว) ไม่รองรับ `tools` — มี `web_search_options` ในตัว
- OpenRouter catalog มี field `supported_parameters` บอกชัดเจน แต่ search.py ไม่ได้ใช้
- บัค perplexity 404 เกิดจากจุดนี้

**OpenRouter catalog field**:
| Model | `tools` | `web_search_options` |
|-------|---------|---------------------|
| `openai/gpt-5.6-luna` | ✅ | ❌ |
| `anthropic/claude-sonnet-5` | ✅ | ❌ |
| `perplexity/sonar-pro` | ❌ | ✅ |

**ทางแก้**: สร้าง **SearchAdapter** module — interface เดียวที่ตัดสินใจ:
- รับ model name + query
- ตรวจ `supported_parameters` (cache จาก catalog)
- เลือก format: `tools` (server tool) หรือ `web_search_options` (perplexity built-in)
- ซ่อน fallback chain ไว้ข้างใน

**Deletion test**: ถ้ามี adapter จุดเดียว ลบ logic กระจาย 4 จุดออก → complexity concentrate ที่ adapter (deep module)

---

### P1 — Will hit bugs (แก้รองลงมา)

#### P1.1 Hidden coupling ผ่าน `cl.user_session` (100+ จุด)

**ไฟล์**: `backend/handlers/chat.py` (50+ จุด), `backend/core/orchestrator.py` (10+ จุด), และอื่นๆ

**ปัญหาปัจจุบัน**:
- 100+ จุดเรียก `cl.user_session.get/set` — dependency ซ่อนอยู่ ไม่ปรากฏใน function signature
- ทดสอบไม่ได้ถ้าไม่มี Chainlit context
- รีแฟคเตอร์ยาก — ไม่รู้ว่าฟังก์ชันไหนต้องการ session key อะไร

**ทางแก้**: สร้าง **SessionContext** object — รวม session keys ทั้งหมดเป็น dataclass ส่งผ่าน parameter

---

#### P1.2 `_thread_local` เป็น shared mutable bag (ไม่มี schema)

**ไฟล์**: `backend/globals.py:64`, `backend/core/orchestrator.py:511-522`, `backend/tools/search.py:44,95-106`

**ปัญหาปัจจุบัน**:
- `_thread_local` เก็บ `agent_name`, `search_call_count`, `max_search_calls`, `search_config` — ไม่มี schema enforcement
- โมดูลไหนก็เพิ่ม attribute ได้ ไม่มีใครรู้ว่ามีอะไรบ้าง
- coupling ซ่อนอยู่ — ไม่รู้จาก signature ว่าฟังก์ชันต้องการ `_thread_local.search_config`

**ทางแก้**: แทนที่ด้วย **AgentRunContext** dataclass — ส่งผ่าน parameter แทน thread-local

---

### P2 — Code smell (แก้ทีหลังได้)

#### P2.1 Shallow wrapper modules (fail deletion test)

| Module | บรรทัด | Deletion test |
|--------|-------|---------------|
| `backend/agents/tool_registry.py` | 39 | **FAIL** — complexity แค่ย้ายไป call sites |
| `backend/agents/capability.py` | 144 | **FAIL** — static data ควรเป็น config file |
| `backend/llm/rotator.py` | 100 | **FAIL** — hardcoding แค่ย้ายมาที่นี่ |
| `backend/agents/templates.py` | 99 | **FAIL** — มี template เดียว, premature structure |

**ทางแก้**: inline หรือย้ายไปเป็น config file (JSON/YAML)

---

#### P2.2 `user_prompt_ctx` ContextVar ข้าม thread

**ไฟล์**: `backend/globals.py:65`, `backend/handlers/chat.py:97,512,1323`, `backend/core/orchestrator.py:63,86`, `backend/credit_logger.py:17`

**ปัญหาปัจจุบัน**:
- ใช้ `contextvars.copy_context()` ใน orchestrator.py:435 — ถ้า copy ผิด ค่าหาย
- propagation ใน async boundary ไม่ชัดเจน

**ทางแก้**: ส่ง user_prompt ผ่าน parameter หรือใช้ proper async context propagation

---

## วิธีเริ่ม refactor (หลัง HANDOFF ครบ)

1. อ่าน `/codebase-design` skill สำหรับ vocabulary (module, interface, depth, seam, adapter)
2. เริ่มจาก **P0.2 (SearchAdapter)** ก่อน — เพราะ:
   - แก้บัค perplexity 404 ที่ยังไม่ได้แก้
   - สร้าง seam ที่ทำให้ P0.1 ง่ายขึ้น (adapter รับ context ผ่าน parameter ไม่ใช่ global)
3. แล้วค่อย **P0.1 (dependency injection)** — ใหญ่สุด กระทบหลายไฟล์
4. P1/P2 ทำทีหลังได้

## กฏที่ต้องยึดตอน refactor

1. **TDD** — red before green, ทีละ slice
2. **Surgical changes** — แก้เฉพาะที่เกี่ยวข้อง ไม่ refactor ข้างเคียง
3. **code-review** — mandatory หลังแต่ละ refactor step
4. **DEVELOPER_LOG.md** — บันทึกทุกการเปลี่ยนแปลง
5. **อย่าลบ globals ทิ้งก่อนสร้าง adapter** — ทำทีละตัว, ทดสอบ, แล้วค่อยลบ
