"""CentralManager — the heart of the system: assess + plan in 1 LLM call."""

import asyncio
import contextvars
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

class CentralManager:
    """AI Manager: ประเมินความต้องการ, ถาม requirement, วิเคราะห์และวางแผน multi-agent"""

    def __init__(self, llm_manager: LLMManager):
        self.llm_manager = llm_manager

    async def assess(self, user_input: str, conversation_history: list[dict] | None = None) -> dict:
        """ประเมินความต้องการ: CHAT (ตอบเลย) / INFO (ตอบเลย) / TASK_NEEDS_INFO (ถามเพิ่ม) / TASK_READY (วางแผน)"""
        history_text = ""
        if conversation_history:
            # No cap — send full conversation history so Secretary can recall all past tasks (Issue #30)
            recent = conversation_history
            history_text = "\nConversation so far:\n"
            for msg in recent:
                content = msg.get('content', '')
                history_text += f"- {msg.get('role', 'user')}: {content}\n"

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
            "- If the user wants something produced/created/designed but missing key details → ask\n"
            "- If the user has provided enough detail to design a plan → plan\n"
            "- NEVER provide work output (concepts, designs, drafts, plans, content) directly in a chat response — this platform uses AI agents to do the work, not the assessor.\n"
            "- Use the same language as the user.\n\n"
            f"{history_text}"
            f"User message: {user_input}\n"
            "Response JSON:"
        )
        response = (await self.llm_manager.call_async(prompt, caller="assess")).strip()
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
        force_plan: bool = False,
        force_proceed: bool = False,
        has_attachment: bool = False,
        chat_only: bool = False,
    ) -> dict:
        """Unified call: assess + analyze + model assignment in one LLM response.

        Returns same format as assess() for chat/info/ask paths.
        For plan path, includes 'agents' and 'model_assignment' keys.
        For feedback path, includes 'feedback_text' and 'target_agent' keys.
        Falls back to assess() on parse error.
        """
        history_text = ""
        if conversation_history:
            # No cap — send full conversation history so Secretary can recall all past tasks (Issue #30)
            recent = conversation_history
            history_text = "\nConversation so far:\n"
            for msg in recent:
                content = msg.get('content', '')
                history_text += f"- {msg.get('role', 'user')}: {content}\n"

        cap_registry = CapabilityRegistry()
        catalog = cap_registry.list_catalog()
        caps_text = "\n".join(
            f"- {c['name']}: {c['description']}" for c in catalog
        ) if catalog else "none"

        models_text = "Assign each agent a model from this list: 'google/gemini-3.5-flash', 'anthropic/claude-sonnet-5', 'openai/gpt-5.6-luna'. Choose the most suitable model based on the agent's role and tasks. The Manager uses 'openrouter/free' by default."

        # Build last task context (if any) — include full agent outputs + media results (Issue #30)
        last_task_text = ""
        if last_task_context:
            last_task_text = "\nLast completed task:\n"
            last_task_text += f"- User request: {last_task_context.get('user_input', '')}\n"
            last_task_text += f"- Result summary: {last_task_context.get('result', '')}\n"
            # Include full per-agent outputs (not truncated) so follow-up prompts have real context
            agent_outputs = last_task_context.get('agent_outputs', [])
            for a in agent_outputs:
                name = a.get('name', 'Agent')
                agent_id = a.get('id', '')
                role = a.get('role', '')
                output = a.get('output', '')
                last_task_text += f"- Agent output [{name}] (id={agent_id}, role={role}):\n{output}\n"
            # Include all media results (image, audio, video, file, transcription)
            media_results = last_task_context.get('media_results', [])
            for m in media_results:
                mtype = m.get('type', 'media')
                url = m.get('url', '')
                prompt = m.get('prompt', '')
                agent_name = m.get('agentName', '')
                last_task_text += f"- Media result ({mtype}): prompt={prompt} | url={url} | agent={agent_name}\n"

        # Safety net: if combined context (history + last task) exceeds 60000 chars,
        # truncate oldest history content to fit — prevents context window overflow (Issue #30)
        MAX_CONTEXT_CHARS = 60000
        combined_len = len(history_text) + len(last_task_text)
        if combined_len > MAX_CONTEXT_CHARS:
            # Truncate history_text from the front (oldest messages first)
            excess = combined_len - MAX_CONTEXT_CHARS
            history_text = history_text[excess:]

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
                # Include full agent details so Secretary can decide reuse based on all fields
                goal = a.get('goal', '')
                persona = a.get('persona', '')[:200] if a.get('persona') else ''
                expertise = a.get('expertise', [])
                personality = a.get('personality', {})
                brand_context = a.get('brand_context', {})
                if goal:
                    team_text += f"  goal: {goal}\n"
                if persona:
                    team_text += f"  persona: {persona}\n"
                if expertise:
                    team_text += f"  expertise: {expertise}\n"
                if personality:
                    team_text += f"  personality: {personality}\n"
                if brand_context:
                    team_text += f"  brand_context: {brand_context}\n"

        if has_attachment:
            attachment_status = "A file/image is attached. The user may want to discuss it, ask questions about it, or have agents process it."
        else:
            attachment_status = "No file is attached. If the user's request involves analyzing, reviewing, or extracting information from a file, document, PDF, image, or spreadsheet, you MUST use 'ask' to request the file before creating a plan. Do NOT proceed with assumptions about file contents."

        if chat_only:
            prompt = (
                "You are the Central Secretary of an AI Agent Management Platform.\n"
                "This platform CREATES and MANAGES AI agents (not human workers) to do tasks.\n\n"
                f"Attachment status: {attachment_status}\n\n"
                "You are in CHAT MODE. You can ONLY respond with 'chat'.\n"
                "Answer the user's question directly — this includes answering questions about attached images/files,\n"
                "analyzing images, summarizing documents, general conversation, and self-introduction.\n"
                "Do NOT create plans, agents, or tuning proposals.\n"
                "If the user seems to want work produced (content creation, image generation, etc.),\n"
                "suggest they switch to Plan mode to create a plan.\n\n"
                "Respond with:\n"
                '  {"action": "chat", "message": "your reply"}\n\n'
                "Use the same language as the user.\n\n"
                f"{history_text}"
                f"User message: {user_input}\n\n"
                "Output ONLY the JSON object, no explanation:"
            )
        else:
            prompt = (
                "You are the Central Secretary of an AI Agent Management Platform.\n"
                "This platform CREATES and MANAGES AI agents (not human workers) to do tasks.\n"
                "Users can request new AI agents to be created, assign them tasks, and tune their behavior.\n\n"
                f"Attachment status: {attachment_status}\n\n"
                "Evaluate the user's message and respond with a single JSON object.\n\n"
                "First, decide what to do:\n"
                "- chat: greetings, small talk, general questions, self-introduction requests, questions about an attached image/file, image analysis, document summary\n"
                "- info: questions about system/agents/status\n"
                "- ask: user wants work done but needs are unclear\n"
                "- create_agents: user wants to CREATE agents to keep in the team WITHOUT running a task right now\n"
                "  Use this when user says 'สร้าง agent ไว้ในทีม', 'อยากได้นัก...ไว้ในทีม', 'เพิ่ม agent' without specifying work to do\n"
                "  Respond with agent specs (same format as plan) but action='create_agents'\n"
                "  When the user specifies a number of agents (e.g. '2 คน', '3 agents'), create EXACTLY that many agents.\n"
                "  Do NOT reduce, consolidate, or reuse existing agents when the user explicitly asks to create new ones.\n"
                "  Each agent should have a distinct focus even if they share the same role.\n"
                "  Create agents that match EXACTLY what the user requests — same role, same quantity.\n"
                "  Do NOT substitute with a different role or create fewer agents than requested.\n"
                "- plan: user wants specific work/task produced and delivered (content creation, images to generate, videos to produce, reports to write, etc.)\n"
                "  Use 'plan' when user clearly states WHAT work to do, not just WHAT roles they want.\n"
                "  If team already has agents with matching roles, REUSE them — set 'reuse_existing' to true and reference by name\n"
                "- tuning: user wants to adjust, refine, or change how an EXISTING agent behaves — one that has already been created and saved in the registry.\n"
                "  This applies to tone, style, personality, expertise, or any aspect of a registered agent.\n"
                "  If the user mentions a specific agent, tune that one. If not, use context to determine which agent(s) to tune.\n\n"
            )

        if force_plan:
            prompt += (
                "IMPORTANT: The user is in PLAN MODE. This mode supports ALL actions: creating agents, executing tasks, tuning agents, and more.\n"
                "Do NOT restrict yourself to only team creation — evaluate what the user wants and respond accordingly.\n\n"
                "You MUST respond with 'plan', 'create_agents', or 'tuning'.\n"
                "Do NOT use 'chat' or 'info'.\n"
                "You MAY use 'ask' ONLY when a critical input is clearly missing (e.g. the user references a file/document/image but none is attached).\n"
                "If information is missing or vague, make reasonable assumptions and proceed.\n"
                "The user will review your proposal and can reject it with feedback if needed.\n\n"
                "When the user specifies a number of agents (e.g. '2 คน', '3 agents'), create EXACTLY that many agents.\n"
                "Do NOT reduce, consolidate, or reuse existing agents when the user explicitly asks to create new ones.\n"
                "Each agent should have a distinct focus even if they share the same role.\n"
                "Create agents that match EXACTLY what the user requests — same role, same quantity.\n"
                "Do NOT substitute with a different role or create fewer agents than requested.\n\n"
                "If the conversation history contains a '[REJECTED]' entry, the user rejected the previous plan.\n"
                "Read their feedback carefully and create a REVISED plan that addresses their concerns.\n"
                "Do NOT create the same plan again — change what the user asked to change.\n\n"
                "Use 'tuning' ONLY when agents already exist in the registry (shown in 'Current team agents' above) AND the user wants to modify existing agent behavior.\n"
                "If the conversation history contains a 'Proposed team:' entry and the user wants to modify, adjust, or refine that team, use 'create_agents' — NOT 'tuning'.\n"
                "The 'Proposed team' is a draft, not yet created. Modifying a draft means regenerating it with changes, which is 'create_agents'.\n"
                "'tuning' applies to agents that have already been created and saved in the system.\n\n"
                "Use 'create_agents' when the user wants to create new agents WITHOUT running a task right now, OR when modifying a previously proposed team.\n"
                "When modifying a previously proposed team, PRESERVE all unchanged agents exactly as they were — keep their name, role, goal, persona, tools, and model.\n"
                "Only change the specific agents or fields the user mentioned, or add/remove agents as requested.\n"
                "Do NOT regenerate unchanged agents from scratch.\n"
                "Use 'plan' when the user wants WORK DONE — producing content, images, videos, analysis, or any deliverable.\n"
                "If team already has agents with matching roles, REUSE them — set 'reuse_existing' to true and reference by name.\n"
                "Only create NEW agents when the team lacks the required capability.\n\n"

                "If there is a 'Last completed task' above, the user's message is likely a FOLLOW-UP or REFINEMENT of that task.\n"
                "In that case, create a plan that builds on the previous work — reuse the same agents or add new ones,\n"
                "and set their goals to refine/adjust/improve the previous output based on the user's new request.\n"
                "Include the previous result as context in the agent goals so they know what to improve.\n\n"
            )
        else:
            prompt += (
                "IMPORTANT: Do NOT create a plan for greetings, self-introductions, or simple questions.\n"
                "Only create a plan when the user explicitly asks for work to be done.\n"
                "Use 'tuning' when the user wants to modify agent behavior — not when asking for new work.\n\n"
                "If you already asked a question and received an answer, do NOT ask the same or similar question again.\n"
                "Either ask a DIFFERENT question about genuinely missing info, or proceed with reasonable assumptions.\n"
                "When in doubt, make reasonable assumptions and proceed rather than asking repeatedly.\n\n"
            )

        if force_proceed:
            prompt += (
                "IMPORTANT: You have already asked clarifying questions and the user has provided answers.\n"
                "Do NOT use 'ask' again. Proceed with the available information — make reasonable assumptions where needed.\n"
                "You MUST respond with 'plan' or 'create_agents'.\n\n"
            )

        prompt += (
            "For chat/info/ask, respond with:\n"
            '  {"action": "chat", "message": "your reply"}\n'
            '  {"action": "info", "message": "your reply"}\n'
            '  {"action": "ask", "questions": ["q1", "q2", ...]}\n\n'
            "IMPORTANT: For chat and info, you MUST include a 'message' field with your full reply. Do not return empty message.\n\n"

            "For tuning, respond with:\n"
            '  {"action": "tuning", "tuning_text": "what the user wants to change", "target_agent": "agent name or empty if unclear"}\n\n'

            "For create_agents, respond with essential fields at minimum:\n"
            "{\n"
            '  "action": "create_agents",\n'
            '  "summary": "brief summary of agents being created",\n'
            '  "team_name": "a short, descriptive team name (NOT the user prompt)",\n'
            '  "team_description": "1-2 sentence description of the team purpose",\n'
            '  "agents": [\n'
            "    {\n"
            '      "name": "Role #N (e.g. Creative Writer #1)",\n'
            '      "role": "Agent Role",\n'
            '      "goal": "Agent Goal",\n'
            '      "persona": "Brief persona/backstory as a single string",\n'
            '      "personality": {"tone": "...", "communication_style": "...", "language": "..."},\n'
            '      "expertise": ["skill1", "skill2"],\n'
            '      "brand_context": {"brand_name": "", "guidelines": "", "target_audience": ""},\n'
            '      "tools": ["capability_name"],\n'
            '      "model": "choose from: google/gemini-3.5-flash, anthropic/claude-sonnet-5, openai/gpt-5.6-luna",\n'
            '      "output_format": "format specification for output (optional, e.g. [Hook] [Body] [CTA] [Hashtags])",\n'
            '      "quality_criteria": "criteria for quality checking (optional, e.g. 1. Must have hook 2. Must have CTA)",\n'
            '      "review_iterations": null,\n'
            '      "max_iter": null,\n'
            '      "max_retry_limit": null,\n'
            '      "allow_delegation": false\n'
            "    }\n"
            "  ]\n"
            "}\n"
            "You MUST include name, role, goal, persona, personality, expertise, brand_context, tools, and model for every agent.\n"
            "Always generate personality, expertise, and brand_context even if the user doesn't specify them — infer from the role and goal.\n"
            "If the conversation history shows a previously proposed team and the user wants to modify it, UPDATE that team instead of creating a new one.\n\n"

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
            '      "model": "choose from: google/gemini-3.5-flash, anthropic/claude-sonnet-5, openai/gpt-5.6-luna",\n'
            '      "template_id": "template id if using a predefined template (optional)",\n'
            '      "output_format": "format specification for output (optional, e.g. [Hook] [Body] [CTA] [Hashtags])",\n'
            '      "quality_criteria": "criteria for quality checking (optional, e.g. 1. Must have hook 2. Must have CTA)",\n'
            '      "review_iterations": null,\n'
            '      "max_iter": null,\n'
            '      "max_retry_limit": null,\n'
            '      "allow_delegation": false\n'
            "    }\n"
            "  ],\n"
            '  "image_model": "model_id from specialized catalog (REQUIRED if plan uses generate_image)",\n'
            '  "video_model": "model_id from specialized catalog (REQUIRED if plan uses generate_video)",\n'
            '  "search_model": "(deprecated — web search is now built-in via OpenRouter server tools)",\n'
            '  "tts_model": "model_id from specialized catalog (REQUIRED if plan uses text_to_speech)",\n'
            '  "stt_model": "model_id from specialized catalog (REQUIRED if plan uses transcribe_audio)",\n'
            '  "vision_model": "model_id from specialized catalog (REQUIRED if plan uses analyze_image)"\n'
            "}\n\n"
            "Design Rules for plan:\n"
            "- Do NOT include a Manager agent in your response — the system has a Manager already. Only include worker agents.\n"
            "- REUSE existing team agents when possible — if a team agent already has the right role/tools, include it by name instead of creating a new one\n"
            "- When deciding whether to reuse an existing agent, consider ALL of its fields: goal, persona, expertise, personality, brand_context — not just role and tools. If an existing agent's goal and expertise closely match the task, reuse it rather than creating a new one.\n"
            "- Only create NEW agents when the team lacks the required capability\n"
            "- CRITICAL: When reusing an existing agent, you MUST keep ALL of its original tools. Do NOT remove or replace existing tools (analyze_image, generate_image, etc.). You may ADD model_traits like 'reasoning' or 'long_context' but you must NEVER remove existing tools. Tools give agents external abilities — removing them cripples the agent.\n"
            "- Model_traits (reasoning, creative_writing, write_code, long_context) are NOT tools — they guide model selection only. Never use them to replace actual tools.\n"
            "- If the user mentions @AgentName, that agent MUST be included in the plan — use the exact name from the team agents list\n"
            "- Each agent has a 'reuse_existing' field: set true to use an existing agent as-is, false to create new or modify. You decide based on context.\n"
            "- Create as many agents as needed (1, 2, 3, or more)\n"
            "- Each agent should have a clear, distinct responsibility\n"
            "- Assign capabilities based on the descriptions below\n"
            "- Capabilities of type 'tool' (generate_image, generate_video, text_to_speech, transcribe_audio, analyze_image, generate_document) give external abilities\n"
            "- Capabilities of type 'model_trait' (reasoning, creative_writing, write_code, long_context) guide model selection\n"
            "- Assign each agent the most suitable model from: 'google/gemini-3.5-flash', 'anthropic/claude-sonnet-5', 'openai/gpt-5.6-luna'. Consider the agent's role and tasks when choosing.\n"
            "- Leave image_model/video_model/search_model/tts_model/stt_model/vision_model empty — the user will select models in the plan card\n"
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
            "- Each agent's task_description MUST be scoped to ONLY their responsibility — do NOT overlap with other agents' work.\n"
            "- If there is a content writer and an image designer, the content writer writes ONLY the text content. The image designer creates images.\n"
            "- Do NOT have one agent describe or produce what another agent should create.\n"
            "- If an image designer needs to create images based on a content writer's output, set depends_on: [\"Content Writer name\"] so the image designer receives the content automatically.\n"
            "- BAD: 'Generate images based on descriptions provided by the manager' (vague, no depends_on)\n"
            "- BAD: 'Write an article AND describe image concepts' (scope overlap — image concepts are the image designer's job)\n"
            "- GOOD (no depends_on): 'Write 1 engaging caption for a coffee shop post about latte art. Include hashtags and CTA.'\n"
            "- GOOD (with depends_on): 'Based on the caption from Creative Copywriter, create 1 image that visually matches the described scene. Call generate_image with a detailed English prompt.' + depends_on: [\"Creative Copywriter\"]\n"
            "- Include: what to create, how many, subject/theme, and which tool to call.\n"
            "- If an agent has generate_image in tools, its task_description MUST explicitly say 'Call generate_image to create N images of [specific subject]' — not 'design images' or 'create visual concepts'.\n"
            "- Agents with media tools (generate_image, generate_video) MUST call those tools as part of their work. Writing image/video prompts as text output is NOT acceptable — the agent must CALL the tool.\n\n"

            "CRITICAL — Tool Assignment Rules:\n"
            "- If the user asks to CREATE/GENERATE/MAKE any visual output (poster, image, picture, graphic, illustration, banner, thumbnail, logo, infographic, ภาพ, โปสเตอร์, กราฟิก, รูป, แบนเนอร์), you MUST assign 'generate_image' to at least one agent's tools.\n"
            "- If the user asks to CREATE/GENERATE video content, you MUST assign 'generate_video' to at least one agent's tools.\n"
            "- If the user asks to analyze/examine an image, you MUST assign 'analyze_image' to at least one agent's tools.\n"
            "- If the user asks to generate a document/report/file, you MUST assign 'generate_document' to at least one agent's tools.\n"
            "- Writing text descriptions of images or prompts WITHOUT calling generate_image is NOT acceptable when the user wants actual images.\n"
            "- When in doubt about whether a tool is needed, assign it — it is better to have the tool and not use it than to lack it.\n\n"

            f"Available capabilities:\n{caps_text}\n\n"
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
                    for chunk in self.llm_manager.call_streaming(prompt, caller="assess_and_plan"):
                        full_response.append(chunk)
                        chunk_queue.put(chunk)
                except Exception as e:
                    chunk_queue.put(e)
                chunk_queue.put(None)  # sentinel

            _ctx = contextvars.copy_context()
            thread = threading.Thread(target=lambda: _ctx.run(_stream_in_thread), daemon=True)
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
            response = (await self.llm_manager.call_async(prompt, caller="assess_and_plan")).strip()
        if not response:
            selected = self.llm_manager._selected_model or self.llm_manager._default_model or "auto"
            return {
                "action": "chat",
                "message": f"❌ โมเดล '{selected}' ส่งคำตอบกลับมาว่างเปล่า อาจไม่รองรับคำสั่งที่ซับซ้อน ลองเปลี่ยนโมเดลแล้วส่งใหม่อีกครั้ง"
            }
        if os.getenv("DEBUG_MODE", "false").lower() == "true":
            print(f"[DEBUG-PLAN-RAW] LLM response (first 800 chars): {response[:800]}", flush=True)
        result = self._parse_unified_response(response, valid_model_ids, chat_only=chat_only, user_input=user_input)

        # If parsing failed and we're on free routing, retry with rotator
        if result.get("action") == "chat" and "ไม่ใช่ JSON" in result.get("message", ""):
            if self.llm_manager._is_free_routing():
                print(f"[assess_and_plan] Response not JSON — retrying with free model rotator", flush=True)
                try:
                    retry_response = self.llm_manager._get_rotator().call(prompt, caller="assess_and_plan:retry")
                    if retry_response and retry_response.strip():
                        retry_result = self._parse_unified_response(retry_response.strip(), valid_model_ids, chat_only=chat_only, user_input=user_input)
                        if retry_result.get("action") in ("plan", "create_agents", "ask", "tuning"):
                            return retry_result
                        print(f"[assess_and_plan] Rotator retry also failed to produce valid JSON", flush=True)
                except Exception as retry_err:
                    print(f"[assess_and_plan] Rotator retry error: {_sanitize_error(retry_err)}", flush=True)
        if chat_only and result.get("action") != "chat":
            result = {
                "action": "chat",
                "message": result.get("message") or "ฟังก์ชันนี้ต้องใช้ในโหมด Plan ครับ กรุณาสลับไปโหมด Plan เพื่อสร้างแผนงานหรือจัดการ agent",
            }
        return result

    def _parse_unified_response(
        self, text: str, valid_model_ids: set[str] | None = None, chat_only: bool = False, user_input: str = ""
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
                            f"⚠️ โมเดล '{selected}' ส่งคำตอบกลับมาไม่ถูกต้อง "
                            f"ลองเปลี่ยนโมเดลแล้วส่งใหม่อีกครั้ง"
                        )
                    }

                if result["action"] in ("plan", "create_agents"):
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
                                "persona": item.get("persona", item.get("backstory", "")).strip() if isinstance(item.get("persona", item.get("backstory", "")), str) else "",
                                "backstory": item.get("backstory", "").strip(),
                                "personality": item.get("personality", {}) if isinstance(item.get("personality"), dict) else {},
                                "expertise": item.get("expertise", []) if isinstance(item.get("expertise"), list) else [],
                                "brand_context": item.get("brand_context", {}) if isinstance(item.get("brand_context"), dict) else {},
                                "tools": item.get("tools", []) if isinstance(item.get("tools"), list) else [],
                                "task_description": item.get("task_description", "").strip(),
                                "depends_on": [d.strip() for d in depends_on if isinstance(d, str) and d.strip()],
                                "model": item.get("model", "openrouter/free").strip() or "openrouter/free",
                                "reuse_existing": item.get("reuse_existing", False),
                                "output_format": item.get("output_format", "").strip(),
                                "quality_criteria": item.get("quality_criteria", "").strip(),
                                "review_iterations": item.get("review_iterations"),
                                "max_iter": item.get("max_iter"),
                                "max_retry_limit": item.get("max_retry_limit"),
                                "allow_delegation": item.get("allow_delegation", False) if isinstance(item.get("allow_delegation"), bool) else False,
                            })
                    if not agents:
                        return {"action": "chat", "message": "ไม่สามารถวางแผนได้ กรุณาลองใหม่"}

                    # Post-parse validation: ensure generate_image is assigned when user requests images/posters
                    user_input_lower = user_input.lower() if user_input else ""
                    image_keywords = ["poster", "โปสเตอร์", "image", "รูป", "ภาพ", "picture", "photo", "ออกแบบภาพ", "สร้างภาพ", "banner", "แบนเนอร์"]
                    needs_image = any(kw in user_input_lower for kw in image_keywords)
                    has_image_tool = any("generate_image" in a.get("tools", []) for a in agents)
                    if needs_image and not has_image_tool:
                        # Find the most likely design/visual agent
                        design_keywords = ["design", "poster", "image", "visual", "artist", "designer", "ภาพ", "ออกแบบ", "ศิลปิน", "graphic"]
                        best_idx = -1
                        best_score = 0
                        for i, a in enumerate(agents):
                            name_role = (a.get("name", "") + " " + a.get("role", "")).lower()
                            score = sum(1 for kw in design_keywords if kw in name_role)
                            if score > best_score:
                                best_score = score
                                best_idx = i
                        if best_idx >= 0:
                            agents[best_idx]["tools"] = list(set(agents[best_idx].get("tools", []) + ["generate_image"]))
                            if not agents[best_idx].get("task_description", ""):
                                agents[best_idx]["task_description"] = "Call generate_image to create the requested visual content."
                            elif "generate_image" not in agents[best_idx]["task_description"].lower():
                                agents[best_idx]["task_description"] += " Call generate_image to create the requested visual content."
                            print(f"[SECRETARY] Auto-added generate_image to agent: {agents[best_idx]['name']}", flush=True)

                    model_assignment = {"manager": result.get("manager_model", "openrouter/free"), "workers": {}}
                    for a in agents:
                        model_assignment["workers"][a["name"]] = a.get("model", "openrouter/free")

                    return {
                        "action": result["action"],
                        "summary": result.get("summary", ""),
                        "team_name": result.get("team_name", ""),
                        "team_description": result.get("team_description", ""),
                        "agents": agents,
                        "model_assignment": model_assignment,
                        "image_model": "",
                        "video_model": "",
                        "search_model": "",
                        "tts_model": "",
                        "stt_model": "",
                        "vision_model": "",
                    }

                return result
        except (json.JSONDecodeError, AttributeError) as e:
            print(f"[DEBUG-PARSE-UNIFIED] Failed: {e}", flush=True)
            print(f"[DEBUG-PARSE-UNIFIED] Response (first 500 chars): {text[:500]}", flush=True)
        selected = self.llm_manager._selected_model or self.llm_manager._default_model or "auto"
        if chat_only:
            return {
                "action": "chat",
                "message": (
                    f"⚠️ โมเดล '{selected}' ส่งคำตอบกลับมาไม่ถูกต้อง "
                    f"ลองเปลี่ยนโมเดลแล้วส่งใหม่อีกครั้ง"
                )
            }
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
        conversation_history: list[dict] | None = None,
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
                "goal": spec.get("goal", ""),
                "persona": spec.get("backstory", spec.get("persona", ""))[:200],
                "personality": personality,
                "expertise": spec.get("expertise", []),
                "brand_context": spec.get("brand_context", {}),
                "tools": spec.get("tools", []),
                "model": spec.get("model", ""),
            })

        history_text = ""
        if conversation_history:
            # No cap — send full conversation history so Secretary can recall all past tasks (Issue #30)
            recent = conversation_history
            history_text = "\nConversation context:\n"
            for msg in recent:
                content = msg.get('content', '')
                history_text += f"- {msg.get('role', 'user')}: {content}\n"

        prompt = (
            "You are the Central Secretary analyzing a user request to tune/adjust agents.\n"
            "Based on the user's request, propose specific tuning changes to agents.\n\n"
            f"User request: {feedback_text}\n\n"
        )
        if task_result:
            prompt += f"Last task result (for context):\n{task_result[:1000]}\n\n"
        if history_text:
            prompt += f"{history_text}\n"
        prompt += (
            f"Agents available for tuning:\n{json.dumps(agents_info, ensure_ascii=False, indent=2)}\n\n"
            "Analyze the request and decide which agent(s) need adjustments.\n"
            "For each agent, specify which fields to change and why.\n\n"
            "Tunable fields:\n"
            "- name (agent's display name)\n"
            "- role (agent's role title)\n"
            "- goal (the agent's objective — what it should accomplish)\n"
            "- personality.tone (e.g. professional, casual, friendly, formal)\n"
            "- personality.communication_style (e.g. concise, detailed, conversational)\n"
            "- personality.language (e.g. th, en, mixed)\n"
            "- persona/backstory (free text describing the agent's character)\n"
            "- expertise (list of skills/knowledge areas)\n"
            "- brand_context.brand_name (the brand the agent works for)\n"
            "- brand_context.guidelines (tone/style rules)\n"
            "- brand_context.target_audience (who the agent's output is for)\n"
            "- tools (list of capability names — e.g. generate_image, generate_video, text_to_speech, transcribe_audio, analyze_image, generate_document)\n"
            "- model (LLM model ID — choose from: google/gemini-3.5-flash, anthropic/claude-sonnet-5, openai/gpt-5.6-luna)\n"
            "- template_id (template ID for predefined output templates)\n"
            "- depends_on (list of agent names this agent depends on)\n"
            "- output_format (format specification for agent output, e.g. [Hook] [Body] [CTA] [Hashtags])\n"
            "- quality_criteria (criteria for quality checking, e.g. 1. Must have hook 2. Must have CTA)\n"
            "- review_iterations (int or null, max Manager review rounds, null = unlimited)\n"
            "- max_iter (int or null, max agent thinking iterations, null = unlimited)\n"
            "- max_retry_limit (int or null, max agent retries, null = unlimited)\n"
            "- allow_delegation (bool, allow agent to delegate to other agents, default false)\n\n"
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

        response = (await self.llm_manager.call_async(prompt, caller="analyze_feedback")).strip()
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
        return (await self.llm_manager.call_async(prompt, caller="chat_response")).strip()

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
        return (await self.llm_manager.call_with_image_async(prompt, image_data_url, caller="chat_response_with_image")).strip()

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
        return (await self.llm_manager.call_with_multimodal_async(prompt, content_blocks, plugins, caller="chat_response_multimodal")).strip()

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
        chat_only: bool = False,
        registry_agents: list[dict] | None = None,
        team_agents: list[dict] | None = None,
        team_name: str | None = None,
        last_task_context: dict | None = None,
    ) -> dict:
        """assess_and_plan with multimodal content blocks (image, PDF, audio, video)."""
        history_text = ""
        if conversation_history:
            # No cap — send full conversation history so Secretary can recall all past tasks (Issue #30)
            recent = conversation_history
            history_text = "\nConversation so far:\n"
            for msg in recent:
                content = msg.get('content', '')
                history_text += f"- {msg.get('role', 'user')}: {content}\n"

        cap_registry = CapabilityRegistry()
        catalog = cap_registry.list_catalog()
        caps_text = "\n".join(
            f"- {c['name']}: {c['description']}" for c in catalog
        ) if catalog else "none"

        models_text = "Assign each agent a model from this list: 'google/gemini-3.5-flash', 'anthropic/claude-sonnet-5', 'openai/gpt-5.6-luna'. Choose the most suitable model based on the agent's role and tasks. The Manager uses 'openrouter/free' by default."

        # Build registry agents text
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
                # Include full agent details so Secretary can decide reuse based on all fields
                goal = a.get('goal', '')
                persona = a.get('persona', '')[:200] if a.get('persona') else ''
                expertise = a.get('expertise', [])
                personality = a.get('personality', {})
                brand_context = a.get('brand_context', {})
                if goal:
                    team_text += f"  goal: {goal}\n"
                if persona:
                    team_text += f"  persona: {persona}\n"
                if expertise:
                    team_text += f"  expertise: {expertise}\n"
                if personality:
                    team_text += f"  personality: {personality}\n"
                if brand_context:
                    team_text += f"  brand_context: {brand_context}\n"

        # Build last task context
        last_task_text = ""
        if last_task_context:
            last_task_text = "\nLast completed task:\n"
            last_task_text += f"- User request: {last_task_context.get('user_input', '')[:200]}\n"
            last_task_text += f"- Result summary: {last_task_context.get('result', '')[:1500]}\n"
            agents_ctx = last_task_context.get('agents', [])
            for a in agents_ctx:
                name = a.get('name', 'Agent')
                role = a.get('role', '')
                persona = a.get('persona', a.get('backstory', ''))
                personality = a.get('personality', {})
                tone = personality.get('tone', '') if isinstance(personality, dict) else ''
                style = personality.get('communication_style', '') if isinstance(personality, dict) else ''
                last_task_text += f"- Agent: {name} ({role}) | tone={tone} | style={style} | persona={persona[:100]}\n"

        if chat_only:
            prompt = (
                "You are the Central Secretary of an Agent Management Platform.\n"
                "You are in CHAT MODE. You can ONLY respond with 'chat'.\n"
                "Answer the user's question directly — this includes answering questions about attached images/files,\n"
                "analyzing images, summarizing documents, general conversation, and self-introduction.\n"
                "Do NOT create plans, agents, or tuning proposals.\n"
                "If the user seems to want work produced (content creation, image generation, etc.),\n"
                "suggest they switch to Plan mode to create a plan.\n\n"
                "The user has attached a file. Analyze the attached content and use it in your response.\n\n"
                "Respond with:\n"
                '  {"action": "chat", "message": "your reply"}\n\n'
                "Use the same language as the user.\n\n"
                f"{history_text}"
                f"User message: {user_input}\n\n"
                "Output ONLY the JSON object, no explanation:"
            )
        else:
            prompt = (
                "You are the Central Secretary of an Agent Management Platform.\n"
                "Evaluate the user's message and respond with a single JSON object.\n\n"
                "First, decide what to do:\n"
                "- chat: greetings, small talk, general questions, self-introduction requests, questions about an attached image/file, image analysis, document summary\n"
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
            '      "model": "choose from: google/gemini-3.5-flash, anthropic/claude-sonnet-5, openai/gpt-5.6-luna",\n'
            '      "template_id": "template id if using a predefined template (optional)",\n'
            '      "output_format": "format specification for output (optional, e.g. [Hook] [Body] [CTA] [Hashtags])",\n'
            '      "quality_criteria": "criteria for quality checking (optional, e.g. 1. Must have hook 2. Must have CTA)",\n'
            '      "review_iterations": null,\n'
            '      "max_iter": null,\n'
            '      "max_retry_limit": null,\n'
            '      "allow_delegation": false\n'
            "    }\n"
            "  ],\n"
            '  "image_model": "model_id from specialized catalog (REQUIRED if plan uses generate_image)",\n'
            '  "video_model": "model_id from specialized catalog (REQUIRED if plan uses generate_video)",\n'
            '  "search_model": "(deprecated — web search is now built-in via OpenRouter server tools)",\n'
            '  "tts_model": "model_id from specialized catalog (REQUIRED if plan uses text_to_speech)",\n'
            '  "stt_model": "model_id from specialized catalog (REQUIRED if plan uses transcribe_audio)",\n'
            '  "vision_model": "model_id from specialized catalog (REQUIRED if plan uses analyze_image)"\n'
            "}\n\n"
            "Design Rules for plan:\n"
            "- Do NOT include a Manager agent in your response — the system has a Manager already. Only include worker agents.\n"
            "- REUSE existing team agents when possible — if a team agent already has the right role/tools, include it by name instead of creating a new one\n"
            "- When deciding whether to reuse an existing agent, consider ALL of its fields: goal, persona, expertise, personality, brand_context — not just role and tools. If an existing agent's goal and expertise closely match the task, reuse it rather than creating a new one.\n"
            "- Only create NEW agents when the team lacks the required capability\n"
            "- CRITICAL: When reusing an existing agent, you MUST keep ALL of its original tools. Do NOT remove or replace existing tools (analyze_image, generate_image, etc.). You may ADD model_traits like 'reasoning' or 'long_context' but you must NEVER remove existing tools. Tools give agents external abilities — removing them cripples the agent.\n"
            "- Model_traits (reasoning, creative_writing, write_code, long_context) are NOT tools — they guide model selection only. Never use them to replace actual tools.\n"
            "- If the user mentions @AgentName, that agent MUST be included in the plan — use the exact name from the team agents list\n"
            "- Each agent has a 'reuse_existing' field: set true to use an existing agent as-is, false to create new or modify. You decide based on context.\n"
            "- Create as many agents as needed (1, 2, 3, or more)\n"
            "- Each agent should have a clear, distinct responsibility\n"
            "- Assign capabilities based on the descriptions below\n"
            "- Assign each agent the most suitable model from: 'google/gemini-3.5-flash', 'anthropic/claude-sonnet-5', 'openai/gpt-5.6-luna'. Consider the agent's role and tasks when choosing.\n"
            "- Write all content in the SAME language as the user's request\n"
            "- Name agents as 'Role #N' (e.g. Creative Writer #1)\n"
            "- Give each agent personality, expertise, and brand_context fields\n"
            "- backstory should be brief — personality, expertise, and brand_context carry the detail\n\n"
            f"Available capabilities:\n{caps_text}\n\n"
            f"{history_text}"
            f"{last_task_text}"
            f"{registry_text}"
            f"{team_text}"
            f"User message: {user_input}\n\n"
            "Output ONLY the JSON object, no explanation:"
        )

        if stream_callback:
            import queue, threading
            chunk_queue: queue.Queue = queue.Queue()
            full_response = []

            def _stream_in_thread():
                try:
                    for chunk in self.llm_manager.call_with_multimodal_streaming(prompt, content_blocks, plugins, caller="assess_and_plan_multimodal"):
                        full_response.append(chunk)
                        chunk_queue.put(chunk)
                except Exception as e:
                    chunk_queue.put(e)
                chunk_queue.put(None)

            _ctx = contextvars.copy_context()
            thread = threading.Thread(target=lambda: _ctx.run(_stream_in_thread), daemon=True)
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
            response = (await self.llm_manager.call_with_multimodal_async(prompt, content_blocks, plugins, caller="assess_and_plan_multimodal")).strip()

        if not response:
            selected = self.llm_manager._selected_model or self.llm_manager._default_model or "auto"
            return {
                "action": "chat",
                "message": f"❌ โมเดล '{selected}' ส่งคำตอบกลับมาว่างเปล่า อาจไม่รองรับ multimodal input"
            }
        result = self._parse_unified_response(response, valid_model_ids, chat_only=chat_only, user_input=user_input)

        # If parsing failed and we're on free routing, retry with rotator's vision models
        if result.get("action") == "chat" and "ไม่ใช่ JSON" in result.get("message", ""):
            if self.llm_manager._is_free_routing():
                print(f"[assess_and_plan_multimodal] Response not JSON — retrying with rotator vision models", flush=True)
                try:
                    retry_response = self.llm_manager._get_rotator().call_with_multimodal(prompt, content_blocks, plugins, caller="assess_and_plan_multimodal:retry")
                    if retry_response and retry_response.strip():
                        retry_result = self._parse_unified_response(retry_response.strip(), valid_model_ids, chat_only=chat_only, user_input=user_input)
                        if retry_result.get("action") in ("plan", "create_agents", "ask", "tuning"):
                            return retry_result
                        print(f"[assess_and_plan_multimodal] Rotator retry also failed to produce valid JSON", flush=True)
                except Exception as retry_err:
                    print(f"[assess_and_plan_multimodal] Rotator retry error: {_sanitize_error(retry_err)}", flush=True)

        if chat_only and result.get("action") != "chat":
            result = {
                "action": "chat",
                "message": result.get("message") or "ฟังก์ชันนี้ต้องใช้ในโหมด Plan ครับ กรุณาสลับไปโหมด Plan เพื่อสร้างแผนงานหรือจัดการ agent",
            }
        return result

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
        return (await self.llm_manager.call_async(prompt, caller="info_response")).strip()

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
            # No cap — send full conversation history so Secretary can recall all past tasks (Issue #30)
            recent = conversation_history
            history_text = "\nConversation context:\n"
            for msg in recent:
                content = msg.get('content', '')
                history_text += f"- {msg.get('role', 'user')}: {content}\n"

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
            "- Capabilities of type 'tool' (generate_image, generate_video, text_to_speech, transcribe_audio, analyze_image, generate_document) give the agent external abilities\n"
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
        response = await self.llm_manager.call_async(prompt, caller="analyze")
        return self._parse_agent_specs(response, user_input)

    def check_resources(
        self, agent_spec: dict, registry: AgentRegistry, team_id: str | None = None
    ) -> dict:
        """
        เช็ค Registry ว่ามี Agent ที่ตรงกับ spec หรือไม่
        ลำดับการเช็ค:
        1. reuse_existing=True → หาจาก name
        2. name ตรงกับ agent เดิม → ใช้ของเดิม
        3. ไม่เจอ → create new (ไม่ fallback ด้วย role/tools substring —
           Secretary ตัดสินใจ reuse จากข้อมูลครบทุกฟิลด์แล้ว ถ้าไม่บอก reuse ก็สร้างใหม่)
        Returns: {"type": "existing", "agent": {...}} หรือ {"type": "create", "spec": {...}}
        """
        spec_name = agent_spec.get("name", "").strip()
        reuse_existing = agent_spec.get("reuse_existing", False)

        # 1) If LLM says reuse_existing, try name match only — no fallback
        if reuse_existing and spec_name:
            existing = registry.find_by_name(spec_name, team_id=team_id)
            if existing and not existing.get("is_manager"):
                return {"type": "existing", "agent": existing}
            # Not found by name — don't fallback, create new
            return {"type": "create", "spec": agent_spec}

        # 2) If name matches an existing agent — only when reuse_existing is not explicitly False
        if spec_name and reuse_existing is not False:
            existing = registry.find_by_name(spec_name, team_id=team_id)
            if existing and not existing.get("is_manager"):
                return {"type": "existing", "agent": existing}

        # 3) Secretary didn't request reuse — create new agent.
        # Removed role/tools substring fallback (find_idle_agent) because it matched
        # agents imprecisely (e.g. "writer" matched any writer role). Secretary now
        # receives full agent details (goal, persona, expertise, etc.) and decides
        # reuse explicitly via reuse_existing=true.
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
                        "output_format": "",
                        "quality_criteria": "",
                        "review_iterations": None,
                        "max_iter": None,
                        "max_retry_limit": None,
                        "allow_delegation": False,
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



