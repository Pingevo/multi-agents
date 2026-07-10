"""TaskStore — JSON-backed task persistence."""

import json
import uuid
from datetime import datetime
from backend.globals import TASK_REGISTRY_FILE

class TaskStore:
    """เก็บประวัติ Task ลง JSON file เพื่อไม่ให้หายเมื่อ refresh"""

    def __init__(self, filepath: str = TASK_REGISTRY_FILE):
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
                self._save()
                return t
        return None

    def list_tasks(self) -> list[dict]:
        return self.tasks

    def delete_task(self, task_id: str) -> bool:
        original_len = len(self.tasks)
        self.tasks = [t for t in self.tasks if t.get("id") != task_id]
        if len(self.tasks) < original_len:
            self._save()
            return True
        return False

    def clear_all(self):
        self.tasks = []
        self._save()


