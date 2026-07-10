# Context — Domain Glossary

This file defines the domain language for the Dynamic Agent Management Platform.
It is a glossary only — no implementation details, no specs, no scratch notes.

## Terms

### Agent

An AI entity with a role, goal, backstory, and set of tools that performs a specific responsibility within a task. Created by the CentralSecretary from user requests and registered in the AgentRegistry.

### AgentRegistry

The single source of truth for all registered agents. Persists agent specifications (name, role, goal, persona, tools, status) to `agent_registry.json`. Agents can be Idle, Busy, or have other statuses.

### AgentFactory

Creates CrewAI Agent and Task instances at runtime from agent specs. Bridges the gap between stored registry data and live CrewAI execution.

### CentralSecretary

The AI assessor that evaluates user input and decides: chat (answer directly), ask (request more info), or plan (design a multi-agent plan). It also analyzes requirements and designs agent specs.

### Plan

A proposed course of action containing one or more agents and a task description. Presented to the user for approval before execution. A plan can use existing agents from the Registry or propose new ones.

### Task

A unit of work assigned to one or more agents. Tracked in the TaskStore with progress, status, and results. A task progresses through states: running, complete, or error.

### TaskStore

Persists task records to `task_registry.json`. Each task has an ID, title, assigned agent(s), progress percentage, status, and result.

### ChatSession

A persistent conversation between the user and the platform. Each session has its own message history stored in `chat_sessions.json`. Users can create, rename, switch between, and delete sessions.

### ChatStore

Manages multiple chat sessions with persistence to `chat_sessions.json`. Each session contains a list of messages with roles (user/assistant) and message types (text, plan, progress, result).

### StateMessenger

The communication layer between the backend and frontend. Sends structured JSON messages (platform_state, chat_reply) over Chainlit WebSocket. Manages platform state, task updates, plan presentation, progress updates, and chat message persistence.

### ExecutionOrchestrator

Runs multi-agent tasks using CrewAI. Creates a Crew with agents and tasks, executes hierarchically with a manager agent coordinating delegation, and extracts per-agent outputs from the CrewOutput. Reports progress via a callback.

### Manager Agent

An auto-created agent that coordinates the team during hierarchical execution. Has `allow_delegation=True` and no tools — its job is to delegate tasks to worker agents, run independent tasks in parallel, wait for dependent tasks, and synthesize results. Created by `AgentFactory.create_manager_agent()`.

### Plan Approval

The gate between planning and execution. When a plan is presented, the user can approve, reject, or cancel. Only after approval do agents get registered (if new) and the task begins execution.

### Progress Update

A real-time update sent during task execution, containing a percentage and status label. Updates are keyed by a progressId (typically the task_id) so the frontend can update in-place rather than appending duplicates.

### Platform State

The full state of the platform sent to the frontend: agents, tasks, current_plan, notifications, and system_status. Sent as a JSON payload over WebSocket whenever state changes.

### Capability

A named ability that an agent can have, such as `search_web`, `generate_image`, `reasoning`, `creative_writing`, `write_code`, or `long_context`. Capabilities are the user-facing language for what an agent can do. Each capability maps to either a tool (external function/API) or a model trait (guides model selection).

### CapabilityRegistry

The single source of truth for all available capabilities. Maps each capability name to its fulfillment strategy: a tool adapter (e.g., `search_web` → DuckDuckGo function) or a model trait (e.g., `reasoning` → `{"strength": "reasoning"}`). Replaces the hardcoded `ToolRegistry.TOOL_CATALOG`.

### CapabilityResolver

Resolves capabilities to concrete tools and model traits for agents. Takes agent specs (with capability names) and produces a `ResolvedAgent` with bound tools and model traits. Used by `AgentFactory` during agent creation.

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
- **image_approval** — image generation approval card with prompt, agent name, and approval status
- **image_result** — generated image display with URL and prompt
- **chat_history** — full message history for a session (sent on session switch)
- **chat_sessions** — list of all sessions with active session ID
