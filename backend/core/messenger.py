"""StateMessenger — sends platform state to frontend via JSON messages."""

import asyncio
import json
import os
import requests
from datetime import datetime

import chainlit as cl
from backend.globals import AGENT_REGISTRY_FILE, TASK_REGISTRY_FILE, CHAT_SESSIONS_FILE
from backend.agents.task_store import TaskStore
from backend.agents.chat_store import ChatStore
from backend.agents.history_store import HistoryStore
from backend.agents.registry import AgentRegistry
from backend.agents.tool_registry import ToolRegistry
from backend.agents.team_registry import TeamRegistry
from backend.llm.manager import LLMManager
from schemas import (
    PlanAgentItem, ResultAgentItem, AgentProgressEntry,
    ChatReplyText, ChatReplyPlanValidationError, ChatReplyPlan, ChatReplyProgress,
    ChatReplyAgentProgress, ChatReplyResult, ChatReplyImageApproval, ChatReplyImageResult,
    ChatReplyAudioResult, ChatReplyTranscriptionResult, ChatReplyVideoResult, ChatReplyFileResult,
    ChatReplyModelCatalog, ModelCatalogItem, ChatReplyAgentReview, chat_reply,
)

class StateMessenger:
    """ส่ง Platform State ให้ Custom Frontend ผ่าน JSON Messages"""

    def __init__(self, task_store: TaskStore | None = None, chat_store: ChatStore | None = None, history_store: HistoryStore | None = None):
        self.task_store = task_store or TaskStore()
        self.chat_store = chat_store or ChatStore()
        self.history_store = history_store or HistoryStore()
        self.current_session_id: str | None = None
        self._main_loop: asyncio.AbstractEventLoop | None = None
        self.state = {
            "tasks": self.task_store.list_tasks(),
            "current_plan": None,
            "notifications": [],
            "system_status": "Ready",
            "available_tools": ToolRegistry().list_tool_catalog(),
            "credits": None,
        }

    @staticmethod
    def _fetch_credits() -> dict | None:
        """Fetch credit balance from OpenRouter /key endpoint."""
        try:
            llm_mgr = LLMManager()
            if not llm_mgr._is_openrouter():
                return None
            resp = requests.get(
                f"{llm_mgr.base_url}/key",
                headers={"Authorization": f"Bearer {llm_mgr.api_key}"},
                timeout=5,
            )
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                return {
                    "limit": data.get("limit"),
                    "limit_remaining": data.get("limit_remaining"),
                    "limit_reset": data.get("limit_reset"),
                    "usage": data.get("usage", 0),
                    "usage_daily": data.get("usage_daily", 0),
                    "usage_weekly": data.get("usage_weekly", 0),
                    "usage_monthly": data.get("usage_monthly", 0),
                    "is_free_tier": data.get("is_free_tier", True),
                }
        except Exception as e:
            print(f"[Credits] Failed to fetch: {_sanitize_error(e)}")
        return None

    @staticmethod
    def _get_resolved_model_name() -> str:
        """Get the actual model name that adaptive mode would pick."""
        try:
            return LLMManager().get_selected_model_name()
        except Exception:
            return "local"

    @staticmethod
    def _agents_for_ui(agents: list[dict]) -> list[dict]:
        return [
            {
                "id": a.get("id"),
                "name": a.get("name", "Unnamed"),
                "role": a.get("role", ""),
                "goal": a.get("goal", ""),
                "persona": a.get("persona", ""),
                "tools": a.get("tools", []),
                "model": a.get("model", ""),
                "status": a.get("status", "Idle"),
                "team_id": a.get("team_id"),
                "is_manager": a.get("is_manager", False),
                "expertise": a.get("expertise", []),
                "personality": a.get("personality", {}),
                "brand_context": a.get("brand_context", {}),
                "learnings": a.get("learnings", []),
                "depends_on": a.get("depends_on", []),
                "template_id": a.get("template_id", ""),
                "output_format": a.get("output_format", ""),
                "quality_criteria": a.get("quality_criteria", ""),
                "review_iterations": a.get("review_iterations", 3),
                "max_iter": a.get("max_iter", 20),
                "max_retry_limit": a.get("max_retry_limit", 3),
                "allow_delegation": a.get("allow_delegation", False),
            }
            for a in agents
        ]

    async def _send(self, trigger: str = "update"):
        self.state["credits"] = self._fetch_credits()
        payload = {
            "type": "platform_state",
            "payload": self.state,
        }
        await cl.Message(content=json.dumps(payload, ensure_ascii=False)).send()

    async def init(self, registry: AgentRegistry, team_id: str | None = None):
        self.state["agents"] = self._agents_for_ui(registry.list_agents())
        self.state["tasks"] = self.task_store.get_tasks_by_team(team_id) if team_id else self.task_store.list_tasks()
        await self._send()

    async def update_agents(self, registry: AgentRegistry):
        self.state["agents"] = self._agents_for_ui(registry.list_agents())
        await self._send()

    async def update_tasks(self, task_store: TaskStore, team_id: str | None = None):
        self.state["tasks"] = task_store.get_tasks_by_team(team_id) if team_id else task_store.list_tasks()
        await self._send()

    async def set_status(self, status: str):
        self.state["system_status"] = status
        await self._send()

    async def notify(self, message: str):
        notifications = self.state["notifications"]
        notifications.append(message)
        if len(notifications) > 5:
            notifications.pop(0)
        await self._send()

    async def reply(self, message: str):
        """Send a chat reply message to the frontend (separate from notifications)"""
        self.state["notifications"] = []
        await self._send()
        payload = chat_reply(ChatReplyText(message=message))
        await cl.Message(content=json.dumps(payload, ensure_ascii=False)).send()
        self.persist_message({"role": "assistant", "content": message, "messageType": "text"})

    async def reply_plan_validation_error(self, errors: list[str]):
        """Send a plan validation error — frontend resets plan card to pending"""
        self.state["notifications"] = []
        await self._send()
        message = "\n".join(errors)
        payload = chat_reply(ChatReplyPlanValidationError(message=message, errors=errors))
        await cl.Message(content=json.dumps(payload, ensure_ascii=False)).send()
        self.persist_message({"role": "assistant", "content": message, "messageType": "plan_validation_error", "validationErrors": errors})

    async def reply_thinking(self, chunk: str, thinking_id: str = "thinking"):
        """Send a streaming thinking chunk to the frontend."""
        print(f"[DEBUG-THINKING] reply_thinking chunk='{chunk[:20]}', id={thinking_id}", flush=True)
        payload = {
            "type": "chat_reply",
            "payload": {
                "messageType": "thinking",
                "chunk": chunk,
                "thinkingId": thinking_id,
            }
        }
        await cl.Message(content=json.dumps(payload, ensure_ascii=False)).send()

    async def reply_thinking_done(self, thinking_id: str = "thinking"):
        """Signal that thinking stream is complete."""
        print(f"[DEBUG-THINKING] reply_thinking_done id={thinking_id}", flush=True)
        payload = {
            "type": "chat_reply",
            "payload": {
                "messageType": "thinking_done",
                "thinkingId": thinking_id,
            }
        }
        await cl.Message(content=json.dumps(payload, ensure_ascii=False)).send()

    async def reply_plan(self, agents: list[dict], task_description: str, plan_type: str = "new", image_model: str = "", video_model: str = "", search_model: str = "", tts_model: str = "", stt_model: str = "", vision_model: str = "", has_image_tool: bool = False, has_video_tool: bool = False, has_search_tool: bool = False, has_tts_tool: bool = False, has_stt_tool: bool = False, has_vision_tool: bool = False, has_vision_input: bool = False, manager_model: str = "", agent_specs: list = None, model_assignment: dict = None, current_input: str = "", team_name: str = "", team_description: str = ""):
        """Send a plan card as a chat message"""
        self.state["notifications"] = []
        await self._send()
        plan_agents = [
            PlanAgentItem(
                name=a.get("name", "Unnamed"),
                role=a.get("role", ""),
                goal=a.get("goal", ""),
                persona=a.get("persona", a.get("backstory", "")),
                personality=a.get("personality", {}),
                expertise=a.get("expertise", []),
                brand_context=a.get("brand_context", {}),
                tools=a.get("tools", []),
                depends_on=a.get("depends_on", []),
                is_existing=a.get("is_existing", False),
                model=a.get("model", ""),
                original_tools=a.get("original_tools", []),
                original_goal=a.get("original_goal", ""),
                original_persona=a.get("original_persona", ""),
                task_description=a.get("task_description", ""),
            )
            for a in agents
        ]

        # Estimate cost based on models used
        estimated_cost = self._estimate_plan_cost(agents, manager_model, image_model, video_model, search_model, tts_model, stt_model, vision_model)

        payload = chat_reply(ChatReplyPlan(
            planAgents=plan_agents,
            planTaskDescription=task_description,
            planType=plan_type,
            teamName=team_name,
            teamDescription=team_description,
            imageModel=image_model,
            videoModel=video_model,
            searchModel=search_model,
            ttsModel=tts_model,
            sttModel=stt_model,
            visionModel=vision_model,
            hasImageTool=has_image_tool,
            hasVideoTool=has_video_tool,
            hasSearchTool=has_search_tool,
            hasTtsTool=has_tts_tool,
            hasSttTool=has_stt_tool,
            hasVisionTool=has_vision_tool,
            hasVisionInput=has_vision_input,
            managerModel=manager_model,
            estimatedCost=estimated_cost,
        ))
        await cl.Message(content=json.dumps(payload, ensure_ascii=False)).send()
        self.persist_message({"role": "assistant", "messageType": "plan", "planAgents": payload["payload"]["planAgents"], "planTaskDescription": task_description, "planType": plan_type, "planStatus": "pending", "imageModel": image_model, "videoModel": video_model, "searchModel": search_model, "ttsModel": tts_model, "sttModel": stt_model, "visionModel": vision_model, "hasImageTool": has_image_tool, "hasVideoTool": has_video_tool, "hasSearchTool": has_search_tool, "hasTtsTool": has_tts_tool, "hasSttTool": has_stt_tool, "hasVisionTool": has_vision_tool, "hasVisionInput": has_vision_input, "managerModel": manager_model, "estimatedCost": estimated_cost, "agentSpecs": agent_specs or [], "modelAssignment": model_assignment or {}, "currentInput": current_input})

    def _estimate_plan_cost(self, agents: list[dict], manager_model: str, image_model: str, video_model: str, search_model: str, tts_model: str, stt_model: str, vision_model: str) -> str:
        """Estimate cost based on model pricing. Returns a human-readable string."""
        all_models = set()
        for a in agents:
            m = a.get("model", "")
            if m:
                all_models.add(m)
        if manager_model:
            all_models.add(manager_model)
        for m in [image_model, video_model, search_model, tts_model, stt_model, vision_model]:
            if m:
                all_models.add(m)

        if not all_models:
            return ""

        free_count = 0
        paid_count = 0
        for m in all_models:
            if ":free" in m or m == "openrouter/free":
                free_count += 1
            else:
                paid_count += 1

        if paid_count == 0:
            return "✅ ฟรีทั้งหมด (0 บาท)"
        elif free_count > 0:
            return f"⚠️ ผสม: {free_count} ฟรี, {paid_count} เสียเงิน — ตรวจสอบโมเดลก่อนยืนยัน"
        else:
            return f"💰 ใช้โมเดลเสียเงิน {paid_count} ตัว — คาดว่าใช้ ~$0.01-0.05 ต่อ task"

    async def reply_progress(self, percent: int, label: str, progress_id: str = ""):
        """Send a progress card as a chat message"""
        payload = chat_reply(ChatReplyProgress(
            progressId=progress_id,
            progressPercent=percent,
            progressLabel=label,
        ))
        await cl.Message(content=json.dumps(payload, ensure_ascii=False)).send()
        # Progress: update or insert in session (don't duplicate)
        if self.current_session_id:
            session = self.chat_store.get_session(self.current_session_id)
            if session:
                msgs = session["messages"]
                existing = None
                for m in msgs:
                    if m.get("messageType") == "progress" and m.get("progressId") == progress_id:
                        existing = m
                        break
                prog_msg = {"role": "assistant", "messageType": "progress", "progressId": progress_id, "progressPercent": percent, "progressLabel": label}
                if existing:
                    existing.update(prog_msg)
                else:
                    msgs.append(prog_msg)
                session["updated_at"] = datetime.now().isoformat()
                self.chat_store._save()

    async def reply_agent_progress(self, task_id: str, agents_progress: list[dict]):
        """Send per-agent progress card — updates in-place by task_id"""
        overall = sum(a.get("progress", 0) for a in agents_progress) // max(len(agents_progress), 1)
        entries = [
            AgentProgressEntry(
                name=a.get("name", "Agent"),
                role=a.get("role", ""),
                status=a.get("status", "pending"),
                progress=a.get("progress", 0),
                output=a.get("output", ""),
                current_task=a.get("current_task", ""),
                current_tool=a.get("current_tool", ""),
                tool_description=a.get("tool_description", ""),
                model=a.get("model", ""),
                review_round=a.get("review_round", 0),
                review_summary=a.get("review_summary", ""),
                review_feedback=a.get("review_feedback", ""),
                review_history=a.get("review_history", []),
            )
            for a in agents_progress
        ]
        payload = chat_reply(ChatReplyAgentProgress(
            taskId=task_id,
            overallProgress=overall,
            agents=entries,
        ))
        await cl.Message(content=json.dumps(payload, ensure_ascii=False)).send()
        # Update or insert in session
        if self.current_session_id:
            session = self.chat_store.get_session(self.current_session_id)
            if session:
                msgs = session["messages"]
                existing = None
                for m in msgs:
                    if m.get("messageType") == "agent_progress" and m.get("taskId") == task_id:
                        existing = m
                        break
                prog_msg = {"role": "assistant", "messageType": "agent_progress", "taskId": task_id, "overallProgress": overall, "agents": agents_progress}
                if existing:
                    existing.update(prog_msg)
                else:
                    msgs.append(prog_msg)
                session["updated_at"] = datetime.now().isoformat()
                self.chat_store._save()

    async def reply_result(self, summary: str, agents: list[dict] | None = None, is_error: bool = False):
        """Send a result card as a chat message, with per-agent collapsible outputs"""
        result_agents = [
            ResultAgentItem(
                name=a.get("name", ""),
                role=a.get("role", ""),
                output=a.get("output", ""),
            )
            for a in (agents or [])
        ]
        payload = chat_reply(ChatReplyResult(
            resultSummary=summary,
            resultError=is_error,
            resultAgents=result_agents,
        ))
        print(f"[DEBUG-synth] reply_result: sending result message, agents={len(result_agents)}, summary={summary[:60]}", flush=True)
        await cl.Message(content=json.dumps(payload, ensure_ascii=False)).send()
        print(f"[DEBUG-synth] reply_result: message sent successfully", flush=True)
        self.persist_message({"role": "assistant", "messageType": "result", "resultSummary": summary, "resultError": is_error, "resultAgents": [a.model_dump() for a in result_agents]})

    async def reply_image_approval(self, prompt: str, approval_id: str, agent_name: str = "", media_type: str = "image", duration: int = 0, model: str = "", approval_status: str = "pending", image_error: str = ""):
        """Send a media approval card — user must approve before generation"""
        payload = chat_reply(ChatReplyImageApproval(
            imagePrompt=prompt,
            approvalId=approval_id,
            agentName=agent_name,
            mediaType=media_type,
            duration=duration,
            model=model,
            approvalStatus=approval_status,
            imageError=image_error,
        ))
        await cl.Message(content=json.dumps(payload, ensure_ascii=False)).send()
        self.persist_message({"role": "assistant", "messageType": "image_approval", "imagePrompt": prompt, "approvalId": approval_id, "agentName": agent_name, "mediaType": media_type, "duration": duration, "model": model, "approvalStatus": approval_status, "imageError": image_error})

    async def reply_agent_review(self, review_id: str, task_id: str, agent_name: str, agent_role: str, output: str, review_status: str = "pending"):
        """Send a per-agent review card — user must approve before dependents can start"""
        payload = chat_reply(ChatReplyAgentReview(
            reviewId=review_id,
            taskId=task_id,
            agentName=agent_name,
            agentRole=agent_role,
            output=output[:8000],
            reviewStatus=review_status,
        ))
        await cl.Message(content=json.dumps(payload, ensure_ascii=False)).send()
        self.persist_message({"role": "assistant", "messageType": "agent_review", "reviewId": review_id, "taskId": task_id, "agentName": agent_name, "agentRole": agent_role, "output": output[:8000], "reviewStatus": review_status})

    async def update_agent_review_status(self, review_id: str, status: str):
        """Update the reviewStatus of an agent_review message in the current session"""
        if not self.current_session_id:
            return
        session = self.chat_store.get_session(self.current_session_id)
        if not session:
            return
        for msg in session.get("messages", []):
            if msg.get("messageType") == "agent_review" and msg.get("reviewId") == review_id:
                msg["reviewStatus"] = status
                self.chat_store._save()
                # Send socket message so frontend updates consistently
                payload = chat_reply(ChatReplyAgentReview(
                    reviewId=review_id,
                    taskId=msg.get("taskId", ""),
                    agentName=msg.get("agentName", ""),
                    agentRole=msg.get("agentRole", ""),
                    output=msg.get("output", ""),
                    reviewStatus=status,
                ))
                await cl.Message(content=json.dumps(payload, ensure_ascii=False)).send()
                break

    async def reply_image_result(self, image_url: str, prompt: str, approval_id: str, task_id: str | None = None, media_type: str = "image", agent_name: str = ""):
        """Send a generated media result (image or video)"""
        payload = chat_reply(ChatReplyImageResult(
            imageUrl=image_url,
            imagePrompt=prompt,
            approvalId=approval_id,
            taskId=task_id or "",
            mediaType=media_type,
            agentName=agent_name,
        ))
        await cl.Message(content=json.dumps(payload, ensure_ascii=False)).send()
        self.persist_message({"role": "assistant", "messageType": "image_result", "imageUrl": image_url, "imagePrompt": prompt, "approvalId": approval_id, "taskId": task_id, "mediaType": media_type, "agentName": agent_name})

    async def reply_audio_result(self, audio_url: str, prompt: str, voice: str = "", agent_name: str = "", model: str = "", task_id: str = ""):
        """Send a TTS audio result to the frontend."""
        payload = chat_reply(ChatReplyAudioResult(
            audioUrl=audio_url,
            audioPrompt=prompt,
            voice=voice,
            agentName=agent_name,
            model=model,
            taskId=task_id,
        ))
        await cl.Message(content=json.dumps(payload, ensure_ascii=False)).send()
        self.persist_message({"role": "assistant", "messageType": "audio_result", "audioUrl": audio_url, "audioPrompt": prompt, "voice": voice, "agentName": agent_name, "model": model})

    async def reply_transcription_result(self, transcription_text: str, audio_url: str = "", agent_name: str = "", model: str = "", task_id: str = ""):
        """Send a transcription (STT) result to the frontend."""
        payload = chat_reply(ChatReplyTranscriptionResult(
            transcriptionText=transcription_text,
            audioUrl=audio_url,
            agentName=agent_name,
            model=model,
            taskId=task_id,
        ))
        await cl.Message(content=json.dumps(payload, ensure_ascii=False)).send()
        self.persist_message({"role": "assistant", "messageType": "transcription_result", "transcriptionText": transcription_text, "audioUrl": audio_url, "agentName": agent_name, "model": model})

    async def reply_video_result(self, video_url: str, prompt: str, agent_name: str = "", model: str = "", task_id: str = ""):
        """Send a video generation result to the frontend."""
        payload = chat_reply(ChatReplyVideoResult(
            videoUrl=video_url,
            videoPrompt=prompt,
            agentName=agent_name,
            model=model,
            taskId=task_id,
        ))
        await cl.Message(content=json.dumps(payload, ensure_ascii=False)).send()
        self.persist_message({"role": "assistant", "messageType": "video_result", "videoUrl": video_url, "videoPrompt": prompt, "agentName": agent_name, "model": model})

    async def reply_file_result(self, file_url: str, file_name: str, file_mime: str = "", agent_name: str = "", task_id: str = ""):
        """Send a generic file result to the frontend."""
        payload = chat_reply(ChatReplyFileResult(
            fileUrl=file_url,
            fileName=file_name,
            fileMime=file_mime,
            agentName=agent_name,
            taskId=task_id,
        ))
        await cl.Message(content=json.dumps(payload, ensure_ascii=False)).send()
        self.persist_message({"role": "assistant", "messageType": "file_result", "fileUrl": file_url, "fileName": file_name, "fileMime": file_mime, "agentName": agent_name})

    async def reply_model_catalog(self, recommended: dict, search_results: list, selected_model: str = "", catalog_type: str = "text"):
        """Send model catalog to frontend for user selection"""
        # Resolve actual model name if adaptive (empty)
        resolved_model = selected_model
        if not selected_model:
            resolved_model = self._get_resolved_model_name()
        # Convert to ModelCatalogItem lists
        rec_items = {}
        for cat, models in recommended.items():
            rec_items[cat] = [
                ModelCatalogItem(
                    id=m.get("id", ""),
                    name=m.get("name", ""),
                    context_length=m.get("context_length", "?"),
                    prompt_price=m.get("prompt_price", "?"),
                    completion_price=m.get("completion_price", "?"),
                    categories=m.get("categories", []),
                    is_free=m.get("is_free", False),
                )
                for m in models
            ]
        search_items = [
            ModelCatalogItem(
                id=m.get("id", ""),
                name=m.get("name", ""),
                context_length=m.get("context_length", "?"),
                prompt_price=m.get("prompt_price", "?"),
                completion_price=m.get("completion_price", "?"),
                categories=m.get("categories", []),
                is_free=m.get("is_free", False),
            )
            for m in search_results
        ]
        payload = chat_reply(ChatReplyModelCatalog(
            recommended=rec_items,
            searchResults=search_items,
            selectedModel=selected_model,
            catalogType=catalog_type,
        ))
        # Add resolved model name for adaptive mode display
        payload["payload"]["resolvedModel"] = resolved_model
        await cl.Message(content=json.dumps(payload, ensure_ascii=False)).send()

    async def reply_tuning_proposal(self, proposals: list[dict]):
        """Send a tuning proposal card to the frontend for user confirmation."""
        payload = {
            "type": "chat_reply",
            "payload": {
                "messageType": "tuning_proposal",
                "proposals": proposals,
            }
        }
        await cl.Message(content=json.dumps(payload, ensure_ascii=False)).send()
        self.persist_message({"role": "assistant", "messageType": "tuning_proposal", "proposals": proposals})

    def log_history(self, task_id: str, task_title: str, actor: str, action: str, target: str = ""):
        """Log a detailed audit entry and broadcast to frontend in real-time."""
        self.history_store.add_entry(task_id, task_title, actor, action, target)
        self._broadcast_history()

    def _broadcast_history(self):
        """Schedule a reply_history() call on the event loop (works from async or thread context)."""
        try:
            loop = asyncio.get_running_loop()
            asyncio.ensure_future(self.reply_history())
        except RuntimeError:
            if self._main_loop and self._main_loop.is_running():
                self._main_loop.call_soon_threadsafe(
                    lambda: asyncio.ensure_future(self.reply_history())
                )

    async def reply_history(self, limit: int = 20):
        """Send task history logs to frontend."""
        payload = {
            "type": "chat_reply",
            "payload": {
                "messageType": "history_data",
                "historyLogs": self.history_store.list_history(limit),
            },
        }
        await cl.Message(content=json.dumps(payload, ensure_ascii=False)).send()

    async def reply_chat_history(self, session_id: str):
        """Send full chat history for a session, including canvas state"""
        session = self.chat_store.get_session(session_id)
        messages = session["messages"] if session else []
        canvas_state = self.chat_store.get_canvas_state(session_id) if session else None
        settings = self.chat_store.get_settings(session_id) if session else {}
        migrated = [self._migrate_msg_urls(m) for m in messages]
        payload = {
            "type": "chat_reply",
            "payload": {
                "messageType": "chat_history",
                "sessionId": session_id,
                "messages": migrated,
                "canvasState": canvas_state,
                "selectedModel": settings.get("selected_model", ""),
            },
        }
        await cl.Message(content=json.dumps(payload, ensure_ascii=False)).send()

    @staticmethod
    def _migrate_msg_urls(msg: dict) -> dict:
        """Convert absolute URLs in persisted messages to relative paths."""
        import re
        m = dict(msg)
        url_fields = ("attachmentUrl", "imageUrl", "videoUrl", "audioUrl", "fileUrl")
        for field in url_fields:
            val = m.get(field)
            if val and isinstance(val, str):
                m[field] = re.sub(r'^https?://[^/]+(/public/.+)', r'\1', val)
        atts = m.get("attachments")
        if atts and isinstance(atts, list):
            m["attachments"] = [
                {**a, "url": re.sub(r'^https?://[^/]+(/public/.+)', r'\1', a["url"])}
                if a.get("url") and isinstance(a["url"], str) else a
                for a in atts
            ]
        return m

    async def reply_chat_sessions(self, team_id: str | None = None):
        """Send list of chat sessions, optionally filtered by team"""
        if team_id is not None:
            sessions = self.chat_store.list_sessions(team_id=team_id, include_unassigned=True)
        else:
            sessions = self.chat_store.list_sessions()
        session_list = [
            {"id": s["id"], "title": s["title"], "updated_at": s.get("updated_at", "")}
            for s in sessions
        ]
        payload = {
            "type": "chat_reply",
            "payload": {
                "messageType": "chat_sessions",
                "sessions": session_list,
                "currentSessionId": self.current_session_id,
            },
        }
        await cl.Message(content=json.dumps(payload, ensure_ascii=False)).send()

    async def reply_notifications(self, team_id: str | None = None):
        """Send aggregated notifications across all sessions."""
        notifications = self.chat_store.get_all_notifications(team_id=team_id)
        payload = {
            "type": "chat_reply",
            "payload": {
                "messageType": "notifications",
                "notifications": notifications,
                "count": len(notifications),
            },
        }
        await cl.Message(content=json.dumps(payload, ensure_ascii=False)).send()

    def persist_message(self, message: dict):
        """Persist a message to the current chat session"""
        if self.current_session_id:
            self.chat_store.add_message(self.current_session_id, message)

    def update_persisted_message(self, message_type: str, updates: dict):
        """Update the last persisted message of a given type with new fields."""
        if not self.current_session_id:
            return
        session = self.chat_store.get_session(self.current_session_id)
        if not session:
            return
        msgs = session["messages"]
        for m in reversed(msgs):
            if m.get("messageType") == message_type:
                m.update(updates)
                session["updated_at"] = datetime.now().isoformat()
                self.chat_store._save()
                return

    def update_plan_status(self, status: str):
        """Update the planStatus of the most recent plan message in the current session"""
        if not self.current_session_id:
            return
        session = self.chat_store.get_session(self.current_session_id)
        if not session:
            return
        msgs = session["messages"]
        for i in range(len(msgs) - 1, -1, -1):
            if msgs[i].get("messageType") == "plan":
                msgs[i]["planStatus"] = status
                self.chat_store._save()
                break

    def update_approval_status(self, approval_id: str, status: str):
        """Update the approvalStatus of an image_approval message in the current session"""
        if not self.current_session_id:
            return
        session = self.chat_store.get_session(self.current_session_id)
        if not session:
            return
        msgs = session["messages"]
        for i in range(len(msgs) - 1, -1, -1):
            if msgs[i].get("messageType") == "image_approval" and msgs[i].get("approvalId") == approval_id:
                msgs[i]["approvalStatus"] = status
                self.chat_store._save()
                break

    async def clear_plan(self):
        self.state["current_plan"] = None
        await self._send()

    async def set_plan(self, agent: dict, task_description: str, plan_type: str = "new"):
        self.state["current_plan"] = {
            "agents": [agent],
            "task_description": task_description,
            "plan_type": plan_type,
        }
        await self._send()

    async def set_multi_agent_plan(self, agents: list[dict], task_description: str, plan_type: str = "new"):
        self.state["current_plan"] = {
            "agents": agents,
            "task_description": task_description,
            "plan_type": plan_type,
        }
        await self._send()

    async def add_task(self, task_id: str, title: str, agent_name: str) -> dict:
        task = {
            "id": task_id,
            "title": title,
            "agent": agent_name,
            "status": "running",
            "progress": 0,
            "result": "",
            "created_at": datetime.now().isoformat(),
        }
        self.task_store.add_task(task)
        self.state["tasks"] = self.task_store.list_tasks()
        await self._send()
        return task

    async def update_task(self, task_id: str, **kwargs):
        self.task_store.update_task(task_id, **kwargs)
        self.state["tasks"] = self.task_store.list_tasks()
        await self._send()

    async def update_task_image(self, task_id: str, image_url: str, image_prompt: str, media_type: str = "image"):
        """Append a generated image to its originating task's image list."""
        task = self.task_store.get_task(task_id)
        images = task.get("images", []) if task else []
        images.append({"url": image_url, "prompt": image_prompt, "media_type": media_type})
        self.task_store.update_task(task_id, image_url=image_url, image_prompt=image_prompt, images=images)
        self.state["tasks"] = self.task_store.list_tasks()
        await self._send()

    async def delete_task(self, task_id: str):
        self.task_store.delete_task(task_id)
        self.state["tasks"] = self.task_store.list_tasks()
        await self._send()

    async def reply_team_list(self, team_registry: TeamRegistry):
        """Send list of all teams to the frontend."""
        teams = team_registry.list_teams()
        team_list = [
            {
                "id": t.get("id"),
                "name": t.get("name", ""),
                "description": t.get("description", ""),
                "manager_model": t.get("manager_model", "auto"),
                "agent_ids": t.get("agent_ids", []),
                "created_at": t.get("created_at", ""),
                "updated_at": t.get("updated_at", ""),
            }
            for t in teams
        ]
        payload = {
            "type": "chat_reply",
            "payload": {
                "messageType": "team_list",
                "teams": team_list,
            },
        }
        await cl.Message(content=json.dumps(payload, ensure_ascii=False)).send()



