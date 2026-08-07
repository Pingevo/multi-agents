# Developer Log

## 2026-08-06 (session 17) — Implement #136 BrandRegistry (TDD)

### Context
M6 Phase 1 เริ่มที่ #136 (BrandRegistry + Brand entity) — รากของ dependency chain
(#136 → #137 → #33 → #138). ทำตาม mattpocock skill: codebase-design ออกแบบ interface
→ tdd เขียน failing test → implement → code-review.

### Design (codebase-design skill)
Module: BrandRegistry — JSON-backed brand registry (CRUD), mirror pattern ของ TeamRegistry
ที่มีอยู่ (เดียวกับ _load/_save, uuid[:8], isoformat timestamps, sorted reverse).

Interface (เล็ก/ลึก — 5 methods):
- __init__(filepath, user_id) — per-user isolation ผ่าน resolve_data_path
- create_brand(name, brand_context=None) -> dict
- get_brand(brand_id) -> dict | None
- update_brand(brand_id, fields) -> bool
- delete_brand(brand_id) -> bool
- list_brands() -> list[dict]

brand_context structure (จาก ADR-0005 + CONTEXT.md):
{tone, target_audience, guidelines, forbidden_words}

Design note: ADR บอก "ลบ Brand → ต้องจัดการทีมข้างใต้ก่อน" แต่ guard นั้น couple กับ
TeamRegistry → เก็บไว้ที่ service/UI layer ใน #138 ไม่ใส่ใน BrandRegistry
(deep + single-responsibility + Simplicity First).

Seam under test: public methods ของ BrandRegistry, ผ่าน tempfile JSON
(เหมือน test_team_filtering.py).

### TDD loop
1. Red: เขียน test_brand_registry.py (16 tests, 6 classes) → ModuleNotFoundError
2. Green: เพิ่ม BRAND_REGISTRY_FILE ใน globals.py + legacy_map → สร้าง
   backend/agents/brand_registry.py (89 บรรทัด) → 16/16 passed
3. Regression: test_team_filtering.py + test_agent_registry.py = 28 passed (ไม่พัง)

### Changes
- backend/globals.py — เพิ่ม BRAND_REGISTRY_FILE + legacy_map entry (2 บรรทัด)
- backend/agents/brand_registry.py (new) — BrandRegistry class + DEFAULT_BRAND_CONTEXT
- test_brand_registry.py (new) — 16 tests ครอบ CRUD + per-user isolation

### Verification
- pytest test_brand_registry.py -v → 16 passed
- pytest test_team_filtering.py test_agent_registry.py -q → 28 passed
- import smoke test ผ่าน

### Files Changed
- backend/globals.py (M)
- backend/agents/brand_registry.py (new)
- test_brand_registry.py (new)

### Next
- #137: TeamRegistry เพิ่ม brand_id (required field) — พึ่ง #136 ที่เสร็จแล้ว
- #33: ย้าย brand_context จาก agent → Brand (resolve ผ่าน team → brand)
- #138: BrandWindow UI + TeamCreateModal เลือก Brand

## 2026-08-05 (session 16) — Architecture: Add Brand entity (User → Brand → Team → Agent)

### Context
User ดูแลหลายแบรนด์ แต่ hierarchy ปัจจุบันคือ User → Team → Agent (ไม่มี Brand)
ทีมกระจัดกระจาย ไม่มีที่รวม และ `brand_context` เก็บใน agent แต่ละตัวทำให้ drift
OST Opportunity 2 บอก "แบ่งทีมตามแบรนด์ → (มีแล้ว: ระบบทีม)" — ผิด เพราะยังไม่มี Brand entity

### Decision (domain-modeling skill)
เพิ่ม Brand entity ระหว่าง User และ Team → User → Brand → Team → Agent
`brand_context` ย้ายจาก agent → Brand (single source of truth)
ทีมในแบรนด์เดียวกันใช้ brand_context ร่วมกัน → ไม่ drift
MongoDB product data ยังเป็น shared factual data ไม่ filter ตามแบรนด์

ผ่านเกณฑ์ ADR 3 ข้อ: hard to reverse, surprising without context, real trade-off
→ สร้าง ADR-0005

### Changes (docs only — no code yet, awaiting approval per "User is Manager" rule)

#### 1. `OST.md` — แก้ Opportunity 2, 7, 8 + ตารางสรุป
- Opportunity 2: "แบ่งทีมตามแบรนด์ → (มีแล้ว)" → "ต้องมี: Brand entity"
- Opportunity 7: brand_context เก็บ per Brand ไม่ใช่ per team
- Opportunity 8: ย้ายจาก "ทีมรู้แบรนด์" → "แบรนด์รู้ตัวเอง"
- ตารางสรุป: เพิ่ม Brand entity เป็น "ต้องมี" ใหม่

#### 2. `docs/adr/0005-brand-entity.md` (new)
- บันทึกการตัดสินใจ + Considered Options (3 ทางเลือก) + Consequences
- Reject: 2-layer + tag, Reject: move to Team (#33/#109 original), Choose: Brand entity

#### 3. `CONTEXT.md` — domain glossary
- เพิ่ม term: Brand, BrandRegistry
- แก้ term: Team (เพิ่ม brand_id), TeamRegistry (เพิ่ม brand_id)
- แก้ term: Agent (brand_context = derived ไม่ใช่ stored)
- แก้ term: AgentRegistry, AgentFactory (brand_context ดึงจาก Brand ผ่าน team)

#### 4. `SYSTEM_PROTOCOL.md`
- Section 0 (vision): Platform → Brand → Team → Agent (แก้จาก Team → Brand)
- Section 1 (architecture): เพิ่ม BrandRegistry ใน backend modules
- Section 2 (UI): เพิ่ม BrandWindow ใน windows list
- Section 3.5 (Agent Persona): brand_context = derived (ไม่ใช่ attribute ของ agent)
- Section 4: เพิ่ม "Brand System" + แก้ Team System ให้สังกัด Brand
- Section 13: เพิ่ม `brand_registry.json` ใน per-user data list

#### 5. GitHub Issues (M6: Company Knowledge Base)
- #33 (existing): แก้ title + body + labels → ย้าย brand_context จาก agent ไป Brand entity
- #109 (existing): ปิด — superseded by ADR-0005 (duplicate of #33)
- #136 (new): BrandRegistry + Brand entity (backend)
- #137 (new): TeamRegistry เพิ่ม brand_id
- #138 (new): BrandWindow UI + TeamCreateModal เลือก Brand

#### 6. Project Board (Multi-Agents Board)
- Add #33, #136, #137, #138 เข้า board
- ตั้ง Theme = Opp8: Brand (ทั้ง 4)
- ตั้ง Priority: #33, #136, #137 = P1, #138 = P2
- ตั้ง Status = Todo (ทั้ง 4)

### Verification
- ไม่มี code change → ไม่ต้อง run tests
- ตรวจสอบ: ไฟล์ docs ทั้งหมดสอดคล้องกัน (OST ↔ ADR ↔ CONTEXT ↔ SYSTEM_PROTOCOL)
- ตรวจสอบ: issues ทั้ง 4 อยู่ใน M6 milestone + มี Theme field

### Files Changed
- `OST.md` — แก้ Opportunity 2, 7, 8 + ตารางสรุป
- `docs/adr/0005-brand-entity.md` (new)
- `CONTEXT.md` — เพิ่ม/แก้ term Brand, BrandRegistry, Team, TeamRegistry, Agent, AgentRegistry, AgentFactory
- `SYSTEM_PROTOCOL.md` — แก้ Section 0, 1, 2, 3.5, 4, 13
- GitHub: #33 (updated), #109 (closed), #136, #137, #138 (new)
- Project Board: added 4 items with Theme + Priority + Status

### Post-mortem
- ตอนแรกวางจะสร้าง worktree แยก — user ทักทายว่าไม่จำเป็น เพราะไม่มีงานควบ → แก้เป็น branch ธรรมดา
- MCP server ล่มระหว่างดึง issue → ใช้ REST API ผ่าน Python แทน ได้ผลเหมือนกัน
- #33 มีใน board view ก่อนหน้า แต่ GraphQL บอก 0 project items → น่าจะเป็น draft item ที่ไม่ได้ link issue
  (add ใหม่จึงไม่ซ้ำ)

### Next (awaiting user approval)
- Implement #136: BrandRegistry (TDD: red test → green impl)
- Implement #137: TeamRegistry brand_id
- Implement #33: ย้าย brand_context จาก agent → Brand
- Implement #138: BrandWindow UI + TeamCreateModal

ลำดับทั้งหมดอยู่ใน GitHub Issues (Depends on / Blocks ใน issue body) + Project Board
ไม่สร้างไฟล์ plan แยก — milestone + issue + board เพียงพอ

### #34 วินิจฉัย + ย้าย
#34 = `UserPreferenceStore` เก็บ preference ข้าม team/agent ของ user คนเดียว
→ ไม่ใช่เรื่องแบรนด์ (Theme เดิม = Opp8: Brand ผิด)
→ ย้าย Theme → Opp4: Memory
→ ย้าย Milestone → M11 (Continuous Learning & Memory)

### #106, #107, #108 แก้ body + Priority
- body เดิมบอก "Milestone: M7" แต่อยู่ใน M6 → แก้เป็น M6
- Priority เดิม P3 รอง → ไม่สอดคล้องกับ due 25 ก.ย.
- #106 (Knowledge Store architecture) → P1 (foundation)
- #108 (query_knowledge_base tool) → P2 (หลัง #106)
- #107 (Knowledge Management UI) → P2 (หลัง #106)
- เพิ่ม Depends on / Blocks ใน body ให้ชัด

### ลบ m6-plan.md
- สร้าง `docs/m6-plan.md` ไปก่อนหน้า → over-engineer (duplicate กับ milestone + board)
- ลบทิ้ง + คืน `project-board.md` เดิม
- ลำดับงานอยู่ใน GitHub Issues (Depends on/Blocks ใน body) + Board (Priority field) พอ

---

## 2026-08-05 (session 15) — Fix: Manager review prompt missing date injection (Task B bug follow-up)

### Context
Bug discovered via @conversation: Task C — Manager reviewer rejected valid
2026 data as "future/hallucination" even though the agent confirmed the date
via browse_web. Root cause: Task B (commit 41756f6) injected "Today's date"
into agent backstory (factory.py) but NOT into the Manager review prompt.
Manager reviewer is a direct LLM call (manager_llm.call(review_prompt)) that
bypasses AgentFactory, so it never received the date.

### Diagnosis (diagnosing-bugs skill, 6 phases)
- Phase 1 (feedback loop): wrote `test_manager_review_date.py` — failing test
  asserting `_build_manager_review_prompt()` contains "Today's date"
- Phase 2 (reproduce): confirmed red — function didn't exist (prompt was
  built inline in `_batch_manager_review` closure, no testable seam)
- Phase 3 (hypothesise): H1 = Manager prompt missing date injection (verified
  by reading orchestrator.py lines 826-870 — no date anywhere)
- Phase 4 (instrument): not needed — root cause clear from code inspection
- Phase 5 (fix + regression): extracted `_build_manager_review_prompt` to
  module level (created testable seam) + injected date at top of prompt
- Phase 6 (cleanup): no debug instrumentation; regression test in place

### Changes (TDD: red → green)

#### 1. `backend/core/orchestrator.py` — extract + date injection
- Added `from datetime import datetime` import
- Extracted `_build_manager_review_prompt(...)` as module-level function
  (was inline closure in `_batch_manager_review`, untestable)
- Injected `Today's date: <weekday>, <month> <day>, <year>` at top of prompt
  (after persona, before agent outputs) — parity with agent backstory format
- `_batch_manager_review` now calls `_build_manager_review_prompt(...)` —
  same behavior, but testable

#### 2. `test_manager_review_date.py` (new) — 4 tests, all passing
- `test_prompt_contains_today_date_label` — prompt has "Today's date" label
- `test_prompt_contains_current_year` — prompt has current year
- `test_date_appears_before_agent_outputs` — date comes before outputs
- `test_date_present_with_multiple_agents` — works with multiple agents

### Verification
- `pytest test_manager_review_date.py`: 4 passed
- `pytest` (7 test files): 59 passed (no regressions)

### Files Changed
- `backend/core/orchestrator.py` — extract `_build_manager_review_prompt`, date injection
- `test_manager_review_date.py` (new)

### Post-mortem
What would have prevented this bug: Task B injected date into agent
backstory but the Manager reviewer uses a separate LLM call path that
bypasses AgentFactory. The fix closes that gap. Architectural note: any
future LLM call path that judges "current vs future" data must receive
the date — consider centralizing date injection if more call paths appear.

---

## 2026-08-05 (session 14) — Fix perplexity 404 regression + restore resolve_search_model

### What
Commit `de04b54` (AI Usage Hub integration) accidentally regressed two fixes
from commit `7ce1ce0`:
1. `supports_server_tool` reverted from checking `"web_search_options"` back to
   `"web_search"` — all Perplexity models returned True (wrong), got `tools`
   instead of `web_search_options`, and 404'd on every search call
2. `SearchAdapter.resolve_search_model()` method was deleted — `search.py`
   fell back to reading `_globals._search_model` directly (P0.1 regression)

### Why (root cause — diagnosing-bugs Phase 3 hypothesis #1 confirmed)
The AI Usage Hub commit rewrote `search_adapter.py` to add `log_ai_usage` calls
and in the process dropped the `resolve_search_model` method and reverted the
`web_search_options` parameter check. Tests did not catch the regression
because `test_search_adapter.py` and `test_web_search_migration.py` used
`"web_search"` in their fake catalogs — matching the (wrong) adapter code
rather than the real OpenRouter catalog which uses `"web_search_options"`.

### TDD slices (red → green)
1. RED: Updated fake catalogs in `test_search_adapter.py` and
   `test_web_search_migration.py` to use `"web_search_options"` (mirroring
   real OpenRouter metadata) → 5 + 3 tests fail
2. GREEN: Restored `"web_search_options"` check in `supports_server_tool` →
   all 13 adapter tests pass
3. GREEN: Restored `resolve_search_model()` method on SearchAdapter + restored
   `search.py` delegation → 42 search-related tests pass
4. Restored missing test files: `test_adapter_resolve_model.py`,
   `test_search_uses_adapter.py` (deleted by `de04b54`)

### Verification
- Full suite: 399 passed, 8 deselected, 0 regressions
- Manual test (browser): "ค้นหาข่าวล่าสุดเกี่ยวกับ youtuber Jedz"
  - search_model = perplexity/sonar-pro-search (top-level, button filled)
  - search executed with perplexity — NO 404
  - browse_web validated + executed (read GamingDose + Pantip pages)
  - agent synthesized answer from full page content

### What would have prevented this bug
Test data in `test_search_adapter.py` / `test_web_search_migration.py` should
have mirrored the real OpenRouter catalog (`web_search_options`) from the
start. Using the old parameter name (`web_search`) in fake catalogs made the
tests tautological — they passed against the wrong code. With correct test
data, commit `de04b54` would have failed CI immediately.

### Files
- `backend/tools/search_adapter.py` — restored `resolve_search_model`, fixed
  `supports_server_tool` to check `web_search_options`
- `backend/tools/search.py` — `_resolve_search_model` delegates to adapter again
- `test_search_adapter.py` — fake catalog uses `web_search_options`
- `test_web_search_migration.py` — fake catalog uses `web_search_options`
- `test_adapter_resolve_model.py` — restored (was deleted by de04b54)
- `test_search_uses_adapter.py` — restored (was deleted by de04b54)

## 2026-08-05 (session 13) — Task C: Secretary prompt instructs agents to read full pages

### What
Added `_build_search_behavior_section()` to `backend/core/secretary.py` — a new
extracted prompt section that tells the Secretary to instruct any agent with
`search_web` to call `browse_web` on source URLs (falling back to `scrape_web`)
to read the full page BEFORE writing its final answer. Wired into both the plan
prompt and the retry prompt at the existing `_build_design_rules_section()` call
sites.

### Why (Market Parity — Task C / HANDOFF search-parity)
Market leaders (Claude, ChatGPT, Gemini) read the actual page content before
synthesizing answers. Our `search_web` returns only the search-engine summary
with source URLs — agents never opened the full page, so synthesized answers
were shallower than the market. `browse_web` (Playwright) and `scrape_web`
(urllib) already exist in `tool_registry.py` but the Secretary prompt never
told agents to use them after search.

### TDD slices
1. RED: `test_secretary_read_full_pages.py` — 5 tests for the new section
   (exists, mentions browse_web, mentions scrape_web fallback, links to
   search_web, says "before synthesizing"). ImportError on first run.
2. GREEN: Added `_build_search_behavior_section()` + wired into 2 prompt
   sites. 5/5 pass.
3. No refactor needed — followed existing extracted-helper pattern.

### Verification
- New test: 5/5 pass
- Full suite: 392 passed, 8 deselected, 0 regressions
- code-review: 1 hard violation (this DEVELOPER_LOG entry — now fixed),
  2 judgement calls suppressed (duplicated wiring = repo convention;
  multi-assertion test = single function under test, not horizontal slicing)

### Files
- `backend/core/secretary.py` — new `_build_search_behavior_section()` + 2 wiring lines
- `test_secretary_read_full_pages.py` — new test file (5 tests)

### Spec
- HANDOFF.md Task C: "เพิ่มใน secretary prompt: ถ้า search_web ส่ง URL กลับมา
  ให้ agent เรียก browse_web อ่านหน้าจริงก่อน synthesize"

## 2026-08-05 (session 12) — Integrate AI Usage Hub (replace local JSONL logging)

### What
Replace local-only `llm-call-log.jsonl` logging with HTTP push to central AI
Usage Hub at `https://digital.in.th` (per `AI_USAGE_HUB_DEVELOPER_API.md` from
sellcenter team). Old `credit_logger.log_llm_call` will be removed; all 19
OpenRouter call sites will switch to new `log_ai_usage()`.

### Why
- Market Parity Baseline: every AI app in the market has a cost dashboard
- Old logger wrote to local file only — nobody looked at it
- Hub gives cross-project dashboard, filter by user/reference/date
- Hub doc mandates error-path logging (old logger only logged success)
- Token `svc_42` issued by sellcenter for this project

### TDD slices (vertical, one test → one implementation per cycle)
1. ✅ RED→GREEN: `test_ai_usage_hub.py` (12 tests) — `log_ai_usage()` module
   with fire-and-forget HTTP, env-var guard, contextvar defaults, never-throws
2. ✅ RED→GREEN: `test_llm_manager_logging.py` (3 tests) — LLMManager success
   + error path pushes to `log_ai_usage` with correct fields
3. ✅ RED→GREEN: `test_rotator_logging.py` (3 tests) — FreeModelRotator
   success + error + streaming, with `attempt` field
4. ✅ RED→GREEN: `test_media_logging.py` (4 tests) — image, TTS, vision
   (previously unlogged: TTS, STT, vision)
5. ✅ RED→GREEN: `test_search_adapter_logging.py` (2 tests) — search
   success + error (previously unlogged entirely)
6. ✅ GREEN: orchestrator litellm + crewai event bus callbacks switched
   to `log_ai_usage` (safety net for future call sites)
7. ✅ GREEN: chat.py sets `ai_user_ctx` + `ai_reference_ctx` at 3 entry
   points (multi-agent, single-agent, main chat) so all logs auto-include
   user_id and session_id
8. ✅ GREEN: deleted `backend/credit_logger.py`, removed
   `llm-call-log.jsonl` from `.gitignore`, removed unused import in
   `backend/llm/selector.py`
9. ✅ GREEN: full test run (394/394 pass) + code-review skill (2 sub-agents:
   Standards + Spec). Fixed 4 spec findings:
   - Added `log_failure_event` to LiteLLM callback (error path was missing)
   - TTS/STT now send `cost_usd` from `X-OR-Cost-USD` header or JSON body
   - Local fallback (Ollama) calls now logged with `provider=fallback_provider`
   - Removed silent `provider="openrouter"` default → now "unknown" so
     missing-provider bugs surface in dashboard (spec says mandatory)

### Post-review: re-read spec file, found 3 more gaps (session 12b)
After reading the actual `AI_USAGE_HUB_DEVELOPER_API.md` (not just the
reconstructed summary), found 3 fields the spec asks for that were missing:
- `request_id` (spec §2) — provider generation id, used as idempotency key.
  Added `response.id` / `data.id` / `chunk.id` to all success paths that
  have a response object.
- `units` (spec §2) — non-token usage like images/videos/audio. Added
  `{"images_processed": 1}`, `{"videos_generated": 1}`,
  `{"audio_generated": 1}`, `{"audio_transcribed": 1}` to media paths.
- `metadata.analysis_type` (spec §4) — tag for filtering by job type in
  dashboard. Added `"chat"`, `"media"`, `"search"`, `"agent"` to all 19
  success paths. Verified 19/19 success paths now carry metadata.

### Second re-review: closed 2 more gaps (session 12c)
Spec re-review sub-agent found 2 more issues:
- `request_id` missing in 5 paths (image, TTS, STT, vision, CrewAI
  callback) that use raw HTTP instead of OpenAI SDK. Added `data.get("id")`,
  `resp.headers.get("X-OR-Generation-ID")`, `result.get("id")`,
  `getattr(event, "id", None)` respectively.
- `metadata.analysis_type` missing in all 18 error paths. Spec §4 says
  dashboard filtering needs both success + error. Added metadata to all
  18 error paths. Verified 37/37 log_ai_usage calls now carry metadata.

### Third check: full field coverage audit (session 12d)
Ran a script to audit every spec field across all 37 log_ai_usage calls.
Found 1 real gap: CrewAI event bus callback (orchestrator.py:149) was
missing `duration_ms` because CrewAI events don't expose start/end time.
Added `"duration_ms": None` explicitly so the field is present (Hub treats
None as "unknown"). All other "missing" fields were false positives:
- `user`/`reference` come from contextvars, not call site dict
- `request_id`/`prompt_tokens`/`completion_tokens`/`cost_usd`/`raw_usage`
  only present in success paths (error paths have no response object)
- `error_message` only present in error paths (18 error = 18 error_message)
- `units` only for non-token ops (image/video/TTS/STT), chat has tokens

### Fourth check: leftover + edge cases (session 12e)
Final sweep for anything dropped:
- Deleted leftover `llm-call-log.jsonl` (41KB) still on disk from old logger
- Video polling failure + timeout had no log. Added `status="error"` for
  polling failure and `status="timeout"` for 5-min timeout (spec §2 lists
  `timeout` as valid status). Now 39 log_ai_usage calls total.

### Fifth check: code-review skill final audit (session 12f)
Per mattpocock-skills rule "Delivering work / after code changes → code-review
YES", ran final completeness audit sub-agent. All 5 categories passed:
- Call site coverage: all sites have log in success + error paths
- Spec field coverage: all fields present where appropriate
- Cleanup: credit_logger deleted, no log_llm_call remnants
- Config: .env.example has all 3 env vars
- Edge cases: video polling, local fallback, streaming, LiteLLM, CrewAI all covered
Fixed indentation inconsistency in rotator.py error paths (4 metadata lines
+ 4 closing braces had 16/12 spaces instead of 20/16 to match siblings).
Style only — Python accepted both, tests passed either way.

### Sixth check: skeptical re-audit (session 12g)
User said "ไม่เชื่อ ลองอีกรอบ" — ran another completeness audit. Found 2 more
indentation bugs in llm/manager.py that the previous audit missed:
- Line 363: streaming error path metadata had indent=20, siblings indent=24
- Line 576: call_with_fallback error path metadata had indent=20, siblings=24
Both fixed. All 6 categories now PASS. 394/394 tests still pass.

### Verification (all slices)
- 394/394 tests pass (8 deselected — pre-existing, unrelated)
- Confirmed `usage.cost` reachable via OpenAI SDK (Pydantic `extra='allow'`)
- Confirmed 19 OpenRouter call sites via grep (12 logged success-only,
  7 unlogged: TTS, STT, vision, search)
- All 19 sites now push to Hub with success + error paths
- Local fallback (Ollama) calls also logged
- LiteLLM callback covers both success + failure (safety net for future
  call sites and CrewAI internals)
- contextvars auto-populate `user` (user_id) and `reference` (session_id)
- code-review: 0 hard Standards violations; 4 Spec findings fixed

### Files
- `backend/ai_usage_hub.py` — new module, single function `log_ai_usage(entry)`
- `test_ai_usage_hub.py` — new test (12 cases)
- `test_llm_manager_logging.py` — new test (3 cases, currently RED)

---

## 2026-08-05 (session 11) — Fix FreeModelRotator stale slugs (issue #125)

### What
Replaced hardcoded `_FREE_MODEL_RANKING` (8 stale slugs that all 404) with
dynamic catalog fetch — `get_ranking()` now filters OpenRouter catalog for
models with `:free` suffix that currently exist, sorted by context_length
descending (smartest first).

### Why (No Hardcode rule + issue #125)
OpenRouter retired free tier for `deepseek-r1:free`, `llama-3.3-70b:free`,
`qwen3-coder:free`, `gpt-oss-120b:free`, etc. — all 4 rotator attempts 404'd,
leaving the user with "⚠️ โมเดล 'openrouter/free' ไม่สามารถสร้างแผนงานได้".
Hardcoding slugs that drift over time violates No Hardcode.

### TDD slices
1. RED: `test_rotator_dynamic_ranking.py` — 5 tests for dynamic ranking (catalog injection, excludes paid/stale, sorts by context_length, empty when catalog empty)
2. GREEN: Added `catalog` parameter to `FreeModelRotator.__init__`, `_fetch_catalog_models()`, rewrote `get_ranking()` to filter + sort dynamically. Kept `_FALLBACK_RANKING` (2 slugs) as safety net for API fetch failure only.
3. REFACTOR: Updated `get_model_details()` to use `get_ranking()` instead of deleted `_FREE_MODEL_RANKING`
4. Fix existing tests: `test_free_model_rotator.py` + `test_integration_pipeline.py` — inject fake catalog instead of hitting API, assert dynamic behavior instead of specific stale slugs

### Verification
- 370/370 tests pass, 0 regressions
- New test `test_rotator_dynamic_ranking.py` locks in: only free models, no paid, no stale slugs, sorted by context_length, empty catalog → empty ranking
- Fallback only triggers on API fetch failure (not on empty catalog)

### Files
- `backend/llm/rotator.py` — added `catalog` param, `_fetch_catalog_models()`, rewrote `get_ranking()`, kept `_FALLBACK_RANKING` for fetch failure only
- `test_rotator_dynamic_ranking.py` — new test for dynamic ranking seam
- `test_free_model_rotator.py` — updated to inject catalog, assert dynamic behavior
- `test_integration_pipeline.py` — updated 3 tests to inject catalog

### Issue
Closes #125 — https://github.com/Pingevo/multi-agents/issues/125

## 2026-08-05 (session 10) — SearchAdapter architecture completed (P0.2 done)

### What
Completed the SearchAdapter deepening per ADR-0004 + HANDOFF P0.2:
1. **Bug fix**: `supports_server_tool` checked `"web_search"` (old name) instead of `"web_search_options"` (current OpenRouter param) — Perplexity models all returned True (wrong), reproducing the 404 bug ADR-0004 was meant to fix
2. **Consolidation**: Added `SearchAdapter.resolve_search_model(ai_search_model, selected_model, default_model)` as the single resolution point. `search.py:_resolve_search_model` is now a thin wrapper delegating to the adapter — 4 scattered decision points → 1 deep module + 1 wrapper
3. **Test data fix**: `test_search_adapter.py` + `test_web_search_migration.py` used `"web_search"` in fake catalogs (which is why the adapter bug passed tests). Updated to `"web_search_options"` to mirror real OpenRouter metadata

### Why (architectural)
- ADR-0004 created the adapter as the "single decision point" but the parameter-name check was wrong — the adapter was making the wrong decision, defeating its purpose
- HANDOFF P0.2 marked "DONE" but manual test of Perplexity was pending — the bug would have surfaced immediately on first real Perplexity use
- The 4 scattered decision points (secretary, chat.py, orchestrator, search.py) for model resolution are now 1 adapter + 1 thin wrapper — locality: bugs concentrate in the adapter

### TDD slices (red → green → refactor)
1. RED: Updated `test_search_adapter.py` fake catalog to use `web_search_options` → 5 Perplexity tests fail
2. GREEN: Fixed `supports_server_tool` to check `web_search_options` → 13/13 pass
3. RED: New `test_adapter_resolve_model.py` for `resolve_search_model` → AttributeError
4. GREEN: Added `resolve_search_model` to adapter → 5/5 pass
5. REFACTOR: `search.py:_resolve_search_model` delegates to adapter → 29/29 pass (behavior preserved)
6. Fix test data in `test_web_search_migration.py` → 42/42 pass

### Verification
- Full suite: 364 passed, 0 regressions
- ADR-0004 amended with the parameter-name fix + consolidation
- HANDOFF P0.2 now genuinely complete (not just "code done")

### Files
- `backend/tools/search_adapter.py` — added `resolve_search_model`, fixed `supports_server_tool` param check
- `backend/tools/search.py` — `_resolve_search_model` now delegates to adapter
- `test_search_adapter.py` — fake catalog uses `web_search_options`
- `test_web_search_migration.py` — fake catalog uses `web_search_options`
- `test_adapter_resolve_model.py` — new test for `resolve_search_model` seam
- `test_search_uses_adapter.py` — new test locking in delegation
- `docs/adr/0004-search-adapter-for-format-selection.md` — amendment

### Remaining (out of scope this session)
- P0.1: Replace `_globals._search_model` with dependency injection (the wrapper still reads the global — that's the next slice)
- P1.1: `cl.user_session` hidden coupling (100+ points)
- P2: Catalog duplication (`discovery.get_catalog_summary` vs `selector._build_media_catalog`)

## 2026-08-05 (session 9) — Fix search_model never selected: discovery missed web_search_options param

### Bug
User ขอข่าว "spider-man brand new day" → Secretary สร้าง plan ได้ แต่ `search_model: ""`
ทำให้ปุ่ม "อนุมัติแผน" disabled และแสดง "กรุณาเลือกโมเดล: Search"

### Root cause (diagnosing-bugs skill, 6 phases)
`backend/llm/discovery.py:100` ตรวจ `"web_search" in supported_parameters`
แต่ OpenRouter เปลี่ยนชื่อ parameter เป็น `web_search_options` สำหรับ Perplexity
และ routing models ที่รองรับ search — ไม่มีโมเดลไหนในปัจจุบันที่ใช้ `web_search`
อีกแล้ว ทำให้ `output_groups["search"]` ว่าง และ `get_catalog_summary()`
ไม่ส่งบรรทัด "Web search models:" ให้ Secretary LLM เลย → LLM ไม่มี search model ID
จะใส่ใน `search_model` field

นี่คือ root cause เดียวกับ ADR-0004 (SearchAdapter) และ issue #124:
OpenRouter มี 2 ชื่อ parameter สำหรับ search (`tools:[openrouter:web_search]`
vs `web_search_options`) ระบบเราตรวจแค่ชื่อเดิม

### Fix
`backend/llm/discovery.py:99-107` — เพิ่ม `"web_search_options" in params` เข้าไปใน
เงื่อนไข: `if ("web_search" in params or "web_search_options" in params) and "text" in output_modalities`

### Verification
- `/tmp/test_search_catalog.py` (regression test, red → green): assert "Web search" in summary
- ก่อน fix: AssertionError (RED)
- หลัง fix: "Web search models: sakana/fugu-ultra, perplexity/sonar-pro-search, ..." (GREEN)
- Server restart แล้ว พร้อมทดสอบในเบราว์เซอร์

### Note
หลัง fix มีโมเดลทั่วไป (gpt-4o, sakana/fugu-ultra) ติดเข้ามาใน search list
เพราะ OpenRouter อนุญาตให้ใช้ `web_search_options` เป็น routing feature
โมเดลเหล่านี้ทำ search ได้จริง (ผ่าน routing) แต่ไม่ใช่ search-specialized
แยกปัญหานี้ไว้ใน issue #124 (capability metadata) — ไม่ขยาย scope ในครั้งนี้

## 2026-08-05 (session 8) — Fix NameError: _sanitize_error undefined in messenger.py

### Bug
User ขอข่าว "spider-man brand new day" → Manager ตอบ `❌ เกิดข้อผิดพลาด: name '_sanitize_error' is not defined`

### Root cause
`backend/core/messenger.py:70` เรียก `_sanitize_error(e)` ใน `_fetch_credits()` exception handler
แต่ไม่ได้ import จาก `backend.utils` — เมื่อ credits fetch ไปเจอ exception ก็เกิด NameError ซ้อนทับ
ส่งไปถึง user

### Fix
เพิ่ม `from backend.utils import _sanitize_error` ใน messenger.py (1 บรรทัด)

### Verification
- `python -c "from backend.core.messenger import StateMessenger"` → OK
- `_sanitize_error(ValueError('test'))` → "test error"

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

### Seventh check: one-shot script (session 12h)
User challenged: "recheck กี่รอบก็เจอตกหล่นทุกรอบ มันจะไปจบที่ตรงไหน?"
Wrote `scripts/check_ai_usage_hub.py` — checks all 6 categories in one pass:
1. Call site coverage (success + error per file)
2. Spec field coverage (mandatory fields per block)
3. Cleanup (credit_logger, jsonl, imports)
4. Config (.env.example vars)
5. Edge cases (video polling, fallback, streaming, litellm, crewai)
6. Code quality (indentation consistency)
First run found 2 real issues: local fallback (Ollama) success paths missing
`cost_usd`. Ollama is free → actual cost = 0 → added `"cost_usd": 0` explicitly.
Second run: ALL CHECKS PASSED. Script is reusable for future call site additions.

### Eighth check: independent audit (session 12i)
User challenged: "มั่นใจได้ไงว่า script ไม่ bias"
Ran independent sub-agent audit WITHOUT using my script. Found 2 real issues
my script missed (script had same blind spots as code author):
1. `"_stream_id" in dir()` — dir() doesn't check local vars. Fixed to `locals()`.
   Affected 3 streaming paths (manager.py:274,345, rotator.py:432).
2. `provider="local"` for Ollama fallback — spec only allows openrouter|gemini|
   openai|anthropic|apify|9arm|other. "local" would be normalized to "other"
   server-side but better to send "other" explicitly. Fixed 4 log calls.
False positives (audit was wrong): GET /models and /key calls don't need logging
(spec = "เรียก AI provider จริง" = generation, not catalog fetch). user/reference
come from contextvars in _normalize_entry(), not call site dict.
Lesson: self-written checker has same blind spots as code author. Independent
audit catches what self-audit can't.

### Diagnosing-bugs: log not appearing on dashboard (session 13)
User reported: "ไม่เห็นบนเว็บเลย ทั้งๆที่ทำงานจนจบ plan แล้ว"

Phase 1 (feedback loop): python script that loads .env and POSTs to Hub.
Phase 2 (reproduce): 3/3 runs → HTTP 403 {"success":false,"error":"Insufficient scope"}
Phase 3 (hypotheses):
  H1: token lacks scope → predicts 403 on every request regardless of payload ✓
  H2: token expired → predicts 401 ✗ (got 403)
  H3: wrong endpoint → predicts 404 ✗ (got 403)
  H4: token bound to wrong project → same as H1
  H5: rate limit → predicts 429 ✗
Phase 4 (instrument): tested all combinations:
  - minimal payload (just provider) → 403
  - batch endpoint → 403
  - Bearer auth instead of x-service-token → 403
  All 403. Root cause = token scope, not payload/auth/endpoint.
Phase 5 (fix what we can):
  - ai_usage_hub.py: added one-time console warning when env vars unset
    (was silent no-op — user couldn't tell why logs weren't appearing)
  - ai_usage_hub.py: _safe_post now prints HTTP errors instead of swallowing
    (was silent on 4xx/5xx — user couldn't tell Hub was rejecting)
  - Also fixed duplicated file content (242→122 lines, was accidentally doubled)
Phase 6: root cause is token scope — user must ask sellcenter team to fix.
  Code changes committed so future config issues are visible in console.

## 2026-08-05 — Task D: Frontend parity (visible reasoning + source chips)

### Context
Search parity HANDOFF Task D — frontend did not show what the market (Claude,
ChatGPT, Gemini, Perplexity) shows during agent execution:
1. AI reasoning streaming token-by-token (TasksWindow only showed "ยังไม่มี output"
   even though backend already streams `thinking` and StoryboardArea/ChatPanelRight
   already render it)
2. Source URLs as clickable chips (we embedded them in output text)

### Changes

**Slice 1 — Backend tool descriptions carry real args**
- `backend/core/orchestrator.py` `_tool_description()` — surface `query` for
  `search_web` ("🔍 Searching: <query>") and `url` for `browse_web`/`scrape_web`
  ("📖 Reading: <url>"). Previously only `generate_image` had arg-aware text;
  other tools fell back to generic "⚙️ Using <tool>...".
- `test_orchestrator.py` — added `TestToolDescription` (7 tests, all green).
  Covers search/browse/scrape/generate_image/unknown/missing-arg cases.

**Slice 2 — Visible reasoning in TasksWindow (parity gap fix)**
- `frontend/src/components/retro/TasksWindow.tsx`:
  - `ResultPanel` Output tab: when agent is `running` and has no output yet,
    render the streaming `thinking` field (italic, scrollable, max 160px)
    instead of "ยังไม่มี output". Falls back to animated "กำลังคิด..." dots
    when thinking hasn't started. `tool_description` shows as a single context
    line above the reasoning.
  - `FlowNode`: live reasoning preview (last 140 chars) under the agent card
    while running, falling back to tool_description then dots.
- `frontend/retro-mockup.css` — `.tw-node-thinking`, `.tw-rp-thinking` styles.
- Reuses the existing `animate-thinking` Tailwind keyframe (no new animation).

**Slice 3 — Source chips under output**
- `frontend/src/utils/sources.ts` (new) — `extractSourceUrls(text)` pulls
  http(s) URLs out of agent output, dedupes, returns `{url, label(host)}`.
  Catches both `Source: <url>` format (search prompt) and bare URLs.
- `frontend/src/components/retro/TasksWindow.tsx` — under Output in ResultPanel,
  render chips (mono font, retro chip style) opening in a new tab.
- `frontend/retro-mockup.css` — `.tw-rp-sources`, `.tw-rp-chips`, `.tw-rp-chip`.

### Verification
- `npm run build` — passes (no TS errors, vite build clean)
- `tsc --noEmit` — passes
- `pytest test_orchestrator.py` — 15 passed (7 new + 8 existing)
- Browser preview opened for user to verify visually

### Files changed
- backend/core/orchestrator.py
- test_orchestrator.py
- frontend/src/components/retro/TasksWindow.tsx
- frontend/src/utils/sources.ts (new)
- frontend/retro-mockup.css

### Code review fixes (2026-08-05)
Two hard issues from code-review skill:
1. **Schema mismatch** — `frontend/src/schemas/messages.ts` `AgentProgressEntry`
   was missing `thinking` field (and stale status union). Backend already sends
   it, frontend already consumes it via `chatTypes.ts`. Added `thinking?: string`
   and aligned status union with backend (`waiting_approval`, `awaiting_review`).
2. **Inline styles** — `TasksWindow.tsx` thinking block used inline styles
   (violates CLAUDE.md Surgical Changes — styling belongs in CSS). Extracted to
   `.tw-rp-thinking`, `.tw-rp-tool-desc`, `.tw-rp-thinking-waiting`,
   `.tw-rp-thinking-dots`, `.tw-rp-empty` in `retro-mockup.css`. Also collapsed
   the 3 duplicated dot spans into a `[0, 0.2, 0.4].map(...)` (Duplicated Code
   smell from the review).

TDD violation fix:
- Installed `vitest` as devDependency (minimal — no config file needed, vitest
  reads vite config). Added `test`/`test:watch` scripts to `package.json`.
- Wrote `frontend/src/utils/sources.test.ts` — 8 tests covering empty input,
  `Source:` prefix format, bare URLs, dedup, trailing punctuation, host label,
  long-host truncation, non-http scheme rejection. All green.

### Files changed (review fixes)
- frontend/src/schemas/messages.ts
- frontend/src/components/retro/TasksWindow.tsx
- frontend/retro-mockup.css
- frontend/src/utils/sources.test.ts (new)
- frontend/package.json (test scripts + vitest devDep)

### Diagnosing-bugs: streaming methods skip log_ai_usage when stream omits usage (session 14)

User asked: "จริงๆแล้วแค่ plan approval มันก็ต้องมีการใช้เครดิตแล้วไม่ใช่หรอ?"
→ Correct insight: plan creation calls LLM (streaming path), so log MUST reach Hub.

Phase 1 (feedback loop): unit test mocking stream without usage_data → assert log_ai_usage called.
Phase 2 (reproduce): test failed — log_ai_usage NOT called when usage_data is None.
Phase 3 (hypotheses):
  H1: `if usage_data:` guard skips log on success when stream omits usage ✓
  H2: log_ai_usage itself broken ✗ (e2e test with real token → 201)
  H3: env vars not loaded ✗ (verified loaded)
Phase 4 (instrument): audit ALL 9 LLM call paths via subagent:
  - 6/9 correct (call_with_fallback, _call_with_image, _call_with_multimodal, rotator.call, rotator.call_with_image, rotator.call_with_multimodal)
  - 3/9 had same bug: call_streaming, call_with_multimodal_streaming, rotator.call_streaming
  All 3 had `if usage_data:` without `else` — same copy-paste pattern.
Phase 5 (fix + regression test):
  - Added `else` clause to all 3 methods: log success without token/cost when stream omits usage
  - Wrote 3 regression tests (one per method) — all pass
  - E2E test: Hub accepts no-usage payload → 201 Created
Phase 6: 415/415 tests pass. Debug prints removed.

Root cause: copy-paste of `if usage_data:` pattern across 3 streaming methods,
none had an `else` branch. When a model's stream doesn't include usage metadata
(some models do this even with stream_options={"include_usage": True}), the
entire success log was silently skipped.

Architecture note: this is a code duplication problem — the same streaming+
log pattern is copied 3 times. A shared helper would prevent this class of
bug. See architecture assessment below.


## 2026-08-06 — MongoDB recheck + กฎใหม่ Section 17 (Assumption & Pivot Protocol)

### Signal ที่เรียนรู้
- เดิม: คิดว่า MongoDB (digital.in.th:27017) เก็บสินค้า ให้เราดึง (read-only)
- ความจริง: MongoDB `itsAgents` ว่างเปล่า + user มีสิทธิ์ readWrite
- สรุป: MongoDB คือ data storage ของระบบเรา ไม่ใช่แหล่งดึงสินค้า

### ประเด็นใหญ่ที่เจอ
- ทุก milestone ข้างหน้าสมมติว่า "เก็บใน JSON" โดยไม่ได้เขียน assumption นี้ออกมา
- พอทิศ MongoDB เปลี่ยน → assumption ซ่อนโผล่ออกมาทีละ issue ในทุก milestone
- "data persistence layer" ไม่เคยเป็น issue ของตัวเอง ไม่เคยอยู่ใน OST
- ADR-0003 บอกชัดว่า JSON คือชั่วคราว มี seam (store classes) ไว้ย้าย แต่ไม่เคยตั้ง issue/milestone ให้

### สิ่งที่ทำ
1. เช็ค .env: MONGO_DB เดิม = `tsAgents` (ตก i) → user แก้เป็น `itsAgents`
2. ทดสอบ auth: authSource=itsAgents ผ่าน (เดิมใช้ tsAgents → fail มาตลอด)
3. สำรวจ database: itsAgents ว่างเปล่า (0 collections)
4. ทดสอบสิทธิ์: readWrite ใน itsAgents อันเดียว (ไม่มีสิทธิ์ db อื่น)
5. วิจัยหลักการ pivot roadmap (Strangler Fig, assumption mapping, agile replan)
6. สรุปเป็นกฎใหม่ Section 17 ใน SYSTEM_PROTOCOL.md

### กฎใหม่: Section 17 — Assumption & Pivot Protocol
- 15.1: ทุก OST Opportunity ต้องมี Assumption ชัด (ไม่งั้น = planning fiction)
- 15.2: เมื่อ assumption พัง → Impact Analysis ก่อน (ไล่ทุก issue ทุก milestone) → บันทึก ADR → ปรับ OST → mark issue pivot → สร้าง issue ใหม่ → ปรับ milestone → อัปเดต log
- 15.3: เมื่อไหนสร้าง milestone ใหม่ vs ใส่ใน milestone เดิม (foundation กระทบหลาย M → สร้างใหม่)
- 15.4: ห้ามลบ issue, ห้ามแก้ issue จนเป็นเรื่องอื่น, ห้ามปรับแผนเงียบ, ห้าม blame
- 15.5: ตัวอย่างเคส MongoDB (สร้าง M6.5 ใหม่ + mark #129 pivot + สร้าง issue ใหม่)

### ผลกระทบต่อแผน (ยังไม่ได้แก้ — รอ user ยืนยันทิศ)
- #129 (ดึงสินค้า): ต้อง mark pivot + สร้าง issue ใหม่ "data persistence layer"
- #106 (Knowledge Store): ต้องแก้ body (ลบ MongoDB connector ดึงสินค้า)
- #24, #31, #36, #116, #132 (เก็บ data): ต้องเพิ่ม note ว่า assumption เปลี่ยน
- M6 milestone: ลด scope เหลือ Brand + Knowledge (พักสินค้า)
- สร้าง milestone ใหม่ M6.5: Data Persistence Migration

### ดำเนินการ pivot ตาม Section 17 (user ยืนยันทิศ)
1. ✅ สร้าง ADR 0006: `docs/adr/0006-mongodb-data-storage-pivot.md`
2. ✅ แก้ OST Opp 7: เพิ่ม assumption เดิม (ผิด) + ใหม่ + pivot note
3. ✅ สร้าง milestone M6.5 (#14): "Data Persistence Migration" due 2026-10-15
4. ✅ mark #129 pivot: เพิ่ม note ใน body (ไม่ลบ, บอก why)
5. ✅ สร้าง issue #139: "DataStore abstraction — facade สำหรับย้าย JSON → MongoDB" (M6.5, P1)
6. ✅ แก้ #106: ลบ "MongoDB connector ดึงสินค้า" + เพิ่ม pivot note
7. ✅ เพิ่ม note ADR-0006 ใน #24, #31, #36, #116, #132 (assumption "เก็บใน JSON" อาจเปลี่ยน)
8. ✅ ปรับ M6 desc: "Brand entity + Knowledge Store (REST API, URL, File, Text). MongoDB product data paused (ADR-0006 → M6.5)"

---

## 2026-08-06/07 — แก้กฎ Secrets + Issue lifecycle + Project Board workaround

### แก้กฎ Secrets & Credentials (Section 16)
- **ปัญหา**: กฎเดิมเขียน "ห้ามอ่านค่า secret จาก .env" แต่ความจริงอนุญาตให้ดึงค่าไปใช้ได้ แค่ห้ามค่าจริงปรากฏใน context ของ agent
- **แก้ใน**: SYSTEM_PROTOCOL.md Section 16 + global_rules.md
- **กฎใหม่**: ✅ `set -a; source .env; set +a` แล้วใช้ `$VAR` / ❌ `cat .env`, `echo $TOKEN`, `grep KEY .env`
- **Commit**: `044b75e` (บน feat/brand-entity → merge เข้า dev ใน `6accf5d`)

### แก้กฎ Issue lifecycle + Project Board (issue-tracker.md + project-board.md)
- **ปัญหาที่เจอ**: ทำ #139 เสร็จ จะอัปเดต Status=Done ตามกฎ แต่พบว่า:
  1. repo `Pingevo/multi-agents` เราไม่ใช่เจ้าของ สร้าง project board ใน repo ไม่ได้
  2. กฎเดิมบอก "Issues ทั้งหมดถูกเพิ่มเข้า board อัตโนมัติ" — **ผิด** #139 ไม่ได้ถูกเพิ่มอัตโนมัติ
  3. กฎเดิมไม่ได้อธิบายว่า board อยู่ที่ไหน ใช้ token อะไร ไม่มีขั้นตอนชัดเจน
- **แก้ใน**:
  - `docs/agents/issue-tracker.md` — Issue lifecycle เพิ่มขั้น "เช็คว่า issue อยู่ใน board หรือยัง" + อธิบาย workaround (board ของ token owner ไม่ใช่ repo board) + ตัวอย่าง GraphQL commands
  - `docs/agents/project-board.md` — เพิ่ม section "IDs สำหรับ GraphQL" (Project ID, Status field ID, Done option ID) + ตัวอย่าง mutation
- **ไฟล์ที่แก้**: `docs/agents/issue-tracker.md`, `docs/agents/project-board.md`

### แยก branch ที่ผิด
- **ปัญหา**: commit #139 (DataStore) ปนอยู่ใน `feat/brand-entity` (M6 branch) ทั้งที่ #139 เป็น M6.5
- **แก้**:
  1. สร้าง `feat/m6.5-data-persistence` จาก `93954db` cherry-pick `2c9e6fe` → `60d6d0c`
  2. reset `feat/brand-entity` ลบ `2c9e6fe` ออก (เหลือถึง `044b75e`)
  3. merge `feat/brand-entity` เข้า `dev` (commit `6accf5d`)

### อัปเดต #139 บน GitHub
- เพิ่ม #139 เข้า Project Board (item ID `PVTI_lAHOEgEBqs4BdqeLzg1m87w`)
- อัปเดต Status → Done
- เพิ่ม comment สรุปงาน (commit hash, ไฟล์, ผล test, ยังเหลืออะไร)
- ไม่ปิด issue — รอ human verify (ตามกฎ)
