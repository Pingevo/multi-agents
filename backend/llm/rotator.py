"""FreeModelRotator — fallback through free model ranking when openrouter/free fails."""

import re
import time
import requests
from crewai import LLM
from backend.utils import _sanitize_error
from backend.credit_logger import log_llm_call


class FreeModelRotator:
    """Rotates through free model ranking when openrouter/free fails.

    Ranking is from best (smartest/largest) to worst (smallest/least capable).
    Only used when the selected model is 'openrouter/free'.
    """

    # Hardcoded ranking — best to worst, tried in order
    _FREE_MODEL_RANKING = [
        "deepseek/deepseek-r1:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "qwen/qwen3-coder:free",
        "openai/gpt-oss-120b:free",
        "nousresearch/hermes-3-llama-3.1-405b:free",
        "google/gemini-2.0-flash-exp:free",
        "mistralai/mistral-nemo:free",
        "meta-llama/llama-3.2-3b-instruct:free",
    ]

    def __init__(self, api_key: str, base_url: str, temperature: float = 0.7):
        self.api_key = api_key
        self.base_url = base_url
        self.temperature = temperature

    def get_ranking(self) -> list[str]:
        """Return the hardcoded free model ranking."""
        return list(self._FREE_MODEL_RANKING)

    def get_models(self) -> list[str]:
        """Alias for get_ranking — used by ModelSelector."""
        return self.get_ranking()

    def get_model_details(self) -> list[dict]:
        """Return model details for ModelSelector. Uses hardcoded ranking with minimal info."""
        return [
            {"id": mid, "context_length": 131072, "pricing": {"prompt": "0", "completion": "0"}, "description": mid}
            for mid in self._FREE_MODEL_RANKING
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
                response = client.chat.completions.create(
                    model=model_id,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=self.temperature,
                    max_tokens=8192,
                )
                log_llm_call(model_id, response.usage, caller=f"{caller}:attempt{attempt}", prompt_preview=prompt)
                print(f"[FreeModelRotator] Succeeded on attempt {attempt} with {model_id}", flush=True)
                return response.choices[0].message.content or ""
            except Exception as e:
                print(f"[FreeModelRotator] Attempt {attempt}/{max_attempts} with {model_id}: {_sanitize_error(e)}", flush=True)
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
                log_llm_call(model_id, response.usage, caller=f"{caller}:attempt{attempt}", prompt_preview=prompt)
                print(f"[FreeModelRotator] Vision succeeded on attempt {attempt} with {model_id}", flush=True)
                return response.choices[0].message.content or ""
            except Exception as e:
                print(f"[FreeModelRotator] Vision attempt {attempt}/{max_attempts} with {model_id}: {_sanitize_error(e)}", flush=True)
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
                messages = [{"role": "user", "content": [{"type": "text", "text": prompt}] + content_blocks}]
                kwargs = {"model": model_id, "messages": messages, "temperature": self.temperature, "max_tokens": 8192}
                if plugins:
                    kwargs["extra_body"] = {"plugins": plugins}
                response = client.chat.completions.create(**kwargs)
                log_llm_call(model_id, response.usage, caller=f"{caller}:attempt{attempt}", prompt_preview=prompt)
                print(f"[FreeModelRotator] Multimodal succeeded on attempt {attempt} with {model_id}", flush=True)
                return response.choices[0].message.content or ""
            except Exception as e:
                print(f"[FreeModelRotator] Multimodal attempt {attempt}/{max_attempts} with {model_id}: {_sanitize_error(e)}", flush=True)
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
                stream = client.chat.completions.create(
                    model=model_id,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=self.temperature,
                    max_tokens=8192,
                    stream=True,
                    stream_options={"include_usage": True},
                )
                usage_data = None
                for chunk in stream:
                    if chunk.usage:
                        usage_data = chunk.usage
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
                if usage_data:
                    log_llm_call(model_id, usage_data, caller=f"{caller}:stream:attempt{attempt}", prompt_preview=prompt)
                print(f"[FreeModelRotator] Stream succeeded on attempt {attempt} with {model_id}", flush=True)
                return
            except Exception as e:
                print(f"[FreeModelRotator] Stream attempt {attempt}/{max_attempts} with {model_id}: {_sanitize_error(e)}", flush=True)
                continue

        raise RuntimeError(f"All {max_attempts} streaming attempts failed")
