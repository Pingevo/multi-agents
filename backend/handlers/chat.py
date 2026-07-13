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

import chainlit as cl
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
from backend.core.secretary import CentralSecretary
from backend.core.orchestrator import ExecutionOrchestrator
from backend.core.messenger import StateMessenger
from backend.attachment.processor import process_attachment, process_url
from backend.attachment.security import check_model_modality_support, llm_manager_tier_check
from backend.attachment.url import classify_url, URL_REGEX
from backend.handlers.actions import (
    on_action_create_agent,
    on_action_accept,
    on_action_reject,
    on_action_cancel,
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

    if messenger:
        agent_names = ", ".join(s.get("name", "Agent") for s in agent_specs)
        await messenger.add_task(task_id, user_input, agent_names)
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
        pre_assigned = cl.user_session.get("pre_assigned_models")
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
        result = await orchestrator.run_async(user_input, agent_specs, pre_assigned_models=pre_assigned)
        cl.user_session.set("pre_assigned_models", None)

        raw_output = result.get("raw", str(result))
        agent_outputs = result.get("agent_outputs", [])

        # Store last task context for feedback tuning
        cl.user_session.set("last_task_result", raw_output[:2000])
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
                    "output": (out.get("output", "") or "")[:2000],
                    "model": spec.get("model", ""),
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
                    refined = llm_manager.call_with_fallback(review_prompt)
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

            for idx, media_result in enumerate(sorted_results):
                await _send_approval_card(media_result, idx)

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
                        await _send_approval_card(media_entry, len(_g._media_tool_results) - 1)

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
                        await _send_approval_card(media_entry, len(_g._media_tool_results) - 1)

            has_pending_approvals = len(_g._media_tool_results) > 0
            print(f"[DEBUG-RESULT] media_tool_results={len(_g._media_tool_results)}, has_pending={has_pending_approvals}", flush=True)
            if has_pending_approvals:
                await messenger.reply_result(
                    f"⏳ งานเสร็จแล้ว — รออนุมัติสร้างสื่อ ({len(_g._media_tool_results)} รายการ) — ดูผลลัพธ์ใน Storyboard →",
                    agent_outputs,
                )
            else:
                await messenger.reply_result(
                    f"✅ งานเสร็จสมบูรณ์ ({len(agent_specs)} agents) — ดูผลลัพธ์ใน Storyboard →",
                    agent_outputs,
                )

            if raw_output and len(raw_output) > 20 and not raw_output.strip().startswith("{"):
                await messenger.reply(raw_output[:4000])
    except Exception as e:
        tb = traceback.format_exc()
        print(f"[CREW ERROR] {_sanitize_error(e)}")
        _debug(f"[TRACEBACK] {tb}", flush=True)
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
        if messenger:
            await messenger.update_agents(registry)
        cl.user_session.set("state", STATE_IDLE)
        cl.user_session.set("current_agent_specs", None)
        cl.user_session.set("current_input", None)


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

    if messenger:
        await messenger.add_task(task_id, user_input, agent_name)

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
        result = await orchestrator.run_async(user_input, [agent_spec])
        task_result = result

        # Store last task context for feedback tuning
        cl.user_session.set("last_task_result", str(result)[:2000])
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


@cl.on_chat_start
async def on_chat_start():
    registry = AgentRegistry()
    cl.user_session.set("registry", registry)
    cl.user_session.set("state", STATE_IDLE)
    cl.user_session.set("current_agent_specs", None)
    cl.user_session.set("current_input", None)
    cl.user_session.set("current_registry_id", None)
    cl.user_session.set("conversation_history", [])

    team_registry = TeamRegistry()
    cl.user_session.set("team_registry", team_registry)

    chat_store = ChatStore()
    # Create default session if none exists
    sessions = chat_store.list_sessions()
    if not sessions:
        default = chat_store.create_session("New Chat")
        current_session_id = default["id"]
    else:
        current_session_id = sessions[0]["id"]

    messenger = StateMessenger(task_store=TaskStore(), chat_store=chat_store)
    messenger.current_session_id = current_session_id
    cl.user_session.set("messenger", messenger)
    await messenger.init(registry)
    await messenger.set_status("Ready")
    await messenger.reply_chat_sessions()
    await messenger.reply_team_list(team_registry)
    await messenger.reply_chat_history(current_session_id)

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
    if settings.get("selected_model"):
        cl.user_session.set("selected_model", settings["selected_model"])
    # Restore media model overrides
    for key in ("ai_image_model", "ai_video_model", "ai_search_model", "ai_tts_model", "ai_stt_model", "ai_vision_model"):
        if settings.get(key):
            cl.user_session.set(key, settings[key])

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
            for media_type in ("image", "video", "search"):
                filtered = []
                for m in all_models:
                    arch = m.get("architecture", {})
                    output_modalities = arch.get("output_modalities", [])
                    mid = m.get("id", "").lower()
                    # Skip OpenRouter routing models — they are text-only, not real media models
                    if mid.startswith("openrouter/"):
                        continue
                    if media_type == "image" and "image" in output_modalities:
                        filtered.append(m)
                    elif media_type == "video" and "video" in output_modalities:
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
    registry = cl.user_session.get("registry") or AgentRegistry()
    messenger = get_messenger()

    # Parse mode prefix: __mode:chat__ or __mode:plan__
    input_mode = "plan"
    mode_match = re.match(r'^__mode:(chat|plan)__\n', user_input)
    if mode_match:
        input_mode = mode_match.group(1)
        user_input = user_input[mode_match.end():]

    # Extract attachment data from message
    attachment = None
    attachment_match = re.search(r'\[ATTACHMENT\|([^\|]+)\|([^\|]+)\|([^\]]+)\]', user_input)
    if attachment_match:
        file_url, file_name, file_mime = attachment_match.groups()
        attachment = {"file_url": file_url, "file_name": file_name, "file_mime": file_mime}
        # Remove attachment marker from user_input before processing
        user_input = re.sub(r'\n\n\[ATTACHMENT\|[^\]]+\]', '', user_input).strip()
        # Store attachment URL in session for later use
        cl.user_session.set("last_attachment_url", file_url)
        cl.user_session.set("last_attachment_name", file_name)
        cl.user_session.set("last_attachment_mime", file_mime)
        print(f"[ATTACHMENT] {file_name} → {file_url}", flush=True)

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
        elif action_name == "approve_image":
            approval_id = payload.get("approval_id", "")
            print(f"[APPROVE] approval_id={approval_id}", flush=True)
            # Persist approval status so it survives refresh
            if messenger:
                messenger.update_approval_status(approval_id, "approved")
            pending = cl.user_session.get(f"pending_media_{approval_id}")
            if pending and messenger:
                prompt = pending["prompt"]
                task_id = pending.get("task_id")
                media_type = pending.get("media_type", "image")
                duration = pending.get("duration", 5)
                print(f"[APPROVE] Generating {media_type}, model={cl.user_session.get('ai_image_model')}, prompt={prompt[:60]}...", flush=True)
                try:
                    llm_mgr = LLMManager()
                    gen_mgr = MediaGenerationManager(llm_mgr)
                    gen_mgr.set_models(
                        image_model=cl.user_session.get("ai_image_model") or "",
                        video_model=cl.user_session.get("ai_video_model") or "",
                    )
                    if media_type == "video":
                        result = await asyncio.to_thread(gen_mgr.generate_video, prompt, duration=duration)
                    else:
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
                    gen_mgr.set_models(
                        image_model=cl.user_session.get("ai_image_model") or "",
                        video_model=cl.user_session.get("ai_video_model") or "",
                    )
                    if media_type == "video":
                        result = await asyncio.to_thread(gen_mgr.generate_video, prompt, duration=duration)
                    else:
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
        elif action_name == "new_chat":
            current_team_id = cl.user_session.get("current_team_id")
            session = messenger.chat_store.create_session("New Chat", team_id=current_team_id)
            messenger.current_session_id = session["id"]
            await messenger.reply_chat_sessions()
            await messenger.reply_chat_history(session["id"])
        elif action_name == "switch_chat":
            session_id = payload.get("session_id", "")
            session = messenger.chat_store.get_session(session_id)
            if session:
                messenger.current_session_id = session_id
                # Restore settings for this session
                settings = messenger.chat_store.get_settings(session_id)
                cl.user_session.set("selected_model", settings.get("selected_model", ""))
                for key in ("ai_image_model", "ai_video_model", "ai_search_model", "ai_tts_model", "ai_stt_model", "ai_vision_model"):
                    cl.user_session.set(key, settings.get(key, ""))
                await messenger.reply_chat_sessions()
                await messenger.reply_chat_history(session_id)
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
            await messenger.reply_chat_sessions()
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
            await messenger.reply_chat_sessions()
            await messenger.reply_chat_history(messenger.current_session_id)
        elif action_name == "save_canvas":
            session_id = payload.get("session_id", "")
            canvas_state = payload.get("canvas_state", {})
            if session_id and canvas_state:
                messenger.chat_store.save_canvas_state(session_id, canvas_state)
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
                print(f"[DEBUG-MODEL-CHANGE] {agent_name} → {model_id}", flush=True)
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
            team_registry = cl.user_session.get("team_registry") or TeamRegistry()
            if team_id:
                team = team_registry.get_team(team_id)
                if team and messenger:
                    # List sessions for this team (include legacy unassigned sessions)
                    sessions = messenger.chat_store.list_sessions(team_id=team_id, include_unassigned=True)
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
                    # List agents for this team
                    registry = cl.user_session.get("registry") or AgentRegistry()
                    team_agents = registry.list_agents(team_id=team_id)
                    if messenger:
                        await messenger.update_agents(registry)
        elif action_name == "list_teams":
            team_registry = cl.user_session.get("team_registry") or TeamRegistry()
            if messenger:
                await messenger.reply_team_list(team_registry)
        return

    # Persist user message to chat session
    if messenger:
        messenger.persist_message({"role": "user", "content": user_input, "messageType": "text"})

    # Process attachment via unified pipeline
    attachment_ctx = None
    last_attach_url = cl.user_session.get("last_attachment_url") or ""
    last_attach_name = cl.user_session.get("last_attachment_name") or ""
    last_attach_mime = cl.user_session.get("last_attachment_mime") or ""
    if last_attach_url:
        attachment_ctx = await process_attachment(last_attach_url, last_attach_name, last_attach_mime)
        print(f"[ATTACHMENT] Processed {last_attach_name} → type={attachment_ctx['type']}", flush=True)

    # Detect and process URLs in user message
    urls_in_message = re.findall(URL_REGEX, user_input)
    print(f"[DEBUG-URL] Found {len(urls_in_message)} URLs in message: {urls_in_message}", flush=True)
    url_contexts = []
    for found_url in urls_in_message:
        if last_attach_url and found_url == last_attach_url:
            continue
        print(f"[DEBUG-URL] Processing URL: {found_url[:80]}...", flush=True)
        url_ctx = await process_url(found_url)
        url_contexts.append(url_ctx)
        print(f"[URL] Processed {found_url} → type={url_ctx['type']}", flush=True)

    # Merge attachment + URL contexts
    all_contexts = []
    if attachment_ctx:
        all_contexts.append(attachment_ctx)
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
        elif ctx["type"] == "text":
            text_context_parts.append(ctx["text_content"])
        if ctx.get("crewai_files"):
            crewai_files.update(ctx["crewai_files"])
        context_texts.append(ctx["context_text"])
        if ctx.get("required_modality"):
            required_modalities.append(ctx["required_modality"])

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
    if text_context_parts:
        user_input_for_ai = f"{user_input}\n\n[Attached content:\n" + "\n---\n".join(text_context_parts) + "\n]"
    elif context_summary:
        user_input_for_ai = f"{user_input}\n\n{context_summary}"
    else:
        user_input_for_ai = user_input

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

    # Gather conversation history for context
    conversation_history = cl.user_session.get("conversation_history") or []

    # Chat mode: bypass assess_and_plan, answer directly with LLM
    if input_mode == "chat" and state == STATE_IDLE:
        if messenger:
            await messenger.notify("💬 กำลังตอบ...")
        try:
            llm_manager = LLMManager()
            selected_model = cl.user_session.get("selected_model") or ""
            if selected_model and llm_manager._is_openrouter():
                llm_manager.set_selected_model(selected_model)
            secretary = CentralSecretary(llm_manager)
            if multimodal_blocks:
                response = await secretary.chat_response_multimodal(
                    user_input, multimodal_blocks, multimodal_plugins
                )
            elif text_context_parts:
                response = await secretary.chat_response(user_input_for_ai)
            else:
                response = await secretary.chat_response(user_input_for_ai)
            if messenger:
                await messenger.reply(response)
            conversation_history.append({"role": "user", "content": user_input, "attachment_context_text": context_summary})
            conversation_history.append({"role": "assistant", "content": response})
            cl.user_session.set("conversation_history", conversation_history)
        except Exception as e:
            if messenger:
                await messenger.reply(f"⚠️ เกิดข้อผิดพลาด: {_sanitize_error(e)}")
        finally:
            cl.user_session.set("last_attachment_url", None)
            cl.user_session.set("last_attachment_name", None)
            cl.user_session.set("last_attachment_mime", None)
            cl.user_session.set("attachment_context", None)
            cl.user_session.set("attachment_crewai_files", None)
        return

    if state == STATE_IDLE:
        cl.user_session.set("state", STATE_ASSESSING)
        if messenger:
            selected_model = cl.user_session.get("selected_model") or ""
            if selected_model:
                await messenger.notify(f"🧠 กำลังประเมินและวางแผน... (Model: {selected_model})")
                print(f"[PLAN] User selected model: {selected_model}", flush=True)
            else:
                # Adaptive — show which model the system will actually use
                llm_mgr_tmp = LLMManager()
                resolved = llm_mgr_tmp.get_selected_model_name()
                await messenger.notify(f"🧠 กำลังประเมินและวางแผน... (Adaptive → {resolved})")
                print(f"[PLAN] Adaptive mode → resolved to {resolved}", flush=True)

        try:
            llm_manager = LLMManager()
            selected_model = cl.user_session.get("selected_model") or llm_manager.get_selected_model_name()
            if selected_model and llm_manager._is_openrouter():
                llm_manager.set_selected_model(selected_model)
            tool_registry = ToolRegistry()
            secretary = CentralSecretary(llm_manager)

            # Build model table for unified call
            model_table = "none"
            valid_model_ids = set()
            if llm_manager._is_openrouter():
                model_selector = ModelSelector(
                    base_url=llm_manager.base_url,
                    api_key=llm_manager.api_key,
                    rotator=None,
                    default_model=llm_manager._default_model,
                )
                loop = asyncio.get_event_loop()
                candidates = await loop.run_in_executor(None, model_selector._get_candidates)
                valid_model_ids = {c["id"] for c in candidates}
                model_table = model_selector._build_candidate_table(candidates)
                discovery = ModelDiscoveryService(base_url=llm_manager.base_url, api_key=llm_manager.api_key)
                media_catalog = await loop.run_in_executor(None, discovery.get_catalog_summary)
            else:
                media_catalog = "none"

            thinking_id = f"thinking-{int(time.time())}"
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

            # Always pass registry agents so secretary can handle tuning anytime
            registry_agents = registry.list_agents()

            # Pass team agents if a team is selected
            team_agents = None
            team_name = None
            current_team_id = cl.user_session.get("current_team_id")
            if current_team_id:
                team_registry = cl.user_session.get("team_registry") or TeamRegistry()
                team = team_registry.get_team(current_team_id)
                if team:
                    team_name = team.get("name", "")
                    team_agents = registry.list_agents(team_id=current_team_id)

            result = await secretary.assess_and_plan(
                user_input_for_ai, conversation_history,
                model_table=model_table,
                valid_model_ids=valid_model_ids,
                media_catalog=media_catalog,
                stream_callback=_stream_cb,
                last_task_context=last_task_context,
                registry_agents=registry_agents,
                team_agents=team_agents,
                team_name=team_name,
            ) if not multimodal_blocks else await secretary.assess_and_plan_multimodal(
                user_input, multimodal_blocks, multimodal_plugins,
                conversation_history=conversation_history,
                model_table=model_table,
                valid_model_ids=valid_model_ids,
                media_catalog=media_catalog,
                stream_callback=_stream_cb,
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
                response = result.get("message") or await secretary.chat_response(user_input)
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

                tuning = await secretary.analyze_feedback(tuning_text, agent_specs_for_tuning, last_result)
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
                agents = registry.list_agents()
                tasks = messenger.state.get("tasks", []) if messenger else []
                if messenger:
                    await messenger.notify("ℹ️ กำลังดึงข้อมูลระบบ...")
                response = await secretary.info_response(user_input, agents, tasks, STATE_IDLE)
                if messenger:
                    await messenger.reply(response)
                conversation_history.append({"role": "user", "content": user_input})
                conversation_history.append({"role": "assistant", "content": response})
                cl.user_session.set("conversation_history", conversation_history)
                return

            if action == "ask":
                cl.user_session.set("state", STATE_GATHERING_REQUIREMENTS)
                cl.user_session.set("current_input", user_input)
                questions = result.get("questions", [])
                questions_text = "\n".join(f"• {q}" for q in questions)
                if messenger:
                    await messenger.reply(f"ก่อนที่จะเริ่มทำงาน ผมต้องการข้อมูลเพิ่มเติม:\n\n{questions_text}")
                conversation_history.append({"role": "user", "content": user_input})
                conversation_history.append({"role": "assistant", "content": f"Questions: {questions_text}"})
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
                _debug(f"[DEBUG-PLAN] agent_specs count={len(agent_specs)}, models={model_assignment}", flush=True)
                if agent_specs:
                    for s in agent_specs:
                        _debug(f"[DEBUG-PLAN] agent: {s.get('name', '?')} role={s.get('role', '?')} tools={s.get('tools', [])} model={s.get('model', '?')} depends_on={s.get('depends_on', [])}", flush=True)
                if not agent_specs:
                    raise ValueError("AI ไม่สามารถวิเคราะห์แผนงานได้")

                # Store model_assignment for run_async to skip assign_models
                cl.user_session.set("pre_assigned_models", model_assignment)
                cl.user_session.set("ai_image_model", result.get("image_model", ""))
                cl.user_session.set("ai_video_model", result.get("video_model", ""))
                cl.user_session.set("ai_search_model", result.get("search_model", ""))
                cl.user_session.set("ai_tts_model", result.get("tts_model", ""))
                cl.user_session.set("ai_stt_model", result.get("stt_model", ""))
                cl.user_session.set("ai_vision_model", result.get("vision_model", ""))
                print(f"[DEBUG-MODELS] image_model={result.get('image_model', '')} video_model={result.get('video_model', '')} search_model={result.get('search_model', '')} tts_model={result.get('tts_model', '')} stt_model={result.get('stt_model', '')} vision_model={result.get('vision_model', '')}", flush=True)

                # Check Registry for existing agents that match each spec
                resolved_specs = []
                agents_for_plan = []
                has_existing = False
                for spec in agent_specs:
                    resource = secretary.check_resources(spec, registry)
                    if resource["type"] == "existing":
                        existing_agent = resource["agent"]
                        merged = registry.to_spec(existing_agent)
                        merged["task_description"] = spec.get("task_description", user_input)
                        merged["depends_on"] = spec.get("depends_on", [])
                        merged["registry_id"] = existing_agent.get("id")
                        resolved_specs.append(merged)
                        agents_for_plan.append({
                            "id": existing_agent.get("id"),
                            "name": existing_agent.get("name", "Unnamed"),
                            "role": existing_agent.get("role", ""),
                            "goal": existing_agent.get("goal", ""),
                            "persona": existing_agent.get("persona", ""),
                            "tools": existing_agent.get("tools", []),
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
                            "persona": spec.get("backstory", ""),
                            "tools": spec.get("tools", []),
                            "depends_on": spec.get("depends_on", []),
                            "status": "Idle",
                            "is_existing": False,
                            "model": model_assignment.get("workers", {}).get(spec.get("name", ""), model_assignment.get("manager", "")),
                        })

                cl.user_session.set("current_agent_specs", resolved_specs)
                cl.user_session.set("state", STATE_AWAITING_APPROVAL)

                print(f"[DEBUG-PLAN] Sending plan to frontend: {len(agents_for_plan)} agents, plan_type={'existing' if has_existing else 'new'}", flush=True)

                if messenger:
                    await messenger.update_agents(registry)
                    plan_type = "existing" if has_existing else "new"
                    await messenger.set_multi_agent_plan(
                        agents_for_plan,
                        user_input,
                        plan_type=plan_type,
                    )
                    await messenger.reply_plan(agents_for_plan, user_input, plan_type=plan_type,
                        image_model=result.get('image_model', ''),
                        video_model=result.get('video_model', ''),
                        search_model=result.get('search_model', ''),
                        tts_model=result.get('tts_model', ''),
                        stt_model=result.get('stt_model', ''),
                        vision_model=result.get('vision_model', ''),
                        has_image_tool=result.get('image_model', '') != '' or result.get('has_image_tool', False),
                        has_video_tool=result.get('video_model', '') != '' or result.get('has_video_tool', False),
                        has_search_tool=result.get('search_model', '') != '' or result.get('has_search_tool', False),
                        has_tts_tool=result.get('tts_model', '') != '' or result.get('has_tts_tool', False),
                        has_stt_tool=result.get('stt_model', '') != '' or result.get('has_stt_tool', False),
                        has_vision_tool=result.get('vision_model', '') != '' or result.get('has_vision_tool', False),
                        manager_model=model_assignment.get('manager', ''),
                        agent_specs=resolved_specs,
                        model_assignment=model_assignment,
                        current_input=user_input)
                    print("[DEBUG-PLAN] reply_plan sent", flush=True)

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
            secretary = CentralSecretary(llm_manager)

            # Build model table for unified call
            model_table = "none"
            valid_model_ids = set()
            if llm_manager._is_openrouter():
                model_selector = ModelSelector(
                    base_url=llm_manager.base_url,
                    api_key=llm_manager.api_key,
                    rotator=None,
                    default_model=llm_manager._default_model,
                )
                loop = asyncio.get_event_loop()
                candidates = await loop.run_in_executor(None, model_selector._get_candidates)
                valid_model_ids = {c["id"] for c in candidates}
                model_table = model_selector._build_candidate_table(candidates)
                discovery = ModelDiscoveryService(base_url=llm_manager.base_url, api_key=llm_manager.api_key)
                media_catalog = await loop.run_in_executor(None, discovery.get_catalog_summary)
            else:
                media_catalog = "none"

            thinking_id = f"thinking-reassess-{int(time.time())}"
            async def _stream_cb_reassess(chunk: str):
                if messenger:
                    await messenger.reply_thinking(chunk, thinking_id)

            result = await secretary.assess_and_plan(
                user_input, conversation_history,
                model_table=model_table,
                valid_model_ids=valid_model_ids,
                media_catalog=media_catalog,
                stream_callback=_stream_cb_reassess,
            )
            if messenger:
                await messenger.reply_thinking_done(thinking_id)
            print(f"[DEBUG-REASSESS] action={result.get('action')}", flush=True)

            action = result.get("action", "chat")

            if action == "ask":
                # Still need more info
                cl.user_session.set("state", STATE_GATHERING_REQUIREMENTS)
                questions = result.get("questions", [])
                questions_text = "\n".join(f"• {q}" for q in questions)
                if messenger:
                    await messenger.reply(f"ขอบคุณครับ ยังต้องการข้อมูลเพิ่มอีกนิด:\n\n{questions_text}")
                conversation_history.append({"role": "assistant", "content": f"Questions: {questions_text}"})
                cl.user_session.set("conversation_history", conversation_history)
                return

            if action == "plan":
                # Now we have enough info — unified call already produced agent specs
                cl.user_session.set("state", STATE_PLANNING)
                original_input = cl.user_session.get("current_input") or user_input
                combined_input = original_input + " " + user_input

                agent_specs = result.get("agents", [])
                model_assignment = result.get("model_assignment", {"manager": "", "workers": {}})
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
                    resource = secretary.check_resources(spec, registry)
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
                            "tools": existing_agent.get("tools", []),
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
                            "persona": spec.get("backstory", ""),
                            "tools": spec.get("tools", []),
                            "depends_on": spec.get("depends_on", []),
                            "status": "Idle",
                            "is_existing": False,
                            "model": model_assignment.get("workers", {}).get(spec.get("name", ""), model_assignment.get("manager", "")),
                        })

                cl.user_session.set("current_input", combined_input)
                cl.user_session.set("current_agent_specs", resolved_specs)
                cl.user_session.set("state", STATE_AWAITING_APPROVAL)

                if messenger:
                    await messenger.update_agents(registry)
                    plan_type = "existing" if has_existing else "new"
                    await messenger.set_multi_agent_plan(
                        agents_for_plan,
                        combined_input,
                        plan_type=plan_type,
                    )
                    await messenger.reply_plan(agents_for_plan, combined_input, plan_type=plan_type,
                        image_model=result.get('image_model', ''),
                        video_model=result.get('video_model', ''),
                        search_model=result.get('search_model', ''),
                        tts_model=result.get('tts_model', ''),
                        stt_model=result.get('stt_model', ''),
                        vision_model=result.get('vision_model', ''),
                        has_image_tool=result.get('image_model', '') != '' or result.get('has_image_tool', False),
                        has_video_tool=result.get('video_model', '') != '' or result.get('has_video_tool', False),
                        has_search_tool=result.get('search_model', '') != '' or result.get('has_search_tool', False),
                        has_tts_tool=result.get('tts_model', '') != '' or result.get('has_tts_tool', False),
                        has_stt_tool=result.get('stt_model', '') != '' or result.get('has_stt_tool', False),
                        has_vision_tool=result.get('vision_model', '') != '' or result.get('has_vision_tool', False),
                        manager_model=model_assignment.get('manager', ''),
                        agent_specs=resolved_specs,
                        model_assignment=model_assignment,
                        current_input=combined_input)
                return

            # Fallback: treat as chat
            cl.user_session.set("state", STATE_IDLE)
            response = result.get("message") or await secretary.chat_response(user_input)
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

    elif state in (STATE_CREATING_AGENT, STATE_AWAITING_APPROVAL, STATE_EXECUTING, STATE_PLANNING, STATE_ASSESSING):
        if messenger:
            await messenger.notify(f"⏳ รอสถานะปัจจุบัน: {state}")



