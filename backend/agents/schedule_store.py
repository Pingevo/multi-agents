"""Scheduled task store — persist recurring task definitions."""

import json
from datetime import datetime
from pathlib import Path

from backend.globals import resolve_data_path


class ScheduledTaskStore:
    """Store scheduled/recurring tasks for a user."""

    def __init__(self, user_id: str = "default"):
        self.user_id = user_id
        # Use per-user directory (data/users/{uid}/) instead of flat file in data/
        # — prevents cross-user data leakage when multiple users share the same server.
        self.file = Path(resolve_data_path("scheduled_tasks.json", user_id=user_id))
        self.file.parent.mkdir(parents=True, exist_ok=True)
        self.tasks: list[dict] = []
        self._load()

    def _migrate_old_path(self):
        """One-time migration: move data/scheduled_tasks_{user_id}.json to new per-user path."""
        old_file = Path(f"data/scheduled_tasks_{self.user_id}.json")
        if old_file.exists() and not self.file.exists():
            self.file.parent.mkdir(parents=True, exist_ok=True)
            old_file.rename(self.file)
            print(f"[ScheduledTaskStore] Migrated {old_file} -> {self.file}", flush=True)

    def _load(self):
        self._migrate_old_path()
        if self.file.exists():
            try:
                self.tasks = json.loads(self.file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self.tasks = []

    def _save(self):
        self.file.write_text(json.dumps(self.tasks, ensure_ascii=False, indent=2), encoding="utf-8")

    def list_scheduled(self) -> list[dict]:
        return self.tasks

    def add_scheduled(self, name: str, prompt: str, interval_hours: float, mode: str = "plan", team_id: str = "") -> dict:
        task = {
            "id": f"sched_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "name": name,
            "prompt": prompt,
            "interval_hours": interval_hours,
            "mode": mode,
            "team_id": team_id,
            "last_run": None,
            "next_run": datetime.now().isoformat(),
            "created_at": datetime.now().isoformat(),
            "active": True,
        }
        self.tasks.append(task)
        self._save()
        return task

    def delete_scheduled(self, task_id: str) -> bool:
        before = len(self.tasks)
        self.tasks = [t for t in self.tasks if t.get("id") != task_id]
        if len(self.tasks) < before:
            self._save()
            return True
        return False

    def delete_by_team(self, team_id: str) -> int:
        before = len(self.tasks)
        self.tasks = [t for t in self.tasks if t.get("team_id") != team_id]
        deleted = before - len(self.tasks)
        if deleted > 0:
            self._save()
        return deleted

    def toggle_active(self, task_id: str) -> bool:
        for t in self.tasks:
            if t.get("id") == task_id:
                t["active"] = not t.get("active", True)
                self._save()
                return t["active"]
        return False

    def mark_run(self, task_id: str):
        from datetime import datetime as dt, timedelta
        for t in self.tasks:
            if t.get("id") == task_id:
                now = dt.now()
                t["last_run"] = now.isoformat()
                t["next_run"] = (now + timedelta(hours=t.get("interval_hours", 24))).isoformat()
                self._save()
                break

    def get_due_tasks(self) -> list[dict]:
        """Return tasks that are due to run."""
        from datetime import datetime as dt
        now = dt.now()
        due = []
        for t in self.tasks:
            if not t.get("active", True):
                continue
            next_run = t.get("next_run")
            if not next_run:
                due.append(t)
                continue
            try:
                next_dt = dt.fromisoformat(next_run)
                if now >= next_dt:
                    due.append(t)
            except (ValueError, TypeError):
                due.append(t)
        return due
