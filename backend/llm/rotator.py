"""FreeModelRotator — deprecated, kept for backward compatibility."""

import random
import re
import requests
from crewai import LLM
from backend.utils import _sanitize_error

class FreeModelRotator:
    """DEPRECATED: Use OpenRouter routing models (openrouter/auto, openrouter/free) instead.
    Kept for backward compatibility — will be removed in future cleanup.
    """
    """Fetches models from OpenRouter and rotates through them on failure.

    When free_only=True (default): fetches only :free models.
    When free_only=False (paid tier): fetches all tool-capable large models.
    """

    def __init__(self, api_key: str, base_url: str, temperature: float = 0.7, free_only: bool = True):
        self.api_key = api_key
        self.base_url = base_url
        self.temperature = temperature
        self.free_only = free_only
        self._models: list[str] | None = None
        self._model_details: list[dict] | None = None

    _SMALL_KEYWORDS = ("mini", "nano", "xs", "tiny", "small")
    _NON_CHAT_KEYWORDS = ("content-safety", "guard", "moderation", "safety")
    _MIN_PARAMS_BILLION = 20.0

    def _parse_param_count(self, model_id: str) -> float | None:
        import re
        match = re.search(r"(\d+\.?\d*)b\b", model_id.lower())
        return float(match.group(1)) if match else None

    def _is_large_model(self, model_id: str) -> bool:
        lower = model_id.lower()
        if any(kw in lower for kw in self._SMALL_KEYWORDS):
            return False
        if any(kw in lower for kw in self._NON_CHAT_KEYWORDS):
            return False
        params = self._parse_param_count(model_id)
        if params is not None:
            return params >= self._MIN_PARAMS_BILLION
        return True

    def _fetch_free_models(self) -> list[str]:
        """Fetch only :free models from OpenRouter API, filtered to large chat models."""
        try:
            resp = requests.get(
                f"{self.base_url}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=15,
            )
            if resp.status_code != 200:
                print(f"[FreeModelRotator] API returned {resp.status_code}")
                return []
            data = resp.json().get("data", [])
            free_models = [m for m in data if ":free" in m.get("id", "")]
            large_models = [m for m in free_models if self._is_large_model(m["id"])]
            print(f"[FreeModelRotator] {len(free_models)} free models, {len(large_models)} after size filter")
            self._model_details = large_models
            return [m["id"] for m in large_models]
        except Exception as e:
            print(f"[FreeModelRotator] Fetch error: {_sanitize_error(e)}")
            return []

    def _fetch_models(self) -> list[str]:
        """Fetch models from OpenRouter API, filtered to large models that support tool use."""
        try:
            resp = requests.get(
                f"{self.base_url}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=15,
            )
            if resp.status_code != 200:
                print(f"[FreeModelRotator] API returned {resp.status_code}")
                return []
            data = resp.json().get("data", [])
            if self.free_only:
                data = [m for m in data if ":free" in m.get("id", "")]
            tool_capable = [m for m in data if "tools" in m.get("supported_parameters", [])]
            large_models = [m for m in tool_capable if self._is_large_model(m["id"])]
            if self.free_only:
                print(f"[FreeModelRotator] {len(data)} free models, {len(tool_capable)} tool-capable, {len(large_models)} after size filter")
            else:
                large_models.sort(key=lambda m: self._parse_param_count(m["id"]) or 0, reverse=True)
                print(f"[FreeModelRotator] {len(data)} total models, {len(tool_capable)} tool-capable, {len(large_models)} after size filter")
            self._model_details = large_models
            return [m["id"] for m in large_models]
        except Exception as e:
            print(f"[FreeModelRotator] Fetch error: {_sanitize_error(e)}")
            return []

    def get_models(self) -> list[str]:
        """Return models list, fetching on first call."""
        if self._models is None:
            self._models = self._fetch_models()
        return self._models

    def get_model_details(self) -> list[dict]:
        """Return full model metadata list (for candidate table)."""
        if self._model_details is None:
            self.get_models()
        return self._model_details or []

    def pick_model(self) -> str:
        """Pick a random free model."""
        models = self.get_models()
        return random.choice(models) if models else ""

    def pick_smartest_model(self) -> str:
        """Pick the largest model by parameter count (for critical decisions like assess)."""
        models = self.get_models()
        if not models:
            return ""
        return max(models, key=lambda m: self._parse_param_count(m) or 0)

    def call(self, prompt: str, max_attempts: int = 4) -> str:
        """Try free models largest-first, then random. Raises RuntimeError after all attempts fail."""
        import time

        models = self.get_models()
        if not models:
            raise RuntimeError("No free models available")

        # Sort by parameter count descending — try smartest first
        sorted_models = sorted(models, key=lambda m: self._parse_param_count(m) or 0, reverse=True)

        tried: set[str] = set()
        backoff = 0.5
        for attempt in range(1, max_attempts + 1):
            available = [m for m in sorted_models if m not in tried]
            if not available:
                tried.clear()
                available = sorted_models
            model_id = available[0]  # largest available first
            tried.add(model_id)

            try:
                import app as _app
                _LLM = getattr(_app, "LLM", LLM)
                llm = _LLM(
                    model=f"openrouter/{model_id}",
                    base_url=self.base_url,
                    api_key=self.api_key,
                    temperature=self.temperature,
                    max_retries=0,
                )
                result = llm.call(prompt)
                if attempt > 1:
                    print(f"[FreeModelRotator] Succeeded on attempt {attempt} with {model_id}")
                return result
            except Exception as e:
                print(f"[FreeModelRotator] Attempt {attempt}/{max_attempts} with {model_id}: {_sanitize_error(e)}")
                if attempt < max_attempts:
                    time.sleep(backoff)
                    backoff *= 2

        raise RuntimeError(f"All {max_attempts} attempts failed")

    def call_streaming(self, prompt: str, max_attempts: int = 4):
        """Streaming version of call() — yields text chunks as they arrive."""
        from openai import OpenAI

        models = self.get_models()
        if not models:
            raise RuntimeError("No free models available")

        sorted_models = sorted(models, key=lambda m: self._parse_param_count(m) or 0, reverse=True)
        tried: set[str] = set()

        for attempt in range(1, max_attempts + 1):
            available = [m for m in sorted_models if m not in tried]
            if not available:
                tried.clear()
                available = sorted_models
            model_id = available[0]
            tried.add(model_id)

            try:
                client = OpenAI(base_url=self.base_url, api_key=self.api_key, max_retries=0)
                stream = client.chat.completions.create(
                    model=model_id,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=self.temperature,
                    stream=True,
                )
                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
                return
            except Exception as e:
                print(f"[FreeModelRotator] Stream attempt {attempt}/{max_attempts} with {model_id}: {_sanitize_error(e)}")
                continue

        raise RuntimeError(f"All {max_attempts} streaming attempts failed")
