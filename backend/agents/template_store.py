"""Task template store — save and load reusable task prompts."""

import json
import os
from datetime import datetime
from pathlib import Path


class TaskTemplateStore:
    """Persist task templates so users can reuse common prompts."""

    def __init__(self, user_id: str = "default"):
        self.user_id = user_id
        self.file = Path(f"data/task_templates_{user_id}.json")
        self.file.parent.mkdir(parents=True, exist_ok=True)
        self.templates: list[dict] = []
        self._load()

    def _load(self):
        if self.file.exists():
            try:
                self.templates = json.loads(self.file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self.templates = []

    def _save(self):
        self.file.write_text(json.dumps(self.templates, ensure_ascii=False, indent=2), encoding="utf-8")

    def list_templates(self) -> list[dict]:
        return self.templates

    def add_template(self, name: str, prompt: str, mode: str = "plan") -> dict:
        template = {
            "id": f"tpl_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "name": name,
            "prompt": prompt,
            "mode": mode,
            "created_at": datetime.now().isoformat(),
        }
        self.templates.append(template)
        self._save()
        return template

    def delete_template(self, template_id: str) -> bool:
        before = len(self.templates)
        self.templates = [t for t in self.templates if t.get("id") != template_id]
        if len(self.templates) < before:
            self._save()
            return True
        return False
