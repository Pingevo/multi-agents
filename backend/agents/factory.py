"""AgentFactory — creates CrewAI agents and tasks."""

import chainlit as cl
from crewai import Agent, Task, Crew, Process, LLM
from backend.llm.manager import LLMManager
from backend.agents.capability import CapabilityRegistry, CapabilityResolver
from backend.agents.tool_registry import ToolRegistry
from backend.agents.templates import get_template_contract, detect_template_id
from backend.globals import _thread_local

class AgentFactory:
    """เสก Agent และ Task ใหม่ระหว่างรัน (Runtime)"""

    def __init__(self, llm_manager: LLMManager, tool_registry: ToolRegistry):
        self.llm_manager = llm_manager
        self.tool_registry = tool_registry
        self._cap_resolver = CapabilityResolver()

    def _build_agent_backstory(self, spec: dict) -> str:
        """Compose deep persona from personality, expertise, brand_context, learnings."""
        parts = []

        # Base identity
        name = spec.get("name", "Agent")
        role = spec.get("role", "")
        parts.append(f"You are {name}, a {role}.")

        # Original backstory (if any) — keep for backward compat
        backstory = spec.get("backstory", spec.get("persona", ""))
        if backstory and isinstance(backstory, str) and len(backstory) > 20:
            parts.append(backstory)

        # Personality
        p = spec.get("personality", {})
        if isinstance(p, dict):
            tone = p.get("tone", "")
            style = p.get("communication_style", "")
            lang = p.get("language", "")
            if tone:
                parts.append(f"Your tone is {tone}.")
            if style:
                parts.append(f"Communication style: {style}.")
            if lang:
                parts.append(f"Primary language: {lang}.")

        # Expertise (permanent skills)
        expertise = spec.get("expertise", [])
        if expertise and isinstance(expertise, list):
            parts.append(f"Your expertise: {', '.join(expertise)}.")

        # Brand context
        bc = spec.get("brand_context", {})
        if isinstance(bc, dict):
            brand_name = bc.get("brand_name", "")
            guidelines = bc.get("guidelines", "")
            audience = bc.get("target_audience", "")
            if brand_name:
                parts.append(f"You work for brand '{brand_name}'.")
            if guidelines:
                parts.append(f"Brand guidelines: {guidelines}")
            if audience:
                parts.append(f"Target audience: {audience}")

        # Learnings (last 5 — memory from past work)
        learnings = spec.get("learnings", [])
        if learnings and isinstance(learnings, list):
            recent = learnings[-5:]
            lessons = [l.get("lesson", str(l)) if isinstance(l, dict) else str(l) for l in recent]
            if lessons:
                parts.append("Lessons from past work:")
                for lesson in lessons:
                    parts.append(f"  - {lesson}")

        # Output format — user-specified format for agent output
        output_format = spec.get("output_format", "")
        if output_format:
            parts.append(f"You MUST format your output as: {output_format}")

        # Quality criteria — user-specified criteria for self-checking
        quality_criteria = spec.get("quality_criteria", "")
        if quality_criteria:
            parts.append(f"Your work must meet these quality criteria:\n{quality_criteria}")

        return "\n".join(parts)

    def create_agent(self, spec: dict, model_id: str = "") -> Agent:
        resolved = self._cap_resolver.assign_to_agent(
            spec.get("tools", []), spec
        )
        tools = []
        for tool_name in resolved["tools"]:
            tool = self.tool_registry.get(tool_name)
            if tool:
                tools.append(tool)

        if model_id:
            print(f"[AgentFactory] Agent {spec.get('name', '')} assigned model: {model_id}")
            llm = self.llm_manager.build_llm_for_model(model_id)
        else:
            llm = self.llm_manager.get_llm()

        backstory = self._build_agent_backstory(spec)

        return Agent(
            role=spec["role"],
            goal=spec["goal"],
            backstory=backstory,
            llm=llm,
            tools=tools,
            allow_delegation=spec.get("allow_delegation", False),
            verbose=True,
            max_iter=spec.get("max_iter") or 25,  # 0 = use CrewAI default
            max_retry_limit=spec.get("max_retry_limit") or 3,  # 0 = use CrewAI default
        )

    def create_task(self, agent: Agent, spec: dict, user_input: str, agent_memory: list[dict] | None = None) -> Task:
        tool_names = spec.get("tools", [])
        tool_instructions = ""
        cap_registry = CapabilityRegistry()
        for cap_name in tool_names:
            resolution = cap_registry.resolve(cap_name)
            if resolution and resolution["type"] == "tool":
                if cap_name == "generate_image":
                    tool_instructions += (
                        "\n\nCRITICAL: You MUST call the generate_image tool with a detailed English prompt "
                        "that describes the visual you want to create. "
                        "Do NOT write SVG, HTML, or any code/markup directly in your response — this is a FAILURE. "
                        "Do NOT just describe the image in text — actually CALL the tool. "
                        "The prompt should be in English and visually descriptive. "
                        "Call the tool once per image you need to create — do not repeat the same call. "
                        "The user will review your prompt before generation happens — this is by design to control API costs. "
                        "If you write SVG, HTML, or any markup instead of calling the tool, your output will be rejected."
                    )
                elif cap_name == "generate_video":
                    tool_instructions += (
                        "\n\nCRITICAL: You MUST call the generate_video tool with a detailed English prompt "
                        "that describes the scene, camera movement, lighting, and mood. "
                        "Do NOT write any code/markup directly in your response — this is a FAILURE. "
                        "Do NOT just describe the video in text — actually CALL the tool. "
                        "The prompt should be in English and cinematically descriptive. "
                        "Use duration parameter (2-15 seconds) to set clip length. "
                        "Call the tool once per video you need to create — do not repeat the same call. "
                        "The user will review your prompt before generation happens — this is by design to control API costs. "
                        "If you write any markup instead of calling the tool, your output will be rejected."
                    )
                elif cap_name == "generate_document":
                    tool_instructions += (
                        "\n\nIMPORTANT: You MUST call the generate_document tool to produce a downloadable file. "
                        "Do NOT paste long document content directly in your response text. "
                        "Pass the full content as the 'content' parameter and a filename as the 'filename' parameter. "
                        "The user will download the file — do not dump it in chat."
                    )

        attachment_ctx = cl.user_session.get("attachment_context")
        attachment_text = ""
        input_files = None
        if attachment_ctx:
            if attachment_ctx.get("text_content"):
                attachment_text = f"\n\nAttached file content:\n{attachment_ctx['text_content'][:50000]}\n"
            if attachment_ctx.get("context_text"):
                attachment_text += f"\nAttachment context: {attachment_ctx['context_text']}"
            crewai_files = cl.user_session.get("attachment_crewai_files")
            if crewai_files:
                input_files = crewai_files

        # Inject template-specific runtime contract if agent has a template_id
        template_id = spec.get("template_id", "")
        if not template_id:
            template_id = detect_template_id(spec.get("role", ""), spec.get("name", "")) or ""
        template_contract = ""
        if template_id:
            contract = get_template_contract(template_id)
            if contract:
                template_contract = f"\n\n{contract}"

        # Build self-check instruction for quality
        self_check = (
            "\n\nBefore submitting your work, do a self-check: "
            "Is the output complete? Does it match the requirements? "
            "Is the tone consistent with your persona? "
            "If something is missing, fix it before submitting."
        )

        # Build team context so each agent knows what others are doing
        team_context = ""
        all_specs = cl.user_session.get("current_agent_specs") or []
        if all_specs and len(all_specs) > 1:
            team_lines = []
            for s in all_specs:
                if s.get("name") == spec.get("name"):
                    continue
                team_lines.append(f"  - {s.get('name', 'Agent')}: {s.get('task_description', s.get('role', ''))[:120]}")
            if team_lines:
                team_context = f"\nYour team members are handling:\n" + "\n".join(team_lines) + "\n"

        # Build agent memory section from previous attempts (experiential memory)
        memory_text = ""
        if agent_memory:
            memory_lines = ["\n--- PREVIOUS ATTEMPTS ---"]
            for i, mem in enumerate(agent_memory):
                memory_lines.append(f"Attempt {i+1}:")
                prev_output = mem.get("output", "")[:3000]
                mem_feedback = mem.get("feedback", "")
                memory_lines.append(f"Output: {prev_output}")
                if mem_feedback:
                    memory_lines.append(f"Manager feedback: {mem_feedback}")
            memory_lines.append("--- END PREVIOUS ATTEMPTS ---")
            memory_lines.append("Address the feedback above in your new attempt. Do NOT repeat the same mistakes.")
            memory_text = "\n".join(memory_lines) + "\n"

        task_kwargs = {
            "description": (
                f"Context: A user requested: {user_input}\n\n"
                f"You are: {spec.get('name', 'Agent')} — {spec.get('role', '')}\n"
                f"Your task: {spec.get('task_description', '')}\n"
                f"{team_context}\n"
                f"{memory_text}"
                "Your deliverable must be EXACTLY what your task_description specifies. "
                "If it's not in your task_description, it's not your job — another team member is handling it. "
                "Your output will be reviewed by the user before downstream agents can proceed. "
                "Write your output as a structured deliverable. "
                "USE YOUR ASSIGNED TOOLS — do not describe what you would create, actually CALL the tools to produce output. "
                "Do not use conversational language (e.g., greetings, 'here are your...', 'please review'). "
                "Produce your work as a structured deliverable. "
                "Do not explain how things work internally."
                f"{tool_instructions}"
                f"{self_check}"
                f"{attachment_text}"
                f"{template_contract}"
            ),
            "agent": agent,
            "expected_output": (
                "A structured deliverable in the same language as the user's request. "
                "Report what you produced, what tools you used, and any relevant details. "
                "This is a report to the manager agent, not a message to the user."
            ),
        }
        if input_files:
            task_kwargs["input_files"] = input_files

        # Use agent's output_format as expected_output if specified
        output_format = spec.get("output_format", "")
        if output_format:
            task_kwargs["expected_output"] = output_format

        return Task(**task_kwargs)



