"""BrandRegistry — JSON-backed brand registry (CRUD).

Single source of truth for brands owned by a user. Each brand holds
brand_context (tone, target_audience, guidelines, forbidden_words) so that
all teams under the same brand share one voice. Persists to
brand_registry.json (per-user when user_id is provided).

Issue: #136 — BrandRegistry + Brand entity
ADR: docs/adr/0005-brand-entity.md
"""

import json
import uuid
from datetime import datetime

from backend.globals import BRAND_REGISTRY_FILE, resolve_data_path


DEFAULT_BRAND_CONTEXT = {
    "tone": "",
    "target_audience": "",
    "guidelines": "",
    "forbidden_words": [],
}


class BrandRegistry:
    """คลาสสำหรับเก็บข้อมูล Brand ทั้งหมดของ user"""

    def __init__(self, filepath: str = BRAND_REGISTRY_FILE, user_id: str | None = None):
        if user_id:
            filepath = resolve_data_path("brand_registry.json", user_id)
        self.filepath = filepath
        self.brands: list[dict] = []
        self._load()

    def _load(self):
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                self.brands = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.brands = []

    def _save(self):
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(self.brands, f, ensure_ascii=False, indent=2)

    def create_brand(self, name: str, brand_context: dict | None = None) -> dict:
        ctx = dict(DEFAULT_BRAND_CONTEXT)
        if brand_context:
            ctx.update(brand_context)
        brand = {
            "id": str(uuid.uuid4())[:8],
            "name": name,
            "brand_context": ctx,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        self.brands.append(brand)
        self._save()
        return brand

    def get_brand(self, brand_id: str) -> dict | None:
        for b in self.brands:
            if b.get("id") == brand_id:
                return b
        return None

    def update_brand(self, brand_id: str, fields: dict) -> bool:
        brand = self.get_brand(brand_id)
        if not brand:
            return False
        for key in ("name", "brand_context"):
            if key in fields:
                brand[key] = fields[key]
        brand["updated_at"] = datetime.now().isoformat()
        self._save()
        return True

    def delete_brand(self, brand_id: str) -> bool:
        original_len = len(self.brands)
        self.brands = [b for b in self.brands if b.get("id") != brand_id]
        if len(self.brands) < original_len:
            self._save()
            return True
        return False

    def list_brands(self) -> list[dict]:
        return sorted(self.brands, key=lambda b: b.get("created_at", ""), reverse=True)
