"""ExecutionOrchestrator — wave-based parallel agent execution."""

import asyncio
import contextvars
import json
import os
import re
import threading
import uuid
import traceback
import chainlit as cl
import litellm
from litellm.integrations.custom_logger import CustomLogger
from crewai import Agent, Task, Crew, Process, LLM
from crewai.events import crewai_event_bus
from crewai.events.types.agent_events import AgentExecutionStartedEvent, AgentExecutionCompletedEvent
from crewai.events.types.tool_usage_events import ToolUsageStartedEvent, ToolUsageFinishedEvent
from crewai.events.types.task_events import TaskStartedEvent, TaskCompletedEvent
from crewai.events.types.llm_events import LLMCallCompletedEvent
from crewai.events import event_types
from backend.globals import _progress_callback, _media_tool_results, _thread_local, _search_model, user_prompt_ctx
from backend.utils import _sanitize_error, _debug
from backend.llm.manager import LLMManager, _is_rate_limit_error
from backend.llm.selector import ModelSelector
from backend.media.manager import MediaGenerationManager
from backend.agents.factory import AgentFactory
from backend.agents.tool_registry import ToolRegistry
from backend.agents.registry import AgentRegistry
from backend.agents.templates import validate_template_output, detect_template_id, get_template_contract
from backend.core.messenger import StateMessenger
from backend.credit_logger import log_llm_call

MAX_REVIEW_RETRIES = int(os.environ.get("MAX_REVIEW_RETRIES", "3"))


# --- LLM call logging context (shared between CrewAI events and litellm callback) ---
_llm_call_context: dict[str, str] = {}

def set_llm_call_context(caller: str):
    """Set context for the next LLM call (e.g. 'manager_review:round2', 'agent:Writer#1')."""
    _llm_call_context[threading.get_ident()] = caller

def clear_llm_call_context():
    _llm_call_context.pop(threading.get_ident(), None)


# --- LiteLLM global success callback (captures ALL LLM calls including CrewAI internals) ---
class LiteLLMCallLogger(CustomLogger):
    def log_success_event(self, kwargs, response_obj, start_time, end_time):
        try:
            model = getattr(response_obj, "model", "") or kwargs.get("model", "unknown")
            usage = getattr(response_obj, "usage", None)
            if not usage:
                usage = kwargs.get("usage", {})
            ctx = _llm_call_context.get(threading.get_ident(), "")
            caller = ctx or "litellm"
            user_prompt = user_prompt_ctx.get("") or getattr(_thread_local, "user_prompt", "")
            if usage:
                print(f"[LITELLM-EVENT] model={model}, caller={caller}, usage={usage}", flush=True)
            log_llm_call(model, usage, caller=caller, prompt_preview="", user_prompt=user_prompt)
        except Exception as e:
            print(f"[LITELLM-EVENT] Callback error: {e}", flush=True)

_litellm_logger = LiteLLMCallLogger()
if _litellm_logger not in litellm.success_callback:
    litellm.success_callback.append(_litellm_logger)


# --- CrewAI event bus logging (kept as backup) ---
def _on_llm_call_completed(event: LLMCallCompletedEvent):
    """Log CrewAI LLM calls via event bus (backup for litellm callback)."""
    usage = event.usage or {}
    model = event.model or "unknown"
    agent_role = getattr(event, "agent_role", None) or ""
    task_name = getattr(event, "task_name", None) or ""
    ctx = _llm_call_context.get(threading.get_ident(), "")
    caller = ctx or (f"agent:{agent_role}" if agent_role else "crewai")
    if task_name:
        caller += f":{task_name[:50]}"
    user_prompt = user_prompt_ctx.get("") or getattr(_thread_local, "user_prompt", "")
    if not usage:
        print(f"[LLM-EVENT] No usage data for model={model}, caller={caller}", flush=True)
    else:
        print(f"[LLM-EVENT] model={model}, caller={caller}, usage={usage}", flush=True)
    log_llm_call(model, usage, caller=caller, prompt_preview="", user_prompt=user_prompt)

crewai_event_bus.on(LLMCallCompletedEvent)(_on_llm_call_completed)

async def _async_progress_callback(sync_callback, progress_data):
    """Bridge: run progress callback in async context for run_coroutine_threadsafe."""
    result = sync_callback(progress_data)
    if asyncio.iscoroutine(result):
        await result


class ExecutionOrchestrator:
    """รวม Agent Factory เพื่อรัน Crew แบบ Dynamic โดยไม่สร้าง Chat Log รก"""

    def __init__(
        self,
        llm_manager: LLMManager,
        tool_registry: ToolRegistry,
        progress_callback=None,
        agent_progress_callback=None,
    ):
        self.llm_manager = llm_manager
        self.tool_registry = tool_registry
        self.agent_factory = AgentFactory(llm_manager, tool_registry)
        self._progress_callback = progress_callback
        self._agent_progress_callback = agent_progress_callback
        self._media_gen_manager = MediaGenerationManager(llm_manager)
        self._event_handlers: list[tuple] = []
        self._agent_specs: list[dict] = []
        self._main_loop: asyncio.AbstractEventLoop | None = None
        self._state_lock = __import__("threading").Lock()
        self._ctx: contextvars.Context | None = None
        self.skip_review_agents: set[str] = set()
        self.model_selector: ModelSelector | None = None
        if llm_manager._is_openrouter():
            self.model_selector = ModelSelector(
                llm_manager.api_key, llm_manager.base_url, llm_manager.temperature,
                rotator=None,
                default_model=llm_manager._default_model,
            )

    _TOOL_DESCRIPTIONS = {
        "generate_image": "🎨 Preparing image generation...",
    }

    @staticmethod
    def _clean_agent_output(output: str) -> str:
        """Strip CrewAI internal markers and box-drawing noise from agent output."""
        if not output:
            return output
        # Remove box-drawing characters used by CrewAI verbose logs
        cleaned = re.sub(r'[\u2500-\u257F]', '', output)
        # Remove common internal markers/sections
        markers = [
            "Crew Execution Started",
            "Crew Execution Completed",
            "Task Started",
            "Task Completed",
            "Agent Final Answer",
            "Final Answer:",
            "Final Deliverable:",
            "Tracing is disabled.",
            "To enable tracing",
            "crewai traces enable",
        ]
        for marker in markers:
            cleaned = cleaned.replace(marker, "")
        # Trim leading/trailing whitespace and collapse multiple blank lines
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned.strip())
        return cleaned

    def _tool_description(self, tool_name: str, tool_args: dict | str) -> str:
        desc = self._TOOL_DESCRIPTIONS.get(tool_name, f"⚙️ Using {tool_name}...")
        if tool_name == "generate_image" and isinstance(tool_args, dict):
            prompt = tool_args.get("prompt", "")
            if prompt:
                return f"🎨 Image prompt: {prompt[:60]}"
        return desc

    def _match_agent_index(self, agent_role: str | None) -> int:
        if not agent_role:
            return -1
        for i, spec in enumerate(self._agent_specs):
            if spec.get("role", "").lower() in agent_role.lower() or agent_role.lower() in spec.get("role", "").lower():
                return i
            if spec.get("name", "").lower() in agent_role.lower() or agent_role.lower() in spec.get("name", "").lower():
                return i
        return -1

    def _build_progress(self, updates: dict[int, dict], agent_state: dict[int, dict] | None = None) -> list[dict]:
        result = []
        for i, spec in enumerate(self._agent_specs):
            # Start from persistent state if available, else from defaults
            if agent_state and i in agent_state:
                entry = dict(agent_state[i])
            else:
                entry = {
                    "name": spec.get("name", "Agent"),
                    "role": spec.get("role", ""),
                    "status": "pending",
                    "progress": 0,
                    "model": spec.get("model", ""),
                }
            # Apply new updates on top
            if i in updates:
                entry.update(updates[i])
            result.append(entry)
        return result

    def _register_event_listeners(self):
        # Persistent per-agent state — accumulates all fields across updates
        self._agent_state: dict[int, dict] = {}

        def _has_media_tool(idx: int) -> bool:
            if idx >= len(self._agent_specs):
                return False
            tools = self._agent_specs[idx].get("tools", [])
            return any("image" in str(t).lower() or "video" in str(t).lower() or "generate" in str(t).lower() for t in tools)

        def _merge_and_send(updates: dict[int, dict]):
            """Merge updates into persistent state, then send full progress."""
            if not self._agent_progress_callback or not self._main_loop or not self._ctx:
                return
            with self._state_lock:
                for idx, upd in updates.items():
                    if idx not in self._agent_state:
                        self._agent_state[idx] = {
                            "name": self._agent_specs[idx].get("name", "Agent") if idx < len(self._agent_specs) else "Agent",
                            "role": self._agent_specs[idx].get("role", "") if idx < len(self._agent_specs) else "",
                            "status": "pending",
                            "progress": 0,
                            "model": self._agent_specs[idx].get("model", "") if idx < len(self._agent_specs) else "",
                        }
                    self._agent_state[idx].update(upd)
                progress = self._build_progress({}, self._agent_state)
            ctx = self._ctx
            loop = self._main_loop
            callback = self._agent_progress_callback

            def _schedule():
                loop.create_task(
                    _async_progress_callback(callback, progress),
                    context=ctx,
                )

            loop.call_soon_threadsafe(_schedule)

        def on_agent_started(source, event: AgentExecutionStartedEvent):
            idx = self._match_agent_index(event.agent_role)
            if idx >= 0:
                task_desc = ""
                delegated_by = []
                if idx < len(self._agent_specs):
                    task_desc = self._agent_specs[idx].get("task_description", "")
                    deps = self._agent_specs[idx].get("depends_on", [])
                    if deps:
                        delegated_by = deps
                upd = {"status": "running", "progress": 30, "current_task": task_desc, "current_tool": "", "tool_description": ""}
                if delegated_by:
                    upd["delegated_by"] = delegated_by
                _merge_and_send({idx: upd})

        def on_tool_started(source, event: ToolUsageStartedEvent):
            idx = self._match_agent_index(event.agent_role)
            if idx >= 0:
                tool_desc = self._tool_description(event.tool_name, event.tool_args)
                _merge_and_send({idx: {"status": "running", "progress": 50, "current_tool": event.tool_name, "tool_description": tool_desc}})

        def on_tool_finished(source, event: ToolUsageFinishedEvent):
            idx = self._match_agent_index(event.agent_role)
            if idx >= 0:
                output_preview = str(event.output)[:5000] if event.output else ""
                _merge_and_send({idx: {"status": "running", "progress": 70, "current_tool": "", "tool_description": "", "tool_output": output_preview}})

        def on_task_completed(source, event: TaskCompletedEvent):
            idx = self._match_agent_index(event.agent_role)
            if idx >= 0:
                output_raw = ""
                if hasattr(event, "output") and event.output:
                    output_raw = getattr(event.output, "raw", str(event.output))[:8000]
                if _has_media_tool(idx):
                    _merge_and_send({idx: {"status": "waiting_approval", "progress": 100, "current_task": "", "current_tool": "", "tool_description": "", "output": output_raw}})
                else:
                    _merge_and_send({idx: {"status": "running", "progress": 90, "current_task": "Preparing for review", "current_tool": "", "tool_description": "", "output": output_raw}})

        def on_agent_completed(source, event: AgentExecutionCompletedEvent):
            idx = self._match_agent_index(event.agent_role)
            if idx >= 0:
                if _has_media_tool(idx):
                    upd = {"status": "waiting_approval", "progress": 100, "current_task": "", "current_tool": "", "tool_description": ""}
                else:
                    upd = {"status": "running", "progress": 90, "current_task": "Preparing for review", "current_tool": "", "tool_description": ""}
                _merge_and_send({idx: upd})

        def on_llm_stream_chunk(source, event):
            agent_role = getattr(event, "agent_role", None)
            chunk = getattr(event, "chunk", "")
            call_type = getattr(event, "call_type", None)
            # Only capture LLM_CALL chunks as thinking text, not TOOL_CALL
            if call_type and str(call_type) != "LLMCallType.LLM_CALL" and "tool" in str(call_type).lower():
                return
            if not chunk:
                return
            # CrewAI often sends agent_role=None in stream chunks — use thread_local fallback
            if not agent_role:
                agent_role = getattr(_thread_local, "agent_name", None)
                if not agent_role:
                    return
                _debug(f"[STREAM-CHUNK] agent_role was None, using thread_local fallback: {agent_role!r}", flush=True)
            idx = self._match_agent_index(agent_role)
            if idx < 0:
                _debug(f"[STREAM-CHUNK] No match for agent_role={agent_role!r}, specs={[s.get('role') for s in self._agent_specs]}", flush=True)
                return
            with self._state_lock:
                prev_thinking = self._agent_state.get(idx, {}).get("thinking", "")
                new_thinking = (prev_thinking + chunk)[:2000]
            _merge_and_send({idx: {"thinking": new_thinking}})

        handlers = [
            (AgentExecutionStartedEvent, on_agent_started),
            (ToolUsageStartedEvent, on_tool_started),
            (ToolUsageFinishedEvent, on_tool_finished),
            (TaskCompletedEvent, on_task_completed),
            (AgentExecutionCompletedEvent, on_agent_completed),
            (event_types.LLMStreamChunkEvent, on_llm_stream_chunk),
        ]
        for event_type, handler in handlers:
            crewai_event_bus.on(event_type)(handler)
            self._event_handlers.append((event_type, handler))

    def _unregister_event_listeners(self):
        for event_type, handler in self._event_handlers:
            try:
                crewai_event_bus.off(event_type, handler)
            except Exception:
                pass
        self._event_handlers.clear()

    async def run_async(
        self,
        user_input: str,
        agent_specs: list[dict],
        pre_assigned_models: dict | None = None,
        task_id: str | None = None,
        task_title: str | None = None,
        messenger: StateMessenger | None = None,
    ) -> dict:
        global _progress_callback, _media_gen_manager, _media_tool_results, _search_model
        _progress_callback = self._progress_callback
        _media_gen_manager = self._media_gen_manager
        _media_tool_results = []  # Reset for this run
        total = len(agent_specs)
        self._agent_specs = agent_specs
        # Store task context for LLM call logging
        _thread_local.user_prompt = user_input[:200]
        user_prompt_ctx.set(user_input[:200])

        # Set AI-selected media/search models for this run
        ai_image_model = cl.user_session.get("ai_image_model") or ""
        ai_video_model = cl.user_session.get("ai_video_model") or ""
        ai_search_model = cl.user_session.get("ai_search_model") or ""
        ai_tts_model = cl.user_session.get("ai_tts_model") or ""
        ai_stt_model = cl.user_session.get("ai_stt_model") or ""
        ai_vision_model = cl.user_session.get("ai_vision_model") or ""
        self._media_gen_manager.set_models(
            image_model=ai_image_model, video_model=ai_video_model,
            tts_model=ai_tts_model, stt_model=ai_stt_model, vision_model=ai_vision_model,
        )
        _search_model = ai_search_model

        # Use pre-assigned models from unified call, or fall back to LLM assignment
        _selected_model = cl.user_session.get("selected_model") or ""
        if pre_assigned_models and pre_assigned_models.get("workers"):
            model_assignment = pre_assigned_models
            # Force manager model = user's top-bar selection (overrides any stale value)
            if _selected_model:
                model_assignment["manager"] = _selected_model
            print(f"[ExecutionOrchestrator] Using pre-assigned models: {model_assignment}", flush=True)
        else:
            model_assignment = {"manager": "", "workers": {}}
            if self.model_selector:
                try:
                    loop = asyncio.get_event_loop()
                    model_assignment = await loop.run_in_executor(
                        None,
                        lambda: self.model_selector.assign_models(
                            agent_specs, manager_goal=user_input
                        )
                    )
                except Exception as e:
                    print(f"[ExecutionOrchestrator] ModelSelector error: {e}")
            # Force manager model = user's top-bar selection
            if _selected_model:
                model_assignment["manager"] = _selected_model

        self._main_loop = asyncio.get_event_loop()
        self._ctx = contextvars.copy_context()
        self._register_event_listeners()

        # History logging context
        _hist_task_id = task_id or str(uuid.uuid4())[:8]
        _hist_task_title = task_title or user_input[:80]
        _hist_messenger = messenger
        if _hist_messenger:
            _hist_messenger._main_loop = self._main_loop

        def _log_hist(actor, action, target=""):
            if _hist_messenger:
                try:
                    _hist_messenger.log_history(_hist_task_id, _hist_task_title, actor, action, target)
                except Exception:
                    pass

        # Log plan creation
        _log_hist("Manager", f"แบ่งงาน {len(agent_specs)} agents")

        # Resolve actual model names: if model is "" (adaptive), find what get_llm() would pick
        for i, spec in enumerate(agent_specs):
            agent_name = spec.get("name", "")
            worker_model = model_assignment["workers"].get(agent_name, "")
            print(f"[DEBUG-MODEL-RESOLVE] agent={agent_name}, worker_model={worker_model!r}, pre_assigned={model_assignment}", flush=True)
            if not worker_model:
                # Auto-routing — find what the routing/user-selected model actually is
                resolved = self.llm_manager.get_selected_model_name()
                model_assignment["workers"][agent_name] = resolved
                spec["model"] = resolved
                worker_model = resolved
            spec["model"] = worker_model
        # Also resolve manager model
        if not model_assignment.get("manager"):
            model_assignment["manager"] = self.llm_manager.get_selected_model_name()

        print(f"[ExecutionOrchestrator] Resolved models: {model_assignment}", flush=True)
        for i, spec in enumerate(agent_specs):
            print(f"[ExecutionOrchestrator] Agent {i} '{spec.get('name', '')}' model={spec.get('model', '')!r}", flush=True)

        try:
            agents = []
            tasks = []
            for i, spec in enumerate(agent_specs):
                worker_model = model_assignment["workers"].get(spec.get("name", ""), "")
                agent = self.agent_factory.create_agent(spec, model_id=worker_model)
                task = self.agent_factory.create_task(agent, spec, user_input)
                agents.append(agent)
                tasks.append(task)
                tool_names = [getattr(t, "name", str(t)) for t in agent.tools]
                _debug(f"[DEBUG] Agent: {agent.role}, tools: {tool_names}")

                if self._progress_callback:
                    pct = int((i / total) * 100)
                    self._progress_callback(pct, f"Agent {i+1}/{total}: {spec.get('name', '')} starting...")

            # Send initial progress: all pending with task descriptions
            if self._agent_progress_callback:
                initial = self._build_progress({})
                for i, s in enumerate(agent_specs):
                    initial[i]["current_task"] = s.get("task_description", "")
                    _log_hist(f"Manager → {s.get('name', f'Agent {i+1}')}", "มอบหมาย: ", s.get("task_description", "")[:200])
                callback = self._agent_progress_callback
                ctx = self._ctx
                main_loop = self._main_loop
                if main_loop and ctx:
                    main_loop.create_task(callback(initial), context=ctx)
                else:
                    asyncio.ensure_future(callback(initial))

            # Run all worker agents in parallel — each in its own thread
            loop = asyncio.get_event_loop()

            def run_single_agent_sync(agent, task, spec, idx):
                """Run one agent on its task as a standalone Crew (sync, for thread pool).
                Falls back to local LLM on rate limit errors."""
                _thread_local.agent_name = spec.get("name", f"Agent {idx+1}")
                set_llm_call_context(f"agent:{spec.get('name', f'Agent {idx+1}')}")
                import time as _time
                print(f"[DEBUG-PARALLEL-START] Agent {idx} '{spec.get('name', '')}' starting at {_time.time():.3f}", flush=True)
                single_crew = Crew(
                    agents=[agent],
                    tasks=[task],
                    process=Process.sequential,
                    verbose=True,
                )
                try:
                    single_result = single_crew.kickoff()
                except Exception as e:
                    err_msg = _sanitize_error(e)
                    _debug(f"[DEBUG-PARALLEL] Agent {spec.get('name', '')} error: {err_msg}", flush=True)
                    if ("429" in err_msg or "rate limit" in err_msg.lower() or "402" in err_msg or "credit" in err_msg.lower()):
                        # If using openrouter/free, try free model rotator first
                        if self.llm_manager._is_free_routing():
                            rotator = self.llm_manager._get_rotator()
                            for free_model in rotator.get_ranking():
                                try:
                                    _debug(f"[DEBUG-PARALLEL] Retrying {spec.get('name', '')} with free model: {free_model}", flush=True)
                                    agent.llm = rotator.build_crewai_llm(free_model)
                                    single_crew = Crew(
                                        agents=[agent],
                                        tasks=[task],
                                        process=Process.sequential,
                                        verbose=True,
                                    )
                                    single_result = single_crew.kickoff()
                                    break
                                except Exception as rotator_err:
                                    _debug(f"[DEBUG-PARALLEL] Free model {free_model} failed: {_sanitize_error(rotator_err)}", flush=True)
                                    continue
                            else:
                                # All free models failed — fall through to local fallback
                                pass
                            if 'single_result' in locals():
                                pass  # got a result from rotator
                            else:
                                if self.llm_manager.local_fallback_enabled:
                                    self.llm_manager.report_rate_limit()
                                    fallback_llm = self.llm_manager._build_llm(
                                        self.llm_manager.fallback_provider,
                                        self.llm_manager.fallback_model,
                                        self.llm_manager.fallback_base_url,
                                        self.llm_manager.fallback_api_key,
                                    )
                                    agent.llm = fallback_llm
                                    _debug(f"[DEBUG-PARALLEL] Retrying {spec.get('name', '')} with local LLM (dev fallback)", flush=True)
                                    single_crew = Crew(
                                        agents=[agent],
                                        tasks=[task],
                                        process=Process.sequential,
                                        verbose=True,
                                    )
                                    single_result = single_crew.kickoff()
                                else:
                                    raise
                        elif self.llm_manager.local_fallback_enabled:
                            # Non-free model — only local fallback
                            self.llm_manager.report_rate_limit()
                            fallback_llm = self.llm_manager._build_llm(
                                self.llm_manager.fallback_provider,
                                self.llm_manager.fallback_model,
                                self.llm_manager.fallback_base_url,
                                self.llm_manager.fallback_api_key,
                            )
                            agent.llm = fallback_llm
                            _debug(f"[DEBUG-PARALLEL] Retrying {spec.get('name', '')} with local LLM (dev fallback)", flush=True)
                            single_crew = Crew(
                                agents=[agent],
                                tasks=[task],
                                process=Process.sequential,
                                verbose=True,
                            )
                            single_result = single_crew.kickoff()
                        else:
                            raise
                    else:
                        raise
                raw = getattr(single_result, "raw", str(single_result))
                name = spec.get("name", f"Agent {idx+1}")
                role = spec.get("role", "")
                _debug(f"[DEBUG-PARALLEL] Agent {name} completed, output_len={len(str(raw))}", flush=True)
                clear_llm_call_context()
                return {"name": name, "role": role, "output": str(raw)}

            # === Dependency-driven scheduler with Manager auto-review ===
            # Each agent starts as soon as all its depends_on targets are approved.
            # On completion, Manager LLM reviews output automatically.
            # If approved, output is available to dependents. If not, agent re-runs with feedback.
            agent_name_to_idx = {agent_specs[i].get("name", f"Agent {i+1}"): i for i in range(len(agents))}
            print(f"[DEBUG-SCHED] agent_specs deps: {[(s.get('name'), s.get('depends_on', [])) for s in agent_specs]}", flush=True)

            approved_outputs: dict[str, str] = {}   # name -> approved output
            agent_outputs = [None] * len(agents)

            # Get messenger for sending progress updates
            _messenger = cl.user_session.get("messenger")

            # Get Manager config from registry for auto-review
            _registry = cl.user_session.get("registry")
            _manager_persona = "You are an experienced team manager who coordinates teams effectively."
            _manager_goal = "Coordinate the team and synthesize results."
            _manager_model = model_assignment.get("manager", "")
            # Force manager model = user's top-bar selection (highest priority)
            _selected = cl.user_session.get("selected_model") or ""
            if _selected:
                _manager_model = _selected
            if _registry:
                _current_team_id = cl.user_session.get("current_team_id")
                _team_agents = _registry.list_agents(team_id=_current_team_id) if _current_team_id else _registry.list_agents()
                _manager_agent = next((a for a in _team_agents if a.get("is_manager")), None)
                if _manager_agent:
                    _manager_persona = _manager_agent.get("persona", _manager_persona)
                    _manager_goal = _manager_agent.get("goal", _manager_goal)

            def _send_progress_for_agent(idx, status, output_text="", review_round=None, review_summary=None, review_feedback=None, review_history=None):
                """Send progress update for a single agent."""
                # Log to history store
                _agent_name = agent_specs[idx].get("name", f"Agent {idx+1}")
                _agent_model = agent_specs[idx].get("model", "")
                if status == "running":
                    _log_hist(_agent_name, f"เริ่มทำงาน ({_agent_model})")
                elif status == "complete":
                    _summary = f" — {review_summary}" if review_summary else ""
                    _log_hist(_agent_name, f"เสร็จสิ้น{_summary}")
                elif status == "error":
                    _log_hist(_agent_name, f"เกิดข้อผิดพลาด: {(output_text or '')[:200]}")
                elif status == "awaiting_review":
                    _log_hist(_agent_name, "รอตรวจสอบผลลัพธ์")
                if not (self._agent_progress_callback and self._main_loop and self._ctx):
                    return
                with self._state_lock:
                    if idx not in self._agent_state:
                        self._agent_state[idx] = {
                            "name": agent_specs[idx].get("name", "Agent"),
                            "role": agent_specs[idx].get("role", ""),
                            "status": "pending",
                            "progress": 0,
                            "model": agent_specs[idx].get("model", ""),
                            "review_history": [],
                        }
                    self._agent_state[idx]["status"] = status
                    self._agent_state[idx]["progress"] = 100 if status in ("complete", "error", "awaiting_review") else 0
                    if output_text:
                        self._agent_state[idx]["output"] = output_text[:8000]
                    if review_round is not None:
                        self._agent_state[idx]["review_round"] = review_round
                    if review_summary is not None:
                        self._agent_state[idx]["review_summary"] = review_summary
                    if review_feedback is not None:
                        self._agent_state[idx]["review_feedback"] = review_feedback
                    if review_history is not None:
                        self._agent_state[idx]["review_history"] = review_history
                    progress = self._build_progress({}, self._agent_state)
                _ctx = self._ctx
                _loop = self._main_loop
                _cb = self._agent_progress_callback
                _loop.call_soon_threadsafe(lambda p=progress: _loop.create_task(_async_progress_callback(_cb, p), context=_ctx))

            async def _batch_manager_review(agents_data, retry_count):
                """Manager LLM reviews multiple agent outputs in one call.
                
                agents_data: list of {idx, name, role, goal, output}
                Returns: dict {idx: {approved, feedback, summary}}
                """
                # Build combined review prompt
                agents_section = ""
                template_contracts = ""
                for a in agents_data:
                    agents_section += (
                        f"\n--- Agent: {a['name']} (role: {a['role']}) ---\n"
                        f"Task: {a['goal']}\n"
                        f"Output:\n{a['output']}\n"
                    )
                    # Include agent-specific quality criteria if set
                    qc = a.get("quality_criteria", "")
                    if qc:
                        agents_section += f"QUALITY CRITERIA for {a['name']} (MUST check all):\n{qc}\n"
                    of = a.get("output_format", "")
                    if of:
                        agents_section += f"EXPECTED OUTPUT FORMAT for {a['name']}:\n{of}\n"
                    # Detect template contract for this agent
                    a_tmpl_id = detect_template_id(a.get("role", ""), a.get("name", ""))
                    if a_tmpl_id:
                        contract = get_template_contract(a_tmpl_id)
                        if contract:
                            template_contracts += f"\n=== REQUIRED OUTPUT FORMAT for {a['name']} ===\n{contract}\n"

                review_prompt = (
                    f"{_manager_persona}\n"
                    f"Your goal: {_manager_goal}\n\n"
                    f"You are reviewing the outputs of {len(agents_data)} agent(s) in this wave.\n"
                    f"User's original request: {user_input}\n\n"
                    f"Review attempt #{retry_count + 1} for this wave.\n\n"
                    f"{agents_section}\n\n"
                )
                if template_contracts:
                    review_prompt += (
                        f"{template_contracts}\n\n"
                        f"CRITICAL — TEMPLATE COMPLIANCE:\n"
                        f"- Check each required heading/section from the template one by one.\n"
                        f"- REJECT if ANY required section is missing or empty.\n"
                        f"- REJECT if the output does not follow the required format/template structure.\n"
                        f"- In feedback, list exactly which sections are missing or incomplete.\n\n"
                    )
                review_prompt += (
                    f"Evaluate each agent's output against their task and the user's request.\n"
                    f"Respond in JSON ONLY — a JSON array with one entry per agent:\n"
                    f'[{{"name": "agent name", "approved": true/false, "feedback": "specific feedback if not approved, empty if approved", "summary": "1-2 sentence summary in Thai"}}]\n\n'
                    f"Rules:\n"
                    f"- REJECT if the output is vague, generic, or lacks specific details (names, numbers, dates, sources) that the task requires\n"
                    f"- REJECT if the output mentions tools but doesn't show actual results from using them\n"
                    f"- REJECT if the output is too brief or doesn't address the user's actual question\n"
                    f"- REJECT if any specific requirement from the user's original request is not addressed in the output — check each requirement one by one\n"
                    f"- If an agent has QUALITY CRITERIA listed above, check EACH criterion one by one and REJECT if any is not met\n"
                    f"- If an agent has an EXPECTED OUTPUT FORMAT listed above, REJECT if the output does not follow that format\n"
                    f"- APPROVE only if the output contains concrete, specific information that fully addresses the user's request and follows the required format\n"
                    f"- feedback must be specific: tell the agent exactly what details to add or fix, including which sections are missing\n"
                    f"- summary should be concise: e.g. 'รอบ 1: งานยังไม่ครบ ขาดสรุป — สั่งแก้' or 'รอบ 2: ครบ ตรงโจทย์ — ผ่าน'\n"
                )

                if _manager_model:
                    manager_llm = self.llm_manager.build_llm_for_model(_manager_model)
                    def _review_call():
                        set_llm_call_context(f"manager_review:round{retry_count + 1}")
                        try:
                            return manager_llm.call(review_prompt)
                        except Exception as review_err:
                            err_msg = _sanitize_error(review_err)
                            if self.llm_manager._is_free_routing() and ("429" in err_msg or "rate limit" in err_msg.lower() or "402" in err_msg or "credit" in err_msg.lower()):
                                _debug(f"[DEBUG-REVIEW] manager review failed, trying free model rotator", flush=True)
                                rotator = self.llm_manager._get_rotator()
                                for free_model in rotator.get_ranking():
                                    try:
                                        _debug(f"[DEBUG-REVIEW] Trying free model: {free_model}", flush=True)
                                        free_llm = rotator.build_crewai_llm(free_model)
                                        return free_llm.call(review_prompt)
                                    except Exception as fm_err:
                                        _debug(f"[DEBUG-REVIEW] Free model {free_model} failed: {_sanitize_error(fm_err)}", flush=True)
                                        continue
                            raise
                        finally:
                            clear_llm_call_context()
                    raw = await loop.run_in_executor(None, _review_call)
                else:
                    raw = await loop.run_in_executor(None, lambda: self.llm_manager.call_with_fallback(review_prompt, caller=f"manager_review:round{retry_count + 1}"))

                results = {}
                try:
                    # Try parsing as JSON array
                    json_match = re.search(r'\[.*\]', str(raw), re.DOTALL)
                    if json_match:
                        parsed = json.loads(json_match.group())
                        if isinstance(parsed, list):
                            for item in parsed:
                                name = item.get("name", "")
                                results[name] = {
                                    "approved": item.get("approved", True),
                                    "feedback": item.get("feedback", ""),
                                    "summary": item.get("summary", "ผ่าน" if item.get("approved") else "ไม่ผ่าน — สั่งแก้"),
                                }
                except (json.JSONDecodeError, AttributeError):
                    pass

                # Fallback: if parsing failed, approve all
                if not results:
                    for a in agents_data:
                        results[a["name"]] = {"approved": True, "feedback": "", "summary": "ตรวจสอบแล้ว — ผ่าน"}

                return results

            async def run_agent_only(idx):
                """Run a single agent without review. Returns (result, output_text)."""
                name = agent_specs[idx].get("name", f"Agent {idx+1}")
                role = agent_specs[idx].get("role", "")
                deps = agent_specs[idx].get("depends_on", [])

                # Inject upstream context from approved outputs
                if deps:
                    context_parts = []
                    for dep_name in deps:
                        dep_output = approved_outputs.get(dep_name, "")
                        if dep_output:
                            context_parts.append(f"--- Output from {dep_name} ---\n{dep_output}")
                    if context_parts:
                        upstream_context = "\n\n".join(context_parts)
                        tasks[idx] = self.agent_factory.create_task(
                            agents[idx], agent_specs[idx], user_input + f"\n\n[UPSTREAM CONTEXT]\n{upstream_context}"
                        )
                        print(f"[DEBUG-SCHED] Agent {name} received context from: {deps}", flush=True)
                    else:
                        print(f"[WARN-SCHED] Agent {name} depends on {deps} but no upstream context available", flush=True)

                _send_progress_for_agent(idx, "running")
                result = await loop.run_in_executor(
                    None, run_single_agent_sync,
                    agents[idx], tasks[idx], agent_specs[idx], idx
                )
                if isinstance(result, Exception):
                    return result, str(result)
                return result, result.get("output", "")

            async def rerun_agent_with_feedback(idx, feedback, agent_memory=None):
                """Re-run a single agent with manager feedback and previous attempt memory."""
                name = agent_specs[idx].get("name", f"Agent {idx+1}")
                role = agent_specs[idx].get("role", "")
                deps = agent_specs[idx].get("depends_on", [])

                feedback_prompt = user_input
                if deps:
                    context_parts = []
                    for dep_name in deps:
                        dep_output = approved_outputs.get(dep_name, "")
                        if dep_output:
                            context_parts.append(f"--- Output from {dep_name} ---\n{dep_output}")
                    if context_parts:
                        feedback_prompt += f"\n\n[UPSTREAM CONTEXT]\n" + "\n\n".join(context_parts)
                feedback_prompt += f"\n\n[MANAGER FEEDBACK]\n{feedback}"
                tasks[idx] = self.agent_factory.create_task(
                    agents[idx], agent_specs[idx], feedback_prompt,
                    agent_memory=agent_memory,
                )
                result = await loop.run_in_executor(
                    None, run_single_agent_sync,
                    agents[idx], tasks[idx], agent_specs[idx], idx
                )
                if isinstance(result, Exception):
                    return result, str(result)
                return result, result.get("output", "")

            # Per-agent review state tracking
            agent_review_state = {}  # idx -> {retry_count, review_history, current_output, current_result}
            # Per-agent experiential memory: tracks previous outputs + feedback for retries
            agent_memories: dict[str, list[dict]] = {}  # name -> [{output, feedback, round}]

            async def schedule_and_run():
                """Dynamic scheduler with batch review: launch agents as deps become approved,
                batch-review all completed agents in a wave, re-run only rejected ones."""
                done_indices = set()

                while len(done_indices) < len(agents):
                    # Check if user requested to stop generation
                    if cl.user_session.get("cancel_generation"):
                        print(f"[DEBUG-SCHED] Cancel requested — marking remaining agents as cancelled", flush=True)
                        for i in range(len(agents)):
                            if i not in done_indices:
                                name = agent_specs[i].get("name", f"Agent {i+1}")
                                _send_progress_for_agent(i, "error", "Cancelled by user")
                                agent_outputs[i] = {"name": name, "role": agent_specs[i].get("role", ""), "output": "Cancelled by user"}
                                done_indices.add(i)
                        break

                    # Find agents whose deps are all approved and not yet started/done
                    launchable = []
                    for i in range(len(agents)):
                        if i in done_indices or i in agent_review_state:
                            continue
                        deps = agent_specs[i].get("depends_on", [])
                        all_deps_approved = all(
                            dep_name in approved_outputs or dep_name not in agent_name_to_idx
                            for dep_name in deps
                        )
                        if all_deps_approved:
                            launchable.append(i)

                    if not launchable and not agent_review_state:
                        print(f"[WARN-SCHED] No agents can start and none pending — breaking", flush=True)
                        break

                    # Launch all eligible agents in parallel
                    running = {}
                    for i in launchable:
                        name = agent_specs[i].get("name", f"Agent {i+1}")
                        print(f"[DEBUG-SCHED] Launching agent '{name}' — deps satisfied", flush=True)
                        running[i] = asyncio.create_task(run_agent_only(i))

                    # Wait for ALL running agents to complete (batch)
                    if running:
                        await asyncio.wait(running.values(), return_when=asyncio.ALL_COMPLETED)

                    # Check cancel after agents completed — skip review if cancelled
                    if cl.user_session.get("cancel_generation"):
                        print(f"[DEBUG-SCHED] Cancel requested after wave — skipping review, approving all", flush=True)
                        for i in list(running.keys()):
                            if i not in done_indices and i in agent_review_state:
                                name = agent_specs[i].get("name", f"Agent {i+1}")
                                st = agent_review_state[i]
                                approved_outputs[name] = st["current_output"]
                                _send_progress_for_agent(i, "complete", st["current_output"][:8000],
                                    review_summary="Cancelled — output approved without review")
                                done_indices.add(i)
                        continue

                    # Collect results
                    pending_review = []  # agents that completed successfully and need review
                    for i, t in list(running.items()):
                        name = agent_specs[i].get("name", f"Agent {i+1}")
                        role = agent_specs[i].get("role", "")
                        result, output_text = t.result()

                        if isinstance(result, Exception):
                            err_str = str(result)
                            _debug(f"[DEBUG-SCHED] Agent {name} failed: {_sanitize_error(result)}", flush=True)
                            agent_outputs[i] = {"name": name, "role": role, "output": f"Error: {err_str}"}
                            _send_progress_for_agent(i, "error", err_str[:8000])
                            approved_outputs[name] = f"Error: {err_str}"
                            done_indices.add(i)
                        else:
                            print(f"[DEBUG-SCHED] Agent '{name}' completed, output_len={len(output_text)}", flush=True)
                            agent_review_state[i] = {
                                "retry_count": 0,
                                "review_history": [],
                                "current_output": output_text,
                                "current_result": result,
                            }
                            agent_outputs[i] = result

                            # ── Template deterministic validation (before manager review) ──
                            tmpl_id = agent_specs[i].get("template_id", "")
                            if not tmpl_id:
                                tmpl_id = detect_template_id(agent_specs[i].get("role", ""), agent_specs[i].get("name", "")) or ""
                            if tmpl_id:
                                validation = validate_template_output(tmpl_id, output_text)
                                if validation:
                                    state_ph = agent_review_state.get(i)
                                    if state_ph:
                                        tmpl_feedback = validation["feedback"]
                                        tmpl_summary = validation["summary"]
                                        print(f"[DEBUG-SCHED] Agent '{name}' failed template validation: {tmpl_summary}", flush=True)
                                        state_ph["review_history"].append({
                                            "round": state_ph["retry_count"] + 1,
                                            "status": "rejected",
                                            "summary": f"Template check: {tmpl_summary}",
                                            "feedback": tmpl_feedback,
                                            "output_preview": output_text[:2000],
                                        })
                                        tmpl_review_iters = agent_specs[i].get("review_iterations", MAX_REVIEW_RETRIES)
                                        if state_ph["retry_count"] >= tmpl_review_iters:
                                            print(f"[DEBUG-SCHED] Agent '{name}' hit max retries on template validation — force approving", flush=True)
                                            approved_outputs[name] = output_text
                                            _send_progress_for_agent(i, "complete", output_text[:8000],
                                                review_round=state_ph["retry_count"] + 1,
                                                review_summary="ครบ retry สูงสุด — ใช้ output ปัจจุบัน (template check ไม่ผ่าน)",
                                                review_history=state_ph["review_history"])
                                            done_indices.add(i)
                                            del agent_review_state[i]
                                        else:
                                            state_ph["retry_count"] += 1
                                            if name not in agent_memories:
                                                agent_memories[name] = []
                                            agent_memories[name].append({
                                                "output": output_text[:3000],
                                                "feedback": tmpl_feedback,
                                                "round": state_ph["retry_count"],
                                            })
                                            _send_progress_for_agent(i, "running",
                                                review_round=state_ph["retry_count"],
                                                review_summary=tmpl_summary,
                                                review_feedback=tmpl_feedback,
                                                review_history=state_ph["review_history"])
                                            rerun_result, rerun_output = await rerun_agent_with_feedback(
                                                i, tmpl_feedback, agent_memory=agent_memories.get(name)
                                            )
                                            if isinstance(rerun_result, Exception):
                                                approved_outputs[name] = f"Error: {rerun_output}"
                                                _send_progress_for_agent(i, "error", rerun_output[:8000])
                                                done_indices.add(i)
                                                del agent_review_state[i]
                                            else:
                                                state_ph["current_output"] = rerun_output
                                                state_ph["current_result"] = rerun_result
                                                agent_outputs[i] = rerun_result
                                                reval = validate_template_output(tmpl_id, rerun_output)
                                                if reval is None:
                                                    pending_review.append(i)
                                                    print(f"[DEBUG-SCHED] Agent '{name}' passed template validation on retry", flush=True)
                                                else:
                                                    pending_review.append(i)
                                                    print(f"[DEBUG-SCHED] Agent '{name}' still failing template validation after retry — sending to manager", flush=True)
                                    else:
                                        pending_review.append(i)
                                else:
                                    pending_review.append(i)
                            else:
                                pending_review.append(i)

                    # Batch review loop for pending agents
                    while pending_review:
                        # Check if user requested to stop generation
                        if cl.user_session.get("cancel_generation"):
                            print(f"[DEBUG-SCHED] Cancel requested — approving all pending with current output", flush=True)
                            for idx in pending_review:
                                name = agent_specs[idx].get("name", f"Agent {idx+1}")
                                state = agent_review_state[idx]
                                approved_outputs[name] = state["current_output"]
                                agent_outputs[idx] = state["current_result"]
                                _send_progress_for_agent(idx, "complete", state["current_output"][:8000],
                                    review_round=state["retry_count"] + 1,
                                    review_summary="หยุดโดยผู้ใช้ — ใช้ output ปัจจุบัน",
                                    review_history=state["review_history"])
                                done_indices.add(idx)
                                del agent_review_state[idx]
                            pending_review = []
                            break

                        # Check for skip_review requests
                        still_pending = []
                        for idx in pending_review:
                            name = agent_specs[idx].get("name", f"Agent {idx+1}")
                            state = agent_review_state[idx]

                            if name in self.skip_review_agents:
                                self.skip_review_agents.discard(name)
                                state["review_history"].append({
                                    "round": state["retry_count"] + 1,
                                    "status": "approved",
                                    "summary": "User หยุดตรวจ — ใช้ output ปัจจุบัน",
                                    "feedback": "",
                                    "output_preview": state["current_output"][:2000],
                                })
                                approved_outputs[name] = state["current_output"]
                                agent_outputs[idx] = state["current_result"]
                                _send_progress_for_agent(idx, "complete", state["current_output"][:8000],
                                    review_round=state["retry_count"] + 1,
                                    review_summary="User หยุดตรวจ — ใช้ output ปัจจุบัน",
                                    review_history=state["review_history"])
                                print(f"[DEBUG-SCHED] Agent '{name}' review skipped by user", flush=True)
                                done_indices.add(idx)
                                del agent_review_state[idx]
                            else:
                                still_pending.append(idx)

                        pending_review = still_pending
                        if not pending_review:
                            break

                        # Mark all pending as awaiting_review
                        agents_data = []
                        for idx in pending_review:
                            name = agent_specs[idx].get("name", f"Agent {idx+1}")
                            role = agent_specs[idx].get("role", "")
                            goal = agent_specs[idx].get("goal", "")
                            state = agent_review_state[idx]
                            _send_progress_for_agent(idx, "awaiting_review", state["current_output"][:8000],
                                review_round=state["retry_count"] + 1,
                                review_history=state["review_history"])
                            agents_data.append({
                                "idx": idx,
                                "name": name,
                                "role": role,
                                "goal": goal,
                                "output": state["current_output"],
                                "quality_criteria": agent_specs[idx].get("quality_criteria", ""),
                                "output_format": agent_specs[idx].get("output_format", ""),
                            })

                        # Determine wave retry count (max of all pending)
                        wave_retry = max(agent_review_state[idx]["retry_count"] for idx in pending_review)

                        # Batch review
                        print(f"[DEBUG-SCHED] Batch reviewing {len(agents_data)} agents (wave retry {wave_retry})", flush=True)
                        reviews = await _batch_manager_review(agents_data, wave_retry)

                        # Process results
                        next_pending = []
                        for idx in pending_review:
                            name = agent_specs[idx].get("name", f"Agent {idx+1}")
                            role = agent_specs[idx].get("role", "")
                            goal = agent_specs[idx].get("goal", "")
                            state = agent_review_state[idx]
                            review = reviews.get(name, {"approved": True, "feedback": "", "summary": "ตรวจสอบแล้ว — ผ่าน"})

                            print(f"[DEBUG-SCHED] Agent '{name}' review round {state['retry_count']+1}: approved={review['approved']}, summary={review['summary']}", flush=True)

                            state["review_history"].append({
                                "round": state["retry_count"] + 1,
                                "status": "approved" if review["approved"] else "rejected",
                                "summary": review["summary"],
                                "feedback": review["feedback"],
                                "output_preview": state["current_output"][:2000],
                            })

                            if review["approved"]:
                                approved_outputs[name] = state["current_output"]
                                agent_outputs[idx] = state["current_result"]
                                _send_progress_for_agent(idx, "complete", state["current_output"][:8000],
                                    review_round=state["retry_count"] + 1,
                                    review_summary=review["summary"],
                                    review_history=state["review_history"])
                                print(f"[DEBUG-SCHED] Agent '{name}' approved by Manager", flush=True)
                                done_indices.add(idx)
                                del agent_review_state[idx]
                            else:
                                # Check max retry limit before re-running
                                agent_review_iters = agent_specs[idx].get("review_iterations", MAX_REVIEW_RETRIES)
                                if state["retry_count"] >= agent_review_iters:
                                    print(f"[DEBUG-SCHED] Agent '{name}' hit max retries ({agent_review_iters}) — force approving", flush=True)
                                    approved_outputs[name] = state["current_output"]
                                    agent_outputs[idx] = state["current_result"]
                                    _send_progress_for_agent(idx, "complete", state["current_output"][:8000],
                                        review_round=state["retry_count"] + 1,
                                        review_summary=f"ครบจำนวน retry สูงสุด ({agent_review_iters}) — ใช้ output ปัจจุบัน",
                                        review_history=state["review_history"])
                                    done_indices.add(idx)
                                    del agent_review_state[idx]
                                else:
                                    # Re-run with feedback
                                    _send_progress_for_agent(idx, "running",
                                        review_round=state["retry_count"] + 1,
                                        review_summary=review["summary"],
                                        review_feedback=review["feedback"],
                                        review_history=state["review_history"])
                                    state["retry_count"] += 1
                                    # Record experiential memory: previous output + feedback
                                    if name not in agent_memories:
                                        agent_memories[name] = []
                                    agent_memories[name].append({
                                        "output": state["current_output"][:3000],
                                        "feedback": review["feedback"],
                                        "round": state["retry_count"],
                                    })
                                    next_pending.append(idx)

                        # Re-run rejected agents in parallel
                        if next_pending:
                            # Check cancel before re-running
                            if cl.user_session.get("cancel_generation"):
                                print(f"[DEBUG-SCHED] Cancel requested before re-run — approving all", flush=True)
                                for idx in next_pending:
                                    name = agent_specs[idx].get("name", f"Agent {idx+1}")
                                    state = agent_review_state[idx]
                                    approved_outputs[name] = state["current_output"]
                                    agent_outputs[idx] = state["current_result"]
                                    _send_progress_for_agent(idx, "complete", state["current_output"][:8000],
                                        review_round=state["retry_count"] + 1,
                                        review_summary="หยุดโดยผู้ใช้ — ใช้ output ปัจจุบัน",
                                        review_history=state["review_history"])
                                    done_indices.add(idx)
                                    del agent_review_state[idx]
                                pending_review = []
                                break
                            rerun_tasks = {}
                            for idx in next_pending:
                                name = agent_specs[idx].get("name", f"Agent {idx+1}")
                                state = agent_review_state[idx]
                                feedback = reviews.get(name, {}).get("feedback", "")
                                mem = agent_memories.get(name, [])
                                rerun_tasks[idx] = asyncio.create_task(rerun_agent_with_feedback(idx, feedback, agent_memory=mem))

                            await asyncio.wait(rerun_tasks.values(), return_when=asyncio.ALL_COMPLETED)

                            # Collect re-run results
                            pending_review = []
                            for idx, t in list(rerun_tasks.items()):
                                name = agent_specs[idx].get("name", f"Agent {idx+1}")
                                role = agent_specs[idx].get("role", "")
                                state = agent_review_state[idx]
                                result, output_text = t.result()

                                if isinstance(result, Exception):
                                    err_str = str(result)
                                    agent_outputs[idx] = {"name": name, "role": role, "output": f"Error: {err_str}"}
                                    _send_progress_for_agent(idx, "error", err_str[:8000])
                                    approved_outputs[name] = f"Error: {err_str}"
                                    done_indices.add(idx)
                                    del agent_review_state[idx]
                                else:
                                    state["current_output"] = output_text
                                    state["current_result"] = result
                                    agent_outputs[idx] = result
                                    print(f"[DEBUG-SCHED] Agent '{name}' re-run (attempt {state['retry_count']+1}), output_len={len(output_text)}", flush=True)
                                    pending_review.append(idx)
                        else:
                            pending_review = []

            # Check cancel before scheduling next wave
            if cl.user_session.get("cancel_generation"):
                print(f"[DEBUG-SCHED] Cancel requested — skipping schedule_and_run", flush=True)
            else:
                await schedule_and_run()

            # Filter None (shouldn't happen but safe)
            agent_outputs = [o for o in agent_outputs if o is not None]
            print(f"[DEBUG-SCHED] All agents completed. {len(agent_outputs)} agent outputs collected.", flush=True)

            # Manager synthesizes all outputs — pull config from registry
            _debug(f"[DEBUG-PARALLEL] Manager synthesizing {len(agent_outputs)} outputs", flush=True)

            # Get Manager agent from registry for persona/goal
            registry = cl.user_session.get("registry")
            manager_persona = "You are an experienced team manager who coordinates teams effectively."
            manager_goal = "Coordinate the team and synthesize results."
            if registry:
                current_team_id = cl.user_session.get("current_team_id")
                team_agents = registry.list_agents(team_id=current_team_id) if current_team_id else registry.list_agents()
                manager_agent = next((a for a in team_agents if a.get("is_manager")), None)
                if manager_agent:
                    manager_persona = manager_agent.get("persona", manager_persona)
                    manager_goal = manager_agent.get("goal", manager_goal)

            # Send progress: all agents complete, Manager synthesizing
            if self._agent_progress_callback and self._main_loop and self._ctx:
                progress = self._build_progress({}, self._agent_state)
                for i, spec in enumerate(agent_specs):
                    progress[i]["status"] = "complete"
                    progress[i]["progress"] = 100
                    if i < len(agent_outputs):
                        progress[i]["output"] = (agent_outputs[i].get("output", "") or "")[:8000]
                    # Preserve review_history from agent_state
                    if i in self._agent_state:
                        progress[i]["review_history"] = self._agent_state[i].get("review_history", [])
                        progress[i]["review_round"] = self._agent_state[i].get("review_round", 0)
                        progress[i]["review_summary"] = self._agent_state[i].get("review_summary", "")
                progress.append({
                    "name": "Manager",
                    "role": "Reviewing deliverables",
                    "status": "running",
                    "progress": 50,
                    "current_task": "Reviewing team deliverables for quality",
                })
                ctx = self._ctx
                loop = self._main_loop
                callback = self._agent_progress_callback

                def _schedule_manager_progress():
                    print(f"[DEBUG-synth] Sending Manager 'running' progress to frontend", flush=True)
                    loop.create_task(
                        _async_progress_callback(callback, progress),
                        context=ctx,
                    )
                loop.call_soon_threadsafe(_schedule_manager_progress)

            synthesis_prompt = (
                f"User request: {user_input}\n\n"
                f"{manager_persona}\n"
                f"Your goal: {manager_goal}\n"
                f"Your team has completed their tasks.\n"
                f"Below are the outputs from each team member, along with their review history:\n\n"
            )
            for ao in agent_outputs:
                clean_output = self._clean_agent_output(ao['output'])
                synthesis_prompt += f"--- {ao['name']} ({ao['role']}) ---\n{clean_output}\n\n"
                # Include review history if available
                agent_name = ao.get("name", "")
                for i, spec in enumerate(agent_specs):
                    if spec.get("name", "") == agent_name and i in self._agent_state:
                        state = self._agent_state[i]
                        review_history = state.get("review_history", [])
                        if review_history:
                            synthesis_prompt += f"Review history ({len(review_history)} rounds):\n"
                            for rh in review_history:
                                synthesis_prompt += f"  Round {rh.get('round', '?')}: {rh.get('status', '?')} — {rh.get('summary', '')}\n"
                            synthesis_prompt += "\n"
                        break
            synthesis_prompt += (
                "\nSummarize the team's deliverables for the user:\n"
                "1. Briefly state what each agent found or produced (1-2 sentences each)\n"
                "2. Note any key insights or important findings\n"
                "3. If there are gaps or limitations, mention them concisely\n\n"
                "Do NOT copy or rephrase agent outputs — the user already sees them in full.\n"
                "Do NOT include phrases like 'Final Answer:', 'Task Completed:', or 'Crew Completion:'.\n"
                "Keep your summary brief and focused on synthesis, not on repeating content.\n"
                "Respond in Thai if the user's request was in Thai."
            )

            manager_model = model_assignment.get("manager", "")
            # Force manager model = user's top-bar selection (highest priority)
            _selected = cl.user_session.get("selected_model") or ""
            if _selected:
                manager_model = _selected
            if manager_model:
                manager_llm = self.llm_manager.build_llm_for_model(manager_model)
                def _synthesis_call():
                    set_llm_call_context("manager_synthesis")
                    try:
                        return manager_llm.call(synthesis_prompt)
                    except Exception as syn_err:
                        err_msg = _sanitize_error(syn_err)
                        if self.llm_manager._is_free_routing() and ("429" in err_msg or "rate limit" in err_msg.lower() or "402" in err_msg or "credit" in err_msg.lower()):
                            _debug(f"[DEBUG-SYNTH] manager synthesis failed, trying free model rotator", flush=True)
                            rotator = self.llm_manager._get_rotator()
                            for free_model in rotator.get_ranking():
                                try:
                                    _debug(f"[DEBUG-SYNTH] Trying free model: {free_model}", flush=True)
                                    free_llm = rotator.build_crewai_llm(free_model)
                                    return free_llm.call(synthesis_prompt)
                                except Exception as fm_err:
                                    _debug(f"[DEBUG-SYNTH] Free model {free_model} failed: {_sanitize_error(fm_err)}", flush=True)
                                    continue
                        raise
                    finally:
                        clear_llm_call_context()
                manager_raw = await loop.run_in_executor(None, _synthesis_call)
            else:
                manager_raw = await loop.run_in_executor(
                    None, lambda: self.llm_manager.call_with_fallback(synthesis_prompt, caller="manager_synthesis")
                )

            # Clean manager output and add it to agent_outputs so it appears in result card
            clean_manager_output = self._clean_agent_output(str(manager_raw))
            agent_outputs.append({
                "name": "Manager",
                "role": "Project Manager",
                "output": clean_manager_output,
            })

            # Send final progress: Manager synthesis complete
            if self._agent_progress_callback and self._main_loop and self._ctx:
                progress = self._build_progress({}, self._agent_state)
                for i, spec in enumerate(agent_specs):
                    progress[i]["status"] = "complete"
                    progress[i]["progress"] = 100
                    if i < len(agent_outputs) - 1:  # exclude manager output (last entry)
                        progress[i]["output"] = (agent_outputs[i].get("output", "") or "")[:8000]
                    if i in self._agent_state:
                        progress[i]["review_history"] = self._agent_state[i].get("review_history", [])
                        progress[i]["review_round"] = self._agent_state[i].get("review_round", 0)
                        progress[i]["review_summary"] = self._agent_state[i].get("review_summary", "")
                progress.append({
                    "name": "Manager",
                    "role": "Project Manager",
                    "status": "complete",
                    "progress": 100,
                    "output": clean_manager_output[:8000],
                    "current_task": "Review complete",
                })
                ctx = self._ctx
                loop = self._main_loop
                callback = self._agent_progress_callback

                def _schedule_manager_done():
                    print(f"[DEBUG-synth] Sending Manager 'complete' progress to frontend", flush=True)
                    loop.create_task(
                        _async_progress_callback(callback, progress),
                        context=ctx,
                    )
                loop.call_soon_threadsafe(_schedule_manager_done)

            return {
                "raw": clean_manager_output,
                "agent_outputs": agent_outputs,
                "agent_memories": agent_memories,
            }
        finally:
            _log_hist("Manager", "ทีมทำงานเสร็จทั้งหมด ✅")
            _progress_callback = None
            _media_gen_manager = None
            _search_model = ""
            self._unregister_event_listeners()


# ============================================================
# Dashboard Manager

