"""Chainlit message handlers: on_chat_start, on_message."""

print("[CHAT-MODULE] Loaded chat.py v2 with DEBUG-URL", flush=True)

import asyncio
import base64
import contextvars
import json
import os
import re
import time
import traceback
import uuid
from datetime import datetime
from pathlib import Path

import chainlit as cl
from backend.core.crewai_patch import *  # noqa: F401,F403 — monkey-patch CrewAI multimodal support
from backend.globals import *
from backend import globals as _g
from backend.utils import _sanitize_error, _debug
from backend.llm.manager import LLMManager, _is_rate_limit_error
from backend.llm.catalog import ModelCatalog
from backend.llm.discovery import ModelDiscoveryService
from backend.llm.selector import ModelSelector
from backend.media.manager import MediaGenerationManager
from backend.agents.registry import AgentRegistry
from backend.agents.task_store import TaskStore
from backend.agents.chat_store import ChatStore
from backend.agents.tool_registry import ToolRegistry
from backend.agents.team_registry import TeamRegistry
from backend.agents.history_store import HistoryStore
from backend.agents.template_store import TaskTemplateStore
from backend.agents.schedule_store import ScheduledTaskStore
from backend.core.scheduler import get_scheduler
from backend.core.secretary import CentralManager
from backend.core.orchestrator import ExecutionOrchestrator
from backend.core.messenger import StateMessenger
from backend.attachment.processor import process_attachment, process_url
from backend.attachment.security import check_model_modality_support, llm_manager_tier_check
from backend.attachment.url import classify_url, find_urls_in_text
from backend.handlers.actions import (
    on_action_create_agent,
    on_action_accept,
    on_action_reject,
    on_action_cancel,
    on_action_confirm_tuning,
    on_action_reject_tuning,
    on_action_add_agent_form,
    on_action_edit_agent_form,
    on_action_delete_agent,
    on_action_assign_task_form,
    on_action_create_team,
    on_action_update_team,
    on_action_delete_team,
    on_action_delete_chat_session,
    on_action_config_agent,
)
from schemas import (
    PlanAgentItem, ResultAgentItem, AgentProgressEntry,
    ChatReplyText, ChatReplyPlanValidationError, ChatReplyPlan, ChatReplyProgress, ChatReplyAgentProgress,
    ChatReplyResult, ChatReplyImageApproval, ChatReplyImageResult,
    ChatReplyModelCatalog, ModelCatalogItem,
    ChatReplyAudioResult, ChatReplyTranscriptionResult, ChatReplyVideoResult, ChatReplyFileResult,
    StatePayload, chat_reply,
)


def get_messenger() -> StateMessenger:
    return cl.user_session.get("messenger")


async def execute_multi_agent_task(
    user_input: str,
    agent_specs: list[dict],
    registry: AgentRegistry,
):
    """รัน Task กับหลาย Agent พร้อมกันใน Crew เดียว"""
    cl.user_session.set("state", STATE_EXECUTING)
    messenger = get_messenger()
    task_id = str(uuid.uuid4())[:8]
    from backend.globals import _thread_local, user_prompt_ctx
    _thread_local.user_prompt = user_input[:200]
    user_prompt_ctx.set(user_input[:200])

    if messenger:
        agent_names = ", ".join(s.get("name", "Agent") for s in agent_specs)
        await messenger.add_task(task_id, user_input, agent_names)
        messenger.log_history(task_id, user_input[:80], "User", "สั่งงาน: ", user_input[:200])
        messenger.log_history(task_id, user_input[:80], "Manager", "รับคำสั่ง สร้าง plan")
        initial_agents = [
            {
                "name": s.get("name", "Agent"),
                "role": s.get("role", ""),
                "status": "pending",
                "progress": 0,
                "model": s.get("model", ""),
            }
            for s in agent_specs
        ]
        await messenger.reply_agent_progress(task_id, initial_agents)

    for spec in agent_specs:
        rid = spec.get("registry_id")
        if rid:
            registry.update_status(rid, "Busy")
    if messenger:
        await messenger.update_agents(registry)

    _exec_loop = asyncio.get_event_loop()
    _exec_ctx = contextvars.copy_context()
    agent_outputs = []

    def update_progress(percent: int, status: str):
        if messenger:
            def _schedule():
                _exec_loop.create_task(
                    messenger.update_task(task_id, progress=percent, result=status),
                    context=_exec_ctx,
                )
            _exec_loop.call_soon_threadsafe(_schedule)

    async def update_agent_progress(agents_progress: list[dict]):
        if messenger:
            await messenger.reply_agent_progress(task_id, agents_progress)

    try:
        llm_manager = LLMManager()
        selected_model = cl.user_session.get("selected_model") or llm_manager.get_selected_model_name()
        if selected_model and llm_manager._is_openrouter():
            llm_manager.set_selected_model(selected_model)
        tool_registry = ToolRegistry()
        orchestrator = ExecutionOrchestrator(llm_manager, tool_registry, update_progress, update_agent_progress)
        cl.user_session.set("orchestrator", orchestrator)
        pre_assigned = cl.user_session.get("pre_assigned_models")
        print(f"[DEBUG-EXEC] Starting with {len(agent_specs)} agents, pre_assigned={pre_assigned}", flush=True)
        for spec in agent_specs:
            name = spec.get("name", "")
            if pre_assigned and name and pre_assigned.get("workers", {}).get(name):
                spec["model"] = pre_assigned["workers"][name]
            if not spec.get("model"):
                spec["model"] = ""
        if messenger and not pre_assigned:
            await messenger.notify(f"⚙️ กำลังกำหนด model ให้ {len(agent_specs)} agents...")
        if messenger:
            await messenger.notify("🔥 Crew เริ่มทำงานแล้ว — รอผลลัพธ์...")
        print(f"[DEBUG-EXEC] Calling orchestrator.run_async...", flush=True)
        result = await orchestrator.run_async(user_input, agent_specs, pre_assigned_models=pre_assigned, task_id=task_id, task_title=user_input[:80], messenger=messenger)
        print(f"[DEBUG-EXEC] orchestrator.run_async completed successfully", flush=True)
        cl.user_session.set("pre_assigned_models", None)

        raw_output = result.get("raw", str(result))
        agent_outputs = result.get("agent_outputs", [])
        agent_memories = result.get("agent_memories", {})

        # Store last task context for feedback tuning
        cl.user_session.set("last_task_result", raw_output[:6000])
        cl.user_session.set("last_agent_specs", agent_specs)
        cl.user_session.set("last_user_input", user_input)

        if messenger:
            final_agents = []
            for i, spec in enumerate(agent_specs):
                out = agent_outputs[i] if i < len(agent_outputs) else {}
                final_agents.append({
                    "name": spec.get("name", "Agent"),
                    "role": spec.get("role", ""),
                    "status": "complete",
                    "progress": 100,
                    "output": (out.get("output", "") or "")[:6000],
                    "model": spec.get("model", ""),
                })
            # Add Manager as complete in final progress so frontend stops showing "Synthesizing"
            manager_output = next((a for a in agent_outputs if a.get("name") == "Manager"), None)
            if manager_output:
                final_agents.append({
                    "name": "Manager",
                    "role": "Project Manager",
                    "status": "complete",
                    "progress": 100,
                    "output": (manager_output.get("output", "") or "")[:8000],
                    "model": "",
                })
            await messenger.reply_agent_progress(task_id, final_agents)

            cl.run_sync(
                messenger.update_task(
                    task_id,
                    progress=100,
                    status="complete",
                    result=raw_output,
                    agent_outputs=agent_outputs,
                    agent_progress=final_agents,
                )
            )

            def _day_sort_key(item):
                prompt_lower = item.get("prompt", "").lower()
                for day_num in range(1, 10):
                    if f"day {day_num}" in prompt_lower or f"day{day_num}" in prompt_lower:
                        return day_num
                return 99
            sorted_results = sorted(_g._media_tool_results, key=lambda r: (0 if r.get("type") == "image" else 1, _day_sort_key(r)))

            has_reviewer = any(
                any(kw in (spec.get("role", "") + spec.get("name", "")).lower()
                    for kw in ["review", "quality", "checker", "approver", "editor"])
                for spec in agent_specs
            )

            if has_reviewer and sorted_results and llm_manager:
                print(f"[APPROVAL-FLOW] Plan has reviewer — refining {len(sorted_results)} prompts via manager LLM", flush=True)
                await messenger.notify("🔍 Reviewer กำลังตรวจสอบ prompt สำหรับสื่อ...")
                try:
                    prompts_text = "\n".join(
                        f"{i+1}. [{r.get('type','image')}] {r.get('prompt','')}"
                        for i, r in enumerate(sorted_results)
                    )
                    review_prompt = (
                        f"You are reviewing image/video generation prompts for quality.\n"
                        f"Original prompts from agents:\n{prompts_text}\n\n"
                        f"For each prompt, check: clarity, visual detail, English quality, alignment with the task.\n"
                        f"If a prompt is good, keep it as-is. If it needs improvement, rewrite it.\n"
                        f"Return ONLY the refined prompts, one per line, prefixed with the index number and type.\n"
                        f"Format: N. [type] refined prompt here"
                    )
                    refined = llm_manager.call_with_fallback(review_prompt, caller="prompt_refinement")
                    for line in refined.strip().split("\n"):
                        line = line.strip()
                        m = re.match(r'^(\d+)\.\s*\[?(\w+)\]?\s*(.+)', line)
                        if m:
                            idx = int(m.group(1)) - 1
                            if 0 <= idx < len(sorted_results):
                                sorted_results[idx]["prompt"] = m.group(3).strip()
                    print(f"[APPROVAL-FLOW] Prompts refined by reviewer", flush=True)
                except Exception as e:
                    print(f"[APPROVAL-FLOW] Review failed, using original prompts: {_sanitize_error(e)}", flush=True)
            else:
                print(f"[APPROVAL-FLOW] No reviewer in plan — prompts are final from agent", flush=True)

            async def _send_approval_card(media_result, idx):
                media_type = media_result.get("type", "image")
                media_prompt = media_result.get("prompt", "")
                media_duration = media_result.get("duration", 5)
                agent_name = media_result.get("agent_name", "")
                if not agent_name:
                    tool_name = "generate_image" if media_type == "image" else "generate_video"
                    for spec in agent_specs:
                        if tool_name in spec.get("tools", []):
                            agent_name = spec.get("name", "")
                            break
                _debug(f"[DEBUG-APPROVAL] Sending approval card: agent_name='{agent_name}', type={media_type}, prompt_len={len(media_prompt)}", flush=True)
                if not media_prompt:
                    return
                approval_id = f"{media_type}_{task_id}_{idx}"
                cl.user_session.set(f"pending_media_{approval_id}", {
                    "prompt": media_prompt,
                    "agent_name": agent_name,
                    "task_id": task_id,
                    "media_type": media_type,
                    "duration": media_duration,
                })
                await messenger.reply_image_approval(
                    media_prompt, approval_id, agent_name,
                    media_type=media_type, duration=media_duration,
                    model=media_result.get("model", "")
                )

            # Collect all approval cards data (don't send yet)
            pending_approval_cards = []
            for idx, media_result in enumerate(sorted_results):
                pending_approval_cards.append((media_result, idx))

            if not any(r.get("type") == "video" for r in _g._media_tool_results):
                for i, agent_out in enumerate(agent_outputs):
                    agent_spec = agent_specs[i] if i < len(agent_specs) else {}
                    if "generate_video" not in agent_spec.get("tools", []):
                        continue
                    output_text = agent_out.get("output", "")
                    vid_match = re.search(
                        r'"name"\s*:\s*"generate_video"\s*,\s*"arguments"\s*:\s*\{[^}]*"prompt"\s*:\s*"([^"]+)"',
                        output_text
                    )
                    if vid_match:
                        vid_prompt = vid_match.group(1)
                        _debug(f"[DEBUG-FALLBACK] Extracted video prompt from agent output: {vid_prompt[:80]}...", flush=True)
                        media_entry = {
                            "type": "video", "prompt": vid_prompt,
                            "duration": 5, "agent_name": agent_out.get("name", ""),
                        }
                        _g._media_tool_results.append(media_entry)
                        pending_approval_cards.append((media_entry, len(_g._media_tool_results) - 1))

            if not any(r.get("type") == "image" for r in _g._media_tool_results):
                for i, agent_out in enumerate(agent_outputs):
                    agent_spec = agent_specs[i] if i < len(agent_specs) else {}
                    if "generate_image" not in agent_spec.get("tools", []):
                        continue
                    output_text = agent_out.get("output", "")
                    img_match = re.search(r'```\s*\n([A-Za-z][^`]{20,})\n```', output_text)
                    if not img_match:
                        img_match = re.search(r'Prompt[:\s]+([A-Za-z][^\n]{20,})', output_text)
                    if img_match:
                        img_prompt = img_match.group(1).strip()
                        image_model = cl.user_session.get("ai_image_model") or ""
                        _debug(f"[DEBUG-FALLBACK] Extracted image prompt from agent output: {img_prompt[:80]}...", flush=True)
                        media_entry = {
                            "type": "image", "prompt": img_prompt,
                            "agent_name": agent_out.get("name", ""),
                            "model": image_model,
                        }
                        _g._media_tool_results.append(media_entry)
                        pending_approval_cards.append((media_entry, len(_g._media_tool_results) - 1))

            has_pending_approvals = len(_g._media_tool_results) > 0
            print(f"[DEBUG-RESULT] media_tool_results={len(_g._media_tool_results)}, has_pending={has_pending_approvals}", flush=True)
            print(f"[DEBUG-synth] chat.py: about to call reply_result, agent_outputs={len(agent_outputs)}", flush=True)
            if has_pending_approvals:
                await messenger.reply_result(
                    f"⏳ งานเสร็จแล้ว — รออนุมัติสร้างสื่อ ({len(_g._media_tool_results)} รายการ) — ดูผลลัพธ์ใน Storyboard",
                    agent_outputs,
                )
            else:
                await messenger.reply_result(
                    f"✅ งานเสร็จสมบูรณ์ ({len(agent_specs)} agents)",
                    agent_outputs,
                )

            # Send AI response first, then approval cards
            if raw_output and len(raw_output) > 20 and not raw_output.strip().startswith("{"):
                await messenger.reply(raw_output[:4000])

            # Now send approval cards after AI response
            for media_result, idx in pending_approval_cards:
                await _send_approval_card(media_result, idx)

            # Update task status to review (user can review results)
            task_store = cl.user_session.get("task_store")
            current_task_id = cl.user_session.get("current_task_id")
            if task_store and current_task_id:
                task_store.update_task(current_task_id, status="review", progress=100)
                await messenger.update_tasks(task_store)
    except Exception as e:
        tb = traceback.format_exc()
        print(f"[CREW ERROR] {_sanitize_error(e)}", flush=True)
        print(f"[CREW ERROR] Type: {type(e).__name__}, Args: {e.args}", flush=True)
        _debug(f"[TRACEBACK] {tb}", flush=True)
        # Store failed task context for retry
        cl.user_session.set("last_failed_task", {
            "user_input": user_input,
            "agent_specs": agent_specs,
            "pre_assigned_models": pre_assigned,
            "error": str(e),
        })
        if _is_rate_limit_error(e):
            llm_mgr = LLMManager()
            llm_mgr.report_rate_limit()
            if messenger:
                if llm_mgr.local_fallback_enabled:
                    await messenger.reply("⚠️ ติดลิมิตการใช้ AI ฝรั่ง กำลังสลับไปใช้ Local LLM ชั่วคราว (60 วินาที)")
                else:
                    await messenger.reply("⚠️ ติดลิมิตการใช้ OpenRouter — กรุณารอสักครู่แล้วลองใหม่ (Local fallback ปิดอยู่)")
        if messenger:
            cl.run_sync(
                messenger.update_task(
                    task_id,
                    progress=100,
                    status="error",
                    result=f"❌ เกิดข้อผิดพลาด: {str(e)}\n\n```\n{tb[:1000]}\n```",
                )
            )
            await messenger.reply_progress(100, "❌ งานล้มเหลว", progress_id=task_id)
            await messenger.reply_result(
                "❌ งานล้มเหลว",
                [{"name": "Error", "role": "", "output": f"{str(e)}\n\n{tb[:500]}"}],
                is_error=True,
            )
    finally:
        for spec in agent_specs:
            rid = spec.get("registry_id")
            if rid:
                registry.update_status(rid, "Idle")
                # Auto-learning: store task outcome as learning
                agent_output = None
                for out in agent_outputs:
                    if out.get("agent") == spec.get("name") or out.get("name") == spec.get("name"):
                        agent_output = out.get("output", "")[:500]
                        break
                if agent_output:
                    registry.add_learning(rid, {
                        "type": "task_completion",
                        "lesson": f"Task: {user_input[:100]} → Output: {agent_output[:200]}",
                        "timestamp": datetime.now().isoformat(),
                    })
                # Store rejection feedback as experiential learning
                agent_name = spec.get("name", "")
                mem_entries = agent_memories.get(agent_name, [])
                for mem in mem_entries:
                    feedback = mem.get("feedback", "")
                    if feedback:
                        registry.add_learning(rid, {
                            "type": "rejection_feedback",
                            "lesson": f"Rejected output feedback: {feedback[:300]}",
                            "timestamp": datetime.now().isoformat(),
                        })
        if messenger:
            await messenger.update_agents(registry)
        cl.user_session.set("state", STATE_IDLE)
        cl.user_session.set("current_agent_specs", None)
        cl.user_session.set("current_input", None)
        cl.user_session.set("attachment_context", None)
        cl.user_session.set("attachment_crewai_files", None)
        cl.user_session.set("attachment_plugins", None)


async def execute_task_with_agent(
    user_input: str,
    agent_spec: dict,
    registry_id: str | None,
    registry: AgentRegistry,
):
    """รัน Task กับ Agent ที่ระบุ พร้อมอัปเดต Task Slot และ Registry Status"""
    cl.user_session.set("state", STATE_EXECUTING)
    messenger = get_messenger()
    task_id = str(uuid.uuid4())[:8]
    agent_name = agent_spec.get("name", "Agent")
    from backend.globals import _thread_local, user_prompt_ctx
    _thread_local.user_prompt = user_input[:200]
    user_prompt_ctx.set(user_input[:200])

    if messenger:
        await messenger.add_task(task_id, user_input, agent_name)
        messenger.log_history(task_id, user_input[:80], "User", "สั่งงาน: ", user_input[:200])
        messenger.log_history(task_id, user_input[:80], "Manager", "รับคำสั่ง สร้าง plan")

    if registry_id:
        registry.update_status(registry_id, "Busy")
        if messenger:
            await messenger.update_agents(registry)

    _exec_loop = asyncio.get_event_loop()
    _exec_ctx = contextvars.copy_context()
    task_result = None

    def update_progress(percent: int, status: str):
        if messenger:
            def _schedule():
                _exec_loop.create_task(
                    messenger.update_task(task_id, progress=percent, result=status),
                    context=_exec_ctx,
                )
            _exec_loop.call_soon_threadsafe(_schedule)

    try:
        llm_manager = LLMManager()
        tool_registry = ToolRegistry()
        orchestrator = ExecutionOrchestrator(llm_manager, tool_registry, update_progress)
        result = await orchestrator.run_async(user_input, [agent_spec], task_id=task_id, task_title=user_input[:80], messenger=messenger)
        task_result = result

        # Store last task context for feedback tuning
        cl.user_session.set("last_task_result", str(result)[:6000])
        cl.user_session.set("last_agent_specs", [agent_spec])
        cl.user_session.set("last_user_input", user_input)

        if messenger:
            cl.run_sync(
                messenger.update_task(
                    task_id,
                    progress=100,
                    status="complete",
                    result=str(result),
                )
            )
            await messenger.notify(f"✅ งานของ {agent_name} เสร็จสมบูรณ์")
    except Exception as e:
        tb = traceback.format_exc()
        print(f"[CREW ERROR] {_sanitize_error(e)}")
        _debug(f"[TRACEBACK] {tb}", flush=True)
        # Store failed task context for retry
        cl.user_session.set("last_failed_task", {
            "user_input": user_input,
            "agent_specs": [agent_spec],
            "pre_assigned_models": None,
            "error": str(e),
        })
        if _is_rate_limit_error(e):
            llm_mgr = LLMManager()
            llm_mgr.report_rate_limit()
            if messenger:
                await messenger.notify("⚠️ ติดลิมิต AI ฝรั่ง สลับไป Local LLM ชั่วคราว (60 วินาที)")
        if messenger:
            cl.run_sync(
                messenger.update_task(
                    task_id,
                    progress=100,
                    status="error",
                    result=f"❌ เกิดข้อผิดพลาด: {str(e)}\n\n```\n{tb[:1000]}\n```",
                )
            )
            await messenger.notify(f"❌ งานของ {agent_name} ล้มเหลว")
    finally:
        if registry_id:
            registry.update_status(registry_id, "Idle")
            # Auto-learning: store task outcome
            if task_result:
                result_str = str(task_result)[:500]
                registry.add_learning(registry_id, {
                    "type": "task_completion",
                    "lesson": f"Task: {user_input[:100]} → Output: {result_str[:200]}",
                    "timestamp": datetime.now().isoformat(),
                })
            if messenger:
                await messenger.update_agents(registry)
        cl.user_session.set("state", STATE_IDLE)
        cl.user_session.set("current_agent_specs", None)
        cl.user_session.set("current_input", None)
        cl.user_session.set("current_registry_id", None)
        cl.user_session.set("attachment_context", None)
        cl.user_session.set("attachment_crewai_files", None)
        cl.user_session.set("attachment_plugins", None)


def _restore_conversation_history(session_id: str, chat_store: ChatStore) -> list[dict]:
    """Rebuild conversation_history from persisted chat_store messages.

    Filters to LLM-relevant messages only (user, text, plan, result, tuning_proposal).
    Caps at last 20 entries, truncates each content to 4000 chars.
    """
    session = chat_store.get_session(session_id)
    if not session:
        return []
    messages = session.get("messages", [])
    history = []
    for msg in messages:
        role = msg.get("role", "")
        msg_type = msg.get("messageType", "text")
        content = ""
        if role == "user":
            content = msg.get("content", "")
        elif role == "assistant":
            if msg_type == "text":
                content = msg.get("content", "")
            elif msg_type == "plan":
                summary = msg.get("planSummary", "")
                agents = msg.get("planAgents", [])
                agent_names = [a.get("name", "") for a in agents] if isinstance(agents, list) else []
                content = f"Proposed plan: {summary}. Agents: {', '.join(agent_names)}"
            elif msg_type == "result":
                content = f"Task result: {msg.get('resultSummary', '')}"
            elif msg_type == "tuning_proposal":
                content = "Agent tuning proposed."
            else:
                continue
        else:
            continue
        if not content:
            continue
        if len(content) > 4000:
            content = content[:4000] + "..."
        history.append({"role": role, "content": content})
    return history[-20:]


@cl.on_chat_start
async def on_chat_start():
    # Disable CrewAI trace prompt — it blocks on stdin input in non-interactive mode
    try:
        from crewai.events.listeners.tracing.utils import mark_first_execution_done
        mark_first_execution_done(user_consented=False)
    except Exception:
        pass

    # Auth check — get token from user_env (passed via socket userEnv field)
    user_env = cl.user_session.get("env") or {}
    auth_token = ""
    if isinstance(user_env, dict):
        auth_token = user_env.get("authToken") or user_env.get("auth_token") or ""
    if not auth_token:
        auth_token = cl.user_session.get("authToken") or cl.user_session.get("auth_token") or ""
    user_id = None
    username = ""

    if auth_token:
        from backend.auth.session import SessionManager
        from backend.auth.user_store import UserStore
        _session_mgr = SessionManager()
        _user_store = UserStore()
        user_id = _session_mgr.verify_token(auth_token)
        if user_id:
            profile = _user_store.get_by_id(user_id)
            if profile:
                username = profile.get("username", "")
                _user_store.update_last_login(user_id)
        else:
            cl.user_session.set("auth_token", None)

    # Fallback: dev mode without auth — use legacy paths
    cl.user_session.set("user_id", user_id)

    registry = AgentRegistry(user_id=user_id)
    cl.user_session.set("registry", registry)
    cl.user_session.set("state", STATE_IDLE)
    cl.user_session.set("current_agent_specs", None)
    cl.user_session.set("current_input", None)
    cl.user_session.set("current_registry_id", None)

    team_registry = TeamRegistry(user_id=user_id)
    cl.user_session.set("team_registry", team_registry)

    chat_store = ChatStore(user_id=user_id)
    cl.user_session.set("chat_store", chat_store)
    # Create default session if none exists
    sessions = chat_store.list_sessions()
    if not sessions:
        default = chat_store.create_session("New Chat")
        current_session_id = default["id"]
    else:
        current_session_id = sessions[0]["id"]
        # Restore team_id from the session if available
        first_session = chat_store.get_session(current_session_id)
        if first_session and first_session.get("team_id"):
            cl.user_session.set("current_team_id", first_session["team_id"])

    # Restore conversation history from persisted session
    cl.user_session.set("conversation_history", _restore_conversation_history(current_session_id, chat_store))

    messenger = StateMessenger(task_store=TaskStore(user_id=user_id), chat_store=chat_store, history_store=HistoryStore(user_id=user_id))
    messenger.current_session_id = current_session_id
    cl.user_session.set("messenger", messenger)
    await messenger.init(registry)
    await messenger.set_status("Ready")
    await messenger.reply_chat_sessions()
    await messenger.reply_team_list(team_registry)
    await messenger.reply_chat_history(current_session_id)
    await messenger.reply_notifications()

    # Restore plan approval state if last message is a pending plan
    session = chat_store.get_session(current_session_id)
    if session and session.get("messages"):
        last_msg = session["messages"][-1]
        if last_msg.get("messageType") == "plan" and last_msg.get("planStatus") == "pending":
            cl.user_session.set("state", STATE_AWAITING_APPROVAL)
            cl.user_session.set("current_agent_specs", last_msg.get("agentSpecs", []))
            cl.user_session.set("current_input", last_msg.get("currentInput", ""))
            pre_assigned = last_msg.get("modelAssignment", {})
            if pre_assigned:
                cl.user_session.set("pre_assigned_models", pre_assigned)
            print(f"[DEBUG-RESTORE] Restored STATE_AWAITING_APPROVAL from pending plan", flush=True)

    # Restore user settings from persisted session
    settings = chat_store.get_settings(current_session_id)
    if settings.get("current_team_id"):
        cl.user_session.set("current_team_id", settings["current_team_id"])
    if settings.get("selected_model"):
        cl.user_session.set("selected_model", settings["selected_model"])
    else:
        # Fall back to manager agent's model from registry
        for a in registry.list_agents():
            if a.get("is_manager") or a.get("role", "").lower() == "manager":
                mgr_model = a.get("model", "")
                if mgr_model:
                    cl.user_session.set("selected_model", mgr_model)
                break
    # Restore media model overrides
    for key in ("ai_image_model", "ai_video_model", "ai_search_model", "ai_tts_model", "ai_stt_model", "ai_vision_model"):
        if settings.get(key):
            cl.user_session.set(key, settings[key])

    # Start background scheduler for recurring tasks
    scheduler = get_scheduler()
    await scheduler.start()

    # Send model catalog with resolved model name so frontend shows proper names
    try:
        llm_mgr = LLMManager()
        if llm_mgr._is_openrouter():
            catalog = ModelCatalog(llm_mgr.api_key, llm_mgr.base_url)
            loop = asyncio.get_event_loop()
            recommended = await loop.run_in_executor(None, catalog.get_recommended)
            selected = cl.user_session.get("selected_model") or ""
            await messenger.reply_model_catalog(recommended, [], selected)

            # Also fetch and send media catalogs (image + video + search)
            selector = ModelSelector(llm_mgr.api_key, llm_mgr.base_url)
            all_models = await loop.run_in_executor(None, selector._fetch_all_models)
            for media_type in ("image", "video", "search", "vision"):
                filtered = []
                for m in all_models:
                    arch = m.get("architecture", {})
                    output_modalities = arch.get("output_modalities", [])
                    input_modalities = arch.get("input_modalities", [])
                    mid = m.get("id", "").lower()
                    # Skip OpenRouter routing models — they are text-only, not real media models
                    if mid.startswith("openrouter/"):
                        continue
                    if media_type == "image" and "image" in output_modalities:
                        filtered.append(m)
                    elif media_type == "video" and "video" in output_modalities:
                        filtered.append(m)
                    elif media_type == "vision" and "image" in input_modalities:
                        filtered.append(m)
                    elif media_type == "search":
                        params = m.get("supported_parameters", [])
                        search_keywords = ["sonar", "perplexity", "search", "online"]
                        if "web_search" in params or any(kw in mid for kw in search_keywords):
                            filtered.append(m)
                if not filtered:
                    continue
                entries = []
                for m in filtered:
                    mid = m.get("id", "")
                    name = m.get("name", mid)
                    pricing = m.get("pricing", {})
                    def _convert(price):
                        try:
                            return round(float(price) * 1_000_000, 6)
                        except (ValueError, TypeError):
                            return price if price else "?"
                    prompt_price = _convert(pricing.get("prompt", "?"))
                    comp_price = _convert(pricing.get("completion", "?"))
                    image_price = _convert(pricing.get("image", "?"))
                    video_price = _convert(pricing.get("video", "?"))
                    audio_price = _convert(pricing.get("audio", "?"))
                    web_search_price = _convert(pricing.get("web_search", "?"))
                    all_prices = [prompt_price, comp_price, image_price, video_price, audio_price, web_search_price]
                    known_prices = [p for p in all_prices if isinstance(p, (int, float))]
                    is_free = len(known_prices) > 0 and all(p == 0 for p in known_prices)
                    entries.append({
                        "id": mid,
                        "name": name,
                        "context_length": m.get("context_length", "?"),
                        "prompt_price": prompt_price,
                        "completion_price": comp_price,
                        "image_price": image_price,
                        "video_price": video_price,
                        "audio_price": audio_price,
                        "web_search_price": web_search_price,
                        "categories": [media_type],
                        "is_free": is_free,
                    })
                grouped = {media_type: entries}
                print(f"[CHAT-START] Sending media catalog for {media_type}: {len(entries)} models", flush=True)
                await messenger.reply_model_catalog(grouped, [], "", catalog_type="media")
    except Exception as e:
        print(f"[CHAT-START] Failed to send model catalog: {_sanitize_error(e)}", flush=True)



# ============================================================
# Message Router
# ============================================================
def _parse_json_command(text: str) -> dict | None:
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and parsed.get("type") == "action":
            return {
                "name": parsed.get("name"),
                "payload": parsed.get("payload", {}),
            }
    except (json.JSONDecodeError, ValueError):
        return None
    return None


@cl.on_message
async def on_message(message: cl.Message):
    print(f"[DEBUG-MSG] on_message called, content[:100]={message.content[:100]}", flush=True)
    state = cl.user_session.get("state") or STATE_IDLE
    user_input = message.content
    registry = cl.user_session.get("registry")
    if not registry:
        registry = AgentRegistry(user_id=cl.user_session.get("user_id"))
        cl.user_session.set("registry", registry)
    messenger = get_messenger()

    # Parse mode prefix: __mode:chat__ or __mode:plan__
    input_mode = "plan"
    mode_match = re.match(r'^__mode:(chat|plan)__\n', user_input)
    if mode_match:
        input_mode = mode_match.group(1)
        user_input = user_input[mode_match.end():]

    # Extract attachment data from message (support multiple attachments)
    attachments = []
    attachment_matches = re.findall(r'\[ATTACHMENT\|([^\|]+)\|([^\|]+)\|([^\]]+)\]', user_input)
    if attachment_matches:
        for file_url, file_name, file_mime in attachment_matches:
            attachments.append({"file_url": file_url, "file_name": file_name, "file_mime": file_mime})
        # Remove all attachment markers from user_input before processing
        user_input = re.sub(r'\n\n\[ATTACHMENT\|[^\]]+\]', '', user_input).strip()
        # Store attachments list in session for later use
        cl.user_session.set("last_attachments", attachments)
        # Also set single-attachment vars for backward compat (first file)
        cl.user_session.set("last_attachment_url", attachments[0]["file_url"])
        cl.user_session.set("last_attachment_name", attachments[0]["file_name"])
        cl.user_session.set("last_attachment_mime", attachments[0]["file_mime"])
        print(f"[ATTACHMENT] {len(attachments)} files: {[a['file_name'] for a in attachments]}", flush=True)

    # Set user_prompt for LLM call logging (covers all entry paths: chat, plan, feedback)
    from backend.globals import _thread_local, user_prompt_ctx
    _thread_local.user_prompt = user_input[:200]
    user_prompt_ctx.set(user_input[:200])

    # Handle JSON action commands from custom frontend
    command = _parse_json_command(user_input)
    if command:
        action_name = command.get("name")
        payload = command.get("payload") or {}
        if action_name == "accept_plan":
            await on_action_accept(cl.Action(name="accept_plan", payload=payload))
        elif action_name == "reject_plan":
            await on_action_reject(cl.Action(name="reject_plan", payload=payload))
        elif action_name == "cancel_plan":
            await on_action_cancel(cl.Action(name="cancel_plan", payload=payload))
        elif action_name == "confirm_tuning":
            await on_action_confirm_tuning(cl.Action(name="confirm_tuning", payload=payload))
        elif action_name == "reject_tuning":
            await on_action_reject_tuning(cl.Action(name="reject_tuning", payload=payload))
        elif action_name == "confirm_create_agent":
            await on_action_create_agent(cl.Action(name="confirm_create_agent", payload=payload))
        elif action_name == "add_agent_form":
            await on_action_add_agent_form(cl.Action(name="add_agent_form", payload=payload))
        elif action_name == "edit_agent_form":
            await on_action_edit_agent_form(cl.Action(name="edit_agent_form", payload=payload))
        elif action_name == "delete_agent":
            await on_action_delete_agent(cl.Action(name="delete_agent", payload=payload))
        elif action_name == "assign_task_form":
            await on_action_assign_task_form(cl.Action(name="assign_task_form", payload=payload))
        elif action_name == "delete_task":
            task_id = payload.get("task_id", "")
            if messenger and task_id:
                await messenger.delete_task(task_id)
        elif action_name == "refresh_credits":
            if messenger:
                await messenger._send(trigger="refresh")
        elif action_name == "approve_image":
            approval_id = payload.get("approval_id", "")
            model_override = payload.get("model", "")
            print(f"[APPROVE] approval_id={approval_id}, model_override={model_override}", flush=True)
            # Persist approval status so it survives refresh
            if messenger:
                messenger.update_approval_status(approval_id, "approved")
            pending = cl.user_session.get(f"pending_media_{approval_id}")
            if pending and messenger:
                prompt = pending["prompt"]
                task_id = pending.get("task_id")
                media_type = pending.get("media_type", "image")
                duration = pending.get("duration", 5)
                print(f"[APPROVE] Generating {media_type}, model_override={model_override or cl.user_session.get('ai_image_model')}, prompt={prompt[:60]}...", flush=True)
                try:
                    llm_mgr = LLMManager()
                    gen_mgr = MediaGenerationManager(llm_mgr)
                    resolved_image_model = model_override or cl.user_session.get("ai_image_model") or ""
                    resolved_video_model = model_override or cl.user_session.get("ai_video_model") or ""
                    print(f"[APPROVE] Resolved models: image={resolved_image_model!r}, video={resolved_video_model!r}, ai_image_model={cl.user_session.get('ai_image_model')!r}", flush=True)
                    gen_mgr.set_models(
                        image_model=resolved_image_model,
                        video_model=resolved_video_model,
                    )
                    if media_type == "video":
                        if not resolved_video_model:
                            await messenger.reply("⚠️ ยังไม่ได้เลือก Video model — กรุณาเลือก model สำหรับสร้างวิดีโอก่อนกดอนุมัติ")
                            return
                        result = await asyncio.to_thread(gen_mgr.generate_video, prompt, duration=duration)
                    else:
                        if not resolved_image_model:
                            await messenger.reply("⚠️ ยังไม่ได้เลือก Image model — กรุณาเลือก model สำหรับสร้างรูปภาพก่อนกดอนุมัติ")
                            return
                        result = await asyncio.to_thread(gen_mgr.generate_image, prompt)
                    _debug(f"[DEBUG-APPROVE] Result: {result[:100]}", flush=True)
                    if result.startswith("Error:"):
                        # Keep pending_media for retry, send error card
                        error_msg = result.replace("Error: ", "").strip()
                        await messenger.reply_image_approval(
                            prompt, approval_id, pending.get("agent_name", ""),
                            media_type=media_type, duration=duration,
                            model=pending.get("model", ""),
                            approval_status="error",
                            image_error=error_msg,
                        )
                    else:
                        print(f"[APPROVE] Image generated successfully: {result[:80]}", flush=True)
                        await messenger.reply_image_result(result, prompt, approval_id, task_id=task_id, media_type=media_type, agent_name=pending.get('agent_name', ''))
                        print(f"[APPROVE] reply_image_result sent", flush=True)
                        if task_id:
                            await messenger.update_task_image(task_id, result, prompt, media_type=media_type)
                        # Keep pending_media for regenerate after success
                except Exception as e:
                    _debug(f"[DEBUG-APPROVE] Error: {_sanitize_error(e)}", flush=True)
                    # Keep pending_media for retry
                    await messenger.reply(f"⚠️ เกิดข้อผิดพลาดในการสร้างสื่อ: {_sanitize_error(e)}")
            elif messenger:
                _debug(f"[DEBUG-APPROVE] No pending media found for {approval_id}", flush=True)
                await messenger.reply(f"⚠️ ไม่พบคำขอสร้างสื่อ (ID: {approval_id}) อาจหมดอายุแล้ว กรุณาลองใหม่")
        elif action_name == "retry_image":
            approval_id = payload.get("approval_id", "")
            _debug(f"[DEBUG-RETRY] approval_id={approval_id}", flush=True)
            pending = cl.user_session.get(f"pending_media_{approval_id}")
            if pending and messenger:
                prompt = pending["prompt"]
                task_id = pending.get("task_id")
                media_type = pending.get("media_type", "image")
                duration = pending.get("duration", 5)
                _debug(f"[DEBUG-RETRY] Retrying {media_type} for prompt: {prompt[:80]}...", flush=True)
                try:
                    llm_mgr = LLMManager()
                    gen_mgr = MediaGenerationManager(llm_mgr)
                    retry_image_model = cl.user_session.get("ai_image_model") or ""
                    retry_video_model = cl.user_session.get("ai_video_model") or ""
                    gen_mgr.set_models(
                        image_model=retry_image_model,
                        video_model=retry_video_model,
                    )
                    if media_type == "video":
                        if not retry_video_model:
                            await messenger.reply("⚠️ ยังไม่ได้เลือก Video model — กรุณาเลือก model สำหรับสร้างวิดีโอก่อน")
                            return
                        result = await asyncio.to_thread(gen_mgr.generate_video, prompt, duration=duration)
                    else:
                        if not retry_image_model:
                            await messenger.reply("⚠️ ยังไม่ได้เลือก Image model — กรุณาเลือก model สำหรับสร้างรูปภาพก่อน")
                            return
                        result = await asyncio.to_thread(gen_mgr.generate_image, prompt)
                    _debug(f"[DEBUG-RETRY] Result: {result[:100]}", flush=True)
                    if result.startswith("Error:"):
                        await messenger.reply(f"⚠️ {result}")
                    else:
                        await messenger.reply_image_result(result, prompt, approval_id, task_id=task_id, media_type=media_type, agent_name=pending.get('agent_name', ''))
                        if task_id:
                            await messenger.update_task_image(task_id, result, prompt, media_type=media_type)
                        # Keep pending_media for regenerate after success
                except Exception as e:
                    _debug(f"[DEBUG-RETRY] Error: {_sanitize_error(e)}", flush=True)
                    await messenger.reply(f"⚠️ เกิดข้อผิดพลาดในการสร้างสื่อ: {_sanitize_error(e)}")
            elif messenger:
                await messenger.reply(f"⚠️ ไม่พบคำขอสร้างสื่อ (ID: {approval_id}) อาจหมดอายุแล้ว")
        elif action_name == "edit_image_prompt":
            approval_id = payload.get("approval_id", "")
            new_prompt = payload.get("new_prompt", "").strip()
            if new_prompt and messenger:
                pending = cl.user_session.get(f"pending_media_{approval_id}") or {}
                pending["prompt"] = new_prompt
                cl.user_session.set(f"pending_media_{approval_id}", pending)
                media_type = pending.get("media_type", "image")
                duration = pending.get("duration", 0)
                await messenger.reply_image_approval(
                    new_prompt, approval_id, pending.get("agent_name", ""),
                    media_type=media_type, duration=duration
                )
            elif messenger:
                await messenger.reply(f"⚠️ prompt ว่าง กรุณาใส่ prompt แล้วลองใหม่")
        elif action_name == "reject_image":
            approval_id = payload.get("approval_id", "")
            if messenger:
                messenger.update_approval_status(approval_id, "rejected")
                await messenger.reply(f"❌ ยกเลิกการสร้างสื่อ (ID: {approval_id})")
                cl.user_session.set(f"pending_media_{approval_id}", None)
                await messenger.reply_notifications(team_id=cl.user_session.get("current_team_id"))
        elif action_name == "approve_agent_result":
            review_id = payload.get("review_id", "")
            print(f"[DEBUG-AGENT-REVIEW] approve: review_id={review_id}", flush=True)
            review_control = cl.user_session.get("agent_review_control") or {}
            review_events = review_control.get("review_events", {})
            review_results = review_control.get("review_results", {})
            # Find the agent idx from review_id format "review_{task_id}_{idx}"
            try:
                idx = int(review_id.rsplit("_", 1)[-1])
            except (ValueError, IndexError):
                idx = -1
            if idx >= 0 and idx in review_events:
                review_results[idx] = {"approved": True, "feedback": ""}
                review_events[idx].set()
                if messenger:
                    await messenger.update_agent_review_status(review_id, "approved")
                    await messenger.notify(f"✅ อนุมัติผลงานของ agent แล้ว — ส่งต่อให้ agent ตัวถัดไปได้")
                    await messenger.reply_notifications(team_id=cl.user_session.get("current_team_id"))
            else:
                if messenger:
                    await messenger.reply(f"⚠️ ไม่พบ review request (ID: {review_id}) อาจหมดอายุแล้ว")
        elif action_name == "reject_agent_result":
            review_id = payload.get("review_id", "")
            feedback = payload.get("feedback", "")
            print(f"[DEBUG-AGENT-REVIEW] reject: review_id={review_id}, feedback={feedback[:100]}", flush=True)
            review_control = cl.user_session.get("agent_review_control") or {}
            review_events = review_control.get("review_events", {})
            review_results = review_control.get("review_results", {})
            try:
                idx = int(review_id.rsplit("_", 1)[-1])
            except (ValueError, IndexError):
                idx = -1
            if idx >= 0 and idx in review_events:
                review_results[idx] = {"approved": False, "feedback": feedback}
                review_events[idx].set()
                if messenger:
                    await messenger.notify(f"🔄 ส่งกลับให้ agent ทำงานใหม่พร้อม feedback ของ user")
                    await messenger.reply_notifications(team_id=cl.user_session.get("current_team_id"))
            else:
                if messenger:
                    await messenger.reply(f"⚠️ ไม่พบ review request (ID: {review_id}) อาจหมดอายุแล้ว")
        elif action_name == "retry_task":
            failed = cl.user_session.get("last_failed_task")
            if not failed:
                if messenger:
                    await messenger.reply("⚠️ ไม่มีงานที่ล้มเหลวให้ลองใหม่")
                return
            if messenger:
                await messenger.notify("🔄 กำลังลองทำงานใหม่...")
            cl.user_session.set("last_failed_task", None)
            # Re-execute the failed task
            failed_input = failed.get("user_input", "")
            failed_specs = failed.get("agent_specs", [])
            failed_models = failed.get("pre_assigned_models")
            if failed_specs and len(failed_specs) > 1:
                await execute_multi_agent_task(failed_input, failed_specs, pre_assigned=failed_models)
            elif failed_specs and len(failed_specs) == 1:
                await execute_task_with_agent(failed_input, failed_specs[0])
            else:
                if messenger:
                    await messenger.reply("⚠️ ไม่สามารถลองใหม่ได้ — ข้อมูลงานไม่ครบ")
        elif action_name == "new_chat":
            current_team_id = cl.user_session.get("current_team_id")
            session = messenger.chat_store.create_session("New Chat", team_id=current_team_id)
            messenger.current_session_id = session["id"]
            cl.user_session.set("conversation_history", [])
            await messenger.reply_chat_sessions(team_id=current_team_id)
            await messenger.reply_chat_history(session["id"])
            await messenger.reply_notifications(team_id=current_team_id)
        elif action_name == "switch_chat":
            session_id = payload.get("session_id", "")
            session = messenger.chat_store.get_session(session_id)
            if session:
                messenger.current_session_id = session_id
                # Restore conversation history for this session
                cl.user_session.set("conversation_history", _restore_conversation_history(session_id, messenger.chat_store))
                # Restore settings for this session
                settings = messenger.chat_store.get_settings(session_id)
                cl.user_session.set("selected_model", settings.get("selected_model", ""))
                for key in ("ai_image_model", "ai_video_model", "ai_search_model", "ai_tts_model", "ai_stt_model", "ai_vision_model"):
                    cl.user_session.set(key, settings.get(key, ""))
                current_team_id = cl.user_session.get("current_team_id")
                await messenger.reply_chat_sessions(team_id=current_team_id)
                await messenger.reply_chat_history(session_id)
                await messenger.reply_notifications(team_id=current_team_id)
                # Restore plan approval state if last message is a pending plan
                msgs = session.get("messages", [])
                if msgs and msgs[-1].get("messageType") == "plan" and msgs[-1].get("planStatus") == "pending":
                    cl.user_session.set("state", STATE_AWAITING_APPROVAL)
                    cl.user_session.set("current_agent_specs", msgs[-1].get("agentSpecs", []))
                    cl.user_session.set("current_input", msgs[-1].get("currentInput", ""))
                    pre_assigned = msgs[-1].get("modelAssignment", {})
                    if pre_assigned:
                        cl.user_session.set("pre_assigned_models", pre_assigned)
                    print(f"[DEBUG-RESTORE] Restored STATE_AWAITING_APPROVAL for session {session_id}", flush=True)
                else:
                    cl.user_session.set("state", STATE_IDLE)
                    cl.user_session.set("current_agent_specs", None)
                    cl.user_session.set("current_input", None)
        elif action_name == "rename_chat":
            session_id = payload.get("session_id", "")
            title = payload.get("title", "Untitled")
            messenger.chat_store.rename_session(session_id, title)
            current_team_id = cl.user_session.get("current_team_id")
            await messenger.reply_chat_sessions(team_id=current_team_id)
        elif action_name == "delete_chat":
            session_id = payload.get("session_id", "")
            messenger.chat_store.delete_session(session_id)
            # Switch to another session or create new
            current_team_id = cl.user_session.get("current_team_id")
            remaining = messenger.chat_store.list_sessions(team_id=current_team_id, include_unassigned=True)
            if remaining:
                messenger.current_session_id = remaining[0]["id"]
            else:
                new_s = messenger.chat_store.create_session("New Chat", team_id=current_team_id)
                messenger.current_session_id = new_s["id"]
            await messenger.reply_chat_sessions(team_id=current_team_id)
            await messenger.reply_chat_history(messenger.current_session_id)
        elif action_name == "save_canvas":
            session_id = payload.get("session_id", "")
            canvas_state = payload.get("canvas_state", {})
            if session_id and canvas_state:
                messenger.chat_store.save_canvas_state(session_id, canvas_state)
        elif action_name == "list_task_templates":
            user_id = cl.user_session.get("user_id", "default")
            tpl_store = TaskTemplateStore(user_id=user_id)
            templates = tpl_store.list_templates()
            if messenger:
                payload_resp = chat_reply(ChatReplyText(
                    message=json.dumps({"type": "task_templates", "templates": templates}, ensure_ascii=False),
                ))
                await cl.Message(content=json.dumps(payload_resp, ensure_ascii=False)).send()
        elif action_name == "save_task_template":
            user_id = cl.user_session.get("user_id", "default")
            tpl_store = TaskTemplateStore(user_id=user_id)
            name = payload.get("name", "Untitled")
            prompt = payload.get("prompt", "")
            mode = payload.get("mode", "plan")
            if prompt:
                tpl = tpl_store.add_template(name, prompt, mode)
                if messenger:
                    await messenger.notify(f"✅ บันทึก template '{name}' แล้ว")
        elif action_name == "delete_task_template":
            user_id = cl.user_session.get("user_id", "default")
            tpl_store = TaskTemplateStore(user_id=user_id)
            tpl_id = payload.get("template_id", "")
            if tpl_id and tpl_store.delete_template(tpl_id):
                if messenger:
                    await messenger.notify("🗑️ ลบ template แล้ว")
        elif action_name == "list_scheduled_tasks":
            user_id = cl.user_session.get("user_id", "default")
            sched_store = ScheduledTaskStore(user_id=user_id)
            tasks = sched_store.list_scheduled()
            if messenger:
                payload_resp = chat_reply(ChatReplyText(
                    message=json.dumps({"type": "scheduled_tasks", "tasks": tasks}, ensure_ascii=False),
                ))
                await cl.Message(content=json.dumps(payload_resp, ensure_ascii=False)).send()
        elif action_name == "add_scheduled_task":
            user_id = cl.user_session.get("user_id", "default")
            sched_store = ScheduledTaskStore(user_id=user_id)
            name = payload.get("name", "Scheduled Task")
            prompt = payload.get("prompt", "")
            interval = float(payload.get("interval_hours", 24))
            mode = payload.get("mode", "plan")
            if prompt:
                current_team_id = cl.user_session.get("current_team_id", "")
                sched = sched_store.add_scheduled(name, prompt, interval, mode, team_id=current_team_id)
                if messenger:
                    await messenger.notify(f"⏰ ตั้งเวลา '{name}' ทุก {interval} ชม. แล้ว")
        elif action_name == "delete_scheduled_task":
            user_id = cl.user_session.get("user_id", "default")
            sched_store = ScheduledTaskStore(user_id=user_id)
            task_id = payload.get("task_id", "")
            if task_id and sched_store.delete_scheduled(task_id):
                if messenger:
                    await messenger.notify("🗑️ ลบงานตั้งเวลาแล้ว")
        elif action_name == "toggle_scheduled_task":
            user_id = cl.user_session.get("user_id", "default")
            sched_store = ScheduledTaskStore(user_id=user_id)
            task_id = payload.get("task_id", "")
            if task_id:
                active = sched_store.toggle_active(task_id)
                if messenger:
                    await messenger.notify(f"{'▶️ เปิด' if active else '⏸️ ปิด'}งานตั้งเวลาแล้ว")
        elif action_name == "rate_task":
            rating = int(payload.get("rating", 0))
            if 1 <= rating <= 5:
                last_input = cl.user_session.get("last_user_input", "")
                last_result = cl.user_session.get("last_task_result", "")
                user_id = cl.user_session.get("user_id", "default")
                ratings_file = Path(f"data/task_ratings_{user_id}.json")
                ratings_file.parent.mkdir(parents=True, exist_ok=True)
                ratings = []
                if ratings_file.exists():
                    try:
                        ratings = json.loads(ratings_file.read_text(encoding="utf-8"))
                    except (json.JSONDecodeError, OSError):
                        pass
                ratings.append({
                    "rating": rating,
                    "task": last_input[:200],
                    "result_preview": last_result[:200],
                    "timestamp": datetime.now().isoformat(),
                })
                ratings_file.write_text(json.dumps(ratings, ensure_ascii=False, indent=2), encoding="utf-8")
                if messenger:
                    await messenger.notify(f"⭐ ขอบคุณสำหรับการให้คะแนน ({rating}/5)")
        elif action_name == "fetch_model_catalog":
            llm_mgr = LLMManager()
            if llm_mgr._is_openrouter():
                catalog = ModelCatalog(llm_mgr.api_key, llm_mgr.base_url)
                loop = asyncio.get_event_loop()
                recommended = await loop.run_in_executor(None, catalog.get_recommended)
                selected = cl.user_session.get("selected_model") or ""
                if messenger:
                    await messenger.reply_model_catalog(recommended, [], selected)
            else:
                if messenger:
                    await messenger.reply("⚠️ Model catalog ใช้ได้เฉพาะ OpenRouter tier (paid/free)")
        elif action_name == "fetch_media_catalog":
            media_type = payload.get("media_type", "image")
            llm_mgr = LLMManager()
            if llm_mgr._is_openrouter():
                discovery = ModelDiscoveryService(base_url=llm_mgr.base_url, api_key=llm_mgr.api_key)
                loop = asyncio.get_event_loop()
                # Map media_type to discovery category
                discovery_map = {
                    "image": "output:image",
                    "video": "output:video",
                    "search": "output:search",
                    "tts": "output:audio",
                    "stt": "input:audio_input",
                    "vision": "input:vision",
                }
                target = discovery_map.get(media_type, f"output:{media_type}")
                filtered = []
                if target.startswith("output:"):
                    cat = target.split(":")[1]
                    all_groups = await loop.run_in_executor(None, discovery.discover_all)
                    filtered = all_groups.get(cat, [])
                elif target.startswith("input:"):
                    cat = target.split(":")[1]
                    all_groups = await loop.run_in_executor(None, discovery.discover_input_capabilities)
                    filtered = all_groups.get(cat, [])
                # Fallback for search: if no models found by category, filter by web_search pricing
                if media_type == "search" and not filtered:
                    all_groups = all_groups if 'all_groups' in dir() else await loop.run_in_executor(None, discovery.discover_all)
                    all_flat = []
                    for group_models in all_groups.values():
                        all_flat.extend(group_models)
                    filtered = [m for m in all_flat if m.get("pricing", {}).get("web_search") and m["pricing"]["web_search"] not in ("0", 0, None, "")]
                # Build catalog entries in the same format as ModelCatalog
                entries = []
                for m in filtered:
                    mid = m["id"]
                    pricing = m.get("pricing", {})
                    def _convert_media(price):
                        try:
                            return round(float(price) * 1_000_000, 6)
                        except (ValueError, TypeError):
                            return price if price else "?"
                    prompt_price = _convert_media(pricing.get("prompt", "?"))
                    comp_price = _convert_media(pricing.get("completion", "?"))
                    image_price = _convert_media(pricing.get("image", "?"))
                    video_price = _convert_media(pricing.get("video", "?"))
                    audio_price = _convert_media(pricing.get("audio", "?"))
                    web_search_price = _convert_media(pricing.get("web_search", "?"))
                    all_prices = [prompt_price, comp_price, image_price, video_price, audio_price, web_search_price]
                    known_prices = [p for p in all_prices if isinstance(p, (int, float))]
                    is_free = len(known_prices) > 0 and all(p == 0 for p in known_prices)
                    entries.append({
                        "id": mid,
                        "name": m.get("name", mid),
                        "context_length": m.get("context_length", "?"),
                        "prompt_price": prompt_price,
                        "completion_price": comp_price,
                        "image_price": image_price,
                        "video_price": video_price,
                        "audio_price": audio_price,
                        "web_search_price": web_search_price,
                        "categories": [media_type],
                        "is_free": is_free,
                        "input_modalities": m.get("input_modalities", []),
                        "output_modalities": m.get("output_modalities", []),
                    })
                # Group by category (media_type) so ModelPicker can render correctly
                grouped = {media_type: entries}
                if messenger:
                    await messenger.reply_model_catalog(grouped, [], "", catalog_type="media")
            else:
                if messenger:
                    await messenger.reply("⚠️ Media catalog ใช้ได้เฉพาะ OpenRouter tier (paid/free)")
        elif action_name == "search_models":
            query = payload.get("query", "")
            llm_mgr = LLMManager()
            if llm_mgr._is_openrouter() and query:
                catalog = ModelCatalog(llm_mgr.api_key, llm_mgr.base_url)
                loop = asyncio.get_event_loop()
                results = await loop.run_in_executor(None, catalog.search, query)
                recommended = await loop.run_in_executor(None, catalog.get_recommended)
                selected = cl.user_session.get("selected_model") or ""
                if messenger:
                    await messenger.reply_model_catalog(recommended, results, selected)
        elif action_name == "set_selected_model":
            model_id = payload.get("model_id", "")
            cl.user_session.set("selected_model", model_id)
            # Update LLMManager immediately so assess_and_plan uses the correct model
            llm_manager = LLMManager()
            llm_manager.set_selected_model(model_id)
            # Also update pre_assigned_models manager so plan uses the same model
            pre_assigned = cl.user_session.get("pre_assigned_models") or {"manager": "", "workers": {}}
            pre_assigned["manager"] = model_id
            cl.user_session.set("pre_assigned_models", pre_assigned)
            # Sync: update manager agent's model in registry
            registry = cl.user_session.get("registry")
            if registry:
                for a in registry.list_agents():
                    if a.get("is_manager") or a.get("role", "").lower() == "manager":
                        registry.update_agent(a["id"], {"model": model_id})
                        print(f"[DEBUG-MODEL-SYNC] Updated manager agent '{a.get('name')}' model → {model_id}", flush=True)
                        break
                # Push updated agent list to frontend
                messenger = cl.user_session.get("messenger")
                if messenger:
                    await messenger.update_agents(registry)
            # Persist settings to chat store so they survive refresh
            messenger = cl.user_session.get("messenger")
            if messenger and messenger.current_session_id:
                messenger.chat_store.save_settings(messenger.current_session_id, {
                    "selected_model": model_id,
                })
            # No chat reply — UI shows selection in the model button
        elif action_name == "change_agent_model":
            agent_name = payload.get("agent_name", "")
            model_id = payload.get("model_id", "")
            # Update pre_assigned_models in session
            pre_assigned = cl.user_session.get("pre_assigned_models") or {"manager": "", "workers": {}}
            if agent_name and model_id:
                if agent_name in pre_assigned.get("workers", {}):
                    pre_assigned["workers"][agent_name] = model_id
                elif pre_assigned.get("manager") == agent_name or agent_name.lower() == "manager":
                    pre_assigned["manager"] = model_id
                else:
                    pre_assigned.setdefault("workers", {})[agent_name] = model_id
                cl.user_session.set("pre_assigned_models", pre_assigned)
                print(f"[DEBUG-MODEL-CHANGE] {agent_name} → {model_id}, pre_assigned={pre_assigned}", flush=True)
        elif action_name == "change_manager_model":
            model_id = payload.get("model_id", "")
            if model_id:
                pre_assigned = cl.user_session.get("pre_assigned_models") or {"manager": "", "workers": {}}
                pre_assigned["manager"] = model_id
                cl.user_session.set("pre_assigned_models", pre_assigned)
                print(f"[DEBUG-MODEL-CHANGE] manager → {model_id}", flush=True)
        elif action_name == "change_media_model":
            media_type = payload.get("media_type", "")
            model_id = payload.get("model_id", "")
            if media_type and model_id is not None:
                session_key = f"ai_{media_type.replace('Model', '_model')}"
                cl.user_session.set(session_key, model_id)
                print(f"[DEBUG-MEDIA-CHANGE] {media_type} → {model_id}", flush=True)
                # Persist to chat_store so it survives refresh
                messenger = cl.user_session.get("messenger")
                if messenger and messenger.current_session_id:
                    settings = messenger.chat_store.get_settings(messenger.current_session_id)
                    settings[f"ai_{media_type.replace('Model', '_model')}"] = model_id
                    messenger.chat_store.save_settings(messenger.current_session_id, settings)
        elif action_name == "stop_generation":
            cl.user_session.set("cancel_generation", True)
            print(f"[STOP] User requested to stop generation", flush=True)
            if messenger:
                await messenger.reply("⏹️ หยุดการทำงานแล้ว")
        elif action_name == "fetch_notifications":
            current_team_id = cl.user_session.get("current_team_id")
            if messenger:
                await messenger.reply_notifications(team_id=current_team_id)
        elif action_name == "skip_review":
            agent_name = payload.get("agent_name", "")
            if agent_name:
                orchestrator = cl.user_session.get("orchestrator")
                if orchestrator:
                    orchestrator.skip_review_agents.add(agent_name)
                    print(f"[SKIP-REVIEW] User requested to skip review for agent '{agent_name}'", flush=True)
        elif action_name == "upload_file":
            file_data = payload.get("file_data", "")
            file_name = payload.get("file_name", "upload")
            file_mime = payload.get("file_mime", "application/octet-stream")
            if file_data and file_name:
                import base64
                attach_dir = os.path.join(os.path.dirname(__file__), "public", "attachments")
                os.makedirs(attach_dir, exist_ok=True)
                # Sanitize filename
                safe_name = re.sub(r'[^a-zA-Z0-9._-]', '_', file_name)
                unique_name = f"{uuid.uuid4().hex[:8]}_{safe_name}"
                filepath = os.path.join(attach_dir, unique_name)
                try:
                    file_bytes = base64.b64decode(file_data.split(",")[-1] if "," in file_data else file_data)
                    with open(filepath, "wb") as f:
                        f.write(file_bytes)
                    file_url = f"/public/attachments/{unique_name}"
                    if messenger:
                        payload_resp = chat_reply(ChatReplyFileResult(
                            fileUrl=file_url,
                            fileName=file_name,
                            fileMime=file_mime,
                        ))
                        await cl.Message(content=json.dumps(payload_resp, ensure_ascii=False)).send()
                    print(f"[UPLOAD] Saved {file_name} → {file_url}", flush=True)
                except Exception as e:
                    if messenger:
                        await messenger.reply(f"❌ Upload failed: {_sanitize_error(e)}")
        elif action_name == "create_team":
            await on_action_create_team(cl.Action(name="create_team", payload=payload))
        elif action_name == "update_team":
            await on_action_update_team(cl.Action(name="update_team", payload=payload))
        elif action_name == "delete_team":
            await on_action_delete_team(cl.Action(name="delete_team", payload=payload))
        elif action_name == "delete_chat_session":
            await on_action_delete_chat_session(cl.Action(name="delete_chat_session", payload=payload))
        elif action_name == "config_agent":
            await on_action_config_agent(cl.Action(name="config_agent", payload=payload))
        elif action_name == "select_team":
            team_id = payload.get("team_id", "")
            cl.user_session.set("current_team_id", team_id if team_id else None)
            # Persist team_id to chat settings so it survives refresh
            if messenger and messenger.current_session_id:
                team_settings = messenger.chat_store.get_settings(messenger.current_session_id)
                team_settings["current_team_id"] = team_id if team_id else None
                messenger.chat_store.save_settings(messenger.current_session_id, team_settings)
            team_registry = cl.user_session.get("team_registry") or TeamRegistry()
            if team_id:
                team = team_registry.get_team(team_id)
                if team and messenger:
                    # List sessions for this team (include legacy unassigned sessions)
                    sessions = messenger.chat_store.list_sessions(team_id=team_id, include_unassigned=True)
                    # If no sessions exist for this team, create a fresh one
                    if not sessions:
                        new_s = messenger.chat_store.create_session("New Chat", team_id=team_id)
                        sessions = [new_s]
                        messenger.current_session_id = new_s["id"]
                    else:
                        # Switch to the first session belonging to this team
                        messenger.current_session_id = sessions[0]["id"]
                    session_list = [
                        {"id": s["id"], "title": s["title"], "updated_at": s.get("updated_at", "")}
                        for s in sessions
                    ]
                    payload_sessions = {
                        "type": "chat_reply",
                        "payload": {
                            "messageType": "chat_sessions",
                            "sessions": session_list,
                            "currentSessionId": messenger.current_session_id,
                        },
                    }
                    await cl.Message(content=json.dumps(payload_sessions, ensure_ascii=False)).send()
                    # Load chat history for the team's session (fresh if new)
                    await messenger.reply_chat_history(messenger.current_session_id)
                    # List agents for this team
                    registry = cl.user_session.get("registry")
                    if not registry:
                        registry = AgentRegistry(user_id=cl.user_session.get("user_id"))
                        cl.user_session.set("registry", registry)
                    team_agents = registry.list_agents(team_id=team_id)
                    if messenger:
                        await messenger.update_agents(registry)
            else:
                # Going back to team list — show all sessions
                if messenger:
                    await messenger.reply_chat_sessions()
        elif action_name == "list_teams":
            team_registry = cl.user_session.get("team_registry") or TeamRegistry()
            if messenger:
                await messenger.reply_team_list(team_registry)
        return

    # Reset cancel flag for new real user message (not action commands)
    cl.user_session.set("cancel_generation", False)

    # Persist user message to chat session
    if messenger:
        msg_data = {"role": "user", "content": user_input, "messageType": "text"}
        last_attachments = cl.user_session.get("last_attachments") or []
        if last_attachments:
            # Store full array for multi-attachment display
            msg_data["attachments"] = [{"url": a["file_url"], "name": a["file_name"], "mime": a["file_mime"]} for a in last_attachments]
            # Also store single-attachment fields for backward compat (first file)
            msg_data["attachmentUrl"] = last_attachments[0]["file_url"]
            msg_data["attachmentName"] = last_attachments[0]["file_name"]
            msg_data["attachmentMime"] = last_attachments[0]["file_mime"]
        messenger.persist_message(msg_data)

    # Process all attachments via unified pipeline
    all_contexts = []
    last_attachments = cl.user_session.get("last_attachments") or []
    attachment_urls = set(a["file_url"] for a in last_attachments)
    for att in last_attachments:
        att_ctx = await process_attachment(att["file_url"], att["file_name"], att["file_mime"])
        print(f"[ATTACHMENT] Processed {att['file_name']} → type={att_ctx['type']}", flush=True)
        all_contexts.append(att_ctx)

    # Detect and process URLs in user message
    urls_in_message = find_urls_in_text(user_input)
    print(f"[DEBUG-URL] Found {len(urls_in_message)} URLs in message: {urls_in_message}", flush=True)
    url_contexts = []
    extracted_urls = set()
    for found_url in urls_in_message:
        if found_url in attachment_urls:
            continue
        print(f"[DEBUG-URL] Processing URL: {found_url[:80]}...", flush=True)
        url_ctx = await process_url(found_url)
        url_contexts.append(url_ctx)
        print(f"[URL] Processed {found_url} → type={url_ctx['type']}", flush=True)
        if url_ctx["type"] in ("text", "multimodal") and (url_ctx.get("text_content") or url_ctx.get("content_blocks")):
            extracted_urls.add(found_url)

    # Merge attachment + URL contexts
    all_contexts.extend(url_contexts)

    # Build unified context for AI
    multimodal_blocks = []
    multimodal_plugins = None
    text_context_parts = []
    crewai_files = {}
    context_texts = []
    required_modalities = []

    for ctx in all_contexts:
        if ctx["type"] == "multimodal":
            multimodal_blocks.extend(ctx["content_blocks"])
            if ctx.get("plugins"):
                multimodal_plugins = ctx["plugins"]
            if ctx.get("text_content"):
                text_context_parts.append(ctx["text_content"])
        elif ctx["type"] == "text":
            text_context_parts.append(ctx["text_content"])
        if ctx.get("crewai_files"):
            crewai_files.update(ctx["crewai_files"])
        context_texts.append(ctx["context_text"])
        if ctx.get("required_modality"):
            required_modalities.append(ctx["required_modality"])

    # Store vision input flag for plan card model filtering
    has_vision_input = "image" in required_modalities
    cl.user_session.set("has_vision_input", has_vision_input)

    # Model compatibility check
    selected_model = cl.user_session.get("selected_model") or ""
    if selected_model and required_modalities and llm_manager_tier_check():
        for modality in required_modalities:
            if not check_model_modality_support(selected_model, modality):
                if messenger:
                    await messenger.reply(
                        f"⚠️ Model '{selected_model}' อาจไม่รองรับ {modality} input. "
                        f"แนะนำให้เปลี่ยน model เป็นที่รองรับ multimodal (เช่น Google Gemini)"
                    )
                break

    # Build user_input_for_ai
    context_summary = " ".join(context_texts)
    # Remove URLs that were successfully extracted from the user-facing text
    user_input_clean = user_input
    for extracted_url in extracted_urls:
        user_input_clean = user_input_clean.replace(extracted_url, "[content extracted below]")
    if text_context_parts:
        user_input_for_ai = f"{user_input_clean}\n\n[Attached content:\n" + "\n---\n".join(text_context_parts) + "\n]"
    elif context_summary:
        user_input_for_ai = f"{user_input_clean}\n\n{context_summary}"
    else:
        user_input_for_ai = user_input_clean

    # Store for CrewAI worker agents
    cl.user_session.set("attachment_context", {
        "type": "multimodal" if multimodal_blocks else "text" if text_context_parts else "metadata",
        "content_blocks": multimodal_blocks,
        "plugins": multimodal_plugins,
        "text_content": "\n---\n".join(text_context_parts),
        "context_text": context_summary,
        "crewai_files": crewai_files or None,
    } if all_contexts else None)
    cl.user_session.set("attachment_crewai_files", crewai_files or None)
    cl.user_session.set("attachment_plugins", multimodal_plugins)

    # Gather conversation history for context
    conversation_history = cl.user_session.get("conversation_history") or []

    # If user sends a new message while a plan is pending, discard old plan and reprocess
    if state == STATE_AWAITING_APPROVAL:
        cl.user_session.set("state", STATE_IDLE)
        cl.user_session.set("current_agent_specs", None)
        cl.user_session.set("current_input", None)
        state = STATE_IDLE

    # Chat mode: still assess intent first, but allow direct chat response
    if input_mode == "chat" and state == STATE_IDLE:
        try:
            llm_manager = LLMManager()
            selected_model = cl.user_session.get("selected_model") or ""
            if selected_model and llm_manager._is_openrouter():
                llm_manager.set_selected_model(selected_model)
            manager = CentralManager(llm_manager)

            # Quick assess: check if user wants to create agents or plan work
            model_table = "none"
            valid_model_ids = set()
            media_catalog = "none"
            registry_agents = registry.list_agents()
            current_team_id = cl.user_session.get("current_team_id")
            team_agents = None
            team_name = None
            if current_team_id:
                team_registry = cl.user_session.get("team_registry") or TeamRegistry()
                team = team_registry.get_team(current_team_id)
                if team:
                    team_name = team.get("name", "")
                    team_agents = registry.list_agents(team_id=current_team_id)

            last_task_context = None
            last_result = cl.user_session.get("last_task_result")
            last_specs = cl.user_session.get("last_agent_specs")
            last_input = cl.user_session.get("last_user_input")
            if last_result and last_specs:
                last_task_context = {
                    "user_input": last_input or "",
                    "result": last_result,
                    "agents": last_specs,
                }

            result = await manager.assess_and_plan(
                user_input_for_ai, conversation_history,
                model_table=model_table,
                valid_model_ids=valid_model_ids,
                media_catalog=media_catalog,
                last_task_context=last_task_context,
                registry_agents=registry_agents,
                team_agents=team_agents,
                team_name=team_name,
                has_attachment=bool(multimodal_blocks or text_context_parts),
                chat_only=True,
            ) if not multimodal_blocks else await manager.assess_and_plan_multimodal(
                user_input, multimodal_blocks, multimodal_plugins,
                conversation_history=conversation_history,
                model_table=model_table,
                valid_model_ids=valid_model_ids,
                media_catalog=media_catalog,
                chat_only=True,
                registry_agents=registry_agents,
                team_agents=team_agents,
                team_name=team_name,
                last_task_context=last_task_context,
            )

            # Chat mode: only handle chat responses
            response = result.get("message") or "ขออภัย ไม่เข้าใจ ลองใหม่อีกครั้ง"
            if messenger:
                await messenger.reply(response)
            conversation_history.append({"role": "user", "content": user_input, "attachment_context_text": context_summary})
            conversation_history.append({"role": "assistant", "content": response})
            cl.user_session.set("conversation_history", conversation_history)
            return
        except Exception as e:
            if messenger:
                await messenger.reply(f"⚠️ เกิดข้อผิดพลาด: {_sanitize_error(e)}")
        finally:
            cl.user_session.set("last_attachments", [])
            cl.user_session.set("last_attachment_url", None)
            cl.user_session.set("last_attachment_name", None)
            cl.user_session.set("last_attachment_mime", None)
            # Don't clear attachment_context/plugins here — agents need them during task execution
        return

    if state == STATE_IDLE:
        cl.user_session.set("state", STATE_ASSESSING)

        try:
            llm_manager = LLMManager()
            selected_model = cl.user_session.get("selected_model") or llm_manager.get_selected_model_name()
            if selected_model and llm_manager._is_openrouter():
                llm_manager.set_selected_model(selected_model)
            tool_registry = ToolRegistry()
            manager = CentralManager(llm_manager)

            # Build model table for unified call
            model_table = "none"
            valid_model_ids = set()
            media_catalog = "none"

            thinking_id = f"thinking-{int(time.time())}"
            if messenger:
                await messenger.reply_thinking("…", thinking_id)
            async def _stream_cb(chunk: str):
                if messenger:
                    await messenger.reply_thinking(chunk, thinking_id)

            # Build last task context (optional — tuning can happen without it)
            last_task_context = None
            last_result = cl.user_session.get("last_task_result")
            last_specs = cl.user_session.get("last_agent_specs")
            last_input = cl.user_session.get("last_user_input")
            if last_result and last_specs:
                last_task_context = {
                    "user_input": last_input or "",
                    "result": last_result,
                    "agents": last_specs,
                }

            # Only pass registry agents if user is in a team context (for tuning/reuse)
            # When creating a new team via AI modal, don't show existing agents
            current_team_id = cl.user_session.get("current_team_id")
            if current_team_id:
                registry_agents = registry.list_agents()
            else:
                registry_agents = []

            # Pass team agents if a team is selected
            team_agents = None
            team_name = None
            if current_team_id:
                team_registry = cl.user_session.get("team_registry") or TeamRegistry()
                team = team_registry.get_team(current_team_id)
                if team:
                    team_name = team.get("name", "")
                    team_agents = registry.list_agents(team_id=current_team_id)

            _has_att = bool(multimodal_blocks or text_context_parts)
            print(f"[DEBUG-ATTACH] multimodal_blocks={len(multimodal_blocks) if multimodal_blocks else 0}, text_context_parts={len(text_context_parts) if text_context_parts else 0}, has_attachment={_has_att}, input_mode={input_mode}", flush=True)
            result = await manager.assess_and_plan(
                user_input_for_ai, conversation_history,
                model_table=model_table,
                valid_model_ids=valid_model_ids,
                media_catalog=media_catalog,
                stream_callback=_stream_cb,
                last_task_context=last_task_context,
                registry_agents=registry_agents,
                team_agents=team_agents,
                team_name=team_name,
                force_plan=(input_mode == "plan"),
                has_attachment=_has_att,
            ) if not multimodal_blocks else await manager.assess_and_plan_multimodal(
                user_input, multimodal_blocks, multimodal_plugins,
                conversation_history=conversation_history,
                model_table=model_table,
                valid_model_ids=valid_model_ids,
                media_catalog=media_catalog,
                stream_callback=_stream_cb,
                registry_agents=registry_agents,
                team_agents=team_agents,
                team_name=team_name,
                last_task_context=last_task_context,
            )
            if messenger:
                await messenger.reply_thinking_done(thinking_id)
            if os.getenv("DEBUG_MODE", "false").lower() == "true":
                print(f"[DEBUG-UNIFIED] user_input='{user_input[:50]}' action={result.get('action')}", flush=True)
                if result.get("action") == "plan":
                    print(f"[DEBUG-PLAN] raw agents JSON: {json.dumps(result.get('agents', []), ensure_ascii=False)[:500]}", flush=True)

            action = result.get("action", "chat")

            if action == "chat":
                cl.user_session.set("state", STATE_IDLE)
                response = result.get("message") or "ขออภัย ไม่เข้าใจ ลองใหม่อีกครั้ง"
                if messenger:
                    await messenger.reply(response)
                conversation_history.append({"role": "user", "content": user_input})
                conversation_history.append({"role": "assistant", "content": response})
                cl.user_session.set("conversation_history", conversation_history)
                return

            if action == "tuning":
                cl.user_session.set("state", STATE_IDLE)
                tuning_text = result.get("tuning_text", user_input)
                target_agent = result.get("target_agent", "")
                if messenger:
                    await messenger.notify("📝 กำลังวิเคราะห์การปรับแต่ง agent...")

                # Use last task agents if available, otherwise use all registry agents
                last_specs = cl.user_session.get("last_agent_specs") or []
                last_result = cl.user_session.get("last_task_result") or ""
                all_agents = registry.list_agents()

                # Build agent list for analysis: prefer last task agents, fallback to registry
                if last_specs:
                    agent_specs_for_tuning = last_specs
                elif all_agents:
                    # Convert registry agents to spec format
                    agent_specs_for_tuning = []
                    for a in all_agents:
                        spec = registry.to_spec(a)
                        spec["registry_id"] = a.get("id", "")
                        agent_specs_for_tuning.append(spec)
                else:
                    if messenger:
                        await messenger.reply("ยังไม่มี agent ในระบบ กรุณาสร้าง agent ก่อน หรือสั่งงานใหม่")
                    return

                # If user specified a target agent, filter to that one
                if target_agent:
                    filtered = [s for s in agent_specs_for_tuning if target_agent.lower() in s.get("name", "").lower()]
                    if filtered:
                        agent_specs_for_tuning = filtered

                tuning = await manager.analyze_feedback(tuning_text, agent_specs_for_tuning, last_result, conversation_history=conversation_history)
                proposals = tuning.get("tuning_proposals", [])

                if not proposals:
                    if messenger:
                        await messenger.reply("วิเคราะห์แล้ว — ไม่พบสิ่งที่ต้องปรับแต่งในตอนนี้")
                    return

                # Store tuning proposal in session for confirm/reject actions
                cl.user_session.set("pending_tuning_proposal", proposals)

                # Store feedback as learning for each affected agent
                for proposal in proposals:
                    agent_id = proposal.get("agent_id", "")
                    if agent_id:
                        registry.add_learning(agent_id, {
                            "type": "user_feedback",
                            "lesson": tuning_text,
                            "timestamp": datetime.now().isoformat(),
                        })

                if messenger:
                    await messenger.reply_tuning_proposal(proposals)
                return

            if action == "info":
                cl.user_session.set("state", STATE_IDLE)
                response = result.get("message") or "ขออภัย ไม่สามารถดึงข้อมูลได้ในตอนนี้"
                if messenger:
                    await messenger.reply(response)
                conversation_history.append({"role": "user", "content": user_input})
                conversation_history.append({"role": "assistant", "content": response})
                cl.user_session.set("conversation_history", conversation_history)
                return

            if action == "ask":
                # In plan mode, allow ask for critical missing info (e.g. missing file)
                questions = result.get("questions", [])
                if questions:
                    cl.user_session.set("state", STATE_GATHERING_REQUIREMENTS)
                    cl.user_session.set("current_input", user_input)
                    asked_questions = cl.user_session.get("asked_questions") or []
                    asked_questions.extend(questions)
                    cl.user_session.set("asked_questions", asked_questions)
                    if messenger:
                        await messenger.reply_thinking_done(thinking_id)
                        combined_questions = "\n\n".join(f"❓ {q}" for q in questions)
                        await messenger.reply(combined_questions)
                    conversation_history.append({"role": "user", "content": user_input})
                    conversation_history.append({"role": "assistant", "content": json.dumps({"questions": questions}, ensure_ascii=False)})
                    cl.user_session.set("conversation_history", conversation_history)
                    return
                # No questions — force proceed with assumptions
                result = await manager.assess_and_plan(
                    user_input_for_ai, conversation_history,
                    model_table=model_table,
                    valid_model_ids=valid_model_ids,
                    media_catalog=media_catalog,
                    stream_callback=_stream_cb,
                    last_task_context=last_task_context,
                    registry_agents=registry_agents,
                    team_agents=team_agents,
                    team_name=team_name,
                    force_plan=True,
                    force_proceed=True,
                    has_attachment=bool(multimodal_blocks or text_context_parts),
                )
                if messenger:
                    await messenger.reply_thinking_done(thinking_id)
                action = result.get("action", "plan")
                # Fall through to plan/create_agents/tuning handling below

            if action == "create_agents":
                # Show approval card with plan_type=create_agents (both Chat and Plan mode)
                cl.user_session.set("state", STATE_AWAITING_APPROVAL)
                cl.user_session.set("current_input", user_input)
                conversation_history.append({"role": "user", "content": user_input})
                cl.user_session.set("conversation_history", conversation_history)

                agent_specs = result.get("agents", [])
                model_assignment = result.get("model_assignment", {"manager": "", "workers": {}})
                if not agent_specs:
                    if messenger:
                        await messenger.reply("⚠️ ไม่สามารถสร้าง agent ได้ — กรุณาลองใหม่อีกครั้ง")
                    cl.user_session.set("state", STATE_IDLE)
                    return

                # For create_agents: always create new agents (no existing matching)
                resolved_specs = []
                agents_for_plan = []
                for spec in agent_specs:
                    resolved_specs.append(spec)
                    agents_for_plan.append({
                        "id": None,
                        "name": spec.get("name", "Unnamed"),
                        "role": spec.get("role", ""),
                        "goal": spec.get("goal", ""),
                        "persona": spec.get("persona", spec.get("backstory", "")),
                        "personality": spec.get("personality", {}),
                        "expertise": spec.get("expertise", []),
                        "brand_context": spec.get("brand_context", {}),
                        "tools": spec.get("tools", []),
                        "depends_on": spec.get("depends_on", []),
                        "status": "Idle",
                        "is_existing": False,
                        "model": model_assignment.get("workers", {}).get(spec.get("name", ""), model_assignment.get("manager", "")),
                    })

                cl.user_session.set("current_agent_specs", resolved_specs)
                cl.user_session.set("pre_assigned_models", model_assignment)
                cl.user_session.set("current_plan_type", "create_agents")

                # Detect media tools from agent specs
                ca_all_tools = []
                for spec in agent_specs:
                    ca_all_tools.extend(spec.get("tools", []))
                ca_has_image = any("generate_image" in str(t) for t in ca_all_tools)
                ca_has_video = any("generate_video" in str(t) for t in ca_all_tools)
                ca_has_search = any("search" in str(t) for t in ca_all_tools)
                ca_has_tts = any("tts" in str(t).lower() for t in ca_all_tools)
                ca_has_stt = any("stt" in str(t).lower() or "transcri" in str(t).lower() for t in ca_all_tools)
                ca_has_vision = any("vision" in str(t).lower() for t in ca_all_tools)

                _plan_title = agent_specs[0].get("task_description", user_input) if agent_specs else user_input
                if messenger:
                    await messenger.reply_plan(agents_for_plan, _plan_title, plan_type="create_agents",
                        image_model=result.get('image_model', ''),
                        video_model=result.get('video_model', ''),
                        search_model=result.get('search_model', ''),
                        tts_model=result.get('tts_model', ''),
                        stt_model=result.get('stt_model', ''),
                        vision_model=result.get('vision_model', ''),
                        has_image_tool=ca_has_image,
                        has_video_tool=ca_has_video,
                        has_search_tool=ca_has_search,
                        has_tts_tool=ca_has_tts,
                        has_stt_tool=ca_has_stt,
                        has_vision_tool=ca_has_vision,
                        has_vision_input=cl.user_session.get("has_vision_input", False),
                        manager_model=model_assignment.get('manager', ''),
                        agent_specs=agent_specs,
                        model_assignment=model_assignment,
                        current_input=user_input,
                        team_name=result.get('team_name', ''),
                        team_description=result.get('team_description', ''),
                    )
                # Store proposed team in conversation history so AI can modify it later
                # Replace any previous "Proposed team" entry instead of appending
                team_summary = json.dumps({
                    "team_name": result.get('team_name', ''),
                    "team_description": result.get('team_description', ''),
                    "manager": {"persona": result.get('manager_persona', ''), "goal": result.get('manager_goal', 'ประสานงานทีมและกระจายงาน'), "model": model_assignment.get('manager', '')},
                    "agents": [{"name": a.get("name",""), "role": a.get("role",""), "goal": a.get("goal",""), "persona": a.get("persona", a.get("backstory","")), "tools": a.get("tools",[]), "model": a.get("model","")} for a in agent_specs],
                }, ensure_ascii=False)
                conversation_history = [msg for msg in conversation_history if 'Proposed team:' not in msg.get('content', '')]
                conversation_history.append({"role": "assistant", "content": f"Proposed team: {team_summary}"})
                cl.user_session.set("conversation_history", conversation_history)
                return

            if action == "plan":
                # Unified call already produced agent specs + model assignments
                cl.user_session.set("state", STATE_PLANNING)
                cl.user_session.set("current_input", user_input)
                conversation_history.append({"role": "user", "content": user_input})
                cl.user_session.set("conversation_history", conversation_history)

                agent_specs = result.get("agents", [])
                model_assignment = result.get("model_assignment", {"manager": "", "workers": {}})
                # Manager model = top bar selected_model (single manager)
                selected = cl.user_session.get("selected_model") or ""
                if selected:
                    model_assignment["manager"] = selected
                _debug(f"[DEBUG-PLAN] agent_specs count={len(agent_specs)}, models={model_assignment}", flush=True)
                if agent_specs:
                    for s in agent_specs:
                        _debug(f"[DEBUG-PLAN] agent: {s.get('name', '?')} role={s.get('role', '?')} tools={s.get('tools', [])} model={s.get('model', '?')} depends_on={s.get('depends_on', [])}", flush=True)
                if not agent_specs:
                    raise ValueError("AI ไม่สามารถวิเคราะห์แผนงานได้")

                # Store model_assignment for run_async to skip assign_models
                cl.user_session.set("pre_assigned_models", model_assignment)
                # Fallback: if manager didn't set media models, keep existing user selection
                existing_img = cl.user_session.get("ai_image_model") or ""
                existing_vid = cl.user_session.get("ai_video_model") or ""
                existing_search = cl.user_session.get("ai_search_model") or ""
                cl.user_session.set("ai_image_model", result.get("image_model", "") or existing_img)
                cl.user_session.set("ai_video_model", result.get("video_model", "") or existing_vid)
                cl.user_session.set("ai_search_model", result.get("search_model", "") or existing_search)
                cl.user_session.set("ai_tts_model", result.get("tts_model", ""))
                cl.user_session.set("ai_stt_model", result.get("stt_model", ""))
                cl.user_session.set("ai_vision_model", result.get("vision_model", ""))
                print(f"[DEBUG-MODELS] image_model={result.get('image_model', '')} video_model={result.get('video_model', '')} search_model={result.get('search_model', '')} tts_model={result.get('tts_model', '')} stt_model={result.get('stt_model', '')} vision_model={result.get('vision_model', '')}", flush=True)

                # Check Registry for existing agents that match each spec
                resolved_specs = []
                agents_for_plan = []
                has_existing = False
                used_agent_ids = set()
                for spec in agent_specs:
                    resource = manager.check_resources(spec, registry)
                    _debug(f"[DEBUG-PLAN] spec={spec.get('name','?')} role={spec.get('role','?')} resource_type={resource.get('type','?')}", flush=True)
                    if resource.get("type") == "existing":
                        _debug(f"[DEBUG-PLAN] existing match: {resource['agent'].get('name','?')} id={resource['agent'].get('id','?')} is_manager={resource['agent'].get('is_manager',False)} already_used={resource['agent'].get('id','?') in used_agent_ids}", flush=True)
                    if resource.get("type") == "existing" and resource["agent"].get("id") not in used_agent_ids:
                        existing_agent = resource["agent"]
                        used_agent_ids.add(existing_agent.get("id"))
                        merged = registry.to_spec(existing_agent)
                        merged["task_description"] = spec.get("task_description", user_input)
                        merged["depends_on"] = spec.get("depends_on", [])
                        merged["registry_id"] = existing_agent.get("id")
                        # Capture original values before secretary overrides
                        orig_tools = list(existing_agent.get("tools", []))
                        orig_goal = existing_agent.get("goal", "")
                        orig_persona = existing_agent.get("persona", "")
                        # Merge tools: preserve original tools, add new ones from secretary
                        # Never remove existing tools — secretary can only ADD capabilities
                        secretary_tools = spec.get("tools", [])
                        secretary_goal = spec.get("goal", "")
                        secretary_persona = spec.get("persona", spec.get("backstory", ""))
                        if secretary_tools:
                            merged_tools = list(orig_tools)
                            for t in secretary_tools:
                                if t not in merged_tools:
                                    merged_tools.append(t)
                            merged["tools"] = merged_tools
                        if secretary_goal:
                            merged["goal"] = secretary_goal
                        if secretary_persona:
                            merged["persona"] = secretary_persona
                        resolved_specs.append(merged)
                        agents_for_plan.append({
                            "id": existing_agent.get("id"),
                            "name": existing_agent.get("name", "Unnamed"),
                            "role": existing_agent.get("role", ""),
                            "goal": merged.get("goal", ""),
                            "persona": merged.get("persona", ""),
                            "personality": existing_agent.get("personality", {}),
                            "expertise": existing_agent.get("expertise", []),
                            "brand_context": existing_agent.get("brand_context", {}),
                            "tools": merged.get("tools", []),
                            "depends_on": spec.get("depends_on", []),
                            "status": existing_agent.get("status", "Idle"),
                            "is_existing": True,
                            "model": model_assignment.get("workers", {}).get(existing_agent.get("name", ""), model_assignment.get("manager", "")),
                            "original_tools": orig_tools,
                            "original_goal": orig_goal,
                            "original_persona": orig_persona,
                        })
                        has_existing = True
                    else:
                        resolved_specs.append(spec)
                        agents_for_plan.append({
                            "id": None,
                            "name": spec.get("name", "Unnamed"),
                            "role": spec.get("role", ""),
                            "goal": spec.get("goal", ""),
                            "persona": spec.get("persona", spec.get("backstory", "")),
                            "personality": spec.get("personality", {}),
                            "expertise": spec.get("expertise", []),
                            "brand_context": spec.get("brand_context", {}),
                            "tools": spec.get("tools", []),
                            "depends_on": spec.get("depends_on", []),
                            "status": "Idle",
                            "is_existing": False,
                            "model": model_assignment.get("workers", {}).get(spec.get("name", ""), model_assignment.get("manager", "")),
                        })

                cl.user_session.set("current_agent_specs", resolved_specs)
                cl.user_session.set("current_plan_type", "plan")
                cl.user_session.set("state", STATE_AWAITING_APPROVAL)

                print(f"[DEBUG-PLAN] Sending plan to frontend: {len(agents_for_plan)} agents, plan_type={'existing' if has_existing else 'new'}", flush=True)

                # Detect media tools from agent specs
                all_tools = []
                for spec in resolved_specs:
                    all_tools.extend(spec.get("tools", []))
                plan_has_image_tool = any("generate_image" in str(t) for t in all_tools)
                plan_has_video_tool = any("generate_video" in str(t) for t in all_tools)
                plan_has_search_tool = any("search" in str(t) for t in all_tools)
                plan_has_tts_tool = any("tts" in str(t).lower() for t in all_tools)
                plan_has_stt_tool = any("stt" in str(t).lower() or "transcri" in str(t).lower() for t in all_tools)
                plan_has_vision_tool = any("vision" in str(t).lower() for t in all_tools)

                if messenger:
                    await messenger.update_agents(registry)
                    plan_type = "existing" if has_existing else "new"
                    _plan_title = resolved_specs[0].get("task_description", user_input) if resolved_specs else user_input
                    await messenger.set_multi_agent_plan(
                        agents_for_plan,
                        _plan_title,
                        plan_type=plan_type,
                    )
                    await messenger.reply_plan(agents_for_plan, _plan_title, plan_type=plan_type,
                        image_model=result.get('image_model', ''),
                        video_model=result.get('video_model', ''),
                        search_model=result.get('search_model', ''),
                        tts_model=result.get('tts_model', ''),
                        stt_model=result.get('stt_model', ''),
                        vision_model=result.get('vision_model', ''),
                        has_image_tool=plan_has_image_tool,
                        has_video_tool=plan_has_video_tool,
                        has_search_tool=plan_has_search_tool,
                        has_tts_tool=plan_has_tts_tool,
                        has_stt_tool=plan_has_stt_tool,
                        has_vision_tool=plan_has_vision_tool,
                        has_vision_input=cl.user_session.get("has_vision_input", False),
                        manager_model=model_assignment.get('manager', ''),
                        agent_specs=resolved_specs,
                        model_assignment=model_assignment,
                        current_input=user_input)
                    print("[DEBUG-PLAN] reply_plan sent", flush=True)

                    task_store = cl.user_session.get("task_store")
                    if not task_store:
                        task_store = TaskStore(user_id=cl.user_session.get("user_id", "default"))
                        cl.user_session.set("task_store", task_store)
                    current_team_id = cl.user_session.get("current_team_id", "")
                    current_session_id = cl.user_session.get("current_session_id", messenger.current_session_id)
                    task_entry = task_store.add_task({
                        "team_id": current_team_id,
                        "session_id": current_session_id,
                        "status": "draft",
                        "plan_agents": [{"name": s.get("name", ""), "role": s.get("role", "")} for s in resolved_specs],
                        "plan_type": "existing" if has_existing else "new",
                        "input": user_input[:500],
                        "progress": 0,
                        "result": None,
                        "images": [],
                    })
                    cl.user_session.set("current_task_id", task_entry["id"])
                    await messenger.update_tasks(task_store)

        except Exception as e:
            cl.user_session.set("state", STATE_IDLE)
            if _is_rate_limit_error(e):
                llm_mgr = LLMManager()
                llm_mgr.report_rate_limit()
                if messenger:
                    await messenger.reply("⚠️ ติดลิมิต AI ฝรั่ง สลับไป Local LLM ชั่วคราว (60 วินาที) กรุณาลองใหม่")
            elif messenger:
                await messenger.reply(f"❌ เกิดข้อผิดพลาด: {str(e)}")

    elif state == STATE_GATHERING_REQUIREMENTS:
        # User is answering clarifying questions — re-assess with new info
        cl.user_session.set("state", STATE_ASSESSING)
        conversation_history.append({"role": "user", "content": user_input})
        cl.user_session.set("conversation_history", conversation_history)

        try:
            llm_manager = LLMManager()
            selected_model = cl.user_session.get("selected_model") or llm_manager.get_selected_model_name()
            if selected_model and llm_manager._is_openrouter():
                llm_manager.set_selected_model(selected_model)
            tool_registry = ToolRegistry()
            manager = CentralManager(llm_manager)

            # Build model table for unified call
            model_table = "none"
            valid_model_ids = set()
            media_catalog = "none"

            # Pass registry and team agents so LLM can reuse existing agents
            registry_agents = registry.list_agents()
            current_team_id = cl.user_session.get("current_team_id")
            team_agents = None
            team_name = None
            if current_team_id:
                team_registry = cl.user_session.get("team_registry") or TeamRegistry()
                team = team_registry.get_team(current_team_id)
                if team:
                    team_name = team.get("name", "")
                    team_agents = registry.list_agents(team_id=current_team_id)

            # Pass last task context if available
            last_task_context = None
            last_result = cl.user_session.get("last_task_result")
            last_specs = cl.user_session.get("last_agent_specs")
            last_input = cl.user_session.get("last_user_input")
            if last_result and last_specs:
                last_task_context = {
                    "user_input": last_input or "",
                    "result": last_result,
                    "agents": last_specs,
                }

            thinking_id = f"thinking-reassess-{int(time.time())}"
            if messenger:
                await messenger.reply_thinking("…", thinking_id)
            async def _stream_cb_reassess(chunk: str):
                if messenger:
                    await messenger.reply_thinking(chunk, thinking_id)

            result = await manager.assess_and_plan(
                user_input, conversation_history,
                model_table=model_table,
                valid_model_ids=valid_model_ids,
                media_catalog=media_catalog,
                stream_callback=_stream_cb_reassess,
                registry_agents=registry_agents,
                team_agents=team_agents,
                team_name=team_name,
                last_task_context=last_task_context,
                force_plan=True,
                has_attachment=bool(cl.user_session.get("last_attachment_url")),
            )
            if messenger:
                await messenger.reply_thinking_done(thinking_id)
            print(f"[DEBUG-REASSESS] action={result.get('action')}", flush=True)

            action = result.get("action", "chat")

            if action == "ask":
                # Force proceed — don't ask again, use available info
                print(f"[DEBUG-REASSESS] Got 'ask' in GATHERING_REQUIREMENTS, forcing proceed", flush=True)
                result = await manager.assess_and_plan(
                    user_input, conversation_history,
                    model_table=model_table,
                    valid_model_ids=valid_model_ids,
                    media_catalog=media_catalog,
                    stream_callback=_stream_cb_reassess,
                    force_proceed=True,
                    registry_agents=registry_agents,
                    team_agents=team_agents,
                    team_name=team_name,
                    has_attachment=bool(cl.user_session.get("last_attachment_url")),
                )
                if messenger:
                    await messenger.reply_thinking_done(thinking_id)
                action = result.get("action", "plan")
                # Fall through to plan/create_agents handling below

            if action == "plan":
                # Now we have enough info — unified call already produced agent specs
                cl.user_session.set("state", STATE_PLANNING)
                cl.user_session.set("asked_questions", [])
                original_input = cl.user_session.get("current_input") or user_input
                combined_input = original_input + " " + user_input

                agent_specs = result.get("agents", [])
                model_assignment = result.get("model_assignment", {"manager": "", "workers": {}})
                # Manager model = top bar selected_model (single manager)
                selected = cl.user_session.get("selected_model") or ""
                if selected:
                    model_assignment["manager"] = selected
                if not agent_specs:
                    raise ValueError("AI ไม่สามารถวิเคราะห์แผนงานได้")

                cl.user_session.set("pre_assigned_models", model_assignment)
                cl.user_session.set("ai_image_model", result.get("image_model", ""))
                cl.user_session.set("ai_video_model", result.get("video_model", ""))
                cl.user_session.set("ai_search_model", result.get("search_model", ""))
                cl.user_session.set("ai_tts_model", result.get("tts_model", ""))
                cl.user_session.set("ai_stt_model", result.get("stt_model", ""))
                cl.user_session.set("ai_vision_model", result.get("vision_model", ""))

                # Check Registry for existing agents
                resolved_specs = []
                agents_for_plan = []
                has_existing = False
                for spec in agent_specs:
                    resource = manager.check_resources(spec, registry)
                    if resource["type"] == "existing":
                        existing_agent = resource["agent"]
                        merged = registry.to_spec(existing_agent)
                        merged["task_description"] = spec.get("task_description", combined_input)
                        merged["depends_on"] = spec.get("depends_on", [])
                        merged["registry_id"] = existing_agent.get("id")
                        resolved_specs.append(merged)
                        agents_for_plan.append({
                            "id": existing_agent.get("id"),
                            "name": existing_agent.get("name", "Unnamed"),
                            "role": existing_agent.get("role", ""),
                            "goal": existing_agent.get("goal", ""),
                            "persona": existing_agent.get("persona", ""),
                            "personality": existing_agent.get("personality", {}),
                            "expertise": existing_agent.get("expertise", []),
                            "brand_context": existing_agent.get("brand_context", {}),
                            "tools": existing_agent.get("tools", []),
                            "depends_on": spec.get("depends_on", []),
                            "status": existing_agent.get("status", "Idle"),
                            "is_existing": True,
                            "model": model_assignment.get("workers", {}).get(existing_agent.get("name", ""), model_assignment.get("manager", "")),
                        })
                        has_existing = True
                    else:
                        resolved_specs.append(spec)
                        agents_for_plan.append({
                            "id": None,
                            "name": spec.get("name", "Unnamed"),
                            "role": spec.get("role", ""),
                            "goal": spec.get("goal", ""),
                            "persona": spec.get("persona", spec.get("backstory", "")),
                            "personality": spec.get("personality", {}),
                            "expertise": spec.get("expertise", []),
                            "brand_context": spec.get("brand_context", {}),
                            "tools": spec.get("tools", []),
                            "depends_on": spec.get("depends_on", []),
                            "status": "Idle",
                            "is_existing": False,
                            "model": model_assignment.get("workers", {}).get(spec.get("name", ""), model_assignment.get("manager", "")),
                        })

                cl.user_session.set("current_input", combined_input)
                cl.user_session.set("current_agent_specs", resolved_specs)
                cl.user_session.set("current_plan_type", "plan")
                cl.user_session.set("state", STATE_AWAITING_APPROVAL)

                # Detect media tools from agent specs
                plan2_all_tools = []
                for spec in resolved_specs:
                    plan2_all_tools.extend(spec.get("tools", []))
                plan2_has_image = any("generate_image" in str(t) for t in plan2_all_tools)
                plan2_has_video = any("generate_video" in str(t) for t in plan2_all_tools)
                plan2_has_search = any("search" in str(t) for t in plan2_all_tools)
                plan2_has_tts = any("tts" in str(t).lower() for t in plan2_all_tools)
                plan2_has_stt = any("stt" in str(t).lower() or "transcri" in str(t).lower() for t in plan2_all_tools)
                plan2_has_vision = any("vision" in str(t).lower() for t in plan2_all_tools)

                if messenger:
                    await messenger.update_agents(registry)
                    plan_type = "existing" if has_existing else "new"
                    _plan_title = resolved_specs[0].get("task_description", combined_input) if resolved_specs else combined_input
                    await messenger.set_multi_agent_plan(
                        agents_for_plan,
                        _plan_title,
                        plan_type=plan_type,
                    )
                    await messenger.reply_plan(agents_for_plan, _plan_title, plan_type=plan_type,
                        image_model=result.get('image_model', ''),
                        video_model=result.get('video_model', ''),
                        search_model=result.get('search_model', ''),
                        tts_model=result.get('tts_model', ''),
                        stt_model=result.get('stt_model', ''),
                        vision_model=result.get('vision_model', ''),
                        has_image_tool=plan2_has_image,
                        has_video_tool=plan2_has_video,
                        has_search_tool=plan2_has_search,
                        has_tts_tool=plan2_has_tts,
                        has_stt_tool=plan2_has_stt,
                        has_vision_tool=plan2_has_vision,
                        has_vision_input=cl.user_session.get("has_vision_input", False),
                        manager_model=model_assignment.get('manager', ''),
                        agent_specs=resolved_specs,
                        model_assignment=model_assignment,
                        current_input=combined_input)

                    task_store = cl.user_session.get("task_store")
                    if not task_store:
                        task_store = TaskStore(user_id=cl.user_session.get("user_id", "default"))
                        cl.user_session.set("task_store", task_store)
                    current_team_id = cl.user_session.get("current_team_id", "")
                    current_session_id = cl.user_session.get("current_session_id", messenger.current_session_id)
                    task_entry = task_store.add_task({
                        "team_id": current_team_id,
                        "session_id": current_session_id,
                        "status": "draft",
                        "plan_agents": [{"name": s.get("name", ""), "role": s.get("role", "")} for s in resolved_specs],
                        "plan_type": "existing" if has_existing else "new",
                        "input": combined_input[:500],
                        "progress": 0,
                        "result": None,
                        "images": [],
                    })
                    cl.user_session.set("current_task_id", task_entry["id"])
                    await messenger.update_tasks(task_store)
                return

            # Fallback: treat as chat
            cl.user_session.set("state", STATE_IDLE)
            response = result.get("message") or "ขออภัย ไม่เข้าใจ ลองใหม่อีกครั้ง"
            if messenger:
                await messenger.reply(response)
            conversation_history.append({"role": "assistant", "content": response})
            cl.user_session.set("conversation_history", conversation_history)

        except Exception as e:
            cl.user_session.set("state", STATE_IDLE)
            if _is_rate_limit_error(e):
                llm_mgr = LLMManager()
                llm_mgr.report_rate_limit()
                if messenger:
                    await messenger.notify("⚠️ ติดลิมิต AI ฝรั่ง สลับไป Local LLM ชั่วคราว (60 วินาที) กรุณาลองใหม่")
            elif messenger:
                await messenger.notify(f"❌ เกิดข้อผิดพลาด: {str(e)}")

    elif state in (STATE_CREATING_AGENT, STATE_EXECUTING, STATE_PLANNING, STATE_ASSESSING):
        if messenger:
            await messenger.notify(f"⏳ รอสถานะปัจจุบัน: {state}")



