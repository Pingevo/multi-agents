"""SessionManager — JSON-backed session token management at data/sessions.json."""

import json
import os
import secrets
from datetime import datetime, timedelta


class SessionManager:
    """สร้างและ verify session token — เก็บใน JSON file"""

    SESSION_TTL_HOURS = 24 * 7  # 7 days

    def __init__(self, filepath: str | None = None):
        if filepath is None:
            data_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "data",
            )
            os.makedirs(data_dir, exist_ok=True)
            filepath = os.path.join(data_dir, "sessions.json")
        self.filepath = filepath
        self.sessions: dict[str, dict] = {}
        self._load()

    def _load(self):
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                self.sessions = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.sessions = {}

    def _save(self):
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(self.sessions, f, ensure_ascii=False, indent=2)

    def create_session(self, user_id: str) -> str:
        """Create a new session token for a user. Returns the token."""
        token = secrets.token_urlsafe(32)
        self.sessions[token] = {
            "user_id": user_id,
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(hours=self.SESSION_TTL_HOURS)).isoformat(),
        }
        self._save()
        return token

    def verify_token(self, token: str) -> str | None:
        """Verify a session token. Returns user_id if valid, None if invalid/expired."""
        if not token:
            return None
        session = self.sessions.get(token)
        if not session:
            return None
        expires_at = datetime.fromisoformat(session.get("expires_at", "2000-01-01T00:00:00"))
        if datetime.now() > expires_at:
            del self.sessions[token]
            self._save()
            return None
        return session.get("user_id")

    def revoke_session(self, token: str):
        """Revoke a session token."""
        if token in self.sessions:
            del self.sessions[token]
            self._save()

    def revoke_all_for_user(self, user_id: str):
        """Revoke all sessions for a user."""
        to_remove = [t for t, s in self.sessions.items() if s.get("user_id") == user_id]
        for t in to_remove:
            del self.sessions[t]
        if to_remove:
            self._save()
