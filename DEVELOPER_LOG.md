# DEVELOPER_LOG

## 2026-07-10 (Session 6) — Feature: Agent Tuning — Deep Persona

### Summary
Expanded agent schema from flat (name, role, goal, backstory) to deep persona with personality, expertise, brand_context, learnings, and team_id. Updated AgentFactory to compose rich backstory from all persona fields. Updated CentralSecretary plan prompts to generate deep persona fields. Added self-check quality instruction to task descriptions.

### Branch
`feature/agent-tuning` (branched from `main`)

### Files Modified
- `SYSTEM_PROTOCOL.md` — Updated North Star with company/team/brand vision, added Section 3.5 Agent Persona
- `backend/agents/registry.py` — Expanded schema: personality, expertise, brand_context, learnings, team_id; auto-naming `[Role] #N`; `add_learning()` method; updated `to_spec()`, `update_agent()`, `to_markdown_table()`
- `backend/agents/factory.py` — New `_build_agent_backstory()` composes persona from all fields; added self-check instruction to task descriptions
- `backend/core/secretary.py` — Both plan prompts updated to request personality, expertise, brand_context fields; plan parsing extracts new fields

### Key Changes
1. **Agent naming**: Auto-generates `[Role] #N` (e.g. "Creative Writer #1") instead of generic names
2. **Deep persona in prompts**: `_build_agent_backstory()` combines identity + personality + expertise + brand_context + learnings into rich backstory
3. **Self-check**: Task descriptions now instruct agents to self-verify before submitting
4. **Learnings storage**: `add_learning()` keeps last 10 entries per agent for memory

### Status
Phase 1 (Deep Persona Schema) complete. Phase 2 (Feedback Loop) and Phase 3 (Learnings & Memory) pending.

---

## 2026-07-10 (Session 5) — Feature: Playwright Headless Browser for JS-Heavy URL Scraping

### Summary
Added Playwright as fallback scraper for JS-heavy websites (Shopee, Lazada, TikTok) that block `requests.get()`. When `requests.get()` returns empty/too-short text or the domain is known to require JavaScript, the system automatically falls back to headless Chromium to render and extract page content.

### Branch
`feature/url-headless-browser` (branched from `refactor/modularize-and-cleanup` after Session 2-4 commit)

### Changes
- **`backend/attachment/url.py`**: Added `JS_REQUIRED_DOMAINS` list (shopee, lazada, tiktok, amazon) and `is_js_required_domain()` helper
- **`backend/attachment/processor.py`**:
  - Added `scrape_with_playwright()` — headless Chromium with SSRF protection, 30s timeout, text extraction
  - Modified `process_url()` webpage branch: requests first (skip for JS domains) → Playwright fallback if text < 500 chars → metadata if both fail
- **`test_playwright_scrape.py`**: 13 new tests (scrape, SSRF, timeout, fallback, JS-required domain, failure handling)

### Test Results
- 13/13 new tests pass
- 46/46 existing attachment tests pass (no regressions)

### Skills Compliance
- **codebase-design**: Designed `scrape_with_playwright()` interface before implementing
- **tdd**: Wrote 13 failing tests first, then implemented to make them pass
- **implement**: Implemented in 3 files with minimal changes
- **code-review**: Pending

### Security
- SSRF protection maintained (localhost/internal IPs blocked before Playwright)
- No cookies/sessions/credentials stored
- Browser closed after every use (context manager)
- `.env` and session data confirmed in `.gitignore`

## 2026-07-10 (Session 4) — Fix: Socket TransportError, Per-Agent Thinking, Routing Model Free Display

### Summary
Fixed 3 critical issues found during testing: socket hardcoded to localhost:8000 causing TransportError in browser preview (blocking all actions including image approval), per-agent thinking not rendered in Storyboard agent cards, and routing models (openrouter/auto, openrouter/free) incorrectly shown as free.

### Changes
- **`frontend/src/App.tsx`**: Changed `BACKEND_URL` from hardcoded `'http://localhost:8000'` to `window.location.origin` — socket now connects through whatever proxy/host the browser uses
- **`frontend/src/components/ChatPanelRight.tsx`**: Added `hasThinking` check and thinking render block in `AgentStatusRow` — shows agent's `thinking` text in a scrollable box when agent is running
- **`frontend/src/components/ModelPicker.tsx`**: Added `ROUTING_MODELS` array and `isRoutingModel()` helper; `isModelFree()` returns `false` for routing models; `getModelCostTier()` returns `'unknown'` for routing models
- **`backend/handlers/chat.py`**: Added `[DEBUG-RESULT]` log before `reply_result()` showing media_tool_results count

### Root Causes
1. **Socket TransportError**: `BACKEND_URL` was hardcoded — browser preview proxy couldn't reach `localhost:8000` directly, so all socket actions (approve, reject, retry) silently failed
2. **No per-agent thinking**: Backend already sends `thinking` in `reply_agent_progress`, but `AgentStatusRow` only rendered `current_task`, `current_tool`, and `output`
3. **Routing models shown as free**: `isModelFree()` checked only pricing fields; routing models have all-zero/unknown prices but route to paid models

## 2026-07-10 (Session 3) — Fix: Execution UX, Result Ordering, Pricing Display

### Summary
Fixed 6 issues: thinking display appearing too late, progress bar flickering, agent output not auto-expanding, result card sent before image approval cards, missing final summary from manager, and inverted is_free logic causing incorrect pricing display.

### Changes
- **`frontend/src/App.tsx`**:
  - Added `isThinking` state — set `true` at send time, `false` on `thinking_done` or terminal message
  - `thinkingStartRef` now set at send time (not at first chunk arrival)
  - Replaced blanket `else { setIsProcessing(false); }` with terminal types check (`result`, `text`, `plan`, `plan_validation_error`, `image_result`, etc.)
  - State messages: only `setIsProcessing(false)` when no running tasks AND no pending approvals
  - Pass `isThinking` to MainLayout
- **`frontend/src/components/MainLayout.tsx`**: Added `isThinking` to props interface, destructuring, and pass to ChatPanelRight
- **`frontend/src/components/ChatPanelRight.tsx`**:
  - Added `isThinking` to props — shows thinking block when `isThinking === true` even if `thinkingText` is empty
  - Replaced `!thinkingText` with `!isThinking` in "Processing..." fallback condition
  - Inline thinking block (inside plan card) now shows when `isThinking || thinkingText`
  - Standalone thinking block shows when `isThinking` (not just `thinkingText`)
  - `AgentProgressCard`: Added `useEffect` to auto-expand agents with status `complete` or `waiting_approval` that have output
  - PlanCard: Added warning "⚠️ ไม่ใช่ image model — อาจมีค่าใช้จ่าย" when image model is not in image media catalog
- **`backend/handlers/chat.py`**:
  - Moved `reply_result()` from before approval cards to after all approval cards are sent
  - Conditional result message: "⏳ รออนุมัติสร้างสื่อ" if pending approvals, "✅ งานเสร็จสมบูรณ์" if none
  - Added `messenger.reply(raw_output[:4000])` after result card when raw_output is meaningful text (not JSON, >20 chars)
  - Fixed inverted `is_free` logic at lines 500 and 790: `":free" in mid or not all_pricing_fields` (was `":free" not in mid and not all_pricing_fields`)
- **`backend/media/manager.py`**: Added `else` log for FREE image model (was only logging for PAID)
- **`test_execution_ux.py`**: 9 tests covering is_free logic, result ordering, final summary conditions, media gen free detection

### Design Decisions
- Thinking timer measures total time from user send to thinking_done (not just streaming time)
- Progress bar stays visible until a terminal event arrives — non-terminal types don't change isProcessing
- Result card comes after approval cards to avoid confusing "complete" message
- Manager's raw_output shown as final summary when it contains readable text
- `is_free` logic: free = `:free` suffix OR all prices are zero (was inverted before)

## 2026-07-10 (Session 2) — Fix: Manager Model User Control & Plan Card Transparency

### Summary
Fixed regression from Fix 1 where manager model was overridden by UI fallback in adaptive mode. Now manager model comes from AI's choice (Secretary's plan), is visible in plan card, and user can change it before accepting.

### Changes
- **`chat.py` line 107**: Added fallback `or llm_manager.get_selected_model_name()` to `execute_multi_agent_task` (was still using `or ""`)
- **`chat.py` lines 1080/1248**: Removed `if selected_model: model_assignment["manager"] = selected_model` override — manager model now comes from AI's plan, not UI
- **`chat.py` lines 798-804**: Added `change_manager_model` action handler — updates `pre_assigned_models["manager"]` in session
- **`chat.py` lines 1162/1321**: Added `manager_model=model_assignment.get('manager', '')` to both `reply_plan()` calls
- **`schemas/__init__.py`**: Added `managerModel: str = ""` to `ChatReplyPlan`
- **`messenger.py`**: `reply_plan()` now accepts and sends `manager_model` parameter in payload + persist
- **`frontend/src/schemas/messages.ts`**: Added `managerModel?: string` to `ChatReplyPlan`
- **`frontend/src/components/chatTypes.ts`**: Added `managerModel?: string` to `ChatMessage`
- **`frontend/src/App.tsx`**: Added `managerModel` to plan message mapping, chat history restore, and `change_manager_model` action handler
- **`frontend/src/components/MainLayout.tsx`**: Added `onChangeManagerModel` prop passthrough
- **`frontend/src/components/ChatPanelRight.tsx`**: Added `managerModel` + `onChangeManagerModel` to `ChatPanelRightProps` and `PlanCard`. Plan card now shows manager model as first row with ModelPicker for changing it
- **`test_manager_model_not_overridden.py`**: 4 regression tests — secretary returns AI's manager model, ChatReplyPlan has managerModel field, change_manager_model updates session

### Design Decision
- Secretary (AI) assigns manager model in plan JSON — same as before
- Manager model is NOT overridden by UI selected_model — user can change it in plan card
- Model from UI = model of Secretary (chat/analysis), not model of Manager
- User sees and controls all models before accepting plan

## 2026-07-10 (Session 1) — Fix: Manager Model, Image Pricing Display, Agent Thinking

### Summary
Fixed 3 bugs: manager model not matching UI in adaptive mode, image models showing "Free" when they have paid image pricing, agent thinking not displaying because CrewAI sends agent_role=None in stream chunks.

### Fix 1: Manager model not matching UI
- **Root cause**: `chat.py` read `selected_model` from session which is empty in adaptive mode → `set_selected_model()` never called → LLMManager used default, not the resolved model shown in UI.
- **Fix**: `chat.py` lines 971 and 1175 — changed `selected_model = cl.user_session.get("selected_model") or ""` to `selected_model = cl.user_session.get("selected_model") or llm_manager.get_selected_model_name()`. This ensures the model is always set, matching what the UI displays.

### Fix 2: Image pricing display showing "Free" incorrectly
- **Root cause**: OpenRouter API returns `pricing = {prompt: "0", completion: "0", image: "0.01"}` for image models, but backend only sent `prompt_price` and `completion_price` to frontend. UI showed "Free" because both were 0, even though `image: 0.01` is paid.
- **Backend fix** (`chat.py` lines 464-477 and 740-755): Added `image_price`, `video_price`, `audio_price`, `web_search_price` fields to catalog entries. Changed `is_free` to check all pricing fields — model is free only when no pricing field has a value > 0.
- **Frontend fix** (`ModelPicker.tsx`):
  - Added optional pricing fields to `ModelCatalogEntry` interface
  - Added `getMaxPrice()` — returns highest non-zero price across all fields
  - Added `isModelFree()` — returns true only when all known prices are 0
  - Added `getModelCostTier()` — uses max price for cost tier classification
  - Detail panel now shows Image/Video/Audio/Web Search prices when > 0
  - Cost tier bar and free badge use new helpers
  - `ModelRow` cost indicator dot uses `getModelCostTier` and `getMaxPrice`
  - Removed unused `getCostTier` function

### Fix 3: Agent thinking not displaying
- **Root cause**: CrewAI's `LLMStreamChunkEvent` sends `agent_role=None` for all stream chunks. The `on_llm_stream_chunk` handler returned early when `agent_role` was None, so thinking text was never captured.
- **Fix** (`orchestrator.py` line 208-230): When `agent_role` is None, fall back to `_thread_local.agent_name` (set in `run_single_agent_sync` before kickoff). This is the agent name from the spec, which `_match_agent_index` can match against agent_specs by name.

## 2026-07-09 (Session 2 — Modularization Cleanup & Integration Tests)

### Summary
- Fixed all pre-existing test bugs (event loop hang, timeout test, empty agents plan rejection)
- Removed 558 lines of duplicate attachment code from `chat.py` (already extracted to `backend/attachment/`)
- Deleted 7 unused frontend components, extracted shared types to `chatTypes.ts`
- Created 14 integration tests with mocked OpenRouter API covering full LLM pipeline
- All 107 tests pass in ~28 seconds

### Test Bug Fixes
- **`test_valid_json_response_returns_plan`**: Test data had empty `agents` list → secretary rejected plan and returned `action:"chat"`. Fixed by adding a realistic agent in test JSON.
- **`test_timeout_returns_error`**: Hardcoded 30s timeout made test hang. Added `stream_timeout` parameter to `assess_and_plan()` and `assess_and_plan_multimodal()`. Test now uses `stream_timeout=3`.
- **Pytest event loop hang**: `run_in_executor(None, chunk_queue.get, 0.1)` blocked executor threads, causing thread pool exhaustion when streaming thread never yields. Replaced with non-blocking `chunk_queue.get_nowait()` + `asyncio.sleep(0.05)` polling loop.
- **`conftest.py`**: Added to set fresh asyncio event loop per test.
- **`asyncio.run()`**: Replaced all `asyncio.get_event_loop().run_until_complete()` calls in tests.

### Backend: Duplicate Code Removal
- **`backend/handlers/chat.py`**: Deleted lines 456-1013 (558 lines) — duplicate `URL_REGEX`, `classify_url`, `_is_localhost_url`, `download_with_limit`, `check_model_modality_support`, `llm_manager_tier_check`, `_resolve_file_path`, `_extract_text_content`, `process_attachment`, `process_url`, `AUDIO_FORMAT_MAP`, `URL_EXT_MAP`, `MAX_TEXT_LENGTH`, `MAX_URL_DOWNLOAD_SIZE`. These were already extracted to `backend/attachment/` package.
- **`backend/attachment/url.py`**: Added `URL_REGEX` constant (was only in deleted duplicate code).
- **`backend/handlers/chat.py`**: Updated import to `from backend.attachment.url import classify_url, URL_REGEX`.

### Frontend: Dead Code Cleanup
- **Deleted 7 unused components** (zero imports from any other file):
  - `AgentSidebar.tsx` — replaced by `AgentPalette` + `DetailPanel`
  - `ChatPanel.tsx` — replaced by `ChatPanelRight.tsx` (types extracted to `chatTypes.ts`)
  - `CanvasArea.tsx` — replaced by `StoryboardArea.tsx` (types `PendingApproval`/`ImageResult` moved to `platform.ts`)
  - `CanvasView.tsx` — superseded by `StoryboardArea`
  - `TaskGrid.tsx` — superseded by `StoryboardArea`
  - `CommandConsole.tsx` — superseded by `ChatPanelRight` input
  - `AgentNode.tsx` — only imported by `CanvasView` (also deleted)
- **`chatTypes.ts`** (new): Extracted all shared types from `ChatPanel.tsx` (`PlanAgent`, `ResultAgent`, `ChatMessageType`, `PlanStatus`, `ImageApprovalStatus`, `ChatMessage`, `AgentProgressEntry`, `ActivityEntry`). Updated all imports in `App.tsx`, `MainLayout.tsx`, `StoryboardArea.tsx`, `DetailPanel.tsx`, `ChatPanelRight.tsx`.
- **`platform.ts`**: Added `PendingApproval` and `ImageResult` interfaces (moved from `CanvasArea.tsx`).

### Integration Tests (`test_integration_pipeline.py`)
- **14 tests, 5 test classes**:
  - `TestLLMManagerTierDetection` (3): paid/free/error tier detection from OpenRouter credits endpoint
  - `TestLLMManagerCallWithFallback` (2): primary success, primary failure without fallback
  - `TestFreeModelRotatorIntegration` (2): model filtering (small/non-chat excluded), rotation on failure
  - `TestModelSelectorIntegration` (2): candidate fetching from rotator, LLM-driven model assignment
  - `TestCentralSecretaryIntegration` (4): plan response, chat response, empty stream, timeout
  - `TestEndToEndPipeline` (1): full pipeline rotator→selector→secretary produces valid plan
- All HTTP calls mocked via `unittest.mock.patch` — no real API calls.

### Files Changed
- `backend/core/secretary.py` — `stream_timeout` param, non-blocking queue polling
- `backend/handlers/chat.py` — 558 lines duplicate code removed, import updated
- `backend/attachment/url.py` — added `URL_REGEX`
- `frontend/src/types/platform.ts` — added `PendingApproval`, `ImageResult`
- `frontend/src/components/chatTypes.ts` — new file (extracted types)
- `frontend/src/components/StoryboardArea.tsx` — updated imports
- `frontend/src/components/MainLayout.tsx` — updated imports
- `frontend/src/components/DetailPanel.tsx` — updated imports
- `frontend/src/components/ChatPanelRight.tsx` — updated imports
- `frontend/src/App.tsx` — updated imports
- `frontend/src/components/AgentSidebar.tsx` — deleted
- `frontend/src/components/ChatPanel.tsx` — deleted
- `frontend/src/components/CanvasArea.tsx` — deleted
- `frontend/src/components/CanvasView.tsx` — deleted
- `frontend/src/components/TaskGrid.tsx` — deleted
- `frontend/src/components/CommandConsole.tsx` — deleted
- `frontend/src/components/AgentNode.tsx` — deleted
- `test_routing_model_planning.py` — test data fix, asyncio.run(), stream_timeout=3
- `test_integration_pipeline.py` — new file (14 integration tests)
- `conftest.py` — new file (asyncio event loop fix)

---

## 2026-07-09

### Multimodal Attachment Processing Pipeline

**Problem:** Only image attachments were supported via a hardcoded `image_data_url` path. No support for PDF, audio, video, text/DOCX/XLSX files, or any URL types (direct file URLs, webpage URLs, YouTube URLs). No model compatibility check, no streaming for multimodal, no CrewAI file integration for worker agents.

**Changes:**
- **Backend: Core processing functions** (`app.py`): Added `classify_url()`, `process_attachment()`, `process_url()`, `download_with_limit()`, `check_model_modality_support()`, `_resolve_file_path()`, `_extract_text_content()`, `_is_localhost_url()`, `llm_manager_tier_check()`. These handle all file types (image, PDF, audio, video, text, DOCX, XLSX, SVG) and URL types (image URL, PDF URL, audio URL, video URL, YouTube URL, webpage URL).
- **Backend: LLMManager multimodal methods** (`app.py`): Added `call_with_multimodal_async()`, `_call_with_multimodal()`, `call_with_multimodal_streaming()` — supports `image_url`, `file`, `input_audio`, `video_url` content blocks with optional plugins (e.g., PDF file-parser).
- **Backend: CentralSecretary multimodal methods** (`app.py`): Added `chat_response_multimodal()` for chat mode and `assess_and_plan_multimodal()` for plan mode — both support multimodal content blocks and streaming.
- **Backend: on_message refactor** (`app.py`): Replaced old image-only attachment handling with unified `process_attachment()` + `process_url()` pipeline. Detects URLs in user messages, merges all contexts, checks model compatibility, routes to multimodal or text LLM calls, stores attachment context for CrewAI worker agents.
- **Backend: create_task update** (`app.py`): Worker agents now receive attachment text content in task description and `input_files` (CrewAI Files API) when `crewai-files` package is available.
- **Backend: Cleanup** (`app.py`): `on_action_accept` clears attachment context after plan execution.
- **Frontend: Audio/video player** (`ChatPanelRight.tsx`): Attachment preview in chat messages now renders `<audio>` and `<video>` elements for audio/video attachments.
- **Tests** (`test_process_attachment.py`): 46 unit tests covering `classify_url` (9 tests), `process_attachment` (image, PDF, audio MP3/WAV, video, text, JSON, CSV, DOCX, XLSX, SVG, large text truncation, metadata, file-not-found — 20 tests), `process_url` (image, YouTube, PDF, audio, video small/large, webpage scraping, script/style stripping, 404 error, SSRF — 12 tests), `download_with_limit` (size limit), `check_model_modality_support` (supports/unsupported/unknown), integration tests (URL detection, attachment+URL together, conversation history excludes base64 — 3 tests).
- **Dependencies**: Installed `python-docx` and `beautifulsoup4`.

**Key design decisions:**
- Images/PDFs/audio use base64 data URLs for OpenRouter multimodal API; videos use `video_url` with direct URL or base64 (if <20MB).
- Webpage URLs are scraped with BeautifulSoup (strips script/style/nav/footer).
- YouTube URLs are passed directly as `video_url` (no download).
- SSRF protection: localhost/internal IP URLs are rejected (except `localhost:8000` for self-hosted attachments).
- URL download size limit: 50MB (`MAX_URL_DOWNLOAD_SIZE`).
- Text extraction truncates at 50,000 chars (`MAX_TEXT_LENGTH`).
- Model compatibility check warns user if selected model doesn't support required modality.
- Conversation history stores `context_text` only (not full multimodal blocks) to avoid memory bloat.
- CrewAI `input_files` integration is optional (graceful degradation if `crewai-files` package not installed).

**Files changed:** `app.py`, `frontend/src/components/ChatPanelRight.tsx`, `test_process_attachment.py`

---

## 2026-07-07

### Stop Button, Quota Display, Image Approval Review Flow

**Problem:** No way to stop AI generation mid-execution. No visibility into OpenRouter credit balance. Image prompts from agents may not be reviewed when a reviewer/quality agent exists in the plan.

**Changes:**
- **Frontend: Stop button** (`ChatPanelRight.tsx` + `MainLayout.tsx` + `App.tsx`): Send button (📤) becomes Stop button (⏹️ red) when `isProcessing`. `onStop` prop wired through MainLayout → ChatPanelRight. `handleStop` in App.tsx sends `stop_generation` action and resets `isProcessing`.
- **Backend: Stop action** (`app.py`): `stop_generation` action handler sets `cancel_generation` flag in session and replies "⏹️ หยุดการทำงานแล้ว".
- **Backend: Credits fetch** (`StateMessenger._fetch_credits` in `app.py`): Calls OpenRouter `GET /key` endpoint to fetch `limit_remaining`, `usage`, `usage_daily`, `usage_monthly`, `is_free_tier`. Included in every `_send()` state payload.
- **Schema: Credits field** (`schemas/__init__.py`): `StatePayload` now includes `credits: Optional[dict]`.
- **Frontend: Quota display** (`Header.tsx` + `MainLayout.tsx` + `platform.ts` + `PlatformContext.tsx`): Header shows wallet icon with remaining/limit credits. Shows "Free Tier" warning if free tier. Yellow text when remaining < $1. Tooltip shows daily/monthly usage.
- **Backend: Image approval review flow** (`ExecutionOrchestrator.run_async` in `app.py`): After wave execution, checks if any agent has "review", "quality", "checker", "approver", or "editor" in role/name. If yes, sends captured prompts to manager LLM for refinement before sending approval cards. If no reviewer, prompts are final as-is from agent. Logs `[APPROVAL-FLOW]` for debugging.

**Files changed:** `app.py`, `schemas/__init__.py`, `frontend/src/components/Header.tsx`, `frontend/src/components/ChatPanelRight.tsx`, `frontend/src/components/MainLayout.tsx`, `frontend/src/App.tsx`, `frontend/src/types/platform.ts`, `frontend/src/context/PlatformContext.tsx`

---

### Image Generation Fix + Wave Progress UI + Retry/Error Handling

**Problem:** Image generation failed with "OpenRouter image API returned no URL" because the API returns `b64_json` (base64-encoded image) not `url`. Wave execution UI showed agents in wrong order because progress updates were only sent at start and end, not between waves. No retry mechanism existed for failed image generation.

**Changes:**
- **Backend: Fix `_openrouter_image()`** (`app.py`): Removed unsupported `resolution` and `output_format` fields from payload. Now handles both `b64_json` (base64 decode + save) and `url` (download) response formats from OpenRouter Images API.
- **Backend: Wave progress updates** (`ExecutionOrchestrator.run_async` in `app.py`): Added `_send_progress` calls before each wave starts (mark agents as "running") and after each wave completes (mark agents as "complete"). Previous waves' agents stay "complete", future waves' agents stay "pending". This ensures UI reflects actual wave execution order.
- **Backend: Error approval card** (`app.py`): `reply_image_approval` now accepts `approval_status` and `image_error` params. On generation failure, sends error card with `approvalStatus="error"` instead of plain text. `pending_media` is preserved for retry.
- **Backend: `retry_image` action** (`app.py`): New action handler that re-attempts image generation using stored `pending_media`. Clears `pending_media` on success.
- **Backend: Schema update** (`schemas/__init__.py`): `ChatReplyImageApproval` now includes `approvalStatus` and `imageError` fields.
- **Frontend: Error status + retry** (`ChatPanel.tsx` + `ChatPanelRight.tsx` + `StoryboardArea.tsx` + `CanvasArea.tsx` + `MainLayout.tsx` + `App.tsx`): `ImageApprovalStatus` type now includes `'error'`. `PendingApproval` and `ChatMessage` include `approvalStatus` and `imageError`. Approval cards show error message with 🔄 Retry button when status is `'error'`. `onRetryImage` handler wired through MainLayout → StoryboardArea → AgentCard. `retry_image` action in App.tsx resets status to `'pending'` optimistically.

**Files changed:** `app.py`, `schemas/__init__.py`, `frontend/src/components/ChatPanel.tsx`, `frontend/src/components/ChatPanelRight.tsx`, `frontend/src/components/StoryboardArea.tsx`, `frontend/src/components/CanvasArea.tsx`, `frontend/src/components/MainLayout.tsx`, `frontend/src/App.tsx`

---

### Model Visibility, Wave Execution Fix, and Readable Final Results

**Problem:** Users couldn't see which model was running during planning/execution, and wave-based execution had a bug where upstream context was empty. Final results were raw CrewAI text full of internal markers, making them hard to understand. Image approval cards didn't show which model would be used for generation.

**Changes:**
- **Backend: Wave execution fix** (`ExecutionOrchestrator.run_async` in `app.py`): Removed the pre-marking of agents as "completed" with empty output before wave execution. Dependencies now wait for real outputs before injecting upstream context.
- **Backend: Model visibility in progress** (`app.py`): Added `model` field to all agent progress payloads. Planning notification now shows user-selected model or "Adaptive mode". Logs print selected model and adaptive status.
- **Backend: Agent output cleaning** (`ExecutionOrchestrator._clean_agent_output` in `app.py`): New helper strips CrewAI internal markers ("Final Answer:", "Task Completed", "Crew Completion", box-drawing chars) from agent outputs before manager synthesis and final result.
- **Backend: Improved manager synthesis** (`ExecutionOrchestrator.run_async` in `app.py`): Prompt now explicitly asks for a clean, user-facing response with clear headings and no internal markers.
- **Backend: Image approval model** (`app.py` + `schemas/__init__.py`): `generate_image`/`generate_video` tools capture the current generation model. `ChatReplyImageApproval` now includes `model` field. `reply_image_approval` persists and sends the model.
- **Frontend: Agent progress model** (`ChatPanel.tsx` + `ChatPanelRight.tsx` + `StoryboardArea.tsx` + `CanvasArea.tsx`): `AgentProgressEntry` includes `model`; agent cards display it under the name.
- **Frontend: Image approval model** (`App.tsx` + `ChatPanel.tsx` + `CanvasArea.tsx` + `StoryboardArea.tsx` + `MainLayout.tsx` + `schemas/messages.ts`): `ChatMessage` and `PendingApproval` include `model`; approval cards show the generation model.
- **Frontend: Readable result card** (`ChatPanelRight.tsx` + `ChatPanel.tsx`): Result card now shows the Manager's synthesized output as the main user-facing answer, with other agent raw outputs as collapsible "Agent details".

**Files changed:** `app.py`, `schemas/__init__.py`, `frontend/src/components/ChatPanel.tsx`, `frontend/src/components/ChatPanelRight.tsx`, `frontend/src/components/StoryboardArea.tsx`, `frontend/src/components/CanvasArea.tsx`, `frontend/src/components/MainLayout.tsx`, `frontend/src/App.tsx`, `frontend/src/schemas/messages.ts`

---

### Dynamic Model Selection — User picks model at session and plan level

**Problem:** Users had no control over which LLM model to use. The system auto-selected via rotator, but users wanted to choose models like in Windsurf/Devin/GPT/Gemini interfaces.

**Changes:**
- **Backend: `ModelCatalog` class** (`app.py`): Fetches all models from OpenRouter API, categorizes into recommended groups (reasoning, coding, vision, fast, chat) by keyword matching, sorts by popularity. Provides `search()` for keyword filtering. No hardcoded model lists — all dynamic from API.
- **Backend: `ChatReplyModelCatalog` schema** (`schemas/__init__.py`): New message type `model_catalog` with `recommended` (dict by category), `searchResults`, and `selectedModel` fields. Added `ModelCatalogItem` sub-model.
- **Backend: `StateMessenger.reply_model_catalog()`**: Sends model catalog to frontend as `chat_reply` message.
- **Backend: Action handlers** in `on_message`:
  - `fetch_model_catalog`: Fetches recommended models and sends to frontend.
  - `search_models`: Searches by keyword, returns results + recommended.
  - `set_selected_model`: Stores user's session-level model choice in `cl.user_session`.
  - `change_agent_model`: Updates `pre_assigned_models` for specific agent in plan.
- **Backend: `LLMManager.set_selected_model()`**: New method to override rotator's smartest pick. `get_llm()` checks `_selected_model` first.
- **Backend: `PlanAgentItem.model`**: Added `model` field to schema so plan cards show assigned model per agent.
- **Backend: `assess_and_plan`**: Both `STATE_IDLE` and `STATE_GATHERING_REQUIREMENTS` paths now apply `selected_model` from session before calling secretary.
- **Frontend: `ModelPicker.tsx`**: New component — Windsurf/Devin style model selector with:
  - Categorized recommended models (Reasoning, Chat, Coding, Vision, Fast) with icons
  - Search bar with live filtering
  - Price + context length display per model
  - Selected model indicator
- **Frontend: `ChatPanelRight.tsx`**: Added Cpu icon button next to send button to open ModelPicker. Shows current model below input bar. PlanCard now shows model per agent with inline edit when plan is pending.
- **Frontend: `App.tsx`**: Parses `model_catalog` messages, manages `selectedModel` state, wires `set_selected_model` action.
- **Frontend: `MainLayout.tsx`**: Passes model-related props through to ChatPanelRight.
- **Frontend: `schemas/messages.ts`**: Added `ModelCatalogItem`, `ChatReplyModelCatalog` types, `model` field to `PlanAgentItem`.

### Remove hardcoded LLM_PAID_MODEL — AI selects model for all tiers

**Problem:** `LLM_PAID_MODEL=anthropic/claude-3.5-sonnet` was hardcoded in `.env` and used directly in `LLMManager.get_llm()` and `call_with_fallback()`. This contradicts the project principle "AI เลือก model เอง" — paid tier had no AI selection, just a fixed model name that could 404 if OpenRouter changes model IDs.

**Changes:**
- `FreeModelRotator`: Added `free_only` parameter (default `True`). When `False` (paid tier), fetches all tool-capable large models from OpenRouter, sorted by param count (top 30). Added `get_model_details()` to return full metadata.
- `LLMManager`: Removed `self.paid_model` and `LLM_PAID_MODEL` env var. Now creates a rotator for both paid (`free_only=False`) and free (`free_only=True`) tiers. `get_llm()` and `call_with_fallback()` use rotator's `pick_smartest_model()` / `call()` for both tiers.
- `ModelSelector._fetch_candidates()`: Now uses `rotator.get_model_details()` for real metadata (context_length, pricing, description) instead of dummy values. Works for both paid and free tiers.
- `ModelSelector.assign_models()`: Prompt updated — removed "FREE" labels, now tier-agnostic.
- `.env.example`: Removed `LLM_PAID_MODEL` line. Updated tier descriptions.

**Files changed:** `app.py`, `.env.example`

---

## 2026-07-02

### Summary
- สร้าง `SYSTEM_PROTOCOL.md` ตามคำสั่ง User เป็นรัฐธรรมนู่งของโปรเจกต์
- ปรับ UI จาก Chatbot-First เป็น **Platform Dashboard** แบบเต็มรูปแบบด้วย Custom React Frontend
- ระบบ Dynamic Agent Management Platform อยู่ในสถานะพร้อมใช้งาน

### Completed Features
- **Custom React Frontend**: แยก Frontend ออกจาก Chainlit Chat UI โดยสมบูรณ์ (`frontend/`)
- **Platform Dashboard Layout**: Header + Agent Sidebar + Task Grid + Compact Command Console
- **StateMessenger**: Backend ส่ง Platform State ผ่าน JSON Messages แทน Custom Elements
- **Intent Router v2**: Central Secretary แยก CHAT / INFO / TASK ก่อนตัดสินใจ
- **Information Retrieval**: คำถามข้อมูล/สถานะระบบตอบทันที ไม่สร้าง Task Slot
- **Agent Registry**: JSON-backed single source of truth สำหรับ Agent ทั้งหมด
- **Manual Agent Management**: Add/Edit/Delete/Assign Task ผ่าน Sidebar
- **Task Slots**: แต่ละงานมี Slot ของตัวเองบน Dashboard พร้อม Progress Bar และ Result
- **Reusable Execution**: `execute_task_with_agent` ใช้ร่วมกันโดย accept_plan และ assign_task
- ลบ `ProgressStreamer` ที่สร้าง `cl.Step` รกหน้าแชท

### Current Files
- `/Users/its-dev2/my-agent-app/app.py` - Main application logic (Chainlit backend + CrewAI)
- `/Users/its-dev2/my-agent-app/agent_registry.json` - Agent registry data
- `/Users/its-dev2/my-agent-app/SYSTEM_PROTOCOL.md` - Project constitution
- `/Users/its-dev2/my-agent-app/frontend/` - Custom React frontend (Vite + TypeScript + Tailwind)

### Run Commands
```bash
# Backend (Terminal 1)
source venv/bin/activate && chainlit run app.py --watch --host 0.0.0.0 --port 8000

# Frontend (Terminal 2)
cd /Users/its-dev2/my-agent-app/frontend && npm run dev
```

### Notes
- Node.js ติดตั้งภายในโปรเจกต์ที่ `/Users/its-dev2/my-agent-app/.node/`
- Frontend URL: http://localhost:5173
- Backend URL: http://localhost:8000
- **Patch**: แก้ไข `chainlit/socket.py` ใน venv ให้ `user_env_dict` ถูก initialize เป็น `{}` ก่อน conditional block เพื่อแก้ `UnboundLocalError` เวลา WebSocket connect โดยไม่มี user_env
- **Custom Socket.io**: เปลี่ยน `App.tsx` ให้ใช้ `socket.io-client` ตรงๆ แทน `@chainlit/react-client` hooks เพื่อควบคุม connection เองและหลีกเลี่ยง sticky session cookie ปัญหา
- **UUID v4**: เปลี่ยน message ID generation เป็น UUID v4 เพื่อผ่าน Chainlit backend validation
- **Action Fix**: ลบ `value=""` parameter จาก `cl.Action()` ทุกจุด และให้ `accept_plan` รับทั้ง `STATE_CREATING_AGENT` และ `STATE_AWAITING_APPROVAL`
- **UI Overhaul - Agent Sidebar**: แทน `prompt()` ด้วย `AgentFormModal` และ `AssignTaskModal`, เพิ่ม search/filter, avatar colors, expandable cards
- **UI Overhaul - Chat Panel**: เพิ่ม `ChatPanel` component พร้อม chat history, typing indicator, auto-scroll
- **UI Overhaul - Tabs**: เพิ่ม tab switching ระหว่าง Chat และ Tasks ใน `MainLayout`
- **UI Overhaul - Input**: เปลี่ยน `CommandConsole` เป็น multi-line textarea (Enter=send, Shift+Enter=newline)
- **Chat Tracking**: `App.tsx` เก็บ chat history, แปลง notifications เป็น system messages, แปลง task results เป็น assistant messages

### Agentic Architecture Refactor
- **SYSTEM_PROTOCOL.md ข้อ 3**: เปลี่ยนจาก Intent Router 3 หมวดตายตัว → AI Assessor ประเมินเอง + ถาม requirement
- **State Machine**: เพิ่ม `STATE_ASSESSING` และ `STATE_GATHERING_REQUIREMENTS` ลบ `STATE_CHECKING_RESOURCES`
- **CentralSecretary.assess()**: แทนที่ `route()` — AI ประเมินเองว่า chat / info / ask / plan
- **Requirement Gathering Loop**: AI ถาม clarifying questions วนลูปจน requirement ชัด แล้วเข้า planning
- **Multi-Agent Planning**: `analyze()` ปลด hardcode "1 agent only" + "only search_web" → ปล่อยให้ AI กำหนด
- **StateMessenger.set_multi_agent_plan()**: รองรับ plan หลาย agent
- **execute_multi_agent_task()**: รัน Crew หลาย agent แบบ sequential
- **accept_plan handler**: สร้าง + register ทุก agent ใน plan พร้อมกัน
- **Frontend Plan type**: เปลี่ยน `agent: Agent` → `agents: Agent[]`
- **TaskGrid**: แสดง multi-agent plan cards พร้อม role, goal, tools ของแต่ละตัว
- **Conversation History**: เก็บ context ระหว่างการถามตอบเพื่อให้ AI มีบริบท
- **Prompt cleanup**: ลด hardcode rules, ลบ debug logging, ปรับ prompt เป็นอังกฤษทั้งหมด

## 2026-07-02 (Session 2 — Chat UI/UX Refinements)

### Summary
- แก้บั๊ก PlanCard และ ProgressCard ในแชท
- สร้างระบบ multi-chat sessions พร้อมเก็บประวัติแชท
- เพิ่มการเลือก agent เดิมจาก Registry

### Bug Fixes
- **PlanCard buttons**: เพิ่ม `planStatus` ('pending'/'approved'/'rejected') — ปุ่มหายหลังกด + แสดง badge
- **ProgressCard spinner**: เพิ่ม `progressId` (ใช้ `task_id`) — อัปเดต progress แบบ in-place ไม่เพิ่มซ้ำ + หยุด spinner ที่ 100%
- **Progress ไม่ถึง 100%**: เพิ่ม `reply_progress(100, ...)` ก่อน `reply_result` ทั้ง success และ error path
- **Plan กดได้ซ้ำ**: เพิ่ม `update_plan_status()` ใน StateMessenger — อัปเดต planStatus ใน session ที่ persist ไว้
- **Disable input ตอนมี plan**: `CommandConsole` disabled เมื่อ `current_plan` มีค่าหรือ `isProcessing`

### Multi-Chat Sessions
- **ChatStore class**: JSON-backed persistence (`chat_sessions.json`) — create/get/rename/delete/list/add_message
- **ChatSidebar component**: แถบซ้าย — New/Switch/Rename/Delete chat (inline edit, hover actions)
- **StateMessenger integration**: `reply_chat_history`, `reply_chat_sessions`, `persist_message`
- **Action handlers**: `new_chat`, `switch_chat`, `rename_chat`, `delete_chat` ใน `on_message`
- **on_chat_start**: สร้าง default session + ส่ง session list + chat history
- **User message persistence**: บันทึกข้อความ user ลง session ด้วย
- **Auto-title**: ตั้งชื่อ session จากข้อความแรกของ user
- **Frontend parsing**: `parseChatSessionMessage` จัดการ `chat_history` (replace messages) และ `chat_sessions` (update sidebar)

### Task Management
- **Delete task**: เพิ่ม `delete_task` ใน TaskStore + StateMessenger + action handler + ปุ่มใน TaskGrid (มี confirm dialog)
- **Per-agent results**: เพิ่ม `agent_outputs` ใน task — TaskGrid แสดงผลแยกต่อ agent (ชื่อ + role + output)
- **Debug logging**: เพิ่ม `[DEBUG-CREW]` log ใน ExecutionOrchestrator เพื่อตรวจสอบโครงสร้าง `tasks_output`

### Agent Reuse from Registry
- **check_resources()**: เรียกในทั้ง 2 plan flow (STATE_IDLE และ STATE_GATHERING_REQUIREMENTS)
- **Matching logic**: เช็ค role + tools ของ agent เดิมใน Registry ที่ Idle
- **PlanCard badge**: แสดง "Existing" (เขียว) หรือ "New" (ฟ้า) ต่อ agent
- **plan_type**: "existing" ถ้ามีอย่างน้อย 1 agent เดิม, "new" ถ้าทั้งหมดใหม่
- **is_existing flag**: ส่งจาก backend ผ่าน `reply_plan` ไป frontend

### Files Modified
- `app.py` — ChatStore, StateMessenger methods, action handlers, check_resources integration, debug logging
- `frontend/src/App.tsx` — parseChatSessionMessage, chatSessions/activeSessionId state
- `frontend/src/components/ChatPanel.tsx` — planStatus, progressId, is_existing badge
- `frontend/src/components/ChatSidebar.tsx` — (new) session sidebar
- `frontend/src/components/MainLayout.tsx` — ChatSidebar integration, disable input on plan
- `frontend/src/components/TaskGrid.tsx` — delete button, per-agent results
- `frontend/src/components/CommandConsole.tsx` — disabled placeholder text
- `frontend/src/types/platform.ts` — AgentOutput interface, agent_outputs field

## 2026-07-03 (Session 3 — MattPocock Skills Setup)

### Summary
- ติดตั้งและตั้งค่า MattPocock engineering skills สำหรับการทำงาน
- สร้าง domain glossary และ architectural decision records

### Files Created
- `CLAUDE.md` — skills config + Karpathy principles (Think Before Coding, Simplicity First, Surgical Changes, Goal-Driven Execution)
- `CONTEXT.md` — domain glossary: 15 คำศัพท์ (Agent, AgentRegistry, AgentFactory, CentralSecretary, Plan, Task, TaskStore, ChatSession, ChatStore, StateMessenger, ExecutionOrchestrator, Plan Approval, Progress Update, Platform State, Message Types)
- `docs/agents/issue-tracker.md` — local markdown tracker config
- `docs/agents/triage-labels.md` — 5 canonical labels
- `docs/agents/domain.md` — single-context layout
- `docs/adr/0001-local-markdown-issue-tracker.md`
- `docs/adr/0002-chainlit-crewai-architecture.md`
- `docs/adr/0003-json-file-persistence.md`
- `.scratch/` — โฟลเดอร์สำหรับ local issues

### Known Issues (Pending)
- **ผลลัพธ์ agent เหมือนกัน**: มี debug logging รอเทสต์ — ต้องสั่งงานแล้วดู `[DEBUG-CREW]` log
- **User approval ก่อน generate รูป/วิดีโอ**: ยังไม่ได้ทำ (เก็บไว้ทำภายหลัง)
- **ย้ายไป OpenRouter**: ยังไม่ได้ทำ
- **สร้าง git repo**: ยังไม่ได้ทำ

### Current Data
- **Agents**: 5 (Content Planner, Content Creator, Content Scheduling, ContentPlanner, PostingAgent) — ทั้งหมด Idle
- **Tasks**: 2 (เสร็จแล้ว)
- **Chat sessions**: 2

### Image Generation + Approval Flow
- **generate_image tool**: เพิ่มใน ToolRegistry — ใช้ Pollinations.ai (FLUX model, free, ไม่ต้อง API key)
- **Design**: Agent สร้าง prompt → หยุด → user เห็น prompt → approve/reject → gen รูปจริง
- **Tool behavior**: ไม่ gen รูปจริง แค่ return `[IMAGE_GENERATED]` marker + prompt
- **Post-task detection**: `execute_multi_agent_task` เช็ค output ว่ามี `[IMAGE_GENERATED]` → ส่ง image approval card
- **StateMessenger**: เพิ่ม `reply_image_approval()` + `reply_image_result()`
- **Action handlers**: `approve_image` → สร้าง URL + ส่ง image_result, `reject_image` → cancel
- **Frontend ChatPanel**: เพิ่ม `ImageApprovalCard` (purple theme, Generate/Cancel buttons) + `ImageResultCard` (แสดงรูป)
- **App.tsx**: parse `image_approval` + `image_result` message types, optimistic update approvalStatus
- **MainLayout**: pass `onApproveImage`/`onRejectImage` callbacks
- **Pollinations.ai**: URL สร้างรูป on-demand เมื่อ browser เปิด (ไม่ต้อง server-side fetch)

### Bug Fix
- **Fallback agent outputs identical**: แก้ให้ agent แรกได้ `raw`, ที่เหลือได้ `[No individual output captured]` (ไม่ใช้ raw เดียวกันทุกตัว)
- **Image approval card not showing**: Agent มี `generate_image` tool แต่ LLM ไม่เรียกใช้จริง (เพราะ task description ไม่ชัดเจน) ทำให้ไม่มี `[IMAGE_GENERATED]` marker ใน output แก้โดย:
  1. เพิ่มคำสั่งชัดเจนใน `create_task`: "You MUST call the generate_image tool"
  2. เปลี่ยน tool description เป็นภาษาอังกฤษเพื่อให้ LLM เข้าใจดีขึ้น
  3. เพิ่ม fallback detection: ถ้า agent มี `generate_image` ใน tools แต่ไม่เรียกใช้ ให้สกัด output เป็น prompt และส่ง approval card อยู่ดี
- **approve_image หมุนไม่หยุด**: ถ้า `pending_image_{approval_id}` หาย (refresh/session ใหม่) โค้ดเดิมไม่ส่งอะไรกลับ แก้โดยเพิ่ม else ส่ง error message
- **LLM Auto-Fallback**: เพิ่มระบบสลับ LLM อัตโนมัติเมื่อติด rate limit:
  - `LLMManager` มี `_is_in_cooldown()` + `report_rate_limit()` + `_build_llm()`
  - `_is_rate_limit_error()` helper ตรวจจับ 429/rate limit/quota exceeded
  - ทุก catch block หลักเรียก `report_rate_limit()` เพื่อสลับไป fallback provider
  - Cooldown 60 วินาที แล้วกลับใช้ primary อัตโนมัติ
  - `.env.example` เพิ่ม `LLM_FALLBACK_*` config + Gemini Flash setup guide
- **Google AI Studio provider**: เพิ่ม `google` provider ใน `LLMManager._build_llm()` รองรับ Gemini API ผ่าน OpenAI-compatible endpoint (ไม่มี provider prefix)
- **`.gitignore`**: สร้างไฟล์เพื่อป้องกัน `.env` (มี API key) ถูก push ขึ้น git พร้อม ignore `__pycache__`, `venv/`, data files
- **Hierarchical Multi-Agent**: เปลี่ยนจาก `Process.sequential` เป็น `Process.hierarchical`:
  - `AgentFactory.create_manager_agent()` — สร้าง manager agent ที่ `allow_delegation=True` คอยประสานงาน
  - `ExecutionOrchestrator.run_async()` — ใช้ `manager_agent` + `Process.hierarchical`
  - `CentralSecretary.analyze()` — อัปเดต prompt บอก LLM ว่า manager จะประสานงาน ทำขนานได้
  - Worker agents ยัง `allow_delegation=False` ป้องกัน delegation loop
- **Image generation improvements**:
  - `ImageResultCard` — ปุ่ม edit prompt แก้แล้ว regenerate ใหม่ (`edit_image_prompt` action)
  - `TaskGrid` — แสดงรูปที่สร้างใน task แท็บ พร้อมพับ/ขยาย task ได้
  - `StateMessenger.update_task_image()` — บันทึก `image_url` + `image_prompt` ลง task store เมื่อ user อนุมัติรูป

## 2026-07-03

### Summary
- เพิ่ม `FreeModelRotator` — ดึงรายชื่อ `:free` models จาก OpenRouter API แล้วสุ่มลองทีละตัว ข้าม `openrouter/free` router ที่ติด provider Stealth
- แก้ `LLMManager` ใช้ `FreeModelRotator` เมื่อ `LLM_MODEL=openrouter/free` ทั้ง `call_with_fallback` และ `get_llm`
- แก้ double-prefix `openrouter/openrouter/free` → เช็ค `startswith("openrouter/")` ก่อน prepend
- ปรับ fallback จับ error ทุกประเภท (ไม่ใช่แค่ 429) + app-level retry พร้อม backoff

### Changes
- **`FreeModelRotator` class** (`app.py`):
  - `_fetch_free_models()` — GET `/api/v1/models` กรอง `:free` suffix
  - `get_models()` — lazy cache
  - `pick_model()` — สุ่ม model จากลิสต์ (ใช้ใน `get_llm()` สำหรับ CrewAI)
  - `call(prompt, max_attempts)` — สุ่มลองทีละตัว ไม่ซ้ำตัวเดิมในรอบเดียว มี exponential backoff
- **`LLMManager` integration**:
  - `__init__` — สร้าง `FreeModelRotator` เมื่อ provider=openrouter + model=openrouter/free
  - `get_llm()` — ใช้ `rotator.pick_model()` เลือก model สำหรับ CrewAI
  - `call_with_fallback()` — ใช้ `rotator.call()` แทน `_build_llm` + retry loop
- **Tests**: `test_free_model_rotator.py` — 9 tests ครอบคลุม fetch, rotation, exhaustion, pick_model, size filter
- **Size filter**: `_is_large_model()` กรอง models ที่เล็กกว่า 20B ออก (เช่น 3b, 9b, 1.2b, mini, nano, xs) เพื่อให้ cloud AI ฉลาดกว่า local qwen2.5:7b เสมอ

### LLM-Driven Model Assignment
- **`ModelSelector` class** (`app.py`):
  - `_fetch_candidates()` — ดึง model list พร้อม metadata (context_length, pricing, description) จาก OpenRouter API
  - `assign_models(agent_specs, manager_goal)` — ให้ LLM วิเคราะห์และเลือก model ที่เหมาะสมให้แต่ละ agent + manager (smartest สำหรับ manager, task-suited สำหรับ workers)
  - Fallback เป็น random pick ถ้า LLM ตอบผิดหรือล้มเหลว
  - ไม่มี hardcode — ดึง model list สดทุกครั้ง รองรับ free tier และ paid tier
- **`LLMManager.build_llm_for_model(model_id)`** — สร้าง LLM สำหรับ model เฉพาะ (ใช้กับ ModelSelector assignments)
- **`AgentFactory.create_agent(spec, model_id)`** + **`create_manager_agent(..., model_id)`** — รับ model_id จาก ModelSelector
- **`ExecutionOrchestrator.run_async()`** — เรียก `ModelSelector.assign_models()` ครั้งเดียวต่อ plan ส่ง model_id ให้แต่ละ agent
- **Tests**: `test_model_selector.py` — 6 tests ครอบคลุม fetch, valid mapping, invalid id fallback, LLM fail fallback, manager assignment
- **Mattpocock enforcement**: `.windsurf/rules/mattpocock-skills.md` — workspace rule ที่โหลดเข้า context ทุก session อัตโนมัติ ไม่ต้องเตือน
- **Smartest-first rotation**: `pick_smartest_model()` เลือก model ใหญ่สุดสำหรับขั้น assess/analyze (ประตูตัดสินใจ) + `call()` เรียงลำดับตามขนาด ลองตัวใหญ่สุดก่อน ถ้า 429 ค่อยลงตัวถัดไป
- **No randomness in decision path**: `ModelSelector` ใช้ `pick_smartest_model()` ทั้งในการวิเคราะห์และ fallback — ไม่มี `_random_pick` ใน decision path แล้ว ลบ `_random_pick` ออกจาก `ModelSelector` ส่ง `rotator` จาก `ExecutionOrchestrator`
- **Tool descriptions in analyze prompt**: `analyze()` ส่ง tool catalog (name + description) แทนแค่ชื่อ ให้ LLM อนุมานเองว่า agent ไหนใช้ tool ไหน — ไม่มี hardcode tool name ใน prompt
- **Per-agent progress tracking**: `StateMessenger.reply_agent_progress()` ส่ง progress แยกต่อ agent (status + progress + output) อัปเดต in-place by `taskId` — `ExecutionOrchestrator` ส่ง progress ตอนสร้าง agent, `execute_multi_agent_task` ส่ง final progress พร้อม output — Frontend: `AgentProgressCard` ใน ChatPanel + sub-progress bars ใน TaskGrid
- **Free-only model assignment (403 fix)**: `ModelSelector._fetch_candidates()` ใช้ `rotator._models` (free models เท่านั้น) แทนการดึงจาก OpenRouter `/models` ทั้งหมด — ไม่มี paid model เข้า CrewAI อีกต่อไป ป้องกัน 403 daily limit error
- **Typed message schemas**: `schemas/__init__.py` (Pydantic) + `frontend/src/schemas/messages.ts` (TypeScript) — กำหนด contract ระหว่าง backend-frontend `StateMessenger` ใช้ `chat_reply()` helper + Pydantic models แทน dict ล้วน — `App.tsx` ใช้ `ChatReplyEnvelope` + `ChatReplyPayload` typed union แทน `any`
- **Activity log UX**: `ActivityEntry` มี `status: 'current' | 'completed'` — ขั้นตอนที่เสร็จแล้วแสดงติ๊กถูกสีเขียว, ขั้นตอนปัจจุบันแสดง spinner — `addActivity` อัปเดต entry เก่าเป็น completed อัตโนมัติ
- **Backend notifications**: เพิ่ม `notify()` ในทุกขั้นตอนสำคัญ (assess, analyze, model assignment, crew kickoff) — frontend เห็นสถานะ real-time ไม่ค้างที่ "Sending message..."
- **Capability-based tool/model assignment**: `CapabilityRegistry` แทน `ToolRegistry.TOOL_CATALOG` แบบ hardcode — แต่ละ capability บอกว่าเป็น `tool` (เรียก function ภายนอก) หรือ `model_trait` (guide model selection) — `CapabilityResolver` แปลง capabilities → tools + traits สำหรับ agent — `analyze()` prompt ใช้ capability catalog แทน tool catalog — `ModelSelector` รับ capabilities ใน agent list เพื่อเลือก model ที่เหมาะสม — `AgentFactory.create_task` ใช้ `CapabilityRegistry.resolve()` สำหรับ tool instructions — มี 6 capabilities: `search_web`, `generate_image` (tool), `reasoning`, `creative_writing`, `write_code`, `long_context` (model_trait) — Tests: 12 tests ใน `test_capability_registry.py` — Pydantic schemas: `CapabilityItem`, `CapabilityResolution`, `ResolvedAgent` ใน `schemas/__init__.py` — CONTEXT.md อัปเดต domain terms

## 2026-07-04 (Session 4 — Real-time Agent Progress Display)

### Summary
- แทนที่ Progress % ปลอมด้วย Real-time Task Status แสดงสิ่งที่ agent กำลังทำจริง
- เพิ่ม CrewAI Event Listeners จับ event จาก `crewai_event_bus` ส่งไป frontend ทันที
- ปรับ UI จาก Progress Bar → Agent Status Card แสดง task, tool, partial results

### Backend Changes
- **CrewAI Event Imports**: `crewai_event_bus`, `AgentExecutionStartedEvent`, `AgentExecutionCompletedEvent`, `ToolUsageStartedEvent`, `ToolUsageFinishedEvent`, `TaskStartedEvent`, `TaskCompletedEvent`
- **ExecutionOrchestrator**:
  - `_register_event_listeners()` — ลงทะเบียน 5 handlers บน `crewai_event_bus`:
    - `on_agent_started` → agent เริ่มทำงาน, ส่ง task description
    - `on_tool_started` → agent ใช้ tool, ส่ง tool name + description (เช่น "🔍 Searching: ...")
    - `on_tool_finished` → tool เสร็จ, ส่ง output preview (150 ตัวอักษรแรก)
    - `on_task_completed` → task เสร็จ, ส่ง output (200 ตัวอักษรแรก)
    - `on_agent_completed` → agent เสร็จ (fallback ถ้าไม่มี task_completed)
  - `_unregister_event_listeners()` — ล้าง handlers หลัง crew kickoff
  - `_tool_description()` — map tool name → emoji description (🔍 search, 🎨 image)
  - `_match_agent_index()` — match agent_role จาก event กับ agent_specs
  - `_build_progress()` — สร้าง progress list จาก agent_specs + updates dict
  - `run_async()` — เรียก `_register_event_listeners()` ก่อน kickoff, `_unregister` ใน finally
- **StateMessenger.reply_agent_progress()** — ส่ง `current_task`, `current_tool`, `tool_description` ผ่าน `AgentProgressEntry`
- **schemas/__init__.py** — `AgentProgressEntry` เพิ่ม `current_task`, `current_tool`, `tool_description` fields

### Frontend Changes
- **ChatPanel.tsx**:
  - `AgentProgressEntry` interface — เพิ่ม `current_task?`, `current_tool?`, `tool_description?`
  - ลบ `statusIcon` function (ไม่ใช้แล้ว)
  - `toolIcon()` — map tool name → lucide icon (Search, Image, PenTool, Wrench)
  - `AgentStatusRow` (new) — แสดง per-agent status card:
    - Status badge: "Working" (มี tool), "Thinking..." (ไม่มี tool), "Done"
    - Task description แสดงในขณะที่ agent กำลังทำงาน (Brain icon)
    - Tool usage แสดง tool icon + description (เช่น "🔍 Searching: query")
    - Partial output preview (Eye icon, กดเปิด/ปิดได้)
  - `AgentProgressCard` — ปรับให้ใช้ `AgentStatusRow` แทน progress bar เดิม, ลบ overall % display
- **messages.ts** — `AgentProgressEntry` เพิ่ม 3 fields ใหม่
- **types/platform.ts** — `AgentProgress` เพิ่ม 3 fields ใหม่
- **App.tsx** — `parseChatSessionMessage` เพิ่ม `agentProgressTaskId`, `agentProgressOverall`, `agentProgressList` ใน chat history restore

### Files Modified
- `app.py` — CrewAI event imports, ExecutionOrchestrator event listeners, StateMessenger.reply_agent_progress
- `schemas/__init__.py` — AgentProgressEntry new fields
- `frontend/src/components/ChatPanel.tsx` — AgentStatusRow, AgentProgressCard redesign, toolIcon
- `frontend/src/schemas/messages.ts` — AgentProgressEntry new fields
- `frontend/src/types/platform.ts` — AgentProgress new fields
- `frontend/src/App.tsx` — chat history parser includes agent_progress fields

## 2026-07-04 (Session 5 — Consolidate 3 LLM Calls into 1)

### Summary
- รวม `assess()` + `analyze()` + `assign_models()` เป็น LLM call เดียว (`assess_and_plan()`)
- ลดเวลารอจาก 3 LLM calls → 1 call (เร็วขึ้น ~3x)
- เก็บ methods เดิมไว้เป็น fallback

### Backend Changes
- **`CentralSecretary.assess_and_plan()`** (new) — unified call ที่รวม assess + analyze + model assignment ใน prompt เดียว
  - รับ `model_table` และ `valid_model_ids` เพื่อให้ LLM assign model ได้ใน call เดียว
  - คืน JSON ที่มี action + agents (พร้อม model field) + model_assignment
- **`CentralSecretary._parse_unified_response()`** (new) — parse unified response, validate model IDs
- **`ExecutionOrchestrator.run_async()`** — เพิ่ม `pre_assigned_models` parameter
  - ถ้ามี pre-assigned → ข้าม `assign_models()` call
  - ถ้าไม่มี → fall back to `assign_models()` เดิม
- **`on_message` IDLE handler** — ใช้ `assess_and_plan()` แทน `assess()` + `analyze()`
  - สร้าง ModelSelector เพื่อดึง model table ก่อนเรียก
  - เก็บ `pre_assigned_models` ใน user_session
- **`on_message` GATHERING_REQUIREMENTS handler** — ใช้ `assess_and_plan()` แทน `assess()` + `analyze()`
- **Approve handler** — ส่ง `pre_assigned_models` ให้ `run_async()`, ล้างหลังใช้
- **Notification** — เปลี่ยนจาก "🧠 กำลังประเมินความต้องการ..." → "🧠 กำลังประเมินและวางแผน..."

### Async Fix (socket disconnect during LLM calls)
- **Root cause:** LLM calls (`call_with_fallback`, `assign_models`, `_get_candidates`) were sync and blocked the asyncio event loop, preventing websocket ping/pong responses → socket disconnect → frontend "Sending message" stuck
- **`LLMManager.call_async()`** (new) — wraps `call_with_fallback` in `asyncio.run_in_executor()` so event loop stays free
- **All `CentralSecretary` methods** (`assess`, `assess_and_plan`, `chat_response`, `info_response`, `analyze`) — changed to `async def`, use `await self.llm_manager.call_async()`
- **`on_message` handlers** — added `await` to all secretary method calls
- **`ModelSelector._get_candidates()`** — wrapped in `run_in_executor` in both IDLE and GATHERING_REQUIREMENTS handlers
- **`ExecutionOrchestrator.assign_models` fallback** — wrapped in `run_in_executor` in `run_async()`

### Files Modified
- `app.py` — assess_and_plan, _parse_unified_response, run_async, on_message handlers, async LLM calls

## 2026-07-04 (Session 5b — Fix spinner ดับกลางคัน)

### Problem
- Frontend ปิด `isProcessing` ทันทีเมื่อได้ notification เพราะไม่มี running tasks
- ผู้ใช้เห็น spinner หายไปทั้งที่ LLM ยังทำงานอยู่ → คิดว่าระบบค้าง

### Fix
- **`App.tsx`** — ลบ branch ที่ปิด `isProcessing` เมื่อมี notifications (บรรทัด 319-322 เดิม)
- ตอนนี้ `isProcessing` ปิดเฉพาะเมื่อ: ไม่มี running tasks **และ** ไม่มี notifications
- **`app.py` `StateMessenger.reply()`** — clear notifications ก่อนส่ง reply เพื่อให้ frontend ปิด spinner
- **`app.py` `StateMessenger.reply_plan()`** — clear notifications ก่อนส่ง plan เช่นเดียวกัน

### Files Modified
- `frontend/src/App.tsx` — ลบ early isProcessing=false branch
- `app.py` — clear notifications in reply() and reply_plan()

## 2026-07-04 (Session 5c — Fix model ไม่รองรับ tool use)

### Problem
- `nousresearch/hermes-3-llama-3.1-405b:free` ไม่รองรับ tool use แต่ถูก assign ให้ agent ที่มี tools
- Error: "No endpoints found that support tool use" (404)

### Root Cause
- `FreeModelRotator._fetch_free_models()` กรองแค่ size ไม่ได้กรอง tool capability
- OpenRouter API มี field `supported_parameters` ที่บอกว่า model รองรับ `tools` หรือไม่

### Fix
- **`FreeModelRotator._fetch_free_models()`** — เพิ่ม filter `tools` ใน `supported_parameters`
- จาก 23 free models → 18 tool-capable → 10 หลัง size filter
- Models ที่ถูกกรองออก: hermes-3-llama-405b, llama-3.2-3b, dolphin-mistral, lfm-2.5-1.2b-instruct, nemotron-3.5-content-safety

### Files Modified
- `app.py` — `FreeModelRotator._fetch_free_models()` เพิ่ม tool capability filter

## 2026-07-04 (Session 5d — Auto-detect LLM Tier)

### Problem
- ต้องการ priority: paid → free → local → error
- สลับ tier ได้ง่ายแค่เปลี่ยน API key ไม่ต้องแก้ code

### Solution
- **`LLMManager._detect_tier()`** (new) — เรียก OpenRouter `/api/v1/credits` เช็คเครดิต
  - มี credits > 0 → `tier=paid` → ใช้ `LLM_PAID_MODEL`
  - ไม่มี credits → `tier=free` → ใช้ `FreeModelRotator`
  - ไม่มี key → `tier=local` → ใช้ Ollama
- **`call_with_fallback()`** — 3-tier fallback: paid → free → local → RuntimeError
- **`get_llm()`** — เลือก LLM ตาม tier
- **`build_llm_for_model()`** — กรอง model_id ที่ไม่อยู่ใน rotator list (free tier)
- **`on_message` handlers** — เปลี่ยน `provider == "openrouter"` → `tier in ("paid", "free")`
- **`.env.example`** — อัปเดต docs สำหรับ auto-detect

### Files Modified
- `app.py` — `LLMManager` auto-detect tier, `call_with_fallback`, `get_llm`, `build_llm_for_model`
- `.env.example` — อัปเดต documentation

## 2026-07-04 (Session 5e — Parallel Agents + Output Display)

### Changes
1. **Parallel agent execution** — แทน `Process.hierarchical` (ทำทีละคน) ด้วย `asyncio.gather()` รันแต่ละ agent เป็น Crew แยกพร้อมกัน แล้ว Manager synthesize ผลลัพธ์
2. **Output display** — เพิ่ม `max-h` จาก 128px/192px → 384px ใน ChatPanel และ TaskGrid

### Files Modified
- `app.py` — `ExecutionOrchestrator.run_async` เปลี่ยนจาก hierarchical Crew เป็น parallel worker crews + manager synthesis
- `frontend/src/components/ChatPanel.tsx` — `max-h-32` → `max-h-96`
- `frontend/src/components/TaskGrid.tsx` — `max-h-48` → `max-h-96` (2 จุด)

## 2026-07-04 (Session 5f — True Parallel + Manager Fallback)

### Problem
- `akickoff()` อาจเป็น sync wrapper → `asyncio.gather` รันทีละตัว ไม่ parallel จริง
- Manager synthesis เรียก `manager_llm.call()` ตรงๆ → โดน 429 ไม่มี fallback

### Fix
1. **True parallel** — ใช้ `loop.run_in_executor` ครอบ `single_crew.kickoff()` (sync) แต่ละตัว → รันใน thread แยกจริง
2. **Manager fallback** — เปลี่ยน `manager_llm.call()` → `self.llm_manager.call_with_fallback()` → มี fallback paid→free→local

### Files Modified
- `app.py` — `ExecutionOrchestrator.run_async`: `run_in_executor` สำหรับ workers + `call_with_fallback` สำหรับ manager

## 2026-07-04 (Session 5g — Agent 429 Fallback to Local)

### Problem
- CrewAI agents เรียก LLM ตรงๆ ไม่ผ่าน `call_with_fallback` → โดน 429 ไม่ fallback ไป local
- ทุก agent โดน 429 พร้อมกันเพราะ free tier rate limit หมด (50/day)

### Fix
- **`run_single_agent_sync`** — ห่อ `kickoff()` ด้วย try/except ถ้าโดน 429 ให้ trigger cooldown + retry ด้วย local Ollama LLM
- Ollama มี `qwen2.5:7b` และ `llama3.2:3b` ที่รองรับ tools

### Files Modified
- `app.py` — `run_single_agent_sync`: เพิ่ม 429 retry with local fallback LLM

## 2026-07-04 (Session 5h — Thread-safe Progress Callbacks)

### Problem
- Event handlers ทำงานใน thread pool threads แต่ `cl.run_sync()` ไม่ทำงานข้าม thread
- UI ไม่อัปเดตระหว่าง agents ทำงาน — เด้งจาก 0 → 100% ทีเดียว

### Fix
1. **`asyncio.run_coroutine_threadsafe()`** — ส่ง progress update จาก worker thread ไปยัง main event loop
2. **`_async_progress_callback`** — bridge function รัน callback ใน async context
3. **`threading.Lock`** — ป้องกัน race condition ใน state tracking
4. **`update_agent_progress`** — เปลี่ยนเป็น async function

### Files Modified
- `app.py` — `_async_progress_callback` (new), `ExecutionOrchestrator.__init__` (add `_main_loop`, `_state_lock`), `_register_event_listeners` (thread-safe), `run_async` (set `_main_loop`), `execute_multi_agent_task` (async `update_agent_progress`)

## 2026-07-04 (Session 5i — Chainlit Context Fix for Threads)

### Problem
- `cl.Message.send()` ต้องการ Chainlit context var ซึ่งมีเฉพาะใน main thread
- Worker threads (จาก `run_in_executor`) ไม่มี context → error "Chainlit context not found"
- ผล: progress ไม่อัปเดตระหว่างทำงาน เด้ง 0 → 100% ทีเดียว

### Fix
1. **`contextvars.copy_context()`** — copy context จาก main thread ก่อนเริ่ม parallel agents
2. **`loop.call_soon_threadsafe` + `ctx.run()`** — ส่ง progress กลับไป main thread พร้อม context ที่ถูกต้อง
3. **`update_progress`** — แทนที่ `cl.run_sync()` ด้วย context-aware scheduling (2 จุด)

### Files Modified
- `app.py` — import `contextvars`, `ExecutionOrchestrator.__init__` (`_ctx`), `run_async` (capture context), `_send_progress` (use `ctx.run`), `execute_multi_agent_task` + `execute_single_agent_task` (`update_progress` context-aware)

## 2026-07-04 (Session 5j — create_task with context=)

### Problem
- `ctx.run(lambda: asyncio.ensure_future(coro))` สร้าง Task แต่ Task ไม่ได้รับ context → Chainlit context หาย
- `asyncio.ensure_future` ไม่รองรับ `context=` parameter

### Fix
- เปลี่ยนเป็น `loop.create_task(coro, context=ctx)` ทั้ง 3 จุด (`_send_progress`, `update_progress` x2)
- `loop.create_task` รองรับ `context=` ใน Python 3.11 → Chainlit context var ถูกส่งไปยัง coroutine ถูกต้อง

### Files Modified
- `app.py` — `_send_progress`, `update_progress` (2 จุด)

## 2026-07-04 (Session 5k — UI Preview & Toggle State)

### Problem
1. Preview ถูกตัด — backend ส่ง output แค่ 200 chars
2. ปุ่ม Preview/Hide reset ทุกครั้งที่ progress update เพราะ `showOutput` อยู่ใน `AgentStatusRow` ซึ่งถูก unmount/remount

### Fix
1. Backend output limit: 200 → 2000 (final) และ 150/200 → 1500/2000 (progress events)
2. Lift `showOutput` state ขึ้น `AgentProgressCard` ใช้ `Set<string>` เก็บ agent names ที่เปิด preview
3. เปลี่ยน `key={idx}` เป็น `key={agent.name}` ให้ React รักษา state ระหว่าง re-render

### Files Modified
- `frontend/src/components/ChatPanel.tsx` — `AgentStatusRow` (props), `AgentProgressCard` (state + key)
- `app.py` — output preview lengths in `_register_event_listeners` และ final `reply_agent_progress`

## 2026-07-04 (Session 6 — Coroutine Fix & Agent Output Quality)

### Problem
1. `RuntimeWarning: coroutine 'update_agent_progress' was never awaited` — initial progress ส่งไม่ถึง frontend เพราะเรียก coroutine โดยไม่ await
2. Worker agent ตอบเหมือนแชทบอท ("Here are your placeholder images...") เพราะ task description เขียนเหมือนคุยกับ user ไม่ใช่ส่ง report ให้ manager

### Fix
1. **Coroutine fix** (`app.py:1616-1627`): เปลี่ยน `self._agent_progress_callback(initial)` เป็น `main_loop.create_task(callback(initial), context=ctx)` — รูปแบบเดียวกับ `_send_progress` ใน event listeners มี fallback `asyncio.ensure_future` กรณีไม่มี context
2. **Task description fix** (`app.py:1039-1058`): เปลี่ยน `description` จาก `"User request: ..."` เป็น `"Context: A user requested: ..."` + บอกชัดว่า agent เป็น worker ใน multi-agent system, output ไป manager ไม่ใช่ user. เปลี่ยน `expected_output` จาก `"A concise answer..."` เป็น `"A structured deliverable... report to the manager agent"`

### Files Modified
- `app.py` — `create_task` (description + expected_output), `run_async` (initial progress scheduling)

## 2026-07-04 (Session 7 — Image & Video Generation with Tiered Fallback)

### Problem
1. `generate_image` tool แค่คืน marker `[IMAGE_GENERATED]` ไม่ได้สร้างภาพจริง
2. ไม่มี `generate_video` tool ในระบบ
3. ตาม North Star Goal: ต้องใช้ OpenRouter เป็น API หลัก สำหรับ text, image, video

### Implementation
1. **สร้าง `MediaGenerationManager` class** — จัดการ image/video generation แบบ tiered fallback:
   - Tier 1: OpenRouter API (paid) — `POST /api/v1/images`, `POST /api/v1/videos` (async polling)
   - Tier 2: Pollinations.ai (free, no API key) — `GET /image/{prompt}`, `GET /video/{prompt}`
   - Tier 3: Error message — แจ้งว่าติด limit
   - บันทึกไฟล์ลง `public/generated/` แล้วคืน URL
2. **แก้ `generate_image` tool** — เปลี่ยนจาก placeholder เป็นเรียก `MediaGenerationManager.generate_image()` จริง
3. **สร้าง `generate_video` tool** — `@tool` decorator, เรียก `MediaGenerationManager.generate_video()`, รับ parameter `duration` (2-15 วินาที)
4. **ลงทะเบียนใน `ToolRegistry`** — `self.register("generate_video", generate_video)`
5. **เพิ่มใน `CapabilityRegistry`** — `generate_video` capability
6. **เพิ่ม tool instructions** ใน `create_task` สำหรับ `generate_video`
7. **Wire up `_media_gen_manager` global** — ตั้งใน `run_async`, ล้างใน `finally` block
8. **เพิ่ม env var** `POLLINATIONS_API_KEY` ใน `.env.example`

### Files Modified
- `app.py` — `MediaGenerationManager` (new class), `generate_image` (rewrite), `generate_video` (new tool), `ToolRegistry`, `CapabilityRegistry`, `create_task`, `ExecutionOrchestrator.__init__` + `run_async`
- `.env.example` — เพิ่ม `POLLINATIONS_API_KEY`

### Bug Fix (หลังทดสอบ)
- **Pollinations 401 error**: `gen.pollinations.ai/image` และ `/video` คืน 401 เพราะต้องมี API key
- **แก้**: เปลี่ยน image ไปใช้ legacy URL `image.pollinations.ai/prompt/{prompt}` (ไม่ต้อง key), video ต้องมี key (แจ้ง error ชัดเจน)
- **เพิ่ม**: `User-Agent` header, `nologo=true` parameter, env var `OPENROUTER_IMAGE_MODEL`/`OPENROUTER_VIDEO_MODEL`

### Approval-Based Media Generation + OpenRouter API Fix
- **Verify OpenRouter API**: ตรวจสอบกับ docs จริง พบว่า Image API (`POST /api/v1/images`) ถูกต้อง, Video API (`POST /api/v1/videos`) ต้องแก้ polling flow
- **Fix OpenRouter Video**: ใช้ `polling_url` จาก response, เช็ค `unsigned_urls` array, download ผ่าน `/content?index=0` พร้อม Authorization header, จัดการ status `failed` และ `error`
- **Fix default video model**: เปลี่ยนจาก `bytedance/seedance-1-5` เป็น `google/veo-3.1` (มีจริงใน docs)
- **Approval flow ใหม่**: Agent เขียน prompt → tool คืน `[IMAGE_PROMPT_READY]`/`[VIDEO_PROMPT_READY]` → post-execution ส่ง approval card → user เลือก approve/edit/cancel → กด approve แล้ว `MediaGenerationManager` gen จริง
- **เหตุผล**: การ gen image/video ใช้โควต้าเยอะ ต้องให้ user ควบคุมก่อน gen จริง
- **Placeholder video**: ตอน dev/free tier ถ้า Pollinations video ใช้ไม่ได้ จะสร้าง placeholder image (ไม่ใช่ error) เพื่อให้ลูปทำงานครบ ตอน paid tier พัง = error จริง
- **Schema**: เพิ่ม `mediaType` และ `duration` ใน `ChatReplyImageApproval` และ `ChatReplyImageResult`
- **Frontend**: `ImageApprovalCard` และ `ImageResultCard` รองรับ video (แสดง 🎬 label, render `<video>` tag)
- **Session key**: เปลี่ยนจาก `pending_image_` เป็น `pending_media_` รองรับทั้ง image และ video
- **ไฟล์ที่แก้**: `app.py`, `schemas/__init__.py`, `.env.example`, `frontend/src/schemas/messages.ts`, `frontend/src/App.tsx`, `frontend/src/components/ChatPanel.tsx`

### Smoke Test OpenRouter on Free Tier
- **ปัญหา**: ตอน free tier โค้ด OpenRouter image/video path ไม่เคยถูกเรียก → ไม่ยืนยันได้ว่าพอขึ้น paid จะใช้ได้จริง
- **แก้**: เปลี่ยน `generate_image` และ `generate_video` ให้ลองเรียก OpenRouter ก่อนเสมอ (แม้ free tier)
  - ถ้าได้ **402** → log "endpoint verified (402 = no credits)" → fallback ไป Pollinations/placeholder
  - ถ้าได้ **429** → log "rate limited" → fallback
  - ถ้าได้ **error อื่น** → log "⚠️ may need fixing before paid tier" → fallback แต่แจ้งเตือน
  - ถ้าสำเร็จ → ใช้ผลลัพธ์ได้เลย
- **ผล**: โค้ด OpenRouter path ถูก exercise ทุกครั้ง ยืนยันได้ว่า endpoint + format ถูก พอขึ้น paid เปลี่ยนแค่ env

### Fix CentralSecretary task_description (vague → specific)
- **ปัญหา**: task_description กว้างเกินไป เช่น "Generate images based on descriptions provided by the manager" แต่ agents รัน parallel — manager ไม่ได้ส่งคำสั่งมาก่อน
- **ผล**: ImageAgent สร้าง infographic ของ plan แทน content image, VideoAgent ไม่เรียก tool, ImageAgent loop 5 รอบ
- **แก้**: เพิ่มกฎใน prompt ของ CentralSecretary:
  - บอกชัดว่า agents รัน parallel ไม่ได้รอ manager
  - ต้องเขียน task_description ที่ self-contained: สร้างอะไร กี่ชิ้น เรื่องอะไร เรียก tool อะไร
  - ห้ามเขียน "based on manager" หรือ "as directed by manager"
  - มีตัวอย่าง BAD/GOOD ให้ LLM เข้าใจ
- **เพิ่ม**: ใน `create_task` บอกให้เรียก tool "exactly ONCE, do not repeat or loop"

### Fix agent count: remove hard-coded rules, let LLM decide (diagnosing-bugs Phase 1-6)
- **ปัญหา**: CentralSecretary สร้าง 1 ImageAgent + 1 VideoAgent สำหรับโจทย์ "3 วัน" → ไม่พอ และแต่ละ agent ไม่รู้ว่าต้องสร้างกี่ชิ้น
- **ความผิดพลาดก่อนหน้า**: แก้ด้วยการ hard-code "ONE AGENT PER DELIVERABLE ITEM" ใน prompt → ขัดหลัก Reasoning over Workflow
- **แก้ใหม่**: ถอด hard-code ออก ให้ LLM ตัดสินใจเอง:
  - CentralSecretary prompt: "Decide how many agents to create based on the user's request. You may create one agent per item or one agent that handles multiple items — use your judgment."
  - create_task: เปลี่ยน "exactly ONCE" เป็น "once per item you need to create — do not repeat the same call"
  - GOOD example แสดงทั้งแบบ 1 agent หลายชิ้น และ 1 agent 1 ชิ้น

### Fix 4 bugs: missing video approval, garbled prompts, 1-of-3 images, hardcoded model (diagnosing-bugs Phase 1-6)
- **Bug 1 — ไม่มี video approval card**: post-execution อ่าน agent final answer หา `[VIDEO_PROMPT_READY]` แต่ CrewAI กลืน tool result ไปแล้ว → agent ไม่ echo marker กลับมา
- **Bug 2 — กด approve 3 อันได้ 1 รูป**: fallback ส่ง `output_text[:500]` (JSON ทั้งก้อน) เป็น prompt → API สร้างรูปไม่ได้หรือชนกัน
- **Bug 3 — prompt ติดข้อความแปลก**: เช่น "Prompt ready for user approval" ติดมาเพราะ fallback ใช้ agent output ทั้งก้อน
- **Bug 4 — OpenRouter image model hardcode**: `black-forest-labs/flux-1-schnell` ไม่มีใน OpenRouter → 404
- **Root cause 1-3**: โค้ดอ่าน agent final answer แทน tool result โดยตรง
- **แก้ 1-3**: เพิ่ม global `_media_tool_results` list → `generate_image`/`generate_video` append ลงไปตอนถูกเรียก → post-execution อ่านจาก list แทน
- **แก้ 4**: ถอด hardcode default ออก → ถ้า `OPENROUTER_IMAGE_MODEL` ไม่ set จะไม่ส่ง model field ใน API request (OpenRouter ใช้ default เอง)
- **ไฟล์ที่แก้**: `app.py`, `.env.example`

### Fix: agent_name ใน approval card + image tier check
- **ปัญหา 1**: approval card ไม่แสดงชื่อ agent เพราะ tool ไม่รู้ว่าถูกเรียกโดย agent ไหน
- **แก้**: เพิ่ม global `_current_agent_name` → ตั้งค่าก่อน agent รันใน `run_single_agent_sync` → tool อ่านค่านี้ตอน append ลง `_media_tool_results`
- **ปัญหา 2**: `generate_image` ไม่มี tier check — paid tier ทุก API ล้มเหลวแล้ว return error ทั้งหมด แต่ dev/free tier ก็ return error ด้วย (ควรมี placeholder)
- **แก้**: เพิ่ม `_placeholder_image` method + tier check: paid → error, free → placeholder
- **ไฟล์ที่แก้**: `app.py`

### Fix: race condition on agent_name (threading.local)
- **ปัญหา**: ทุก approval card แสดง "by CreativeVideoAgent" ทั้งที่เป็นรูป — เพราะ agents รันใน parallel threads และ `_current_agent_name` เป็น global string → thread สุดท้ายเขียนทับ
- **แก้**: เปลี่ยนจาก global string เป็น `threading.local()` → แต่ละ thread มี `agent_name` ของตัวเอง → ไม่เขียนทับกัน
- **ไฟล์ที่แก้**: `app.py`
- **ปัญหา 1**: local LLM (qwen2.5:7b) บางครั้งเขียน text ที่หน้าตาเหมือน tool call (`brtc{"name": "generate_video", ...}`) แทนการเรียก tool จริง → ไม่มี video approval card
- **แก้**: เพิ่ม fallback ใน post-execution: ถ้า agent มี `generate_video` ใน tools แต่ไม่มี entry ใน `_media_tool_results` → parse agent output หา `"prompt": "..."` pattern → สร้าง approval card จาก prompt ที่หาได้
- **ปัญหา 2**: ไม่มี log จาก approve handler → ไม่รู้สาเหตุที่กด approve 2 อันแล้วได้ 1 รูป
- **แก้**: เพิ่ม `[DEBUG-APPROVE]` print statements ใน approve handler (approval_id, prompt, result, error)
- **ไฟล์ที่แก้**: `app.py`

### Code-review fixes: 3 hard issues
- **Issue 1 — Duplicated approval card logic**: post-execution loop และ video fallback เขียนโค้ดสร้าง approval card ซ้ำกัน → แก้โดย extract `_send_approval_card` helper ใช้จากทั้ง 2 ที่
- **Issue 2 — Video fallback regex กว้างเกินไป**: `re.search(r'"prompt"\s*:\s*"([^"]+)"', ...)` match ทุก `"prompt"` ใน output รวม image prompts → แก้โดยเปลี่ยน regex ให้ match เฉพาะ `"name": "generate_video"` พร้อม `"arguments"` ที่มี `"prompt"`
- **Issue 3 — Approve 2 อันได้ 1 รูป (ต้อง refresh)**: `generate_image()` เป็น sync `requests.post` ที่บล็อก event loop ทั้งหมด → message ที่ 2 ที่ส่งมาระหว่างนั้นถูกค้าง → แก้โดยใช้ `asyncio.to_thread()` รัน sync generation ใน thread pool → event loop ไม่บล็อก → รับ message ที่ 2 ได้ทันที
- **ไฟล์ที่แก้**: `app.py`

### Fix: placeholder 404 + OpenRouter 400 model error + frontend error handling
- **ปัญหา 1 — Placeholder 404**: `_placeholder_image()` และ `_placeholder_video()` คืน URL `/public/generated/placeholder_image.jpg` และ `placeholder_video.jpg` แต่ไม่เคยสร้างไฟล์ → browser ได้ 404 → รูปไม่แสดง + Safari video player errors (`invalid-placard`, `pip-placard`, `airplay-placard`)
- **แก้**: เปลี่ยน placeholder methods ให้สร้าง JPEG จริงด้วย Pillow (ไม่ต้องเรียก API ภายนอก) → บันทึกไฟล์ใน `public/generated/` → browser ได้ไฟล์จริง
- **ปัญหา 2 — OpenRouter 400 ZodError**: เมื่อ `OPENROUTER_IMAGE_MODEL`/`OPENROUTER_VIDEO_MODEL` ว่าง → payload ไม่มี `model` field → API ตอบ 400 `ZodError: expected string for model`
- **แก้**: เพิ่มเงื่อนไข `if self.image_model:` / `if self.video_model:` → ถ้าไม่มี model ให้ skip OpenRouter ไป Pollinations/placeholder เลย → ไม่เสีย API call ไปเปล่า
- **ปัญหา 3 — Frontend ไม่ handle 404/placeholder**: `<img>` และ `<video>` ไม่มี `onError` handler → ถ้าไฟล์ 404 จะแสดง broken image icon
- **แก้**: เพิ่ม `loadError` state + `onError` handler + `isPlaceholder` check → ถ้า placeholder หรือ 404 ให้แสดงข้อความ "generation pending paid tier" แทน broken element
- **ไฟล์ที่แก้**: `app.py`, `frontend/src/components/ChatPanel.tsx`

### Fix: Task แสดงผลลัพธ์ไม่ครบ + output preview หาย + Manager ไม่แสดง progress
- **ปัญหา 1 — Task แสดงแค่รูปล่าสุด**: `update_task_image` เขียนทับ `image_url` ทุกครั้ง → รูปเดิมหาย → แก้โดยเปลี่ยนเป็น append ลง `images` array + แสดงทั้งหมดใน `TaskGrid`
- **ปัญหา 2 — Output preview หายเมื่อ agent อื่นทำงาน**: `_build_progress` สร้าง entry ใหม่ทุกครั้ง → completed agents ไม่มี `output` ใน update → แก้โดยเก็บ `state["outputs"]` และ include output ใน progress updates ของ completed agents
- **ปัญหา 3 — Manager synthesis ไม่มง progress**: Manager step เรียก `llm_manager.call_with_fallback` โดยไม่ส่ง progress update → UI ดูเหมือนค้าง → แก้โดยส่ง progress update ก่อนเริ่ม synthesis (all agents complete + Manager running) + เพิ่ม Manager output ลง `agent_outputs` เพื่อแสดงใน result card
- **ไฟล์ที่แก้**: `app.py`, `frontend/src/components/TaskGrid.tsx`, `frontend/src/App.tsx`, `frontend/src/types/platform.ts`

### Fix: Dedup prompts + local fallback opt-in + sort approval cards + get_task
- **ปัญหา 1 — รูปซ้ำ (5 ใบแทน 3)**: CrewAI retry หลัง LLM error → `generate_image` ถูกเรียกซ้ำ → แก้โดยเพิ่ม prompt hash dedup ใน `generate_image`/`generate_video` — ถ้า prompt ซ้ำ (hash match) จะ skip ไม่ append ลง `_media_tool_results`
- **ปัญหา 2 — Copywriter มีภาษาจีนผสม**: local Ollama (`qwen2.5:7b`) เป็นโมเดลจีน → แก้โดยเพิ่ม `LOCAL_LLM_FALLBACK` env var (default `true` สำหรับ dev) — เมื่อ `false` จะไม่ fallback ไป local และแจ้ง error ตาม PRD (OpenRouter เป็น API เดียว)
- **ปัญหา 3 — Approval cards สลับลำดับ**: parallel execution → tool results มาถึงไม่พร้อมกัน → แก้โดย sort `_media_tool_results` ก่อนส่ง: images ก่อน videos, แต่ละกลุ่มเรียงตาม day number ที่ detect จาก prompt
- **ปัญหา 4 — TaskStore ไม่มี get_task**: `update_task_image` เรียก `get_task` แต่ method ไม่มี → แก้โดยเพิ่ม `get_task(task_id)` ที่ `TaskStore`
- **ปัญหา 5 — Output preview หายเมื่อ agent อื่นทำงาน**: `_build_progress` ไม่ preserve output ของ agent ที่ไม่ได้อยู่ใน update ปัจจุบัน → แก้โดยเพิ่ม `state` parameter และ restore output จาก `state["outputs"]`
- **ไฟล์ที่แก้**: `app.py`, `.env.example`

### Redesign: Dark Canvas + Chat (n8n-inspired)
- **เปลี่ยน theme**: light → dark mode (`bg: #0f1117`, `surface: #1a1d28`, accent indigo-violet gradient) ใน `tailwind.config.js` + `index.css`
- **Layout ใหม่**: เปลี่ยนจาก AgentSidebar + tab switching → **Canvas/Chat toggle** ใน header
  - **Canvas View**: visual node graph (User → Manager → Workers → Output) แสดง agent status, progress, tools แบบ real-time + task list ด้านล่าง
  - **Chat View**: chat messages + plan/approval/result cards (เหมือนเดิมแต่ dark theme)
- **คอมโพเนนต์ใหม่**: `CanvasView.tsx`, `AgentNode.tsx`, `DetailPanel.tsx`
- **คอมโพเนนต์ที่แก้**: `Header.tsx` (toggle + settings), `MainLayout.tsx` (rewrite), `ChatPanel.tsx` (dark theme)
- **คอมโพเนนต์ที่ไม่ใช้แล้ว**: `AgentSidebar.tsx`, `TaskGrid.tsx` (รวมใน CanvasView)
- **ฟีเจอร์ครบ**: Agent CRUD (DetailPanel + Settings), Task management (Canvas), Chat, Media approval, Progress tracking

---

## [2025-07-06] Interactive Canvas Redesign with @xyflow/react

### เป้าหมาย
Redesign UI เป็น 3-column layout: AgentPalette (ซ้าย) | CanvasArea (กลาง, react-flow) | ChatPanelRight (ขวา, resizable) — ยกเลิก toggle Canvas/Chat, ใช้ canvas เป็น primary view

### การเปลี่ยนแปลง
- **ติดตั้ง**: `@xyflow/react@12.11.1` สำหรับ canvas rendering (drag-drop, connect nodes, minimap, controls)
- **คอมโพเนนต์ใหม่**:
  - `AgentPalette.tsx` — sidebar ซ้าย สำหรับ drag agents ไป canvas, แสดง AI suggested agents จาก plan
  - `CanvasArea.tsx` — react-flow canvas กลางจอ, custom node types (agent, system), auto-layout, drag-drop from palette, debounced auto-save
  - `ChatPanelRight.tsx` — chat panel ขวา, resizable (280-600px), toggle ระหว่าง messages และ sessions list, มี input bar ในตัว
- **คอมโพเนนต์ที่แก้**:
  - `Header.tsx` — ลบ Canvas/Chat toggle, เหลือแค่ logo + status + settings
  - `MainLayout.tsx` — rewrite เป็น 3-column layout, จัดการ per-session canvas state, sync กับ backend
  - `App.tsx` — parse canvasState จาก chat_history, ส่ง canvasStateFromBackend ไป MainLayout
- **Backend (app.py)**:
  - `ChatStore.save_canvas_state()` / `get_canvas_state()` — persist canvas state ลง JSON ตาม session
  - `reply_chat_history()` — ส่ง canvasState กลับพร้อม chat history
  - `save_canvas` action handler — รับ canvas state จาก frontend บันทึกลง session
- **คอมโพเนนต์ที่ไม่ใช้ใน MainLayout แล้ว**: `CanvasView.tsx`, `ChatPanel.tsx`, `ChatSidebar.tsx`, `CommandConsole.tsx` (แทนด้วย CanvasArea + ChatPanelRight)
- **ฟีเจอร์ครบ**: Agent CRUD (DetailPanel), drag-drop agents, connect nodes, per-session canvas persistence, resizable chat, session list toggle

---

## [2025-07-06] Canvas as Visual Workflow Dashboard

### เป้าหมาย
Canvas ไม่ใช่แค่แสดง nodes เป็น grid แต่เป็น dashboard แสดง AI workflow แบบ visual — auto-arrange จาก plan, real-time execution, คลิก node ดู output/media

### การเปลี่ยนแปลง
- **`CanvasArea.tsx`** — rewrite auto-arrange + node components:
  - **Auto-arrange from plan**: ดึง `currentPlan` (agents, task_description) มาสร้าง topology User → Manager → [Agents fan-out] → Output (fan-in)
  - **Plan-aware nodes**: Manager node แสดง task_description, agent nodes แสดง goal + tools
  - **Real-time status**: node border/color เปลี่ยนตาม status (pending/running/complete/error), progress bar, current tool, animated edges
  - **Media in nodes**: แสดงรูป/วิดีโอจาก `task.images` ใน agent node เลย
  - **Output preview**: คลิกดู output text ใน node ได้
  - **Quick actions on hover**: Assign Task, Edit, Delete บน node โดยไม่ต้องเปิด DetailPanel
  - **Edge animation**: Manager → Agent animated ขณะ running, Agent → Output animated ขณะ complete
- **`MainLayout.tsx`** — ส่ง `currentPlan`, `tasks`, `onEdit`, `onAssignTask`, `onDelete` ไปยัง CanvasArea
- **`DetailPanel.tsx`** — ย้ายจาก overlay ขวาไปเป็น panel ซ้าย (แทน AgentPalette เมื่อเลือก agent)
- **`ChatPanelRight.tsx`** — session list เป็น dropdown ด้านบน chat แทน toggle mode

---

## [2025-07-06] Canvas Vertical Locked Dashboard + Bug Fixes

### Bug 1: Canvas ไม่อัปเดตเมื่อ plan ปรากฏ
- **สาเหตุ**: `App.tsx:handleStateMessage` เรียก `addChatMessage(reply)` แต่ไม่ได้เรียก `updateState({ current_plan })` — canvas อ่าน `current_plan` จาก PlatformContext ที่ไม่เคยถูก set
- **แก้**: เพิ่ม `planAgentsToAgents()` helper + เรียก `updateState({ current_plan })` เมื่อ plan message มาถึง, และ `updateState({ current_plan: null })` เมื่อ accept/reject plan
- **ไฟล์**: `App.tsx`

### Bug 2: Status แสดง complete จากข้อมูลเก่า
- **สาเหตุ**: `latestProgress` ใน `MainLayout.tsx` หา `agent_progress` ล่าสุดจากทุก messages — ถ้ามี task เก่าที่เสร็จ ข้อมูล status 'complete' จะถูกใช้กับ agent ใหม่
- **แก้**: ตรวจหา plan message ที่อยู่หลัง agent_progress ล่าสุด — ถ้ามี plan ใหม่มาหลัง progress ถือว่า progress เก่า
- **ไฟล์**: `MainLayout.tsx`

### Canvas Vertical + Locked
- เปลี่ยน layout จาก horizontal (User → Manager → Output ซ้ายไปขวา) เป็น vertical (บนลงล่าง)
- ปิด interactivity ที่ไม่จำเป็น: `nodesDraggable={false}`, `nodesConnectable={false}`, `panOnDrag={false}`, `zoomOnScroll={false}`, `zoomOnPinch={false}`, `zoomOnDoubleClick={false}`
- ลบ drag-drop handler และ `Controls` component (ไม่จำเป็นสำหรับ locked dashboard)
- เก็บ `fitView` อัตโนมัติ + `MiniMap`
- **ไฟล์**: `CanvasArea.tsx`

### Feature: Dashed Borders สำหรับ Pending Plan
- เมื่อ plan status = 'pending' → agent nodes มี `border-dashed` (เส้นประ)
- หลัง approve → เปลี่ยนเป็น border ทึบปกติ
- เพิ่ม `planPending` prop ใน `AgentNodeData` และ `CanvasAreaInnerProps`
- ส่งจาก `MainLayout.tsx` (derive จาก last plan message status)
- **ไฟล์**: `CanvasArea.tsx`, `MainLayout.tsx`

## 2026-07-06 (Session 3)

### Summary
- ปรับ canvas ให้ draggable + pan/zoom ได้ แต่ไม่ให้ connect หรือ edit edges
- แก้บัค status แสดง complete ตั้งแต่เริ่ม (stale tasks/progress จาก task เก่า)
- ย้าย image/video approval cards จาก chat ไปที่ agent nodes ใน canvas
- ซ่อน image_approval และ image_result จาก chat (แสดงบน canvas แทน)

### Changes

#### 1. Draggable Nodes + Default Vertical Layout (`CanvasArea.tsx`)
- `nodesDraggable={true}`, `panOnDrag` เปิดใช้งาน
- `nodesConnectable={false}`, `onConnect` no-op (ไม่ให้ลากเส้มเชื่อม)
- แยก auto-arrange effect เป็น 2 ส่วน:
  - Structure effect: สร้าง topology ใหม่เฉพาะเมื่อ plan/agent count เปลี่ยน (ใช้ `structureKey`)
  - Data-update effect: อัปเดต progress/selection/approvals โดยไม่ reset ตำแหน่ง
- `isDraggingRef` ป้องกัน auto-arrange ทับตำแหน่งที่ user ลาก
- `onNodeDragStart`/`onNodeDragStop` สำหรับ track สถานะ dragging

#### 2. Fix Complete-from-Start Bug (`App.tsx`, `MainLayout.tsx`)
- `App.tsx:handleSendCommand` — ล้าง `tasks: []` และ `current_plan: null` เมื่อ user ส่ง message ใหม่
- `MainLayout.tsx:latestProgress` — เพิ่มการตรวจ user message ถ้ามี user message หลัง progress ล่าสุด → ถือว่า progress เก่า

#### 3. Move Generation Approvals to Canvas (`CanvasArea.tsx`, `MainLayout.tsx`)
- `MainLayout.tsx` — derive `pendingApprovals` และ `imageResults` จาก chatMessages
  - `imageResults` cross-reference กับ `image_approval` เพื่อหา `agentName`
- เพิ่ม `PendingApproval` และ `ImageResult` interfaces ใน `CanvasArea.tsx`
- `AgentNodeData` เพิ่ม `pendingApprovals`, `imageResults`, `onApproveImage`, `onRejectImage`, `onEditImagePrompt`
- แสดง approval cards (Generate/Edit/Cancel) ใน agent node
- แสดง generated media (image/video) ใน agent node
- `MainLayout.tsx` — เพิ่ม `handleApproveImage`, `handleRejectImage`, `handleEditImagePrompt` ส่งไปยัง `onAction`

#### 4. Chat Cleanup (`ChatPanel.tsx`)
- ซ่อน `image_approval` และ `image_result` จาก chat (`return null`)
- แสดงเฉพาะ: text messages, plan cards, progress, result, activity log

---

## [2026-07-06] OpenRouter-Only Refactor: AI-Selected Media & Search Models

### เป้าหมาย
ทำให้ระบบใช้ OpenRouter เป็น API ตัวเดียวสำหรับทุกอย่าง (text, image, video, search)
โดย AI เป็นตัวตัดสินใจเลือก model ทั้งหมด — ไม่มี hardcode, ไม่มี DuckDuckGo, ไม่มี Pollinations

### การเปลี่ยนแปลง

#### 1. ModelSelector (`app.py`)
- เพิ่ม `_fetch_all_models()` — ดึง model catalog ทั้งหมดจาก OpenRouter `/models` (free API call)
- เพิ่ม `_build_media_catalog()` — คัดกรอง model ที่รองรับ image/video/search จาก catalog
- ส่ง media catalog เข้าไปใน `assess_and_plan` prompt เดียวกับ text model assignment
- **ไม่เสียเครดิตเพิ่ม** — ใช้ LLM call เดียวกันที่มีอยู่แล้ว

#### 2. CentralSecretary.assess_and_plan (`app.py`)
- เพิ่ม `media_catalog` parameter
- ขยาย JSON schema ใน prompt ให้ AI เลือก `image_model`, `video_model`, `search_model`
- `_parse_unified_response` สกัดค่าทั้ง 3 ออกมาจาก AI response

#### 3. MediaGenerationManager (`app.py`)
- ลบ Pollinations fallback ทั้งหมด (image + video)
- ลบ `POLLINATIONS_*` constants และ `_pollinations_image` / `_pollinations_video` methods
- เพิ่ม `set_models(image_model, video_model)` — รับ model ที่ AI เลือก
- ใช้ OpenRouter เท่านั้น ถ้าไม่มี model → แจ้ง error

#### 4. search_web tool (`app.py`)
- เปลี่ยนจาก DuckDuckGo (DDGS) เป็น OpenRouter chat completion
- ใช้ model ที่ AI เลือก (เช่น perplexity/sonar) ผ่าน `_search_model` global
- ลบ `from ddgs import DDGS` import

#### 5. Wiring (`app.py`)
- ทั้ง 2 call sites (idle flow + reassess flow) ส่ง `media_catalog` ให้ `assess_and_plan`
- เก็บ `ai_image_model`, `ai_video_model`, `ai_search_model` ใน session
- `run_async` อ่านจาก session แล้ว `set_models()` บน `MediaGenerationManager` + `_search_model`
- Approval handler ก็อ่านจาก session เช่นกัน

#### 6. Config cleanup
- `.env.example` — ลบ `POLLINATIONS_API_KEY`, `OPENROUTER_IMAGE_MODEL`, `OPENROUTER_VIDEO_MODEL`
- `SYSTEM_PROTOCOL.md` — อัปเดต Search → OpenRouter (ลบ DuckDuckGo)
- `CapabilityRegistry` — อัปเดต descriptions ให้สะท้อน OpenRouter-only

---

## 2026-07-08

### Routing Model Planning Guard + Streaming Timeout + Empty Response Handling

**Problem:** When user selects `openrouter/free` or `openrouter/auto` as the active model, the planning phase (`CentralSecretary.assess_and_plan`) sends a complex JSON-generation prompt to the routing model. OpenRouter returns HTTP 200 but with an empty SSE stream. The streaming loop has no total timeout, so the UI spinner hangs forever and no error reaches the user. Previous ad-hoc fix silently retried with `openrouter/auto` (paid) — violating "User is the Manager" principle.

**Root cause:** No guard against routing models in the planning path. Routing models (`openrouter/free`, `openrouter/auto`) cannot reliably produce complex JSON output required by the planning prompt. The streaming consumer also lacked a total timeout.

**Changes:**
- **Backend: Routing model guard** (`CentralSecretary.assess_and_plan` in `app.py`): Added check at the top of `assess_and_plan` that rejects `openrouter/free` and `openrouter/auto` before calling the LLM. Returns a user-facing error message telling the user to pick a specific model. Respects user's model choice — does not silently switch to a paid model.
- **Backend: Streaming timeout** (`assess_and_plan` in `app.py`): Added 30s total timeout around the streaming loop so the system cannot hang indefinitely on empty streams.
- **Backend: Empty stream detection** (`LLMManager.call_streaming` in `app.py`): Added `got_content` flag and `timeout=120` on the OpenAI client. If stream completes without yielding any content, logs a warning. Empty response in `assess_and_plan` returns a clear error to the user.
- **Backend: Tool-capable model fallback** (`ExecutionOrchestrator.run_async` in `app.py`): Fixed fallback for routing models with tools — now uses `_get_candidates()` to find a real tool-capable model instead of `_pick_smartest()` which returned another routing model.
- **Frontend: isProcessing reset** (`App.tsx`): Changed logic to `isProcessing = true` only for `progress`/`agent_progress` message types, `false` for everything else. Previously chat replies didn't reset `isProcessing`, causing the spinner to stay on after error messages.
- **Frontend: Model picker always visible** (`ChatPanelRight.tsx`): Removed `{agent.model && (` conditional so model section always shows in plan card, even when model is empty (shows "Auto (system default)"). Pinned model defaults to `openrouter/auto` when empty. `showAutoRouter` always true.
- **Test: Regression test** (`test_routing_model_planning.py`): 4 tests covering: (1) `openrouter/free` rejected before LLM call, (2) `openrouter/auto` rejected before LLM call, (3) empty stream returns error within timeout, (4) default routing model rejected when no user selection.

**Files changed:** `app.py`, `frontend/src/App.tsx`, `frontend/src/components/ChatPanelRight.tsx`, `test_routing_model_planning.py`

## 2026-07-08

### Dynamic OpenRouter Model Discovery — TTS, STT, Vision, Embeddings Support

**Problem:** System only supported text, image, video, and web search models. Model selection used hardcoded keywords (e.g. "sora", "wan", "kling" for video). No support for TTS, STT, Vision analysis, or Embeddings models. Manager AI couldn't plan tasks requiring narration (TTS), transcription (STT), or image analysis (Vision).

**Changes:**

**Backend — New ModelDiscoveryService** (`app.py`):
- **ModelDiscoveryService class**: Deep module that fetches all models from OpenRouter `GET /models?output_modalities=all` and groups them dynamically by `architecture.output_modalities` (text, image, video, audio, embeddings) and `supported_parameters` (web_search → search). No hardcoded keywords.
- **discover_all()**: Returns dict grouped by output modality. Search models identified by `web_search` parameter, not name keywords.
- **discover_input_capabilities()**: Groups by `architecture.input_modalities` — vision (image input), audio_input (STT).
- **get_catalog_summary()**: Text summary for Manager prompt — includes all categories with model IDs.

**Backend — New Capabilities** (`app.py`):
- **CapabilityRegistry**: Added `text_to_speech`, `transcribe_audio`, `analyze_image` as tool-type capabilities.
- **ToolRegistry**: Registered `text_to_speech`, `transcribe_audio`, `analyze_image` tools.

**Backend — New CrewAI Tools** (`app.py`):
- **text_to_speech(text, voice)**: Captures TTS request for user approval, stores in `_media_tool_results` with type "tts".
- **transcribe_audio(audio_url)**: Captures STT request, stores with type "stt".
- **analyze_image(image_url, question)**: Captures vision analysis request, stores with type "vision".
- All tools follow same pattern as `generate_image`/`generate_video` — prompt ready for user approval.

**Backend — MediaGenerationManager** (`app.py`):
- Added `tts_model`, `stt_model`, `vision_model` fields.
- Updated `set_models()` to accept all new model types.
- **ExecutionOrchestrator**: Passes `ai_tts_model`, `ai_stt_model`, `ai_vision_model` from user_session to `set_models()`.

**Backend — Planning Prompt** (`app.py`):
- Updated `assess_and_plan()` prompt: Plan JSON now includes `tts_model`, `stt_model`, `vision_model` fields.
- Design rules mention all tool capabilities including `text_to_speech`, `transcribe_audio`, `analyze_image`.
- Replaced `_build_media_catalog()` calls with `ModelDiscoveryService.get_catalog_summary()` at both plan and reassess sites.
- `fetch_media_catalog` action now uses `ModelDiscoveryService` instead of hardcoded keyword filtering — supports image, video, search, tts, stt, vision types dynamically.
- Plan result parsing stores `ai_tts_model`, `ai_stt_model`, `ai_vision_model` in user_session.
- `reply_plan()` passes new model fields and has_*_tool flags to frontend.

**Backend — Schemas** (`schemas/__init__.py`):
- **ChatReplyPlan**: Added `ttsModel`, `sttModel`, `visionModel`, `hasTtsTool`, `hasSttTool`, `hasVisionTool` fields.

**Frontend — Schemas** (`frontend/src/schemas/messages.ts`):
- **ChatReplyPlan**: Added `ttsModel`, `sttModel`, `visionModel`, `hasTtsTool`, `hasSttTool`, `hasVisionTool` to interface.

**Frontend — ChatMessage** (`frontend/src/components/ChatPanel.tsx`):
- Added `ttsModel`, `sttModel`, `visionModel`, `hasTtsTool`, `hasSttTool`, `hasVisionTool` to ChatMessage interface.

**Frontend — ModelPicker** (`frontend/src/components/ModelPicker.tsx`):
- Added `Volume2`, `Mic`, `FileText` icons for TTS, STT, Embeddings categories.
- Added `input_modalities`, `output_modalities` to `ModelCatalogEntry` interface.
- Added `tts`, `stt`, `vision_analysis`, `embeddings` to `CATEGORY_ICONS`, `CATEGORY_LABELS`, `CATEGORY_ORDER`.

**Frontend — PlanCard** (`frontend/src/components/ChatPanelRight.tsx`):
- Added TTS, STT, Vision model pickers in plan card — same pattern as image/video/search pickers.
- Updated condition to show media models section when any of 6 tool types is present.
- Updated `onChangeMediaModel` prop type to include `ttsModel`, `sttModel`, `visionModel`.
- Passes new props from PlanCard usage to ChatMessage.

**Frontend — App.tsx** (`frontend/src/App.tsx`):
- Updated `change_media_model` handler to support new media types.
- Updated plan message parsing to extract new model fields.

**Tests** (`test_model_discovery.py`, `test_capability_registry.py`):
- 15 new tests for `ModelDiscoveryService`: discover_all() grouping by output_modalities, input_modalities, catalog summary, no hardcoded keywords, OpenRouter routing model exclusion, agent collaboration artifacts.
- 7 new tests for `CapabilityRegistry`: text_to_speech, transcribe_audio, analyze_image resolution, catalog inclusion, tool binding, multi-capability assignment.
- Total: 34 tests, all passing.

**Agent Collaboration:** TTS agent produces audio → Video agent receives it via `depends_on` and can reference it in task_description. Plan JSON supports `tts_model` field when plan uses `text_to_speech` tool. Dependency chain tested in `TestAgentCollaborationArtifacts`.

**Files changed:** `app.py`, `schemas/__init__.py`, `frontend/src/schemas/messages.ts`, `frontend/src/components/ChatPanel.tsx`, `frontend/src/components/ModelPicker.tsx`, `frontend/src/components/ChatPanelRight.tsx`, `frontend/src/App.tsx`, `test_model_discovery.py`, `test_capability_registry.py`

**Design decision:** Routing models are not suitable for deterministic planning prompts that require precise JSON output. The system prevents their use for planning but allows them for simple chat. Users must explicitly choose a concrete model for planning tasks. The system never silently switches the user to a paid model.

### Multimodal Chat Input & Output — File Attach + Audio/Video/File Result Cards

**Problem:** Chat input only accepted text. No way to upload files (images for vision analysis, audio for transcription). No rendering for TTS audio output, STT transcription results, or generic file downloads in the chat stream.

**Changes:**

**Backend — New Schema Models** (`schemas/__init__.py`):
- **ChatReplyAudioResult**: TTS output — `audioUrl`, `audioPrompt`, `voice`, `agentName`, `model`, `taskId`.
- **ChatReplyTranscriptionResult**: STT output — `transcriptionText`, `audioUrl`, `agentName`, `model`, `taskId`.
- **ChatReplyVideoResult**: Video generation output — `videoUrl`, `videoPrompt`, `agentName`, `model`, `taskId`.
- **ChatReplyFileResult**: Generic file output — `fileUrl`, `fileName`, `fileMime`, `agentName`, `taskId`.
- All added to `ChatReplyEnvelope` discriminated union.

**Backend — StateMessenger Methods** (`app.py`):
- `reply_audio_result()`: Sends TTS audio result card to frontend.
- `reply_transcription_result()`: Sends transcription text card.
- `reply_video_result()`: Sends video result card.
- `reply_file_result()`: Sends file download card.
- All persist to chat session for history.

**Backend — File Upload Action** (`app.py`):
- `upload_file` action: Accepts base64 file data + filename + mime type, saves to `public/attachments/` with UUID prefix, returns `file_result` message with URL.

**Frontend — Schemas** (`frontend/src/schemas/messages.ts`):
- Added `audio_result`, `transcription_result`, `video_result`, `file_result` to `ChatMessageType`.
- Added `ChatReplyAudioResult`, `ChatReplyTranscriptionResult`, `ChatReplyVideoResult`, `ChatReplyFileResult` interfaces.
- Added all to `ChatReplyPayload` union.

**Frontend — ChatMessage** (`frontend/src/components/ChatPanel.tsx`):
- Extended `ChatMessage` with `audioUrl`, `audioPrompt`, `voice`, `transcriptionText`, `videoUrl`, `videoPrompt`, `fileUrl`, `fileName`, `fileMime` fields.
- Added new types to `ChatMessageType`.

**Frontend — File Attachment Input** (`frontend/src/components/ChatPanelRight.tsx`):
- Added paperclip button next to send — opens hidden file input accepting `image/*, audio/*, video/*, .pdf, .txt, .json, .csv, .doc, .docx, .md`.
- File size validation: max 20MB.
- Preview bar above textarea: thumbnail for images, icon for audio/video/generic files, with remove (X) button.
- `handleSubmit` now passes attachment data URL to `onSend`.
- `onSend` signature updated to accept optional `attachment` parameter.

**Frontend — Result Cards** (`frontend/src/components/ChatPanelRight.tsx`):
- `audio_result`: `<audio controls>` player with prompt text + agent/model metadata.
- `transcription_result`: Card with transcription text, copy-to-clipboard button, agent/model metadata.
- `video_result`: `<video controls>` player with prompt text + metadata.
- `file_result`: Download link card with file icon, name, mime type, agent name.

**Frontend — App.tsx** (`frontend/src/App.tsx`):
- `parseChatReply()` handles all 4 new message types → creates `ChatMessage` with appropriate fields.
- `handleSendCommand` accepts optional attachment — sends `upload_file` action first, then the text message.

**Frontend — MainLayout.tsx** (`frontend/src/components/MainLayout.tsx`):
- `onSendCommand` prop type updated to accept optional attachment.

**Files changed:** `schemas/__init__.py`, `app.py`, `frontend/src/schemas/messages.ts`, `frontend/src/components/ChatPanel.tsx`, `frontend/src/components/ChatPanelRight.tsx`, `frontend/src/components/MainLayout.tsx`, `frontend/src/App.tsx`
