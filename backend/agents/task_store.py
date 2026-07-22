"""TaskStore — JSON-backed task persistence, separated from chat sessions."""

import json
import uuid
from datetime import datetime
from backend.globals import TASK_REGISTRY_FILE, resolve_data_path

class TaskStore:
    """เก็บประวัติ Task ลง JSON file — แยกจาก chat sessions"""

    def __init__(self, filepath: str = TASK_REGISTRY_FILE, user_id: str | None = None):
        if user_id:
            filepath = resolve_data_path("task_registry.json", user_id)
        self.filepath = filepath
        self.tasks: list[dict] = []
        self._load()

    def _load(self):
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                self.tasks = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.tasks = []

    def _save(self):
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(self.tasks, f, ensure_ascii=False, indent=2)

    def add_task(self, task: dict) -> dict:
        if "id" not in task:
            task["id"] = f"task_{uuid.uuid4().hex[:8]}"
        task.setdefault("status", "draft")
        task.setdefault("created_at", datetime.now().isoformat())
        self.tasks.append(task)
        self._save()
        return task

    def get_task(self, task_id: str) -> dict | None:
        for t in self.tasks:
            if t.get("id") == task_id:
                return t
        return None

    def update_task(self, task_id: str, **kwargs) -> dict | None:
        for t in self.tasks:
            if t.get("id") == task_id:
                t.update(kwargs)
                if kwargs.get("status") == "done":
                    t["done_at"] = datetime.now().isoformat()
                self._save()
                return t
        return None

    def list_tasks(self) -> list[dict]:
        return self.tasks

    def get_tasks_by_team(self, team_id: str) -> list[dict]:
        return [
            t for t in self.tasks
            if t.get("team_id") == team_id
            and not (not t.get("session_id") and t.get("status") in ("complete", "done"))
        ]

    def get_tasks_by_session(self, session_id: str) -> list[dict]:
        return [t for t in self.tasks if t.get("session_id") == session_id]

    def delete_task(self, task_id: str) -> bool:
        original_len = len(self.tasks)
        self.tasks = [t for t in self.tasks if t.get("id") != task_id]
        if len(self.tasks) < original_len:
            self._save()
            return True
        return False

    def delete_tasks_by_team(self, team_id: str) -> int:
        before = len(self.tasks)
        self.tasks = [t for t in self.tasks if t.get("team_id") != team_id]
        deleted = before - len(self.tasks)
        if deleted > 0:
            self._save()
        return deleted

    def delete_tasks_by_session(self, session_id: str) -> int:
        before = len(self.tasks)
        self.tasks = [t for t in self.tasks if t.get("session_id") != session_id]
        deleted = before - len(self.tasks)
        if deleted > 0:
            self._save()
        return deleted

    def detach_tasks_by_session(self, session_id: str) -> int:
        """Unset session_id on tasks from a deleted session, keeping the tasks themselves."""
        count = 0
        for t in self.tasks:
            if t.get("session_id") == session_id:
                t["session_id"] = None
                count += 1
        if count > 0:
            self._save()
        return count

    def clear_all(self):
        self.tasks = []
        self._save()


