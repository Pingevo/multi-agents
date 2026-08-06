"""FreeModelRotator — fallback through free model ranking when openrouter/free fails."""

import re
import time
import requests
from crewai import LLM
from backend.utils import _sanitize_error
from backend.ai_usage_hub import log_ai_usage


class FreeModelRotator:
    """Rotates through free model ranking when openrouter/free fails.

    Ranking is fetched dynamically from the OpenRouter catalog (No Hardcode)
    — only models with ':free' suffix that currently exist are included,
    sorted by context_length descending so the smartest model is tried first.

    Falls back to a small static list only if the catalog fetch fails (e.g.
    network error). This prevents 404s when OpenRouter retires free slugs
    (issue #125: deepseek-r1:free, llama-3.3-70b:free, etc. were retired).
    """

    # Fallback only — used when catalog fetch fails. Kept short on purpose:
    # if these also 404, the rotator reports failure and the caller surfaces
    # the error rather than silently retrying with stale slugs.
    _FALLBACK_RANKING = [
        "google/gemini-2.0-flash-exp:free",
        "meta-llama/llama-3.2-3b-instruct:free",
    ]

    def __init__(self, api_key: str, base_url: str, temperature: float = 0.7,
                 catalog=None):
        # catalog: injectable for tests — an object with get_models() -> list[dict]
        # mimicking OpenRouter /models response. None = fetch from API at runtime.
        self.api_key = api_key
        self.base_url = base_url
        self.temperature = temperature
        self._catalog = catalog
        self._ranking_cache: list[str] | None = None

    def _fetch_catalog_models(self) -> list[dict]:
        """Fetch models from injected catalog or OpenRouter /models endpoint."""
        if self._catalog is not None:
            return self._catalog.get_models()
        try:
            resp = requests.get(
                f"{self.base_url.rstrip('/')}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=15,
            )
            if resp.status_code == 200:
                return resp.json().get("data", [])
        except Exception as e:
            print(f"[FreeModelRotator] Failed to fetch catalog: {_sanitize_error(e)}", flush=True)
        return []

    def get_ranking(self) -> list[str]:
        """Return free model slugs that currently exist in the catalog.

        Filters for ':free' suffix, excludes openrouter/ routing models,
        sorts by context_length descending (smartest first).

        Empty catalog (no models returned) → empty list (caller handles).
        Fetch failure (network error) → falls back to _FALLBACK_RANKING.
        """
        if self._ranking_cache is not None:
            return list(self._ranking_cache)

        all_models = self._fetch_catalog_models()
        # Distinguish "fetch failed" (None) from "catalog empty" ([])
        # _fetch_catalog_models returns [] for both — use a sentinel for fetch failure
        # Simpler: if catalog is injected and returns [], that's a real empty catalog.
        # If fetch from API fails, _fetch_catalog_models already printed and returns [].
        # In that case, fall back so we don't silently break free-model retry.
        if not all_models and self._catalog is None:
            # API fetch failed (or returned empty) — use fallback as safety net
            self._ranking_cache = list(self._FALLBACK_RANKING)
            return list(self._ranking_cache)

        free_models = []
        for m in all_models:
            mid = m.get("id", "")
            if ":free" not in mid:
                continue
            if mid.startswith("openrouter/"):
                continue
            free_models.append({
                "id": mid,
                "context_length": m.get("context_length", 0) or 0,
            })

        # Sort by context_length descending — smartest (largest context) first
        free_models.sort(key=lambda m: m["context_length"], reverse=True)
        self._ranking_cache = [m["id"] for m in free_models]
        return list(self._ranking_cache)

    def get_models(self) -> list[str]:
        """Alias for get_ranking — used by ModelSelector."""
        return self.get_ranking()

    def get_model_details(self) -> list[dict]:
        """Return model details for ModelSelector. Uses dynamic ranking with minimal info."""
        return [
            {"id": mid, "context_length": 131072, "pricing": {"prompt": "0", "completion": "0"}, "description": mid}
            for mid in self.get_ranking()
        ]

    def pick_smartest_model(self) -> str:
        """Return the smartest model from the ranking (first entry)."""
        models = self.get_ranking()
        return models[0] if models else ""

    def build_crewai_llm(self, model_id: str, max_tokens: int = 8192) -> LLM:
        """Build a CrewAI LLM object for a specific free model."""
        return LLM(
            model=f"openrouter/{model_id}",
            base_url=self.base_url,
            api_key=self.api_key,
            temperature=self.temperature,
            max_retries=0,
            stream=True,
            max_tokens=max_tokens,
        )

    def call(self, prompt: str, max_attempts: int = 4, caller: str = "rotator") -> str:
        """Try free models in ranking order. Raises RuntimeError after all attempts fail."""
        models = self.get_ranking()
        if not models:
            raise RuntimeError("No free models available")

        tried: set[str] = set()
        backoff = 0.5
        for attempt in range(1, min(max_attempts, len(models)) + 1):
            available = [m for m in models if m not in tried]
            if not available:
                break
            model_id = available[0]
            tried.add(model_id)

            try:
                from openai import OpenAI
                client = OpenAI(base_url=self.base_url, api_key=self.api_key, max_retries=0, timeout=120)
                started_at = time.time()
                response = client.chat.completions.create(
                    model=model_id,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=self.temperature,
                    max_tokens=8192,
                )
                usage = response.usage.model_dump() if response.usage and hasattr(response.usage, "model_dump") else (response.usage or {})
                log_ai_usage({
                    "provider": "openrouter",
                    "model": model_id,
                    "operation": "chat.completions",
                    "source": caller,
                    "status": "success",
                    "prompt_tokens": usage.get("prompt_tokens"),
                    "completion_tokens": usage.get("completion_tokens"),
                    "cost_usd": usage.get("cost"),
                    "duration_ms": int((time.time() - started_at) * 1000),
                    "attempt": attempt,
                    "raw_usage": usage,
                    "request_id": getattr(response, "id", None),
                    "metadata": {"analysis_type": "chat"},
                })
                print(f"[FreeModelRotator] Succeeded on attempt {attempt} with {model_id}", flush=True)
                return response.choices[0].message.content or ""
            except Exception as e:
                err_msg = _sanitize_error(e)
                log_ai_usage({
                    "provider": "openrouter",
                    "model": model_id,
                    "operation": "chat.completions",
                    "source": caller,
                    "status": "error",
                    "error_message": err_msg,
                    "duration_ms": int((time.time() - started_at) * 1000),
                    "attempt": attempt,
                    "metadata": {"analysis_type": "chat"},
                })
                print(f"[FreeModelRotator] Attempt {attempt}/{max_attempts} with {model_id}: {err_msg}", flush=True)
                if attempt < max_attempts:
                    time.sleep(backoff)
                    backoff *= 2

        raise RuntimeError(f"All {max_attempts} free model attempts failed")

    # Free models that support vision/multimodal input — fetched dynamically from API
    _vision_free_models_cache: list[str] | None = None

    # Models that look like vision models but can't generate structured output
    _VISION_BLOCKLIST = {
        "nvidia/nemotron-3.5-content-safety:free",
        "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
        "nvidia/nemotron-nano-12b-v2-vl:free",
        "openai/gpt-oss-120b:free",
    }

    # Preferred vision models — tried first if available
    _VISION_PREFERRED = [
        "google/gemini-2.0-flash-exp:free",
        "google/gemma-4-31b-it:free",
        "google/gemma-4-26b-a4b-it:free",
        "meta-llama/llama-3.2-90b-vision-instruct:free",
        "meta-llama/llama-4-scout:free",
        "qwen/qwen2.5-vl-72b-instruct:free",
        "qwen/qwen2-vl-72b-instruct:free",
    ]

    def _fetch_vision_free_models(self) -> list[str]:
        """Fetch free models that support image input from OpenRouter API."""
        if self._vision_free_models_cache is not None:
            return self._vision_free_models_cache
        try:
            resp = requests.get(
                f"{self.base_url.rstrip('/')}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=15,
            )
            if resp.status_code == 200:
                all_models = resp.json().get("data", [])
                vision_free = []
                for m in all_models:
                    mid = m.get("id", "")
                    if ":free" not in mid:
                        continue
                    if mid.startswith("openrouter/"):
                        continue
                    if mid in self._VISION_BLOCKLIST:
                        continue
                    arch = m.get("architecture", {})
                    if "image" in arch.get("input_modalities", []):
                        vision_free.append(mid)
                # Sort: preferred models first, then the rest
                vision_free.sort(key=lambda m: (
                    0 if m in self._VISION_PREFERRED else 1,
                    self._VISION_PREFERRED.index(m) if m in self._VISION_PREFERRED else 999
                ))
                self._vision_free_models_cache = vision_free
                print(f"[FreeModelRotator] Discovered {len(vision_free)} free vision models: {vision_free}", flush=True)
                return vision_free
        except Exception as e:
            print(f"[FreeModelRotator] Failed to fetch vision models: {_sanitize_error(e)}", flush=True)
        # Fallback to known model if API fails
        self._vision_free_models_cache = ["google/gemini-2.0-flash-exp:free"]
        return self._vision_free_models_cache

    def call_with_image(self, prompt: str, image_data_url: str, max_attempts: int = 3, caller: str = "rotator_vision") -> str:
        """Try vision-capable free models for image input."""
        from openai import OpenAI

        models = self._fetch_vision_free_models()
        if not models:
            raise RuntimeError("No free vision models available")
        tried: set[str] = set()
        backoff = 0.5

        for attempt in range(1, min(max_attempts, len(models)) + 1):
            available = [m for m in models if m not in tried]
            if not available:
                break
            model_id = available[0]
            tried.add(model_id)

            try:
                client = OpenAI(base_url=self.base_url, api_key=self.api_key, max_retries=0, timeout=120)
                started_at = time.time()
                response = client.chat.completions.create(
                    model=model_id,
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": image_data_url}},
                        ],
                    }],
                    temperature=self.temperature,
                    max_tokens=8192,
                )
                usage = response.usage.model_dump() if response.usage and hasattr(response.usage, "model_dump") else (response.usage or {})
                log_ai_usage({
                    "provider": "openrouter",
                    "model": model_id,
                    "operation": "chat.completions",
                    "source": caller,
                    "status": "success",
                    "prompt_tokens": usage.get("prompt_tokens"),
                    "completion_tokens": usage.get("completion_tokens"),
                    "cost_usd": usage.get("cost"),
                    "duration_ms": int((time.time() - started_at) * 1000),
                    "attempt": attempt,
                    "raw_usage": usage,
                    "request_id": getattr(response, "id", None),
                    "metadata": {"analysis_type": "chat"},
                })
                print(f"[FreeModelRotator] Vision succeeded on attempt {attempt} with {model_id}", flush=True)
                return response.choices[0].message.content or ""
            except Exception as e:
                err_msg = _sanitize_error(e)
                log_ai_usage({
                    "provider": "openrouter",
                    "model": model_id,
                    "operation": "chat.completions",
                    "source": caller,
                    "status": "error",
                    "error_message": err_msg,
                    "duration_ms": int((time.time() - started_at) * 1000),
                    "attempt": attempt,
                    "metadata": {"analysis_type": "chat"},
                })
                print(f"[FreeModelRotator] Vision attempt {attempt}/{max_attempts} with {model_id}: {err_msg}", flush=True)
                if attempt < max_attempts:
                    time.sleep(backoff)
                    backoff *= 2

        raise RuntimeError(f"All {max_attempts} vision model attempts failed")

    def call_with_multimodal(self, prompt: str, content_blocks: list[dict], plugins: list = None, max_attempts: int = 3, caller: str = "rotator_multimodal") -> str:
        """Try vision-capable free models for multimodal content."""
        from openai import OpenAI

        models = self._fetch_vision_free_models()
        if not models:
            raise RuntimeError("No free vision models available")
        tried: set[str] = set()
        backoff = 0.5

        for attempt in range(1, min(max_attempts, len(models)) + 1):
            available = [m for m in models if m not in tried]
            if not available:
                break
            model_id = available[0]
            tried.add(model_id)

            try:
                client = OpenAI(base_url=self.base_url, api_key=self.api_key, max_retries=0, timeout=120)
                started_at = time.time()
                messages = [{"role": "user", "content": [{"type": "text", "text": prompt}] + content_blocks}]
                kwargs = {"model": model_id, "messages": messages, "temperature": self.temperature, "max_tokens": 8192}
                if plugins:
                    kwargs["extra_body"] = {"plugins": plugins}
                response = client.chat.completions.create(**kwargs)
                usage = response.usage.model_dump() if response.usage and hasattr(response.usage, "model_dump") else (response.usage or {})
                log_ai_usage({
                    "provider": "openrouter",
                    "model": model_id,
                    "operation": "chat.completions",
                    "source": caller,
                    "status": "success",
                    "prompt_tokens": usage.get("prompt_tokens"),
                    "completion_tokens": usage.get("completion_tokens"),
                    "cost_usd": usage.get("cost"),
                    "duration_ms": int((time.time() - started_at) * 1000),
                    "attempt": attempt,
                    "raw_usage": usage,
                    "request_id": getattr(response, "id", None),
                    "metadata": {"analysis_type": "chat"},
                })
                print(f"[FreeModelRotator] Multimodal succeeded on attempt {attempt} with {model_id}", flush=True)
                return response.choices[0].message.content or ""
            except Exception as e:
                err_msg = _sanitize_error(e)
                log_ai_usage({
                    "provider": "openrouter",
                    "model": model_id,
                    "operation": "chat.completions",
                    "source": caller,
                    "status": "error",
                    "error_message": err_msg,
                    "duration_ms": int((time.time() - started_at) * 1000),
                    "attempt": attempt,
                    "metadata": {"analysis_type": "chat"},
                })
                print(f"[FreeModelRotator] Multimodal attempt {attempt}/{max_attempts} with {model_id}: {err_msg}", flush=True)
                if attempt < max_attempts:
                    time.sleep(backoff)
                    backoff *= 2

        raise RuntimeError(f"All {max_attempts} multimodal model attempts failed")

    def call_streaming(self, prompt: str, max_attempts: int = 4, caller: str = "rotator"):
        """Streaming version of call() — yields text chunks as they arrive."""
        from openai import OpenAI

        models = self.get_ranking()
        if not models:
            raise RuntimeError("No free models available")

        tried: set[str] = set()

        for attempt in range(1, min(max_attempts, len(models)) + 1):
            available = [m for m in models if m not in tried]
            if not available:
                break
            model_id = available[0]
            tried.add(model_id)

            try:
                client = OpenAI(base_url=self.base_url, api_key=self.api_key, max_retries=0, timeout=120)
                started_at = time.time()
                stream = client.chat.completions.create(
                    model=model_id,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=self.temperature,
                    max_tokens=8192,
                    stream=True,
                    stream_options={"include_usage": True},
                )
                usage_data = None
                _stream_id = None
                for chunk in stream:
                    if chunk.usage:
                        usage_data = chunk.usage
                    if hasattr(chunk, "id") and chunk.id:
                        _stream_id = chunk.id
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
                if usage_data:
                    usage = usage_data.model_dump() if hasattr(usage_data, "model_dump") else (usage_data or {})
                    log_ai_usage({
                        "provider": "openrouter",
                        "model": model_id,
                        "operation": "chat.completions",
                        "source": caller,
                        "status": "success",
                        "prompt_tokens": usage.get("prompt_tokens"),
                        "completion_tokens": usage.get("completion_tokens"),
                        "cost_usd": usage.get("cost"),
                        "duration_ms": int((time.time() - started_at) * 1000),
                        "attempt": attempt,
                        "raw_usage": usage,
                        "request_id": _stream_id if "_stream_id" in locals() else None,
                        "metadata": {"analysis_type": "chat"},
                    })
                else:
                    log_ai_usage({
                        "provider": "openrouter",
                        "model": model_id,
                        "operation": "chat.completions",
                        "source": caller,
                        "status": "success",
                        "duration_ms": int((time.time() - started_at) * 1000),
                        "attempt": attempt,
                        "request_id": _stream_id if "_stream_id" in locals() else None,
                        "metadata": {"analysis_type": "chat", "note": "stream omitted usage"},
                    })
                print(f"[FreeModelRotator] Stream succeeded on attempt {attempt} with {model_id}", flush=True)
                return
            except Exception as e:
                err_msg = _sanitize_error(e)
                log_ai_usage({
                    "provider": "openrouter",
                    "model": model_id,
                    "operation": "chat.completions",
                    "source": caller,
                    "status": "error",
                    "error_message": err_msg,
                    "duration_ms": int((time.time() - started_at) * 1000),
                    "attempt": attempt,
                    "metadata": {"analysis_type": "chat"},
                })
                print(f"[FreeModelRotator] Stream attempt {attempt}/{max_attempts} with {model_id}: {err_msg}", flush=True)
                continue

        raise RuntimeError(f"All {max_attempts} streaming attempts failed")
