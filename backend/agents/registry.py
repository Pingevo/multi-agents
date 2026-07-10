"""AgentRegistry — JSON-backed agent registry (single source of truth)."""

import json
import uuid
from datetime import datetime
from backend.globals import AGENT_REGISTRY_FILE

class AgentRegistry:
    """คลาสสำหรับเก็บข้อมูล Agent ทั้งหมด (ID, Name, Role, Persona, Status)"""

    def __init__(self, filepath: str = AGENT_REGISTRY_FILE):
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

    def add_agent(self, spec: dict) -> dict:
        agent = {
            "id": str(uuid.uuid4())[:8],
            "name": spec.get("name", "Unnamed"),
            "role": spec.get("role", ""),
            "goal": spec.get("goal", ""),
            "persona": spec.get("backstory", ""),
            "tools": spec.get("tools", []),
            "depends_on": spec.get("depends_on", []),
            "model": spec.get("model", ""),
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
                for key in ("name", "role", "goal", "persona", "tools", "model"):
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

    def list_agents(self) -> list[dict]:
        return self.agents

    def to_spec(self, agent: dict) -> dict:
        """แปลงข้อมูล Agent ในทะเบียนให้เป็น spec ที่ AgentFactory ใช้ได้"""
        return {
            "id": agent.get("id"),
            "name": agent.get("name", "Unnamed"),
            "role": agent.get("role", ""),
            "goal": agent.get("goal", agent.get("role", "")),
            "backstory": agent.get("persona", ""),
            "tools": agent.get("tools", []),
            "model": agent.get("model", ""),
            "task_description": agent.get("last_task", ""),
            "depends_on": agent.get("depends_on", []),
        }

    def to_markdown_table(self) -> str:
        if not self.agents:
            return "_ยังไม่มี Agent ในทะเบียน_"
        lines = [
            "| ID | Name | Role | Status | Tools |",
            "|---|---|---|---|---|",
        ]
        for a in self.agents:
            status = "🟢 Idle" if a.get("status") == "Idle" else "🔴 Busy"
            tools = ", ".join(a.get("tools", [])) if a.get("tools") else "-"
            name = a.get("name", "")[:25]
            role = a.get("role", "")[:35]
            lines.append(f"| {a.get('id', '')} | {name} | {role} | {status} | {tools} |")
        return "\n".join(lines)


