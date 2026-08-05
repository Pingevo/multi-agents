# Developer Log

## 2026-08-05 (session 7) — P0.2 SearchAdapter: fix perplexity 404 + consolidate search format decision

### Context
Manual test หลัง Task A เจอ bug: perplexity/sonar-pro + `tools:[openrouter:web_search]` →
404 "No endpoints found that support tool use". Perplexity models มี built-in search
(`web_search_options`) ไม่รองรับ `tools` array — แต่ `_call_openrouter_web_search` ส่ง
`tools` ให้ทุกโมเดล ทำให้ perplexity ค้นเว็บไม่ได้

### Root cause (HANDOFF.md P0.2)
Decision logic กระจาย 4 จุด ไม่มีจุดเดียวที่ตรวจ model capability:
1. Secretary (plan phase) — เลือก search_model
2. chat.py — เก็บใน `cl.user_session("ai_search_model")`
3. orchestrator.py — อ่านจาก session → เขียนลง `_globals._search_model`
4. search.py — `_call_openrouter_web_search` ส่ง `tools` เสมอ (ไม่ตรวจ capability)

### Fix — SearchAdapter (deep module, codebase-design vocabulary)
สร้าง `backend/tools/search_adapter.py` — interface เดียวที่ตัดสินใจ format:
- `supports_server_tool(model) -> bool`: ตรวจ `supported_parameters` จาก `ModelDiscoveryService`
  - `"tools" in params` → True (server tool format)
  - `"web_search" in params` (ไม่มี tools) → False (perplexity built-in)
  - ไม่พบใน catalog → prefix heuristic fallback (`perplexity/` → False)
- `_build_request_body(query, model, search_config)`: เลือก `tools` หรือ `web_search_options`
- `search(query, model, search_config)`: HTTP execution + format selection

`backend/tools/search.py` `_call_openrouter_web_search` ตอนนี้ delegate ไป adapter
`backend/llm/discovery.py` เพิ่ม `get_supported_parameters(model_id)` (surgical addition)

### TDD (red → green, seams confirmed with user first)
- **Seam 1 (approved): `supports_server_tool`** — `test_search_adapter.py` 13 tests
  (perplexity 5 รุ่น → False, claude/gpt/gemini/grok → True, edge cases)
- **Seam 2 (not approved)**: ไม่เขียน test ใหม่ที่ `search()` — อัปเดต `test_web_search_migration.py`
  เดิมให้ตรวจทั้ง 2 รูปแบบ (tools + web_search_options) แทน
- `test_server_tool_compat.py` ถูกลบระหว่าง code-review (Duplicated Code smell — `test_search_adapter.py` ครอบคลุมแล้ว)

### code-review results
- **Standards**: 0 hard violations, 1 judgement call (duplicate test — fixed by deletion)
- **Spec**: 0 missing (deletion test deferred per spec line 249 "อย่าลบ globals ทิ้งก่อนสร้าง adapter"),
  0 scope creep, 0 wrong implementations

### Verification
- `pytest test_search_adapter.py`: 13 passed
- `pytest test_web_search_migration.py`: 13 passed (ทั้ง tools + web_search_options formats)
- `pytest` ทั้งหมด: 368 passed, 0 failed (no regressions)
- **Manual test pending**: สั่งค้นด้วย perplexity จริง เพื่อยืนยันไม่เจอ 404 (ชดเชยการไม่มี test ที่ Seam 2)

### Files changed
- `backend/tools/search_adapter.py` (NEW) — SearchAdapter class
- `backend/llm/discovery.py` — added `get_supported_parameters()`
- `backend/tools/search.py` — `_call_openrouter_web_search` delegates to adapter, ลบ `_build_web_search_tool` (ย้ายไป adapter)
- `test_search_adapter.py` (NEW) — 13 tests for supports_server_tool
- `test_web_search_migration.py` — อัปเดตตรวจทั้ง 2 รูปแบบ (13 tests)
- `test_server_tool_compat.py` — ลบ (duplicate of test_search_adapter.py)

### Notes
- `_resolve_search_model` และ `_check_search_call_limit` ยังอยู่ใน search.py (อ่าน globals — P0.1 จะแก้)
- 4 จุดตัดสินใจเดิมยังไม่ลบ (ตาม spec "ทำทีละตัว, ทดสอบ, แล้วค่อยลบ") — P0.1 จะรวมเข้า adapter

## 2026-08-05 (session 6) — Fix search_model propagation (Python module-rebinding gotcha)

### Context
Manual test หลัง Task A commit เจอ bug: plan approval ตั้ง `search_model=perplexity/sonar-pro`
(เห็นใน `[DEBUG-MODELS]` log) แต่ `search_web` ใช้ `openrouter/free` จริง (เห็นใน
`[SearchTool] Searching` log) — user เลือก paid model แต่ระบบใช้ free

### Root cause (diagnosing-bugs skill, 6 phases)
Python module-rebinding gotcha: `from backend.globals import _search_model` ใน
`backend/tools/search.py` คัดลอก binding ตอน import ครั้งเดียว — การ reassign
`_search_model` ใน orchestrator (ผ่าน `global _search_model`) ไม่ส่งผลให้
`_resolve_search_model` ใน search.py เห็นค่าใหม่

### Fix
- `backend/tools/search.py`: เปลี่ยนจาก `from backend.globals import _search_model`
  เป็น `import backend.globals as _globals` แล้วอ่าน `_globals._search_model`
  แบบ dynamic ใน `_resolve_search_model`
- ลบ `global _search_model` ออกจาก `search_web` (ไม่ได้ assign แล้ว)

### Tests (TDD: red → green)
- `test_search_model_propagation.py` (new, 2 tests): จับ bug จริง — set
  `g._search_model` แล้วเรียก `_resolve_search_model` ต้องเห็นค่าใหม่
- `test_search_model_fallback.py`: แก้ 4 tests ที่ใช้ `monkeypatch` กับ
  `backend.tools.search._search_model` (เลิกใช้แล้ว) → เปลี่ยนเป็น patch
  `backend.globals._search_model` แทน

### Verification
- `pytest test_search_model_propagation.py`: 2 passed (red → green)
- `pytest test_web_search_migration.py test_search_model_fallback.py test_date_injection.py test_search_model_propagation.py`: 20 passed
- `pytest test_orchestrator.py test_agent_registry.py test_handler_wiring.py`: 35 passed
- รวม 55 tests ผ่านหมด ไม่มี regression

### Files Changed
- `backend/tools/search.py` — dynamic read ของ `_globals._search_model`
- `test_search_model_propagation.py` (new) — regression test สำหรับ bug นี้
- `test_search_model_fallback.py` — แก้ monkeypatch target ให้ตรงกับ dynamic read

### Post-mortem
สมมติฐานแรก (`global _search_model` หาย) ผิด — มีอยู่แล้ว สมมติฐานจริงคือ
Python gotcha: `from X import Y` คัดลอก binding ไม่ใช่ reference บทเรียน:
ถ้า module A reassign global ที่ module B import ไว้, B ต้องอ่านแบบ dynamic
(`import X; X.Y`) ไม่ใช่ `from X import Y`

---

## 2026-08-04 (session 5) — Migrate search from deprecated plugin to server tool (Task A: search parity)

### Context
OpenRouter deprecated `plugins: [{id: "web"}]` in favor of
`tools: [{type: "openrouter:web_search", parameters: {...}}]` (server tool).
Without migration, search breaks when OpenRouter removes plugin support.
Server tool also lets the model decide when to search (vs plugin forcing
search every call) — matches Claude/ChatGPT/Gemini behavior.

### Changes (TDD: red → green)

#### 1. `backend/globals.py` — search server-tool defaults (No Hardcode)
- Added `DEFAULT_SEARCH_ENGINE = "auto"` and `DEFAULT_SEARCH_MAX_RESULTS = 5`
- Defaults overridable per-agent via spec's `search_config` field

#### 2. `backend/tools/search.py` — server tool format
- Added `_build_web_search_tool(search_config)` — pure function, builds
  `{"type": "openrouter:web_search", "parameters": {...}}` from config +
  defaults. Testable without HTTP (matches `_resolve_search_model` pattern)
- Added `_get_search_config()` — reads `_thread_local.search_config`
  (set by orchestrator from agent spec), mirrors `max_search_calls` pattern
- `_call_openrouter_web_search` now sends `tools: [web_tool]` instead of
  `plugins: [{"id": "web", "max_results": 5}]`

#### 3. Agent spec wiring — `search_config` field through the pipeline
- `backend/core/orchestrator.py` — set `_thread_local.search_config` from spec
- `backend/agents/registry.py` — add/serialize `search_config` (3 places)
- `backend/handlers/actions.py` — add/serialize `search_config` (2 places)
- `backend/core/messenger.py` — serialize `search_config`
- `backend/core/secretary.py` — JSON templates (4) + parsing + description

#### 4. `test_web_search_migration.py` (new) — 8 tests, all passing
- `TestBuildWebSearchTool` (7): type, parameters key, default engine/max_results,
  custom config override, partial config, no plugins key
- `TestCallUsesServerTool` (1): request body uses `tools` not `plugins`

### Verification
- `pytest test_web_search_migration.py`: 8 passed
- `pytest` (6 test files): 50 passed (no regressions)

### Files Changed
- `backend/globals.py` — search server-tool defaults
- `backend/tools/search.py` — `_build_web_search_tool`, `_get_search_config`, server tool format
- `backend/core/orchestrator.py` — wire `search_config` to `_thread_local`
- `backend/agents/registry.py` — `search_config` in allow-lists + serialization
- `backend/handlers/actions.py` — `search_config` in allow-lists + serialization
- `backend/core/messenger.py` — `search_config` serialization
- `backend/core/secretary.py` — `search_config` in templates + parsing + description
- `test_web_search_migration.py` (new)

---

## 2026-08-04 (session 3) — Rule: Market Parity Baseline

### Context
หลังจากแก้ search_model bug พบปัญหาใหม่: agent ไม่รู้วันที่ปัจจุบัน เลยตัดข้อมูล box office ที่ถูกต้องออกเพราะคิดว่าเป็น "อนาคต" (เห็นวันที่ กรกฎาคม-สิงหาคม 2026 ในผลค้นหา แต่ไม่รู้ว่า "วันนี้" คือ 4 ส.ค. 2026)

User สังเกตเห็นปัญหาใหญ่กว่า: ถ้าตลาด (Claude/ChatGPT/Gemini) มี feature นี้อยู่แล้ว เราไม่ควรต้องมาเจอทีละอย่างผ่าน bug — เราควรสำรวจและทำให้ครบตั้งแต่ต้น

### Changes
- `~/.codeium/windsurf/memories/global_rules.md` — เพิ่มกฏ "Market Parity Baseline" (NON-NEGOTIABLE)
- `SYSTEM_PROTOCOL.md` — เพิ่ม section 14 "Market Parity Baseline" พร้อม checklist 10 features
- `CLAUDE.md` — เพิ่ม Market Parity Baseline เป็น key rule แรกใน Project protocol

### Parity Approach
- สำรวจตลาด: Claude, ChatGPT, Gemini, Devin, Cursor, Replit Agent, AI agent frameworks
- พบ 100+ features รวม real-world actions (email, calendar, shopping, booking)
- **บทเรียน**: manual checklist ไม่มีทางครบ — ทุกครั้งที่สำรวจเพิ่ม ก็เจอ feature ใหม่
- **วิธีที่ใช้**: Bug-driven parity — เจอ bug หรือ user อยาก feature → ค้นหาตลาด → ทำให้เหมือน
- กฏนี้บันทึกใน `global_rules.md` + `SYSTEM_PROTOCOL.md` section 14 + `CLAUDE.md`

### Next
- เริ่มทำ parity feature แรก: Current Date/Time injection
- ทำตามวิธี bug-driven: เจอ bug วันที่ → ค้นหาตลาด → ทำให้เหมือน

---

## 2026-08-04 (session 4) — Date injection in agent backstory (Task B: search parity)

### Context
Bug: Agent rejected valid box office data as "future information" because it
didn't know the current date. Market standard (Claude/ChatGPT/Gemini) injects
the current date into the system prompt automatically. CrewAI 1.15.1 has no
`inject_date` parameter on `Agent`, so the date must be injected into the
backstory (which becomes part of the system prompt).

### Changes (TDD: red → green)

#### 1. `backend/agents/factory.py` — inject current date in `_build_agent_backstory()`
- Added `from datetime import datetime` import
- At the top of `_build_agent_backstory()`, before base identity, append
  `Today's date: <weekday>, <month> <day>, <year>` to the parts list
- Every agent now knows what "today" is, fixing the false "future data" rejection

#### 2. `test_date_injection.py` (new) — 3 tests, all passing
- `test_backstory_contains_current_date` — backstory contains current year
- `test_backstory_contains_today_keyword` — backstory has explicit "Today's date" label
- `test_date_appears_in_full_backstory_with_other_fields` — date injection works alongside other persona fields

### Verification
- `pytest test_date_injection.py`: 3 passed
- `pytest test_date_injection.py test_orchestrator.py test_agent_registry.py`: 29 passed (no regressions)

### Files Changed
- `backend/agents/factory.py` — date injection in `_build_agent_backstory()`
- `test_date_injection.py` (new)

---

## 2026-08-04 (session 2) — Bugfix: search_web used openrouter/free (slow 48-65s) instead of user-selected model

### Context
User reported 15-minute task runtime. Diagnosed via `diagnosing-bugs` skill (all 6 phases).
- Phase 1 (feedback loop): `test_synth_timing.py` measured Manager synthesis = 5-35s (NOT the bottleneck)
- Phase 2 (reproduce): `test_search_timing.py` measured search_web = 47.9s avg × 16 calls = 12.8 min ← matches "15 min"
- Phase 3 (hypothesize): H1 = openrouter/free slow. Verified via `test_search_models.py`: free=64.8s, perplexity/sonar=14.9s, gpt-4o-mini=11.3s
- Phase 4 (instrument): confirmed `search_web` reads `_search_model` (session key `ai_search_model`), NOT `selected_model` (top bar). When `ai_search_model` empty → falls back to `_default_model` = "openrouter/free" (hardcoded in manager.py:44)
- Root cause: Secretary prompt marked `search_model` as "deprecated — web search is now built-in", so Secretary never set it. ChatWindow.tsx (retro UI) didn't display/validate search model (unlike image_model). Violates SYSTEM_PROTOCOL.md line 22: "ใช้ paid LLM (ไม่ใช่ free tier)"

### Changes (TDD: red → green → review)

#### Backend
- `backend/tools/search.py`:
  - Extracted `_resolve_search_model(selected_model, default_model)` — testable resolution logic
  - Resolution order: ai_search_model → selected_model → default_model → "openrouter/free" (last resort only)
  - `search_web` now reads `cl.user_session.get("selected_model")` and passes to `_resolve_search_model`
- `backend/core/secretary.py`:
  - Extracted `_build_plan_schema_section()` and `_build_design_rules_section()` as module-level functions (testable)
  - Changed `search_model` prompt from "deprecated" → "REQUIRED if plan uses search_web" (matches image_model pattern)
  - Added `search_web→search_model` mapping in design rules (was missing)
  - Applied to both `assess_and_plan` and `assess_and_plan_multimodal` prompts

#### Frontend
- `frontend/src/components/retro/ChatWindow.tsx`:
  - Added `{hasSearchTool && renderMediaModel('Search', 'searchModel', ...)}` in plan-models section
  - Added `if (hasSearchTool && !msg.searchModel) missingModels.push('Search')` in validation (blocks approve if missing)

#### Tests
- `test_search_model_fallback.py` (new, 7 tests):
  - `TestSearchModelFallback` (4): ai_search_model priority, fallback to selected_model, no free when selected set, default fallback
  - `TestSecretaryPromptSearchModel` (3): no "deprecated", says "REQUIRED", maps search_web→search_model
- All 18 tests pass (7 new + 6 search_limit + 5 media_retry)
- `tsc --noEmit` clean

### Verification
- `pytest test_search_model_fallback.py test_search_limit.py test_media_retry_auto_approve.py` → 18 passed
- `tsc --noEmit` → clean
- Pending: live retest with same Arsenal prompt to confirm search uses paid model + runtime drops from ~15min to ~2min

### Notes
- Did NOT change `_default_model` in manager.py (out of scope — that's the last-resort fallback)
- Did NOT remove `openrouter/free` fallback entirely (kept as last resort when nothing else available)
- Diagnostic scripts (`test_synth_timing.py`, `test_search_timing.py`, `test_search_models.py`) kept for future debugging

---

## 2026-08-04 — Bugfix: Media Reject Workflow + Search 502 + Stop Status + Progress Regression

### Context
Session ต่อจากการ implement enhanced media reject workflow (inline feedback for regeneration).
Manual testing เจอ bugs เพิ่มเติม ใช้ `diagnosing-bugs` skill ในการวิเคราะห์และแก้ไข

### Changes

#### Bug 1: กด Stop แล้ว agent status ยังเป็น "waiting"/"Done"
- **Root cause:** `handleStop` ใน `App.tsx` ลบเฉพาะ `progress` messages แต่ไม่อัปเดต `agent_progress` status
- **Root cause (backend):** `chat.py` ตั้ง `status: "complete"` เสมอ ไม่เช็ค `was_cancelled`
- **Fix:**
  - `frontend/src/App.tsx` — `handleStop` เพิ่ม logic อัปเดต agent_progress ที่มี status `running`/`pending`/`waiting_approval`/`awaiting_review` → `error` + `reviewSummary: "หยุดโดยผู้ใช้"`
  - `backend/handlers/chat.py` — เช็ค `was_cancelled` ก่อนตั้ง agent/Manager status ถ้า cancelled → `status: "error"` + `review_summary: "หยุดโดยผู้ใช้"`

#### Bug 2: search_web คืน Error 502 "Invalid URL" จาก provider "Stealth"
- **Root cause:** `search_web` ใช้ CrewAI LLM.call() ซึ่งไม่ forward `extra_body`/`additional_params` ไปยัง HTTP request จริง — `openrouter/free` บางครั้ง route ไป Stealth provider ที่ไม่รองรับ web search จริง
- **Fix:** `backend/tools/search.py` — เปลี่ยนจาก CrewAI LLM เป็น `requests.post()` ตรงไป OpenRouter API พร้อม `plugins: [{"id": "web", "max_results": 5}]` (verified สำเร็จ 200 พร้อม sources)

#### Bug 3: Task status แสดง "Done"/"เสร็จสิ้น" แทน "ยกเลิก" หลัง stop
- **Root cause:** Frontend หลายจุดไม่เช็ค `wasStopped` จาก `review_summary`
- **Fix:**
  - `frontend/src/components/retro/TasksWindow.tsx` — `statusInfo` เพิ่ม case `stop` → "⏹ ยกเลิก"
  - `frontend/src/components/retro/TasksWindow.tsx` — FlowNode + ResultPanel เช็ค `wasStopped` จาก `reviewSummary`/`review_summary` ที่มี "หยุดโดย" → override `complete` → `stopped`
  - `frontend/src/components/retro/TasksWindow.tsx` — run status + TaskListItem เช็ค `runWasStopped`
  - `frontend/src/components/retro/tasksToPlans.ts` — เปลี่ยน `stopped` → `'stopped'` แทน `'done'` + statusText "ยกเลิก"
  - `frontend/retro-mockup.css` — เพิ่ม `.tw-ti-badge.stopped`, `.tw-flow-badge.stopped`, `.tw-node.stopped`, `.tw-node-status.stopped` (สี amber)

#### Bug 4: Spinner หมุนรอบ FlowNode รบกวนสายตา
- **Root cause:** `.tw-node.running::after` สร้างเส้นหมุนรอบกรอบ node
- **Fix:** `frontend/retro-mockup.css` — ลบ `.tw-node.running::after` rule ออก

#### Bug 5: Progress ลดลง (70 → 50) เมื่อ agent เรียก tool หลายครั้ง
- **Root cause:** `on_tool_started` ตั้ง progress 50, `on_tool_finished` ตั้ง 70 — ถ้าเรียก tool อีกครั้ง progress กลับไป 50
- **Fix:** `backend/core/orchestrator.py` — `_merge_and_send` เพิ่ม high-water mark: ถ้า status เป็น `running` และ progress ใหม่ < progress ปัจจุบัน → ไม่อัปเดต progress

### Verification
- pytest: 313 passed, 8 deselected
- tsc --noEmit: สะอาด
- Manual test: search_web สำเร็จ (BBC Sport, Sky Sports sources), stop แสดง "ยกเลิก", ไม่มี spinner

### Files Changed
- `backend/handlers/chat.py` — was_cancelled check สำหรับ agent/Manager status
- `backend/tools/search.py` — ใช้ requests.post + web plugin แทน CrewAI LLM
- `backend/core/orchestrator.py` — high-water mark สำหรับ progress
- `frontend/src/App.tsx` — handleStop อัปเดต agent_progress status
- `frontend/src/components/retro/TasksWindow.tsx` — wasStopped check ทุกจุด
- `frontend/src/components/retro/tasksToPlans.ts` — stopped → 'stopped' แทน 'done'
- `frontend/retro-mockup.css` — เพิ่ม .stopped classes, ลบ spinner

## 2026-08-04 — UX: Manager Synthesis Progress + search_web Hard Limit (config-driven)

### Context
Manual testing เจอว่า Manager synthesis ใช้เวลา 60+ วินาทีโดยไม่มี progress feedback ทำให้ user รู้สึกว่า "นานเกินไป" ใช้ `diagnosing-bugs` skill วิเคราะห์ พบว่า agent เรียก search_web 16 ครั้ง (over-searching) เพราะไม่มี per-tool limit ทำให้ context มหาศาล และ Manager synthesis LLM call ช้า

### Changes

#### 1. บันทึกกฏ "No Hardcode" ใน global_rules.md
- `~/.codeium/windsurf/memories/global_rules.md` — เพิ่มกฏ: ค่าที่อาจเปลี่ยนแปลงต้องเป็น config ไม่ใช่ค่าคงที่ในโค้ด

#### 2. เพิ่ม `max_search_calls` ใน agent spec (config-driven, ไม่ใช่ hardcode)
- **Pattern:** อิงตาม `max_iter`, `max_retry_limit` ที่มีอยู่แล้ว + `_thread_local` สำหรับ parallel-safe per-agent state
- `backend/tools/search.py` — อ่าน `_thread_local.max_search_calls` และ `_thread_local.search_call_count` ถ้า count >= max → return limit message
- `backend/core/orchestrator.py` — set `_thread_local.search_call_count = 0` และ `_thread_local.max_search_calls = spec.get("max_search_calls")` ตอน agent เริ่ม (บรรทัด 473)
- `backend/agents/registry.py` — เพิ่ม `max_search_calls` ใน allowed fields (3 จุด)
- `backend/handlers/actions.py` — เพิ่ม `max_search_calls` ใน allowed fields (3 จุด)
- `backend/core/messenger.py` — เพิ่ม `max_search_calls` ใน agent spec serialization
- `backend/core/secretary.py` — เพิ่มใน prompt description + template JSON (3 templates) + parsing logic

#### 3. Progress 85% ระหว่าง Manager synthesis
- `backend/core/orchestrator.py` — extract `_send_manager_progress()` method (reusable สำหรับ 50% และ 85%) ส่ง progress 85% + "Manager กำลังสรุปผลและตรวจสอบคุณภาพ..." ก่อน LLM call

#### 4. Frontend แสดง Manager progress ใน banner
- `frontend/src/components/retro/TasksWindow.tsx` — synthesizing banner แสดง `current_task` + progress percentage ของ Manager

### Verification
- pytest: 10 passed (test_search_limit.py 5 + test_media_retry_auto_approve.py 5)
- tsc --noEmit: สะอาด
- All imports OK (no syntax errors)

### Files Changed
- `~/.codeium/windsurf/memories/global_rules.md` — กฏ "No Hardcode"
- `backend/tools/search.py` — per-agent search call limit via _thread_local
- `backend/core/orchestrator.py` — set thread_local + _send_manager_progress() + progress 85%
- `backend/agents/registry.py` — max_search_calls in allowed fields + serialization
- `backend/handlers/actions.py` — max_search_calls in allowed fields + int parsing + serialization
- `backend/core/messenger.py` — max_search_calls in agent spec serialization
- `backend/core/secretary.py` — max_search_calls in prompt + templates + parsing
- `frontend/src/components/retro/TasksWindow.tsx` — Manager progress in synthesizing banner
- `test_search_limit.py` — new test file (5 tests)
