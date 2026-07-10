"""ModelCatalog — fetches and categorizes models from OpenRouter."""

import requests
from backend.utils import _sanitize_error

class ModelCatalog:
    """Fetches and categorizes models from OpenRouter for user selection.

    Provides:
    - recommended: top models grouped by category (chat, reasoning, coding, vision, fast)
    - search: filter by keyword
    - all: full list with metadata
    """

    _CATEGORY_KEYWORDS = {
        "reasoning": ["o3", "o1", "thinking", "reasoning", "deepseek-r1", "qwq"],
        "coding": ["coder", "code", "starcoder", "deepseek-coder", "qwen2.5-coder"],
        "vision": ["vision", "llava", "pixtral", "gpt-4o", "claude-3", "gemini", "qwen2-vl", "qwen2.5-vl"],
        "fast": ["flash", "mini", "haiku", "8b", "7b", "3b", "1.5b", "nano"],
        "free": [":free"],
    }

    _POPULAR_PREFIXES = [
        "openai/gpt-4o", "openai/gpt-4.1", "anthropic/claude", "google/gemini",
        "deepseek/deepseek", "meta-llama/llama", "qwen/qwen",
        "mistral/mistral", "x-ai/grok", "nvidia/nemotron",
    ]

    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url
        self._all_models: list[dict] | None = None

    def _fetch_all(self) -> list[dict]:
        if self._all_models is not None:
            return self._all_models
        try:
            resp = requests.get(
                f"{self.base_url}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=15,
            )
            if resp.status_code == 200:
                self._all_models = resp.json().get("data", [])
                print(f"[ModelCatalog] Fetched {len(self._all_models)} models from OpenRouter")
            else:
                self._all_models = []
        except Exception as e:
            print(f"[ModelCatalog] Fetch error: {_sanitize_error(e)}")
            self._all_models = []
        return self._all_models

    def _categorize(self, model: dict) -> list[str]:
        mid = model.get("id", "").lower()
        cats = []
        for cat, keywords in self._CATEGORY_KEYWORDS.items():
            if any(kw in mid for kw in keywords):
                cats.append(cat)
        if not cats:
            cats.append("chat")
        return cats

    def _is_popular(self, model_id: str) -> bool:
        lower = model_id.lower()
        return any(lower.startswith(p) for p in self._POPULAR_PREFIXES)

    def _model_summary(self, m: dict) -> dict:
        pricing = m.get("pricing", {})
        prompt_price = pricing.get("prompt", "?")
        comp_price = pricing.get("completion", "?")
        # OpenRouter returns per-token prices; convert to per-1M-tokens for display
        try:
            prompt_price = round(float(prompt_price) * 1_000_000, 6)
        except (ValueError, TypeError):
            pass
        try:
            comp_price = round(float(comp_price) * 1_000_000, 6)
        except (ValueError, TypeError):
            pass
        return {
            "id": m.get("id", ""),
            "name": m.get("name", m.get("id", "")),
            "context_length": m.get("context_length", "?"),
            "prompt_price": prompt_price,
            "completion_price": comp_price,
            "categories": self._categorize(m),
            "is_free": ":free" in m.get("id", ""),
            "supported_parameters": m.get("supported_parameters", []),
        }

    def get_recommended(self, limit_per_cat: int = 0) -> dict[str, list[dict]]:
        """Return models grouped by category, sorted by popularity then price."""
        all_models = self._fetch_all()
        by_cat: dict[str, list[dict]] = {}
        for m in all_models:
            summary = self._model_summary(m)
            for cat in summary["categories"]:
                by_cat.setdefault(cat, []).append(summary)

        result = {}
        for cat, models in by_cat.items():
            models.sort(key=lambda x: (not self._is_popular(x["id"]), x.get("prompt_price", "999") if x.get("prompt_price") != "?" else "999"))
            result[cat] = models if limit_per_cat <= 0 else models[:limit_per_cat]
        return result

    def search(self, query: str, limit: int = 0) -> list[dict]:
        """Search models by keyword."""
        all_models = self._fetch_all()
        q = query.lower().strip()
        if not q:
            return []
        results = []
        for m in all_models:
            mid = m.get("id", "").lower()
            mname = m.get("name", "").lower()
            if q in mid or q in mname:
                results.append(self._model_summary(m))
        return results if limit <= 0 else results[:limit]

    def get_all(self, limit: int = 100) -> list[dict]:
        """Return all models (limited)."""
        all_models = self._fetch_all()
        return [self._model_summary(m) for m in all_models[:limit]]

