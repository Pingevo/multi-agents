"""AgentRegistry — JSON-backed agent registry (single source of truth)."""

import json
import uuid
from datetime import datetime
from backend.globals import AGENT_REGISTRY_FILE, resolve_data_path

class AgentRegistry:
    """คลาสสำหรับเก็บข้อมูล Agent ทั้งหมด (ID, Name, Role, Persona, Status)"""

    def __init__(self, filepath: str = AGENT_REGISTRY_FILE, user_id: str | None = None):
        if user_id:
            filepath = resolve_data_path("agent_registry.json", user_id)
        self.filepath = filepath
        self.agents: list[dict] = []
        self._load()

    def _load(self):
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                self.agents = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.agents = []

    def _save(self):
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(self.agents, f, ensure_ascii=False, indent=2)

    def _next_agent_number(self, role: str) -> int:
        """Auto-increment agent number per role: Creative Writer #1, #2, ..."""
        count = 0
        role_lower = role.lower() if role else ""
        for a in self.agents:
            if role_lower and role_lower in a.get("role", "").lower():
                count += 1
        return count + 1

    def add_agent(self, spec: dict) -> dict:
        role = spec.get("role", "")
        # Auto-generate name as [Role] #N if not provided or generic
        name = spec.get("name", "")
        if not name or name == "Unnamed":
            num = self._next_agent_number(role)
            name = f"{role} #{num}" if role else "Unnamed"

        agent = {
            "id": str(uuid.uuid4())[:8],
            "name": name,
            "role": role,
            "goal": spec.get("goal", ""),
            "persona": spec.get("backstory", spec.get("persona", "")),
            "personality": spec.get("personality", {
                "tone": "",
                "communication_style": "",
                "language": "",
            }),
            "expertise": spec.get("expertise", []),
            "brand_context": spec.get("brand_context", {
                "brand_name": "",
                "guidelines": "",
                "target_audience": "",
            }),
            "learnings": spec.get("learnings", []),
            "tools": spec.get("tools", []),
            "depends_on": spec.get("depends_on", []),
            "model": spec.get("model", ""),
            "team_id": spec.get("team_id", None),
            "is_manager": spec.get("is_manager", False),
            "status": "Idle",
            "created_at": datetime.now().isoformat(),
            "last_used_at": None,
        }
        self.agents.append(agent)
        self._save()
        return agent

    def find_idle_agent(self, required_role: str, required_tools: list[str]) -> dict | None:
        required_role_lower = required_role.lower() if required_role else ""
        for agent in self.agents:
            if agent.get("status") != "Idle":
                continue
            # 1) Exact tools match has highest priority
            if required_tools and all(t in agent.get("tools", []) for t in required_tools):
                return agent
            # 2) Role keyword match
            if required_role_lower and required_role_lower in agent.get("role", "").lower():
                return agent
        return None

    def get_by_id(self, agent_id: str) -> dict | None:
        for agent in self.agents:
            if agent.get("id") == agent_id:
                return agent
        return None

    def update_status(self, agent_id: str, status: str) -> bool:
        for agent in self.agents:
            if agent.get("id") == agent_id:
                agent["status"] = status
                if status == "Busy":
                    agent["last_used_at"] = datetime.now().isoformat()
                self._save()
                return True
        return False

    def update_agent(self, agent_id: str, fields: dict) -> bool:
        for agent in self.agents:
            if agent.get("id") == agent_id:
                for key in ("name", "role", "goal", "persona", "personality",
                            "expertise", "brand_context", "learnings",
                            "tools", "model", "team_id"):
                    if key in fields:
                        agent[key] = fields[key]
                self._save()
                return True
        return False

    def delete_agent(self, agent_id: str) -> bool:
        original_len = len(self.agents)
        self.agents = [a for a in self.agents if a.get("id") != agent_id]
        if len(self.agents) < original_len:
            self._save()
            return True
        return False

    def list_agents(self, team_id: str | None = None) -> list[dict]:
        if team_id is None:
            return self.agents
        return [a for a in self.agents if a.get("team_id") == team_id]

    def to_spec(self, agent: dict) -> dict:
        """แปลงข้อมูล Agent ในทะเบียนให้เป็น spec ที่ AgentFactory ใช้ได้"""
        return {
            "id": agent.get("id"),
            "name": agent.get("name", "Unnamed"),
            "role": agent.get("role", ""),
            "goal": agent.get("goal", agent.get("role", "")),
            "backstory": agent.get("persona", ""),
            "personality": agent.get("personality", {}),
            "expertise": agent.get("expertise", []),
            "brand_context": agent.get("brand_context", {}),
            "learnings": agent.get("learnings", []),
            "tools": agent.get("tools", []),
            "model": agent.get("model", ""),
            "task_description": agent.get("last_task", ""),
            "depends_on": agent.get("depends_on", []),
            "team_id": agent.get("team_id"),
        }

    def add_learning(self, agent_id: str, learning: dict) -> bool:
        """Add a learning entry to an agent's learnings list (keeps last 10)."""
        for agent in self.agents:
            if agent.get("id") == agent_id:
                learnings = agent.get("learnings", [])
                learnings.append(learning)
                agent["learnings"] = learnings[-10:]
                self._save()
                return True
        return False

    def to_markdown_table(self) -> str:
        if not self.agents:
            return "_ยังไม่มี Agent ในทะเบียน_"
        lines = [
            "| ID | Name | Role | Status | Tools | Expertise |",
            "|---|---|---|---|---|---|",
        ]
        for a in self.agents:
            status = "🟢 Idle" if a.get("status") == "Idle" else "🔴 Busy"
            tools = ", ".join(a.get("tools", [])) if a.get("tools") else "-"
            name = a.get("name", "")[:25]
            role = a.get("role", "")[:35]
            expertise = ", ".join(a.get("expertise", [])[:3]) if a.get("expertise") else "-"
            lines.append(f"| {a.get('id', '')} | {name} | {role} | {status} | {tools} | {expertise} |")
        return "\n".join(lines)


