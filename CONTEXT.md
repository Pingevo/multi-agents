# Context — Domain Glossary

This file defines the domain language for the Dynamic Agent Management Platform.
It is a glossary only — no implementation details, no specs, no scratch notes.

## Terms

### Agent

An AI entity with a role, goal, backstory, and set of tools that performs a specific responsibility within a task. Created by the CentralSecretary from user requests and registered in the AgentRegistry. Has deep persona: personality, expertise, learnings. Brand_context is derived from the Brand of the team the agent belongs to, not stored on the agent.

### AgentRegistry

The single source of truth for all registered agents. Persists agent specifications (name, role, goal, persona, tools, status, model, team_id) to `agent_registry.json`. Agents can be Idle, Busy, or have other statuses. Brand_context is not stored here — it is resolved at runtime via team → brand.

### AgentFactory

Creates CrewAI Agent and Task instances at runtime from agent specs. Bridges the gap between stored registry data and live CrewAI execution. Composes rich backstory from all persona fields via `_build_agent_backstory()`, pulling brand_context from the team's Brand at runtime.

### CentralSecretary

The AI assessor that evaluates user input and decides: chat (answer directly), ask (request more info), or plan (design a multi-agent plan). It also analyzes requirements and designs agent specs.

### Plan

A proposed course of action containing one or more agents and a task description. Presented to the user for approval before execution. A plan can use existing agents from the Registry or propose new ones.

### Task

A unit of work assigned to one or more agents. Tracked in the TaskStore with progress, status, and results. A task progresses through states: running, complete, error, or stopped.

### TaskStore

Persists task records to `task_registry.json`. Each task has an ID, title, assigned agent(s), progress percentage, status, and result.

### ChatSession

A persistent conversation between the user and the platform. Each session has its own message history stored in `chat_sessions.json`. Users can create, rename, switch between, and delete sessions. Sessions can be associated with a team via `team_id`.

### ChatStore

Manages multiple chat sessions with persistence to `chat_sessions.json`. Each session contains a list of messages with roles (user/assistant) and message types (text, plan, progress, result, agent_progress, image_approval, image_result). Also persists `canvas_state`, `settings`, `pending_media`, `media_tool_results`, and `tuning_proposal`.

### StateMessenger

The communication layer between the backend and frontend. Sends structured JSON messages (platform_state, chat_reply, agent_progress, result) over Chainlit WebSocket. Manages platform state, task updates, plan presentation, progress updates, and chat message persistence.

### ExecutionOrchestrator

Runs multi-agent tasks using CrewAI. Creates a Crew with agents and tasks, executes hierarchically with a manager agent coordinating delegation, and extracts per-agent outputs from the CrewOutput. Reports progress via a callback. Implements review loop for quality control.

### Manager Agent

An auto-created agent that coordinates the team during hierarchical execution. Has `allow_delegation=True` and no tools — its job is to delegate tasks to worker agents, run independent tasks in parallel, wait for dependent tasks, synthesize results, and review agent outputs. Created by `AgentFactory.create_manager_agent()`.

### Plan Approval

The gate between planning and execution. When a plan is presented, the user can approve, reject, or cancel. Only after approval do agents get registered (if new) and the task begins execution.

### Progress Update

A real-time update sent during task execution, containing a percentage and status label. Updates are keyed by a progressId (typically the task_id) so the frontend can update in-place rather than appending duplicates.

### Platform State

The full state of the platform sent to the frontend: agents, tasks, current_plan, notifications, and system_status. Sent as a JSON payload over WebSocket whenever state changes.

### Capability

A named ability that an agent can have, such as `search_web`, `generate_image`, `reasoning`, `creative_writing`, `write_code`, or `long_context`. Capabilities are the user-facing language for what an agent can do. Each capability maps to either a tool (external function/API) or a model trait (guides model selection).

### CapabilityRegistry

The single source of truth for all available capabilities. Maps each capability name to its fulfillment strategy: a tool adapter (e.g., `search_web` → DuckDuckGo function) or a model trait (e.g., `reasoning` → `{"strength": "reasoning"}`).

### CapabilityResolver

Resolves capabilities to concrete tools and model traits for agents. Takes agent specs (with capability names) and produces a `ResolvedAgent` with bound tools and model traits. Used by `AgentFactory` during agent creation.

### Brand

A brand that a user manages. Sits between User and Team in the hierarchy: User → Brand → Team → Agent. Holds `brand_context` (tone, target audience, guidelines, forbidden words) as the single source of truth so that all teams under the same brand share one voice. Stored in `brand_registry.json`.
_Avoid_: Label, brand label, brand profile

### BrandRegistry

The single source of truth for all brands owned by a user. Persists brand definitions (name, brand_context, created_at) to `brand_registry.json`. Supports per-user data isolation via `user_id`.

### Team

A group of agents that work together under a Manager agent. Each team belongs to exactly one Brand (`brand_id`). Team holds operational settings (review_iterations, max_retry, model selection) but not brand_context — that lives on the Brand. Stored in `team_registry.json`.
_Avoid_: Group, squad

### TeamRegistry

Manages team definitions with persistence to `team_registry.json`. Each team has a required `brand_id` linking it to a Brand, a manager spec, worker agent specs, and team-level settings. Supports per-user data isolation via `user_id`.

### MediaGenerationManager

Handles generation of images, videos, text-to-speech, and speech-to-text via OpenRouter API. Stores generated media in `data/users/{user_id}/generated/`. Supports an approval flow where agents propose prompts and users approve before generation.

### LLMManager

Manages all LLM API calls through OpenRouter. Handles chat completions, streaming, error recovery, and rate limit detection. Works with ModelRotator for automatic model switching on failures.

### ModelDiscoveryService

Fetches available models from OpenRouter API and checks their capabilities (vision, tools, context length, pricing). Caches results for performance. Used to determine which models support multimodal inputs.

### ModelRotator

Automatically switches to an alternative model when the current model hits rate limits or returns errors. Maintains a fallback chain of models ordered by capability match.

### ModelSelector

Selects the best model for a task based on capability requirements (reasoning, creative, vision, etc.) and pricing constraints. Uses ModelCatalog to find matching models.

### ModelCatalog

A catalog of supported LLM models with their capabilities, pricing, and context lengths. Used by ModelSelector to find the best model for a given task.

### SearchAdapter

The single decision point for web search request format. Checks a model's `supported_parameters` (via ModelDiscoveryService) and selects the correct OpenRouter format: `tools` (server tool) for tools-capable models like Claude/GPT/Gemini, or `web_search_options` (built-in search) for Perplexity models. Hides capability detection, format selection, and HTTP execution behind a small interface. Created to fix the perplexity 404 bug where sending `tools` to a built-in-search model returned "No endpoints found that support tool use".

### Scheduler

Runs recurring tasks on a schedule (daily, weekly, monthly). Uses ScheduledTaskStore for persistence. Runs as a background process alongside the Chainlit server.

### ScheduledTaskStore

Persists scheduled task definitions to `data/users/{uid}/scheduled_tasks.json`. Each scheduled task has a prompt, team_id, schedule config, and enabled flag. Supports per-user data isolation.

### HistoryStore

Handles per-task audit log persistence to `data/users/{user_id}/history_log.json`. Records task execution history, agent actions, and review outcomes. Supports per-user data isolation.

### TemplateStore

Manages task templates that can be reused across sessions. Stored in `data/users/{user_id}/task_templates.json`. Templates contain pre-configured agent specs and task descriptions.

### TaskTemplate

A reusable task definition with pre-configured agent specs, tools, and task description. Can be instantiated as a new task with optional parameter overrides.

### ReviewLoop

The quality control process where the Manager agent reviews worker agent outputs. If output doesn't meet quality standards, feedback is sent back and the agent retries. Tracks `review_round`, `review_summary`, `review_feedback`, and `review_history`. Number of rounds controlled by `review_iterations` setting (0 = unlimited).

### ReviewRound

A single iteration of the review loop. Contains: round number, status (approved/failed), summary, feedback, and output_preview. Stored in `review_history` array on the agent progress entry.

### RetroDesktop

The main frontend component rendering a Windows 95-style retro desktop environment. Contains desktop icons, a taskbar, and draggable windows. Manages window state through WindowManager.

### WindowManager

Manages window lifecycle in the retro desktop: position, z-index, focus, minimize/maximize. Each window type (ChatWindow, TasksWindow, etc.) is registered and can be opened/closed from the taskbar or desktop icons.

### AuthProvider

Pluggable authentication interface. Current implementation: `System81AuthProvider` (OAuth via Sellercenter System81). Supports token-based and username/password authentication. Can be extended for OAuth, LDAP, SAML.

### System81AuthProvider

Authenticates users against the Sellercenter System81 identity service. Supports redirect flow (user redirected to System81 login, returns with token) and direct credentials (backend calls System81 login API). Maps System81 user info to internal User dataclass.

### SessionManager

Creates and verifies session tokens stored in `data/sessions.json` with 7-day TTL. Used by both Chainlit backend (via socket auth) and FastAPI auth server (via REST API).

### UserStore

Stores user profiles in `data/users.json`. Tracks last login, username, email, avatar. Supports per-user data isolation by providing `user_id` to all store classes.

### FastAPI Auth Server

Separate FastAPI application running on port 8001. Serves REST API endpoints for authentication: `/api/auth/login`, `/api/auth/verify`, `/api/auth/logout`, `/api/auth/login-url`. Has CORS middleware for cross-origin requests from the frontend.

### Vite Dev Server

Development server for the React frontend, running on port 5173. Proxies API requests to Chainlit (port 8000) and auth API (port 8001) via `vite.config.ts` proxy configuration. This is the URL users should open in the browser — NOT port 8000.

### Attachment Processing

The pipeline that handles user-uploaded files and URLs. Classifies file types (image, PDF, audio, video, text, DOCX, XLSX, SVG) and URL types (direct file, YouTube, webpage), then converts them to OpenRouter multimodal content blocks or extracted text. Enforces SSRF protection, download size limits (50MB), and text truncation (50K chars).

### Multimodal Content Block

An OpenRouter API content block type: `image_url`, `file`, `input_audio`, or `video_url`. Used to send non-text data to vision/multimodal models. Each block type maps to a specific file category and may require plugins (e.g., PDF file-parser).

### Model Modality Support

Whether a model accepts a specific input type (image, file, audio, video). Checked via `ModelDiscoveryService` before sending multimodal content. If unsupported, the system warns the user and falls back to text extraction or metadata.

### URL Classification

Categorizes URLs by domain and file extension: `youtube` (youtube.com/youtu.be), `image` (.jpg/.png/.gif/.webp), `pdf` (.pdf), `audio` (.mp3/.wav/.ogg), `video` (.mp4/.webm/.mov), `webpage` (default). Determines how `process_url` handles each URL.

### CrewAI Input Files

CrewAI's native file passing mechanism (`input_files` parameter on Task). When `crewai-files` package is available, attachment files are wrapped as CrewAI File objects and passed directly to worker agents. Falls back to text injection in task description if unavailable.

## Message Types

- **text** — plain text message (user or assistant)
- **plan** — plan card with agents, task description, and plan type
- **progress** — progress bar with percentage and label
- **result** — task result with per-agent outputs
- **agent_progress** — per-agent progress with status, output, review data (review_round, review_summary, review_feedback, review_history)
- **image_approval** — image generation approval card with prompt, agent name, and approval status
- **image_result** — generated image display with URL and prompt
- **chat_history** — full message history for a session (sent on session switch)
- **chat_sessions** — list of all sessions with active session ID

### AI Usage Hub

Central logging service at `https://digital.in.th` สำหรับ tracking การใช้ AI/scraping provider แบบรวมศูนย์ — ทุกโปรเจกต์ยิง log ไปจุดเดียว หัวหน้าดู dashboard ที่ `https://digital.in.th/ai-usage`

**คำศัพท์:**
- **`log_ai_usage(entry)`** — ฟังก์ชันหลักใน `backend/ai_usage_hub.py` ยิง HTTP POST ไป Hub แบบ fire-and-forget (daemon thread, ไม่ throw)
- **`provider`** — ชื่อ provider ที่เรียก (`openrouter`, `ollama`, `apify`, `9arm`) — บังคับส่งทุกครั้ง
- **`analysis_type`** — ประเภทงาน (`chat`, `media`, `search`, `agent`) ส่งใน `metadata.analysis_type` เพื่อ filter ใน dashboard
- **`user` vs `reference`** — `user` = ใครสั่ง (actor, เช่น user_id), `reference` = เรื่องอะไร (subject, เช่น session_id) — ตั้งใน contextvar ที่ `chat.py` ไม่ใช่ในแต่ละ call site
- **`cost_usd`** — ราคาจริงจาก provider (`usage.cost` ของ OpenRouter) ห้ามประมาณ
- **`request_id`** — id ที่ provider คืนมา (generation id) ใช้เป็น idempotency key ได้

**กฎสำคัญ:** ทุก call site ที่เรียก AI provider ต้อง log ทั้ง success และ error path — ไม่มี exception (ดู `SYSTEM_PROTOCOL.md` section 15)
