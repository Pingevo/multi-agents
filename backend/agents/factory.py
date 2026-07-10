"""AgentFactory — creates CrewAI agents and tasks."""

import chainlit as cl
from crewai import Agent, Task, Crew, Process, LLM
from backend.llm.manager import LLMManager
from backend.agents.capability import CapabilityRegistry, CapabilityResolver
from backend.agents.tool_registry import ToolRegistry
from backend.globals import _thread_local

class AgentFactory:
    """เสก Agent และ Task ใหม่ระหว่างรัน (Runtime)"""

    def __init__(self, llm_manager: LLMManager, tool_registry: ToolRegistry):
        self.llm_manager = llm_manager
        self.tool_registry = tool_registry
        self._cap_resolver = CapabilityResolver()

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

        return Agent(
            role=spec["role"],
            goal=spec["goal"],
            backstory=spec['backstory'],
            llm=llm,
            tools=tools,
            allow_delegation=False,
            verbose=True,
            max_iter=20,
            max_retry_limit=3,
        )

    def create_manager_agent(self, user_input: str, agent_specs: list[dict], model_id: str = "") -> Agent:
        agent_names = ", ".join(s.get("name", "Agent") for s in agent_specs)
        agent_roles = "; ".join(f"{s.get('name', 'Agent')} ({s.get('role', '')})" for s in agent_specs)

        if model_id:
            print(f"[AgentFactory] Manager assigned model: {model_id}")
            llm = self.llm_manager.build_llm_for_model(model_id)
        else:
            llm = self.llm_manager.get_llm()

        return Agent(
            role="Project Manager",
            goal=(
                f"Coordinate the team to accomplish: {user_input}\n"
                f"Available team members: {agent_roles}\n"
                "Delegate tasks efficiently, run independent tasks in parallel, "
                "and synthesize results into a final deliverable."
            ),
            backstory=(
                "You are an experienced project manager who coordinates teams effectively. "
                "You know when tasks can run in parallel and when one must wait for another. "
                "You ensure quality by reviewing each agent's output before moving forward."
            ),
            llm=llm,
            tools=[],
            allow_delegation=True,
            verbose=True,
            max_iter=25,
            max_retry_limit=3,
        )

    def create_task(self, agent: Agent, spec: dict, user_input: str) -> Task:
        tool_names = spec.get("tools", [])
        tool_instructions = ""
        cap_registry = CapabilityRegistry()
        for cap_name in tool_names:
            resolution = cap_registry.resolve(cap_name)
            if resolution and resolution["type"] == "tool":
                if cap_name == "generate_image":
                    tool_instructions += (
                        "\n\nIMPORTANT: You MUST call the generate_image tool with a detailed English prompt "
                        "that describes the visual you want to create. "
                        "Do NOT just describe the image in text — actually CALL the tool. "
                        "The prompt should be in English and visually descriptive. "
                        "Call the tool once per image you need to create — do not repeat the same call. "
                        "The user will review your prompt before generation happens — this is by design to control API costs."
                    )
                elif cap_name == "generate_video":
                    tool_instructions += (
                        "\n\nIMPORTANT: You MUST call the generate_video tool with a detailed English prompt "
                        "that describes the scene, camera movement, lighting, and mood. "
                        "Do NOT just describe the video in text — actually CALL the tool. "
                        "The prompt should be in English and cinematically descriptive. "
                        "Use duration parameter (2-15 seconds) to set clip length. "
                        "Call the tool once per video you need to create — do not repeat the same call. "
                        "The user will review your prompt before generation happens — this is by design to control API costs."
                    )
                elif cap_name == "search_web":
                    tool_instructions += (
                        "\n\nUse the search_web tool when you need current information or facts."
                    )

        attachment_ctx = cl.user_session.get("attachment_context")
        attachment_text = ""
        input_files = None
        if attachment_ctx:
            if attachment_ctx.get("text_content"):
                attachment_text = f"\n\nAttached file content:\n{attachment_ctx['text_content'][:5000]}\n"
            if attachment_ctx.get("context_text"):
                attachment_text += f"\nAttachment context: {attachment_ctx['context_text']}"
            crewai_files = cl.user_session.get("attachment_crewai_files")
            if crewai_files:
                input_files = crewai_files

        task_kwargs = {
            "description": (
                f"Context: A user requested: {user_input}\n\n"
                f"You are: {spec.get('name', 'Agent')} — {spec.get('role', '')}\n"
                f"Your task: {spec.get('task_description', '')}\n\n"
                "You are a worker agent in a multi-agent system. "
                "Your output will be collected and synthesized by a manager agent — it will NOT be shown directly to the user. "
                "Write your output as a report to the manager, not as a message to the user. "
                "Do not use conversational language (e.g., greetings, 'here are your...', 'please review'). "
                "Produce your work as a structured deliverable. "
                "Use your assigned tools when needed. "
                "Do not explain how things work internally."
                f"{tool_instructions}"
                f"{attachment_text}"
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
        return Task(**task_kwargs)



