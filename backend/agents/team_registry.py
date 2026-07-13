"""TeamRegistry — JSON-backed team registry (CRUD)."""

import json
import uuid
from datetime import datetime
from backend.globals import TEAM_REGISTRY_FILE, resolve_data_path


class TeamRegistry:
    """คลาสสำหรับเก็บข้อมูล Team ทั้งหมด"""

    def __init__(self, filepath: str = TEAM_REGISTRY_FILE, user_id: str | None = None):
        if user_id:
            filepath = resolve_data_path("team_registry.json", user_id)
        self.filepath = filepath
        self.teams: list[dict] = []
        self._load()

    def _load(self):
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                self.teams = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.teams = []

    def _save(self):
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(self.teams, f, ensure_ascii=False, indent=2)

    def create_team(self, name: str, description: str = "", manager_model: str = "auto") -> dict:
        team = {
            "id": str(uuid.uuid4())[:8],
            "name": name,
            "description": description,
            "manager_model": manager_model,
            "agent_ids": [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        self.teams.append(team)
        self._save()
        return team

    def get_team(self, team_id: str) -> dict | None:
        for t in self.teams:
            if t.get("id") == team_id:
                return t
        return None

    def update_team(self, team_id: str, fields: dict) -> bool:
        team = self.get_team(team_id)
        if not team:
            return False
        for key in ("name", "description", "manager_model", "agent_ids"):
            if key in fields:
                team[key] = fields[key]
        team["updated_at"] = datetime.now().isoformat()
        self._save()
        return True

    def delete_team(self, team_id: str) -> bool:
        original_len = len(self.teams)
        self.teams = [t for t in self.teams if t.get("id") != team_id]
        if len(self.teams) < original_len:
            self._save()
            return True
        return False

    def list_teams(self) -> list[dict]:
        return sorted(self.teams, key=lambda t: t.get("created_at", ""), reverse=True)

    def add_agent(self, team_id: str, agent_id: str) -> bool:
        team = self.get_team(team_id)
        if not team:
            return False
        if agent_id not in team.get("agent_ids", []):
            team.setdefault("agent_ids", []).append(agent_id)
            team["updated_at"] = datetime.now().isoformat()
            self._save()
        return True

    def remove_agent(self, team_id: str, agent_id: str) -> bool:
        team = self.get_team(team_id)
        if not team:
            return False
        ids = team.get("agent_ids", [])
        if agent_id in ids:
            ids.remove(agent_id)
            team["updated_at"] = datetime.now().isoformat()
            self._save()
            return True
        return False
