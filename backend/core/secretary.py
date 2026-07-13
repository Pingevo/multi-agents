"""CentralSecretary — the heart of the system: assess + plan in 1 LLM call."""

import asyncio
import json
import os
import re
import traceback
from backend.llm.manager import LLMManager
from backend.llm.discovery import ModelDiscoveryService
from backend.agents.capability import CapabilityRegistry
from backend.agents.registry import AgentRegistry
from backend.utils import _sanitize_error, _debug
from backend.globals import STATE_IDLE, STATE_GATHERING_REQUIREMENTS

class CentralSecretary:
    """AI Assessor: ประเมินความต้องการ, ถาม requirement, วิเคราะห์และวางแผน multi-agent"""

    def __init__(self, llm_manager: LLMManager):
        self.llm_manager = llm_manager

    async def assess(self, user_input: str, conversation_history: list[dict] | None = None) -> dict:
        """ประเมินความต้องการ: CHAT (ตอบเลย) / INFO (ตอบเลย) / TASK_NEEDS_INFO (ถามเพิ่ม) / TASK_READY (วางแผน)"""
        history_text = ""
        if conversation_history:
            history_text = "\nConversation so far:\n"
            for msg in conversation_history:
                history_text += f"- {msg.get('role', 'user')}: {msg.get('content', '')[:100]}\n"

        prompt = (
            "You are an AI Assessor for an Agent Management Platform.\n"
            "Evaluate the user's message and decide what to do next.\n\n"
            "Respond with EXACTLY one of these JSON objects (no other text):\n"
            '- {"action": "chat", "message": "your reply"} — for greetings, small talk, general questions\n'
            '- {"action": "info", "message": "your reply"} — for questions about the system/agents/status\n'
            '- {"action": "ask", "questions": ["q1", "q2", ...]} — when the user wants work done but needs are unclear\n'
            '- {"action": "plan", "summary": "brief summary of understood requirements"} — when requirements are clear enough to plan\n\n'
            "Guidelines:\n"
            "- If the user is just chatting or asking who you are → chat\n"
            "- If the user is asking about available agents or system status → info\n"
            "- If the user wants something done but missing key details (scope, quantity, platform, timeline) → ask\n"
            "- If the user has provided enough detail to design a plan → plan\n"
            "- Use the same language as the user.\n\n"
            f"{history_text}"
            f"User message: {user_input}\n"
            "Response JSON:"
        )
        response = (await self.llm_manager.call_async(prompt)).strip()
        return self._parse_assessment(response)

    def _parse_assessment(self, text: str) -> dict:
        """Parse LLM assessment response, with fallback"""
        try:
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                if "action" in result:
                    return result
        except (json.JSONDecodeError, AttributeError):
            pass
        return {"action": "chat", "message": "ขออภัย ไม่เข้าใจคำถาม ลองใหม่อีกครั้ง"}

    async def assess_and_plan(
        self,
        user_input: str,
        conversation_history: list[dict] | None = None,
        model_table: str | None = None,
        valid_model_ids: set[str] | None = None,
        media_catalog: str | None = None,
        stream_callback=None,
        last_task_context: dict | None = None,
        registry_agents: list[dict] | None = None,
        team_agents: list[dict] | None = None,
        team_name: str | None = None,
    ) -> dict:
        """Unified call: assess + analyze + model assignment in one LLM response.

        Returns same format as assess() for chat/info/ask paths.
        For plan path, includes 'agents' and 'model_assignment' keys.
        For feedback path, includes 'feedback_text' and 'target_agent' keys.
        Falls back to assess() on parse error.
        """
        history_text = ""
        if conversation_history:
            history_text = "\nConversation so far:\n"
            for msg in conversation_history:
                history_text += f"- {msg.get('role', 'user')}: {msg.get('content', '')[:100]}\n"

        cap_registry = CapabilityRegistry()
        catalog = cap_registry.list_catalog()
        caps_text = "\n".join(
            f"- {c['name']}: {c['description']}" for c in catalog
        ) if catalog else "none"

        models_text = model_table or "none"

        # Build last task context (if any)
        last_task_text = ""
        if last_task_context:
            last_task_text = "\nLast completed task:\n"
            last_task_text += f"- User request: {last_task_context.get('user_input', '')[:200]}\n"
            last_task_text += f"- Result summary: {last_task_context.get('result', '')[:500]}\n"
            agents_ctx = last_task_context.get('agents', [])
            for a in agents_ctx:
                name = a.get('name', 'Agent')
                role = a.get('role', '')
                persona = a.get('persona', a.get('backstory', ''))
                personality = a.get('personality', {})
                tone = personality.get('tone', '') if isinstance(personality, dict) else ''
                style = personality.get('communication_style', '') if isinstance(personality, dict) else ''
                last_task_text += f"- Agent: {name} ({role}) | tone={tone} | style={style} | persona={persona[:100]}\n"

        # Build registry agents text — always available for tuning
        registry_text = ""
        if registry_agents:
            registry_text = "\nAvailable agents in registry:\n"
            for a in registry_agents:
                name = a.get('name', 'Agent')
                aid = a.get('id', '')
                role = a.get('role', '')
                personality = a.get('personality', {})
                tone = personality.get('tone', '') if isinstance(personality, dict) else ''
                style = personality.get('communication_style', '') if isinstance(personality, dict) else ''
                registry_text += f"- {name} (id={aid}) | role={role} | tone={tone} | style={style}\n"

        # Build team context text
        team_text = ""
        if team_agents:
            team_label = f"Team '{team_name}'" if team_name else "Current team"
            team_text = f"\n{team_label} agents (use these for tasks when possible):\n"
            for a in team_agents:
                name = a.get('name', 'Agent')
                aid = a.get('id', '')
                role = a.get('role', '')
                model = a.get('model', 'auto')
                tools = a.get('tools', [])
                team_text += f"- {name} (id={aid}) | role={role} | model={model} | tools={tools}\n"

        prompt = (
            "You are the Central Secretary of an Agent Management Platform.\n"
            "Evaluate the user's message and respond with a single JSON object.\n\n"
            "First, decide what to do:\n"
            "- chat: greetings, small talk, general questions, self-introduction requests\n"
            "- info: questions about system/agents/status\n"
            "- ask: user wants work done but needs are unclear\n"
            "- plan: user wants specific work produced (content, images, videos, analysis, etc.)\n"
            "- tuning: user wants to adjust, refine, or change how an agent behaves — tone, style, personality, expertise, or any aspect.\n"
            "  This can happen at ANY time: after a task, before a task, or even with no task at all.\n"
            "  If the user mentions a specific agent, tune that one. If not, use context to determine which agent(s) to tune.\n\n"

            "IMPORTANT: Do NOT create a plan for greetings, self-introductions, or simple questions.\n"
            "Only create a plan when the user explicitly asks for work to be done.\n"
            "Use 'tuning' when the user wants to modify agent behavior — not when asking for new work.\n\n"

            "For chat/info/ask, respond with:\n"
            '  {"action": "chat", "message": "your reply"}\n'
            '  {"action": "info", "message": "your reply"}\n'
            '  {"action": "ask", "questions": ["q1", "q2", ...]}\n\n'

            "For tuning, respond with:\n"
            '  {"action": "tuning", "tuning_text": "what the user wants to change", "target_agent": "agent name or empty if unclear"}\n\n'

            "For plan, respond with a complete plan including agents AND model assignments:\n"
            "{\n"
            '  "action": "plan",\n'
            '  "summary": "brief summary",\n'
            '  "agents": [\n'
            "    {\n"
            '      "name": "Role #N (e.g. Creative Writer #1)",\n'
            '      "role": "Agent Role",\n'
            '      "goal": "Agent Goal",\n'
            '      "backstory": "Brief backstory",\n'
            '      "personality": {\n'
            '        "tone": "e.g. friendly, professional, casual",\n'
            '        "communication_style": "e.g. concise, detailed",\n'
            '        "language": "e.g. th, en, mixed"\n'
            '      },\n'
            '      "expertise": ["skill1", "skill2", "knowledge area"],\n'
            '      "brand_context": {\n'
            '        "brand_name": "",\n'
            '        "guidelines": "tone, style, rules",\n'
            '        "target_audience": ""\n'
            '      },\n'
            '      "tools": ["capability_name"],\n'
            '      "task_description": "What this agent should do",\n'
            '      "depends_on": [],\n'
            '      "model": "model_id from the list"\n'
            "    }\n"
            "  ],\n"
            '  "manager_model": "model_id from the list or openrouter/auto",\n'
            '  "image_model": "model_id from specialized catalog (REQUIRED if plan uses generate_image)",\n'
            '  "video_model": "model_id from specialized catalog (REQUIRED if plan uses generate_video)",\n'
            '  "search_model": "model_id from specialized catalog (REQUIRED if plan uses search_web)",\n'
            '  "tts_model": "model_id from specialized catalog (REQUIRED if plan uses text_to_speech)",\n'
            '  "stt_model": "model_id from specialized catalog (REQUIRED if plan uses transcribe_audio)",\n'
            '  "vision_model": "model_id from specialized catalog (REQUIRED if plan uses analyze_image)"\n'
            "}\n\n"

            "Design Rules for plan:\n"
            "- Create as many agents as needed (1, 2, 3, or more)\n"
            "- Each agent should have a clear, distinct responsibility\n"
            "- Assign capabilities based on the descriptions below\n"
            "- Capabilities of type 'tool' (search_web, generate_image, generate_video, text_to_speech, transcribe_audio, analyze_image) give external abilities\n"
            "- Capabilities of type 'model_trait' (reasoning, creative_writing, write_code, long_context) guide model selection\n"
            "- Assign the SMARTER/larger model to the manager (it coordinates)\n"
            "- Assign models suited to each worker's task based on capabilities\n"
            "- Only use model IDs from the available models list\n"
            "- You can use 'openrouter/auto' as a model ID — OpenRouter will automatically select the best model for each request\n"
            "- For image_model/video_model/search_model/tts_model/stt_model/vision_model: you MUST pick a specific model from the specialized catalog if the plan uses those tools — do NOT leave empty\n"
            "- If the plan does NOT need a particular specialized model, leave that field empty\n"
            "- Write all content in the SAME language as the user's request\n"
            "- Name agents as 'Role #N' (e.g. Creative Writer #1, Graphic Designer #2)\n"
            "- Give each agent a personality (tone, communication_style, language) that fits their role\n"
            "- List specific expertise/skills for each agent (e.g. SEO, color theory, Thai consumer behavior)\n"
            "- If the user mentions a brand, fill in brand_context for all agents on that brand\n"
            "- backstory should be brief — the personality, expertise, and brand_context fields carry the detail\n\n"

            "CRITICAL — task_description & depends_on rules:\n"
            "- By default, agents with NO depends_on run IN PARALLEL.\n"
            "- If agent B needs the output of agent A to do its job, set depends_on: [\"Agent A name\"]. Agent B will receive Agent A's output automatically before starting.\n"
            "- Agents WITHOUT depends_on CANNOT see other agents' output — their task_description MUST be self-contained.\n"
            "- Agents WITH depends_on CAN reference the upstream agent's output — e.g. 'Based on the caption from Creative Copywriter, generate an image that matches'.\n"
            "- Decide how many agents to create based on the user's request. You may create one agent per item or one agent that handles multiple items — use your judgment.\n"
            "- Each task_description MUST be specific — tell the agent EXACTLY what to produce, including how many items and what subject/theme.\n"
            "- BAD: 'Generate images based on descriptions provided by the manager' (vague, no depends_on)\n"
            "- GOOD (no depends_on): 'Write 1 engaging caption for a coffee shop post about latte art. Include hashtags and CTA.'\n"
            "- GOOD (with depends_on): 'Based on the caption from Creative Copywriter, create 1 image that visually matches the described scene. Call generate_image with a detailed English prompt.' + depends_on: [\"Creative Copywriter\"]\n"
            "- Include: what to create, how many, subject/theme, and which tool to call.\n\n"

            f"Available capabilities:\n{caps_text}\n\n"
            f"Available text models:\n{models_text}\n\n"
            f"Specialized AI models:\n{media_catalog or 'none'}\n\n"
            f"{history_text}"
            f"{last_task_text}"
            f"{registry_text}"
            f"{team_text}"
            f"User message: {user_input}\n\n"
            "Output ONLY the JSON object, no explanation:"
        )
        print(f"[DEBUG-PROMPT] media_catalog: {media_catalog or 'none'}", flush=True)

        if stream_callback:
            # Streaming mode: collect chunks while sending them to frontend
            import queue, threading
            chunk_queue: queue.Queue = queue.Queue()
            full_response = []

            def _stream_in_thread():
                try:
                    for chunk in self.llm_manager.call_streaming(prompt):
                        full_response.append(chunk)
                        chunk_queue.put(chunk)
                except Exception as e:
                    chunk_queue.put(e)
                chunk_queue.put(None)  # sentinel

            thread = threading.Thread(target=_stream_in_thread, daemon=True)
            thread.start()

            # Poll queue without blocking — no artificial timeout, HTTP client handles it
            while True:
                try:
                    item = chunk_queue.get_nowait()
                except queue.Empty:
                    await asyncio.sleep(0.05)
                    continue
                if item is None:
                    break
                if isinstance(item, Exception):
                    print(f"[assess_and_plan] Streaming error: {_sanitize_error(item)}")
                    break
                if item:
                    await stream_callback(item)

            thread.join(timeout=1)
            response = "".join(full_response).strip()
        else:
            response = (await self.llm_manager.call_async(prompt)).strip()

        print(f"[DEBUG-STREAM] Response length: {len(response)}, full response: {response[:3000]}", flush=True)
        if not response:
            selected = self.llm_manager._selected_model or self.llm_manager._default_model or "auto"
            return {
                "action": "chat",
                "message": f"❌ โมเดล '{selected}' ส่งคำตอบกลับมาว่างเปล่า อาจไม่รองรับคำสั่งที่ซับซ้อน ลองเปลี่ยนโมเดลแล้วส่งใหม่อีกครั้ง"
            }
        if os.getenv("DEBUG_MODE", "false").lower() == "true":
            print(f"[DEBUG-PLAN-RAW] LLM response (first 800 chars): {response[:800]}", flush=True)
        return self._parse_unified_response(response, valid_model_ids)

    def _parse_unified_response(
        self, text: str, valid_model_ids: set[str] | None = None
    ) -> dict:
        """Parse unified assess_and_plan response."""
        try:
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                if "action" not in result:
                    selected = self.llm_manager._selected_model or self.llm_manager._default_model or "auto"
                    return {
                        "action": "chat",
                        "message": (
                            f"⚠️ โมเดล '{selected}' ส่งคำตอบกลับมาไม่ถูกต้อง (ไม่มี JSON action) "
                            f"ลองเปลี่ยนโมเดลแล้วส่งใหม่อีกครั้ง"
                        )
                    }

                if result["action"] == "plan":
                    agents = []
                    for item in result.get("agents", []):
                        if isinstance(item, dict) and "name" in item and "role" in item:
                            depends_on = item.get("depends_on", [])
                            if not isinstance(depends_on, list):
                                depends_on = []
                            agents.append({
                                "name": item.get("name", "").strip(),
                                "role": item.get("role", "").strip(),
                                "goal": item.get("goal", "").strip(),
                                "backstory": item.get("backstory", "").strip(),
                                "personality": item.get("personality", {}) if isinstance(item.get("personality"), dict) else {},
                                "expertise": item.get("expertise", []) if isinstance(item.get("expertise"), list) else [],
                                "brand_context": item.get("brand_context", {}) if isinstance(item.get("brand_context"), dict) else {},
                                "tools": item.get("tools", []) if isinstance(item.get("tools"), list) else [],
                                "task_description": item.get("task_description", "").strip(),
                                "depends_on": [d.strip() for d in depends_on if isinstance(d, str) and d.strip()],
                                "model": item.get("model", ""),
                            })
                    if not agents:
                        return {"action": "chat", "message": "ไม่สามารถวางแผนได้ กรุณาลองใหม่"}

                    manager_model = result.get("manager_model", "")
                    model_assignment = {"manager": manager_model, "workers": {}}
                    for a in agents:
                        model_assignment["workers"][a["name"]] = a.get("model", "")

                    if valid_model_ids:
                        valid_list = sorted(valid_model_ids)
                        if model_assignment["manager"] not in valid_model_ids:
                            model_assignment["manager"] = valid_list[0] if valid_list else ""
                        for i, a in enumerate(agents):
                            mid = model_assignment["workers"].get(a["name"], "")
                            if mid not in valid_model_ids:
                                replacement = valid_list[0] if valid_list else ""
                                model_assignment["workers"][a["name"]] = replacement
                                agents[i]["model"] = replacement

                    return {
                        "action": "plan",
                        "summary": result.get("summary", ""),
                        "agents": agents,
                        "model_assignment": model_assignment,
                        "image_model": result.get("image_model", ""),
                        "video_model": result.get("video_model", ""),
                        "search_model": result.get("search_model", ""),
                    }

                return result
        except (json.JSONDecodeError, AttributeError) as e:
            print(f"[DEBUG-PARSE-UNIFIED] Failed: {e}", flush=True)
            print(f"[DEBUG-PARSE-UNIFIED] Response (first 500 chars): {text[:500]}", flush=True)
        selected = self.llm_manager._selected_model or self.llm_manager._default_model or "auto"
        return {
            "action": "chat",
            "message": (
                f"⚠️ โมเดล '{selected}' ไม่สามารถสร้างแผนงานได้ (คำตอบไม่ใช่ JSON) "
                f"ลองเปลี่ยนโมเดลแล้วส่งใหม่อีกครั้ง"
            )
        }

    async def analyze_feedback(
        self,
        feedback_text: str,
        agent_specs: list[dict],
        task_result: str = "",
    ) -> dict:
        """Analyze user feedback/tuning request and propose persona changes for agents.

        Works with agents from last task OR from registry — tuning can happen anytime.

        Returns: {
            "tuning_proposals": [
                {
                    "agent_name": "...",
                    "agent_id": "...",
                    "changes": [
                        {"field": "personality.tone", "old_value": "...", "new_value": "...", "reason": "..."},
                        ...
                    ]
                },
                ...
            ]
        }
        """
        agents_info = []
        for spec in agent_specs:
            personality = spec.get("personality", {})
            agents_info.append({
                "name": spec.get("name", "Agent"),
                "id": spec.get("registry_id", spec.get("id", "")),
                "role": spec.get("role", ""),
                "persona": spec.get("backstory", spec.get("persona", ""))[:200],
                "personality": personality,
                "expertise": spec.get("expertise", []),
                "brand_context": spec.get("brand_context", {}),
            })

        prompt = (
            "You are the Central Secretary analyzing a user request to tune/adjust agents.\n"
            "Based on the user's request, propose specific tuning changes to agent personas.\n\n"
            f"User request: {feedback_text}\n\n"
        )
        if task_result:
            prompt += f"Last task result (for context):\n{task_result[:1000]}\n\n"
        prompt += (
            f"Agents available for tuning:\n{json.dumps(agents_info, ensure_ascii=False, indent=2)}\n\n"
            "Analyze the request and decide which agent(s) need persona adjustments.\n"
            "For each agent, specify which fields to change and why.\n\n"
            "Tunable fields:\n"
            "- personality.tone (e.g. professional, casual, friendly, formal)\n"
            "- personality.communication_style (e.g. concise, detailed, conversational)\n"
            "- personality.language (e.g. th, en, mixed)\n"
            "- persona/backstory (free text describing the agent's character)\n"
            "- expertise (list of skills/knowledge areas)\n"
            "- brand_context.guidelines (tone/style rules)\n\n"
            "Respond with ONLY this JSON (no other text):\n"
            "{\n"
            '  "tuning_proposals": [\n'
            "    {\n"
            '      "agent_name": "Agent Name",\n'
            '      "agent_id": "agent_id",\n'
            '      "changes": [\n'
            '        {"field": "personality.tone", "old_value": "current value", "new_value": "new value", "reason": "why this change"}\n'
            "      ]\n"
            "    }\n"
            "  ]\n"
            "}\n\n"
            "Rules:\n"
            "- Only include agents that need changes\n"
            "- Be specific with old_value and new_value\n"
            "- Use dot notation for nested fields (e.g. personality.tone)\n"
            "- Provide clear reasons in the same language as the feedback\n"
            "- If no tuning is needed, return empty tuning_proposals array\n"
        )

        response = (await self.llm_manager.call_async(prompt)).strip()
        try:
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return result
        except (json.JSONDecodeError, AttributeError):
            pass
        return {"tuning_proposals": []}

    async def chat_response(self, user_input: str) -> str:
        """ตอบกลับทักทาย/คำถามทั่วไป"""
        llm = self.llm_manager.get_llm()
        prompt = (
            "You are the assistant of an Agent Management Platform.\n"
            "Respond to the user's message. Be concise and friendly.\n\n"
            "Respond in the same language as the user's message.\n\n"
            "Do not mention agents or the system unless asked.\n\n"
            f"User message: {user_input}\n\n"
            "Answer:"
        )
        return (await self.llm_manager.call_async(prompt)).strip()

    async def chat_response_with_image(self, user_input: str, image_data_url: str) -> str:
        """ตอบกลับพร้อมวิเคราะห์รูปภาพ (vision/multimodal)"""
        prompt = (
            "You are the assistant of an Agent Management Platform.\n"
            "The user has attached an image. Analyze and describe what you see in the image.\n"
            "Respond in the same language as the user's message.\n"
            "Be concise and friendly.\n\n"
            f"User message: {user_input}\n\n"
            "Answer:"
        )
        return (await self.llm_manager.call_with_image_async(prompt, image_data_url)).strip()

    async def chat_response_multimodal(
        self, user_input: str, content_blocks: list[dict], plugins: list = None
    ) -> str:
        """ตอบกลับพร้อมวิเคราะห์ไฟล์ multimodal (image, PDF, audio, video)"""
        prompt = (
            "You are the assistant of an Agent Management Platform.\n"
            "The user has attached a file. Analyze and respond based on the attached content.\n"
            "Respond in the same language as the user's message.\n"
            "Be concise and friendly.\n\n"
            f"User message: {user_input}\n\n"
            "Answer:"
        )
        return (await self.llm_manager.call_with_multimodal_async(prompt, content_blocks, plugins)).strip()

    async def assess_and_plan_multimodal(
        self,
        user_input: str,
        content_blocks: list[dict],
        plugins: list = None,
        conversation_history: list[dict] | None = None,
        model_table: str | None = None,
        valid_model_ids: set[str] | None = None,
        media_catalog: str | None = None,
        stream_callback=None,
    ) -> dict:
        """assess_and_plan with multimodal content blocks (image, PDF, audio, video)."""
        history_text = ""
        if conversation_history:
            history_text = "\nConversation so far:\n"
            for msg in conversation_history:
                history_text += f"- {msg.get('role', 'user')}: {msg.get('content', '')[:100]}\n"

        cap_registry = CapabilityRegistry()
        catalog = cap_registry.list_catalog()
        caps_text = "\n".join(
            f"- {c['name']}: {c['description']}" for c in catalog
        ) if catalog else "none"

        models_text = model_table or "none"

        prompt = (
            "You are the Central Secretary of an Agent Management Platform.\n"
            "Evaluate the user's message and respond with a single JSON object.\n\n"
            "First, decide what to do:\n"
            "- chat: greetings, small talk, general questions, self-introduction requests\n"
            "- info: questions about system/agents/status\n"
            "- ask: user wants work done but needs are unclear\n"
            "- plan: user wants specific work produced (content, images, videos, analysis, etc.)\n\n"
            "The user has attached a file. Analyze the attached content and use it in your assessment.\n\n"
            "For chat/info/ask, respond with:\n"
            '  {"action": "chat", "message": "your reply"}\n'
            '  {"action": "info", "message": "your reply"}\n'
            '  {"action": "ask", "questions": ["q1", "q2", ...]}\n\n'
            "For plan, respond with a complete plan including agents AND model assignments:\n"
            "{\n"
            '  "action": "plan",\n'
            '  "summary": "brief summary",\n'
            '  "agents": [\n'
            "    {\n"
            '      "name": "Role #N (e.g. Creative Writer #1)",\n'
            '      "role": "Agent Role",\n'
            '      "goal": "Agent Goal",\n'
            '      "backstory": "Brief backstory",\n'
            '      "personality": {\n'
            '        "tone": "e.g. friendly, professional, casual",\n'
            '        "communication_style": "e.g. concise, detailed",\n'
            '        "language": "e.g. th, en, mixed"\n'
            '      },\n'
            '      "expertise": ["skill1", "skill2", "knowledge area"],\n'
            '      "brand_context": {\n'
            '        "brand_name": "",\n'
            '        "guidelines": "tone, style, rules",\n'
            '        "target_audience": ""\n'
            '      },\n'
            '      "tools": ["capability_name"],\n'
            '      "task_description": "What this agent should do",\n'
            '      "depends_on": [],\n'
            '      "model": "model_id from the list"\n'
            "    }\n"
            "  ],\n"
            '  "manager_model": "model_id from the list or openrouter/auto",\n'
            '  "image_model": "model_id from specialized catalog (REQUIRED if plan uses generate_image)",\n'
            '  "video_model": "model_id from specialized catalog (REQUIRED if plan uses generate_video)",\n'
            '  "search_model": "model_id from specialized catalog (REQUIRED if plan uses search_web)",\n'
            '  "tts_model": "model_id from specialized catalog (REQUIRED if plan uses text_to_speech)",\n'
            '  "stt_model": "model_id from specialized catalog (REQUIRED if plan uses transcribe_audio)",\n'
            '  "vision_model": "model_id from specialized catalog (REQUIRED if plan uses analyze_image)"\n'
            "}\n\n"
            "Design Rules for plan:\n"
            "- Create as many agents as needed (1, 2, 3, or more)\n"
            "- Each agent should have a clear, distinct responsibility\n"
            "- Assign capabilities based on the descriptions below\n"
            "- Only use model IDs from the available models list\n"
            "- You can use 'openrouter/auto' as a model ID — OpenRouter will automatically select the best model\n"
            "- Write all content in the SAME language as the user's request\n"
            "- Name agents as 'Role #N' (e.g. Creative Writer #1)\n"
            "- Give each agent personality, expertise, and brand_context fields\n"
            "- backstory should be brief — personality, expertise, and brand_context carry the detail\n\n"
            f"Available capabilities:\n{caps_text}\n\n"
            f"Available text models:\n{models_text}\n\n"
            f"Specialized AI models:\n{media_catalog or 'none'}\n\n"
            f"{history_text}"
            f"User message: {user_input}\n\n"
            "Output ONLY the JSON object, no explanation:"
        )

        if stream_callback:
            import queue, threading
            chunk_queue: queue.Queue = queue.Queue()
            full_response = []

            def _stream_in_thread():
                try:
                    for chunk in self.llm_manager.call_with_multimodal_streaming(prompt, content_blocks, plugins):
                        full_response.append(chunk)
                        chunk_queue.put(chunk)
                except Exception as e:
                    chunk_queue.put(e)
                chunk_queue.put(None)

            thread = threading.Thread(target=_stream_in_thread, daemon=True)
            thread.start()

            while True:
                try:
                    item = chunk_queue.get_nowait()
                except queue.Empty:
                    await asyncio.sleep(0.05)
                    continue
                if item is None:
                    break
                if isinstance(item, Exception):
                    print(f"[assess_and_plan_multimodal] Streaming error: {_sanitize_error(item)}")
                    break
                if item:
                    await stream_callback(item)

            thread.join(timeout=1)
            response = "".join(full_response).strip()
        else:
            response = (await self.llm_manager.call_with_multimodal_async(prompt, content_blocks, plugins)).strip()

        if not response:
            selected = self.llm_manager._selected_model or self.llm_manager._default_model or "auto"
            return {
                "action": "chat",
                "message": f"❌ โมเดล '{selected}' ส่งคำตอบกลับมาว่างเปล่า อาจไม่รองรับ multimodal input"
            }
        return self._parse_unified_response(response, valid_model_ids)

    async def info_response(self, user_input: str, agents: list[dict], tasks: list[dict], state: str) -> str:
        """ตอบคำถามข้อมูลระบบ"""
        llm = self.llm_manager.get_llm()
        prompt = (
            "You are the central secretary of an Agent Management Platform.\n"
            "Answer the user's question based on the system data below.\n\n"
            "Respond in the same language as the user's question.\n\n"
            f"System state: {state}\n"
            f"Agents (JSON): {json.dumps(agents, ensure_ascii=False, indent=2)}\n\n"
            f"Tasks (JSON): {json.dumps(tasks, ensure_ascii=False, indent=2)}\n\n"
            f"User question: {user_input}\n\n"
            "Answer:"
        )
        return (await self.llm_manager.call_async(prompt)).strip()

    async def analyze(self, user_input: str, available_tools: list[str], conversation_history: list[dict] | None = None) -> list[dict]:
        """วิเคราะห์และออกแบบ multi-agent plan — ไม่จำกัดจำนวน agent หรือ capabilities"""
        llm = self.llm_manager.get_llm()

        # Build capability descriptions from registry
        cap_registry = CapabilityRegistry()
        catalog = cap_registry.list_catalog()
        caps_text = "\n".join(
            f"- {c['name']}: {c['description']}" for c in catalog
        ) if catalog else "none"

        history_text = ""
        if conversation_history:
            history_text = "\nConversation context:\n"
            for msg in conversation_history[-10:]:
                history_text += f"- {msg.get('role', 'user')}: {msg.get('content', '')[:150]}\n"

        prompt = (
            "You are the Central Secretary of an Agent Management Platform.\n"
            "Analyze the user's request and design a multi-agent plan to accomplish it.\n\n"
            f"User request: {user_input}\n"
            f"{history_text}"
            f"Available capabilities: {caps_text}\n\n"
            "Design Rules:\n"
            "- Create as many agents as needed (1, 2, 3, or more — your decision)\n"
            "- Each agent should have a clear, distinct responsibility\n"
            "- Assign capabilities to agents based on the descriptions above — "
            "match each capability to the agent whose task requires it\n"
            "- Capabilities of type 'tool' (search_web, generate_image) give the agent external abilities\n"
            "- Capabilities of type 'model_trait' (reasoning, creative_writing, write_code, long_context) "
            "guide model selection but are not tools\n"
            "- A manager agent will coordinate the team and delegate tasks\n"
            "- Independent tasks may run in parallel; dependent tasks will wait\n"
            "- Write all content in the SAME language as the user's request\n\n"
            "Output format (JSON array, no other text):\n"
            "[\n"
            "  {\n"
            '    "name": "Agent Name",\n'
            '    "role": "Agent Role",\n'
            '    "goal": "Agent Goal",\n'
            '    "backstory": "Agent Backstory/Persona",\n'
            '    "tools": ["capability_name"],\n'
            '    "task_description": "What this agent should do"\n'
            "  }\n"
            "]\n\n"
            "Output ONLY the JSON array, no explanation:"
        )
        response = await self.llm_manager.call_async(prompt)
        return self._parse_agent_specs(response, user_input)

    def check_resources(
        self, agent_spec: dict, registry: AgentRegistry
    ) -> dict:
        """
        เช็ค Registry ว่ามี Agent ที่ว่างและตรงสายงานหรือไม่
        Returns: {"type": "existing", "agent": {...}} หรือ {"type": "create", "spec": {...}}
        """
        existing = registry.find_idle_agent(
            agent_spec.get("role", ""), agent_spec.get("tools", [])
        )
        if existing:
            return {"type": "existing", "agent": existing}
        return {"type": "create", "spec": agent_spec}

    def _parse_agent_specs(self, text: str, user_input: str) -> list[dict]:
        """Parse agent specs from JSON array or text format"""
        agents = []

        # Try JSON array first
        try:
            json_match = re.search(r'\[.*\]', text, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                if isinstance(parsed, list):
                    for item in parsed:
                        if isinstance(item, dict) and "name" in item and "role" in item:
                            depends_on = item.get("depends_on", [])
                            if not isinstance(depends_on, list):
                                depends_on = []
                            agents.append({
                                "name": item.get("name", "").strip(),
                                "role": item.get("role", "").strip(),
                                "goal": item.get("goal", "").strip(),
                                "backstory": item.get("backstory", "").strip(),
                                "personality": item.get("personality", {}) if isinstance(item.get("personality"), dict) else {},
                                "expertise": item.get("expertise", []) if isinstance(item.get("expertise"), list) else [],
                                "brand_context": item.get("brand_context", {}) if isinstance(item.get("brand_context"), dict) else {},
                                "tools": item.get("tools", []) if isinstance(item.get("tools"), list) else [],
                                "task_description": item.get("task_description", user_input).strip(),
                                "depends_on": [d.strip() for d in depends_on if isinstance(d, str) and d.strip()],
                            })
                    if agents:
                        return agents
        except (json.JSONDecodeError, AttributeError):
            pass

        # Fallback: text format parsing
        blocks = re.split(r"\n(?=\d+\.\s*Agent Name:)", text.strip())
        for block in blocks:
            if not block.strip():
                continue

            name_match = re.search(r"Agent Name:\s*(.+)", block)
            role_match = re.search(r"Role:\s*(.+)", block)
            goal_match = re.search(r"Goal:\s*(.+)", block)
            backstory_match = re.search(r"Backstory:\s*(.+)", block)
            tools_match = re.search(r"Tools:\s*(.+)", block)
            task_match = re.search(r"Task Description:\s*(.+)", block)

            if name_match and role_match:
                tools_str = tools_match.group(1).strip() if tools_match else ""
                tools = [t.strip() for t in tools_str.split(",") if t.strip()]
                agents.append(
                    {
                        "name": name_match.group(1).strip(),
                        "role": role_match.group(1).strip(),
                        "goal": goal_match.group(1).strip() if goal_match else "",
                        "backstory": backstory_match.group(1).strip()
                        if backstory_match
                        else "",
                        "tools": tools,
                        "task_description": task_match.group(1).strip()
                        if task_match
                        else user_input,
                    }
                )

        if not agents:
            agents.append(
                {
                    "name": "Agent หลัก",
                    "role": "ผู้ช่วยทั่วไป",
                    "goal": "ตอบคำถามและช่วยเหลือ User",
                    "backstory": "คุณเป็นผู้ช่วยที่มีประสบการณ์",
                    "tools": [],
                    "task_description": user_input,
                }
            )
        return agents



