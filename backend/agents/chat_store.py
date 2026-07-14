"""ChatStore — JSON-backed chat session persistence."""

import json
import uuid
from datetime import datetime
from backend.globals import CHAT_SESSIONS_FILE, resolve_data_path

class ChatStore:
    """เก็บประวัติแชทหลาย session ลง JSON file"""

    def __init__(self, filepath: str = CHAT_SESSIONS_FILE, user_id: str | None = None):
        if user_id:
            filepath = resolve_data_path("chat_sessions.json", user_id)
        self.filepath = filepath
        self.sessions: list[dict] = []
        self._load()

    def _load(self):
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                self.sessions = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.sessions = []

    def _save(self):
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(self.sessions, f, ensure_ascii=False, indent=2)

    def create_session(self, title: str = "New Chat", team_id: str | None = None) -> dict:
        session = {
            "id": str(uuid.uuid4())[:8],
            "title": title,
            "team_id": team_id,
            "messages": [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        self.sessions.append(session)
        self._save()
        return session

    def get_session(self, session_id: str) -> dict | None:
        for s in self.sessions:
            if s.get("id") == session_id:
                return s
        return None

    def add_message(self, session_id: str, message: dict):
        session = self.get_session(session_id)
        if session:
            session["messages"].append(message)
            session["updated_at"] = datetime.now().isoformat()
            # Auto-title from first user message
            if session["title"] == "New Chat" and message.get("role") == "user":
                title = message.get("content", "")[:40]
                if len(message.get("content", "")) > 40:
                    title += "..."
                session["title"] = title
            self._save()

    def rename_session(self, session_id: str, title: str) -> dict | None:
        session = self.get_session(session_id)
        if session:
            session["title"] = title
            session["updated_at"] = datetime.now().isoformat()
            self._save()
            return session
        return None

    def delete_session(self, session_id: str) -> bool:
        original_len = len(self.sessions)
        self.sessions = [s for s in self.sessions if s.get("id") != session_id]
        if len(self.sessions) < original_len:
            self._save()
            return True
        return False

    def delete_sessions_by_team(self, team_id: str) -> int:
        original_len = len(self.sessions)
        self.sessions = [s for s in self.sessions if s.get("team_id") != team_id]
        deleted = original_len - len(self.sessions)
        if deleted > 0:
            self._save()
        return deleted

    def list_sessions(self, team_id: str | None = None, include_unassigned: bool = False) -> list[dict]:
        sessions = self.sessions
        if team_id is not None:
            if include_unassigned:
                sessions = [s for s in sessions if s.get("team_id") == team_id or s.get("team_id") is None]
            else:
                sessions = [s for s in sessions if s.get("team_id") == team_id]
        return sorted(sessions, key=lambda s: s.get("updated_at", ""), reverse=True)

    def save_canvas_state(self, session_id: str, canvas_state: dict):
        """Save canvas state (nodes + edges) for a session"""
        session = self.get_session(session_id)
        if session:
            session["canvas_state"] = canvas_state
            session["updated_at"] = datetime.now().isoformat()
            self._save()

    def get_canvas_state(self, session_id: str) -> dict | None:
        """Get canvas state for a session"""
        session = self.get_session(session_id)
        if session:
            return session.get("canvas_state")
        return None

    def save_settings(self, session_id: str, settings: dict):
        """Save user settings (selected_model, force_tier, etc.) for a session"""
        session = self.get_session(session_id)
        if session:
            session["settings"] = settings
            session["updated_at"] = datetime.now().isoformat()
            self._save()

    def get_settings(self, session_id: str) -> dict:
        """Get user settings for a session"""
        session = self.get_session(session_id)
        if session:
            return session.get("settings", {})
        return {}


