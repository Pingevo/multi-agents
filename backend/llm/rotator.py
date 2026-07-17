"""FreeModelRotator — fallback through hardcoded free model ranking when openrouter/free fails."""

import re
import time
import requests
from crewai import LLM
from backend.utils import _sanitize_error
from backend.credit_logger import log_llm_call


class FreeModelRotator:
    """Rotates through hardcoded free model ranking when openrouter/free fails.

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
