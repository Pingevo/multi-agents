"""ExecutionOrchestrator — wave-based parallel agent execution."""

import asyncio
import contextvars
import json
import re
import traceback
import chainlit as cl
from crewai import Agent, Task, Crew, Process, LLM
from crewai.events import crewai_event_bus
from crewai.events.types.agent_events import AgentExecutionStartedEvent, AgentExecutionCompletedEvent
from crewai.events.types.tool_usage_events import ToolUsageStartedEvent, ToolUsageFinishedEvent
from crewai.events.types.task_events import TaskStartedEvent, TaskCompletedEvent
from crewai.events import event_types
from backend.globals import _progress_callback, _media_tool_results, _thread_local, _search_model
from backend.utils import _sanitize_error, _debug
from backend.llm.manager import LLMManager, _is_rate_limit_error
from backend.llm.selector import ModelSelector
from backend.media.manager import MediaGenerationManager
from backend.agents.factory import AgentFactory
from backend.agents.tool_registry import ToolRegistry
from backend.agents.registry import AgentRegistry
from backend.core.messenger import StateMessenger

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
        self.model_selector: ModelSelector | None = None
        if llm_manager._is_openrouter():
            self.model_selector = ModelSelector(
                llm_manager.api_key, llm_manager.base_url, llm_manager.temperature,
                rotator=None,
                default_model=llm_manager._default_model,
            )

    _TOOL_DESCRIPTIONS = {
        "search_web": "🔍 Searching the web...",
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
        if tool_name == "search_web" and isinstance(tool_args, dict):
            query = tool_args.get("query", "")
            if query:
                return f"🔍 Searching: {query[:60]}"
        elif tool_name == "generate_image" and isinstance(tool_args, dict):
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
                if idx < len(self._agent_specs):
                    task_desc = self._agent_specs[idx].get("task_description", "")
                _merge_and_send({idx: {"status": "running", "progress": 30, "current_task": task_desc, "current_tool": "", "tool_description": ""}})

        def on_tool_started(source, event: ToolUsageStartedEvent):
            idx = self._match_agent_index(event.agent_role)
            if idx >= 0:
                tool_desc = self._tool_description(event.tool_name, event.tool_args)
                _merge_and_send({idx: {"status": "running", "progress": 50, "current_tool": event.tool_name, "tool_description": tool_desc}})

        def on_tool_finished(source, event: ToolUsageFinishedEvent):
            idx = self._match_agent_index(event.agent_role)
            if idx >= 0:
                output_preview = str(event.output)[:5000] if event.output else ""
                _merge_and_send({idx: {"status": "running", "progress": 70, "current_tool": "", "tool_description": "", "output": output_preview}})

        def on_task_completed(source, event: TaskCompletedEvent):
            idx = self._match_agent_index(event.agent_role)
            if idx >= 0:
                output_raw = ""
                if hasattr(event, "output") and event.output:
                    output_raw = getattr(event.output, "raw", str(event.output))[:8000]
                status = "waiting_approval" if _has_media_tool(idx) else "complete"
                _merge_and_send({idx: {"status": status, "progress": 100, "current_task": "", "current_tool": "", "tool_description": "", "output": output_raw}})

        def on_agent_completed(source, event: AgentExecutionCompletedEvent):
            idx = self._match_agent_index(event.agent_role)
            if idx >= 0:
                status = "waiting_approval" if _has_media_tool(idx) else "complete"
                upd = {"status": status, "progress": 100, "current_task": "", "current_tool": "", "tool_description": ""}
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
    ) -> dict:
        global _progress_callback, _media_gen_manager, _media_tool_results, _search_model
        _progress_callback = self._progress_callback
        _media_gen_manager = self._media_gen_manager
        _media_tool_results = []  # Reset for this run
        total = len(agent_specs)
        self._agent_specs = agent_specs

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
        if pre_assigned_models and pre_assigned_models.get("workers"):
            model_assignment = pre_assigned_models
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

        self._main_loop = asyncio.get_event_loop()
        self._ctx = contextvars.copy_context()
        self._register_event_listeners()

        # Resolve actual model names: if model is "" (adaptive), find what get_llm() would pick
        for i, spec in enumerate(agent_specs):
            agent_name = spec.get("name", "")
            worker_model = model_assignment["workers"].get(agent_name, "")
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
                callback = self._agent_progress_callback
                ctx = self._ctx
                main_loop = self._main_loop
                if main_loop and ctx:
                    main_loop.create_task(callback(initial), context=ctx)
                else:
                    asyncio.ensure_future(callback(initial))

            manager = self.agent_factory.create_manager_agent(
                user_input, agent_specs, model_id=model_assignment["manager"]
            )

            # Run all worker agents in parallel — each in its own thread
            loop = asyncio.get_event_loop()

            def run_single_agent_sync(agent, task, spec, idx):
                """Run one agent on its task as a standalone Crew (sync, for thread pool).
                Falls back to local LLM on rate limit errors."""
                _thread_local.agent_name = spec.get("name", f"Agent {idx+1}")
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
                    if ("429" in err_msg or "rate limit" in err_msg.lower()) and self.llm_manager.local_fallback_enabled:
                        # Trigger cooldown and retry with local fallback LLM (dev-only)
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
                raw = getattr(single_result, "raw", str(single_result))
                name = spec.get("name", f"Agent {idx+1}")
                role = spec.get("role", "")
                _debug(f"[DEBUG-PARALLEL] Agent {name} completed, output_len={len(str(raw))}", flush=True)
                return {"name": name, "role": role, "output": str(raw)}

            # === Wave-based dependency-aware execution ===
            # Build dependency graph: compute waves (topological order)
            agent_name_to_idx = {agent_specs[i].get("name", f"Agent {i+1}"): i for i in range(len(agents))}
            print(f"[DEBUG-WAVES] agent_specs deps: {[(s.get('name'), s.get('depends_on', [])) for s in agent_specs]}", flush=True)
            completed_outputs: dict[str, str] = {}  # name -> output
            agent_outputs = [None] * len(agents)

            # Compute waves: agents with no unresolved depends_on go in current wave
            remaining = set(range(len(agents)))
            waves: list[list[int]] = []
            max_iterations = len(agents) + 1  # prevent infinite loop on circular deps
            iteration = 0
            while remaining and iteration < max_iterations:
                iteration += 1
                wave = []
                for i in list(remaining):
                    deps = agent_specs[i].get("depends_on", [])
                    # Check if all dependencies are satisfied (completed or not in this run)
                    all_satisfied = all(
                        dep_name in completed_outputs or dep_name not in agent_name_to_idx
                        for dep_name in deps
                    )
                    if all_satisfied:
                        wave.append(i)
                if not wave:
                    # Circular dependency or unresolvable — force remaining into one wave
                    wave = list(remaining)
                    print(f"[WARN] Circular/unresolvable dependencies detected, forcing remaining agents into one wave", flush=True)
                waves.append(wave)
                # Remove waved agents from remaining and mark as completed for next wave's dependency check
                for i in wave:
                    remaining.discard(i)
                    name = agent_specs[i].get("name", f"Agent {i+1}")
                    completed_outputs[name] = "__pending__"  # placeholder so dependents can proceed

            print(f"[DEBUG-WAVES] Execution plan: {len(waves)} wave(s): {[[agent_specs[i].get('name', '') for i in w] for w in waves]}", flush=True)

            # Execute wave by wave
            for wave_idx, wave in enumerate(waves):
                print(f"[DEBUG-WAVES] Starting wave {wave_idx+1}/{len(waves)}: {[agent_specs[i].get('name', '') for i in wave]}", flush=True)

                # Send progress: mark agents in this wave as running, previous waves as complete
                if self._agent_progress_callback and self._main_loop and self._ctx:
                    progress = self._build_progress({})
                    for i, spec in enumerate(agent_specs):
                        if i in wave:
                            progress[i]["status"] = "running"
                            progress[i]["progress"] = 10
                        elif any(i in w for w in waves[:wave_idx]):
                            progress[i]["status"] = "complete"
                            progress[i]["progress"] = 100
                        else:
                            progress[i]["status"] = "pending"
                    _ctx = self._ctx
                    _loop = self._main_loop
                    _cb = self._agent_progress_callback
                    _loop.call_soon_threadsafe(lambda p=progress: _loop.create_task(_async_progress_callback(_cb, p), context=_ctx))

                # Inject upstream context into tasks for agents with depends_on
                for i in wave:
                    deps = agent_specs[i].get("depends_on", [])
                    if deps:
                        context_parts = []
                        for dep_name in deps:
                            dep_output = completed_outputs.get(dep_name, "")
                            if dep_output:
                                context_parts.append(f"--- Output from {dep_name} ---\n{dep_output}")
                        if context_parts:
                            # Rebuild task with upstream context
                            upstream_context = "\n\n".join(context_parts)
                            tasks[i] = self.agent_factory.create_task(
                                agents[i], agent_specs[i], user_input + f"\n\n[UPSTREAM CONTEXT]\n{upstream_context}"
                            )
                            _debug(f"[DEBUG-WAVES] Agent {agent_specs[i].get('name', '')} received context from: {deps}", flush=True)
                        else:
                            print(f"[WARN-WAVES] Agent {agent_specs[i].get('name', '')} depends on {deps} but no upstream context available", flush=True)

                # Run wave agents in parallel
                wave_results = await asyncio.gather(
                    *[
                        loop.run_in_executor(
                            None, run_single_agent_sync,
                            agents[i], tasks[i], agent_specs[i], i
                        )
                        for i in wave
                    ],
                    return_exceptions=True,
                )

                # Collect wave results and mark agents as completed
                for j, i in enumerate(wave):
                    res = wave_results[j]
                    name = agent_specs[i].get("name", f"Agent {i+1}")
                    remaining.discard(i)
                    if isinstance(res, Exception):
                        role = agent_specs[i].get("role", "")
                        err_str = str(res)
                        _debug(f"[DEBUG-WAVES] Agent {name} failed: {_sanitize_error(res)}", flush=True)
                        agent_outputs[i] = {"name": name, "role": role, "output": f"Error: {err_str}"}
                        completed_outputs[name] = f"Error: {err_str}"
                        # Mark agent as error in progress so storyboard shows it immediately
                        if self._agent_progress_callback and self._main_loop and self._ctx:
                            err_updates = {i: {"status": "error", "progress": 100, "output": err_str[:8000]}}
                            with self._state_lock:
                                for idx, upd in err_updates.items():
                                    if idx not in self._agent_state:
                                        self._agent_state[idx] = {
                                            "name": agent_specs[idx].get("name", "Agent"),
                                            "role": agent_specs[idx].get("role", ""),
                                            "status": "pending",
                                            "progress": 0,
                                            "model": agent_specs[idx].get("model", ""),
                                        }
                                    self._agent_state[idx].update(upd)
                                progress = self._build_progress({}, self._agent_state)
                            _ctx2 = self._ctx
                            _loop2 = self._main_loop
                            _cb2 = self._agent_progress_callback
                            _loop2.call_soon_threadsafe(lambda p=progress: _loop2.create_task(_async_progress_callback(_cb2, p), context=_ctx2))
                    else:
                        agent_outputs[i] = res
                        completed_outputs[name] = res.get("output", "")

                # Send progress: mark agents in this wave as complete (or waiting_approval for media agents)
                if self._agent_progress_callback and self._main_loop and self._ctx:
                    wave_updates = {}
                    for i, spec in enumerate(agent_specs):
                        if i in wave:
                            agent_tools = spec.get("tools", [])
                            has_media_tool = any("image" in str(t).lower() or "video" in str(t).lower() or "generate" in str(t).lower() for t in agent_tools)
                            status = "waiting_approval" if has_media_tool else "complete"
                            print(f"[DEBUG-WAVE-STATUS] Agent {i} '{spec.get('name', '')}' tools={agent_tools} has_media={has_media_tool} → status={status}", flush=True)
                            upd = {"status": status, "progress": 100}
                            if agent_outputs[i]:
                                upd["output"] = (agent_outputs[i].get("output", "") or "")[:8000]
                            wave_updates[i] = upd
                        elif any(i in w for w in waves[:wave_idx]):
                            prev_tools = spec.get("tools", [])
                            prev_has_media = any("image" in str(t).lower() or "video" in str(t).lower() or "generate" in str(t).lower() for t in prev_tools)
                            wave_updates[i] = {"status": "waiting_approval" if prev_has_media else "complete", "progress": 100}
                    # Merge into persistent state and send
                    with self._state_lock:
                        for idx, upd in wave_updates.items():
                            if idx not in self._agent_state:
                                self._agent_state[idx] = {
                                    "name": agent_specs[idx].get("name", "Agent"),
                                    "role": agent_specs[idx].get("role", ""),
                                    "status": "pending",
                                    "progress": 0,
                                    "model": agent_specs[idx].get("model", ""),
                                }
                            self._agent_state[idx].update(upd)
                        progress = self._build_progress({}, self._agent_state)
                    _ctx2 = self._ctx
                    _loop2 = self._main_loop
                    _cb2 = self._agent_progress_callback
                    _loop2.call_soon_threadsafe(lambda p=progress: _loop2.create_task(_async_progress_callback(_cb2, p), context=_ctx2))

            # Filter None (shouldn't happen but safe)
            agent_outputs = [o for o in agent_outputs if o is not None]

            # Manager synthesizes all outputs
            _debug(f"[DEBUG-PARALLEL] Manager synthesizing {len(agent_outputs)} outputs", flush=True)

            # Send progress: all agents complete, Manager synthesizing
            if self._agent_progress_callback and self._main_loop and self._ctx:
                progress = self._build_progress({})
                for i, spec in enumerate(agent_specs):
                    progress[i]["status"] = "complete"
                    progress[i]["progress"] = 100
                    if i < len(agent_outputs):
                        progress[i]["output"] = (agent_outputs[i].get("output", "") or "")[:8000]
                progress.append({
                    "name": "Manager",
                    "role": "Synthesizing all agent outputs",
                    "status": "running",
                    "progress": 50,
                    "current_task": "Synthesizing all agent outputs into final response",
                })
                ctx = self._ctx
                loop = self._main_loop
                callback = self._agent_progress_callback

                def _schedule_manager_progress():
                    loop.create_task(
                        _async_progress_callback(callback, progress),
                        context=ctx,
                    )
                loop.call_soon_threadsafe(_schedule_manager_progress)

            synthesis_prompt = (
                f"User request: {user_input}\n\n"
                f"You are the Project Manager. Your team has completed their tasks.\n"
                f"Below are the outputs from each team member:\n\n"
            )
            for ao in agent_outputs:
                # Strip internal CrewAI markers from outputs before sending to manager
                clean_output = self._clean_agent_output(ao['output'])
                synthesis_prompt += f"--- {ao['name']} ({ao['role']}) ---\n{clean_output}\n\n"
            synthesis_prompt += (
                "\nPlease synthesize all outputs into a clean, user-friendly final response. "
                "Write it as if you are directly answering the user. "
                "Use clear headings, bullet points, and natural language. "
                "Do NOT include internal team member names, raw output markers, or technical metadata. "
                "Do NOT include phrases like 'Final Answer:', 'Task Completed:', or 'Crew Completion:'. "
                "Return only the final deliverable the user asked for."
            )

            manager_model = model_assignment.get("manager", "")
            if manager_model:
                manager_llm = self.llm_manager.build_llm_for_model(manager_model)
                manager_raw = await loop.run_in_executor(
                    None, manager_llm.call, synthesis_prompt
                )
            else:
                manager_raw = await loop.run_in_executor(
                    None, self.llm_manager.call_with_fallback, synthesis_prompt
                )

            # Clean manager output and add it to agent_outputs so it appears in result card
            clean_manager_output = self._clean_agent_output(str(manager_raw))
            agent_outputs.append({
                "name": "Manager",
                "role": "Project Manager",
                "output": clean_manager_output,
            })

            return {
                "raw": clean_manager_output,
                "agent_outputs": agent_outputs,
            }
        finally:
            _progress_callback = None
            _media_gen_manager = None
            _search_model = ""
            self._unregister_event_listeners()


# ============================================================
# Dashboard Manager

