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
        """Merge user settings into session — previously this REPLACED the entire
        settings dict, causing data loss (e.g., selecting a model would erase
        current_team_id, ai_image_model, etc.). Now merges to preserve existing keys."""
        session = self.get_session(session_id)
        if session:
            existing = session.get("settings", {})
            existing.update(settings)
            session["settings"] = existing
            session["updated_at"] = datetime.now().isoformat()
            self._save()

    def get_settings(self, session_id: str) -> dict:
        """Get user settings for a session"""
        session = self.get_session(session_id)
        if session:
            return session.get("settings", {})
        return {}

    _NOTIFICATION_TYPES = {"plan", "image_approval", "agent_review", "tuning_proposal"}
    _NOTIFICATION_MAX_AGE_DAYS = 15

    def get_all_notifications(self, team_id: str | None = None) -> list[dict]:
        """Get all notification-worthy messages across sessions.

        Returns messages with messageType in: plan, image_approval, agent_review, tuning_proposal.
        Each includes: session_id, session_title, timestamp, and all message fields.
        Filters out messages older than 15 days.
        """
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(days=self._NOTIFICATION_MAX_AGE_DAYS)
        results: list[dict] = []

        sessions = self.list_sessions(team_id=team_id, include_unassigned=True) if team_id else self.list_sessions()
        for session in sessions:
            sid = session.get("id", "")
            stitle = session.get("title", "")
            for msg in session.get("messages", []):
                msg_type = msg.get("messageType", "")
                if msg_type not in self._NOTIFICATION_TYPES:
                    continue
                # Parse timestamp — try multiple fields
                ts_str = msg.get("timestamp") or msg.get("createdAt") or ""
                if isinstance(ts_str, (int, float)):
                    ts = datetime.fromtimestamp(ts_str / 1000 if ts_str > 1e12 else ts_str)
                elif isinstance(ts_str, str) and ts_str:
                    try:
                        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00").replace("+00:00", ""))
                    except ValueError:
                        ts = datetime.now()
                else:
                    ts = datetime.now()
                if ts < cutoff:
                    continue
                entry = dict(msg)
                entry["sessionId"] = sid
                entry["sessionTitle"] = stitle
                entry["timestamp"] = ts.isoformat()
                results.append(entry)

        results.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return results

    # ============================================================
    # Pending media persistence — survives backend restart
    # Without this, approve/retry buttons on media approval cards
    # stop working after restart because pending_media is in-memory only
    # ============================================================

    def save_pending_media(self, session_id: str, approval_id: str, pending_data: dict):
        """Persist pending media approval data so it survives backend restart."""
        session = self.get_session(session_id)
        if session:
            if "pending_media" not in session:
                session["pending_media"] = {}
            session["pending_media"][approval_id] = pending_data
            session["updated_at"] = datetime.now().isoformat()
            self._save()

    def get_pending_media(self, session_id: str, approval_id: str) -> dict | None:
        """Retrieve pending media data by approval_id — used as fallback when cl.user_session is empty."""
        session = self.get_session(session_id)
        if session:
            return session.get("pending_media", {}).get(approval_id)
        return None

    def get_all_pending_media(self, session_id: str) -> dict[str, dict]:
        """Return all pending media for a session — used to restore on on_chat_start/switch_chat."""
        session = self.get_session(session_id)
        if session:
            return session.get("pending_media", {})
        return {}

    def clear_pending_media(self, session_id: str, approval_id: str):
        """Remove pending media after approve/retry completes — prevents stale data buildup."""
        session = self.get_session(session_id)
        if session and "pending_media" in session:
            session["pending_media"].pop(approval_id, None)
            session["updated_at"] = datetime.now().isoformat()
            self._save()

    def clear_all_pending_media(self, session_id: str):
        """Clear ALL pending media for a session — used on new task start to prevent
        stale approvals from previous runs accumulating and showing as 40+ pending items."""
        session = self.get_session(session_id)
        if session and "pending_media" in session:
            session["pending_media"] = {}
            session["updated_at"] = datetime.now().isoformat()
            self._save()

    # ============================================================
    # Instruction history — user feedback given when rejecting media
    # Stored per approval_id so the frontend can display the history of
    # instructions the user gave to refine the media prompt.
    # ============================================================

    def append_instruction_history(self, session_id: str, approval_id: str, instruction: str):
        """Append a user instruction to the history for a given approval_id.

        Called when the user rejects media with feedback. The instruction is
        stored both in a per-approval_id map AND in the corresponding
        image_approval message so it can be displayed in the UI and restored
        after refresh.
        """
        if not instruction:
            return
        session = self.get_session(session_id)
        if not session:
            return
        history_map = session.setdefault("instruction_history", {})
        history = history_map.setdefault(approval_id, [])
        history.append(instruction)
        # Also update the image_approval message so instructionHistory is
        # restored when messages are loaded after a page refresh
        for msg in session.get("messages", []):
            if msg.get("messageType") == "image_approval" and msg.get("approvalId") == approval_id:
                msg["instructionHistory"] = list(history)
                break
        session["updated_at"] = datetime.now().isoformat()
        self._save()

    def get_instruction_history(self, session_id: str, approval_id: str) -> list[str]:
        """Return the list of user instructions for a given approval_id."""
        session = self.get_session(session_id)
        if not session:
            return []
        return session.get("instruction_history", {}).get(approval_id, [])

    def get_all_instruction_history(self, session_id: str) -> dict[str, list[str]]:
        """Return all instruction history for a session — used to restore on chat start/switch."""
        session = self.get_session(session_id)
        if not session:
            return {}
        return session.get("instruction_history", {})

    # ============================================================
    # Media tool results persistence — survives backend restart
    # Needed to rebuild approval cards if they're lost from memory
    # ============================================================

    def save_media_tool_results(self, session_id: str, results: list[dict]):
        """Persist media tool results so approval cards can be rebuilt after restart."""
        session = self.get_session(session_id)
        if session:
            session["media_tool_results"] = results
            session["updated_at"] = datetime.now().isoformat()
            self._save()

    def get_media_tool_results(self, session_id: str) -> list[dict]:
        """Retrieve saved media tool results for a session."""
        session = self.get_session(session_id)
        if session:
            return session.get("media_tool_results", [])
        return []

    def clear_media_tool_results(self, session_id: str):
        """Clear media tool results after all approvals are processed."""
        session = self.get_session(session_id)
        if session:
            session.pop("media_tool_results", None)
            session["updated_at"] = datetime.now().isoformat()
            self._save()

    # ============================================================
    # Tuning proposal persistence — survives backend restart
    # ============================================================

    def save_tuning_proposal(self, session_id: str, proposals: list[dict]):
        """Persist tuning proposals so they survive restart."""
        session = self.get_session(session_id)
        if session:
            session["pending_tuning_proposal"] = proposals
            session["updated_at"] = datetime.now().isoformat()
            self._save()

    def get_tuning_proposal(self, session_id: str) -> list[dict] | None:
        """Retrieve saved tuning proposals."""
        session = self.get_session(session_id)
        if session:
            return session.get("pending_tuning_proposal")
        return None

    def clear_tuning_proposal(self, session_id: str):
        """Clear tuning proposals after user accepts/rejects."""
        session = self.get_session(session_id)
        if session:
            session.pop("pending_tuning_proposal", None)
            session["updated_at"] = datetime.now().isoformat()
            self._save()


