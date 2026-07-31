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

# Max characters for agent output sent to chat — replaces scattered magic numbers (4000/6000/8000)
# that caused output to be truncated mid-sentence. 50000 is safe for WebSocket transport.
MAX_OUTPUT_CHARS = 50000


async def execute_multi_agent_task(
    user_input: str,
    agent_specs: list[dict],
    registry: AgentRegistry,
):
    """รัน Task กับหลาย Agent พร้อมกันใน Crew เดียว"""
    cl.user_session.set("state", STATE_EXECUTING)
    messenger = get_messenger()
    if messenger:
        messenger._main_loop = asyncio.get_event_loop()
    task_store = cl.user_session.get("task_store")
    task_id = cl.user_session.get("current_task_id") or str(uuid.uuid4())[:8]
    # Capture session ID at task start — used to prevent cross-session leak if user switches
    # sessions while task is running. Approval cards should only appear in the original session.
    _task_session_id = messenger.current_session_id if messenger else None
    from backend.globals import _thread_local, user_prompt_ctx
    _thread_local.user_prompt = user_input[:200]
    user_prompt_ctx.set(user_input[:200])

    if messenger:
        agent_names = ", ".join(s.get("name", "Agent") for s in agent_specs)
        existing_task = task_store.get_task(task_id) if task_store else None
        if existing_task:
            task_store.update_task(task_id, status="running", progress=0, agent=agent_names)
        else:
            await messenger.add_task(task_id, user_input[:60], agent_names, team_id=cl.user_session.get("current_team_id"))
        await messenger.update_tasks(task_store, team_id=cl.user_session.get("current_team_id"))
        messenger.log_history(task_id, user_input[:80], "User", "สั่งงาน: ", user_input[:200], team_id=cl.user_session.get("current_team_id") or "")
        messenger.log_history(task_id, user_input[:80], "Manager", "รับคำสั่ง สร้าง plan", team_id=cl.user_session.get("current_team_id") or "")
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
        # NOTE: reply_progress() is intentionally NOT called here — the progress card
        # gets stuck showing "กำลังเริ่มทำงาน..." after the task completes.
        # Progress is shown via agent_progress updates + TasksWindow instead.

    for spec in agent_specs:
        rid = spec.get("registry_id")
        if rid:
            registry.update_status(rid, "Busy")
    if messenger:
        _tid = cl.user_session.get("current_team_id")
        await messenger.update_agents(registry, team_id=_tid)

    _exec_loop = asyncio.get_event_loop()
    _exec_ctx = contextvars.copy_context()
    agent_outputs = []

    def update_progress(percent: int, status: str):
        if messenger:
            def _schedule():
                _exec_loop.create_task(
                    messenger.update_task(task_id, team_id=cl.user_session.get("current_team_id"), progress=percent, result=status),
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
        orchestrator = ExecutionOrchestrator(llm_manager, tool_registry, update_progress, update_agent_progress, user_id=cl.user_session.get("user_id"))
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
            await messenger.reply_progress(0, "กำลังเริ่มทำงาน...", progress_id=task_id)
            await messenger.notify("🔥 Crew เริ่มทำงานแล้ว — รอผลลัพธ์...")
        print(f"[DEBUG-EXEC] Calling orchestrator.run_async...", flush=True)
        result = await orchestrator.run_async(user_input, agent_specs, pre_assigned_models=pre_assigned, task_id=task_id, task_title=user_input[:80], messenger=messenger)
        print(f"[DEBUG-EXEC] orchestrator.run_async completed successfully", flush=True)
        cl.user_session.set("pre_assigned_models", None)

        raw_output = result.get("raw", str(result))
        agent_outputs = result.get("agent_outputs", [])
        agent_memories = result.get("agent_memories", {})

        # last_* session storage removed — context is now built from chat_store
        # via _build_last_task_context_from_chat_store, ensuring per-session isolation (Issue #30)

        if messenger:
            final_agents = []
            for i, spec in enumerate(agent_specs):
                out = agent_outputs[i] if i < len(agent_outputs) else {}
                final_agents.append({
                    "name": spec.get("name", "Agent"),
                    "role": spec.get("role", ""),
                    "status": "complete",
                    "progress": 100,
                    "output": (out.get("output", "") or "")[:MAX_OUTPUT_CHARS],
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
                    "output": (manager_output.get("output", "") or "")[:MAX_OUTPUT_CHARS],
                    "model": "",
                })
            await messenger.reply_agent_progress(task_id, final_agents)

            for i, spec in enumerate(agent_specs):
                out = agent_outputs[i] if i < len(agent_outputs) else {}
                agent_name = spec.get("name", f"Agent {i+1}")
                output_preview = (out.get("output", "") or "")[:200]
                messenger.log_history(task_id, user_input[:80], agent_name, "ทำงานเสร็จ: ", output_preview, team_id=cl.user_session.get("current_team_id") or "")

            # Bug 9: Use 'stopped' status when user cancelled — not 'complete'
            was_cancelled = cl.user_session.get("cancel_generation") or False
            cl.run_sync(
                messenger.update_task(
                    task_id,
                    team_id=cl.user_session.get("current_team_id"),
                    progress=100,
                    status="stopped" if was_cancelled else "complete",
                    result=raw_output,
                    agent_outputs=agent_outputs,
                    agent_progress=final_agents,
                )
            )

            # Map media type to the field that holds the display text for that type
            # — TTS stores 'text', STT stores 'audio_url', Vision stores 'question', etc.
            # Without this mapping, non-image/video types show empty strings in approval cards.
            prompt_map = {"image": "prompt", "video": "prompt", "tts": "text", "stt": "audio_url", "vision": "question", "document": "filename"}
            tool_map = {"image": "generate_image", "video": "generate_video", "tts": "text_to_speech", "stt": "transcribe_audio", "vision": "analyze_image", "document": "generate_document"}

            def _day_sort_key(item):
                # Use type-aware field to get display text for sort key
                field = prompt_map.get(item.get("type", "image"), "prompt")
                prompt_lower = item.get(field, "").lower()
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
                    # Use type-aware field mapping so reviewer sees actual content for all media types
                    prompts_text = "\n".join(
                        f"{i+1}. [{r.get('type','image')}] {r.get(prompt_map.get(r.get('type','image'), 'prompt'), '')}"
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
                                # Write back to the correct field for this media type
                                field = prompt_map.get(sorted_results[idx].get("type", "image"), "prompt")
                                sorted_results[idx][field] = m.group(3).strip()
                    print(f"[APPROVAL-FLOW] Prompts refined by reviewer", flush=True)
                except Exception as e:
                    print(f"[APPROVAL-FLOW] Review failed, using original prompts: {_sanitize_error(e)}", flush=True)
            else:
                print(f"[APPROVAL-FLOW] No reviewer in plan — prompts are final from agent", flush=True)

            async def _send_approval_card(media_result, idx):
                media_type = media_result.get("type", "image")
                # Use type-aware field mapping — TTS stores 'text', STT stores 'audio_url', etc.
                # Without this, non-image/video types have empty 'prompt' → approval card silently dropped
                prompt_field = prompt_map.get(media_type, "prompt")
                media_prompt = media_result.get(prompt_field, "")
                media_duration = media_result.get("duration", 5)
                agent_name = media_result.get("agent_name", "")
                if not agent_name:
                    # Map media type to the tool name that produces it
                    tool_name = tool_map.get(media_type, "generate_image")
                    for spec in agent_specs:
                        if tool_name in spec.get("tools", []):
                            agent_name = spec.get("name", "")
                            break
                _debug(f"[DEBUG-APPROVAL] Sending approval card: agent_name='{agent_name}', type={media_type}, prompt_len={len(media_prompt)}", flush=True)
                if not media_prompt:
                    return
                approval_id = f"{media_type}_{task_id}_{idx}"
                # Store ALL type-specific fields in pending data so approve/retry handlers can use them
                pending_data = {
                    "prompt": media_prompt,
                    "agent_name": agent_name,
                    "task_id": task_id,
                    "media_type": media_type,
                    "duration": media_duration,
                    "model": media_result.get("model", ""),
                }
                # Copy type-specific fields for non-image/video types
                for k, v in media_result.items():
                    if k not in ("type", "agent_name", "duration", "model") and k != prompt_field:
                        pending_data[k] = v
                cl.user_session.set(f"pending_media_{approval_id}", pending_data)
                # Also persist to chat_store so approve/retry works after backend restart
                # — cl.user_session is in-memory and lost on restart, but chat_store is JSON-backed
                _cs = cl.user_session.get("chat_store")
                _sid = messenger.current_session_id if messenger else None
                if _cs and _sid:
                    _cs.save_pending_media(_sid, approval_id, pending_data)
                # Pass the session ID at task start — prevents cross-session leak if user switched sessions
                await messenger.reply_image_approval(
                    media_prompt, approval_id, agent_name,
                    media_type=media_type, duration=media_duration,
                    model=media_result.get("model", ""),
                    task_session_id=_task_session_id or "",
                )

            # Collect all approval cards data (don't send yet)
            pending_approval_cards = []
            for idx, media_result in enumerate(sorted_results):
                pending_approval_cards.append((media_result, idx))

            # Post-execution validation: ensure agents used their assigned tools
            from backend.core.tool_validator import validate_tool_usage
            image_model = cl.user_session.get("ai_image_model") or ""
            await validate_tool_usage(agent_specs, agent_outputs, _g._media_tool_results, image_model=image_model, llm_manager=llm_manager)

            # Re-sort after validation may have added new results
            sorted_results = sorted(_g._media_tool_results, key=lambda r: (0 if r.get("type") == "image" else 1, _day_sort_key(r)))

            # Add any new results from validation to pending approval cards
            for idx, media_result in enumerate(sorted_results):
                if (media_result, idx) not in pending_approval_cards:
                    pending_approval_cards.append((media_result, idx))

            # Documents don't need approval — exclude them from the pending count
            # so the message says 'done' instead of 'waiting for approval' when only docs are pending
            has_pending_approvals = any(r.get("type") != "document" for r in _g._media_tool_results)
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

            # Send each agent's output as a separate chat bubble — including Manager.
            # Outputs are sent here after Manager review is complete (or after user stops,
            # in which case the orchestrator returns whatever outputs are available).
            for agent_out in agent_outputs:
                agent_name = agent_out.get("name", "")
                output_text = agent_out.get("output", "") or ""
                if output_text and len(output_text) > 10:
                    await messenger.reply_agent_output(agent_name, output_text[:MAX_OUTPUT_CHARS], agent_out.get("id", ""))

            # Now send approval cards after agent output bubbles
            # Documents are saved to disk and sent as download links — they don't need approval
            for media_result, idx in pending_approval_cards:
                mr_type = media_result.get("type", "image")
                if mr_type == "document":
                    # Save document content to disk and send as file result
                    doc_filename = media_result.get("filename", "document.md")
                    # Sanitize filename to prevent path traversal
                    doc_filename = os.path.basename(doc_filename)
                    doc_content = media_result.get("content", "")
                    doc_type = media_result.get("doc_type", "markdown")
                    user_id = cl.user_session.get("user_id", "")
                    if user_id:
                        doc_dir = os.path.join(DATA_DIR, "users", user_id, "generated")
                    else:
                        doc_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "public", "generated")
                    os.makedirs(doc_dir, exist_ok=True)
                    doc_path = os.path.join(doc_dir, doc_filename)
                    with open(doc_path, "w", encoding="utf-8") as f:
                        f.write(doc_content)
                    doc_url = f"/api/media/generated/{doc_filename}" if user_id else f"/public/generated/{doc_filename}"
                    await messenger.reply_file_result(doc_url, doc_filename, "text/markdown", media_result.get("agent_name", ""))
                    continue
                await _send_approval_card(media_result, idx)
                # Use type-aware field mapping — same as _send_approval_card
                _pf = prompt_map.get(media_result.get("type", "image"), "prompt")
                _display = media_result.get(_pf, "")
                messenger.log_history(task_id, user_input[:80], media_result.get("agent_name", "Agent"), f"ส่ง approval card ({media_result.get('type', 'image')}): ", _display[:200], team_id=cl.user_session.get("current_team_id") or "")

            # Send notifications so NotificationsWindow shows pending media approvals
            await messenger.reply_notifications(team_id=cl.user_session.get("current_team_id"))

            # Persist media_tool_results to chat_store — _g._media_tool_results is a global
            # in-memory list that's lost on restart; without this, approval cards can't be rebuilt
            _cs = cl.user_session.get("chat_store")
            _sid = messenger.current_session_id if messenger else None
            if _cs and _sid and _g._media_tool_results:
                _cs.save_media_tool_results(_sid, _g._media_tool_results)

            # Update task status to review (user can review results)
            task_store = cl.user_session.get("task_store")
            current_task_id = cl.user_session.get("current_task_id")
            if task_store and current_task_id:
                task_store.update_task(current_task_id, status="review", progress=100)
                await messenger.update_tasks(task_store, team_id=cl.user_session.get("current_team_id"))
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
            _tid = cl.user_session.get("current_team_id")
            cl.run_sync(
                messenger.update_task(
                    task_id,
                    team_id=_tid,
                    progress=100,
                    status="error",
                    result=f"❌ เกิดข้อผิดพลาด: {str(e)}\n\n```\n{tb[:1000]}\n```",
                )
            )
            await messenger.reply_agent_progress(
                task_id,
                [{"name": s.get("name", "Agent"), "role": s.get("role", ""), "status": "error", "progress": 100, "model": s.get("model", "")} for s in agent_specs],
            )
            await messenger.reply(f"❌ งานล้มเหลว: {str(e)[:500]}")
            messenger.log_history(task_id, user_input[:80], "System", "เกิดข้อผิดพลาด: ", str(e)[:200], team_id=_tid or "")
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
            _tid = cl.user_session.get("current_team_id")
            await messenger.update_agents(registry, team_id=_tid)
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
        await messenger.add_task(task_id, user_input, agent_name, team_id=cl.user_session.get("current_team_id"))
        messenger.log_history(task_id, user_input[:80], "User", "สั่งงาน: ", user_input[:200], team_id=cl.user_session.get("current_team_id") or "")
        messenger.log_history(task_id, user_input[:80], "Manager", "รับคำสั่ง สร้าง plan", team_id=cl.user_session.get("current_team_id") or "")

    if registry_id:
        registry.update_status(registry_id, "Busy")
        if messenger:
            _tid = cl.user_session.get("current_team_id")
            await messenger.update_agents(registry, team_id=_tid)

    _exec_loop = asyncio.get_event_loop()
    _exec_ctx = contextvars.copy_context()
    task_result = None

    def update_progress(percent: int, status: str):
        if messenger:
            def _schedule():
                _exec_loop.create_task(
                    messenger.update_task(task_id, team_id=cl.user_session.get("current_team_id"), progress=percent, result=status),
                    context=_exec_ctx,
                )
            _exec_loop.call_soon_threadsafe(_schedule)

    try:
        llm_manager = LLMManager()
        # Set user's selected model on this instance — without this, the LLMManager
        # uses the default routing model instead of the user's top-bar selection
        _sel = cl.user_session.get("selected_model") or ""
        if _sel and llm_manager._is_openrouter():
            llm_manager.set_selected_model(_sel)
        tool_registry = ToolRegistry()
        orchestrator = ExecutionOrchestrator(llm_manager, tool_registry, update_progress, user_id=cl.user_session.get("user_id"))
        result = await orchestrator.run_async(user_input, [agent_spec], task_id=task_id, task_title=user_input[:80], messenger=messenger)
        task_result = result

        # last_* session storage removed — context is now built from chat_store
        # via _build_last_task_context_from_chat_store, ensuring per-session isolation (Issue #30)

        if messenger:
            # Persist media_tool_results if any — single-agent tasks can also generate media
            _cs = cl.user_session.get("chat_store")
            _sid = messenger.current_session_id if messenger else None
            if _cs and _sid and _g._media_tool_results:
                _cs.save_media_tool_results(_sid, _g._media_tool_results)

            cl.run_sync(
                messenger.update_task(
                    task_id,
                    team_id=cl.user_session.get("current_team_id"),
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
            _tid = cl.user_session.get("current_team_id")
            cl.run_sync(
                messenger.update_task(
                    task_id,
                    team_id=_tid,
                    progress=100,
                    status="error",
                    result=f"❌ เกิดข้อผิดพลาด: {str(e)}\n\n```\n{tb[:1000]}\n```",
                )
            )
            await messenger.reply(f"❌ งานของ {agent_name} ล้มเหลว: {str(e)[:500]}")
            messenger.log_history(task_id, user_input[:80], "System", "เกิดข้อผิดพลาด: ", str(e)[:200], team_id=_tid or "")
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
                _tid = cl.user_session.get("current_team_id")
                await messenger.update_agents(registry, team_id=_tid)
        cl.user_session.set("state", STATE_IDLE)
        cl.user_session.set("current_agent_specs", None)
        cl.user_session.set("current_input", None)
        cl.user_session.set("current_registry_id", None)
        cl.user_session.set("attachment_context", None)
        cl.user_session.set("attachment_crewai_files", None)
        cl.user_session.set("attachment_plugins", None)


def _build_last_task_context_from_chat_store(session_id: str, chat_store: ChatStore) -> dict | None:
    """Build last_task_context by reading directly from chat_store.

    Replaces cl.user_session.get("last_*") — ensures context is always scoped
    to the current chat session, preventing cross-session context leakage (Issue #30).

    Finds the latest result message, then collects:
    - user input before the plan
    - result summary
    - agent specs from the plan
    - full agent outputs (text messages with agentName/agentId between plan and result)
    - all media results (image_result, audio_result, video_result, file_result, transcription_result)
    """
    session = chat_store.get_session(session_id)
    if not session:
        return None
    messages = session.get("messages", [])

    # Find the latest result message (search backwards)
    result_idx = None
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].get("messageType") == "result":
            result_idx = i
            break
    if result_idx is None:
        return None

    result_msg = messages[result_idx]
    result_summary = result_msg.get("resultSummary", "")

    # Find the plan message before this result
    plan_idx = None
    for i in range(result_idx - 1, -1, -1):
        if messages[i].get("messageType") == "plan":
            plan_idx = i
            break

    # Find the user input before the plan (or before result if no plan)
    search_from = plan_idx if plan_idx is not None else result_idx
    user_input = ""
    for i in range(search_from - 1, -1, -1):
        if messages[i].get("role") == "user":
            user_input = messages[i].get("content", "")
            break

    # Extract agent specs from plan
    agent_specs = []
    if plan_idx is not None:
        plan_msg = messages[plan_idx]
        plan_agents = plan_msg.get("planAgents", [])
        if isinstance(plan_agents, list):
            agent_specs = plan_agents

    # Collect agent outputs (text messages with agentName between plan and next user message)
    # Agent outputs are persisted AFTER result because chat.py calls reply_result before reply_agent_output,
    # so we must search beyond result_idx — up to the next user message (or end of messages)
    agent_outputs = []
    start_idx = (plan_idx + 1) if plan_idx is not None else 0
    # Find the next user message after result_idx — that marks the start of a new task
    next_user_idx = len(messages)
    for i in range(result_idx + 1, len(messages)):
        if messages[i].get("role") == "user":
            next_user_idx = i
            break
    for i in range(start_idx, next_user_idx):
        msg = messages[i]
        if msg.get("messageType") == "text" and msg.get("agentName"):
            agent_outputs.append({
                "name": msg.get("agentName", ""),
                "id": msg.get("agentId", ""),
                "output": msg.get("content", ""),
            })

    # Collect all media results between plan and result (and after result for late arrivals)
    media_types = ["image_result", "audio_result", "video_result", "file_result", "transcription_result"]
    media_results = []
    for i in range(start_idx, len(messages)):
        msg = messages[i]
        msg_type = msg.get("messageType", "")
        if msg_type in media_types:
            if msg_type == "image_result":
                media_results.append({
                    "type": msg.get("mediaType", "image"),
                    "url": msg.get("imageUrl", ""),
                    "prompt": msg.get("imagePrompt", ""),
                    "agentName": msg.get("agentName", ""),
                })
            elif msg_type == "audio_result":
                media_results.append({
                    "type": "audio",
                    "url": msg.get("audioUrl", ""),
                    "prompt": msg.get("audioPrompt", ""),
                    "agentName": msg.get("agentName", ""),
                })
            elif msg_type == "video_result":
                media_results.append({
                    "type": "video",
                    "url": msg.get("videoUrl", ""),
                    "prompt": msg.get("videoPrompt", ""),
                    "agentName": msg.get("agentName", ""),
                })
            elif msg_type == "file_result":
                media_results.append({
                    "type": "file",
                    "url": msg.get("fileUrl", ""),
                    "prompt": msg.get("fileName", ""),
                    "agentName": msg.get("agentName", ""),
                })
            elif msg_type == "transcription_result":
                media_results.append({
                    "type": "transcription",
                    "url": msg.get("audioUrl", ""),
                    "prompt": msg.get("transcriptionText", ""),
                    "agentName": msg.get("agentName", ""),
                })

    return {
        "user_input": user_input,
        "result": result_summary,
        "agents": agent_specs,
        "agent_outputs": agent_outputs,
        "media_results": media_results,
    }


def _restore_conversation_history(session_id: str, chat_store: ChatStore) -> list[dict]:
    """Rebuild conversation_history from persisted chat_store messages.

    Returns ALL messages (no cap) with full content (no truncation) —
    Secretary needs complete history to recall past tasks and media results (Issue #30).
    Includes agent outputs (text with agentName) and all media types so
    follow-up prompts after restart have the same context as live sessions.
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
                # Include agentName + agentId attribution so Secretary knows which agent produced each output
                agent_name = msg.get("agentName", "")
                agent_id = msg.get("agentId", "")
                raw_content = msg.get("content", "")
                if agent_name:
                    content = f"[Agent: {agent_name} (id={agent_id})]: {raw_content}"
                else:
                    content = raw_content
            elif msg_type == "plan":
                summary = msg.get("planSummary", "")
                agents = msg.get("planAgents", [])
                agent_names = [a.get("name", "") for a in agents] if isinstance(agents, list) else []
                content = f"Proposed plan: {summary}. Agents: {', '.join(agent_names)}"
            elif msg_type == "result":
                content = f"Task result: {msg.get('resultSummary', '')}"
            elif msg_type == "tuning_proposal":
                content = "Agent tuning proposed."
            elif msg_type == "image_result":
                # Restore image results so Secretary knows what images were generated (Issue #30)
                content = f"Image result: prompt={msg.get('imagePrompt', '')} | url={msg.get('imageUrl', '')} | agent={msg.get('agentName', '')}"
            elif msg_type == "image_approval":
                content = f"Image approval: prompt={msg.get('imagePrompt', '')} | status={msg.get('approvalStatus', '')} | agent={msg.get('agentName', '')}"
            elif msg_type == "audio_result":
                content = f"Audio result: prompt={msg.get('audioPrompt', '')} | url={msg.get('audioUrl', '')} | agent={msg.get('agentName', '')}"
            elif msg_type == "video_result":
                content = f"Video result: prompt={msg.get('videoPrompt', '')} | url={msg.get('videoUrl', '')} | agent={msg.get('agentName', '')}"
            elif msg_type == "file_result":
                content = f"File result: name={msg.get('fileName', '')} | url={msg.get('fileUrl', '')} | agent={msg.get('agentName', '')}"
            elif msg_type == "transcription_result":
                content = f"Transcription result: text={msg.get('transcriptionText', '')} | agent={msg.get('agentName', '')}"
            else:
                continue
        else:
            continue
        if not content:
            continue
        # No cap — send full content (Issue #30)
        history.append({"role": role, "content": content})
    return history


def _build_media_catalog_entries(models: list[dict], media_type: str) -> list[dict]:
    """Convert raw model dicts from OpenRouter API into catalog entries for the frontend.

    Handles two model formats:
    - Regular /models endpoint: has 'pricing' with per-token fields (prompt, completion, etc.)
    - Dedicated /videos/models or /images/models endpoints: has 'pricing_skus' with per-generation fields
    """
    entries = []
    for m in models:
        mid = m.get("id", "")
        name = m.get("name", mid)
        pricing = m.get("pricing", {})
        pricing_skus = m.get("pricing_skus", {})

        def _convert(price):
            try:
                return round(float(price) * 1_000_000, 6)
            except (ValueError, TypeError):
                return price if price else "?"

        # Extract pricing — dedicated endpoints use pricing_skus, regular endpoint uses pricing
        if media_type == "video" and pricing_skus:
            # Video models: pricing_skus has per-second pricing (e.g. duration_seconds, duration_seconds_with_audio)
            # Pick the most representative price — prefer with_audio, then base duration_seconds
            video_sku = (
                pricing_skus.get("duration_seconds_with_audio")
                or pricing_skus.get("duration_seconds")
                or pricing_skus.get("text_to_video_duration_seconds_720p")
                or pricing_skus.get("duration_seconds_720p")
                or pricing_skus.get("video_tokens")
                or "?"
            )
            # Video pricing is per-second, not per-token — convert to display-friendly format
            try:
                video_price = round(float(video_sku), 4)
            except (ValueError, TypeError):
                video_price = video_sku
            prompt_price = "?"
            comp_price = "?"
            image_price = "?"
            image_output_price = "?"
            video_output_price = video_price
            audio_price = "?"
            web_search_price = "?"
        elif media_type == "image" and pricing_skus:
            # Image models: pricing_skus has per-image pricing
            image_sku = (
                pricing_skus.get("generate")
                or pricing_skus.get("image")
                or pricing_skus.get("standard")
                or "?"
            )
            try:
                image_price = round(float(image_sku), 4)
            except (ValueError, TypeError):
                image_price = image_sku
            prompt_price = "?"
            comp_price = "?"
            image_output_price = image_price
            video_price = "?"
            video_output_price = "?"
            audio_price = "?"
            web_search_price = "?"
        else:
            # Regular /models endpoint — per-token pricing
            prompt_price = _convert(pricing.get("prompt", "?"))
            comp_price = _convert(pricing.get("completion", "?"))
            image_price = _convert(pricing.get("image", "?"))
            image_output_price = _convert(pricing.get("image_output", "?"))
            video_price = _convert(pricing.get("video", "?"))
            video_output_price = _convert(pricing.get("video_output", "?"))
            audio_price = _convert(pricing.get("audio", "?"))
            web_search_price = _convert(pricing.get("web_search", "?"))

        # For TTS/STT models from regular endpoint, text prices are misleading — show audio price instead
        # — without this, the picker displays prompt/completion prices that don't reflect actual TTS/STT cost
        if media_type in ("tts", "stt"):
            prompt_price = "?"
            comp_price = "?"

        all_prices = [prompt_price, comp_price, image_price, image_output_price, video_price, video_output_price, audio_price, web_search_price]
        known_prices = [p for p in all_prices if isinstance(p, (int, float))]
        media_price_map = {
            "image": image_price if isinstance(image_price, (int, float)) else image_output_price,
            "video": video_price if isinstance(video_price, (int, float)) else video_output_price,
            "search": web_search_price,
            "tts": audio_price,
            "stt": audio_price,
            "vision": None,
        }
        media_price = media_price_map.get(media_type)
        if media_price is not None:
            is_free = isinstance(media_price, (int, float)) and media_price == 0 and all(p == 0 for p in known_prices)
        else:
            is_free = len(known_prices) > 0 and all(p == 0 for p in known_prices)

        entries.append({
            "id": mid,
            "name": name,
            "context_length": m.get("context_length", "?"),
            "prompt_price": prompt_price,
            "completion_price": comp_price,
            "image_price": image_price,
            "image_output_price": image_output_price,
            "video_price": video_price,
            "video_output_price": video_output_price,
            "audio_price": audio_price,
            "web_search_price": web_search_price,
            "categories": [media_type],
            "is_free": is_free,
            "input_modalities": m.get("input_modalities", m.get("architecture", {}).get("input_modalities", [])),
            "output_modalities": m.get("output_modalities", m.get("architecture", {}).get("output_modalities", [])),
        })
    return entries


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

    task_store = TaskStore(user_id=user_id)
    cl.user_session.set("task_store", task_store)

    # Clean up stale tasks: any task still marked "running" from a previous session
    # is stale because backend restarted — no process is actually executing it.
    # Mark as "stopped" so UI doesn't show it as still working.
    stopped_task_ids = set()
    for t in task_store.tasks:
        if t.get("status") == "running":
            t["status"] = "stopped"
            stopped_task_ids.add(t.get("id", ""))
            print(f"[CHAT-START] Marked stale task {t.get('id', '?')} as stopped", flush=True)
    task_store._save()

    # Bug 10: Cleanup stale chat messages — make restart behave like user pressed stop.
    # When backend crashes mid-execution, persisted chat messages still show agents as
    # "running" and progress cards at 0%. This cleanup fixes all sessions for this user.
    if stopped_task_ids:
        for session in chat_store.sessions:
            msgs = session.get("messages", [])
            if not msgs:
                continue
            modified = False
            has_stopped_agent_progress = False

            # 10a: Update agent_progress messages for stopped tasks
            for m in msgs:
                if m.get("messageType") == "agent_progress":
                    task_id = m.get("taskId", "")
                    if task_id in stopped_task_ids:
                        has_stopped_agent_progress = True
                        agents = m.get("agents", [])
                        for a in agents:
                            if a.get("status") in ("running", "awaiting_review", "pending"):
                                a["status"] = "complete"
                                a["progress"] = 100
                                a["review_summary"] = "หยุดโดยระบบ (backend restart)"
                                modified = True
                        m["overallProgress"] = 100
                        m["agents"] = agents

            # 10b: Remove progress messages that are < 100% (stale "กำลังทำงาน...")
            msgs = [m for m in msgs if not (
                m.get("messageType") == "progress" and
                (m.get("progressPercent", 0) or 0) < 100
            )]
            # Check if we removed any
            if len(msgs) < len(session.get("messages", [])):
                modified = True
                session["messages"] = msgs

            # 10c: Add result message if session has stopped agent_progress but no result
            # — frontend needs a terminal message to set isProcessing = false
            # 10e: Also extract agent outputs from agent_progress and create agent_output
            # bubbles — when user stops normally, chat.py sends reply_agent_output for
            # each agent. Without this, restart shows no output bubbles (unlike stop).
            if has_stopped_agent_progress:
                # Check for existing agent output bubbles (messageType=text with agentName)
                has_agent_bubbles = any(
                    m.get("messageType") == "text" and m.get("agentName")
                    for m in msgs
                )
                # Extract agent outputs from agent_progress if no bubbles exist yet
                if not has_agent_bubbles:
                    agent_output_msgs = []
                    for m in msgs:
                        if m.get("messageType") == "agent_progress":
                            task_id = m.get("taskId", "")
                            if task_id in stopped_task_ids:
                                for a in m.get("agents", []):
                                    output_text = (a.get("output", "") or "").strip()
                                    agent_name = a.get("name", "Agent")
                                    if output_text and len(output_text) > 10:
                                        agent_output_msgs.append({
                                            "role": "assistant",
                                            "content": output_text,
                                            "messageType": "text",
                                            "agentName": agent_name,
                                        })
                    if agent_output_msgs:
                        modified = True

                # Add result message if missing — frontend needs terminal message to clear isProcessing
                has_result = any(m.get("messageType") == "result" for m in msgs)
                if not has_result:
                    # Insert agent output bubbles before result message
                    if agent_output_msgs:
                        msgs.extend(agent_output_msgs)
                    msgs.append({
                        "role": "assistant",
                        "messageType": "result",
                        "resultSummary": "หยุดโดยระบบ — แสดงผลลัพธ์ที่ทำเสร็จแล้ว",
                        "resultAgents": [],
                        "resultError": False,
                    })
                    modified = True
                elif agent_output_msgs:
                    # Result exists but bubbles don't — insert bubbles before result
                    result_idx = next((i for i, m in enumerate(msgs) if m.get("messageType") == "result"), len(msgs))
                    for j, bubble in enumerate(agent_output_msgs):
                        msgs.insert(result_idx + j, bubble)

            if modified:
                session["messages"] = msgs
                session["updated_at"] = datetime.now().isoformat()
                print(f"[CHAT-START] Cleaned stale messages in session {session.get('id', '?')}", flush=True)

        # 10d: Save all session changes
        chat_store._save()

    messenger = StateMessenger(task_store=task_store, chat_store=chat_store, history_store=HistoryStore(user_id=user_id))
    messenger.current_session_id = current_session_id
    messenger._main_loop = asyncio.get_event_loop()
    cl.user_session.set("messenger", messenger)

    # Restore user settings from persisted session (before init so team_id is available)
    settings = chat_store.get_settings(current_session_id)
    if settings.get("current_team_id"):
        cl.user_session.set("current_team_id", settings["current_team_id"])
    if settings.get("selected_model"):
        cl.user_session.set("selected_model", settings["selected_model"])
    else:
        # Fall back to manager agent's model from registry
        _tid = cl.user_session.get("current_team_id")
        for a in registry.list_agents(team_id=_tid):
            if a.get("is_manager") or a.get("role", "").lower() == "manager":
                mgr_model = a.get("model", "")
                if mgr_model:
                    cl.user_session.set("selected_model", mgr_model)
                break
    # Restore media model overrides
    for key in ("ai_image_model", "ai_video_model", "ai_search_model", "ai_tts_model", "ai_stt_model", "ai_vision_model"):
        if settings.get(key):
            cl.user_session.set(key, settings[key])

    # Now send initial state with team_id filtering
    current_team_id = cl.user_session.get("current_team_id")
    await messenger.init(registry, team_id=current_team_id)
    await messenger.set_status("Ready")
    await messenger.reply_chat_sessions(team_id=current_team_id)
    await messenger.reply_team_list(team_registry)
    await messenger.reply_chat_history(current_session_id)
    await messenger.reply_notifications(team_id=current_team_id)

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

    # Restore pending media from chat_store — cl.user_session is in-memory and lost on restart,
    # but pending_media is needed for approve/retry buttons on existing approval cards.
    # Without this, clicking approve after restart shows "ไม่พบคำขอสร้างสื่อ อาจหมดอายุแล้ว"
    _restored_media = chat_store.get_all_pending_media(current_session_id)
    if _restored_media:
        for _aid, _pdata in _restored_media.items():
            cl.user_session.set(f"pending_media_{_aid}", _pdata)
        print(f"[DEBUG-RESTORE] Restored {len(_restored_media)} pending media items from chat_store", flush=True)

    # Fix stale "approved" cards stuck on "กำลังสร้าง..." after backend restart —
    # user approved but backend died before sending result/error, so the card has no
    # working buttons. Reset to "pending" so user can re-approve.
    _session = chat_store.get_session(current_session_id)
    if _session:
        _msgs = _session.get("messages", [])
        _fixed = 0
        for _msg in _msgs:
            if (_msg.get("messageType") == "image_approval"
                    and _msg.get("approvalStatus") == "approved"):
                _msg["approvalStatus"] = "pending"
                _fixed += 1
        if _fixed:
            chat_store._save()
            print(f"[DEBUG-RESTORE] Reset {_fixed} stale 'approved' media cards back to 'pending'", flush=True)

    # Restore media_tool_results from chat_store — needed to rebuild approval cards if needed
    _saved_results = chat_store.get_media_tool_results(current_session_id)
    if _saved_results:
        _g._media_tool_results = _saved_results
        print(f"[DEBUG-RESTORE] Restored {len(_saved_results)} media_tool_results from chat_store", flush=True)

    # Restore pending tuning proposal from chat_store
    _saved_tuning = chat_store.get_tuning_proposal(current_session_id)
    if _saved_tuning:
        cl.user_session.set("pending_tuning_proposal", _saved_tuning)
        print(f"[DEBUG-RESTORE] Restored tuning proposal from chat_store", flush=True)

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

            # Also fetch and send media catalogs (image + video + search + vision)
            # Video and image models require dedicated endpoints — they don't appear in /models
            # with output_modalities=["video"] or ["image"] on OpenRouter's API
            selector = ModelSelector(llm_mgr.api_key, llm_mgr.base_url)
            all_models = await loop.run_in_executor(None, selector._fetch_all_models)
            LLMManager.populate_multimodal_cache(all_models)
            discovery = ModelDiscoveryService(base_url=llm_mgr.base_url, api_key=llm_mgr.api_key)

            for media_type in ("image", "video", "search", "vision"):
                if media_type == "video":
                    # Video models are only available via dedicated /videos/models endpoint
                    video_models = await loop.run_in_executor(None, discovery.fetch_video_models)
                    entries = _build_media_catalog_entries(video_models, "video")
                elif media_type == "image":
                    # Image models are only available via dedicated /images/models endpoint
                    image_models = await loop.run_in_executor(None, discovery.fetch_image_models)
                    entries = _build_media_catalog_entries(image_models, "image")
                else:
                    # Search, vision, etc. still use regular /models endpoint
                    filtered = []
                    for m in all_models:
                        arch = m.get("architecture", {})
                        output_modalities = arch.get("output_modalities", [])
                        input_modalities = arch.get("input_modalities", [])
                        mid = m.get("id", "").lower()
                        if mid.startswith("openrouter/"):
                            continue
                        if media_type == "vision" and "image" in input_modalities:
                            filtered.append(m)
                        elif media_type == "search":
                            params = m.get("supported_parameters", [])
                            search_keywords = ["sonar", "perplexity", "search", "online"]
                            if "web_search" in params or any(kw in mid for kw in search_keywords):
                                filtered.append(m)
                    if not filtered:
                        continue
                    entries = _build_media_catalog_entries(filtered, media_type)

                if not entries:
                    continue
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
        elif action_name == "add_agent" or action_name == "add_agent_form":
            # RetroDesktop sends "add_agent", MainLayout sends "add_agent_form" —
            # route both to the same handler so agents are always persisted
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
                await messenger.delete_task(task_id, team_id=cl.user_session.get("current_team_id"))
        elif action_name == "refresh_credits":
            if messenger:
                await messenger._send(trigger="refresh")
        elif action_name == "approve_image":
            approval_id = payload.get("approval_id", "")
            model_override = payload.get("model", "")
            print(f"[APPROVE] approval_id={approval_id}, model_override={model_override}", flush=True)
            # Persist approval status so it survives refresh
            if messenger:
                await messenger.update_approval_status(approval_id, "approved")
            pending = cl.user_session.get(f"pending_media_{approval_id}")
            # Fallback to chat_store if not in session — happens after backend restart
            # — without this fallback, approve button silently fails with "ไม่พบคำขอสร้างสื่อ"
            if not pending:
                _cs = cl.user_session.get("chat_store")
                _msgr = cl.user_session.get("messenger")
                _sid = _msgr.current_session_id if _msgr else None
                if _cs and _sid:
                    pending = _cs.get_pending_media(_sid, approval_id)
            if pending and messenger:
                prompt = pending["prompt"]
                task_id = pending.get("task_id")
                media_type = pending.get("media_type", "image")
                duration = pending.get("duration", 5)
                agent_name = pending.get("agent_name", "")
                print(f"[APPROVE] Generating {media_type}, model_override={model_override or cl.user_session.get('ai_image_model')}, prompt={prompt[:60]}...", flush=True)
                try:
                    llm_mgr = LLMManager()
                    gen_mgr = MediaGenerationManager(llm_mgr, user_id=cl.user_session.get("user_id"))
                    # Pass ALL 5 models — not just image/video, so TTS/STT/Vision can generate
                    resolved_image_model = model_override or cl.user_session.get("ai_image_model") or ""
                    resolved_video_model = model_override or cl.user_session.get("ai_video_model") or ""
                    resolved_tts_model = model_override or cl.user_session.get("ai_tts_model") or ""
                    resolved_stt_model = model_override or cl.user_session.get("ai_stt_model") or ""
                    resolved_vision_model = model_override or cl.user_session.get("ai_vision_model") or ""
                    print(f"[APPROVE] Resolved models: image={resolved_image_model!r}, video={resolved_video_model!r}, tts={resolved_tts_model!r}, stt={resolved_stt_model!r}, vision={resolved_vision_model!r}", flush=True)
                    gen_mgr.set_models(
                        image_model=resolved_image_model,
                        video_model=resolved_video_model,
                        tts_model=resolved_tts_model,
                        stt_model=resolved_stt_model,
                        vision_model=resolved_vision_model,
                    )
                    # Dispatch to the correct generation method based on media type
                    if media_type == "video":
                        if not resolved_video_model:
                            await messenger.reply("⚠️ ยังไม่ได้เลือก Video model — กรุณาเลือก model สำหรับสร้างวิดีโอก่อนกดอนุมัติ")
                            return
                        result = await asyncio.to_thread(gen_mgr.generate_video, prompt, duration=duration)
                    elif media_type == "tts":
                        if not resolved_tts_model:
                            await messenger.reply("⚠️ ยังไม่ได้เลือก TTS model — กรุณาเลือก model สำหรับสร้างเสียงก่อนกดอนุมัติ")
                            return
                        text = pending.get("text", prompt)
                        voice = pending.get("voice", "alloy")
                        result = await asyncio.to_thread(gen_mgr.generate_tts, text, voice)
                    elif media_type == "stt":
                        if not resolved_stt_model:
                            await messenger.reply("⚠️ ยังไม่ได้เลือก STT model — กรุณาเลือก model สำหรับการถอดเสียงก่อนกดอนุมัติ")
                            return
                        audio_url = pending.get("audio_url", prompt)
                        result = await asyncio.to_thread(gen_mgr.generate_stt, audio_url, user_id=cl.user_session.get("user_id", ""))
                    elif media_type == "vision":
                        if not resolved_vision_model:
                            await messenger.reply("⚠️ ยังไม่ได้เลือก Vision model — กรุณาเลือก model สำหรับวิเคราะห์ภาพก่อนกดอนุมัติ")
                            return
                        image_url = pending.get("image_url", "")
                        question = pending.get("question", prompt)
                        result = await asyncio.to_thread(gen_mgr.generate_vision, image_url, question, user_id=cl.user_session.get("user_id", ""))
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
                            prompt, approval_id, agent_name,
                            media_type=media_type, duration=duration,
                            model=pending.get("model", ""),
                            approval_status="error",
                            image_error=error_msg,
                        )
                        # Refresh notifications so error status is reflected
                        await messenger.reply_notifications(team_id=cl.user_session.get("current_team_id"))
                    else:
                        print(f"[APPROVE] {media_type} generated successfully: {result[:80]}", flush=True)
                        # Dispatch to the correct reply method based on media type
                        # — reply_image_result is for image/video only; TTS/STT/Vision need their own reply methods
                        if media_type == "tts":
                            await messenger.reply_audio_result(result, pending.get("text", prompt), pending.get("voice", ""), agent_name, resolved_tts_model)
                        elif media_type == "stt":
                            await messenger.reply_transcription_result(result, pending.get("audio_url", ""), agent_name, resolved_stt_model)
                        elif media_type == "vision":
                            await messenger.reply(result)
                        else:
                            await messenger.reply_image_result(result, prompt, approval_id, task_id=task_id, media_type=media_type, agent_name=agent_name)
                        # Only update task images for image/video — STT/Vision return text, not URLs
                        if task_id and media_type in ("image", "video"):
                            await messenger.update_task_image(task_id, result, prompt, media_type=media_type, team_id=cl.user_session.get("current_team_id"))
                        # Refresh notifications so the approval moves from "pending" to "completed" tab
                        await messenger.reply_notifications(team_id=cl.user_session.get("current_team_id"))
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
            # Fallback to chat_store if not in session — happens after backend restart
            if not pending:
                _cs = cl.user_session.get("chat_store")
                _msgr = cl.user_session.get("messenger")
                _sid = _msgr.current_session_id if _msgr else None
                if _cs and _sid:
                    pending = _cs.get_pending_media(_sid, approval_id)
            if pending and messenger:
                prompt = pending["prompt"]
                task_id = pending.get("task_id")
                media_type = pending.get("media_type", "image")
                duration = pending.get("duration", 5)
                agent_name = pending.get("agent_name", "")
                _debug(f"[DEBUG-RETRY] Retrying {media_type} for prompt: {prompt[:80]}...", flush=True)
                try:
                    llm_mgr = LLMManager()
                    gen_mgr = MediaGenerationManager(llm_mgr, user_id=cl.user_session.get("user_id"))
                    # Pass ALL 5 models — same fix as approve_image handler
                    retry_image_model = cl.user_session.get("ai_image_model") or ""
                    retry_video_model = cl.user_session.get("ai_video_model") or ""
                    retry_tts_model = cl.user_session.get("ai_tts_model") or ""
                    retry_stt_model = cl.user_session.get("ai_stt_model") or ""
                    retry_vision_model = cl.user_session.get("ai_vision_model") or ""
                    gen_mgr.set_models(
                        image_model=retry_image_model,
                        video_model=retry_video_model,
                        tts_model=retry_tts_model,
                        stt_model=retry_stt_model,
                        vision_model=retry_vision_model,
                    )
                    # Dispatch to the correct generation method based on media type
                    if media_type == "video":
                        if not retry_video_model:
                            await messenger.reply("⚠️ ยังไม่ได้เลือก Video model — กรุณาเลือก model สำหรับสร้างวิดีโอก่อน")
                            return
                        result = await asyncio.to_thread(gen_mgr.generate_video, prompt, duration=duration)
                    elif media_type == "tts":
                        if not retry_tts_model:
                            await messenger.reply("⚠️ ยังไม่ได้เลือก TTS model — กรุณาเลือก model สำหรับสร้างเสียงก่อน")
                            return
                        text = pending.get("text", prompt)
                        voice = pending.get("voice", "alloy")
                        result = await asyncio.to_thread(gen_mgr.generate_tts, text, voice)
                    elif media_type == "stt":
                        if not retry_stt_model:
                            await messenger.reply("⚠️ ยังไม่ได้เลือก STT model — กรุณาเลือก model สำหรับการถอดเสียงก่อน")
                            return
                        audio_url = pending.get("audio_url", prompt)
                        result = await asyncio.to_thread(gen_mgr.generate_stt, audio_url, user_id=cl.user_session.get("user_id", ""))
                    elif media_type == "vision":
                        if not retry_vision_model:
                            await messenger.reply("⚠️ ยังไม่ได้เลือก Vision model — กรุณาเลือก model สำหรับวิเคราะห์ภาพก่อน")
                            return
                        image_url = pending.get("image_url", "")
                        question = pending.get("question", prompt)
                        result = await asyncio.to_thread(gen_mgr.generate_vision, image_url, question, user_id=cl.user_session.get("user_id", ""))
                    else:
                        if not retry_image_model:
                            await messenger.reply("⚠️ ยังไม่ได้เลือก Image model — กรุณาเลือก model สำหรับสร้างรูปภาพก่อน")
                            return
                        result = await asyncio.to_thread(gen_mgr.generate_image, prompt)
                    if result.startswith("Error:"):
                        await messenger.reply(f"⚠️ {result}")
                    else:
                        print(f"[RETRY-TRACE] result={result[:60]}, calling update_approval_status", flush=True)
                        await messenger.update_approval_status(approval_id, "approved")
                        print(f"[RETRY-TRACE] update_approval_status done, calling reply_image_result", flush=True)
                        # Dispatch to the correct reply method based on media type
                        if media_type == "tts":
                            await messenger.reply_audio_result(result, pending.get("text", prompt), pending.get("voice", ""), agent_name, retry_tts_model)
                        elif media_type == "stt":
                            await messenger.reply_transcription_result(result, pending.get("audio_url", ""), agent_name, retry_stt_model)
                        elif media_type == "vision":
                            await messenger.reply(result)
                        else:
                            await messenger.reply_image_result(result, prompt, approval_id, task_id=task_id, media_type=media_type, agent_name=agent_name)
                        print(f"[RETRY-TRACE] reply_image_result done", flush=True)
                        # Only update task images for image/video — STT/Vision return text, not URLs
                        if task_id and media_type in ("image", "video"):
                            await messenger.update_task_image(task_id, result, prompt, media_type=media_type, team_id=cl.user_session.get("current_team_id"))
                        print(f"[RETRY-TRACE] update_task_image done", flush=True)
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
                # Fallback to chat_store if not in session — happens after backend restart
                if not pending:
                    _cs = cl.user_session.get("chat_store")
                    _sid = messenger.current_session_id if messenger else None
                    if _cs and _sid:
                        pending = _cs.get_pending_media(_sid, approval_id) or {}
                media_type = pending.get("media_type", "image")
                # Update the type-specific field, not just 'prompt'
                # — TTS uses 'text', Vision uses 'question', STT uses 'audio_url'
                prompt_field_map = {"image": "prompt", "video": "prompt", "tts": "text", "stt": "audio_url", "vision": "question", "document": "filename"}
                field = prompt_field_map.get(media_type, "prompt")
                pending[field] = new_prompt
                pending["prompt"] = new_prompt  # also update prompt for display consistency
                cl.user_session.set(f"pending_media_{approval_id}", pending)
                # Also update in chat_store so edited prompt survives restart
                _cs = cl.user_session.get("chat_store")
                _sid = messenger.current_session_id if messenger else None
                if _cs and _sid:
                    _cs.save_pending_media(_sid, approval_id, pending)
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
                await messenger.update_approval_status(approval_id, "rejected")
                await messenger.reply(f"❌ ยกเลิกการสร้างสื่อ (ID: {approval_id})")
                cl.user_session.set(f"pending_media_{approval_id}", None)
                # Also clear from chat_store — prevents stale pending data buildup in JSON
                _cs = cl.user_session.get("chat_store")
                _sid = messenger.current_session_id if messenger else None
                if _cs and _sid:
                    _cs.clear_pending_media(_sid, approval_id)
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
            # Fix: task_store is not a local var in on_message scope — fetch from session
            _ts = cl.user_session.get("task_store")
            await messenger.update_tasks(_ts, team_id=current_team_id)
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
                # Fix: task_store is not a local var in on_message scope — fetch from session
                _ts = cl.user_session.get("task_store")
                await messenger.update_tasks(_ts, team_id=current_team_id)
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
                # Restore pending media from chat_store — same as on_chat_start
                # — without this, approve/retry buttons fail after switching sessions
                _restored = messenger.chat_store.get_all_pending_media(session_id)
                if _restored:
                    for _aid, _pdata in _restored.items():
                        cl.user_session.set(f"pending_media_{_aid}", _pdata)
                    print(f"[DEBUG-RESTORE] Restored {len(_restored)} pending media for session {session_id}", flush=True)
                # Restore media_tool_results — needed to rebuild approval cards
                _saved_results = messenger.chat_store.get_media_tool_results(session_id)
                if _saved_results:
                    _g._media_tool_results = _saved_results
                # Restore pending tuning proposal
                _saved_tuning = messenger.chat_store.get_tuning_proposal(session_id)
                if _saved_tuning:
                    cl.user_session.set("pending_tuning_proposal", _saved_tuning)
        elif action_name == "rename_chat":
            session_id = payload.get("session_id", "")
            title = payload.get("title", "Untitled")
            messenger.chat_store.rename_session(session_id, title)
            current_team_id = cl.user_session.get("current_team_id")
            await messenger.reply_chat_sessions(team_id=current_team_id)
        elif action_name == "delete_chat":
            session_id = payload.get("session_id", "")
            messenger.chat_store.delete_session(session_id)
            # Delete only draft (pending) tasks from this session
            task_store = cl.user_session.get("task_store") or TaskStore(user_id=cl.user_session.get("user_id", "default"))
            draft_tasks = [t for t in task_store.get_tasks_by_session(session_id) if t.get("status") == "draft"]
            for t in draft_tasks:
                task_store.delete_task(t["id"])
            # Detach remaining tasks from the deleted session
            task_store.detach_tasks_by_session(session_id)
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
            await messenger.update_tasks(task_store, team_id=current_team_id)
            await messenger.reply_notifications(team_id=current_team_id)
            if draft_tasks:
                await messenger.notify(f"🗑 ลบแชทและ {len(draft_tasks)} task ที่รอดำเนินการแล้ว")
            else:
                await messenger.notify("🗑 ลบแชทแล้ว")
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
                # Pull from chat_store instead of cl.user_session — ensures per-session isolation (Issue #30)
                _ctx = _build_last_task_context_from_chat_store(
                    messenger.current_session_id, messenger.chat_store
                )
                last_input = _ctx.get("user_input", "") if _ctx else ""
                last_result = _ctx.get("result", "") if _ctx else ""
                user_id = cl.user_session.get("user_id", "default")
                # Use per-user directory (data/users/{uid}/) for ratings —
                # prevents cross-user data leakage when multiple users share the same server.
                from backend.globals import resolve_data_path
                ratings_file = Path(resolve_data_path("task_ratings.json", user_id=user_id))
                ratings_file.parent.mkdir(parents=True, exist_ok=True)
                # Migrate old flat file to per-user path if it exists (one-time)
                old_ratings = Path(f"data/task_ratings_{user_id}.json")
                if old_ratings.exists() and not ratings_file.exists():
                    old_ratings.rename(ratings_file)
                    print(f"[ratings] Migrated {old_ratings} -> {ratings_file}", flush=True)
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

                # Video and image models require dedicated endpoints — they don't appear
                # in the regular /models endpoint with output_modalities filtering
                if media_type == "video":
                    video_models = await loop.run_in_executor(None, discovery.fetch_video_models)
                    entries = _build_media_catalog_entries(video_models, "video")
                elif media_type == "image":
                    image_models = await loop.run_in_executor(None, discovery.fetch_image_models)
                    entries = _build_media_catalog_entries(image_models, "image")
                else:
                    # Search, vision, tts, stt still use regular /models endpoint
                    discovery_map = {
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
                    entries = _build_media_catalog_entries(filtered, media_type)

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
                _tid = cl.user_session.get("current_team_id")
                for a in registry.list_agents(team_id=_tid):
                    if a.get("is_manager") or a.get("role", "").lower() == "manager":
                        registry.update_agent(a["id"], {"model": model_id})
                        print(f"[DEBUG-MODEL-SYNC] Updated manager agent '{a.get('name')}' model → {model_id}", flush=True)
                        break
                # Push updated agent list to frontend
                messenger = cl.user_session.get("messenger")
                if messenger:
                    _tid = cl.user_session.get("current_team_id")
                    await messenger.update_agents(registry, team_id=_tid)
            # Persist settings to chat store so they survive refresh
            messenger = cl.user_session.get("messenger")
            if messenger and messenger.current_session_id:
                # Merge with existing settings — save_settings now merges, but
                # be explicit to avoid overwriting current_team_id, ai_*_model, etc.
                existing = messenger.chat_store.get_settings(messenger.current_session_id)
                existing["selected_model"] = model_id
                messenger.chat_store.save_settings(messenger.current_session_id, existing)
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
                # Per-user isolation: save attachments to data/users/{uid}/attachments/
                # — prevents cross-user data leakage when multiple users share the same server.
                _uid = cl.user_session.get("user_id")
                if _uid:
                    attach_dir = os.path.join(user_data_dir(_uid), "attachments")
                    _url_prefix = "/api/media/attachments"
                else:
                    # Dev mode fallback — use project root public/attachments/ (fixes pre-existing bug
                    # where os.path.dirname(__file__) resolved to backend/handlers/ instead of project root)
                    attach_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "public", "attachments")
                    _url_prefix = "/public/attachments"
                os.makedirs(attach_dir, exist_ok=True)
                # Sanitize filename
                safe_name = re.sub(r'[^a-zA-Z0-9._-]', '_', file_name)
                unique_name = f"{uuid.uuid4().hex[:8]}_{safe_name}"
                filepath = os.path.join(attach_dir, unique_name)
                try:
                    file_bytes = base64.b64decode(file_data.split(",")[-1] if "," in file_data else file_data)
                    with open(filepath, "wb") as f:
                        f.write(file_bytes)
                    file_url = f"{_url_prefix}/{unique_name}"
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
                    # List sessions for this team only — do NOT include unassigned
                    # sessions, as they may contain messages from another team's
                    # earlier use of the default session and would leak across teams.
                    sessions = messenger.chat_store.list_sessions(team_id=team_id)
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
                    # Restore conversation_history for the new team's session —
                    # cl.user_session is per-connection, so without this the previous
                    # team's history would leak into the new team's context (Issue #30)
                    cl.user_session.set("conversation_history", _restore_conversation_history(
                        messenger.current_session_id, messenger.chat_store
                    ))
                    # List agents for this team
                    registry = cl.user_session.get("registry")
                    if not registry:
                        registry = AgentRegistry(user_id=cl.user_session.get("user_id"))
                        cl.user_session.set("registry", registry)
                    team_agents = registry.list_agents(team_id=team_id)
                    if messenger:
                        await messenger.update_agents(registry, team_id=team_id)
                        task_store = cl.user_session.get("task_store")
                        if task_store:
                            await messenger.update_tasks(task_store, team_id=team_id)
                        await messenger.reply_notifications(team_id=team_id)
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
        att_ctx = await process_attachment(att["file_url"], att["file_name"], att["file_mime"], user_id=cl.user_session.get("user_id"))
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

    # Model compatibility check — strip unsupported modalities to prevent LLM crash
    selected_model = cl.user_session.get("selected_model") or ""
    if selected_model and required_modalities and llm_manager_tier_check():
        unsupported_modalities = set()
        for modality in required_modalities:
            if not check_model_modality_support(selected_model, modality):
                unsupported_modalities.add(modality)
                if messenger:
                    await messenger.reply(
                        f"⚠️ Model '{selected_model}' อาจไม่รองรับ {modality} input. "
                        f"แนะนำให้เปลี่ยน model เป็นที่รองรับ multimodal (เช่น Google Gemini)"
                    )
        # Strip unsupported media blocks so the LLM doesn't receive data it can't process
        # — without this, the model returns empty responses or crashes (e.g. GPT-5.6 + audio)
        if unsupported_modalities and multimodal_blocks:
            # Map modality names to content block types for filtering
            block_type_map = {
                "audio": "input_audio",
                "video": "video_url",
                "image": "image_url",
            }
            stripped_types = {block_type_map.get(m) for m in unsupported_modalities if block_type_map.get(m)}
            if stripped_types:
                original_count = len(multimodal_blocks)
                multimodal_blocks = [
                    b for b in multimodal_blocks
                    if b.get("type") not in stripped_types
                ]
                # Clear plugins if we stripped all blocks (plugins are for multimodal only)
                if not multimodal_blocks:
                    multimodal_plugins = None
                print(
                    f"[ATTACHMENT] Stripped {original_count - len(multimodal_blocks)} unsupported "
                    f"media block(s) for model '{selected_model}' (unsupported: {unsupported_modalities})",
                    flush=True,
                )

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

            # Build last task context from chat_store — ensures per-session isolation (Issue #30)
            last_task_context = _build_last_task_context_from_chat_store(
                messenger.current_session_id, messenger.chat_store
            )

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

            # Build last task context from chat_store — ensures per-session isolation (Issue #30)
            last_task_context = _build_last_task_context_from_chat_store(
                messenger.current_session_id, messenger.chat_store
            )

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

            # If user pressed stop while LLM was running, discard the result
            if cl.user_session.get("cancel_generation"):
                print(f"[DEBUG-CANCEL] Generation cancelled — discarding assess_and_plan result", flush=True)
                cl.user_session.set("state", STATE_IDLE)
                cl.user_session.set("cancel_generation", False)
                return

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

                # Pull from chat_store instead of cl.user_session — ensures per-session isolation (Issue #30)
                _tuning_ctx = _build_last_task_context_from_chat_store(
                    messenger.current_session_id, messenger.chat_store
                )
                last_specs = _tuning_ctx.get("agents", []) if _tuning_ctx else []
                last_result = _tuning_ctx.get("result", "") if _tuning_ctx else ""
                all_agents = registry.list_agents(team_id=cl.user_session.get("current_team_id"))

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

                # Fix: add thinking bubble during analyze_feedback — this is a second LLM call
                # that runs after the first thinking_done, leaving the user staring at a blank screen
                tuning_thinking_id = f"thinking-tuning-{int(time.time())}"
                if messenger:
                    await messenger.reply_thinking("📝 กำลังวิเคราะห์การปรับแต่ง agent...", tuning_thinking_id)
                tuning = await manager.analyze_feedback(tuning_text, agent_specs_for_tuning, last_result, conversation_history=conversation_history)
                if messenger:
                    await messenger.reply_thinking_done(tuning_thinking_id)
                proposals = tuning.get("tuning_proposals", [])

                if not proposals:
                    if messenger:
                        await messenger.reply("วิเคราะห์แล้ว — ไม่พบสิ่งที่ต้องปรับแต่งในตอนนี้")
                    return

                # Store tuning proposal in session for confirm/reject actions
                cl.user_session.set("pending_tuning_proposal", proposals)
                # Also persist to chat_store — survives restart so confirm/reject still works
                _cs = cl.user_session.get("chat_store")
                _sid = messenger.current_session_id if messenger else None
                if _cs and _sid:
                    _cs.save_tuning_proposal(_sid, proposals)

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

                # If user pressed stop while LLM was running, discard the result
                if cl.user_session.get("cancel_generation"):
                    print(f"[DEBUG-CANCEL] Generation cancelled — discarding force_proceed result", flush=True)
                    cl.user_session.set("state", STATE_IDLE)
                    cl.user_session.set("cancel_generation", False)
                    return

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

                # Auto-detect: if user wants visual output but no agent has generate_image, auto-add it
                _image_keywords = ['poster', 'image', 'picture', 'graphic', 'illustration', 'banner',
                                   'thumbnail', 'logo', 'infographic', 'ภาพ', 'โปสเตอร์', 'กราฟิก',
                                   'รูป', 'แบนเนอร์', 'ภาพประกอบ']
                _user_lower = user_input.lower()
                _needs_image = any(kw in _user_lower for kw in _image_keywords)
                _has_image_tool = any('generate_image' in str(s.get('tools', [])) for s in agent_specs)
                if _needs_image and not _has_image_tool:
                    _target_idx = 0
                    for i, s in enumerate(agent_specs):
                        _role = (s.get('role', '') + ' ' + s.get('name', '')).lower()
                        if any(kw in _role for kw in ['design', 'creative', 'artist', 'graphic', 'visual', 'ออกแบบ', 'กราฟิก', 'ศิลป์']):
                            _target_idx = i
                            break
                    _tools = agent_specs[_target_idx].get('tools', [])
                    if 'generate_image' not in _tools:
                        _tools.append('generate_image')
                        agent_specs[_target_idx]['tools'] = _tools
                        _debug(f"[DEBUG-AUTO-TOOL] Auto-added generate_image to agent '{agent_specs[_target_idx].get('name', '?')}'", flush=True)

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
                    resource = manager.check_resources(spec, registry, team_id=cl.user_session.get("current_team_id"))
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
                        # Preserve user-configured fields — Secretary must NOT override
                        # goal/persona of existing agents. Only task_description and
                        # depends_on are per-task and can be set by Secretary.
                        orig_tools = list(existing_agent.get("tools", []))
                        # Preserve original goal/persona for plan display — Secretary
                        # must NOT override these on existing agents (see comment above)
                        orig_goal = existing_agent.get("goal", "")
                        orig_persona = existing_agent.get("persona", "")
                        # Merge tools: preserve original tools, add new ones from secretary
                        secretary_tools = spec.get("tools", [])
                        if secretary_tools:
                            merged_tools = list(orig_tools)
                            for t in secretary_tools:
                                if t not in merged_tools:
                                    merged_tools.append(t)
                            merged["tools"] = merged_tools
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
                    _tid = cl.user_session.get("current_team_id")
                    await messenger.update_agents(registry, team_id=_tid)
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
                    await messenger.update_tasks(task_store, team_id=cl.user_session.get("current_team_id"))
                    await messenger.reply_notifications(team_id=cl.user_session.get("current_team_id"))

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

            # Build last task context from chat_store — ensures per-session isolation (Issue #30)
            last_task_context = _build_last_task_context_from_chat_store(
                messenger.current_session_id, messenger.chat_store
            )

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

                # If user pressed stop while LLM was running, discard the result
                if cl.user_session.get("cancel_generation"):
                    print(f"[DEBUG-CANCEL] Generation cancelled — discarding reassess result", flush=True)
                    cl.user_session.set("state", STATE_IDLE)
                    cl.user_session.set("cancel_generation", False)
                    return

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
                    resource = manager.check_resources(spec, registry, team_id=cl.user_session.get("current_team_id"))
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
                    _tid = cl.user_session.get("current_team_id")
                    await messenger.update_agents(registry, team_id=_tid)
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
                    await messenger.update_tasks(task_store, team_id=cl.user_session.get("current_team_id"))
                    await messenger.reply_notifications(team_id=cl.user_session.get("current_team_id"))
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



