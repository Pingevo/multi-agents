"""HistoryStore — JSON-backed per-task audit log persistence."""

import json
from datetime import datetime
from backend.globals import resolve_data_path


class HistoryStore:
    """เก็บประวัติการทำงานแบบละเอียดลง JSON file ราย task"""

    def __init__(self, user_id: str | None = None):
        self.filepath = resolve_data_path("history_log.json", user_id)
        self.logs: list[dict] = []
        self._load()

    def _load(self):
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                self.logs = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.logs = []

    def _save(self):
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(self.logs, f, ensure_ascii=False, indent=2)

    def add_entry(self, task_id: str, task_title: str, actor: str, action: str, target: str = "") -> dict:
        entry = {
            "time": datetime.now().strftime("%H:%M"),
            "actor": actor,
            "action": action,
            "target": target,
        }
        for log in self.logs:
            if log.get("task_id") == task_id:
                log["entries"].append(entry)
                self._save()
                return entry
        self.logs.append({
            "task_id": task_id,
            "task_title": task_title,
            "created_at": datetime.now().isoformat(),
            "entries": [entry],
        })
        self._save()
        return entry

    def list_history(self, limit: int = 20) -> list[dict]:
        return self.logs[-limit:]

    def clear_all(self):
        self.logs = []
        self._save()
